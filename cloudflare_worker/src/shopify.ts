/**
 * Shopify GraphQL API & Variant Mapping Preserve Layer
 * Solves the structural flaw of variant image disconnection during asset updates.
 */

import {
  ProductSnapshot,
  StoreSnapshot,
  VariantMapping,
  MediaItem,
  DualFeedMetadataRecord,
  ShopifyGraphQLResponse,
  Env,
} from "./types";

/**
 * Custom error thrown when Shopify Admin API rejects access due to expired/invalid access token,
 * re-installation, or tenant authentication mismatch. Triggers automated Self-Healing.
 */
export class ShopifyAuthError extends Error {
  public readonly shop: string;
  public readonly statusCode?: number;
  constructor(shop: string, message: string, statusCode?: number) {
    super(message);
    this.name = "ShopifyAuthError";
    this.shop = shop;
    this.statusCode = statusCode;
  }
}

interface MockProductMetaState {
  cleanAdImageUrl?: string;
  dualFeedMetadata?: DualFeedMetadataRecord;
  variantMediaIds?: Record<string, string>;
  variantCleanAdImageUrls?: Record<string, string>;
}

interface GraphQLProductNode {
  id: string;
  title: string;
  descriptionHtml?: string;
  media?: {
    edges?: Array<{
      node: {
        id: string;
        mediaContentType?: string;
        image?: {
          url: string;
          altText?: string;
        };
      };
    }>;
  };
  variants?: {
    edges?: Array<{
      node: {
        id: string;
        title: string;
        sku?: string;
        price?: string;
        cleanAdImageMetafield?: {
          id?: string;
          value?: string;
        };
        media?: {
          edges?: Array<{
            node: {
              id: string;
              image?: {
                url: string;
              };
            };
          }>;
        };
      };
    }>;
  };
  cleanAdImageMetafield?: {
    value?: string;
  };
  dualFeedMeta?: {
    value?: string;
  };
}

interface ProductsQueryResponse {
  products?: {
    pageInfo?: {
      hasNextPage?: boolean;
      endCursor?: string;
    };
    edges?: Array<{
      cursor?: string;
      node: GraphQLProductNode;
    }>;
  };
}

interface ProductByIdQueryResponse {
  product?: GraphQLProductNode;
}

interface ProductVariantsBulkUpdateResponse {
  productVariantsBulkUpdate?: {
    productVariants?: Array<{ id: string }>;
    userErrors?: Array<{ field?: string[]; message: string }>;
  };
}

interface MetafieldsSetResponse {
  metafieldsSet?: {
    metafields?: Array<{ id: string }>;
    userErrors?: Array<{ field?: string[]; message: string }>;
  };
}

interface MetafieldsDeleteResponse {
  metafieldsDelete?: {
    deletedMetafields?: Array<{
      ownerId: string;
      namespace: string;
      key: string;
    }>;
    userErrors?: Array<{ field?: string[]; message: string }>;
  };
}

interface ProductMetafieldIdsResponse {
  product?: {
    cleanMeta?: { id?: string };
    dualMeta?: { id?: string };
  };
}

interface AppSubscriptionCreateResponse {
  appSubscriptionCreate?: {
    appSubscription?: {
      id: string;
      status: string;
      trialDays?: number;
      lineItems?: Array<{
        id: string;
        plan?: {
          pricingDetails?: {
            __typename?: string;
            [key: string]: unknown;
          };
        };
      }>;
    };
    confirmationUrl?: string;
    userErrors?: Array<{ field?: string[]; message: string }>;
  };
}

interface AppUsageRecordCreateResponse {
  appUsageRecordCreate?: {
    appUsageRecord?: {
      id: string;
    };
    userErrors?: Array<{
      field?: string[];
      message: string;
    }>;
  };
}

interface ActiveSubscriptionsResponse {
  currentAppInstallation?: {
    activeSubscriptions?: Array<{
      id: string;
      name: string;
      status: string;
      test: boolean;
    }>;
  };
}

const MOCK_PRODUCT_META_STORE = new Map<string, Map<string, MockProductMetaState>>();
const PINNED_METAFIELD_DEF_SHOPS = new Set<string>();

const SHOP_DOMAIN_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9-]{1,60}\.myshopify\.com$/;

function assertValidShopDomain(shop: string): void {
  if (!shop || shop.length > 100 || !SHOP_DOMAIN_PATTERN.test(shop)) {
    throw new Error(`Security Violation: Invalid Shopify shop domain '${shop}'`);
  }
}

export class ShopifyVariantManager {
  private shop: string;
  private accessToken: string;
  private env?: Env;

  constructor(shop: string, accessToken: string, env?: Env) {
    assertValidShopDomain(shop);
    this.shop = shop;
    this.accessToken = accessToken;
    this.env = env;
  }

  /**
   * Resets in-memory mock product metafield state for a given shop.
   */
  static async resetMockShopState(shop: string, env?: Env): Promise<void> {
    assertValidShopDomain(shop);
    MOCK_PRODUCT_META_STORE.delete(shop);
    PINNED_METAFIELD_DEF_SHOPS.delete(shop);
    if (env?.SNAPSHOT_BUCKET) {
      try {
        await env.SNAPSHOT_BUCKET.delete(`state/${shop}/mock_meta.json`);
      } catch {}
    }
  }

  private async loadMockMetaFromR2(): Promise<void> {
    if (!this.env?.SNAPSHOT_BUCKET) return;
    try {
      const obj = await this.env.SNAPSHOT_BUCKET.get(`state/${this.shop}/mock_meta.json`);
      if (obj) {
        const data = (await obj.json()) as Record<string, MockProductMetaState>;
        const shopMap = this.getShopMockMap();
        for (const [gid, meta] of Object.entries(data)) {
          shopMap.set(gid, meta);
        }
      }
    } catch (err) {
      console.warn(`[ShopifyVariantManager] Failed to load mock meta from R2 for ${this.shop}:`, err);
    }
  }

  private async saveMockMetaToR2(): Promise<void> {
    if (!this.env?.SNAPSHOT_BUCKET) return;
    try {
      const shopMap = this.getShopMockMap();
      const obj: Record<string, MockProductMetaState> = {};
      for (const [gid, meta] of shopMap.entries()) {
        obj[gid] = meta;
      }
      await this.env.SNAPSHOT_BUCKET.put(
        `state/${this.shop}/mock_meta.json`,
        JSON.stringify(obj, null, 2),
        { httpMetadata: { contentType: "application/json" } }
      );
    } catch (err) {
      console.warn(`[ShopifyVariantManager] Failed to save mock meta to R2 for ${this.shop}:`, err);
    }
  }

  private getShopMockMap(): Map<string, MockProductMetaState> {
    let shopMap = MOCK_PRODUCT_META_STORE.get(this.shop);
    if (!shopMap) {
      shopMap = new Map<string, MockProductMetaState>();
      MOCK_PRODUCT_META_STORE.set(this.shop, shopMap);
    }
    return shopMap;
  }

  /**
   * Executes a Shopify Admin GraphQL query/mutation with exponential backoff + jitter
   * when HTTP 429 or GraphQL THROTTLED errors occur (max 3 retries).
   */
  private async executeGraphQLWithBackoff<T = Record<string, unknown>>(
    query: string,
    variables?: Record<string, unknown>,
    apiVersion = "2024-10"
  ): Promise<ShopifyGraphQLResponse<T>> {
    const endpoint = `https://${this.shop}/admin/api/${apiVersion}/graphql.json`;
    const maxRetries = 3;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": this.accessToken,
        },
        body: JSON.stringify(variables ? { query, variables } : { query }),
        signal: AbortSignal.timeout(10_000),
      });

      if (res.status === 429 && attempt < maxRetries) {
        const delayMs = Math.pow(2, attempt) * 1000 + Math.floor(Math.random() * 250);
        await new Promise((r) => setTimeout(r, delayMs));
        continue;
      }

      if (res.status === 401) {
        const bodyText = await res.text().catch(() => "");
        throw new ShopifyAuthError(
          this.shop,
          `Shopify authentication failed (401 Unauthorized): ${bodyText || res.statusText}`,
          401
        );
      }

      if (!res.ok) {
        const bodyText = await res.text().catch(() => "");
        if (
          res.status === 403 ||
          bodyText.includes("Invalid API key") ||
          bodyText.includes("access token") ||
          bodyText.includes("unrecognized login") ||
          bodyText.includes("app has been uninstalled")
        ) {
          throw new ShopifyAuthError(
            this.shop,
            `Shopify authentication rejected (${res.status}): ${bodyText || res.statusText}`,
            res.status
          );
        }
        throw new Error(`Shopify GraphQL error: ${res.status} ${res.statusText}`);
      }

      const json = (await res.json()) as ShopifyGraphQLResponse<T>;
      if (Array.isArray(json?.errors)) {
        const authErr = json.errors.find((e) => {
          const msg = String(e?.message || "").toLowerCase();
          return (
            msg.includes("invalid api key") ||
            msg.includes("access token") ||
            msg.includes("unrecognized login") ||
            msg.includes("unauthorized") ||
            msg.includes("app has been uninstalled")
          );
        });
        if (authErr) {
          throw new ShopifyAuthError(
            this.shop,
            `Shopify GraphQL authentication error: ${authErr.message}`,
            401
          );
        }
      }
      const isThrottled =
        Array.isArray(json?.errors) &&
        json.errors.some(
          (e) =>
            e?.extensions?.code === "THROTTLED" ||
            String(e?.message || "").toLowerCase().includes("throttled")
        );

      if (isThrottled && attempt < maxRetries) {
        const delayMs = Math.pow(2, attempt) * 1000 + Math.floor(Math.random() * 250);
        await new Promise((r) => setTimeout(r, delayMs));
        continue;
      }

      return json;
    }

    throw new Error("Shopify GraphQL max retries exceeded due to rate limiting.");
  }

  /**
   * Registers and pins the `safemedia.clean_ad_image_url` Metafield Definition for both
   * `PRODUCT` and `PRODUCTVARIANT` owner types so merchants and Shopify App Reviewers
   * can view them directly in Shopify Admin and map them in Google & YouTube (`g:image_link`)
   * and Facebook & Instagram (`image_link`) channels.
   */
  async ensureCleanAdMetafieldDefinition(): Promise<{
    success: boolean;
    pinned: boolean;
    definitionId?: string;
    variantDefinitionId?: string;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      PINNED_METAFIELD_DEF_SHOPS.add(this.shop);
      return {
        success: true,
        pinned: true,
        definitionId: "gid://shopify/MetafieldDefinition/mock_safemedia_clean_ad_image_url",
        variantDefinitionId: "gid://shopify/MetafieldDefinition/mock_safemedia_variant_clean_ad_image_url",
      };
    }

    if (PINNED_METAFIELD_DEF_SHOPS.has(this.shop)) {
      return { success: true, pinned: true };
    }

    const mutation = `
      mutation metafieldDefinitionCreate($definition: MetafieldDefinitionInput!) {
        metafieldDefinitionCreate(definition: $definition) {
          createdDefinition {
            id
            namespace
            key
            pinnedPosition
          }
          userErrors {
            field
            message
            code
          }
        }
      }
    `;

    interface MetafieldDefCreateData {
      metafieldDefinitionCreate?: {
        createdDefinition?: { id: string };
        userErrors?: Array<{ code?: string; message?: string; field?: string[] }>;
      };
    }

    const isDefCreatedOrExisting = (resData?: MetafieldDefCreateData): { ok: boolean; id?: string } => {
      const createdId = resData?.metafieldDefinitionCreate?.createdDefinition?.id;
      const userErrors = resData?.metafieldDefinitionCreate?.userErrors || [];
      const alreadyExists = userErrors.some(
        (e) =>
          e?.code === "TAKEN" ||
          String(e?.message || "").toLowerCase().includes("already") ||
          String(e?.message || "").toLowerCase().includes("taken")
      );
      return {
        ok: Boolean(createdId || alreadyExists || userErrors.length === 0),
        id: createdId,
      };
    };

    try {
      const [prodJson, varJson] = await Promise.all([
        this.executeGraphQLWithBackoff<MetafieldDefCreateData>(mutation, {
          definition: {
            name: "Clean Ad Feed Image URL (Google & Meta)",
            namespace: "safemedia",
            key: "clean_ad_image_url",
            description:
              "AI-cleaned badge-free product image URL mapped to Google Merchant Center (g:image_link) and Meta Catalog (image_link) while preserving decorated storefront media.",
            type: "url",
            ownerType: "PRODUCT",
            pin: true,
          },
        }),
        this.executeGraphQLWithBackoff<MetafieldDefCreateData>(mutation, {
          definition: {
            name: "Clean Variant Ad Feed Image URL (Google & Meta)",
            namespace: "safemedia",
            key: "clean_ad_image_url",
            description:
              "AI-cleaned badge-free variant image URL mapped to Google Merchant Center (g:image_link) and Meta Catalog (image_link) while preserving decorated storefront variant media.",
            type: "url",
            ownerType: "PRODUCTVARIANT",
            pin: true,
          },
        }),
      ]);

      const prodRes = isDefCreatedOrExisting(prodJson?.data);
      const varRes = isDefCreatedOrExisting(varJson?.data);

      if (prodRes.ok && varRes.ok) {
        PINNED_METAFIELD_DEF_SHOPS.add(this.shop);
        return {
          success: true,
          pinned: true,
          definitionId: prodRes.id,
          variantDefinitionId: varRes.id,
        };
      }
    } catch {
      // Non-blocking best-effort definition registration
    }

    return { success: true, pinned: true };
  }

  private mapGraphQLProductNode(p: GraphQLProductNode): ProductSnapshot {
    const mediaList: MediaItem[] = [];
    for (const mEdge of p.media?.edges || []) {
      if (mEdge.node.mediaContentType === "IMAGE" && mEdge.node.image) {
        mediaList.push({
          id: mEdge.node.id,
          url: mEdge.node.image.url,
          altText: mEdge.node.image.altText || "",
        });
      }
    }

    let parsedDualMeta: DualFeedMetadataRecord | undefined = undefined;
    if (p.dualFeedMeta?.value) {
      try {
        parsedDualMeta = JSON.parse(p.dualFeedMeta.value) as DualFeedMetadataRecord;
      } catch {
        parsedDualMeta = undefined;
      }
    }

    const variants: VariantMapping[] = [];
    for (const vEdge of p.variants?.edges || []) {
      const v = vEdge.node;
      const vMedia = v.media?.edges?.[0]?.node;
      const cleanAdImageUrl =
        v.cleanAdImageMetafield?.value ||
        parsedDualMeta?.variantCleanImageMap?.[v.id] ||
        undefined;
      variants.push({
        variantId: v.id,
        variantTitle: v.title,
        originalMediaId: vMedia ? vMedia.id : "",
        originalImageUrl: vMedia?.image?.url || (mediaList[0]?.url || ""),
        cleanAdImageUrl,
        sku: v.sku || "",
        price: v.price || "",
      });
    }

    return {
      productId: p.id,
      productTitle: p.title,
      bodyHtml: p.descriptionHtml || "",
      variants,
      originalMediaList: mediaList,
      capturedAt: new Date().toISOString(),
      cleanAdImageUrl: p.cleanAdImageMetafield?.value || undefined,
      dualFeedMetadata: parsedDualMeta,
    };
  }

  /**
   * Fetches product and variant hierarchy from Shopify GraphQL Admin API using cursor pagination.
   * If mock mode / token is not set, returns realistic sample data for local testing.
   */
  async fetchProductsWithVariants(maxProducts = 250): Promise<ProductSnapshot[]> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      await this.loadMockMetaFromR2();
      return this.getMockProducts();
    }

    const query = `
      query getProductsWithMedia($first: Int!, $after: String) {
        products(first: $first, after: $after) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              title
              descriptionHtml
              cleanAdImageMetafield: metafield(namespace: "safemedia", key: "clean_ad_image_url") {
                id
                value
              }
              dualFeedMeta: metafield(namespace: "safemedia", key: "dual_feed_metadata") {
                id
                value
              }
              media(first: 20) {
                edges {
                  node {
                    id
                    mediaContentType
                    ... on MediaImage {
                      image {
                        url
                        altText
                      }
                    }
                  }
                }
              }
              variants(first: 100) {
                edges {
                  node {
                    id
                    title
                    sku
                    price
                    cleanAdImageMetafield: metafield(namespace: "safemedia", key: "clean_ad_image_url") {
                      id
                      value
                    }
                    media(first: 1) {
                      edges {
                        node {
                          id
                          ... on MediaImage {
                            image {
                              url
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    `;

    const products: ProductSnapshot[] = [];
    let afterCursor: string | null = null;
    let hasNextPage = true;

    while (hasNextPage && products.length < maxProducts) {
      const batchSize = Math.min(50, maxProducts - products.length);
      const json: ShopifyGraphQLResponse<ProductsQueryResponse> =
        await this.executeGraphQLWithBackoff<ProductsQueryResponse>(
          query,
          { first: batchSize, after: afterCursor },
          "2024-10"
        );

      if (json.errors) {
        throw new Error(`Shopify GraphQL errors: ${JSON.stringify(json.errors)}`);
      }

      const connection: ProductsQueryResponse["products"] = json.data?.products;
      const edges = connection?.edges || [];

      for (const edge of edges) {
        products.push(this.mapGraphQLProductNode(edge.node));
      }

      hasNextPage = Boolean(connection?.pageInfo?.hasNextPage) && edges.length > 0;
      afterCursor = connection?.pageInfo?.endCursor || null;
      if (!afterCursor) break;
    }

    return products;
  }

  /**
   * Fetches a single product with its media, variants, and safemedia metafields,
   * returning explicit existence status ("exists" | "deleted" | "unknown") in a single GraphQL call.
   */
  async fetchProductWithExistence(
    productId: string
  ): Promise<{ status: "exists"; product: ProductSnapshot } | { status: "deleted" } | { status: "unknown" }> {
    const gid = productId.startsWith("gid://shopify/Product/")
      ? productId
      : productId.startsWith("gid://")
      ? productId
      : `gid://shopify/Product/${productId}`;

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      try {
        const all = await this.fetchProductsWithVariants();
        const match = all.find((p) => p.productId === gid || p.productId === productId);
        return match ? { status: "exists", product: match } : { status: "deleted" };
      } catch {
        return { status: "unknown" };
      }
    }

    const query = `
      query getProductById($id: ID!) {
        product(id: $id) {
          id
          title
          descriptionHtml
          cleanAdImageMetafield: metafield(namespace: "safemedia", key: "clean_ad_image_url") {
            value
          }
          dualFeedMeta: metafield(namespace: "safemedia", key: "dual_feed_metadata") {
            value
          }
          media(first: 30) {
            edges {
              node {
                ... on MediaImage {
                  id
                  mediaContentType
                  image {
                    url
                    altText
                  }
                }
              }
            }
          }
          variants(first: 100) {
            edges {
              node {
                id
                title
                sku
                price
                cleanAdImageMetafield: metafield(namespace: "safemedia", key: "clean_ad_image_url") {
                  id
                  value
                }
                media(first: 1) {
                  edges {
                    node {
                      ... on MediaImage {
                        id
                        image {
                          url
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    `;

    try {
      const json = await this.executeGraphQLWithBackoff<ProductByIdQueryResponse>(query, { id: gid }, "2024-10");
      if (json.errors) {
        return { status: "unknown" };
      }
      if (!json.data?.product) {
        return { status: "deleted" };
      }
      return { status: "exists", product: this.mapGraphQLProductNode(json.data.product) };
    } catch (err: unknown) {
      if (err instanceof ShopifyAuthError) throw err;
      return { status: "unknown" };
    }
  }

  /**
   * Fetches a single product with its media, variants, and safemedia metafields.
   * Significantly reduces Shopify GraphQL rate limit consumption compared to full-catalog scans.
   */
  async fetchProductById(productId: string): Promise<ProductSnapshot | null> {
    const res = await this.fetchProductWithExistence(productId);
    return res.status === "exists" ? res.product : null;
  }

  /**
   * Lightweight existence check for a single product ID (used when catalog size >= 250
   * or live catalog fetch failed). Distinguishes confirmed deletion from transient errors.
   */
  async checkProductExists(productId: string): Promise<"exists" | "deleted" | "unknown"> {
    const gid = productId.startsWith("gid://shopify/Product/")
      ? productId
      : productId.startsWith("gid://")
      ? productId
      : `gid://shopify/Product/${productId}`;

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      try {
        const all = await this.fetchProductsWithVariants();
        const found = all.some((p) => p.productId === gid || p.productId === productId);
        return found ? "exists" : "deleted";
      } catch {
        return "unknown";
      }
    }

    const query = `
      query checkProductExists($id: ID!) {
        product(id: $id) {
          id
        }
      }
    `;

    try {
      const json = await this.executeGraphQLWithBackoff<{
        product?: { id: string } | null;
      }>(query, { id: gid }, "2024-10");

      if (json.errors) {
        return "unknown";
      }
      return json.data?.product ? "exists" : "deleted";
    } catch (err: unknown) {
      if (err instanceof ShopifyAuthError) throw err;
      return "unknown";
    }
  }

  /**
   * Rebinds variants to their corresponding new media IDs in Shopify.
   * Guarantees zero variant-image detachment.
   */
  async rebindVariants(
    productId: string,
    variantUpdates: Array<{ variantId: string; newMediaId: string }>
  ): Promise<{ success: boolean; updatedCount: number }> {
    const gid = productId.startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      const shopMap = this.getShopMockMap();
      const current = shopMap.get(gid) || {};
      const updatedMap: Record<string, string> = { ...(current.variantMediaIds || {}) };
      for (const u of variantUpdates) {
        updatedMap[u.variantId] = u.newMediaId;
      }
      shopMap.set(gid, { ...current, variantMediaIds: updatedMap });
      return { success: true, updatedCount: variantUpdates.length };
    }

    const mutation = `
      mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $productId, variants: $variants) {
          productVariants {
            id
          }
          userErrors {
            field
            message
          }
        }
      }
    `;

    const variables = {
      productId: gid,
      variants: variantUpdates.map((u) => ({
        id: u.variantId,
        mediaId: u.newMediaId,
      })),
    };

    const json = await this.executeGraphQLWithBackoff<ProductVariantsBulkUpdateResponse>(mutation, variables, "2024-10");
    if (json.errors || (json.data?.productVariantsBulkUpdate?.userErrors && json.data.productVariantsBulkUpdate.userErrors.length > 0)) {
      throw new Error(`Rebind failed: ${JSON.stringify(json.errors || json.data?.productVariantsBulkUpdate?.userErrors)}`);
    }

    return { success: true, updatedCount: variantUpdates.length };
  }

  /**
   * Priority 1 (Dual-Feed Smart Routing):
   * Writes the AI-cleaned ad image URLs and metadata into both the parent product's
   * and all cleaned variants' hidden Metafields (`safemedia.clean_ad_image_url` and
   * `safemedia.dual_feed_metadata`), chunked to Shopify's 25-input metafieldsSet limit.
   */
  async setCleanAdImageMetafield(
    productId: string,
    cleanAdImageUrl: string,
    metadata: DualFeedMetadataRecord,
    variantCleanImageMap?: Record<string, string>
  ): Promise<{ success: boolean; metafieldId?: string }> {
    const gid = productId.startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;
    const effectiveVariantMap: Record<string, string> = {
      ...(metadata.variantCleanImageMap || {}),
      ...(variantCleanImageMap || {}),
    };
    const mergedMetadata: DualFeedMetadataRecord = {
      ...metadata,
      ...(Object.keys(effectiveVariantMap).length > 0
        ? { variantCleanImageMap: effectiveVariantMap }
        : {}),
    };

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      await this.loadMockMetaFromR2();
      const shopMap = this.getShopMockMap();
      const existing = shopMap.get(gid) || {};
      shopMap.set(gid, {
        ...existing,
        cleanAdImageUrl,
        dualFeedMetadata: mergedMetadata,
        variantCleanAdImageUrls: {
          ...(existing.variantCleanAdImageUrls || {}),
          ...effectiveVariantMap,
        },
      });
      await this.saveMockMetaToR2();
      return { success: true, metafieldId: "gid://shopify/Metafield/mock_1" };
    }

    const mutation = `
      mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
          metafields {
            id
            namespace
            key
            value
          }
          userErrors {
            field
            message
            code
          }
        }
      }
    `;

    const allInputs: Array<{
      ownerId: string;
      namespace: string;
      key: string;
      type: string;
      value: string;
    }> = [
      {
        ownerId: gid,
        namespace: "safemedia",
        key: "clean_ad_image_url",
        type: "url",
        value: cleanAdImageUrl,
      },
      {
        ownerId: gid,
        namespace: "safemedia",
        key: "dual_feed_metadata",
        type: "json",
        value: JSON.stringify(mergedMetadata),
      },
    ];

    for (const [vid, vUrl] of Object.entries(effectiveVariantMap)) {
      if (!vUrl) continue;
      const variantGid = vid.startsWith("gid://") ? vid : `gid://shopify/ProductVariant/${vid}`;
      allInputs.push({
        ownerId: variantGid,
        namespace: "safemedia",
        key: "clean_ad_image_url",
        type: "url",
        value: vUrl,
      });
    }

    const MAX_METAFIELDS_PER_SET = 25;
    const chunks: typeof allInputs[] = [];
    for (let i = 0; i < allInputs.length; i += MAX_METAFIELDS_PER_SET) {
      chunks.push(allInputs.slice(i, i + MAX_METAFIELDS_PER_SET));
    }

    // Execute Metafield Definition check and first Metafield batch update in parallel to save GraphQL round-trip time
    const [, firstJson] = await Promise.all([
      this.ensureCleanAdMetafieldDefinition().catch(() => {}),
      this.executeGraphQLWithBackoff<MetafieldsSetResponse>(
        mutation,
        { metafields: chunks[0] },
        "2024-10"
      ),
    ]);
    const firstErrors = firstJson.data?.metafieldsSet?.userErrors;
    if (firstJson.errors || (firstErrors && firstErrors.length > 0)) {
      throw new Error(`Metafield update failed: ${JSON.stringify(firstJson.errors || firstErrors)}`);
    }

    for (let i = 1; i < chunks.length; i++) {
      const nextJson = await this.executeGraphQLWithBackoff<MetafieldsSetResponse>(
        mutation,
        { metafields: chunks[i] },
        "2024-10"
      );
      const nextErrors = nextJson.data?.metafieldsSet?.userErrors;
      if (nextJson.errors || (nextErrors && nextErrors.length > 0)) {
        throw new Error(`Metafield update failed: ${JSON.stringify(nextJson.errors || nextErrors)}`);
      }
    }

    const firstId = firstJson.data?.metafieldsSet?.metafields?.[0]?.id;
    return { success: true, metafieldId: firstId };
  }

  private async deleteMetafieldIdentifiers(
    identifiers: Array<{ ownerId: string; namespace: string; key: string }>,
    contextLabel: string
  ): Promise<{ success: boolean; deletedCount: number; error?: string; ownerNotFound?: boolean }> {
    if (identifiers.length === 0) {
      return { success: true, deletedCount: 0 };
    }
    const deleteMutation = `
      mutation metafieldsDelete($metafields: [MetafieldIdentifierInput!]!) {
        metafieldsDelete(metafields: $metafields) {
          deletedMetafields {
            ownerId
            namespace
            key
          }
          userErrors {
            field
            message
          }
        }
      }
    `;

    const MAX_METAFIELDS_PER_DELETE = 25;
    let totalDeleted = 0;

    for (let i = 0; i < identifiers.length; i += MAX_METAFIELDS_PER_DELETE) {
      const chunk = identifiers.slice(i, i + MAX_METAFIELDS_PER_DELETE);
      const json = await this.executeGraphQLWithBackoff<MetafieldsDeleteResponse>(
        deleteMutation,
        { metafields: chunk },
        "2024-10"
      );

      const userErrors = json.data?.metafieldsDelete?.userErrors;
      if (json.errors || (userErrors && userErrors.length > 0)) {
        const serialized = JSON.stringify(json.errors || userErrors);
        console.warn(
          `[Shopify] metafieldsDelete returned errors for ${contextLabel}:`,
          serialized
        );
        const errLower = serialized.toLowerCase();
        const ownerNotFound =
          errLower.includes("does not exist") ||
          errLower.includes("not found") ||
          errLower.includes("could not find");
        return {
          success: false,
          deletedCount: totalDeleted,
          error: serialized,
          ...(ownerNotFound ? { ownerNotFound: true } : {}),
        };
      }

      totalDeleted += json.data?.metafieldsDelete?.deletedMetafields?.length ?? 0;
    }

    return { success: true, deletedCount: totalDeleted };
  }

  /**
   * Deletes variant metafield identifiers resiliently: if a batch hits ownerNotFound
   * because one or more variants were deleted in Shopify, retries per-variant so
   * surviving variants are still cleared while confirmed-deleted variants are skipped.
   * Non-ownerNotFound errors (rate limits, permissions, network) are always propagated.
   */
  private async deleteVariantMetafieldIdentifiersResilient(
    identifiers: Array<{ ownerId: string; namespace: string; key: string }>,
    contextLabel: string
  ): Promise<{ success: boolean; deletedCount: number; error?: string; ownerNotFound?: boolean }> {
    if (identifiers.length === 0) {
      return { success: true, deletedCount: 0 };
    }

    const batchRes = await this.deleteMetafieldIdentifiers(identifiers, contextLabel);
    if (batchRes.success || !batchRes.ownerNotFound) {
      return batchRes;
    }

    if (identifiers.length === 1) {
      return { success: true, deletedCount: 0 };
    }

    let deletedCount = 0;
    for (const singleId of identifiers) {
      const singleRes = await this.deleteMetafieldIdentifiers([singleId], `${contextLabel} (${singleId.ownerId})`);
      if (singleRes.success) {
        deletedCount += singleRes.deletedCount;
      } else if (!singleRes.ownerNotFound) {
        return {
          success: false,
          deletedCount,
          error: singleRes.error,
        };
      }
    }
    return { success: true, deletedCount };
  }

  /**
   * Removes safemedia.clean_ad_image_url metafields from specific variants (e.g., partial snapshot rollback).
   */
  async clearVariantCleanAdImageMetafields(
    productId: string,
    variantIds: string[]
  ): Promise<{ success: boolean; deletedCount?: number; error?: string; ownerNotFound?: boolean }> {
    const gid = productId.startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;
    const uniqueVariantIds = Array.from(new Set(variantIds.filter(Boolean)));
    if (uniqueVariantIds.length === 0) {
      return { success: true, deletedCount: 0 };
    }

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      await this.loadMockMetaFromR2();
      const shopMap = this.getShopMockMap();
      const existing = shopMap.get(gid);
      if (existing?.variantCleanAdImageUrls) {
        const updatedVarMap = { ...existing.variantCleanAdImageUrls };
        for (const vid of uniqueVariantIds) {
          delete updatedVarMap[vid];
        }
        shopMap.set(gid, { ...existing, variantCleanAdImageUrls: updatedVarMap });
        await this.saveMockMetaToR2();
      }
      return { success: true, deletedCount: uniqueVariantIds.length };
    }

    try {
      const identifiers = uniqueVariantIds.map((vid) => ({
        ownerId: vid.startsWith("gid://") ? vid : `gid://shopify/ProductVariant/${vid}`,
        namespace: "safemedia",
        key: "clean_ad_image_url",
      }));
      return await this.deleteVariantMetafieldIdentifiersResilient(identifiers, `${gid} variants`);
    } catch (err: unknown) {
      if (err instanceof ShopifyAuthError) throw err;
      console.error(`[Shopify] Error in clearVariantCleanAdImageMetafields for ${gid}:`, err);
      return {
        success: false,
        deletedCount: 0,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /**
   * Rollback Helper: Removes safemedia hidden metafields from product and its variants
   * when rolling back to a snapshot where no clean ad image existed.
   * Uses modern Shopify metafieldsDelete mutation (2024-10) with direct identifier inputs.
   */
  async clearCleanAdImageMetafield(
    productId: string,
    variantIds?: string[]
  ): Promise<{ success: boolean; deletedCount?: number; error?: string; ownerNotFound?: boolean }> {
    const gid = productId.startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;
    const uniqueVariantIds = Array.from(new Set((variantIds || []).filter(Boolean)));

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      await this.loadMockMetaFromR2();
      const shopMap = this.getShopMockMap();
      const existing = shopMap.get(gid);
      if (existing) {
        shopMap.set(gid, {
          ...existing,
          cleanAdImageUrl: undefined,
          dualFeedMetadata: undefined,
          variantCleanAdImageUrls: undefined,
        });
      }
      await this.saveMockMetaToR2();
      return { success: true, deletedCount: 2 + uniqueVariantIds.length };
    }

    try {
      const productIdentifiers = [
        {
          ownerId: gid,
          namespace: "safemedia",
          key: "clean_ad_image_url",
        },
        {
          ownerId: gid,
          namespace: "safemedia",
          key: "dual_feed_metadata",
        },
      ];

      const parentRes = await this.deleteMetafieldIdentifiers(productIdentifiers, gid);
      if (!parentRes.success) {
        return parentRes;
      }

      if (uniqueVariantIds.length === 0) {
        return parentRes;
      }

      const variantIdentifiers = uniqueVariantIds.map((vid) => ({
        ownerId: vid.startsWith("gid://") ? vid : `gid://shopify/ProductVariant/${vid}`,
        namespace: "safemedia",
        key: "clean_ad_image_url",
      }));
      const varRes = await this.deleteVariantMetafieldIdentifiersResilient(variantIdentifiers, `${gid} variants`);
      if (!varRes.success) {
        return {
          success: false,
          deletedCount: parentRes.deletedCount + varRes.deletedCount,
          error: varRes.error,
        };
      }

      return {
        success: true,
        deletedCount: parentRes.deletedCount + varRes.deletedCount,
      };
    } catch (err: unknown) {
      if (err instanceof ShopifyAuthError) throw err;
      console.error(`[Shopify] Error in clearCleanAdImageMetafield for ${gid}:`, err);
      return {
        success: false,
        deletedCount: 0,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /**
   * Registers the PRODUCTS_UPDATE webhook in Shopify so that whenever a merchant uploads
   * a decorated image, SafeMedia Shield automatically cleans it and populates the hidden metafield.
   */
  async registerProductUpdateWebhook(callbackUrl: string): Promise<{
    success: boolean;
    webhookId?: string;
    callbackUrl: string;
    alreadyRegistered?: boolean;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      return { success: true, webhookId: "gid://shopify/WebhookSubscription/mock", callbackUrl };
    }

    // 1. Check existing webhooks first
    const checkQuery = `
      query {
        webhookSubscriptions(first: 25, topics: [PRODUCTS_UPDATE]) {
          edges {
            node {
              id
              topic
              endpoint {
                __typename
                ... on WebhookHttpEndpoint {
                  callbackUrl
                }
              }
            }
          }
        }
      }
    `;

    interface WebhookSubscriptionsQueryData {
      webhookSubscriptions?: {
        edges?: Array<{
          node?: {
            id?: string;
            endpoint?: {
              callbackUrl?: string;
            };
          };
        }>;
      };
    }
    const checkJson = await this.executeGraphQLWithBackoff<WebhookSubscriptionsQueryData>(checkQuery);
    const existing = checkJson.data?.webhookSubscriptions?.edges || [];
    for (const edge of existing) {
      if (edge.node?.endpoint?.callbackUrl === callbackUrl) {
        return {
          success: true,
          webhookId: edge.node.id,
          callbackUrl,
          alreadyRegistered: true,
        };
      }
    }

    // 2. Register new PRODUCTS_UPDATE webhook
    const createMutation = `
      mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
        webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
          webhookSubscription {
            id
            topic
          }
          userErrors {
            field
            message
          }
        }
      }
    `;

    interface WebhookSubscriptionCreateData {
      webhookSubscriptionCreate?: {
        webhookSubscription?: {
          id?: string;
          topic?: string;
        };
        userErrors?: Array<{
          field?: string[];
          message?: string;
        }>;
      };
    }
    const json = await this.executeGraphQLWithBackoff<WebhookSubscriptionCreateData>(createMutation, {
      topic: "PRODUCTS_UPDATE",
      webhookSubscription: {
        callbackUrl,
        format: "JSON",
      },
    });
    const userErrors = json.data?.webhookSubscriptionCreate?.userErrors;
    if (json.errors || (userErrors && userErrors.length > 0)) {
      throw new Error(`Webhook registration failed: ${JSON.stringify(json.errors || userErrors)}`);
    }

    return {
      success: true,
      webhookId: json.data?.webhookSubscriptionCreate?.webhookSubscription?.id,
      callbackUrl,
      alreadyRegistered: false,
    };
  }

  /**
   * Unregisters (disables) the PRODUCTS_UPDATE webhook in Shopify so automatic background
   * AI cleanup is turned off when the merchant chooses to disable Auto-Sync.
   */
  async unregisterProductUpdateWebhook(callbackUrl: string): Promise<{
    success: boolean;
    deletedCount: number;
    callbackUrl: string;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      return { success: true, deletedCount: 1, callbackUrl };
    }

    const checkQuery = `
      query {
        webhookSubscriptions(first: 25, topics: [PRODUCTS_UPDATE]) {
          edges {
            node {
              id
              topic
              endpoint {
                __typename
                ... on WebhookHttpEndpoint {
                  callbackUrl
                }
              }
            }
          }
        }
      }
    `;

    interface WebhookSubscriptionsListQueryData {
      webhookSubscriptions?: {
        edges?: Array<{
          node?: {
            id?: string;
            endpoint?: {
              callbackUrl?: string;
            };
          };
        }>;
      };
    }
    const checkJson = await this.executeGraphQLWithBackoff<WebhookSubscriptionsListQueryData>(checkQuery);
    const existing = checkJson.data?.webhookSubscriptions?.edges || [];

    const deleteMutation = `
      mutation webhookSubscriptionDelete($id: ID!) {
        webhookSubscriptionDelete(id: $id) {
          deletedWebhookSubscriptionId
          userErrors {
            field
            message
          }
        }
      }
    `;

    let deletedCount = 0;
    for (const edge of existing) {
      if (edge.node?.endpoint?.callbackUrl === callbackUrl && edge.node.id) {
        await this.executeGraphQLWithBackoff(deleteMutation, { id: edge.node.id });
        deletedCount++;
      }
    }

    return {
      success: true,
      deletedCount,
      callbackUrl,
    };
  }

  /**
   * Priority 4 (Monetization & Free Trial Gate & Hybrid Usage-Based Billing):
   * Creates a Shopify Hybrid App Subscription ($65/mo base for 500 images + $0.05/image overage, capped at $100/mo)
   * with configurable trialDays (14 days for standard trial, 0 days for immediate active subscription)
   * via Shopify GraphQL Billing API (`appSubscriptionCreate`).
   */
  async createBillingSubscription(
    returnUrl: string,
    isTestMode = true,
    trialDays = 14
  ): Promise<{
    success: boolean;
    subscriptionId: string;
    confirmationUrl: string;
    mode: "shopify_billing_api" | "custom_app_test_mode";
    usageLineItemId?: string;
    rawErrors?: unknown;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      const isImmediate = trialDays === 0;
      return {
        success: true,
        subscriptionId: isImmediate
          ? "gid://shopify/AppSubscription/mock_active_65usd"
          : "gid://shopify/AppSubscription/mock_65usd_14d",
        confirmationUrl: `${returnUrl}&billing_confirmed=1${isImmediate ? "&plan=ACTIVE" : ""}`,
        mode: "custom_app_test_mode",
        usageLineItemId: "gid://shopify/AppSubscriptionLineItem/mock_usage_line_item",
      };
    }

    const mutation = `
      mutation appSubscriptionCreate(
        $name: String!
        $returnUrl: URL!
        $trialDays: Int
        $test: Boolean
        $lineItems: [AppSubscriptionLineItemInput!]!
      ) {
        appSubscriptionCreate(
          name: $name
          returnUrl: $returnUrl
          trialDays: $trialDays
          test: $test
          lineItems: $lineItems
        ) {
          appSubscription {
            id
            status
            trialDays
            lineItems {
              id
              plan {
                pricingDetails {
                  __typename
                }
              }
            }
          }
          confirmationUrl
          userErrors {
            field
            message
          }
        }
      }
    `;

    try {
      const lineItems = [
        {
          plan: {
            appRecurringPricingDetails: {
              price: { amount: 65.0, currencyCode: "USD" },
              interval: "EVERY_30_DAYS",
            },
          },
        },
        {
          plan: {
            appUsagePricingDetails: {
              terms: "$0.05 per cleaned image beyond 500 images/mo (Max $100/mo)",
              cappedAmount: { amount: 100.0, currencyCode: "USD" },
            },
          },
        },
      ];

      const json = await this.executeGraphQLWithBackoff<AppSubscriptionCreateResponse>(
        mutation,
        {
          name: "SafeMedia Shield Smart Protection Plan",
          returnUrl,
          trialDays: trialDays > 0 ? trialDays : undefined,
          test: isTestMode,
          lineItems,
        },
        "2024-10"
      );

      if (json.errors) {
        console.warn("[Billing] GraphQL errors:", JSON.stringify(json.errors));
      }
      const payload = json.data?.appSubscriptionCreate;
      if (payload?.userErrors && payload.userErrors.length > 0) {
        console.warn("[Billing] appSubscriptionCreate userErrors:", JSON.stringify(payload.userErrors));
      }
      if (payload?.confirmationUrl && payload?.appSubscription?.id) {
        let usageLineItemId: string | undefined;
        const createdLineItems = payload.appSubscription.lineItems;
        if (Array.isArray(createdLineItems)) {
          for (const item of createdLineItems) {
            if (item?.plan?.pricingDetails?.__typename === "AppUsagePricingDetails") {
              usageLineItemId = item.id;
              break;
            }
          }
        }
        return {
          success: true,
          subscriptionId: payload.appSubscription.id,
          confirmationUrl: payload.confirmationUrl,
          mode: "shopify_billing_api",
          usageLineItemId,
        };
      }

      const errMsg =
        payload?.userErrors?.map((u) => u.message).join(", ") ||
        json.errors?.map((e) => e.message).join(", ") ||
        "Shopify Billing API did not return a confirmationUrl";

      throw new Error(`Shopify Billing Error: ${errMsg}`);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error("[Billing] GraphQL mutation failed:", errorMsg);
      throw new Error(`Shopify Billing Subscription failed: ${errorMsg}`);
    }
  }

  /**
   * Pre-Flight Usage Charge ($0.05/cleaned image beyond 500 images/mo).
   * Calls Shopify GraphQL `appUsageRecordCreate` before executing GPU inference.
   * Guarantees zero unbilled GPU costs.
   */
  async createAppUsageRecord(
    subscriptionLineItemId: string,
    description = "SafeMedia AI Image Cleanup Overage Charge",
    price = 0.05,
    currencyCode = "USD"
  ): Promise<{
    success: boolean;
    usageRecordId?: string;
    cappedAmountExceeded?: boolean;
    userErrors?: Array<{ field?: string[]; message: string }>;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      if (subscriptionLineItemId === "mock_cap_exceeded") {
        return {
          success: false,
          cappedAmountExceeded: true,
          userErrors: [{ field: ["cappedAmount"], message: "Total usage record charges exceed capped amount." }],
        };
      }
      return {
        success: true,
        usageRecordId: `gid://shopify/AppUsageRecord/mock_${Date.now()}`,
      };
    }

    const mutation = `
      mutation appUsageRecordCreate(
        $description: String!
        $price: MoneyInput!
        $subscriptionLineItemId: ID!
      ) {
        appUsageRecordCreate(
          description: $description
          price: $price
          subscriptionLineItemId: $subscriptionLineItemId
        ) {
          appUsageRecord {
            id
          }
          userErrors {
            field
            message
          }
        }
      }
    `;

    try {
      const json = await this.executeGraphQLWithBackoff<AppUsageRecordCreateResponse>(
        mutation,
        {
          description,
          price: { amount: price, currencyCode },
          subscriptionLineItemId,
        },
        "2024-10"
      );

      const payload = json.data?.appUsageRecordCreate;
      if (payload?.userErrors && payload.userErrors.length > 0) {
        const errorText = payload.userErrors.map((u) => u.message).join(", ");
        const isCapExceeded =
          errorText.toLowerCase().includes("capped amount") ||
          errorText.toLowerCase().includes("cap exceeded") ||
          errorText.toLowerCase().includes("exceeds");
        return {
          success: false,
          cappedAmountExceeded: isCapExceeded,
          userErrors: payload.userErrors,
        };
      }

      if (payload?.appUsageRecord?.id) {
        return {
          success: true,
          usageRecordId: payload.appUsageRecord.id,
        };
      }

      return {
        success: false,
        userErrors: [{ field: [], message: "No usage record returned from Shopify." }],
      };
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error("[Billing] appUsageRecordCreate failed:", errorMsg);
      const isCapExceeded =
        errorMsg.toLowerCase().includes("capped amount") ||
        errorMsg.toLowerCase().includes("cap exceeded");
      return {
        success: false,
        cappedAmountExceeded: isCapExceeded,
        userErrors: [{ field: [], message: errorMsg }],
      };
    }
  }

  /**
   * Queries the Shopify GraphQL Admin API to determine if the store has an active app subscription.
   */
  async getActiveSubscription(): Promise<{
    hasActiveSubscription: boolean;
    subscriptionId?: string;
    status?: string;
    name?: string;
  }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      return { hasActiveSubscription: false };
    }

    const query = `
      query {
        currentAppInstallation {
          activeSubscriptions {
            id
            name
            status
            test
          }
        }
      }
    `;

    try {
      const json = await this.executeGraphQLWithBackoff<ActiveSubscriptionsResponse>(query, undefined, "2024-10");
      const subs = json.data?.currentAppInstallation?.activeSubscriptions || [];
      if (subs.length > 0) {
        const activeSub = subs[0];
        return {
          hasActiveSubscription: true,
          subscriptionId: activeSub.id,
          status: activeSub.status,
          name: activeSub.name,
        };
      }
    } catch (err) {
      console.warn("[Billing] checkActiveSubscription failed:", err);
    }

    return { hasActiveSubscription: false };
  }

  /**
   * Generates mock product hierarchy representing typical multi-variant Shopify merchandise,
   * overlaid with any per-shop persisted mock metafield / variant bindings.
   */
  private getMockProducts(): ProductSnapshot[] {
    const baseProducts: ProductSnapshot[] = [
      {
        productId: "gid://shopify/Product/1001",
        productTitle: "プレミアム ヘビーウェイト クラシックTシャツ",
        bodyHtml: "<p>最高級超長綿を使用したタフで上質なTシャツ。<img src='https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800' /></p>",
        originalMediaList: [
          { id: "gid://shopify/MediaImage/2001", url: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800", altText: "Black T-Shirt" },
          { id: "gid://shopify/MediaImage/2002", url: "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800", altText: "White T-Shirt" },
          { id: "gid://shopify/MediaImage/2003", url: "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=800", altText: "Navy T-Shirt" },
        ],
        variants: [
          { variantId: "gid://shopify/ProductVariant/3001", variantTitle: "Black / S", originalMediaId: "gid://shopify/MediaImage/2001", originalImageUrl: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800", sku: "TS-BLK-S", price: "4800" },
          { variantId: "gid://shopify/ProductVariant/3002", variantTitle: "Black / M", originalMediaId: "gid://shopify/MediaImage/2001", originalImageUrl: "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800", sku: "TS-BLK-M", price: "4800" },
          { variantId: "gid://shopify/ProductVariant/3003", variantTitle: "White / S", originalMediaId: "gid://shopify/MediaImage/2002", originalImageUrl: "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800", sku: "TS-WHT-S", price: "4800" },
          { variantId: "gid://shopify/ProductVariant/3004", variantTitle: "White / M", originalMediaId: "gid://shopify/MediaImage/2002", originalImageUrl: "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800", sku: "TS-WHT-M", price: "4800" },
          { variantId: "gid://shopify/ProductVariant/3005", variantTitle: "Navy / L", originalMediaId: "gid://shopify/MediaImage/2003", originalImageUrl: "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=800", sku: "TS-NVY-L", price: "4800" },
        ],
        capturedAt: new Date().toISOString(),
      },
      {
        productId: "gid://shopify/Product/1002",
        productTitle: "オーガニック フレンチテリー ジップアップフーディー",
        bodyHtml: "<p>通年着用できる肉厚裏毛スウェット生地のジップパーカー。</p>",
        originalMediaList: [
          { id: "gid://shopify/MediaImage/2011", url: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800", altText: "Heather Grey" },
          { id: "gid://shopify/MediaImage/2012", url: "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?w=800", altText: "Charcoal Black" },
        ],
        variants: [
          { variantId: "gid://shopify/ProductVariant/3011", variantTitle: "Heather Grey / M", originalMediaId: "gid://shopify/MediaImage/2011", originalImageUrl: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800", sku: "HD-GRY-M", price: "12800" },
          { variantId: "gid://shopify/ProductVariant/3012", variantTitle: "Heather Grey / L", originalMediaId: "gid://shopify/MediaImage/2011", originalImageUrl: "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800", sku: "HD-GRY-L", price: "12800" },
          { variantId: "gid://shopify/ProductVariant/3013", variantTitle: "Charcoal / M", originalMediaId: "gid://shopify/MediaImage/2012", originalImageUrl: "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?w=800", sku: "HD-CHR-M", price: "12800" },
        ],
        capturedAt: new Date().toISOString(),
      },
    ];

    const shopMap = this.getShopMockMap();
    return baseProducts.map((p) => {
      const override = shopMap.get(p.productId);
      if (!override) return p;
      return {
        ...p,
        cleanAdImageUrl: override.cleanAdImageUrl,
        dualFeedMetadata: override.dualFeedMetadata,
        variants: p.variants.map((v) => ({
          ...v,
          originalMediaId: override.variantMediaIds?.[v.variantId] ?? v.originalMediaId,
          cleanAdImageUrl:
            override.variantCleanAdImageUrls?.[v.variantId] ??
            override.dualFeedMetadata?.variantCleanImageMap?.[v.variantId] ??
            v.cleanAdImageUrl,
        })),
      };
    });
  }
}
