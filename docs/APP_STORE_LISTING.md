# AdFeed Clean: Google Shopping — Shopify App Store Listing Documentation

This document contains the official metadata, copy, visual asset specifications, hybrid pricing terms, technical endpoints, and submission checklist for publishing **AdFeed Clean: Google Shopping** to the Shopify App Store.

> **Last Synced with Implementation**: 2026-11-26  
> **Related Documents**:
> - Resubmission Checklist: [APP_REVIEW_RESUBMISSION_CHECKLIST.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_RESUBMISSION_CHECKLIST.md)
> - E2E Demo Screencast Scenario: [APP_REVIEW_SCREENCAST_SCENARIO.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/APP_REVIEW_SCREENCAST_SCENARIO.md)
> - System Design: [SYSTEM_DESIGN.md](file:///Users/yusuke/antigravity/Micro-SaaS/docs/SYSTEM_DESIGN.md)

---

## 1. App Store Metadata & Basic Information

| Field | Submission Value (English) | Submission Value (Japanese) |
| :--- | :--- | :--- |
| **App Name** *(max 30 chars)* | `AdFeed Clean: Google Shopping` *(29 chars)* | `AdFeed Clean: Google Shopping` *(29文字)* |
| **App Subtitle** *(max 61 chars)* | `Auto clean ad images for Google Shopping. Keep store badges.` *(60 chars)* | `自社ストアのセール帯を残し、Google広告の審査落ちを自動防止` *(30文字)* |
| **Category** | Marketing & Conversion ➔ Advertising | マーケティング・コンバージョン ➔ 広告 |
| **Subcategory** | Sourcing & Selling products ➔ Product feeds | 仕入れ・販売 ➔ 商品フィード |
| **Primary Language** | English | 日本語（多言語対応） |
| **Supported Languages** | English, Japanese | 英語、日本語 |
| **Search Keywords / Tags** | `google shopping`, `ad policy`, `merchant center`, `watermark remover`, `promo badge`, `image clean`, `dual feed`, `feed management`, `ad feed`, `variant protection` | `Googleショッピング`, `Google広告`, `Merchant Center`, `透かし削除`, `セール帯`, `白抜き画像`, `商品フィード`, `審査落ち防止`, `バリアント保護` |

---

## 2. Key Benefits / Features *(max 80 chars each)*

### Feature 1: Dual-Feed Smart Routing
- **EN** *(71 chars)*: `Keep store promo badges; auto-send clean images to Google & Meta feeds.`
- **JA** *(39 chars)*: `ストアのセール帯はそのまま、Google・Meta広告用の白抜き画像を自動配信`

### Feature 2: Zero-UI Always-On Protection
- **EN** *(74 chars)*: `Zero manual work: Webhooks auto-clean product & variant images in seconds.`
- **JA** *(37 chars)*: `手作業ゼロ：商品登録や更新のWebhookで商品・バリアント画像を自動処理`

### Feature 3: 1-Click Rollback & Variant Lock
- **EN** *(76 chars)*: `1-click snapshot rollback & variant lock protect your store from overwrites.`
- **JA** *(30 chars)*: `1クリック復元＆バリアント保護で元画像を上書きせず安全に運用`

---

## 3. App Store Listing — App Details *(max 500 chars; no bullets, pricing, free, trial, or %)*

### English Version *(454 chars / 456 chars with CRLF)*

```text
Google Shopping and Meta Commerce ban promotional badges, discount banners, and watermarks on primary ad images, yet removing them from your storefront hurts conversions.

AdFeed Clean automates Dual-Feed routing so your storefront keeps original promotional badges untouched while AI cleans images via webhooks into product metafields and live Google XML and Meta JSON feeds. Variant link protection and 1-click snapshot rollback keep your catalog safe.
```

---

### Japanese Version *(227 chars / 229 chars with CRLF)*

```text
GoogleショッピングやMeta広告ではメイン画像へのセール帯・割引バッジ・透かし掲載が禁止されていますが、自社ストアから装飾を外すと購入率が低下します。

AdFeed Cleanはデュアルフィード自動分離により、自社ストアの元のセール帯画像をそのまま保持しながら、商品登録や更新時にAIが広告用クリーン画像を自動生成してメタフィールドとGoogle XML・Meta JSONフィードへ配信します。バリアント保護と1クリック復元にも対応しています。
```

---

## 4. Visual Assets Specifications & Location

All visual assets have been generated at exact platform specifications and are stored in the repository:

| Asset Name | Target Dimensions | Format | File Path | Worker Public URL |
| :--- | :--- | :--- | :--- | :--- |
| **App Icon** | 1200 x 1200 px | PNG / SVG | [app_icon_1200x1200.png](file:///Users/yusuke/antigravity/Micro-SaaS/assets/app_icon_1200x1200.png) | `https://safemedia-shield-worker.safemedia.workers.dev/assets/app_icon_1200x1200.svg` |
| **Promo Banner 1: Dual-Feed** | 1600 x 900 px | PNG / SVG | [banner_dual_feed_1600x900.png](file:///Users/yusuke/antigravity/Micro-SaaS/assets/banner_dual_feed_1600x900.png) | `https://safemedia-shield-worker.safemedia.workers.dev/assets/banner_dual_feed_1600x900.svg` |
| **Promo Banner 2: Always-On** | 1600 x 900 px | PNG / SVG | [banner_always_on_1600x900.png](file:///Users/yusuke/antigravity/Micro-SaaS/assets/banner_always_on_1600x900.png) | `https://safemedia-shield-worker.safemedia.workers.dev/assets/banner_always_on_1600x900.svg` |
| **Promo Banner 3: 1-Click Rollback** | 1600 x 900 px | PNG / SVG | [banner_one_click_rollback_1600x900.png](file:///Users/yusuke/antigravity/Micro-SaaS/assets/banner_one_click_rollback_1600x900.png) | `https://safemedia-shield-worker.safemedia.workers.dev/assets/banner_one_click_rollback_1600x900.svg` |

---

## 5. Pricing Plan Setup in Shopify Partner Dashboard

Matches the exact Shopify GraphQL `appSubscriptionCreate` implementation in [shopify.ts#L1442-L1471](file:///Users/yusuke/antigravity/Micro-SaaS/cloudflare_worker/src/shopify.ts#L1442-L1471) and quota constants in [index.ts#L37-L44](file:///Users/yusuke/antigravity/Micro-SaaS/cloudflare_worker/src/index.ts#L37-L44):

* **Plan Type**: Recurring + Usage-based Hybrid Application Charge (Single Unified Tier)
* **Plan Name (Billing API)**: `SafeMedia Shield Smart Protection Plan` *(Listing / UI label: `AdFeed Clean Pro` / `Smart Protection Plan`)*
* **Base Recurring Price**: `$65.00 USD` every 30 days *(includes 500 cleaned images/month)*
* **Usage Charge Rate**: `$0.05 USD` per cleaned image beyond 500 images/month
* **Usage Terms**: `$0.05 per cleaned image beyond 500 images/mo (Max $100/mo)`
* **Capped Amount (Usage Cap)**: `$100.00 USD` every 30 days
* **Trial Days**: `14` days *(up to 50 cleaned images during trial; 5 free Canary Previews before or during trial)*
* **Terms of Service Liability Cap**: Capped at 1 month base fee ($65.00 USD / ¥9,800 JPY).
* **Refund / Cancellation Policy**: Managed directly through Shopify App Billing. Uninstalling the app cancels future billing immediately.

---

## 6. URLs & Technical Endpoints

Aligned with [shopify.app.toml](file:///Users/yusuke/antigravity/Micro-SaaS/shopify.app.toml) and [index.ts#L2650-L2657](file:///Users/yusuke/antigravity/Micro-SaaS/cloudflare_worker/src/index.ts#L2650-L2657):

* **App URL**: `https://safemedia-shield-worker.safemedia.workers.dev`
* **Allowed Redirection URL (OAuth Callback)**: `https://safemedia-shield-worker.safemedia.workers.dev/api/auth/callback`
* **Privacy Policy URL**: `https://safemedia-shield-worker.safemedia.workers.dev/privacy`
* **Terms of Service URL**: `https://safemedia-shield-worker.safemedia.workers.dev/terms`
* **Support Email**: `studio.nexus.ops@gmail.com`
* **Emergency Contact**: `studio.nexus.ops@gmail.com`

### Mandatory Compliance & App Webhook Endpoints
All webhook endpoints verify Shopify HMAC-SHA256 signatures:
* **Mandatory Compliance Endpoint (`shopify.app.toml`)**: `https://safemedia-shield-worker.safemedia.workers.dev/webhooks/compliance` (`customers/data_request`, `customers/redact`, `shop/redact`)
  * *(Individual privacy paths `/webhooks/privacy/customers/data_request`, `/webhooks/privacy/customers/redact`, and `/webhooks/privacy/shop/redact` are also routed and handled identically.)*
* **App Uninstalled**: `https://safemedia-shield-worker.safemedia.workers.dev/webhooks/app/uninstalled`
* **Product Lifecycle**: `/webhooks/products/create`, `/webhooks/products/update`, `/webhooks/products/delete`

---

## 7. Instructions for the Shopify App Review Team *(max 2,800 chars)*

When submitting your app in the Shopify Partner Dashboard, paste the following into the **"Testing instructions" (`Instruction notes`)** field *(2,675 chars / 2,702 chars with CRLF)*:

```text
### Testing Instructions: AdFeed Clean: Google Shopping

1. Authentication & Credentials (4.5.4 & 4.5.5):
- No external login, password, 2FA, OTP, or SSO is required.
- Authenticates via Shopify OAuth 2.0 (read_products, write_products) inside Shopify Admin. Reviewers get full access immediately upon installation.
- Zero Customer PII: Does not access or store customer names, emails, addresses, or orders.

2. Pricing Plan Structure (1.2.3):
- Single unified hybrid plan via Shopify Billing API: $65.00 USD / 30 days (500 cleaned images/mo included) + $0.05 USD/image overage (max $100.00 USD cap), with a 14-day free trial.
- Because there is only one paid plan tier, no plan upgrade/downgrade switching is needed. Merchants can cancel anytime by uninstalling.

3. Updated E2E Demo Screencast (4.5.3):
Video URL: https://youtu.be/_9HRf_v4ORo
Timestamps (with English captions):
- 0:00-0:40 Onboarding & Setup: 14-day trial activation, Zone 1 Auto-Protection (products/update webhook), 4-Step Channel Mapping Guide.
- 0:40-1:50 Canary Preview & Variant Preservation: AI badge removal on 1 sample product and variant-image link verification.
- 1:50-2:55 Full Catalog Batch Sync: Pre-sync cloud snapshot creation and non-destructive metafield generation.
- 2:55-4:30 Metafield & Ad Feeds: Product metafield (safemedia.clean_ad_image_url) in Shopify Admin + live Google Shopping RSS XML (<g:image_link>) and Meta JSON (image_link) feeds.
- 4:30-4:50 Storefront Preservation: Live Online Store showing original promo badges 100% unaltered.
- 4:50-5:47 1-Click Rollback & Diff: Live snapshot restore, 6-column Before vs. After comparison table, and reverted metafield check.

4. Step-by-Step Verification:
- Step 1: Install on a dev store with at least 1 product containing a promotional/sale badge image.
- Step 2: Approve the 14-day free trial screen (or run up to 5 free Canary Previews in Zone 2 Step 1 first).
- Step 3: Run Zone 2 Step 1 ("Test on 1 Sample Product") and click variant pills to confirm before/after previews and variant link preservation.
- Step 4: Run Zone 2 Step 2 ("Start Full Catalog Batch Sync"), then verify: (a) Metafield "safemedia.clean_ad_image_url" in Shopify Admin -> Products, (b) live "RSS XML Feed" (<g:image_link>) & "JSON Feed" (image_link) in Channel Distribution Status, and (c) Online Store page keeping the original badged image.
- Step 5: Run Zone 2 Step 3 ("Revert to Previous Snapshot" -> Virgin Baseline -> "Yes, Restore Now") and verify the Before vs. After comparison table and reverted metafield.
- Step 6: Verify /privacy and /terms footer links (EN/JA) and compliance webhooks (/webhooks/compliance, /webhooks/app/uninstalled).
```

---

## 8. Partner Dashboard Submission Checklist

- [x] **OAuth 2.0 Flow**: Implemented and tested (`/api/auth`, `/api/auth/callback`).
- [x] **Mandatory Compliance Webhooks**: Implemented with HMAC-SHA256 signature verification (`/webhooks/compliance`, `/webhooks/app/uninstalled`).
- [x] **Hosted Privacy Policy**: Publicly accessible at `/privacy` with EN/JA toggle.
- [x] **Hosted Terms of Service**: Publicly accessible at `/terms` with $65 / ¥9,800 liability cap and EN/JA toggle.
- [x] **App Icon (1200x1200px PNG)**: Generated and verified in `assets/app_icon_1200x1200.png`.
- [x] **Promotional Banners (1600x900px PNG)**: 3 high-res feature cards generated in `assets/`.
- [x] **Billing Integration**: Shopify App Billing API ($65/mo for 500 images + $0.05/image overage capped at $100/mo, 14-day trial with 50-image cap, 5 free canary sample quota, `BILLING_TEST_MODE = "false"`).
- [x] **Storefront Safety**: Dual-feed metafield isolation (`safemedia.clean_ad_image_url`) + Google XML / Meta JSON supplemental feeds + 1-Click Rollback with 6-column comparison table.
- [x] **Security**: SSRF protection, tenant path isolation, timingSafeEqual constant-time HMAC comparison.
- [ ] **Demo Screencast & Listing Sync**: Replace Listing demo video URL and `Proof of resolution *` URL with the newly recorded English E2E screencast, align Partner Dashboard Pricing to Hybrid ($65/mo + $0.05/image, $100 cap), and paste Section 7 into `Testing instructions`.
