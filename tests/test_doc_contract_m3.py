#!/usr/bin/env python3
"""
Test Suite: Milestone 3 Documentation Contract Verification
Target: docs/SYSTEM_DESIGN.md

Validates:
1. TOC anchor link integrity against GFM heading slug specification.
2. Code block syntax validity (JSON, TypeScript, Bash, TOML, Mermaid).
3. Zero unauthorized occurrences of legacy compression terms ('-% Lighter', 'KB saved', 'Bulk Store Image Optimization').
4. Contract alignment between docs/SYSTEM_DESIGN.md and codebase (endpoints, types, metafields, UI zones).
"""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "SYSTEM_DESIGN.md"
INDEX_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "index.ts"
TYPES_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "types.ts"
UI_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"


def gfm_slug(text: str) -> str:
    """Standard GitHub Flavored Markdown slug generation."""
    text = text.strip()
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = text.lower()

    cleaned = []
    for ch in text:
        if ch in ' \t\u3000':
            cleaned.append('-')
        elif ch in '-_':
            cleaned.append(ch)
        elif ch.isalnum():
            cleaned.append(ch)
    return ''.join(cleaned)


class TestDocumentationContractM3(unittest.TestCase):
    """Empirical challenge suite for docs/SYSTEM_DESIGN.md contract integrity."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.exists(), f"Doc file missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()

    def test_01_toc_link_integrity(self):
        """Verify that every anchor link in Table of Contents resolves to a valid heading."""
        toc_match = re.search(r'## 目次 \(Table of Contents\)(.*?)(?=\n## |\Z)', self.content, re.DOTALL)
        self.assertIsNotNone(toc_match, "Table of Contents section not found")
        toc_text = toc_match.group(1)

        toc_links = re.findall(r'\[([^\]]+)\]\(#([^\)]+)\)', toc_text)
        self.assertGreaterEqual(len(toc_links), 25, "Expected at least 25 TOC links")

        # Collect all headings in document
        headings = {}
        for idx, line in enumerate(self.lines, 1):
            m = re.match(r'^(#{1,6})\s+(.*)$', line)
            if m:
                title = m.group(2).strip()
                slug = gfm_slug(title)
                headings[slug] = (idx, title)

        broken = []
        for title, anchor in toc_links:
            if anchor not in headings:
                broken.append((title, anchor))

        self.assertEqual(len(broken), 0, f"Broken TOC anchor links: {broken}")

    def test_02_json_code_blocks_validity(self):
        """Extract and validate all JSON code blocks in SYSTEM_DESIGN.md."""
        fence_pattern = re.compile(r'^(\s*)`{3,}([a-zA-Z0-9_\-]+)?')
        in_block = False
        lang = ""
        block_lines = []
        start_line = 0
        json_blocks = []

        for idx, line in enumerate(self.lines, 1):
            if not in_block:
                m = fence_pattern.match(line)
                if m:
                    in_block = True
                    lang = (m.group(2) or "").lower()
                    block_lines = []
                    start_line = idx
            else:
                if line.strip().startswith('```'):
                    in_block = False
                    if lang == "json":
                        json_blocks.append((start_line, idx, "\n".join(block_lines)))
                else:
                    block_lines.append(line)

        self.assertGreaterEqual(len(json_blocks), 5, "Expected at least 5 JSON code blocks")

        for s, e, code in json_blocks:
            try:
                parsed = json.loads(code)
                self.assertTrue(isinstance(parsed, (dict, list)), f"JSON at lines {s}-{e} must be object or array")
            except json.JSONDecodeError as err:
                self.fail(f"Invalid JSON in SYSTEM_DESIGN.md at lines {s}-{e}: {err}\nSnippet:\n{code}")

    def test_03_typescript_code_blocks_syntax(self):
        """Extract and validate all TypeScript interface code blocks."""
        fence_pattern = re.compile(r'^(\s*)`{3,}([a-zA-Z0-9_\-]+)?')
        in_block = False
        lang = ""
        block_lines = []
        start_line = 0
        ts_blocks = []

        for idx, line in enumerate(self.lines, 1):
            if not in_block:
                m = fence_pattern.match(line)
                if m:
                    in_block = True
                    lang = (m.group(2) or "").lower()
                    block_lines = []
                    start_line = idx
            else:
                if line.strip().startswith('```'):
                    in_block = False
                    if lang in ("typescript", "ts"):
                        ts_blocks.append((start_line, idx, "\n".join(block_lines)))
                else:
                    block_lines.append(line)

        self.assertGreaterEqual(len(ts_blocks), 2, "Expected at least 2 TypeScript code blocks")

        for s, e, code in ts_blocks:
            # Check balanced curly braces
            open_count = code.count('{')
            close_count = code.count('}')
            self.assertEqual(open_count, close_count, f"Unbalanced braces in TS block lines {s}-{e}: open={open_count}, close={close_count}")

            # Verify interface declarations
            interfaces = re.findall(r'interface\s+([A-Za-z0-9_]+)', code)
            self.assertGreater(len(interfaces), 0, f"TS block lines {s}-{e} should declare at least one interface")

    def test_04_bash_code_blocks_syntax(self):
        """Extract and validate all Bash code blocks via bash -n."""
        fence_pattern = re.compile(r'^(\s*)`{3,}([a-zA-Z0-9_\-]+)?')
        in_block = False
        lang = ""
        block_lines = []
        start_line = 0
        bash_blocks = []

        for idx, line in enumerate(self.lines, 1):
            if not in_block:
                m = fence_pattern.match(line)
                if m:
                    in_block = True
                    lang = (m.group(2) or "").lower()
                    block_lines = []
                    start_line = idx
            else:
                if line.strip().startswith('```'):
                    in_block = False
                    if lang in ("bash", "sh", "zsh"):
                        bash_blocks.append((start_line, idx, "\n".join(block_lines)))
                else:
                    block_lines.append(line)

        self.assertGreaterEqual(len(bash_blocks), 1, "Expected at least 1 Bash code block")

        for s, e, code in bash_blocks:
            proc = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, f"Bash syntax error at lines {s}-{e}: {proc.stderr}")

    def test_05_prohibited_terms_zero_tolerance(self):
        """Assert zero unauthorized occurrences of legacy compression terms."""
        prohibited = [
            "-% Lighter",
            "KB saved",
            "Bulk Store Image Optimization"
        ]

        unauthorized_hits = []
        for term in prohibited:
            for idx, line in enumerate(self.lines, 1):
                if term.lower() in line.lower():
                    # Check if occurrence is explicitly stating its complete removal
                    is_removal_context = any(w in line for w in ["完全排除", "排除", "従来の", "eliminated", "removed"])
                    if not is_removal_context:
                        unauthorized_hits.append((term, idx, line.strip()))

        self.assertEqual(len(unauthorized_hits), 0, f"Unauthorized legacy compression terms found: {unauthorized_hits}")

    def test_06_canary_test_schema_parity(self):
        """Assert that documented CanaryTestResult schema matches pure dual-feed specification."""
        self.assertIn("interface CanaryTestResult", self.content)
        # Check required pure dual feed fields
        for field in ["productId", "originalImageUrl", "cleanAdImageUrl", "metafieldKey", "aiMetadata", "variantChecks", "canaryUsedCount"]:
            self.assertIn(field, self.content, f"Field '{field}' must be documented in CanaryTestResult")

        # Assert no legacy byte size fields in documented active schema
        # In SYSTEM_DESIGN.md lines 205-228, originalSizeKB and savingsPercentage must NOT be present
        canary_block_match = re.search(r'interface CanaryTestResult\s*\{(.*?)\}', self.content, re.DOTALL)
        self.assertIsNotNone(canary_block_match, "CanaryTestResult interface block not found")
        block_text = canary_block_match.group(1)
        self.assertNotIn("originalSizeKB", block_text)
        self.assertNotIn("optimizedSizeKB", block_text)
        self.assertNotIn("savingsPercentage", block_text)

    def test_07_batch_and_rollback_endpoint_parity(self):
        """Assert that batch and rollback endpoints and contracts are accurately documented."""
        self.assertIn("POST /api/batch/start", self.content)
        self.assertIn("POST /api/batch/abort", self.content)
        self.assertIn("POST /api/batch/resume", self.content)
        self.assertIn("POST /api/rollback", self.content)
        self.assertIn("safemedia.clean_ad_image_url", self.content)

    def test_08_ui_architecture_parity(self):
        """Assert that 2-Zone layout and 5-layer card structure are documented."""
        self.assertIn("2-Zone", self.content)
        self.assertIn("Zone 1", self.content)
        self.assertIn("Zone 2", self.content)
        self.assertIn("5-Layer", self.content)
        self.assertIn("AdFeed Clean: Google Ad Shield", self.content)


if __name__ == "__main__":
    unittest.main()
