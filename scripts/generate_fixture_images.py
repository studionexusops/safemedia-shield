#!/usr/bin/env python3
"""
Generate Shopify Test Fixture Images for AdFeed Clean
Produces the 5 required test images for App Review Screencast & E2E Validation:
1. product1_canary_sale_banner.jpg (The Complete Snowboard - Canary Test)
2. product2_var1_sunset_orange_sale.jpg (Multi-Variant: 152cm / Sunset Orange)
3. product2_var2_arctic_blue_50off.jpg (Multi-Variant: 156cm / Arctic Blue)
4. product2_var3_stealth_black_freeship.jpg (Multi-Variant: 160cm / Stealth Black)
5. product3_control_clean_white.jpg (Minimalist Pure Snowboard - Control Test)
"""

import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "test_fixtures", "products")
BRAIN_DIR = "/Users/yusuke/.gemini/antigravity/brain/84192e1b-37c6-4be6-8572-cedff2e15826"

PATH_CANARY_BASE = os.path.join(BRAIN_DIR, "modern_freestyle_snowboard_1793459652288.jpg")
PATH_ORANGE_BASE = os.path.join(BRAIN_DIR, "sunset_orange_snowboard_1793459759875.jpg")
PATH_BLUE_BASE   = os.path.join(BRAIN_DIR, "arctic_blue_snowboard_1793459775779.jpg")
PATH_BLACK_BASE  = os.path.join(BRAIN_DIR, "stealth_black_snowboard_1793459795215.jpg")

def get_font(size: int, bold: bool = True):
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def apply_top_sale_banner(img: Image.Image, main_text: str = "SALE / 20% OFF") -> Image.Image:
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = canvas.size

    banner_height = int(h * 0.08)
    banner_y = int(h * 0.05)

    # Shadow
    draw.rectangle([(0, banner_y + 4), (w, banner_y + banner_height + 4)], fill=(0, 0, 0, 50))
    # Crimson Red banner (#E11D48)
    draw.rectangle([(0, banner_y), (w, banner_y + banner_height)], fill=(225, 29, 72, 245))

    # Gold accent border lines (#FBBF24)
    border_h = 4
    draw.rectangle([(0, banner_y), (w, banner_y + border_h)], fill=(251, 191, 36, 255))
    draw.rectangle([(0, banner_y + banner_height - border_h), (w, banner_y + banner_height)], fill=(251, 191, 36, 255))

    font = get_font(int(banner_height * 0.52), bold=True)
    bbox = draw.textbbox((0, 0), main_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((w - tw) // 2, banner_y + (banner_height - th) // 2 - 2)

    # Text shadow + crisp white text
    draw.text((pos[0] + 2, pos[1] + 2), main_text, fill=(100, 0, 20, 150), font=font)
    draw.text(pos, main_text, fill=(255, 255, 255, 255), font=font)

    combined = Image.alpha_composite(canvas, overlay)
    return combined.convert("RGB")

def apply_circular_badge(img: Image.Image, main_text: str, sub_text: str, bg_color: tuple, outline_color: tuple, pos_ratio: tuple) -> Image.Image:
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = canvas.size

    radius = int(min(w, h) * 0.115)
    cx, cy = int(w * pos_ratio[0]), int(h * pos_ratio[1])

    # Soft drop shadow
    draw.ellipse([(cx - radius + 6, cy - radius + 6), (cx + radius + 6, cy + radius + 6)], fill=(0, 0, 0, 60))
    # Main badge background
    draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], fill=bg_color)
    # Inner border
    inner_r = radius - 7
    draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], outline=outline_color, width=3)

    font_main = get_font(int(radius * 0.44), bold=True)
    font_sub = get_font(int(radius * 0.25), bold=True)

    bbox_main = draw.textbbox((0, 0), main_text, font=font_main)
    m_w, m_h = bbox_main[2] - bbox_main[0], bbox_main[3] - bbox_main[1]

    if sub_text:
        bbox_sub = draw.textbbox((0, 0), sub_text, font=font_sub)
        s_w, s_h = bbox_sub[2] - bbox_sub[0], bbox_sub[3] - bbox_sub[1]

        total_h = m_h + s_h + 6
        p_main = (cx - m_w // 2, cy - total_h // 2)
        p_sub = (cx - s_w // 2, p_main[1] + m_h + 6)

        draw.text((p_main[0] + 1, p_main[1] + 1), main_text, fill=(0, 0, 0, 80), font=font_main)
        draw.text(p_main, main_text, fill=(255, 255, 255, 255), font=font_main)

        draw.text((p_sub[0] + 1, p_sub[1] + 1), sub_text, fill=(0, 0, 0, 80), font=font_sub)
        draw.text(p_sub, sub_text, fill=(255, 255, 255, 240), font=font_sub)
    else:
        p_main = (cx - m_w // 2, cy - m_h // 2)
        draw.text((p_main[0] + 1, p_main[1] + 1), main_text, fill=(0, 0, 0, 80), font=font_main)
        draw.text(p_main, main_text, fill=(255, 255, 255, 255), font=font_main)

    combined = Image.alpha_composite(canvas, overlay)
    return combined.convert("RGB")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Product 1: Canary Test (SALE / 20% OFF red banner)
    print("Generating Product 1: The Complete Snowboard (Canary Test)...")
    img_canary_base = Image.open(PATH_CANARY_BASE)
    p1 = apply_top_sale_banner(img_canary_base, "SALE / 20% OFF")
    p1_path = os.path.join(OUTPUT_DIR, "product1_canary_sale_banner.jpg")
    p1.save(p1_path, quality=95)
    print(f" -> Saved: {p1_path}")

    # 2. Product 2 - Variant A: 152cm / Sunset Orange (SALE Badge)
    print("Generating Product 2 - Var A: Sunset Orange (SALE Badge)...")
    img_orange_base = Image.open(PATH_ORANGE_BASE)
    p2_a = apply_circular_badge(
        img_orange_base,
        main_text="SALE",
        sub_text="SPECIAL",
        bg_color=(234, 88, 12, 250), # Vibrant Orange #EA580C
        outline_color=(254, 215, 170, 240),
        pos_ratio=(0.22, 0.18)
    )
    p2_a_path = os.path.join(OUTPUT_DIR, "product2_var1_sunset_orange_sale.jpg")
    p2_a.save(p2_a_path, quality=95)
    print(f" -> Saved: {p2_a_path}")

    # 2. Product 2 - Variant B: 156cm / Arctic Blue (50% OFF Badge)
    print("Generating Product 2 - Var B: Arctic Blue (50% OFF Badge)...")
    img_blue_base = Image.open(PATH_BLUE_BASE)
    p2_b = apply_circular_badge(
        img_blue_base,
        main_text="50% OFF",
        sub_text="LIMITED",
        bg_color=(2, 132, 199, 250), # Arctic Blue #0284C7
        outline_color=(186, 230, 253, 240),
        pos_ratio=(0.78, 0.18)
    )
    p2_b_path = os.path.join(OUTPUT_DIR, "product2_var2_arctic_blue_50off.jpg")
    p2_b.save(p2_b_path, quality=95)
    print(f" -> Saved: {p2_b_path}")

    # 2. Product 2 - Variant C: 160cm / Stealth Black (FREE SHIPPING Badge)
    print("Generating Product 2 - Var C: Stealth Black (FREE SHIPPING Badge)...")
    img_black_base = Image.open(PATH_BLACK_BASE)
    p2_c = apply_circular_badge(
        img_black_base,
        main_text="FREE",
        sub_text="SHIPPING",
        bg_color=(15, 23, 42, 250), # Stealth Navy/Black #0F172A
        outline_color=(148, 163, 184, 240),
        pos_ratio=(0.22, 0.18)
    )
    p2_c_path = os.path.join(OUTPUT_DIR, "product2_var3_stealth_black_freeship.jpg")
    p2_c.save(p2_c_path, quality=95)
    print(f" -> Saved: {p2_c_path}")

    # 3. Product 3: Minimalist Pure Snowboard (Control Test - Pure Clean White)
    print("Generating Product 3: Minimalist Pure Snowboard (Control Test)...")
    # Base orange, blue or black without badge, or canary base without banner
    # Let's use canary base without any banner (clean minimalist board with pure white studio background)
    p3 = img_canary_base.convert("RGB")
    p3_path = os.path.join(OUTPUT_DIR, "product3_control_clean_white.jpg")
    p3.save(p3_path, quality=95)
    print(f" -> Saved: {p3_path}")

    print("\n--- Summary of Generated Fixtures ---")
    for f in [p1_path, p2_a_path, p2_b_path, p2_c_path, p3_path]:
        print(f"File: {os.path.basename(f)} ({os.path.getsize(f)/1024:.1f} KB)")

if __name__ == "__main__":
    main()
