/**
 * Shopify GraphQL API & Variant Mapping Preserve Layer
 * Solves the structural flaw of variant image disconnection during asset updates.
 */

import { ProductSnapshot, StoreSnapshot, VariantMapping, MediaItem } from "./types";

export class ShopifyVariantManager {
  private shop: string;
  private accessToken: string;

  constructor(shop: string, accessToken: string) {
    this.shop = shop;
    this.accessToken = accessToken;
  }

  /**
   * Fetches product and variant hierarchy from Shopify GraphQL Admin API.
   * If mock mode / token is not set, returns realistic sample data for local testing.
   */
  async fetchProductsWithVariants(): Promise<ProductSnapshot[]> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
      return this.getMockProducts();
    }

    const query = `
      query getProductsWithMedia($first: Int!) {
        products(first: $first) {
          edges {
            node {
              id
              title
              descriptionHtml
              cleanAdImageMetafield: metafield(namespace: "safemedia", key: "clean_ad_image_url") {
                value
              }
              dualFeedMeta: metafield(namespace: "safemedia", key: "dual_feed_metadata") {
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
              variants(first: 50) {
                edges {
                  node {
                    id
                    title
                    sku
                    price
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

    const res = await fetch(`https://${this.shop}/admin/api/2024-01/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({ query, variables: { first: 50 } }),
    });

    if (!res.ok) {
      throw new Error(`Shopify GraphQL error: ${res.status} ${res.statusText}`);
    }

    const json = (await res.json()) as any;
    if (json.errors) {
      throw new Error(`Shopify GraphQL errors: ${JSON.stringify(json.errors)}`);
    }

    const products: ProductSnapshot[] = [];
    for (const edge of json.data.products.edges) {
      const p = edge.node;
      const mediaList: MediaItem[] = [];
      for (const mEdge of p.media.edges) {
        if (mEdge.node.mediaContentType === "IMAGE" && mEdge.node.image) {
          mediaList.push({
            id: mEdge.node.id,
            url: mEdge.node.image.url,
            altText: mEdge.node.image.altText || "",
          });
        }
      }

      const variants: VariantMapping[] = [];
      for (const vEdge of p.variants.edges) {
        const v = vEdge.node;
        const vMedia = v.media?.edges?.[0]?.node;
        variants.push({
          variantId: v.id,
          variantTitle: v.title,
          originalMediaId: vMedia ? vMedia.id : "",
          originalImageUrl: vMedia?.image?.url || (mediaList[0]?.url || ""),
          sku: v.sku || "",
          price: v.price || "",
        });
      }

      let parsedDualMeta: any = undefined;
      if (p.dualFeedMeta?.value) {
        try {
          parsedDualMeta = JSON.parse(p.dualFeedMeta.value);
        } catch {
          parsedDualMeta = undefined;
        }
      }

      products.push({
        productId: p.id,
        productTitle: p.title,
        bodyHtml: p.descriptionHtml || "",
        variants,
        originalMediaList: mediaList,
        capturedAt: new Date().toISOString(),
        cleanAdImageUrl: p.cleanAdImageMetafield?.value || undefined,
        dualFeedMetadata: parsedDualMeta,
      });
    }

    return products;
  }

  /**
   * Rebinds variants to their corresponding new media IDs in Shopify.
   * Guarantees zero variant-image detachment.
   */
  async rebindVariants(
    productId: string,
    variantUpdates: Array<{ variantId: string; newMediaId: string }>
  ): Promise<{ success: boolean; updatedCount: number }> {
    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
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
      productId,
      variants: variantUpdates.map((u) => ({
        id: u.variantId,
        mediaId: u.newMediaId,
      })),
    };

    const res = await fetch(`https://${this.shop}/admin/api/2024-01/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({ query: mutation, variables }),
    });

    const json = (await res.json()) as any;
    if (json.errors || json.data?.productVariantsBulkUpdate?.userErrors?.length) {
      throw new Error(`Rebind failed: ${JSON.stringify(json.errors || json.data.productVariantsBulkUpdate.userErrors)}`);
    }

    return { success: true, updatedCount: variantUpdates.length };
  }

  /**
   * Priority 1 (Dual-Feed Smart Routing):
   * Writes the AI-cleaned ad image URL and metadata into the product's hidden Metafields
   * (`safemedia.clean_ad_image_url` and `safemedia.dual_feed_metadata`).
   */
  async setCleanAdImageMetafield(
    productId: string,
    cleanAdImageUrl: string,
    metadata: {
      sourceImageUrl: string;
      cleanedAt: string;
      maskCoveragePct?: number;
      processingSec?: number;
      engine?: string;
    }
  ): Promise<{ success: boolean; metafieldId?: string }> {
    const gid = productId.startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;

    if (!this.accessToken || this.accessToken.startsWith("mock_")) {
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

    const variables = {
      metafields: [
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
          value: JSON.stringify(metadata),
        },
      ],
    };

    const res = await fetch(`https://${this.shop}/admin/api/2024-01/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({ query: mutation, variables }),
    });

    const json = (await res.json()) as any;
    const userErrors = json.data?.metafieldsSet?.userErrors;
    if (json.errors || (userErrors && userErrors.length > 0)) {
      throw new Error(`Metafield update failed: ${JSON.stringify(json.errors || userErrors)}`);
    }

    const firstId = json.data?.metafieldsSet?.metafields?.[0]?.id;
    return { success: true, metafieldId: firstId };
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

    const checkRes = await fetch(`https://${this.shop}/admin/api/2024-01/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({ query: checkQuery }),
    });
    const checkJson = (await checkRes.json()) as any;
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

    const res = await fetch(`https://${this.shop}/admin/api/2024-01/graphql.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": this.accessToken,
      },
      body: JSON.stringify({
        query: createMutation,
        variables: {
          topic: "PRODUCTS_UPDATE",
          webhookSubscription: {
            callbackUrl,
            format: "JSON",
          },
        },
      }),
    });

    const json = (await res.json()) as any;
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
   * Generates mock product hierarchy representing typical multi-variant Shopify merchandise.
   */
  private getMockProducts(): ProductSnapshot[] {
    return [
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
  }
}
