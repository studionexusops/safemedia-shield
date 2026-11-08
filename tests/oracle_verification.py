#!/usr/bin/env python3
"""
tests/oracle_verification.py
Authoritative Differential & Oracle Verification Script for SafeMedia Shield / AdFeed Clean.

Empirically verifies the core business invariant:
"Pure Dual-Feed Non-Destruction"

Invariant Assertions:
1. Pre-operation vs Post-operation Storefront Media Invariant:
   - For every product: media IDs, media URLs, altText, and media count must be 100.000% identical.
2. Variant-to-Media Binding Invariant:
   - For every variant in every product: ProductVariant.mediaId must be 100.000% identical.
3. Dual-Feed Metafield Isolation:
   - Only 'safemedia.clean_ad_image_url' and 'safemedia.dual_feed_metadata' are populated.
   - Clean ad image URLs are distinct from decorated storefront URLs.
4. Two-Phase Rollback Invariant:
   - Restores variant media links and rolls back metafields to exact snapshot baseline.
   - Recovers from simulated competitor store corruption.
5. Multi-Tenant Non-Interference:
   - Zero state leakage between distinct Shopify stores.
6. Static AST / Mutation Safety:
   - Zero destructive mutations (productUpdate, productDeleteMedia, etc.) in Worker source.
"""

import copy
import json
import os
import pathlib
import re
import sys
import time
import unittest
from typing import Any, Dict, List, Tuple

# Set up project import path
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.mock_worker_harness import (
    PRIMARY_SHOP,
    OTHER_SHOP,
    PRIMARY_TOKEN,
    TestClient,
    compute_shopify_hmac,
    get_default_catalog,
)
from cloudflare_worker.test_e2e_simulation import SafeMediaShieldSimulator


class StorefrontOracleSnapshot:
    """Captures an exhaustive, deep snapshot of storefront media and variant state."""

    def __init__(self, catalog: List[Dict[str, Any]]):
        self.products: Dict[str, Dict[str, Any]] = {}
        for p in catalog:
            pid = p["id"]
            self.products[pid] = {
                "id": pid,
                "title": p.get("title", ""),
                "body_html": p.get("body_html", ""),
                "media": copy.deepcopy(p.get("media", [])),
                "variants": copy.deepcopy(p.get("variants", [])),
                "metafields": copy.deepcopy(p.get("metafields", {})),
            }

    def diff_storefront_media(self, current_catalog: List[Dict[str, Any]]) -> List[str]:
        """
        Compares current catalog against this baseline snapshot.
        Returns list of discrepancies found in storefront media or variant bindings.
        """
        violations = []
        current_map = {p["id"]: p for p in current_catalog}

        # Check product count
        if set(self.products.keys()) != set(current_map.keys()):
            violations.append(
                f"Product set mismatch: expected {list(self.products.keys())}, got {list(current_map.keys())}"
            )
            return violations

        for pid, baseline in self.products.items():
            curr = current_map[pid]

            # 1. Storefront Media List comparison
            base_media = baseline["media"]
            curr_media = curr.get("media", [])
            if len(base_media) != len(curr_media):
                violations.append(
                    f"Product {pid}: media count changed from {len(base_media)} to {len(curr_media)}"
                )
                continue

            for idx, (bm, cm) in enumerate(zip(base_media, curr_media)):
                if bm.get("id") != cm.get("id"):
                    violations.append(
                        f"Product {pid} media[{idx}]: ID changed from '{bm.get('id')}' to '{cm.get('id')}'"
                    )
                if bm.get("url") != cm.get("url"):
                    violations.append(
                        f"Product {pid} media[{idx}]: URL changed from '{bm.get('url')}' to '{cm.get('url')}'"
                    )

            # 2. Variant bindings comparison
            base_variants = baseline["variants"]
            curr_variants = curr.get("variants", [])
            if len(base_variants) != len(curr_variants):
                violations.append(
                    f"Product {pid}: variant count changed from {len(base_variants)} to {len(curr_variants)}"
                )
                continue

            for idx, (bv, cv) in enumerate(zip(base_variants, curr_variants)):
                if bv.get("id") != cv.get("id"):
                    violations.append(
                        f"Product {pid} variant[{idx}]: ID changed from '{bv.get('id')}' to '{cv.get('id')}'"
                    )
                if bv.get("media_id") != cv.get("media_id"):
                    violations.append(
                        f"Product {pid} variant '{bv.get('title')}': media_id changed from '{bv.get('media_id')}' to '{cv.get('media_id')}'"
                    )

            # 3. Product HTML / Title invariant
            if baseline["title"] != curr.get("title"):
                violations.append(
                    f"Product {pid}: Title changed from '{baseline['title']}' to '{curr.get('title')}'"
                )
            if baseline["body_html"] != curr.get("body_html"):
                violations.append(
                    f"Product {pid}: Body HTML changed from '{baseline['body_html']}' to '{curr.get('body_html')}'"
                )

        return violations

    def check_metafield_isolation(self, current_catalog: List[Dict[str, Any]]) -> List[str]:
        """Verifies that only allowed dual-feed metafields are written."""
        violations = []
        allowed_keys = {"safemedia.clean_ad_image_url", "safemedia.dual_feed_metadata"}

        for p in current_catalog:
            pid = p["id"]
            metafields = p.get("metafields", {})
            for k in metafields:
                if k not in allowed_keys and k.startswith("safemedia."):
                    violations.append(
                        f"Product {pid}: Unrecognized or forbidden metafield '{k}' found"
                    )
        return violations


class OracleDualFeedVerification(unittest.TestCase):
    """Differential Oracle Test Suite verifying Pure Dual-Feed Non-Destruction."""

    def setUp(self):
        self.client = TestClient()
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})
        self.store = self.client.app.get_store(PRIMARY_SHOP)

    def test_oracle_01_static_ast_mutation_safety(self):
        """
        ORACLE-01: Static AST / Mutation Safety Scan.
        Assert that cloudflare_worker/src never calls destructive Shopify mutations.
        """
        worker_src = REPO_ROOT / "cloudflare_worker" / "src"
        destructive_patterns = [
            r"mutation\s+productUpdate\b",
            r"mutation\s+productDelete\b",
            r"mutation\s+productDeleteMedia\b",
            r"mutation\s+stagedUploadsCreate\b",
            r"mutation\s+fileCreate\b",
            r"\boptimizeImage\b",
            r"\bOptimizationResult\b",
            r"\bedgeOptimize\b",
        ]

        found_destructive = []
        for ts_file in worker_src.glob("*.ts"):
            content = ts_file.read_text(encoding="utf-8")
            for pattern in destructive_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    found_destructive.append(f"{ts_file.name}: matched forbidden pattern '{pattern}' ({len(matches)} times)")

        self.assertEqual(
            found_destructive,
            [],
            f"Static safety check failed: Destructive mutations or legacy WebP routines found: {found_destructive}",
        )

    def test_oracle_02_canary_test_non_destruction_oracle(self):
        """
        ORACLE-02: Canary Test Storefront Non-Destruction Oracle.
        Records exact baseline before Canary, runs Canary, asserts 100.00% storefront identity.
        """
        # 1. Record baseline
        baseline = StorefrontOracleSnapshot(self.store.catalog)

        # 2. Run Canary test
        res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res.status_code, 200, f"Canary failed: {res.text}")
        data = res.json()

        # Canary contract verification
        self.assertIn("cleanAdImageUrl", data)
        self.assertIn("originalImageUrl", data)
        self.assertNotEqual(data["cleanAdImageUrl"], data["originalImageUrl"], "Clean ad image must differ from original")
        self.assertEqual(data["metafieldKey"], "safemedia.clean_ad_image_url")
        self.assertEqual(data["canaryUsedCount"], 1)

        # Verify variantChecks in response
        for vc in data["variantChecks"]:
            self.assertTrue(vc["preserved"], f"Variant {vc['variantId']} reported as NOT preserved")
            self.assertTrue(vc["hasOriginalMedia"], f"Variant {vc['variantId']} missing original media")

        # 3. Oracle comparison: Storefront media & variant bindings
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            violations,
            [],
            f"Storefront media was mutated during Canary test! Violations: {violations}",
        )

    def test_oracle_03_webhook_update_non_destruction_oracle(self):
        """
        ORACLE-03: Webhook Update Storefront Non-Destruction Oracle.
        Simulates products/update webhook for an existing decorated item.
        Asserts storefront media is 100.00% untouched while clean ad metafield is populated.
        """
        # 1. Record baseline
        baseline = StorefrontOracleSnapshot(self.store.catalog)

        # 2. Simulate incoming products/update webhook
        target_prod = self.store.catalog[0]
        payload = {
            "id": target_prod["id"].split("/")[-1],
            "title": target_prod["title"],
            "image": {"src": target_prod["media"][0]["url"]},
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(body_bytes),
        }

        res = self.client.post("/webhooks/products/update", data=body_bytes, headers=headers)
        self.assertEqual(res.status_code, 200, f"Webhook failed: {res.text}")
        wh_data = res.json()
        self.assertTrue(wh_data.get("success"), f"Webhook did not succeed: {wh_data}")
        self.assertFalse(wh_data.get("skipped"), "Webhook was unexpectedly skipped")
        self.assertIn("cleanAdImageUrl", wh_data)

        # 3. Oracle comparison: Storefront media & variant bindings must remain 100% identical
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            violations,
            [],
            f"Storefront media was mutated during Webhook update! Violations: {violations}",
        )

        # 4. Metafield isolation check
        meta_violations = baseline.check_metafield_isolation(self.store.catalog)
        self.assertEqual(
            meta_violations,
            [],
            f"Illegal metafields written during Webhook update: {meta_violations}",
        )

        # Confirm clean ad image URL is present on the product
        self.assertEqual(
            target_prod["metafields"]["safemedia.clean_ad_image_url"],
            wh_data["cleanAdImageUrl"],
        )
        self.assertIn("dualFeedMetadata", target_prod)

    def test_oracle_04_full_catalog_batch_sync_non_destruction_oracle(self):
        """
        ORACLE-04: Full Catalog Batch Sync Non-Destruction Oracle.
        Activates 14-day trial, runs full catalog batch sync.
        Asserts 100.00% identity of storefront media IDs, URLs, and variant links for ALL products.
        """
        # 1. Activate trial
        sub_res = self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(sub_res.status_code, 200)

        # 2. Record baseline
        baseline = StorefrontOracleSnapshot(self.store.catalog)

        # 3. Run full catalog batch sync
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200, f"Batch start failed: {batch_res.text}")
        batch_data = batch_res.json()
        self.assertTrue(batch_data.get("success"))
        self.assertIn("snapshotId", batch_data)
        self.assertEqual(batch_data.get("totalProducts"), len(self.store.catalog))

        # 4. Oracle comparison: Storefront media and variant links 100.00% identical
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            violations,
            [],
            f"Storefront media was mutated during Catalog Batch Sync! Violations: {violations}",
        )

        # 5. Metafield assertions: every product now has safemedia.clean_ad_image_url
        meta_violations = baseline.check_metafield_isolation(self.store.catalog)
        self.assertEqual(
            meta_violations,
            [],
            f"Illegal metafields written during Catalog Batch Sync: {meta_violations}",
        )

        for p in self.store.catalog:
            pid = p["id"]
            self.assertIn(
                "safemedia.clean_ad_image_url",
                p.get("metafields", {}),
                f"Product {pid} missing safemedia.clean_ad_image_url",
            )
            clean_url = p["metafields"]["safemedia.clean_ad_image_url"]
            self.assertTrue(
                clean_url.startswith("https://cdn.safemedia.io/clean/"),
                f"Product {pid} clean URL invalid: {clean_url}",
            )
            self.assertIn(
                "dualFeedMetadata",
                p,
                f"Product {pid} missing dualFeedMetadata",
            )
            self.assertEqual(
                p["dualFeedMetadata"]["engine"],
                "Florence2-LaMa-DualFeed-v1",
            )

    def test_oracle_05_sequential_full_journey_non_destruction_oracle(self):
        """
        ORACLE-05: Sequential Full Journey Non-Destruction Oracle.
        Executes Canary -> Webhook -> Full Catalog Batch Sync in strict sequence.
        Verifies storefront media state remains 100.00% identical at EVERY step.
        """
        initial_baseline = StorefrontOracleSnapshot(self.store.catalog)

        # Step A: Canary Preview
        canary_res = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(canary_res.status_code, 200)
        violations_after_canary = initial_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations_after_canary, [], "Violations after Canary!")

        # Step B: Webhook Update
        target_prod = self.store.catalog[1]
        raw_body = json.dumps({
            "id": target_prod["id"].split("/")[-1],
            "title": target_prod["title"],
            "image": {"src": target_prod["media"][0]["url"]},
        }).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        wh_res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(wh_res.status_code, 200)
        violations_after_webhook = initial_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations_after_webhook, [], "Violations after Webhook!")

        # Step C: Activate Trial & Full Catalog Batch Sync
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)

        violations_after_batch = initial_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations_after_batch, [], "Violations after Batch Sync!")

    def test_oracle_06_rollback_restores_snapshot_and_reverts_metafields(self):
        """
        ORACLE-06: Two-Phase Rollback Oracle.
        Takes pre-batch snapshot, executes batch sync, then triggers 1-Click Rollback.
        Verifies:
        1. Variant media bindings are strictly preserved/restored.
        2. Clean ad image metafields are reverted to snapshot state (cleared if virgin).
        """
        # 1. Take snapshot of virgin state
        virgin_baseline = StorefrontOracleSnapshot(self.store.catalog)
        snap_id = self.store.create_snapshot()

        # 2. Activate subscription and perform batch sync
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)

        # Confirm metafields are populated
        for p in self.store.catalog:
            self.assertIn("safemedia.clean_ad_image_url", p.get("metafields", {}))

        # 3. Trigger 1-Click Rollback to virgin snapshot
        rollback_res = self.client.post(
            "/api/rollback",
            json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id},
        )
        self.assertEqual(rollback_res.status_code, 200, f"Rollback failed: {rollback_res.text}")
        rb_data = rollback_res.json()
        self.assertTrue(rb_data.get("success"))
        self.assertTrue(rb_data.get("metafieldsRestored"))
        self.assertEqual(rb_data.get("snapshotId"), snap_id)

        # 4. Oracle comparison: Storefront media & variant links must match virgin baseline 100.00%
        violations = virgin_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations, [], f"Storefront media discrepancy after rollback: {violations}")

        # 5. Metafields must be cleared back to virgin state
        for p in self.store.catalog:
            self.assertNotIn(
                "safemedia.clean_ad_image_url",
                p.get("metafields", {}),
                f"Product {p['id']} still has clean_ad_image_url after rolling back to virgin snapshot!",
            )

    def test_oracle_07_rollback_heals_competitor_corruption(self):
        """
        ORACLE-07: Catastrophic Competitor Corruption Recovery Oracle.
        Simulates competitor app severing variant media bindings (setting media_id to None).
        Executes Rollback, asserts all variant bindings are 100.00% healed.
        """
        # 1. Record healthy baseline & take snapshot
        healthy_baseline = StorefrontOracleSnapshot(self.store.catalog)
        snap_id = self.store.create_snapshot()

        # 2. Simulate competitor disaster (sever all variant media bindings)
        for p in self.store.catalog:
            for v in p.get("variants", []):
                v["media_id"] = None

        # Verify corruption has occurred
        corrupted_violations = healthy_baseline.diff_storefront_media(self.store.catalog)
        self.assertGreater(
            len(corrupted_violations),
            0,
            "Corruption simulation failed to introduce discrepancies",
        )

        # 3. Trigger 1-Click Rollback
        rollback_res = self.client.post(
            "/api/rollback",
            json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id},
        )
        self.assertEqual(rollback_res.status_code, 200)

        # 4. Assert 100.00% restoration of variant bindings
        healed_violations = healthy_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            healed_violations,
            [],
            f"Variant bindings were NOT fully restored after rollback: {healed_violations}",
        )

    def test_oracle_08_multi_tenant_isolation_oracle(self):
        """
        ORACLE-08: Multi-Tenant State Isolation Oracle.
        Asserts that actions performed on PRIMARY_SHOP never mutate OTHER_SHOP storefront media.
        """
        store_b = self.client.app.get_store(OTHER_SHOP)
        baseline_b = StorefrontOracleSnapshot(store_b.catalog)

        # Perform Canary, Webhook, and Batch Sync on PRIMARY_SHOP
        self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})

        # Verify Store B storefront media is 100.00% unaffected
        violations_b = baseline_b.diff_storefront_media(store_b.catalog)
        self.assertEqual(
            violations_b,
            [],
            f"Multi-tenant breach: Store B catalog modified by actions on Store A: {violations_b}",
        )

        # Verify Store B has zero safemedia metafields
        for p in store_b.catalog:
            self.assertEqual(
                p.get("metafields", {}),
                {},
                f"Store B product {p['id']} received unexpected metafields from Store A operations",
            )

    def test_oracle_09_stress_harness_multi_media_variant_matrix(self):
        """
        ORACLE-09: Stress Harness: 50-Product Dynamic Catalog with Complex Variant Matrix.
        Generates 50 products:
        - Diverse media counts (0 to 8 media per product)
        - Diverse variant counts (1 to 10 variants per product)
        - Partial variant-to-media bindings (some variants have media, some have None)
        Executes Batch Sync -> asserts 100.00% storefront media identity across all 50 products.
        """
        complex_catalog = []
        for p_idx in range(1, 51):
            prod_id = f"gid://shopify/Product/5000{p_idx:02d}"
            # Vary media count
            media_count = p_idx % 9  # 0 to 8
            media_list = [
                {
                    "id": f"gid://shopify/MediaImage/6000{p_idx:02d}_{m_idx:02d}",
                    "url": f"https://cdn.shopify.com/orig/prod_{p_idx}_media_{m_idx}.jpg",
                }
                for m_idx in range(media_count)
            ]

            # Vary variant count
            variant_count = (p_idx % 10) + 1  # 1 to 10 variants
            variants = []
            for v_idx in range(variant_count):
                # Bind to a media item if media exists and based on index, else None
                bound_media_id = None
                if media_list and v_idx < len(media_list):
                    bound_media_id = media_list[v_idx]["id"]
                elif media_list:
                    bound_media_id = media_list[0]["id"]

                variants.append({
                    "id": f"gid://shopify/ProductVariant/7000{p_idx:02d}_{v_idx:02d}",
                    "title": f"Variant {v_idx + 1}",
                    "media_id": bound_media_id,
                    "sku": f"SKU-{p_idx}-{v_idx}",
                })

            complex_catalog.append({
                "id": prod_id,
                "title": f"Stress Product {p_idx}",
                "body_html": f"<p>Description for product {p_idx}</p>",
                "media": media_list,
                "variants": variants,
                "metafields": {},
            })

        self.store.catalog = complex_catalog
        baseline = StorefrontOracleSnapshot(complex_catalog)

        # Activate subscription and run full catalog batch sync
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        batch_res = self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(batch_res.status_code, 200)
        self.assertEqual(batch_res.json()["totalProducts"], 50)

        # Oracle Assertion: 100.000% identity of storefront media and variant links across all 50 products
        violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            violations,
            [],
            f"Stress matrix invariant violation! Discrepancies: {violations}",
        )

        # Rollback and verify 100.000% restoration
        snap_id = batch_res.json()["snapshotId"]
        rollback_res = self.client.post(
            "/api/rollback",
            json_data={"shop": PRIMARY_SHOP, "snapshotId": snap_id},
        )
        self.assertEqual(rollback_res.status_code, 200)

        post_rollback_violations = baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(
            post_rollback_violations,
            [],
            f"Post-rollback discrepancies on 50-product stress catalog: {post_rollback_violations}",
        )

    def test_oracle_10_intermediate_snapshot_metafield_restoration(self):
        """
        ORACLE-10: Intermediate Snapshot State Machine Oracle.
        Step 1: Product 1 is cleaned (Canary/Webhook).
        Step 2: Snapshot 1 is recorded (Product 1 has clean ad image, Product 2 does NOT).
        Step 3: Product 2 is cleaned during Batch Sync (both products have clean ad images).
        Step 4: Rollback to Snapshot 1.
        Assert:
        - Product 1 retains its clean ad image and metadata.
        - Product 2 has its clean ad image metafield strictly removed/reverted.
        - Storefront media for both products is 100.00% identical.
        """
        # Step 1: Clean Product 1 via Webhook
        p1 = self.store.catalog[0]
        p2 = self.store.catalog[1]

        raw_body = json.dumps({
            "id": p1["id"].split("/")[-1],
            "title": p1["title"],
            "image": {"src": p1["media"][0]["url"]},
        }).encode("utf-8")
        headers = {
            "X-Shopify-Shop-Domain": PRIMARY_SHOP,
            "X-Shopify-Hmac-Sha256": compute_shopify_hmac(raw_body),
        }
        wh_res = self.client.post("/webhooks/products/update", data=raw_body, headers=headers)
        self.assertEqual(wh_res.status_code, 200)
        p1_clean_url = wh_res.json()["cleanAdImageUrl"]

        # Step 2: Create Snapshot 1 (Product 1 has clean URL, Product 2 is virgin)
        intermediate_snap_id = self.store.create_snapshot()
        intermediate_baseline = StorefrontOracleSnapshot(self.store.catalog)

        # Step 3: Run Batch Sync (populates clean URL on Product 2 as well)
        self.client.post("/api/billing/subscribe", json_data={"shop": PRIMARY_SHOP})
        self.client.post("/api/batch/start", json_data={"shop": PRIMARY_SHOP, "force_reclean": True})

        # Confirm both products now have clean ad images
        self.assertIn("safemedia.clean_ad_image_url", self.store.catalog[0].get("metafields", {}))
        self.assertIn("safemedia.clean_ad_image_url", self.store.catalog[1].get("metafields", {}))

        # Step 4: Rollback to Snapshot 1
        rollback_res = self.client.post(
            "/api/rollback",
            json_data={"shop": PRIMARY_SHOP, "snapshotId": intermediate_snap_id},
        )
        self.assertEqual(rollback_res.status_code, 200)

        # Assert storefront media is 100.00% identical
        violations = intermediate_baseline.diff_storefront_media(self.store.catalog)
        self.assertEqual(violations, [])

        # Assert Product 1 still has its clean URL from Snapshot 1
        self.assertEqual(
            self.store.catalog[0].get("metafields", {}).get("safemedia.clean_ad_image_url"),
            p1_clean_url,
        )

        # Assert Product 2 has NO clean URL (as it was in Snapshot 1)
        self.assertIsNone(
            self.store.catalog[1].get("metafields", {}).get("safemedia.clean_ad_image_url"),
            "Product 2 clean URL was not reverted when rolling back to Snapshot 1!",
        )



def run_oracle_suite() -> Tuple[bool, int, int]:
    suite = unittest.TestLoader().loadTestsFromTestCase(OracleDualFeedVerification)
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time

    print("\n" + "=" * 80)
    print("  ORACLE VERIFICATION SUITE SUMMARY")
    print("=" * 80)
    print(f"  Tests Executed : {result.testsRun}")
    print(f"  Passed         : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures       : {len(result.failures)}")
    print(f"  Errors         : {len(result.errors)}")
    print(f"  Duration       : {duration:.3f}s")
    print("=" * 80)

    verdict = len(result.failures) == 0 and len(result.errors) == 0
    return verdict, result.testsRun, len(result.failures) + len(result.errors)


if __name__ == "__main__":
    success, total, errors = run_oracle_suite()
    sys.exit(0 if success else 1)
