"""
tests/test_oauth_and_gdpr.py
Comprehensive Verification Suite for Shopify OAuth 2.0 Flow and Mandatory GDPR/Privacy Webhooks.
Verifies STEP 1 of App Store Publishing Readiness:
1. Multi-tenant OAuth 2.0 authorization initiation (GET /api/auth)
2. OAuth 2.0 callback with query parameter HMAC verification and token exchange (GET /api/auth/callback)
3. Mandatory GDPR customer data request webhook (POST /webhooks/privacy/customers/data_request)
4. Mandatory GDPR customer redact webhook (POST /webhooks/privacy/customers/redact)
5. Mandatory GDPR shop redact webhook (POST /webhooks/privacy/shop/redact)
6. Mandatory app uninstalled webhook (POST /webhooks/app/uninstalled)
7. Security: HMAC-SHA256 signature verification, domain validation, anti-forgery guards.
"""

import unittest
import urllib.parse
import json
import time
import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
    OTHER_SHOP,
    WEBHOOK_SECRET,
    compute_shopify_hmac,
    compute_shopify_query_hmac,
)


class TestShopifyOAuthAndPrivacy(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()
        self.test_shop = "merchant-store-new.myshopify.com"

    # =========================================================================
    # 1. Shopify OAuth 2.0 Initiation (GET /api/auth)
    # =========================================================================

    def test_oauth_init_valid_shop_redirects_to_shopify(self):
        """TC-OAUTH-01: GET /api/auth with valid shop redirects to Shopify OAuth consent screen."""
        res = self.client.get(f"/api/auth?shop={self.test_shop}")
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location")
        self.assertTrue(location, "Location header missing from 302 redirect")

        parsed = urllib.parse.urlparse(location)
        self.assertEqual(parsed.netloc, self.test_shop)
        self.assertEqual(parsed.path, "/admin/oauth/authorize")

        query = dict(urllib.parse.parse_qsl(parsed.query))
        self.assertEqual(query.get("client_id"), "safemedia_shield_app_key")
        self.assertIn("read_products", query.get("scope", ""))
        self.assertIn("write_products", query.get("scope", ""))
        self.assertTrue(query.get("state"), "OAuth state nonce missing")
        self.assertIn("/api/auth/callback", query.get("redirect_uri", ""))

    def test_oauth_init_invalid_shop_rejected(self):
        """TC-OAUTH-02: GET /api/auth with invalid or missing shop returns 400 INVALID_SHOP_DOMAIN."""
        # Missing shop
        res_missing = self.client.get("/api/auth")
        self.assertEqual(res_missing.status_code, 400)
        self.assertEqual(res_missing.json().get("code"), "INVALID_SHOP_DOMAIN")

        # Invalid shop domains
        bad_shops = [
            "attacker.com",
            "evil.myshopify.com.attacker.com",
            "invalid_chars!.myshopify.com",
            "http://not-a-domain",
            "../traversal.myshopify.com",
        ]
        for bad_shop in bad_shops:
            res = self.client.get(f"/api/auth?shop={bad_shop}")
            self.assertEqual(res.status_code, 400, f"Bad shop '{bad_shop}' did not return 400")
            self.assertEqual(res.json().get("code"), "INVALID_SHOP_DOMAIN")

    # =========================================================================
    # 2. Shopify OAuth 2.0 Callback (GET /api/auth/callback)
    # =========================================================================

    def test_oauth_callback_valid_hmac_exchanges_token_and_redirects(self):
        """TC-OAUTH-03: GET /api/auth/callback with valid query HMAC exchanges token and redirects to embedded app."""
        params = {
            "shop": self.test_shop,
            "code": "auth_code_xyz123456",
            "state": "random_uuid_nonce_999",
            "timestamp": str(int(time.time())),
        }
        query_hmac = compute_shopify_query_hmac(params, WEBHOOK_SECRET)
        params["hmac"] = query_hmac

        qs = urllib.parse.urlencode(params)
        res = self.client.get(f"/api/auth/callback?{qs}")
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location")
        self.assertTrue(location, "Location header missing from 302 redirect")
        self.assertIn(f"https://{self.test_shop}/admin/apps/safemedia_shield_app_key", location)

        # Verify tenant store was initialized
        store = self.client.app.get_store(self.test_shop)
        self.assertTrue(hasattr(store, "auth") and store.auth)
        self.assertEqual(store.auth["shop"], self.test_shop)
        self.assertEqual(store.auth["accessToken"], "shpat_oauth_merchant-store-new_auth_code_xyz123456")

    def test_oauth_callback_forged_hmac_rejected(self):
        """TC-OAUTH-04: GET /api/auth/callback with forged or missing HMAC returns 401 INVALID_OAUTH_HMAC."""
        # Forged HMAC
        params = {
            "shop": self.test_shop,
            "code": "auth_code_xyz123456",
            "state": "random_uuid_nonce_999",
            "timestamp": str(int(time.time())),
            "hmac": "forged_hex_digest_0000000000000000000000000000000000000000000000000000000000000000",
        }
        qs = urllib.parse.urlencode(params)
        res = self.client.get(f"/api/auth/callback?{qs}")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("code"), "INVALID_OAUTH_HMAC")

        # Missing HMAC
        del params["hmac"]
        qs_no_hmac = urllib.parse.urlencode(params)
        res_no_hmac = self.client.get(f"/api/auth/callback?{qs_no_hmac}")
        self.assertEqual(res_no_hmac.status_code, 400)
        self.assertEqual(res_no_hmac.json().get("code"), "MISSING_OAUTH_PARAMS")

        # Missing code
        params_no_code = {
            "shop": self.test_shop,
            "hmac": "dummy_hmac",
        }
        qs_no_code = urllib.parse.urlencode(params_no_code)
        res_no_code = self.client.get(f"/api/auth/callback?{qs_no_code}")
        self.assertEqual(res_no_code.status_code, 400)
        self.assertEqual(res_no_code.json().get("code"), "MISSING_OAUTH_PARAMS")

    # =========================================================================
    # 3. Mandatory GDPR Customer Data Request Webhook
    # =========================================================================

    def test_gdpr_customer_data_request_webhook(self):
        """TC-GDPR-01: POST /webhooks/privacy/customers/data_request responds 200 OK confirming no PII stored."""
        payload = {
            "shop_id": 999123,
            "shop_domain": PRIMARY_SHOP,
            "customer": {"id": 12345, "email": "customer@example.com", "phone": "+15551234567"},
            "orders_requested": [1001, 1002],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }

        # Valid webhook
        res = self.client.post("/webhooks/privacy/customers/data_request", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))
        self.assertIn("No customer personal data", res.json().get("message", ""))

        # Forged HMAC rejected with 401
        bad_headers = {**headers, "X-Shopify-Hmac-Sha256": "forged_signature_=="}
        res_bad = self.client.post("/webhooks/privacy/customers/data_request", data=raw_body, headers=bad_headers)
        self.assertEqual(res_bad.status_code, 401)
        self.assertEqual(res_bad.json().get("code"), "INVALID_WEBHOOK_HMAC")

        # Missing shop header rejected with 401
        no_shop_headers = {"X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body)}
        res_no_shop = self.client.post("/webhooks/privacy/customers/data_request", data=raw_body, headers=no_shop_headers)
        self.assertEqual(res_no_shop.status_code, 401)
        self.assertEqual(res_no_shop.json().get("code"), "MISSING_WEBHOOK_HEADERS")

    # =========================================================================
    # 4. Mandatory GDPR Customer Redact Webhook
    # =========================================================================

    def test_gdpr_customer_redact_webhook(self):
        """TC-GDPR-02: POST /webhooks/privacy/customers/redact responds 200 OK confirming no PII stored."""
        payload = {
            "shop_id": 999123,
            "shop_domain": PRIMARY_SHOP,
            "customer": {"id": 12345, "email": "customer@example.com"},
            "orders_to_redact": [1001],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }

        # Valid webhook
        res = self.client.post("/webhooks/privacy/customers/redact", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))
        self.assertIn("No customer personal data stored", res.json().get("message", ""))

        # Forged HMAC rejected with 401
        bad_headers = {**headers, "X-Shopify-Hmac-Sha256": "bad_sig_=="}
        res_bad = self.client.post("/webhooks/privacy/customers/redact", data=raw_body, headers=bad_headers)
        self.assertEqual(res_bad.status_code, 401)
        self.assertEqual(res_bad.json().get("code"), "INVALID_WEBHOOK_HMAC")

    # =========================================================================
    # 5. Mandatory GDPR Shop Redact Webhook (48h after uninstall)
    # =========================================================================

    def test_gdpr_shop_redact_webhook(self):
        """TC-GDPR-03: POST /webhooks/privacy/shop/redact purges store data and responds 200 OK."""
        # Setup store with catalog
        store = self.client.app.get_store(self.test_shop)
        self.assertTrue(len(store.catalog) > 0)

        payload = {
            "shop_id": 888444,
            "shop_domain": self.test_shop,
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": self.test_shop,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }

        # Valid webhook
        res = self.client.post("/webhooks/privacy/shop/redact", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))
        self.assertIn("purged/archived", res.json().get("message", ""))

        # Verify catalog was purged
        self.assertEqual(len(store.catalog), 0)

        # Forged HMAC rejected with 401
        bad_headers = {**headers, "X-Shopify-Hmac-Sha256": "forged_=="}
        res_bad = self.client.post("/webhooks/privacy/shop/redact", data=raw_body, headers=bad_headers)
        self.assertEqual(res_bad.status_code, 401)
        self.assertEqual(res_bad.json().get("code"), "INVALID_WEBHOOK_HMAC")

    # =========================================================================
    # 6. Mandatory App Uninstalled Webhook (Immediate Uninstall)
    # =========================================================================

    def test_app_uninstalled_webhook(self):
        """TC-UNINST-01: POST /webhooks/app/uninstalled immediately disables auto-sync and trips circuit breaker."""
        store = self.client.app.get_store(self.test_shop)
        store.auto_sync_enabled = True
        store.circuit_breaker_tripped = False

        payload = {
            "id": 888444,
            "myshopify_domain": self.test_shop,
        }
        raw_body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": self.test_shop,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }

        # Valid webhook
        res = self.client.post("/webhooks/app/uninstalled", data=raw_body, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))
        self.assertIn("uninstall processed", res.json().get("message", ""))

        # Verify auto-sync is disabled and circuit breaker tripped
        self.assertFalse(store.auto_sync_enabled)
        self.assertTrue(store.circuit_breaker_tripped)

        # TC-UNINST-02: Ensure canary quota is preserved across uninstalls (Denial of Wallet defense)
        store.canary_used_count = 3
        res_uninstall2 = self.client.post("/webhooks/app/uninstalled", data=raw_body, headers=headers)
        self.assertEqual(res_uninstall2.status_code, 200)
        self.assertEqual(store.canary_used_count, 3, "Canary used count must not be reset on app uninstallation")

        # Forged HMAC rejected with 401
        bad_headers = {**headers, "X-Shopify-Hmac-Sha256": "fake_=="}
        res_bad = self.client.post("/webhooks/app/uninstalled", data=raw_body, headers=bad_headers)
        self.assertEqual(res_bad.status_code, 401)
        self.assertEqual(res_bad.json().get("code"), "INVALID_WEBHOOK_HMAC")

    # =========================================================================
    # 7. Auto-Sync Toggle Endpoint (POST /api/auto-sync/toggle)
    # =========================================================================

    def test_auto_sync_toggle_endpoint(self):
        """TC-TOGGLE-01: POST /api/auto-sync/toggle guards free trial and flips state cleanly."""
        store = self.client.app.get_store(PRIMARY_SHOP)
        store.plan_status = "CANARY_TRIAL"

        # 1. Blocked for unsubscribed CANARY_TRIAL merchants
        res_blocked = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res_blocked.status_code, 402)
        self.assertEqual(res_blocked.json().get("code"), "SUBSCRIPTION_REQUIRED_FOR_AUTOSYNC")

        # 2. Permitted when 14-day free trial or active subscription is started
        store.plan_status = "TRIAL_14D_ACTIVE"
        store.auto_sync_enabled = True

        res1 = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.json().get("autoSyncEnabled"))
        self.assertFalse(store.auto_sync_enabled)

        res2 = self.client.post("/api/auto-sync/toggle", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json().get("autoSyncEnabled"))
        self.assertTrue(store.auto_sync_enabled)


if __name__ == "__main__":
    unittest.main()
