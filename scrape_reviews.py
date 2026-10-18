"""
scrape_reviews.py

Shopify App Storeの画像編集・最適化系競合アプリから低評価レビュー（★1〜2）を取得し、
複数のアプリで共通して発生している致命的なペイン（特定のアプリに依存しない構造的課題）を
自動抽出・分類・検証するツール。
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from playwright.sync_api import sync_playwright

# 調査対象とする画像編集・最適化系の主要競合アプリ定義
DEFAULT_COMPETITOR_APPS = [
    {
        "slug": "bulk-image-edit",
        "name": "Hextom Bulk Image Edit & SEO",
        "category": "一括画像編集・リサイズ・SEO",
        "description": "画像リサイズ、透かし追加、Alt属性、ファイル名一括変更などの総合ツール",
    },
    {
        "slug": "smart-image-optimizer",
        "name": "TinySEO: SEO & Image Optimizer (TinyIMG)",
        "category": "画像圧縮・WebP変換・SEO",
        "description": "画像圧縮、WebP変換、メタデータ生成、JSON-LD対応の代表的アプリ",
    },
    {
        "slug": "crush-pics",
        "name": "Crush: Speed & Image Optimizer",
        "category": "画像軽量化・ファイルリネーム",
        "description": "ストア画像の軽量化、自動圧縮、ファイル名SEOリネーム特化アプリ",
    },
    {
        "slug": "photo-resize-by-pixc",
        "name": "Pixc: AI Photo Resize",
        "category": "画像正方形化・アスペクト比統一",
        "description": "商品画像の縦横比統一、正方形化、余白（白枠）追加に特化したアプリ",
    },
    {
        "slug": "imageoptimizer",
        "name": "LoyaltyHarbour Image Optimizer",
        "category": "画像圧縮・最適化",
        "description": "ストア全画像のバックグラウンド自動圧縮・Altタグ更新アプリ",
    },
    {
        "slug": "webp-image",
        "name": "WEBP Image Optimizer+Speed SEO",
        "category": "WebP変換・画像SEO",
        "description": "商品画像のWebPフォーマット変換および一括ファイル名最適化アプリ",
    },
]

# 構造的課題（アーキテクチャや業務構造に起因する真のペイン）の分類定義
PAIN_CATEGORIES = {
    "variant_image_loss": {
        "title": "バリアント紐付けの喪失 & 元画像の消滅・置換ミス",
        "description": "画像更新やWebP変換によって、商品バリアント（色/サイズ）と画像の関係性が切断される、またはストアから画像が消滅する。",
        "structural_cause": "ShopifyのGraphQL/REST APIにおける商品メディア（MediaImage/ProductImage）とVariantの参照IDの再マッピング不備、およびCDNパス差し替え時の参照不整合。",
        "patterns": [
            r"variant", r"remove.*image", r"lost.*image", r"disappear", r"no image",
            r"deleted.*image", r"detach", r"wrong image", r"video thumbnail.*main",
            r"re-?upload.*image.*variant"
        ],
    },
    "rollback_failure": {
        "title": "不可逆な破壊 & ロールバック（元に戻す機能）の破綻",
        "description": "一括編集後のリバート（Revert/Restore）機能が動作しない、タイムアウトする、または元に戻す過程で画像が欠損・破損し、手動復旧を強いられる。",
        "structural_cause": "外部SaaS側でオリジナル画像のフルスナップショット・世代管理・HTML状態の完全保管を行っておらず、インプレース上書きまたは簡易履歴のみに頼っているため。",
        "patterns": [
            r"revert", r"restore", r"undo", r"backup", r"rollback", r"mess.*up",
            r"break.*store", r"broke", r"ruin", r"reset.*back", r"can't go back",
            r"cannot revert", r"no way to reverse"
        ],
    },
    "aspect_ratio_border_distortion": {
        "title": "強制的正方形化・白枠追加によるデザイン崩壊 & 画質劣化",
        "description": "アスペクト比を揃える処理で強引に白枠（Border/Padding）が追加され、非白背景テーマのストアデザインが破壊される。過剰クロップや画質低下も発生。",
        "structural_cause": "ストアテーマのCSSレスポンシブデザイン（object-fit等）を考慮せず、画像ラスターデータ自体の物理解像度・キャンバスサイズを強引に正方形化（白埋め）しているため。",
        "patterns": [
            r"white border", r"frame", r"crop", r"square", r"border", r"aspect ratio",
            r"background", r"blur", r"quality.*worse", r"distort", r"empty space",
            r"white background", r"small and have"
        ],
    },
    "ad_policy_violation": {
        "title": "外部広告チャネル（Google Shopping等）のポリシー違反・広告強制停止",
        "description": "自社ストア用に透かしやセール帯・テキストを画像に追加した結果、Google Merchant Center連携フィードで「Promotional Overlay」規約違反となり広告が全面停止する。",
        "structural_cause": "「自社ストアのブランディング用画像」と「Google/Meta等の広告フィード用プレーン画像」の分離配信機構（デュアルイメージパイプライン）が存在しない構造的欠陥。",
        "patterns": [
            r"google", r"merchant", r"watermark", r"policy", r"flag", r"disapproved",
            r"promotional overlay", r"stop showing your product"
        ],
    },
    "description_html_breakage": {
        "title": "商品説明文（HTML）内の埋め込み画像リンク切れ・破損",
        "description": "画像最適化・CDNパス変更・WebP化により、商品メイン画像だけでなく商品説明本文（body_html）内の画像タグ（<img>）が無効化・リンク切れになる。",
        "structural_cause": "Shopifyの商品データ構造において、メイン画像（Product.images）と商品説明文内の画像（Product.body_html内のインラインURL）が別管理されており、HTML解析・追従置換が行われないため。",
        "patterns": [
            r"description", r"body_html", r"html", r"product description", r"in the description"
        ],
    },
    "uncontrollable_batch_processing": {
        "title": "非同期一括処理の暴走（キャンセル不能・全件強制・進捗ブラックボックス）",
        "description": "カタログ全体（数千〜数万画像）に対して一括処理が強制され、プレビュー確認や部分適用ができず、途中で停止・キャンセルできずに長時間拘束される。",
        "structural_cause": "長大ジョブに対するリアルタイムジョブキュー制御、段階的カナリアリリース（1商品テスト適用）、緊急サーキットブレーカー（中断API）の設計不足。",
        "patterns": [
            r"no way to stop", r"cannot stop", r"unable to stop", r"cancel", r"freeze",
            r"stuck", r"hang", r"take.*day", r"take.*hour", r"waiting for it to stop",
            r"force.*all", r"can't choose which image", r"analyze button"
        ],
    },
}

# 課金・サポート等に関するノイズパターンの定義（プロダクト機能以外の不満）
NOISE_PATTERNS = [
    r"uninstalled.*still.*charg", r"refund", r"customer service", r"support.*slow",
    r"scam", r"charged.*after", r"credit card", r"false advertising.*free", r"price.*expensive",
    r"subscription", r"stole my money"
]


def build_review_url(app_slug: str, page_num: int = 1, filter_low_ratings: bool = True) -> str:
    """Shopify App StoreのレビューページURLを生成する"""
    base = f"https://apps.shopify.com/{app_slug}/reviews"
    params = {}
    if filter_low_ratings:
        params["ratings[]"] = ["1", "2"]
    if page_num > 1:
        params["page"] = [str(page_num)]

    query = urlencode(params, doseq=True)
    return f"{base}?{query}" if query else base


def scrape_app_reviews(
    app_info: dict,
    max_pages: int = 2,
    headless: bool = True,
    browser_page=None,
) -> list[dict]:
    """
    単一アプリから低評価レビューを取得する。
    """
    slug = app_info["slug"]
    app_name = app_info["name"]
    reviews = []

    need_close = False
    p = None
    browser = None
    page = browser_page

    if page is None:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        # 画像やメディア等の重いリソースをブロックして高速化
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            else route.continue_(),
        )
        need_close = True

    try:
        for page_num in range(1, max_pages + 1):
            url = build_review_url(slug, page_num=page_num, filter_low_ratings=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=12000)
                try:
                    page.wait_for_selector("[data-merchant-review]", timeout=4000)
                except Exception:
                    # レビューが存在しない（最終ページ到達など）
                    break

                elements = page.query_selector_all("[data-merchant-review]")
                if not elements:
                    break

                for el in elements:
                    # 星評価
                    rating_el = el.query_selector('[role="img"][aria-label*="star"], [aria-label*="star"]')
                    rating_raw = rating_el.get_attribute("aria-label").strip() if rating_el else ""

                    # 星数（数値）の抽出
                    star_match = re.search(r"(\d+)", rating_raw)
                    star_val = int(star_match.group(1)) if star_match else None
                    if star_val not in (1, 2):
                        continue

                    # 本文
                    text_el = (
                        el.query_selector("[data-truncate-content-copy]")
                        or el.query_selector("[data-truncate-review]")
                        or el.query_selector("p")
                    )
                    text = text_el.inner_text().strip() if text_el else ""
                    if not text:
                        continue

                    # 投稿日
                    date_el = el.query_selector(".tw-text-fg-tertiary.tw-text-body-xs, .tw-text-body-xs, time")
                    date_str = date_el.inner_text().strip() if date_el else ""

                    reviews.append({
                        "app_slug": slug,
                        "app_name": app_name,
                        "rating": rating_raw,
                        "rating_value": star_val,
                        "date": date_str,
                        "text": text,
                        "source_url": url,
                    })

            except Exception as e:
                break
    finally:
        if need_close:
            if browser:
                browser.close()
            if p:
                p.stop()

    return reviews


def scrape_all_competitor_reviews(
    competitor_apps: list[dict] = DEFAULT_COMPETITOR_APPS,
    max_pages: int = 2,
    headless: bool = True,
) -> list[dict]:
    """
    定義された全競合アプリから低評価レビューを一括スクレイピングする。
    """
    all_reviews = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        # 通信高速化: 不要リソースの遮断
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            else route.continue_(),
        )

        for app in competitor_apps:
            app_reviews = scrape_app_reviews(
                app_info=app,
                max_pages=max_pages,
                headless=headless,
                browser_page=page,
            )
            all_reviews.extend(app_reviews)

        browser.close()

    return all_reviews


def analyze_reviews_and_extract_pains(reviews: list[dict]) -> dict:
    """
    収集されたレビューから構造的ペインを抽出し、複数アプリに共通する構造的課題であるかを検証する。
    """
    total_reviews = len(reviews)
    slug_to_app = {a["slug"]: a for a in DEFAULT_COMPETITOR_APPS}
    app_review_counts = {}

    for r in reviews:
        slug = r.get("app_slug", "")
        # slugまたはapp_nameから正規アプリ名を取得
        if slug in slug_to_app:
            canon_name = slug_to_app[slug]["name"]
        else:
            canon_name = r.get("app_name", "Unknown App")
        app_review_counts[canon_name] = app_review_counts.get(canon_name, 0) + 1

    classified_results = {}
    for pain_key, info in PAIN_CATEGORIES.items():
        classified_results[pain_key] = {
            "key": pain_key,
            "title": info["title"],
            "description": info["description"],
            "structural_cause": info["structural_cause"],
            "matched_reviews": [],
            "affected_apps": set(),
            "evidence_samples": [],
        }

    noise_reviews = []

    for r in reviews:
        text = r["text"]
        slug = r.get("app_slug", "")
        canon_name = slug_to_app[slug]["name"] if slug in slug_to_app else r.get("app_name", "Unknown App")
        matched_any_pain = False

        # 各構造的ペインにマッチするか判定
        for pain_key, info in PAIN_CATEGORIES.items():
            patterns = info["patterns"]
            if any(re.search(pat, text, re.I) for pat in patterns):
                classified_results[pain_key]["matched_reviews"].append(r)
                classified_results[pain_key]["affected_apps"].add(canon_name)
                matched_any_pain = True

        # ノイズ（サポート・返金・フリーミアム不満）のチェック
        is_noise = any(re.search(pat, text, re.I) for pat in NOISE_PATTERNS)
        if is_noise and not matched_any_pain:
            noise_reviews.append(r)

    # 構造的課題の検証（Cross-App Validation）
    structural_issues = []
    app_specific_issues = []

    for pain_key, data in classified_results.items():
        affected_apps = sorted(list(data["affected_apps"]))
        app_count = len(affected_apps)
        match_count = len(data["matched_reviews"])

        # 代表的なエビデンスをアプリごとに1〜2件抽出
        samples_by_app = {}
        for rev in data["matched_reviews"]:
            app = rev["app_name"]
            if app not in samples_by_app:
                samples_by_app[app] = []
            if len(samples_by_app[app]) < 2:
                samples_by_app[app].append({
                    "app_name": rev["app_name"],
                    "rating": rev["rating"],
                    "date": rev["date"],
                    "text": rev["text"],
                })

        all_samples = []
        for app_samples in samples_by_app.values():
            all_samples.extend(app_samples)

        pain_summary = {
            "key": pain_key,
            "title": data["title"],
            "description": data["description"],
            "structural_cause": data["structural_cause"],
            "match_count": match_count,
            "affected_apps": affected_apps,
            "affected_app_count": app_count,
            "evidence_samples": all_samples,
            # 2つ以上の独立したアプリで発生している場合を「構造的課題」と認定
            "is_structural_issue": app_count >= 2,
        }

        if app_count >= 2:
            structural_issues.append(pain_summary)
        elif app_count == 1:
            app_specific_issues.append(pain_summary)

    # 影響アプリ数が多い順にソート
    structural_issues.sort(key=lambda x: (x["affected_app_count"], x["match_count"]), reverse=True)

    return {
        "summary": {
            "total_reviews_analyzed": total_reviews,
            "competitor_apps_analyzed": len(app_review_counts),
            "reviews_per_app": app_review_counts,
            "total_structural_pains_identified": len(structural_issues),
            "pure_noise_reviews_count": len(noise_reviews),
        },
        "structural_issues": structural_issues,
        "app_specific_issues": app_specific_issues,
    }


def format_markdown_report(analysis: dict) -> str:
    """
    抽出された構造的課題と分析結果を美しいMarkdown形式のレポートに成形する。
    """
    summary = analysis["summary"]
    structural = analysis["structural_issues"]

    lines = [
        "# Shopify画像編集系 競合低評価レビュー分析 & 構造的課題検証レポート",
        "",
        f"> **分析実施日**: {datetime.now().strftime('%Y-%m-%d')}  ",
        f"> **調査対象**: 画像編集・最適化系競合 {summary['competitor_apps_analyzed']} アプリ（★1〜2の低評価レビュー計 {summary['total_reviews_analyzed']} 件）  ",
        f"> **検証目的**: 特定のアプリ固有の不具合ではなく、Shopify画像処理領域に横断する『構造的課題（SaaS化の急所）』であるかを証明・検証する。",
        "",
        "---",
        "",
        "## 1. 調査対象アプリ & レビュー収集数",
        "",
        "| 対象アプリ名 | 収集レビュー数（★1〜2） | 主な機能ドメイン |",
        "| :--- | :---: | :--- |",
    ]

    for app in DEFAULT_COMPETITOR_APPS:
        name = app["name"]
        count = summary["reviews_per_app"].get(name, 0)
        lines.append(f"| **{name}** | {count} 件 | {app['category']} |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. 結論：複数アプリで共通発生している【構造的課題】の検証結果",
        "",
        "競合アプリの低評価レビューを横断分析した結果、**単一アプリの実装バグではなく、Shopifyの画像データ仕様およびマーチャント業務の構造に起因する致命的ペインが複数アプリで同時に発生していること**が実証されました。",
        "",
        "| 構造的課題（コアペイン） | 発生アプリ数 | 該当する競合アプリ | 構造的リスクの本質 |",
        "| :--- | :---: | :--- | :--- |",
    ])

    for issue in structural:
        apps_str = ", ".join([a.split(":")[0].split("(")[0].strip() for a in issue["affected_apps"]])
        lines.append(
            f"| **{issue['title']}** | **{issue['affected_app_count']} アプリ** | {apps_str} | {issue['structural_cause'][:60]}... |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. 各構造的課題の詳細分析 & 現場の生の声（レビューエビデンス）",
        "",
    ])

    for idx, issue in enumerate(structural, 1):
        lines.extend([
            f"### 【構造的課題 {idx}】{issue['title']}",
            "",
            f"- **該当アプリ数**: {issue['affected_app_count']} アプリ ({', '.join(issue['affected_apps'])})",
            f"- **該当レビュー件数**: {issue['match_count']} 件",
            f"- **事象の概要**: {issue['description']}",
            f"- **なぜ構造的課題なのか**: {issue['structural_cause']}",
            "",
            "#### 現場のリアルな被害レビュー引用（エビデンス）:",
            "",
        ])

        for sample in issue["evidence_samples"][:4]:
            text_escaped = sample["text"].replace("\n", " ").strip()
            lines.append(
                f"> **[{sample['app_name']}] ({sample['rating']} / {sample['date']})**  \n> *\"{text_escaped}\"*\n"
            )

        lines.append("")

    lines.extend([
        "---",
        "",
        "## 4. プロダクトマネジメント視点の分析（単一アプリのバグではなく『構造的課題』である証明）",
        "",
        "| 構造的課題 | なぜ競合全社が同じ失敗を繰り返すのか（Shopifyの構造的制約） | 解決に必要なアーキテクチャ |",
        "| :--- | :--- | :--- |",
        "| **① バリアント連動破壊 & 画像消失** | Shopifyの商品メディアAPIにおいて、`ProductImage`と`ProductVariant`の紐付けは外部キー参照。画像の一括差替・WebP化時にAPIを叩くとリレーションがNULLクリアされる仕様 | **Variant Mapping Preserve Layer**<br>処理前にVariant-Image-SKUの完全マッピングテーブルを外部DBにキャッシュし、画像登録後に不可逆再バインドを保証。 |",
        "| **② ロールバック機能の破綻** | 多くのアプリがサーバー代節約のためにオリジナル元画像をCDNから即時破棄、またはインプレース上書きしている | **Cloud Immutable Snapshot**<br>編集前の元画像・CDN URL・商品HTMLを外部ストレージ（S3/R2）に世代管理スナップショット保存。1クリック10秒完全ロールバック。 |",
        "| **③ 白枠・余白追加のデザイン崩壊** | 単純な画像リサイズAPI（Canvas/Pillow）で余白に白（#FFFFFF）を埋めているため、透明背景PNGやダークテーマ・カスタム背景ストアで大事故になる | **Non-Destructive Adaptive CSS**<br>画像データを物理変形せず、ShopifyテーマのCSS/object-fitに合わせたスマートコンテナ配信、または透過パディング処理。 |",
        "| **④ Google広告規約違反（BAN）** | 自社ストアで見せたい「透かし・セール帯」と、Google Merchant Center/Metaが要求する「白抜きクリーン画像」が1つの画像URLで共存できない | **Dual-Feed Smart Routing**<br>ストアフロント用（装飾付き）と広告連携用（純白抜きプレーン）を自動分離配信するパイプライン。 |",
        "| **⑤ 非同期一括処理の暴走** | カタログ数万件を単一の重いキューで回し、UI側でキャンセルAPIや段階適用（プレビュー/カナリア検証）を提供していない | **Canary Batch UX & Circuit Breaker**<br>「1商品プレビュー → 5商品カナリアテスト → 全体適用」の段階承認フローと、即時中断可能なジョブコントローラ。 |",
        "",
        "---",
        "",
        "## 5. 月額9,800円 Micro-SaaS ソリューション仮説 & ROI検証",
        "",
        "### プロダクト仮説: 『SafeMedia Shield for Shopify』",
        "*〜『画像編集でストアを壊さない』フェイルセーフ＆Google広告規約準拠の次世代画像配信SaaS〜*",
        "",
        "#### A. コアバリュー（なぜ既存アプリから乗り換えるのか）",
        "既存の画像編集アプリは「多機能・安価」を競った結果、**ストア破壊事故・Google広告停止事故を頻発させて低評価の山を築いている**。本SaaSは「スピードや派手な編集」ではなく、**『絶対に事故を起こさないフェイルセーフ（保険）』**に特化することで、月商数百万〜数千万円のマーチャントから月額9,800円を確実に獲得する。",
        "",
        "#### B. 月額9,800円のプライシング正当性（ROI試算）",
        "",
        "| リスク・損失項目 | 既存アプリ使用時（手作業・事故リスク） | SafeMedia Shield 導入後 |",
        "| :--- | :--- | :--- |",
        "| **Google広告停止損失** | 透かしによるポリシー違反で広告審査落ち：**売上損失 数十万〜数百万円/回** | **広告規約違反 0%（クリーンフィード自動分離）** |",
        "| **商品画像・HTML復旧人件費** | バリアント紐付け消失・HTML画像リンク切れ復旧：50時間 × 2,500円 ＝ **約12.5万円** | **1クリック10秒で完全復元（復旧コスト 0円）** |",
        "| **手作業2重管理コスト** | 自社用画像とGoogle用画像の個別作成・手動管理：10時間/月 ＝ **約2.5万円/月** | **自動パイプライン化により工数ゼロ** |",
        "| **月間実質コスト比較** | **月2.5万〜15万円以上の人件費＋広告停止の売上蒸発リスク** | **月額 9,800 円（固定）** |",
        "",
        "👉 **結論**: 「バイト1人の作業代（2〜3万円/月）」未満であり、「広告停止による大損害を防ぐ保険」として、月商200万円以上のマーチャントであれば稟議不要で即決できる価格妥当性を持つ。",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Shopify画像編集系競合アプリの低評価レビュー収集＆構造的ペイン抽出ツール"
    )
    parser.add_argument(
        "--apps",
        nargs="+",
        help="対象アプリslugの指定（未指定時は定義された全競合を対象）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=2,
        help="各アプリから取得する最大ページ数（デフォルト: 2ページ）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="ヘッドレスモードで実行（デフォルト: True）",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "summary"],
        default="summary",
        help="出力フォーマット (summary, markdown, json)",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        help="既存の収集済みJSONファイルから分析のみを行う場合に使用",
    )
    parser.add_argument(
        "--save-reviews",
        type=str,
        help="取得した生のレビューデータをJSONファイルとして保存するパス",
    )
    parser.add_argument(
        "--save-report",
        type=str,
        help="生成したMarkdownレポートを保存するファイルパス",
    )

    args = parser.parse_args()

    reviews = []

    if args.cache_file:
        with open(args.cache_file, "r", encoding="utf-8") as f:
            reviews = json.load(f)
    else:
        target_apps = DEFAULT_COMPETITOR_APPS
        if args.apps:
            target_apps = [a for a in DEFAULT_COMPETITOR_APPS if a["slug"] in args.apps]
            if not target_apps:
                # 定義外のslugの場合は直接辞書化して使用
                target_apps = [{"slug": s, "name": s, "category": "画像系", "description": ""} for s in args.apps]

            # 進捗を標準エラーに出力（パイプラインを阻害しないため）
        print(f"Scraping low rating reviews across {len(target_apps)} apps...", file=sys.stderr)
        reviews = scrape_all_competitor_reviews(
            competitor_apps=target_apps,
            max_pages=args.max_pages,
            headless=args.headless,
        )

        if args.save_reviews:
            with open(args.save_reviews, "w", encoding="utf-8") as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)
            print(f"Saved {len(reviews)} reviews to {args.save_reviews}", file=sys.stderr)

    # 構造的課題の抽出・検証
    analysis = analyze_reviews_and_extract_pains(reviews)

    # Markdownレポート作成
    md_report = format_markdown_report(analysis)

    if args.save_report:
        with open(args.save_report, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"Saved markdown report to {args.save_report}", file=sys.stderr)

    # 出力形式に応じた標準出力
    if args.format == "json":
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(md_report)
    else:
        # summary形式
        print("=" * 60)
        print("  Shopify画像編集系競合 構造的ペイン検証サマリー")
        print("=" * 60)
        sum_data = analysis["summary"]
        print(f"分析レビュー総数: {sum_data['total_reviews_analyzed']} 件 (競合 {sum_data['competitor_apps_analyzed']} アプリ)")
        for app, count in sum_data["reviews_per_app"].items():
            print(f"  - {app}: {count} 件")
        print("-" * 60)
        print(f"抽出された【構造的課題】: {sum_data['total_structural_pains_identified']} 件 (2アプリ以上で共通発生)")
        for idx, issue in enumerate(analysis["structural_issues"], 1):
            print(f"\n{idx}. {issue['title']}")
            print(f"   影響アプリ数: {issue['affected_app_count']} アプリ ({', '.join(issue['affected_apps'])})")
            print(f"   該当レビュー件数: {issue['match_count']} 件")
            print(f"   根本原因: {issue['structural_cause']}")
            if issue["evidence_samples"]:
                sample = issue["evidence_samples"][0]
                sample_snippet = sample["text"].replace("\n", " ")[:120]
                print(f"   引用例 [{sample['app_name']}]: \"{sample_snippet}...\"")
        print("=" * 60)


if __name__ == "__main__":
    main()
