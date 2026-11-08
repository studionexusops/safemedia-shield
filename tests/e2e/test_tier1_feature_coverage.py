"""
test_tier1_feature_coverage.py
Tier 1: Feature Coverage E2E Tests (>=5 test cases per core feature).

Core Features Tested:
1. Canary AI Promo Removal (5 test cases)
2. Batch Non-Destructive Metafield Generation (5 test cases)
3. Auto-Sync Webhook Toggle (5 test cases)
4. 1-Click Rollback (5 test cases)
5. 2-Zone UI Layout (5 test cases)
6. Security Guards (5 test cases)
Total: 30 test cases
"""

import json
import pathlib
import sys
import time
import unittest
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
    OTHER_SHOP,
    compute_shopify_hmac,
)


class TestTier1CanaryAIPromoRemoval(unittest.TestCase):
    """Tier 1 - Feature 1: Canary 1-Product AI Text/Badge Removal Preview."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_canary_01_returns_before_and_after_images(self):
        """TC-T1-CANARY-01: Canary preview returns Before (Storefront) vs After (Clean Ad Image) URLs."""
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200, f"Expected 200 OK: {res.text}")
        data = res.json()
        self.assertIn("originalImageUrl", data)
        self.assertIn("cleanAdImageUrl", data)
        self.assertTrue(data["originalImageUrl"].startswith("http"), "originalImageUrl must be a valid URL")
        self.assertTrue(data["cleanAdImageUrl"].startswith("http"), "cleanAdImageUrl must be a valid URL")
        self.assertNotEqual(data["originalImageUrl"], data["cleanAdImageUrl"], "Clean ad image must be distinct from original")

    def test_canary_02_pure_dual_feed_metafield_contract(self):
        """TC-T1-CANARY-02: Canary result returns safemedia.clean_ad_image_url metafieldKey without legacy WebP metrics."""
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("metafieldKey"), "safemedia.clean_ad_image_url")
        self.assertNotIn("savingsPercentage", data, "Pure Dual-Feed contract eliminates WebP savingsPercentage")

    def test_canary_03_preserves_variant_media_bindings(self):
        """TC-T1-CANARY-03: Canary verifies all variant media links are 100% preserved."""
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        variant_checks = data.get("variantChecks", [])
        self.assertGreater(len(variant_checks), 0, "Canary product must have variants to check")
        for vc in variant_checks:
            self.assertTrue(vc.get("preserved"), f"Variant {vc.get('variantId')} media binding was not preserved")
            self.assertTrue(vc.get("hasOriginalMedia"), f"Variant {vc.get('variantId')} lost original media reference")

    def test_canary_04_returns_ai_metadata(self):
        """TC-T1-CANARY-04: Canary returns AI metadata including processing time, mask coverage %, and engine."""
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        ai_meta = data.get("aiMetadata", {})
        self.assertIn("processingSec", ai_meta)
        self.assertIn("maskCoveragePct", ai_meta)
        self.assertIn("engine", ai_meta)
        self.assertGreater(ai_meta["processingSec"], 0)
        self.assertGreater(ai_meta["maskCoveragePct"], 0)
        self.assertIn("Florence", ai_meta["engine"])

    def test_canary_05_increments_quota_and_reports_limit(self):
        """TC-T1-CANARY-05: Canary increments trial usage counter from 0 to 1 and reports limit of 5."""
        res1 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1.get("canaryUsedCount"), 1)
        self.assertEqual(data1.get("canaryLimit"), 5)

        # Check /api/status matches
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}")
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["billing"]["canaryUsedCount"], 1)


class TestTier1BatchNonDestructiveMetafields(unittest.TestCase):
    """Tier 1 - Feature 2: Batch Non-Destructive Metafield Generation."""

    def setUp(self):
        self.client = TestClient()
        # Activate 14-day trial so batch processing is permitted
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0})

    def test_batch_01_starts_successfully_with_snapshot(self):
        """TC-T1-BATCH-01: Full catalog batch sync starts with pre-execution immutable snapshot."""
        res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200, f"Expected 200 OK: {res.text}")
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("snapshotId", data)
        self.assertGreater(data.get("totalProducts", 0), 0)

    def test_batch_02_populates_clean_ad_image_metafields(self):
        """TC-T1-BATCH-02: Batch generates clean ad image URLs into safemedia.clean_ad_image_url metafields."""
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}")
        self.assertEqual(status_res.status_code, 200)
        products = status_res.json().get("dualFeedProducts", [])
        self.assertGreater(len(products), 0)
        for p in products:
            self.assertIsNotNone(p.get("cleanAdImageUrl"), f"Product {p.get('productId')} missing cleanAdImageUrl metafield")
            self.assertTrue(p["cleanAdImageUrl"].startswith("https://cdn.safemedia.io/clean/"))

    def test_batch_03_storefront_images_remain_unmodified(self):
        """TC-T1-BATCH-03: Invariant check: Storefront image URLs remain 100% untouched and preserved."""
        status_before = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        orig_storefront_urls = [p["storefrontImageUrl"] for p in status_before["dualFeedProducts"]]

        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})

        status_after = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        after_storefront_urls = [p["storefrontImageUrl"] for p in status_after["dualFeedProducts"]]

        self.assertEqual(orig_storefront_urls, after_storefront_urls, "Storefront images must never be altered by batch sync!")

    def test_batch_04_variant_mappings_remain_intact(self):
        """TC-T1-BATCH-04: Invariant check: Variant media bindings remain intact across all catalog products."""
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        store = self.client.app.get_store(PRIMARY_SHOP)
        for prod in store.catalog:
            for variant in prod.get("variants", []):
                self.assertIsNotNone(variant.get("media_id"), f"Variant {variant.get('id')} lost media_id reference")

    def test_batch_05_job_state_completed_with_zero_errors(self):
        """TC-T1-BATCH-05: Batch job state transitions to COMPLETED with total == processed and zero errors."""
        res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}")
        job_state = status_res.json().get("jobState", {})
        self.assertEqual(job_state.get("status"), "COMPLETED")
        self.assertEqual(job_state.get("processed"), job_state.get("total"))
        self.assertEqual(len(job_state.get("errors", [])), 0)


class TestTier1AutoSyncWebhookToggle(unittest.TestCase):
    """Tier 1 - Feature 3: Auto-Sync Webhook Toggle and Event Receiver."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0})

    def test_toggle_01_unregister_disables_auto_sync(self):
        """TC-T1-TOGGLE-01: POST /api/webhooks/unregister disables auto-sync in tenant state."""
        res = self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json().get("autoSyncEnabled"))
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}")
        self.assertFalse(status_res.json()["billing"]["autoSyncEnabled"])

    def test_toggle_02_disabled_webhook_skips_processing(self):
        """TC-T1-TOGGLE-02: Disabled auto-sync returns skipped response without processing AI."""
        self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/black_promo_sale.jpg"}}
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("skipped"))
        self.assertEqual(res.json().get("reason"), "auto_sync_disabled")

    def test_toggle_03_register_enables_auto_sync(self):
        """TC-T1-TOGGLE-03: POST /api/webhooks/register enables auto-sync and stores webhookId."""
        self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})
        res = self.client.post("/api/webhooks/register", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("autoSyncEnabled"))
        self.assertIn("webhookId", res.json())

    def test_toggle_04_enabled_webhook_processes_ai_cleanup(self):
        """TC-T1-TOGGLE-04: Enabled auto-sync executes AI cleanup and populates metafield on product update."""
        self.client.post("/api/webhooks/register", json_data={"shop": PRIMARY_SHOP})
        payload = {
            "id": 1001,
            "title": "プレミアム ヘビーウェイト クラシックTシャツ",
            "image": {"src": "https://cdn.shopify.com/orig/black_promo_sale.jpg"},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("skipped"))
        self.assertIn("cleanAdImageUrl", data)
        self.assertEqual(data.get("metafieldKey"), "clean_ad_image_url")

    def test_toggle_05_webhook_deduplication_skips_identical_image(self):
        """TC-T1-TOGGLE-05: Repeated webhook for same image URL skips GPU call (idempotency guard)."""
        payload = {
            "id": 1001,
            "image": {"src": "https://cdn.shopify.com/orig/black_promo_sale.jpg"},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        # First call processes
        res1 = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res1.status_code, 200)

        # Second call skips
        res2 = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json().get("skipped"))
        self.assertEqual(res2.json().get("reason"), "already_cleaned_for_current_image")


class TestTier1OneClickRollback(unittest.TestCase):
    """Tier 1 - Feature 4: 1-Click Rollback (R2 Immutable Snapshot Restore)."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0})

    def test_rollback_01_restores_variant_bindings(self):
        """TC-T1-ROLLBACK-01: Rollback restores variant bindings to pre-batch snapshot baseline."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        # Snapshot baseline has valid media_ids
        snap_id = store.create_snapshot()

        # Simulate corrupting variant media_id
        store.catalog[0]["variants"][0]["media_id"] = None

        # Execute rollback
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))

        # Verify variant restored
        self.assertIsNotNone(store.catalog[0]["variants"][0]["media_id"])

    def test_rollback_02_reverts_batch_metafields(self):
        """TC-T1-ROLLBACK-02: Rollback clears newly created clean ad image metafields back to snapshot state."""
        # Baseline: clean store without ad metafields
        snap_id = self.client.app.get_store(PRIMARY_SHOP).create_snapshot()

        # Execute batch sync (adds metafields)
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        status_after_batch = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertIsNotNone(status_after_batch["dualFeedProducts"][0]["cleanAdImageUrl"])

        # Rollback to pre-batch snapshot
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("metafieldsRestored"))

        # Metafields should be back to baseline (None)
        status_after_rollback = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertIsNone(status_after_rollback["dualFeedProducts"][0]["cleanAdImageUrl"])

    def test_rollback_03_performance_under_10_seconds(self):
        """TC-T1-ROLLBACK-03: Rollback completes well within the 10-second SLA limit."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        snap_id = store.create_snapshot()

        t0 = time.time()
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        duration = time.time() - t0

        self.assertEqual(res.status_code, 200)
        self.assertLess(duration, 10.0, f"Rollback took {duration:.3f}s (exceeded 10s SLA)")

    def test_rollback_04_specific_snapshot_id_targeted(self):
        """TC-T1-ROLLBACK-04: Rollback accepts explicit snapshotId to restore historical version."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        snap_id_1 = store.create_snapshot()
        time.sleep(0.01)
        snap_id_2 = store.create_snapshot()

        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id_1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("snapshotId"), snap_id_1)

    def test_rollback_05_idempotent_multiple_runs(self):
        """TC-T1-ROLLBACK-05: Running rollback multiple times in succession remains idempotent and stable."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        snap_id = store.create_snapshot()

        res1 = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        res2 = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(len(store.catalog), 2)


class TestTier1TwoZoneUILayout(unittest.TestCase):
    """Tier 1 - Feature 5: 2-Zone Information Architecture & Unified 5-Layer UI."""

    def setUp(self):
        self.client = TestClient()

    def test_ui_01_branding_updated_and_legacy_absent(self):
        """TC-T1-UI-01: Dashboard displays 'AdFeed Clean for Google Shopping' and excludes legacy 'SafeMedia Shield'."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("AdFeed Clean for Google Shopping", html)
        self.assertNotIn("SafeMedia Shield", html)

    def test_ui_02_manual_refresh_button_removed(self):
        """TC-T1-UI-02: Manual refresh button ('🔄 Refresh' / 'btn_refresh') is absent from header."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        html = res.text
        self.assertNotIn("🔄 Refresh", html)
        self.assertNotIn("btn_refresh", html)

    def test_ui_03_zone1_core_automation_structure(self):
        """TC-T1-UI-03: Zone 1 (Core Automation) renders live status indicator, toggle button, and synced feed table."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        html = res.text
        self.assertIn("zone-core-automation", html)
        self.assertIn("Zone 1: Core Automation", html)
        self.assertIn("toggle_auto_sync", html)
        self.assertIn("synced_feed_table", html)
        self.assertIn("🟢 Active", html)

    def test_ui_04_zone2_sequential_three_steps(self):
        """TC-T1-UI-04: Zone 2 (Onboarding Tools & Safety Suite) renders Step 1, Step 2, and Step 3 sequentially."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        html = res.text
        self.assertIn("zone-onboarding-safety", html)
        self.assertIn("card-canary-preview", html)
        self.assertIn("card-catalog-sync", html)
        self.assertIn("card-rollback", html)
        self.assertIn("Step 1", html)
        self.assertIn("Step 2", html)
        self.assertIn("Step 3", html)

    def test_ui_05_unified_5_layer_cards_and_bilingual_dictionary(self):
        """TC-T1-UI-05: Action cards contain 5-layer hierarchy and embedded bilingual (EN/JA) dictionary."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        html = res.text
        self.assertIn("layer-1-badge", html)
        self.assertIn("layer-2-title", html)
        self.assertIn("layer-3-description", html)
        self.assertIn("layer-4-actions", html)
        self.assertIn("layer-5-preview", html)
        self.assertIn("const I18N =", html)
        self.assertIn("ja: {", html)
        self.assertIn("en: {", html)


class TestTier1SecurityGuards(unittest.TestCase):
    """Tier 1 - Feature 6: Security Perimeter (HMAC, SSRF, Multi-Tenant Isolation, Circuit Breaker)."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_sec_01_valid_hmac_accepted_forged_rejected(self):
        """TC-T1-SEC-01: Valid Webhook HMAC signature accepted; forged signature rejected with 401."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw_body = json.dumps(payload).encode("utf-8")

        # Forged signature
        forged_headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "forged_invalid_signature_==",
        }
        res_forged = self.client.post("/webhooks/products/update", data=raw_body, headers=forged_headers)
        self.assertEqual(res_forged.status_code, 401)
        self.assertEqual(res_forged.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # Valid signature
        valid_headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        res_valid = self.client.post("/webhooks/products/update", data=raw_body, headers=valid_headers)
        self.assertEqual(res_valid.status_code, 200)

    def test_sec_02_ssrf_blocks_private_ips_and_metadata(self):
        """TC-T1-SEC-02: SSRF defense blocks loopback, cloud metadata (169.254.169.254), and private IPs with 400."""
        for bad_ip_url in [
            "http://127.0.0.1:8080/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/internal.png",
            "http://192.168.1.1/secret.jpg",
        ]:
            payload = {"id": 1001, "image": {"src": bad_ip_url}}
            raw = json.dumps(payload).encode("utf-8")
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
            }
            res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
            self.assertEqual(res.status_code, 400, f"SSRF URL {bad_ip_url} was not blocked!")
            self.assertEqual(res.json().get("code"), "INVALID_IMAGE_URL")

    def test_sec_03_path_traversal_shop_domain_blocked(self):
        """TC-T1-SEC-03: Path traversal in shop parameter (../../etc/passwd) rejected with 400 INVALID_SHOP_DOMAIN."""
        res = self.client.get("/api/status?shop=../../etc/passwd")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    def test_sec_04_cross_tenant_snooping_denied(self):
        """TC-T1-SEC-04: Cross-tenant snooping without shop authentication token rejected with 403."""
        res = self.client.get(f"/api/status?shop={OTHER_SHOP}")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED")

    def test_sec_05_circuit_breaker_halts_background_webhooks(self):
        """TC-T1-SEC-05: Emergency Stop (Circuit Breaker) immediately halts incoming webhooks with 423 Locked."""
        # Trip circuit breaker
        abort_res = self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(abort_res.status_code, 200)
        self.assertTrue(abort_res.json().get("circuitBreakerTripped"))

        # Subsequent webhook returns 423
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        wh_res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(wh_res.status_code, 423)
        self.assertEqual(wh_res.json().get("reason"), "circuit_breaker_tripped")


if __name__ == "__main__":
    unittest.main()
