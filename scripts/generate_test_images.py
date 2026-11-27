import os
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int):
    # macOS/Linux/Windowsの標準フォントを探索、なければデフォルト
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/Library/Fonts/Arial.ttf",              # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
        "C:\\Windows\\Fonts\\arial.ttf"          # Windows
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def apply_corner_watermark(base_img: Image.Image, text: str = "CONFIDENTIAL") -> Image.Image:
    """レベル1想定: 単色背景・隅に配置される半透明の透かし"""
    img = base_img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    font = get_font(int(img.height * 0.04))
    # 右下に配置 (不透明度 約40%)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    position = (img.width - text_w - 20, img.height - text_h - 20)
    
    draw.text(position, text, fill=(100, 100, 100, 100), font=font)
    return Image.alpha_composite(img, overlay).convert("RGB")

def apply_sale_banner(base_img: Image.Image, text: str = "20% OFF") -> Image.Image:
    """レベル2想定: 画像端にかかるセール帯バナー（不透明矩形＋白文字）"""
    img = base_img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    banner_height = int(img.height * 0.08)
    banner_y = int(img.height * 0.15)
    
    # 赤いバナー帯
    draw.rectangle([(0, banner_y), (img.width, banner_y + banner_height)], fill=(220, 38, 38, 230))
    
    font = get_font(int(banner_height * 0.6))
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_pos = ((img.width - text_w) // 2, banner_y + (banner_height - text_h) // 2)
    
    draw.text(text_pos, text, fill=(255, 255, 255, 255), font=font)
    return Image.alpha_composite(img, overlay).convert("RGB")

def apply_center_overlay(base_img: Image.Image, text: str = "LIMITED SALE") -> Image.Image:
    """レベル3想定: 商品領域に大きく重なる斜め半透明テキスト"""
    img = base_img.convert("RGBA")
    
    # テキストレイヤーを独立して作成し回転
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    font = get_font(int(img.height * 0.08))
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((img.width - text_w) // 2, (img.height - text_h) // 2), text, fill=(255, 0, 0, 140), font=font)
    
    rotated_txt = txt_layer.rotate(30, resample=Image.Resampling.BICUBIC)
    return Image.alpha_composite(img, rotated_txt).convert("RGB")

def process_image(input_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    with Image.open(input_path) as img:
        # レベル1
        img_lvl1 = apply_corner_watermark(img, text="© STORE NAME")
        img_lvl1.save(os.path.join(output_dir, f"{base_name}_lvl1_corner.jpg"), quality=95)
        
        # レベル2
        img_lvl2 = apply_sale_banner(img, text="SAVE 20% NOW")
        img_lvl2.save(os.path.join(output_dir, f"{base_name}_lvl2_banner.jpg"), quality=95)
        
        # レベル3
        img_lvl3 = apply_center_overlay(img, text="SPECIAL OFFER")
        img_lvl3.save(os.path.join(output_dir, f"{base_name}_lvl3_center.jpg"), quality=95)

if __name__ == "__main__":
    # 使用例: raw_images または ./shopify_samples ディレクトリ内の画像を処理
    sample_dir = "./shopify_samples"
    output_dir = "./synthetic_tests"
    processed = 0

    if os.path.isdir(sample_dir):
        for fname in sorted(os.listdir(sample_dir)):
            if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                process_image(os.path.join(sample_dir, fname), output_dir=output_dir)
                processed += 1

    input_file = "raw_sample.jpg"  # 単体テスト対象のクリーン画像パス
    if os.path.exists(input_file):
        process_image(input_file, output_dir=output_dir)
        processed += 1

    if processed > 0:
        print(f"合成テスト画像の生成が完了しました（元画像 {processed} 枚 × 3レベル = 計 {processed * 3} 枚 -> {output_dir}）。")
    else:
        print(f"対象ファイルが見つかりません: {sample_dir} または {input_file}")

