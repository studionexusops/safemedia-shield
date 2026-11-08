#!/usr/bin/env python3
"""Sync SVGs from assets/ directory into cloudflare_worker/src/assets.ts"""

import os
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
TARGET_TS = os.path.join(REPO_ROOT, "cloudflare_worker", "src", "assets.ts")

with open(os.path.join(ASSETS_DIR, "app_icon_1200x1200.svg"), "r", encoding="utf-8") as f:
    icon_svg = f.read().strip()

with open(os.path.join(ASSETS_DIR, "banner_dual_feed_1600x900.svg"), "r", encoding="utf-8") as f:
    dual_svg = f.read().strip()

with open(os.path.join(ASSETS_DIR, "banner_always_on_1600x900.svg"), "r", encoding="utf-8") as f:
    always_svg = f.read().strip()

with open(os.path.join(ASSETS_DIR, "banner_one_click_rollback_1600x900.svg"), "r", encoding="utf-8") as f:
    rollback_svg = f.read().strip()

# Safely escape backticks and interpolation inside template literals
def escape_for_ts_template(svg_str: str) -> str:
    return svg_str.replace("`", "\\`").replace("${", "\\${")

content = f"""/**
 * SafeMedia Shield / AdFeed Clean - Public Brand & Store Assets
 * High-resolution vector SVGs for App Icon and Promotional Banners.
 */

export const ASSET_APP_ICON_SVG = `{escape_for_ts_template(icon_svg)}`;

export const ASSET_BANNER_DUAL_FEED_SVG = `{escape_for_ts_template(dual_svg)}`;

export const ASSET_BANNER_ALWAYS_ON_SVG = `{escape_for_ts_template(always_svg)}`;

export const ASSET_BANNER_ONE_CLICK_ROLLBACK_SVG = `{escape_for_ts_template(rollback_svg)}`;

export function getPublicAsset(pathname: string): {{ content: string; contentType: string }} | null {{
  const cleanPath = pathname.replace(/^\\/assets\\//, "");
  switch (cleanPath) {{
    case "app_icon_1200x1200.svg":
    case "app-icon.svg":
    case "app-icon":
      return {{ content: ASSET_APP_ICON_SVG, contentType: "image/svg+xml" }};

    case "banner_dual_feed_1600x900.svg":
    case "banner-dual-feed.svg":
    case "banner-dual-feed":
      return {{ content: ASSET_BANNER_DUAL_FEED_SVG, contentType: "image/svg+xml" }};

    case "banner_always_on_1600x900.svg":
    case "banner-always-on.svg":
    case "banner-always-on":
      return {{ content: ASSET_BANNER_ALWAYS_ON_SVG, contentType: "image/svg+xml" }};

    case "banner_one_click_rollback_1600x900.svg":
    case "banner-one-click-rollback.svg":
    case "banner-one-click-rollback":
      return {{ content: ASSET_BANNER_ONE_CLICK_ROLLBACK_SVG, contentType: "image/svg+xml" }};

    default:
      return null;
  }}
}}
"""

with open(TARGET_TS, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully synced SVGs to cloudflare_worker/src/assets.ts")
