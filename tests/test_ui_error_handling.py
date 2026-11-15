"""
Unit tests for Phase 4: Frontend UI Error Masking & Sanitization
Validates:
1. runCanaryTest handles AI_WARMING_UP, AI_SERVICE_BUSY, IN_PROGRESS without raw error leakage.
2. Fallback in runCanaryTest displays safe, merchant-friendly error message instead of raw API strings.
3. showNotification error sanitizer prevents raw JSON or stack traces from rendering in UI toasts.
4. Catch block in runCanaryTest avoids raw err.message display.
"""

import unittest
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestUiErrorHandling(unittest.TestCase):
    def setUp(self):
        self.ui_code = (REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts").read_text(encoding="utf-8")

    def test_run_canary_test_evaluates_standard_error_codes(self):
        """Verifies that runCanaryTest inspects data.code for AI_WARMING_UP and AI_SERVICE_BUSY."""
        self.assertIn("dataCode === 'AI_WARMING_UP'", self.ui_code)
        self.assertIn("dataCode === 'AI_SERVICE_BUSY'", self.ui_code)
        self.assertIn("dataCode === 'INVALID_IMAGE_URL'", self.ui_code)

    def test_run_canary_test_handles_in_progress_and_missing_image(self):
        """Verifies that runCanaryTest matches in_progress and missing processed image as warming up."""
        self.assertIn("rawLower.includes('in_progress')", self.ui_code)
        self.assertIn("rawLower.includes('missing processed image')", self.ui_code)

    def test_run_canary_test_uses_step1_err_temporary_fallback(self):
        """Verifies that runCanaryTest falls back to step1_err_temporary instead of rawError."""
        # Find the else branch in runCanaryTest error handler
        self.assertIn("displayMsg = t('step1_err_temporary');", self.ui_code)
        # Ensure catch block does not interpolate err.message directly into red div
        self.assertNotIn("Error: ' + err.message", self.ui_code)
        self.assertIn("t('step1_err_temporary')", self.ui_code)

    def test_show_notification_has_sanitizer(self):
        """Verifies that showNotification intercepts error messages with sanitizeUiErrorMessage."""
        self.assertIn("function sanitizeUiErrorMessage", self.ui_code)
        self.assertIn("message = sanitizeUiErrorMessage(message);", self.ui_code)

    def test_i18n_has_parity_for_new_error_keys(self):
        """Verifies that both English and Japanese have step1_err_temporary and step1_err_invalid_image."""
        self.assertIn("step1_err_temporary:", self.ui_code)
        self.assertIn("step1_err_invalid_image:", self.ui_code)


if __name__ == "__main__":
    unittest.main()
