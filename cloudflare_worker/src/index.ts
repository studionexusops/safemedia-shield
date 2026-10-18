/**
 * SafeMedia Shield - Cloudflare Workers Main Entrypoint
 * Handles HTTP Routing, Shopify API orchestration, R2 snapshots, and RunPod execution.
 */

import { Env, CanaryTestResult, BatchJobState } from "./types";
import { ShopifyVariantManager } from "./shopify";
import { SnapshotEngine } from "./snapshot";
import { RunPodClient } from "./runpod_client";
import { renderDashboardHtml } from "./ui";

let currentJobState: BatchJobState = {
  jobId: "init",
  status: "IDLE",
  total: 0,
  processed: 0,
  errors: [],
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const shop = url.searchParams.get("shop") || env.SHOPIFY_SHOP || "safemedia-test-20261011.myshopify.com";

    // Set CORS headers for embedded app requests
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Shopify-Access-Token",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // 1. Dashboard UI Route
    if (url.pathname === "/" && request.method === "GET") {
      const html = renderDashboardHtml(shop);
      return new Response(html, {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // 1.5 Public CDN Route: Serve AI-Cleaned Ad Images from Cloudflare R2
    // Used by Shopify Metafield (safemedia.clean_ad_image_url) & Google Merchant Center Feeds
    if (url.pathname.startsWith("/clean-media/") && request.method === "GET") {
      const parts = url.pathname.replace("/clean-media/", "").split("/");
      if (parts.length >= 2 && env.SNAPSHOT_BUCKET) {
        const r2Key = `clean_images/${parts[0]}/${parts.slice(1).join("/")}`;
        const obj = await env.SNAPSHOT_BUCKET.get(r2Key);
        if (obj) {
          return new Response(obj.body, {
            headers: {
              "Content-Type": obj.httpMetadata?.contentType || "image/jpeg",
              "Cache-Control": "public, max-age=31536000, immutable",
              ...corsHeaders,
            },
          });
        }
      }
      return new Response("Clean media not found", { status: 404, headers: corsHeaders });
    }

    // Initialize core services
    const shopHeader = request.headers.get("X-Shopify-Shop-Domain");
    const activeShop = shopHeader || shop;
    const token = request.headers.get("X-Shopify-Access-Token") || env.SHOPIFY_ACCESS_TOKEN || "";
    const variantManager = new ShopifyVariantManager(activeShop, token);
    const snapshotEngine = new SnapshotEngine(env, activeShop);
    const runpodClient = new RunPodClient(env);

    // 2. API: Current Status, Snapshot Info & Dual-Feed Metafield Status
    if (url.pathname === "/api/status" && request.method === "GET") {
      const [latestSnapshot, r2Objects, products] = await Promise.all([
        snapshotEngine.getLatestSnapshot(),
        snapshotEngine.listR2Objects(),
        variantManager.fetchProductsWithVariants().catch(() => []),
      ]);

      const dualFeedProducts = products.map((p) => ({
        productId: p.productId,
        productTitle: p.productTitle,
        storefrontImageUrl: p.originalMediaList[0]?.url || "",
        cleanAdImageUrl: p.cleanAdImageUrl || null,
        dualFeedMetadata: p.dualFeedMetadata || null,
      }));

      return Response.json(
        {
          shop: activeShop,
          protectionActive: true,
          r2BucketName: "safemedia-snapshots",
          r2Objects,
          latestSnapshot: latestSnapshot
            ? {
                snapshotId: latestSnapshot.snapshotId,
                createdAt: latestSnapshot.createdAt,
                totalProducts: latestSnapshot.totalProducts,
                totalImages: latestSnapshot.totalImages,
                r2Key: `snapshots/${activeShop}/${latestSnapshot.snapshotId}.json`,
              }
            : null,
          dualFeedProducts,
          jobState: currentJobState,
        },
        { headers: corsHeaders }
      );
    }

    // 2.2 API: Register Shopify PRODUCTS_UPDATE Webhook
    if (url.pathname === "/api/webhooks/register" && request.method === "POST") {
      try {
        const callbackUrl = `${url.origin}/webhooks/products/update`;
        const result = await variantManager.registerProductUpdateWebhook(callbackUrl);
        return Response.json(result, { headers: corsHeaders });
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 2.3 Webhook Receiver: Shopify `products/update` (Zero-UI Event-Driven Dual-Feed Routing)
    if (url.pathname === "/webhooks/products/update" && request.method === "POST") {
      try {
        const payload = (await request.json()) as any;
        const productNumericId = payload.id;
        if (!productNumericId) {
          return Response.json({ skipped: true, reason: "missing_product_id" }, { headers: corsHeaders });
        }

        const productId = `gid://shopify/Product/${productNumericId}`;
        const primaryImageUrl = payload.image?.src || payload.images?.[0]?.src;
        if (!primaryImageUrl) {
          return Response.json({ skipped: true, reason: "no_product_image" }, { headers: corsHeaders });
        }

        // Prevent infinite webhook loop: check if this exact image URL was already processed
        const currentProducts = await variantManager.fetchProductsWithVariants();
        const targetProd = currentProducts.find((p) => p.productId === productId);
        if (
          targetProd?.dualFeedMetadata?.sourceImageUrl === primaryImageUrl &&
          targetProd?.cleanAdImageUrl &&
          !payload.force_reclean
        ) {
          return Response.json(
            {
              success: true,
              skipped: true,
              reason: "already_cleaned_for_current_image",
              productId,
              cleanAdImageUrl: targetProd.cleanAdImageUrl,
            },
            { headers: corsHeaders }
          );
        }

        // Execute AI Cleanup -> Save to Cloudflare R2 -> Write to Shopify Hidden Metafield
        const cleanResult = await runpodClient.cleanImageForAdFeed({
          shop: activeShop,
          productId,
          imageUrl: primaryImageUrl,
          workerOrigin: url.origin,
          precleanedBase64: payload.clean_image_base64,
          maskCoveragePct: payload.mask_coverage_pct,
          processingSec: payload.processing_sec,
        });

        await variantManager.setCleanAdImageMetafield(productId, cleanResult.cleanAdImageUrl, {
          sourceImageUrl: primaryImageUrl,
          cleanedAt: new Date().toISOString(),
          maskCoveragePct: cleanResult.maskCoveragePct,
          processingSec: cleanResult.processingSec,
          engine: cleanResult.engine,
        });

        return Response.json(
          {
            success: true,
            skipped: false,
            productId,
            productTitle: payload.title || targetProd?.productTitle,
            storefrontImageUrl: primaryImageUrl,
            cleanAdImageUrl: cleanResult.cleanAdImageUrl,
            metafieldNamespace: "safemedia",
            metafieldKey: "clean_ad_image_url",
            processingSec: cleanResult.processingSec,
            maskCoveragePct: cleanResult.maskCoveragePct,
            engine: cleanResult.engine,
          },
          { headers: corsHeaders }
        );
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 2.4 API: On-Demand Dual-Feed Sync (E2E Verification & Manual Trigger)
    if (url.pathname === "/api/dual-feed/sync" && request.method === "POST") {
      try {
        const body = (await request.json().catch(() => ({}))) as any;
        const products = await variantManager.fetchProductsWithVariants();
        if (products.length === 0) {
          return Response.json({ error: "No products found in store." }, { status: 400, headers: corsHeaders });
        }

        // Select requested product or the main multi-variant product
        const targetProduct =
          (body.productId && products.find((p) => p.productId === body.productId || p.productId.endsWith(`/${body.productId}`))) ||
          products.reduce((prev, curr) => (curr.variants.length > prev.variants.length ? curr : prev));

        const storefrontImageUrl =
          body.sourceImageUrl ||
          targetProduct.originalMediaList[0]?.url ||
          "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800";

        const cleanResult = await runpodClient.cleanImageForAdFeed({
          shop: activeShop,
          productId: targetProduct.productId,
          imageUrl: storefrontImageUrl,
          workerOrigin: url.origin,
          precleanedBase64: body.cleanImageBase64,
          maskCoveragePct: body.maskCoveragePct,
          processingSec: body.processingSec,
        });

        await variantManager.setCleanAdImageMetafield(targetProduct.productId, cleanResult.cleanAdImageUrl, {
          sourceImageUrl: storefrontImageUrl,
          cleanedAt: new Date().toISOString(),
          maskCoveragePct: cleanResult.maskCoveragePct,
          processingSec: cleanResult.processingSec,
          engine: cleanResult.engine,
        });

        return Response.json(
          {
            success: true,
            productId: targetProduct.productId,
            productTitle: targetProduct.productTitle,
            storefrontImageUrl,
            cleanAdImageUrl: cleanResult.cleanAdImageUrl,
            r2Key: cleanResult.r2Key,
            metafieldNamespace: "safemedia",
            metafieldKey: "clean_ad_image_url",
            processingSec: cleanResult.processingSec,
            maskCoveragePct: cleanResult.maskCoveragePct,
            engine: cleanResult.engine,
          },
          { headers: corsHeaders }
        );
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 2.5 API: Create Snapshot On-Demand
    if (url.pathname === "/api/snapshot/create" && request.method === "POST") {
      try {
        const products = await variantManager.fetchProductsWithVariants();
        const snapshot = await snapshotEngine.createSnapshot(products);
        return Response.json(
          {
            success: true,
            snapshotId: snapshot.snapshotId,
            r2BucketName: "safemedia-snapshots",
            r2Key: `snapshots/${activeShop}/${snapshot.snapshotId}.json`,
            createdAt: snapshot.createdAt,
            totalProducts: snapshot.totalProducts,
            totalImages: snapshot.totalImages,
            message: "ストアの最新状態をCloudflare R2へ安全にバックアップ（スナップショット保存）しました。",
          },
          { headers: corsHeaders }
        );
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 3. API: Canary Test (1-Product Verification - Dual-Feed + Variant Preserve)
    if (url.pathname === "/api/canary/test" && request.method === "POST") {
      try {
        const products = await variantManager.fetchProductsWithVariants();
        if (products.length === 0) {
          return Response.json({ error: "No products found in store." }, { status: 400, headers: corsHeaders });
        }

        // Auto-select the product with the most variants for rigorous testing
        const canaryProduct = products.reduce((prev, curr) =>
          curr.variants.length > prev.variants.length ? curr : prev
        );

        const targetImage = canaryProduct.originalMediaList[0]?.url || "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800";
        const optResult = await runpodClient.optimizeImage(targetImage);

        const variantChecks = canaryProduct.variants.map((v) => ({
          variantId: v.variantId,
          variantTitle: v.variantTitle,
          preserved: Boolean(v.originalMediaId),
          activeImageUrl: v.originalImageUrl || targetImage,
        }));

        const canaryResponse: CanaryTestResult = {
          productId: canaryProduct.productId,
          productTitle: canaryProduct.productTitle,
          originalSizeKB: Math.round(optResult.originalBytes / 1024),
          optimizedSizeKB: Math.round(optResult.optimizedBytes / 1024),
          savingsPercentage: optResult.savingsPercentage,
          originalImageUrl: targetImage,
          optimizedImageUrl: canaryProduct.cleanAdImageUrl || optResult.optimizedImageUrl || targetImage,
          cleanAdImageUrl: canaryProduct.cleanAdImageUrl,
          metafieldKey: "safemedia.clean_ad_image_url",
          variantChecks,
        };

        return Response.json(canaryResponse, { headers: corsHeaders });
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 4. API: Start Batch Optimization
    if (url.pathname === "/api/batch/start" && request.method === "POST") {
      const products = await variantManager.fetchProductsWithVariants();

      // Create snapshot before touching anything
      const snapshot = await snapshotEngine.createSnapshot(products);

      currentJobState = {
        jobId: snapshot.snapshotId,
        status: "RUNNING",
        total: products.length,
        processed: 0,
        startedAt: new Date().toISOString(),
        errors: [],
      };

      return Response.json(
        {
          success: true,
          jobId: currentJobState.jobId,
          total: products.length,
          snapshotId: snapshot.snapshotId,
          message: "Safe batch processing initiated with pre-execution snapshot saved.",
        },
        { headers: corsHeaders }
      );
    }

    // 5. API: Emergency Circuit Breaker (Abort)
    if (url.pathname === "/api/batch/abort" && request.method === "POST") {
      currentJobState.status = "ABORTED";
      return Response.json(
        { success: true, message: "Circuit breaker activated. Batch operation immediately halted." },
        { headers: corsHeaders }
      );
    }

    // 6. API: 1-Click Time Machine Rollback
    if (url.pathname === "/api/rollback" && request.method === "POST") {
      try {
        const result = await snapshotEngine.rollbackToSnapshot(variantManager);
        return Response.json(result, { headers: corsHeaders });
      } catch (err: any) {
        return Response.json({ success: false, error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    return new Response("Not Found", { status: 404, headers: corsHeaders });
  },
};
