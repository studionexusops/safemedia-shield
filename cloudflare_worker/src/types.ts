/**
 * Type definitions for SafeMedia Shield (Cloudflare Worker & Shopify Gateway)
 */

export interface VariantMapping {
  variantId: string;
  variantTitle: string;
  originalMediaId: string;
  originalImageUrl: string;
  cleanAdImageUrl?: string;
  sku?: string;
  price?: string;
}

export interface MediaItem {
  id: string;
  url: string;
  altText?: string;
}

export interface DualFeedMetadataRecord {
  sourceImageUrl?: string;
  shopifyImageUrl?: string;
  cleanedAt?: string;
  maskCoveragePct?: number;
  processingSec?: number;
  engine?: string;
  cleanedImageUrls?: Record<string, string>;
  variantCleanImageMap?: Record<string, string>;
}

export interface ProductSnapshot {
  productId: string;
  productTitle: string;
  title?: string;
  bodyHtml: string;
  variants: VariantMapping[];
  originalMediaList: MediaItem[];
  capturedAt: string;
  cleanAdImageUrl?: string;
  dualFeedMetadata?: DualFeedMetadataRecord;
}

export interface StoreSnapshot {
  snapshotId: string;
  shop: string;
  createdAt: string;
  totalProducts: number;
  totalImages: number;
  products: Record<string, ProductSnapshot>;
  isBaseline?: boolean;
}

export interface CanaryVariantCheck {
  variantId: string;
  title: string;
  hasOriginalMedia: boolean;
  preserved: boolean;
  originalImageUrl?: string;
  cleanAdImageUrl?: string;
  newlyCleaned?: boolean;

  // Backwards compatibility aliases for existing UI before M2
  variantTitle?: string;
  activeImageUrl?: string;
}

export interface SanitizedErrorResponse {
  error: string;
  code: string;
  details?: string;
}

export interface CanaryTestResult {
  productId: string;
  productTitle: string;
  originalImageUrl: string;       // Storefront decorated image (Before)
  cleanAdImageUrl: string;        // AI-cleaned ad image (After)
  metafieldKey: "safemedia.clean_ad_image_url" | string;
  aiMetadata: {
    processingSec: number;
    maskCoveragePct: number;
    engine: string;
  };
  variantChecks: CanaryVariantCheck[];
  canaryUsedCount: number;
  canaryLimit: number;
  skipped?: boolean;
  skipReason?: string;
  newlyCleanedCount?: number;

  // Dual-Feed explicit aliases
  beforeImageUrl?: string;
  afterImageUrl?: string;

  // Backwards-compatible fields for transitional UI (prior to M2 UI rewrite)
  /** @deprecated Use cleanAdImageUrl */
  optimizedImageUrl?: string;
  /** @deprecated WebP compression byte stats removed in Pure Dual-Feed */
  originalSizeKB?: number;
  /** @deprecated WebP compression byte stats removed in Pure Dual-Feed */
  optimizedSizeKB?: number;
  /** @deprecated WebP compression byte stats removed in Pure Dual-Feed */
  compressionRatio?: number;
  /** @deprecated WebP compression byte stats removed in Pure Dual-Feed */
  savedKB?: number;
  /** @deprecated WebP compression byte stats removed in Pure Dual-Feed */
  savingsPercentage?: number;
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
  shop?: string;
  status: "IDLE" | "RUNNING" | "COMPLETED" | "ABORTED" | "CANCELLED" | "FAILED";
  total: number;
  processed: number;
  skippedCount?: number;
  cleanedCount?: number;
  cleanedProductIds?: string[];
  currentProductId?: string;
  currentProductTitle?: string;
  avgProcessingSec?: number;
  estimatedRemainingSec?: number;
  errors: string[];
  startedAt?: string;
  updatedAt?: string;
  finishedAt?: string;
}

export interface TenantBillingState {
  shop: string;
  planStatus: "CANARY_TRIAL" | "TRIAL_14D_ACTIVE" | "TRIAL_ACTIVE" | "TRIAL_CAP_REACHED" | "ACTIVE" | "PAUSED_USAGE_CAP_REACHED";
  planName: string;
  priceUsd: number;
  trialDays: number;
  canaryUsedCount: number;
  canaryLimit: number;
  trialUsedCount?: number;
  trialLimit?: number;
  monthlyIncludedCount?: number;
  monthlyUsageCount?: number;
  overagePriceUsd?: number;
  cappedAmountUsd?: number;
  usageLineItemId?: string;
  currentBillingPeriodStart?: string;
  subscriptionId?: string;
  confirmationUrl?: string;
  activatedAt?: string;
  firstInstalledAt?: string;
  hasEverSubscribed?: boolean;
  trialEndsAt?: string;
  circuitBreakerTripped: boolean;
  autoSyncEnabled?: boolean;
  webhookId?: string;
  updatedAtMs?: number;
}

export interface GpuSlotLockRecord {
  slotId: number;
  shop: string;
  productId?: string;
  lockedAt: number;
  expiresAt: number;
}

export interface TenantAuthState {
  shop: string;
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
  scope: string;
  installedAt: string;
  uninstalledAt?: string;
}

export interface OAuthStateRecord {
  shop: string;
  state: string;
  createdAt: number;
}

export interface RollbackProductDataDiff {
  productId: string;
  productTitle: string;
  snapshotId: string;
  revertedAt: string;
  storefrontImageUrl: string;
  storefrontUnchanged: true;
  beforeRevert: {
    storefrontImageUrl: string;
    cleanAdImageMetafield: string | null;
    gmcImageLink: string;
    metaImageLink: string;
    variantCount: number;
    cleanedVariantCount?: number;
    variantCleanImageMap?: Record<string, string>;
    variantLinksPreserved: boolean;
  };
  afterRevert: {
    storefrontImageUrl: string;
    cleanAdImageMetafield: string | null;
    gmcImageLink: string;
    metaImageLink: string;
    metafieldAction: "RESTORED_TO_SNAPSHOT" | "PURGED_TO_VIRGIN" | "SKIPPED_DELETED";
    variantCount: number;
    cleanedVariantCount?: number;
    variantCleanImageMap?: Record<string, string>;
    variantLinksPreserved: boolean;
  };
  skipped?: boolean;
  clearedAfterRollback?: boolean;
}

export interface RollbackExecutionResult {
  success: boolean;
  restoredCount: number;
  restoredProducts: number;
  skippedCount?: number;
  skippedProductIds?: string[];
  snapshotId: string;
  snapshotTimestamp: string;
  revertedAt: string;
  metafieldsRestored: boolean;
  productDataDiffs: RollbackProductDataDiff[];
  beforeAfterComparisons: RollbackProductDataDiff[];
  message: string;
}

export interface SnapshotSummary {
  snapshotId: string;
  key: string;
  createdAt: string;
  totalProducts: number;
  totalImages: number;
  isBaseline: boolean;
  isLatest: boolean;
  label: string;
}

export interface AdFeedPreviewResponse {
  shop: string;
  metafieldNamespace: "safemedia";
  metafieldKey: "clean_ad_image_url";
  metafieldDefinitionPinned: boolean;
  channelMappings: {
    googleShopping: {
      channelApp: string;
      targetAttribute: "g:image_link";
      sourceMetafield: "product.metafields.safemedia.clean_ad_image_url";
      status: "MAPPED_AND_READY" | "READY_WAITING_CLEAN_ITEMS";
    };
    metaCatalog: {
      channelApp: string;
      targetAttribute: "image_link";
      sourceMetafield: "product.metafields.safemedia.clean_ad_image_url";
      status: "MAPPED_AND_READY" | "READY_WAITING_CLEAN_ITEMS";
    };
  };
  items: Array<{
    productId: string;
    variantId?: string;
    variantTitle?: string;
    productTitle: string;
    storefrontUrl: string;
    storefrontImageUrl: string;
    cleanAdImageUrl: string | null;
    googleShoppingFeedItem: {
      "g:id": string;
      "g:item_group_id"?: string;
      "g:title": string;
      "g:image_link": string;
      "storefront_original_preserved": string;
    };
    metaCatalogFeedItem: {
      "id": string;
      "item_group_id"?: string;
      "title": string;
      "image_link": string;
    };
  }>;
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
  // Environment mode & Billing configuration
  ENVIRONMENT?: string;
  BILLING_TEST_MODE?: string;
  // Shopify live store credentials
  SHOPIFY_SHOP?: string;
  SHOPIFY_ACCESS_TOKEN?: string;
  SHOPIFY_WEBHOOK_SECRET?: string;
  ADMIN_API_SECRET?: string;
  // Shopify Public App & OAuth 2.0 Credentials
  SHOPIFY_API_KEY?: string;
  SHOPIFY_API_SECRET?: string;
  APP_URL?: string;
}

export interface ShopifyGraphQLResponse<T = Record<string, unknown>> {
  data?: T;
  errors?: Array<{
    message: string;
    locations?: Array<{ line: number; column: number }>;
    path?: Array<string | number>;
    extensions?: {
      code?: string;
      [key: string]: unknown;
    };
  }>;
  extensions?: {
    cost?: {
      requestedQueryCost?: number;
      actualQueryCost?: number;
      throttleStatus?: {
        maximumAvailable?: number;
        currentlyAvailable?: number;
        restoreRate?: number;
      };
    };
  };
}

export interface RunPodJobResponse {
  id?: string;
  status?: string;
  output?: {
    image_url?: string;
    image_base64?: string;
    mask_coverage_pct?: number;
    processing_time_sec?: number;
    engine?: string;
    [key: string]: unknown;
  };
  error?: string;
  delayTime?: number;
  executionTime?: number;
}

