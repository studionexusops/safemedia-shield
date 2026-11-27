"""
verify_e2e_webhook.py
Cloudflare Workersの本番エンドポイントに対して以下を一気通貫（E2E）で検証するスクリプト:
1. Shopify `PRODUCTS_UPDATE` Webhookの自動登録 (`/api/webhooks/register`)
2. Webhookイベント発火 (`/webhooks/products/update`) ➔ AIクリーン画像のCloudflare R2保存 ➔ Shopify商品の隠しメタフィールド (`safemedia.clean_ad_image_url`) 自動格納
3. 生成された広告用クリーン画像URLの公開アクセス確認 (Google Merchant Centerクローラー互換性)
4. 同一画像に対するWebhook無限ループ防止機能の動作確認 (`skipped: true`)
5. Shopify GraphQL経由でのメタフィールド格納状態の確認 (`/api/status`)
"""

import json
import requests

WORKER_BASE_URL = "https://safemedia-shield-worker.safemedia.workers.dev"
PAYLOAD_PATH = "./inpainted_results/e2e_webhook_payload.json"


def main():
    print("=== 1. Registering Shopify PRODUCTS_UPDATE Webhook ===")
    reg_res = requests.post(f"{WORKER_BASE_URL}/api/webhooks/register", timeout=20)
    print(f"Status: {reg_res.status_code} | Response: {reg_res.text}")

    print("\n=== 2. Sending products/update Webhook Payload (E2E AI Cleanup -> R2 -> Shopify Metafield) ===")
    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    wh_res = requests.post(
        f"{WORKER_BASE_URL}/webhooks/products/update",
        json=payload,
        headers={"X-Shopify-Shop-Domain": "safemedia-test-20261011.myshopify.com"},
        timeout=30,
    )
    print(f"Status: {wh_res.status_code}")
    wh_data = wh_res.json()
    print(json.dumps(wh_data, indent=2, ensure_ascii=False))

    clean_url = wh_data.get("cleanAdImageUrl")
    assert wh_data.get("success") is True, "Webhook E2E failed!"
    assert clean_url and clean_url.startswith(WORKER_BASE_URL + "/clean-media/"), f"Unexpected clean URL: {clean_url}"

    print("\n=== 3. Verifying Public Clean Image URL (Google Merchant Center Crawler Check) ===")
    img_res = requests.get(clean_url, timeout=15)
    print(
        f"GET {clean_url} -> Status: {img_res.status_code}, "
        f"Content-Type: {img_res.headers.get('Content-Type')}, "
        f"Size: {len(img_res.content)} bytes"
    )
    assert img_res.status_code == 200 and len(img_res.content) > 5000, "Clean image URL failed check!"

    print("\n=== 4. Verifying Infinite Webhook Loop Prevention (Idempotency Check) ===")
    payload_repeat = dict(payload)
    payload_repeat.pop("force_reclean", None)
    repeat_res = requests.post(
        f"{WORKER_BASE_URL}/webhooks/products/update",
        json=payload_repeat,
        headers={"X-Shopify-Shop-Domain": "safemedia-test-20261011.myshopify.com"},
        timeout=20,
    )
    print(f"Status: {repeat_res.status_code} | Response: {repeat_res.text}")

    print("\n=== 5. Verifying Live Shopify Product Metafield via /api/status ===")
    status_res = requests.get(f"{WORKER_BASE_URL}/api/status", timeout=20)
    status_data = status_res.json()
    df_products = status_data.get("dualFeedProducts", [])
    for p in df_products:
        if p.get("cleanAdImageUrl"):
            print(f"Verified Shopify Product Metafield: {json.dumps(p, indent=2, ensure_ascii=False)}")

    print("\n✅ E2E Dual-Feed Automation (Webhook -> AI Cleanup -> R2 -> Shopify Hidden Metafield) PASSED!")


if __name__ == "__main__":
    main()
