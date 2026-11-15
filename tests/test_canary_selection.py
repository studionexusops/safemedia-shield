import unittest
import json
from tests.e2e.mock_worker_harness import PRIMARY_SHOP, TestClient

class TestCanaryProductSelection(unittest.TestCase):
    """
    Validation for merchant-friendly Canary product selection:
    1. GET /api/products returns catalog with variants count & clean state.
    2. POST /api/canary/test accepts specific productId and runs test on that product.
    3. Invalid productId returns 404 and refunds reserved canary quota.
    4. Omitting productId smartly prioritizes uncleaned products, rotating across catalog on successive runs.
    """

    def setUp(self):
        self.client = TestClient()
        # Reset billing to fresh CANARY_TRIAL
        self.client.post("/api/billing/reset", json_data={"shop": PRIMARY_SHOP, "planStatus": "CANARY_TRIAL", "canaryUsedCount": 0})
        self.store = self.client.app.get_store(PRIMARY_SHOP)

    def test_01_get_products_list_api(self):
        """GET /api/products returns products with metadata, non-empty title, and cleanup status."""
        res = self.client.get(f"/api/products?shop={PRIMARY_SHOP}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("products", data)
        products = data["products"]
        self.assertGreaterEqual(len(products), 1)
        p1 = products[0]
        self.assertIn("id", p1)
        self.assertIn("title", p1)
        self.assertTrue(len(p1["title"]) > 0, "Product title must not be empty")
        self.assertIn("variantCount", p1)
        self.assertIn("hasCleanAdImage", p1)

    def test_02_canary_test_with_specific_product_id(self):
        """POST /api/canary/test processes chosen productId when explicitly supplied."""
        # Get products
        products_res = self.client.get(f"/api/products?shop={PRIMARY_SHOP}").json()["products"]
        self.assertGreaterEqual(len(products_res), 1)
        target_prod = products_res[-1]  # Pick the last product
        target_id = target_prod["id"]

        # Run canary with specific productId
        res = self.client.post("/api/canary/test", json_data={
            "shop": PRIMARY_SHOP,
            "productId": target_id,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["productId"], target_id)
        self.assertEqual(data["canaryUsedCount"], 1)

    def test_03_invalid_product_id_returns_404_and_refunds_quota(self):
        """Supplying non-existent productId returns 404 PRODUCT_NOT_FOUND and does not drain quota."""
        status_before = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        used_before = status_before["billing"]["canaryUsedCount"]

        res = self.client.post("/api/canary/test", json_data={
            "shop": PRIMARY_SHOP,
            "productId": "gid://shopify/Product/9999999999_non_existent",
        })
        self.assertEqual(res.status_code, 404)
        data = res.json()
        self.assertEqual(data.get("code"), "PRODUCT_NOT_FOUND")

        # Verify quota was refunded
        status_after = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_after["billing"]["canaryUsedCount"], used_before)

    def test_04_successive_runs_rotate_uncleaned_products(self):
        """When productId is omitted, canary smartly selects uncleaned products on successive runs."""
        # Add 3 distinct products to store catalog with varying variants
        self.store.catalog = [
            {
                "id": "gid://shopify/Product/1001",
                "title": "Product Alpha (10 variants)",
                "media": [{"url": "https://cdn.shopify.com/orig/alpha.jpg"}],
                "variants": [{"id": f"v_a_{i}", "title": f"Size {i}", "media_id": f"m_a_{i}"} for i in range(10)],
            },
            {
                "id": "gid://shopify/Product/1002",
                "title": "Product Beta (5 variants)",
                "media": [{"url": "https://cdn.shopify.com/orig/beta.jpg"}],
                "variants": [{"id": f"v_b_{i}", "title": f"Color {i}", "media_id": f"m_b_{i}"} for i in range(5)],
            },
            {
                "id": "gid://shopify/Product/1003",
                "title": "Product Gamma (2 variants)",
                "media": [{"url": "https://cdn.shopify.com/orig/gamma.jpg"}],
                "variants": [{"id": f"v_c_{i}", "title": f"Option {i}", "media_id": f"m_c_{i}"} for i in range(2)],
            },
        ]

        # Run 1: Should select Product Alpha (highest variants among uncleaned)
        res1 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["productId"], "gid://shopify/Product/1001")

        # Run 2: Should select Product Beta (highest variants among remaining uncleaned)
        res2 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["productId"], "gid://shopify/Product/1002")

        # Run 3: Should select Product Gamma (last uncleaned product)
        res3 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.json()["productId"], "gid://shopify/Product/1003")

        # Run 4: All products cleaned -> falls back to highest variants (Alpha)
        res4 = self.client.post("/api/canary/test", json_data={"shop": PRIMARY_SHOP})
        self.assertEqual(res4.status_code, 200)
        self.assertEqual(res4.json()["productId"], "gid://shopify/Product/1001")

    def test_05_product_without_image_returns_400_and_refunds_quota(self):
        """When a selected product has no image, return 400 NO_PRODUCT_IMAGE and refund canary quota."""
        # Setup catalog with an imageless product (like The Minimal Snowboard without photos)
        self.store.catalog = [
            {
                "id": "gid://shopify/Product/9001",
                "title": "The Minimal Snowboard (No Media)",
                "media": [],
                "variants": [{"id": "v_1", "title": "Default", "media_id": ""}],
            }
        ]
        status_before = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        used_before = status_before["billing"]["canaryUsedCount"]

        res = self.client.post("/api/canary/test", json_data={
            "shop": PRIMARY_SHOP,
            "productId": "gid://shopify/Product/9001",
        })
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data.get("code"), "NO_PRODUCT_IMAGE")
        self.assertIn("No product image found.", data.get("error", ""))

        # Verify canary quota was not drained (refunded)
        status_after = self.client.get(f"/api/status?shop={PRIMARY_SHOP}").json()
        self.assertEqual(status_after["billing"]["canaryUsedCount"], used_before)

if __name__ == "__main__":
    unittest.main()
