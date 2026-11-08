"""
Local unit test for RunPod Serverless Handler logic.
"""

import base64
import sys
import unittest
from handler import handler, fetch_image_bytes


class TestRunPodHandler(unittest.TestCase):
    def setUp(self):
        # 1x1 Transparent PNG in base64
        self.sample_png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )

    def test_missing_input(self):
        res = handler({"input": {}})
        self.assertEqual(res["status"], "error")
        self.assertIn("Missing", res["message"])

    def test_unsupported_task(self):
        try:
            import PIL
        except ImportError:
            print("Skipping PIL-dependent test: PIL not installed in this environment.")
            return

        res = handler({
            "input": {
                "task": "optimize",
                "image_base64": self.sample_png_b64,
                "quality": 80,
                "format": "WEBP"
            }
        })
        self.assertEqual(res["status"], "error")
        self.assertIn("Unsupported task", res["message"])

    def test_ssrf_blocking_private_ip(self):
        with self.assertRaises(ValueError):
            fetch_image_bytes("https://127.0.0.1/evil.png")

    def test_ssrf_blocking_insecure_http(self):
        with self.assertRaises(ValueError):
            fetch_image_bytes("http://example.com/evil.png")

    def test_ssrf_blocking_localhost(self):
        with self.assertRaises(ValueError):
            fetch_image_bytes("https://localhost/evil.png")


if __name__ == "__main__":
    unittest.main()
