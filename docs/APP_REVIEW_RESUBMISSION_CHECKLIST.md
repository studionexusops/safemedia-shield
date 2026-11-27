# AdFeed Clean: Google Shopping — Shopify App Store 再提出チェックリスト（2026-11-19以降）

> **対象イベント**: Shopify App Review クールダウン解除（**2026年11月19日以降**）に伴う再提出  
> **関連ドキュメント**:  
> - デモ動画撮影シナリオ: [APP_REVIEW_SCREENCAST_SCENARIO.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_SCREENCAST_SCENARIO.md)  
> - 統合システム設計書: [SYSTEM_DESIGN.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/SYSTEM_DESIGN.md)  
> - ストア掲載・提出情報: [APP_STORE_LISTING.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_STORE_LISTING.md)  
> - テスト仕様書: [TEST_SPEC_SHOPIFY_INTEGRATION.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/TEST_SPEC_SHOPIFY_INTEGRATION.md)  

---

## 1. 審査メールの要点と対応方針

| 項目 | メール記載内容・位置づけ | 対応方針 |
| :--- | :--- | :--- |
| **再提出解禁日** | **2026年11月19日以降** | 停止解除後、全チェック項目を完了させてから再提出する（不備のまま再提出するとクールダウンが長期化するため厳禁）。 |
| **`4.5.3` デモ動画** *(必須・核心)* | オンボーディング、メタフィールド経由の Google Shopping / Meta 配信、ストアフロント元画像保持、1クリック・ロールバックと前後比較がE2Eで映っていない。 | [APP_REVIEW_SCREENCAST_SCENARIO.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_SCREENCAST_SCENARIO.md) に沿って英語UI＋英語字幕で新規録画し、Listing側と `Proof of resolution` 側の両方を更新する。 |
| **`1.2.3` プラン変更** *(定型リマインド)* | 複数プラン間のアップグレード／ダウングレードを自己完結させる規定。 | **新規開発は不要**（単一プラン `$65/mo` 構成は規約違反ではない）。`Testing Instructions` に単一プランである旨を明記し、Partner Dashboard の料金表記と実装を一致させる。 |
| **`4.5.4` / `4.5.5` 認証情報** *(定型リマインド)* | 外部ログイン・2FA/OTP/SSOなしでテストできる認証情報と手順の提示。 | 本アプリは Shopify OAuth 2.0 のみで完結し外部ログイン不要であるため、`Testing Instructions` 冒頭にその旨を明記する。 |

---

## 2. 再提出前チェックリスト

### Step 1: E2Eデモ動画（4.5.3）の録画・アップロード
- [ ] **事前準備**: アプリ画面の右上言語設定を **`EN`（英語）** にし、3タブ（Tab 1: アプリ管理画面 / Tab 2: Shopify商品管理画面 / Tab 3: オンラインストア商品ページ）を用意する。
- [ ] **録画実施**: [APP_REVIEW_SCREENCAST_SCENARIO.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_SCREENCAST_SCENARIO.md#L49-L180) の Scene 1〜6 を切れ目のない一連の操作として録画する（目安 3分〜3分30秒）。
  - [ ] **Scene 1**: オンボーディング（可能な限り未承認状態からの `14-Day Free Trial` 承認を含む）と Zone 1（Active）・4ステップガイドの確認
  - [ ] **Scene 2**: Step 1 カナリアプレビュー ＆ バリアントピル（`.variant-pill`）切替による紐付け保持確認
  - [ ] **Scene 3**: Step 2 カタログ全件一括同期 ＆ `Recent Synced Product Feed` の Before/After 確認
  - [ ] **Scene 4**: Shopify商品管理画面のメタフィールド（`safemedia.clean_ad_image_url`）確認 ＋ `RSS XML Feed ↗`（`<g:image_link>`）および `JSON Feed ↗`（`image_link`）のライブ確認
  - [ ] **Scene 5**: オンラインストア（Storefront）を開き、セール帯付き元画像が100%保持されていることを確認
  - [ ] **Scene 6**: Step 3 `Revert to Previous Snapshot` 実行 ➔ `Rollback Before vs. After Product Data Comparison`（6列比較表）の提示 ➔ 商品管理画面/フィード表で復元確認
- [ ] **英語字幕の挿入**: [字幕一覧表](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_SCREENCAST_SCENARIO.md#L184-L200) の英語テキスト（01〜11）を動画に焼き込む（または英語音声を収録）。
- [ ] **URL反映（2箇所）**:
  - [ ] YouTube（限定公開 / Unlisted）または Loom 等へアップロードする。
  - [ ] Partner Dashboard の **App listing（掲載情報）のデモ動画URL** を新しい動画URLに差し替える。
  - [ ] 審査画面の **`Proof of resolution *`** 欄にも新しい動画URLを入力する準備をする。

---

### Step 2: Partner Dashboard 設定・本番環境の整合性確認
- [ ] **課金テストモードの確認**: [`cloudflare_worker/wrangler.toml`](file:///Users/yusuke/antigravity/Micro-SaaS/cloudflare_worker/wrangler.toml) の `BILLING_TEST_MODE` が本番公開審査向けの設定（`"false"`）になっていることを確認する（参考: [TEST_SPEC_SHOPIFY_INTEGRATION.md#L68-L69](file:///Users/yusuke/antigravity/Micro-SaaS/docs/TEST_SPEC_SHOPIFY_INTEGRATION.md#L68-L69)）。
- [ ] **料金表記の一致確認**: Partner Dashboard の「Pricing」欄と実装（[shopify.ts#L1442-L1471](file:///Users/yusuke/antigravity/Micro-SaaS/cloudflare_worker/src/shopify.ts#L1442-L1471)）が一致しているか確認する。
  - 基本プラン: `SafeMedia Shield Smart Protection Plan`（Listing表記: `AdFeed Clean Pro`） / `$65.00 USD` every 30 days（月500枚まで内包 / `14-day free trial`・トライアル上限50枚）
  - 超過従量課金: `$0.05 USD` per additional cleaned image（上限 `$100.00 USD`）
  - *(※ [APP_STORE_LISTING.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_STORE_LISTING.md) もハイブリッド従量課金仕様へ同期済み)*
- [ ] **Distribution画面の残項目確認**: Partner Dashboard の審査ステータス画面を開き、`4.5.3` 以外に未解決（Unresolved）フラグが立っている項目がないか目視確認する。

---

### Step 3: `Testing Instructions` の更新（4.5.4 / 4.5.5 / 1.2.3 誤判定防止）
Partner Dashboard の **`Testing instructions`** 欄に、以下の最新テンプレートを貼り付ける（`[ここに新しい動画のURLを貼る]` を差し替えて使用）。

```text
### App Review Testing Instructions for AdFeed Clean: Google Shopping

Thank you for reviewing AdFeed Clean: Google Shopping!

1. Authentication & Credentials (Requirements 4.5.4 & 4.5.5):
   - No external login, username/password, 2FA, OTP, or SSO credentials are required.
   - Our app authenticates exclusively via standard Shopify OAuth 2.0 (read_products, write_products) and operates as an embedded app inside Shopify Admin. Reviewers have full access to all features immediately upon installation on a development store.
   - Zero Customer PII: Our app does not access, read, or store any customer names, emails, addresses, or order data.

2. Pricing Plan Structure (Requirement 1.2.3):
   - Our app offers a single, unified pricing plan via the Shopify Billing API ($65.00 USD / 30 days including 500 cleaned images/month + $0.05 USD per image overage up to a $100.00 USD cap, with a 14-day free trial).
   - Because there is only one paid plan tier, no multi-tier upgrade/downgrade switching is required. Merchants can cancel anytime by uninstalling the app, and all charges appear directly in Shopify Admin billing history.

3. Updated End-to-End Demo Screencast (Requirement 4.5.3):
   Video URL: [ここに新しい動画のURLを貼る]

   What this updated E2E screencast demonstrates with English captions:
   - 0:00 - 0:35 (Onboarding & Setup): 14-day free trial activation, Zone 1 Always-On Auto-Protection (products/update webhook), and the 4-Step Channel Mapping Guide.
   - 0:35 - 1:10 (Canary Preview & Variant Preservation): AI badge removal test on 1 sample product and interactive verification of 100% variant-image link preservation.
   - 1:10 - 1:45 (Full Catalog Batch Sync): Automatic pre-sync cloud snapshot creation and non-destructive metafield generation across the catalog.
   - 1:45 - 2:25 (Metafield & Google Shopping / Meta Ad Feed Delivery): Verification of the pinned product metafield (safemedia.clean_ad_image_url) in Shopify Admin and live inspection of the Google Merchant Center RSS XML Supplemental Feed (<g:image_link>) and Meta Catalog JSON Feed (image_link).
   - 2:25 - 2:45 (Storefront Badged Image Preservation): Live verification on the Online Store showing original promotional badges remain 100% unaltered.
   - 2:45 - 3:30 (1-Click Snapshot Rollback & Before/After Comparison): Live execution of 1-click rollback to a previous snapshot alongside the 6-column "Rollback Before vs. After Product Data Comparison" table showing exact before-and-after product metafield and feed states.

4. Step-by-Step Verification in Test Store:
   - Step 1: Install the app on a Shopify development store with at least 1 product containing a promotional/sale badge image.
   - Step 2: Approve the 14-day free trial subscription screen (or run up to 5 free Canary Previews in Zone 2 Step 1 first).
   - Step 3: Run Zone 2 Step 1 ("Test on 1 Sample Product") and click variant pills to confirm before/after previews and variant link preservation.
   - Step 4: Run Zone 2 Step 2 ("Start Full Catalog Batch Sync"), then verify:
     (a) Product Metafield "safemedia.clean_ad_image_url" in Shopify Admin -> Products.
     (b) Live "RSS XML Feed" (<g:image_link>) and "JSON Feed" (image_link) links in the Channel Distribution Status panel.
     (c) Live Online Store product page showing the original badged image untouched.
   - Step 5: Run Zone 2 Step 3 ("Revert to Previous Snapshot" -> select Virgin Baseline -> "Yes, Restore Now") and verify the Before vs. After comparison table and reverted metafield state.
   - Step 6: Check /privacy and /terms links in the footer (EN/JA supported) and compliance webhooks (/webhooks/privacy/customers/data_request, /webhooks/privacy/customers/redact, /webhooks/privacy/shop/redact, /webhooks/app/uninstalled).
```

---

### Step 4: 再提出の実行（2026年11月19日以降）
- [ ] Partner Dashboard の `4.5.3` 指摘欄にて、動画URLを入力し **`Mark resolved`** をクリックする。
- [ ] 上記 Step 1〜3 がすべて反映されていることを最終確認したうえで、アプリを再提出（Resubmit）する。
