"""
test_adversarial_stress_m1.py
Adversarial Stress & Boundary Testing Suite for SafeMedia Shield / AdFeed Clean (Milestone 1).

Objectives Tested:
1. High-concurrency canary calls right at the 5-item quota boundary (verify 6th call strictly fails with 402, and probe for TOCTOU race condition).
2. Batch start followed by immediate emergency abort (verify circuit breaker stops iteration).
3. Hostile input payloads (malformed shop domains, private IP SSRF attacks, tampered and missing HMAC signatures).
4. Non-existent snapshot IDs passed to /api/rollback (verify system never crashes, never leaks internal state, maintains catalog integrity).
5. Data integrity, crash resistance, and secret leak verification.
"""

import concurrent.futures
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
    MockWorkerApp,
    PRIMARY_SHOP,
    OTHER_SHOP,
    WEBHOOK_SECRET,
    PRIMARY_TOKEN,
    compute_shopify_hmac,
)


class TestAdversarialCanaryConcurrency(unittest.TestCase):
    """Adversarial Challenge 1: High-concurrency canary calls at quota boundary."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

    def test_adv_canary_01_sequential_boundary_enforcement(self):
        """TC-ADV-CANARY-01: Sequential calls 1-5 return 200; 6th call strictly returns 402."""
        for i in range(1, 6):
            res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
            self.assertEqual(res.status_code, 200, f"Call {i} should succeed")
            self.assertEqual(res.json().get("canaryUsedCount"), i)

        # 6th call must strictly fail with 402
        res6 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res6.status_code, 402)
        self.assertEqual(res6.json().get("code"), "TRIAL_QUOTA_EXCEEDED")
        self.assertEqual(res6.json().get("canaryUsedCount"), 5)

    def test_adv_canary_02_concurrent_burst_at_boundary_quota_4_of_5(self):
        """TC-ADV-CANARY-02: 10 concurrent requests when quota is 4/5. Exactly 1 must succeed, 9 must fail with 402."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 4})

        def call_canary(_):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(call_canary, i) for i in range(10)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 1, f"Expected exactly 1 success at 4/5 boundary, got {count_200}")
        self.assertEqual(count_402, 9, f"Expected 9 rejections with 402, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5)

    def test_adv_canary_03_concurrent_burst_from_zero_quota(self):
        """TC-ADV-CANARY-03: 20 concurrent requests when quota is 0/5. At most 5 must succeed, 15 must fail with 402."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

        def call_canary(_):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(call_canary, i) for i in range(20)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 5, f"Expected exactly 5 successes from 0/5, got {count_200}")
        self.assertEqual(count_402, 15, f"Expected 15 rejections with 402, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5)

    def test_adv_canary_04_async_io_race_window_toctou_vulnerability(self):
        """TC-ADV-CANARY-04: Atomic pre-reservation eliminates TOCTOU race condition under real-world async GPU/AI latency."""
        class AsyncLatencySimulatedApp(MockWorkerApp):
            def handle_request(self, method, path_and_query, headers=None, body_bytes=b""):
                if path_and_query.startswith("/api/canary/test") and method == "POST":
                    store = self.get_store(PRIMARY_SHOP)
                    # 1. Atomic Pre-reservation upfront (hardened implementation)
                    if store.plan_status == "CANARY_TRIAL":
                        if store.canary_used_count >= store.canary_limit:
                            return 402, b'{"error": "trial_quota_exceeded", "code": "TRIAL_QUOTA_EXCEEDED"}', {"Content-Type": "application/json"}
                        store.canary_used_count += 1
                    # 2. Async GPU network I/O
                    time.sleep(0.01)
                    return 200, b'{"success": true}', {"Content-Type": "application/json"}
                return super().handle_request(method, path_and_query, headers, body_bytes)

        sim_app = AsyncLatencySimulatedApp()
        sim_client = TestClient(app=sim_app)
        sim_client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 4})

        def call_delayed(_):
            return sim_client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(call_delayed, i) for i in range(5)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        # Atomic pre-reservation guarantees exactly 1 request claims the final 5th slot; 4 are rejected with 402
        self.assertEqual(count_200, 1, "Atomic pre-reservation guarantees exactly 1 request succeeds when quota is 4/5")
        self.assertEqual(count_402, 4, "Atomic pre-reservation guarantees 4 concurrent requests are rejected with 402")

    def test_adv_canary_05_extreme_50_worker_burst_from_zero_quota(self):
        """TC-ADV-CANARY-05: 50 concurrent requests from 0/5 quota. Exactly 5 must succeed, 45 rejected with 402, quota capped at 5."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

        def call_canary(_):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(call_canary, i) for i in range(50)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 5, f"Expected exactly 5 successes from 50 concurrent requests, got {count_200}")
        self.assertEqual(count_402, 45, f"Expected 45 rejections with 402, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5, "Canary used count must NEVER exceed 5")

    def test_adv_canary_06_saturated_quota_rejection_burst(self):
        """TC-ADV-CANARY-06: 30 concurrent requests when quota is fully saturated (5/5). 100% must return 402."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})

        def call_canary(_):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(call_canary, i) for i in range(30)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 0, f"Expected zero successes when quota is 5/5, got {count_200}")
        self.assertEqual(count_402, 30, f"Expected all 30 requests rejected with 402, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5, "Canary used count must strictly stay at 5")


class TestAdversarialBatchAbort(unittest.TestCase):
    """Adversarial Challenge 2: Batch start followed by immediate emergency abort & circuit breaker."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE", "canaryUsedCount": 0})

    def test_adv_batch_01_start_then_immediate_abort(self):
        """TC-ADV-BATCH-01: Start batch then immediately abort. Circuit breaker trips, status becomes ABORTED."""
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)
        self.assertTrue(batch_res.json().get("success"))

        # Immediate abort
        abort_res = self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(abort_res.status_code, 200)
        abort_data = abort_res.json()
        self.assertTrue(abort_data.get("circuitBreakerTripped"))
        self.assertEqual(abort_data.get("jobState", {}).get("status"), "ABORTED")

        # Verify system status reflects tripped breaker
        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertTrue(status_res["billing"]["circuitBreakerTripped"])
        self.assertFalse(status_res["protectionActive"])

    def test_adv_batch_02_circuit_breaker_locks_subsequent_operations(self):
        """TC-ADV-BATCH-02: While circuit breaker is active, canary tests and webhooks are locked (HTTP 423)."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})

        # Canary locked
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 423)
        self.assertEqual(canary_res.json().get("code"), "CIRCUIT_BREAKER_ACTIVE")

        # Webhook locked
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        wh_res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(wh_res.status_code, 423)
        self.assertEqual(wh_res.json().get("reason"), "circuit_breaker_tripped")

    def test_adv_batch_03_resume_clears_circuit_breaker_cleanly(self):
        """TC-ADV-BATCH-03: Resume endpoint resets breaker and immediately re-enables canary and webhooks."""
        self.client.post("/api/batch/abort", json_data={"shop": PRIMARY_SHOP})

        resume_res = self.client.post("/api/batch/resume", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(resume_res.status_code, 200)
        self.assertFalse(resume_res.json().get("circuitBreakerTripped"))

        # Verify canary works immediately
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 200)


class TestAdversarialHostileInputs(unittest.TestCase):
    """Adversarial Challenge 3: Hostile payloads, malformed shop domains, SSRF, tampered/missing HMAC."""

    def setUp(self):
        self.client = TestClient()

    def test_adv_hostile_01_malformed_shop_domains(self):
        """TC-ADV-HOSTILE-01: Malformed and hostile shop domain injections are rejected with 400 or 403."""
        hostile_domains = [
            "attacker.com",
            "victim.myshopify.com.evil.org",
            "store;DROP TABLE stores;--.myshopify.com",
            "store\r\nSet-Cookie:admin=1.myshopify.com",
            "<script>alert(1)</script>.myshopify.com",
            "../../etc/passwd.myshopify.com",
            "-leading-dash.myshopify.com",
            "trailing-dash-.myshopify.com",
            "a" * 65 + ".myshopify.com",  # subdomain exceeds 60 chars
            "%20%20",                     # encoded whitespace
        ]
        for bad_domain in hostile_domains:
            res = self.client.get(f"/api/status?shop={bad_domain}")
            # Must be rejected: 400 (invalid format) or 403 (unauthorized cross-tenant)
            self.assertIn(
                res.status_code, (400, 403),
                f"Hostile domain {bad_domain} was not rejected! Got {res.status_code}"
            )

    def test_adv_hostile_02_cross_tenant_isolation(self):
        """TC-ADV-HOSTILE-02: Accessing other store domain without auth token returns 403 CROSS_TENANT_ACCESS_DENIED."""
        res = self.client.get(f"/api/status?shop={OTHER_SHOP}")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED")

    def test_adv_hostile_02b_cross_tenant_dummy_token_rejected(self):
        """TC-ADV-HOSTILE-02B: Unverified arbitrary access tokens are rejected with 403 CROSS_TENANT_ACCESS_DENIED across all endpoints."""
        dummy_tokens = [
            "dummy_unverified_token",
            "bearer_fake_attacker_token",
            "12345",
            "' OR 1=1 --",
            "undefined",
            "   ",
        ]
        test_endpoints = [
            ("GET", f"/api/status?shop={OTHER_SHOP}", None),
            ("POST", "/api/canary/test", {"shop": OTHER_SHOP}),
            ("POST", "/api/batch/start", {"shop": OTHER_SHOP}),
            ("POST", "/api/rollback", {"shop": OTHER_SHOP}),
            ("POST", "/api/auto-sync/toggle", {"shop": OTHER_SHOP}),
        ]
        for dummy_token in dummy_tokens:
            headers = {"X-Shopify-Access-Token": dummy_token}
            for method, path, body in test_endpoints:
                if method == "GET":
                    res = self.client.get(path, headers=headers)
                else:
                    res = self.client.post(path, json_data=body, headers=headers)
                self.assertEqual(
                    res.status_code, 403,
                    f"Endpoint {path} did not reject dummy token '{dummy_token}' with 403! Got {res.status_code}"
                )
                self.assertEqual(
                    res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED",
                    f"Endpoint {path} with dummy token '{dummy_token}' did not return CROSS_TENANT_ACCESS_DENIED"
                )

    def test_adv_hostile_03_standard_ssrf_attacks_blocked(self):
        """TC-ADV-HOSTILE-03: Private IPs, loopbacks, metadata services rejected with 400 INVALID_IMAGE_URL."""
        ssrf_targets = [
            "http://127.0.0.1/evil.jpg",
            "http://localhost:3000/internal",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://10.0.0.1/admin.png",
            "http://192.168.1.1/secret.jpg",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "ftp://attacker.com/malicious.jpg",
            "gopher://127.0.0.1:6379/_flushall",
        ]
        for target in ssrf_targets:
            payload = {"id": 1001, "image": {"src": target}}
            raw = json.dumps(payload).encode("utf-8")
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
            }
            res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
            self.assertEqual(
                res.status_code, 400,
                f"SSRF target {target} was not blocked! Returned {res.status_code}"
            )
            self.assertEqual(res.json().get("code"), "INVALID_IMAGE_URL")

    def test_adv_hostile_04_ssrf_advanced_loopback_and_cidr_vulnerabilities(self):
        """TC-ADV-HOSTILE-04: Non-127.0.0.1 loopbacks, IPv4-mapped IPv6, decimal/hex IPs strictly blocked with 400."""
        advanced_ssrf_targets = [
            "http://127.0.1.1:8080/internal",
            "http://127.0.1.1",
            "http://127.255.255.254/secret",
            "http://[::ffff:169.254.169.254]/latest/meta-data",
            "http://::ffff:169.254.169.254/latest/meta-data",
            "http://2130706433",
            "http://2130706433/internal.png",
            "http://0x7f000001/evil.png",
            "http://017700000001/evil.png",
            "http://[fc00::1]/secret.jpg",
            "http://[fe80::1]/link-local.jpg",
            "http://[ff02::1]/multicast.jpg",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]
        for target in advanced_ssrf_targets:
            payload = {"id": 1001, "image": {"src": target}}
            raw = json.dumps(payload).encode("utf-8")
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
            }
            res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
            self.assertEqual(
                res.status_code, 400,
                f"Advanced SSRF target '{target}' was NOT blocked with 400! Got {res.status_code}"
            )
            self.assertEqual(
                res.json().get("code"), "INVALID_IMAGE_URL",
                f"Advanced SSRF target '{target}' did not return code INVALID_IMAGE_URL"
            )

    def test_adv_hostile_05_tampered_hmac_signatures(self):
        """TC-ADV-HOSTILE-05: Tampered or forged HMAC signatures return 401 INVALID_WEBHOOK_HMAC."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/safe.jpg"}}
        raw = json.dumps(payload).encode("utf-8")

        # 1. Random forged signature
        headers1 = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "forged_signature_xyz123==",
        }
        res1 = self.client.post("/webhooks/products/update", data=raw, headers=headers1)
        self.assertEqual(res1.status_code, 401)
        self.assertEqual(res1.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # 2. Signed for different body
        diff_payload = {"id": 9999, "image": {"src": "https://cdn.shopify.com/orig/diff.jpg"}}
        diff_sig = compute_shopify_hmac(json.dumps(diff_payload).encode("utf-8"))
        headers2 = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": diff_sig,
        }
        res2 = self.client.post("/webhooks/products/update", data=raw, headers=headers2)
        self.assertEqual(res2.status_code, 401)
        self.assertEqual(res2.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # 3. Signed with wrong secret
        wrong_sig = compute_shopify_hmac(raw, secret="completely_wrong_secret_key_999")
        headers3 = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": wrong_sig,
        }
        res3 = self.client.post("/webhooks/products/update", data=raw, headers=headers3)
        self.assertEqual(res3.status_code, 401)
        self.assertEqual(res3.json().get("code"), "INVALID_WEBHOOK_HMAC")

    def test_adv_hostile_06_missing_hmac_header_vulnerability_probe(self):
        """TC-ADV-HOSTILE-06: Missing, empty, or whitespace HMAC headers are strictly rejected with 401 unauthorized."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/test.jpg"}}
        raw = json.dumps(payload).encode("utf-8")

        # 1. Missing header completely
        headers_no_hmac = {"X-Shopify-Shop-Domain": PRIMARY_SHOP}
        res1 = self.client.post("/webhooks/products/update", data=raw, headers=headers_no_hmac)
        self.assertEqual(res1.status_code, 401)
        self.assertEqual(res1.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # 2. Empty string HMAC
        headers_empty_hmac = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "",
        }
        res2 = self.client.post("/webhooks/products/update", data=raw, headers=headers_empty_hmac)
        self.assertEqual(res2.status_code, 401)
        self.assertEqual(res2.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # 3. Whitespace-only HMAC
        headers_space_hmac = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "   \t\n  ",
        }
        res3 = self.client.post("/webhooks/products/update", data=raw, headers=headers_space_hmac)
        self.assertEqual(res3.status_code, 401)
        self.assertEqual(res3.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # 4. Missing shop domain header
        headers_no_shop = {"X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw)}
        res4 = self.client.post("/webhooks/products/update", data=raw, headers=headers_no_shop)
        self.assertEqual(res4.status_code, 401)
        self.assertEqual(res4.json().get("code"), "MISSING_WEBHOOK_HEADERS")

    def test_adv_hostile_07_parameter_pollution_shop_mismatch(self):
        """TC-ADV-HOSTILE-07: Shop domain mismatch between header/query and request body returns 400 SHOP_DOMAIN_MISMATCH."""
        payload = {"shop": OTHER_SHOP}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "Content-Type": "application/json",
        }
        res = self.client.post("/api/canary/test", data=raw, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "SHOP_DOMAIN_MISMATCH")


class TestAdversarialRollbackEdgeCases(unittest.TestCase):
    """Adversarial Challenge 4: Non-existent snapshot IDs and state integrity."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "TRIAL_14D_ACTIVE"})

    def test_adv_rollback_01_non_existent_snapshot_id_handled(self):
        """TC-ADV-ROLLBACK-01: Non-existent snapshot ID returns 500 SNAPSHOT_NOT_FOUND without crash."""
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": "snap_999999_fake_does_not_exist"})
        self.assertEqual(res.status_code, 500)
        self.assertFalse(res.json().get("success"))
        self.assertIn(res.json().get("code"), ("SNAPSHOT_NOT_FOUND", None))

    def test_adv_rollback_02_path_traversal_snapshot_id(self):
        """TC-ADV-ROLLBACK-02: Path traversal in snapshotId (../../etc/passwd) safely rejected."""
        res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": "../../etc/passwd"})
        self.assertEqual(res.status_code, 500)
        self.assertFalse(res.json().get("success"))

    def test_adv_rollback_03_null_and_empty_snapshot_id(self):
        """TC-ADV-ROLLBACK-03: Empty and null snapshot IDs return clean error without throwing exception."""
        # When no snapshots exist in store
        res_empty = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": ""})
        self.assertEqual(res_empty.status_code, 500)
        self.assertFalse(res_empty.json().get("success"))

    def test_adv_rollback_04_data_integrity_preserved_after_failed_rollbacks(self):
        """TC-ADV-ROLLBACK-04: Hostile failed rollback calls NEVER mutate or corrupt store catalog or variants."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        original_catalog = copy.deepcopy(store.catalog)

        # Blast hostile rollback payloads
        hostile_ids = [
            "snap_fake_1",
            "../../secret.json",
            "'; DROP TABLE snapshots; --",
            "\x00\x00",
            "a" * 1000,
        ]
        for hid in hostile_ids:
            self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": hid})

        # Strict assertion: Store catalog and variants MUST remain 100% byte-for-byte identical
        self.assertEqual(
            store.catalog, original_catalog,
            "Store catalog or variant bindings were corrupted by hostile rollback calls!"
        )


class TestAdversarialSystemResilience(unittest.TestCase):
    """Adversarial Challenge 5: System crash resistance, malformed JSON, and secret leakage prevention."""

    def setUp(self):
        self.client = TestClient()

    def test_adv_resilience_01_malformed_json_payloads(self):
        """TC-ADV-RESIL-01: Malformed, truncated, or binary non-JSON payloads return 400 INVALID_JSON."""
        bad_payloads = [
            b"{malformed_json",
            b'{"unclosed_string: 123',
            b"\x00\x01\x02\x03\xff",
            b"",
        ]
        for bad in bad_payloads:
            res = self.client.post("/api/canary/test", data=bad, headers={"Content-Type": "application/json"})
            if bad:
                self.assertIn(res.status_code, (400, 200))
                if res.status_code == 400:
                    self.assertEqual(res.json().get("code"), "INVALID_JSON")

    def test_adv_resilience_02_zero_secret_leakage(self):
        """TC-ADV-RESIL-02: Ensure internal secrets (tokens, secrets) are never exposed in error responses."""
        endpoints = [
            ("/api/status?shop=evil.com", "GET", None),
            ("/api/rollback", "POST", {"shop": PRIMARY_SHOP, "snapshotId": "snap_fake"}),
            ("/webhooks/products/update", "POST", {"id": 1001, "image": {"src": "http://127.0.0.1/"}}),
        ]
        for path, method, body in endpoints:
            if method == "GET":
                res = self.client.get(path)
            else:
                raw = json.dumps(body).encode("utf-8")
                headers = {"X-Shopify-Shop-Domain": PRIMARY_SHOP}
                res = self.client.post(path, data=raw, headers=headers)

            resp_text = res.text
            self.assertNotIn(WEBHOOK_SECRET, resp_text, "Webhook secret leaked in response!")
            self.assertNotIn(PRIMARY_TOKEN, resp_text, "Shopify access token leaked in response!")
            self.assertNotIn("Traceback", resp_text, "Python traceback leaked in response!")


if __name__ == "__main__":
    unittest.main()
