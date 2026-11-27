/**
 * SafeMedia Shield / AdFeed Clean - Public Legal Pages (Privacy Policy & Terms of Service)
 * Styled with Shopify Polaris design guidelines, responsive layout, and bilingual (EN/JA) toggle.
 */

export function renderPrivacyPolicyHtml(currentLang: "en" | "ja" = "en", cspNonce: string = ""): string {
  const safeNonce = cspNonce && /^[a-zA-Z0-9+/=_-]+$/.test(cspNonce) ? ` nonce="${cspNonce}"` : "";
  const isJa = currentLang === "ja";
  return `<!DOCTYPE html>
<html lang="${currentLang}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Privacy Policy | AdFeed Clean for Google Shopping</title>
  <style>
    :root {
      --p-surface: #ffffff;
      --p-background: #f6f6f7;
      --p-text: #202223;
      --p-subdued: #6d7175;
      --p-border: #e1e3e5;
      --p-primary: #008060;
      --p-primary-hover: #004c3f;
      --p-card-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
      --p-radius: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--p-background);
      color: var(--p-text);
      line-height: 1.6;
      padding: 32px 16px;
    }
    .container {
      max-width: 860px;
      margin: 0 auto;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: inherit;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #008060 0%, #004c3f 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: bold;
      font-size: 20px;
      box-shadow: 0 2px 6px rgba(0, 128, 96, 0.3);
    }
    .brand-title {
      font-size: 20px;
      font-weight: 700;
      color: var(--p-text);
    }
    .brand-subtitle {
      font-size: 13px;
      color: var(--p-subdued);
    }
    .lang-switcher {
      display: flex;
      background: #e4e5e7;
      border-radius: 8px;
      padding: 2px;
    }
    .lang-btn {
      padding: 6px 14px;
      border: none;
      background: transparent;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 6px;
      color: var(--p-subdued);
      transition: all 0.2s ease;
    }
    .lang-btn.active {
      background: #fff;
      color: var(--p-text);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    .nav-links {
      display: flex;
      gap: 16px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    .nav-links a {
      color: var(--p-primary);
      text-decoration: none;
      font-weight: 600;
    }
    .nav-links a:hover {
      text-decoration: underline;
    }
    .card {
      background: var(--p-surface);
      border: 1px solid var(--p-border);
      border-radius: var(--p-radius);
      box-shadow: var(--p-card-shadow);
      padding: 40px;
      margin-bottom: 24px;
    }
    h1 {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #1a1a1a;
    }
    .effective-date {
      font-size: 13px;
      color: var(--p-subdued);
      margin-bottom: 24px;
    }
    h2 {
      font-size: 20px;
      font-weight: 600;
      margin-top: 32px;
      margin-bottom: 12px;
      padding-bottom: 6px;
      border-bottom: 1px solid #edf0f2;
      color: #1a1a1a;
    }
    p, li {
      font-size: 15px;
      color: #303030;
      margin-bottom: 14px;
    }
    ul, ol {
      padding-left: 24px;
      margin-bottom: 16px;
    }
    li {
      margin-bottom: 8px;
    }
    .callout {
      background: #f0fdf4;
      border-left: 4px solid var(--p-primary);
      padding: 16px 20px;
      border-radius: 0 8px 8px 0;
      margin: 20px 0;
      font-size: 14px;
    }
    .callout-title {
      font-weight: 700;
      color: var(--p-primary-hover);
      margin-bottom: 4px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 14px;
    }
    th, td {
      border: 1px solid var(--p-border);
      padding: 12px;
      text-align: left;
    }
    th {
      background: #f9fafb;
      font-weight: 600;
    }
    .footer {
      text-align: center;
      font-size: 13px;
      color: var(--p-subdued);
      margin-top: 32px;
      padding-top: 20px;
      border-top: 1px solid var(--p-border);
    }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="/" class="brand">
        <div class="brand-icon">🛡️</div>
        <div>
          <div class="brand-title">AdFeed Clean</div>
          <div class="brand-subtitle">for Google Shopping</div>
        </div>
      </a>
      <div class="lang-switcher">
        <button class="lang-btn${isJa ? "" : " active"}" onclick="switchLang('en')">English</button>
        <button class="lang-btn${isJa ? " active" : ""}" onclick="switchLang('ja')">日本語</button>
      </div>
    </div>

    <div class="nav-links">
      <a href="/">← Back to App</a>
      <span>•</span>
      <a href="/privacy">Privacy Policy</a>
      <span>•</span>
      <a href="/terms">Terms of Service</a>
    </div>

    <!-- ENGLISH CONTENT -->
    <div id="content-en" class="card${isJa ? " hidden" : ""}">
      <h1>Privacy Policy</h1>
      <div class="effective-date">Effective Date: November 27, 2026 | Version 2.0</div>

      <div class="callout">
        <div class="callout-title">Commitment to Data Minimization & Privacy</div>
        <div>
          <strong>AdFeed Clean for Google Shopping</strong> ("we", "us", or "our") is designed exclusively for Shopify merchants.
          We strictly practice data minimization. <strong>We do NOT collect, process, or store end-consumer personal data</strong>
          (such as shopper names, physical addresses, email addresses, payment methods, or purchase transactions).
        </div>
      </div>

      <h2>1. About AdFeed Clean</h2>
      <p>
        AdFeed Clean provides automated image dual-routing for Shopify merchants. When merchants upload or update product images containing promotional badges or sales banners, our service uses AI inpainting to generate secondary policy-compliant clean images. These clean images are stored in dedicated Shopify product and variant metafields (<code>safemedia.clean_ad_image_url</code>) and served via an authenticated Supplemental Feed (<code>/api/feed-preview.xml</code>) for Google Merchant Center and Meta Catalog feeds, while your storefront continues displaying the original promotional badges.
      </p>

      <h2>2. Information We Collect and Process</h2>
      <p>To deliver our core service, we process only merchant store and catalog metadata:</p>
      <table>
        <thead>
          <tr>
            <th>Data Category</th>
            <th>Specific Data Points</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Merchant Authentication</strong></td>
            <td>Shopify store domain (e.g. <code>store.myshopify.com</code>), OAuth API access tokens, feed access tokens</td>
            <td>Authenticating API requests, protecting supplemental feed endpoints, and writing clean image URLs to product and variant metafields.</td>
          </tr>
          <tr>
            <td><strong>Product Catalog Media</strong></td>
            <td>Product IDs, Variant IDs, existing public product image URLs, MediaImage IDs, supplemental feed cache</td>
            <td>Analyzing promotional text/overlays, mapping variants to avoid broken links, serving clean ad feeds, and generating multi-version immutable safety rollback snapshots.</td>
          </tr>
          <tr>
            <td><strong>Service Usage & Billing</strong></td>
            <td>Canary preview test count (up to 5 free), 14-day trial quota (up to 50 images), monthly usage count (500 included + metered overage), subscription & usage charge IDs, circuit-breaker pause state</td>
            <td>Enforcing trial/monthly quotas, metered usage billing via Shopify Billing API, and emergency stop controls.</td>
          </tr>
        </tbody>
      </table>

      <h2>3. End-Consumer Data (Zero PII Policy)</h2>
      <p>
        Our application operates solely on product catalog assets. <strong>We do not access, intercept, or retain any Personally Identifiable Information (PII) belonging to your store's end customers.</strong> We do not track shopper behavior, IP addresses, or purchase history.
      </p>

      <h2>4. Shopify Mandatory Compliance & GDPR / CCPA Webhooks</h2>
      <p>We comply fully with Shopify's platform requirements and mandatory GDPR/CCPA webhook endpoints:</p>
      <ul>
        <li>
          <strong><code>customers/data_request</code></strong>: Because we do not store customer PII, we immediately verify and acknowledge requests confirming zero customer records exist.
        </li>
        <li>
          <strong><code>customers/redact</code></strong>: Because we do not store customer PII, we immediately acknowledge with zero redaction required.
        </li>
        <li>
          <strong><code>shop/redact</code></strong>: Received 48 hours after a store uninstalls our app. We automatically and permanently delete all tenant data (including R2 snapshots, cleaned image assets under <code>/clean-media/</code>, supplemental feed caches, catalog mappings, and billing states) from our systems.
        </li>
        <li>
          <strong><code>app/uninstalled</code></strong>: Received immediately upon app uninstallation. We immediately revoke stored OAuth tokens and deactivate background webhook listeners.
        </li>
      </ul>

      <h2>5. AI Inference & Image Processing Architecture</h2>
      <p>
        Product images submitted for cleaning are processed via stateless, isolated GPU inference workers. Images are fetched via validated HTTPS URLs, cleaned using AI text/badge inpainting, and saved back to our secure distributed cloud storage and your Shopify product/variant metafields.
      </p>
      <p>
        <strong>Model Training Policy:</strong> Your product images and metadata are <em>never</em> used to train public third-party foundation models, nor are they shared with unauthorized external entities.
      </p>

      <h2>6. Security and Tenant Isolation</h2>
      <p>We implement enterprise-grade security controls to safeguard merchant data:</p>
      <ul>
        <li><strong>Multi-Tenant Isolation:</strong> All R2 snapshot files and state records are partitioned strictly by store domain (e.g., <code>state/{shop}/...</code>). Cross-tenant access is cryptographically blocked.</li>
        <li><strong>SSRF Defense:</strong> Strict URL and IP validation prevents Server-Side Request Forgery against private networks and cloud metadata services.</li>
        <li><strong>Signature Verification:</strong> All incoming Shopify webhooks and OAuth redirects are verified using HMAC-SHA256 constant-time comparison to prevent timing attacks.</li>
        <li><strong>Encryption in Transit and at Rest:</strong> All data in transit uses TLS 1.3, and edge snapshots are encrypted at rest with AES-256.</li>
      </ul>

      <h2>7. Merchant Rights & Data Retention</h2>
      <p>
        Merchants retain full ownership of their catalog media and snapshots. You may request immediate deletion of your store snapshots and cached configuration at any time by contacting us or uninstalling the app.
      </p>

      <h2>8. Contact Information</h2>
      <p>If you have any questions, privacy inquiries, or data requests, please contact our Data Protection team at:</p>
      <p><strong>Email:</strong> <a href="mailto:studio.nexus.ops@gmail.com" style="color:var(--p-primary);">studio.nexus.ops@gmail.com</a></p>
    </div>

    <!-- JAPANESE CONTENT -->
    <div id="content-ja" class="card${isJa ? "" : " hidden"}">
      <h1>プライバシーポリシー (Privacy Policy)</h1>
      <div class="effective-date">最終改定日: 2026年11月27日 | バージョン 2.0</div>

      <div class="callout">
        <div class="callout-title">データ最小化とプライバシー保護への誓約</div>
        <div>
          <strong>AdFeed Clean for Google Shopping</strong>（以下「本サービス」）は、Shopifyマーチャント向けに特化して設計されています。
          当社は厳格なデータ最小化を実践しており、<strong>購入者（一般エンド消費者）の個人情報（氏名、住所、メールアドレス、クレジットカード番号、購買履歴等）を一切取得・保管・処理いたしません。</strong>
        </div>
      </div>

      <h2>1. 本サービスについて</h2>
      <p>
        AdFeed Cleanは、Shopifyマーチャント向けに商品画像の「デュアルフィード自動分離配信」を提供します。セール帯や装飾の入った商品画像から、Google広告・Meta広告ポリシーに適合するクリーン画像をAIで自動生成し、Shopifyの専用メタフィールド（商品・バリアント単位の <code>safemedia.clean_ad_image_url</code>）に格納するとともに、認証付き補足フィード（<code>/api/feed-preview.xml</code>）として提供します。これにより、自社ストアでは売れる装飾画像を維持したまま、広告審査落ち（BAN）を自動回避します。
      </p>

      <h2>2. 取得および処理する情報</h2>
      <p>本サービスの提供に必要な範囲に限定し、以下のマーチャント店舗情報およびカタログメタデータのみを処理します：</p>
      <table>
        <thead>
          <tr>
            <th>区分</th>
            <th>具体的なデータ項目</th>
            <th>利用目的</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>マーチャント認証情報</strong></td>
            <td>ShopifyストアURL（<code>*.myshopify.com</code>）、OAuthアクセストークン、フィードアクセストークン</td>
            <td>APIリクエストの認証、補足フィードエンドポイントの保護、およびクリーン画像URLのメタフィールド格納</td>
          </tr>
          <tr>
            <td><strong>商品カタログ画像データ</strong></td>
            <td>商品ID、バリアントID、既存の公開商品画像URL、MediaImage ID、補足フィードキャッシュ</td>
            <td>セール帯や文字のAI検知・クリーンアップ、バリアント紐付けの維持、広告フィード配信、および1クリック復元用マルチ世代イミュータブルスナップショットの作成</td>
          </tr>
          <tr>
            <td><strong>利用実績および課金状態</strong></td>
            <td>カナリア試行回数（最大5件無料）、14日間トライアル枠（最大50枚）、月間処理枚数（500枚内包＋超過従量課金）、課金ID、緊急停止（サーキットブレーカー）状態</td>
            <td>無料枠・月間クォータの管理、Shopify Billing APIによる従量課金連携、および緊急停止制御</td>
          </tr>
        </tbody>
      </table>

      <h2>3. エンド消費者の個人情報について（ゼロPII方針）</h2>
      <p>
        本サービスは商品カタログ画像とそのメタデータのみを取り扱います。<strong>貴社ストアの一般購入者の個人情報（氏名、住所、クレジットカード情報等）にアクセスすることは一切なく、アクセス権限（Scope）も要求いたしません。</strong>
      </p>

      <h2>4. Shopify必須コンプライアンス（GDPR / CCPA対応）</h2>
      <p>当社はShopifyのプラットフォーム規約およびGDPR/CCPA必須Webhookに完全準拠しています：</p>
      <ul>
        <li><strong><code>customers/data_request</code></strong>: 当社は購入者データを保持しないため、顧客データが存在しない旨を即時確認・応答します。</li>
        <li><strong><code>customers/redact</code></strong>: 同様に購入者データを保持しないため、即時応答します。</li>
        <li><strong><code>shop/redact</code></strong>: アプリ削除から48時間後にShopifyより送信される通知です。本通知を受信後、当社システム内に保存されている当該ストアの全スナップショット、クリーン画像（<code>/clean-media/</code>）、補足フィードキャッシュ、および設定データを完全削除（物理消去）します。</li>
        <li><strong><code>app/uninstalled</code></strong>: アプリのアンインストール時に即時受信し、トークンを無効化してWebhook受信を停止します。</li>
      </ul>

      <h2>5. AI推論と画像処理環境</h2>
      <p>
        画像処理はステートレス（状態非保持）な専用GPU環境で実行されます。処理された画像は安全な分散クラウドストレージおよび貴社Shopifyメタフィールド（商品・バリアント単位）に格納されます。
        <strong>マーチャントの画像データが一般公開用の基底AIモデルの学習に使用されることは一切ありません。</strong>
      </p>

      <h2>6. セキュリティとテナント分離</h2>
      <ul>
        <li><strong>完全なテナント分離:</strong> データは店舗ドメイン単位（<code>state/{shop}/...</code>）で厳格に論理・物理分離され、他店舗からの参照は暗号学的に防止されます。</li>
        <li><strong>SSRF防御:</strong> 内部ネットワークやクラウドメタデータへの不正リクエスト（SSRF）を完全に遮断します。</li>
        <li><strong>HMAC署名検証:</strong> 全てのShopify通信はHMAC-SHA256署名および定数時間比較により改ざん・タイミング攻撃を防御します。</li>
      </ul>

      <h2>7. お問い合わせ窓口</h2>
      <p>プライバシーポリシーに関するご質問やデータ削除のご要望は、下記窓口までご連絡ください：</p>
      <p><strong>窓口:</strong> <a href="mailto:studio.nexus.ops@gmail.com" style="color:var(--p-primary);">studio.nexus.ops@gmail.com</a></p>
    </div>

    <div class="footer">
      &copy; 2026 AdFeed Clean for Google Shopping. All rights reserved.
    </div>
  </div>

  <script${safeNonce}>
    function switchLang(lang) {
      const en = document.getElementById('content-en');
      const ja = document.getElementById('content-ja');
      const btns = document.querySelectorAll('.lang-btn');
      
      if (lang === 'ja') {
        en.classList.add('hidden');
        ja.classList.remove('hidden');
        btns[0].classList.remove('active');
        btns[1].classList.add('active');
        document.documentElement.lang = 'ja';
      } else {
        ja.classList.add('hidden');
        en.classList.remove('hidden');
        btns[1].classList.remove('active');
        btns[0].classList.add('active');
        document.documentElement.lang = 'en';
      }
    }
  </script>
</body>
</html>`;
}

export function renderTermsOfServiceHtml(currentLang: "en" | "ja" = "en", cspNonce: string = ""): string {
  const safeNonce = cspNonce && /^[a-zA-Z0-9+/=_-]+$/.test(cspNonce) ? ` nonce="${cspNonce}"` : "";
  const isJa = currentLang === "ja";
  return `<!DOCTYPE html>
<html lang="${currentLang}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Terms of Service | AdFeed Clean for Google Shopping</title>
  <style>
    :root {
      --p-surface: #ffffff;
      --p-background: #f6f6f7;
      --p-text: #202223;
      --p-subdued: #6d7175;
      --p-border: #e1e3e5;
      --p-primary: #008060;
      --p-primary-hover: #004c3f;
      --p-card-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
      --p-radius: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--p-background);
      color: var(--p-text);
      line-height: 1.6;
      padding: 32px 16px;
    }
    .container {
      max-width: 860px;
      margin: 0 auto;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: inherit;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #008060 0%, #004c3f 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: bold;
      font-size: 20px;
      box-shadow: 0 2px 6px rgba(0, 128, 96, 0.3);
    }
    .brand-title {
      font-size: 20px;
      font-weight: 700;
      color: var(--p-text);
    }
    .brand-subtitle {
      font-size: 13px;
      color: var(--p-subdued);
    }
    .lang-switcher {
      display: flex;
      background: #e4e5e7;
      border-radius: 8px;
      padding: 2px;
    }
    .lang-btn {
      padding: 6px 14px;
      border: none;
      background: transparent;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 6px;
      color: var(--p-subdued);
      transition: all 0.2s ease;
    }
    .lang-btn.active {
      background: #fff;
      color: var(--p-text);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    .nav-links {
      display: flex;
      gap: 16px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    .nav-links a {
      color: var(--p-primary);
      text-decoration: none;
      font-weight: 600;
    }
    .nav-links a:hover {
      text-decoration: underline;
    }
    .card {
      background: var(--p-surface);
      border: 1px solid var(--p-border);
      border-radius: var(--p-radius);
      box-shadow: var(--p-card-shadow);
      padding: 40px;
      margin-bottom: 24px;
    }
    h1 {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #1a1a1a;
    }
    .effective-date {
      font-size: 13px;
      color: var(--p-subdued);
      margin-bottom: 24px;
    }
    h2 {
      font-size: 20px;
      font-weight: 600;
      margin-top: 32px;
      margin-bottom: 12px;
      padding-bottom: 6px;
      border-bottom: 1px solid #edf0f2;
      color: #1a1a1a;
    }
    p, li {
      font-size: 15px;
      color: #303030;
      margin-bottom: 14px;
    }
    ul, ol {
      padding-left: 24px;
      margin-bottom: 16px;
    }
    li {
      margin-bottom: 8px;
    }
    .callout {
      background: #eff6ff;
      border-left: 4px solid #2563eb;
      padding: 16px 20px;
      border-radius: 0 8px 8px 0;
      margin: 20px 0;
      font-size: 14px;
    }
    .callout-warning {
      background: #fffbeb;
      border-left-color: #d97706;
    }
    .callout-title {
      font-weight: 700;
      color: #1e40af;
      margin-bottom: 4px;
    }
    .callout-warning .callout-title {
      color: #92400e;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 14px;
    }
    th, td {
      border: 1px solid var(--p-border);
      padding: 12px;
      text-align: left;
    }
    th {
      background: #f9fafb;
      font-weight: 600;
    }
    .footer {
      text-align: center;
      font-size: 13px;
      color: var(--p-subdued);
      margin-top: 32px;
      padding-top: 20px;
      border-top: 1px solid var(--p-border);
    }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <a href="/" class="brand">
        <div class="brand-icon">🛡️</div>
        <div>
          <div class="brand-title">AdFeed Clean</div>
          <div class="brand-subtitle">for Google Shopping</div>
        </div>
      </a>
      <div class="lang-switcher">
        <button class="lang-btn${isJa ? "" : " active"}" onclick="switchLang('en')">English</button>
        <button class="lang-btn${isJa ? " active" : ""}" onclick="switchLang('ja')">日本語</button>
      </div>
    </div>

    <div class="nav-links">
      <a href="/">← Back to App</a>
      <span>•</span>
      <a href="/privacy">Privacy Policy</a>
      <span>•</span>
      <a href="/terms">Terms of Service</a>
    </div>

    <!-- ENGLISH CONTENT -->
    <div id="content-en" class="card${isJa ? " hidden" : ""}">
      <h1>Terms of Service</h1>
      <div class="effective-date">Effective Date: November 27, 2026 | Version 2.0</div>

      <div class="callout">
        <div class="callout-title">Summary of Key Terms</div>
        <div>
          Welcome to <strong>AdFeed Clean for Google Shopping</strong>. By installing and using this application on your Shopify store,
          you agree to these Terms. Our service provides automated Dual-Feed ad image generation to safeguard your Google Shopping and Meta Catalog campaigns
          while preserving promotional badges on your online store.
        </div>
      </div>

      <h2>1. Service Description</h2>
      <p>
        AdFeed Clean provides an automated, non-destructive image processing pipeline designed for Shopify merchants:
      </p>
      <ul>
        <li><strong>Dual-Feed Smart Routing:</strong> Retains sales-driving promotional badges and banners on your storefront while automatically generating clean, policy-compliant images in dedicated product and variant Shopify metafields (<code>safemedia.clean_ad_image_url</code>) and an authenticated Supplemental XML Feed (<code>/api/feed-preview.xml</code>) for Google Merchant Center and Meta Catalog.</li>
        <li><strong>Zero-UI Always-On Shield &amp; Circuit Breaker:</strong> Asynchronously processes product images via Shopify webhooks (<code>products/create</code>, <code>products/update</code>) in the background, with instant pause / emergency stop controls.</li>
        <li><strong>1-Click Snapshot Restore:</strong> Captures multi-version immutable snapshots (including baseline and point-in-time states) of original product image URLs and variant bindings in secure cloud storage before updates, allowing safe one-click rollback at any time (gracefully skipping deleted products or variants).</li>
      </ul>

      <h2>2. Subscription, Free Trial & Billing Terms</h2>
      <table>
        <thead>
          <tr>
            <th>Plan Feature</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Monthly Subscription Fee</strong></td>
            <td><strong>$65.00 USD / month</strong> (billed via Shopify App Billing API; includes <strong>500 cleaned images / month</strong>)</td>
          </tr>
          <tr>
            <td><strong>Usage-Based Overage</strong></td>
            <td><strong>$0.05 USD per cleaned image</strong> beyond 500 images/month, <strong>capped at $100.00 USD / month</strong> in overage charges</td>
          </tr>
          <tr>
            <td><strong>Free Trial Period</strong></td>
            <td><strong>14 Days Free Trial</strong> upon initial installation (includes up to <strong>50 clean images</strong> during the trial period)</td>
          </tr>
          <tr>
            <td><strong>Free Sample Quota</strong></td>
            <td><strong>5 Sample Preview Tests</strong> (Canary Preview) included prior to subscription commitment</td>
          </tr>
          <tr>
            <td><strong>Billing Cycle & Cancellation</strong></td>
            <td>Recurring monthly charge managed via Shopify. You may cancel at any time by uninstalling the application from your Shopify Admin.</td>
          </tr>
        </tbody>
      </table>
      <p>
        Charges are processed directly through your Shopify bill in accordance with Shopify's App Billing policies. If you cancel or uninstall before the end of the 14-day free trial, your payment method will not be charged.
      </p>

      <h2>3. Storefront Integrity & Variant Protection Standard</h2>
      <p>
        We recognize the critical value of your store catalog integrity. Our application operates under a strict "Store Integrity First" standard:
      </p>
      <ul>
        <li><strong>Non-Destructive Routing:</strong> Original master images and theme assets on your storefront are never deleted, overwritten, or modified. Clean images are stored exclusively in dedicated product and variant metafields.</li>
        <li><strong>Variant Protection:</strong> Before updating any media references, the system cross-checks all product variant IDs (<code>MediaImage</code> bindings and variant-level metafields) to guarantee no variant links are unseated.</li>
        <li><strong>Safety Snapshots:</strong> Every catalog modification creates a multi-version immutable snapshot in secure cloud storage that can be restored with a single click.</li>
      </ul>

      <h2>4. Service Level & Best-Effort SLA</h2>
      <p>
        AI-powered text/badge detection and inpainting are provided on a <strong>best-effort basis</strong>. While our pipeline achieves high accuracy in identifying and removing promotional watermarks, badges, and sale banners according to Google Merchant Center editorial guidelines, we cannot guarantee that every conceivable overlay variation will be 100% recognized or that Google will never reject a feed item.
      </p>
      <p>
        Merchants are strongly advised to verify cleaned images using the built-in 5-item Canary Test tool before initiating catalog-wide synchronization.
      </p>

      <h2>5. Limitation of Liability</h2>
      <div class="callout callout-warning">
        <div class="callout-title">Aggregate Liability Cap: One (1) Month Subscription Fee</div>
        <div>
          To the maximum extent permitted by applicable law, in no event shall AdFeed Clean, its developers, or affiliates be liable
          for any indirect, incidental, consequential, special, or punitive damages (including loss of ad spend, loss of revenue,
          or account suspensions by third-party advertising platforms).
          <br /><br />
          <strong>Our aggregate financial liability arising out of or related to your use of this service shall be strictly capped
          at the total amount actually paid by you for this application during the one (1) month immediately preceding the event giving rise to liability ($65.00 USD base subscription fee plus any applicable usage-based overage fees paid in that month).</strong>
        </div>
      </div>

      <h2>6. Termination, App Uninstallation &amp; Post-Cancellation Feed Policy</h2>
      <p>
        You may terminate this agreement at any time by removing the application from your Shopify admin panel. Clean image URLs (<code>/clean-media/:shop/*</code>) and Supplemental Feed endpoints (<code>/api/feed-preview.xml</code>, <code>/api/ad-feed/preview</code>) are provided <strong>exclusively while your installation and subscription remain active</strong>. Upon uninstallation or cancellation:
      </p>
      <ul>
        <li>All recurring subscription and usage-based billing ceases immediately.</li>
        <li>Webhooks, background listeners, and supplemental feed access are deactivated.</li>
        <li>Within 48 hours, in accordance with Shopify's <code>shop/redact</code> protocol, all stored snapshots, cleaned image assets, and tenant configuration are permanently purged. Subsequent requests to <code>/clean-media/:shop/*</code> or feed endpoints will fail (returning <strong>HTTP 404 Not Found</strong> or <strong>401 Unauthorized</strong>).</li>
        <li><strong>Required Merchant Action:</strong> Before or upon uninstalling/cancelling, you <strong>must remove or unlink the Supplemental Feed URL and <code>safemedia.clean_ad_image_url</code> mapping</strong> in Google Merchant Center and Meta Catalog to prevent feed fetch errors or broken ad image links.</li>
      </ul>

      <h2>7. Merchant Responsibilities</h2>
      <p>You agree to:</p>
      <ul>
        <li>Maintain valid administrative permissions on your Shopify store.</li>
        <li>Ensure you possess the legal rights to use and publish all uploaded catalog images.</li>
        <li>Configure your Google Merchant Center and Meta Catalog feeds to reference the appropriate metafield (<code>safemedia.clean_ad_image_url</code>) or Supplemental Feed URL in accordance with provided documentation, and unlink them upon cancellation.</li>
      </ul>

      <h2>8. Governing Law & Updates to Terms</h2>
      <p>
        These Terms shall be governed by and construed in accordance with the laws of Japan, without regard to its conflict of law provisions.
        We reserve the right to update these Terms from time to time. Continued use of the app following any changes constitutes acceptance of the updated terms.
      </p>

      <h2>9. Support and Inquiries</h2>
      <p>For technical support, billing inquiries, or feedback, please reach out to our support team:</p>
      <p><strong>Email:</strong> <a href="mailto:studio.nexus.ops@gmail.com" style="color:var(--p-primary);">studio.nexus.ops@gmail.com</a></p>
    </div>

    <!-- JAPANESE CONTENT -->
    <div id="content-ja" class="card${isJa ? "" : " hidden"}">
      <h1>利用規約 (Terms of Service)</h1>
      <div class="effective-date">最終改定日: 2026年11月27日 | バージョン 2.0</div>

      <div class="callout">
        <div class="callout-title">重要条項の要約</div>
        <div>
          <strong>AdFeed Clean for Google Shopping</strong>（以下「本サービス」）をご利用いただきありがとうございます。
          本アプリをShopifyストアにインストールすることにより、本規約に同意したものとみなされます。
          本サービスは、自社ストアの売れるセール帯を残したまま、Googleショッピング広告およびMetaカタログ広告の審査落ち（BAN）を自動回避するデュアルフィード画像処理を提供します。
        </div>
      </div>

      <h2>1. サービス内容</h2>
      <p>AdFeed Cleanは、Shopifyマーチャント向けに以下の機能を提供します：</p>
      <ul>
        <li><strong>デュアルフィード自動分離配信:</strong> 自社ストアの装飾画像（セール帯・透かし等）には一切手を加えず、広告用のクリーン画像のみをAIで生成してShopifyの専用メタフィールド（商品・バリアント単位の <code>safemedia.clean_ad_image_url</code>）および認証付き補足フィード（<code>/api/feed-preview.xml</code>）へ自動格納・配信します。</li>
        <li><strong>ゼロUI・常時自動保護＆緊急停止:</strong> 商品の新規登録や画像更新（Webhook）をトリガーとしてバックグラウンドで自動処理し、万一の際はダッシュボードから即時一時停止（サーキットブレーカー）が可能です。</li>
        <li><strong>1クリック・ロールバック機能:</strong> 変更前に元画像とバリアント紐付けのマルチ世代イミュータブルスナップショット（初期ベースライン含む）を安全なクラウドストレージに保存し、1クリックで復元可能です（削除済み商品・バリアントは安全にスキップされます）。</li>
      </ul>

      <h2>2. 料金プラン・無料トライアル・課金条件</h2>
      <table>
        <thead>
          <tr>
            <th>項目</th>
            <th>内容</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>月額基本利用料</strong></td>
            <td><strong>月額 $65.00 USD（約 9,800円）</strong>（Shopify App Billing経由での請求／<strong>月間500枚の画像処理を含む</strong>）</td>
          </tr>
          <tr>
            <td><strong>超過従量課金</strong></td>
            <td>月間500枚を超過した分は <strong>$0.05 USD / 枚</strong>（<strong>超過分の月額上限 $100.00 USD</strong>）</td>
          </tr>
          <tr>
            <td><strong>無料トライアル期間</strong></td>
            <td><strong>初回インストール時 14日間の無料トライアル</strong>（期間中の処理上限 <strong>50枚</strong>）</td>
          </tr>
          <tr>
            <td><strong>サンプル無料枠</strong></td>
            <td>課金前に安全性を確認できる<strong>5件のカナリアテスト無料枠</strong></td>
          </tr>
          <tr>
            <td><strong>解約・キャンセル</strong></td>
            <td>Shopify管理画面からいつでも即時アンインストール可能（解約金・違約金なし）</td>
          </tr>
        </tbody>
      </table>
      <p>
        14日間の無料トライアル期間中にアンインストールされた場合、月額料金は一切請求されません。
      </p>

      <h2>3. ストアデータの安全性とバリアント保護設計</h2>
      <ul>
        <li><strong>非破壊オペレーション:</strong> 自社ストアのメイン画像やテーマファイルを直接上書き・破壊することは決してありません。</li>
        <li><strong>バリアント紐付け完全保護:</strong> 画像の更新前に各バリアント（<code>MediaImage</code> およびバリアント単位メタフィールド）のマッピングを保持・検証し、バリアント選択が外れる事故を防止します。</li>
      </ul>

      <h2>4. 免責事項およびベストエフォート提供</h2>
      <p>
        AIによる文字・装飾除去は<strong>ベストエフォート（最善努力）</strong>にて提供されます。高い精度でセール帯や透かしを検出・補完しますが、あらゆるデザインの装飾の完全な除去や、第三者プラットフォーム（Google・Meta等）による審査承認を100%法的に保証するものではありません。
        マーチャント様におかれましては、全商品一括生成の前に、必ず5件のカナリアテスト機能にて仕上がりをご確認ください。
      </p>

      <h2>5. 損害賠償額の上限（ライアビリティ・キャップ）</h2>
      <div class="callout callout-warning">
        <div class="callout-title">損害賠償額の上限：直近1ヶ月分の実支払利用料（基本料 $65.00 / 9,800円 ＋ 超過従量分）</div>
        <div>
          法律で認められる最大限の範囲において、本サービスの利用または利用不能から生じるいかなる間接損害、特別損害、結果的損害、逸失利益（広告配信停止による売上損失等を含む）について、当社は責任を負いません。
          <br /><br />
          <strong>いかなる場合においても、当社がマーチャントに対して負う損害賠償責任の総額は、損害の原因となった事象の直前1ヶ月間にマーチャントが当社に実際に支払った本サービスの利用料金（基本料金 $65.00 USD / 9,800円 および当該月の超過従量課金額の合計）を上限とします。</strong>
        </div>
      </div>

      <h2>6. 契約終了（アンインストール）と解約後の配信停止・設定解除手順</h2>
      <p>
        マーチャントはShopify管理画面から本アプリを削除することで、いつでも契約を終了できます。なお、クリーン画像URL（<code>/clean-media/:shop/*</code>）および補足フィード（<code>/api/feed-preview.xml</code>、<code>/api/ad-feed/preview</code>）の配信は、<strong>有効なインストールおよびサブスクリプション期間中のみ提供されます</strong>。
      </p>
      <ul>
        <li>アンインストールにより次回以降の請求およびWebhook受信は即時停止されます。</li>
        <li>Shopifyのデータ削除手順（<code>shop/redact</code>）に従い、保存されたスナップショット・クリーン画像・設定情報は48時間以内に完全消去され、以降の画像・フィードアクセスは配信停止（<strong>HTTP 404 Not Found</strong> または <strong>401 Unauthorized</strong>）となります。</li>
        <li><strong>解約時の必須お手続き:</strong> 解約またはアンインストールを行う際は、配信停止によるフィード取得エラーを防ぐため、<strong>事前に必ず Google Merchant Center（GMC）および Meta カタログ側の補助フィード設定・<code>safemedia.clean_ad_image_url</code> マッピングを解除してください</strong>。</li>
      </ul>

      <h2>7. 準拠法および管轄裁判所</h2>
      <p>本規約は日本法に準拠し、本規約に関して生じた紛争については東京地方裁判所を第一審の専属的合意管轄裁判所とします。</p>

      <h2>8. サポート・お問い合わせ</h2>
      <p>ご不明点やお気づきの点がございましたら、下記サポート窓口までお問い合わせください：</p>
      <p><strong>サポート:</strong> <a href="mailto:studio.nexus.ops@gmail.com" style="color:var(--p-primary);">studio.nexus.ops@gmail.com</a></p>
    </div>

    <div class="footer">
      &copy; 2026 AdFeed Clean for Google Shopping. All rights reserved.
    </div>
  </div>

  <script${safeNonce}>
    function switchLang(lang) {
      const en = document.getElementById('content-en');
      const ja = document.getElementById('content-ja');
      const btns = document.querySelectorAll('.lang-btn');
      
      if (lang === 'ja') {
        en.classList.add('hidden');
        ja.classList.remove('hidden');
        btns[0].classList.remove('active');
        btns[1].classList.add('active');
        document.documentElement.lang = 'ja';
      } else {
        ja.classList.add('hidden');
        en.classList.remove('hidden');
        btns[1].classList.remove('active');
        btns[0].classList.add('active');
        document.documentElement.lang = 'en';
      }
    }
  </script>
</body>
</html>`;
}
