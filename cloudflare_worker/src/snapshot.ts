/**
 * Cloud Immutable Snapshot Engine & 1-Click Rollback Manager
 * Saves exact state to Cloudflare R2 before any modification.
 * Enables 10-second complete time-machine recovery with structured Before/After Product Data Diffs.
 */

import {
  Env,
  StoreSnapshot,
  ProductSnapshot,
  RollbackProductDataDiff,
  RollbackExecutionResult,
  SnapshotSummary,
} from "./types";
import { ShopifyVariantManager } from "./shopify";

// In-memory fallback cache for development/mocking when R2 is unconfigured
const MEMORY_SNAPSHOT_STORE: Map<string, StoreSnapshot> = new Map();
const LAST_ROLLBACK_STORE: Map<string, RollbackExecutionResult> = new Map();
const MEMORY_BASELINE_POINTER: Map<string, string> = new Map();
const MEMORY_LATEST_POINTER: Map<string, string> = new Map();

export class SnapshotEngine {
  private env: Env;
  private shop: string;

  constructor(env: Env, shop: string) {
    this.env = env;
    this.shop = shop;
  }

  /**
   * Generates and writes an immutable snapshot to Cloudflare R2.
   * Enforces retention policy: 1 Virgin Baseline + up to 3 Recent Rolling Generations.
   */
  async createSnapshot(products: ProductSnapshot[]): Promise<StoreSnapshot> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const snapshotId = `snap_${this.shop.replace(/[^a-zA-Z0-9]/g, "_")}_${timestamp}`;

    let totalImages = 0;
    const productMap: Record<string, ProductSnapshot> = {};

    for (const p of products) {
      productMap[p.productId] = p;
      totalImages += p.originalMediaList.length;
    }

    // Check if virgin baseline already exists
    const existingBaseline = await this.getBaselineSnapshotId();
    const isBaseline = !existingBaseline;

    const snapshot: StoreSnapshot = {
      snapshotId,
      shop: this.shop,
      createdAt: new Date().toISOString(),
      totalProducts: products.length,
      totalImages,
      products: productMap,
      isBaseline,
    };

    const payload = JSON.stringify(snapshot, null, 2);

    if (this.env.SNAPSHOT_BUCKET) {
      const key = `snapshots/${this.shop}/${snapshotId}.json`;
      await this.env.SNAPSHOT_BUCKET.put(key, payload, {
        httpMetadata: { contentType: "application/json" },
        customMetadata: {
          shop: this.shop,
          createdAt: snapshot.createdAt,
          totalProducts: String(snapshot.totalProducts),
          totalImages: String(snapshot.totalImages),
          isBaseline: String(isBaseline),
        },
      });

      // If virgin baseline does not exist yet, pin this snapshot as the permanent baseline
      if (isBaseline) {
        await this.env.SNAPSHOT_BUCKET.put(
          `snapshots/${this.shop}/baseline.json`,
          JSON.stringify({ baselineSnapshotId: snapshotId, key, createdAt: snapshot.createdAt })
        );
      }

      // Update latest pointer in R2
      await this.env.SNAPSHOT_BUCKET.put(
        `snapshots/${this.shop}/latest.json`,
        JSON.stringify({ latestSnapshotId: snapshotId, key })
      );

      // Prune old generations: retain Virgin Baseline + top 3 most recent rolling snapshots
      await this.pruneOldSnapshots(snapshotId);
    } else {
      // Local development fallback
      if (isBaseline) {
        MEMORY_BASELINE_POINTER.set(this.shop, snapshotId);
        MEMORY_SNAPSHOT_STORE.set(`${this.shop}_baseline`, snapshot);
      }
      MEMORY_LATEST_POINTER.set(this.shop, snapshotId);
      MEMORY_SNAPSHOT_STORE.set(snapshotId, snapshot);
      MEMORY_SNAPSHOT_STORE.set(`${this.shop}_latest`, snapshot);

      // Memory pruning
      this.pruneMemorySnapshots();
    }

    return snapshot;
  }

  /**
   * Retrieves the baseline snapshot ID if already established.
   */
  async getBaselineSnapshotId(): Promise<string | null> {
    if (this.env.SNAPSHOT_BUCKET) {
      const obj = await this.env.SNAPSHOT_BUCKET.get(`snapshots/${this.shop}/baseline.json`);
      if (!obj) return null;
      try {
        const parsed = (await obj.json()) as { baselineSnapshotId?: string };
        return parsed.baselineSnapshotId || null;
      } catch {
        return null;
      }
    }
    return MEMORY_BASELINE_POINTER.get(this.shop) || null;
  }

  /**
   * Retrieves the virgin baseline snapshot for this shop.
   */
  async getBaselineSnapshot(): Promise<StoreSnapshot | null> {
    if (this.env.SNAPSHOT_BUCKET) {
      const baseObj = await this.env.SNAPSHOT_BUCKET.get(`snapshots/${this.shop}/baseline.json`);
      if (!baseObj) return null;
      try {
        const pointer = (await baseObj.json()) as { key?: string; baselineSnapshotId?: string };
        const key = pointer.key || `snapshots/${this.shop}/${pointer.baselineSnapshotId}.json`;
        const snapObj = await this.env.SNAPSHOT_BUCKET.get(key);
        if (!snapObj) return null;
        return (await snapObj.json()) as StoreSnapshot;
      } catch {
        return null;
      }
    }
    return (
      MEMORY_SNAPSHOT_STORE.get(`${this.shop}_baseline`) ||
      (MEMORY_BASELINE_POINTER.get(this.shop)
        ? MEMORY_SNAPSHOT_STORE.get(MEMORY_BASELINE_POINTER.get(this.shop)!) || null
        : null)
    );
  }

  /**
   * Prunes older snapshots in Cloudflare R2, enforcing retention of:
   * 1 Virgin Baseline (permanent oldest snapshot) + max 3 most recent rolling snapshots (Total max 4).
   */
  private async pruneOldSnapshots(currentSnapshotId?: string): Promise<string | null> {
    if (!this.env.SNAPSHOT_BUCKET) return null;

    try {
      const listed = await this.env.SNAPSHOT_BUCKET.list({
        prefix: `snapshots/${this.shop}/`,
      });

      // Filter only individual snapshot JSON files, exclude pointer files (latest.json, baseline.json)
      const snapshotObjects = listed.objects.filter((o) => {
        const filename = o.key.split("/").pop() || "";
        return (
          filename.endsWith(".json") &&
          filename !== "latest.json" &&
          filename !== "baseline.json"
        );
      });

      if (snapshotObjects.length === 0) return null;

      // Sort ascending by key (ISO timestamp in filename) and uploaded time so index 0 is ALWAYS the true oldest Virgin Baseline
      snapshotObjects.sort((a, b) => {
        const timeDiff = a.uploaded.getTime() - b.uploaded.getTime();
        return timeDiff !== 0 ? timeDiff : a.key.localeCompare(b.key);
      });

      const oldestObj = snapshotObjects[0];
      const trueBaselineId = oldestObj.key.split("/").pop()?.replace(/\.json$/, "") || "";

      // Ensure baseline.json always points to the true oldest virgin snapshot
      const existingBaselineId = await this.getBaselineSnapshotId();
      if (existingBaselineId !== trueBaselineId && trueBaselineId) {
        await this.env.SNAPSHOT_BUCKET.put(
          `snapshots/${this.shop}/baseline.json`,
          JSON.stringify({
            baselineSnapshotId: trueBaselineId,
            key: oldestObj.key,
            createdAt: oldestObj.uploaded.toISOString(),
          })
        ).catch(() => {});
      }

      // Separate non-baseline rolling snapshots
      const rollingSnapshots = snapshotObjects.filter((o) => {
        const id = o.key.split("/").pop()?.replace(/\.json$/, "");
        return id !== trueBaselineId;
      });

      // Sort rolling snapshots descending (newest first)
      rollingSnapshots.sort((a, b) => {
        const timeDiff = b.uploaded.getTime() - a.uploaded.getTime();
        return timeDiff !== 0 ? timeDiff : b.key.localeCompare(a.key);
      });

      // Retain max 3 rolling generations + 1 Virgin Baseline = max 4 snapshots total
      const maxRollingGenerations = 3;
      if (rollingSnapshots.length > maxRollingGenerations) {
        const toDelete = rollingSnapshots.slice(maxRollingGenerations);
        for (const item of toDelete) {
          const itemId = item.key.split("/").pop()?.replace(/\.json$/, "");
          if (itemId !== currentSnapshotId && itemId !== trueBaselineId) {
            await this.env.SNAPSHOT_BUCKET.delete(item.key).catch(() => {});
          }
        }
      }

      return trueBaselineId;
    } catch (err) {
      console.warn(`[SnapshotEngine] Pruning snapshots failed for ${this.shop}:`, err);
      return null;
    }
  }

  /**
   * Prunes in-memory snapshots for local mock environment.
   */
  private pruneMemorySnapshots(): void {
    const baselineId = MEMORY_BASELINE_POINTER.get(this.shop);
    const shopPrefix = `snap_${this.shop.replace(/[^a-zA-Z0-9]/g, "_")}_`;
    const shopSnapshots: Array<{ id: string; snapshot: StoreSnapshot }> = [];

    for (const [id, snap] of MEMORY_SNAPSHOT_STORE.entries()) {
      if (id.startsWith(shopPrefix) && id !== baselineId) {
        shopSnapshots.push({ id, snapshot: snap });
      }
    }

    // Sort newest first
    shopSnapshots.sort(
      (a, b) =>
        new Date(b.snapshot.createdAt).getTime() -
        new Date(a.snapshot.createdAt).getTime()
    );

    const maxRollingGenerations = 3;
    if (shopSnapshots.length > maxRollingGenerations) {
      const toDelete = shopSnapshots.slice(maxRollingGenerations);
      for (const item of toDelete) {
        MEMORY_SNAPSHOT_STORE.delete(item.id);
      }
    }
  }

  /**
   * Retrieves the latest snapshot for this shop.
   */
  async getLatestSnapshot(): Promise<StoreSnapshot | null> {
    if (this.env.SNAPSHOT_BUCKET) {
      const pointerObj = await this.env.SNAPSHOT_BUCKET.get(`snapshots/${this.shop}/latest.json`);
      if (!pointerObj) return null;
      const pointer = (await pointerObj.json()) as { key: string };
      const snapObj = await this.env.SNAPSHOT_BUCKET.get(pointer.key);
      if (!snapObj) return null;
      return (await snapObj.json()) as StoreSnapshot;
    } else {
      return MEMORY_SNAPSHOT_STORE.get(`${this.shop}_latest`) || null;
    }
  }

  /**
   * Retrieves the list of available snapshots for this shop (Virgin Baseline + up to 3 Recent Generations),
   * structured for the Time-Machine restore dropdown selector.
   */
  async listSnapshots(): Promise<SnapshotSummary[]> {
    const prunedBaselineId = await this.pruneOldSnapshots();
    const baselineId = prunedBaselineId || (await this.getBaselineSnapshotId());
    const latestSnapshot = await this.getLatestSnapshot();
    const latestId = latestSnapshot?.snapshotId || null;

    const summaries: SnapshotSummary[] = [];

    if (this.env.SNAPSHOT_BUCKET) {
      const listed = await this.env.SNAPSHOT_BUCKET.list({
        prefix: `snapshots/${this.shop}/`,
      });

      const snapshotFiles = listed.objects.filter((o) => {
        const fname = o.key.split("/").pop() || "";
        return (
          fname.endsWith(".json") &&
          fname !== "latest.json" &&
          fname !== "baseline.json"
        );
      });

      for (const file of snapshotFiles) {
        const snapId = file.key.split("/").pop()?.replace(/\.json$/, "") || "";
        const isBase = snapId === baselineId;
        const isLate = snapId === latestId;

        let totalProducts = 0;
        let totalImages = 0;
        let createdAt = file.uploaded.toISOString();

        if (file.customMetadata?.totalProducts) {
          totalProducts = parseInt(file.customMetadata.totalProducts, 10) || 0;
        }
        if (file.customMetadata?.totalImages) {
          totalImages = parseInt(file.customMetadata.totalImages, 10) || 0;
        }
        if (file.customMetadata?.createdAt) {
          createdAt = file.customMetadata.createdAt;
        }

        // If metadata was absent, read JSON file
        if (totalProducts === 0 && (isBase || isLate)) {
          try {
            const obj = await this.env.SNAPSHOT_BUCKET.get(file.key);
            if (obj) {
              const parsed = (await obj.json()) as StoreSnapshot;
              totalProducts = parsed.totalProducts || 0;
              totalImages = parsed.totalImages || 0;
              createdAt = parsed.createdAt || createdAt;
            }
          } catch {
            // ignore
          }
        }

        const dateStr = createdAt.replace("T", " ").replace(/\..+$/, " UTC");
        let label = `Backup (${dateStr} • ${totalProducts} Products)`;
        if (isLate && isBase) {
          label = `🟢 Latest & Virgin Baseline (${dateStr} • ${totalProducts} Products)`;
        } else if (isLate) {
          label = `🟢 Latest Backup (${dateStr} • ${totalProducts} Products)`;
        } else if (isBase) {
          label = `🛡️ Virgin Baseline (Initial Virgin State • ${totalProducts} Products)`;
        }

        summaries.push({
          snapshotId: snapId,
          key: file.key,
          createdAt,
          totalProducts,
          totalImages,
          isBaseline: isBase,
          isLatest: isLate,
          label,
        });
      }
    } else {
      // Memory fallback
      const shopPrefix = `snap_${this.shop.replace(/[^a-zA-Z0-9]/g, "_")}_`;
      const seenIds = new Set<string>();

      for (const [id, snap] of MEMORY_SNAPSHOT_STORE.entries()) {
        if (!id.startsWith(shopPrefix) || seenIds.has(id)) continue;
        seenIds.add(id);

        const isBase = id === baselineId;
        const isLate = id === latestId;
        const dateStr = snap.createdAt.replace("T", " ").replace(/\..+$/, " UTC");
        let label = `Backup (${dateStr} • ${snap.totalProducts} Products)`;
        if (isLate && isBase) {
          label = `🟢 Latest & Virgin Baseline (${dateStr} • ${snap.totalProducts} Products)`;
        } else if (isLate) {
          label = `🟢 Latest Backup (${dateStr} • ${snap.totalProducts} Products)`;
        } else if (isBase) {
          label = `🛡️ Virgin Baseline (Initial Virgin State • ${snap.totalProducts} Products)`;
        }

        summaries.push({
          snapshotId: id,
          key: `snapshots/${this.shop}/${id}.json`,
          createdAt: snap.createdAt,
          totalProducts: snap.totalProducts,
          totalImages: snap.totalImages,
          isBaseline: isBase,
          isLatest: isLate,
          label,
        });
      }
    }

    // Sort descending by createdAt (newest first). Baseline will appear naturally or pinned.
    summaries.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

    return summaries;
  }

  /**
   * Retrieves the most recent rollback execution result (with Before/After product data diffs) for this shop.
   */
  async getLastRollbackResult(): Promise<RollbackExecutionResult | null> {
    if (this.env.SNAPSHOT_BUCKET) {
      try {
        const obj = await this.env.SNAPSHOT_BUCKET.get(`state/${this.shop}/last_rollback.json`);
        if (obj) {
          return (await obj.json()) as RollbackExecutionResult;
        }
      } catch {
        // Fall through
      }
    }
    return LAST_ROLLBACK_STORE.get(this.shop) || null;
  }

  /**
   * Lists stored snapshot objects directly from Cloudflare R2 bucket.
   * Excludes internal pointer files (latest.json, baseline.json) and enforces max 4 retention (1 Baseline + 3 Rolling).
   */
  async listR2Objects(): Promise<Array<{ key: string; size: number; uploaded: string }>> {
    if (this.env.SNAPSHOT_BUCKET) {
      await this.pruneOldSnapshots();
      const listed = await this.env.SNAPSHOT_BUCKET.list({
        prefix: `snapshots/${this.shop}/`,
      });
      const snapshotFiles = listed.objects.filter((o) => {
        const fname = o.key.split("/").pop() || "";
        return (
          fname.endsWith(".json") &&
          fname !== "latest.json" &&
          fname !== "baseline.json"
        );
      });
      snapshotFiles.sort((a, b) => {
        const timeDiff = a.uploaded.getTime() - b.uploaded.getTime();
        return timeDiff !== 0 ? timeDiff : a.key.localeCompare(b.key);
      });
      return snapshotFiles.map((o) => ({
        key: o.key,
        size: o.size,
        uploaded: o.uploaded.toISOString(),
      }));
    }
    return [];
  }

  /**
   * 1-Click Rollback Execution (Time Machine) with Before vs. After Product Data Comparison (Shopify Review 4.5.3).
   * Captures the live state before reverting, restores variants and metafields from the target R2 snapshot,
   * and returns the structured per-product Before/After diff array.
   */
  async rollbackToSnapshot(
    variantManager: ShopifyVariantManager,
    snapshotId?: string
  ): Promise<RollbackExecutionResult> {
    let targetSnapshot: StoreSnapshot | null = null;

    if (snapshotId) {
      const cleanSnapshotId = snapshotId.endsWith(".json")
        ? snapshotId.slice(0, -5)
        : snapshotId;

      if (!/^[a-zA-Z0-9_-]{1,128}$/.test(cleanSnapshotId)) {
        throw new Error("Invalid snapshotId format. Path traversal or invalid characters detected.");
      }

      if (cleanSnapshotId === "baseline") {
        targetSnapshot = await this.getBaselineSnapshot();
      } else if (cleanSnapshotId === "latest") {
        targetSnapshot = await this.getLatestSnapshot();
      } else if (this.env.SNAPSHOT_BUCKET) {
        const obj = await this.env.SNAPSHOT_BUCKET.get(`snapshots/${this.shop}/${cleanSnapshotId}.json`);
        if (obj) targetSnapshot = (await obj.json()) as StoreSnapshot;
      } else {
        targetSnapshot =
          MEMORY_SNAPSHOT_STORE.get(cleanSnapshotId) ||
          MEMORY_SNAPSHOT_STORE.get(snapshotId) ||
          null;
      }
    } else {
      targetSnapshot = await this.getLatestSnapshot();
    }

    if (!targetSnapshot) {
      throw new Error("No snapshot found to rollback to.");
    }

    // 1. Capture live product state right BEFORE executing rollback (for Before vs. After comparison)
    const liveProductsBefore = await variantManager.fetchProductsWithVariants().catch(() => []);
    const beforeProductMap = new Map<string, ProductSnapshot>();
    for (const lp of liveProductsBefore) {
      beforeProductMap.set(lp.productId, lp);
    }

    let restoredCount = 0;
    const products = Object.values(targetSnapshot.products);
    const revertedAt = new Date().toISOString();
    const productDataDiffs: RollbackProductDataDiff[] = [];

    for (const p of products) {
      const liveProd = beforeProductMap.get(p.productId);
      const storefrontImageUrl =
        liveProd?.originalMediaList[0]?.url || p.originalMediaList[0]?.url || "";
      const beforeCleanMeta = liveProd?.cleanAdImageUrl || null;

      // 2. Re-map each variant to its original media ID
      const revertUpdates = p.variants
        .filter((v) => Boolean(v.originalMediaId))
        .map((v) => ({
          variantId: v.variantId,
          newMediaId: v.originalMediaId,
        }));

      if (revertUpdates.length > 0) {
        await variantManager.rebindVariants(p.productId, revertUpdates);
      }

      // 3. Restore or purge ad-feed hidden metafields to exact snapshot state
      let afterCleanMeta: string | null = null;
      let metafieldAction: "RESTORED_TO_SNAPSHOT" | "PURGED_TO_VIRGIN" = "PURGED_TO_VIRGIN";

      if (p.cleanAdImageUrl) {
        await variantManager.setCleanAdImageMetafield(p.productId, p.cleanAdImageUrl, {
          sourceImageUrl: p.dualFeedMetadata?.sourceImageUrl || p.originalMediaList[0]?.url || "",
          shopifyImageUrl: p.dualFeedMetadata?.shopifyImageUrl || p.originalMediaList[0]?.url || "",
          cleanedAt: p.dualFeedMetadata?.cleanedAt || targetSnapshot.createdAt,
          maskCoveragePct: p.dualFeedMetadata?.maskCoveragePct,
          processingSec: p.dualFeedMetadata?.processingSec,
          engine: p.dualFeedMetadata?.engine || "Snapshot-Rollback",
        });
        afterCleanMeta = p.cleanAdImageUrl;
        metafieldAction = "RESTORED_TO_SNAPSHOT";
      } else {
        // Snapshot had no clean image; purge metafield to restore virgin state
        await variantManager.clearCleanAdImageMetafield(p.productId);
        afterCleanMeta = null;
        metafieldAction = "PURGED_TO_VIRGIN";
      }

      productDataDiffs.push({
        productId: p.productId,
        productTitle: p.productTitle,
        snapshotId: targetSnapshot.snapshotId,
        revertedAt,
        storefrontImageUrl,
        storefrontUnchanged: true,
        beforeRevert: {
          storefrontImageUrl,
          cleanAdImageMetafield: beforeCleanMeta,
          gmcImageLink: beforeCleanMeta || storefrontImageUrl,
          metaImageLink: beforeCleanMeta || storefrontImageUrl,
          variantCount: p.variants.length,
          variantLinksPreserved: true,
        },
        afterRevert: {
          storefrontImageUrl,
          cleanAdImageMetafield: afterCleanMeta,
          gmcImageLink: afterCleanMeta || storefrontImageUrl,
          metaImageLink: afterCleanMeta || storefrontImageUrl,
          metafieldAction,
          variantCount: p.variants.length,
          variantLinksPreserved: true,
        },
      });

      restoredCount++;
    }

    const result: RollbackExecutionResult = {
      success: true,
      restoredCount,
      restoredProducts: restoredCount,
      snapshotId: targetSnapshot.snapshotId,
      snapshotTimestamp: targetSnapshot.createdAt,
      revertedAt,
      metafieldsRestored: true,
      productDataDiffs,
      beforeAfterComparisons: productDataDiffs,
      message: "Store media and ad-feed metafields restored successfully.",
    };

    LAST_ROLLBACK_STORE.set(this.shop, result);
    if (this.env.SNAPSHOT_BUCKET) {
      try {
        await this.env.SNAPSHOT_BUCKET.put(
          `state/${this.shop}/last_rollback.json`,
          JSON.stringify(result, null, 2),
          { httpMetadata: { contentType: "application/json" } }
        );
      } catch {
        // Non-blocking persistence
      }
    }

    return result;
  }
}
