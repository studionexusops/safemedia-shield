#!/usr/bin/env python3
"""
Generate Shopify App Store Visual Assets for AdFeed Clean for Google Shopping.
Generates vector SVGs and uses macOS 'sips' to render high-resolution PNGs:
1. app_icon_1200x1200 (1200 x 1200 px)
2. banner_dual_feed_1600x900 (1600 x 900 px)
3. banner_always_on_1600x900 (1600 x 900 px)
4. banner_one_click_rollback_1600x900 (1600 x 900 px)
"""

import os
import subprocess

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

def generate_app_icon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1200" width="1200" height="1200">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00352c"/>
      <stop offset="45%" stop-color="#00664e"/>
      <stop offset="100%" stop-color="#008060"/>
    </linearGradient>
    <linearGradient id="shieldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="50%" stop-color="#f0fdf4"/>
      <stop offset="100%" stop-color="#d1fae5"/>
    </linearGradient>
    <linearGradient id="goldAccent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#f59e0b"/>
    </linearGradient>
    <linearGradient id="emeraldGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>
    <filter id="dropGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="24" stdDeviation="32" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
    <filter id="subtleGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="60" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Base Rounded Container -->
  <rect width="1200" height="1200" rx="260" fill="url(#bgGrad)"/>

  <!-- Ambient Glow Circles -->
  <circle cx="280" cy="300" r="260" fill="#10b981" opacity="0.18" filter="url(#subtleGlow)"/>
  <circle cx="950" cy="900" r="320" fill="#047857" opacity="0.25" filter="url(#subtleGlow)"/>

  <!-- Decorative Hex Grid Accent Lines -->
  <path d="M 120 400 L 1080 400 M 120 800 L 1080 800 M 400 120 L 400 1080 M 800 120 L 800 1080" stroke="#ffffff" stroke-width="1.5" stroke-dasharray="16 24" opacity="0.08"/>

  <!-- Dual Shield Graphic Group -->
  <g transform="translate(600, 530)" filter="url(#dropGlow)">
    <!-- Behind: Warm Promo Tag Badge Shield (Representing Merchant Store Sales) -->
    <path d="M -220 -280 C -220 -280 -60 -310 -20 -310 C 20 -310 180 -280 180 -280 C 180 -20 120 180 -20 280 C -160 180 -220 -20 -220 -280 Z"
          fill="url(#goldAccent)" opacity="0.35" transform="rotate(-12) translate(-50, -20)"/>

    <!-- Main Solid Shield (Representing Google Ad Feed Protection) -->
    <path d="M -260 -280 C -260 -280 -80 -330 0 -330 C 80 -330 260 -280 260 -280 C 260 20 160 260 0 380 C -160 260 -260 20 -260 -280 Z"
          fill="url(#shieldGrad)" stroke="#ffffff" stroke-width="12"/>

    <!-- Inner Emerald Shield Contour -->
    <path d="M -200 -220 C -200 -220 -60 -260 0 -260 C 60 -260 200 -220 200 -220 C 200 10 120 200 0 300 C -120 200 -200 10 -200 -220 Z"
          fill="url(#emeraldGlow)"/>

    <!-- Checkmark & Clean Spark Motif -->
    <!-- Large Crisp White Checkmark -->
    <path d="M -70 20 L -20 70 L 85 -45" fill="none" stroke="#ffffff" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>

    <!-- Sparkling Star / Wand Accent (Top Right of Shield) -->
    <g transform="translate(130, -160)">
      <path d="M 0 -45 Q 0 0 -45 0 Q 0 0 0 45 Q 0 0 45 0 Q 0 0 0 -45 Z" fill="#ffffff"/>
      <circle cx="0" cy="0" r="14" fill="#fbbf24"/>
    </g>
    <!-- Secondary Small Star -->
    <g transform="translate(-120, -140) scale(0.6)">
      <path d="M 0 -45 Q 0 0 -45 0 Q 0 0 0 45 Q 0 0 45 0 Q 0 0 0 -45 Z" fill="#ffffff" opacity="0.9"/>
    </g>
  </g>

  <!-- Typography: App Name -->
  <text x="600" y="1035" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        font-size="64" font-weight="900" letter-spacing="10" fill="#ffffff">ADFEED CLEAN</text>
  <text x="600" y="1090" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        font-size="28" font-weight="700" letter-spacing="6" fill="#a7f3d0">FOR GOOGLE SHOPPING</text>
</svg>
"""

def generate_banner_dual_feed_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a131b"/>
      <stop offset="50%" stop-color="#0d2222"/>
      <stop offset="100%" stop-color="#061214"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#192833"/>
      <stop offset="100%" stop-color="#111c24"/>
    </linearGradient>
    <linearGradient id="primaryBadgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#008060"/>
      <stop offset="100%" stop-color="#10b981"/>
    </linearGradient>
    <linearGradient id="redBadgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#dc2626"/>
      <stop offset="100%" stop-color="#ef4444"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1600" height="900" fill="url(#bgGrad)"/>
  <circle cx="800" cy="450" r="400" fill="#008060" opacity="0.12" filter="blur(80px)"/>

  <!-- Top Header Zone -->
  <g transform="translate(100, 75)">
    <!-- Category Badge -->
    <rect width="260" height="36" rx="18" fill="url(#primaryBadgeGrad)"/>
    <text x="130" y="24" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="800" letter-spacing="2" fill="#ffffff">DUAL-FEED ROUTING</text>

    <!-- Main Title -->
    <text x="0" y="85" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="44" font-weight="800" fill="#ffffff" letter-spacing="-0.5">
      Keep Selling Badges on Store. Clean on Google Shopping.
    </text>

    <!-- Subtitle -->
    <text x="0" y="125" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="400" fill="#94a3b8">
      Zero UI / Event-Driven AI Inpainting. Separate storefront images from Google Ads automatically.
    </text>
  </g>

  <!-- Comparison Cards Container -->
  <!-- LEFT CARD: Your Storefront -->
  <g transform="translate(100, 245)" filter="url(#shadow)">
    <rect width="580" height="580" rx="24" fill="url(#cardGrad)" stroke="#334155" stroke-width="2"/>
    
    <!-- Card Header -->
    <rect x="24" y="24" width="220" height="34" rx="8" fill="#1e293b"/>
    <text x="134" y="47" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="700" fill="#f8fafc">🏪 YOUR STOREFRONT</text>

    <text x="556" y="47" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="700" fill="#38bdf8">Sales Badges Active</text>

    <!-- Product Image Simulation Box -->
    <g transform="translate(40, 80)">
      <rect width="500" height="380" rx="16" fill="#f1f5f9"/>
      
      <!-- Product Placeholder -->
      <path d="M 120 280 C 140 230 200 180 270 190 C 330 200 370 170 410 210 C 420 230 420 280 390 290 Z" fill="#64748b" opacity="0.3"/>
      <ellipse cx="270" cy="240" rx="130" ry="60" fill="#cbd5e1"/>
      <text x="270" y="248" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="22" font-weight="700" fill="#475569">PRODUCT MASTER</text>

      <!-- Prominent Red Sale Corner Badge -->
      <polygon points="0,0 160,0 0,160" fill="url(#redBadgeGrad)"/>
      <text x="45" y="55" transform="rotate(-45, 45, 55)" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="18" font-weight="900" fill="#ffffff" letter-spacing="1">50% OFF</text>

      <!-- Golden Promotional Banner Ribbon -->
      <rect x="40" y="310" width="420" height="46" rx="8" fill="#f59e0b"/>
      <text x="250" y="340" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="18" font-weight="900" fill="#78350f" letter-spacing="1">⚡ LIMITED TIME CYBER DEAL ⚡</text>
    </g>

    <!-- Bottom Status Note -->
    <rect x="40" y="485" width="500" height="60" rx="12" fill="#0f172a" stroke="#1e293b"/>
    <circle cx="70" cy="515" r="8" fill="#10b981"/>
    <text x="92" y="521" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="16" font-weight="700" fill="#f8fafc">Original Store Badges Preserved</text>
  </g>

  <!-- CENTER ROUTING CONNECTOR -->
  <g transform="translate(710, 480)">
    <circle cx="90" cy="30" r="48" fill="#008060" filter="url(#shadow)"/>
    <path d="M 75 30 L 105 30 M 95 20 L 105 30 L 95 40" stroke="#ffffff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="90" y="105" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="800" fill="#a7f3d0" letter-spacing="1">AI INPAINT</text>
    <text x="90" y="125" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="12" font-weight="600" fill="#94a3b8">Cloud AI Engine</text>
  </g>

  <!-- RIGHT CARD: Google Merchant Center Feed -->
  <g transform="translate(920, 245)" filter="url(#shadow)">
    <rect width="580" height="580" rx="24" fill="url(#cardGrad)" stroke="#10b981" stroke-width="2"/>
    
    <!-- Card Header -->
    <rect x="24" y="24" width="260" height="34" rx="8" fill="#064e3b"/>
    <text x="154" y="47" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="700" fill="#6ee7b7">🔍 GOOGLE SHOPPING FEED</text>

    <text x="556" y="47" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="700" fill="#10b981">Policy-Safe Ad Feed</text>

    <!-- Clean Image Simulation Box -->
    <g transform="translate(40, 80)">
      <rect width="500" height="380" rx="16" fill="#f8fafc"/>
      
      <!-- Clean Product Silhouette -->
      <path d="M 120 280 C 140 230 200 180 270 190 C 330 200 370 170 410 210 C 420 230 420 280 390 290 Z" fill="#64748b" opacity="0.3"/>
      <ellipse cx="270" cy="240" rx="130" ry="60" fill="#cbd5e1"/>
      <text x="270" y="248" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="22" font-weight="700" fill="#475569">PRODUCT MASTER</text>

      <!-- Clean Badge Pill at top right -->
      <rect x="330" y="20" width="150" height="32" rx="16" fill="#dcfce7"/>
      <text x="405" y="42" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="13" font-weight="800" fill="#15803d">CLEAN AD FEED</text>
    </g>

    <!-- Bottom Status Note with Metafield Info -->
    <rect x="40" y="485" width="500" height="60" rx="12" fill="#022c22" stroke="#065f46"/>
    <circle cx="70" cy="515" r="8" fill="#10b981"/>
    <text x="92" y="521" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="15" font-weight="700" fill="#ecfdf5">
      Stored in Metafield: <tspan fill="#a7f3d0">safemedia.clean_ad_image_url</tspan>
    </text>
  </g>
</svg>
"""

def generate_banner_always_on_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#081018"/>
      <stop offset="50%" stop-color="#0b1e24"/>
      <stop offset="100%" stop-color="#071217"/>
    </linearGradient>
    <linearGradient id="stepGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#162533"/>
      <stop offset="100%" stop-color="#0e1720"/>
    </linearGradient>
    <linearGradient id="pillGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#008060"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>

  <rect width="1600" height="900" fill="url(#bgGrad)"/>
  <circle cx="400" cy="450" r="300" fill="#0284c7" opacity="0.1" filter="blur(80px)"/>
  <circle cx="1200" cy="450" r="300" fill="#10b981" opacity="0.1" filter="blur(80px)"/>

  <!-- Top Header Zone -->
  <g transform="translate(100, 75)">
    <rect width="250" height="36" rx="18" fill="url(#pillGrad)"/>
    <text x="125" y="24" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="800" letter-spacing="2" fill="#ffffff">ZERO-UI AUTOMATION</text>

    <text x="0" y="85" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="44" font-weight="800" fill="#ffffff" letter-spacing="-0.5">
      Set It &amp; Forget It. Always-On Ad Shield.
    </text>

    <text x="0" y="125" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="400" fill="#94a3b8">
      Zero manual work. Instant background processing triggered automatically by Shopify Webhooks.
    </text>
  </g>

  <!-- 3 Step Process Flow -->
  <!-- STEP 1 -->
  <g transform="translate(100, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#stepGrad)" stroke="#334155" stroke-width="2"/>
    <circle cx="64" cy="64" r="28" fill="#0284c7"/>
    <text x="64" y="72" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="800" fill="#ffffff">1</text>
    <text x="110" y="60" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="700" fill="#ffffff">Merchant Upload</text>
    <text x="110" y="82" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="500" fill="#94a3b8">Normal Shopify Admin Flow</text>

    <!-- Visual Container -->
    <g transform="translate(35, 120)">
      <rect width="360" height="280" rx="16" fill="#1e293b"/>
      <ellipse cx="180" cy="140" rx="90" ry="40" fill="#475569"/>
      <rect x="20" y="20" width="100" height="30" rx="6" fill="#ef4444"/>
      <text x="70" y="41" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="13" font-weight="800" fill="#ffffff">SALE -30%</text>
      <text x="180" y="240" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="14" font-weight="600" fill="#94a3b8">Product with promo badge</text>
    </g>

    <text x="40" y="440" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="16" font-weight="600" fill="#cbd5e1">Upload decorated images as usual.</text>
    <text x="40" y="470" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="400" fill="#94a3b8">
      No complex third-party editor required. Continue using your standard workflow.
    </text>
  </g>

  <!-- STEP 2 -->
  <g transform="translate(585, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#stepGrad)" stroke="#008060" stroke-width="2"/>
    <circle cx="64" cy="64" r="28" fill="#008060"/>
    <text x="64" y="72" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="800" fill="#ffffff">2</text>
    <text x="110" y="60" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="700" fill="#ffffff">Webhook Trigger</text>
    <text x="110" y="82" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="500" fill="#6ee7b7">Instant AI Processing</text>

    <g transform="translate(35, 120)">
      <rect width="360" height="280" rx="16" fill="#064e3b" stroke="#047857"/>
      <circle cx="180" cy="140" r="70" fill="none" stroke="#10b981" stroke-width="2" stroke-dasharray="8 6"/>
      <circle cx="180" cy="140" r="40" fill="none" stroke="#34d399" stroke-width="3"/>
      <circle cx="180" cy="140" r="16" fill="#10b981"/>
      <text x="180" y="240" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="14" font-weight="700" fill="#a7f3d0">products/update Webhook</text>
    </g>

    <text x="40" y="440" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="16" font-weight="600" fill="#cbd5e1">Automatic AI Inpainting.</text>
    <text x="40" y="470" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="400" fill="#94a3b8">
      Dedicated GPU removes badges and promotional overlays automatically in seconds.
    </text>
  </g>

  <!-- STEP 3 -->
  <g transform="translate(1070, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#stepGrad)" stroke="#10b981" stroke-width="2"/>
    <circle cx="64" cy="64" r="28" fill="#10b981"/>
    <text x="64" y="72" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="800" fill="#ffffff">3</text>
    <text x="110" y="60" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="700" fill="#ffffff">Feed Auto-Sync</text>
    <text x="110" y="82" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="500" fill="#a7f3d0">Google Shopping Ready</text>

    <g transform="translate(35, 120)">
      <rect width="360" height="280" rx="16" fill="#0f172a"/>
      <circle cx="180" cy="120" r="45" fill="#10b981"/>
      <path d="M 162 120 L 175 133 L 202 106" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="50" y="195" width="260" height="34" rx="8" fill="#1e293b"/>
      <text x="180" y="218" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
            font-size="13" font-weight="700" fill="#38bdf8">safemedia.clean_ad_image_url</text>
    </g>

    <text x="40" y="440" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="16" font-weight="600" fill="#cbd5e1">Clean Image Linked to Feed.</text>
    <text x="40" y="470" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="400" fill="#94a3b8">
      Designed for Google Merchant Center feed compliance. Zero storefront impact.
    </text>
  </g>
</svg>
"""

def generate_banner_one_click_rollback_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#09121a"/>
      <stop offset="50%" stop-color="#0f2622"/>
      <stop offset="100%" stop-color="#071413"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#162734"/>
      <stop offset="100%" stop-color="#0f1b24"/>
    </linearGradient>
    <linearGradient id="emeraldPill" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#059669"/>
      <stop offset="100%" stop-color="#10b981"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>

  <rect width="1600" height="900" fill="url(#bgGrad)"/>
  <circle cx="800" cy="500" r="350" fill="#10b981" opacity="0.1" filter="blur(80px)"/>

  <!-- Top Header Zone -->
  <g transform="translate(100, 75)">
    <rect width="270" height="36" rx="18" fill="url(#emeraldPill)"/>
    <text x="135" y="24" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="14" font-weight="800" letter-spacing="2" fill="#ffffff">STORE INTEGRITY FIRST</text>

    <text x="0" y="85" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="44" font-weight="800" fill="#ffffff" letter-spacing="-0.5">
      1-Click Rollback. Reliable Catalog Protection.
    </text>

    <text x="0" y="125" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
          font-size="20" font-weight="400" fill="#94a3b8">
      Point-in-time immutable cloud snapshots. Built for catalog safety.
    </text>
  </g>

  <!-- 3 Pillars of Safety -->
  <!-- CARD 1 -->
  <g transform="translate(100, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#cardGrad)" stroke="#334155" stroke-width="2"/>
    <rect x="35" y="40" width="60" height="60" rx="16" fill="#008060"/>
    <text x="65" y="78" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="28">📸</text>
    <text x="115" y="66" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="22" font-weight="700" fill="#ffffff">Immutable Cloud</text>
    <text x="115" y="92" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="15" font-weight="500" fill="#6ee7b7">Snapshot Backup</text>

    <g transform="translate(35, 130)">
      <rect width="360" height="240" rx="16" fill="#0b1720"/>
      <text x="24" y="44" font-family="monospace" font-size="13" fill="#64748b">// Cloud Snapshot Payload</text>
      <text x="24" y="74" font-family="monospace" font-size="13" fill="#38bdf8">"timestamp": <tspan fill="#f8fafc">"2026-10-19T07:00Z"</tspan></text>
      <text x="24" y="104" font-family="monospace" font-size="13" fill="#38bdf8">"totalMedia": <tspan fill="#f59e0b">24</tspan></text>
      <text x="24" y="134" font-family="monospace" font-size="13" fill="#38bdf8">"variantsLocked": <tspan fill="#10b981">true</tspan></text>
      <text x="24" y="164" font-family="monospace" font-size="13" fill="#38bdf8">"status": <tspan fill="#a7f3d0">"VERIFIED_SECURE"</tspan></text>
    </g>

    <text x="40" y="415" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="17" font-weight="700" fill="#f8fafc">Pre-Change Snapshot</text>
    <text x="40" y="445" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="14" font-weight="400" fill="#94a3b8">
      Every image URL and metadata state is preserved before any modifications occur.
    </text>
  </g>

  <!-- CARD 2 -->
  <g transform="translate(585, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#cardGrad)" stroke="#10b981" stroke-width="2"/>
    <rect x="35" y="40" width="60" height="60" rx="16" fill="#0284c7"/>
    <text x="65" y="78" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="28">🔗</text>
    <text x="115" y="66" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="22" font-weight="700" fill="#ffffff">Variant Mapping</text>
    <text x="115" y="92" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="15" font-weight="500" fill="#38bdf8">Locked Media IDs</text>

    <g transform="translate(35, 130)">
      <rect width="360" height="240" rx="16" fill="#0b1720"/>
      <g transform="translate(30, 30)">
        <rect width="300" height="46" rx="8" fill="#1e293b"/>
        <text x="20" y="28" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="13" font-weight="600" fill="#f8fafc">Size: S (Color: Black)</text>
        <circle cx="270" cy="23" r="8" fill="#10b981"/>
      </g>
      <g transform="translate(30, 90)">
        <rect width="300" height="46" rx="8" fill="#1e293b"/>
        <text x="20" y="28" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="13" font-weight="600" fill="#f8fafc">Size: M (Color: Red)</text>
        <circle cx="270" cy="23" r="8" fill="#10b981"/>
      </g>
      <g transform="translate(30, 150)">
        <rect width="300" height="46" rx="8" fill="#1e293b"/>
        <text x="20" y="28" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="13" font-weight="600" fill="#f8fafc">Size: L (Color: White)</text>
        <circle cx="270" cy="23" r="8" fill="#10b981"/>
      </g>
    </g>

    <text x="40" y="415" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="17" font-weight="700" fill="#f8fafc">No Disconnected Variants</text>
    <text x="40" y="445" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="14" font-weight="400" fill="#94a3b8">
      Shopify MediaImage IDs are locked before batch execution. Zero broken customer selections.
    </text>
  </g>

  <!-- CARD 3 -->
  <g transform="translate(1070, 245)" filter="url(#shadow)">
    <rect width="430" height="580" rx="24" fill="url(#cardGrad)" stroke="#f59e0b" stroke-width="2"/>
    <rect x="35" y="40" width="60" height="60" rx="16" fill="#d97706"/>
    <text x="65" y="78" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="28">⏪</text>
    <text x="115" y="66" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="22" font-weight="700" fill="#ffffff">1-Click Revert</text>
    <text x="115" y="92" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="15" font-weight="500" fill="#fbbf24">Point-in-Time Restore</text>

    <g transform="translate(35, 130)">
      <rect width="360" height="240" rx="16" fill="#0b1720"/>
      <g transform="translate(50, 80)">
        <rect width="260" height="56" rx="12" fill="#d97706"/>
        <text x="130" y="35" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="16" font-weight="800" fill="#ffffff">REVERT TO SNAPSHOT</text>
      </g>
      <text x="180" y="170" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="13" font-weight="600" fill="#6ee7b7">Restores original URLs &amp; Metafields</text>
    </g>

    <text x="40" y="415" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="17" font-weight="700" fill="#f8fafc">Built for Peace of Mind</text>
    <text x="40" y="445" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="14" font-weight="400" fill="#94a3b8">
      If you ever want to reset or undo changes, 1 click restores your exact original catalog.
    </text>
  </g>
</svg>
"""

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    assets = [
        ("app_icon_1200x1200", generate_app_icon_svg(), 1200, 1200),
        ("banner_dual_feed_1600x900", generate_banner_dual_feed_svg(), 1600, 900),
        ("banner_always_on_1600x900", generate_banner_always_on_svg(), 1600, 900),
        ("banner_one_click_rollback_1600x900", generate_banner_one_click_rollback_svg(), 1600, 900),
    ]

    for name, svg_content, width, height in assets:
        svg_path = os.path.join(OUTPUT_DIR, f"{name}.svg")
        png_path = os.path.join(OUTPUT_DIR, f"{name}.png")

        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"Generated SVG: {svg_path}")

        cmd = ["sips", "-s", "format", "png", svg_path, "--out", png_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            try:
                from PIL import Image
                im = Image.open(png_path)
                im.save(png_path, optimize=True, compress_level=9)
            except Exception as e:
                pass
            print(f"Rendered PNG ({width}x{height}): {png_path} ({os.path.getsize(png_path)/1024:.1f} KB)")
        else:
            print(f"Error rendering PNG for {name}: {res.stderr}")

if __name__ == "__main__":
    main()
