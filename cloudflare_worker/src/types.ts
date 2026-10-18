/**
 * Type definitions for SafeMedia Shield (Cloudflare Worker & Shopify Gateway)
 */

export interface VariantMapping {
  variantId: string;
  variantTitle: string;
  originalMediaId: string;
  originalImageUrl: string;
  sku?: string;
  price?: string;
}

export interface MediaItem {
  id: string;
  url: string;
  altText?: string;
}

export interface ProductSnapshot {
  productId: string;
  productTitle: string;
  bodyHtml: string;
  variants: VariantMapping[];
  originalMediaList: MediaItem[];
  capturedAt: string;
  cleanAdImageUrl?: string;
  dualFeedMetadata?: {
    sourceImageUrl?: string;
    cleanedAt?: string;
    maskCoveragePct?: number;
    processingSec?: number;
    engine?: string;
  };
}

export interface StoreSnapshot {
  snapshotId: string;
  shop: string;
  createdAt: string;
  totalProducts: number;
  totalImages: number;
  products: Record<string, ProductSnapshot>;
}

export interface CanaryTestResult {
  productId: string;
  productTitle: string;
  originalSizeKB: number;
  optimizedSizeKB: number;
  savingsPercentage: number;
  originalImageUrl: string;
  optimizedImageUrl: string;
  cleanAdImageUrl?: string;
  metafieldKey?: string;
  variantChecks: Array<{
    variantId: string;
    variantTitle: string;
    preserved: boolean;
    activeImageUrl: string;
  }>;
}

export interface DualFeedSyncResult {
  success: boolean;
  skipped?: boolean;
  reason?: string;
  productId: string;
  productTitle?: string;
  storefrontImageUrl: string;
  cleanAdImageUrl: string;
  metafieldNamespace: string;
  metafieldKey: string;
  processingSec: number;
  maskCoveragePct?: number;
  engine: string;
}

export interface BatchJobState {
  jobId: string;
  status: "IDLE" | "RUNNING" | "COMPLETED" | "ABORTED" | "FAILED";
  total: number;
  processed: number;
  currentProductTitle?: string;
  errors: string[];
  startedAt?: string;
  finishedAt?: string;
}

export interface Env {
  // Cloudflare R2 bucket for immutable snapshots & clean ad images
  SNAPSHOT_BUCKET?: R2Bucket;
  // Cloudflare KV for transient state & circuit breaker flags
  STATE_KV?: KVNamespace;
  // RunPod / AI Inpainting API credentials
  RUNPOD_API_KEY?: string;
  RUNPOD_ENDPOINT_ID?: string;
  INPAINT_API_URL?: string;
  // Environment mode
  ENVIRONMENT?: string;
  // Shopify live store credentials
  SHOPIFY_SHOP?: string;
  SHOPIFY_ACCESS_TOKEN?: string;
  SHOPIFY_WEBHOOK_SECRET?: string;
}
