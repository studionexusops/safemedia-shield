"""
test_tier3_combinations.py
Tier 3: Cross-Feature Combinations & Pairwise Interactions E2E Tests.

Pairwise Scenarios:
1. Canary test when Auto-Sync is disabled
2. Batch start when Canary limit (5/5) is reached
3. 1-Click Rollback after full catalog Batch completed
4. Webhook update during active processing (In-flight concurrency lock)
5. Circuit Breaker abort during auto-sync webhook reception
6. Multi-tenant concurrency & state isolation (Store A unaffected by Store B actions)
Total: 6 comprehensive test cases
"""

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
    OTHER_SHOP,
    PRIMARY_TOKEN,
    compute_shopify_hmac,
)


class TestTier3Combinations(unittest.TestCase):
    """Tier 3: Pairwise Interaction & Cross-Feature State Testing."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_pair_01_canary_test_when_auto_sync_disabled(self):
        """TC-T3-PAIR-01: Canary preview test functions independently when Auto-Sync webhook is disabled."""
        # 1. Disable Auto-Sync
        unreg = self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(unreg.status_code, 200)
        self.assertFalse(unreg.json().get("autoSyncEnabled"))

        # 2. Run Canary test -> must succeed
        canary = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary.status_code, 200)
        self.assertIn("cleanAdImageUrl", canary.json())
        self.assertIn("originalImageUrl", canary.json())

        # 3. Webhook remains skipped
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
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
        self.assertTrue(wh.json().get("skipped"))

    def test_pair_02_batch_start_when_canary_limit_reached(self):
        """TC-T3-PAIR-02: Reaching 5/5 canary limit gates batch; activating 14-day trial unlocks full catalog batch."""
        # 1. Max out canary quota to 5/5
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})

        # 2. Attempt batch start while unsubscribed -> blocked with 402
        batch_blocked = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_blocked.status_code, 402)
        self.assertEqual(batch_blocked.json().get("code"), "SUBSCRIPTION_REQUIRED_FOR_BULK")

        # 3. Merchant activates 14-day free trial ($65/mo)
        sub = self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(sub.status_code, 200)

        # 4. Batch start now succeeds with pre-execution snapshot
        batch_allowed = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_allowed.status_code, 200)
        self.assertTrue(batch_allowed.json().get("success"))
        self.assertIn("snapshotId", batch_allowed.json())

    def test_pair_03_rollback_after_batch_completed(self):
        """TC-T3-PAIR-03: 1-Click Rollback after catalog batch successfully reverts metafields and restores store baseline."""
        # 1. Activate trial and start from clean catalog
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE"})
        store = self.client.app.get_store(PRIMARY_SHOP)

        # Verify no clean ad metafields initially
        self.assertIsNone(store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"))

        # 2. Run batch sync
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)
        snap_id = batch_res.json()["snapshotId"]

        # Verify clean ad metafields now exist
        self.assertIsNotNone(store.catalog[0]["metafields"]["safemedia.clean_ad_image_url"])

        # 3. Execute 1-Click Rollback
        rollback_res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(rollback_res.status_code, 200)
        self.assertTrue(rollback_res.json().get("metafieldsRestored"))

        # 4. Verify metafields reverted to clean baseline
        self.assertIsNone(store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"))

    def test_pair_04_webhook_in_flight_lock_prevents_duplicate_processing(self):
        """TC-T3-PAIR-04: In-flight concurrency lock prevents duplicate GPU charges for identical product in-flight."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        store.reset(plan_status="TRIAL_14D_ACTIVE")

        # Simulate lock currently held for product 1001
        store.in_flight_locks[f"{PRIMARY_SHOP}:gid://shopify/Product/1001"] = time.time()

        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/promo1.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("skipped"))
        self.assertEqual(res.json().get("reason"), "already_processing_in_flight")

    def test_pair_05_circuit_breaker_abort_during_auto_sync(self):
        """TC-T3-PAIR-05: Emergency Stop instantly halts ongoing auto-sync processing and resumes cleanly."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE"})

        # Trip Emergency Stop
        abort_res = self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(abort_res.status_code, 200)

        # Incoming webhook while Emergency Stop is active -> rejected with 423 (even if auto_sync was disabled)
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/promo2.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res_blocked = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res_blocked.status_code, 423)
        self.assertEqual(res_blocked.json().get("reason"), "circuit_breaker_tripped")

        # Resume protection
        resume_res = self.client.post("/api/batch/resume", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(resume_res.status_code, 200)

        # Incoming webhook now processes
        res_ok = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res_ok.status_code, 200)
        self.assertFalse(res_ok.json().get("skipped"))

    def test_pair_06_multi_tenant_state_isolation_concurrent(self):
        """TC-T3-PAIR-06: Store B actions (Emergency Stop) do not leak or affect Store A (100% tenant isolation)."""
        # Store A active
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE"})

        # Store B aborts with its own token
        b_abort = self.client.post(
            "/api/batch/abort",
            json_data={"shop": OTHER_SHOP},
            headers={"X-Shopify-Access-Token": "store_b_secret_token"},
        )
        self.assertEqual(b_abort.status_code, 200)

        # Store A status remains completely unaffected
        status_a = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertTrue(status_a["protectionActive"], "Store A protection was corrupted by Store B abort!")
        self.assertFalse(status_a["billing"]["circuitBreakerTripped"])

        # Store A full catalog sync succeeds
        batch_a = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_a.status_code, 200)
        self.assertTrue(batch_a.json().get("success"))


if __name__ == "__main__":
    unittest.main()
