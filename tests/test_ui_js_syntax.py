"""
Test Suite: Client-side JavaScript Syntax & Parsing Verification (Post-Template Evaluation)
Ensures that when ui.ts evaluates its TypeScript template literal (`...`) to produce the final HTML
delivered to the browser, the resulting <script> block is 100% syntactically valid and executable.
"""

import unittest
import os
import re
import subprocess
import tempfile

class TestUiClientJsSyntax(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ui_file = os.path.join(self.base_dir, "cloudflare_worker", "src", "ui.ts")
        self.jsc_bin = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

    def test_post_template_evaluation_client_js_syntax_and_execution(self):
        """Evaluates the template literal in JSC first (matching Worker runtime), then parses and executes the resulting client JS."""
        with open(self.ui_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Static guard: forbid single-backslash quote escapes inside template literal
        self.assertNotIn(r"\'", content, "Single-escaped apostrophe \\' inside template literal will unescape and break client JS strings!")
        self.assertNotIn(r'\"', content, "Single-escaped quote \\\" inside template literal will unescape and break client JS strings!")

        bt = chr(96)
        start_marker = "return " + bt
        end_marker = bt + ";\n}"
        start = content.find(start_marker)
        self.assertNotEqual(start, -1, "return ` must exist in ui.ts")
        start += len(start_marker)
        end = content.rfind(end_marker)
        self.assertNotEqual(end, -1, "`;\\n} must exist in ui.ts")
        raw_template = content[start:end]

        if not os.path.exists(self.jsc_bin):
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step A: Evaluate template literal in JavaScript engine just like Cloudflare Worker does
            gen_html_path = os.path.join(tmpdir, "gen_html.js")
            gen_html_code = f"""
const shop = "test.myshopify.com";
const apiKey = "test_key";
const feedTokenQuery = "";
const autosyncBadgeClass = "";
const autosyncBadgeText = "";
const toggleBtnClass = "";
const toggleBtnIcon = "";
const toggleBtnLabel = "";
const planBadgeClass = "";
const planBadgeText = "";
const planDescText = "";
const planUsageBadgeClass = "";
const planUsageBadgeText = "";
const canaryQuotaDisplayClass = "";
const canaryQuotaDisplayText = "";
const showTrialBtn = false;
const showResumeBtn = false;

const html = {bt}{raw_template}{bt};
print(html);
"""
            with open(gen_html_path, "w", encoding="utf-8") as out:
                out.write(gen_html_code)

            res_html = subprocess.run([self.jsc_bin, gen_html_path], capture_output=True, text=True)
            self.assertEqual(res_html.returncode, 0, f"Template literal evaluation failed: {res_html.stdout} {res_html.stderr}")
            actual_html = res_html.stdout

            # Step B: Extract the actual <script> sent to the browser
            script_match = re.search(r"<script>([\s\S]*?)</script>", actual_html)
            self.assertIsNotNone(script_match, "<script> tag must exist in evaluated HTML")
            actual_client_js = script_match.group(1)

            # Step C: Parse and execute the client script with a mocked DOM
            client_js_path = os.path.join(tmpdir, "actual_browser.js")
            harness = f"""
const window = {{
    location: {{ origin: 'https://test.myshopify.com' }},
    top: {{ location: {{}} }},
    shopify: {{ idToken: async () => 'test_token' }}
}};
const document = {{
    getElementById: (id) => ({{
        classList: {{ add: () => {{}}, remove: () => {{}} }},
        addEventListener: () => {{}},
        innerText: '',
        innerHTML: '',
        value: '',
        disabled: false,
        appendChild: () => {{}}
    }}),
    querySelectorAll: () => [],
    createElement: () => ({{ appendChild: () => {{}}, innerText: '', value: '' }})
}};
const fetch = async () => ({{ json: async () => ({{ success: true }}) }});

{actual_client_js}

print('__BROWSER_JS_VALIDATED_OK__');
"""
            with open(client_js_path, "w", encoding="utf-8") as out:
                out.write(harness)

            res_client = subprocess.run([self.jsc_bin, client_js_path], capture_output=True, text=True)
            self.assertEqual(
                res_client.returncode,
                0,
                f"Browser client JS failed syntax/runtime check:\nSTDOUT: {res_client.stdout}\nSTDERR: {res_client.stderr}"
            )
            self.assertIn("__BROWSER_JS_VALIDATED_OK__", res_client.stdout)

if __name__ == "__main__":
    unittest.main()
