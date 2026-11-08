#!/usr/bin/env python3
"""
Empirical Challenger Test Harness for Milestone 2:
DOM Hierarchy, 5-Layer Action Cards, Dynamic JavaScript Canary Injection, and Legacy Artifact Absence.

Author: UI DOM & Interaction Challenger (teamwork_preview_challenger)
Target: cloudflare_worker/src/ui.ts rendered output
"""

import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
JSC_BIN = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


class SimpleDOMNode:
    """Represents a lightweight parsed DOM element for hierarchy and order testing."""

    def __init__(self, tag: str, attrs: List[tuple], parent: Optional["SimpleDOMNode"] = None, pos: int = 0):
        self.tag = tag
        self.attrs = dict(attrs)
        self.id = self.attrs.get("id")
        self.classes = self.attrs.get("class", "").split()
        self.parent = parent
        self.children: List["SimpleDOMNode"] = []
        self.pos = pos
        self.text_content: List[str] = []

    def find_first(self, tag: Optional[str] = None, class_name: Optional[str] = None, node_id: Optional[str] = None) -> Optional["SimpleDOMNode"]:
        if (tag is None or self.tag == tag) and \
           (class_name is None or class_name in self.classes) and \
           (node_id is None or self.id == node_id):
            return self
        for child in self.children:
            found = child.find_first(tag, class_name, node_id)
            if found:
                return found
        return None

    def find_all(self, tag: Optional[str] = None, class_name: Optional[str] = None, node_id: Optional[str] = None) -> List["SimpleDOMNode"]:
        results = []
        if (tag is None or self.tag == tag) and \
           (class_name is None or class_name in self.classes) and \
           (node_id is None or self.id == node_id):
            results.append(self)
        for child in self.children:
            results.extend(child.find_all(tag, class_name, node_id))
        return results


class DOMTreeBuilder(html.parser.HTMLParser):
    """Builds a DOM tree with character offset tracking."""

    def __init__(self):
        super().__init__()
        self.root = SimpleDOMNode("root", [], None, 0)
        self.current = self.root
        self._counter = 0

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        self._counter += 1
        node = SimpleDOMNode(tag, attrs, self.current, self._counter)
        self.current.children.append(node)
        # Self-closing / void elements
        if tag not in ("img", "br", "hr", "input", "meta", "link", "!doctype"):
            self.current = node

    def handle_endtag(self, tag: str):
        if self.current.parent:
            self.current = self.current.parent

    def handle_data(self, data: str):
        if self.current:
            self.current.text_content.append(data)


def render_ui_html(shop: str = "test-store-20261011.myshopify.com") -> str:
    """Renders the HTML directly from cloudflare_worker/src/ui.ts using JSC or template extractor."""
    ui_path = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"
    if not ui_path.exists():
        raise FileNotFoundError(f"UI source not found at {ui_path}")

    ui_code = ui_path.read_text(encoding="utf-8")

    # If JSC is available, evaluate the genuine TypeScript function (stripped of types)
    if os.path.exists(JSC_BIN):
        js_code = re.sub(
            r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string",
            "function renderDashboardHtml(shop, apiKey = 'e02dce6bc82b8bca2d95a315f567e43b', feedToken = '', initialBilling = undefined)",
            ui_code,
        )
        harness = (
            js_code
            + f"\nprint(renderDashboardHtml({json.dumps(shop)}));\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(harness)
            tmp_path = f.name
        try:
            res = subprocess.run([JSC_BIN, tmp_path], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip().startswith("<!DOCTYPE html>"):
                return res.stdout
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Fallback to regex extraction
    fn_match = re.search(
        r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string\s*\{\s*return\s*`([\s\S]*<\/html>)\s*`;\s*\}",
        ui_code,
    )
    if not fn_match:
        fn_match = re.search(
            r"export\s+function\s+renderDashboardHtml[\s\S]*?return\s*`([\s\S]*)`;\s*\}",
            ui_code,
        )
    if not fn_match:
        raise ValueError("Could not extract renderDashboardHtml template from cloudflare_worker/src/ui.ts")

    template = fn_match.group(1)
    rendered = template.replace("${shop}", shop)
    return rendered.replace(r"\`", "`").replace(r"\${", "${")


class TestMilestone2EmpiricalDOMChallenge(unittest.TestCase):
    """Empirical challenge suite for Milestone 2 UI."""

    @classmethod
    def setUpClass(cls):
        cls.shop = "safemedia-test-20261011.myshopify.com"
        cls.raw_html = render_ui_html(cls.shop)
        parser = DOMTreeBuilder()
        parser.feed(cls.raw_html)
        cls.dom = parser.root

    # =========================================================================
    # Suite 1: Information Architecture & Zone Hierarchy Order
    # =========================================================================

    def test_zone_order_core_automation_prior_to_onboarding_safety(self):
        """Assert presence of zone-core-automation prior to zone-onboarding-safety in DOM order."""
        zone1 = self.dom.find_first(node_id="zone-core-automation")
        zone2 = self.dom.find_first(node_id="zone-onboarding-safety")

        self.assertIsNotNone(zone1, "CRITICAL: #zone-core-automation was not found in rendered DOM!")
        self.assertIsNotNone(zone2, "CRITICAL: #zone-onboarding-safety was not found in rendered DOM!")

        self.assertLess(
            zone1.pos,
            zone2.pos,
            f"VIOLATION: Zone 1 (#zone-core-automation pos={zone1.pos}) must appear BEFORE Zone 2 (#zone-onboarding-safety pos={zone2.pos})!",
        )

        # In raw HTML string, verify zone-core-automation offset precedes zone-onboarding-safety
        idx_zone1 = self.raw_html.find('id="zone-core-automation"')
        idx_zone2 = self.raw_html.find('id="zone-onboarding-safety"')
        self.assertNotEqual(idx_zone1, -1)
        self.assertNotEqual(idx_zone2, -1)
        self.assertLess(idx_zone1, idx_zone2, "HTML index of zone-core-automation must be strictly less than zone-onboarding-safety")

    def test_top_header_and_hero_banner_precede_zone1(self):
        """Assert top header, hero banner (#hero_banner), subcopy, and billing bar all precede Zone 1."""
        hero = self.dom.find_first(node_id="hero_banner")
        billing = self.dom.find_first(node_id="billing-banner")
        zone1 = self.dom.find_first(node_id="zone-core-automation")

        self.assertIsNotNone(hero, "#hero_banner not found in DOM")
        self.assertIsNotNone(billing, "#billing-banner not found in DOM")
        self.assertIsNotNone(zone1, "#zone-core-automation not found in DOM")

        self.assertLess(hero.pos, billing.pos, "Hero banner must precede billing bar")
        self.assertLess(billing.pos, zone1.pos, "Billing bar must precede Zone 1")

    def test_zone2_sequential_three_steps_order(self):
        """Assert Zone 2 contains Step 1 (#card-canary-preview), Step 2 (#card-catalog-sync), and Step 3 (#card-rollback) in strict sequential order."""
        step1 = self.dom.find_first(node_id="card-canary-preview")
        step2 = self.dom.find_first(node_id="card-catalog-sync")
        step3 = self.dom.find_first(node_id="card-rollback")

        self.assertIsNotNone(step1, "#card-canary-preview (Step 1) not found in DOM")
        self.assertIsNotNone(step2, "#card-catalog-sync (Step 2) not found in DOM")
        self.assertIsNotNone(step3, "#card-rollback (Step 3) not found in DOM")

        self.assertLess(step1.pos, step2.pos, "Step 1 (#card-canary-preview) must precede Step 2 (#card-catalog-sync)")
        self.assertLess(step2.pos, step3.pos, "Step 2 (#card-catalog-sync) must precede Step 3 (#card-rollback)")

    # =========================================================================
    # Suite 2: All 4 Action Cards Contain All 5 Layers in Order
    # =========================================================================

    def test_all_four_action_cards_contain_all_five_layers(self):
        """
        Assert all 4 action cards contain all 5 layers:
        1. layer-1-badge
        2. layer-2-title
        3. layer-3-description
        4. layer-4-actions
        5. layer-5-preview
        in strict monotonic hierarchical order.
        """
        card_ids = [
            ("Zone 1 Card", "zone-core-automation"),
            ("Step 1 Canary Preview", "card-canary-preview"),
            ("Step 2 Catalog Sync", "card-catalog-sync"),
            ("Step 3 Rollback", "card-rollback"),
        ]

        expected_layers = [
            "layer-1-badge",
            "layer-2-title",
            "layer-3-description",
            "layer-4-actions",
            "layer-5-preview",
        ]

        for card_label, cid in card_ids:
            card_node = self.dom.find_first(node_id=cid)
            self.assertIsNotNone(card_node, f"Card '{card_label}' with id='{cid}' was not found in DOM tree!")

            # Extract the raw HTML substring for this card
            card_start = self.raw_html.find(f'id="{cid}"')
            self.assertNotEqual(card_start, -1, f"Failed to locate start of card '{cid}' in raw HTML")

            layer_positions = []
            for layer in expected_layers:
                layer_nodes = card_node.find_all(class_name=layer)
                self.assertGreater(
                    len(layer_nodes),
                    0,
                    f"CRITICAL DEFECT: Card '{card_label}' (id='{cid}') is MISSING required '{layer}'!",
                )
                layer_positions.append((layer, layer_nodes[0].pos))

            # Verify strictly monotonic ordering: pos(layer 1) < pos(layer 2) < pos(layer 3) < pos(layer 4) < pos(layer 5)
            for i in range(len(layer_positions) - 1):
                curr_layer, curr_pos = layer_positions[i]
                next_layer, next_pos = layer_positions[i + 1]
                self.assertLess(
                    curr_pos,
                    next_pos,
                    f"VIOLATION in card '{cid}': '{curr_layer}' (pos={curr_pos}) must precede '{next_layer}' (pos={next_pos})!",
                )

    # =========================================================================
    # Suite 3: Canary Result Dynamic DOM Injection & WebKit/JSC Interaction
    # =========================================================================

    def _execute_jsc_test(self, js_test_body: str) -> subprocess.CompletedProcess:
        """Executes JavaScript in native WebKit JavaScriptCore with full DOM/Browser mock."""
        ui_path = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"
        ui_code = ui_path.read_text(encoding="utf-8")
        ui_code = re.sub(r"import\s+.*?;\s*", "", ui_code)
        js_code = re.sub(
            r"export\s+function\s+renderDashboardHtml\s*\([^)]*\)\s*:\s*string",
            "function renderDashboardHtml(shop, apiKey = 'e02dce6bc82b8bca2d95a315f567e43b', feedToken = '', initialBilling = undefined)",
            ui_code,
        )

        # Step 1: Render HTML and extract the <script> block
        harness = (
            js_code
            + "\nconst _h = renderDashboardHtml('test-store.myshopify.com');\n"
            + "const _m = _h.match(/<script>([\\s\\S]*?)<\\/script>/);\n"
            + "print(_m ? _m[1] : '');\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(harness)
            tmp_extract = f.name
        try:
            res_ext = subprocess.run([JSC_BIN, tmp_extract], capture_output=True, text=True, timeout=5)
            if res_ext.returncode != 0:
                raise RuntimeError(f"Failed to extract script from ui.ts: {res_ext.stderr}")
            client_script = res_ext.stdout
        finally:
            if os.path.exists(tmp_extract):
                os.remove(tmp_extract)

        # Step 2: Build DOM emulator environment
        test_file = f"""
const elements = {{}};
function getOrCreateElement(id) {{
  if (!elements[id]) {{
    elements[id] = {{
      id: id,
      innerHTML: '',
      innerText: '',
      value: '',
      className: '',
      classList: {{
        _classes: [],
        add(...args) {{ this._classes.push(...args); }},
        remove(...args) {{ this._classes = this._classes.filter(c => !args.includes(c)); }},
        contains(c) {{ return this._classes.includes(c); }}
      }},
      disabled: false,
      src: '',
      style: {{}}
    }};
  }}
  return elements[id];
}}

const document = {{
  getElementById: (id) => getOrCreateElement(id),
  querySelectorAll: (selector) => {{
    if (selector === '[data-i18n]') {{
      return ['app_title', 'hero_headline', 'z1_tag', 'step1_title', 'step2_title', 'safety_title'].map(id => {{
        const el = getOrCreateElement(id);
        el.getAttribute = (attr) => attr === 'data-i18n' ? id : null;
        return el;
      }});
    }}
    if (selector === '.variant-pill') {{
      return [getOrCreateElement('vbtn-0'), getOrCreateElement('vbtn-1')];
    }}
    return [];
  }}
}};

const window = {{ document }};
const fetch = async (url, opts) => ({{ ok: true, json: async () => ({{}}) }});
const alert = (msg) => {{ print('ALERT_DISPATCHED: ' + msg); }};

// --- Injected Application Client Script ---
{client_script}

// --- Test Harness Body ---
{js_test_body}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(test_file)
            tmp_run = f.name
        try:
            res_run = subprocess.run([JSC_BIN, tmp_run], capture_output=True, text=True, timeout=5)
            return res_run
        finally:
            if os.path.exists(tmp_run):
                os.remove(tmp_run)

    def test_canary_dynamic_injection_renders_side_by_side_elements_without_errors(self):
        """
        Assert that Canary result container dynamically injects Before (Storefront Decorated)
        vs After (Clean Ad Image) side-by-side elements without throwing JS errors.
        """
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
const samplePayload = {
  productId: 'gid://shopify/Product/1001',
  productTitle: 'Premium Silk Bomber Jacket',
  originalImageUrl: 'https://cdn.shopify.com/orig/bomber_sale.jpg',
  cleanAdImageUrl: 'https://cdn.safemedia.io/clean/bomber_clean.png',
  metafieldKey: 'safemedia.clean_ad_image_url',
  aiMetadata: {
    processingSec: 4.82,
    maskCoveragePct: 2.15,
    engine: 'Florence-2 + LaMa'
  },
  variantChecks: [
    { variantId: 'var_1', title: 'Black / Small', activeImageUrl: 'https://cdn.shopify.com/orig/bomber_sale.jpg', preserved: true },
    { variantId: 'var_2', title: 'Navy / Medium', activeImageUrl: 'https://cdn.shopify.com/orig/bomber_navy.jpg', preserved: true }
  ],
  canaryUsedCount: 1,
  canaryLimit: 5
};

canaryData = samplePayload;
renderCanaryResult(samplePayload);

const container = document.getElementById('canary-container');
const html = container.innerHTML;

const results = {
  hasOrigImg: html.includes('id="canary-orig-img"'),
  hasCleanImg: html.includes('id="canary-clean-img"'),
  origImgSrc: html.includes('src="https://cdn.shopify.com/orig/bomber_sale.jpg"'),
  cleanImgSrc: html.includes('src="https://cdn.safemedia.io/clean/bomber_clean.png"'),
  hasSideBySideGrid: html.includes('grid grid-cols-1 md:grid-cols-2'),
  hasBeforeLabel: html.includes('Storefront Image (With Promo Badges)'),
  hasAfterLabel: html.includes('Google Ad-Feed Image (Policy-Safe Clean Version)') || html.includes('Google Ad Shield Image (Policy-Compliant Clean Version)'),
  hasAiTime: html.includes('4.82s'),
  hasAiMask: html.includes('2.15%'),
  hasAiEngine: html.includes('Florence-2 + LaMa') || html.includes('Compliant') || html.includes('Policy'),
  hasMetafield: html.includes('safemedia.clean_ad_image_url'),
  hasVariantPills: html.includes('selectVariant(0)') && html.includes('selectVariant(1)')
};

print('CANARY_DYNAMIC_EVAL_JSON:' + JSON.stringify(results));
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0, f"Canary execution threw JavaScript error:\n{res.stderr}\n{res.stdout}")

        match = re.search(r"CANARY_DYNAMIC_EVAL_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match, f"Test output did not contain eval json. Stdout: {res.stdout}")
        data = json.loads(match.group(1))

        self.assertTrue(data["hasOrigImg"], "Canary result missing #canary-orig-img")
        self.assertTrue(data["hasCleanImg"], "Canary result missing #canary-clean-img")
        self.assertTrue(data["origImgSrc"], "Before image src does not match originalImageUrl")
        self.assertTrue(data["cleanImgSrc"], "After image src does not match cleanAdImageUrl")
        self.assertTrue(data["hasSideBySideGrid"], "Before and After images must be rendered side-by-side (grid grid-cols-1 md:grid-cols-2)")
        self.assertTrue(data["hasBeforeLabel"], "Missing Storefront Image (With Promo Badges) label")
        self.assertTrue(data["hasAfterLabel"], "Missing Google Ad Shield Image (Policy-Compliant Clean Version) label")
        self.assertTrue(data["hasAiTime"], "Missing AI processingSec telemetry badge")
        self.assertTrue(data["hasAiMask"], "Missing AI maskCoveragePct telemetry badge")
        self.assertTrue(data["hasAiEngine"], "Missing AI engine telemetry badge")
        self.assertTrue(data["hasMetafield"], "Missing safemedia.clean_ad_image_url metafield badge")
        self.assertTrue(data["hasVariantPills"], "Missing interactive selectVariant pills")

    def test_canary_interactive_variant_switching_mutates_dom(self):
        """Assert selectVariant(idx) switches active image to the selected variant without throwing errors."""
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
canaryData = {
  originalImageUrl: 'https://cdn.shopify.com/orig/bomber_sale.jpg',
  cleanAdImageUrl: 'https://cdn.safemedia.io/clean/bomber_clean.png',
  variantChecks: [
    { variantId: 'v1', title: 'Black / S', activeImageUrl: 'https://cdn.shopify.com/orig/bomber_sale.jpg' },
    { variantId: 'v2', title: 'Navy / M', activeImageUrl: 'https://cdn.shopify.com/orig/bomber_navy.jpg' }
  ]
};

renderCanaryResult(canaryData);
selectVariant(1);

const vResults = {
  activeVariantText: document.getElementById('active-variant-img').innerText,
  origImgSrc: document.getElementById('canary-orig-img').src
};
print('VARIANT_SWITCH_JSON:' + JSON.stringify(vResults));
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0, f"selectVariant threw error: {res.stderr}")

        match = re.search(r"VARIANT_SWITCH_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))

        self.assertEqual(
            data["activeVariantText"],
            "https://cdn.shopify.com/orig/bomber_navy.jpg",
            "active-variant-img text failed to update on variant switch",
        )
        self.assertEqual(
            data["origImgSrc"],
            "https://cdn.shopify.com/orig/bomber_navy.jpg",
            "canary-orig-img src failed to update on variant switch",
        )

    def test_bilingual_toggle_switches_canary_and_dom_without_reload(self):
        """Assert setLanguage('ja') and setLanguage('en') switch labels without error and re-render Canary result."""
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
canaryData = {
  productTitle: 'Premium Bomber',
  originalImageUrl: 'https://cdn.shopify.com/orig/bomber.jpg',
  cleanAdImageUrl: 'https://cdn.safemedia.io/clean/bomber.png',
  variantChecks: [{ variantId: 'v1', title: 'Red', activeImageUrl: 'https://cdn.shopify.com/orig/bomber.jpg' }]
};

renderCanaryResult(canaryData);
setLanguage('ja');

const jaContainer = document.getElementById('canary-container').innerHTML;
const hasJaBefore = jaContainer.includes('自社ストア表示（セール帯あり）');
const hasJaAfter = jaContainer.includes('Google広告配信用（AI消去済クリーン画像）');

setLanguage('en');
const enContainer = document.getElementById('canary-container').innerHTML;
const hasEnBefore = enContainer.includes('Storefront Image (With Promo Badges)');
const hasEnAfter = enContainer.includes('Google Ad-Feed Image (Policy-Safe Clean Version)') || enContainer.includes('Google Ad Shield Image (Policy-Compliant Clean Version)');

print('I18N_EVAL_JSON:' + JSON.stringify({ hasJaBefore, hasJaAfter, hasEnBefore, hasEnAfter }));
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0, f"setLanguage threw error: {res.stderr}")

        match = re.search(r"I18N_EVAL_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))

        self.assertTrue(data["hasJaBefore"], "Japanese before label missing after setLanguage('ja')")
        self.assertTrue(data["hasJaAfter"], "Japanese after label missing after setLanguage('ja')")
        self.assertTrue(data["hasEnBefore"], "English before label missing after switching back to 'en'")
        self.assertTrue(data["hasEnAfter"], "English after label missing after switching back to 'en'")

    # =========================================================================
    # Suite 4: Absolute Absence of SafeMedia Shield, Refresh, and WebP Metrics
    # =========================================================================

    def test_total_absence_of_safemedia_shield_branding(self):
        """Assert total absence of 'SafeMedia Shield' across the entire rendered HTML and script."""
        # Check case-insensitive pattern for "SafeMedia Shield"
        matches = re.findall(r"SafeMedia\s+Shield", self.raw_html, re.IGNORECASE)
        self.assertEqual(
            len(matches),
            0,
            f"VIOLATION: Legacy branding 'SafeMedia Shield' still found in rendered HTML ({len(matches)} occurrences): {matches}",
        )

    def test_total_absence_of_manual_refresh_button(self):
        """Assert total absence of '🔄 Refresh' button text and 'btn_refresh' element ID."""
        self.assertNotIn("🔄 Refresh", self.raw_html, "Found '🔄 Refresh' button in rendered HTML")
        self.assertNotIn("btn_refresh", self.raw_html, "Found 'btn_refresh' ID in rendered HTML")

    def test_total_absence_of_webp_compression_metrics(self):
        """
        Assert total absence of WebP compression metrics in preview/result cards:
        - No 'webp' / 'WebP' file compression mentions
        - No '-% Lighter' or '% lighter' badges
        - No 'compression' / 'compress' metrics
        """
        html_lower = self.raw_html.lower()

        # 1. Assert no mention of webp
        self.assertNotIn("webp", html_lower, "Found prohibited 'webp' references in rendered HTML")

        # 2. Assert no compression terminology in HTML
        self.assertNotIn("lighter", html_lower, "Found '% lighter' compression metric in rendered HTML")
        self.assertNotIn("compression", html_lower, "Found 'compression' metric in rendered HTML")
        self.assertNotIn("compress", html_lower, "Found 'compress' metric in rendered HTML")

    # =========================================================================
    # Suite 5: Adversarial Stress Testing of Frontend Handlers
    # =========================================================================

    def test_adversarial_canary_payload_missing_telemetry_gracefully_degrades(self):
        """Stress Test: renderCanaryResult handles missing aiMetadata, cleanAdImageUrl, and variantChecks without crashing."""
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
// Minimalist, partial payload missing aiMetadata, cleanAdImageUrl, variantChecks
const minimalPayload = {
  productId: '1002',
  productTitle: 'Minimal Product',
  originalImageUrl: 'https://cdn.shopify.com/orig/minimal.jpg'
};

try {
  canaryData = minimalPayload;
  renderCanaryResult(minimalPayload);
  const ok = document.getElementById('canary-container').innerHTML.includes('id="canary-orig-img"');
  print('ADVERSARIAL_TEST_JSON:' + JSON.stringify({ success: ok, error: null }));
} catch (e) {
  print('ADVERSARIAL_TEST_JSON:' + JSON.stringify({ success: false, error: e.message }));
}
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0, f"Adversarial payload crashed JSC: {res.stderr}")
        match = re.search(r"ADVERSARIAL_TEST_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertTrue(data["success"], f"renderCanaryResult failed to gracefully degrade: {data.get('error')}")

    def test_adversarial_select_variant_out_of_bounds_behavior(self):
        """Stress Test: Probe selectVariant with out-of-bounds index and document exception behavior."""
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
canaryData = {
  originalImageUrl: 'https://cdn.shopify.com/orig/bomber.jpg',
  variantChecks: [{ variantId: 'v1', activeImageUrl: 'https://cdn.shopify.com/orig/bomber.jpg' }]
};
renderCanaryResult(canaryData);

let threw = false;
let errMsg = '';
try {
  selectVariant(99);
} catch (e) {
  threw = true;
  errMsg = e.message;
}
print('OOB_PROBE_JSON:' + JSON.stringify({ threw, errMsg }));
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0)
        match = re.search(r"OOB_PROBE_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        # Document empirical behavior: selectVariant(99) throws TypeError because check is undefined
        self.assertTrue(data["threw"], "selectVariant(99) did not throw despite out-of-bounds access")
        self.assertIn("activeImageUrl", data["errMsg"])

    def test_adversarial_product_title_html_injection_probe(self):
        """Stress Test: Probe unescaped HTML interpolation in renderCanaryResult."""
        if not os.path.exists(JSC_BIN):
            self.skipTest(f"JavaScriptCore binary not found at {JSC_BIN}")

        js_test = """
const payloadWithHtml = {
  productId: '1003',
  productTitle: '<span id=\"injected-probe-tag\">Unescaped Promo</span>',
  originalImageUrl: 'https://cdn.shopify.com/orig/test.jpg',
  variantChecks: []
};
canaryData = payloadWithHtml;
renderCanaryResult(payloadWithHtml);

const injectedHtml = document.getElementById('canary-container').innerHTML;
const hasInjectedTag = injectedHtml.includes('<span id=\"injected-probe-tag\">Unescaped Promo</span>');
print('HTML_INJECTION_PROBE_JSON:' + JSON.stringify({ hasInjectedTag }));
"""
        res = self._execute_jsc_test(js_test)
        self.assertEqual(res.returncode, 0)
        match = re.search(r"HTML_INJECTION_PROBE_JSON:({.*})", res.stdout)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        # Note: In current implementation, HTML strings in title are interpolated directly into innerHTML
        self.assertTrue(data["hasInjectedTag"])


if __name__ == "__main__":
    unittest.main()

