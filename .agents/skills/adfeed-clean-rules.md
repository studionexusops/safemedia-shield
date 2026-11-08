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

### Phase 2: Foundation (基盤・インフラ)
- **指示**: 「工程2を実行せよ」
- **行動**: Phase 1の計画に基づき、Cloudflare Workersの初期セットアップ、Shopify OAuth認証フロー、R2バインディングの設定コードのみを実装せよ。ビジネスロジックには踏み込まないこと。

### Phase 3: Backend (バックエンド/ビジネスロジック)
- **指示**: 「工程3を実行せよ」
- **行動**: Shopify Webhook（出品時）の受信エンドポイント、GraphQL APIによるメタデータ操作、およびRunPod Serverlessへの非同期ジョブ投入ロジックを実装せよ。
- **制約**: WebhookのHMAC署名検証を必ず実装すること。べき等性（Idempotency）を確保し、複数回同一Webhookを受信してもRunPodが多重起動しないようにすること。

### Phase 4: Frontend (フロントエンド)
- **指示**: 「工程4を実行せよ」
- **行動**: Shopify App Bridgeを利用し、マーチャントが「自社用/広告用」のルーティング設定を行うための最小限のUIを実装せよ。

### Phase 5: Audit (監査・テスト)
- **指示**: 「工程5を実行せよ」
- **行動**: 冷酷なセキュリティ監査官として振る舞うこと。これまでに実装したコードに対し、①Shopify Webhookの検証漏れ、②RunPodへの無限ループ・過大課金リスク、③APIキー/トークンのハードコーディングがないかを静的解析し、問題があれば修正案を提示せよ。

## 5. Security & Anti-Vibe-Debt Guardrails
- **セキュリティ・ストリッピングの禁止**: エラーを解消する目的で、CORS設定の全開放（`*`）、認証ミドルウェアのバイパス、型チェックの無効化（`any`の多用）を行うことを固く禁じる。
- **レートリミットとコスト防衛**: RunPod Serverlessを呼び出す処理には、無限リトライを防ぐサーキットブレーカーまたは最大試行回数の制限を必ず設けること。