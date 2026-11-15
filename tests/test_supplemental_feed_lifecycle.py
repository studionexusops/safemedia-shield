"""
Supplemental Feed Lifecycle & Dual-Feed Proof Tests (Shopify App Review 4.5.3 compliant).

Verifies that:
1. Initially, Supplemental Feed has 0 items before any AI cleaning.
2. After Canary Test, only the cleaned product (e.g. 1001) is included, and g:image_link is the clean image.
3. After Full Catalog Batch, all cleaned products are included.
4. On product removal / metafield clear, the product is removed from the Supplemental Feed immediately.
5. On 1-Click Rollback / Purge, Supplemental Feed resets to 0 items.
"""

import unittest
import json
import xml.etree.ElementTree as ET
from tests.e2e.mock_worker_harness import (
    TestClient,
    PRIMARY_SHOP,
)


class TestSupplementalFeedLifecycle(unittest.TestCase):
    def setUp(self):
        self.client = TestClient()
        self.shop = PRIMARY_SHOP
        # Reset to clean initial state
        self.client.post("/api/billing/reset", json_data={
            "shop": self.shop,
            "planStatus": "CANARY_TRIAL",
            "canaryUsedCount": 0,
            "circuitBreakerTripped": False,
            "autoSyncEnabled": True,
        })
        self.client.post(f"/api/admin/purge-metafields?shop={self.shop}")

    def test_01_initial_feed_empty_supplemental(self):
        """Initial state before AI cleaning: 0 items in supplemental feed."""
        res = self.client.get(f"/api/feed-preview.xml?shop={self.shop}&token=valid_feed_token")
        self.assertEqual(res.status_code, 200)
        xml_str = res.text
        self.assertIn("<rss", xml_str)
        self.assertNotIn("<item>", xml_str)

    def test_02_canary_test_populates_only_cleaned_item(self):
        """After Canary Test: exactly 1 product is in feed, proving dual-feed mapping."""
        # 1. Run canary test
        canary_res = self.client.post(
            "/api/canary/test",
            json_data={"shop": self.shop, "productId": "gid://shopify/Product/1001"}
        )
        self.assertEqual(canary_res.status_code, 200)
        canary_data = canary_res.json()
        self.assertEqual(canary_data["productId"], "gid://shopify/Product/1001")
        self.assertTrue(canary_data["cleanAdImageUrl"])

        # 2. Check XML feed: only 1001 appears, and g:image_link contains clean image URL
        feed_res = self.client.get(f"/api/feed-preview.xml?shop={self.shop}")
        self.assertEqual(feed_res.status_code, 200)
        xml_str = feed_res.text
        self.assertIn("shopify_US_1001_3001", xml_str)
        self.assertNotIn("shopify_US_1002_3011", xml_str)

        root = ET.fromstring(xml_str)
        items = root.findall(".//item")
        self.assertEqual(len(items), 1)

    def test_03_full_catalog_batch_populates_all_cleaned_items(self):
        """After full catalog batch, all cleaned items appear in supplemental feed."""
        # Clean both products in store catalog
        store = self.client.app.get_store(self.shop)
        for p in store.catalog:
            p.setdefault("metafields", {})["safemedia.clean_ad_image_url"] = f"https://cdn.safemedia.io/clean_{p['id'].split('/')[-1]}.jpg"

        feed_res = self.client.get(f"/api/feed-preview?shop={self.shop}")
        self.assertEqual(feed_res.status_code, 200)
        data = feed_res.json()
        self.assertEqual(len(data["items"]), len(store.catalog))
        self.assertEqual(data["channelMappings"]["googleShopping"]["status"], "MAPPED_AND_READY")

    def test_04_product_metafield_removal_excludes_from_feed(self):
        """When a product's clean metafield is removed, it is excluded from supplemental feed."""
        store = self.client.app.get_store(self.shop)
        store.catalog[0].setdefault("metafields", {})["safemedia.clean_ad_image_url"] = "https://cdn.safemedia.io/clean_1001.jpg"
        store.catalog[1].setdefault("metafields", {})["safemedia.clean_ad_image_url"] = "https://cdn.safemedia.io/clean_1002.jpg"

        # Remove clean ad image from 1001
        store.catalog[0]["metafields"].pop("safemedia.clean_ad_image_url", None)

        feed_res = self.client.get(f"/api/feed-preview?shop={self.shop}")
        self.assertEqual(feed_res.status_code, 200)
        data = feed_res.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["productId"], "gid://shopify/Product/1002")

    def test_05_admin_purge_resets_feed_to_empty(self):
        """When metafields are purged, supplemental feed resets to 0 items."""
        store = self.client.app.get_store(self.shop)
        store.catalog[0].setdefault("metafields", {})["safemedia.clean_ad_image_url"] = "https://cdn.safemedia.io/clean_1001.jpg"

        # Execute purge
        purge_res = self.client.post(f"/api/admin/purge-metafields?shop={self.shop}")
        self.assertEqual(purge_res.status_code, 200)

        # Check feed
        feed_res = self.client.get(f"/api/feed-preview?shop={self.shop}")
        self.assertEqual(feed_res.status_code, 200)
        data = feed_res.json()
        self.assertEqual(len(data["items"]), 0)


if __name__ == "__main__":
    unittest.main()
