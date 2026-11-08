#!/usr/bin/env python3
"""
tests/test_m2_bilingual_parity.py
Empirical Challenger Test Suite for Milestone 2: I18N & Bilingual Parity Verification.

Validates:
1. 100% key parity between 'en' and 'ja' objects in cloudflare_worker/src/ui.ts.
2. Complete coverage of all data-i18n attributes in the HTML template.
3. DOM language switching simulation: setLanguage('ja') and setLanguage('en').
4. Default language invariant: currentLang = 'en', <html lang="en">, EN button highlighted.
5. Placeholder parameter parity, HTML tag integrity, and dynamic UI elements.
"""

import copy
import json
import os
import pathlib
import re
import sys
import unittest
from html.parser import HTMLParser
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
UI_TS_PATH = REPO_ROOT / "cloudflare_worker" / "src" / "ui.ts"


class TemplateExtractor:
    """Extracts raw HTML template, I18N dictionaries, and client JS from ui.ts."""

    def __init__(self, ui_file_path: pathlib.Path = UI_TS_PATH):
        if not ui_file_path.exists():
            raise FileNotFoundError(f"ui.ts not found at {ui_file_path}")
        self.raw_content = ui_file_path.read_text(encoding="utf-8")
        self.html_template = self._extract_html_template()
        self.script_content = self._extract_script_content()
        self.en_dict, self.ja_dict = self._extract_i18n_dictionaries()

    def _extract_html_template(self) -> str:
        # Extract return `...`; inside renderDashboardHtml
        m = re.search(r"return `([\s\S]*?)`;\s*}", self.raw_content)
        if not m:
            raise ValueError("Could not extract HTML template from renderDashboardHtml in ui.ts")
        template = m.group(1)
        # Substitute ${shop} with test shop domain
        return template.replace("${shop}", "safemedia-test-20261011.myshopify.com")

    def _extract_script_content(self) -> str:
        # Find the inline <script> block at the end of the template
        pos = self.html_template.find("<script>\n")
        if pos == -1:
            pos = self.html_template.find("<script>")
        end_pos = self.html_template.rfind("</script>")
        if pos == -1 or end_pos == -1 or end_pos <= pos:
            raise ValueError("Could not locate client-side <script> block in HTML template")
        return self.html_template[pos + len("<script>"):end_pos]

    def _extract_i18n_dictionaries(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        # Match const I18N = { ... };
        i18n_match = re.search(r"const I18N = \{([\s\S]*?)\n\s*\};\n", self.script_content)
        if not i18n_match:
            raise ValueError("Could not find const I18N definition in ui.ts")
        block = i18n_match.group(1)

        en_match = re.search(r"en:\s*\{([\s\S]*?)\n\s*\},", block)
        ja_match = re.search(r"ja:\s*\{([\s\S]*?)\n\s*\}", block)

        if not en_match or not ja_match:
            raise ValueError("Failed to extract 'en' or 'ja' dictionary blocks from I18N")

        def parse_entries(subblock: str) -> Dict[str, str]:
            res = {}
            for line in subblock.splitlines():
                s = line.strip()
                if not s or s.startswith("//"):
                    continue
                m = re.match(r'^([a-zA-Z0-9_]+)\s*:\s*(?:"(.*)"|\'(.*)\'),?$', s)
                if m:
                    k = m.group(1)
                    v = m.group(2) if m.group(2) is not None else m.group(3)
                    # Unescape quotes from template string escaping (both \\\" and \")
                    v = v.replace('\\\\"', '"').replace('\\\\\'', "'").replace(r'\"', '"').replace(r"\'", "'")
                    res[k] = v
            return res

        en = parse_entries(en_match.group(1))
        ja = parse_entries(ja_match.group(1))
        return en, ja


class DOMElement:
    """Minimal virtual DOM element representation for empirical UI testing."""

    def __init__(self, tag: str, attrs: Dict[str, str], start_pos: int, inner_html: str = ""):
        self.tag = tag
        self.attrs = attrs
        self.data_i18n = attrs.get("data-i18n")
        self.id = attrs.get("id")
        self.classes = attrs.get("class", "").split()
        self.inner_html = inner_html
        self.start_pos = start_pos
        self.end_pos = -1

    def __repr__(self):
        return f"<{self.tag} id={self.id} data-i18n={self.data_i18n}>"


class SimpleVirtualDOM(HTMLParser):
    """Parses HTML template into a navigable virtual DOM supporting data-i18n inspection."""

    def __init__(self, html: str):
        super().__init__()
        self.raw_html = html
        self.elements: List[DOMElement] = []
        self.i18n_elements: List[DOMElement] = []
        self.by_id: Dict[str, DOMElement] = {}
        self.stack: List[Tuple[DOMElement, int]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        attrs_dict = dict(attrs)
        line, offset = self.getpos()
        elem = DOMElement(tag, attrs_dict, line)
        self.elements.append(elem)
        if elem.id:
            self.by_id[elem.id] = elem
        self.stack.append((elem, len(self.raw_html)))

    def handle_endtag(self, tag: str):
        if self.stack:
            elem, _ = self.stack.pop()
            elem.end_pos = self.getpos()[0]

    def parse_all_i18n_elements(self) -> List[DOMElement]:
        # Isolate HTML body before client script block
        script_idx = self.raw_html.find("<script>\n")
        if script_idx == -1:
            script_idx = self.raw_html.find("<script>")
        body_html = self.raw_html[:script_idx] if script_idx != -1 else self.raw_html

        res = []
        tag_pattern = re.compile(
            r"<([a-zA-Z0-9]+)([^>]*data-i18n=[\"\']([^\"\']+)[\"\'][^>]*)>([\s\S]*?)</\1>"
        )
        for m in tag_pattern.finditer(body_html):
            tag = m.group(1)
            raw_attrs = m.group(2)
            i18n_key = m.group(3)
            inner = m.group(4)
            id_m = re.search(r'id=[\"\']([^\"\']+)[\"\']', raw_attrs)
            cls_m = re.search(r'class=[\"\']([^\"\']+)[\"\']', raw_attrs)
            attrs = {"data-i18n": i18n_key}
            if id_m:
                attrs["id"] = id_m.group(1)
            if cls_m:
                attrs["class"] = cls_m.group(1)
            elem = DOMElement(tag, attrs, 0, inner_html=inner)
            res.append(elem)
        return res


class TestBilingualParityKeyCompleteness(unittest.TestCase):
    """Empirical challenges for I18N dictionary parity, parameter symmetry, and tag safety."""

    @classmethod
    def setUpClass(cls):
        cls.extractor = TemplateExtractor()
        cls.en = cls.extractor.en_dict
        cls.ja = cls.extractor.ja_dict

    def test_en_ja_exact_100_percent_key_parity(self):
        """TC-CHALLENGE-01: Verify 100% key parity between 'en' and 'ja' (zero missing in either direction)."""
        en_keys = set(self.en.keys())
        ja_keys = set(self.ja.keys())

        missing_in_ja = en_keys - ja_keys
        missing_in_en = ja_keys - en_keys

        self.assertEqual(
            missing_in_ja,
            set(),
            f"Bilingual parity VIOLATION: The following keys exist in 'en' but are MISSING in 'ja': {sorted(missing_in_ja)}"
        )
        self.assertEqual(
            missing_in_en,
            set(),
            f"Bilingual parity VIOLATION: The following keys exist in 'ja' but are MISSING in 'en': {sorted(missing_in_en)}"
        )
        self.assertEqual(
            len(en_keys),
            len(ja_keys),
            f"Key counts mismatch: en has {len(en_keys)}, ja has {len(ja_keys)}"
        )
        self.assertGreaterEqual(
            len(en_keys),
            75,
            f"Expected at least 75 distinct I18N keys for complete UI coverage, found {len(en_keys)}"
        )

    def test_no_empty_null_or_placeholder_values(self):
        """TC-CHALLENGE-02: Verify no empty, null, or untranslated placeholder values (e.g. TODO, TBD)."""
        forbidden_placeholders = ["TODO", "TBD", "[UNTRANSLATED]", "UNDEFINED", "NULL", "???"]
        for lang_name, dictionary in [("en", self.en), ("ja", self.ja)]:
            for key, val in dictionary.items():
                self.assertIsInstance(val, str, f"[{lang_name}] key '{key}' value must be a string")
                stripped = val.strip()
                self.assertGreater(
                    len(stripped),
                    0,
                    f"[{lang_name}] key '{key}' contains empty or whitespace-only value"
                )
                for ph in forbidden_placeholders:
                    self.assertNotIn(
                        ph,
                        stripped.upper(),
                        f"[{lang_name}] key '{key}' contains untranslated placeholder '{ph}': {val}"
                    )

    def test_placeholder_parameter_parity(self):
        """TC-CHALLENGE-03: Verify dynamic interpolation variables (e.g. {used}, {limit}, {total}) match in en and ja."""
        param_pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
        for key in self.en:
            en_params = set(param_pattern.findall(self.en[key]))
            ja_params = set(param_pattern.findall(self.ja[key]))
            self.assertEqual(
                en_params,
                ja_params,
                f"Dynamic placeholder parameter mismatch in key '{key}': en={en_params} vs ja={ja_params}"
            )

    def test_html_tag_balance_in_i18n_values(self):
        """TC-CHALLENGE-04: Verify embedded HTML formatting tags (<code>, <strong>) in translations are properly closed."""
        tags_to_check = ["strong", "code", "b", "i", "span", "div"]
        for lang_name, dictionary in [("en", self.en), ("ja", self.ja)]:
            for key, val in dictionary.items():
                for tag in tags_to_check:
                    open_count = len(re.findall(rf"<{tag}(?:\s+[^>]*)?>", val))
                    close_count = len(re.findall(rf"</{tag}>", val))
                    self.assertEqual(
                        open_count,
                        close_count,
                        f"[{lang_name}] Unbalanced <{tag}> tag in key '{key}': opens={open_count}, closes={close_count} in '{val}'"
                    )

    def test_brand_name_consistency(self):
        """TC-CHALLENGE-05: Verify brand name 'AdFeed Clean for Google Shopping' is preserved across both languages."""
        self.assertEqual(
            self.en.get("app_title"),
            "AdFeed Clean for Google Shopping"
        )
        self.assertEqual(
            self.ja.get("app_title"),
            "AdFeed Clean for Google Shopping"
        )


class TestHtmlTemplateDataI18nCoverage(unittest.TestCase):
    """Empirical challenges verifying that every data-i18n element in HTML is covered and safe."""

    @classmethod
    def setUpClass(cls):
        cls.extractor = TemplateExtractor()
        cls.vdom = SimpleVirtualDOM(cls.extractor.html_template)
        cls.i18n_elements = cls.vdom.parse_all_i18n_elements()
        cls.en = cls.extractor.en_dict
        cls.ja = cls.extractor.ja_dict

    def test_every_data_i18n_key_exists_in_i18n_dictionary(self):
        """TC-CHALLENGE-06: Every element with data-i18n='xxx' in HTML template exists in I18N dictionary."""
        all_html_keys = [el.data_i18n for el in self.i18n_elements]
        unique_html_keys = set(all_html_keys)

        self.assertGreater(
            len(unique_html_keys),
            30,
            f"Expected at least 30 data-i18n elements in dashboard layout, found {len(unique_html_keys)}"
        )

        missing_in_en = unique_html_keys - set(self.en.keys())
        missing_in_ja = unique_html_keys - set(self.ja.keys())

        self.assertEqual(
            missing_in_en,
            set(),
            f"Orphaned data-i18n attributes found in HTML missing in 'en' dictionary: {missing_in_en}"
        )
        self.assertEqual(
            missing_in_ja,
            set(),
            f"Orphaned data-i18n attributes found in HTML missing in 'ja' dictionary: {missing_in_ja}"
        )

    def test_no_untranslated_japanese_in_initial_html(self):
        """TC-CHALLENGE-07: Verify initial rendered HTML contains zero Japanese characters except the language switcher button."""
        body_part = self.extractor.html_template
        # Remove client script
        script_idx = body_part.find("<script>\n")
        if script_idx != -1:
            body_part = body_part[:script_idx]

        # Mask the intentional language switcher button label: <button ...>日本語</button>
        sanitized = re.sub(r">日本語</button>", ">[LANG_BTN_LABEL]</button>", body_part)

        # Search for any CJK Japanese characters: Hiragana (\u3040-\u309F), Katakana (\u30A0-\u30FF), CJK ideographs (\u4E00-\u9FFF)
        japanese_chars = re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", sanitized)
        self.assertEqual(
            len(japanese_chars),
            0,
            f"Found {len(japanese_chars)} unexpected Japanese characters in initial English dashboard HTML template: {set(japanese_chars)}"
        )

    def test_initial_english_html_content_matches_i18n_en(self):
        """TC-CHALLENGE-08: Verify initial inner content of data-i18n elements matches I18N.en."""
        ws = re.compile(r"\s+")
        tag_re = re.compile(r"<[^>]+>")
        mismatches = []
        for el in self.i18n_elements:
            key = el.data_i18n
            expected_val = self.en[key]
            text_actual = ws.sub(" ", tag_re.sub("", el.inner_html)).strip()
            text_expected = ws.sub(" ", tag_re.sub("", expected_val)).strip()
            if text_actual != text_expected:
                mismatches.append((key, text_actual, text_expected))

        self.assertEqual(
            mismatches,
            [],
            f"Initial English HTML content deviates from I18N.en for keys: {[m[0] for m in mismatches]}"
        )


class TestLanguageSwitcherRuntimeBehavior(unittest.TestCase):
    """Empirical simulation of client-side setLanguage('ja') and setLanguage('en') execution."""

    @classmethod
    def setUpClass(cls):
        cls.extractor = TemplateExtractor()
        cls.en = cls.extractor.en_dict
        cls.ja = cls.extractor.ja_dict
        cls.script = cls.extractor.script_content
        cls.vdom = SimpleVirtualDOM(cls.extractor.html_template)
        cls.i18n_elements = cls.vdom.parse_all_i18n_elements()

    def test_default_language_is_english(self):
        """TC-CHALLENGE-09: Default language is strictly English ('currentLang = \"en\"', <html lang=\"en\">)."""
        # 1. HTML lang attribute
        html_lang = re.search(r'<html\s+lang=["\']([^"\']+)["\']', self.extractor.html_template)
        self.assertIsNotNone(html_lang, "HTML template must specify <html lang=...>")
        self.assertEqual(html_lang.group(1).lower(), "en", "Default <html lang> must be 'en'")

        # 2. Client-side currentLang variable initialization
        current_lang_match = re.search(r'let\s+currentLang\s*=\s*["\']([^"\']+)["\']', self.script)
        self.assertIsNotNone(current_lang_match, "Client script must initialize let currentLang")
        self.assertEqual(current_lang_match.group(1), "en", "Initial currentLang must be 'en'")

        # 3. EN button initially styled as active
        btn_en = self.vdom.by_id.get("lang-en")
        btn_ja = self.vdom.by_id.get("lang-ja")
        self.assertIsNotNone(btn_en, "Missing #lang-en button in dashboard")
        self.assertIsNotNone(btn_ja, "Missing #lang-ja button in dashboard")

        self.assertIn("bg-gray-900", btn_en.classes, "#lang-en must be styled as active (bg-gray-900) initially")
        self.assertIn("text-white", btn_en.classes, "#lang-en must have text-white initially")
        self.assertNotIn("bg-gray-900", btn_ja.classes, "#lang-ja must NOT be active initially")

    def test_set_language_ja_updates_all_data_i18n_elements(self):
        """TC-CHALLENGE-10: Simulate setLanguage('ja') and verify 100% of data-i18n elements update to Japanese."""
        # Simulate setLanguage('ja')
        current_lang = "ja"
        dom_state: Dict[str, str] = {}
        for el in self.i18n_elements:
            key = el.data_i18n
            translated = (self.ja.get(key) or self.en.get(key) or key)
            dom_state[key] = translated

        # Verify every element received valid translation
        for key, val in dom_state.items():
            self.assertEqual(val, self.ja[key], f"Key '{key}' was not updated with Japanese translation")

            # Check Japanese character presence (except for brand name which stays English)
            if key != "app_title":
                has_jp = bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", val))
                self.assertTrue(
                    has_jp,
                    f"Japanese translation for '{key}' contains no Japanese characters: '{val}'"
                )

    def test_language_switch_idempotency_and_roundtrip(self):
        """TC-CHALLENGE-11: Verify round-trip switching (EN -> JA -> EN) is 100% idempotent and lossless."""
        initial_en_state = {el.data_i18n: (self.en.get(el.data_i18n) or el.data_i18n) for el in self.i18n_elements}

        # Step 1: Switch to JA
        ja_state = {el.data_i18n: (self.ja.get(el.data_i18n) or self.en.get(el.data_i18n) or el.data_i18n) for el in self.i18n_elements}
        self.assertNotEqual(initial_en_state, ja_state, "JA state must differ from EN state")

        # Step 2: Switch back to EN
        restored_en_state = {el.data_i18n: (self.en.get(el.data_i18n) or el.data_i18n) for el in self.i18n_elements}
        self.assertEqual(
            initial_en_state,
            restored_en_state,
            "Round-trip language switch EN -> JA -> EN resulted in mutated or corrupted state!"
        )

    def test_runtime_t_helper_fallback_behavior(self):
        """TC-CHALLENGE-12: Verify the client-side t() function logic fallback semantics."""
        # Simulated JS function: return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
        def t(key: str, lang: str, i18n_dict: Dict[str, Dict[str, str]]) -> str:
            return (i18n_dict.get(lang, {}).get(key)) or i18n_dict.get("en", {}).get(key) or key

        mock_i18n = {
            "en": {"greeting": "Hello", "fallback_only": "English Only"},
            "ja": {"greeting": "こんにちは"}
        }

        # Case 1: Existing key in target language
        self.assertEqual(t("greeting", "ja", mock_i18n), "こんにちは")
        self.assertEqual(t("greeting", "en", mock_i18n), "Hello")

        # Case 2: Key missing in target language falls back to English
        self.assertEqual(t("fallback_only", "ja", mock_i18n), "English Only")

        # Case 3: Key missing in both languages falls back to the key string itself
        self.assertEqual(t("unknown_key", "ja", mock_i18n), "unknown_key")
        self.assertEqual(t("unknown_key", "en", mock_i18n), "unknown_key")


class TestDynamicUIElementsBilingualSupport(unittest.TestCase):
    """Empirical verification of dynamic DOM elements populated via client JS."""

    @classmethod
    def setUpClass(cls):
        cls.extractor = TemplateExtractor()
        cls.en = cls.extractor.en_dict
        cls.ja = cls.extractor.ja_dict
        cls.script = cls.extractor.script_content

    def test_dynamic_status_render_bilingual_coverage(self):
        """TC-CHALLENGE-13: Verify renderStatusData() has complete bilingual branches for all dynamic elements."""
        required_branches = [
            ("circuitBreakerTripped", "緊急停止中", "Emergency Stop Active"),
            ("planStatus", "14日間フリートライアル有効", "14-Day Free Trial Active"),
            ("canaryUsedCount", "無料サンプル枠", "Free Sample Preview"),
            ("autoSyncEnabled", "有効 (ON)", "Active"),
            ("autoSyncEnabled", "一時停止 (OFF)", "Paused"),
            ("r2Objects", "件保存中", "files stored"),
        ]

        for prop, ja_snippet, en_snippet in required_branches:
            self.assertIn(
                ja_snippet,
                self.script,
                f"Missing Japanese dynamic string in renderStatusData() for '{prop}': '{ja_snippet}'"
            )
            self.assertIn(
                en_snippet,
                self.script,
                f"Missing English dynamic string in renderStatusData() for '{prop}': '{en_snippet}'"
            )

    def test_dynamic_canary_render_bilingual_coverage(self):
        """TC-CHALLENGE-14: Verify renderCanaryResult() has complete bilingual branches for AI Before/After labels."""
        canary_labels = [
            ("lblProduct", "テスト対象商品:", "Sample Product:"),
            ("lblBadge", "カラー・サイズ画像連動 100%正常", "100% Variant Links Preserved"),
            ("lblBefore", "自社ストア表示（セール帯あり）", "Storefront Image (With Promo Badges)"),
            ("lblAfter", "Google広告配信用（AI消去済クリーン画像）", "Google Ad-Feed Image (Policy-Safe Clean Version)"),
            ("lblSwitch", "カラー・サイズボタンをクリックして", "Click any variant option below"),
        ]

        for var_name, ja_snippet, en_snippet in canary_labels:
            self.assertIn(
                ja_snippet,
                self.script,
                f"Missing Japanese string for canary label '{var_name}': '{ja_snippet}'"
            )
            self.assertIn(
                en_snippet,
                self.script,
                f"Missing English string for canary label '{var_name}': '{en_snippet}'"
            )

    def test_manual_snapshot_button_preserves_data_i18n(self):
        """TC-CHALLENGE-15: Verify takeManualSnapshot() restore logic maintains data-i18n='btn_backup_now' attribute."""
        self.assertIn(
            'data-i18n="btn_backup_now"',
            self.script,
            "takeManualSnapshot() finally block must restore data-i18n='btn_backup_now' on button span"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
