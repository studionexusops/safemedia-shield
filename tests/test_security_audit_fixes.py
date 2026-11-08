"""
tests/test_security_audit_fixes.py
Verification suite for Post-Phase 3 Security & Architecture Audit Fixes (Risks 1 to 5).
Ensures BOLA mitigation, billing confirmation bypass prevention, OAuth fail-closed handling,
feed preview access control, and memory cache eviction policies.
"""

import unittest
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "index.ts"
UI_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"


class TestSecurityAuditFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX_TS_PATH, "r", encoding="utf-8") as f:
            cls.index_ts = f.read()
        with open(UI_TS_PATH, "r", encoding="utf-8") as f:
            cls.ui_ts = f.read()

    # =========================================================================
    # Risk 1: BOLA Mitigation in /api/admin/purge-metafields
    # =========================================================================

    def test_risk1_purge_route_not_exempted_from_auth_guard(self):
        """Risk 1: Verify isPurgeRoute is removed from unauthenticated route bypass list."""
        guard_match = re.search(
            r"if\s*\(!isWebhookRoute\s*&&.*?&&.*?&&.*?\)",
            self.index_ts,
        )
        self.assertTrue(guard_match, "Auth guard condition not found in index.ts")
        guard_condition = guard_match.group(0)
        self.assertNotIn(
            "isPurgeRoute",
            guard_condition,
            "Security vulnerability: isPurgeRoute must NOT bypass common authentication guard!",
        )

    def test_risk1_purge_endpoint_requires_admin_secret_or_tenant_match(self):
        """Risk 1: Verify /api/admin/purge-metafields enforces tenant session match or admin secret."""
        purge_handler_match = re.search(
            r'url\.pathname === "/api/admin/purge-metafields"[\s\S]*?\{([\s\S]*?)(?=// \d|\n\s*if\s*\(url\.pathname)',
            self.index_ts,
        )
        self.assertTrue(purge_handler_match, "purge-metafields handler not found")
        purge_code = purge_handler_match.group(1)

        self.assertIn(
            "isTenantAuthorized",
            purge_code,
            "purge-metafields must check isTenantAuthorized to prevent cross-tenant BOLA",
        )
        self.assertIn(
            "isAdminAuthorized",
            purge_code,
            "purge-metafields must check isAdminAuthorized for administrative operations",
        )
        self.assertIn(
            "PURGE_UNAUTHORIZED",
            purge_code,
            "purge-metafields must return 403 PURGE_UNAUTHORIZED when authorization fails",
        )

    # =========================================================================
    # Risk 2: Billing Confirmation Bypass Prevention (/api/billing/confirm)
    # =========================================================================

    def test_risk2_billing_confirmed_flag_restricted_to_test_environments(self):
        """Risk 2: Verify billing_confirmed=1 query parameter cannot approve billing in production."""
        confirm_handler_match = re.search(
            r'if\s*\(\s*\(url\.pathname === "/api/billing/confirm"[\s\S]*?\{([\s\S]*?)(?=// \d|\n\s*if\s*\(url\.pathname)',
            self.index_ts,
        )
        self.assertTrue(confirm_handler_match, "billing/confirm handler not found")
        confirm_code = confirm_handler_match.group(1)

        # Ensure isTestEnv guard is applied before accepting billingConfirmed == "1"
        self.assertIn(
            "isTestEnv",
            confirm_code,
            "billing/confirm must define isTestEnv to restrict mock approval",
        )
        bypass_pattern = re.search(
            r'else\s*if\s*\(\s*billingConfirmed\s*===\s*"1"\s*&&\s*isTestEnv\s*\)',
            confirm_code,
        )
        self.assertTrue(
            bypass_pattern,
            "billingConfirmed === '1' must be gated strictly by && isTestEnv!",
        )

    # =========================================================================
    # Risk 3: OAuth Dummy Secret Fallback Fail-Closed
    # =========================================================================

    def test_risk3_oauth_fails_closed_when_secret_missing(self):
        """Risk 3: Verify OAuth token exchange fails closed if server secret is missing outside test environment."""
        oauth_match = re.search(
            r'url\.pathname === "/api/auth/callback"[\s\S]*?\{([\s\S]*?)(?=// \d|\n\s*if\s*\(url\.pathname|\n\s*const requestedShop)',
            self.index_ts,
        )
        self.assertTrue(oauth_match, "auth/callback handler not found")
        oauth_code = oauth_match.group(1)

        self.assertIn(
            "OAUTH_SECRET_NOT_CONFIGURED",
            oauth_code,
            "OAuth must fail closed with OAUTH_SECRET_NOT_CONFIGURED when secret is missing",
        )
        self.assertIn(
            "isMockOAuthTest",
            oauth_code,
            "Mock OAuth token generation must be strictly gated by isMockOAuthTest",
        )

    # =========================================================================
    # Risk 4: Feed Preview Public Scraping Protection
    # =========================================================================

    def test_risk4_feed_preview_access_control(self):
        """Risk 4: Verify feed-preview enforces isFeedAccessAuthorized and token validation."""
        self.assertIn(
            "export async function generateFeedToken",
            self.index_ts,
            "generateFeedToken must be exported in index.ts",
        )
        self.assertIn(
            "export async function isFeedAccessAuthorized",
            self.index_ts,
            "isFeedAccessAuthorized must be exported in index.ts",
        )

        feed_handler_match = re.search(
            r'if\s*\(\s*\(url\.pathname === "/api/feed-preview"[\s\S]*?\{([\s\S]*?)(?=// \d|\n\s*if\s*\(url\.pathname)',
            self.index_ts,
        )
        self.assertTrue(feed_handler_match, "feed-preview handler not found")
        feed_code = feed_handler_match.group(1)

        self.assertIn(
            "isFeedAccessAuthorized",
            feed_code,
            "feed-preview must verify authorization via isFeedAccessAuthorized",
        )
        self.assertIn(
            "FEED_UNAUTHORIZED",
            feed_code,
            "feed-preview must reject unauthorized crawling with FEED_UNAUTHORIZED",
        )

    def test_risk4_ui_feed_token_integration(self):
        """Risk 4: Verify ui.ts renderDashboardHtml passes and includes feedToken in feed preview links."""
        self.assertIn(
            "feedToken: string =",
            self.ui_ts,
            "renderDashboardHtml in ui.ts must accept feedToken parameter",
        )
        self.assertIn(
            "feedTokenQuery",
            self.ui_ts,
            "ui.ts must format feedTokenQuery",
        )
        self.assertIn(
            "href=\"/api/feed-preview.xml?shop=${shop}${feedTokenQuery}\"",
            self.ui_ts,
            "ui.ts RSS feed link must include feedTokenQuery",
        )

    # =========================================================================
    # Risk 5: Memory Cache Eviction Policy
    # =========================================================================

    def test_risk5_purge_expired_memory_caches_implemented_and_called(self):
        """Risk 5: Verify purgeExpiredMemoryCaches exists and is triggered on cache operations."""
        self.assertIn(
            "function purgeExpiredMemoryCaches",
            self.index_ts,
            "purgeExpiredMemoryCaches function must be defined in index.ts",
        )
        self.assertIn(
            "MAX_MEMORY_MAP_ENTRIES",
            self.index_ts,
            "MAX_MEMORY_MAP_ENTRIES limit must be configured in index.ts",
        )

        # Verify it is called inside core lock & webhook functions
        in_flight_fn = re.search(
            r"async function acquireInFlightLock[\s\S]*?Promise<boolean>\s*\{([\s\S]*?)\n\}",
            self.index_ts,
        )
        self.assertTrue(in_flight_fn, "acquireInFlightLock body not found")
        self.assertIn(
            "purgeExpiredMemoryCaches()",
            in_flight_fn.group(1),
            "acquireInFlightLock must invoke purgeExpiredMemoryCaches()",
        )

        gpu_slot_fn = re.search(
            r"async function acquireGpuSlot[\s\S]*?Promise<\{[\s\S]*?\}\>\s*\{([\s\S]*?)\n\}",
            self.index_ts,
        )
        self.assertTrue(gpu_slot_fn, "acquireGpuSlot body not found")
        self.assertIn(
            "purgeExpiredMemoryCaches()",
            gpu_slot_fn.group(1),
            "acquireGpuSlot must invoke purgeExpiredMemoryCaches()",
        )

        webhook_processed_fn = re.search(
            r"async function markWebhookProcessed[\s\S]*?Promise<void>\s*\{([\s\S]*?)\n\}",
            self.index_ts,
        )
        self.assertTrue(webhook_processed_fn, "markWebhookProcessed body not found")
        self.assertIn(
            "purgeExpiredMemoryCaches()",
            webhook_processed_fn.group(1),
            "markWebhookProcessed must invoke purgeExpiredMemoryCaches()",
        )


if __name__ == "__main__":
    unittest.main()
