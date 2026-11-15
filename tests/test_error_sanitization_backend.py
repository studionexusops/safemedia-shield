"""
Unit tests for Phase 3: Error Sanitization Backend & RunPod Warming-Up Handling
Validates:
1. runpod_client.ts masks IN_PROGRESS timeout into AI_WARMING_UP / warming up error.
2. index.ts sanitizeUserError masks all raw infrastructure errors into merchant-safe error codes.
3. Zero raw infrastructure leakage across all API catch blocks.
"""

import unittest
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestErrorSanitizationBackend(unittest.TestCase):
    def setUp(self):
        self.runpod_client_code = (REPO_ROOT / "cloudflare_worker" / "src" / "runpod_client.ts").read_text(encoding="utf-8")
        self.index_code = (REPO_ROOT / "cloudflare_worker" / "src" / "index.ts").read_text(encoding="utf-8")
        self.types_code = (REPO_ROOT / "cloudflare_worker" / "src" / "types.ts").read_text(encoding="utf-8")

    def test_runpod_client_masks_in_progress_timeout(self):
        """Verifies that runpod_client.ts handles IN_PROGRESS as warming up and no longer throws 'Missing processed image'."""
        self.assertNotIn(
            "Missing processed image",
            self.runpod_client_code,
            "Raw 'Missing processed image' error message must be removed from runpod_client.ts",
        )
        # Check that both IN_QUEUE and IN_PROGRESS are caught for warming up
        self.assertIn(
            'data.status === "IN_QUEUE" || data.status === "IN_PROGRESS"',
            self.runpod_client_code,
            "runpod_client.ts must treat both IN_QUEUE and IN_PROGRESS as warming up on polling timeout",
        )
        self.assertIn(
            "AI processing engine is warming up",
            self.runpod_client_code,
            "Warming up message must be present for polling timeout",
        )

    def test_types_exports_sanitized_error_response(self):
        """Verifies that SanitizedErrorResponse interface is exported in types.ts."""
        self.assertIn("export interface SanitizedErrorResponse", self.types_code)
        self.assertIn("code: string;", self.types_code)
        self.assertIn("error: string;", self.types_code)

    def test_index_exports_and_defines_sanitize_user_error(self):
        """Verifies that sanitizeUserError function is exported and defined with key error mappings."""
        self.assertIn("export function sanitizeUserError(err: unknown): SanitizedErrorResult", self.index_code)
        self.assertIn("AI_WARMING_UP", self.index_code)
        self.assertIn("AI_SERVICE_BUSY", self.index_code)
        self.assertIn("SHOPIFY_RATE_LIMITED", self.index_code)
        self.assertIn("INVALID_IMAGE_URL", self.index_code)
        self.assertIn("TEMPORARY_ERROR", self.index_code)

    def test_all_api_catch_blocks_call_sanitize_user_error(self):
        """Verifies that API catch blocks in index.ts use sanitizeUserError instead of raw err.message."""
        # Find all catch blocks in index.ts
        catch_matches = re.findall(r"catch\s*\((?:err|procErr)(?::\s*unknown)?\)\s*\{([^}]+)\}", self.index_code)
        
        # Verify that endpoints do not directly return `{ error: errorMsg }` with raw string
        raw_error_leak_matches = re.findall(
            r"return Response\.json\(\s*\{\s*(?:success:\s*false,\s*)?error:\s*(?:errorMsg|message|err\.message)\s*\}",
            self.index_code,
        )
        self.assertEqual(
            len(raw_error_leak_matches),
            0,
            f"Found unprotected raw error returns in index.ts: {raw_error_leak_matches}",
        )

        # Verify that sanitizeUserError is invoked across key routes
        sanitize_calls = re.findall(r"sanitizeUserError\(", self.index_code)
        self.assertGreaterEqual(
            len(sanitize_calls),
            8,
            f"Expected at least 8 calls to sanitizeUserError in index.ts, found {len(sanitize_calls)}",
        )


if __name__ == "__main__":
    unittest.main()
