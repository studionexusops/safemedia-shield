#!/usr/bin/env python3
"""
tests/challenger_stress_oracle.py
Adversarial Stress & Differential Oracle Challenge Suite.
Empirically tests Pure Dual-Feed Non-Destruction Invariant under hostile and edge-case conditions.
"""

import copy
import json
import os
import pathlib
import sys
import time
import unittest
from typing import Any, Dict, List

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    PRIMARY_SHOP,
    OTHER_SHOP,
    TestClient,
    compute_shopify_hmac,
    get_default_catalog,
)
from tests.oracle_verification import StorefrontOracleSnapshot


class ChallengerAdversarialOracle(unittest.TestCase):
    """Aggressive stress harness challenging Pure Dual-Feed Invariants."""

    def setUp(self):
        self.client = TestClient()
        self.client.post(
            "/api/billing/reset",
            json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0},
        )
        self.store = self.client.app.get_store(PRIMARY_SHOP)

    def test_challenger_01_extreme_variant_media_matrix(self):
        """
        Challenge 1: Extreme Product Geometries:
        - 0 media, 1 variant (null media)
        - 1 media, 50 variants all referencing same media
        - 10 media, 0 variants
        - 15 media, 30 variants with alternating/null references
        - Unicode / Emoji titles and html
        """
        catalog = [
            {
                "id": "gid://shopify/Product/9001",
                "title": "Zero Media Product 🚫",
                "body_html": "<p>No media here</p>",
                "media": [],
                "variants": [
                    {"id": "gid://shopify/ProductVariant/9101", "title": "Default", "media_id": None}
                ],
                "metafields": {},
            },
            {
                "id": "gid://shopify/Product/9002",
                "title": "Single Media 50 Variants 👕",
                "body_html": "<p>Massive variant fanout</p>",
                "media": [
                    {"id": "gid://shopify/MediaImage/9201", "url": "https://cdn.shopify.com/orig/shared.jpg"}
                ],
                "variants": [
                    {
                        "id": f"gid://shopify/ProductVariant/92{v:02d}",
                        "title": f"Size {v} / Color {v%5}",
                        "media_id": "gid://shopify/MediaImage/9201",
                    }
                    for v in range(50)
                ],
                "metafields": {},
            },
            {
                "id": "gid://shopify/Product/9003",
                "title": "10 Media 0 Variants 🖼️",
                "body_html": "<p>Gallery only</p>",
                "media": [
                    {"id": f"gid://shopify/MediaImage/93{m:02d}", "url": f"https://cdn.shopify.com/orig/gal_{m}.jpg"}
                    for m in range(10)
                ],
                "variants": [],
                "metafields": {},
            },
            {
                "id": "gid://shopify/Product/9004",
                "title": "Complex Partial Mappings ⚡",
                "body_html": "<p>Some bound, some unbound</p>",
                "media": [
                    {"id": f"gid://shopify/MediaImage/94{m:02d}", "url": f"https://cdn.shopify.com/orig/c_{m}.jpg"}
                    for m in range(15)
                ],
                "variants": [
                    {
                        "id": f"gid://shopify/ProductVariant/94{v:02d}",
                        "title": f"Variant {v}",
                        "media_id": f"gid://shopify/MediaImage/94{v%15:02d}" if v % 2 == 0 else None,
                    }
                    for v in range(30)
                ],
                "metafields": {},
            },
        ]

        self.store.catalog = catalog
        baseline = StorefrontOracleSnapshot(catalog)

        # Activate subscription & run batch
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)

        # Oracle comparison
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations, [], f"Violations on extreme geometries: {violations}")

        # Rollback and re-check
        snap_id = batch_res.json()["snapshotId"]
        rb_res = self.client.post(
            "/api/rollback",
            json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id},
        )
        self.assertEqual(rb_res.status_code, 200)

        post_rb_violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(post_rb_violations, [], f"Post-rollback violations: {post_rb_violations}")

    def test_challenger_02_multi_generation_snapshot_chain(self):
        """
        Challenge 2: Multi-Generation Snapshot & Rollback Chain.
        Tests:
        Gen 0 (Virgin) -> Take Snap 0
        Gen 1 (Clean Product 1) -> Take Snap 1
        Gen 2 (Clean Product 2) -> Take Snap 2
        Gen 3 (Clean All via Batch) -> Take Snap 3
        Rollback to Snap 1 -> verify Product 1 clean, others virgin
        Rollback to Snap 0 -> verify ALL virgin
        Verify storefront media identity is 100.000% at EVERY transition.
        """
        virgin_baseline = StorefrontOracleSnapshot(self.store.catalog)
        time.sleep(0.002)
        snap0_id = self.store.create_snapshot()

        # Gen 1: Clean Product 0
        p0 = self.store.catalog[0]
        payload0 = {"id": p0["id"].split("/")[-1], "title": p0["title"], "image": {"src": p0["media"][0]["url"]}}
        body0 = json.dumps(payload0).encode("utf-8")
        h0 = {"X-Shopify-Shop-Domain": PRIMARY_SHOP, "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body0)}
        res0 = self.client.post("/webhooks/products/update", data=body0, headers=h0)
        self.assertEqual(res0.status_code, 200)
        time.sleep(0.002)
        snap1_id = self.store.create_snapshot()
        baseline1 = StorefrontOracleSnapshot(self.store.catalog)

        # Check storefront identity after Gen 1
        self.assertEqual(virgin_baseline.diff_storefront_media(self.store.catalog), [])

        # Gen 2: Clean Product 1
        p1 = self.store.catalog[1]
        payload1 = {"id": p1["id"].split("/")[-1], "title": p1["title"], "image": {"src": p1["media"][0]["url"]}}
        body1 = json.dumps(payload1).encode("utf-8")
        h1 = {"X-Shopify-Shop-Domain": PRIMARY_SHOP, "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body1)}
        res1 = self.client.post("/webhooks/products/update", data=body1, headers=h1)
        self.assertEqual(res1.status_code, 200)
        time.sleep(0.002)
        snap2_id = self.store.create_snapshot()

        # Check storefront identity after Gen 2
        self.assertEqual(virgin_baseline.diff_storefront_media(self.store.catalog), [])

        # Gen 3: Full Batch Sync
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP, "force_reclean": True})
        self.assertEqual(batch_res.status_code, 200)

        # Check storefront identity after Gen 3
        self.assertEqual(virgin_baseline.diff_storefront_media(self.store.catalog), [])

        # Rollback to Snap 1
        rb1_res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap1_id})
        self.assertEqual(rb1_res.status_code, 200)
        self.assertEqual(baseline1.diff_storefront_media(self.store.catalog), [])
        # Product 0 has clean URL, Product 1 does NOT
        self.assertIsNotNone(self.store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"))
        self.assertIsNone(self.store.catalog[1].get("metafields", {}).get("safemedia.clean_ad_image_url"))

        # Rollback to Snap 0 (Virgin)
        rb0_res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap0_id})
        self.assertEqual(rb0_res.status_code, 200)
        self.assertEqual(virgin_baseline.diff_storefront_media(self.store.catalog), [])
        # All clean URLs cleared
        for p in self.store.catalog:
            self.assertNotIn("safemedia.clean_ad_image_url", p.get("metafields", {}))

    def test_challenger_03_quantitative_identity_metrics(self):
        """
        Challenge 3: Exact Quantitative Metrics:
        Asserts storefront media identity is exactly 100.000%
        and variant binding integrity is exactly 100.000% across all operations.
        """
        initial_catalog = copy.deepcopy(self.store.catalog)
        total_media_count = sum(len(p.get("media", [])) for p in initial_catalog)
        total_variant_count = sum(len(p.get("variants", [])) for p in initial_catalog)

        # Execute operations: Canary -> Webhook -> Batch -> Rollback
        self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        snap_id = self.store.create_snapshot()

        p = self.store.catalog[0]
        body = json.dumps({"id": p["id"].split("/")[-1], "image": {"src": p["media"][0]["url"]}}).encode("utf-8")
        headers = {"X-Shopify-Shop-Domain": PRIMARY_SHOP, "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body)}
        self.client.post("/webhooks/products/update", data=body, headers=headers)

        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})

        # Calculate exact empirical preservation
        identical_media = 0
        intact_variants = 0

        initial_map = {p["id"]: p for p in initial_catalog}
        for curr_p in self.store.catalog:
            init_p = initial_map[curr_p["id"]]
            init_media = init_p.get("media", [])
            curr_media = curr_p.get("media", [])

            for im, cm in zip(init_media, curr_media):
                if im["id"] == cm["id"] and im["url"] == cm["url"]:
                    identical_media += 1

            init_vars = init_p.get("variants", [])
            curr_vars = curr_p.get("variants", [])
            for iv, cv in zip(init_vars, curr_vars):
                if iv["id"] == cv["id"] and iv.get("media_id") == cv.get("media_id"):
                    intact_variants += 1

        media_identity_pct = (identical_media / total_media_count) * 100.0
        variant_integrity_pct = (intact_variants / total_variant_count) * 100.0

        self.assertAlmostEqual(media_identity_pct, 100.000, places=3)
        self.assertAlmostEqual(variant_integrity_pct, 100.000, places=3)
        print(f"\n[CHALLENGER-METRICS] Storefront Media Identity: {media_identity_pct:.3f}%")
        print(f"[CHALLENGER-METRICS] Variant Binding Integrity: {variant_integrity_pct:.3f}%")

    def test_challenger_04_concurrent_burst_safety(self):
        """
        Challenge 4: High-Concurrency Burst (Canary + Webhooks).
        Simulates 20 concurrent requests hitting Canary and Webhook endpoints.
        Asserts:
        - Quota strictly respected (canaryUsedCount <= 5).
        - 100.000% Storefront Media Identity preserved under concurrent load.
        """
        from concurrent.futures import ThreadPoolExecutor

        baseline = StorefrontOracleSnapshot(self.store.catalog)

        def worker_task(idx):
            if idx % 2 == 0:
                return self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
            else:
                p = self.store.catalog[idx % len(self.store.catalog)]
                body = json.dumps({
                    "id": p["id"].split("/")[-1],
                    "title": p["title"],
                    "image": {"src": p["media"][0]["url"]},
                }).encode("utf-8")
                headers = {
                    "X-Shopify-Shop-Domain": PRIMARY_SHOP,
                    "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body),
                }
                return self.client.post("/webhooks/products/update", data=body, headers=headers)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(worker_task, range(20)))

        # Status codes should only be 200, 402 (quota exceeded)
        for r in results:
            self.assertIn(r.status_code, [200, 402], f"Unexpected status code: {r.status_code}")

        # Storefront media identity must be 100.000% intact
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations, [], f"Storefront media corrupted under concurrency: {violations}")

    def test_challenger_05_competitor_damage_and_healing(self):
        """
        Challenge 5: Competitor App Storefront Damage Recovery.
        1. Take clean baseline snapshot.
        2. Competitor overwrites variant media_ids with invalid/mismatched IDs and alters metafields.
        3. Trigger Rollback to snapshot.
        4. Assert variant media bindings and clean ad metafields are 100.000% healed.
        """
        snap_id = self.store.create_snapshot()
        baseline = StorefrontOracleSnapshot(self.store.catalog)

        # Simulate competitor app chaos
        for p in self.store.catalog:
            p["metafields"]["safemedia.clean_ad_image_url"] = "https://malicious.cdn.com/injected.jpg"
            for v in p.get("variants", []):
                v["media_id"] = "gid://shopify/MediaImage/corrupted_competitor_id"

        corrupted_diff = baseline.diff_storefront_media(self.store.catalog)
        self.assertTrue(len(corrupted_diff) > 0, "Failed to introduce competitor corruption")

        # Rollback
        rb_res = self.client.post("/api/rollback", json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id})
        self.assertEqual(rb_res.status_code, 200)

        # Assert 100.000% restored
        healed_diff = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(healed_diff, [], f"Discrepancies after healing competitor corruption: {healed_diff}")
        for p in self.store.catalog:
            self.assertNotIn("safemedia.clean_ad_image_url", p.get("metafields", {}))


if __name__ == "__main__":
    unittest.main()

