import os
import requests
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_shopify_images(store_url: str, max_images: int = 10, output_dir: str = "./shopify_raw"):
    os.makedirs(output_dir, exist_ok=True)
    
    # URLの正規化
    parsed = urlparse(store_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else f"https://{store_url.strip('/')}"
    endpoint = f"{base_url}/products.json?limit=50"
    
    try:
        response = requests.get(endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"ストアからのデータ取得に失敗しました: {e}")
        return

    products = data.get("products", [])
    if not products:
        print("商品データが存在しないか、エンドポイントが非公開です。")
        return

    download_count = 0
    for product in products:
        for img in product.get("images", []):
            if download_count >= max_images:
                break
            
            img_url = img.get("src")
            if not img_url:
                continue

            # Shopify CDNのURLクエリ除去
            clean_url = img_url.split("?")[0]
            ext = os.path.splitext(clean_url)[1] or ".jpg"
            file_name = f"shopify_{product['id']}_{img['id']}{ext}"
            file_path = os.path.join(output_dir, file_name)

            try:
                img_data = requests.get(clean_url, headers=HEADERS, timeout=10).content
                with open(file_path, "wb") as f:
                    f.write(img_data)
                download_count += 1
                print(f"[{download_count}/{max_images}] 保存完了: {file_name}")
            except Exception as e:
                print(f"画像ダウンロード失敗 ({clean_url}): {e}")

        if download_count >= max_images:
            break

    print(f"処理完了: 合計 {download_count} 枚の画像を {output_dir} に保存しました。")

if __name__ == "__main__":
    # 任意の公開ShopifyストアURL（例: アパレル・雑貨系）
    TARGET_STORE = "https://kith.com"  # 調査対象ストアのURLに置き換えて実行
    fetch_shopify_images(TARGET_STORE, max_images=5, output_dir="./shopify_samples")
