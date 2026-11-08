# SafeMedia Shield (AdFeed Clean) - 審査通過後アップデート計画書 (Post-Approval Roadmap)

> **作成日時**: 2026-10-24  
> **ステータス**: 保留中（Shopify App Store 審査通過待ち）  
> **適用タイミング**: アプリ審査通過・本番公開直後の最初のマイナーバージョンアップ  

---

## 1. 概要と背景
Shopify App Store審査期間中は、既存の承認済みコード・Worker・UI・API定義に一切の変更を加えず、現状の安定稼働状態を維持します。  
本ドキュメントは、批判的市場検証により判明した**「GMC連携のラストワンマイル」**および**「大規模店舗によるGPU逆ザヤ防止」**の解決策を、審査通過後に最優先で実装するための設計・仕様メモです。

---

## 2. 審査通過後の2大アップデート項目

### 【アップデート 1】GMCサプリメンタルフィード（補助データソース）動的配信
* **目的**:
  Shopify公式「Google & YouTube」アプリがカスタムメタフィールドの画像連携に対応していない制約を突破し、マーチャントがGMC側で1度URLを登録するだけで、自社ストアのセール帯画像を維持したまま広告用画像のみを自動上書きできるようにする。
* **実装内容**:
  1. **Cloudflare Workers エンドポイント追加**:
     - `GET /feeds/:shop/gmc-supplemental.tsv`
     - 仕様: GMCが要求する `id`（`shopify_US_{productId}_{variantId}`）と `image_link`（R2のクリーン画像URL）の2列TSVを動的生成・CDNキャッシュ付きで返却。
  2. **管理ダッシュボード（Zone 1）への連携ガイド追加**:
     - Polaris Banner または Micro-Card として「Google Merchant Center 3分自動連携ガイド」を配置。
     - 発行したTSVフィードURLを「ワンクリックコピー」できるUIを提供。

---

### 【アップデート 2】Shopify Billing API ハイブリッド課金（逆ザヤ防止サーキットブレーカー）
* **目的**:
  大規模カタログを持つマーチャント（SKU 10,000件等）による全件一括同期やバースト処理時に、GPU推論原価が月額料金（9,800円）を超過して赤字（逆ザヤ）になるのを100%防止する。
* **新価格ストラクチャ**:
  * **基本料金**: 月額 9,800円（約 $65 USD） / 月間 **500枚** までのAI処理を内包（SMBの95%以上は追加費用なし）。
  * **超過従量課金**: 501枚目以降 **1枚あたり 8円（約 $0.05 USD）**（原価3円に対し粗利率60%超を担保）。
  * **Capped Amount（月間請求上限）**: **$100.00 USD**（約15,000円 / 想定外の請求を防止）。
* **実装内容**:
  1. **`appSubscriptionCreate` のハイブリッド化**:
     - `appRecurringPricingDetails`（$65/月）と `appUsagePricingDetails`（terms: "$0.05/image over 500 images", cappedAmount: $100）を単一サブスクリプションで発行。
  2. **4層サーキットブレーカー組み込み**:
     - **Pre-Flight Usage Charge**: 501枚目以降は、RunPod GPU呼び出しの「直前」に `appUsageRecordCreate` を実行。課金成功を確認してからGPUコンテナを起動（未回収リスクの完全排除）。
     - **Cap到達時の即時遮断**: `cappedAmount` に達した場合は1ミリ秒で処理を一時停止（`PAUSED_USAGE_CAP_REACHED`）し、Polarisバナーで上限引き上げを案内。

---

## 3. 実装・検証チェックリスト（審査通過後に着手）
- [ ] `cloudflare_worker/src/feed.ts`（新規作成: TSVサプリメンタルフィード生成）
- [ ] `cloudflare_worker/src/shopify.ts`（`appSubscriptionCreate` のハイブリッド引数拡張）
- [ ] `cloudflare_worker/src/index.ts`（Pre-flight usage charge判定およびCap遮断ロジック追加）
- [ ] `cloudflare_worker/src/ui.ts`（GMC補助フィードURLコピーUI & 従量利用状況メーター表示）
- [ ] 統合E2Eテストでの課金上限・TSV整合性検証
