"""
prepare_e2e_payload.py
ローカル（サンドボックス内・オフライン）で装飾入りテスト画像を Florence-2 + Mask Dilate + LaMa で
クリーンアップし、Cloudflare Worker (Webhook / Dual-Feed API) へ送信するためのJSONペイロードを生成する。
"""

import os
import io
import json
import time
import base64
from PIL import Image
from verify_inpainting_pipeline import AutomatedInpaintPipeline

OUT_PAYLOAD_PATH = "./inpainted_results/e2e_webhook_payload.json"


def main():
    # Use Level 2 banner test image (SAVE 20% NOW red bar across top)
    sample_file = "./synthetic_tests/shopify_8286866473088_41608060534912_lvl2_banner.jpg"
    if not os.path.exists(sample_file):
        raise FileNotFoundError(f"Sample file not found: {sample_file}")

    pipeline = AutomatedInpaintPipeline()
    img = Image.open(sample_file).convert("RGB")

    t0 = time.time()
    mask_np = pipeline.detect_overlay_mask(img, dilate_px=6)
    cleaned_img = pipeline.inpaint_lama(img, mask_np)
    total_sec = round(time.time() - t0, 2)
    mask_pct = round(float((mask_np > 127).sum()) / float(mask_np.size) * 100.0, 2)

    buf = io.BytesIO()
    cleaned_img.save(buf, format="JPEG", quality=95)
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Construct Shopify products/update webhook payload for main test product (10352680632517)
    payload = {
        "id": 10352680632517,
        "title": "The Complete Snowboard",
        "image": {
            "src": "https://cdn.shopify.com/s/files/1/0533/2089/files/Main_b13ad453-477c-4ed1-9b43-81f3345adfd6.jpg?v=1760155000&promo_banner=save20"
        },
        "clean_image_base64": b64_str,
        "mask_coverage_pct": mask_pct,
        "processing_sec": total_sec,
        "force_reclean": True,
    }

    with open(OUT_PAYLOAD_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    print(f"Prepared E2E webhook payload at {OUT_PAYLOAD_PATH} (processing_sec={total_sec}s, mask={mask_pct}%)")


if __name__ == "__main__":
    main()
