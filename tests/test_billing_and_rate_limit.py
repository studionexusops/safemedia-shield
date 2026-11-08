#!/usr/bin/env python3
"""
tests/test_billing_and_rate_limit.py

Verification Test Suite for:
ADDITIONAL_REQUIREMENTS_BILLING_AND_RATE_LIMIT.md

Covers:
1. 50-Image Trial Cap Enforcement (HTTP 402 TRIAL_CAP_REACHED on 51st image)
2. Webhook Concurrency Limiter (Max 2 Parallel GPU Slots per Shop -> concurrency_limit_exceeded)
3. Early Trial Activation / Immediate Subscription (trialDays: 0 via POST /api/billing/activate-now)
4. Pre-Flight Usage Charge for Active Plan (501st+ image overage & Capped Amount safeguard)
5. Static Contract Verification of types.ts, shopify.ts, index.ts, and ui.ts
"""

import json
import os
import pathlib
import sys
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
    PRIMARY_TOKEN,
    WEBHOOK_SECRET,
    compute_shopify_hmac,
)

WORKER_DIR = os.path.join(REPO_ROOT, "cloudflare_worker")
SRC_INDEX = os.path.join(WORKER_DIR, "src", "index.ts")
SRC_TYPES = os.path.join(WORKER_DIR, "src", "types.ts")
SRC_SHOPIFY = os.path.join(WORKER_DIR, "src", "shopify.ts")
SRC_UI = os.path.join(WORKER_DIR, "src", "ui.ts")


class TestBillingAndRateLimitVerification(unittest.TestCase):
    """Executes the test plan from docs/ADDITIONAL_REQUIREMENTS_BILLING_AND_RATE_LIMIT.md."""

    def setUp(self):
        self.client = TestClient()
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "CANARY_TRIAL",
                "canaryUsedCount": 0,
                "trialUsedCount": 0,
                "monthlyUsageCount": 0,
                "circuitBreakerTripped": False,
            },
        )

    def _send_webhook(self, product_id, image_url, webhook_id=None):
        payload = {
            "id": product_id,
            "title": f"Product {product_id}",
            "image": {"src": image_url},
            "force_reclean": True,
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body_bytes, WEBHOOK_SECRET),
            "Content-Type": "application/json",
        }
        if webhook_id:
            headers["X-Shopify-Webhook-Id"] = webhook_id
        return self.client.post("/webhooks/products/update", data=body_bytes, headers=headers)

    # -------------------------------------------------------------------------
    # Test 1: 50-Image Free Trial Cap Enforcement
    # -------------------------------------------------------------------------
    def test_trial_50_cap_enforcement_on_webhook(self):
        """Test 1: 49 -> 50 succeeds, 51st request blocked with HTTP 402 TRIAL_CAP_REACHED."""
        # Set store into TRIAL_ACTIVE with 49 used images
        res = self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "TRIAL_ACTIVE",
                "trialUsedCount": 49,
                "trialLimit": 50,
            },
        )
        self.assertEqual(res.status_code, 200)

        # 50th image: should succeed
        res_50 = self._send_webhook(
            product_id=1001,
            image_url="https://images.unsplash.com/photo-item-50.jpg",
            webhook_id="wh_trial_item_50",
        )
        self.assertEqual(res_50.status_code, 200)
        data_50 = res_50.json()
        self.assertTrue(data_50.get("success"))
        self.assertEqual(data_50.get("trialUsedCount"), 50)

        # 51st image: must be blocked with HTTP 402 TRIAL_CAP_REACHED
        res_51 = self._send_webhook(
            product_id=1002,
            image_url="https://images.unsplash.com/photo-item-51.jpg",
            webhook_id="wh_trial_item_51",
        )
        self.assertEqual(res_51.status_code, 402)
        data_51 = res_51.json()
        self.assertEqual(data_51.get("code"), "TRIAL_CAP_REACHED")
        self.assertIn("Free trial quota", data_51.get("error", ""))

    # -------------------------------------------------------------------------
    # Test 2: Webhook Concurrency Limiter (Max 2 Parallel GPU Slots)
    # -------------------------------------------------------------------------
    def test_webhook_concurrency_limiter_max_2_slots(self):
        """Test 2: When 2 GPU slots are active, 3rd webhook is gracefully skipped with concurrency_limit_exceeded."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        store.plan_status = "ACTIVE"

        # Occupy both GPU slots 1 and 2
        now = time.time()
        store.active_gpu_slots[1] = now
        store.active_gpu_slots[2] = now

        # Send a 3rd webhook request
        res = self._send_webhook(
            product_id=1003,
            image_url="https://images.unsplash.com/photo-slot-test.jpg",
            webhook_id="wh_concurrency_slot_test",
        )

        # Expect 200 OK with concurrency_limit_exceeded (non-failing for Shopify timeout immunity)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("skipped"))
        self.assertEqual(data.get("reason"), "concurrency_limit_exceeded")
        self.assertIn("Concurrent GPU execution limit (2 slots) reached", data.get("message", ""))

    # -------------------------------------------------------------------------
    # Test 3: Early Trial Activation / Immediate Subscription (trialDays: 0)
    # -------------------------------------------------------------------------
    def test_early_trial_activation_now(self):
        """Test 3: POST /api/billing/activate-now issues subscription with trialDays: 0 and unlocks ACTIVE plan."""
        # Setup store at TRIAL_CAP_REACHED
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "TRIAL_CAP_REACHED",
                "trialUsedCount": 50,
            },
        )

        # Call activate-now
        headers = {"X-Shopify-Access-Token": PRIMARY_TOKEN, "Content-Type": "application/json"}
        res = self.client.post("/api/billing/activate-now", json_data={"shop": PRIMARY_SHOP}, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("confirmationUrl", data)
        self.assertEqual(data.get("billing", {}).get("planStatus"), "ACTIVE")
        self.assertEqual(data.get("billing", {}).get("trialDays"), 0)

        # After approval (ACTIVE), 51st webhook is no longer blocked by trial cap
        res_post = self._send_webhook(
            product_id=1004,
            image_url="https://images.unsplash.com/photo-item-post-upgrade.jpg",
            webhook_id="wh_post_upgrade_item",
        )
        self.assertEqual(res_post.status_code, 200)
        self.assertTrue(res_post.json().get("success"))

    # -------------------------------------------------------------------------
    # Test 4: Pre-Flight Usage Charge for Active Plan (501st+ Image)
    # -------------------------------------------------------------------------
    def test_preflight_usage_charge_and_cap_safeguard(self):
        """Test 4: monthlyUsageCount = 500 triggers overage charge, and capped amount pauses processing."""
        # Setup store at ACTIVE with 500 images used (boundary of included tier)
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "ACTIVE",
                "monthlyUsageCount": 500,
                "monthlyIncludedCount": 500,
            },
        )

        # 501st image: should succeed and increment monthlyUsageCount to 501
        res_501 = self._send_webhook(
            product_id=1005,
            image_url="https://images.unsplash.com/photo-item-501.jpg",
            webhook_id="wh_overage_item_501",
        )
        self.assertEqual(res_501.status_code, 200)
        self.assertEqual(res_501.json().get("monthlyUsageCount"), 501)

        # Simulate Capped Amount ($100) reached
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "ACTIVE",
                "monthlyUsageCount": 1500,
                "simulateCappedAmountExceeded": True,
            },
        )

        # 1501st image: must be blocked with HTTP 402 USAGE_CAP_REACHED
        res_cap = self._send_webhook(
            product_id=1006,
            image_url="https://images.unsplash.com/photo-item-cap.jpg",
            webhook_id="wh_overage_item_cap",
        )
        self.assertEqual(res_cap.status_code, 402)
        self.assertEqual(res_cap.json().get("code"), "USAGE_CAP_REACHED")
        self.assertIn("Monthly usage charge cap", res_cap.json().get("error", ""))

    # -------------------------------------------------------------------------
    # Test 5: Reinstall Trial Abuse Defense (Anti-Infinite Trial Exploit)
    # -------------------------------------------------------------------------
    def test_fresh_install_gets_14_days_trial(self):
        """Brand new store receives standard 14 days free trial."""
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "CANARY_TRIAL",
                "hasEverSubscribed": False,
                "firstInstalledAt": time.time(),
            },
        )
        res = self.client.post("/api/billing/subscribe")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("allowedTrialDays"), 14)
        self.assertEqual(data.get("billing", {}).get("trialDays"), 14)
        self.assertEqual(data.get("billing", {}).get("planStatus"), "TRIAL_14D_ACTIVE")

    def test_reinstall_after_14_days_gets_0_days_trial(self):
        """Store reinstalling after 14+ days from first install gets trialDays: 0 (immediate charge)."""
        fifteen_days_ago = time.time() - (15 * 86400)
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "CANARY_TRIAL",
                "hasEverSubscribed": False,
                "firstInstalledAt": fifteen_days_ago,
            },
        )
        res = self.client.post("/api/billing/subscribe")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("allowedTrialDays"), 0)
        self.assertEqual(data.get("billing", {}).get("trialDays"), 0)
        self.assertEqual(data.get("billing", {}).get("planStatus"), "ACTIVE")

    def test_reinstall_with_prior_subscription_gets_0_days_trial(self):
        """Store with prior paid/subscribed history cannot reset trial, receives trialDays: 0 immediately."""
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "CANARY_TRIAL",
                "hasEverSubscribed": True,
                "firstInstalledAt": time.time() - (2 * 86400),
            },
        )
        res = self.client.post("/api/billing/subscribe")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("allowedTrialDays"), 0)
        self.assertEqual(data.get("billing", {}).get("trialDays"), 0)
        self.assertEqual(data.get("billing", {}).get("planStatus"), "ACTIVE")

    def test_reinstall_mid_trial_gets_remaining_days(self):
        """Store reinstalling during trial period receives only remaining days (e.g. 14 - 5 = 9 days)."""
        five_days_ago = time.time() - (5 * 86400)
        self.client.post(
            "/api/billing/reset",
            json_data={
                "shop": PRIMARY_SHOP,
                "planStatus": "CANARY_TRIAL",
                "hasEverSubscribed": False,
                "firstInstalledAt": five_days_ago,
            },
        )
        res = self.client.post("/api/billing/subscribe")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("allowedTrialDays"), 9)
        self.assertEqual(data.get("billing", {}).get("trialDays"), 9)
        self.assertEqual(data.get("billing", {}).get("planStatus"), "TRIAL_14D_ACTIVE")


class TestStaticCodeContract(unittest.TestCase):
    """Static verification ensuring all architectural contracts from the specification exist."""

    def setUp(self):
        with open(SRC_INDEX, "r", encoding="utf-8") as f:
            self.index_ts = f.read()
        with open(SRC_TYPES, "r", encoding="utf-8") as f:
            self.types_ts = f.read()
        with open(SRC_SHOPIFY, "r", encoding="utf-8") as f:
            self.shopify_ts = f.read()
        with open(SRC_UI, "r", encoding="utf-8") as f:
            self.ui_ts = f.read()

    def test_types_ts_contract(self):
        """Verify TenantBillingState has trialLimit: 50, monthlyIncludedCount: 500, usageLineItemId."""
        self.assertIn("trialUsedCount?: number;", self.types_ts)
        self.assertIn("trialLimit?: number;", self.types_ts)
        self.assertIn("monthlyIncludedCount?: number;", self.types_ts)
        self.assertIn("monthlyUsageCount?: number;", self.types_ts)
        self.assertIn("usageLineItemId?: string;", self.types_ts)
        self.assertIn("GpuSlotLockRecord", self.types_ts)

    def test_shopify_ts_hybrid_billing_and_usage_charge(self):
        """Verify createBillingSubscription supports hybrid pricing details and createAppUsageRecord is defined."""
        self.assertIn("appRecurringPricingDetails", self.shopify_ts)
        self.assertIn("appUsagePricingDetails", self.shopify_ts)
        self.assertIn("createAppUsageRecord", self.shopify_ts)
        self.assertIn("appUsageRecordCreate", self.shopify_ts)
        self.assertIn("$0.05 per cleaned image beyond 500 images/mo (Max $100/mo)", self.shopify_ts)

    def test_index_ts_concurrency_and_activate_now(self):
        """Verify acquireGpuSlot, releaseGpuSlot, POST /api/billing/activate-now, and TRIAL_CAP_REACHED."""
        self.assertIn("async function acquireGpuSlot(", self.index_ts)
        self.assertIn("async function releaseGpuSlot(", self.index_ts)
        self.assertIn('reason: "concurrency_limit_exceeded"', self.index_ts)
        self.assertIn('code: "TRIAL_CAP_REACHED"', self.index_ts)
        self.assertIn('url.pathname === "/api/billing/activate-now"', self.index_ts)

    def test_ui_ts_trial_cap_modal(self):
        """Verify ui.ts has trial-cap-modal, executeActivateNow, and 50/50 completed messaging."""
        self.assertIn('id="trial-cap-modal"', self.ui_ts)
        self.assertIn("Free Trial Quota (50/50 Images) Completed!", self.ui_ts)
        self.assertIn("executeActivateNow", self.ui_ts)
        self.assertIn("Activate Full Plan Now ($65/mo)", self.ui_ts)

    def test_reinstall_trial_defense_contract(self):
        """Verify Anti-Trial-Abuse contracts in types.ts and index.ts."""
        self.assertIn("firstInstalledAt?: string;", self.types_ts)
        self.assertIn("hasEverSubscribed?: boolean;", self.types_ts)
        self.assertIn("calculateAllowedTrialDays", self.index_ts)
        self.assertIn("bState.hasEverSubscribed = true;", self.index_ts)

    def test_canary_does_not_consume_trial_or_monthly_quota_in_14d_trial(self):
        """Verify Canary test in 14-day trial does not consume 50-item trial quota, but respects 5-sample safety cap."""
        from tests.e2e.mock_worker_harness import PRIMARY_SHOP, TestClient
        client = TestClient()
        client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0, "trialUsedCount": 0})
        
        # Run 1st Canary test
        res1 = client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res1.status_code, 200)
        
        status_res = client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        billing = status_res["billing"]
        self.assertEqual(billing["trialUsedCount"], 0, "Trial 50-item quota must NOT be consumed by Canary test")
        self.assertEqual(billing["monthlyUsageCount"], 0, "Monthly 500-item quota must NOT be consumed by Canary test")
        self.assertEqual(billing["canaryUsedCount"], 1, "Canary used count must increment for safety limit")

        # Run up to 5 samples
        for _ in range(4):
            r = client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
            self.assertEqual(r.status_code, 200)

        # 6th Canary test in 14-day trial must be blocked with 402 for GPU Abuse defense
        res6 = client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res6.status_code, 402)
        self.assertEqual(res6.json().get("code"), "TRIAL_QUOTA_EXCEEDED")

    def test_ui_ts_quota_not_consumed_messaging(self):
        """Verify ui.ts has explicit notes stating neither trial quota nor monthly included quota is consumed."""
        self.assertIn("step1_quota_note", self.ui_ts)
        self.assertIn("※ 本テストは安全確認用のプレビューであり、プランの画像処理枠（トライアル50枚枠 / 月間内包500枚枠）は消費されません。", self.ui_ts)
        self.assertIn("※ This sample test is a safety verification preview and does not consume your plan image quota (50 Trial / 500 Monthly Included Quota).", self.ui_ts)
        self.assertIn("step1_success_banner", self.ui_ts)
        self.assertIn("プレビュー検証完了（※プランの画像処理枠は消費されていません）", self.ui_ts)
        self.assertIn("Preview Verified (※ Plan image quota has not been consumed)", self.ui_ts)

    def test_ui_ts_canary_quota_exceeded_guides_to_trial(self):
        """Verify ui.ts recognizes TRIAL_QUOTA_EXCEEDED and guides merchants to start 14-day trial instead of retry."""
        self.assertIn("dataCode === 'TRIAL_QUOTA_EXCEEDED'", self.ui_ts)
        self.assertIn("startFreeTrial()", self.ui_ts)
        self.assertIn("step1_btn_trial", self.ui_ts)
        self.assertIn("step1_err_limit_reached", self.ui_ts)


if __name__ == "__main__":
    unittest.main()
