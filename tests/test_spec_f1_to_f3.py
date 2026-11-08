#!/usr/bin/env python3
"""
tests/test_spec_f1_to_f3.py
Automated Verification Suite for TEST_SPEC_SHOPIFY_INTEGRATION.md (F-1 to F-3)

Verifies:
  - [F-1] Auto-Protection Toggle & R2 State / Webhook Subscription Sync
  - [F-2] Auto-Protection Paused (OFF) Safe Skip Defense
  - [F-3] Auto-Protection Active (ON) Zero-UI Automated Cleanup & Infinite Loop Prevention
"""

import json
import unittest
from tests.e2e.mock_worker_harness import (
    MockWorkerApp,
    TestClient,
    PRIMARY_SHOP,
    compute_shopify_hmac,
)


class TestShopifyIntegrationF1ToF3(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()
        # Ensure shop is in TRIAL_14D_ACTIVE with clean state
        self.client.post("/api/billing/reset", json_data={
            "shop": PRIMARY_SHOP,
            "planStatus": "TRIAL_14D_ACTIVE",
            "trialUsedCount": 0,
            "trialLimit": 50,
            "circuitBreakerTripped": False,
            "autoSyncEnabled": True,
        })

    # =========================================================================
    # [F-1] Auto-Protection Toggle & R2 State / Webhook Sync
    # =========================================================================
    def test_f1_toggle_sync_state_and_webhook_registration(self):
        """
        [F-1] Verify toggle endpoint (/api/auto-sync/toggle) and webhook register/unregister
        accurately update tenant billing state and return matching flags.
        """
        # 1. Check initial state (should be True)
        status = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertTrue(status["billing"]["autoSyncEnabled"], "Initial state should be enabled")

        # 2. Toggle to OFF
        toggle_res_1 = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(toggle_res_1.status_code, 200)
        self.assertFalse(toggle_res_1.json()["autoSyncEnabled"], "State after 1st toggle should be False")

        # Verify state endpoint reflects OFF
        status_off = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertFalse(status_off["billing"]["autoSyncEnabled"], "R2 billing state must be false")

        # 3. Toggle back to ON
        toggle_res_2 = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(toggle_res_2.status_code, 200)
        self.assertTrue(toggle_res_2.json()["autoSyncEnabled"], "State after 2nd toggle should be True")

        # Verify state endpoint reflects ON
        status_on = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertTrue(status_on["billing"]["autoSyncEnabled"], "R2 billing state must be true")

        # 4. Explicit unregister API test
        unreg = self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(unreg.status_code, 200)
        self.assertFalse(unreg.json()["autoSyncEnabled"])

        # 5. Explicit register API test
        reg = self.client.post("/api/webhooks/register", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(reg.status_code, 200)
        self.assertTrue(reg.json()["autoSyncEnabled"])
        self.assertIn("webhookId", reg.json())
        print("  [PASS] F-1: Auto-Protection toggle & webhook state sync verified")

    def test_f1_canary_trial_auto_sync_toggle_blocked(self):
        """
        [F-1b] Verify that unsubscribed CANARY_TRIAL merchants cannot toggle Zone 1 auto-protection
        and receive HTTP 402 SUBSCRIPTION_REQUIRED_FOR_AUTOSYNC requiring trial activation.
        """
        # Set store to CANARY_TRIAL
        self.client.post("/api/billing/reset", json_data={
            "shop": PRIMARY_SHOP,
            "planStatus": "CANARY_TRIAL",
        })

        # Attempt toggle
        res = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 402)
        data = res.json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "SUBSCRIPTION_REQUIRED_FOR_AUTOSYNC")
        self.assertIn("14-day free trial", data.get("error"))
        print("  [PASS] F-1b: CANARY_TRIAL auto-sync toggle blocked with HTTP 402 trial gate")

    # =========================================================================
    # [F-2] Auto-Protection Paused (OFF) Safe Skip
    # =========================================================================
    def test_f2_webhook_safely_skipped_when_auto_sync_disabled(self):
        """
        [F-2] Verify that when autoSyncEnabled is False, incoming Shopify product
        update webhooks are immediately acknowledged with HTTP 200 skipped
        without invoking GPU inference or modifying product metafields.
        """
        # Set autoSyncEnabled to False
        self.client.post("/api/webhooks/unregister", json_data={"shop": PRIMARY_SHOP})

        # Send valid HMAC Shopify product update webhook for product 1002
        payload = {
            "id": 1002,
            "title": "Minimalist Pure Snowboard (Control Test)",
            "image": {"src": "https://cdn.shopify.com/orig/minimalist_pure_promo.jpg"},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
            "X-Shopify-Webhook-Id": "wh_test_f2_pause_skip_001",
        }

        res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"), "Response should indicate success: true")
        self.assertTrue(data.get("skipped"), "Response must indicate skipped: true")
        self.assertEqual(data.get("reason"), "auto_sync_disabled", "Skip reason must be auto_sync_disabled")

        # Verify that trial quota was NOT consumed
        status = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status["billing"]["trialUsedCount"], 0, "GPU quota must not be consumed when paused")
        print("  [PASS] F-2: Webhook safely skipped with auto_sync_disabled, 0 GPU cost incurred")

    # =========================================================================
    # [F-3] Auto-Protection Active (ON) Zero-UI Cleanup & Infinite Loop Prevention
    # =========================================================================
    def test_f3_zero_ui_automated_cleanup_and_loop_prevention(self):
        """
        [F-3] Verify that when autoSyncEnabled is True:
        1. Webhook automatically cleans the image and writes to hidden metafield.
        2. Storefront image remains intact (non-destructive).
        3. Trial used count is properly incremented.
        4. Re-delivered webhook with identical image URL is skipped (already_cleaned_for_current_image)
           preventing infinite webhook feedback loops.
        """
        # Ensure autoSyncEnabled is True
        self.client.post("/api/webhooks/register", json_data={"shop": PRIMARY_SHOP})

        # Target product 1001 (The Complete Snowboard)
        promo_url = "https://cdn.shopify.com/orig/the_complete_snowboard_sale_banner.jpg"
        payload = {
            "id": 1001,
            "title": "The Complete Snowboard (Canary Test)",
            "image": {"src": promo_url},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
            "X-Shopify-Webhook-Id": "wh_test_f3_first_execution_001",
        }

        # Step 1: Fire webhook (simulating Shopify product save)
        res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"), "Webhook processing should succeed")
        self.assertFalse(data.get("skipped"), "Webhook processing should not be skipped")
        self.assertIn("cleanAdImageUrl", data, "Clean ad image URL must be generated")
        self.assertEqual(data.get("storefrontImageUrl"), promo_url, "Storefront image must remain unchanged")
        self.assertEqual(data.get("metafieldKey"), "clean_ad_image_url")

        # Step 2: Check status API & feed table data
        status = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status["billing"]["trialUsedCount"], 1, "Trial quota should increment to 1")

        # Find the product in dualFeedProducts
        feed_prod = next((p for p in status["dualFeedProducts"] if p["productId"] == 1001 or p["productId"] == "gid://shopify/Product/1001"), None)
        self.assertIsNotNone(feed_prod, "Product must exist in dualFeedProducts")
        self.assertIsNotNone(feed_prod.get("cleanAdImageUrl"), "Clean ad image URL must be registered in feed")

        # Step 3: Self-Webhook / Loop Prevention Check
        # When Shopify updates the product metafield, it fires another products/update webhook with the same image.
        # This second webhook must be skipped with already_cleaned_for_current_image.
        headers_secondary = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
            "X-Shopify-Webhook-Id": "wh_test_f3_shopify_echo_002",
        }
        res_loop = self.client.post("/webhooks/products/update", data=raw_body, headers=headers_secondary)
        self.assertEqual(res_loop.status_code, 200)
        data_loop = res_loop.json()
        self.assertTrue(data_loop.get("success"))
        self.assertTrue(data_loop.get("skipped"), "Secondary echo webhook MUST be skipped")
        self.assertEqual(data_loop.get("reason"), "already_cleaned_for_current_image", "Infinite loop guard must catch repeat webhook")

        # Verify trial quota was NOT double-counted
        status_after = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_after["billing"]["trialUsedCount"], 1, "Quota must remain 1 (no double charging)")
        print("  [PASS] F-3: Zero-UI cleanup, Storefront protection & infinite loop guard verified")

    def test_f3_runpod_callback_separation_and_multi_image_contract(self):
        """
        [F-3b] Verify Option B (RunPod Webhook Callback Separation + Parallelized I/O + Multi-Image Detection):
        1. /webhooks/runpod/callback endpoint is present with HMAC-SHA256 signature verification (verifyRunPodCallbackSig)
           and atomic completion deduplication (claimWebhookCompletion).
        2. RunPodClient passes `webhook: params.callbackUrl` in the /run request and supports deferredToCallback
           before Cloudflare's 30s ctx.waitUntil wall-clock limit.
        3. ShopifyVariantManager.setCleanAdImageMetafield executes ensureCleanAdMetafieldDefinition and metafieldsSet in parallel.
        4. UI renders Storefront image using p.storefrontImageUrl first so newly uploaded product images appear immediately.
        """
        from pathlib import Path
        root_dir = Path(__file__).resolve().parent.parent
        index_ts = (root_dir / "cloudflare_worker" / "src" / "index.ts").read_text(encoding="utf-8")
        runpod_ts = (root_dir / "cloudflare_worker" / "src" / "runpod_client.ts").read_text(encoding="utf-8")
        shopify_ts = (root_dir / "cloudflare_worker" / "src" / "shopify.ts").read_text(encoding="utf-8")
        ui_ts = (root_dir / "cloudflare_worker" / "src" / "ui.ts").read_text(encoding="utf-8")

        self.assertIn('"/webhooks/runpod/callback"', index_ts)
        self.assertIn("verifyRunPodCallbackSig", index_ts)
        self.assertIn("claimWebhookCompletion", index_ts)
        self.assertIn("latestWebhookImg", index_ts)
        self.assertIn("webhook: params.callbackUrl", runpod_ts)
        self.assertIn("deferredToCallback: true", runpod_ts)
        self.assertIn("this.ensureCleanAdMetafieldDefinition().catch(() => {})", shopify_ts)
        self.assertIn("p.storefrontImageUrl || p.dualFeedMetadata?.sourceImageUrl", ui_ts)
        print("  [PASS] F-3b: RunPod Webhook Callback separation & parallelized I/O contract verified")


if __name__ == "__main__":
    unittest.main()
