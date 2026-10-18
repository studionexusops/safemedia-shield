"""
Local Interactive Demo Server for SafeMedia Shield (Cloudflare Worker Prototype)
Runs on Python 3 standard library with zero external dependencies.
Allows testing the exact Polaris UI, Canary Test, and 1-Click Rollback in your browser.
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# In-memory store simulating Cloudflare R2 and Shopify
MOCK_STORE = [
    {
        "id": "gid://shopify/Product/1001",
        "title": "プレミアム ヘビーウェイト クラシックTシャツ",
        "original_size_kb": 2450,
        "optimized_size_kb": 412,
        "savings_percentage": 83.2,
        "original_image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800",
        "optimized_image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800&auto=format&fit=crop&q=80",
        "media": [
            {"id": "gid://shopify/MediaImage/2001", "url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800"},
            {"id": "gid://shopify/MediaImage/2002", "url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800"},
            {"id": "gid://shopify/MediaImage/2003", "url": "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=800"},
        ],
        "variants": [
            {"id": "gid://shopify/ProductVariant/3001", "title": "Black / S", "media_id": "gid://shopify/MediaImage/2001", "active_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800"},
            {"id": "gid://shopify/ProductVariant/3002", "title": "Black / M", "media_id": "gid://shopify/MediaImage/2001", "active_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800"},
            {"id": "gid://shopify/ProductVariant/3003", "title": "White / S", "media_id": "gid://shopify/MediaImage/2002", "active_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800"},
            {"id": "gid://shopify/ProductVariant/3004", "title": "White / M", "media_id": "gid://shopify/MediaImage/2002", "active_url": "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800"},
            {"id": "gid://shopify/ProductVariant/3005", "title": "Navy / L", "media_id": "gid://shopify/MediaImage/2003", "active_url": "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=800"},
        ]
    }
]

SNAPSHOTS = {}
LATEST_SNAPSHOT_ID = None


class SafeMediaHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        global LATEST_SNAPSHOT_ID

        if parsed.path == "/":
            # Load HTML UI template
            # Render directly matching ui.ts
            with open("cloudflare_worker/src/ui.ts", "r", encoding="utf-8") as f:
                content = f.read()
                # Extract HTML between backticks
                start = content.find("<!DOCTYPE html>")
                end = content.rfind("</html>") + 7
                html = content[start:end].replace("${shop}", "demo-store.myshopify.com")
            
            self._set_headers(200, "text/html; charset=utf-8")
            self.wfile.write(html.encode("utf-8"))
            return

        if parsed.path == "/api/status":
            self._set_headers(200)
            snap = SNAPSHOTS.get(LATEST_SNAPSHOT_ID)
            res = {
                "shop": "demo-store.myshopify.com",
                "protectionActive": True,
                "latestSnapshot": {
                    "snapshotId": snap["snapshot_id"],
                    "createdAt": snap["created_at"],
                    "totalProducts": 1,
                    "totalImages": 3
                } if snap else None
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(b'{"error": "Not Found"}')

    def do_POST(self):
        parsed = urlparse(self.path)
        global LATEST_SNAPSHOT_ID

        if parsed.path == "/api/canary/test":
            snap_id = f"snap_canary_{int(time.time())}"
            SNAPSHOTS[snap_id] = {
                "snapshot_id": snap_id,
                "created_at": datetime.now().isoformat(),
                "products": json.loads(json.dumps(MOCK_STORE))
            }
            LATEST_SNAPSHOT_ID = snap_id

            p = MOCK_STORE[0]
            checks = []
            for v in p["variants"]:
                checks.append({
                    "variantId": v["id"],
                    "variantTitle": v["title"],
                    "preserved": True,
                    "activeImageUrl": v["active_url"]
                })

            resp = {
                "productId": p["id"],
                "productTitle": p["title"],
                "originalSizeKB": p["original_size_kb"],
                "optimizedSizeKB": p["optimized_size_kb"],
                "savingsPercentage": p["savings_percentage"],
                "originalImageUrl": p["original_image_url"],
                "optimizedImageUrl": p["optimized_image_url"],
                "variantChecks": checks
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if parsed.path == "/api/batch/start":
            snap_id = f"snap_batch_{int(time.time())}"
            SNAPSHOTS[snap_id] = {
                "snapshot_id": snap_id,
                "created_at": datetime.now().isoformat(),
                "products": json.loads(json.dumps(MOCK_STORE))
            }
            LATEST_SNAPSHOT_ID = snap_id
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "success": True,
                "total": 1,
                "jobId": snap_id,
                "message": "Batch process started safely."
            }).encode("utf-8"))
            return

        if parsed.path == "/api/batch/abort":
            self._set_headers(200)
            self.wfile.write(b'{"success": true, "message": "Circuit breaker activated."}')
            return

        if parsed.path == "/api/rollback":
            if not LATEST_SNAPSHOT_ID:
                self._set_headers(400)
                self.wfile.write(b'{"success": false, "error": "No snapshot available"}')
                return

            snap = SNAPSHOTS[LATEST_SNAPSHOT_ID]
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "success": True,
                "restoredProducts": 1,
                "message": f"Snapshot ({snap['snapshot_id']}) より1商品5バリアントの画像を完全復元しました。"
            }).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(b'{"error": "Not Found"}')


def run(port=8787):
    server = HTTPServer(("127.0.0.1", port), SafeMediaHandler)
    print(f"SafeMedia Shield Interactive Prototype running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
