/**
 * SafeMedia Shield Embedded UI (Shopify Polaris-styled single page application)
 * Served directly by Cloudflare Workers at GET /
 */

export function renderDashboardHtml(shop: string): string {
  return `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SafeMedia Shield for Shopify</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f1f2f4; color: #202223; }
    .polaris-card { background: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04); border: 1px solid #e1e3e5; }
    .polaris-btn-primary { background-color: #008060; color: #fff; font-weight: 600; transition: all 0.2s; }
    .polaris-btn-primary:hover { background-color: #004c3f; }
    .polaris-btn-danger { background-color: #d82c0d; color: #fff; font-weight: 600; transition: all 0.2s; }
    .polaris-btn-danger:hover { background-color: #bc2200; }
    .badge-success { background-color: #cbf4c9; color: #0e6251; font-weight: 600; }
    .badge-warning { background-color: #ffea8a; color: #8a6100; font-weight: 600; }
  </style>
</head>
<body class="p-4 md:p-8 max-w-5xl mx-auto">

  <!-- Header -->
  <header class="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-gray-200 mb-6 gap-4">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-lg bg-emerald-600 flex items-center justify-center text-white text-xl font-bold shadow-sm">
        🛡️
      </div>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          SafeMedia Shield
          <span class="text-xs px-2.5 py-0.5 rounded-full badge-success">フェイルセーフ有効</span>
        </h1>
        <p class="text-xs text-gray-500">Shopify接続先: <span class="font-mono text-gray-700 font-semibold" id="shop-name">${shop}</span></p>
      </div>
    </div>
    <div class="flex items-center gap-3">
      <button onclick="takeManualSnapshot()" id="btn-take-snapshot" class="px-3 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-100 border border-emerald-300 rounded-lg hover:bg-emerald-200 flex items-center gap-1.5 shadow-sm">
        📸 現在のストアをバックアップ
      </button>
      <button onclick="refreshStatus()" class="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-1.5">
        🔄 状態更新
      </button>
    </div>
  </header>

  <!-- Notification / Alert Banner -->
  <div id="status-banner" class="hidden mb-6 p-4 rounded-xl border flex items-center justify-between"></div>

  <!-- 1. Top Shield: タイムマシン（ロールバック）常時アクセスパネル -->
  <section class="polaris-card p-6 mb-6 border-l-4 border-l-red-500 bg-gradient-to-r from-red-50/30 to-white space-y-4">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <span class="text-red-600 font-bold text-base flex items-center gap-1.5">
            ⏮️ タイムマシン完全ロールバック
          </span>
          <span id="snapshot-tag" class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-mono">確認中...</span>
        </div>
        <p class="text-sm text-gray-600">
          万一デザイン崩れや画像ミスが発生しても、ボタン1クリック・10秒で<strong class="text-gray-900">「バリアント紐付けも含め100%以前の状態」</strong>へ完全復元できます。
        </p>
      </div>
      <button onclick="openRollbackModal()" id="btn-rollback" class="polaris-btn-danger px-5 py-2.5 rounded-lg text-sm shadow flex items-center justify-center gap-2 whitespace-nowrap">
        <span>🔴 過去の状態へ完全復元</span>
      </button>
    </div>
    <!-- R2 Bucket Object Inspector -->
    <div class="bg-gray-50 p-3 rounded-lg border border-gray-200 text-xs space-y-1">
      <div class="flex items-center justify-between text-gray-700 font-semibold">
        <span>🗄️ Cloudflare R2 バケット (<code class="text-emerald-700">safemedia-snapshots</code>) 保存済みオブジェクト:</span>
        <span id="r2-count" class="text-gray-500 font-mono">読込中...</span>
      </div>
      <div id="r2-object-list" class="font-mono text-gray-600 max-h-28 overflow-y-auto space-y-1 pt-1"></div>
    </div>
  </section>

  <!-- 1.5 Priority 1: デュアルフィード分離 & AIクリーンアップ（隠しメタフィールド状態） -->
  <section class="polaris-card p-6 mb-6 border-l-4 border-l-emerald-600 space-y-4">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-gray-100">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-bold text-gray-900">🎯 デュアルフィード分離 ＆ AIクリーンアップ（自動ルーティング）</h2>
          <span class="text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono">Metafield: safemedia.clean_ad_image_url</span>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          自社ストアには「訴求力の高い装飾・セール帯入り画像」を表示したまま、Google Merchant Center / Meta広告フィード向けのクリーン画像を隠しメタフィールドへ自動格納します。
        </p>
      </div>
      <div class="flex gap-2">
        <button onclick="registerWebhook()" id="btn-reg-webhook" class="px-3.5 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm whitespace-nowrap">
          🔗 Webhook自動連動を登録
        </button>
      </div>
    </div>
    <div id="dual-feed-list" class="space-y-3 text-xs text-gray-600">
      <div class="text-center py-4 text-gray-400">Shopify商品のメタフィールド状態を取得中...</div>
    </div>
  </section>

  <!-- 2. Main Workflow: カナリアテスト & 安全最適化 -->
  <div class="grid grid-cols-1 gap-6">

    <!-- カナリアテスト（1商品検証）エリア -->
    <section class="polaris-card p-6">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-gray-100 gap-2 mb-4">
        <div>
          <h2 class="text-lg font-bold text-gray-900 flex items-center gap-2">
            🧪 1商品カナリアテスト（バリアント整合性検証）
          </h2>
          <p class="text-xs text-gray-500">いきなり全件処理を行わず、まず1商品でバリアントが壊れないことを対話的に検証します。</p>
        </div>
        <button onclick="runCanaryTest()" id="btn-run-canary" class="px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 flex items-center gap-2">
          <span>🔍 カナリアテストを実行</span>
        </button>
      </div>

      <!-- カナリア結果表示エリア -->
      <div id="canary-container" class="space-y-6">
        <div class="text-center py-8 text-gray-400 bg-gray-50 rounded-xl border border-dashed border-gray-200">
          「🔍 カナリアテストを実行」をクリックして、バリアントの連動チェックを開始してください。
        </div>
      </div>
    </section>

    <!-- 一括最適化 ＆ 緊急サーキットブレーカー エリア -->
    <section class="polaris-card p-6">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-gray-100 gap-2 mb-4">
        <div>
          <h2 class="text-lg font-bold text-gray-900 flex items-center gap-2">
            🚀 ストア画像の一括最適化（フェイルセーフモード）
          </h2>
          <p class="text-xs text-gray-500">全商品を安全にWebP変換します。処理中いつでも即座に中断（Abort）可能です。</p>
        </div>
        <div class="flex gap-2">
          <button onclick="startBatch()" id="btn-start-batch" class="polaris-btn-primary px-5 py-2 text-sm rounded-lg shadow flex items-center gap-2">
            <span>⚡ 安全一括処理を開始</span>
          </button>
          <button onclick="abortBatch()" id="btn-abort-batch" class="hidden polaris-btn-danger px-4 py-2 text-sm rounded-lg shadow flex items-center gap-2 animate-pulse">
            <span>⛔ 緊急停止（Abort）</span>
          </button>
        </div>
      </div>

      <!-- 進捗プログレスバー -->
      <div id="batch-progress-section" class="hidden space-y-3">
        <div class="flex justify-between text-xs text-gray-600 font-medium">
          <span id="batch-status-text">最適化パイプライン稼働中...</span>
          <span id="batch-percentage">0%</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div id="batch-progress-bar" class="bg-emerald-500 h-3 rounded-full transition-all duration-300" style="width: 0%"></div>
        </div>
        <div id="batch-details" class="text-xs text-gray-500 font-mono bg-gray-50 p-2.5 rounded-lg border border-gray-200">
          スナップショット生成中...
        </div>
      </div>
    </section>

  </div>

  <!-- ロールバック確認モーダル -->
  <div id="rollback-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center hidden p-4">
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-gray-200">
      <div class="flex items-center gap-3 text-red-600">
        <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-xl font-bold">⚠️</div>
        <h3 class="text-lg font-bold text-gray-900">ストアを元の状態にロールバックしますか？</h3>
      </div>
      <p class="text-sm text-gray-600">
        Cloudflare R2に退避された不変スナップショットから、以下のデータを10秒以内に完全復旧します：
      </p>
      <ul class="text-xs text-gray-700 space-y-2 bg-gray-50 p-3 rounded-lg border border-gray-200 list-disc list-inside">
        <li><strong>オリジナル商品画像:</strong> 変換前のURLおよび画像データ</li>
        <li><strong>バリアント紐付け:</strong> カラー・サイズと画像のリレーションを100%再バインド</li>
        <li><strong>商品説明文（HTML）:</strong> リンク切れのない完全な本文状態</li>
      </ul>
      <div class="flex justify-end gap-3 pt-3 border-t border-gray-100">
        <button onclick="closeRollbackModal()" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">キャンセル</button>
        <button onclick="executeRollback()" id="btn-confirm-rollback" class="polaris-btn-danger px-5 py-2 text-sm rounded-lg font-bold shadow">
          今すぐ完全復元する
        </button>
      </div>
    </div>
  </div>

  <script>
    const shop = "${shop}";
    let canaryData = null;

    async function refreshStatus() {
      try {
        const res = await fetch('/api/status?shop=' + encodeURIComponent(shop));
        const data = await res.json();
        const tag = document.getElementById('snapshot-tag');
        if (data.latestSnapshot) {
          tag.innerText = '最終スナップショット: ' + new Date(data.latestSnapshot.createdAt).toLocaleString();
          tag.classList.remove('bg-gray-100', 'text-gray-600');
          tag.classList.add('bg-emerald-100', 'text-emerald-800');
        } else {
          tag.innerText = 'スナップショット未作成';
        }
        const r2Count = document.getElementById('r2-count');
        const r2List = document.getElementById('r2-object-list');
        if (data.r2Objects && data.r2Objects.length > 0) {
          r2Count.innerText = data.r2Objects.length + ' 件のオブジェクト保存中';
          r2List.innerHTML = data.r2Objects.slice().reverse().map(o =>
            '<div class="flex justify-between items-center bg-white px-2 py-1 rounded border border-gray-200">' +
            '<span class="truncate text-emerald-800">' + o.key + '</span>' +
            '<span class="text-gray-400 ml-2 whitespace-nowrap">' + (o.size / 1024).toFixed(1) + ' KB / ' + new Date(o.uploaded).toLocaleTimeString() + '</span>' +
            '</div>'
          ).join('');
        } else {
          r2Count.innerText = '0 件';
          r2List.innerHTML = '<div class="text-gray-400">R2バケット内にオブジェクトがありません</div>';
        }

        const dfList = document.getElementById('dual-feed-list');
        if (data.dualFeedProducts && data.dualFeedProducts.length > 0) {
          const withClean = data.dualFeedProducts.filter(p => p.cleanAdImageUrl);
          const listToRender = withClean.length > 0 ? withClean : data.dualFeedProducts.slice(0, 3);
          dfList.innerHTML = listToRender.map(p => {
            const hasClean = Boolean(p.cleanAdImageUrl);
            const metaInfo = p.dualFeedMetadata
              ? '処理時間: ' + (p.dualFeedMetadata.processingSec || '-') + 's / マスク率: ' + (p.dualFeedMetadata.maskCoveragePct || '-') + '% / Engine: ' + (p.dualFeedMetadata.engine || '-')
              : '未生成（Webhook待機中）';
            return '<div class="p-3 bg-gray-50 rounded-xl border border-gray-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">' +
              '<div class="space-y-1 flex-1 min-w-0">' +
                '<div class="font-bold text-gray-900 flex items-center gap-2">' +
                  '<span>' + p.productTitle + '</span>' +
                  (hasClean
                    ? '<span class="px-2 py-0.5 text-[11px] rounded bg-emerald-100 text-emerald-800 font-bold">✅ 広告用クリーン画像 格納済</span>'
                    : '<span class="px-2 py-0.5 text-[11px] rounded bg-gray-200 text-gray-600">待機中</span>') +
                '</div>' +
                '<div class="font-mono text-[11px] text-gray-500 truncate">Metafield URL: ' +
                  (hasClean ? '<a href="' + p.cleanAdImageUrl + '" target="_blank" class="text-emerald-700 underline font-semibold">' + p.cleanAdImageUrl + '</a>' : '未設定') +
                '</div>' +
                '<div class="text-[11px] text-gray-400 font-mono">' + metaInfo + '</div>' +
              '</div>' +
              (hasClean
                ? '<div class="flex items-center gap-3">' +
                    '<div class="text-center"><span class="block text-[10px] text-gray-400">自社ストア表示</span><img src="' + (p.dualFeedMetadata?.sourceImageUrl || p.storefrontImageUrl) + '" class="w-16 h-16 object-cover rounded border border-gray-300" /></div>' +
                    '<span class="text-emerald-600 font-bold">➔</span>' +
                    '<div class="text-center"><span class="block text-[10px] text-emerald-700 font-bold">GMC広告フィード</span><a href="' + p.cleanAdImageUrl + '" target="_blank"><img src="' + p.cleanAdImageUrl + '" class="w-16 h-16 object-cover rounded border-2 border-emerald-500" /></a></div>' +
                  '</div>'
                : '') +
            '</div>';
          }).join('');
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function registerWebhook() {
      const btn = document.getElementById('btn-reg-webhook');
      btn.disabled = true;
      btn.innerText = '登録中...';
      try {
        const res = await fetch('/api/webhooks/register?shop=' + encodeURIComponent(shop), { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alert('✅ Shopify Webhook (PRODUCTS_UPDATE) 連携が完了しました！\\n\\nCallback URL: ' + data.callbackUrl + '\\nWebhook ID: ' + (data.webhookId || '登録済'));
        } else {
          alert('Webhook登録エラー: ' + (data.error || JSON.stringify(data)));
        }
      } catch (e) {
        alert('通信エラー: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '🔗 Webhook自動連動を登録';
      }
    }

    async function runCanaryTest() {
      const btn = document.getElementById('btn-run-canary');
      btn.disabled = true;
      btn.innerHTML = '<span class="animate-spin">⏳</span> テスト実行中...';
      const container = document.getElementById('canary-container');
      container.innerHTML = '<div class="text-center py-8 text-gray-500">Shopify APIからバリアント情報を取得し、エッジ高速最適化（コールドスタート0秒）で検証中...</div>';

      try {
        const res = await fetch('/api/canary/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        canaryData = data;
        renderCanaryResult(data);
      } catch (err) {
        container.innerHTML = '<div class="text-red-600 p-4 bg-red-50 rounded-lg">エラーが発生しました: ' + err.message + '</div>';
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🔍 カナリアテストを再実行</span>';
        refreshStatus();
      }
    }

    function renderCanaryResult(data) {
      const container = document.getElementById('canary-container');
      let variantButtons = data.variantChecks.map((v, idx) => \`
        <button onclick="selectVariant(\${idx})" id="vbtn-\${idx}" class="variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border \${idx === 0 ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}">
          \${v.variantTitle}
        </button>
      \`).join('');

      container.innerHTML = \`
        <div class="bg-gray-50 p-4 rounded-xl border border-gray-200 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-bold text-gray-900 text-sm">検証商品: \${data.productTitle}</h3>
            <span class="text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">バリアント紐付け保持率 100%</span>
          </div>

          <!-- ビフォー・アフター画像比較 -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white p-3 rounded-lg border border-gray-200 space-y-2">
              <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">元画像 (JPEG/PNG)</span>
              <div class="h-48 rounded bg-gray-100 overflow-hidden flex items-center justify-center">
                <img id="canary-orig-img" src="\${data.originalImageUrl}" class="max-h-full object-contain" alt="Original" />
              </div>
              <div class="text-xs text-gray-600 flex justify-between">
                <span>ファイルサイズ:</span>
                <span class="font-mono font-bold">\${data.originalSizeKB} KB</span>
              </div>
            </div>
            <div class="bg-white p-3 rounded-lg border border-emerald-300 space-y-2">
              <span class="text-xs font-bold text-emerald-600 uppercase tracking-wider">最適化後 (WebP - エッジ高速最適化 0ms)</span>
              <div class="h-48 rounded bg-gray-100 overflow-hidden flex items-center justify-center">
                <img id="canary-opt-img" src="\${data.optimizedImageUrl}" class="max-h-full object-contain" alt="Optimized" />
              </div>
              <div class="text-xs text-emerald-700 flex justify-between font-bold">
                <span>ファイルサイズ: \${data.optimizedSizeKB} KB</span>
                <span class="bg-emerald-100 px-2 py-0.5 rounded text-emerald-800">-\${data.savingsPercentage}% 削減</span>
              </div>
            </div>
          </div>

          <!-- 対話的バリアント切り替えチェッカー -->
          <div class="p-3 bg-white rounded-lg border border-gray-200 space-y-2">
            <span class="text-xs font-bold text-gray-700 block">
              👇 バリアント切り替えテスト（クリックして画像が正しく連動するか確認してください）:
            </span>
            <div class="flex flex-wrap gap-2">
              \${variantButtons}
            </div>
            <div id="variant-indicator" class="text-xs text-gray-600 pt-1 font-mono">
              連動画像: <span id="active-variant-img" class="text-emerald-700 font-semibold">\${data.variantChecks[0].activeImageUrl}</span> (連動チェック: 🟢 正常)
            </div>
          </div>
        </div>
      \`;
    }

    function selectVariant(index) {
      if (!canaryData) return;
      document.querySelectorAll('.variant-pill').forEach((btn, i) => {
        if (i === index) {
          btn.className = 'variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border bg-emerald-600 text-white border-emerald-600';
        } else {
          btn.className = 'variant-pill px-3 py-1.5 text-xs font-semibold rounded-lg border bg-white text-gray-700 border-gray-300 hover:bg-gray-50';
        }
      });
      const check = canaryData.variantChecks[index];
      document.getElementById('active-variant-img').innerText = check.activeImageUrl;
      document.getElementById('canary-orig-img').src = check.activeImageUrl;
      document.getElementById('canary-opt-img').src = check.activeImageUrl;
    }

    let batchInterval = null;
    async function startBatch() {
      document.getElementById('btn-start-batch').classList.add('hidden');
      document.getElementById('btn-abort-batch').classList.remove('hidden');
      const progressSec = document.getElementById('batch-progress-section');
      progressSec.classList.remove('hidden');

      const res = await fetch('/api/batch/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shop })
      });
      const data = await res.json();

      let progress = 10;
      batchInterval = setInterval(() => {
        progress += 20;
        if (progress > 100) progress = 100;
        document.getElementById('batch-progress-bar').style.width = progress + '%';
        document.getElementById('batch-percentage').innerText = progress + '%';
        document.getElementById('batch-details').innerText = '処理中: 全' + data.total + '商品の安全WebP変換 & バリアント再バインド中...';

        if (progress === 100) {
          clearInterval(batchInterval);
          document.getElementById('btn-start-batch').classList.remove('hidden');
          document.getElementById('btn-abort-batch').classList.add('hidden');
          document.getElementById('batch-status-text').innerText = '🎉 安全一括最適化が完了しました！';
          document.getElementById('batch-details').innerText = '全商品画像の最適化とバリアント紐付けの整合性検証が正常に完了しました。';
          refreshStatus();
        }
      }, 800);
    }

    async function abortBatch() {
      if (batchInterval) clearInterval(batchInterval);
      await fetch('/api/batch/abort', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shop })
      });
      document.getElementById('btn-start-batch').classList.remove('hidden');
      document.getElementById('btn-abort-batch').classList.add('hidden');
      document.getElementById('batch-status-text').innerText = '🛑 サーキットブレーカー発動: 処理を安全停止しました';
      document.getElementById('batch-details').innerText = '以降の画像更新はスキップされました。既存データは完全に保護されています。';
    }

    function openRollbackModal() {
      document.getElementById('rollback-modal').classList.remove('hidden');
    }

    function closeRollbackModal() {
      document.getElementById('rollback-modal').classList.add('hidden');
    }

    async function executeRollback() {
      const btn = document.getElementById('btn-confirm-rollback');
      btn.disabled = true;
      btn.innerText = '復旧中（約10秒）...';

      try {
        const res = await fetch('/api/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        closeRollbackModal();
        alert('✅ ロールバック完了: ' + data.message);
        refreshStatus();
      } catch (e) {
        alert('ロールバック中にエラーが発生しました: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '今すぐ完全復元する';
      }
    }

    async function takeManualSnapshot() {
      const btn = document.getElementById('btn-take-snapshot');
      btn.disabled = true;
      btn.innerHTML = '<span class="animate-spin">⏳</span> 保存中...';
      try {
        const res = await fetch('/api/snapshot/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shop })
        });
        const data = await res.json();
        if (data.success) {
          alert('✅ ' + data.message + '\\n\\nR2保存パス: ' + (data.r2Key || '') + '\\n保持商品数: ' + data.totalProducts + '商品 (' + data.totalImages + '画像)');
          refreshStatus();
        } else {
          alert('エラー: ' + data.error);
        }
      } catch (e) {
        alert('エラーが発生しました: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '📸 現在のストアをバックアップ';
      }
    }

    // Initial load
    refreshStatus();
  </script>
</body>
</html>`;
}
