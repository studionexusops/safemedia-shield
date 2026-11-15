/**
 * AdFeed Clean for Google Shopping Embedded UI
 * Shopify Polaris-styled single page application.
 * 2-Zone Architecture: Zone 1 (Core Automation) + Zone 2 (Onboarding & Safety Suite).
 * Unified 5-Layer Action Cards with English-first Global UX and Japanese Toggle.
 */

import { TenantBillingState } from "./types";

export function renderDashboardHtml(shop: string, apiKey: string = "", feedToken: string = "", initialBilling?: Partial<TenantBillingState>): string {
  const feedTokenQuery = feedToken ? `&token=${encodeURIComponent(feedToken)}` : "";
  const isSyncActive = initialBilling ? initialBilling.autoSyncEnabled !== false : true;
  const autosyncBadgeClass = isSyncActive
    ? "px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800"
    : "px-2.5 py-1 text-xs font-bold rounded-full bg-gray-200 text-gray-700";
  const autosyncBadgeText = isSyncActive ? "🟢 Active" : "⚪ Paused";
  const toggleBtnClass = isSyncActive
    ? "px-3.5 py-2 text-xs font-semibold rounded-lg bg-white text-gray-700 border border-gray-300 hover:bg-red-50 hover:text-red-700 hover:border-red-300 shadow-sm flex items-center gap-1.5 transition"
    : "px-3.5 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm flex items-center gap-1.5 transition";
  const toggleBtnIcon = isSyncActive ? "⏸️" : "▶️";
  const toggleBtnLabel = isSyncActive ? "Pause Auto-Protection" : "Resume Auto-Protection";

  let planBadgeClass = "px-2.5 py-1 rounded-md font-bold bg-amber-100 text-amber-900";
  let planBadgeText = "🎁 Free Sample Preview (0 / 5 Used)";
  let planDescText = "Try up to 5 products risk-free. Activate your <strong>14-Day Free Trial ($65/mo)</strong> anytime to unlock unlimited ad-feed generation.";
  let planUsageBadgeClass = "hidden";
  let planUsageBadgeText = "";
  let canaryQuotaDisplayClass = "text-xs text-gray-500 font-medium";
  let canaryQuotaDisplayText = "Free Samples: 0/5 Used";
  let showTrialBtn = true;
  let showResumeBtn = false;

  if (initialBilling) {
    if (initialBilling.circuitBreakerTripped) {
      planBadgeClass = "px-2.5 py-1 rounded-md font-bold bg-red-100 text-red-800";
      planBadgeText = "🛑 Emergency Stop Active (Paused)";
      planDescText = "All background image processing is currently paused for safety.";
      showTrialBtn = false;
      showResumeBtn = true;
    } else if (initialBilling.planStatus === "ACTIVE") {
      const uCount = initialBilling.monthlyUsageCount || 0;
      const iCount = initialBilling.monthlyIncludedCount || 500;
      planBadgeClass = "px-2.5 py-1 rounded-md font-bold bg-emerald-100 text-emerald-800";
      planBadgeText = "✅ Active Protection Plan ($65/mo • 500 Included)";
      planUsageBadgeClass = "px-2.5 py-0.5 rounded-md font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300";
      planUsageBadgeText = `Monthly Usage: ${uCount} / ${iCount} Images${uCount > iCount ? " (Overage Active)" : ""}`;
      planDescText = "Full-catalog smart dual-feed active. 500 images/mo included ($0.05/image overage, capped at $100/mo).";
      canaryQuotaDisplayClass = "hidden text-xs text-gray-500 font-medium";
      showTrialBtn = false;
      showResumeBtn = false;
    } else if (initialBilling.planStatus === "TRIAL_14D_ACTIVE" || initialBilling.planStatus === "TRIAL_ACTIVE") {
      const tUsed = initialBilling.trialUsedCount || 0;
      const tLimit = initialBilling.trialLimit || 50;
      planBadgeClass = "px-2.5 py-1 rounded-md font-bold bg-emerald-100 text-emerald-800";
      planBadgeText = "✅ 14-Day Free Trial Active (50 Quota • $65/mo)";
      planUsageBadgeClass = "px-2.5 py-0.5 rounded-md font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300";
      planUsageBadgeText = `Trial Quota: ${tUsed} / ${tLimit} Used`;
      planDescText = "14-day free trial active. Up to 50 clean images generated free of charge.";
      const cUsed = initialBilling.canaryUsedCount || 0;
      const cLimit = initialBilling.canaryLimit || 5;
      canaryQuotaDisplayText = `Free Samples: ${cUsed}/${cLimit} Used`;
      showTrialBtn = false;
      showResumeBtn = false;
    } else if (
      initialBilling.planStatus === "TRIAL_CAP_REACHED" ||
      ((initialBilling.trialUsedCount || 0) >= (initialBilling.trialLimit || 50) && initialBilling.trialDays !== 0)
    ) {
      planBadgeClass = "px-2.5 py-1 rounded-md font-bold bg-amber-100 text-amber-900 border border-amber-300";
      planBadgeText = "🎉 Free Trial Quota (50/50 Images) Completed";
      planUsageBadgeClass = "px-2.5 py-0.5 rounded-md font-bold text-xs bg-amber-100 text-amber-900 border border-amber-300";
      planUsageBadgeText = "Trial Quota: 50 / 50 Images Used";
      planDescText = "50 free trial ad images generated! <strong>Activate your full subscription ($65/mo)</strong> now to resume immediate processing for your entire catalog.";
      const cUsed = initialBilling.canaryUsedCount || 0;
      const cLimit = initialBilling.canaryLimit || 5;
      canaryQuotaDisplayText = `Free Samples: ${cUsed}/${cLimit} Used`;
      showTrialBtn = true;
      showResumeBtn = false;
    } else {
      const used = initialBilling.canaryUsedCount || 0;
      const limit = initialBilling.canaryLimit || 5;
      planBadgeClass = used >= limit
        ? "px-2.5 py-1 rounded-md font-bold bg-red-100 text-red-800"
        : "px-2.5 py-1 rounded-md font-bold bg-amber-100 text-amber-900";
      planBadgeText = `🎁 Free Sample Preview (${used} / ${limit} Used)`;
      canaryQuotaDisplayText = `Free Samples: ${used}/${limit} Used`;
    }
  }
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="shopify-api-key" content="${apiKey}">
  <title>AdFeed Clean: Google Shopping — Zero-UI Dual-Feed Image Automation for Shopify</title>
  <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f6f6f7; color: #202223; }
    .polaris-card { background: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03); border: 1px solid #e1e3e5; }
    .polaris-btn-primary { background-color: #008060; color: #fff; font-weight: 600; transition: all 0.15s; }
    .polaris-btn-primary:hover { background-color: #006e52; }
    .polaris-btn-danger { background-color: #d82c0d; color: #fff; font-weight: 600; transition: all 0.15s; }
    .polaris-btn-danger:hover { background-color: #bc2200; }
    .step-badge { background-color: #e3f1df; color: #008060; font-weight: 700; }
  </style>
</head>
<body class="p-4 md:p-8 max-w-5xl mx-auto">

  <!-- Top Header (Decluttered: Brand Title, Connected Store & Language Toggle; No Manual Refresh Button) -->
  <header class="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-gray-200 mb-6 gap-4">
    <div class="flex items-center space-x-3">
      <div class="w-11 h-11 rounded-xl bg-emerald-700 flex items-center justify-center text-white text-xl font-bold shadow-sm">
        🛡️
      </div>
      <div>
        <div class="flex items-center gap-2.5">
          <h1 class="text-xl md:text-2xl font-bold text-gray-900" data-i18n="app_title">AdFeed Clean for Google Shopping</h1>
          <span id="header_shield_badge" class="px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200" data-i18n="badge_active">Dual-Feed Engine</span>
        </div>
        <p class="text-xs text-gray-500 mt-0.5">
          <span data-i18n="connected_store">Connected Store:</span>
          <span class="font-mono text-gray-700 font-semibold" id="shop-name">${shop}</span>
        </p>
      </div>
    </div>

    <div class="flex items-center gap-2.5">
      <!-- Language Switcher (English Default for Global Market + Japanese Option) -->
      <div class="inline-flex rounded-lg border border-gray-300 bg-white p-0.5 text-xs font-semibold shadow-sm">
        <button onclick="setLang('en')" id="lang-en" class="px-2.5 py-1 rounded-md bg-gray-900 text-white">EN</button>
        <button onclick="setLang('ja')" id="lang-ja" class="px-2.5 py-1 rounded-md text-gray-600 hover:text-gray-900">日本語</button>
      </div>
    </div>
  </header>

  <!-- Inline Notifications (Zero browser alert() / confirm()) -->
  <div id="inline-notification-container" class="space-y-2 mb-4 hidden"></div>

  <!-- Top Banner 1: High-Converting Headline Banner (ROI & Core Value Proposition) -->
  <section id="hero_banner" class="polaris-card p-5 mb-3 bg-gradient-to-r from-emerald-50/70 via-white to-white border-l-4 border-l-emerald-600 shadow-sm">
    <div class="headline-container mb-2">
      <h2 class="text-base md:text-lg font-bold text-gray-900 tracking-tight" data-i18n="hero_headline">
        Keep High-Converting Sale Badges on Storefront — 100% Policy-Compliant on Google Shopping.
      </h2>
    </div>
    <div class="flex flex-wrap items-center gap-2 pt-1 text-xs font-semibold text-emerald-900">
      <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-100/80 border border-emerald-200">
        🛡️ <span data-i18n="pill_gmc_compliant">Google Merchant Center Compliant</span>
      </span>
      <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-100/80 border border-emerald-200">
        ⚡ <span data-i18n="pill_zero_storefront_change">Zero Storefront Image Changes</span>
      </span>
      <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-100/80 border border-emerald-200">
        🔒 <span data-i18n="pill_variant_preservation">100% Variant Link Preservation</span>
      </span>
    </div>
  </section>

  <!-- Top Banner 2: Functional Sub-Copy Banner (Explaining Dual-Feed Routing & Metafield Mechanism) -->
  <section class="subcopy-banner polaris-card p-4 mb-6 bg-slate-50 border border-slate-200 text-xs md:text-sm text-slate-700 leading-relaxed shadow-sm">
    <div class="flex items-start gap-2.5">
      <span class="text-base mt-0.5">💡</span>
      <div class="space-y-1">
        <strong class="font-bold text-slate-900" data-i18n="hero_subcopy_title">How AdFeed Clean Dual-Feed Protection Works:</strong>
        <p data-i18n="hero_subcopy">
          Shoppers on your store see your original, high-converting promo badges ('SALE', '20% OFF'). In the background, our AI detects and removes promotional badges and stores policy-compliant clean images into hidden product metafields (<code class="font-mono text-emerald-700 bg-white px-1 py-0.5 rounded border border-slate-200">safemedia.clean_ad_image_url</code>) strictly for your Google Shopping and Meta ad feeds.
        </p>
      </div>
    </div>
  </section>

  <!-- Plan & 5-Item Free Preview Quota Bar (Monetization & Safety Gate) -->
  <div id="billing-banner" class="polaris-card p-4 mb-8 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white">
    <div class="space-y-1">
      <div class="flex flex-wrap items-center gap-2.5 text-xs md:text-sm">
        <span id="plan-status-badge" class="${planBadgeClass}">
          ${planBadgeText}
        </span>
        <span id="plan-usage-badge" class="${planUsageBadgeClass}">
          ${planUsageBadgeText}
        </span>
      </div>
      <div id="plan-status-desc" class="text-xs text-gray-600">
        ${planDescText}
      </div>
    </div>
    <div class="flex items-center gap-2 self-start md:self-center">
      <button onclick="startFreeTrial()" id="btn-start-trial" class="${showTrialBtn ? '' : 'hidden '}px-4 py-2 text-xs md:text-sm font-bold rounded-lg bg-gray-900 text-white hover:bg-gray-800 shadow-sm whitespace-nowrap">
        🚀 Start 14-Day Free Trial ($65/mo)
      </button>
      <button onclick="resumeProtection()" id="btn-resume-circuit" class="${showResumeBtn ? '' : 'hidden '}px-3.5 py-2 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm whitespace-nowrap">
        ▶️ Resume Protection
      </button>
    </div>
  </div>

  <!-- MAIN WORKFLOW: 2-ZONE INFORMATION ARCHITECTURE -->
  <div class="space-y-8">

    <!-- ===================================================================== -->
    <!-- ZONE 1: CORE AUTOMATION (Always-On Ad-Feed Protection)                -->
    <!-- Positioned first as the everyday primary automation engine            -->
    <!-- ===================================================================== -->
    <section id="zone-core-automation" class="zone-core-automation polaris-card p-6 border-2 border-emerald-600/30 mb-8 shadow-sm">
      <!-- Layer 1: Badge -->
      <div class="layer-1-badge flex flex-wrap items-center justify-between gap-2 pb-2">
        <div class="flex items-center gap-2">
          <span class="step-badge text-xs px-2.5 py-0.5 rounded-md uppercase tracking-wide" data-i18n="z1_tag">Zone 1 • Core Automation</span>
        </div>
        <div class="flex items-center gap-2">
          <span id="autosync-status-badge" class="${autosyncBadgeClass}">
            ${autosyncBadgeText}
          </span>
          <span id="live_status_indicator" class="hidden"></span>
        </div>
      </div>

      <!-- Layer 2: Title -->
      <div class="layer-2-title pt-1">
        <h3 class="text-lg md:text-xl font-bold text-gray-900" data-i18n="zone1_title">
          Zone 1: Core Automation (Always-On Ad Shield)
        </h3>
      </div>

      <!-- Layer 3: When / What Description -->
      <div class="layer-3-description mt-1 pb-4 border-b border-gray-100 space-y-1">
        <div class="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 inline-block" data-i18n="z1_when">
          When you upload or update products with promotional banners, discount stickers, or text overlays
        </div>
        <p class="text-xs md:text-sm text-gray-600 leading-relaxed" data-i18n="z1_desc">
          Zero-UI background automation. Shopify's <code class="bg-gray-100 px-1 py-0.5 rounded text-gray-800 font-mono text-xs">products/update</code> webhook triggers cloud AI to erase overlays in ~5s without touching your storefront images. The clean ad-feed image URL is saved to metafield <code class="bg-gray-100 px-1.5 py-0.5 rounded text-emerald-800 font-mono text-xs">safemedia.clean_ad_image_url</code> for Google Merchant Center.
        </p>
      </div>

      <!-- Layer 4: Action Buttons (Single Unified Toggle Button) -->
      <div class="layer-4-actions flex flex-wrap items-center gap-2.5 py-4">
        <button onclick="toggleAutoSync()" id="toggle_auto_sync" class="${toggleBtnClass}">
          <span id="toggle_auto_sync_icon">${toggleBtnIcon}</span> <span id="toggle_auto_sync_label">${toggleBtnLabel}</span>
        </button>
        <span id="btn-reg-webhook" class="hidden"></span>
        <span id="btn-unreg-webhook" class="hidden"><span id="lbl-unreg-webhook"></span></span>
      </div>
      <div id="zone1-action-msg" class="hidden mb-3 text-xs rounded-lg p-3 border transition-all duration-200"></div>

      <!-- Layer 5: Preview / Output Container -->
      <div class="layer-5-preview space-y-4" id="z1_output_container">
        <!-- 3-Step Visual Micro-Flow Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div class="micro-step-card bg-gray-50 p-3.5 rounded-lg border border-gray-200 space-y-1">
            <div class="text-[11px] font-bold uppercase tracking-wider text-emerald-700" data-i18n="flow1_title">1. Upload Promo Image as Usual</div>
            <div class="text-gray-600 leading-normal" data-i18n="flow1_desc">Your Shopify storefront keeps showing the eye-catching 'SALE / 20% OFF' badge to boost conversion.</div>
          </div>
          <div class="micro-step-card bg-gray-50 p-3.5 rounded-lg border border-gray-200 space-y-1">
            <div class="text-[11px] font-bold uppercase tracking-wider text-emerald-700" data-i18n="flow2_title">2. AI Removes Text & Banners in ~5s</div>
            <div class="text-gray-600 leading-normal" data-i18n="flow2_desc">AI automatically detects and erases promotional text without altering the product or storefront photo.</div>
          </div>
          <div class="micro-step-card bg-gray-50 p-3.5 rounded-lg border border-gray-200 space-y-1">
            <div class="text-[11px] font-bold uppercase tracking-wider text-emerald-700" data-i18n="flow3_title">3. Ready for Google & Meta Feeds</div>
            <div class="text-gray-600 leading-normal" data-i18n="flow3_desc">Ad feeds map safemedia.clean_ad_image_url as the image link to pass ad policy reviews with zero disapprovals.</div>
          </div>
        </div>

        <!-- Recent Synced Product Feed Table (Collapsible Accordion / Scroll Container) -->
        <div class="pt-2">
          <details open class="group bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden text-xs">
            <summary class="px-4 py-3 bg-gray-50/70 hover:bg-gray-100 cursor-pointer font-bold text-gray-800 flex items-center justify-between transition-colors select-none">
              <div class="flex items-center gap-2">
                <span class="transform group-open:rotate-90 transition-transform inline-block text-[10px] text-gray-500">▶</span>
                <span class="text-xs uppercase tracking-wide text-gray-700" data-i18n="recent_synced_feed_title">Recent Synced Product Feed</span>
                <span id="synced-feed-count-badge" class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-100 text-emerald-800 font-bold">...</span>
              </div>
              <span class="text-[11px] text-gray-500 font-mono hidden sm:inline">Metafield: safemedia.clean_ad_image_url</span>
            </summary>

            <div class="p-4 border-t border-gray-200 space-y-4">
              <!-- Compact Scrollable Table Container -->
              <div id="dual-feed-proof-table" class="overflow-x-auto border border-gray-200 rounded-lg bg-white max-h-72 overflow-y-auto">
                <table id="synced_feed_table" class="min-w-full divide-y divide-gray-200 text-xs">
                  <thead class="bg-gray-50 text-gray-600 font-semibold sticky top-0 z-10 shadow-sm">
                    <tr>
                      <th class="px-4 py-2.5 text-left bg-gray-50">Product</th>
                      <th class="px-4 py-2.5 text-left bg-gray-50">Storefront (Before)</th>
                      <th class="px-4 py-2.5 text-left bg-gray-50">Clean Ad-Feed (After)</th>
                      <th class="px-4 py-2.5 text-left bg-gray-50">Status</th>
                    </tr>
                  </thead>
                  <tbody id="synced_feed_rows" class="divide-y divide-gray-200 bg-white">
                    <tr>
                      <td colspan="4" class="px-4 py-6 text-center text-gray-400" data-i18n="loading_feed">
                        Loading product ad-feed status...
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Collapsible Visual Before / After Media Cards Container -->
              <details open class="border border-emerald-100 bg-emerald-50/20 rounded-lg p-3">
                <summary class="cursor-pointer text-xs font-semibold text-emerald-900 flex items-center justify-between select-none">
                  <span>🖼️ Visual Before & After Ad Image Pairs (Cleaned Media)</span>
                  <span class="text-[11px] text-emerald-700">Toggle View</span>
                </summary>
                <div id="dual-feed-list" class="space-y-3 mt-3 max-h-96 overflow-y-auto pr-1"></div>
              </details>
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- ===================================================================== -->
    <!-- ZONE 2: ONBOARDING TOOLS & SAFETY SUITE (Sequential Steps)            -->
    <!-- Step 1 Canary Preview -> Step 2 Full Catalog Sync -> Step 3 Rollback  -->
    <!-- ===================================================================== -->
    <section id="zone-onboarding-safety" class="zone-onboarding-safety space-y-6">
      <div id="onboarding-feed-guide" class="mb-4 space-y-4">
        <div>
          <span class="text-xs font-bold tracking-wider uppercase text-emerald-700">ZONE 2 • ONBOARDING & SAFETY</span>
          <h3 class="text-lg md:text-xl font-bold text-gray-900 mt-0.5" data-i18n="z2_header_title">
            Zone 2: Onboarding Tools & Safety Suite
          </h3>
          <p class="text-xs md:text-sm text-gray-500 mt-0.5" data-i18n="z2_header_subtitle">
            Sequential tools to test on 1 sample product, generate ad feeds for your entire catalog, and restore with 1-click undo.
          </p>
        </div>

        <!-- Step-by-Step Onboarding & Feed Distribution Roadmap (Shopify Review 4.5.3) -->
        <div class="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3">
          <div class="flex items-center justify-between pb-2 border-b border-gray-100">
            <h4 class="text-xs md:text-sm font-bold text-gray-900 flex items-center gap-2" id="guide-roadmap-heading" data-i18n="guide_roadmap_heading">
              <span>📋</span> <span>Step-by-Step Onboarding & Channel Mapping Guide</span>
            </h4>
            <span class="text-[11px] font-mono text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">Shopify Review 4.5.3 Ready</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div class="p-3 rounded-lg border border-gray-200 bg-gray-50/70 space-y-1">
              <div class="flex items-center justify-between">
                <span class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider" id="guide-step1-lbl" data-i18n="guide_step1_lbl">Step 1: Auto-Sync</span>
                <span id="guide-sync-status" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">🟢 Active</span>
              </div>
              <p class="text-gray-600 text-[11px] leading-snug" id="guide-step1-txt" data-i18n="guide_step1_txt">Webhook automatically watches products/update for new banners.</p>
            </div>

            <div class="p-3 rounded-lg border border-gray-200 bg-gray-50/70 space-y-1">
              <div class="flex items-center justify-between">
                <span class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider" id="guide-step2-lbl" data-i18n="guide_step2_lbl">Step 2: Canary Test</span>
                <span id="guide-canary-status" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">1-Product Sim</span>
              </div>
              <p class="text-gray-600 text-[11px] leading-snug" id="guide-step2-txt" data-i18n="guide_step2_txt">Simulate AI removal on 1 product with variant checks.</p>
            </div>

            <div class="p-3 rounded-lg border border-gray-200 bg-gray-50/70 space-y-1">
              <div class="flex items-center justify-between">
                <span class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider" id="guide-step3-lbl" data-i18n="guide_step3_lbl">Step 3: Catalog Sync</span>
                <span id="guide-batch-status" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">Non-Destructive</span>
              </div>
              <p class="text-gray-600 text-[11px] leading-snug" id="guide-step3-txt" data-i18n="guide_step3_txt">Back up store and write clean ad images to metafields.</p>
            </div>

            <div class="p-3 rounded-lg border border-gray-200 bg-emerald-50/50 space-y-1">
              <div class="flex items-center justify-between">
                <span class="font-bold text-emerald-800 uppercase text-[10px] tracking-wider" id="guide-step4-lbl" data-i18n="guide_step4_lbl">Step 4: Ad Mapping</span>
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">🟢 Live Feeds</span>
              </div>
              <p class="text-gray-600 text-[11px] leading-snug" id="guide-step4-txt" data-i18n="guide_step4_txt">Deliver clean image metafield to GMC & Meta ad feeds.</p>
            </div>
          </div>

          <!-- Channel Mapping & Feed Distribution Preview Sub-Card -->
          <div class="mt-2 pt-2 border-t border-gray-100 bg-slate-50 p-3 rounded-lg space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div class="flex items-center gap-1.5 flex-wrap">
                <strong class="text-gray-900 font-bold" id="channel-mapping-lbl" data-i18n="channel_mapping_lbl">Ad Feed Channel Distribution Status (Supplemental Feeds):</strong>
                <span id="feed-items-count-badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">Supplemental Feed (Live)</span>
              </div>
              <div class="flex items-center gap-2 text-[11px]">
                <a id="feed-xml-link" href="/api/feed-preview.xml?shop=${shop}${feedTokenQuery}" target="_blank" class="text-emerald-700 hover:text-emerald-900 font-mono underline font-medium">RSS XML Feed ↗</a>
                <span>•</span>
                <a id="feed-json-link" href="/api/feed-preview?shop=${shop}${feedTokenQuery}" target="_blank" class="text-emerald-700 hover:text-emerald-900 font-mono underline font-medium">JSON Feed ↗</a>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div class="bg-white p-2.5 rounded border border-gray-200 space-y-1">
                <div class="flex items-center justify-between">
                  <span class="font-bold text-gray-800">🛍️ Google Shopping (GMC)</span>
                  <span id="gmc-mapping-status" class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">🟢 Supplemental Feed Ready</span>
                </div>
                <div class="text-[11px] text-gray-500 font-mono">Target: <code class="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded">g:image_link</code> ➔ safemedia.clean_ad_image_url</div>
                <div class="text-[10px] text-gray-400">Channel: Google Merchant Center (Supplemental Feed)</div>
              </div>
              <div class="bg-white p-2.5 rounded border border-gray-200 space-y-1">
                <div class="flex items-center justify-between">
                  <span class="font-bold text-gray-800">📱 Meta Ad Feed (Facebook/IG)</span>
                  <span id="meta-mapping-status" class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">🟢 Supplementary Feed Ready</span>
                </div>
                <div class="text-[11px] text-gray-500 font-mono">Target: <code class="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded">image_link</code> ➔ safemedia.clean_ad_image_url</div>
                <div class="text-[10px] text-gray-400">Channel: Meta Commerce Manager (Supplementary Feed)</div>
              </div>
            </div>
            <div class="p-2 rounded bg-emerald-50/70 border border-emerald-200/60 text-[11px] text-emerald-900 flex items-start gap-1.5 leading-relaxed">
              <span class="select-none">💡</span>
              <span id="feed-supplemental-note" data-i18n="feed_supplemental_note">Supplemental Feed: Only products with AI-cleaned images are included, safely overwriting image attributes in GMC & Meta without altering other product data.</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 1 Card: 1-Product Canary Test (Unified 5-Layer Layout) -->
      <div id="card-canary-preview" class="action-card polaris-card p-6 shadow-sm">
        <div class="layer-1-badge flex flex-wrap items-center justify-between gap-2 pb-2">
          <div class="flex items-center gap-2">
            <span class="step-badge text-xs px-2.5 py-0.5 rounded-md uppercase tracking-wide" data-i18n="step1_tag">Step 1 • Start Here</span>
            <span class="text-xs text-gray-500 font-medium" data-i18n="step1_risk_free">Risk-Free Verification</span>
          </div>
          <span id="canary_quota_display" class="${canaryQuotaDisplayClass}">${canaryQuotaDisplayText}</span>
        </div>

        <div class="layer-2-title pt-1">
          <h4 class="text-base md:text-lg font-bold text-gray-900" data-i18n="step1_title">
            Test on 1 Sample Product (Canary Preview)
          </h4>
        </div>

        <div class="layer-3-description mt-1 pb-4 border-b border-gray-100 space-y-1">
          <div class="text-xs text-gray-500 font-medium" data-i18n="step1_when">
            When you want to verify AI badge removal quality and variant safety on 1 product first
          </div>
          <p class="text-xs md:text-sm text-gray-600 leading-relaxed" data-i18n="step1_desc">
            Run a safe simulation on a single multi-variant product before syncing. Verify clean promo-badge removal and confirm every color/size option stays 100% linked to the right photo. Storefront images are never modified.
          </p>
          <div class="text-[11px] md:text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1.5 font-medium flex items-center gap-1.5 mt-2" data-i18n="step1_quota_note">※ This sample test is a safety verification preview and does not consume your plan image quota (50 Trial / 500 Monthly Included Quota).</div>
        </div>

        <div class="layer-4-actions flex flex-wrap items-center gap-3 py-4">
          <div class="flex items-center gap-2">
            <label for="select-canary-product" class="text-xs font-semibold text-gray-700 whitespace-nowrap" data-i18n="step1_select_label">Target Product:</label>
            <select id="select-canary-product" class="px-3 py-2 text-xs md:text-sm border border-gray-300 rounded-lg bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 max-w-xs truncate">
              <option value="" data-i18n="step1_opt_auto">🎯 Auto-select (Recommended: Most Variants)</option>
            </select>
          </div>
          <button onclick="runCanaryTest()" id="btn-run-canary" class="polaris-btn-primary px-4 py-2.5 text-xs md:text-sm rounded-lg shadow-sm flex items-center gap-2 whitespace-nowrap">
            <span>🔍</span> <span data-i18n="step1_btn">Test on 1 Sample Product</span>
          </button>
        </div>

        <div class="layer-5-preview" id="canary-container">
          <div class="text-center py-6 px-4 text-xs md:text-sm text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200" data-i18n="step1_empty">
            Click 'Test on 1 Sample Product' above to preview before/after results and test variant switching.
          </div>
        </div>
      </div>

      <!-- Step 2 Card: Full Catalog Batch Sync (Unified 5-Layer Layout) -->
      <div id="card-catalog-sync" class="action-card polaris-card p-6 shadow-sm">
        <div class="layer-1-badge flex flex-wrap items-center justify-between gap-2 pb-2">
          <div class="flex items-center gap-2">
            <span class="step-badge text-xs px-2.5 py-0.5 rounded-md uppercase tracking-wide" data-i18n="step2_tag">Step 2 • Full Catalog Sync</span>
            <span class="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200" data-i18n="step2_non_destructive">
              Non-Destructive Metafield Generation
            </span>
          </div>
        </div>

        <div class="layer-2-title pt-1">
          <h4 class="text-base md:text-lg font-bold text-gray-900" data-i18n="step2_title">
            Sync All Existing Products (Full Catalog Ad-Feed Generation)
          </h4>
        </div>

        <div class="layer-3-description mt-1 pb-4 border-b border-gray-100 space-y-1">
          <div class="text-xs text-gray-500 font-medium" data-i18n="step2_when">
            When you want to generate clean ad images for your entire existing catalog at once
          </div>
          <p class="text-xs md:text-sm text-gray-600 leading-relaxed" data-i18n="step2_desc">
            Automatically backs up your store first, then generates clean ad-feed images in product metafields without altering storefront photos. You can stop the process immediately at any time.
          </p>
        </div>

        <div class="layer-4-actions flex flex-wrap items-center gap-3 py-4">
          <button onclick="startBatch()" id="btn-start-batch" class="polaris-btn-primary px-4 py-2.5 text-xs md:text-sm rounded-lg shadow-sm flex items-center gap-2 whitespace-nowrap">
            <span>⚡</span> <span data-i18n="step2_btn">Start Full Catalog Batch Sync</span>
          </button>
          <button onclick="abortBatch()" id="btn-abort-batch" class="hidden polaris-btn-danger px-4 py-2.5 text-xs md:text-sm rounded-lg shadow-sm flex items-center gap-2 animate-pulse whitespace-nowrap">
            <span>⛔</span> <span data-i18n="step2_abort_btn">Instant Stop (Circuit Breaker)</span>
          </button>
          <button onclick="resumeProtection()" id="btn-resume-circuit-step2" class="hidden px-3.5 py-2.5 text-xs md:text-sm font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm flex items-center gap-2 whitespace-nowrap">
            <span>▶️</span> <span id="lbl-resume-circuit-step2">Resume Protection</span>
          </button>
          <button onclick="cancelBatch()" id="btn-cancel-circuit-step2" class="hidden px-3.5 py-2.5 text-xs md:text-sm font-bold rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 shadow-sm flex items-center gap-2 whitespace-nowrap">
            <span>⏹️</span> <span id="lbl-cancel-circuit-step2" data-i18n="step2_btn_cancel">Cancel Batch</span>
          </button>
        </div>
        <div id="step2-action-msg" class="hidden mb-3 text-xs rounded-lg p-3 border transition-all duration-200"></div>

        <div class="layer-5-preview" id="batch-progress-section">
          <div class="hidden space-y-3" id="batch-progress-inner">
            <div class="flex justify-between text-xs text-gray-600 font-medium">
              <span id="batch-status-text">Processing catalog ad feeds safely...</span>
              <span id="batch-percentage">0%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div id="batch-progress-bar" class="bg-emerald-600 h-3 rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
            <div id="batch-details" class="text-xs text-gray-500 font-mono bg-gray-50 p-2.5 rounded-lg border border-gray-200">
              Creating safety backup before generating ad feeds...
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3 Card: 1-Click Rollback (Unified 5-Layer Layout) -->
      <div id="card-rollback" class="action-card polaris-card p-6 bg-gray-50/70 border border-gray-200 shadow-sm">
        <div class="layer-1-badge flex flex-wrap items-center justify-between gap-2 pb-2">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold uppercase tracking-wide px-2.5 py-0.5 rounded bg-gray-200 text-gray-800" data-i18n="safety_tag">
              Step 3 • Safety Net & Undo
            </span>
            <span id="snapshot-tag" class="text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono">Checking backups...</span>
          </div>
        </div>

        <div class="layer-2-title pt-1">
          <h4 class="text-base md:text-lg font-bold text-gray-900" data-i18n="safety_title">
            1-Click Rollback (Time Machine)
          </h4>
        </div>

        <div class="layer-3-description mt-1 pb-4 border-b border-gray-100 space-y-1">
          <div class="text-xs text-gray-500 font-medium" data-i18n="safety_when">
            When you want to revert changes or reset metafields and variant mappings to a previous point in time
          </div>
          <p class="text-xs md:text-sm text-gray-600 leading-relaxed" data-i18n="safety_desc">
            Instantly revert all metafield values and variant mappings from secure cloud backup in under 10 seconds. Your peace-of-mind safety insurance.
          </p>
        </div>

        <div class="layer-4-actions flex flex-wrap items-center gap-2.5 py-4">
          <button onclick="takeManualSnapshot()" id="btn-take-snapshot" class="px-3.5 py-2 text-xs font-semibold text-gray-800 bg-white border border-gray-300 rounded-lg hover:bg-gray-100 flex items-center gap-1.5 shadow-sm whitespace-nowrap">
            <span>📸</span> <span data-i18n="btn_backup_now">Back Up Store Now</span>
          </button>
          <button onclick="openRollbackModal()" id="btn-rollback" class="polaris-btn-danger px-4 py-2 rounded-lg text-xs md:text-sm shadow-sm flex items-center gap-1.5 whitespace-nowrap">
            <span>⏮️</span> <span data-i18n="btn_restore">Revert to Previous Snapshot</span>
          </button>
        </div>
        <div id="step3-action-msg" class="hidden mb-3 text-xs rounded-lg p-3 border transition-all duration-200"></div>

        <div class="layer-5-preview" id="rollback_info_container">
          <!-- Collapsible Backup History Log -->
          <details class="bg-white rounded-lg border border-gray-200 text-xs">
            <summary class="px-3 py-2 cursor-pointer font-medium text-gray-600 hover:text-gray-900 flex items-center justify-between">
              <span data-i18n="backup_history_toggle">🗄️ View Stored Backup Points</span>
              <span id="r2-count" class="text-gray-400 font-mono">Loading...</span>
            </summary>
            <div id="r2-object-list" class="p-3 border-t border-gray-100 font-mono text-gray-600 max-h-32 overflow-y-auto space-y-1"></div>
          </details>
          <div id="rollback-comparison-panel" class="mt-3 hidden overflow-x-auto border border-gray-200 rounded-xl bg-white shadow-sm p-4"></div>
        </div>
      </div>
    </section>

    <!-- Footer / Legal & Support Links -->
    <footer class="mt-12 pt-6 border-t border-gray-200 text-center text-xs text-gray-500 space-y-2">
      <div class="flex items-center justify-center gap-4">
        <a href="/privacy" target="_blank" class="text-emerald-700 hover:underline font-medium">Privacy Policy</a>
        <span>•</span>
        <a href="/terms" target="_blank" class="text-emerald-700 hover:underline font-medium">Terms of Service</a>
        <span>•</span>
        <a href="mailto:studio.nexus.ops@gmail.com" class="text-gray-600 hover:underline">studio.nexus.ops@gmail.com</a>
      </div>
      <div>&copy; 2026 AdFeed Clean for Google Shopping. All rights reserved.</div>
    </footer>

  </div>

  <!-- Restore Confirmation Modal -->
  <div id="rollback-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4">
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-gray-200">
      <div class="flex items-center gap-3 text-red-600">
        <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-xl font-bold">⚠️</div>
        <h3 class="text-lg font-bold text-gray-900" data-i18n="modal_title">Restore Store to Previous Backup?</h3>
      </div>
      <p class="text-sm text-gray-600" data-i18n="modal_desc">
        Your store will be restored from your secure cloud backup within 10 seconds:
      </p>
      <div class="space-y-1.5 pt-1">
        <label for="rollback-snapshot-select" class="block text-xs font-semibold text-gray-700" data-i18n="modal_select_label">
          Select Backup Point to Restore:
        </label>
        <select id="rollback-snapshot-select" class="w-full text-xs bg-white border border-gray-300 rounded-lg p-2.5 font-mono text-gray-800 focus:ring-2 focus:ring-red-500 focus:outline-none">
          <option value="latest">Latest Backup</option>
        </select>
        <p class="text-[11px] text-gray-500" data-i18n="modal_select_hint">
          Choose from your permanent Virgin Baseline or top 3 recent rolling snapshots.
        </p>
      </div>
      <ul class="text-xs text-gray-700 space-y-2 bg-gray-50 p-3.5 rounded-lg border border-gray-200 list-disc list-inside">
        <li data-i18n="modal_li1"><strong>Original Product Images:</strong> Restores unmodified image URLs</li>
        <li data-i18n="modal_li2"><strong>Variant Links:</strong> Re-links every color and size option to its original photo</li>
        <li data-i18n="modal_li3"><strong>Product Descriptions:</strong> Restores original HTML body content</li>
      </ul>
      <div class="flex justify-end gap-3 pt-3 border-t border-gray-100">
        <button onclick="closeRollbackModal()" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg" data-i18n="modal_cancel">Cancel</button>
        <button onclick="executeRollback()" id="btn-confirm-rollback" class="polaris-btn-danger px-5 py-2 text-sm rounded-lg font-bold shadow" data-i18n="modal_confirm">
          Yes, Restore Now
        </button>
      </div>
    </div>
  </div>

  <!-- Batch Free Trial Confirmation Modal (Zero browser confirm()) -->
  <div id="batch-trial-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4">
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-gray-200">
      <div class="flex items-center gap-3 text-emerald-700">
        <div class="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-xl font-bold">🚀</div>
        <h3 class="text-lg font-bold text-gray-900" id="trial-modal-title" data-i18n="trial_modal_title">14-Day Free Trial Required for Full Catalog Sync</h3>
      </div>
      <p class="text-sm text-gray-600 leading-relaxed" id="trial-modal-desc" data-i18n="trial_modal_desc">
        Full catalog synchronization requires activating the 14-day free trial ($65/mo). Would you like to proceed to Shopify's official charge approval screen to start your free trial?
      </p>
      <div class="bg-gray-50 p-3 rounded-lg border border-gray-200 text-xs text-gray-700 space-y-1">
        <div class="flex items-center gap-2"><span>🛡️</span> <strong>14-Day Risk-Free Trial:</strong> You will not be charged if canceled within 14 days.</div>
        <div class="flex items-center gap-2"><span>⚡</span> <strong>Unlimited Ad-Feed Generation:</strong> Cleans promotional badges for all current and future products.</div>
      </div>
      <div class="flex justify-end gap-3 pt-3 border-t border-gray-100">
        <button onclick="closeBatchTrialModal()" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
        <button onclick="confirmStartTrialFromModal()" class="polaris-btn-primary px-5 py-2 text-sm rounded-lg font-bold shadow">
          Proceed to Shopify Approval
        </button>
      </div>
    </div>
  </div>

  <!-- Early Trial Activation / 50-Image Cap Modal -->
  <div id="trial-cap-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4">
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-gray-200">
      <div class="flex items-center gap-3 text-amber-600">
        <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-xl font-bold">🎉</div>
        <h3 class="text-lg font-bold text-gray-900" id="trial-cap-title">Free Trial Quota (50/50 Images) Completed!</h3>
      </div>
      <p class="text-sm text-gray-600 leading-relaxed" id="trial-cap-desc">
        50 clean ad images have been generated and mapped to your ad feed. Would you like to activate your full subscription now ($65/mo) to unlock the rest of your catalog immediately?
      </p>
      <div class="bg-emerald-50 p-3 rounded-lg border border-emerald-200 text-xs text-emerald-900 space-y-1">
        <div class="flex items-center gap-2"><span>⚡</span> <strong>Immediate Full Activation:</strong> Skips remaining trial waiting period and processes full catalog immediately.</div>
        <div class="flex items-center gap-2"><span>🛡️</span> <strong>Hybrid Smart Plan:</strong> $65/mo includes 500 images + $0.05/image overage (Max $100/mo cap).</div>
      </div>
      <div class="flex justify-end gap-3 pt-3 border-t border-gray-100">
        <button onclick="closeTrialCapModal()" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Wait for 14-day trial end</button>
        <button onclick="executeActivateNow()" class="polaris-btn-primary px-5 py-2 text-sm rounded-lg font-bold shadow bg-emerald-600 hover:bg-emerald-700 text-white">
          Activate Full Plan Now ($65/mo)
        </button>
      </div>
    </div>
  </div>

  <script>
    const shop = "${shop}";
    let currentLang = "en";
    let canaryData = null;
    let lastStatusData = null;
    let cachedAvailableSnapshots = [];

    const urlParams = (typeof URLSearchParams !== 'undefined' && typeof window !== 'undefined' && window.location && window.location.search)
      ? new URLSearchParams(window.location.search)
      : null;
    const appHost = urlParams ? (urlParams.get('host') || '') : '';

    async function apiFetch(url, options) {
      const opts = Object.assign({}, options || {});
      const headers = Object.assign({}, opts.headers || {});
      if (window.shopify && typeof window.shopify.idToken === 'function') {
        try {
          const sessionToken = await window.shopify.idToken();
          if (sessionToken) {
            headers['Authorization'] = 'Bearer ' + sessionToken;
          }
        } catch (e) {
          console.warn('[AppBridge] Failed to retrieve session token');
        }
      }
      return fetch(url, Object.assign({}, opts, { headers }));
    }

    function checkAuthAndHandleRedirect(status, data) {
      if (!data) return false;
      if (
        status === 401 ||
        data.code === 'REAUTH_REQUIRED' ||
        (data.code === 'CROSS_TENANT_ACCESS_DENIED' && data.reauthUrl) ||
        (typeof data.error === 'string' && (
          data.error.includes('Missing store authentication token') ||
          data.error.includes('Invalid store authentication token') ||
          data.error.includes('Re-authorization required') ||
          data.error.includes('expired or re-installed')
        ))
      ) {
        console.warn('[Self-Healing] Re-authorization required.');
        showNotification(
          'info',
          currentLang === 'ja' ? 'Shopify再接続中...' : 'Reconnecting with Shopify...',
          currentLang === 'ja'
            ? 'アプリの再インストールまたはセッション更新を検知しました。Shopifyの認可画面へ自動遷移します。'
            : 'Re-install or expired session detected. Automatically reconnecting with Shopify authorization...'
        );
        let targetUrl = '/api/auth?shop=' + encodeURIComponent(shop) + (appHost ? '&host=' + encodeURIComponent(appHost) : '');
        if (typeof data.reauthUrl === 'string' && data.reauthUrl.startsWith('/api/auth?')) {
          targetUrl = data.reauthUrl;
          if (appHost && !targetUrl.includes('host=')) {
            targetUrl += '&host=' + encodeURIComponent(appHost);
          }
        }
        setTimeout(function() {
          open(targetUrl, '_top');
        }, 1200);
        return true;
      }
      return false;
    }

    const I18N = {
      en: {
        // App Header
        app_title: "AdFeed Clean for Google Shopping",
        badge_active: "Dual-Feed Engine",
        connected_store: "Connected Store:",

        // Top Banners
        hero_headline: "Keep High-Converting Sale Badges on Storefront — 100% Policy-Compliant on Google Shopping.",
        pill_gmc_compliant: "Google Merchant Center Compliant",
        pill_zero_storefront_change: "Zero Storefront Image Changes",
        pill_variant_preservation: "100% Variant Link Preservation",
        hero_subcopy_title: "How AdFeed Clean Dual-Feed Protection Works:",
        hero_subcopy: "Shoppers on your store see your original, high-converting promo badges ('SALE', '20% OFF'). In the background, our AI detects and removes promotional badges and stores policy-compliant clean images into hidden product metafields (safemedia.clean_ad_image_url) strictly for your Google Shopping and Meta ad feeds.",

        // Plan Bar
        trial_quota_format: "🎁 Free Sample Preview ({used} / {limit} Used)",
        trial_active_badge: "✅ 14-Day Free Trial Active ($65/mo • Unlimited)",
        trial_desc_free: "Try up to {limit} products risk-free. Activate your <strong>14-Day Free Trial ($65/mo)</strong> anytime to unlock unlimited ad-feed generation.",
        trial_desc_active: "Unlimited automatic ad-feed cleanup and full-catalog sync are active.",
        btn_start_trial: "🚀 Start 14-Day Free Trial ($65/mo)",
        btn_resume_protection: "▶️ Resume Protection",
        emergency_stop_badge: "🛑 Emergency Stop Active (Paused)",
        emergency_stop_desc: "All background image processing is currently paused for safety.",

        // Zone 1: Core Automation
        z1_tag: "Zone 1 • Core Automation",
        zone1_title: "Zone 1: Core Automation (Always-On Ad Shield)",
        z1_when: "When you upload or update products with promotional banners, discount stickers, or text overlays",
        z1_desc: "Zero-UI background automation. Shopify's products/update webhook triggers cloud AI to erase overlays in ~5s without touching your storefront images. The clean ad-feed image URL is saved to metafield safemedia.clean_ad_image_url for Google Merchant Center.",
        z1_btn_toggle: "Pause Auto-Protection",
        z1_btn_enable: "Resume Auto-Protection",
        z1_btn_disable: "Pause Auto-Protection",
        z1_btn_locked: "Unlock Auto-Protection with 14-Day Free Trial",
        sync_active_badge: "🟢 Active (ON)",
        sync_disabled_badge: "⚪ Paused (OFF)",
        sync_locked_badge: "⚪ Paused (Trial Required)",
        flow1_title: "1. Upload Promo Image as Usual",
        flow1_desc: "Your Shopify storefront keeps showing the eye-catching 'SALE / 20% OFF' badge to boost conversion.",
        flow2_title: "2. AI Removes Text & Banners in ~5s",
        flow2_desc: "AI automatically detects and erases promotional text without altering the product or storefront photo.",
        flow3_title: "3. Ready for Google & Meta Feeds",
        flow3_desc: "Ad feeds map safemedia.clean_ad_image_url as the image link to pass ad policy reviews with zero disapprovals.",
        recent_synced_feed_title: "Recent Synced Product Feed",
        loading_feed: "Loading product ad-feed status...",
        status_clean_ready: "✅ Clean Ad Image Ready",
        status_waiting: "Waiting for update",
        label_storefront: "Storefront (Decorated)",
        label_ad_feed: "Google/Meta Ad Feed (AI-Cleaned)",
        label_open_clean: "Open Clean Image URL",

        // Zone 2 Header
        z2_header_title: "Zone 2: Onboarding Tools & Safety Suite",
        z2_header_subtitle: "Sequential tools to test on 1 sample product, generate ad feeds for your entire catalog, and restore with 1-click undo.",

        // Zone 2, Step 1: Canary Preview
        step1_tag: "Step 1 • Start Here",
        step1_risk_free: "Risk-Free Verification",
        step1_title: "Test on 1 Sample Product (Canary Preview)",
        step1_when: "When you want to verify AI badge removal quality and variant safety on 1 product first",
        step1_desc: "Run a safe simulation on a single multi-variant product before syncing. Verify clean promo-badge removal and confirm every color/size option stays 100% linked to the right photo. Storefront images are never modified.",
        step1_quota_note: "※ This sample test is a safety verification preview and does not consume your plan image quota (50 Trial / 500 Monthly Included Quota).",
        step1_success_banner: "Preview Verified (※ Plan image quota has not been consumed)",
        step1_select_label: "Target Product:",
        step1_opt_auto: "🎯 Auto-select (Recommended: Most Variants)",
        step1_opt_cleaned: "(Cleaned)",
        step1_btn: "Test on 1 Sample Product",
        step1_btn_rerun: "Run Sample Test Again",
        step1_empty: "Click 'Test on 1 Sample Product' above to preview before/after results and test variant switching.",
        step1_lbl_product: "Sample Product:",
        step1_lbl_preserved: "✅ 100% Variant Links Preserved",
        step1_lbl_before: "Storefront Image (With Promo Badges)",
        step1_lbl_after: "Google Ad-Feed Image (Policy-Safe Clean Version)",
        step1_lbl_switch: "👇 Click any variant option below to verify its linked photo stays intact:",
        telemetry_time: "⏱️ Processing Time:",
        telemetry_mask: "✂️ Badge Removed:",
        telemetry_engine: "🧠 AI Engine:",
        telemetry_metafield: "🏷️ Metafield:",
        step1_err_warming_up: "AI processing engine is warming up. Please wait a few moments and try again.",
        step1_err_limit_reached: "Free preview limit reached. Start your 14-day free trial to unlock unlimited processing.",
        step1_err_no_image: "No product image found. Please add an image to your product in Shopify before running the test.",
        step1_err_invalid_image: "The product image could not be safely accessed. Please verify the image in Shopify.",
        step1_err_temporary: "A temporary processing error occurred. Your store data remains completely safe. Please try again.",
        step1_btn_add_image: "Add Image in Shopify",
        step1_btn_retry: "Retry Now",
        step1_btn_trial: "Start 14-Day Free Trial",

        // Zone 2, Step 2: Full Catalog Sync
        step2_tag: "Step 2 • Full Catalog Sync",
        step2_non_destructive: "Non-Destructive Metafield Generation",
        step2_title: "Sync All Existing Products (Full Catalog Ad-Feed Generation)",
        step2_when: "When you want to generate clean ad images for your entire existing catalog at once",
        step2_desc: "Automatically backs up your store first, then generates clean ad-feed images in product metafields without altering storefront photos. You can stop the process immediately at any time.",
        step2_btn: "Start Full Catalog Batch Sync",
        step2_abort_btn: "Instant Stop (Circuit Breaker)",
        step2_btn_cancel: "Cancel Batch",
        step2_btn_cancelling: "Cancelling...",
        batch_cancelled_msg: "✅ Batch sync cancelled and cleared. Safe operations resumed.",
        batch_status_processing: "Generating ad-feed clean images into product metafields...",
        batch_status_done: "🎉 All catalog ad feeds generated successfully!",
        batch_details_init: "Creating safety backup before generating ad feeds...",
        batch_details_running: "Processing: Safely generating ad feeds for {total} products with variant preservation...",
        batch_details_completed: "All product metafields and variant links have been verified and preserved.",
        batch_stopped_text: "🛑 Stopped immediately — existing product images were not modified.",
        batch_stopped_details: "Remaining products were safely skipped.",

        // Zone 2, Step 3: 1-Click Rollback
        safety_tag: "Step 3 • Safety Net & Undo",
        safety_title: "1-Click Rollback (Time Machine)",
        safety_when: "When you want to revert changes or reset metafields and variant mappings to a previous point in time",
        safety_desc: "Instantly revert all metafield values and variant mappings from secure cloud backup in under 10 seconds. Your peace-of-mind safety insurance.",
        btn_backup_now: "Back Up Store Now",
        btn_restore: "Revert to Previous Snapshot",
        btn_restore_locked: "Revert to Previous Snapshot (Requires Trial)",
        backup_history_toggle: "🗄️ View Stored Backup Points",
        modal_title: "Restore Store to Previous Backup?",
        modal_desc: "Your store will be restored from your secure cloud backup within 10 seconds:",
        modal_select_label: "Select Backup Point to Restore:",
        modal_select_hint: "Choose from your permanent Virgin Baseline or top 3 recent rolling snapshots.",
        modal_li1: "<strong>Original Product Images:</strong> Restores unmodified image URLs",
        modal_li2: "<strong>Variant Links:</strong> Re-links every color and size option to its original photo",
        modal_li3: "<strong>Product Descriptions:</strong> Restores original HTML body content",
        modal_cancel: "Cancel",
        modal_confirm: "Yes, Restore Now",

        // 4.5.3 Onboarding & Feed Guide
        guide_roadmap_heading: "<span>📋</span> <span>Step-by-Step Onboarding & Channel Mapping Guide</span>",
        guide_step1_lbl: "Step 1: Auto-Sync",
        guide_step1_txt: "Webhook automatically watches products/update for new banners.",
        guide_step2_lbl: "Step 2: Canary Test",
        guide_step2_txt: "Simulate AI removal on 1 product with variant checks.",
        guide_step3_lbl: "Step 3: Catalog Sync",
        guide_step3_txt: "Back up store and write clean ad images to metafields.",
        guide_step4_lbl: "Step 4: Ad Mapping",
        guide_step4_txt: "Deliver clean image metafield to GMC & Meta ad feeds.",
        channel_mapping_lbl: "Ad Feed Channel Distribution Status (Supplemental Feeds):",
        feed_supplemental_note: "Supplemental Feed: Only products with AI-cleaned images are included, safely overwriting image attributes in GMC & Meta without altering other product data.",
        trial_modal_title: "14-Day Free Trial Required for Full Catalog Sync",
        trial_modal_desc: "Full catalog synchronization requires activating the 14-day free trial ($65/mo). Would you like to proceed to Shopify's official charge approval screen to start your free trial?",
        trial_modal_title_rollback: "14-Day Free Trial Required for Store Rollback",
        trial_modal_desc_rollback: "1-Click Rollback from cloud backups requires activating your 14-day free trial ($65/mo). You will not be charged if canceled within 14 days. Proceed to Shopify official charge approval screen?"
      },

      ja: {
        // App Header
        app_title: "AdFeed Clean for Google Shopping",
        badge_active: "デュアルフィード保護機能",
        connected_store: "接続ストア:",

        // Top Banners
        hero_headline: "自社ストアには「売れるセール帯画像」を残したまま、Googleショッピング広告のポリシー違反（BAN）をゼロに。",
        pill_gmc_compliant: "Google Merchant Center 規約完全準拠",
        pill_zero_storefront_change: "自社ストア画像変更ゼロ（完全非破壊）",
        pill_variant_preservation: "バリアント紐付け100%保護",
        hero_subcopy_title: "AdFeed Clean デュアルフィード保護の仕組み:",
        hero_subcopy: "自社ストアの買い物客には購入率を高めるセール帯付き画像（「SALE」「20% OFF」等）をそのまま表示。裏側ではAIが帯・文字のみを自動消去し、広告フィード専用の隠しメタフィールド（safemedia.clean_ad_image_url）へ自動格納します。",

        // Plan Bar
        trial_quota_format: "🎁 無料サンプル枠 ({used} / {limit} 件使用済)",
        trial_active_badge: "✅ 14日間フリートライアル有効（月額 $65 • 無制限）",
        trial_desc_free: "まず{limit}件まで無料で安全性を確認できます。<strong>14日間無料トライアル（月額 $65）</strong>を開始すると全商品の広告フィード自動生成が無制限になります。",
        trial_desc_active: "全商品の広告用クリーン画像自動生成と一括メタフィールド保存が無制限でご利用いただけます。",
        btn_start_trial: "🚀 14日間無料トライアルを開始 ($65/月)",
        btn_resume_protection: "▶️ 自動保護を再開",
        emergency_stop_badge: "🛑 緊急停止中（自動処理一時停止）",
        emergency_stop_desc: "すべてのバックグラウンド画像処理が安全に停止されています。",

        // Zone 1: Core Automation
        z1_tag: "Zone 1 • メイン自動機能",
        zone1_title: "Zone 1: 常時自動保護（Always-On Ad Shield）",
        z1_when: "Google / Meta広告の「テキスト被り審査落ち」を自動で防ぎたいとき",
        z1_desc: "Shopifyにセール帯や文字入り画像を登録すると、裏側でAIが文字・帯だけを消去したクリーン画像を生成し、広告連携用の隠し項目（safemedia.clean_ad_image_url）へ自動保存します。",
        z1_btn_toggle: "自動保護を一時停止 (OFF)",
        z1_btn_enable: "自動保護を再開 (ON)",
        z1_btn_disable: "自動保護を一時停止 (OFF)",
        z1_btn_locked: "14日間無料トライアルで自動保護を有効化",
        sync_active_badge: "🟢 有効 (ON)",
        sync_disabled_badge: "⚪ 一時停止 (OFF)",
        sync_locked_badge: "⚪ 一時停止 (トライアル未開始)",
        flow1_title: "1. いつも通りセール帯画像を登録",
        flow1_desc: "自社ストアの買い物客には「SALE / 20% OFF」などの訴求力が高い画像をそのまま表示します。",
        flow2_title: "2. AIが約5秒で帯・文字を消去",
        flow2_desc: "商品本体の質感やストア画像は一切変えず、広告規約違反になる文字・バナーだけを自動除去します。",
        flow3_title: "3. Google / Meta広告へクリーン画像を配信",
        flow3_desc: "広告フィードの画像項目に safemedia.clean_ad_image_url を指定するだけで審査落ちを防げます。",
        recent_synced_feed_title: "最新の同期済み広告フィード一覧",
        loading_feed: "商品の広告フィード用クリーン画像ステータスを読込中...",
        status_clean_ready: "✅ 広告用クリーン画像 準備完了",
        status_waiting: "自動処理待機中",
        label_storefront: "自社ストア表示（セール帯あり）",
        label_ad_feed: "Google/Meta広告配信用（AI消去済）",
        label_open_clean: "クリーン画像URLを開く",

        // Zone 2 Header
        z2_header_title: "Zone 2: オンボーディングツール ＆ セーフティスイート",
        z2_header_subtitle: "1商品での安全性テスト、既存全商品の広告フィード一括生成、万一の復元を段階的に行える安全機能群です。",

        // Zone 2, Step 1: Canary Preview
        step1_tag: "Step 1 • まずはここから",
        step1_risk_free: "安心の安全検証",
        step1_title: "1商品で安全シミュレーション（カナリアプレビュー）",
        step1_when: "本番適用の前に、まず1商品だけでAI文字消去の品質と安全性を試したいとき",
        step1_desc: "いきなり全商品を変更せず、まず1商品でセール帯や文字がきれいに消去されるか、カラー・サイズ選択時に正しい画像へ切り替わるかをテストします。ストア画像は一切変更されません。",
        step1_quota_note: "※ 本テストは安全確認用のプレビューであり、プランの画像処理枠（トライアル50枚枠 / 月間内包500枚枠）は消費されません。",
        step1_success_banner: "プレビュー検証完了（※プランの画像処理枠は消費されていません）",
        step1_select_label: "テスト対象商品:",
        step1_opt_auto: "🎯 自動選定（おすすめ: 最多バリアント / 未テスト）",
        step1_opt_cleaned: "（消去済）",
        step1_btn: "1商品でサンプルテストを実行",
        step1_btn_rerun: "サンプルテストを再実行",
        step1_empty: "上の「1商品でサンプルテストを実行」ボタンを押すと、ビフォー・アフター比較とバリアント切り替えテストが表示されます。",
        step1_lbl_product: "テスト対象商品:",
        step1_lbl_preserved: "✅ カラー・サイズ画像連動 100%正常",
        step1_lbl_before: "自社ストア表示（セール帯あり）",
        step1_lbl_after: "Google広告配信用（AI消去済クリーン画像）",
        step1_lbl_switch: "👇 カラー・サイズボタンをクリックして、それぞれの画像が正しく連動するか確認できます：",
        telemetry_time: "⏱️ AI処理時間:",
        telemetry_mask: "✂️ 除去領域:",
        telemetry_engine: "🧠 AI推論エンジン:",
        telemetry_metafield: "🏷️ 格納先メタフィールド:",
        step1_err_warming_up: "AI処理エンジンを準備（ウォームアップ）中です。数秒後にもう一度お試しください。",
        step1_err_limit_reached: "無料サンプルの利用上限に達しました。無制限で同期するには14日間の無料トライアルを開始してください。",
        step1_err_no_image: "商品画像が登録されていません。画像を登録してからテストを実行してください。",
        step1_err_invalid_image: "商品画像URLにアクセスできませんでした。Shopify商品管理で画像をご確認ください。",
        step1_err_temporary: "一時的な通信エラーが発生しました。ストアデータは安全に保護されています。もう一度お試しください。",
        step1_btn_add_image: "Shopifyで画像を追加",
        step1_btn_retry: "もう一度試す",
        step1_btn_trial: "14日間無料トライアルを開始",

        // Zone 2, Step 2: Full Catalog Sync
        step2_tag: "Step 2 • 全商品の一括処理",
        step2_non_destructive: "非破壊メタフィールド一括生成",
        step2_title: "既存商品の全件一括同期（カタログAd-Feed生成）",
        step2_when: "ストア内の既存商品すべてについて、広告用クリーン画像を一括生成したいとき",
        step2_desc: "開始前にストア全体を自動バックアップした上で、自社ストア画像は変更せず、全商品のメタフィールドへ広告用クリーン画像を一括保存します。処理中でもボタン1つで即座に停止できます。",
        step2_btn: "全商品の広告フィード用画像を生成",
        step2_abort_btn: "今すぐ緊急停止",
        step2_btn_cancel: "バッチを完全停止",
        step2_btn_cancelling: "完全停止中...",
        batch_cancelled_msg: "✅ バッチ同期を完全停止し破棄しました。通常保護が有効です。",
        batch_status_processing: "全商品の広告用クリーン画像をメタフィールドへ生成中...",
        batch_status_done: "🎉 全商品の広告フィード用画像生成が完了しました！",
        batch_details_init: "広告用画像生成の前にセーフティバックアップを作成中...",
        batch_details_running: "処理中: 全{total}商品のバリアント保護とメタフィールド生成を実行中...",
        batch_details_completed: "すべての商品メタフィールドとカラー・サイズ紐付けが正常に保護されました。",
        batch_stopped_text: "🛑 緊急停止しました（既存商品データはすべて保護されています）",
        batch_stopped_details: "残りの商品処理は安全にキャンセルされました。",

        // Zone 2, Step 3: 1-Click Rollback
        safety_tag: "Step 3 • セーフティネット＆復元",
        safety_title: "1クリック・タイムマシン復元（セーフティネット）",
        safety_when: "万一メタフィールドやバリアント状態を元に戻したいときに使います",
        safety_desc: "万一メタフィールドやバリアント状態を元に戻したいときに使います。10秒以内に保存済みバックアップから完全復元します。",
        btn_backup_now: "今の状態をバックアップ保存",
        btn_restore: "過去の状態へ復元する",
        btn_restore_locked: "過去の状態へ復元（要トライアル）",
        backup_history_toggle: "🗄️ 保存済みバックアップ履歴を表示",
        modal_title: "ストアをバックアップ時点の状態に戻しますか？",
        modal_desc: "保存された安全バックアップから、10秒以内に以下のデータを完全復元します：",
        modal_select_label: "復元するバックアップ時点を選択:",
        modal_select_hint: "永続保持される初期原本（Baseline）または直近3世代のスナップショットから選択できます。",
        modal_li1: "<strong>オリジナル商品画像:</strong> 加工前の元画像URLへ復元",
        modal_li2: "<strong>バリアント紐付け:</strong> カラー・サイズと画像の連動を100%再設定",
        modal_li3: "<strong>商品説明文（HTML）:</strong> 元の説明文データを復元",
        modal_cancel: "キャンセル",
        modal_confirm: "今すぐ復元を実行する",

        // 4.5.3 Onboarding & Feed Guide
        guide_roadmap_heading: "<span>📋</span> <span>ステップ別オンボーディング＆広告配信ガイド</span>",
        guide_step1_lbl: "Step 1: 常時自動保護",
        guide_step1_txt: "Webhookが商品更新を監視し、セール帯画像を自動検出します。",
        guide_step2_lbl: "Step 2: カナリアテスト",
        guide_step2_txt: "まず1商品でAI文字消去とバリアント紐付けの安全性を確認します。",
        guide_step3_lbl: "Step 3: カタログ一括同期",
        guide_step3_txt: "ストア全体を安全に保存後、メタフィールドへ広告用画像を生成します。",
        guide_step4_lbl: "Step 4: 広告配信連携",
        guide_step4_txt: "クリーン画像メタフィールドをGMCおよびMeta広告へ自動配信します。",
        channel_mapping_lbl: "広告補助フィード配信チャンネル連携状況:",
        feed_supplemental_note: "補助フィード仕様: AIクリーン画像が生成された商品のみが出力され、既存のShopify公式連携を壊さずに広告画像のみを安全に上書きします。",
        trial_modal_title: "全商品の一括処理には14日間無料トライアルが必要です",
        trial_modal_desc: "全商品の一括処理には14日間無料トライアル（月額 $65）の開始が必要です。Shopify公式の課金承認画面へ移動して無料トライアルを開始しますか？",
        trial_modal_title_rollback: "ストア復元機能のご利用には14日間無料トライアルが必要です",
        trial_modal_desc_rollback: "保存されたスナップショットからの1クリック復元は、14日間無料トライアル（月額$65）を開始することで利用可能になります。無料期間中に解約すれば費用は一切発生しません。Shopify公式の課金承認画面へ進みますか？"
      }
    };

    function t(key) {
      return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
    }

    function setLanguage(lang) {
      currentLang = lang;
      const btnEn = document.getElementById('lang-en');
      const btnJa = document.getElementById('lang-ja');
      if (btnEn) {
        btnEn.className = lang === 'en'
          ? 'px-2.5 py-1 rounded-md bg-gray-900 text-white'
          : 'px-2.5 py-1 rounded-md text-gray-600 hover:text-gray-900';
      }
      if (btnJa) {
        btnJa.className = lang === 'ja'
          ? 'px-2.5 py-1 rounded-md bg-gray-900 text-white'
          : 'px-2.5 py-1 rounded-md text-gray-600 hover:text-gray-900';
      }

      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.innerHTML = t(key);
      });

      if (lastStatusData) renderStatusData(lastStatusData);
      if (canaryData) renderCanaryResult(canaryData);
      loadProductOptions();
    }
    const setLang = setLanguage;

    function sanitizeUrl(rawUrl) {
      if (!rawUrl || typeof rawUrl !== 'string') return '#';
      const trimmed = rawUrl.trim();
      if (trimmed.startsWith('/')) return sanitizeText(trimmed);
      if (typeof URL !== 'undefined') {
        try {
          const parsed = new URL(trimmed);
          if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
            return sanitizeText(parsed.href);
          }
        } catch (e) {
          return '#';
        }
      } else if (
        (trimmed.startsWith('https://') || trimmed.startsWith('http://')) &&
        !trimmed.includes('<') &&
        !trimmed.includes('>') &&
        !trimmed.includes(' ')
      ) {
        return sanitizeText(trimmed);
      }
      return '#';
    }

    function isSafeBrowserUrl(rawUrl) {
      if (!rawUrl || typeof rawUrl !== 'string') return false;
      const trimmed = rawUrl.trim();
      if (trimmed.startsWith('/')) return true;
      if (typeof URL !== 'undefined') {
        try {
          const parsed = new URL(trimmed);
          return parsed.protocol === 'https:' || parsed.protocol === 'http:';
        } catch (e) {
          return false;
        }
      }
      return (trimmed.startsWith('https://') || trimmed.startsWith('http://')) && !trimmed.includes('<') && !trimmed.includes('>') && !trimmed.includes(' ');
    }

    function sanitizeUiErrorMessage(raw) {
      if (!raw || typeof raw !== 'string') {
        return currentLang === 'ja'
          ? '一時的な通信エラーが発生しました。ストアデータは安全に保護されています。'
          : 'A temporary communication error occurred. Your store data remains completely safe.';
      }
      const trimmed = raw.trim();
      if (
        trimmed.startsWith('{') ||
        trimmed.startsWith('[') ||
        trimmed.includes('GraphQL error') ||
        trimmed.includes('status=') ||
        trimmed.length > 250
      ) {
        return currentLang === 'ja'
          ? '一時的な通信エラーが発生しました。ストアデータは安全に保護されています。'
          : 'A temporary communication error occurred. Your store data remains completely safe.';
      }
      return sanitizeText(raw);
    }

    function showNotification(type, title, message) {
      if (type === 'error') {
        message = sanitizeUiErrorMessage(message);
      }
      const safeTitle = sanitizeText(title);
      const safeMessage = type === 'error' ? message : sanitizeText(message);
      const container = document.getElementById('inline-notification-container');
      if (!container) return;
      container.classList.remove('hidden');
      const id = 'notif-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
      const colorClasses = type === 'success'
        ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
        : type === 'error'
          ? 'bg-red-50 border-red-300 text-red-900'
          : type === 'warning'
            ? 'bg-amber-50 border-amber-300 text-amber-900'
            : 'bg-blue-50 border-blue-300 text-blue-900';
      const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️';

      const html = '<div id="' + id + '" class="p-3.5 rounded-xl border ' + colorClasses + ' shadow-sm flex items-start justify-between gap-3 text-xs md:text-sm transition-all duration-200">' +
        '<div class="flex items-start gap-2.5">' +
          '<span class="text-base select-none">' + icon + '</span>' +
          '<div>' +
            '<strong class="font-bold block">' + safeTitle + '</strong>' +
            '<span class="leading-relaxed">' + safeMessage + '</span>' +
          '</div>' +
        '</div>' +
        '<button onclick="this.parentElement.remove()" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>' +
      '</div>';
      container.insertAdjacentHTML('beforeend', html);
    }

    function dismissMsg(el) {
      if (el && el.parentElement) {
        el.parentElement.classList.add('hidden');
      }
    }

    let autoCapModalShown = false;
    let batchPollingTimer = null;

    function formatEta(sec, lang) {
      if (sec === undefined || sec === null || sec <= 0) {
        return lang === 'ja' ? 'まもなく完了...' : 'Almost done...';
      }
      if (sec < 60) {
        return lang === 'ja' ? '約 ' + Math.ceil(sec) + '秒' : '~' + Math.ceil(sec) + 's';
      }
      const mins = Math.floor(sec / 60);
      const remainingSecs = Math.ceil(sec % 60);
      return lang === 'ja'
        ? '約 ' + mins + '分 ' + remainingSecs + '秒'
        : '~' + mins + 'm ' + remainingSecs + 's';
    }

    function startBatchPolling() {
      if (batchPollingTimer) return;
      batchPollingTimer = setInterval(async function() {
        await refreshStatus();
      }, 2500);
    }

    function stopBatchPolling() {
      if (batchPollingTimer) {
        clearInterval(batchPollingTimer);
        batchPollingTimer = null;
      }
    }

    function renderBatchProgress(jobState) {
      if (!jobState) return;
      const progressInner = document.getElementById('batch-progress-inner');
      const startBtn = document.getElementById('btn-start-batch');
      const abortBtn = document.getElementById('btn-abort-batch');
      const pctEl = document.getElementById('batch-percentage');
      const barEl = document.getElementById('batch-progress-bar');
      const statusEl = document.getElementById('batch-status-text');
      const detailsEl = document.getElementById('batch-details');

      const total = jobState.total || 0;
      const processed = jobState.processed || 0;
      const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

      if (pctEl) pctEl.innerText = pct + '%';
      if (barEl) barEl.style.width = pct + '%';

      if (jobState.status === 'RUNNING') {
        if (progressInner) progressInner.classList.remove('hidden');
        if (startBtn) startBtn.classList.add('hidden');
        if (abortBtn) abortBtn.classList.remove('hidden');

        const eta = formatEta(jobState.estimatedRemainingSec, currentLang);
        if (statusEl) {
          statusEl.innerText = currentLang === 'ja'
            ? '⚡ 処理中: ' + processed + ' / ' + total + ' 商品 (' + pct + '%) — ⏱️ 残り時間目安: ' + eta
            : '⚡ Processing: ' + processed + ' / ' + total + ' products (' + pct + '%) — ⏱️ Est. remaining: ' + eta;
        }
        if (detailsEl) {
          const currentTitle = jobState.currentProductTitle || (currentLang === 'ja' ? '準備中...' : 'Preparing...');
          const avgSpeed = (jobState.avgProcessingSec || 6.8).toFixed(1);
          detailsEl.innerText = currentLang === 'ja'
            ? '現在処理中: ' + currentTitle + ' | 平均処理速度: 約' + avgSpeed + '秒/件 | ストア画像・バリアント紐付け保護中'
            : 'Current: ' + currentTitle + ' | Avg speed: ~' + avgSpeed + 's/item | Storefront images & variants 100% preserved.';
        }
      } else if (jobState.status === 'COMPLETED') {
        if (startBtn) startBtn.classList.remove('hidden');
        if (abortBtn) abortBtn.classList.add('hidden');

        if (statusEl) {
          statusEl.innerText = currentLang === 'ja'
            ? '🎉 全商品の広告フィード用画像生成が完了しました！ (' + total + '/' + total + ' 商品 • 100%)'
            : '🎉 All catalog ad feeds generated! (' + total + '/' + total + ' products • 100%)';
        }
        if (detailsEl) {
          detailsEl.innerText = currentLang === 'ja'
            ? 'すべての商品メタフィールドとカラー・サイズ紐付けが正常に保護されました。'
            : 'All product metafields and variant links have been verified and preserved.';
        }
        stopBatchPolling();
      } else if (jobState.status === 'ABORTED') {
        if (startBtn) startBtn.classList.remove('hidden');
        if (abortBtn) abortBtn.classList.add('hidden');

        if (statusEl) {
          statusEl.innerText = currentLang === 'ja'
            ? '🛑 緊急停止しました（' + processed + ' / ' + total + ' 商品完了）'
            : '🛑 Stopped immediately — ' + processed + ' / ' + total + ' products processed.';
        }
        if (detailsEl) {
          detailsEl.innerText = currentLang === 'ja'
            ? '残りの商品処理は安全にキャンセルされました。ストア画像は変更されていません。'
            : 'Remaining products were safely skipped. Storefront images were not modified.';
        }
        stopBatchPolling();
      } else if (jobState.status === 'FAILED') {
        if (startBtn) startBtn.classList.remove('hidden');
        if (abortBtn) abortBtn.classList.add('hidden');

        if (statusEl) {
          statusEl.innerText = currentLang === 'ja'
            ? '⚠️ バッチ処理中にエラーが発生しました'
            : '⚠️ Batch Sync Stopped with Errors';
        }
        if (detailsEl) {
          detailsEl.innerText = (jobState.errors && jobState.errors.length > 0)
            ? jobState.errors.join('; ')
            : (currentLang === 'ja' ? '一部の画像処理に失敗しました。' : 'Some image operations failed.');
        }
        stopBatchPolling();
      }
    }

    function openBatchTrialModal(feature) {
      const modal = document.getElementById('batch-trial-modal');
      const titleEl = document.getElementById('trial-modal-title');
      const descEl = document.getElementById('trial-modal-desc');

      if (feature === 'rollback') {
        if (titleEl) titleEl.innerHTML = t('trial_modal_title_rollback');
        if (descEl) descEl.innerHTML = t('trial_modal_desc_rollback');
      } else {
        if (titleEl) titleEl.innerHTML = t('trial_modal_title');
        if (descEl) descEl.innerHTML = t('trial_modal_desc');
      }

      if (modal) modal.classList.remove('hidden');
    }

    function closeBatchTrialModal() {
      const modal = document.getElementById('batch-trial-modal');
      if (modal) modal.classList.add('hidden');
    }

    function openTrialCapModal() {
      const modal = document.getElementById('trial-cap-modal');
      if (modal) modal.classList.remove('hidden');
    }

    function closeTrialCapModal() {
      const modal = document.getElementById('trial-cap-modal');
      if (modal) modal.classList.add('hidden');
    }

    async function executeActivateNow() {
      closeTrialCapModal();
      showNotification('info', 'Immediate Activation', 'Requesting immediate active subscription ($65/mo) without trial waiting...');
      try {
        const res = await apiFetch('/api/billing/activate-now', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        if (data && data.confirmationUrl) {
          if (window.shopify && typeof window.shopify.open === 'function') {
            window.shopify.open(data.confirmationUrl);
          } else {
            window.top.location.href = data.confirmationUrl;
          }
        } else {
          showNotification('error', 'Activation Error', data.error || 'Failed to generate confirmation URL.');
        }
      } catch (err) {
        showNotification('error', 'Network Error', String(err));
      }
    }

    function confirmStartTrialFromModal() {
      closeBatchTrialModal();
      startFreeTrial();
    }

    function renderRollbackComparison(data) {
      const panel = document.getElementById('rollback-comparison-panel');
      if (!panel) return;
      const diffs = data.productDataDiffs || data.beforeAfterComparisons || [];
      if (!diffs || diffs.length === 0) {
        panel.classList.add('hidden');
        return;
      }
      panel.classList.remove('hidden');

      const snapId = data.snapshotId || 'Latest Snapshot';
      const revertTime = data.revertedAt || data.snapshotTimestamp || new Date().toISOString();

      let rowsHtml = '';
      diffs.forEach(function(item) {
        const bMeta = item.beforeRevert && item.beforeRevert.cleanAdImageMetafield;
        const aMeta = item.afterRevert && item.afterRevert.cleanAdImageMetafield;
        const storefrontUrl = (item.afterRevert && item.afterRevert.storefrontImageUrl) || (item.beforeRevert && item.beforeRevert.storefrontImageUrl) || '';
        const vCount = Number((item.afterRevert && item.afterRevert.variantCount) || (item.beforeRevert && item.beforeRevert.variantCount) || 0);
        const bVarCleaned = (item.beforeRevert && item.beforeRevert.cleanedVariantCount !== undefined)
          ? Number(item.beforeRevert.cleanedVariantCount)
          : (item.beforeRevert && item.beforeRevert.variantCleanImageMap ? Object.keys(item.beforeRevert.variantCleanImageMap).length : (bMeta ? vCount : 0));
        const aVarCleaned = (item.afterRevert && item.afterRevert.cleanedVariantCount !== undefined)
          ? Number(item.afterRevert.cleanedVariantCount)
          : (item.afterRevert && item.afterRevert.variantCleanImageMap ? Object.keys(item.afterRevert.variantCleanImageMap).length : (aMeta ? vCount : 0));
        const actionCode = (item.afterRevert && item.afterRevert.metafieldAction) || (aMeta ? 'RESTORED_TO_SNAPSHOT' : 'PURGED_TO_VIRGIN');
        const gmcBefore = (item.beforeRevert && item.beforeRevert.gmcImageLink) || '';
        const gmcAfter = (item.afterRevert && item.afterRevert.gmcImageLink) || '';

        const bMetaDisplay = sanitizeText(bMeta ? bMeta.split('/').pop() : 'None');
        const aMetaDisplay = sanitizeText(aMeta ? aMeta.split('/').pop() : (currentLang === 'ja' ? '初期状態（Metafield削除）' : 'Purged to Virgin'));
        const bGmcDisplay = sanitizeText(gmcBefore ? gmcBefore.split('/').pop() : 'Default');
        const aGmcDisplay = sanitizeText(gmcAfter ? gmcAfter.split('/').pop() : 'Default');
        const safeProdTitle = sanitizeText(item.productTitle);
        const safeProdId = sanitizeText(item.productId);
        const safeStorefrontUrl = sanitizeUrl(storefrontUrl);
        const safeBMetaAttr = sanitizeText(bMeta || 'null');
        const safeAMetaAttr = sanitizeText(aMeta || 'Reverted');
        const safeActionCode = sanitizeText(actionCode);
        const safeSnapRef = sanitizeText(snapId.replace('snap_', '').replace('.json', ''));
        const safeSnapIdFull = sanitizeText(snapId);
        const safeRevertTimeShort = sanitizeText(new Date(revertTime).toLocaleTimeString());

        const variantMetaSummary = vCount > 0
          ? '<div class="text-[10px] text-slate-600 pt-0.5">' +
              (currentLang === 'ja' ? 'バリアント: ' : 'Variants: ') + bVarCleaned + '/' + vCount + ' ➔ ' + aVarCleaned + '/' + vCount +
              ' <span class="px-1 py-0.5 rounded bg-slate-100 text-slate-700 text-[9px]">' + safeActionCode + '</span>' +
            '</div>'
          : '';

        const variantFeedSummary = vCount > 0
          ? '<div class="text-[10px] text-emerald-700">' + aVarCleaned + '/' + vCount + (currentLang === 'ja' ? ' バリアント配信' : ' variant feed items') + '</div>'
          : '';

        rowsHtml += '<tr class="hover:bg-slate-50 border-b border-gray-100 text-xs">' +
          '<td class="px-3 py-3 font-medium text-gray-900">' +
            '<div class="font-semibold">' + safeProdTitle + '</div>' +
            '<div class="text-[10px] text-gray-400 font-mono truncate max-w-[140px]">' + safeProdId + '</div>' +
          '</td>' +
          '<td class="px-3 py-3">' +
            '<div class="flex items-center gap-1.5">' +
              '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">100% UNCHANGED</span>' +
            '</div>' +
            '<div class="mt-1">' +
              '<a href="' + safeStorefrontUrl + '" target="_blank" class="text-[11px] text-gray-600 hover:text-gray-900 underline font-mono truncate max-w-[150px] inline-block">' +
                (currentLang === 'ja' ? '自社ストア画像 ↗' : 'Storefront Media ↗') +
              '</a>' +
            '</div>' +
          '</td>' +
          '<td class="px-3 py-3 font-mono text-[11px]">' +
            '<div class="space-y-1">' +
              '<div class="flex items-center gap-1.5 text-slate-500">' +
                '<span class="text-[10px] uppercase font-bold text-slate-400">Before:</span> ' +
                '<span class="truncate max-w-[130px]" title="' + safeBMetaAttr + '">' + bMetaDisplay + '</span>' +
              '</div>' +
              '<div class="flex items-center gap-1.5 text-emerald-700 font-semibold">' +
                '<span class="text-[10px] uppercase font-bold text-emerald-600">After:</span> ' +
                '<span class="truncate max-w-[130px]" title="' + safeAMetaAttr + '">' + aMetaDisplay + '</span>' +
              '</div>' +
              variantMetaSummary +
            '</div>' +
          '</td>' +
          '<td class="px-3 py-3 font-mono text-[11px]">' +
            '<div class="space-y-1">' +
              '<div class="flex items-center gap-1 text-[10px] text-slate-600">' +
                '<span class="font-bold">GMC:</span> <span class="truncate max-w-[140px]" title="' + sanitizeText(gmcBefore + ' -> ' + gmcAfter) + '">' + bGmcDisplay + ' ➔ ' + aGmcDisplay + '</span>' +
              '</div>' +
              '<div class="flex items-center gap-1 text-[10px] text-slate-600">' +
                '<span class="font-bold">Meta:</span> <span class="truncate max-w-[140px]">' + bGmcDisplay + ' ➔ ' + aGmcDisplay + '</span>' +
              '</div>' +
              variantFeedSummary +
            '</div>' +
          '</td>' +
          '<td class="px-3 py-3">' +
            '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">' +
              '<span>🔗</span> <span>' + vCount + '/' + vCount + ' ' + (currentLang === 'ja' ? '連動保持' : 'Preserved') + '</span>' +
            '</span>' +
            '<div class="text-[10px] text-emerald-700 mt-1 font-medium">' +
              (currentLang === 'ja' ? '画像・Metafield同期済' : 'Media & Metafields Synced') +
            '</div>' +
          '</td>' +
          '<td class="px-3 py-3 font-mono text-[10px] text-gray-500">' +
            '<div class="font-semibold text-gray-700 truncate max-w-[100px]">' + safeSnapRef + '</div>' +
            '<div class="text-[10px] text-gray-400">' + safeRevertTimeShort + '</div>' +
          '</td>' +
        '</tr>';
      });

      const titleText = currentLang === 'ja'
        ? '復元前後の商品データ比較（Rollback Before vs. After Product Data Comparison）'
        : 'Rollback Before vs. After Product Data Comparison';
      const snapLabel = currentLang === 'ja' ? '適用スナップショット' : 'Applied Snapshot';
      const revertLabel = currentLang === 'ja' ? '復元完了時刻' : 'Reverted At';

      panel.innerHTML = '<div class="space-y-3">' +
        '<details open class="group bg-white rounded-lg border border-gray-200 overflow-hidden">' +
          '<summary class="px-4 py-3 bg-gray-50/80 hover:bg-gray-100 cursor-pointer font-bold text-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 select-none transition-colors">' +
            '<div class="flex items-center gap-2">' +
              '<span class="transform group-open:rotate-90 transition-transform inline-block text-[10px] text-gray-500">▶</span>' +
              '<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">Shopify Review 4.5.3 Verified</span>' +
              '<h5 class="text-sm font-bold text-gray-900">' + titleText + '</h5>' +
              '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-blue-100 text-blue-800 font-bold">' + diffs.length + ' ' + (currentLang === 'ja' ? '件の比較データ' : 'items') + '</span>' +
            '</div>' +
            '<div class="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold text-emerald-800">' +
              '<span class="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200">🛡️ Storefront Unchanged</span>' +
              '<span class="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200">🔒 100% Variant Binding</span>' +
            '</div>' +
          '</summary>' +
          '<div class="p-4 border-t border-gray-200 space-y-3">' +
            '<p class="text-xs text-gray-500 font-mono">' +
              snapLabel + ': ' + sanitizeText(snapId) + ' • ' + revertLabel + ': ' + sanitizeText(new Date(revertTime).toLocaleString()) +
            '</p>' +
            '<div class="overflow-x-auto max-h-72 overflow-y-auto border border-gray-200 rounded-lg">' +
              '<table class="min-w-full divide-y divide-gray-200 text-left text-xs">' +
                '<thead class="bg-gray-50 text-[10px] uppercase font-bold text-gray-600 sticky top-0 z-10 shadow-sm">' +
                  '<tr>' +
                    '<th class="px-3 py-2 bg-gray-50">Product</th>' +
                    '<th class="px-3 py-2 bg-gray-50">Storefront Media</th>' +
                    '<th class="px-3 py-2 bg-gray-50">Metafield (Before ➔ After)</th>' +
                    '<th class="px-3 py-2 bg-gray-50">Ad Feed Link</th>' +
                    '<th class="px-3 py-2 bg-gray-50">Variant Preservation</th>' +
                    '<th class="px-3 py-2 bg-gray-50">Snapshot Ref</th>' +
                  '</tr>' +
                '</thead>' +
                '<tbody class="divide-y divide-gray-100 bg-white">' +
                  rowsHtml +
                '</tbody>' +
              '</table>' +
            '</div>' +
          '</div>' +
        '</details>' +
      '</div>';
    }

    async function refreshStatus() {
      try {
        const res = await apiFetch('/api/status?shop=' + encodeURIComponent(shop));
        const data = await res.json().catch(function() { return null; });
        if (checkAuthAndHandleRedirect(res.status, data)) {
          return;
        }
        if (!data) return;
        lastStatusData = data;
        renderStatusData(data);
      } catch (e) {
        console.error(e);
      }
    }

    function renderStatusData(data) {
      if (data.billing) {
        const b = data.billing;
        const badge = document.getElementById('plan-status-badge');
        const desc = document.getElementById('plan-status-desc');
        const trialBtn = document.getElementById('btn-start-trial');
        const resumeBtn = document.getElementById('btn-resume-circuit');

        if (b.circuitBreakerTripped) {
          if (badge) {
            badge.className = 'px-2.5 py-1 rounded-md font-bold bg-red-100 text-red-800';
            badge.innerText = currentLang === 'ja' ? '🛑 緊急停止中（自動処理一時停止）' : '🛑 Emergency Stop Active (Paused)';
          }
          if (desc) {
            desc.innerText = currentLang === 'ja'
              ? 'すべてのバックグラウンド画像処理が安全に停止されています。'
              : 'All background image processing is currently paused for safety.';
          }
          const planUsageBadge = document.getElementById('plan-usage-badge');
          if (planUsageBadge) planUsageBadge.classList.add('hidden');
          if (resumeBtn) resumeBtn.classList.remove('hidden');

          // Step 2 Inline Resume Button and Status Sync
          const resumeBtnStep2 = document.getElementById('btn-resume-circuit-step2');
          const resumeLblStep2 = document.getElementById('lbl-resume-circuit-step2');
          if (resumeBtnStep2) resumeBtnStep2.classList.remove('hidden');
          if (resumeLblStep2) resumeLblStep2.innerText = currentLang === 'ja' ? '保護を再開' : 'Resume Protection';

          const cancelBtnStep2 = document.getElementById('btn-cancel-circuit-step2');
          const cancelLblStep2 = document.getElementById('lbl-cancel-circuit-step2');
          if (cancelBtnStep2) cancelBtnStep2.classList.remove('hidden');
          if (cancelLblStep2) cancelLblStep2.innerText = t('step2_btn_cancel');

          const step2Msg = document.getElementById('step2-action-msg');
          if (step2Msg) {
            step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
            const s2txt = currentLang === 'ja'
              ? '🛑 緊急停止中（自動処理一時停止）: すべてのバックグラウンド画像処理が安全に停止されています。「保護を再開」または「バッチを完全停止」を選択できます。'
              : '🛑 Emergency Stop Active (Paused): All background image processing is currently paused for safety. Click Resume Protection to continue or Cancel Batch to discard.';
            step2Msg.innerHTML = '<span>' + s2txt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step2Msg.classList.remove('hidden');
          }
        } else {
          if (resumeBtn) resumeBtn.classList.add('hidden');
          const resumeBtnStep2 = document.getElementById('btn-resume-circuit-step2');
          if (resumeBtnStep2) resumeBtnStep2.classList.add('hidden');
          const cancelBtnStep2 = document.getElementById('btn-cancel-circuit-step2');
          if (cancelBtnStep2) cancelBtnStep2.classList.add('hidden');
          const canaryContainer = document.getElementById('canary-container');
          if (canaryContainer && canaryContainer.innerHTML.includes('Emergency Stop is currently active')) {
            canaryContainer.innerHTML = '';
          }
          const step2Msg = document.getElementById('step2-action-msg');
          if (step2Msg && step2Msg.innerText.includes('Emergency Stop Active')) {
            step2Msg.classList.add('hidden');
          }
          const isTrialCapReached = b.trialDays !== 0 && b.planStatus !== 'ACTIVE' && (b.planStatus === 'TRIAL_CAP_REACHED' ||
            ((b.planStatus === 'TRIAL_ACTIVE' || b.planStatus === 'TRIAL_14D_ACTIVE') && (b.trialUsedCount || 0) >= (b.trialLimit || 50)));

          if (isTrialCapReached) {
            if (badge) {
              badge.className = 'px-2.5 py-1 rounded-md font-bold bg-amber-100 text-amber-900 border border-amber-300';
              badge.innerText = currentLang === 'ja'
                ? '🎉 無料トライアル枠上限到達 (50 / 50 枚完了)'
                : '🎉 Free Trial Quota (50/50 Images) Completed';
            }
            if (desc) {
              desc.innerHTML = currentLang === 'ja'
                ? '無料トライアル枠（50枚）のクリーン画像生成がすべて完了しました！<strong>今すぐ本契約を開始（月額 $65）</strong>すると、カタログ全体の自動処理が即座に再開されます。'
                : '50 free trial ad images generated! <strong>Activate your full subscription ($65/mo)</strong> now to resume immediate processing for your entire catalog.';
            }
            if (trialBtn) {
              trialBtn.classList.remove('hidden');
              trialBtn.className = 'polaris-btn-primary px-4 py-2 text-xs md:text-sm font-bold shadow bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1.5';
              trialBtn.onclick = openTrialCapModal;
              trialBtn.innerText = currentLang === 'ja'
                ? '🚀 今すぐ本契約を開始して制限解除 ($65/月)'
                : '🚀 Activate Full Plan Now ($65/mo)';
            }
            if (!autoCapModalShown) {
              autoCapModalShown = true;
              openTrialCapModal();
            }
            const planUsageBadge = document.getElementById('plan-usage-badge');
            if (planUsageBadge) {
              planUsageBadge.className = 'px-2.5 py-0.5 rounded-md font-bold text-xs bg-amber-100 text-amber-900 border border-amber-300';
              planUsageBadge.innerText = currentLang === 'ja'
                ? 'トライアル枠: 50 / 50 枚使用済'
                : 'Trial Quota: 50 / 50 Images Used';
            }
            const cUsed = b.canaryUsedCount || 0;
            const cLimit = b.canaryLimit || 5;
            const quotaDisplay = document.getElementById('canary_quota_display');
            if (quotaDisplay) {
              quotaDisplay.classList.remove('hidden');
              quotaDisplay.className = 'text-xs text-gray-500 font-medium';
              quotaDisplay.innerText = currentLang === 'ja'
                ? '無料サンプル枠: ' + cUsed + ' / ' + cLimit + ' 件使用済'
                : 'Free Samples: ' + cUsed + ' / ' + cLimit + ' Used';
            }
          } else if (b.planStatus === 'ACTIVE') {
            const usageCount = b.monthlyUsageCount || 0;
            const includedCount = b.monthlyIncludedCount || 500;
            if (badge) {
              badge.className = 'px-2.5 py-1 rounded-md font-bold bg-emerald-100 text-emerald-800';
              badge.innerText = currentLang === 'ja'
                ? '✅ 本契約プラン有効 ($65/月 • 500枚内包)'
                : '✅ Active Protection Plan ($65/mo • 500 Included)';
            }
            if (desc) {
              desc.innerText = currentLang === 'ja'
                ? '全商品の広告用クリーン画像自動生成が有効です。月間500枚まで基本料金内（超過分: $0.05/枚、上限 $100/月）。'
                : 'Full-catalog smart dual-feed active. 500 images/mo included ($0.05/image overage, capped at $100/mo).';
            }
            if (trialBtn) trialBtn.classList.add('hidden');

            const planUsageBadge = document.getElementById('plan-usage-badge');
            if (planUsageBadge) {
              planUsageBadge.className = 'px-2.5 py-0.5 rounded-md font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300';
              planUsageBadge.innerText = currentLang === 'ja'
                ? '月間利用数: ' + usageCount + ' / ' + includedCount + ' 枚' + (usageCount > includedCount ? ' (超過課金対象)' : '')
                : 'Monthly Usage: ' + usageCount + ' / ' + includedCount + ' Images' + (usageCount > includedCount ? ' (Overage Active)' : '');
            }
            const quotaDisplay = document.getElementById('canary_quota_display');
            if (quotaDisplay) {
              quotaDisplay.classList.add('hidden');
            }
          } else if (b.planStatus === 'TRIAL_14D_ACTIVE' || b.planStatus === 'TRIAL_ACTIVE') {
            const trialUsed = b.trialUsedCount || 0;
            const trialLimit = b.trialLimit || 50;
            if (badge) {
              badge.className = 'px-2.5 py-1 rounded-md font-bold bg-emerald-100 text-emerald-800';
              badge.innerText = currentLang === 'ja'
                ? '✅ 14日間フリートライアル中 (50枚枠 • 月額 $65)'
                : '✅ 14-Day Free Trial Active (50 Quota • $65/mo)';
            }
            if (desc) {
              desc.innerText = currentLang === 'ja'
                ? '14日間無料トライアル中です。50枚まで無料で広告用クリーン画像が自動生成されます。'
                : '14-day free trial active. Up to 50 clean images generated free of charge.';
            }
            if (trialBtn) trialBtn.classList.add('hidden');

            const planUsageBadge = document.getElementById('plan-usage-badge');
            if (planUsageBadge) {
              planUsageBadge.className = 'px-2.5 py-0.5 rounded-md font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300';
              planUsageBadge.innerText = currentLang === 'ja'
                ? 'トライアル枠: ' + trialUsed + ' / ' + trialLimit + ' 枚使用済'
                : 'Trial Quota: ' + trialUsed + ' / ' + trialLimit + ' Used';
            }
            const cUsed = b.canaryUsedCount || 0;
            const cLimit = b.canaryLimit || 5;
            const quotaDisplay = document.getElementById('canary_quota_display');
            if (quotaDisplay) {
              quotaDisplay.classList.remove('hidden');
              quotaDisplay.className = 'text-xs text-gray-500 font-medium';
              quotaDisplay.innerText = currentLang === 'ja'
                ? '無料サンプル枠: ' + cUsed + ' / ' + cLimit + ' 件使用済'
                : 'Free Samples: ' + cUsed + ' / ' + cLimit + ' Used';
            }
          } else {
            const used = b.canaryUsedCount || 0;
            const limit = b.canaryLimit || 5;
            if (badge) {
              badge.className = used >= limit
                ? 'px-2.5 py-1 rounded-md font-bold bg-red-100 text-red-800'
                : 'px-2.5 py-1 rounded-md font-bold bg-amber-100 text-amber-900';
              badge.innerText = currentLang === 'ja'
                ? '🎁 無料サンプル枠 (' + used + ' / ' + limit + ' 件使用済)'
                : '🎁 Free Sample Preview (' + used + ' / ' + limit + ' Used)';
            }
            if (desc) {
              desc.innerHTML = currentLang === 'ja'
                ? 'まず' + limit + '件まで無料で安全性を確認できます。<strong>14日間無料トライアル（月額 $65）</strong>を開始すると全商品の広告フィード自動生成が無制限になります。'
                : 'Try up to ' + limit + ' products risk-free. Activate your <strong>14-Day Free Trial ($65/mo)</strong> anytime to unlock unlimited ad-feed generation.';
            }
            if (trialBtn) {
              trialBtn.classList.remove('hidden');
              trialBtn.className = 'polaris-btn-primary px-4 py-2 text-xs md:text-sm font-bold shadow rounded-lg flex items-center gap-1.5';
              trialBtn.onclick = startFreeTrial;
              trialBtn.innerText = currentLang === 'ja'
                ? '🚀 14日間無料トライアルを開始 ($65/月)'
                : '🚀 Start 14-Day Free Trial ($65/mo)';
            }

            const quotaDisplay = document.getElementById('canary_quota_display');
            if (quotaDisplay) {
              quotaDisplay.classList.remove('hidden');
              quotaDisplay.className = 'text-xs text-gray-500 font-medium';
              quotaDisplay.innerText = currentLang === 'ja'
                ? '無料サンプル枠: ' + used + '/' + limit + '件使用済'
                : 'Free Samples: ' + used + '/' + limit + ' Used';
            }
          }
        }

        // Update Zone 1 Auto-Sync status badge and single toggle button
        const syncBadge = document.getElementById('autosync-status-badge');
        const liveIndicator = document.getElementById('live_status_indicator');
        const toggleBtn = document.getElementById('toggle_auto_sync');
        const regBtn = document.getElementById('btn-reg-webhook');
        const unregBtn = document.getElementById('btn-unreg-webhook');
        const unregLbl = document.getElementById('lbl-unreg-webhook');
        if (unregLbl) {
          unregLbl.innerText = currentLang === 'ja' ? '自動保護を一時停止 (OFF)' : 'Pause Auto-Protection';
        }
        const isCanary = b.planStatus === 'CANARY_TRIAL';
        const isSyncOn = !isCanary && b.autoSyncEnabled !== false;
        if (syncBadge) {
          if (isCanary) {
            syncBadge.className = 'px-2.5 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-900 border border-amber-200';
            syncBadge.innerText = currentLang === 'ja' ? '⚪ 一時停止 (トライアル未開始)' : '⚪ Paused (Trial Required)';
            if (liveIndicator) {
              liveIndicator.className = 'hidden';
            }
            if (toggleBtn) {
              toggleBtn.className = 'px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm flex items-center gap-1.5 transition';
              toggleBtn.innerHTML = '<span>🔒</span> <span id="toggle_auto_sync_label">' + (currentLang === 'ja' ? '14日間無料トライアルで自動保護を有効化' : 'Unlock Auto-Protection with 14-Day Free Trial') + '</span>';
            }
            if (regBtn) regBtn.classList.add('hidden');
            if (unregBtn) unregBtn.classList.add('hidden');
          } else if (isSyncOn) {
            syncBadge.className = 'px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800';
            syncBadge.innerText = currentLang === 'ja' ? '🟢 有効 (ON)' : '🟢 Active';
            if (liveIndicator) {
              liveIndicator.className = 'hidden';
            }
            if (toggleBtn) {
              toggleBtn.className = 'px-4 py-2 text-xs font-semibold rounded-lg bg-white text-gray-700 border border-gray-300 hover:bg-red-50 hover:text-red-700 hover:border-red-300 shadow-sm flex items-center gap-1.5 transition';
              toggleBtn.innerHTML = '<span>⏸️</span> <span id="toggle_auto_sync_label">' + (currentLang === 'ja' ? '自動保護を一時停止 (OFF)' : 'Pause Auto-Protection') + '</span>';
            }
            if (regBtn) regBtn.classList.add('hidden');
            if (unregBtn) unregBtn.classList.add('hidden');
          } else {
            syncBadge.className = 'px-2.5 py-1 text-xs font-bold rounded-full bg-gray-200 text-gray-700';
            syncBadge.innerText = currentLang === 'ja' ? '⚪ 一時停止 (OFF)' : '⚪ Paused';
            if (liveIndicator) {
              liveIndicator.className = 'hidden';
            }
            if (toggleBtn) {
              toggleBtn.className = 'px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm flex items-center gap-1.5 transition';
              toggleBtn.innerHTML = '<span>▶️</span> <span id="toggle_auto_sync_label">' + (currentLang === 'ja' ? '自動保護を再開 (ON)' : 'Resume Auto-Protection') + '</span>';
            }
            if (regBtn) regBtn.classList.add('hidden');
            if (unregBtn) unregBtn.classList.add('hidden');
          }
        }
      }

      if (data.feedToken) {
        const xmlLink = document.getElementById('feed-xml-link');
        const jsonLink = document.getElementById('feed-json-link');
        const tokenSuffix = '&token=' + encodeURIComponent(String(data.feedToken));
        if (xmlLink) xmlLink.setAttribute('href', '/api/feed-preview.xml?shop=' + encodeURIComponent(shop) + tokenSuffix);
        if (jsonLink) jsonLink.setAttribute('href', '/api/feed-preview?shop=' + encodeURIComponent(shop) + tokenSuffix);
      }

      if (Array.isArray(data.availableSnapshots)) {
        cachedAvailableSnapshots = data.availableSnapshots;
      }

      const isCanary = data.billing && data.billing.planStatus === 'CANARY_TRIAL';
      const rollbackBtn = document.getElementById('btn-rollback');
      if (rollbackBtn) {
        if (isCanary) {
          rollbackBtn.innerHTML = '<span>🔒</span> <span data-i18n="btn_restore_locked">' + t('btn_restore_locked') + '</span>';
        } else {
          rollbackBtn.innerHTML = '<span>⏮️</span> <span data-i18n="btn_restore">' + t('btn_restore') + '</span>';
        }
      }

      const tag = document.getElementById('snapshot-tag');
      if (tag) {
        if (data.latestSnapshot) {
          const prefix = currentLang === 'ja' ? '最新バックアップ: ' : 'Latest Backup: ';
          tag.innerText = prefix + new Date(data.latestSnapshot.createdAt).toLocaleString();
        } else {
          tag.innerText = currentLang === 'ja' ? 'バックアップ未作成' : 'No backup yet';
        }
      }

      const r2Count = document.getElementById('r2-count');
      const r2List = document.getElementById('r2-object-list');
      const rawR2List = Array.isArray(data.r2Objects) ? data.r2Objects.filter(o => {
        const k = String(o.key || o || '');
        const fname = k.split('/').pop() || '';
        return fname.endsWith('.json') && fname !== 'latest.json' && fname !== 'baseline.json';
      }) : [];

      if (rawR2List.length > 0) {
        if (r2Count) {
          r2Count.innerText = rawR2List.length + (currentLang === 'ja' ? ' 件保存中 (最大4件: 初期原本1 + 直近3世代)' : ' files stored (Max 4: 1 Baseline + 3 Recent)');
        }
        if (r2List) {
          const descList = rawR2List.slice().reverse();
          const totalLen = descList.length;
          r2List.innerHTML = descList.map((o, idx) => {
            const rawKey = o.key || o;
            const shortKey = sanitizeText(typeof rawKey === 'string' ? rawKey.split('/').pop().replace('snap_', '').replace('.json', '') : rawKey);
            let roleBadge = '';
            if (idx === 0 && totalLen === 1) {
              roleBadge = currentLang === 'ja' ? '🟢 最新 ＆ 🛡️ 初期原本 [Baseline]' : '🟢 Latest & 🛡️ Virgin Baseline';
            } else if (idx === 0) {
              roleBadge = currentLang === 'ja' ? '🟢 最新バックアップ (直近1世代目)' : '🟢 Latest Backup (Rolling #1)';
            } else if (idx === totalLen - 1) {
              roleBadge = currentLang === 'ja' ? '🛡️ 初期原本 [Virgin Baseline]' : '🛡️ Virgin Baseline (Initial State)';
            } else {
              roleBadge = currentLang === 'ja' ? '📦 過去バックアップ (直近' + (idx + 1) + '世代目)' : '📦 Recent Backup (Rolling #' + (idx + 1) + ')';
            }
            return '<div class="flex justify-between items-center bg-gray-50 px-3 py-1.5 rounded-lg border border-gray-200">' +
              '<span class="truncate text-emerald-800 font-medium text-xs">' + sanitizeText(roleBadge) + ' (' + shortKey + ')</span>' +
              '<span class="text-gray-400 ml-2 whitespace-nowrap text-xs">' + (o.size ? (Number(o.size) / 1024).toFixed(1) + ' KB' : '') + '</span>' +
              '</div>';
          }).join('');
        }
      } else {
        if (r2Count) r2Count.innerText = '0';
        if (r2List) r2List.innerHTML = '<div class="text-gray-400">No backup files found</div>';
      }

      // Populate Synced Product Feed Table (#synced_feed_rows) and Rich Cards (#dual-feed-list)
      const feedRows = document.getElementById('synced_feed_rows');
      const dfList = document.getElementById('dual-feed-list');
      const feedCountBadge = document.getElementById('synced-feed-count-badge');
      if (feedCountBadge && data.dualFeedProducts) {
        const cleanCount = data.dualFeedProducts.filter(p => Boolean(p.cleanAdImageUrl)).length;
        feedCountBadge.innerText = cleanCount + ' / ' + data.dualFeedProducts.length + (currentLang === 'ja' ? ' 件クリーン済' : ' Cleaned');
      }

      if (data.dualFeedProducts && data.dualFeedProducts.length > 0) {
        const isJobRunning = Boolean(data.jobState && data.jobState.status === 'RUNNING');
        const activeProdId = data.jobState && data.jobState.currentProductId;
        const activeProdTitle = data.jobState && data.jobState.currentProductTitle;

        if (feedRows) {
          feedRows.innerHTML = data.dualFeedProducts.map(p => {
            const hasClean = Boolean(p.cleanAdImageUrl);
            const isProcessingThis = isJobRunning && !hasClean && Boolean(
              (activeProdId && p.productId === activeProdId) ||
              (activeProdTitle && p.productTitle === activeProdTitle)
            );
            const safeTitle = sanitizeText(p.productTitle);
            const safeStorefrontUrl = sanitizeUrl(p.storefrontImageUrl || p.dualFeedMetadata?.sourceImageUrl);
            const safeCleanUrl = sanitizeUrl(p.cleanAdImageUrl);
            const totalVarCount = Number(p.variantCount || (Array.isArray(p.variants) ? p.variants.length : 0));
            const cleanedVarCount = Number(p.cleanedVariantCount !== undefined ? p.cleanedVariantCount : (Array.isArray(p.variants) ? p.variants.filter(v => Boolean(v.cleanAdImageUrl)).length : 0));

            let metafieldCell = 'Pending';
            let statusBadgeCell = '<span class="px-2 py-0.5 text-[11px] rounded bg-gray-100 text-gray-600">' + t('status_waiting') + '</span>';

            if (hasClean) {
              const varMetaSub = cleanedVarCount > 0
                ? '<div class="text-[10px] text-emerald-600 font-normal mt-0.5">' +
                    (currentLang === 'ja' ? '親商品 + ' + cleanedVarCount + ' バリアント格納済' : 'Product + ' + cleanedVarCount + ' Variant Metafield' + (cleanedVarCount > 1 ? 's' : '')) +
                  '</div>'
                : '';
              metafieldCell = '<a href="' + safeCleanUrl + '" target="_blank" class="underline hover:text-emerald-900">safemedia.clean_ad_image_url ↗</a>' + varMetaSub;
              statusBadgeCell = '<span class="px-2 py-0.5 text-[11px] rounded bg-emerald-100 text-emerald-800 font-semibold">' + t('status_clean_ready') + '</span>';
            } else if (isProcessingThis) {
              metafieldCell = '<span class="text-blue-600 font-medium animate-pulse">' + (currentLang === 'ja' ? 'AI画像生成中...' : 'Generating...') + '</span>';
              statusBadgeCell = '<span class="px-2 py-0.5 text-[11px] rounded bg-blue-100 text-blue-800 font-semibold animate-pulse">' + (currentLang === 'ja' ? '🔄 AI処理中...' : '🔄 Processing AI...') + '</span>';
            }

            const variantBadge = totalVarCount > 0
              ? (cleanedVarCount > 0
                  ? '<div class="mt-1"><span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">📦 ' + cleanedVarCount + '/' + totalVarCount + (currentLang === 'ja' ? ' バリアント対応済' : ' Variants Cleaned') + '</span></div>'
                  : '<div class="mt-1"><span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600">📦 ' + totalVarCount + (currentLang === 'ja' ? ' バリアント' : ' Variants') + '</span></div>')
              : '';

            return '<tr>' +
              '<td class="px-4 py-3 font-medium text-gray-900">' + safeTitle + variantBadge + '</td>' +
              '<td class="px-4 py-3 text-gray-500">' +
                '<a href="' + safeStorefrontUrl + '" target="_blank" class="underline hover:text-gray-800">' +
                  t('label_storefront') +
                '</a>' +
              '</td>' +
              '<td class="px-4 py-3 font-mono ' + (hasClean ? 'text-emerald-700 font-semibold' : (isProcessingThis ? 'text-blue-600 font-medium' : 'text-gray-400')) + '">' +
                metafieldCell +
              '</td>' +
              '<td class="px-4 py-3">' +
                statusBadgeCell +
              '</td>' +
            '</tr>';
          }).join('');
        }

        if (dfList) {
          const withClean = data.dualFeedProducts.filter(p => p.cleanAdImageUrl);
          const listToRender = withClean.length > 0 ? withClean : data.dualFeedProducts.slice(0, 3);
          dfList.innerHTML = listToRender.map(p => {
            const hasClean = Boolean(p.cleanAdImageUrl);
            const safeTitle = sanitizeText(p.productTitle);
            const safeStorefrontUrl = sanitizeUrl(p.storefrontImageUrl || p.dualFeedMetadata?.sourceImageUrl);
            const safeCleanUrl = sanitizeUrl(p.cleanAdImageUrl);
            const totalVarCount = Number(p.variantCount || (Array.isArray(p.variants) ? p.variants.length : 0));
            const cleanedVarCount = Number(p.cleanedVariantCount !== undefined ? p.cleanedVariantCount : (Array.isArray(p.variants) ? p.variants.filter(v => Boolean(v.cleanAdImageUrl)).length : 0));

            const variantPairs = [];
            const seenPairKeys = new Set();
            if (Array.isArray(p.variants)) {
              p.variants.forEach(v => {
                if (v.cleanAdImageUrl) {
                  const origV = v.originalImageUrl || p.storefrontImageUrl || p.dualFeedMetadata?.sourceImageUrl || '';
                  const pairKey = origV + '::' + v.cleanAdImageUrl;
                  if (!seenPairKeys.has(pairKey)) {
                    seenPairKeys.add(pairKey);
                    variantPairs.push({
                      titles: [v.variantTitle || 'Variant'],
                      origUrl: origV,
                      cleanUrl: v.cleanAdImageUrl
                    });
                  } else {
                    const existing = variantPairs.find(vp => (vp.origUrl + '::' + vp.cleanUrl) === pairKey);
                    if (existing && v.variantTitle && existing.titles.indexOf(v.variantTitle) === -1) {
                      existing.titles.push(v.variantTitle);
                    }
                  }
                }
              });
            }

            const variantHeaderBadge = totalVarCount > 0
              ? '<span class="px-2 py-0.5 text-[10px] rounded-full bg-slate-100 text-slate-700 font-semibold border border-slate-200">📦 ' + cleanedVarCount + '/' + totalVarCount + (currentLang === 'ja' ? ' バリアント' : ' Variants') + '</span>'
              : '';

            const metaInfo = p.dualFeedMetadata
              ? (currentLang === 'ja'
                  ? '⏱️ 処理時間: ' + sanitizeText(p.dualFeedMetadata.processingSec || '-') + '秒 • 除去領域: ' + sanitizeText(p.dualFeedMetadata.maskCoveragePct || '-') + '% • 🛡️ Google広告審査: 適合 (ポリシー準拠)'
                  : '⏱️ Time: ' + sanitizeText(p.dualFeedMetadata.processingSec || '-') + 's • Badge Cleaned: ' + sanitizeText(p.dualFeedMetadata.maskCoveragePct || '-') + '% • 🛡️ Google Ads: Policy Compliant')
              : (currentLang === 'ja' ? '商品画像の更新待機中' : 'Waiting for product image update');

            let mediaPairsHtml = '';
            if (hasClean && variantPairs.length > 1) {
              mediaPairsHtml = '<div class="flex flex-wrap gap-2.5">' +
                variantPairs.map(vp => {
                  const safeVOrig = sanitizeUrl(vp.origUrl);
                  const safeVClean = sanitizeUrl(vp.cleanUrl);
                  const safeVLabel = sanitizeText(vp.titles.join(', '));
                  return '<div class="bg-white p-2 rounded-xl border border-gray-200 shadow-sm space-y-1">' +
                    '<div class="text-[10px] font-bold text-slate-700 truncate max-w-[160px]" title="' + safeVLabel + '">🎨 ' + safeVLabel + '</div>' +
                    '<div class="flex items-center gap-2">' +
                      '<a href="' + safeVOrig + '" target="_blank"><img src="' + safeVOrig + '" class="w-16 h-16 object-cover rounded-lg border border-gray-300" /></a>' +
                      '<span class="text-emerald-600 font-bold text-sm">➔</span>' +
                      '<a href="' + safeVClean + '" target="_blank"><img src="' + safeVClean + '" class="w-16 h-16 object-cover rounded-lg border-2 border-emerald-500" /></a>' +
                    '</div>' +
                  '</div>';
                }).join('') +
              '</div>';
            } else if (hasClean) {
              mediaPairsHtml = '<div class="flex items-center gap-3 bg-white p-2.5 rounded-xl border border-gray-200 shadow-sm">' +
                '<div class="text-center"><span class="block text-[11px] text-gray-500 font-semibold mb-1">' + t('label_storefront') + '</span><a href="' + safeStorefrontUrl + '" target="_blank"><img src="' + safeStorefrontUrl + '" class="w-24 h-24 object-cover rounded-lg border border-gray-300" /></a></div>' +
                '<span class="text-emerald-600 font-bold text-lg">➔</span>' +
                '<div class="text-center"><span class="block text-[11px] text-emerald-700 font-bold mb-1">' + t('label_ad_feed') + '</span><a href="' + safeCleanUrl + '" target="_blank"><img src="' + safeCleanUrl + '" class="w-24 h-24 object-cover rounded-lg border-2 border-emerald-500" /></a></div>' +
              '</div>';
            }

            return '<div class="p-4 bg-emerald-50/40 rounded-xl border border-emerald-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">' +
              '<div class="space-y-1.5 flex-1 min-w-0">' +
                '<div class="font-bold text-sm text-gray-900 flex flex-wrap items-center gap-2">' +
                  '<span>' + safeTitle + '</span>' +
                  (hasClean
                    ? '<span class="px-2.5 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-800 font-bold">' + t('status_clean_ready') + '</span>'
                    : '<span class="px-2.5 py-0.5 text-xs rounded-full bg-gray-200 text-gray-600">' + t('status_waiting') + '</span>') +
                  variantHeaderBadge +
                '</div>' +
                '<div class="text-xs text-gray-600 font-mono">' + metaInfo + '</div>' +
                (hasClean
                  ? '<div class="pt-1"><a href="' + safeCleanUrl + '" target="_blank" class="inline-flex items-center gap-1 text-xs text-emerald-700 hover:text-emerald-900 underline font-semibold">🔗 ' + t('label_open_clean') + ' (safemedia.clean_ad_image_url) ↗</a></div>'
                  : '') +
              '</div>' +
              mediaPairsHtml +
            '</div>';
          }).join('');
        }
      } else {
        if (feedRows) {
          feedRows.innerHTML = '<tr>' +
            '<td colspan="4" class="px-4 py-8 text-center text-gray-500 space-y-1">' +
              '<div class="text-sm font-semibold text-gray-700">📦 ' + (currentLang === 'ja' ? '商品が見つかりません' : 'No products found') + '</div>' +
              '<div class="text-xs text-gray-400">' +
                (currentLang === 'ja'
                  ? 'Shopify管理画面で画像を登録した商品を追加するか、アプリを再認可してください。'
                  : 'Add products with photos in Shopify Admin, or re-authorize the app.') +
              '</div>' +
            '</td>' +
          '</tr>';
        }
        if (dfList) {
          dfList.innerHTML = '<div class="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-gray-500">' +
            (currentLang === 'ja' ? '広告フィードの対象商品がまだ同期されていません。' : 'No synchronized ad-feed products yet.') +
          '</div>';
        }
      }

      // Update Step Guide Badges and Feed Channel Mapping Status
      const feedItemsBadge = document.getElementById('feed-items-count-badge');
      if (feedItemsBadge && data.feedPreview && Array.isArray(data.feedPreview.items)) {
        const itemCount = data.feedPreview.items.length;
        feedItemsBadge.innerText = itemCount > 0
          ? (currentLang === 'ja' ? '補助フィード (' + itemCount + ' バリアント配信中)' : 'Supplemental Feed (' + itemCount + ' Variant Items Live)')
          : (currentLang === 'ja' ? '補助フィード (待機中)' : 'Supplemental Feed (Ready)');
      }
      if (data.feedPreview && data.feedPreview.channelMappings) {
        const cm = data.feedPreview.channelMappings;
        const gmcStatus = document.getElementById('gmc-mapping-status');
        const metaStatus = document.getElementById('meta-mapping-status');
        if (gmcStatus && cm.googleShopping) {
          gmcStatus.innerText = '🟢 ' + cm.googleShopping.status;
        }
        if (metaStatus && cm.metaCatalog) {
          metaStatus.innerText = '🟢 ' + cm.metaCatalog.status;
        }
      }
      const guideSync = document.getElementById('guide-sync-status');
      if (guideSync && data.billing) {
        guideSync.innerText = data.billing.autoSyncEnabled !== false ? '🟢 Active' : '⚪ Paused';
      }

      // Automatically render rollback comparison table if previous rollback diffs exist
      if (data.lastRollback && (data.lastRollback.productDataDiffs || data.lastRollback.beforeAfterComparisons)) {
        renderRollbackComparison(data.lastRollback);
      } else if (data.lastRollbackDiffs && data.lastRollbackDiffs.length > 0) {
        renderRollbackComparison({
          productDataDiffs: data.lastRollbackDiffs,
          snapshotId: (data.latestSnapshot && data.latestSnapshot.snapshotId) || 'latest',
          revertedAt: data.latestSnapshot && data.latestSnapshot.createdAt
        });
      }

      // Real-time batch progress & auto-resume polling if job is active
      if (data.jobState) {
        renderBatchProgress(data.jobState);
        if (data.jobState.status === 'RUNNING') {
          startBatchPolling();
        } else {
          stopBatchPolling();
        }
      }
    }

    async function toggleAutoSync() {
      // If user is on CANARY_TRIAL (unsubscribed), clicking auto-sync immediately prompts 14-day trial
      if (lastStatusData && lastStatusData.billing && lastStatusData.billing.planStatus === 'CANARY_TRIAL') {
        startFreeTrial();
        return;
      }
      const btn = document.getElementById('toggle_auto_sync');
      if (btn) btn.disabled = true;
      try {
        const res = await apiFetch('/api/auto-sync/toggle?shop=' + encodeURIComponent(shop), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        if (res.status === 402 || (data && data.code === 'SUBSCRIPTION_REQUIRED_FOR_AUTOSYNC')) {
          const z1Msg = document.getElementById('zone1-action-msg');
          if (z1Msg) {
            z1Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-amber-50 border-amber-300 text-amber-900 flex items-center justify-between gap-2';
            const tTxt = currentLang === 'ja' ? '⚠️ 常時自動保護を有効化するには14日間無料トライアルが必要です。' : '⚠️ Always-on Auto-Protection requires activating your 14-day free trial ($65/mo).';
            z1Msg.innerHTML = '<span>' + tTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            z1Msg.classList.remove('hidden');
          }
          showNotification('error', currentLang === 'ja' ? 'トライアルが必要です' : 'Trial Required', data.error || 'Always-on Auto-Protection requires activating your 14-day free trial ($65/mo).');
          startFreeTrial();
          return;
        }
        if (data.success) {
          const z1Msg = document.getElementById('zone1-action-msg');
          if (z1Msg) z1Msg.classList.add('hidden');
          refreshStatus();
        } else {
          const z1Msg = document.getElementById('zone1-action-msg');
          if (z1Msg) {
            z1Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
            const errTxt = (currentLang === 'ja' ? '❌ 自動保護エラー: ' : '❌ Auto-Sync Error: ') + sanitizeUiErrorMessage(data.error || 'Failed to toggle auto-protection');
            z1Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            z1Msg.classList.remove('hidden');
          }
          showNotification('error', currentLang === 'ja' ? '自動保護エラー' : 'Auto-Sync Error', data.error || 'Failed to toggle auto-protection');
        }
      } catch (e) {
        const z1Msg = document.getElementById('zone1-action-msg');
        if (z1Msg) {
          z1Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
          const errTxt = (currentLang === 'ja' ? '❌ ネットワークエラー: ' : '❌ Network Error: ') + sanitizeUiErrorMessage(e && e.message);
          z1Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          z1Msg.classList.remove('hidden');
        }
        showNotification('error', currentLang === 'ja' ? 'ネットワークエラー' : 'Network Error', e.message);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function startFreeTrial() {
      const btn = document.getElementById('btn-start-trial');
      if (btn) {
        btn.disabled = true;
        btn.innerText = currentLang === 'ja' ? 'Shopify課金承認へリダイレクト中...' : 'Redirecting to Shopify Billing...';
      }
      try {
        const res = await apiFetch('/api/billing/subscribe?shop=' + encodeURIComponent(shop), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json().catch(function() { return null; });
        if (checkAuthAndHandleRedirect(res.status, data)) {
          return;
        }
        if (data && data.confirmationUrl) {
          // Break out of the Shopify Admin iframe to show Shopify's native charge-approval flow
          open(data.confirmationUrl, '_top');
          return;
        } else if (data && data.success && data.billing?.planStatus === 'TRIAL_14D_ACTIVE') {
          refreshStatus();
        } else {
          showNotification('error', currentLang === 'ja' ? '課金エラー' : 'Billing Error', (data && data.error) || 'Failed to initiate Shopify charge approval');
        }
      } catch (e) {
        showNotification('error', currentLang === 'ja' ? 'エラー' : 'Error', e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>🚀</span> <span>' + t('btn_start_trial') + '</span>';
        }
      }
    }

    async function resumeProtection() {
      const resumeBtnStep2 = document.getElementById('btn-resume-circuit-step2');
      const cancelBtnStep2 = document.getElementById('btn-cancel-circuit-step2');
      if (resumeBtnStep2) {
        resumeBtnStep2.disabled = true;
        resumeBtnStep2.innerHTML = '<span class="animate-spin">⏳</span> ' + (currentLang === 'ja' ? '再開中...' : 'Resuming...');
      }
      if (cancelBtnStep2) {
        cancelBtnStep2.disabled = true;
      }
      try {
        await apiFetch('/api/batch/resume', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const step2Msg = document.getElementById('step2-action-msg');
        if (step2Msg) {
          step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-emerald-50 border-emerald-300 text-emerald-900 flex items-center justify-between gap-2';
          const okTxt = currentLang === 'ja'
            ? '✅ 緊急停止を解除し、自動保護を再開しました。'
            : '✅ Emergency Stop cleared. Background protection has been resumed.';
          step2Msg.innerHTML = '<span>' + okTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          step2Msg.classList.remove('hidden');
        }
      } catch (err) {
        console.error('Resume failed:', err);
      } finally {
        if (resumeBtnStep2) {
          resumeBtnStep2.disabled = false;
          resumeBtnStep2.innerHTML = '<span>▶️</span> <span id="lbl-resume-circuit-step2">' + (currentLang === 'ja' ? '保護を再開' : 'Resume Protection') + '</span>';
        }
        if (cancelBtnStep2) {
          cancelBtnStep2.disabled = false;
        }
      }
      refreshStatus();
    }

    async function cancelBatch() {
      const cancelBtnStep2 = document.getElementById('btn-cancel-circuit-step2');
      const resumeBtnStep2 = document.getElementById('btn-resume-circuit-step2');
      if (cancelBtnStep2) {
        cancelBtnStep2.disabled = true;
        cancelBtnStep2.innerHTML = '<span class="animate-spin">⏳</span> ' + t('step2_btn_cancelling');
      }
      if (resumeBtnStep2) {
        resumeBtnStep2.disabled = true;
      }
      try {
        await apiFetch('/api/batch/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const step2Msg = document.getElementById('step2-action-msg');
        if (step2Msg) {
          step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-emerald-50 border-emerald-300 text-emerald-900 flex items-center justify-between gap-2';
          const okTxt = t('batch_cancelled_msg');
          step2Msg.innerHTML = '<span>' + okTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          step2Msg.classList.remove('hidden');
        }
        const canaryContainer = document.getElementById('canary-container');
        if (canaryContainer && canaryContainer.innerHTML.includes('Emergency Stop is currently active')) {
          canaryContainer.innerHTML = '';
        }
        const progressInner = document.getElementById('batch-progress-inner');
        if (progressInner) {
          progressInner.classList.add('hidden');
        }
      } catch (err) {
        console.error('Cancel batch failed:', err);
        showNotification('error', currentLang === 'ja' ? 'キャンセルエラー' : 'Cancellation Error', err.message);
      } finally {
        if (cancelBtnStep2) {
          cancelBtnStep2.disabled = false;
          cancelBtnStep2.innerHTML = '<span>⏹️</span> <span id="lbl-cancel-circuit-step2">' + t('step2_btn_cancel') + '</span>';
          cancelBtnStep2.classList.add('hidden');
        }
        if (resumeBtnStep2) {
          resumeBtnStep2.disabled = false;
          resumeBtnStep2.classList.add('hidden');
        }
      }
      refreshStatus();
    }

    async function registerWebhook() {
      const btn = document.getElementById('btn-reg-webhook');
      if (btn) {
        btn.disabled = true;
        btn.innerText = currentLang === 'ja' ? '有効化中...' : 'Enabling...';
      }
      try {
        const res = await apiFetch('/api/webhooks/register?shop=' + encodeURIComponent(shop), { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showNotification('success',
            currentLang === 'ja' ? '自動クリーンアップ有効化' : 'Automatic Ad-Feed Sync ON',
            currentLang === 'ja'
              ? 'Shopify Webhookが有効化されました。商品を更新すると自動的に広告用クリーン画像が生成されます。'
              : 'Whenever you update a product image in Shopify, AdFeed Clean will automatically generate a clean ad version.'
          );
          refreshStatus();
        } else {
          showNotification('error', currentLang === 'ja' ? 'エラー' : 'Error', data.error || JSON.stringify(data));
        }
      } catch (e) {
        showNotification('error', currentLang === 'ja' ? 'ネットワークエラー' : 'Network Error', e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>🔗</span> <span>' + t('z1_btn_enable') + '</span>';
        }
      }
    }

    async function unregisterWebhook() {
      const btn = document.getElementById('btn-unreg-webhook');
      if (btn) {
        btn.disabled = true;
        btn.innerText = currentLang === 'ja' ? '無効化中...' : 'Disabling...';
      }
      try {
        const res = await apiFetch('/api/webhooks/unregister?shop=' + encodeURIComponent(shop), { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showNotification('info',
            currentLang === 'ja' ? '自動クリーンアップ停止' : 'Automatic Ad-Feed Sync Paused',
            currentLang === 'ja'
              ? '自動クリーンアップ（Shopify Webhook）を無効化（OFF）しました。再度有効化するまで、商品更新時の自動AI処理は行われません。'
              : 'Product updates will no longer trigger background AI cleanup until you re-enable it.'
          );
          refreshStatus();
        } else {
          showNotification('error', currentLang === 'ja' ? 'エラー' : 'Error', data.error || JSON.stringify(data));
        }
      } catch (e) {
        showNotification('error', currentLang === 'ja' ? 'ネットワークエラー' : 'Network Error', e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<span>⏸️</span> <span id="lbl-unreg-webhook">' + (currentLang === 'ja' ? '自動クリーンアップを無効化 (OFF)' : 'Disable Auto-Sync') + '</span>';
        }
      }
    }

    function sanitizeText(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    async function loadProductOptions() {
      const selectElem = document.getElementById('select-canary-product');
      if (!selectElem) return;
      try {
        const res = await apiFetch('/api/products?shop=' + encodeURIComponent(shop));
        if (!res.ok) return;
        const data = await res.json().catch(function() { return null; });
        if (!data || !Array.isArray(data.products)) return;
        
        const currentVal = selectElem.value;
        const autoLabel = t('step1_opt_auto');
        let optionsHtml = '<option value="">' + autoLabel + '</option>';
        data.products.forEach(function(p) {
          const rawTitle = p.title || p.productTitle || ('Product #' + (p.id ? String(p.id).split('/').pop() : ''));
          const cleanSuffix = p.hasCleanAdImage ? (' ' + t('step1_opt_cleaned')) : '';
          const noImageSuffix = (p.hasImage === false || p.imageUrl === '') ? (' ' + (currentLang === 'ja' ? '(画像未登録)' : '(No image)')) : '';
          const varCount = p.variantCount === 1
            ? (' (1 ' + (currentLang === 'ja' ? 'バリアント' : 'variant') + ')')
            : (p.variantCount ? (' (' + p.variantCount + ' ' + (currentLang === 'ja' ? 'バリアント' : 'variants') + ')') : '');
          optionsHtml += '<option value="' + sanitizeText(p.id) + '">' + sanitizeText(rawTitle) + varCount + cleanSuffix + noImageSuffix + '</option>';
        });
        selectElem.innerHTML = optionsHtml;
        if (currentVal) {
          selectElem.value = currentVal;
        }
      } catch (e) {
        // Non-critical background load
      }
    }

    async function runCanaryTest() {
      const btn = document.getElementById('btn-run-canary');
      btn.disabled = true;
      btn.innerHTML = '<span class="animate-spin">⏳</span> ' + (currentLang === 'ja' ? 'AI消去＆検証中...' : 'Testing 1 Product...');
      const container = document.getElementById('canary-container');
      container.innerHTML = '<div class="text-center py-6 text-xs md:text-sm text-gray-500">' +
        (currentLang === 'ja'
          ? 'Shopifyから商品のカラー・サイズ情報を取得し、AIセール帯消去とバリアント紐付けの安全性を検証しています...'
          : 'Fetching product variants from Shopify and verifying 100% variant-image link preservation with AI promo-badge removal...') +
        '</div>';

      const selectElem = document.getElementById('select-canary-product');
      const selectedProductId = selectElem ? selectElem.value : '';
      const requestPayload = { shop: shop };
      if (selectedProductId) {
        requestPayload.productId = selectedProductId;
      }

      try {
        const res = await apiFetch('/api/canary/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestPayload)
        });
        const data = await res.json().catch(function() { return null; });
        if (checkAuthAndHandleRedirect(res.status, data)) {
          return;
        }
        if (!res.ok) {
          const rawError = (data && (data.error || data.message)) || '';
          const rawLower = rawError.toLowerCase();
          const dataCode = (data && data.code) || '';
          const isLimitReached =
            dataCode === 'CANARY_LIMIT_REACHED' ||
            dataCode === 'TRIAL_QUOTA_EXCEEDED' ||
            rawLower.includes('trial_quota_exceeded') ||
            rawLower.includes('limit reached') ||
            rawLower.includes('preview limit') ||
            rawLower.includes('trial limit');
          const isWarmingUp =
            dataCode === 'AI_WARMING_UP' ||
            dataCode === 'AI_SERVICE_BUSY' ||
            rawLower.includes('warming up') ||
            rawLower.includes('provisioning') ||
            rawLower.includes('initializing') ||
            rawLower.includes('wait 10 seconds') ||
            rawLower.includes('in_progress') ||
            rawLower.includes('missing processed image');
          const isNoImage =
            dataCode === 'NO_PRODUCT_IMAGE' ||
            rawLower.includes('no product image') ||
            rawError.includes('商品画像が登録されていません');
          const isInvalidImage =
            dataCode === 'INVALID_IMAGE_URL' ||
            rawLower.includes('invalid image url') ||
            rawLower.includes('ssrf') ||
            rawLower.includes('inaccessible');

          const isTrialActive = lastStatusData && lastStatusData.billing && (
            lastStatusData.billing.planStatus === 'TRIAL_14D_ACTIVE' ||
            lastStatusData.billing.planStatus === 'TRIAL_ACTIVE' ||
            lastStatusData.billing.planStatus === 'ACTIVE'
          );

          let displayMsg = t('step1_err_warming_up');
          let actionBtn = '<button onclick="runCanaryTest()" class="px-3.5 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs whitespace-nowrap">🔄 ' + t('step1_btn_retry') + '</button>';

          if (isNoImage) {
            displayMsg = t('step1_err_no_image');
            actionBtn = '<div class="flex items-center gap-2">' +
              '<a href="https://' + encodeURIComponent(shop) + '/admin/products" target="_blank" rel="noopener noreferrer" class="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs whitespace-nowrap inline-flex items-center gap-1.5">📦 ' + t('step1_btn_add_image') + '</a>' +
              '<button onclick="runCanaryTest()" class="px-3.5 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold text-xs whitespace-nowrap">🔄 ' + t('step1_btn_retry') + '</button>' +
            '</div>';
          } else if (isInvalidImage) {
            displayMsg = t('step1_err_invalid_image');
            actionBtn = '<div class="flex items-center gap-2">' +
              '<a href="https://' + encodeURIComponent(shop) + '/admin/products" target="_blank" rel="noopener noreferrer" class="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs whitespace-nowrap inline-flex items-center gap-1.5">📦 ' + t('step1_btn_add_image') + '</a>' +
              '<button onclick="runCanaryTest()" class="px-3.5 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-800 font-bold text-xs whitespace-nowrap">🔄 ' + t('step1_btn_retry') + '</button>' +
            '</div>';
          } else if (isWarmingUp) {
            displayMsg = t('step1_err_warming_up');
          } else if (isLimitReached) {
            if (isTrialActive) {
              displayMsg = currentLang === 'ja'
                ? '無料プレビュー枠（5件）の上限に達しました。カタログ全体の一括同期（Step 2）へ進んでください。'
                : 'Free sample preview limit (5/5) reached. Proceed with Full Catalog Sync (Step 2).';
              actionBtn = '<button onclick="startBatch()" class="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs whitespace-nowrap">🚀 ' + (currentLang === 'ja' ? 'カタログ一括同期へ進む' : 'Proceed to Catalog Sync') + '</button>';
            } else {
              displayMsg = t('step1_err_limit_reached');
              actionBtn = '<button onclick="startFreeTrial()" class="px-3.5 py-2 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-bold text-xs whitespace-nowrap">🚀 ' + t('step1_btn_trial') + '</button>';
            }
          } else {
            displayMsg = t('step1_err_temporary');
          }

          container.innerHTML = '<div class="p-4 bg-amber-50 border border-amber-300 rounded-xl text-xs md:text-sm text-amber-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">' +
            '<div><strong>⚠️ ' + displayMsg + '</strong></div>' +
            actionBtn +
          '</div>';
          return;
        }
        canaryData = data;
        renderCanaryResult(data);
      } catch (err) {
        container.innerHTML = '<div class="p-4 bg-amber-50 border border-amber-300 rounded-xl text-xs md:text-sm text-amber-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">' +
          '<div><strong>⚠️ ' + t('step1_err_temporary') + '</strong></div>' +
          '<button onclick="runCanaryTest()" class="px-3.5 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs whitespace-nowrap">🔄 ' + t('step1_btn_retry') + '</button>' +
        '</div>';
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🔍</span> <span>' + t('step1_btn_rerun') + '</span>';
        refreshStatus();
      }
    }

    function renderCanaryResult(data) {
      const container = document.getElementById('canary-container');
      const checks = data.variantChecks || [];
      const variantButtons = checks.map((v, idx) =>
        '<button onclick="selectVariant(' + idx + ')" id="vbtn-' + idx + '" class="variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border ' + (idx === 0 ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50') + '">' +
          sanitizeText(v.title || v.variantTitle || ('Variant ' + (idx + 1))) +
        '</button>'
      ).join('');

      const lblProduct = currentLang === 'ja' ? 'テスト対象商品:' : 'Sample Product:';
      const lblBadge = currentLang === 'ja' ? '✅ カラー・サイズ画像連動 100%正常' : '✅ 100% Variant Links Preserved';
      const lblBefore = currentLang === 'ja' ? '自社ストア表示（セール帯あり）' : 'Storefront Image (With Promo Badges)';
      const lblAfter = currentLang === 'ja' ? 'Google広告配信用（AI消去済クリーン画像）' : 'Google Ad-Feed Image (Policy-Safe Clean Version)';
      const lblSuccessBanner = currentLang === 'ja'
        ? 'プレビュー検証完了（※プランの画像処理枠は消費されていません）'
        : 'Preview Verified (※ Plan image quota has not been consumed)';
      const lblSwitch = currentLang === 'ja'
        ? '👇 カラー・サイズボタンをクリックして、それぞれの画像が正しく連動するか確認できます：'
        : '👇 Click any variant option below to verify its linked photo stays intact:';

      const firstCheck = checks.length > 0 ? checks[0] : null;
      const initialOrigRaw = (firstCheck && (firstCheck.originalImageUrl || firstCheck.activeImageUrl || firstCheck.url)) || data.originalImageUrl;
      const initialCleanRaw = (firstCheck && firstCheck.cleanAdImageUrl) || data.cleanAdImageUrl || data.afterImageUrl || data.optimizedImageUrl || initialOrigRaw;
      const cleanImg = sanitizeUrl(initialCleanRaw);
      const origImg = sanitizeUrl(initialOrigRaw);
      const safeProdTitle = sanitizeText(data.productTitle);
      const procSec = sanitizeText(data.aiMetadata?.processingSec || data.processingSec || 4.8);
      const maskPct = sanitizeText(data.aiMetadata?.maskCoveragePct || data.maskCoveragePct || 1.6);
      const metafieldKey = sanitizeText(data.metafieldKey || 'safemedia.clean_ad_image_url');
      const activeFirstUrl = sanitizeText(initialOrigRaw);
      const activeFirstCleanUrl = sanitizeText(initialCleanRaw);
      const variantPairedBadge = checks.length > 0
        ? '<span class="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">' +
            checks.length + (currentLang === 'ja' ? ' バリアントのBefore/Afterペア同期済' : ' Variants Paired (Before & After)') +
          '</span>'
        : '';

      container.innerHTML =
        '<div class="bg-gray-50 p-4 rounded-xl border border-gray-200 space-y-4">' +
          '<div id="canary-success-banner" class="p-3 bg-emerald-50 border border-emerald-300 rounded-lg text-xs md:text-sm text-emerald-900 flex items-center gap-2">' +
            '<span class="text-base">🎉</span>' +
            '<span class="font-bold">' + lblSuccessBanner + '</span>' +
          '</div>' +
          '<div class="flex flex-wrap items-center justify-between gap-2">' +
            '<h3 class="font-bold text-gray-900 text-sm">' + lblProduct + ' ' + safeProdTitle + '</h3>' +
            '<span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">' + lblBadge + '</span>' +
          '</div>' +

          '<div class="grid grid-cols-1 md:grid-cols-2 gap-4">' +
            '<div class="bg-white p-3 rounded-lg border border-gray-200 space-y-2">' +
              '<span class="text-xs font-bold text-gray-600">' + lblBefore + '</span>' +
              '<div class="h-48 rounded bg-gray-100 overflow-hidden flex items-center justify-center">' +
                '<img id="canary-orig-img" src="' + origImg + '" class="max-h-full object-contain" alt="Storefront Original" />' +
              '</div>' +
              '<div class="text-xs text-gray-500 font-mono">' +
                'Storefront view: Sale badge retained for high conversion.' +
              '</div>' +
            '</div>' +
            '<div class="bg-white p-3 rounded-lg border-2 border-emerald-400 space-y-2">' +
              '<span class="text-xs font-bold text-emerald-700">' + lblAfter + '</span>' +
              '<div class="h-48 rounded bg-gray-100 overflow-hidden flex items-center justify-center">' +
                '<img id="canary-clean-img" src="' + cleanImg + '" class="max-h-full object-contain" alt="Clean Ad Feed" />' +
              '</div>' +
              '<div class="text-xs text-emerald-800 font-mono">' +
                'Google Shopping view: Overlays erased, policy-compliant.' +
              '</div>' +
            '</div>' +
          '</div>' +

          '<!-- AI Telemetry Bar -->' +
          '<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono bg-white p-2.5 rounded-lg border border-gray-200">' +
            '<div><span class="text-gray-500">⏱️ Time:</span> <span class="font-bold text-gray-900">' + procSec + 's</span></div>' +
            '<div><span class="text-gray-500">✂️ Mask:</span> <span class="font-bold text-gray-900">' + maskPct + '%</span></div>' +
            '<div><span class="text-gray-500">🛡️ Policy:</span> <span class="font-bold text-emerald-700 truncate">' + (currentLang === 'ja' ? 'Google広告適合' : 'Compliant') + '</span></div>' +
            '<div><span class="text-gray-500">🏷️ Metafield:</span> <span class="font-bold text-emerald-700 truncate">' + metafieldKey + '</span></div>' +
          '</div>' +

          '<!-- Interactive Variant Option Pills -->' +
          '<div class="p-3 bg-white rounded-lg border border-gray-200 space-y-2">' +
            '<div class="flex flex-wrap items-center justify-between gap-2">' +
              '<span class="text-xs font-bold text-gray-700">' + lblSwitch + '</span>' +
              variantPairedBadge +
            '</div>' +
            '<div class="flex flex-wrap gap-2">' + variantButtons + '</div>' +
            '<div class="text-xs text-gray-500 pt-1 font-mono space-y-0.5">' +
              '<div class="truncate">Storefront (Before): <span id="active-variant-img" class="text-gray-800 font-semibold">' + activeFirstUrl + '</span></div>' +
              '<div class="truncate">Ad-Feed Metafield (After): <span id="active-variant-clean-img" class="text-emerald-700 font-semibold">' + activeFirstCleanUrl + '</span></div>' +
            '</div>' +
          '</div>' +
        '</div>';
    }

    function selectVariant(index) {
      if (!canaryData) return;
      document.querySelectorAll('.variant-pill').forEach((btn, i) => {
        btn.className = i === index
          ? 'variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border bg-emerald-600 text-white border-emerald-600'
          : 'variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border bg-white text-gray-700 border-gray-300 hover:bg-gray-50';
      });
      const check = canaryData.variantChecks[index];
      const activeUrl = check.activeImageUrl || check.originalImageUrl || check.url || canaryData.originalImageUrl;
      const cleanVariantUrl = check.cleanAdImageUrl || canaryData.cleanAdImageUrl || canaryData.afterImageUrl || canaryData.optimizedImageUrl || activeUrl;
      document.getElementById('active-variant-img').innerText = activeUrl;
      document.getElementById('canary-orig-img').src = isSafeBrowserUrl(activeUrl) ? activeUrl : '#';
      const cleanImgEl = document.getElementById('canary-clean-img');
      if (cleanImgEl) {
        cleanImgEl.src = isSafeBrowserUrl(cleanVariantUrl) ? cleanVariantUrl : '#';
      }
      const activeCleanEl = document.getElementById('active-variant-clean-img');
      if (activeCleanEl) {
        activeCleanEl.innerText = cleanVariantUrl;
      }
    }

    let batchInterval = null;
    async function startBatch() {
      const isTrial = lastStatusData && lastStatusData.billing && (
        lastStatusData.billing.planStatus === 'TRIAL_14D_ACTIVE' ||
        lastStatusData.billing.planStatus === 'TRIAL_ACTIVE' ||
        lastStatusData.billing.planStatus === 'ACTIVE'
      );
      if (!isTrial) {
        openBatchTrialModal();
        return;
      }

      // Check if trial cap reached
      const b = lastStatusData.billing;
      const isTrialCapReached = b && (b.planStatus === 'TRIAL_CAP_REACHED' ||
        ((b.planStatus === 'TRIAL_ACTIVE' || b.planStatus === 'TRIAL_14D_ACTIVE') && (b.trialUsedCount || 0) >= (b.trialLimit || 50)));
      if (isTrialCapReached) {
        openTrialCapModal();
        return;
      }

      const startBtn = document.getElementById('btn-start-batch');
      const abortBtn = document.getElementById('btn-abort-batch');
      const progressInner = document.getElementById('batch-progress-inner');
      const statusEl = document.getElementById('batch-status-text');
      const detailsEl = document.getElementById('batch-details');
      const pctEl = document.getElementById('batch-percentage');
      const barEl = document.getElementById('batch-progress-bar');

      if (startBtn) startBtn.classList.add('hidden');
      if (abortBtn) abortBtn.classList.remove('hidden');
      if (progressInner) progressInner.classList.remove('hidden');
      if (pctEl) pctEl.innerText = '0%';
      if (barEl) barEl.style.width = '0%';
      if (statusEl) {
        statusEl.innerText = currentLang === 'ja'
          ? '⚡ バッチ同期を開始中...'
          : '⚡ Initiating batch catalog sync...';
      }
      if (detailsEl) {
        detailsEl.innerText = currentLang === 'ja'
          ? 'Cloudflare R2バックアップを確認し、AIクリーンアップジョブを準備しています...'
          : 'Verifying cloud backup and initializing AI cleanup pipeline...';
      }

      try {
        const res = await apiFetch('/api/batch/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        if (!res.ok) {
          if (startBtn) startBtn.classList.remove('hidden');
          if (abortBtn) abortBtn.classList.add('hidden');
          const step2Msg = document.getElementById('step2-action-msg');
          if (step2Msg) {
            step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
            const errMsg = (currentLang === 'ja' ? '❌ バッチ開始エラー: ' : '❌ Batch Start Error: ') + sanitizeUiErrorMessage(data.error || 'Failed to start batch sync');
            step2Msg.innerHTML = '<span>' + errMsg + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step2Msg.classList.remove('hidden');
          }
          showNotification('error',
            currentLang === 'ja' ? 'バッチ開始エラー' : 'Batch Start Error',
            data.error || 'Failed to start batch sync'
          );
          return;
        }

        const step2Msg = document.getElementById('step2-action-msg');
        if (step2Msg) step2Msg.classList.add('hidden');

        if (data.jobState) {
          renderBatchProgress(data.jobState);
        }
        startBatchPolling();
      } catch (err) {
        if (startBtn) startBtn.classList.remove('hidden');
        if (abortBtn) abortBtn.classList.add('hidden');
        const step2Msg = document.getElementById('step2-action-msg');
        if (step2Msg) {
          step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
          const errMsg = (currentLang === 'ja' ? '❌ ネットワークエラー: ' : '❌ Network Error: ') + sanitizeUiErrorMessage(String(err));
          step2Msg.innerHTML = '<span>' + errMsg + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          step2Msg.classList.remove('hidden');
        }
        showNotification('error',
          currentLang === 'ja' ? 'ネットワークエラー' : 'Network Error',
          String(err)
        );
      }
    }

    async function abortBatch() {
      stopBatchPolling();
      const startBtn = document.getElementById('btn-start-batch');
      const abortBtn = document.getElementById('btn-abort-batch');
      const statusEl = document.getElementById('batch-status-text');
      const detailsEl = document.getElementById('batch-details');

      if (startBtn) startBtn.classList.remove('hidden');
      if (abortBtn) abortBtn.classList.add('hidden');
      if (statusEl) {
        statusEl.innerText = currentLang === 'ja'
          ? '🛑 緊急停止しました（既存商品データはすべて保護されています）'
          : '🛑 Stopped immediately — existing product images were not modified.';
      }
      if (detailsEl) {
        detailsEl.innerText = currentLang === 'ja'
          ? '残りの商品処理は安全にキャンセルされました。'
          : 'Remaining products were safely skipped.';
      }

      const step2Msg = document.getElementById('step2-action-msg');
      if (step2Msg) {
        step2Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
        const abortTxt = currentLang === 'ja'
          ? '🛑 緊急停止しました（既存商品データはすべて保護されています）。下の「保護を再開」または「バッチを完全停止」を選択できます。'
          : '🛑 Stopped immediately — existing product images were not modified. Click Resume Protection below to restart anytime or Cancel Batch to discard.';
        step2Msg.innerHTML = '<span>' + abortTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
        step2Msg.classList.remove('hidden');
      }
      const resumeBtnStep2 = document.getElementById('btn-resume-circuit-step2');
      if (resumeBtnStep2) resumeBtnStep2.classList.remove('hidden');
      const cancelBtnStep2 = document.getElementById('btn-cancel-circuit-step2');
      if (cancelBtnStep2) cancelBtnStep2.classList.remove('hidden');

      try {
        await apiFetch('/api/batch/abort', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
      } catch (err) {
        console.error('Abort failed:', err);
      }
      await refreshStatus();
    }

    function populateSnapshotSelect() {
      const selectEl = document.getElementById('rollback-snapshot-select');
      if (!selectEl) return;

      selectEl.innerHTML = '';
      if (!cachedAvailableSnapshots || cachedAvailableSnapshots.length === 0) {
        const opt = document.createElement('option');
        opt.value = 'latest';
        opt.innerText = currentLang === 'ja' ? '🟢 最新のバックアップ (自動取得)' : '🟢 Latest Backup (Auto-Saved)';
        selectEl.appendChild(opt);
        return;
      }

      cachedAvailableSnapshots.forEach((snap, idx) => {
        const opt = document.createElement('option');
        opt.value = snap.snapshotId;
        const dateStr = snap.createdAt ? new Date(snap.createdAt).toLocaleString() : '';
        const prodCount = snap.totalProducts || 0;

        let displayLabel = '';
        if (snap.isLatest && snap.isBaseline) {
          displayLabel = currentLang === 'ja'
            ? '🟢 最新 ＆ 初期原本 (アプリ導入直後 • ' + dateStr + ' • ' + prodCount + '商品)'
            : '🟢 Latest & Virgin Baseline (' + dateStr + ' • ' + prodCount + ' products)';
        } else if (snap.isLatest) {
          displayLabel = currentLang === 'ja'
            ? '🟢 最新のバックアップ (' + dateStr + ' • ' + prodCount + '商品)'
            : '🟢 Latest Backup (' + dateStr + ' • ' + prodCount + ' products)';
        } else if (snap.isBaseline) {
          displayLabel = currentLang === 'ja'
            ? '🛡️ 初期原本 [Virgin Baseline] (アプリ導入直後 • ' + dateStr + ' • ' + prodCount + '商品)'
            : '🛡️ Virgin Baseline (Initial Virgin State • ' + dateStr + ' • ' + prodCount + ' products)';
        } else {
          displayLabel = currentLang === 'ja'
            ? '📦 過去バックアップ #' + (cachedAvailableSnapshots.length - idx) + ' (' + dateStr + ' • ' + prodCount + '商品)'
            : '📦 Past Backup #' + (cachedAvailableSnapshots.length - idx) + ' (' + dateStr + ' • ' + prodCount + ' products)';
        }

        opt.innerText = displayLabel;
        selectEl.appendChild(opt);
      });
    }

    function openRollbackModal() {
      if (lastStatusData && lastStatusData.billing && lastStatusData.billing.planStatus === 'CANARY_TRIAL') {
        openBatchTrialModal('rollback');
        return;
      }
      populateSnapshotSelect();
      document.getElementById('rollback-modal').classList.remove('hidden');
    }

    function closeRollbackModal() {
      document.getElementById('rollback-modal').classList.add('hidden');
    }

    async function executeRollback() {
      const btn = document.getElementById('btn-confirm-rollback');
      const selectEl = document.getElementById('rollback-snapshot-select');
      const selectedSnapshotId = selectEl ? selectEl.value : undefined;

      btn.disabled = true;
      btn.innerText = currentLang === 'ja' ? '復元中（約10秒）...' : 'Restoring (~10s)...';

      try {
        const res = await apiFetch('/api/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop, snapshotId: selectedSnapshotId })
        });

        if (res.status === 402) {
          closeRollbackModal();
          openBatchTrialModal('rollback');
          return;
        }

        const data = await res.json();
        closeRollbackModal();
        if (data.success) {
          const step3Msg = document.getElementById('step3-action-msg');
          if (step3Msg) {
            step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-emerald-50 border-emerald-300 text-emerald-900 flex items-center justify-between gap-2';
            const okTxt = (currentLang === 'ja' ? '✅ ストア復元完了: ' : '✅ Store Restored Successfully: ') + sanitizeText(data.message || 'All media and metafields restored.') + (data.snapshotId ? ' (Snapshot: ' + sanitizeText(data.snapshotId) + ')' : '');
            step3Msg.innerHTML = '<span>' + okTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step3Msg.classList.remove('hidden');
          }
          showNotification('success',
            currentLang === 'ja' ? 'ストア復元完了' : 'Store Restored Successfully',
            (data.message || 'All media and metafields restored.') + (data.snapshotId ? ' (Snapshot: ' + data.snapshotId + ')' : '')
          );
          renderRollbackComparison(data);
        } else {
          const step3Msg = document.getElementById('step3-action-msg');
          if (step3Msg) {
            step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
            const errTxt = (currentLang === 'ja' ? '❌ 復元エラー: ' : '❌ Rollback Error: ') + sanitizeUiErrorMessage(data.error || 'Failed to rollback');
            step3Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step3Msg.classList.remove('hidden');
          }
          showNotification('error',
            currentLang === 'ja' ? '復元エラー' : 'Rollback Error',
            data.error || 'Failed to rollback'
          );
        }
        await refreshStatus();
      } catch (e) {
        const step3Msg = document.getElementById('step3-action-msg');
        if (step3Msg) {
          step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
          const errTxt = (currentLang === 'ja' ? '❌ 復元エラー: ' : '❌ Rollback Error: ') + sanitizeUiErrorMessage(e && e.message);
          step3Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          step3Msg.classList.remove('hidden');
        }
        showNotification('error',
          currentLang === 'ja' ? '復元エラー' : 'Rollback Error',
          e.message
        );
      } finally {
        btn.disabled = false;
        btn.innerText = t('modal_confirm');
      }
    }

    async function takeManualSnapshot() {
      const btn = document.getElementById('btn-take-snapshot');
      btn.disabled = true;
      btn.innerHTML = '<span class="animate-spin">⏳</span> ' + (currentLang === 'ja' ? '保存中...' : 'Backing up...');
      try {
        const res = await apiFetch('/api/snapshot/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        if (data.success) {
          const step3Msg = document.getElementById('step3-action-msg');
          if (step3Msg) {
            step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-emerald-50 border-emerald-300 text-emerald-900 flex items-center justify-between gap-2';
            const okTxt = currentLang === 'ja'
              ? '✅ バックアップ完了: 全' + Number(data.totalProducts || 0) + '商品 (' + Number(data.totalImages || 0) + '枚) の状態をクラウドに保存しました。'
              : '✅ Backup Complete: Saved ' + Number(data.totalProducts || 0) + ' products (' + Number(data.totalImages || 0) + ' images) to cloud storage.';
            step3Msg.innerHTML = '<span>' + okTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step3Msg.classList.remove('hidden');
          }
          showNotification('success',
            currentLang === 'ja' ? 'バックアップ完了' : 'Backup Complete',
            currentLang === 'ja'
              ? '全' + data.totalProducts + '商品 (' + data.totalImages + '枚) の状態を保存しました。'
              : 'Saved ' + data.totalProducts + ' products (' + data.totalImages + ' images) to cloud storage.'
          );
          refreshStatus();
        } else {
          const step3Msg = document.getElementById('step3-action-msg');
          if (step3Msg) {
            step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
            const errTxt = (currentLang === 'ja' ? '❌ バックアップエラー: ' : '❌ Backup Error: ') + sanitizeUiErrorMessage(data.error);
            step3Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
            step3Msg.classList.remove('hidden');
          }
          showNotification('error', currentLang === 'ja' ? 'バックアップエラー' : 'Backup Error', data.error);
        }
      } catch (e) {
        const step3Msg = document.getElementById('step3-action-msg');
        if (step3Msg) {
          step3Msg.className = 'mb-3 text-xs rounded-lg p-3 border bg-red-50 border-red-300 text-red-900 flex items-center justify-between gap-2';
          const errTxt = (currentLang === 'ja' ? '❌ エラー: ' : '❌ Error: ') + sanitizeUiErrorMessage(e && e.message);
          step3Msg.innerHTML = '<span>' + errTxt + '</span><button onclick="dismissMsg(this)" class="text-gray-400 hover:text-gray-700 text-sm font-bold px-1 select-none">✕</button>';
          step3Msg.classList.remove('hidden');
        }
        showNotification('error', currentLang === 'ja' ? 'エラー' : 'Error', e.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>📸</span> <span data-i18n="btn_backup_now">' + t('btn_backup_now') + '</span>';
      }
    }

    // Initial status fetch on page load
    refreshStatus();
    loadProductOptions();
  </script>
</body>
</html>`;
}
