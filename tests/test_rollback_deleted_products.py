"""
Regression tests for deleted-product handling during Snapshot Rollback (Phase 5 Audit Remediation).
Verifies:
1. checkProductExists and fetchProductWithExistence in shopify.ts use inner payload generic types
   (no double-wrapped data) and distinguish "exists", "deleted", and "unknown".
2. deleteMetafieldIdentifiers / deleteVariantMetafieldIdentifiersResilient / clearCleanAdImageMetafield
   separate parent from variant deletion, skip only confirmed-deleted variants, and propagate real errors.
3. snapshot.ts uses single-query fetchProductWithExistence when catalog >= 250 or live fetch fails,
   normalizes product GIDs, marks deleted products in preRollbackResult, and retries once if child variants/media are deleted.
4. snapshot.ts filters variant/media updates against surviving live variants/media so partial deletion does not abort parent restore.
5. snapshot.ts enforces tenant isolation (targetSnapshot.shop === this.shop) and tracks skippedCount/skippedProductIds.
6. index.ts Rollback Suppression Guard excludes skipped products.
7. ui.ts renders SKIPPED_DELETED / DELETED IN SHOPIFY / N/A (Deleted) safely in EN/JA via JSC DOM evaluation.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSC_BIN = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def read_repo_file(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


class TestRollbackDeletedProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shopify_ts = read_repo_file("cloudflare_worker/src/shopify.ts")
        cls.snapshot_ts = read_repo_file("cloudflare_worker/src/snapshot.ts")
        cls.types_ts = read_repo_file("cloudflare_worker/src/types.ts")
        cls.index_ts = read_repo_file("cloudflare_worker/src/index.ts")
        cls.ui_ts = read_repo_file("cloudflare_worker/src/ui.ts")

    def test_check_product_exists_types_and_error_handling(self) -> None:
        fn_match = re.search(
            r"async checkProductExists\(productId: string\): Promise<\"exists\" \| \"deleted\" \| \"unknown\">[\s\S]*?\n  \}",
            self.shopify_ts,
        )
        self.assertIsNotNone(fn_match, "checkProductExists must be defined in shopify.ts")
        body = fn_match.group(0)
        # Finding #1: inner payload type only (not double-wrapped { data?: ... })
        self.assertNotIn("data?: { product?:", body)
        self.assertIn("product?: { id: string } | null;", body)
        self.assertIn('if (json.errors) {\n        return "unknown";', body)
        self.assertIn('return json.data?.product ? "exists" : "deleted";', body)
        self.assertIn('return "unknown";', body)

    def test_metafields_delete_propagates_errors_and_owner_not_found(self) -> None:
        # Finding #4 & Phase 5 #1: deleteMetafieldIdentifiers must propagate errors & ownerNotFound,
        # and clearCleanAdImageMetafield must separate parent product deletion from resilient variant deletion.
        fn_match = re.search(
            r"private async deleteMetafieldIdentifiers[\s\S]*?\n  \}",
            self.shopify_ts,
        )
        self.assertIsNotNone(fn_match)
        body = fn_match.group(0)
        self.assertIn("success: false,", body)
        self.assertIn("ownerNotFound", body)

        self.assertIn("private async deleteVariantMetafieldIdentifiersResilient", self.shopify_ts)
        clear_match = re.search(
            r"async clearCleanAdImageMetafield\([\s\S]*?\n  \}",
            self.shopify_ts,
        )
        self.assertIsNotNone(clear_match)
        clear_body = clear_match.group(0)
        self.assertIn("const parentRes = await this.deleteMetafieldIdentifiers(productIdentifiers, gid);", clear_body)
        self.assertIn("deleteVariantMetafieldIdentifiersResilient(variantIdentifiers", clear_body)

        # snapshot.ts must check clearRes.success and clearVarRes.success
        self.assertIn("if (!clearRes.success)", self.snapshot_ts)
        self.assertIn("if (!clearVarRes.success)", self.snapshot_ts)

    def test_snapshot_fallback_existence_check_and_live_fetch_enrichment(self) -> None:
        # Phase 5 Finding #2 & #3: single-query fetchProductWithExistence + GID normalization + preRollbackResult skipped diff
        self.assertIn("async fetchProductWithExistence(", self.shopify_ts)
        self.assertIn("const fetched = await variantManager.fetchProductWithExistence(p.productId);", self.snapshot_ts)
        self.assertIn('if (fetched.status === "deleted") {', self.snapshot_ts)
        self.assertIn('if (fetched.status === "unknown") {', self.snapshot_ts)
        self.assertIn("liveProd = fetched.product;", self.snapshot_ts)
        self.assertIn("normalizeProductGid(lp.productId)", self.snapshot_ts)
        self.assertIn("normalizeProductGid(p.productId)", self.snapshot_ts)
        self.assertIn("return buildSkippedProductDiff(p, targetSnapshot.snapshotId, revertedAt);", self.snapshot_ts)

    def test_snapshot_partial_variant_and_media_deletion_filtering(self) -> None:
        # Phase 5 Finding #1: filter variant/media updates against surviving live variants/media,
        # use dynamic mediaFetchLimit (20 list / 30 single fetch), and retry once when parent exists
        self.assertIn("const liveVariantIdSet =", self.snapshot_ts)
        self.assertIn("const liveMediaIdSet =", self.snapshot_ts)
        self.assertIn("let mediaFetchLimit = 20;", self.snapshot_ts)
        self.assertIn("mediaFetchLimit = 30;", self.snapshot_ts)
        self.assertIn("const activeSnapshotVariantMap: Record<string, string> = {};", self.snapshot_ts)
        self.assertIn('if (fetched.status === "deleted") {', self.snapshot_ts)
        self.assertIn('if (fetched.status === "unknown") {', self.snapshot_ts)
        self.assertIn('if (fetched.status === "exists" && attempt === 0) {', self.snapshot_ts)

    def test_snapshot_tenant_isolation_and_fail_result_tracking(self) -> None:
        self.assertIn(
            "if (targetSnapshot && targetSnapshot.shop !== this.shop) {\n      targetSnapshot = null;\n    }",
            self.snapshot_ts,
        )
        self.assertIn("const failedSkippedIds = productDataDiffs", self.snapshot_ts)
        self.assertIn("skippedCount: failedSkippedIds.length,", self.snapshot_ts)
        self.assertIn("...(failedSkippedIds.length > 0 ? { skippedProductIds: failedSkippedIds } : {}),", self.snapshot_ts)

    def test_rollback_suppression_guard_excludes_skipped_products(self) -> None:
        # Finding #5: skipped products must not trigger rollback suppression guard
        self.assertIn("if (rbDiff && !rbDiff.clearedAfterRollback && !rbDiff.skipped)", self.index_ts)

    def test_types_and_ui_support_skipped_deleted_and_ad_feed_na(self) -> None:
        self.assertIn('"SKIPPED_DELETED"', self.types_ts)
        self.assertIn("skippedCount?: number;", self.types_ts)
        self.assertIn("skippedProductIds?: string[];", self.types_ts)
        self.assertIn("DELETED IN SHOPIFY", self.ui_ts)
        self.assertIn("N/A (Deleted)", self.ui_ts)
        self.assertIn("配信除外（削除済）", self.ui_ts)
        self.assertIn("allSkipped", self.ui_ts)
        self.assertIn("sanitizeText(data.message", self.ui_ts)

    def test_ui_render_rollback_comparison_skipped_deleted_in_jsc(self) -> None:
        if not os.path.exists(JSC_BIN):
            self.skipTest("JSC binary not available")

        ui_code = re.sub(r"import\s+.*?;\s*", "", self.ui_ts)
        js_code = re.sub(
            r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string",
            "function renderDashboardHtml(shop, apiKey = 'test_key', feedToken = '', initialBilling = undefined)",
            ui_code,
        )
        extract_js = (
            js_code
            + "\nconst _h = renderDashboardHtml('audit-shop.myshopify.com');\n"
            + "const _m = _h.match(/<script>([\\s\\S]*?)<\\/script>/);\n"
            + "print(_m ? _m[1] : '');\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(extract_js)
            extract_path = f.name
        try:
            ext_res = subprocess.run([JSC_BIN, extract_path], capture_output=True, text=True, timeout=5)
            self.assertEqual(ext_res.returncode, 0, ext_res.stderr)
            client_script = ext_res.stdout
        finally:
            if os.path.exists(extract_path):
                os.remove(extract_path)

        test_script = f"""
const elements = {{}};
function getOrCreate(id) {{
  if (!elements[id]) {{
    elements[id] = {{
      id, innerHTML: '', innerText: '', className: '',
      classList: {{ _c: [], add(...a){{ this._c.push(...a); }}, remove(...a){{ this._c = this._c.filter(x => !a.includes(x)); }} }}
    }};
  }}
  return elements[id];
}}
const document = {{
  getElementById: (id) => getOrCreate(id),
  querySelectorAll: () => [],
  createElement: () => ({{ appendChild: () => {{}} }})
}};
const window = {{ document, location: {{ origin: 'https://app.example.com', search: '' }}, top: {{ location: {{ href: '' }} }} }};
const fetch = async () => ({{ ok: true, json: async () => ({{}}) }});
{client_script}
const payload = {{
  snapshotId: 'snap_deleted_test.json',
  revertedAt: '2026-11-23T00:00:00.000Z',
  skippedCount: 1,
  productDataDiffs: [{{
    productId: 'gid://shopify/Product/9999',
    productTitle: 'Deleted Jacket <script>alert(1)</script>',
    snapshotId: 'snap_deleted_test.json',
    revertedAt: '2026-11-23T00:00:00.000Z',
    storefrontImageUrl: 'https://cdn.shopify.com/orig/deleted.jpg',
    storefrontUnchanged: true,
    skipped: true,
    beforeRevert: {{
      storefrontImageUrl: 'https://cdn.shopify.com/orig/deleted.jpg',
      cleanAdImageMetafield: null,
      gmcImageLink: 'https://cdn.shopify.com/orig/deleted.jpg',
      metaImageLink: 'https://cdn.shopify.com/orig/deleted.jpg',
      variantCount: 2,
      cleanedVariantCount: 0,
      variantLinksPreserved: false
    }},
    afterRevert: {{
      storefrontImageUrl: 'https://cdn.shopify.com/orig/deleted.jpg',
      cleanAdImageMetafield: null,
      gmcImageLink: 'https://cdn.shopify.com/orig/deleted.jpg',
      metaImageLink: 'https://cdn.shopify.com/orig/deleted.jpg',
      metafieldAction: 'SKIPPED_DELETED',
      variantCount: 2,
      cleanedVariantCount: 0,
      variantLinksPreserved: false
    }}
  }}]
}};
renderRollbackComparison(payload);
const enHtml = document.getElementById('rollback-comparison-panel').innerHTML;
setLanguage('ja');
renderRollbackComparison(payload);
const jaHtml = document.getElementById('rollback-comparison-panel').innerHTML;
print('RESULT_JSON:' + JSON.stringify({{ enHtml, jaHtml }}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(test_script)
            run_path = f.name
        try:
            run_res = subprocess.run([JSC_BIN, run_path], capture_output=True, text=True, timeout=5)
            self.assertEqual(run_res.returncode, 0, run_res.stderr)
            m = re.search(r"RESULT_JSON:(\{.*\})", run_res.stdout)
            self.assertIsNotNone(m, run_res.stdout)
            data = json.loads(m.group(1))
        finally:
            if os.path.exists(run_path):
                os.remove(run_path)

        # XSS payload must be escaped
        self.assertNotIn("<script>alert(1)</script>", data["enHtml"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", data["enHtml"])
        # Finding #5: Ad Feed column shows N/A (Deleted) instead of active image link
        self.assertIn("DELETED IN SHOPIFY", data["enHtml"])
        self.assertIn("N/A (Deleted)", data["enHtml"])
        self.assertNotIn("deleted.jpg ➔ deleted.jpg", data["enHtml"])
        # Phase 5 Finding 4: Skipped products must not show 0/N -> 0/N or 100% Variant Binding when all skipped
        self.assertNotIn("Variants: 0/2", data["enHtml"])
        self.assertIn("Deleted Products Skipped", data["enHtml"])
        self.assertNotIn("100% Variant Binding", data["enHtml"])
        self.assertIn("配信除外（削除済）", data["jaHtml"])
        self.assertIn("スキップ（削除済み）", data["jaHtml"])
        self.assertNotIn("バリアント: 0/2", data["jaHtml"])
        self.assertIn("削除済み商品をスキップ", data["jaHtml"])

    def test_auth_error_propagation_and_unknown_status_handling(self) -> None:
        # Phase 5 Finding 1: ShopifyAuthError must propagate in shopify.ts, snapshot.ts, index.ts (/api/rollback), and ui.ts
        self.assertIn("if (err instanceof ShopifyAuthError) throw err;", self.shopify_ts)
        self.assertGreaterEqual(self.shopify_ts.count("if (err instanceof ShopifyAuthError) throw err;"), 4)
        self.assertIn("import { ShopifyVariantManager, ShopifyAuthError } from \"./shopify\";", self.snapshot_ts)
        self.assertIn("if (err instanceof ShopifyAuthError) throw err;", self.snapshot_ts)
        self.assertIn("Detected invalid Shopify auth during rollback", self.index_ts)
        self.assertIn("if (checkAuthAndHandleRedirect(res.status, data)) {\n          closeRollbackModal();\n          return;\n        }", self.ui_ts)

        # Phase 5 Finding 2: fetched.status === "unknown" must throw transient error rather than mutating or skipping as deleted
        self.assertEqual(
            self.snapshot_ts.count('if (fetched.status === "unknown") {\n        throw new Error(`Transient Shopify API error while verifying product existence for ${p.productId}`);\n      }') +
            self.snapshot_ts.count('if (fetched.status === "unknown") {\n            throw new Error(`Transient Shopify API error while verifying product existence for ${p.productId}`);\n          }'),
            2,
        )
        self.assertNotIn('(!liveProd && fetched.status === "unknown")', self.snapshot_ts)

        # Phase 5 Finding 3: isProductNotFoundError covers Shopify media/variant association errors
        self.assertIn('msg.includes("not associated with")', self.snapshot_ts)
        self.assertIn('msg.includes("invalid media")', self.snapshot_ts)
        self.assertIn('msg.includes("invalid variant")', self.snapshot_ts)


if __name__ == "__main__":
    unittest.main()
