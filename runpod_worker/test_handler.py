"""
Local unit test for RunPod Serverless Handler logic.
"""

import base64
import sys
import unittest
from handler import handler, optimize_image


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

    def test_optimize_base64_image(self):
        try:
            import PIL
        except ImportError:
            print("Skipping PIL-dependent test: PIL not installed in this environment.")
            return

        res = handler({
            "input": {
                "image_base64": self.sample_png_b64,
                "quality": 80,
                "format": "WEBP"
            }
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["format"], "webp")
        self.assertIn("image_base64", res)
        self.assertGreater(res["optimized_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
