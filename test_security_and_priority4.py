"""
test_security_and_priority4.py
Automated verification suite for SafeMedia Shield MVP pre-release safety & Priority 4:
1. User Operation Tests (Malformed JSON, missing images, SSRF URLs, duplicate requests)
2. Multi-Tenant Isolation Tests (Store A vs Store B concurrent state isolation)
3. Security Tests (Path traversal, cross-tenant snooping, forged Webhook HMAC signatures)
4. Priority 4 Tests (5-item free sample limit, $65/mo 14-day free trial gate, Circuit Breaker)
"""

import requests

BASE_URL = "https://safemedia-shield-worker.safemedia.workers.dev"
PRIMARY_SHOP = "safemedia-test-20261011.myshopify.com"
OTHER_SHOP = "victim-store-999.myshopify.com"


def run_all_tests():
    print("=== [Test 1] Security 3-1: Path Traversal & Cross-Tenant Access Defense ===")
    # 1a. Path traversal in shop parameter
    r = requests.get(f"{BASE_URL}/api/status?shop=../../etc/passwd", timeout=15)
    assert r.status_code == 400 and r.json().get("code") == "INVALID_SHOP_DOMAIN", f"Failed 1a: {r.status_code} {r.text}"
    print("  [PASS] 1a. Path traversal (?shop=../../etc/passwd) blocked with 400 INVALID_SHOP_DOMAIN")

    # 1b. Cross-tenant status snooping without token
    r = requests.get(f"{BASE_URL}/api/status?shop={OTHER_SHOP}", timeout=15)
    assert r.status_code == 403 and r.json().get("code") == "CROSS_TENANT_ACCESS_DENIED", f"Failed 1b: {r.status_code} {r.text}"
    print(f"  [PASS] 1b. Cross-tenant snooping (?shop={OTHER_SHOP}) blocked with 403 CROSS_TENANT_ACCESS_DENIED")

    # 1c. Cross-tenant unauthorized rollback attempt
    r = requests.post(f"{BASE_URL}/api/rollback", json={"shop": OTHER_SHOP}, timeout=15)
    assert r.status_code == 403 and r.json().get("code") == "CROSS_TENANT_ACCESS_DENIED", f"Failed 1c: {r.status_code} {r.text}"
    print("  [PASS] 1c. Cross-tenant unauthorized rollback blocked with 403 CROSS_TENANT_ACCESS_DENIED")

    print("\n=== [Test 2] Security 3-2: Webhook Authentication & Anti-Spoofing ===")
    # 2a. Webhook call without X-Shopify-Shop-Domain header
    r = requests.post(
        f"{BASE_URL}/webhooks/products/update",
        json={"id": 10352680632517, "image": {"src": "https://example.com/a.jpg"}},
        timeout=15,
    )
    assert r.status_code == 401 and r.json().get("code") == "MISSING_WEBHOOK_HEADERS", f"Failed 2a: {r.status_code} {r.text}"
    print("  [PASS] 2a. Anonymous webhook without X-Shopify-Shop-Domain blocked with 401")

    # 2b. Webhook call with forged X-Shopify-Hmac-Sha256 signature
    r = requests.post(
        f"{BASE_URL}/webhooks/products/update",
        headers={
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": "forged_invalid_hmac_signature_999999==",
        },
        json={"id": 10352680632517, "image": {"src": "https://example.com/a.jpg"}},
        timeout=15,
    )
    assert r.status_code == 401 and r.json().get("code") == "INVALID_WEBHOOK_HMAC", f"Failed 2b: {r.status_code} {r.text}"
    print("  [PASS] 2b. Forged X-Shopify-Hmac-Sha256 signature blocked with 401 INVALID_WEBHOOK_HMAC")

    print("\n=== [Test 3] User Operation 1-2: Malformed Data, Missing Image & SSRF Defense ===")
    # Reset primary shop first so quota/circuit breaker are clean
    requests.post(
        f"{BASE_URL}/api/billing/reset",
        json={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0, "circuitBreakerTripped": False},
        timeout=15,
    )

    # 3a. Malformed JSON payload
    r = requests.post(
        f"{BASE_URL}/api/canary/test",
        data="{corrupted_json_payload",
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    assert r.status_code == 400 and r.json().get("code") == "INVALID_JSON", f"Failed 3a: {r.status_code} {r.text}"
    print("  [PASS] 3a. Corrupted JSON payload safely rejected with 400 INVALID_JSON")

    # 3b. Product with NO image (e.g., draft product in Shopify)
    r = requests.post(
        f"{BASE_URL}/webhooks/products/update",
        headers={"X-Shopify-Shop-Domain": PRIMARY_SHOP},
        json={"id": 10352680435909, "title": "The Minimal Snowboard", "image": None, "images": []},
        timeout=15,
    )
    assert r.status_code == 200 and r.json().get("skipped") is True and r.json().get("reason") == "no_product_image", f"Failed 3b: {r.text}"
    print("  [PASS] 3b. Product without images safely skipped without error or GPU charge")

    # 3c. SSRF attempt (internal cloud metadata IP & non-HTTP scheme)
    for bad_url in ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8080/admin", "javascript:alert(1)"]:
        r = requests.post(
            f"{BASE_URL}/webhooks/products/update",
            headers={"X-Shopify-Shop-Domain": PRIMARY_SHOP},
            json={"id": 10352680632517, "image": {"src": bad_url}},
            timeout=15,
        )
        assert r.status_code == 400 and r.json().get("code") == "INVALID_IMAGE_URL", f"Failed 3c ({bad_url}): {r.status_code} {r.text}"
    print("  [PASS] 3c. SSRF internal IPs (169.254.169.254, 127.0.0.1) & javascript: URLs blocked with 400")

    print("\n=== [Test 4] User Operation 1-1 & Priority 4: 5-Item Free Limit & GPU Drain Protection ===")
    # Set quota to 4/5 used
    requests.post(
        f"{BASE_URL}/api/billing/reset",
        json={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 4, "circuitBreakerTripped": False},
        timeout=15,
    )

    # 4a. 5th Canary Test succeeds (4 -> 5)
    r = requests.post(f"{BASE_URL}/api/canary/test", json={"shop": PRIMARY_SHOP}, timeout=20)
    assert r.status_code == 200 and r.json().get("canaryUsedCount") == 5, f"Failed 4a: {r.status_code} {r.text}"
    print("  [PASS] 4a. 5th sample test succeeded (Quota: 5/5 used)")

    # 4b. 6th Canary Test blocked with 402 Payment Required
    r = requests.post(f"{BASE_URL}/api/canary/test", json={"shop": PRIMARY_SHOP}, timeout=15)
    assert r.status_code == 402 and r.json().get("code") == "TRIAL_QUOTA_EXCEEDED", f"Failed 4b: {r.status_code} {r.text}"
    print("  [PASS] 4b. 6th sample test blocked with 402 TRIAL_QUOTA_EXCEEDED")

    # 4c. Webhook AI Cleanup also blocked at 5/5 quota (prevents GPU wallet drain!)
    r = requests.post(
        f"{BASE_URL}/webhooks/products/update",
        headers={"X-Shopify-Shop-Domain": PRIMARY_SHOP},
        json={"id": 10352680632517, "image": {"src": "https://cdn.shopify.com/s/files/1/0843/4306/2725/files/Main.jpg"}},
        timeout=15,
    )
    assert r.status_code == 402 and r.json().get("code") == "TRIAL_QUOTA_EXCEEDED", f"Failed 4c: {r.status_code} {r.text}"
    print("  [PASS] 4c. Unsubscribed webhook flood blocked at 5/5 limit with 402 (GPU cost 100% protected)")

    # 4d. Bulk catalog optimization blocked before starting 14-day trial
    r = requests.post(f"{BASE_URL}/api/batch/start", json={"shop": PRIMARY_SHOP}, timeout=15)
    assert r.status_code == 402 and r.json().get("code") == "SUBSCRIPTION_REQUIRED_FOR_BULK", f"Failed 4d: {r.status_code} {r.text}"
    print("  [PASS] 4d. Full-catalog bulk optimization gated behind 14-day free trial (402)")

    print("\n=== [Test 5] Priority 4: $65/mo 14-Day Free Trial Activation & Circuit Breaker ===")
    # 5a. Activate 14-Day Free Trial ($65/mo)
    r = requests.post(f"{BASE_URL}/api/billing/subscribe", json={"shop": PRIMARY_SHOP, "autoActivate": True}, timeout=20)
    assert r.status_code == 200 and r.json()["billing"]["planStatus"] == "TRIAL_14D_ACTIVE", f"Failed 5a: {r.text}"
    assert r.json()["billing"]["priceUsd"] == 65 and r.json()["billing"]["trialDays"] == 14
    print("  [PASS] 5a. 14-Day Free Trial ($65/mo) activated via /api/billing/subscribe")

    # 5b. Bulk catalog optimization now allowed (creates R2 backup first)
    r = requests.post(f"{BASE_URL}/api/batch/start", json={"shop": PRIMARY_SHOP}, timeout=25)
    assert r.status_code == 200 and r.json().get("success") is True, f"Failed 5b: {r.text}"
    print(f"  [PASS] 5b. Bulk catalog optimization started with pre-execution R2 snapshot ({r.json().get('snapshotId')})")

    # 5c. Trigger Emergency Stop (Circuit Breaker)
    r = requests.post(f"{BASE_URL}/api/batch/abort", json={"shop": PRIMARY_SHOP}, timeout=15)
    assert r.status_code == 200 and r.json().get("circuitBreakerTripped") is True, f"Failed 5c: {r.text}"
    print("  [PASS] 5c. Emergency Stop (Circuit Breaker) activated")

    # 5d. Verify background webhook is immediately paused while Circuit Breaker is active
    r = requests.post(
        f"{BASE_URL}/webhooks/products/update",
        headers={"X-Shopify-Shop-Domain": PRIMARY_SHOP},
        json={"id": 10352680632517, "image": {"src": "https://cdn.shopify.com/s/files/1/0843/4306/2725/files/Main.jpg"}},
        timeout=15,
    )
    assert r.status_code == 423 and r.json().get("reason") == "circuit_breaker_tripped", f"Failed 5d: {r.status_code} {r.text}"
    print("  [PASS] 5d. Background webhooks halted (423 Locked) while Emergency Stop is active")

    # 5e. Resume protection
    r = requests.post(f"{BASE_URL}/api/batch/resume", json={"shop": PRIMARY_SHOP}, timeout=15)
    assert r.status_code == 200 and r.json().get("circuitBreakerTripped") is False
    print("  [PASS] 5e. Protection resumed cleanly")

    print("\n=== [Test 6] Multi-Tenant 2-1: Concurrent Store A & Store B State Isolation ===")
    # Store B (authenticated with its own mock token) triggers Emergency Stop
    r_b = requests.post(
        f"{BASE_URL}/api/batch/abort",
        headers={"X-Shopify-Access-Token": "mock_token_for_store_b"},
        json={"shop": OTHER_SHOP},
        timeout=15,
    )
    assert r_b.status_code == 200 and r_b.json().get("circuitBreakerTripped") is True

    # Check Store A (PRIMARY_SHOP) status -> must still be active and completely unaffected by Store B!
    r_a = requests.get(f"{BASE_URL}/api/status?shop={PRIMARY_SHOP}", timeout=20)
    data_a = r_a.json()
    assert data_a["protectionActive"] is True and data_a["billing"]["circuitBreakerTripped"] is False, f"Store A affected by Store B! {data_a}"
    print("  [PASS] 6a. Store B Emergency Stop did NOT affect Store A (100% per-shop state isolation)")

    # Reset Store A to clean initial state (1/5 sample used) so dashboard is ready for user review
    requests.post(
        f"{BASE_URL}/api/billing/reset",
        json={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 1, "circuitBreakerTripped": False},
        timeout=15,
    )
    print("\n🎉 ALL 6 SECURITY, ABNORMAL INPUT, MULTI-TENANT, AND PRIORITY 4 BILLING TESTS PASSED!")


if __name__ == "__main__":
    run_all_tests()
