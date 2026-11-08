"""
adversarial_challenger_deep_probe.py
Independent Empirical Stress Challenger Harness for Gate Iteration 2.

Exhaustively probes:
1. Webhook HMAC: Missing, empty, whitespace, tampered, wrong secret.
2. SSRF Protection: 127.0.1.1, ::ffff:169.254.169.254, http://2130706433, hex/octal/decimal,
   IPv6 ULA/link-local/multicast, cloud metadata, and legitimate CDN non-regression.
3. Canary Concurrency Quota Boundary: 100-thread concurrent bursts, simulated latency,
   zero-over-allocation invariant (canaryUsedCount <= 5).
4. Multi-Tenant Authorization: Dummy tokens, privilege escalation, cross-tenant isolation on all endpoints.
5. Parameter Pollution: Header/Query vs Body shop domain mismatch.
"""

import concurrent.futures
import copy
import json
import pathlib
import sys
import time
import unittest
import urllib.parse

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
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
    is_valid_public_image_url,
)


class TestEmpiricalHMACChallenge(unittest.TestCase):
    """Deep challenge for Webhook HMAC signature enforcement."""

    def setUp(self):
        self.client = TestClient()

    def test_missing_hmac_header_strictly_401(self):
        """HMAC Challenge 1: Completely missing HMAC header strictly returns 401 INVALID_WEBHOOK_HMAC."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/valid.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {"X-Shopify-Shop-Domain": PRIMARY_SHOP}
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")
        self.assertEqual(res.json().get("error"), "unauthorized")

    def test_empty_and_whitespace_hmac_strictly_401(self):
        """HMAC Challenge 2: Empty, whitespace-only, and newline HMAC headers strictly return 401."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/valid.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        bad_hmac_values = [
            "",
            " ",
            "    ",
            "\t",
            "\n",
            "\r\n",
            "   \t\n   ",
        ]
        for bad_hmac in bad_hmac_values:
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": bad_hmac,
            }
            res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
            self.assertEqual(
                res.status_code, 401,
                f"HMAC value '{repr(bad_hmac)}' did not return 401! Got {res.status_code}"
            )
            self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")

    def test_tampered_and_invalid_hmac_strictly_401(self):
        """HMAC Challenge 3: Tampered payloads or signatures strictly return 401."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/valid.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        valid_hmac = compute_shopify_hmac(raw)

        tampered_cases = [
            ("tampered_signature_string", raw),
            (valid_hmac[:-4] + "AAAA", raw),
            (valid_hmac, raw + b" "),  # Extra trailing space in body invalidates digest
            (compute_shopify_hmac(raw, secret="attacker_secret_key"), raw),
            ("YWJjZA==", raw),  # valid base64 for 'abcd', but wrong digest
        ]
        for sig, body in tampered_cases:
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": sig,
            }
            res = self.client.post("/webhooks/products/update", data=body, headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json().get("code"), "INVALID_WEBHOOK_HMAC")

    def test_valid_hmac_passes_cleanly(self):
        """HMAC Challenge 4: Legitimate HMAC signature strictly succeeds with 200."""
        payload = {"id": 1001, "image": {"src": "https://cdn.shopify.com/orig/valid.jpg"}}
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
        }
        res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))


class TestEmpiricalSSRFChallenge(unittest.TestCase):
    """Deep challenge for SSRF protection and evasion vectors."""

    def setUp(self):
        self.client = TestClient()

    def test_ssrf_attacks_strictly_blocked(self):
        """SSRF Challenge 1: Required vectors 127.0.1.1, ::ffff:169.254.169.254, and 2130706433 strictly blocked."""
        required_targets = [
            "http://127.0.1.1:8080/internal",
            "http://127.0.1.1",
            "http://[::ffff:169.254.169.254]/latest/meta-data",
            "http://::ffff:169.254.169.254/latest/meta-data",
            "http://2130706433",
            "http://2130706433/internal.png",
        ]
        for target in required_targets:
            # 1. Direct function validation check
            self.assertFalse(
                is_valid_public_image_url(target),
                f"is_valid_public_image_url incorrectly allowed required SSRF target '{target}'"
            )
            # 2. HTTP endpoint validation check
            payload = {"id": 1001, "image": {"src": target}}
            raw = json.dumps(payload).encode("utf-8")
            headers = {
                "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw),
            }
            res = self.client.post("/webhooks/products/update", data=raw, headers=headers)
            self.assertEqual(
                res.status_code, 400,
                f"HTTP endpoint allowed required SSRF target '{target}'! Status: {res.status_code}"
            )
            self.assertEqual(res.json().get("code"), "INVALID_IMAGE_URL")

    def test_ssrf_comprehensive_evasion_fuzzing(self):
        """SSRF Challenge 2: Exhaustive evasion fuzzer (hex, octal, IPv6 ULA, CGNAT, link-local, cloud metadata)."""
        hostile_urls = [
            # Dotted decimal loopback CIDR
            "http://127.0.0.1/evil.jpg",
            "http://127.0.0.254/evil.jpg",
            "http://127.1/short",
            "http://127.255.255.254/secret",
            "http://0.0.0.0/zero",
            # Obfuscated integer / hex / octal representations
            "http://0x7f000001/hex",
            "http://0x7f.0.0.1/mixed",
            "http://017700000001/octal",
            "http://2852039166/metadata-decimal",  # 169.254.169.254 as decimal int
            # Cloud Metadata
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.0.1/linklocal",
            "http://metadata.google.internal/computeMetadata/v1/",
            # RFC 1918 Private Ranges
            "http://10.0.0.1/admin",
            "http://10.255.255.255/admin",
            "http://172.16.0.1/internal",
            "http://172.31.255.254/internal",
            "http://192.168.1.1/router",
            "http://192.168.254.254/internal",
            # Carrier Grade NAT (100.64.0.0/10)
            "http://100.64.0.1/cgnat",
            "http://100.127.255.254/cgnat",
            # IPv6 Loopback & Mapped
            "http://[::1]/internal",
            "http://[::]/zero",
            "http://[0:0:0:0:0:0:0:1]/internal",
            "http://[::ffff:127.0.0.1]/mapped",
            "http://[::ffff:10.0.0.1]/mapped",
            # IPv6 ULA (fc00::/7)
            "http://[fc00::1]/ula",
            "http://[fd00::1]/ula",
            "http://[fdff:ffff::1]/ula",
            # IPv6 Link-Local & Site-Local
            "http://[fe80::1]/linklocal",
            "http://[fe80::dead:beef]/linklocal",
            "http://[fec0::1]/sitelocal",
            # IPv6 Multicast
            "http://[ff02::1]/multicast",
            # Internal & local domain extensions
            "http://intranet.local/img.png",
            "http://service.internal/img.png",
            "http://admin.localhost/img.png",
            "http://app.localdomain/img.png",
            "http://router.home.arpa/img.png",
            # Non-HTTP Schemes
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379/_flushall",
            "ftp://attacker.com/malicious.jpg",
            "javascript:alert(1)",
            "dict://127.0.0.1:11211/stat",
        ]

        for url in hostile_urls:
            self.assertFalse(
                is_valid_public_image_url(url),
                f"is_valid_public_image_url allowed hostile target '{url}'"
            )

    def test_ssrf_legitimate_cdn_urls_allowed(self):
        """SSRF Challenge 3: Genuine public CDN and Shopify image URLs must NOT be blocked (No False Positives)."""
        valid_public_urls = [
            "https://cdn.shopify.com/s/files/1/0001/products/tshirt_black.jpg",
            "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800",
            "https://i.imgur.com/example123.png",
            "https://cdn.example-store.com/media/products/2026/bag.webp",
            "http://public-assets.global-merchants.net/image.jpeg",
        ]
        for url in valid_public_urls:
            self.assertTrue(
                is_valid_public_image_url(url),
                f"Legitimate public URL '{url}' was incorrectly blocked by SSRF filter!"
            )


class TestEmpiricalCanaryConcurrencyChallenge(unittest.TestCase):
    """Deep challenge for Canary quota enforcement and race condition prevention."""

    def setUp(self):
        self.client = TestClient()

    def test_concurrent_100_requests_boundary_invariant(self):
        """Canary Concurrency Challenge 1: 100 concurrent requests from 0/5 quota. Exactly 5 succeed, 95 fail."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})

        def burst_call(thread_id):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(burst_call, i) for i in range(100)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 5, f"CRITICAL: Quota boundary violated! Expected 5 successes, got {count_200}")
        self.assertEqual(count_402, 95, f"CRITICAL: Expected 95 rejections with 402, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5, "Canary counter exceeded maximum 5")

    def test_concurrent_burst_at_saturated_quota(self):
        """Canary Concurrency Challenge 2: 50 concurrent requests when quota is 5/5. Exactly 0 succeed, 50 fail."""
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 5})

        def burst_call(thread_id):
            return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(burst_call, i) for i in range(50)]
            results = [f.result() for f in futures]

        statuses = [r.status_code for r in results]
        count_200 = statuses.count(200)
        count_402 = statuses.count(402)

        self.assertEqual(count_200, 0, f"Expected 0 successes on saturated quota, got {count_200}")
        self.assertEqual(count_402, 50, f"Expected 50 rejections on saturated quota, got {count_402}")

        status_res = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_res["billing"]["canaryUsedCount"], 5)


class TestEmpiricalCrossTenantChallenge(unittest.TestCase):
    """Deep challenge for multi-tenant isolation and token authorization."""

    def setUp(self):
        self.client = TestClient()

    def test_dummy_tokens_rejected_on_all_endpoints(self):
        """Cross-Tenant Challenge 1: Dummy tokens return 403 CROSS_TENANT_ACCESS_DENIED across all endpoints."""
        dummy_tokens = [
            "dummy_unverified_token",
            "fake_token_12345",
            "bearer_attacker",
            "' OR 1=1 --",
            "undefined",
            "null",
        ]
        endpoints = [
            ("GET", f"/api/status?shop={OTHER_SHOP}", None),
            ("POST", "/api/canary/test", {"shop": OTHER_SHOP}),
            ("POST", "/api/batch/start", {"shop": OTHER_SHOP}),
            ("POST", "/api/batch/abort", {"shop": OTHER_SHOP}),
            ("POST", "/api/batch/resume", {"shop": OTHER_SHOP}),
            ("POST", "/api/rollback", {"shop": OTHER_SHOP}),
            ("POST", "/api/auto-sync/toggle", {"shop": OTHER_SHOP}),
            ("POST", "/api/billing/subscribe", {"shop": OTHER_SHOP}),
        ]

        for token in dummy_tokens:
            headers = {"X-Shopify-Access-Token": token}
            for method, path, body in endpoints:
                if method == "GET":
                    res = self.client.get(path, headers=headers)
                else:
                    res = self.client.post(path, json_data=body, headers=headers)

                self.assertEqual(
                    res.status_code, 403,
                    f"Endpoint {path} with dummy token '{token}' returned {res.status_code} instead of 403!"
                )
                self.assertEqual(
                    res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED",
                    f"Endpoint {path} did not return code CROSS_TENANT_ACCESS_DENIED"
                )

    def test_primary_token_cannot_access_other_store(self):
        """Cross-Tenant Challenge 2: Primary store token cannot access Store B (No Privilege Escalation)."""
        headers = {"X-Shopify-Access-Token": PRIMARY_TOKEN}
        res = self.client.get(f"/api/status?shop={OTHER_SHOP}", headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("code"), "CROSS_TENANT_ACCESS_DENIED")

    def test_parameter_pollution_domain_mismatch_strictly_400(self):
        """Cross-Tenant Challenge 3: Store domain mismatch between header/query and body returns 400 SHOP_DOMAIN_MISMATCH."""
        mismatch_cases = [
            # Header is Primary, Body is Other
            ("/api/canary/test", {"shop": OTHER_SHOP}, {"X-Shopify-Shop-Domain": PRIMARY_SHOP}),
            # Header is Other, Body is Primary
            ("/api/batch/start", {"shop": PRIMARY_SHOP}, {"X-Shopify-Shop-Domain": OTHER_SHOP}),
        ]
        for path, body, headers in mismatch_cases:
            res = self.client.post(path, json_data=body, headers=headers)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json().get("code"), "SHOP_DOMAIN_MISMATCH")


if __name__ == "__main__":
    unittest.main()
