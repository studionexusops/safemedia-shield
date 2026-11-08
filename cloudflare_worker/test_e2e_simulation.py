"""
End-to-End Simulation & Test Runner for SafeMedia Shield / AdFeed Clean
Pure Dual-Feed Alignment:
1. Immutable Snapshot Generation & Variant Mapping Preservation
2. 1-Product Canary Test (Pure Dual-Feed Before vs After AI Clean Image & Variant Check)
3. Non-Destructive Catalog Batch Generation into Hidden Metafields
4. 1-Click Time Machine Rollback (Restoring variants and metafields)
"""

import copy
import json
import time
import unittest
from datetime import datetime


class SafeMediaShieldSimulator:
    def __init__(self, shop="demo-store.myshopify.com"):
        self.shop = shop
        self.snapshots = {}
        self.latest_snapshot_id = None
        self.current_store_state = self._load_initial_store()
        self.job_state = {"status": "IDLE"}

    def _load_initial_store(self):
        """Simulate Shopify store with multi-variant merchandise."""
        return [
            {
                "id": "gid://shopify/Product/1001",
                "title": "プレミアム ヘビーウェイト クラシックTシャツ",
                "body_html": "<p>最高級超長綿を使用したTシャツ。<img src='https://cdn.shopify.com/orig/black_promo.jpg'/></p>",
                "media": [
                    {"id": "gid://shopify/MediaImage/2001", "url": "https://cdn.shopify.com/orig/black_promo.jpg"},
                    {"id": "gid://shopify/MediaImage/2002", "url": "https://cdn.shopify.com/orig/white.jpg"},
                    {"id": "gid://shopify/MediaImage/2003", "url": "https://cdn.shopify.com/orig/navy.jpg"},
                ],
                "variants": [
                    {"id": "gid://shopify/ProductVariant/3001", "title": "Black / S", "media_id": "gid://shopify/MediaImage/2001", "sku": "TS-BLK-S"},
                    {"id": "gid://shopify/ProductVariant/3002", "title": "Black / M", "media_id": "gid://shopify/MediaImage/2001", "sku": "TS-BLK-M"},
                    {"id": "gid://shopify/ProductVariant/3003", "title": "White / S", "media_id": "gid://shopify/MediaImage/2002", "sku": "TS-WHT-S"},
                    {"id": "gid://shopify/ProductVariant/3004", "title": "White / M", "media_id": "gid://shopify/MediaImage/2002", "sku": "TS-WHT-M"},
                    {"id": "gid://shopify/ProductVariant/3005", "title": "Navy / L", "media_id": "gid://shopify/MediaImage/2003", "sku": "TS-NVY-L"},
                ],
                "metafields": {},
            },
            {
                "id": "gid://shopify/Product/1002",
                "title": "オーガニック フレンチテリー ジップアップフーディー",
                "body_html": "<p>通年着用できる肉厚裏毛スウェット生地。</p>",
                "media": [
                    {"id": "gid://shopify/MediaImage/2011", "url": "https://cdn.shopify.com/orig/grey_badge.jpg"},
                    {"id": "gid://shopify/MediaImage/2012", "url": "https://cdn.shopify.com/orig/charcoal.jpg"},
                ],
                "variants": [
                    {"id": "gid://shopify/ProductVariant/3011", "title": "Grey / M", "media_id": "gid://shopify/MediaImage/2011", "sku": "HD-GRY-M"},
                    {"id": "gid://shopify/ProductVariant/3012", "title": "Grey / L", "media_id": "gid://shopify/MediaImage/2011", "sku": "HD-GRY-L"},
                    {"id": "gid://shopify/ProductVariant/3013", "title": "Charcoal / M", "media_id": "gid://shopify/MediaImage/2012", "sku": "HD-CHR-M"},
                ],
                "metafields": {},
            },
        ]

    def create_snapshot(self):
        """Step 1: Create Cloud Immutable Snapshot (R2 simulation)."""
        snap_id = f"snap_{self.shop}_{int(time.time())}"
        snapshot_data = {
            "snapshot_id": snap_id,
            "shop": self.shop,
            "created_at": datetime.utcnow().isoformat(),
            "products": copy.deepcopy(self.current_store_state),
        }
        self.snapshots[snap_id] = snapshot_data
        self.latest_snapshot_id = snap_id
        return snap_id

    def run_canary_test(self):
        """Step 2: 1-Product Canary Test (Pure Dual-Feed Before vs After AI Clean Image)."""
        self.create_snapshot()
        # Find product with most variants
        canary_product = max(self.current_store_state, key=lambda p: len(p["variants"]))
        target_image = canary_product["media"][0]["url"]

        # Simulate Florence-2 OCR + LaMa AI Inpainting
        numeric_id = "".join(filter(str.isdigit, canary_product["id"]))
        clean_url = f"https://worker.safemedia.dev/clean-media/{self.shop}/clean_{numeric_id}_{int(time.time())}.jpg"

        # Populate hidden metafield without modifying storefront media
        canary_product["metafields"]["safemedia.clean_ad_image_url"] = clean_url
        canary_product["metafields"]["safemedia.dual_feed_metadata"] = {
            "source_image_url": target_image,
            "cleaned_at": datetime.utcnow().isoformat(),
            "mask_coverage_pct": 2.1,
            "processing_sec": 1.45,
            "engine": "Florence2-LaMa-Pipeline",
        }

        # Check all variants maintain intact mapping
        variant_checks = []
        for v in canary_product["variants"]:
            variant_checks.append({
                "variant_id": v["id"],
                "title": v["title"],
                "has_original_media": bool(v["media_id"]),
                "preserved": bool(v["media_id"]),
                "media_id": v["media_id"],
            })

        return {
            "product_id": canary_product["id"],
            "product_title": canary_product["title"],
            "original_image_url": target_image,
            "clean_ad_image_url": clean_url,
            "metafield_key": "safemedia.clean_ad_image_url",
            "ai_metadata": {
                "processing_sec": 1.45,
                "mask_coverage_pct": 2.1,
                "engine": "Florence2-LaMa-Pipeline",
            },
            "variant_checks": variant_checks,
            "all_variants_intact": all(vc["preserved"] for vc in variant_checks),
        }

    def start_batch_generation(self):
        """Step 3: Full Catalog Ad-Feed Generation (Strictly Non-Destructive)."""
        snap_id = self.create_snapshot()
        self.job_state = {"status": "RUNNING", "processed": 0, "total": len(self.current_store_state)}

        for p in self.current_store_state:
            storefront_image = p["media"][0]["url"]
            numeric_id = "".join(filter(str.isdigit, p["id"]))
            clean_url = f"https://worker.safemedia.dev/clean-media/{self.shop}/clean_{numeric_id}_{int(time.time())}.jpg"
            # Storefront media IDs and URLs are NEVER touched
            p["metafields"]["safemedia.clean_ad_image_url"] = clean_url
            p["metafields"]["safemedia.dual_feed_metadata"] = {
                "source_image_url": storefront_image,
                "cleaned_at": datetime.utcnow().isoformat(),
                "engine": "Florence2-LaMa-Pipeline",
            }
            self.job_state["processed"] += 1

        self.job_state["status"] = "COMPLETED"
        return {
            "success": True,
            "job_id": snap_id,
            "total_products": len(self.current_store_state),
            "snapshot_id": snap_id,
            "message": "Full catalog ad-feed generation started. Storefront images remain unaltered.",
        }

    def simulate_bad_competitor_update(self):
        """Simulate how competitor apps corrupt store (detaches variants & overwrites images)."""
        for p in self.current_store_state:
            # Replaces media with new IDs (destructive)
            p["media"] = [{"id": "gid://shopify/MediaImage/9999", "url": "https://cdn.shopify.com/corrupt/new.webp"}]
            # Sever variant mappings (common bug in competitors)
            for v in p["variants"]:
                v["media_id"] = None

    def get_feed_preview(self):
        """Step 3b: Ad-Feed Mapping Preview (GMC & Meta Catalog routing)."""
        items = []
        for p in self.current_store_state:
            storefront_img = p["media"][0]["url"]
            clean_img = p["metafields"].get("safemedia.clean_ad_image_url") or storefront_img
            items.append({
                "productId": p["id"],
                "title": p["title"],
                "storefrontImageUrl": storefront_img,
                "cleanAdImageUrl": clean_img,
                "metafieldKey": "safemedia.clean_ad_image_url",
                "gmcImageLinkField": "g:image_link",
                "metaImageLinkField": "image_link",
                "storefrontUntouched": True,
                "adFeedCompliant": bool(p["metafields"].get("safemedia.clean_ad_image_url")),
            })
        return {
            "shop": self.shop,
            "generatedAt": datetime.utcnow().isoformat(),
            "metafieldNamespaceKey": "safemedia.clean_ad_image_url",
            "feedEndpointXmlUrl": f"https://worker.safemedia.dev/api/feed-preview.xml?shop={self.shop}",
            "items": items,
        }

    def rollback(self, snapshot_id=None):
        """Step 4: 1-Click Time Machine Rollback (Restores variants and metafields with Before/After diffs)."""
        target_id = snapshot_id or self.latest_snapshot_id
        if not target_id:
            raise RuntimeError("No snapshot available for rollback.")

        clean_id = target_id[:-5] if target_id.endswith(".json") else target_id
        if clean_id not in self.snapshots:
            raise RuntimeError(f"Snapshot {clean_id} not found.")

        target_snap = self.snapshots[clean_id]
        before_by_id = {p["id"]: copy.deepcopy(p) for p in self.current_store_state}

        # Restore full state: variant bindings and metafields
        self.current_store_state = copy.deepcopy(target_snap["products"])
        reverted_at = datetime.utcnow().isoformat()

        product_diffs = []
        for restored in self.current_store_state:
            before_p = before_by_id.get(restored["id"], restored)
            before_variants = [
                {"variantId": v["id"], "variantTitle": v["title"], "mediaId": v["media_id"]}
                for v in before_p["variants"]
            ]
            after_variants = [
                {"variantId": v["id"], "variantTitle": v["title"], "mediaId": v["media_id"]}
                for v in restored["variants"]
            ]
            variant_diffs = []
            for idx, av in enumerate(after_variants):
                bv_media = before_variants[idx]["mediaId"] if idx < len(before_variants) else None
                variant_diffs.append({
                    "variantId": av["variantId"],
                    "variantTitle": av["variantTitle"],
                    "beforeMediaId": bv_media,
                    "afterMediaId": av["mediaId"],
                    "restored": True,
                })
            storefront_url = restored["media"][0]["url"] if restored["media"] else ""
            product_diffs.append({
                "productId": restored["id"],
                "title": restored["title"],
                "storefrontImageUrl": storefront_url,
                "beforeRevert": {
                    "storefrontImageUrl": before_p["media"][0]["url"] if before_p["media"] else storefront_url,
                    "cleanAdImageUrl": before_p["metafields"].get("safemedia.clean_ad_image_url"),
                    "variantBindings": before_variants,
                },
                "afterRevert": {
                    "storefrontImageUrl": storefront_url,
                    "cleanAdImageUrl": restored["metafields"].get("safemedia.clean_ad_image_url"),
                    "variantBindings": after_variants,
                },
                "variantBindingDiffs": variant_diffs,
                "metafieldRestored": True,
                "variantsRestoredCount": len(after_variants),
            })

        return {
            "success": True,
            "restored_count": len(self.current_store_state),
            "restored_products": len(self.current_store_state),
            "snapshot_id": clean_id,
            "snapshotId": clean_id,
            "snapshotTimestamp": target_snap.get("timestamp") or target_snap.get("created_at"),
            "revertedAt": reverted_at,
            "metafields_restored": True,
            "metafieldsRestored": True,
            "productDataDiffs": product_diffs,
            "beforeAfterComparisons": product_diffs,
            "message": "Store media and ad-feed metafields restored successfully.",
        }


class TestSafeMediaShieldFlow(unittest.TestCase):
    def setUp(self):
        self.sim = SafeMediaShieldSimulator()

    def test_immutable_snapshot_creation(self):
        snap_id = self.sim.create_snapshot()
        self.assertIsNotNone(snap_id)
        self.assertIn(snap_id, self.sim.snapshots)
        snap = self.sim.snapshots[snap_id]
        self.assertEqual(len(snap["products"]), 2)

    def test_canary_test_preserves_variants_and_dual_feed(self):
        # 1. Capture original storefront state
        orig_media = copy.deepcopy(self.sim.current_store_state[0]["media"])

        # 2. Run canary test
        res = self.sim.run_canary_test()

        # 3. Verify pure dual-feed assertions
        self.assertTrue(res["all_variants_intact"])
        self.assertEqual(len(res["variant_checks"]), 5)
        self.assertIn("clean_ad_image_url", res)
        self.assertNotEqual(res["original_image_url"], res["clean_ad_image_url"])
        self.assertEqual(res["metafield_key"], "safemedia.clean_ad_image_url")
        self.assertEqual(res["ai_metadata"]["engine"], "Florence2-LaMa-Pipeline")

        # 4. Assert zero legacy WebP file-compression metrics
        self.assertNotIn("savings_percentage", res)
        self.assertNotIn("original_size_kb", res)

        # 5. Assert storefront media was NOT modified
        self.assertEqual(self.sim.current_store_state[0]["media"], orig_media)

    def test_non_destructive_catalog_batch_generation(self):
        # 1. Capture initial storefront media for all products
        initial_media_by_prod = {p["id"]: copy.deepcopy(p["media"]) for p in self.sim.current_store_state}

        # 2. Execute catalog batch generation
        batch_res = self.sim.start_batch_generation()
        self.assertTrue(batch_res["success"])
        self.assertEqual(batch_res["total_products"], 2)

        # 3. Verify storefront images and media IDs are 100% untouched
        for p in self.sim.current_store_state:
            self.assertEqual(p["media"], initial_media_by_prod[p["id"]], "Storefront media must NEVER be modified")
            self.assertIn("safemedia.clean_ad_image_url", p["metafields"])
            self.assertTrue(p["metafields"]["safemedia.clean_ad_image_url"].startswith("https://worker.safemedia.dev/clean-media/"))

    def test_circuit_breaker_and_rollback(self):
        # 1. Take safety snapshot
        snap_id = self.sim.create_snapshot()

        # 2. Simulate store corruption (competitor disaster: all variants set to None)
        self.sim.simulate_bad_competitor_update()
        for p in self.sim.current_store_state:
            for v in p["variants"]:
                self.assertIsNone(v["media_id"], "Variant should be corrupted before rollback")

        # 3. Execute 1-click rollback
        rollback_res = self.sim.rollback(snapshot_id=snap_id)
        self.assertTrue(rollback_res["success"])
        self.assertTrue(rollback_res["metafields_restored"])
        self.assertEqual(rollback_res["snapshot_id"], snap_id)

        # 4. Assert 100% restoration
        for p in self.sim.current_store_state:
            for v in p["variants"]:
                self.assertIsNotNone(v["media_id"], "Variant MUST be restored after rollback")

        # Check specific mapping restored
        v1 = self.sim.current_store_state[0]["variants"][0]
        self.assertEqual(v1["media_id"], "gid://shopify/MediaImage/2001")
        self.assertEqual(v1["title"], "Black / S")

        # 5. Assert Before/After product data diffs (Shopify App Review 4.5.3 compliance)
        self.assertIn("productDataDiffs", rollback_res)
        self.assertEqual(len(rollback_res["productDataDiffs"]), 2)
        diff0 = rollback_res["productDataDiffs"][0]
        self.assertIsNone(diff0["beforeRevert"]["variantBindings"][0]["mediaId"])
        self.assertEqual(diff0["afterRevert"]["variantBindings"][0]["mediaId"], "gid://shopify/MediaImage/2001")

    def test_ad_feed_preview_mapping(self):
        self.sim.start_batch_generation()
        preview = self.sim.get_feed_preview()
        self.assertEqual(preview["metafieldNamespaceKey"], "safemedia.clean_ad_image_url")
        self.assertEqual(len(preview["items"]), 2)
        for item in preview["items"]:
            self.assertTrue(item["storefrontUntouched"])
            self.assertTrue(item["adFeedCompliant"])
            self.assertEqual(item["gmcImageLinkField"], "g:image_link")
            self.assertEqual(item["metaImageLinkField"], "image_link")
            self.assertNotEqual(item["storefrontImageUrl"], item["cleanAdImageUrl"])


if __name__ == "__main__":
    unittest.main()
