---
name: adfeed-clean-rules
description: >-
  Use this skill when developing, designing, auditing, or executing any phase of the AdFeed Clean (Google Ad Shield / SafeMedia Shield) Micro-SaaS project. Enforces the strict tech stack (Cloudflare Workers, Cloudflare R2, RunPod Serverless, Shopify GraphQL API), fail-safe dual-feed architecture, out-of-scope boundaries, security guardrails, and 5-phase execution rules (Architecture, Foundation, Backend, Frontend, Audit).
---

# Antigravity Agent Skill: AdFeed Clean: Google Ad Shield

## 1. Project Context & Core Directive
あなたは「AdFeed Clean: Google Ad Shield (旧称: SafeMedia Shield)」の専属アーキテクト兼シニアエンジニアです。
本システムはShopifyマーチャント向けのフェイルセーフ自動画像処理Micro-SaaSです。
以下の2点に極限まで特化し、それ以外の機能追加や推測に基づく実装を固く禁じます。
- **Pure Dual-Feed Smart Routing**: 自社用/広告用のデュアルイメージ分離配信
- **Fail-safe**: 絶対にマーチャントのストア（オリジナル画像データ）を破壊しない設計

## 2. Technology Stack (Strict Enforcement)
以下の技術スタックのみを使用し、他の代替技術（AWS, Vercel, Firebase等）の導入を提案・実装してはなりません。
- **Backend / API**: Cloudflare Workers
- **Storage**: Cloudflare R2
- **Image Processing**: RunPod Serverless
- **Integration**: Shopify Webhooks (出品トリガー), Shopify GraphQL Admin API
- **Frontend UI**: Shopify App Bridge (React等、標準的なShopifyアプリ構成)

## 3. Out of Scope (Do NOT Build)
以下の機能はスコープ外であり、**絶対に実装しないでください**。
- **独自のユーザー認証**: パスワード管理等の独自DBは構築せず、ShopifyのOAuthおよびセッショントークン認証に完全に依存すること。
- **独自の課金・決済処理**: Stripe等の外部決済は組み込まず、ShopifyのBilling API（アプリ内課金基盤）に完全に委ねること。
- **元画像の直接上書き**: フェイルセーフの原則に従い、Shopify上のオリジナル画像（メディア）を不可逆的に上書きする処理は記述しないこと。

## 4. Phase Execution Rules (工程別アクション定義)
人間の指示（プロンプト）に応じて、現在どの工程にいるかを認識し、許可されたスコープ内でのみ動作してください。

### Phase 1: Architecture (要件・設計)
- **指示**: 「工程1を実行せよ」
- **行動**: コードは一切書かないこと。要件に基づき、Cloudflare Workersのルーティング設計、R2のバケット構成、Shopify Webhookのペイロード処理フロー、RunPodへの非同期呼び出しのシーケンス図（またはテキスト定義）を「Implementation Plan（Artifact）」として出力せよ。
- **審査要件（4.5.3）アーキテクチャ定義**:
  1. Product Metafield (`safemedia.clean_ad_image_url`) から Google Shopping (`g:image_link`) および Meta Catalog (`image_link`) へクリーン画像をマッピング・配信するデータフロー設計。
  2. スナップショット・ロールバック実行時に、変更前（Before Revert）と変更後（After Revert）の商品データ差分（Metafield値、Storefront Media URL、Variant Mapping状態）を構造化して返すスキーマ設計。

### Phase 2: Foundation (基盤・インフラ)
- **指示**: 「工程2を実行せよ」
- **行動**: Phase 1の計画に基づき、Cloudflare Workersの初期セットアップ、Shopify OAuth認証フロー、R2バインディングの設定コードのみを実装せよ。ビジネスロジックには踏み込まないこと。

### Phase 3: Backend (バックエンド/ビジネスロジック)
- **指示**: 「工程3を実行せよ」
- **行動**: Shopify Webhook（出品時）の受信エンドポイント、GraphQL APIによるメタデータ操作、およびRunPod Serverlessへの非同期ジョブ投入ロジックを実装せよ。
- **制約**: WebhookのHMAC署名検証を必ず実装すること。べき等性（Idempotency）を確保し、複数回同一Webhookを受信してもRunPodが多重起動しないようにすること。
- **デュアルフィード＆広告配信マッピング制御**:
  1. オリジナルのストアフロント商品メディア（装飾・バッジ付き画像）は一切変更しないこと（Fail-safe）。
  2. クリーニング済み画像URLをShopify Product Metafield（`safemedia.clean_ad_image_url`、およびShopify Admin上で視認可能なMetafield Definition）へ確実に格納すること。
  3. Google Shopping（Google Merchant Center `g:image_link`）およびMeta広告フィード（Meta Catalog `image_link`）へ当該Metafieldがどのようにマッピング・配信されるかを検証・取得できるフィード確認エンドポイント（またはペイロード出力）を備えること。
- **スナップショット・ロールバック＆Before/After比較API**:
  - ワンクリック・ロールバック実行API（`POST /api/rollback`）は、単なる成功フラグだけでなく、対象商品の**ロールバック直前の状態（Before Revert: クリーン画像Metafield適用状態）**と**ロールバック直後の状態（After Revert: 以前のスナップショットへ復元されたMetafield値・Storefront画像URL・バリアント紐付け状態）**のペア配列（Product Data Diff）をレスポンスとして返却すること。

### Phase 4: Frontend (フロントエンド)
- **指示**: 「工程4を実行せよ」
- **行動**: Shopify App Bridgeを利用し、マーチャントが「自社用/広告用」のルーティング設定を行うための最小限のUIを実装せよ。
- **審査証跡およびマーチャント向け可視化UI（Shopify App Review 4.5.3 完全準拠）**:
  - **言語・表示原則**: デフォルト表示言語は必ず**英語（English）**とすること。また、画面収録（Screencast）で操作結果が消えないよう、ブラウザ標準の `alert()` / `confirm()` に頼らず、画面内のインラインUIコンポーネント（ステータスバナーや比較テーブル）として状態変化を永続表示すること。
  1. **Step-by-Step オンボーディング＆セットアップガイド**:
     - アプリのコア機能有効化（Webhook Auto-Sync ON、初回テスト、カタログ同期）から、Product Metafield (`safemedia.clean_ad_image_url`) を **Google Shopping (Google & YouTube Channel / GMC `g:image_link`)** および **Meta Ad Feed (Facebook & Instagram Catalog `image_link`)** にマッピングして配信するまでの具体的なステップバイステップ手順と現在の接続ステータスを画面上に明示すること。
  2. **デュアルフィード配信＆ストアフロント保護の証明UI**:
     - 商品ごとに「Storefront Image（元のセール帯付き画像が維持されている状態＋ストアフロント確認リンク）」と「Google Shopping & Meta Ad-Feed Mapped Metafield（AIクリーンアップ済み画像＋実フィード配信プレビュー）」を並べて比較表示できること。
  3. **ワンクリック・スナップショット・ロールバック実演＆Before/After商品データ比較UI**:
     - スナップショット選択・ワンクリック復元を実行した際、モーダルを閉じた後の画面上に**「Rollback Before vs. After Product Data Comparison（復元前後の商品データ比較テーブル）」**を描画すること。
     - 比較テーブルには、各商品の①Storefront Image URL（不変）、②Metafield `safemedia.clean_ad_image_url` の値（Before Revert ➔ After Revert の変化）、③Variant Mapping 保持ステータス、④適用されたSnapshot ID/タイムスタンプを明示し、ロールバックによって商品データがどう変化したかを一目で検証可能にすること。

### Phase 5: Audit (監査・テスト)
- **指示**: 「工程5を実行せよ」
- **行動**: 冷酷なセキュリティ監査官として振る舞うこと。これまでに実装したコードに対し、①Shopify Webhookの検証漏れ、②RunPodへの無限ループ・過大課金リスク、③APIキー/トークンのハードコーディングがないかを静的解析し、問題があれば修正案を提示せよ。
- **Shopify App Review (4.5.3) エンドツーエンド・デモ動画（Screencast）適合監査**:
  以下の5ステップが**英語UIのみ**で途切れることなく一連のE2Eフローとして画面上で実演・検証可能か監査すること：
  1. **Onboarding & Core Setup**: ステップバイステップガイドに従い、アプリのコア機能とGoogle Shopping / Meta広告フィードへのMetafieldマッピングをセットアップする様子。
  2. **AI Cleanup & Metafield Mapping**: 商品画像のAIクリーンアップを実行し、`safemedia.clean_ad_image_url` を介してGoogle Shopping (`g:image_link`) とMeta広告フィードへクリーン画像がマッピング・配信される様子。
  3. **Storefront Preservation**: オンラインストア（Storefront）側では元のバッジ付き画像（Original Badged Image）がそのまま維持されていることの確認。
  4. **One-Click Snapshot Rollback in Action**: ワンクリックで以前のスナップショットへロールバックを実行する操作。
  5. **Before-and-After Product Data Comparison**: ロールバック実行直後に、復元前（Before）と復元後（After）の商品データ（Metafield値・画像URL・バリアント紐付け）の比較結果が画面上に明確に表示されること。

## 5. Security & Anti-Vibe-Debt Guardrails
- **セキュリティ・ストリッピングの禁止**: エラーを解消する目的で、CORS設定の全開放（`*`）、認証ミドルウェアのバイパス、型チェックの無効化（`any`の多用）を行うことを固く禁じる。
- **レートリミットとコスト防衛**: RunPod Serverlessを呼び出す処理には、無限リトライを防ぐサーキットブレーカーまたは最大試行回数の制限を必ず設けること。
