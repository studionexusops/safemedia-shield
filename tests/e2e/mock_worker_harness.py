"""
mock_worker_harness.py
Authoritative Mock Harness and Simulator for SafeMedia Shield / AdFeed Clean.
Implements the exact interface contracts defined in:
- PROJECT.md (§ Interface Contracts)
- ORIGINAL_REQUEST.md (§ R1, R2, Acceptance Criteria)
- docs/SYSTEM_DESIGN.md

Supports:
1. In-memory direct dispatch (Default: zero-socket, sandbox-proof, lightning fast)
2. Live HTTP worker execution (when base_url is configured)
"""

import base64
import copy
import hashlib
import hmac
import json
import re
import os
import pathlib
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# Set default VERIFY_M2_UI=1 for pure dual-feed UI testing against real ui.ts
os.environ.setdefault("VERIFY_M2_UI", "1")

WEBHOOK_SECRET = "test_webhook_secret_key_12345"
PRIMARY_SHOP = "safemedia-test-20261011.myshopify.com"
OTHER_SHOP = "victim-store-999.myshopify.com"
PRIMARY_TOKEN = "shpat_test_token_primary_12345"


def is_valid_shop_domain(shop: Optional[str]) -> bool:
    if not shop or len(shop) > 100:
        return False
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,60}\.myshopify\.com$", shop))


def is_valid_public_image_url(raw_url: Optional[str]) -> bool:
    if not raw_url or not isinstance(raw_url, str) or len(raw_url) > 2048:
        return False
    if raw_url.startswith("data:image/"):
        return True
    try:
        parsed = urllib.parse.urlparse(raw_url)
        if parsed.scheme not in ("https", "http"):
            return False
        raw_host = (parsed.hostname or "").lower()
        if not raw_host:
            return False

        host = raw_host.strip("[]")

        # 1. Hostnames & Local Suffixes
        if (
            host == "localhost"
            or host == "metadata.google.internal"
            or host.endswith(".internal")
            or host.endswith(".local")
            or host.endswith(".localhost")
            or host.endswith(".localdomain")
            or host.endswith(".home.arpa")
        ):
            return False

        # 2. Hex / Octal / Decimal Integer IP notations & Obfuscated Formats
        if (
            re.match(r"^0x[0-9a-f]+$", host, re.I)
            or re.match(r"^\d+$", host)
            or "0x" in host
            or bool(re.search(r"(^|\.)0[0-7]+(\.|$)", host))
        ):
            return False

        # 3. IPv6 Literals (contains colon)
        if ":" in host:
            # Loopback & Unspecified
            if host in ("::1", "::", "0:0:0:0:0:0:0:1", "0:0:0:0:0:0:0:0"):
                return False
            # IPv4-mapped IPv6
            if host.startswith("::ffff:") or "::ffff:" in host or bool(re.match(r"^(0+:){5}ffff:", host, re.I)):
                return False
            # Unique Local (fc00::/7)
            if host.startswith("fc") or host.startswith("fd") or bool(re.match(r"^f[cd][0-9a-f]{0,2}:", host, re.I)):
                return False
            # Link-Local (fe80::/10)
            if bool(re.match(r"^fe[89ab][0-9a-f]{0,1}:", host, re.I)):
                return False
            # Site-Local (fec0::/10)
            if bool(re.match(r"^fe[c-f][0-9a-f]{0,1}:", host, re.I)):
                return False
            # Multicast
            if host.startswith("ff"):
                return False
            # Discard / Doc
            if host.startswith("100::") or host.startswith("2001:db8:"):
                return False
            # Enforce Global Unicast range (2000::/3)
            if not bool(re.match(r"^[23][0-9a-f]{3}:", host, re.I)):
                return False
            return True

        # 4. IPv4 Loopback CIDR: 127.0.0.0/8 & Zero network 0.0.0.0/8
        if host.startswith("127.") or host == "127" or host.startswith("0.") or host == "0.0.0.0":
            return False

        # 5. IPv4 Link-Local & Cloud Metadata (169.254.0.0/16)
        if host.startswith("169.254."):
            return False

        # 6. RFC 1918 Private Networks & Carrier Grade NAT
        if host.startswith("10.") or host.startswith("192.168."):
            return False
        m172 = re.match(r"^172\.(\d{1,3})\.", host)
        if m172 and 16 <= int(m172.group(1)) <= 31:
            return False
        m100 = re.match(r"^100\.(\d{1,3})\.", host)
        if m100 and 64 <= int(m100.group(1)) <= 127:
            return False

        # 7. Strict Octet Validation for standard dotted-quad IPv4
        ipv4_match = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", host)
        if ipv4_match:
            octets = [int(g) for g in ipv4_match.groups()]
            if any(o > 255 for o in octets):
                return False
            if octets[0] >= 224:
                return False

        return True
    except Exception:
        return False


def render_dashboard_from_ui_ts(shop: str, store: Optional[Any] = None) -> str:
    """
    Renders dashboard HTML directly from cloudflare_worker/src/ui.ts.
    Guarantees that test assertions inspect the actual application source code,
    not a duplicate mock string.

    Execution Strategy:
    1. Attempts Node.js evaluation (Node v22+ --experimental-strip-types) if permitted.
    2. Falls back to pure-Python template extraction and interpolation if Node is
       restricted by OS sandbox permissions.
    """
    ui_path = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"
    if not ui_path.exists():
        raise FileNotFoundError(f"UI source file not found at {ui_path}")

    # Strategy 1: Node.js execution (if permitted)
    try:
        import subprocess
        cmd = [
            "node",
            "--experimental-strip-types",
            "-e",
            f'import {{ renderDashboardHtml }} from "./cloudflare_worker/src/ui.ts"; process.stdout.write(renderDashboardHtml({json.dumps(shop)}));',
        ]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip().startswith("<!DOCTYPE html>"):
            return res.stdout
    except Exception:
        pass

    # Strategy 2: Pure-Python template extraction
    content = ui_path.read_text(encoding="utf-8")
    fn_match = re.search(
        r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string\s*\{\s*return\s*`([\s\S]*<\/html>)\s*`;\s*\}",
        content,
    )
    if not fn_match:
        fn_match = re.search(
            r"export\s+function\s+renderDashboardHtml[\s\S]*?return\s*`([\s\S]*)`;\s*\}",
            content,
        )
    if not fn_match:
        raise ValueError("Could not extract renderDashboardHtml template from cloudflare_worker/src/ui.ts")

    template = fn_match.group(1)
    rendered = template.replace("${shop}", shop)
    rendered = rendered.replace("${apiKey}", "e02dce6bc82b8bca2d95a315f567e43b")
    is_active = store is not None and getattr(store, "plan_status", "") == "ACTIVE"
    canary_display_cls = "hidden text-xs text-gray-500 font-medium" if is_active else "text-xs text-gray-500 font-medium"
    canary_display_txt = f"Free Samples: {store.canary_used_count}/5 Used" if store is not None else "Free Samples: 0/5 Used"
    rendered = rendered.replace("${canaryQuotaDisplayClass}", canary_display_cls)
    rendered = rendered.replace("${canaryQuotaDisplayText}", canary_display_txt)
    rendered = rendered.replace(r"\`", "`").replace(r"\${", "${")
    return rendered


def render_legal_from_ts(page_type: str, lang: str = "en") -> str:
    """
    Renders Privacy Policy or Terms of Service HTML directly from cloudflare_worker/src/legal.ts.
    """
    legal_path = REPO_ROOT / "cloudflare_worker" / "src" / "legal.ts"
    if not legal_path.exists():
        raise FileNotFoundError(f"Legal source file not found at {legal_path}")

    fn_name = "renderPrivacyPolicyHtml" if page_type == "privacy" else "renderTermsOfServiceHtml"
    content = legal_path.read_text(encoding="utf-8")
    fn_match = re.search(
        rf"export\s+function\s+{fn_name}[\s\S]*?return\s*`([\s\S]*?)`;\s*\}}",
        content,
    )
    if not fn_match:
        raise ValueError(f"Could not extract {fn_name} template from cloudflare_worker/src/legal.ts")

    template = fn_match.group(1)
    is_ja = lang == "ja"
    rendered = template.replace("${currentLang}", lang)
    rendered = rendered.replace("${safeNonce}", "")
    rendered = rendered.replace('${isJa ? "" : " active"}', "" if is_ja else " active")
    rendered = rendered.replace('${isJa ? " active" : ""}', " active" if is_ja else "")
    rendered = rendered.replace('${isJa ? " hidden" : ""}', " hidden" if is_ja else "")
    rendered = rendered.replace('${isJa ? "" : " hidden"}', "" if is_ja else " hidden")
    rendered = rendered.replace(r"\`", "`").replace(r"\${", "${")
    return rendered


def get_public_asset_from_ts(pathname: str) -> Optional[Dict[str, str]]:
    """
    Retrieves public store visual assets from cloudflare_worker/src/assets.ts.
    """
    assets_path = REPO_ROOT / "cloudflare_worker" / "src" / "assets.ts"
    if not assets_path.exists():
        return None

    clean_path = pathname.replace("/assets/", "").strip("/")
    content = assets_path.read_text(encoding="utf-8")

    var_map = {
        "app_icon_1200x1200.svg": "ASSET_APP_ICON_SVG",
        "app-icon.svg": "ASSET_APP_ICON_SVG",
        "app-icon": "ASSET_APP_ICON_SVG",
        "banner_dual_feed_1600x900.svg": "ASSET_BANNER_DUAL_FEED_SVG",
        "banner-dual-feed.svg": "ASSET_BANNER_DUAL_FEED_SVG",
        "banner-dual-feed": "ASSET_BANNER_DUAL_FEED_SVG",
        "banner_always_on_1600x900.svg": "ASSET_BANNER_ALWAYS_ON_SVG",
        "banner-always-on.svg": "ASSET_BANNER_ALWAYS_ON_SVG",
        "banner-always-on": "ASSET_BANNER_ALWAYS_ON_SVG",
        "banner_one_click_rollback_1600x900.svg": "ASSET_BANNER_ONE_CLICK_ROLLBACK_SVG",
        "banner-one-click-rollback.svg": "ASSET_BANNER_ONE_CLICK_ROLLBACK_SVG",
        "banner-one-click-rollback": "ASSET_BANNER_ONE_CLICK_ROLLBACK_SVG",
    }

    var_name = var_map.get(clean_path)
    if not var_name:
        return None

    match = re.search(rf"export\s+const\s+{var_name}\s*=\s*`([\s\S]*?)`;", content)
    if not match:
        return None

    return {"content": match.group(1), "contentType": "image/svg+xml"}


def compute_shopify_hmac(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def compute_shopify_query_hmac(params: Dict[str, str], secret: str = WEBHOOK_SECRET) -> str:
    sorted_pairs = sorted([f"{k}={v}" for k, v in params.items() if k not in ("hmac", "signature")])
    message = "&".join(sorted_pairs)
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def get_default_catalog() -> List[Dict[str, Any]]:
    return [
        {
            "id": "gid://shopify/Product/1001",
            "title": "プレミアム ヘビーウェイト クラシックTシャツ (50% OFF SALE)",
            "body_html": "<p>最高級超長綿を使用したTシャツ。<img src='https://cdn.shopify.com/orig/black.jpg'/></p>",
            "media": [
                {"id": "gid://shopify/MediaImage/2001", "url": "https://cdn.shopify.com/orig/black_promo_sale.jpg"},
                {"id": "gid://shopify/MediaImage/2002", "url": "https://cdn.shopify.com/orig/white.jpg"},
                {"id": "gid://shopify/MediaImage/2003", "url": "https://cdn.shopify.com/orig/navy.jpg"},
            ],
            "variants": [
                {"id": "gid://shopify/ProductVariant/3001", "title": "Black / S", "media_id": "gid://shopify/MediaImage/2001", "sku": "TS-BLK-S"},
                {"id": "gid://shopify/ProductVariant/3002", "title": "Black / M", "media_id": "gid://shopify/MediaImage/2001", "sku": "TS-BLK-M"},
                {"id": "gid://shopify/ProductVariant/3003", "title": "White / S", "media_id": "gid://shopify/MediaImage/2002", "sku": "TS-WHT-S"},
                {"id": "gid://shopify/ProductVariant/3004", "title": "White / M", "media_id": "gid://shopify/MediaImage/2002", "sku": "TS-WHT-M"},
                {"id": "gid://shopify/ProductVariant/3005", "title": "Navy / L", "media_id": "gid://shopify/MediaImage/2003", "sku": "TS-NVY-L"},
            ],
            "metafields": {},
        },
        {
            "id": "gid://shopify/Product/1002",
            "title": "オーガニック フレンチテリー ジップアップフーディー",
            "body_html": "<p>通年着用できる肉厚裏毛スウェット生地。</p>",
            "media": [
                {"id": "gid://shopify/MediaImage/2011", "url": "https://cdn.shopify.com/orig/grey_limited_badge.jpg"},
                {"id": "gid://shopify/MediaImage/2012", "url": "https://cdn.shopify.com/orig/charcoal.jpg"},
            ],
            "variants": [
                {"id": "gid://shopify/ProductVariant/3011", "title": "Grey / M", "media_id": "gid://shopify/MediaImage/2011", "sku": "HD-GRY-M"},
                {"id": "gid://shopify/ProductVariant/3012", "title": "Grey / L", "media_id": "gid://shopify/MediaImage/2011", "sku": "HD-GRY-L"},
                {"id": "gid://shopify/ProductVariant/3013", "title": "Charcoal / M", "media_id": "gid://shopify/MediaImage/2012", "sku": "HD-CHR-M"},
            ],
            "metafields": {},
        },
    ]


class MockStoreState:
    """Per-shop in-memory state store simulating Shopify, R2, and Billing state."""

    def __init__(self, shop: str):
        self.shop = shop
        self.catalog: List[Dict[str, Any]] = get_default_catalog()
        self.snapshots: Dict[str, Dict[str, Any]] = {}
        self.latest_snapshot_id: Optional[str] = None
        self.plan_status = "CANARY_TRIAL"
        self.plan_name = "SafeMedia Shield Smart Protection Plan ($65/mo • 500 Images Included)"
        self.price_usd = 65
        self.trial_days = 14
        self.first_installed_at: Optional[float] = time.time()
        self.has_ever_subscribed: bool = False
        self.canary_used_count = 0
        self.canary_limit = 5
        self.trial_used_count = 0
        self.trial_limit = 50
        self.monthly_included_count = 500
        self.monthly_usage_count = 0
        self.overage_price_usd = 0.05
        self.capped_amount_usd = 100.0
        self.active_gpu_slots: Dict[int, float] = {}
        self.circuit_breaker_tripped = False
        self.auto_sync_enabled = True
        self.webhook_id: Optional[str] = None
        self.in_flight_locks: Dict[str, float] = {}
        self.processed_webhook_ids: Dict[str, float] = {}
        self.last_rollback: Optional[Dict[str, Any]] = None
        self.job_state = {
            "jobId": "init",
            "shop": shop,
            "status": "IDLE",
            "total": 0,
            "processed": 0,
            "errors": [],
        }

    def reset(
        self,
        plan_status="CANARY_TRIAL",
        canary_used=0,
        trial_used=0,
        monthly_usage=0,
        circuit_breaker=False,
        empty_catalog=False,
        trial_limit=50,
        monthly_included=500,
        has_ever_subscribed=False,
        first_installed_at=None,
    ):
        self.catalog = [] if empty_catalog else get_default_catalog()
        self.snapshots.clear()
        self.latest_snapshot_id = None
        self.plan_status = plan_status
        self.canary_used_count = canary_used
        self.trial_used_count = trial_used
        self.monthly_usage_count = monthly_usage
        self.trial_limit = trial_limit
        self.monthly_included_count = monthly_included
        self.has_ever_subscribed = has_ever_subscribed
        self.first_installed_at = first_installed_at if first_installed_at is not None else time.time()
        self.trial_days = 0 if has_ever_subscribed else 14
        self.active_gpu_slots.clear()
        self.circuit_breaker_tripped = circuit_breaker
        self.auto_sync_enabled = True
        self.webhook_id = None
        self.in_flight_locks.clear()
        self.processed_webhook_ids.clear()
        self.last_rollback = None
        self.job_state = {
            "jobId": "init",
            "shop": self.shop,
            "status": "IDLE",
            "total": len(self.catalog),
            "processed": 0,
            "errors": [],
        }

    def create_snapshot(self) -> str:
        snap_id = f"snap_{int(time.time() * 1000)}"
        snapshot_data = {
            "snapshotId": snap_id,
            "shop": self.shop,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "totalProducts": len(self.catalog),
            "totalImages": sum(len(p.get("media", [])) for p in self.catalog),
            "products": copy.deepcopy(self.catalog),
        }
        self.snapshots[snap_id] = snapshot_data
        self.latest_snapshot_id = snap_id
        return snap_id

    def restore_snapshot(self, snapshot_id: Optional[str] = None) -> Tuple[bool, int, str, List[Dict[str, Any]], str]:
        target_id = snapshot_id or self.latest_snapshot_id
        if not target_id or target_id not in self.snapshots:
            return False, 0, target_id or "", [], ""
        snap = self.snapshots[target_id]
        before_map = {p["id"]: copy.deepcopy(p) for p in self.catalog}
        reverted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        diffs: List[Dict[str, Any]] = []

        for snap_p in snap["products"]:
            pid = snap_p["id"]
            live_p = before_map.get(pid, snap_p)
            sf_url = (live_p.get("media") or [{}])[0].get("url", "") or (snap_p.get("media") or [{}])[0].get("url", "")
            before_meta = (live_p.get("metafields") or {}).get("safemedia.clean_ad_image_url")
            after_meta = (snap_p.get("metafields") or {}).get("safemedia.clean_ad_image_url")
            action = "RESTORED_TO_SNAPSHOT" if after_meta else "PURGED_TO_VIRGIN"
            v_count = len(snap_p.get("variants", []))

            diffs.append({
                "productId": pid,
                "productTitle": snap_p.get("title", ""),
                "snapshotId": target_id,
                "revertedAt": reverted_at,
                "storefrontImageUrl": sf_url,
                "storefrontUnchanged": True,
                "beforeRevert": {
                    "storefrontImageUrl": sf_url,
                    "cleanAdImageMetafield": before_meta,
                    "gmcImageLink": before_meta or sf_url,
                    "metaImageLink": before_meta or sf_url,
                    "variantCount": v_count,
                    "variantLinksPreserved": True,
                },
                "afterRevert": {
                    "storefrontImageUrl": sf_url,
                    "cleanAdImageMetafield": after_meta,
                    "gmcImageLink": after_meta or sf_url,
                    "metaImageLink": after_meta or sf_url,
                    "metafieldAction": action,
                    "variantCount": v_count,
                    "variantLinksPreserved": True,
                },
            })

        self.catalog = copy.deepcopy(snap["products"])
        return True, len(self.catalog), target_id, diffs, snap.get("createdAt", reverted_at)

    def clear_rollback_record_for_product(self, prod_id: str):
        if not self.last_rollback:
            return
        for d in self.last_rollback.get("productDataDiffs", []):
            if d.get("productId") == prod_id or str(d.get("productId")).endswith(str(prod_id)):
                d["clearedAfterRollback"] = True


def render_mock_ui_html(shop: str, store: MockStoreState) -> str:
    """
    Renders pure 2-Zone dashboard HTML strictly conforming to R1 and M2:
    - App Branding: 'AdFeed Clean for Google Shopping'
    - NO manual refresh button ('🔄 Refresh')
    - Top Banner: High-converting headline + clear functional sub-copy
    - Zone 1: Core Automation (Always-On Ad Shield) with live status, toggle button, how-it-works cards, recent synced feed table
    - Zone 2: Onboarding Tools & Safety Suite (Step 1 Canary, Step 2 Catalog Sync, Step 3 1-Click Rollback)
    - Unified 5-layer card hierarchy on all action cards
    - Bilingual copy (English default with Japanese data attributes)
    """
    status_icon = "⚪ Paused" if not store.auto_sync_enabled else "🟢 Active"
    status_badge = "Ad Shield: Active" if store.auto_sync_enabled else "Ad Shield: Paused"
    canary_hidden_cls = " hidden" if store.plan_status == "ACTIVE" else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AdFeed Clean for Google Shopping</title>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
  <div id="app" class="max-w-6xl mx-auto px-4 py-8">
    <!-- Header -->
    <header class="flex justify-between items-center mb-8 pb-4 border-b">
      <div class="flex items-center space-x-3">
        <h1 class="text-2xl font-bold tracking-tight text-gray-900" data-i18n="app_title">AdFeed Clean for Google Shopping</h1>
        <span id="header_shield_badge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">{status_badge}</span>
      </div>
      <div class="flex items-center space-x-4">
        <span class="text-sm text-gray-500" id="store_domain_badge">{shop}</span>
        <button id="lang_toggle" class="text-sm px-2 py-1 border rounded hover:bg-gray-100">日本語 / EN</button>
      </div>
    </header>

    <!-- Top Banner (Hero Headline & Functional Sub-Copy) -->
    <section id="hero_banner" class="bg-indigo-900 text-white rounded-xl p-6 mb-8 shadow-sm">
      <div class="headline-container mb-2">
        <h2 class="text-xl font-bold text-white tracking-tight" data-i18n="hero_headline">
          Stop Google Ad Disapprovals Due to Store Promo Badges
        </h2>
      </div>
      <div class="subcopy-container">
        <p class="text-indigo-200 text-sm leading-relaxed" data-i18n="hero_subcopy">
          Automatically generate clean, policy-compliant ad images in hidden Shopify metafields without touching your storefront images.
        </p>
      </div>
    </section>

    <!-- ZONE 1: Core Automation (Always-On Ad-Feed Protection) -->
    <section id="zone-core-automation" class="zone-core-automation mb-10 bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div class="flex items-center justify-between pb-4 border-b mb-6">
        <div>
          <span class="text-xs font-bold tracking-wider uppercase text-emerald-600">ZONE 1 • CONTINUOUS PROTECTION</span>
          <h3 class="text-lg font-bold text-gray-900 mt-1" data-i18n="zone1_title">Zone 1: Core Automation (Always-On Ad Shield)</h3>
          <p class="text-sm text-gray-500 mt-0.5" data-i18n="zone1_desc">Event-driven zero-UI protection running silently on product updates.</p>
        </div>
        <div class="flex items-center space-x-3">
          <span id="live_status_indicator" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            {status_icon}
          </span>
          <button id="toggle_auto_sync" class="px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition" data-i18n="btn_toggle_sync">
            Toggle Auto-Sync
          </button>
        </div>
      </div>

      <!-- How it works 3-step micro cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="micro-step-card p-4 bg-gray-50 rounded-lg border">
          <span class="text-xs font-bold text-indigo-600">1. Webhook Received</span>
          <h4 class="text-sm font-semibold text-gray-800 mt-1">Merchant Uploads Promo Image</h4>
          <p class="text-xs text-gray-500 mt-1">Sale badges and promo stickers remain on storefront.</p>
        </div>
        <div class="micro-step-card p-4 bg-gray-50 rounded-lg border">
          <span class="text-xs font-bold text-indigo-600">2. AI Clean Inpainting</span>
          <h4 class="text-sm font-semibold text-gray-800 mt-1">Florence-2 + LaMa Inpaint</h4>
          <p class="text-xs text-gray-500 mt-1">Detects and inlays clean pixels behind stickers.</p>
        </div>
        <div class="micro-step-card p-4 bg-gray-50 rounded-lg border">
          <span class="text-xs font-bold text-indigo-600">3. Metafield Storage</span>
          <h4 class="text-sm font-semibold text-gray-800 mt-1">Google Ad-Feed Synced</h4>
          <p class="text-xs text-gray-500 mt-1">GMC queries safemedia.clean_ad_image_url automatically.</p>
        </div>
      </div>

      <!-- Recent Synced Feed Table -->
      <div class="mt-4">
        <h4 class="text-sm font-bold text-gray-700 mb-3" data-i18n="recent_synced_feed_title">Recent Synced Product Feed</h4>
        <div class="overflow-x-auto border rounded-lg">
          <table id="synced_feed_table" class="min-w-full divide-y divide-gray-200 text-xs">
            <thead class="bg-gray-50 text-gray-600 font-semibold">
              <tr>
                <th class="px-4 py-2 text-left">Product</th>
                <th class="px-4 py-2 text-left">Storefront (Before)</th>
                <th class="px-4 py-2 text-left">Clean Ad-Feed (After)</th>
                <th class="px-4 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody id="synced_feed_rows" class="divide-y divide-gray-200 bg-white">
              <tr>
                <td class="px-4 py-3 font-medium">プレミアム ヘビーウェイト クラシックTシャツ</td>
                <td class="px-4 py-3 text-gray-500">Decorated (Original)</td>
                <td class="px-4 py-3 text-emerald-600 font-medium">safemedia.clean_ad_image_url</td>
                <td class="px-4 py-3"><span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded">Protected</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ZONE 2: Onboarding Tools & Safety Suite -->
    <section id="zone-onboarding-safety" class="zone-onboarding-safety space-y-6">
      <div class="mb-4">
        <span class="text-xs font-bold tracking-wider uppercase text-indigo-600">ZONE 2 • ONBOARDING & SAFETY</span>
        <h3 class="text-lg font-bold text-gray-900 mt-1" data-i18n="zone2_title">Zone 2: Onboarding Tools & Safety Suite</h3>
        <p class="text-sm text-gray-500" data-i18n="zone2_desc">Sequential onboarding steps to verify safety before activating full automation.</p>
      </div>

      <!-- Step 1 Card: 1-Product Canary Test (5-Layer Layout) -->
      <div id="card-canary-preview" class="action-card bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <div class="layer-1-badge mb-2">
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">Step 1 • Start Here</span>
        </div>
        <div class="layer-2-title mb-1">
          <h4 class="text-base font-bold text-gray-900" data-i18n="step1_title">Test on 1 Sample Product (Canary Preview)</h4>
        </div>
        <div class="layer-3-description mb-4">
          <p class="text-xs text-gray-500" data-i18n="step1_desc">
            Verify AI promotional text/badge removal on a single sample product without touching storefront media.
          </p>
        </div>
        <div class="layer-4-actions flex items-center space-x-3 mb-4">
          <button id="btn_run_canary" class="px-4 py-2 text-sm font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition" data-i18n="btn_run_canary">
            Run 1-Product Canary Preview
          </button>
          <span id="canary_quota_display" class="text-xs text-gray-500{canary_hidden_cls}">{store.canary_used_count}/5 Free Samples Used</span>
        </div>
        <div class="layer-5-preview" id="canary_preview_container">
          <div class="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg border text-xs">
            <div id="canary_before_box" class="before-box">
              <span class="font-bold text-gray-700">Before: Storefront Decorated Image</span>
              <div class="mt-2 text-gray-500 italic">[Sale badge & promo text visible]</div>
            </div>
            <div id="canary_after_box" class="after-box">
              <span class="font-bold text-emerald-700">After: Policy-Compliant Clean Ad Image</span>
              <div class="mt-2 text-emerald-600 font-medium">[AI Inpainted: Promo Badge Removed]</div>
            </div>
          </div>
          <div id="canary_variant_checks" class="mt-2 text-xs text-gray-500">
            Variants intact: <span class="font-semibold text-emerald-600">5/5 preserved</span>
          </div>
        </div>
      </div>

      <!-- Step 2 Card: Full Catalog Batch Sync (5-Layer Layout) -->
      <div id="card-catalog-sync" class="action-card bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <div class="layer-1-badge mb-2">
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">Step 2 • Full Catalog</span>
        </div>
        <div class="layer-2-title mb-1">
          <h4 class="text-base font-bold text-gray-900" data-i18n="step2_title">Sync All Existing Products (Full Catalog Ad-Feed Generation)</h4>
        </div>
        <div class="layer-3-description mb-4">
          <p class="text-xs text-gray-500" data-i18n="step2_desc">
            Non-destructive background generation of clean ad images into metafields across your entire catalog.
          </p>
        </div>
        <div class="layer-4-actions flex items-center space-x-3 mb-4">
          <button id="btn_start_batch" class="px-4 py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition" data-i18n="btn_start_batch">
            Start Full Catalog Batch Sync
          </button>
          <button id="btn_abort_batch" class="px-4 py-2 text-sm font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition" data-i18n="btn_abort_batch">
            Instant Stop (Circuit Breaker)
          </button>
        </div>
        <div class="layer-5-preview" id="batch_progress_container">
          <div class="p-3 bg-gray-50 rounded-lg border text-xs text-gray-600">
            Status: <span id="batch_status_text" class="font-semibold">{store.job_state.get('status', 'IDLE')}</span>
          </div>
        </div>
      </div>

      <!-- Step 3 Card: 1-Click Rollback (5-Layer Layout) -->
      <div id="card-rollback" class="action-card bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <div class="layer-1-badge mb-2">
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">Step 3 • Safety Net</span>
        </div>
        <div class="layer-2-title mb-1">
          <h4 class="text-base font-bold text-gray-900" data-i18n="step3_title">1-Click Rollback (Time Machine)</h4>
        </div>
        <div class="layer-3-description mb-4">
          <p class="text-xs text-gray-500" data-i18n="step3_desc">
            Instantly revert all metafield values and variant mappings from Cloudflare R2 immutable snapshot in under 10 seconds.
          </p>
        </div>
        <div class="layer-4-actions flex items-center space-x-3 mb-4">
          <button id="btn_rollback" class="px-4 py-2 text-sm font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition" data-i18n="btn_rollback">
            Revert to Previous Snapshot
          </button>
        </div>
        <div class="layer-5-preview" id="rollback_info_container">
          <div class="p-3 bg-gray-50 rounded-lg border text-xs text-gray-600">
            Latest Snapshot: <span id="latest_snapshot_id" class="font-mono">{store.latest_snapshot_id or 'None'}</span>
          </div>
        </div>
      </div>
    </section>
  </div>

  <!-- Embedded Bilingual Dictionary -->
  <script>
    const I18N = {{
      en: {{
        app_title: "AdFeed Clean for Google Shopping",
        hero_headline: "Stop Google Ad Disapprovals Due to Store Promo Badges",
        hero_subcopy: "Automatically generate clean, policy-compliant ad images in hidden Shopify metafields without touching your storefront images.",
        zone1_title: "Zone 1: Core Automation (Always-On Ad Shield)",
        step1_title: "Test on 1 Sample Product (Canary Preview)",
        step2_title: "Sync All Existing Products (Full Catalog Ad-Feed Generation)",
        step3_title: "1-Click Rollback (Time Machine)"
      }},
      ja: {{
        app_title: "AdFeed Clean: Google広告シールド",
        hero_headline: "セール帯・透かしによるGoogle広告審査落ちを完全防止",
        hero_subcopy: "ストアの装飾画像には一切触れず、隠しメタフィールドへポリシー準拠のAI白抜き画像を自動生成します。",
        zone1_title: "ゾーン1: 常時自動保護（Always-On Ad Shield）",
        step1_title: "ステップ1: 1商品で安全シミュレーション（カナリアプレビュー）",
        step2_title: "ステップ2: 既存商品の全件一括同期（カタログAd-Feed生成）",
        step3_title: "ステップ3: 1クリック・タイムマシン復元（セーフティネット）"
      }}
    }};
  </script>
</body>
</html>"""


class MockWorkerApp:
    """Core application router executing request logic in-memory or over HTTP."""

    def __init__(self):
        self.stores: Dict[str, MockStoreState] = {}

    def get_store(self, shop: str) -> MockStoreState:
        if shop not in self.stores:
            self.stores[shop] = MockStoreState(shop)
        return self.stores[shop]

    def reset_all(self):
        self.stores.clear()

    def handle_request(
        self,
        method: str,
        path_and_query: str,
        headers: Optional[Dict[str, str]] = None,
        body_bytes: bytes = b"",
    ) -> Tuple[int, bytes, Dict[str, str]]:
        headers = {k.title(): v for k, v in (headers or {}).items()}
        parsed_url = urllib.parse.urlparse(path_and_query)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # CORS preflight
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Shopify-Access-Token, X-Shopify-Shop-Domain, X-Shopify-Hmac-Sha256",
        }
        if method == "OPTIONS":
            return 204, b"", cors_headers

        # Public Legal Routes: Privacy Policy & Terms of Service
        if path == "/privacy":
            if method == "HEAD":
                return 200, b"", {**cors_headers, "Content-Type": "text/html; charset=utf-8"}
            if method == "GET":
                lang = query_params.get("lang", ["en"])[0]
                html = render_legal_from_ts("privacy", lang)
                return 200, html.encode("utf-8"), {**cors_headers, "Content-Type": "text/html; charset=utf-8"}

        if path == "/terms":
            if method == "HEAD":
                return 200, b"", {**cors_headers, "Content-Type": "text/html; charset=utf-8"}
            if method == "GET":
                lang = query_params.get("lang", ["en"])[0]
                html = render_legal_from_ts("terms", lang)
                return 200, html.encode("utf-8"), {**cors_headers, "Content-Type": "text/html; charset=utf-8"}

        # Public Asset Routes: App Icon & Promotional Banners
        if path.startswith("/assets/"):
            asset_info = get_public_asset_from_ts(path)
            if asset_info:
                if method == "HEAD":
                    return 200, b"", {**cors_headers, "Content-Type": asset_info["contentType"]}
                if method == "GET":
                    return 200, asset_info["content"].encode("utf-8"), {**cors_headers, "Content-Type": asset_info["contentType"]}
            return 404, b"Asset not found", cors_headers

        # Parse JSON body if present
        parsed_body = None
        if body_bytes:
            try:
                parsed_body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                return 400, json.dumps({"error": "Invalid JSON payload", "code": "INVALID_JSON"}).encode("utf-8"), {
                    **cors_headers,
                    "Content-Type": "application/json",
                }

        # Resolve shop domain
        shop_header = headers.get("X-Shopify-Shop-Domain")
        query_shop = query_params.get("shop", [None])[0]
        body_shop = parsed_body.get("shop") if isinstance(parsed_body, dict) else None
        requested_shop = shop_header or query_shop or body_shop or PRIMARY_SHOP

        # Security Guard 1.1: Parameter Pollution / Shop Domain Mismatch Defense
        if parsed_body and isinstance(parsed_body, dict) and parsed_body.get("shop") and parsed_body.get("shop") != requested_shop:
            return 400, json.dumps({
                "error": "Shop domain mismatch between header/query and request body.",
                "code": "SHOP_DOMAIN_MISMATCH",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # Security Guard 1: Shop Domain Regex Validation
        if not is_valid_shop_domain(requested_shop):
            return 400, json.dumps({
                "error": "Invalid Shopify store domain format.",
                "code": "INVALID_SHOP_DOMAIN",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # 1.1 API: Shopify OAuth 2.0 Authorization Initiation
        if path == "/api/auth" and method == "GET":
            if not query_shop or not is_valid_shop_domain(query_shop):
                return 400, json.dumps({
                    "error": "Invalid or missing 'shop' query parameter.",
                    "code": "INVALID_SHOP_DOMAIN",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            state = str(uuid.uuid4())
            redirect_uri = urllib.parse.quote("https://mock.safemedia.workers.dev/api/auth/callback")
            scopes = urllib.parse.quote("read_products,write_products")
            auth_url = f"https://{query_shop}/admin/oauth/authorize?client_id=safemedia_shield_app_key&scope={scopes}&redirect_uri={redirect_uri}&state={state}"
            return 302, b"", {**cors_headers, "Location": auth_url}

        # 1.2 API: Shopify OAuth 2.0 Callback
        if path == "/api/auth/callback" and method == "GET":
            query_dict = dict(urllib.parse.parse_qsl(parsed_url.query))
            code = query_dict.get("code")
            hmac_val = query_dict.get("hmac")
            state_val = query_dict.get("state")
            if not code or not hmac_val or not state_val:
                return 400, json.dumps({
                    "error": "Missing required OAuth code, state, or HMAC signature.",
                    "code": "MISSING_OAUTH_PARAMS",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            expected_hmac = compute_shopify_query_hmac(query_dict, WEBHOOK_SECRET)
            if hmac_val.lower() != expected_hmac.lower():
                return 401, json.dumps({
                    "error": "Invalid HMAC signature in OAuth callback.",
                    "code": "INVALID_OAUTH_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store = self.get_store(requested_shop)
            access_token = f"shpat_oauth_{requested_shop.split('.')[0]}_{code}"
            store.auth = {
                "shop": requested_shop,
                "accessToken": access_token,
                "scope": "read_products,write_products",
                "installedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            return 302, b"", {**cors_headers, "Location": f"https://{requested_shop}/admin/apps/safemedia_shield_app_key"}

        # 2.2d Mandatory Shopify Privacy & GDPR Webhook Handlers
        if path.startswith("/webhooks/privacy/") and method == "POST":
            if not shop_header:
                return 401, json.dumps({
                    "error": "Missing X-Shopify-Shop-Domain webhook header",
                    "code": "MISSING_WEBHOOK_HEADERS",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            hmac_header = headers.get("X-Shopify-Hmac-Sha256")
            if not hmac_header or not hmac_header.strip():
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            expected_hmac = compute_shopify_hmac(body_bytes, WEBHOOK_SECRET)
            if hmac_header.strip() != expected_hmac:
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store = self.get_store(requested_shop)
            if path == "/webhooks/privacy/customers/data_request":
                return 200, json.dumps({
                    "success": True,
                    "shop": requested_shop,
                    "message": "No customer personal data collected or stored.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            if path == "/webhooks/privacy/customers/redact":
                return 200, json.dumps({
                    "success": True,
                    "shop": requested_shop,
                    "message": "No customer personal data stored.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            if path == "/webhooks/privacy/shop/redact":
                store.catalog.clear()
                store.snapshots.clear()
                return 200, json.dumps({
                    "success": True,
                    "shop": requested_shop,
                    "message": "Shop data purged/archived successfully.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # 2.2e Mandatory Shopify App Uninstalled Webhook Handler
        if path == "/webhooks/app/uninstalled" and method == "POST":
            if not shop_header:
                return 401, json.dumps({
                    "error": "Missing X-Shopify-Shop-Domain webhook header",
                    "code": "MISSING_WEBHOOK_HEADERS",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            hmac_header = headers.get("X-Shopify-Hmac-Sha256")
            if not hmac_header or not hmac_header.strip():
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            expected_hmac = compute_shopify_hmac(body_bytes, WEBHOOK_SECRET)
            if hmac_header.strip() != expected_hmac:
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store = self.get_store(requested_shop)
            store.auto_sync_enabled = False
            store.circuit_breaker_tripped = True
            if hasattr(store, "auth") and store.auth:
                store.auth["uninstalledAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "message": "App uninstall processed successfully.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # Webhook Route Specific Security
        if path == "/webhooks/products/update":
            if not shop_header:
                return 401, json.dumps({
                    "error": "Missing X-Shopify-Shop-Domain webhook header",
                    "code": "MISSING_WEBHOOK_HEADERS",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Security Guard 4: Mandatory Shopify Webhook HMAC-SHA256 Verification
            hmac_header = headers.get("X-Shopify-Hmac-Sha256")
            if not hmac_header or not hmac_header.strip():
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            expected_hmac = compute_shopify_hmac(body_bytes, WEBHOOK_SECRET)
            if hmac_header.strip() != expected_hmac:
                return 401, json.dumps({
                    "error": "unauthorized",
                    "message": "Missing or invalid HMAC signature",
                    "code": "INVALID_WEBHOOK_HMAC",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store = self.get_store(requested_shop)

            # Webhook Idempotency Check (X-Shopify-Webhook-Id)
            webhook_id_header = headers.get("X-Shopify-Webhook-Id")
            if webhook_id_header and webhook_id_header.strip():
                wid = webhook_id_header.strip()
                seen_at = store.processed_webhook_ids.get(wid)
                if seen_at and time.time() - seen_at < 86400:
                    return 200, json.dumps({
                        "success": True,
                        "skipped": True,
                        "reason": "duplicate_webhook_id",
                        "webhookId": wid,
                        "message": "Duplicate Shopify webhook event ignored (idempotent).",
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Circuit Breaker Check
            if store.circuit_breaker_tripped:
                return 423, json.dumps({
                    "success": False,
                    "skipped": True,
                    "reason": "circuit_breaker_tripped",
                    "message": "Emergency Stop is active. Background processing is paused.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Auto-Sync Toggle Check
            if not store.auto_sync_enabled:
                return 200, json.dumps({
                    "success": True,
                    "skipped": True,
                    "reason": "auto_sync_disabled",
                    "message": "Auto-Sync on Product Update is currently disabled.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            payload = parsed_body or {}
            product_id = payload.get("id")
            if not product_id:
                return 200, json.dumps({"skipped": True, "reason": "missing_product_id"}).encode("utf-8"), {
                    **cors_headers,
                    "Content-Type": "application/json",
                }

            prod_gid = str(product_id) if str(product_id).startswith("gid://") else f"gid://shopify/Product/{product_id}"
            primary_img = (payload.get("image") or {}).get("src") or (payload.get("images") or [{}])[0].get("src")
            if not primary_img:
                return 200, json.dumps({"skipped": True, "reason": "no_product_image"}).encode("utf-8"), {
                    **cors_headers,
                    "Content-Type": "application/json",
                }

            # SSRF Validation
            if not is_valid_public_image_url(primary_img):
                return 400, json.dumps({
                    "error": "Invalid or unsafe image URL.",
                    "code": "INVALID_IMAGE_URL",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Quota Check for Unsubscribed Stores
            if store.plan_status == "CANARY_TRIAL" and store.canary_used_count >= store.canary_limit:
                return 402, json.dumps({
                    "error": f"Free preview limit ({store.canary_limit}/{store.canary_limit} items) reached. Please start your 14-day free trial ($65/mo) to continue automatic ad-feed cleanup.",
                    "code": "TRIAL_QUOTA_EXCEEDED",
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Trial 50-Item Cap Guard
            if store.plan_status in ("TRIAL_ACTIVE", "TRIAL_14D_ACTIVE", "TRIAL_CAP_REACHED"):
                if store.plan_status == "TRIAL_CAP_REACHED" or store.trial_used_count >= store.trial_limit:
                    store.plan_status = "TRIAL_CAP_REACHED"
                    return 402, json.dumps({
                        "error": f"Free trial quota ({store.trial_limit}/{store.trial_limit} images) completed. Please activate your subscription ($65/mo) to unlock unlimited catalog processing.",
                        "code": "TRIAL_CAP_REACHED",
                        "trialUsedCount": store.trial_used_count,
                        "trialLimit": store.trial_limit,
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Webhook Concurrency Guard: 2 parallel slots per shop
            now = time.time()
            # Clean expired slots (TTL 45s)
            store.active_gpu_slots = {k: v for k, v in store.active_gpu_slots.items() if now - v < 45}
            acquired_slot = None
            for slot_id in (1, 2):
                if slot_id not in store.active_gpu_slots:
                    acquired_slot = slot_id
                    store.active_gpu_slots[slot_id] = now
                    break

            if acquired_slot is None:
                return 200, json.dumps({
                    "success": True,
                    "skipped": True,
                    "reason": "concurrency_limit_exceeded",
                    "productId": prod_gid,
                    "message": "Concurrent GPU execution limit (2 slots) reached. Queued/skipped to avoid burst costs.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Concurrency / In-Flight lock check
            lock_key = f"{requested_shop}:{prod_gid}"
            if lock_key in store.in_flight_locks and now - store.in_flight_locks[lock_key] < 60:
                store.active_gpu_slots.pop(acquired_slot, None)
                return 200, json.dumps({
                    "success": True,
                    "skipped": True,
                    "reason": "already_processing_in_flight",
                    "productId": prod_gid,
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store.in_flight_locks[lock_key] = now
            try:
                target_prod = next((p for p in store.catalog if p["id"] == prod_gid), None)
                if target_prod:
                    current_clean = target_prod.get("metafields", {}).get("safemedia.clean_ad_image_url")
                    if current_clean and not payload.get("force_reclean"):
                        if webhook_id_header and webhook_id_header.strip():
                            store.processed_webhook_ids[webhook_id_header.strip()] = now
                        return 200, json.dumps({
                            "success": True,
                            "skipped": True,
                            "reason": "already_cleaned_for_current_image",
                            "productId": prod_gid,
                            "cleanAdImageUrl": current_clean,
                        }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                # Rollback Suppression Guard:
                # Prevent webhook echoes or subsequent edits from triggering auto-cleanup
                # and incrementing monthly usage when product was reverted via 1-Click Rollback.
                if store.last_rollback and not payload.get("force_reclean"):
                    diffs = store.last_rollback.get("productDataDiffs") or []
                    rb_diff = next((d for d in diffs if d.get("productId") == prod_gid or d.get("productId") == str(product_id)), None)
                    if rb_diff and not rb_diff.get("clearedAfterRollback") and not rb_diff.get("skipped"):
                        after_revert = rb_diff.get("afterRevert") or {}
                        is_same_img = (
                            rb_diff.get("storefrontImageUrl") == primary_img or
                            after_revert.get("storefrontImageUrl") == primary_img
                        )
                        if is_same_img:
                            reverted_at_str = rb_diff.get("revertedAt")
                            reverted_ts = time.time()
                            if reverted_at_str:
                                try:
                                    import datetime
                                    reverted_ts = datetime.datetime.fromisoformat(reverted_at_str.replace("Z", "+00:00")).timestamp()
                                except Exception:
                                    reverted_ts = time.time()
                            time_since_revert = time.time() - reverted_ts
                            is_recent = 0 <= time_since_revert < 120
                            is_purged_virgin = after_revert.get("metafieldAction") == "PURGED_TO_VIRGIN"
                            if is_recent or is_purged_virgin:
                                if webhook_id_header and webhook_id_header.strip():
                                    store.processed_webhook_ids[webhook_id_header.strip()] = now
                                return 200, json.dumps({
                                    "success": True,
                                    "skipped": True,
                                    "reason": "reverted_by_rollback",
                                    "productId": prod_gid,
                                    "revertedAt": reverted_at_str,
                                    "message": "Product was restored to virgin snapshot state via 1-Click Rollback. Auto-sync skipped to prevent billing increment.",
                                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                # Pre-Flight Usage Charge for ACTIVE Plan (501+ images)
                if store.plan_status == "ACTIVE" and store.monthly_usage_count >= store.monthly_included_count:
                    if getattr(store, "simulate_capped_amount_exceeded", False):
                        store.plan_status = "PAUSED_USAGE_CAP_REACHED"
                        store.circuit_breaker_tripped = True
                        return 402, json.dumps({
                            "error": "Monthly usage charge cap ($100.00) reached. Processing paused to prevent unexpected charges.",
                            "code": "USAGE_CAP_REACHED",
                        }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                clean_ad_url = f"https://cdn.safemedia.io/clean/{requested_shop}/{int(now)}_cleaned.jpg"
                if target_prod:
                    target_prod.setdefault("metafields", {})["safemedia.clean_ad_image_url"] = clean_ad_url
                    target_prod["dualFeedMetadata"] = {
                        "sourceImageUrl": primary_img,
                        "cleanedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "maskCoveragePct": 7.8,
                        "processingSec": 1.45,
                        "engine": "Florence2-LaMa-DualFeed-v1",
                    }

                if store.plan_status == "CANARY_TRIAL":
                    store.canary_used_count = min(store.canary_limit, store.canary_used_count + 1)
                elif store.plan_status in ("TRIAL_ACTIVE", "TRIAL_14D_ACTIVE"):
                    store.trial_used_count += 1
                elif store.plan_status == "ACTIVE":
                    store.monthly_usage_count += 1

                if webhook_id_header and webhook_id_header.strip():
                    store.processed_webhook_ids[webhook_id_header.strip()] = now

                return 200, json.dumps({
                    "success": True,
                    "skipped": False,
                    "productId": prod_gid,
                    "productTitle": payload.get("title", target_prod.get("title") if target_prod else "Sample"),
                    "storefrontImageUrl": primary_img,
                    "cleanAdImageUrl": clean_ad_url,
                    "metafieldNamespace": "safemedia",
                    "metafieldKey": "clean_ad_image_url",
                    "processingSec": 1.45,
                    "maskCoveragePct": 7.8,
                    "engine": "Florence2-LaMa-DualFeed-v1",
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                    "trialUsedCount": store.trial_used_count,
                    "trialLimit": store.trial_limit,
                    "monthlyUsageCount": store.monthly_usage_count,
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}
            finally:
                store.in_flight_locks.pop(lock_key, None)
                if acquired_slot is not None:
                    store.active_gpu_slots.pop(acquired_slot, None)

        # Security Guard 2: Multi-Tenant Isolation on Non-Webhook Endpoints
        token = headers.get("X-Shopify-Access-Token")
        if requested_shop != PRIMARY_SHOP:
            if not token or not token.strip():
                return 403, json.dumps({
                    "error": "Cross-tenant access denied. Missing store authentication token for requested shop.",
                    "code": "CROSS_TENANT_ACCESS_DENIED",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Verify token authenticity
            is_valid_token = False
            if requested_shop == OTHER_SHOP and token.strip() in ("mock_token_for_store_b", "store_b_secret_token"):
                is_valid_token = True
            elif token.strip() == "test_admin_api_secret_key_123":
                is_valid_token = True

            if not is_valid_token:
                return 403, json.dumps({
                    "error": "Cross-tenant access denied. Invalid store authentication token for requested shop.",
                    "code": "CROSS_TENANT_ACCESS_DENIED",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        store = self.get_store(requested_shop)

        def build_feed_preview_payload() -> Dict[str, Any]:
            items = []
            for p in store.catalog:
                clean_url = (p.get("metafields") or {}).get("safemedia.clean_ad_image_url")
                if not clean_url:
                    continue
                numeric_id = "".join(c for c in p["id"] if c.isdigit()) or "1001"
                sf_url = (p.get("media") or [{}])[0].get("url", "")
                mapped_url = clean_url
                items.append({
                    "productId": p["id"],
                    "productTitle": p["title"],
                    "storefrontUrl": f"https://{requested_shop}/products/product-{numeric_id}",
                    "storefrontImageUrl": sf_url,
                    "cleanAdImageUrl": clean_url,
                    "googleShoppingFeedItem": {
                        "g:id": f"shopify_US_{numeric_id}_3001",
                        "g:title": p["title"],
                        "g:image_link": mapped_url,
                        "storefront_original_preserved": sf_url,
                    },
                    "metaCatalogFeedItem": {
                        "id": numeric_id,
                        "title": p["title"],
                        "image_link": mapped_url,
                    },
                })
            return {
                "shop": requested_shop,
                "metafieldNamespace": "safemedia",
                "metafieldKey": "clean_ad_image_url",
                "metafieldDefinitionPinned": True,
                "channelMappings": {
                    "googleShopping": {
                        "channelApp": "Google & YouTube Channel / Google Merchant Center",
                        "targetAttribute": "g:image_link",
                        "sourceMetafield": "product.metafields.safemedia.clean_ad_image_url",
                        "status": "MAPPED_AND_READY" if items else "READY_WAITING_CLEAN_ITEMS",
                    },
                    "metaCatalog": {
                        "channelApp": "Facebook & Instagram Channel / Meta Commerce Manager",
                        "targetAttribute": "image_link",
                        "sourceMetafield": "product.metafields.safemedia.clean_ad_image_url",
                        "status": "MAPPED_AND_READY" if items else "READY_WAITING_CLEAN_ITEMS",
                    },
                },
                "items": items,
            }

        # GET / (HTML Dashboard)
        if path == "/" and method == "GET":
            if os.environ.get("VERIFY_M2_UI", "1") == "1":
                html = render_dashboard_from_ui_ts(requested_shop, store).encode("utf-8")
            else:
                html = render_mock_ui_html(requested_shop, store).encode("utf-8")
            return 200, html, {**cors_headers, "Content-Type": "text/html; charset=utf-8"}

        # GET /api/status
        if path == "/api/status" and method == "GET":
            dual_feed_products = []
            for p in store.catalog:
                clean_url = p.get("metafields", {}).get("safemedia.clean_ad_image_url")
                dual_feed_products.append({
                    "productId": p["id"],
                    "productTitle": p["title"],
                    "storefrontImageUrl": (p.get("media") or [{}])[0].get("url", ""),
                    "cleanAdImageUrl": clean_url,
                    "dualFeedMetadata": p.get("dualFeedMetadata"),
                })

            feed_preview = build_feed_preview_payload()
            resp = {
                "shop": requested_shop,
                "protectionActive": not store.circuit_breaker_tripped,
                "billing": {
                    "shop": requested_shop,
                    "planStatus": store.plan_status,
                    "planName": store.plan_name,
                    "priceUsd": store.price_usd,
                    "trialDays": store.trial_days,
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                    "trialUsedCount": store.trial_used_count,
                    "trialLimit": store.trial_limit,
                    "monthlyIncludedCount": store.monthly_included_count,
                    "monthlyUsageCount": store.monthly_usage_count,
                    "circuitBreakerTripped": store.circuit_breaker_tripped,
                    "autoSyncEnabled": store.auto_sync_enabled,
                },
                "r2BucketName": "safemedia-snapshots",
                "r2Objects": [f"snapshots/{requested_shop}/{sid}.json" for sid in store.snapshots],
                "latestSnapshot": {
                    "snapshotId": store.latest_snapshot_id,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "totalProducts": len(store.catalog),
                } if store.latest_snapshot_id else None,
                "dualFeedProducts": dual_feed_products,
                "feedPreview": feed_preview,
                "lastRollback": store.last_rollback,
                "lastRollbackDiffs": (store.last_rollback or {}).get("productDataDiffs", []),
                "jobState": store.job_state,
            }
            return 200, json.dumps(resp).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # GET /api/feed-preview
        if path in ("/api/feed-preview", "/api/ad-feed/preview", "/api/feed-preview.xml") and method == "GET":
            feed_preview = build_feed_preview_payload()
            if path.endswith(".xml") or query_params.get("format", [""])[0] == "xml":
                xml_items = "\n".join(
                    f"    <item><g:id>{it['googleShoppingFeedItem']['g:id']}</g:id>"
                    f"<g:image_link>{it['googleShoppingFeedItem']['g:image_link']}</g:image_link></item>"
                    for it in feed_preview["items"]
                )
                xml_doc = (
                    f'<?xml version="1.0" encoding="UTF-8"?>\n'
                    f'<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
                    f'  <channel>\n{xml_items}\n  </channel>\n</rss>'
                )
                return 200, xml_doc.encode("utf-8"), {**cors_headers, "Content-Type": "application/xml; charset=utf-8"}
            return 200, json.dumps(feed_preview).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/admin/purge-metafields
        if path == "/api/admin/purge-metafields" and method in ("POST", "GET"):
            purged_count = 0
            for p in store.catalog:
                if (p.get("metafields") or {}).pop("safemedia.clean_ad_image_url", None):
                    purged_count += 1
                (p.get("metafields") or {}).pop("safemedia.dual_feed_metadata", None)
            store.canary_used_count = 0
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "purgedCount": purged_count,
                "canaryUsedCount": 0,
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/billing/subscribe
        if path == "/api/billing/subscribe" and method == "POST":
            # Dynamic trial calculation (Anti-Trial Abuse / Reinstall Defense)
            if store.has_ever_subscribed:
                allowed_trial_days = 0
            elif store.first_installed_at:
                elapsed_days = int((time.time() - store.first_installed_at) / 86400)
                allowed_trial_days = max(0, 14 - elapsed_days) if elapsed_days < 14 else 0
            else:
                allowed_trial_days = 14
                store.first_installed_at = time.time()

            store.trial_days = allowed_trial_days
            store.plan_status = "ACTIVE" if allowed_trial_days == 0 else "TRIAL_14D_ACTIVE"
            store.auto_sync_enabled = True
            store.canary_used_count = 0  # Unblock canary with fresh 5-sample limit for trial verification
            if allowed_trial_days == 0:
                store.has_ever_subscribed = True
            return 200, json.dumps({
                "success": True,
                "allowedTrialDays": allowed_trial_days,
                "billing": {
                    "shop": requested_shop,
                    "planStatus": store.plan_status,
                    "planName": store.plan_name,
                    "priceUsd": 65,
                    "trialDays": allowed_trial_days,
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                    "trialUsedCount": store.trial_used_count,
                    "trialLimit": store.trial_limit,
                    "monthlyIncludedCount": store.monthly_included_count,
                    "monthlyUsageCount": store.monthly_usage_count,
                    "circuitBreakerTripped": store.circuit_breaker_tripped,
                    "autoSyncEnabled": store.auto_sync_enabled,
                    "hasEverSubscribed": store.has_ever_subscribed,
                },
                "confirmationUrl": f"https://{requested_shop}/admin/charges/confirm_trial",
                "mode": "production_subscription",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/billing/activate-now (Immediate Activation, trialDays: 0)
        if path == "/api/billing/activate-now" and method == "POST":
            store.plan_status = "ACTIVE"
            store.trial_days = 0
            store.auto_sync_enabled = True
            return 200, json.dumps({
                "success": True,
                "confirmationUrl": f"https://{requested_shop}/admin/charges/confirm_active_now",
                "subscriptionId": "gid://shopify/AppSubscription/active_now_123",
                "billing": {
                    "shop": requested_shop,
                    "planStatus": store.plan_status,
                    "planName": store.plan_name,
                    "priceUsd": 65,
                    "trialDays": 0,
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                    "trialUsedCount": store.trial_used_count,
                    "trialLimit": store.trial_limit,
                    "monthlyIncludedCount": store.monthly_included_count,
                    "monthlyUsageCount": store.monthly_usage_count,
                    "circuitBreakerTripped": store.circuit_breaker_tripped,
                    "autoSyncEnabled": store.auto_sync_enabled,
                },
                "mode": "production_subscription",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/billing/reset
        if path == "/api/billing/reset" and method == "POST":
            body = parsed_body or {}
            store.reset(
                plan_status=body.get("planStatus", "CANARY_TRIAL"),
                canary_used=body.get("canaryUsedCount", 0),
                trial_used=body.get("trialUsedCount", 0),
                monthly_usage=body.get("monthlyUsageCount", 0),
                trial_limit=body.get("trialLimit", 50),
                monthly_included=body.get("monthlyIncludedCount", 500),
                circuit_breaker=bool(body.get("circuitBreakerTripped", False)),
                empty_catalog=bool(body.get("emptyCatalog", False)),
                has_ever_subscribed=bool(body.get("hasEverSubscribed", False)),
                first_installed_at=body.get("firstInstalledAt"),
            )
            if "simulateCappedAmountExceeded" in body:
                store.simulate_capped_amount_exceeded = bool(body["simulateCappedAmountExceeded"])
            return 200, json.dumps({
                "success": True,
                "billing": {
                    "shop": requested_shop,
                    "planStatus": store.plan_status,
                    "canaryUsedCount": store.canary_used_count,
                    "trialUsedCount": store.trial_used_count,
                    "monthlyUsageCount": store.monthly_usage_count,
                    "trialLimit": store.trial_limit,
                    "monthlyIncludedCount": store.monthly_included_count,
                    "circuitBreakerTripped": store.circuit_breaker_tripped,
                },
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/webhooks/register
        if path == "/api/webhooks/register" and method == "POST":
            store.auto_sync_enabled = True
            store.webhook_id = "gid://shopify/WebhookSubscription/9991"
            return 200, json.dumps({
                "webhookId": store.webhook_id,
                "topic": "PRODUCTS_UPDATE",
                "autoSyncEnabled": True,
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/webhooks/unregister
        if path == "/api/webhooks/unregister" and method == "POST":
            store.auto_sync_enabled = False
            store.webhook_id = None
            return 200, json.dumps({
                "success": True,
                "autoSyncEnabled": False,
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/auto-sync/toggle
        if path == "/api/auto-sync/toggle" and method == "POST":
            if store.plan_status == "CANARY_TRIAL":
                return 402, json.dumps({
                    "success": False,
                    "error": "Always-on Auto-Protection requires activating your 14-day free trial ($65/mo).",
                    "code": "SUBSCRIPTION_REQUIRED_FOR_AUTOSYNC",
                    "planStatus": store.plan_status,
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            store.auto_sync_enabled = not store.auto_sync_enabled
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "autoSyncEnabled": store.auto_sync_enabled,
                "message": f"Auto-sync {'enabled' if store.auto_sync_enabled else 'disabled'}.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # GET /api/products
        if path == "/api/products" and method == "GET":
            products_list = []
            for p in store.catalog:
                has_clean = bool(p.get("clean_ad_image_url") or p.get("metafields", {}).get("safemedia.clean_ad_image_url"))
                orig_media = (p.get("media") or [{}])[0].get("url", "")
                resolved_title = p.get("title") or p.get("productTitle", "Untitled Product")
                products_list.append({
                    "id": p["id"],
                    "title": resolved_title,
                    "productTitle": resolved_title,
                    "imageUrl": orig_media,
                    "variantCount": len(p.get("variants", [])),
                    "hasCleanAdImage": has_clean,
                    "cleanAdImageUrl": p.get("clean_ad_image_url") or p.get("metafields", {}).get("safemedia.clean_ad_image_url"),
                })
            return 200, json.dumps({"products": products_list}).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/canary/test
        if path == "/api/canary/test" and method == "POST":
            if store.circuit_breaker_tripped:
                return 423, json.dumps({
                    "error": "Emergency Stop is currently active. Resume protection before running tests.",
                    "code": "CIRCUIT_BREAKER_ACTIVE",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            # Quota Check & Atomic Pre-Reservation
            quota_reserved = False
            if store.plan_status in ("CANARY_TRIAL", "TRIAL_14D_ACTIVE", "TRIAL_ACTIVE"):
                if store.canary_used_count >= store.canary_limit:
                    limit_msg = (
                        f"You have used all {store.canary_limit} free sample tests. Start your 14-day free trial ($65/mo) to unlock unlimited products."
                        if store.plan_status == "CANARY_TRIAL"
                        else f"Canary preview limit reached ({store.canary_limit}/{store.canary_limit}). Proceed with full catalog sync."
                    )
                    return 402, json.dumps({
                        "error": limit_msg,
                        "code": "TRIAL_QUOTA_EXCEEDED",
                        "canaryUsedCount": store.canary_used_count,
                        "canaryLimit": store.canary_limit,
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}
                store.canary_used_count += 1
                quota_reserved = True

            try:
                if len(store.catalog) == 0:
                    if quota_reserved:
                        store.canary_used_count = max(0, store.canary_used_count - 1)
                        quota_reserved = False
                    return 400, json.dumps({
                        "error": "No products found in store.",
                        "code": "EMPTY_CATALOG",
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                req_product_id = parsed_body.get("productId") if isinstance(parsed_body, dict) else None
                if req_product_id:
                    matched = [p for p in store.catalog if p.get("id") == req_product_id or str(p.get("id", "")).endswith(str(req_product_id))]
                    if not matched:
                        if quota_reserved:
                            store.canary_used_count = max(0, store.canary_used_count - 1)
                            quota_reserved = False
                        return 404, json.dumps({
                            "error": f"Product with ID {req_product_id} not found.",
                            "code": "PRODUCT_NOT_FOUND",
                        }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}
                    target_prod = matched[0]
                else:
                    prods_with_media = [p for p in store.catalog if (p.get("media") or []) and (p.get("media") or [{}])[0].get("url")]
                    base_pool = prods_with_media if len(prods_with_media) > 0 else store.catalog
                    uncleaned = [
                        p for p in base_pool
                        if not p.get("clean_ad_image_url") and not p.get("metafields", {}).get("safemedia.clean_ad_image_url")
                    ]
                    candidates = uncleaned if len(uncleaned) > 0 else base_pool
                    target_prod = max(candidates, key=lambda p: len(p.get("variants", [])))

                media_list = target_prod.get("media") or []
                orig_img = media_list[0].get("url") if len(media_list) > 0 else None

                if not orig_img:
                    if quota_reserved:
                        store.canary_used_count = max(0, store.canary_used_count - 1)
                        quota_reserved = False
                    return 400, json.dumps({
                        "error": "No product image found. Please add an image to your product in Shopify before running the test.",
                        "message": "No product image found. Please add an image to your product in Shopify before running the test.",
                        "code": "NO_PRODUCT_IMAGE",
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                if not is_valid_public_image_url(orig_img):
                    if quota_reserved:
                        store.canary_used_count = max(0, store.canary_used_count - 1)
                        quota_reserved = False
                    return 400, json.dumps({
                        "error": "Target product image URL is unsafe or invalid.",
                        "code": "INVALID_IMAGE_URL",
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

                clean_img = f"https://cdn.safemedia.io/clean/{requested_shop}/canary_{int(time.time())}.jpg"
                target_prod["clean_ad_image_url"] = clean_img
                if "metafields" not in target_prod:
                    target_prod["metafields"] = {}
                target_prod["metafields"]["safemedia.clean_ad_image_url"] = clean_img
                store.clear_rollback_record_for_product(target_prod["id"])

                variant_checks = [
                    {
                        "variantId": v["id"],
                        "title": v["title"],
                        "hasOriginalMedia": bool(v.get("media_id")),
                        "preserved": bool(v.get("media_id")),
                    }
                    for v in target_prod.get("variants", [])
                ]

                canary_resp = {
                    "productId": target_prod["id"],
                    "productTitle": target_prod["title"],
                    "originalImageUrl": orig_img,
                    "cleanAdImageUrl": clean_img,
                    "metafieldKey": "safemedia.clean_ad_image_url",
                    "aiMetadata": {
                        "processingSec": 1.32,
                        "maskCoveragePct": 9.2,
                        "engine": "Florence2-LaMa-DualFeed-v1",
                    },
                    "variantChecks": variant_checks,
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                }
                return 200, json.dumps(canary_resp).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}
            except Exception as e:
                if quota_reserved:
                    store.canary_used_count = max(0, store.canary_used_count - 1)
                    quota_reserved = False
                return 500, json.dumps({"error": str(e)}).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/batch/start
        if path == "/api/batch/start" and method == "POST":
            if store.plan_status == "CANARY_TRIAL":
                return 402, json.dumps({
                    "error": "Full-catalog bulk processing requires activating your 14-day free trial ($65/mo).",
                    "code": "SUBSCRIPTION_REQUIRED_FOR_BULK",
                    "canaryUsedCount": store.canary_used_count,
                    "canaryLimit": store.canary_limit,
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            if len(store.catalog) == 0:
                return 200, json.dumps({
                    "success": True,
                    "jobId": "snap_empty",
                    "totalProducts": 0,
                    "message": "Empty catalog. Zero products to process.",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            snap_id = store.create_snapshot()
            store.circuit_breaker_tripped = False

            for p in store.catalog:
                clean_url = f"https://cdn.safemedia.io/clean/{requested_shop}/{p['id'].split('/')[-1]}_clean.jpg"
                p.setdefault("metafields", {})["safemedia.clean_ad_image_url"] = clean_url
                store.clear_rollback_record_for_product(p["id"])
                p["dualFeedMetadata"] = {
                    "sourceImageUrl": (p.get("media") or [{}])[0].get("url", ""),
                    "cleanedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "maskCoveragePct": 8.0,
                    "processingSec": 1.2,
                    "engine": "Florence2-LaMa-DualFeed-v1",
                }

            store.job_state = {
                "jobId": snap_id,
                "shop": requested_shop,
                "status": "COMPLETED",
                "total": len(store.catalog),
                "processed": len(store.catalog),
                "errors": [],
            }

            return 200, json.dumps({
                "success": True,
                "jobId": snap_id,
                "totalProducts": len(store.catalog),
                "snapshotId": snap_id,
                "message": "Full catalog ad-feed generation started. Storefront images remain unaltered.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/batch/abort
        if path == "/api/batch/abort" and method == "POST":
            store.job_state["status"] = "ABORTED"
            store.circuit_breaker_tripped = True
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "jobState": store.job_state,
                "circuitBreakerTripped": True,
                "message": "Circuit breaker activated. All processing for this store is immediately halted.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/batch/resume
        if path == "/api/batch/resume" and method == "POST":
            store.circuit_breaker_tripped = False
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "circuitBreakerTripped": False,
                "message": "Protection resumed.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/batch/cancel
        if path == "/api/batch/cancel" and method == "POST":
            store.job_state["status"] = "CANCELLED"
            store.job_state["estimatedRemainingSec"] = 0
            store.circuit_breaker_tripped = False
            return 200, json.dumps({
                "success": True,
                "shop": requested_shop,
                "jobState": store.job_state,
                "circuitBreakerTripped": False,
                "message": "Batch processing cancelled and cleared. Safe operations resumed.",
            }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        # POST /api/rollback
        if path == "/api/rollback" and method == "POST":
            target_snap_id = (parsed_body or {}).get("snapshotId")
            if target_snap_id:
                clean_snap_id = target_snap_id[:-5] if target_snap_id.endswith(".json") else target_snap_id
                if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", clean_snap_id):
                    return 500, json.dumps({
                        "success": False,
                        "error": "Invalid snapshotId format. Path traversal or invalid characters detected.",
                        "code": "INVALID_SNAPSHOT_ID",
                    }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            success, restored_count, snap_id, diffs, snap_ts = store.restore_snapshot(target_snap_id)
            if not success:
                return 500, json.dumps({
                    "success": False,
                    "error": "No snapshot found to rollback or invalid snapshotId.",
                    "code": "SNAPSHOT_NOT_FOUND",
                }).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

            reverted_at = diffs[0]["revertedAt"] if diffs else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            rb_result = {
                "success": True,
                "restoredCount": restored_count,
                "restoredProducts": restored_count,
                "snapshotId": snap_id,
                "snapshotTimestamp": snap_ts,
                "revertedAt": reverted_at,
                "metafieldsRestored": True,
                "productDataDiffs": diffs,
                "beforeAfterComparisons": diffs,
                "message": "Store media and ad-feed metafields restored successfully.",
            }
            store.last_rollback = rb_result
            return 200, json.dumps(rb_result).encode("utf-8"), {**cors_headers, "Content-Type": "application/json"}

        return 404, json.dumps({"error": "Not Found"}).encode("utf-8"), {
            **cors_headers,
            "Content-Type": "application/json",
        }


class HttpResponseWrapper:
    def __init__(self, status_code: int, content: bytes, headers: Dict[str, str]):
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self._text: Optional[str] = None
        self._json: Optional[Any] = None

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self.content.decode("utf-8", errors="replace")
        return self._text

    def json(self) -> Any:
        if self._json is None:
            self._json = json.loads(self.text)
        return self._json


class TestClient:
    """
    Universal test client.
    - If base_url is None: dispatches in-memory directly via MockWorkerApp (zero network sockets, lightning fast).
    - If base_url is provided (e.g. 'https://safemedia-shield-worker...'): dispatches real HTTP requests over the wire.
    """

    def __init__(self, base_url: Optional[str] = None, app: Optional[MockWorkerApp] = None):
        resolved_base_url = base_url or os.environ.get("BASE_URL")
        self.base_url = resolved_base_url.rstrip("/") if resolved_base_url else None
        self.app = app or MockWorkerApp()

    def request(
        self,
        method: str,
        path: str,
        json_data: Any = None,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 15.0,
    ) -> HttpResponseWrapper:
        # Live network mode
        if self.base_url:
            url = f"{self.base_url}{path}"
            req_headers = headers.copy() if headers else {}
            body_bytes = None
            if json_data is not None:
                body_bytes = json.dumps(json_data).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            elif data is not None:
                body_bytes = data

            req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return HttpResponseWrapper(resp.status, resp.read(), dict(resp.headers))
            except urllib.error.HTTPError as e:
                return HttpResponseWrapper(e.code, e.read(), dict(e.headers))

        # In-memory dispatch mode
        req_headers = headers.copy() if headers else {}
        body_bytes = b""
        if json_data is not None:
            body_bytes = json.dumps(json_data).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            body_bytes = data

        status, content, resp_headers = self.app.handle_request(method, path, req_headers, body_bytes)
        return HttpResponseWrapper(status, content, resp_headers)

    def get(self, path: str, headers: Optional[Dict[str, str]] = None, timeout: float = 15.0):
        return self.request("GET", path, headers=headers, timeout=timeout)

    def post(self, path: str, json_data: Any = None, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 15.0):
        return self.request("POST", path, json_data=json_data, data=data, headers=headers, timeout=timeout)
