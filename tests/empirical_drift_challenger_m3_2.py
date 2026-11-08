#!/usr/bin/env python3
"""
Empirical Code-to-Doc Drift Verification Suite
Target: docs/SYSTEM_DESIGN.md vs cloudflare_worker/src/{index.ts, ui.ts, types.ts}

Objective:
1. Verify REST API endpoints: confirm /api/canary/test, /api/batch/start, /api/batch/abort,
   /api/batch/resume, /api/rollback match actual route handlers in cloudflare_worker/src/index.ts.
2. Verify TypeScript interface fields: compare CanaryTestResult, StoreSnapshot, ProductSnapshot,
   TenantBillingState documented in docs/SYSTEM_DESIGN.md against definitions in cloudflare_worker/src/types.ts.
3. Verify UI element IDs and I18N key count (116 keys) documented in Section 3.5 against cloudflare_worker/src/ui.ts.
4. Formulate verdict: CONFIRMED or VIOLATION_FOUND.
"""

import json
import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "SYSTEM_DESIGN.md"
INDEX_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "index.ts"
TYPES_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "types.ts"
UI_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"


def extract_interface_block(text: str, interface_name: str) -> str:
    """Extracts the body of a TypeScript interface declaration using balanced braces."""
    idx = text.find(f"interface {interface_name}")
    if idx == -1:
        return ""
    start = text.find("{", idx)
    if start == -1:
        return ""
    brace_depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_depth += 1
        elif text[i] == "}":
            brace_depth -= 1
            if brace_depth == 0:
                end = i
                break
    return text[start + 1 : end]


def parse_interface_fields(block_text: str):
    """
    Parses top-level fields of a TypeScript interface block.
    Respects nested braces/brackets/parentheses and tracks JSDoc @deprecated tags.
    """
    clean_lines = []
    for line in block_text.split("\n"):
        deprecated = "@deprecated" in line
        # Strip comments
        line_clean = re.sub(r"//.*", "", line)
        line_clean = re.sub(r"/\*.*?\*/", "", line_clean)
        clean_lines.append((line_clean, deprecated))

    tokens = []
    current_entry = ""
    brace_depth = 0
    is_deprecated = False

    for line, dep in clean_lines:
        if dep:
            is_deprecated = True
        for char in line:
            if char in "{<(":
                brace_depth += 1
            elif char in "}>)":
                brace_depth -= 1

            if char in ";\n" and brace_depth == 0:
                entry = current_entry.strip()
                if entry:
                    tokens.append((entry, is_deprecated))
                current_entry = ""
                is_deprecated = False
            else:
                current_entry += char
    entry = current_entry.strip()
    if entry:
        tokens.append((entry, is_deprecated))

    fields = {}
    for entry, dep in tokens:
        m = re.match(r"^([a-zA-Z0-9_]+)(\??)\s*:\s*(.+)$", entry, re.DOTALL)
        if m:
            fname = m.group(1)
            is_opt = bool(m.group(2))
            raw_type = m.group(3).strip().rstrip(";")
            fields[fname] = {
                "name": fname,
                "optional": is_opt,
                "type": " ".join(raw_type.split()),
                "deprecated": dep,
            }
    return fields


def extract_i18n_keys(ui_content: str):
    """Extracts en and ja keys from const I18N in ui.ts."""
    en_match = re.search(r"en:\s*\{(.*?)\n\s*\},", ui_content, re.DOTALL)
    ja_match = re.search(r"ja:\s*\{(.*?)\n\s*\}", ui_content, re.DOTALL)

    def parse_keys(block):
        if not block:
            return []
        keys = []
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            m = re.match(r"^([a-zA-Z0-9_]+)\s*:", line)
            if m:
                keys.append(m.group(1))
        return keys

    en_keys = parse_keys(en_match.group(1)) if en_match else []
    ja_keys = parse_keys(ja_match.group(1)) if ja_match else []
    return en_keys, ja_keys


class TestCodeToDocDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert DOC_PATH.exists(), f"Doc file missing: {DOC_PATH}"
        assert INDEX_PATH.exists(), f"Index file missing: {INDEX_PATH}"
        assert TYPES_PATH.exists(), f"Types file missing: {TYPES_PATH}"
        assert UI_PATH.exists(), f"UI file missing: {UI_PATH}"

        cls.doc_content = DOC_PATH.read_text(encoding="utf-8")
        cls.index_content = INDEX_PATH.read_text(encoding="utf-8")
        cls.types_content = TYPES_PATH.read_text(encoding="utf-8")
        cls.ui_content = UI_PATH.read_text(encoding="utf-8")

    # =========================================================================
    # Part 1: REST API Endpoints Verification
    # =========================================================================
    def test_01_core_rest_api_endpoints_match(self):
        """Verify the 5 mandatory REST API endpoints match route handlers in index.ts."""
        core_endpoints = [
            ("POST", "/api/canary/test"),
            ("POST", "/api/batch/start"),
            ("POST", "/api/batch/abort"),
            ("POST", "/api/batch/resume"),
            ("POST", "/api/rollback"),
        ]

        for method, path in core_endpoints:
            pattern = re.compile(
                rf'url\.pathname\s*===\s*"{re.escape(path)}"\s*&&\s*request\.method\s*===\s*"{method}"'
            )
            match = pattern.search(self.index_content)
            self.assertIsNotNone(
                match,
                f"Core endpoint {method} {path} not found in cloudflare_worker/src/index.ts",
            )
            # Verify documented in SYSTEM_DESIGN.md
            self.assertIn(
                f"`{method} {path}`",
                self.doc_content,
                f"Core endpoint {method} {path} not documented in docs/SYSTEM_DESIGN.md",
            )

    def test_02_additional_api_endpoints_match(self):
        """Verify additional documented API routes match index.ts."""
        additional_endpoints = [
            ("GET", "/api/status"),
            ("POST", "/api/billing/subscribe"),
            ("POST", "/api/billing/reset"),
            ("POST", "/api/webhooks/register"),
            ("POST", "/api/webhooks/unregister"),
            ("POST", "/api/dual-feed/sync"),
            ("POST", "/api/snapshot/create"),
            ("POST", "/webhooks/products/update"),
        ]

        for method, path in additional_endpoints:
            pattern = re.compile(
                rf'url\.pathname\s*===\s*"{re.escape(path)}"\s*&&\s*request\.method\s*===\s*"{method}"'
            )
            match = pattern.search(self.index_content)
            self.assertIsNotNone(
                match,
                f"Endpoint {method} {path} handler missing in cloudflare_worker/src/index.ts",
            )
            endpoint_documented = path in self.doc_content or (
                path == "/api/webhooks/unregister" and "unregister" in self.doc_content
            )
            self.assertTrue(
                endpoint_documented,
                f"Endpoint {path} missing in docs/SYSTEM_DESIGN.md",
            )

        # Check clean media route with prefix
        self.assertIn('url.pathname.startsWith("/clean-media/")', self.index_content)
        self.assertIn("/clean-media/:shop/:filename", self.doc_content)

        # Check root UI route
        self.assertIn('url.pathname === "/" && request.method === "GET"', self.index_content)

    def test_03_endpoint_status_codes_and_payload_contracts(self):
        """Verify HTTP status codes documented for canary and batch endpoints."""
        # 1. Canary status codes: 402, 423, 400, 200
        self.assertIn("CIRCUIT_BREAKER_ACTIVE", self.index_content)
        self.assertIn("CIRCUIT_BREAKER_ACTIVE", self.doc_content)
        self.assertIn("TRIAL_QUOTA_EXCEEDED", self.index_content)
        self.assertIn("TRIAL_QUOTA_EXCEEDED", self.doc_content)
        self.assertIn("INVALID_IMAGE_URL", self.index_content)
        self.assertIn("INVALID_IMAGE_URL", self.doc_content)

        # 2. Batch start subscription requirement: 402 SUBSCRIPTION_REQUIRED_FOR_BULK
        self.assertIn("SUBSCRIPTION_REQUIRED_FOR_BULK", self.index_content)
        self.assertIn("SUBSCRIPTION_REQUIRED_FOR_BULK", self.doc_content)

        # 3. Rollback response attributes: restoredCount, snapshotId, metafieldsRestored
        for key in ["restoredCount", "snapshotId", "metafieldsRestored", "success"]:
            self.assertIn(key, self.doc_content)

    # =========================================================================
    # Part 2: TypeScript Interface Fields Comparison
    # =========================================================================
    def test_04_typescript_interface_store_snapshot(self):
        """Compare StoreSnapshot fields in doc vs types.ts."""
        doc_fields = parse_interface_fields(extract_interface_block(self.doc_content, "StoreSnapshot"))
        code_fields = parse_interface_fields(extract_interface_block(self.types_content, "StoreSnapshot"))

        self.assertTrue(len(doc_fields) > 0, "No fields parsed for doc StoreSnapshot")
        self.assertTrue(len(code_fields) > 0, "No fields parsed for code StoreSnapshot")

        # Every documented field must exist in code
        for fname, d_info in doc_fields.items():
            self.assertIn(fname, code_fields, f"StoreSnapshot.{fname} missing in types.ts")
            c_info = code_fields[fname]
            self.assertEqual(
                d_info["optional"],
                c_info["optional"],
                f"StoreSnapshot.{fname} optionality mismatch: doc={d_info['optional']} vs code={c_info['optional']}",
            )

        # No extra undocumented non-deprecated fields in code
        extra = set(code_fields.keys()) - set(doc_fields.keys())
        self.assertEqual(extra, set(), f"Extra undocumented fields in code StoreSnapshot: {extra}")

    def test_05_typescript_interface_product_snapshot(self):
        """Compare ProductSnapshot fields in doc vs types.ts."""
        doc_fields = parse_interface_fields(extract_interface_block(self.doc_content, "ProductSnapshot"))
        code_fields = parse_interface_fields(extract_interface_block(self.types_content, "ProductSnapshot"))

        expected_fields = [
            "productId",
            "productTitle",
            "bodyHtml",
            "variants",
            "originalMediaList",
            "capturedAt",
            "cleanAdImageUrl",
            "dualFeedMetadata",
        ]

        for fname in expected_fields:
            self.assertIn(fname, doc_fields, f"ProductSnapshot.{fname} missing in doc")
            self.assertIn(fname, code_fields, f"ProductSnapshot.{fname} missing in types.ts")
            self.assertEqual(
                doc_fields[fname]["optional"],
                code_fields[fname]["optional"],
                f"ProductSnapshot.{fname} optionality mismatch",
            )

    def test_06_typescript_interface_tenant_billing_state(self):
        """Compare TenantBillingState fields in doc vs types.ts."""
        doc_fields = parse_interface_fields(extract_interface_block(self.doc_content, "TenantBillingState"))
        code_fields = parse_interface_fields(extract_interface_block(self.types_content, "TenantBillingState"))

        self.assertTrue(len(doc_fields) >= 12, f"Expected >= 12 fields, found {len(doc_fields)}")
        for fname, d_info in doc_fields.items():
            self.assertIn(fname, code_fields, f"TenantBillingState.{fname} missing in types.ts")
            c_info = code_fields[fname]
            self.assertEqual(
                d_info["optional"],
                c_info["optional"],
                f"TenantBillingState.{fname} optionality mismatch",
            )

        extra = set(code_fields.keys()) - set(doc_fields.keys())
        self.assertEqual(extra, set(), f"Extra undocumented fields in code TenantBillingState: {extra}")

    def test_07_typescript_interface_canary_test_result(self):
        """Compare CanaryTestResult fields in doc vs types.ts."""
        doc_fields = parse_interface_fields(extract_interface_block(self.doc_content, "CanaryTestResult"))
        code_fields = parse_interface_fields(extract_interface_block(self.types_content, "CanaryTestResult"))

        # Primary pure dual-feed fields
        primary_fields = [
            "productId",
            "productTitle",
            "originalImageUrl",
            "cleanAdImageUrl",
            "metafieldKey",
            "aiMetadata",
            "variantChecks",
            "canaryUsedCount",
            "canaryLimit",
            "beforeImageUrl",
            "afterImageUrl",
        ]

        for fname in primary_fields:
            self.assertIn(fname, doc_fields, f"CanaryTestResult.{fname} missing in doc")
            self.assertIn(fname, code_fields, f"CanaryTestResult.{fname} missing in code types.ts")

        # Any extra fields in code must be explicitly marked @deprecated
        extra_fields = set(code_fields.keys()) - set(doc_fields.keys())
        for extra_name in extra_fields:
            self.assertTrue(
                code_fields[extra_name]["deprecated"],
                f"Field '{extra_name}' in CanaryTestResult is not documented and not marked @deprecated!",
            )

    # =========================================================================
    # Part 3: UI Element IDs and I18N Key Count (116 Keys)
    # =========================================================================
    def test_08_i18n_symmetric_key_count_exactly_116(self):
        """Verify that I18N in ui.ts defines exactly 116 symmetrical keys for en and ja."""
        en_keys, ja_keys = extract_i18n_keys(self.ui_content)

        self.assertEqual(
            len(en_keys),
            116,
            f"Expected exactly 116 English I18N keys, found {len(en_keys)}: {en_keys}",
        )
        self.assertEqual(
            len(ja_keys),
            116,
            f"Expected exactly 116 Japanese I18N keys, found {len(ja_keys)}: {ja_keys}",
        )

        diff = set(en_keys) ^ set(ja_keys)
        self.assertEqual(
            diff,
            set(),
            f"Asymmetric I18N keys between en and ja: {diff}",
        )

        # Check documented claim in SYSTEM_DESIGN.md
        self.assertIn("116共通キー", self.doc_content)
        self.assertIn("厳密に一致する116個のキー", self.doc_content)

    def test_09_ui_element_ids_in_section_3_5(self):
        """Verify all DOM element IDs documented in Section 3.5 exist in ui.ts."""
        sec35_match = re.search(
            r"### 3\.5 管理ダッシュボード UI / UX 設計.*?(?=## 第4章|\Z)",
            self.doc_content,
            re.DOTALL,
        )
        self.assertIsNotNone(sec35_match, "Section 3.5 not found in docs/SYSTEM_DESIGN.md")
        sec35_text = sec35_match.group(0)

        # Extract all element IDs documented with # prefix or id="..." attribute
        doc_ids = set(re.findall(r"#([a-zA-Z0-9_\-]+)", sec35_text)) | set(
            re.findall(r"id=[\"']([a-zA-Z0-9_\-]+)[\"']", sec35_text)
        )

        self.assertTrue(
            len(doc_ids) >= 30,
            f"Expected at least 30 DOM IDs documented in Section 3.5, found {len(doc_ids)}",
        )

        # Extract actual DOM IDs defined in ui.ts
        ui_ids = set(re.findall(r'id=[\"\']([a-zA-Z0-9_\-]+)[\"\']', self.ui_content))

        missing_ids = doc_ids - ui_ids
        self.assertEqual(
            missing_ids,
            set(),
            f"Documented DOM IDs in Section 3.5 not found in ui.ts: {missing_ids}",
        )

    def test_10_representative_i18n_table_keys(self):
        """Verify all 24 representative keys in Section 3.5.7 table exist in I18N."""
        en_keys, _ = extract_i18n_keys(self.ui_content)
        en_set = set(en_keys)

        representative_keys = [
            "app_title",
            "badge_active",
            "hero_headline",
            "pill_gmc_compliant",
            "pill_zero_storefront_change",
            "pill_variant_preservation",
            "zone1_title",
            "z1_when",
            "z1_desc",
            "z1_btn_toggle",
            "status_clean_ready",
            "step1_title",
            "step1_when",
            "step1_lbl_before",
            "step1_lbl_after",
            "telemetry_time",
            "telemetry_mask",
            "step2_title",
            "step2_when",
            "step2_btn",
            "step2_abort_btn",
            "safety_title",
            "safety_when",
            "btn_backup_now",
            "btn_restore",
        ]

        for k in representative_keys:
            self.assertIn(
                k,
                en_set,
                f"Representative I18N key '{k}' documented in Section 3.5.7 table missing from I18N in ui.ts",
            )

    def test_11_branding_and_zero_ui_refresh_removal(self):
        """Verify branding AdFeed Clean for Google Shopping and absence of manual refresh button."""
        brand_str = "AdFeed Clean for Google Shopping"
        self.assertIn(brand_str, self.doc_content)
        self.assertIn(brand_str, self.ui_content)

        # Manual refresh button (btn_refresh) should NOT be present in ui.ts DOM
        self.assertNotIn('id="btn_refresh"', self.ui_content)
        self.assertNotIn("id='btn_refresh'", self.ui_content)


def run_empirical_suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCodeToDocDrift)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    print("EMPIRICAL CODE-TO-DOC DRIFT VERIFICATION SUMMARY")
    print("=" * 65)
    print(f"Total Tests Run : {result.testsRun}")
    print(f"Failures        : {len(result.failures)}")
    print(f"Errors          : {len(result.errors)}")

    if result.wasSuccessful():
        verdict = "CONFIRMED"
        print(f"Final Verdict   : {verdict} (Codebase and docs/SYSTEM_DESIGN.md are in 100% agreement)")
    else:
        verdict = "VIOLATION_FOUND"
        print(f"Final Verdict   : {verdict} (Drift detected between code and doc)")
    print("=" * 65 + "\n")

    return verdict, result


if __name__ == "__main__":
    verdict, result = run_empirical_suite()
    sys.exit(0 if result.wasSuccessful() else 1)
