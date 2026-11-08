"""
test_tier4_real_world_lifecycle.py
Tier 4: Real-World Application Scenarios (Complete Merchant Lifecycle).

Merchant Lifecycle Journey:
1. App Installation & Dashboard Discovery (2-Zone layout, Zone 1 active, Zone 2 onboarding)
2. 1-Product Canary Trial with Sale Badge Removal Verification (Before vs After, variants intact, quota 1/5)
3. 14-Day Free Trial ($65/mo) Activation & Full Catalog Batch Sync (R2 snapshot + clean ad metafields)
4. Storefront Media & Variant Preservation Invariant Verification (Storefront images 100% untouched)
5. Zero-UI Auto-Sync on New Product Upload (Webhook reception -> AI cleanup -> Metafield update)
6. 1-Click Rollback Safety Net Verification (Complete restore to pre-batch snapshot in <10s)
7. Full End-to-End Sequential Journey Execution
Total: 7 comprehensive test cases
"""

import copy
import json
import pathlib
import sys
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
    compute_shopify_hmac,
)


class TestTier4RealWorldLifecycle(unittest.TestCase):
    """Tier 4: End-to-End Merchant Lifecycle Real-World Journey."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_lifecycle_stage1_app_installation_and_dashboard_discovery(self):
        """TC-T4-01: Phase 1: Merchant installs app and accesses dashboard with 2-Zone layout."""
        res = self.client.get(f"/?shop={PRIMARY_SHOP}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify new branding
        self.assertIn("AdFeed Clean for Google Shopping", html)
        self.assertNotIn("SafeMedia Shield", html)
        self.assertNotIn("🔄 Refresh", html)

        # Verify Zone 1 (Core Automation / Always-On Ad Shield)
        self.assertIn("zone-core-automation", html)
        self.assertIn("🟢 Active", html)
        self.assertIn("toggle_auto_sync", html)
        self.assertIn("synced_feed_table", html)

        # Verify Zone 2 (Onboarding & Safety Suite)
        self.assertIn("zone-onboarding-safety", html)
        self.assertIn("card-canary-preview", html)
        self.assertIn("card-catalog-sync", html)
        self.assertIn("card-rollback", html)

        # Verify initial quota state
        status = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status["billing"]["planStatus"], "CANARY_TRIAL")
        self.assertEqual(status["billing"]["canaryUsedCount"], 0)
        self.assertEqual(status["billing"]["canaryLimit"], 5)

    def test_lifecycle_stage2_canary_trial_with_promo_badge_removal(self):
        """TC-T4-02: Phase 2: Merchant tests on 1 sample product; verifies sale badge removal and variant safety."""
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 200)
        data = canary_res.json()

        # Before (Storefront) vs After (Clean Ad Image)
        self.assertIn("originalImageUrl", data)
        self.assertIn("cleanAdImageUrl", data)
        self.assertNotEqual(data["originalImageUrl"], data["cleanAdImageUrl"])

        # Metafield contract
        self.assertEqual(data["metafieldKey"], "safemedia.clean_ad_image_url")

        # AI metadata
        self.assertIn("Florence", data["aiMetadata"]["engine"])
        self.assertGreater(data["aiMetadata"]["maskCoveragePct"], 0)
        self.assertGreater(data["aiMetadata"]["processingSec"], 0)

        # Variant preservation
        for vc in data["variantChecks"]:
            self.assertTrue(vc["preserved"])
            self.assertTrue(vc["hasOriginalMedia"])

        # Quota updated to 1/5
        self.assertEqual(data["canaryUsedCount"], 1)

    def test_lifecycle_stage3_trial_activation_and_full_catalog_batch_sync(self):
        """TC-T4-03: Phase 3: Merchant activates 14-day free trial ($65/mo) and initiates full catalog batch sync."""
        # 1. Activate trial
        sub_res = self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(sub_res.status_code, 200)
        self.assertEqual(sub_res.json()["billing"]["planStatus"], "TRIAL_14D_ACTIVE")
        self.assertEqual(sub_res.json()["billing"]["priceUsd"], 65)

        # 2. Run full catalog batch sync
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)
        batch_data = batch_res.json()
        self.assertTrue(batch_data["success"])
        self.assertIn("snapshotId", batch_data)
        self.assertGreater(batch_data["totalProducts"], 0)

        # Verify job completed
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["jobState"]["status"], "COMPLETED")
        self.assertEqual(status_res["jobState"]["processed"], batch_data["totalProducts"])

    def test_lifecycle_stage4_storefront_protection_and_dual_feed_verification(self):
        """TC-T4-04: Phase 4: Critical Invariant: Storefront images remain 100% untouched while ad metafields populate."""
        # Record baseline storefront images before batch
        store = self.client.app.get_store(PRIMARY_SHOP)
        orig_storefront_images = [copy.deepcopy(p["media"]) for p in store.catalog]
        orig_variants = [copy.deepcopy(p["variants"]) for p in store.catalog]

        # Activate trial and batch sync
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})

        # Verify storefront media and variants are 100% IDENTICAL
        for i, prod in enumerate(store.catalog):
            self.assertEqual(prod["media"], orig_storefront_images[i], "Storefront media was modified by batch!")
            self.assertEqual(prod["variants"], orig_variants[i], "Storefront variants were modified by batch!")

            # Verify clean ad metafield is populated
            self.assertIn("safemedia.clean_ad_image_url", prod["metafields"])
            self.assertTrue(prod["metafields"]["safemedia.clean_ad_image_url"].startswith("https://cdn.safemedia.io/clean/"))

    def test_lifecycle_stage5_zero_ui_auto_sync_on_new_product_upload(self):
        """TC-T4-05: Phase 5: Normal operations: merchant uploads decorated product; webhook triggers zero-UI sync."""
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})

        # Shopify sends products/update webhook for newly uploaded item
        payload = {
            "id": 1002,
            "title": "オーガニック フレンチテリー ジップアップフーディー",
            "image": {"src": "https://cdn.shopify.com/orig/grey_limited_badge.jpg"},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }

        webhook_res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(webhook_res.status_code, 200)
        wh_data = webhook_res.json()
        self.assertTrue(wh_data["success"])
        self.assertFalse(wh_data["skipped"])
        self.assertIn("cleanAdImageUrl", wh_data)

        # Confirm storefront image remains decorated
        self.assertEqual(wh_data["storefrontImageUrl"], "https://cdn.shopify.com/orig/grey_limited_badge.jpg")

    def test_lifecycle_stage6_one_click_rollback_time_machine_safety_net(self):
        """TC-T4-06: Phase 6: Safety net: 1-Click Rollback restores pre-batch snapshot baseline in <10 seconds."""
        # 1. Take snapshot before batch
        store = self.client.app.get_store(PRIMARY_SHOP)
        snap_id = store.create_snapshot()

        # 2. Run batch sync (populates clean ad metafields)
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertIsNotNone(store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"))

        # 3. Trigger 1-Click Rollback
        t0 = time.time()
        rollback_res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        duration = time.time() - t0

        self.assertEqual(rollback_res.status_code, 200)
        self.assertTrue(rollback_res.json().get("success"))
        self.assertTrue(rollback_res.json().get("metafieldsRestored"))
        self.assertLess(duration, 10.0, "Rollback exceeded 10-second SLA limit")

        # 4. Confirm clean ad metafields reverted to clean snapshot baseline
        self.assertIsNone(store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"))

    def test_lifecycle_full_end_to_end_journey(self):
        """TC-T4-07: Complete end-to-end multi-step merchant journey executed seamlessly."""
        # Step 1: Install & Discover Dashboard
        dash = self.client.get(f"/?shop={PRIMARY_SHOP}")
        self.assertEqual(dash.status_code, 200)
        self.assertIn("AdFeed Clean for Google Shopping", dash.text)

        # Step 2: Canary Preview (1 sample product)
        canary = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary.status_code, 200)
        self.assertEqual(canary.json()["canaryUsedCount"], 1)

        # Step 3: Activate 14-Day Free Trial ($65/mo)
        sub = self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(sub.status_code, 200)
        self.assertEqual(sub.json()["billing"]["planStatus"], "TRIAL_14D_ACTIVE")

        # Step 4: Full Catalog Batch Sync
        batch = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch.status_code, 200)
        snap_id = batch.json()["snapshotId"]

        # Step 5: Zero-UI Webhook Auto-Sync on new product
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/black_promo_sale.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        wh = self.client.post(
            "/webhooks/products/update",
            data=raw,
            headers={
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
            },
        )
        self.assertEqual(wh.status_code, 200)

        # Step 6: 1-Click Rollback Restores Baseline
        rollback = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(rollback.status_code, 200)
        self.assertTrue(rollback.json()["metafieldsRestored"])


import copy

if __name__ == "__main__":
    unittest.main()
