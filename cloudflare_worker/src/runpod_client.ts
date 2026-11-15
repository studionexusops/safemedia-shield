/**
 * RunPod Serverless AI Cleanup Client
 * Pure Dual-Feed: Calls the RunPod Serverless endpoint (Florence-2 + LaMa)
 * to remove promotional badges, text, and watermarks for Google Merchant Center ad feeds.
 * Features built-in mock fallback for development & offline testing.
 */

import { Env } from "./types";
import { isValidPublicImageUrl } from "./index";

export interface CleanAdImageResult {
  status: "success" | "error";
  cleanAdImageUrl: string;
  r2Key?: string;
  processingSec: number;
  maskCoveragePct: number;
  engine: string;
  deferredToCallback?: boolean;
  jobId?: string;
}

const MAX_PRECLEANED_IMAGE_BYTES = 15 * 1024 * 1024; // 15 MB

function isSupportedRasterMagicBytes(bytes: Uint8Array): boolean {
  if (bytes.length < 12) return false;
  // JPEG: FF D8 FF
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return true;
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) {
    return true;
  }
  // GIF: GIF87a / GIF89a
  if (bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x38) return true;
  // WebP: RIFF....WEBP
  if (
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return true;
  }
  return false;
}

function shortUrlHash(input: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

export class RunPodClient {
  private env: Env;
  private apiKey?: string;
  private endpointId?: string;
  private inpaintApiUrl?: string;

  constructor(env: Env) {
    this.env = env;
    this.apiKey = env.RUNPOD_API_KEY;
    this.endpointId = env.RUNPOD_ENDPOINT_ID;
    this.inpaintApiUrl = env.INPAINT_API_URL;
  }

  /**
   * Priority 1: Dual-Feed AI Cleanup (Florence-2 + Mask Dilate + LaMa Inpainting)
   * Takes a decorated storefront image URL (or pre-cleaned base64 payload),
   * stores the cleaned image in Cloudflare R2, and returns a publicly crawlable HTTPS URL
   * suitable for Shopify Metafield (`type: "url"`) and Google Merchant Center feeds.
   */
  async cleanImageForAdFeed(params: {
    shop: string;
    productId: string;
    imageUrl: string;
    workerOrigin: string;
    precleanedBase64?: string;
    maskCoveragePct?: number;
    processingSec?: number;
    callbackUrl?: string;
    engineOverride?: string;
  }): Promise<CleanAdImageResult> {
    if (!params.precleanedBase64 && !isValidPublicImageUrl(params.imageUrl)) {
      throw new Error(`Unsafe or invalid image URL blocked by SSRF filter: ${params.imageUrl}`);
    }

    const startMs = Date.now();
    const numericId = params.productId.replace(/\D/g, "") || "prod";
    const imgHash = shortUrlHash(params.imageUrl);
    const filename = `clean_${numericId}_${imgHash}_${Date.now()}.jpg`;
    const r2Key = `clean_images/${params.shop}/${filename}`;
    const publicCleanUrl = `${params.workerOrigin}/clean-media/${params.shop}/${filename}`;

    let imageBytes: Uint8Array | null = null;
    let maskCoveragePct = params.maskCoveragePct ?? 1.6;
    let engine = "Florence2-LaMa-Pipeline";
    let reportedSec = params.processingSec;

    // Case 1: Direct base64 from local Python pipeline or webhook worker push
    if (params.precleanedBase64) {
      const hasDataPrefix = params.precleanedBase64.startsWith("data:");
      if (hasDataPrefix && !/^data:image\/(jpeg|jpg|png|webp|gif);base64,/i.test(params.precleanedBase64)) {
        throw new Error("Unsupported precleaned image data URI MIME type.");
      }
      const cleanB64 = params.precleanedBase64.replace(/^data:image\/(jpeg|jpg|png|webp|gif);base64,/i, "");
      if (cleanB64.length > Math.ceil((MAX_PRECLEANED_IMAGE_BYTES * 4) / 3) + 4) {
        throw new Error("Precleaned base64 payload exceeds maximum allowed image size.");
      }
      const binaryStr = atob(cleanB64);
      if (binaryStr.length > MAX_PRECLEANED_IMAGE_BYTES) {
        throw new Error("Decoded precleaned image exceeds maximum allowed size.");
      }
      const bytes = new Uint8Array(binaryStr.length);
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }
      if (!isSupportedRasterMagicBytes(bytes)) {
        throw new Error("Precleaned payload failed raster image magic-byte validation.");
      }
      imageBytes = bytes;
      engine = params.engineOverride || "Florence2-LaMa-LocalVerified";
    }
    // Case 2: External Inpainting API URL (e.g. local tunnel or dedicated inference microservice)
    else if (this.inpaintApiUrl) {
      const res = await fetch(this.inpaintApiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(15_000),
        body: JSON.stringify({
          input: {
            task: "inpaint_clean",
            image_url: params.imageUrl,
          },
        }),
      });
      if (!res.ok) {
        throw new Error(`Inpaint API error: ${res.status}`);
      }
      interface InpaintApiResponse {
        output?: {
          image_base64?: string;
          mask_coverage_pct?: number;
          processing_sec?: number;
        };
        image_base64?: string;
        mask_coverage_pct?: number;
        processing_sec?: number;
      }
      const data = (await res.json()) as InpaintApiResponse;
      const out = data.output || data;
      if (out.image_base64) {
        const cleanB64 = out.image_base64.replace(/^data:image\/\w+;base64,/, "");
        const binaryStr = atob(cleanB64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        imageBytes = bytes;
        maskCoveragePct = out.mask_coverage_pct ?? maskCoveragePct;
        reportedSec = out.processing_sec ?? reportedSec;
        engine = "Florence2-LaMa-API";
      }
    }
    // Case 3: RunPod Serverless GPU Endpoint (Webhook Callback Separation + Fast Polling)
    else if (this.apiKey && this.endpointId) {
      const endpointUrl = `https://api.runpod.ai/v2/${this.endpointId}/run`;
      const res = await fetch(endpointUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        signal: AbortSignal.timeout(10_000),
        body: JSON.stringify({
          input: {
            task: "inpaint_clean",
            image_url: params.imageUrl,
            dilate_px: 6,
          },
          ...(params.callbackUrl ? { webhook: params.callbackUrl } : {}),
        }),
      });
      if (!res.ok) {
        throw new Error(`AI Inpaint API failed: ${res.status}`);
      }
      interface RunPodServerlessJobResponse {
        id?: string;
        status?: string;
        error?: string;
        output?: {
          status?: string;
          message?: string;
          image_base64?: string;
          mask_coverage_pct?: number;
          processing_sec?: number;
          engine?: string;
        };
      }
      let data = (await res.json()) as RunPodServerlessJobResponse;
      let pollCount = 0;
      // When callbackUrl is registered, poll up to 10s (10 * 1s) so Worker #1 finishes with plenty of headroom (>15s remaining)
      // before Cloudflare's 30s ctx.waitUntil wall-clock limit; if RunPod is cold-starting (>10s),
      // RunPod's native webhook callback will deliver the completed output to /webhooks/runpod/callback in a fresh Worker invocation.
      const maxPollAttempts = params.callbackUrl ? 10 : 25;
      const pollIntervalMs = params.callbackUrl ? 1000 : 2000;
      while (
        (data.status === "IN_QUEUE" || data.status === "IN_PROGRESS") &&
        data.id &&
        pollCount < maxPollAttempts
      ) {
        await new Promise((r) => setTimeout(r, pollIntervalMs));
        const statusRes = await fetch(`https://api.runpod.ai/v2/${this.endpointId}/status/${data.id}`, {
          headers: { Authorization: `Bearer ${this.apiKey}` },
          signal: AbortSignal.timeout(5_000),
        });
        if (statusRes.ok) {
          data = (await statusRes.json()) as RunPodServerlessJobResponse;
        }
        pollCount++;
      }
      if (
        params.callbackUrl &&
        data.id &&
        (data.status === "IN_QUEUE" || data.status === "IN_PROGRESS")
      ) {
        return {
          status: "success",
          deferredToCallback: true,
          jobId: data.id,
          cleanAdImageUrl: "",
          processingSec: Number(((Date.now() - startMs) / 1000).toFixed(2)),
          maskCoveragePct: 0,
          engine: "RunPod-Serverless-Callback-Pending",
        };
      }
      const out = data.output;
      if (!out || out.status !== "success" || !out.image_base64) {
        if (data.status === "IN_QUEUE" || data.status === "IN_PROGRESS") {
          throw new Error("AI processing engine is warming up. Please wait 10 seconds and try again.");
        }
        throw new Error(`AI processing failed (${data.status}). Please try again.`);
      }
      const binaryStr = atob(out.image_base64);
      const bytes = new Uint8Array(binaryStr.length);
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }
      imageBytes = bytes;
      maskCoveragePct = out.mask_coverage_pct ?? maskCoveragePct;
      reportedSec = out.processing_sec ?? reportedSec;
      engine = "RunPod-Serverless-Florence2-LaMa";
    }
    // Case 4: Edge Fallback (fetches source image and stores immutable clean copy in R2)
    else {
      if (!isValidPublicImageUrl(params.imageUrl)) {
        throw new Error(`Unsafe or invalid image URL for edge fallback: ${params.imageUrl}`);
      }
      const res = await fetch(params.imageUrl, {
        signal: AbortSignal.timeout(10_000),
        redirect: "error",
      });
      const contentType = res.headers.get("content-type") || "";
      if (
        res.ok &&
        ((contentType.startsWith("image/") && !contentType.includes("svg")) ||
          contentType === "application/octet-stream")
      ) {
        const fetchedBytes = new Uint8Array(await res.arrayBuffer());
        if (fetchedBytes.length > MAX_PRECLEANED_IMAGE_BYTES || !isSupportedRasterMagicBytes(fetchedBytes)) {
          throw new Error("Fetched image exceeds size limit or failed raster magic-byte validation.");
        }
        imageBytes = fetchedBytes;
      } else {
        throw new Error(`Invalid response or non-image content type (${contentType}) from image URL`);
      }
      engine = "Edge-R2-Proxy (Configure RUNPOD_ENDPOINT_ID or precleanedBase64 for GPU)";
    }

    if (imageBytes && this.env.SNAPSHOT_BUCKET) {
      await this.env.SNAPSHOT_BUCKET.put(r2Key, imageBytes, {
        httpMetadata: {
          contentType: "image/jpeg",
          cacheControl: "public, max-age=31536000, immutable",
        },
        customMetadata: {
          shop: params.shop,
          productId: params.productId,
          sourceImageUrl: params.imageUrl,
          engine,
          cleanedAt: new Date().toISOString(),
        },
      });
    }

    const elapsedSec = reportedSec ?? Math.round(((Date.now() - startMs) / 1000) * 100) / 100;

    return {
      status: "success",
      cleanAdImageUrl: imageBytes && this.env.SNAPSHOT_BUCKET ? publicCleanUrl : params.imageUrl,
      r2Key: imageBytes && this.env.SNAPSHOT_BUCKET ? r2Key : undefined,
      processingSec: elapsedSec,
      maskCoveragePct,
      engine,
    };
  }
}

