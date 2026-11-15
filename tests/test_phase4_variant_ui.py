#!/usr/bin/env python3
"""
Phase 4 Verification Suite: Full-Variant Frontend UI (cloudflare_worker/src/ui.ts)
Evaluates actual client JS extracted from ui.ts inside WebKit JavaScriptCore (JSC) to verify:
1. Step 1 Canary Preview: selectVariant(idx) switches BOTH Storefront (Before) and Clean Ad-Feed (After)
   images and URL labels in lockstep, with XSS/URL safety guards.
2. Zone 1 Feed & Channel Status: #feed-items-count-badge, #synced_feed_rows, and #dual-feed-list
   reflect per-variant coverage and deduplicated variant Before/After pairs.
3. Step 3 6-Column Rollback Comparison: renderRollbackComparison() renders per-variant metafield
   counts (before -> after), metafieldAction, GMC/Meta feed transitions, and variant preservation.
4. Bilingual EN/JA rendering parity across all new variant-aware UI sections.
"""

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"
JSC_BIN = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _extract_client_script() -> str:
    ui_code = UI_TS_PATH.read_text(encoding="utf-8")
    ui_code = re.sub(r"import\s+.*?;\s*", "", ui_code)
    js_code = re.sub(
        r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string",
        "function renderDashboardHtml(shop, apiKey = 'test_key', feedToken = '', initialBilling = undefined)",
        ui_code,
    )
    harness = (
        js_code
        + "\nconst _h = renderDashboardHtml('variant-shop.myshopify.com');\n"
        + "const _m = _h.match(/<script>([\\s\\S]*?)<\\/script>/);\n"
        + "print(_m ? _m[1] : '');\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(harness)
        tmp_path = f.name
    try:
        res = subprocess.run([JSC_BIN, tmp_path], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to extract script from ui.ts: {res.stderr}")
        return res.stdout
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _run_jsc_with_dom(client_script: str, test_body: str) -> dict:
    wrapper = f"""
const elements = {{}};
function getOrCreateElement(id) {{
  if (!elements[id]) {{
    elements[id] = {{
      id: id,
      innerHTML: '',
      innerText: '',
      value: '',
      className: '',
      src: '',
      href: '',
      disabled: false,
      style: {{}},
      attrs: {{}},
      setAttribute(k, v) {{ this.attrs[k] = v; this[k] = v; }},
      getAttribute(k) {{ return this.attrs[k] ?? null; }},
      classList: {{
        _classes: [],
        add(...args) {{ this._classes.push(...args); }},
        remove(...args) {{ this._classes = this._classes.filter(c => !args.includes(c)); }},
        contains(c) {{ return this._classes.includes(c); }}
      }}
    }};
  }}
  return elements[id];
}}

const document = {{
  getElementById: (id) => getOrCreateElement(id),
  querySelectorAll: (selector) => {{
    if (selector === '[data-i18n]') return [];
    if (selector === '.variant-pill') {{
      return [getOrCreateElement('vbtn-0'), getOrCreateElement('vbtn-1'), getOrCreateElement('vbtn-2')];
    }}
    return [];
  }},
  createElement: () => ({{ appendChild: () => {{}}, innerText: '', value: '' }})
}};

const window = {{ document, location: {{ origin: 'https://app.example.com', search: '' }}, top: {{ location: {{ href: '' }} }} }};
const fetch = async () => ({{ ok: true, json: async () => ({{}}) }});

{client_script}

{test_body}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(wrapper)
        tmp_path = f.name
    try:
        res = subprocess.run([JSC_BIN, tmp_path], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            raise AssertionError(f"JSC execution failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        match = re.search(r"RESULT_JSON:(\{.*\})", res.stdout)
        if not match:
            raise AssertionError(f"RESULT_JSON marker missing from JSC output:\n{res.stdout}")
        return json.loads(match.group(1))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class TestPhase4FullVariantFrontendUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(JSC_BIN):
            raise unittest.SkipTest(f"JavaScriptCore binary not found at {JSC_BIN}")
        cls.client_script = _extract_client_script()

    def test_canary_select_variant_switches_both_before_and_after_images(self):
        """Step 1: selectVariant(idx) must switch BOTH Storefront (Before) and Clean Ad-Feed (After) images and URLs."""
        test_body = """
canaryData = {
  productId: 'gid://shopify/Product/1001',
  productTitle: 'Alpine Snowboard',
  originalImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
  cleanAdImageUrl: 'https://cdn.example.com/clean/orange_clean.jpg',
  metafieldKey: 'safemedia.clean_ad_image_url',
  aiMetadata: { processingSec: 4.5, maskCoveragePct: 5.2, engine: 'Florence-2 + LaMa' },
  variantChecks: [
    {
      variantId: 'gid://shopify/ProductVariant/1',
      title: 'Sunset Orange',
      hasOriginalMedia: true,
      preserved: true,
      originalImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
      cleanAdImageUrl: 'https://cdn.example.com/clean/orange_clean.jpg',
      activeImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg'
    },
    {
      variantId: 'gid://shopify/ProductVariant/2',
      title: 'Arctic Blue',
      hasOriginalMedia: true,
      preserved: true,
      originalImageUrl: 'https://cdn.shopify.com/orig/blue_50off.jpg',
      cleanAdImageUrl: 'https://cdn.example.com/clean/blue_clean.jpg',
      activeImageUrl: 'https://cdn.shopify.com/orig/blue_50off.jpg'
    },
    {
      variantId: 'gid://shopify/ProductVariant/3',
      title: 'Unsafe Variant',
      hasOriginalMedia: true,
      preserved: true,
      originalImageUrl: 'javascript:alert(1)',
      cleanAdImageUrl: 'javascript:alert(2)',
      activeImageUrl: 'javascript:alert(1)'
    }
  ]
};

renderCanaryResult(canaryData);
const initialHtml = document.getElementById('canary-container').innerHTML;
const initialCleanLabel = document.getElementById('active-variant-clean-img').innerText;

selectVariant(1);
const afterV1 = {
  origSrc: document.getElementById('canary-orig-img').src,
  cleanSrc: document.getElementById('canary-clean-img').src,
  activeOrigLabel: document.getElementById('active-variant-img').innerText,
  activeCleanLabel: document.getElementById('active-variant-clean-img').innerText,
  pill1Class: document.getElementById('vbtn-1').className
};

selectVariant(2);
const afterUnsafe = {
  origSrc: document.getElementById('canary-orig-img').src,
  cleanSrc: document.getElementById('canary-clean-img').src
};

print('RESULT_JSON:' + JSON.stringify({ initialHtml, initialCleanLabel, afterV1, afterUnsafe }));
"""
        data = _run_jsc_with_dom(self.client_script, test_body)
        self.assertIn("3 Variants Paired (Before & After)", data["initialHtml"])
        self.assertIn("https://cdn.example.com/clean/orange_clean.jpg", data["initialHtml"])
        self.assertEqual(data["afterV1"]["origSrc"], "https://cdn.shopify.com/orig/blue_50off.jpg")
        self.assertEqual(data["afterV1"]["cleanSrc"], "https://cdn.example.com/clean/blue_clean.jpg")
        self.assertEqual(data["afterV1"]["activeOrigLabel"], "https://cdn.shopify.com/orig/blue_50off.jpg")
        self.assertEqual(data["afterV1"]["activeCleanLabel"], "https://cdn.example.com/clean/blue_clean.jpg")
        self.assertIn("bg-emerald-600", data["afterV1"]["pill1Class"])
        self.assertEqual(data["afterUnsafe"]["origSrc"], "#")
        self.assertEqual(data["afterUnsafe"]["cleanSrc"], "#")

    def test_zone1_feed_table_and_visual_pairs_reflect_multi_variant_coverage(self):
        """Zone 1: renderStatusData populates #feed-items-count-badge, variant coverage, and deduplicated variant pairs."""
        test_body = """
const statusPayload = {
  shop: 'variant-shop.myshopify.com',
  billing: { planStatus: 'ACTIVE', autoSyncEnabled: true, monthlyUsageCount: 3, monthlyIncludedCount: 500, circuitBreakerTripped: false },
  feedPreview: {
    channelMappings: {
      googleShopping: { status: 'MAPPED_AND_READY' },
      metaCatalog: { status: 'MAPPED_AND_READY' }
    },
    items: [
      { variantId: 'v1' },
      { variantId: 'v2' },
      { variantId: 'v3' }
    ]
  },
  dualFeedProducts: [
    {
      productId: 'gid://shopify/Product/1001',
      productTitle: 'Alpine Snowboard',
      storefrontImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
      cleanAdImageUrl: 'https://cdn.example.com/clean/orange_clean.jpg',
      dualFeedMetadata: { processingSec: 4.5, maskCoveragePct: 6.1 },
      variantCount: 3,
      cleanedVariantCount: 3,
      variants: [
        { variantId: 'v1', variantTitle: 'Orange / 152cm', originalImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg', cleanAdImageUrl: 'https://cdn.example.com/clean/orange_clean.jpg' },
        { variantId: 'v2', variantTitle: 'Orange / 156cm', originalImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg', cleanAdImageUrl: 'https://cdn.example.com/clean/orange_clean.jpg' },
        { variantId: 'v3', variantTitle: 'Blue / 156cm', originalImageUrl: 'https://cdn.shopify.com/orig/blue_sale.jpg', cleanAdImageUrl: 'https://cdn.example.com/clean/blue_clean.jpg' }
      ]
    }
  ]
};

renderStatusData(statusPayload);
const out = {
  feedCountText: document.getElementById('feed-items-count-badge').innerText,
  rowsHtml: document.getElementById('synced_feed_rows').innerHTML,
  cardsHtml: document.getElementById('dual-feed-list').innerHTML
};
print('RESULT_JSON:' + JSON.stringify(out));
"""
        data = _run_jsc_with_dom(self.client_script, test_body)
        self.assertIn("3 Variant Items Live", data["feedCountText"])
        self.assertIn("3/3 Variants Cleaned", data["rowsHtml"])
        self.assertIn("Product + 3 Variant Metafields", data["rowsHtml"])
        # Deduplication: Orange / 152cm and Orange / 156cm share the same pair and merge into one card
        self.assertIn("Orange / 152cm, Orange / 156cm", data["cardsHtml"])
        self.assertIn("Blue / 156cm", data["cardsHtml"])
        self.assertIn("https://cdn.example.com/clean/blue_clean.jpg", data["cardsHtml"])
        self.assertEqual(data["cardsHtml"].count("https://cdn.example.com/clean/orange_clean.jpg"), 3)  # 1 clean link + 1 <a href> + 1 <img src> (deduplicated across 2 sizes)

    def test_step3_rollback_comparison_renders_variant_metafield_diffs_and_bilingual_labels(self):
        """Step 3: renderRollbackComparison displays per-variant before/after metafield counts and action codes."""
        test_body = """
const rollbackPayload = {
  snapshotId: 'snap_variant_baseline.json',
  revertedAt: '2026-11-15T00:00:00.000Z',
  productDataDiffs: [
    {
      productId: 'gid://shopify/Product/1001',
      productTitle: 'Alpine Snowboard',
      snapshotId: 'snap_variant_baseline.json',
      revertedAt: '2026-11-15T00:00:00.000Z',
      storefrontImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
      storefrontUnchanged: true,
      beforeRevert: {
        storefrontImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
        cleanAdImageMetafield: 'https://cdn.example.com/clean/orange_clean.jpg',
        gmcImageLink: 'https://cdn.example.com/clean/orange_clean.jpg',
        metaImageLink: 'https://cdn.example.com/clean/orange_clean.jpg',
        variantCount: 3,
        cleanedVariantCount: 3,
        variantLinksPreserved: true
      },
      afterRevert: {
        storefrontImageUrl: 'https://cdn.shopify.com/orig/orange_sale.jpg',
        cleanAdImageMetafield: null,
        gmcImageLink: 'https://cdn.shopify.com/orig/orange_sale.jpg',
        metaImageLink: 'https://cdn.shopify.com/orig/orange_sale.jpg',
        metafieldAction: 'PURGED_TO_VIRGIN',
        variantCount: 3,
        cleanedVariantCount: 0,
        variantLinksPreserved: true
      }
    }
  ]
};

renderRollbackComparison(rollbackPayload);
const enHtml = document.getElementById('rollback-comparison-panel').innerHTML;

setLanguage('ja');
renderRollbackComparison(rollbackPayload);
const jaHtml = document.getElementById('rollback-comparison-panel').innerHTML;

print('RESULT_JSON:' + JSON.stringify({ enHtml, jaHtml }));
"""
        data = _run_jsc_with_dom(self.client_script, test_body)
        # EN checks
        self.assertIn("Variants: 3/3 ➔ 0/3", data["enHtml"])
        self.assertIn("PURGED_TO_VIRGIN", data["enHtml"])
        self.assertIn("orange_clean.jpg ➔ orange_sale.jpg", data["enHtml"])
        self.assertIn("0/3 variant feed items", data["enHtml"])
        self.assertIn("3/3 Preserved", data["enHtml"])
        self.assertIn("Media & Metafields Synced", data["enHtml"])
        # JA checks
        self.assertIn("バリアント: 3/3 ➔ 0/3", data["jaHtml"])
        self.assertIn("0/3 バリアント配信", data["jaHtml"])
        self.assertIn("3/3 連動保持", data["jaHtml"])
        self.assertIn("画像・Metafield同期済", data["jaHtml"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
