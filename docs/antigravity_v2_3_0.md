# Antigravity 実行指示書: 収益最大化・構造的ボトルネック解消＆営業自動化アップデート (v2.3.0 厳格監査版)

> **対象システム**: AdFeed Clean: Google Shopping (`safemedia-shield-worker`)  
> **作成日**: 2026-10-25  
> **目的**: 事業収益性検証および技術・市場ファクト監査により特定された「GMC連携の技術的断絶」「大規模カタログでのAPIタイムアウト」「タダ乗り（解約後利用・トライアル乱用）」「GPU逆ザヤリスク」「SMB価格障壁」「営業ファネルの非現実性」をすべて解消し、100%ファクトと実現性に基づいた収益化基盤を完成させる。  
> **最重要制約（審査保護ルール）**:  
> 1. 既存のセキュリティガード（7層SSRF、HMAC検証、Anti-TOCTOU、テナント分離）および非破壊デュアルフィードのコアロジックは一切劣化させず、全自動テスト（E2E）の100% PASSを維持すること。  
> 2. 現在Shopify App Store審査期間中であるため、コード改修およびローカルテスト（`tests/`）の完全検証までを直ちに完了させ、**本番環境への `wrangler deploy` は審査通過確定の直後に実行できるよう待機（または別名ステージングWorkerへデプロイ）すること**。

---

## 1. ファクトに基づく6大構造課題と解決アーキテクチャ

1. **【技術ファクト】GMC連携のラストワンマイルと「R2インデックス型TSV高速配信」**:
   - **事実**: Shopify公式「Google & YouTube」アプリにはカスタムメタフィールドを画像にマッピングする機能が存在しない。また、GMCがサプリメンタルフィード（TSV）をフェッチする際、都度Shopify GraphQL APIを全件ページネーション取得すると、商品数1,000件以上の店舗でWorkersがタイムアウトし破綻する。さらに、最新の「Google Merchant Center Next」では初期状態で補助フィード設定が非表示（Add-on化）になっている。
   - **解決策**: AIクリーンアップ実行時（Webhook / Batch）にR2内の軽量インデックス（`feeds/{shop}/index.json`）へ商品ID・全バリアントID・クリーン画像URLを保存し、**TSVリクエスト時はShopify APIを一切叩かずR2からミリ秒単位で動的生成して返却する仕組み**を実装する。UIには「GMC Nextでのアドオン有効化3ステップ」と「国コード（US/JP/GB等）選択機能」を実装する。
2. **【技術・規約ファクト】解約後のタダ乗り防止と「GMCクローラー仕様準拠（HTTP 404/410）」**:
   - **事実**: 初月やトライアル中だけ一括処理して即解約しても画像URLが生き続けるとLTVが崩壊する。一方、解約後の画像アクセスに `402 Payment Required` を返すと、Googlebot（GMC画像クローラー）が異常ステータスとして再試行ループに陥る。また、警告なしに即座にリンク切れにするとマーチャントから★1レビューを書かれるリスクがある。
   - **解決策**: アンインストール後または課金失効後の `/clean-media/:shop/*` および `/feeds/:shop/*` へのアクセスには、クローラー標準規格である **HTTP `404 Not Found`（または `410 Gone`）** を返却する。また、ダッシュボードおよび利用規約（`/terms`）に「解約時はGMC側の補助フィード設定を解除してください（解約後は配信停止されます）」と明確に事前告知する。
3. **【Shopify API仕様ファクト】トライアル中50枚キャップと「日時ベース自動昇格ロジック」**:
   - **事実**: トライアル開始直後に10,000件を一括処理して解約される「GPUコスト持ち逃げ」を防ぐにはトライアル中の処理上限（50枚）が必須である。しかし、Shopify Billing APIは「14日間のトライアルが終了して初回課金に移行した瞬間」にWebhookを送信しない（ステータスは初回承認時から一貫して `ACTIVE`）。
   - **解決策**: サブスクリプション承認時に `activatedAt` と `trialEndsAt`（`activatedAt + 14 days`）をR2に記録する。リクエスト処理時に **`Date.now() < Date.parse(trialEndsAt)` であればトライアル上限（50枚）を適用し、`trialEndsAt` 経過後は自動的に本プラン上限（Starter 100枚 / Pro 500枚）へ昇格させる確定ロジック**を実装する。
4. **【財務ファクト】2段階プラン（$19 / $65）とPre-Flight従量課金サーキットブレーカー**:
   - **事実**: 競合フィードアプリが月額$5〜$29である中、$65単一プランではSMB層が導入を躊躇し初期レビューが集まらない。また、フラット課金では大規模店舗のバースト処理でGPU原価が逆ザヤになる。
   - **解決策**: **Starterプラン（$19/月・100枚内包）** と **Proプラン（$65/月・500枚内包）** の2段階とし、上限超過時はRunPod呼び出しの**直前**に `appUsageRecordCreate`（$0.05/枚）を叩くPre-Flight従量課金を実装する。
5. **【競合ファクト】Google純正「無料AI（自動画像改善）」との明確な差別化**:
   - **事実**: GMCには無料の「Automatic image improvements」が存在するため、違いを説明できなければ解約される。
   - **解決策**: 「Google標準AIは一度ポリシー違反で広告が停止（Disapproved）された後にしか動かず、大きなセール帯は修復失敗して放置される『事後処置』であるのに対し、AdFeed Cleanは審査落ちとアカウント評価低下を未然に防ぐ『事前予防の保険』である」というファクト比較表をUI・ストア説明文に明記する。
6. **【営業統計ファクト】スパムフィルタを回避する「承諾型（Permission-based）2ステップ営業」と実演画像生成**:
   - **事実**: 2026年現在、初回コールドメールにいきなり画像（PNG）を添付したりURLリンクを貼ると、Gmail/Outlookのスパムフィルタにより高確率で迷惑メールフォルダへ直行する。また、B2Bコールドメールの現実的な返信率は1〜3%、成約率は0.5〜1%である。
   - **解決策**:
     1. 営業メール1通目は**「添付なし・リンクなしの短文テキスト」**で「御社のセール帯付き商品画像をGMC審査通過用にAI白抜きしたサンプル画像を手元で作ってみたのですが、ここにお送りしてもよろしいでしょうか？」と尋ね、**返信（承諾）があった相手にのみ2通目で「Before/After比較画像」を送る2ステップ方式**をプレイブックに採用する。
     2. 返信が来た際に1コマンドで高品質なBefore/After比較カード（PNG）を生成できるスクリプト `scripts/generate_outreach_preview.py` を実装する。

---

## 2. 実装タスク一覧（Code, Scripts & Architecture Tasks）

### Task 1: R2インデックス型GMCサプリメンタルフィード（TSV）配信 ＆ 解約時404ロックの実装
Shopify APIのレート制限・タイムアウトを100%回避する高速TSV配信と、クローラー標準規格に準拠した配信ロックを実装する。

- **対象ファイル**:
  - `cloudflare_worker/src/feed.ts`（新規作成）
  - `cloudflare_worker/src/index.ts`（ルーティング更新・インデックス更新・配信ロック追加）
- **実装仕様**:
  1. **フィード用R2インデックスの自動維持 (`feeds/{shop}/index.json`)**:
     - カナリアテスト、Webhook自動同期、バッチ処理で商品のクリーン画像（`cleanAdImageUrl`）が生成された際、R2の `feeds/{shop}/index.json` に以下の構造で商品・バリアント情報をUPSERT保存する（ロールバック時は該当エントリを削除または復元）：
       ```typescript
       interface FeedIndexEntry {
         productId: string;        // 数値ID (例: "10352680632517")
         variantIds: string[];     // 全バリアントの数値ID配列 (例: ["4829101", "4829102"])
         cleanImageUrl: string;    // 公開クリーン画像URL
         updatedAt: string;
       }
       ```
  2. **超高速TSV動的配信エンドポイント (`GET /feeds/:shop/gmc-supplemental.tsv`)**:
     - **クエリパラメータ**:
       - `token`: テナント固有の読み取り専用トークン（`billingState.feedToken` と定数時間比較 `timingSafeEqual` で検証。不一致時は `403 Forbidden`）。
       - `country`: ターゲット国コード（正規表現 `/^[A-Z]{2}$/` で検証。デフォルト `US`、`JP`, `GB`, `CA`, `AU` 等に対応）。
       - `id_format`: `shopify`（デフォルト: `shopify_{COUNTRY}_{product_id}_{variant_id}`）、`variant_id`（`{variant_id}` のみ）、`product_id`（`{product_id}` のみ）。
     - **生成ロジック**:
       - R2から `feeds/{shop}/index.json` を読み出し（Shopify GraphQL APIは叩かないため0.05秒以内で応答可能）、ヘッダー `id\timage_link\n` に続けて全バリアント分の行（Fan-out）を出力する。
       - レスポンスヘッダー: `Content-Type: text/tab-separated-values; charset=utf-8`、`Cache-Control: public, max-age=300`。
  3. **解約後・未課金時のクローラー準拠配信ロック（HTTP 404 / 410）**:
     - `GET /feeds/:shop/gmc-supplemental.tsv` および `GET /clean-media/:shop/:filename` において、該当テナントの `auth.json`（`uninstalledAt` の有無）および `billing.json`（`planStatus`）を確認する。
     - アンインストール済み（`uninstalledAt` が設定済み）の場合は、Googlebotがリンク消滅を正常認識できるよう **HTTP `404 Not Found`（`{ "error": "Feed or media no longer active (App Uninstalled)", "code": "SUBSCRIPTION_INACTIVE" }`）** を返却する。

---

### Task 2: 2段階プラン・日時判定トライアル50枚上限・Pre-Flight従量課金の実装
Shopify Billing APIの仕様に完全準拠したトライアル期間判定と、Starter/Proの2段階ハイブリッド課金を実装する。

- **対象ファイル**:
  - `cloudflare_worker/src/shopify.ts`
  - `cloudflare_worker/src/index.ts`
- **新料金プラン＆クォータ仕様**:
  1. **Free Sample Preview (`CANARY_TRIAL`)**:
     - 無料サンプル **5枚** まで（一括処理不可）。
  2. **14-Day Free Trial (トライアル期間中: `Date.now() < Date.parse(trialEndsAt)`)**:
     - Starter または Pro プランの承認後14日間。
     - **トライアル期間中の保護キャップ**: トライアル期間中の累計AI処理上限を **50枚** に制限する（決済確定前の大量一括処理によるGPUタダ乗りを防止）。50枚に達した場合は `402 TRIAL_BATCH_LIMIT_REACHED` で一時停止し、「14日間のトライアル終了後（または即時本課金移行時）に残りの全カタログが処理可能になります」と案内する。
  3. **Starter Plan (`STARTER` / 月額 $19.00 USD)**:
     - トライアル期間終了後、月間 **100枚** までのAIクリーンアップを内包。
     - 超過従量課金: 101枚目以降 **$0.05 USD / 枚**（Capped Amount: **$50.00 USD**）。
  4. **Pro / Agency Plan (`PRO` / 月額 $65.00 USD)**:
     - トライアル期間終了後、月間 **500枚** までのAIクリーンアップを内包。
     - 超過従量課金: 501枚目以降 **$0.05 USD / 枚**（Capped Amount: **$100.00 USD**）。
- **実装ディテール**:
  1. `TenantBillingState` インターフェースの拡張（後方互換性を維持）:
     - `planTier?: "FREE_PREVIEW" | "STARTER" | "PRO"`
     - `trialEndsAt?: string`（サブスクリプション開始時に `new Date(Date.now() + 14 * 86400 * 1000).toISOString()` をセット）
     - `monthlyIncludedLimit?: number`（Starter=100, Pro=500）
     - `monthlyProcessedCount?: number`（当月処理枚数カウンタ）
     - `usageLineItemId?: string`
     - `cappedAmountReached?: boolean`
     - `feedToken?: string`（初回生成時にランダムな32文字hexトークンを発行・保存）
  2. **トライアル自動昇格ヘルパー関数 `getEffectiveMonthlyLimit(billingState)`**:
     - `planStatus === "TRIAL_14D_ACTIVE"` であっても、`trialEndsAt` が過去日時になっている場合は自動的に本課金状態（Starterなら100枚、Proなら500枚）として上限を返す。逆に `trialEndsAt` が未来日時であれば `50`（トライアル上限）を返す。
  3. **Pre-Flight Usage Charge（事前従量課金ガード）**:
     - 本課金期間中に `monthlyProcessedCount >= getEffectiveMonthlyLimit(billingState)` となった場合、RunPod GPUを呼び出す**直前**に `appUsageRecordCreate`（`$0.05 USD`、idempotencyKey付与）を実行する。Capped Amount到達時または課金失敗時は即座に `402 PAUSED_USAGE_CAP_REACHED` で遮断し、GPUコンテナを起動しない。

---

### Task 3: 管理ダッシュボードUI（GMC Nextガイド・2プラン選択・利用規約）の改修
導入店舗がGMC連携で迷わないUIと、2プラン選択、および法務告知を実装する。

- **対象ファイル**:
  - `cloudflare_worker/src/ui.ts`
  - `cloudflare_worker/src/legal.ts`
- **UI・法務改修要件**:
  1. **Zone 1 への「GMC連携セットアップウィザード（2タブ切替）」追加 (`ui.ts`)**:
     - **Tab A: Google & YouTube（公式アプリ）をご利用の場合【推奨・3分】**:
       - 専用のGMCサプリメンタルフィードURL表示ボックス ＋ **「📋 Copy Feed URL」ボタン** ＋ **「対象国コード選択（US / JP / GB / CA / AU）」プルダウン**（選択変更時にURLの `&country=XX` がリアルタイムに切り替わること）。
       - **GMC Next 迷子防止3ステップガイド**:
         1. Google Merchant Center Next を開き、`Settings (歯車) ➔ Add-ons` へ移動し、**「Advanced data source management（高度なデータソース管理）」を有効化**する。
         2. `Settings ➔ Data sources ➔ Supplemental sources` タブを開き、「Add supplemental product data」をクリック。
         3. 「Add product data from a file」を選択し、上記でコピーしたTSVフィードURLを貼り付けてスケジュール（毎日取得）を保存し、メインデータソースにリンクする。
     - **Tab B: Simprosys / DataFeedWatch 等のフィードアプリをご利用の場合**:
       - 各アプリの画像マッピング設定にて、カスタムメタフィールド `safemedia.clean_ad_image_url` を直接指定する手順を表示。
  2. **課金バー（`#billing-banner`）の2プラン選択＆クォータメーター化 (`ui.ts`)**:
     - `🚀 Starter Plan ($19/mo • 100 imgs)` と `🏢 Pro Plan ($65/mo • 500 imgs)` の選択ボタンを配置（既存の `#btn-start-trial` IDも互換性のため維持または適切にバインドすること）。
     - 処理枚数メーターを表示。
  3. **日英バイリンガル辞書（`I18N`）の完全同期 (`ui.ts`)**:
     - 追加したすべての文言キーを `en` と `ja` に100%対称で追加し、`test_m2_bilingual_parity.py` が100% PASS状態を維持すること。
  4. **利用規約への配信有効期間・解約時手順の明記 (`legal.ts`)**:
     - `/terms`（日英両方）に、「クリーン画像URLおよびGMCサプリメンタルフィードの配信は、有効なサブスクリプション期間中のみ提供されます。アンインストールまたは解約後はHTTP 404となり配信が停止されますので、解約前に必ずGMC側の補助フィード設定を解除してください」と明記する。

---

### Task 4: 「Before/After実演画像」自動生成営業スクリプトの新規実装
営業メールの2通目（承諾後）やSNS/LPで提示するための「Before/After比較ビジュアル」を1コマンドで生成できるCLIツールを作成する。

- **対象ファイル**:
  - `scripts/generate_outreach_preview.py`（新規作成）
- **スクリプト仕様**:
  - **引数**: `--image-url <画像URL>`、`--store-name <店舗名>`、`--output <出力PNGパス>`、`--demo`（外部通信やGPUなしで即座に合成テスト画像を生成できるセルフテストモード）。
  - **処理内容**:
    1. `--demo` 指定時はローカルでセール帯付きのBefore画像と、帯を消去したAfter画像を合成生成する。`--image-url` 指定時は画像をダウンロードし、ローカルまたはRunPod APIで白抜きAfter画像を生成する。
    2. Pillow (`PIL`) を用いて、1600x900px の高解像度ダークテーマ比較カード画像（PNG）を生成する：
       - 左側: **「Before: Storefront Image (High CVR, ❌ GMC Disapproved)」**
       - 右側: **「After: AdFeed Clean AI (✅ 100% GMC Compliant in ~5s)」**
       - 上部ヘッダーに `Prepared for {store_name}`、下部フッターに `Keep sale badges on Shopify. Send clean images to Google Shopping automatically.` を描画。

---

### Task 5: 営業プレイブック・ターゲットリスト・ストア申請資料のファクトベース刷新
楽観的な数値を排除し、現実のB2Bコンバージョン統計とスパム回避ルールに基づいたドキュメントへ全面刷新する。

- **対象ファイルと修正内容**:
  1. `GTM_GROWTH_PLAYBOOK.md`:
     - **現実的なファネル数値（逆算KPI）の設定**:
       - コールドアウトリーチの現実的な返信率（2〜4%）、トライアル導入率（1〜1.5%）、有料転換率（40〜50%）に基づき、**60日で20〜30社の導入を得るためのアクション母数（国内・海外合わせたターゲットリスト300〜500件へのアプローチ＋制作会社・代理店30社へのアプローチ）**を明記する。
     - **スパムフィルタを回避する「承諾型（Permission-based）2ステップ営業」**:
       - 1通目（初回連絡）は**「画像添付なし・URLリンクなしの短文プレーンテキスト」**とし、「御社の〇〇の商品画像のセール帯を、Googleショッピング審査通過用にAIで白抜きした比較サンプルを手元で作ってみたのですが、ご参考までにここにお送りしてもよろしいでしょうか？」とだけ尋ねるテンプレートへ変更する。
       - 2通目（返信が来た後）で、`scripts/generate_outreach_preview.py` で生成したBefore/After比較画像と14日間トライアルURLを送付するフローを確立する。
     - **GMC連携マニュアルの修正**: 公式「Google & YouTube」アプリでの誤ったメタフィールド手順を削除し、**「GMC Nextでのアドオン有効化＋サプリメンタルフィード（TSV）URL登録手順」** に全面刷新する。
     - **Reddit / コミュニティでのBAN回避ルール**: スレッド内に直接App Storeリンクを貼る行為を禁止し、「GMC NextでサプリメンタルTSVを使ってメイン画像を上書きする純粋な技術解決策」を回答するプロトコルへ修正する。
     - **レビュー依頼の規約遵守化**: Shopify規約違反（レビュー操作）を避けるため、「★5を依頼する」という表現を「GMC審査通過の瞬間に率直なレビューを依頼するコンシェルジュ・オンボーディング」へ修正する。
  2. `OUTREACH_TARGETS.md`:
     - **最優先ターゲット（Priority 1）の再定義**: 初期20〜30社の最速獲得ターゲットとして、**「国内で楽天市場・Yahoo!ショッピング・AmazonとShopifyを併用しており、モール用の文字焼き込み画像を流用してGoogle広告審査に落ちているEC事業者・支援会社」** を最優先セクションとして追加する。
     - **代理店への提案切り口の変更**: いきなり月額ツールを売るのではなく、「代理店が見込み客へGoogle広告のリプレイス提案をする際の『無料監査・実演アカウント（50枚無料枠）』として提供する」ピッチテンプレートを追加する。
  3. `APP_STORE_LISTING.md`:
     - **Pricing**: Starter Plan ($19/mo • 100 images) と Pro Plan ($65/mo • 500 images) の2段階ハイブリッド課金へ更新。
     - **Google無料AI（Automatic image improvements）との明確な比較セクション追加**:
       - Google標準AI＝「審査落ちして広告が止まった後の事後処理・複雑なセール帯は失敗・商品が削れるリスク」。
       - AdFeed Clean＝「審査落ちを未然に防ぐ事前予防・Florence-2 + Big-LaMaによる高品質補完・1クリック復元保証」。
  4. `POST_APPROVAL_ROADMAP.md` & `SYSTEM_DESIGN.md`:
     - 本指示書（v2.3.0）の全実装内容を反映し、システム設計書およびロードマップのステータスを最新化する。

---

## 3. 検証・テスト要件（Verification & Quality Gate）

Antigravityはすべてのコード、スクリプト、ドキュメントの改修完了後、以下のテストを実行し、**全件PASS（Exit Code: 0）**を確認して報告せよ（※本番 `wrangler deploy` は審査通過まで実行しないこと）。

1. **統合E2Eテストスイートの拡張と実行 (`python3 tests/e2e/test_pure_dual_feed_e2e.py`)**:
   - 既存の78テストが100% PASSすること。
   - 以下の新規テストケースを追加し、PASSすることを確認せよ：
     - **R2インデックス型サプリメンタルフィード生成テスト**: `GET /feeds/:shop/gmc-supplemental.tsv?token=...&country=JP` が、Shopify APIを呼ばずにR2インデックスから `id\timage_link` ヘッダーと `shopify_JP_{productId}_{variantId}` の全バリアント展開行をミリ秒単位で正しく出力すること。
     - **解約時クローラー準拠404ロックテスト**: アンインストール後（`uninstalledAt` 設定後）に `/feeds/:shop/gmc-supplemental.tsv` および `/clean-media/:shop/*` へアクセスした際、`404 Not Found`（または `410 Gone`）で確実に遮断されること。
     - **2段階プラン・日時ベース14日トライアル昇格・Pre-Flight従量課金テスト**:
       - `trialEndsAt` が未来日時の場合、50枚を超過すると `402 TRIAL_BATCH_LIMIT_REACHED` で保護停止すること。
       - `trialEndsAt` が過去日時の場合、自動的にStarter（100枚）またはPro（500枚）の上限へ昇格し、上限超過時に `appUsageRecordCreate` が事前実行され、Capped Amount到達時にはRunPod呼び出し前に安全遮断されること。
2. **営業プレビュー画像生成スクリプトの動作検証**:
   - `python3 scripts/generate_outreach_preview.py --demo --store-name "Tokyo Sneaker Store" --output assets/sample_outreach_preview.png` を実行し、エラーなく1600x900pxの比較画像が生成されることを確認せよ。
3. **全既存テストスイートの回帰検証（100% PASS必須）**:
   - `python3 -m unittest discover tests/e2e`
   - `python3 tests/oracle_verification.py`
   - `python3 tests/empirical_dom_challenger_m2.py`
   - `python3 tests/test_m2_bilingual_parity.py`（新規追加したGMC Nextガイドや2プラン文言を含め、日英キーが100%完全一致していること）
   - `python3 tests/test_legal_and_store_assets.py`
   - `python3 tests/test_oauth_and_gdpr.py`

---

## 4. Antigravity への実行開始コマンド（コピペ用プロンプト）

以下のテキストをコピーしてAntigravityに入力してください：

```text
プロジェクト内の `ANTIGRAVITY_EXECUTION_DIRECTIVE.md` (v2.3.0 厳格監査版) を読み込んでください。
この指示書に記載されている Task 1 〜 Task 5：
1. R2インデックス型GMCサプリメンタルフィードTSV高速配信（国コード対応・全バリアント展開）＆解約時HTTP 404配信ロックの実装
2. Starter ($19/100枚) / Pro ($65/500枚) の2段階ハイブリッド課金、`trialEndsAt` 日時判定によるトライアル中50枚上限キャップと自動昇格、およびPre-Flight従量課金サーキットブレーカーの実装
3. ダッシュボードUIへの「GMC Nextアドオン有効化ガイド＆2タブ連携ウィザード」追加と、利用規約（/terms）への解約時配信停止・設定解除案内の明記
4. 営業用Before/After比較カード自動生成スクリプト（`scripts/generate_outreach_preview.py`）の新規実装とデモ画像出力
5. `GTM_GROWTH_PLAYBOOK.md`（承諾型2ステップ営業・現実的ファネル数値）、`OUTREACH_TARGETS.md`、`APP_STORE_LISTING.md`、`SYSTEM_DESIGN.md` の全面アップデート
を順番にすべて実装してください。
※注意：現在Shopify審査待ちのため、本番への `wrangler deploy` は実行せず、コード実装と指示書セクション3の全自動テストスイート（新規テスト含む）の100% PASS（Exit Code: 0）までを完了させて結果を報告してください。
```