"""
Post-Phase 3 Security & Architecture Remediation Regression Tests (High / Medium / Low).
Verifies every remediation applied after the post-Phase 3 audit stays enforced.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_repo_file(rel_path: str) -> str:
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8") as f:
        return f.read()


class TestPostPhase3SecurityRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index_ts = read_repo_file("cloudflare_worker/src/index.ts")
        cls.runpod_client_ts = read_repo_file("cloudflare_worker/src/runpod_client.ts")
        cls.shopify_ts = read_repo_file("cloudflare_worker/src/shopify.ts")
        cls.snapshot_ts = read_repo_file("cloudflare_worker/src/snapshot.ts")
        cls.legal_ts = read_repo_file("cloudflare_worker/src/legal.ts")
        cls.ui_ts = read_repo_file("cloudflare_worker/src/ui.ts")
        cls.worker_handler_py = read_repo_file("runpod_worker/handler.py")
        cls.root_handler_py = read_repo_file("handler.py")

    def test_handler_py_root_and_worker_identical(self) -> None:
        self.assertEqual(
            self.root_handler_py,
            self.worker_handler_py,
            "Root handler.py and runpod_worker/handler.py must stay synchronized",
        )

    def test_python_handler_hardening(self) -> None:
        self.assertIn("Image.MAX_IMAGE_PIXELS = 16_000_000", self.worker_handler_py)
        self.assertIn("class _PinnedHTTPSConnection(http.client.HTTPSConnection):", self.worker_handler_py)
        self.assertIn("ALLOW_RUNTIME_MODEL_DOWNLOAD", self.worker_handler_py)
        self.assertIn("LAMA_MODEL_SHA256", self.worker_handler_py)
        self.assertIn("FLORENCE_MODEL_REVISION", self.worker_handler_py)
        self.assertNotIn("traceback.format_exc()", self.worker_handler_py)
        self.assertNotIn("data:image/svg+xml", self.worker_handler_py)

    def test_callback_hmac_fail_closed_and_canonical_binding(self) -> None:
        self.assertNotIn("safemedia_callback_default", self.index_ts)
        fn_match = re.search(
            r"async function generateRunPodCallbackSig\([\s\S]*?\n\}",
            self.index_ts,
        )
        self.assertIsNotNone(fn_match)
        fn_body = fn_match.group(0)
        for field in ("imageUrl", "sourceImg", "shopifyImg", "slotId", "canaryReserved", "trialReserved"):
            self.assertIn(field, fn_body)

        cb_match = re.search(
            r"if \(url\.pathname === \"/webhooks/runpod/callback\"[\s\S]*?verifyRunPodCallbackSig\([\s\S]*?\);",
            self.index_ts,
        )
        self.assertIsNotNone(cb_match)
        cb_body = cb_match.group(0)
        self.assertIn("isValidPublicImageUrl", cb_body)
        self.assertIn("slotId: callbackSlotId", cb_body)
        self.assertNotIn("error: cbPayload.error || cbPayload.output?.message", self.index_ts)

    def test_r2_atomic_locks_and_webhook_idempotency(self) -> None:
        for fn_name in (
            "claimWebhookCompletion",
            "claimWebhookIdempotency",
            "acquireInFlightLock",
            "acquireGpuSlot",
            "acquireBatchLock",
        ):
            match = re.search(rf"async function {fn_name}\([\s\S]*?\n\}}", self.index_ts)
            self.assertIsNotNone(match, f"{fn_name} not found")
            self.assertIn("onlyIf:", match.group(0), f"{fn_name} must use atomic R2 conditional put (onlyIf)")
            self.assertIn("etagDoesNotMatch", match.group(0))
            self.assertIn("etagMatches", match.group(0))

        self.assertIn("claimWebhookIdempotency(env, requestedShop, webhookIdHeader.trim())", self.index_ts)
        self.assertIn("releaseClaimedWebhookId", self.index_ts)

    def test_feed_token_and_auth_checks(self) -> None:
        self.assertNotIn("safemedia-feed-token-salt", self.index_ts)
        feed_auth_match = re.search(
            r"async function isFeedAccessAuthorized\([\s\S]*?\n\}",
            self.index_ts,
        )
        self.assertIsNotNone(feed_auth_match)
        self.assertNotIn("!== \"production\"", feed_auth_match.group(0))
        self.assertIn("env.ENVIRONMENT === \"test\"", feed_auth_match.group(0))

        img_url_match = re.search(
            r"function isValidPublicImageUrl\([\s\S]*?\n\}",
            self.index_ts,
        )
        self.assertIsNotNone(img_url_match)
        self.assertNotIn("svg\\+xml", img_url_match.group(0))
        self.assertIn("(jpeg|jpg|png|webp|gif)", img_url_match.group(0))

    def test_jwt_session_token_and_timeouts(self) -> None:
        jwt_match = re.search(
            r"async function verifySessionToken\([\s\S]*?\n\}",
            self.index_ts,
        )
        self.assertIsNotNone(jwt_match)
        jwt_body = jwt_match.group(0)
        self.assertIn('typeof payload.exp !== "number"', jwt_body)
        self.assertIn("payload.aud !== expectedApiKey", jwt_body)
        self.assertIn('typeof payload.dest !== "string"', jwt_body)
        self.assertIn('destUrl.protocol !== "https:"', jwt_body)
        self.assertIn("AbortSignal.timeout(10_000)", self.index_ts)

    def test_dashboard_status_legal_and_billing_hardening(self) -> None:
        self.assertNotIn("tokenPrefix:", self.index_ts)
        self.assertNotIn("rawErrors: subResult.rawErrors", self.index_ts)
        self.assertNotIn("e02dce6bc82b8bca2d95a315f567e43b", self.index_ts)
        self.assertNotIn("e02dce6bc82b8bca2d95a315f567e43b", self.ui_ts)

        # GET / must not pass feedToken in initial HTML or auto-mutate billing on query param
        root_match = re.search(
            r'if \(url\.pathname === "/" && request\.method === "GET"\) \{[\s\S]*?renderDashboardHtml\([^\n]+\);',
            self.index_ts,
        )
        self.assertIsNotNone(root_match)
        root_block = root_match.group(0)
        self.assertNotIn('url.searchParams.get("billing_confirmed") === "1"', root_block)
        self.assertIn('renderDashboardHtml(requestedShop, env.SHOPIFY_API_KEY, "", billingState)', root_block)
        self.assertIn("frame-ancestors https://${requestedShop} https://admin.shopify.com;", self.index_ts)

        # /privacy & /terms CSP nonces
        self.assertIn("renderPrivacyPolicyHtml(lang, cspNonce)", self.index_ts)
        self.assertIn("renderTermsOfServiceHtml(lang, cspNonce)", self.index_ts)
        self.assertIn("script-src 'nonce-${cspNonce}'; object-src 'none';", self.index_ts)
        self.assertIn("cspNonce: string =", self.legal_ts)

        # Billing confirm must validate shopParam and not bypass via "-test-" domain name
        confirm_match = re.search(
            r'\(url\.pathname === "/api/billing/confirm"[\s\S]*?let isApproved = false;',
            self.index_ts,
        )
        self.assertIsNotNone(confirm_match)
        confirm_block = confirm_match.group(0)
        self.assertIn("isValidShopDomain(shopParam)", confirm_block)
        self.assertNotIn('shopParam.includes("-test-")', confirm_block)
        self.assertNotIn("shopParam === configuredPrimaryShop", confirm_block)

        # Billing autoActivate & reset gating
        self.assertIn('(env.ENVIRONMENT === "test" || isAdminAuthorized) && bodyCloneJson?.autoActivate === true', self.index_ts)
        reset_match = re.search(
            r'if \(url\.pathname === "/api/billing/reset" && request\.method === "POST"\) \{[\s\S]*?ShopifyVariantManager\.resetMockShopState',
            self.index_ts,
        )
        self.assertIsNotNone(reset_match)
        self.assertIn("isAdminAuthorized", reset_match.group(0))

        # Dual-feed sync quota checks must NOT skip when cleanImageBase64 is supplied
        self.assertNotIn('if (billingState.planStatus === "CANARY_TRIAL" && !body.cleanImageBase64)', self.index_ts)
        self.assertNotIn('if (billingState.planStatus === "ACTIVE" && !body.cleanImageBase64)', self.index_ts)
        self.assertIn("allowPrecleanedPayload", self.index_ts)

        # mock_usage fallback must be strictly gated to test environment
        for line in self.index_ts.splitlines():
            if "mock_usage" in line:
                self.assertIn('env.ENVIRONMENT === "test"', line)

    def test_client_shopify_and_snapshot_hardening(self) -> None:
        self.assertIn("MAX_PRECLEANED_IMAGE_BYTES", self.runpod_client_ts)
        self.assertIn("isSupportedRasterMagicBytes", self.runpod_client_ts)
        self.assertIn('redirect: "error"', self.runpod_client_ts)

        self.assertIn("assertValidShopDomain(shop);", self.shopify_ts)
        for fn_name in ("registerProductUpdateWebhook", "unregisterProductUpdateWebhook"):
            fn_match = re.search(rf"async {fn_name}\([\s\S]*?\):\s*Promise<[\s\S]*?>\s*\{{[\s\S]*?\n  \}}", self.shopify_ts)
            self.assertIsNotNone(fn_match, f"{fn_name} not found")
            self.assertIn("executeGraphQLWithBackoff", fn_match.group(0))

        self.assertIn("assertTenantSnapshotKey", self.snapshot_ts)
        self.assertIn("ROLLBACK_CONCURRENCY", self.snapshot_ts)
        self.assertIn("catch (err)", self.snapshot_ts)

    def test_ui_sanitization_and_redirect_guard_in_jsc(self) -> None:
        jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
        if not os.path.exists(jsc) and not shutil.which("jsc"):
            self.skipTest("JavaScriptCore jsc unavailable")
        jsc_bin = jsc if os.path.exists(jsc) else "jsc"

        bt = chr(96)
        start_marker = "return " + bt
        end_marker = bt + ";\n}"
        start = self.ui_ts.find(start_marker)
        self.assertNotEqual(start, -1, "return ` must exist in ui.ts")
        start += len(start_marker)
        end = self.ui_ts.rfind(end_marker)
        self.assertNotEqual(end, -1, "`;\\n} must exist in ui.ts")
        raw_tpl = self.ui_ts[start:end]

        with tempfile.TemporaryDirectory() as tmpdir:
            gen_html_path = os.path.join(tmpdir, "gen_html.js")
            gen_html_code = f"""
const shop = "my-shop.myshopify.com";
const apiKey = "test_key";
const feedTokenQuery = "";
const autosyncBadgeClass = "";
const autosyncBadgeText = "";
const toggleBtnClass = "";
const toggleBtnIcon = "";
const toggleBtnLabel = "";
const planBadgeClass = "";
const planBadgeText = "";
const planDescText = "";
const planUsageBadgeClass = "";
const planUsageBadgeText = "";
const canaryQuotaDisplayClass = "";
const canaryQuotaDisplayText = "";
const showTrialBtn = false;
const showResumeBtn = false;
const html = {bt}{raw_tpl}{bt};
print(html);
"""
            with open(gen_html_path, "w", encoding="utf-8") as f:
                f.write(gen_html_code)
            res_html = subprocess.run([jsc_bin, gen_html_path], capture_output=True, text=True, check=False)
            self.assertEqual(res_html.returncode, 0, f"jsc template eval failed: {res_html.stderr or res_html.stdout}")

            # Grab the inline application script (excluding CDN script tags)
            scripts = re.findall(r"<script>([\s\S]*?)</script>", res_html.stdout)
            self.assertTrue(scripts, "Evaluated HTML must contain inline <script>")
            js_body = max(scripts, key=len)

            for func_name in ("sanitizeText", "sanitizeUrl", "checkAuthAndHandleRedirect", "sanitizeUiErrorMessage"):
                self.assertIn(f"function {func_name}(", js_body)

            self.assertNotIn("console.log", self.ui_ts)

            probe_js = r"""
            const window = { top: { location: { href: "" } }, self: {}, location: { href: "", origin: "https://app.example.com" }, shopify: null };
            window.self = window;
            const document = {
              getElementById: () => null,
              querySelector: () => null,
              addEventListener: () => {}
            };
            const localStorage = { getItem: () => null, setItem: () => {} };
            const navigator = { language: "en-US" };
            const console = { warn: () => {}, error: () => {}, log: () => {} };
            """
            fn_snippets = []
            for pattern in (
                r"function sanitizeText\(str\) \{[\s\S]*?\n    \}",
                r"function sanitizeUrl\(rawUrl\) \{[\s\S]*?\n    \}",
                r"function checkAuthAndHandleRedirect\(status, data\) \{[\s\S]*?\n    \}",
            ):
                m = re.search(pattern, js_body)
                self.assertIsNotNone(m, f"Pattern not found: {pattern}")
                fn_snippets.append(m.group(0))

            probe_path = os.path.join(tmpdir, "probe.js")
            harness = (
                probe_js
                + "\nconst currentLang = 'en';\n"
                + "const shop = 'my-shop.myshopify.com';\n"
                + "const appHost = 'abcHost';\n"
                + "let openedTarget = '';\n"
                + "function setTimeout(fn) { fn(); }\n"
                + "function open(url) { openedTarget = url; window.location.href = url; }\n"
                + "function showNotification() {}\n"
                + "\n".join(fn_snippets)
                + r"""
                const xss = sanitizeText('<img src=x onerror=alert(1)>');
                if (xss.includes('<') || xss.includes('>')) throw new Error('sanitizeText failed: ' + xss);

                const jsScheme = sanitizeUrl('javascript:alert(1)');
                if (jsScheme !== '#') throw new Error('sanitizeUrl allowed javascript scheme: ' + jsScheme);

                const svgData = sanitizeUrl('data:image/svg+xml;base64,PHN2Zz4=');
                if (svgData !== '#') throw new Error('sanitizeUrl allowed svg data URI: ' + svgData);

                const okUrl = sanitizeUrl('https://cdn.shopify.com/test.jpg');
                if (!okUrl.startsWith('https://cdn.shopify.com/')) throw new Error('sanitizeUrl blocked valid https: ' + okUrl);

                // Open redirect probe: external URL must NOT redirect to evil.com
                window.location.href = "";
                checkAuthAndHandleRedirect(401, { code: 'REAUTH_REQUIRED', reauthUrl: 'https://evil.com/phish' });
                if (window.location.href.includes('evil.com')) {
                  throw new Error('Open redirect to evil.com allowed: ' + window.location.href);
                }
                if (!window.location.href.startsWith('/api/auth?shop=')) {
                  throw new Error('Expected fallback /api/auth?shop=... redirect, got: ' + window.location.href);
                }

                // Valid relative /api/auth path should propagate host
                window.location.href = "";
                checkAuthAndHandleRedirect(401, { code: 'REAUTH_REQUIRED', reauthUrl: '/api/auth?shop=my-shop.myshopify.com' });
                if (!window.location.href.includes('host=abcHost')) {
                  throw new Error('Expected host propagation on valid reauthUrl, got: ' + window.location.href);
                }
                print('JSC_SECURITY_PROBES_OK');
                """
            )
            with open(probe_path, "w", encoding="utf-8") as f:
                f.write(harness)
            proc = subprocess.run([jsc_bin, probe_path], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, f"jsc failed: {proc.stderr or proc.stdout}")
            self.assertIn("JSC_SECURITY_PROBES_OK", proc.stdout)

    def test_phase5_variant_cap_and_url_normalization_remediations(self) -> None:
        """Verify Phase 5 audit remediations:
        1. MAX_SYNC_UNIQUE_IMAGES_PER_REQUEST cap on webhook & dual-feed sync, plus O(1) aggregated usage billing.
        2. variants(first: 100) in shopify.ts GraphQL queries (no truncation at 50).
        3. normalizeImageUrlKey & lookupCleanedImageUrl for Shopify CDN ?v= cache-buster immunity.
        """
        # Risk 1: Request image cap & O(1) aggregated overage charge
        self.assertIn("const MAX_SYNC_UNIQUE_IMAGES_PER_REQUEST = 6;", self.index_ts)
        self.assertIn("uncleanedUrls.slice(0, MAX_SYNC_UNIQUE_IMAGES_PER_REQUEST)", self.index_ts)
        self.assertIn("uncleaned.slice(0, MAX_SYNC_UNIQUE_IMAGES_PER_REQUEST)", self.index_ts)
        self.assertIn("const aggregatedOveragePrice = Math.round(", self.index_ts)
        self.assertNotIn("for (let o = 0; o < overageCount; o++)", self.index_ts)
        self.assertNotIn("for (let c = 0; c < extraChargesNeeded; c++)", self.index_ts)

        # Risk 2: Shopify GraphQL variant limit raised from 50 to 100
        self.assertNotIn("variants(first: 50)", self.shopify_ts)
        self.assertGreaterEqual(self.shopify_ts.count("variants(first: 100)"), 2)

        # Risk 3: URL normalization & cache-buster deduplication
        self.assertIn("function normalizeImageUrlKey(", self.index_ts)
        self.assertIn("function lookupCleanedImageUrl(", self.index_ts)

        jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
        if not os.path.exists(jsc) and not shutil.which("jsc"):
            return
        jsc_bin = jsc if os.path.exists(jsc) else "jsc"

        # Execute the TS functions in JSC to verify runtime behavior on ?v= URLs
        fn_norm = re.search(r"function normalizeImageUrlKey\([\s\S]*?\n\}", self.index_ts)
        fn_collect = re.search(r"function collectUniqueProductImages\([\s\S]*?\n\}", self.index_ts)
        fn_map = re.search(r"function getExistingCleanedUrlMap\([\s\S]*?\n\}", self.index_ts)
        fn_lookup = re.search(r"function lookupCleanedImageUrl\([\s\S]*?\n\}", self.index_ts)
        fn_build = re.search(r"function buildVariantCleanImageMap\([\s\S]*?\n\}", self.index_ts)
        for m in (fn_norm, fn_collect, fn_map, fn_lookup, fn_build):
            self.assertIsNotNone(m)

        raw_ts_funcs = "\n\n".join(m.group(0) for m in (fn_norm, fn_collect, fn_map, fn_lookup, fn_build) if m)
        # Strip TypeScript type annotations for JSC execution
        js_funcs = (
            raw_ts_funcs
            .replace("url?: string | null", "url")
            .replace("prod?: ProductSnapshot | null", "prod")
            .replace("extraUrls: Array<string | undefined | null> = []", "extraUrls = []")
            .replace("): string[] {", ") {")
            .replace("): string {", ") {")
            .replace("): string | undefined {", ") {")
            .replace("): Record<string, string> {", ") {")
            .replace("const seenNormalized = new Set<string>();", "const seenNormalized = new Set();")
            .replace("const ordered: string[] = [];", "const ordered = [];")
            .replace("const map: Record<string, string> = {};", "const map = {};")
            .replace("const result: Record<string, string> = {};", "const result = {};")
            .replace("origUrl?: string | null, cleanUrl?: string | null", "origUrl, cleanUrl")
            .replace("cleanedImageUrls: Record<string, string>,", "cleanedImageUrls,")
            .replace("origUrl?: string | null", "origUrl")
            .replace("prod: ProductSnapshot,", "prod,")
            .replace("fallbackPrimaryCleanUrl?: string", "fallbackPrimaryCleanUrl")
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            test_js_path = os.path.join(tmpdir, "test_norm.js")
            test_js = (
                js_funcs
                + """
const prod = {
  productId: 'gid://shopify/Product/100',
  productTitle: 'Snowboard',
  originalMediaList: [{ id: 'm1', url: 'https://cdn.shopify.com/s/files/1/orange.jpg?v=100' }],
  cleanAdImageUrl: 'https://worker.example.com/clean/orange_clean.jpg',
  dualFeedMetadata: {
    cleanedImageUrls: {
      'https://cdn.shopify.com/s/files/1/orange.jpg?v=100': 'https://worker.example.com/clean/orange_clean.jpg',
      'https://cdn.shopify.com/s/files/1/blue.jpg?v=100': 'https://worker.example.com/clean/blue_clean.jpg'
    }
  },
  variants: [
    { variantId: 'v1', variantTitle: 'Orange S', originalMediaId: 'm1', originalImageUrl: 'https://cdn.shopify.com/s/files/1/orange.jpg?v=200' },
    { variantId: 'v2', variantTitle: 'Blue M', originalMediaId: 'm2', originalImageUrl: 'https://cdn.shopify.com/s/files/1/blue.jpg?v=999&width=1024' }
  ]
};

const unique = collectUniqueProductImages(prod, ['https://cdn.shopify.com/s/files/1/orange.jpg?v=300']);
if (unique.length !== 2) throw new Error('Expected 2 deduplicated images across ?v= drift, got ' + unique.length);

const existingMap = getExistingCleanedUrlMap(prod);
const uncleaned = unique.filter(u => !lookupCleanedImageUrl(existingMap, u));
if (uncleaned.length !== 0) throw new Error('Expected 0 uncleaned images when only ?v= changed, got ' + uncleaned.length);

const varMap = buildVariantCleanImageMap(prod, existingMap, prod.cleanAdImageUrl);
if (varMap['v1'] !== 'https://worker.example.com/clean/orange_clean.jpg') throw new Error('v1 mapping failed');
if (varMap['v2'] !== 'https://worker.example.com/clean/blue_clean.jpg') throw new Error('v2 mapping failed');
print('URL_NORM_VERIFIED');
"""
            )
            with open(test_js_path, "w", encoding="utf-8") as f:
                f.write(test_js)
            res = subprocess.run([jsc_bin, test_js_path], capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, f"JSC URL normalization test failed: {res.stderr or res.stdout}")
            self.assertIn("URL_NORM_VERIFIED", res.stdout)


if __name__ == "__main__":
    unittest.main()
