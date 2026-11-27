"""
Local unit test for RunPod Serverless Handler logic.
"""

import base64
import sys
import unittest
import numpy as np
from PIL import Image, ImageDraw
from handler import (
    handler,
    fetch_image_bytes,
    SafeMediaInpaintEngine,
    _is_promo_or_watermark_text,
    _is_noise_ocr_label,
)


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

    def test_promo_vs_product_text_classification(self):
        # Promotional / watermark texts must be flagged for removal
        for label in [
            "</s>SALE / 20% OFF",
            "</s>50% OFF",
            "</s>FREE SHIPPING",
            "</s>WINTER CLEARANCE / 20% OFF",
            "</s>© STORE NAME",
            "</s>LIMITED OFFER",
            "</s>送料無料",
        ]:
            self.assertTrue(_is_promo_or_watermark_text(label), f"Expected promo=True for {label}")

        # Product brand names / model labels must be preserved
        for label in [
            "</s>SOLARIS",
            "</s>AEROX",
            "</s>SMITH",
            "</s>MOUNTAIN PEAKS",
            "</s>GORE-TEX",
            "</s>VELOCITY",
            "</s>CARBON FREERIDE 156",
        ]:
            self.assertFalse(_is_promo_or_watermark_text(label), f"Expected promo=False for {label}")

    def test_noise_ocr_label_filter(self):
        self.assertTrue(_is_noise_ocr_label("</s>١٠٠-١-٠.٠:٢٠"))
        self.assertTrue(_is_noise_ocr_label("</s>"))
        self.assertFalse(_is_noise_ocr_label("</s>SALE"))
        self.assertFalse(_is_noise_ocr_label("</s>©"))

    def test_top_edge_banner_with_border_detection(self):
        # Simulate a 200x200 image with a top-edge (y=0..24) red banner + gold border (y=24..27)
        img = Image.new("RGB", (200, 200), (250, 250, 250))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 200, 24], fill=(200, 20, 30))
        draw.rectangle([0, 24, 200, 27], fill=(210, 170, 50))
        # Product body in the center
        draw.rectangle([60, 60, 140, 160], fill=(30, 80, 150))

        img_np = np.array(img)
        bg = SafeMediaInpaintEngine._estimate_background_color(img_np)
        self.assertGreater(bg[0], 240.0)

        banner_mask = SafeMediaInpaintEngine._detect_horizontal_banners(
            img_np, bg, promo_boxes=[(40, 4, 160, 20)]
        )
        # Banner + gold border must be fully masked
        self.assertEqual(int(banner_mask[10, 100]), 255)
        self.assertEqual(int(banner_mask[26, 100]), 255)
        # Product body must remain completely unmasked
        self.assertEqual(int(banner_mask[100, 100]), 0)

    def test_badge_region_extraction_swallows_border_and_shadow(self):
        img = Image.new("RGB", (300, 300), (252, 252, 252))
        draw = ImageDraw.Draw(img)
        # Drop shadow + orange circular badge
        draw.ellipse([34, 34, 114, 114], fill=(190, 190, 190))
        draw.ellipse([30, 30, 110, 110], fill=(230, 90, 20))
        img_np = np.array(img)
        bg = SafeMediaInpaintEngine._estimate_background_color(img_np)
        pts = [(48.0, 58.0), (92.0, 58.0), (92.0, 82.0), (48.0, 82.0)]
        badge_mask = SafeMediaInpaintEngine._extract_badge_region_mask(img_np, bg, pts)
        self.assertIsNotNone(badge_mask)
        assert badge_mask is not None
        # Both badge interior and drop shadow edge must be covered
        self.assertEqual(int(badge_mask[70, 70]), 255)
        self.assertEqual(int(badge_mask[112, 70]), 255)
        # Far background must remain untouched
        self.assertEqual(int(badge_mask[250, 250]), 0)


if __name__ == "__main__":
    unittest.main()
