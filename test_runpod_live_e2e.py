"""
test_runpod_live_e2e.py
Mac上のAIを一切使わず、100%クラウド間（Shopify Webhook ➔ Cloudflare Workers ➔ RunPod Serverless GPU ➔ Cloudflare R2 ➔ Shopify 隠しメタフィールド）
で赤帯バナー入り画像が自動修復・格納されることを実証するスクリプト。
"""

import base64
import json
import time
import requests

WORKER_BASE_URL = "https://safemedia-shield-worker.safemedia.workers.dev"
DECORATED_IMAGE_PATH = "./synthetic_tests/shopify_8286866473088_41608060534912_lvl2_banner.jpg"


def main():
    # Step 1: Host the decorated "SAVE 20% NOW" banner image at a public HTTPS URL on R2
    # so RunPod Serverless can fetch it via `image_url` just like a Shopify CDN image.
    with open(DECORATED_IMAGE_PATH, "rb") as f:
        decorated_b64 = base64.b64encode(f.read()).decode("utf-8")

    print("=== 1. Hosting Decorated Banner Image ('SAVE 20% NOW') on Public CDN URL ===")
    stage_res = requests.post(
        f"{WORKER_BASE_URL}/api/dual-feed/sync",
        json={
            "productId": "gid://shopify/Product/10352680632517",
            "cleanImageBase64": decorated_b64,
        },
        timeout=30,
    )
    stage_data = stage_res.json()
    decorated_public_url = stage_data["cleanAdImageUrl"]
    print(f"Decorated Image Public URL: {decorated_public_url}")

    # Step 2: Now fire the Shopify `products/update` Webhook with ONLY the image URL (NO local AI!)
    # Cloudflare Workers will call RunPod Serverless GPU (cho9rydg8gsc9w), clean the banner,
    # store the cleaned image in R2, and update Shopify's hidden metafield `safemedia.clean_ad_image_url`.
    print("\n=== 2. Firing Webhook (Cloudflare Workers -> RunPod GPU -> R2 -> Shopify Metafield) ===")
    t0 = time.time()
    webhook_res = requests.post(
        f"{WORKER_BASE_URL}/webhooks/products/update",
        json={
            "id": 10352680632517,
            "title": "The Complete Snowboard",
            "image": {
                "src": decorated_public_url,
            },
            "force_reclean": True,
        },
        headers={"X-Shopify-Shop-Domain": "safemedia-test-20261011.myshopify.com"},
        timeout=90,
    )
    elapsed = round(time.time() - t0, 2)
    print(f"HTTP Status: {webhook_res.status_code} (Round-trip: {elapsed}s)")
    wh_data = webhook_res.json()
    print(json.dumps(wh_data, indent=2, ensure_ascii=False))

    assert wh_data.get("success") is True, f"RunPod E2E failed: {wh_data}"
    assert wh_data.get("engine") == "RunPod-Serverless-Florence2-LaMa", f"Expected RunPod engine, got: {wh_data.get('engine')}"

    clean_url = wh_data["cleanAdImageUrl"]
    print(f"\n=== 3. Downloading RunPod GPU Cleaned Image from R2 ({clean_url}) ===")
    img_res = requests.get(clean_url, timeout=20)
    assert img_res.status_code == 200, "Failed to download cleaned image from R2"
    out_file = "./inpainted_results/runpod_gpu_cleaned_result.jpg"
    with open(out_file, "wb") as f:
        f.write(img_res.content)
    print(f"Saved RunPod GPU cleaned image to {out_file} ({len(img_res.content)} bytes)")


if __name__ == "__main__":
    main()
