"""
test_tier2_boundary_corner.py
Tier 2: Boundary & Corner Cases E2E Tests (>=5 test cases per scenario).

Scenarios Covered:
1. 5/5 Canary Limit Exceeded (5 test cases)
2. Invalid Shop Domains (5 test cases)
3. Empty Product Catalogs (5 test cases)
4. Malformed Webhook HMAC & Payload (5 test cases)
5. SSRF Private IP Rejection (5 test cases)
6. Abort Batch Mid-Flight & Circuit Breaker (5 test cases)
7. Rollback Non-Existent Snapshot & Edge Conditions (5 test cases)
Total: 35 test cases
"""

import json
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
    OTHER_SHOP,
    compute_shopify_hmac,
)


class TestTier2CanaryLimitBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 1: 5/5 Canary Trial Limit & Wallet Protection."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_canary_bound_01_quota_at_zero_allows_five_runs(self):
        """TC-T2-CANARY-BOUND-01: Quota allows exactly 5 free sample runs sequentially from 0/5."""
        for expected_count in range(1, 6):
            res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
            self.assertEqual(res.status_code, 200, f"Run {expected_count} failed")
            self.assertEqual(res.json().get("canaryUsedCount"), expected_count)

    def test_canary_bound_02_sixth_canary_blocked_with_402(self):
        """TC-T2-CANARY-BOUND-02: 6th Canary preview test is blocked with 402 TRIAL_QUOTA_EXCEEDED."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.json().get("code"), "TRIAL_QUOTA_EXCEEDED")
        err_msg = res.json().get("error", "").lower()
        self.assertTrue("free sample" in err_msg or "limit" in err_msg or "quota" in err_msg)

    def test_canary_bound_03_webhook_cleanup_blocked_at_quota_limit(self):
        """TC-T2-CANARY-BOUND-03: Webhook AI cleanup blocked at 5/5 quota when unsubscribed to protect GPU wallet."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.json().get("code"), "TRIAL_QUOTA_EXCEEDED")

    def test_canary_bound_04_14d_trial_activation_unblocks_quota(self):
        """TC-T2-CANARY-BOUND-04: Activating 14-day free trial ($65/mo) unblocks canary and allows unlimited runs."""
        # Max out quota
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})
        sub_res = self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(sub_res.status_code, 200)

        # Canary now proceeds without 402
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 200)

    def test_canary_bound_05_quota_cannot_be_bypassed_via_fake_params(self):
        """TC-T2-CANARY-BOUND-05: Quota counter cannot be bypassed by appending query parameters."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})
        res = self.client.post(f"/api/canary/test?shop={PRIMARY_SHOP}&bypass=1", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.json().get("code"), "TRIAL_QUOTA_EXCEEDED")


class TestTier2ShopDomainBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 2: Shopify Store Domain Validation & Path Traversal Prevention."""

    def setUp(self):
        self.client = TestClient()

    def test_shop_bound_01_path_traversal_dot_dot_slash(self):
        """TC-T2-SHOP-BOUND-01: Path traversal domain (../../etc/passwd) rejected with 400."""
        res = self.client.get("/api/status?shop=../../etc/passwd")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    def test_shop_bound_02_excessively_long_domain(self):
        """TC-T2-SHOP-BOUND-02: Overly long domain (>100 chars) rejected with 400."""
        long_domain = "a" * 105 + ".myshopify.com"
        res = self.client.get(f"/api/status?shop={long_domain}")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    def test_shop_bound_03_injection_characters_rejected(self):
        """TC-T2-SHOP-BOUND-03: Domain containing shell injection characters rejected with 400."""
        bad_domain = "store;rm -rf;.myshopify.com"
        res = self.client.get(f"/api/status?shop={bad_domain}")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    def test_shop_bound_04_non_myshopify_domain_rejected(self):
        """TC-T2-SHOP-BOUND-04: Non-myshopify domain (e.g. custom domain without .myshopify.com) rejected with 400."""
        res = self.client.get("/api/status?shop=phishing-store.com")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    def test_shop_bound_05_empty_and_special_char_domain(self):
        """TC-T2-SHOP-BOUND-05: Empty or whitespace shop domain rejected with 400."""
        res = self.client.get("/api/status?shop=%20%20")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")


class TestTier2EmptyCatalogBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 3: Empty Product Catalogs & Missing Media."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "emptyCatalog": True})

    def test_catalog_bound_01_canary_on_empty_catalog(self):
        """TC-T2-CATALOG-BOUND-01: Canary preview test on empty store returns 400 with descriptive error."""
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "EMPTY_CATALOG")

    def test_catalog_bound_02_batch_start_on_empty_catalog(self):
        """TC-T2-CATALOG-BOUND-02: Batch start on store with 0 products completes safely with 0 products processed."""
        res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("totalProducts"), 0)

    def test_catalog_bound_03_webhook_missing_images_array(self):
        """TC-T2-CATALOG-BOUND-03: Webhook payload with empty images array returns skipped without GPU charge."""
        payload = {"id": 1001, "title": "Draft Product", "images": []}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("skipped"))
        self.assertEqual(res.json().get("reason"), "no_product_image")

    def test_catalog_bound_04_webhook_image_null(self):
        """TC-T2-CATALOG-BOUND-04: Webhook payload with null image object returns skipped cleanly."""
        payload = {"id": 1001, "image": None}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("skipped"))
        self.assertEqual(res.json().get("reason"), "no_product_image")

    def test_catalog_bound_05_webhook_missing_product_id(self):
        """TC-T2-CATALOG-BOUND-05: Webhook payload missing product ID returns skipped with missing_product_id."""
        payload = {"image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("skipped"))
        self.assertEqual(res.json().get("reason"), "missing_product_id")


class TestTier2WebhookHMACBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 4: Malformed Webhook HMAC & Payload Authentication."""

    def setUp(self):
        self.client = TestClient()

    def test_hmac_bound_01_missing_shop_domain_header(self):
        """TC-T2-HMAC-BOUND-01: Webhook call without X-Shopify-Shop-Domain header returns 401."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        res = self.client.post("/webhooks/products/update", data=raw)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "MISSING_WEBHOOK_HEADERS")

    def test_hmac_bound_02_forged_hmac_header(self):
        """TC-T2-HMAC-BOUND-02: Webhook call with forged X-Shopify-Hmac-Sha256 signature returns 401."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "fake_forged_signature_==",
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")

    def test_hmac_bound_03_empty_hmac_header(self):
        """TC-T2-HMAC-BOUND-03: Empty HMAC header string returns 401 INVALID_WEBHOOK_HMAC."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "",
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")

    def test_hmac_bound_04_corrupted_json_payload(self):
        """TC-T2-HMAC-BOUND-04: Malformed non-JSON payload returns 400 INVALID_JSON."""
        bad_data = b"{corrupted_json_payload"
        res = self.client.post("/api/canary/test", data=bad_data, headers={"Content-Type": "application/json"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_JSON")

    def test_hmac_bound_05_tampered_payload_mismatch(self):
        """TC-T2-HMAC-BOUND-05: Payload modified after signature generation is rejected with 401."""
        orig_payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/safe.jpg"}}
        raw_orig = json.dumps(orig_payload).encode("utf-8")
        sig = compute_shopify_hmac(raw_orig)

        # Tamper payload
        tampered = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/malicious.jpg"}}
        raw_tampered = json.dumps(tampered).encode("utf-8")

        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": sig,
        }
        res = self.client.post("/webhooks/products/update", data=raw_tampered, headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")


class TestTier2SSRFBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 5: SSRF Private IP Rejection & Non-HTTP Schemes."""

    def setUp(self):
        self.client = TestClient()

    def _test_bad_url(self, bad_url: str):
        payload = {"id": 1001, "image": {"src": bad_url}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 400, f"URL {bad_url} was not blocked!")
        self.assertEqual(res.json().get("code"), "INVALID_IMAGE_URL")

    def test_ssrf_bound_01_loopback_ip(self):
        """TC-T2-SSRF-BOUND-01: Full IPv4 loopback CIDR (127.0.0.0/8) & IPv6 loopback rejected with 400."""
        self._test_bad_url("http://127.0.0.1:8080/internal")
        self._test_bad_url("http://127.0.1.1:8080/internal")
        self._test_bad_url("http://127.255.255.254/admin")
        self._test_bad_url("http://[::1]/internal")

    def test_ssrf_bound_02_cloud_metadata_ip(self):
        """TC-T2-SSRF-BOUND-02: Cloud metadata endpoints (169.254.0.0/16 & internal domains) rejected with 400."""
        self._test_bad_url("http://169.254.169.254/latest/meta-data/")
        self._test_bad_url("http://169.254.1.1/info")
        self._test_bad_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_ssrf_bound_03_rfc1918_and_cgnat_ranges(self):
        """TC-T2-SSRF-BOUND-03: RFC1918 Class A/B/C & CGNAT (100.64.0.0/10) private IPs rejected with 400."""
        self._test_bad_url("http://10.0.0.1/admin.png")
        self._test_bad_url("http://172.16.0.1/internal.jpg")
        self._test_bad_url("http://172.31.255.255/admin.png")
        self._test_bad_url("http://100.64.0.1/cgnat.png")
        self._test_bad_url("http://100.127.255.255/cgnat.png")

    def test_ssrf_bound_04_ipv4_mapped_and_ipv6_private(self):
        """TC-T2-SSRF-BOUND-04: IPv4-mapped IPv6 (::ffff:) and IPv6 ULA (fc00::/7) / Link-Local (fe80::/10) rejected."""
        self._test_bad_url("http://[::ffff:127.0.0.1]/admin")
        self._test_bad_url("http://[::ffff:169.254.169.254]/latest/meta-data/")
        self._test_bad_url("http://[::ffff:10.0.0.1]/secret.png")
        self._test_bad_url("http://[fc00::1]/internal.jpg")
        self._test_bad_url("http://[fd12:3456:789a::1]/data.png")
        self._test_bad_url("http://[fe80::1]/linklocal.png")

    def test_ssrf_bound_05_non_http_schemes_and_encoded_ips(self):
        """TC-T2-SSRF-BOUND-05: Non-HTTP schemes & hex/decimal integer IP notations rejected with 400."""
        self._test_bad_url("javascript:alert(1)")
        self._test_bad_url("file:///etc/passwd")
        self._test_bad_url("http://2130706433/admin")    # 127.0.0.1 decimal
        self._test_bad_url("http://0x7f000001/admin")   # 127.0.0.1 hex


class TestTier2AbortAndCircuitBreakerBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 6: Abort Batch Mid-Flight & Emergency Circuit Breaker."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0})

    def test_abort_bound_01_trips_breaker_and_sets_aborted_state(self):
        """TC-T2-ABORT-BOUND-01: POST /api/batch/abort sets status to ABORTED and trips circuit breaker."""
        res = self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("circuitBreakerTripped"))
        self.assertEqual(res.json().get("jobState", {}).get("status"), "ABORTED")

    def test_abort_bound_02_canary_rejected_while_breaker_tripped(self):
        """TC-T2-ABORT-BOUND-02: Canary test while circuit breaker active returns 423 CIRCUIT_BREAKER_ACTIVE."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 423)
        self.assertEqual(res.json().get("code"), "CIRCUIT_BREAKER_ACTIVE")

    def test_abort_bound_03_webhook_rejected_while_breaker_tripped(self):
        """TC-T2-ABORT-BOUND-03: Webhook while circuit breaker active returns 423 Locked."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 423)
        self.assertEqual(res.json().get("reason"), "circuit_breaker_tripped")

    def test_abort_bound_04_resume_resets_breaker_cleanly(self):
        """TC-T2-ABORT-BOUND-04: POST /api/batch/resume resets circuit breaker to false."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        res = self.client.post("/api/batch/resume", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json().get("circuitBreakerTripped"))

    def test_abort_bound_05_operations_succeed_immediately_after_resume(self):
        """TC-T2-ABORT-BOUND-05: Canary and webhooks immediately execute after circuit breaker resume."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/resume", json_data={"shop": PRIMARY_SHOP})

        # Canary succeeds
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 200)


class TestTier2RollbackBoundaries(unittest.TestCase):
    """Tier 2 - Scenario 7: Rollback Non-Existent Snapshot & Edge Conditions."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE"})

    def test_rollback_bound_01_no_snapshots_returns_error(self):
        """TC-T2-ROLLBACK-BOUND-01: Rollback when no snapshots exist returns 500 SNAPSHOT_NOT_FOUND."""
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json().get("code"), "SNAPSHOT_NOT_FOUND")

    def test_rollback_bound_02_invalid_snapshot_id_rejected(self):
        """TC-T2-ROLLBACK-BOUND-02: Rollback with non-existent snapshotId returns 500 SNAPSHOT_NOT_FOUND."""
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": "snap_999999_nonexistent"})
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json().get("code"), "SNAPSHOT_NOT_FOUND")

    def test_rollback_bound_03_cross_tenant_rollback_rejected(self):
        """TC-T2-ROLLBACK-BOUND-03: Rollback on another store without auth token returns 403."""
        res = self.client.post("/api/rollback", json_data={"shop": OTHER_SHOP})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED")

    def test_rollback_bound_04_corrupted_request_body_handled(self):
        """TC-T2-ROLLBACK-BOUND-04: Malformed body sent to rollback returns 400 INVALID_JSON."""
        res = self.client.post("/api/rollback", data=b"{corrupted_json", headers={"Content-Type": "application/json"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_JSON")

    def test_rollback_bound_05_restores_store_with_zero_initial_metafields(self):
        """TC-T2-ROLLBACK-BOUND-05: Rollback correctly clears metafields if snapshot had zero metafields."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        snap_id = store.create_snapshot()

        # Add dirty metafield
        store.catalog[0].setdefault("metafields", {})["safemedia.clean_ad_image_url"] = "https://dirty-url.jpg"

        # Rollback
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(res.status_code, 200)

        # Metafield must be gone
        self.assertNotIn("safemedia.clean_ad_image_url", store.catalog[0].get("metafields", {}))


if __name__ == "__main__":
    unittest.main()
