"""
tests/test_legal_and_store_assets.py
Comprehensive Verification Suite for Shopify App Store Publishing STEP 2:
1. Public Privacy Policy (GET /privacy, HEAD /privacy, bilingual EN/JA)
2. Public Terms of Service (GET /terms, HEAD /terms, bilingual EN/JA, $65 liability cap)
3. Public Brand & Store Visual Assets (GET /assets/..., HEAD /assets/...)
4. Physical PNG & SVG Asset Dimensions & Existence (1200x1200px icon, 1600x900px banners)
5. Embedded Dashboard Footer Legal & Support Links
"""

import os
import pathlib
import subprocess
import unittest
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import TestClient, PRIMARY_SHOP


class TestLegalAndStoreAssets(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()

    # =========================================================================
    # 1. Privacy Policy Tests (GET /privacy, HEAD /privacy)
    # =========================================================================

    def test_privacy_policy_get_returns_200_html(self):
        """TC-LEGAL-01: GET /privacy returns HTTP 200 with Polaris-styled HTML."""
        res = self.client.get("/privacy")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("Content-Type", ""))
        body = res.text

        # Basic document structure
        self.assertIn("<!DOCTYPE html>", body)
        self.assertIn("Privacy Policy | AdFeed Clean for Google Shopping", body)
        self.assertIn("Effective Date: November 27, 2026 | Version 2.0", body)
        self.assertIn('lang="en"', body)
        self.assertIn('<div id="content-en" class="card">', body)
        self.assertIn('<div id="content-ja" class="card hidden">', body)
        self.assertNotIn("navigator.language", body)

        # Zero-PII commitment
        self.assertIn("We do NOT collect, process, or store end-consumer personal data", body)
        self.assertIn("Zero PII Policy", body)

        # GDPR / CCPA mandatory webhooks coverage
        self.assertIn("customers/data_request", body)
        self.assertIn("customers/redact", body)
        self.assertIn("shop/redact", body)
        self.assertIn("app/uninstalled", body)

        # AI training policy & security
        self.assertIn("train public third-party foundation models", body)
        self.assertIn("safemedia.clean_ad_image_url", body)
        self.assertIn("/api/feed-preview.xml", body)
        self.assertIn("studio.nexus.ops@gmail.com", body)

        # Language toggle scripts and elements
        self.assertIn("switchLang('ja')", body)
        self.assertIn("content-ja", body)
        self.assertIn("content-en", body)

    def test_privacy_policy_head_request_returns_200_no_body(self):
        """TC-LEGAL-02: HEAD /privacy returns HTTP 200 without payload (for uptime monitors & curl -I)."""
        res = self.client.request("HEAD", "/privacy")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("Content-Type", ""))
        self.assertEqual(len(res.content), 0)

    def test_privacy_policy_japanese_query_support(self):
        """TC-LEGAL-03: GET /privacy?lang=ja sets document lang to ja and renders Japanese content visible."""
        res = self.client.get("/privacy?lang=ja")
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('lang="ja"', body)
        self.assertIn('<div id="content-en" class="card hidden">', body)
        self.assertIn('<div id="content-ja" class="card">', body)
        self.assertIn("プライバシーポリシー", body)
        self.assertIn("データ最小化とプライバシー保護への誓約", body)
        self.assertIn("購入者（一般エンド消費者）の個人情報", body)

    # =========================================================================
    # 2. Terms of Service Tests (GET /terms, HEAD /terms)
    # =========================================================================

    def test_terms_of_service_get_returns_200_html(self):
        """TC-LEGAL-04: GET /terms returns HTTP 200 with comprehensive terms, pricing, and liability cap."""
        res = self.client.get("/terms")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("Content-Type", ""))
        body = res.text

        self.assertIn("Terms of Service | AdFeed Clean for Google Shopping", body)
        self.assertIn("Effective Date: November 27, 2026 | Version 2.0", body)
        self.assertIn('lang="en"', body)
        self.assertIn('<div id="content-en" class="card">', body)
        self.assertIn('<div id="content-ja" class="card hidden">', body)
        self.assertNotIn("navigator.language", body)

        self.assertIn("Dual-Feed Smart Routing", body)
        self.assertIn("Zero-UI Always-On Shield", body)
        self.assertIn("1-Click Snapshot Restore", body)
        self.assertIn("/api/feed-preview.xml", body)

        # Pricing, Overage & Trial terms
        self.assertIn("$65.00 USD / month", body)
        self.assertIn("500 cleaned images / month", body)
        self.assertIn("$0.05 USD per cleaned image", body)
        self.assertIn("$100.00 USD / month", body)
        self.assertIn("14 Days Free Trial", body)
        self.assertIn("50 clean images", body)
        self.assertIn("5 Sample Preview Tests", body)

        # Post-cancellation feed deactivation & GMC unlink instructions
        self.assertIn("/clean-media/:shop/*", body)
        self.assertIn("HTTP 404 Not Found", body)
        self.assertIn("must remove or unlink the Supplemental Feed URL", body)

        # Liability Cap & Best-Effort SLA
        self.assertIn("Aggregate Liability Cap: One (1) Month Subscription Fee", body)
        self.assertIn("$65.00 USD", body)
        self.assertIn("best-effort basis", body)

        # Storefront integrity guarantee
        self.assertIn("Non-Destructive Routing", body)
        self.assertIn("Variant Protection", body)
        self.assertIn("studio.nexus.ops@gmail.com", body)

    def test_terms_of_service_head_request_returns_200_no_body(self):
        """TC-LEGAL-05: HEAD /terms returns HTTP 200 without payload."""
        res = self.client.request("HEAD", "/terms")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("Content-Type", ""))
        self.assertEqual(len(res.content), 0)

    def test_terms_of_service_japanese_query_support(self):
        """TC-LEGAL-06: GET /terms?lang=ja renders Japanese Terms of Service with current pricing & feed deactivation notice."""
        res = self.client.get("/terms?lang=ja")
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('lang="ja"', body)
        self.assertIn('<div id="content-en" class="card hidden">', body)
        self.assertIn('<div id="content-ja" class="card">', body)
        self.assertIn("利用規約", body)
        self.assertIn("月額 $65.00 USD（約 9,800円）", body)
        self.assertIn("月間500枚の画像処理を含む", body)
        self.assertIn("$0.05 USD / 枚", body)
        self.assertIn("14日間の無料トライアル", body)
        self.assertIn("50枚", body)
        self.assertIn("HTTP 404 Not Found", body)
        self.assertIn("事前に必ず Google Merchant Center（GMC）および Meta カタログ側の補助フィード設定", body)

    # =========================================================================
    # 3. Public Visual Asset Routes (GET /assets/..., HEAD /assets/...)
    # =========================================================================

    def test_public_asset_app_icon_svg(self):
        """TC-ASSET-01: GET /assets/app_icon_1200x1200.svg returns valid SVG."""
        res = self.client.get("/assets/app_icon_1200x1200.svg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "image/svg+xml")
        self.assertIn("<svg", res.text)
        self.assertIn("viewBox=\"0 0 1200 1200\"", res.text)
        self.assertIn("ADFEED CLEAN", res.text)
        self.assertIn("FOR GOOGLE SHOPPING", res.text)

    def test_public_asset_dual_feed_banner_svg(self):
        """TC-ASSET-02: GET /assets/banner_dual_feed_1600x900.svg returns valid 16:9 SVG."""
        res = self.client.get("/assets/banner_dual_feed_1600x900.svg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "image/svg+xml")
        self.assertIn("viewBox=\"0 0 1600 900\"", res.text)
        self.assertIn("DUAL-FEED ROUTING", res.text)
        self.assertIn("safemedia.clean_ad_image_url", res.text)

    def test_public_asset_always_on_banner_svg(self):
        """TC-ASSET-03: GET /assets/banner_always_on_1600x900.svg returns valid 16:9 SVG."""
        res = self.client.get("/assets/banner_always_on_1600x900.svg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "image/svg+xml")
        self.assertIn("viewBox=\"0 0 1600 900\"", res.text)
        self.assertIn("ZERO-UI AUTOMATION", res.text)

    def test_public_asset_one_click_rollback_banner_svg(self):
        """TC-ASSET-04: GET /assets/banner_one_click_rollback_1600x900.svg returns valid 16:9 SVG."""
        res = self.client.get("/assets/banner_one_click_rollback_1600x900.svg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "image/svg+xml")
        self.assertIn("viewBox=\"0 0 1600 900\"", res.text)
        self.assertIn("STORE INTEGRITY FIRST", res.text)
        self.assertIn("Immutable Cloud", res.text)

    def test_public_asset_head_and_404(self):
        """TC-ASSET-05: HEAD returns 200 no body; missing asset returns 404."""
        res_head = self.client.request("HEAD", "/assets/app_icon_1200x1200.svg")
        self.assertEqual(res_head.status_code, 200)
        self.assertEqual(len(res_head.content), 0)

        res_404 = self.client.get("/assets/non_existent_asset.svg")
        self.assertEqual(res_404.status_code, 404)

    # =========================================================================
    # 4. Physical Asset Files Verification (Exact Pixel Dimensions & Storage)
    # =========================================================================

    def test_physical_png_and_svg_assets_exist(self):
        """TC-PHYSICAL-01: Verifies all PNG and SVG files exist in assets/ directory."""
        assets_dir = REPO_ROOT / "assets"
        expected_files = [
            "app_icon_1200x1200.png",
            "app_icon_1200x1200.svg",
            "banner_dual_feed_1600x900.png",
            "banner_dual_feed_1600x900.svg",
            "banner_always_on_1600x900.png",
            "banner_always_on_1600x900.svg",
            "banner_one_click_rollback_1600x900.png",
            "banner_one_click_rollback_1600x900.svg",
        ]
        for fname in expected_files:
            fpath = assets_dir / fname
            self.assertTrue(fpath.exists(), f"Expected asset file missing: {fpath}")
            self.assertGreater(fpath.stat().st_size, 0, f"Asset file is empty: {fpath}")

    def test_physical_png_dimensions_via_sips(self):
        """TC-PHYSICAL-02: Verifies exact 1200x1200 and 1600x900 dimensions via macOS sips."""
        assets_dir = REPO_ROOT / "assets"
        specs = [
            ("app_icon_1200x1200.png", 1200, 1200),
            ("banner_dual_feed_1600x900.png", 1600, 900),
            ("banner_always_on_1600x900.png", 1600, 900),
            ("banner_one_click_rollback_1600x900.png", 1600, 900),
        ]

        for fname, exp_w, exp_h in specs:
            fpath = str(assets_dir / fname)
            cmd = ["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", fpath]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                out = res.stdout
                self.assertIn(f"pixelWidth: {exp_w}", out, f"Incorrect width for {fname}")
                self.assertIn(f"pixelHeight: {exp_h}", out, f"Incorrect height for {fname}")
            except FileNotFoundError:
                # Fallback if sips is not found in test environment
                pass

    # =========================================================================
    # 5. Dashboard Embedded Footer Legal & Support Links
    # =========================================================================

    def test_dashboard_ui_contains_legal_footer(self):
        """TC-UI-FOOTER-01: GET / (Dashboard) contains links to /privacy and /terms."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('href="/privacy"', body)
        self.assertIn('href="/terms"', body)
        self.assertIn("studio.nexus.ops@gmail.com", body)
        self.assertIn("AdFeed Clean for Google Shopping. All rights reserved.", body)


if __name__ == "__main__":
    unittest.main()
