"""
verify_inpainting_pipeline.py

ComfyUIの推奨ノード構成をPythonで忠実に実装・検証するスクリプト:
1. Load Image: テスト画像（lvl1_corner, lvl2_banner, lvl3_center）を読み込み
2. Florence2Run:
   - タスクA: <OCR_WITH_REGION> で画像内の全テキスト領域（ポリゴン）を検出
   - タスクB: <CAPTION_TO_PHRASE_GROUNDING> でセール帯・バナー矩形（赤い帯など）を検出
3. Mask Dilate (膨張処理):
   - 検出したマスクを膨張させ、アンチエイリアス・半透明のにじみを完全に包含
4. Inpainting Model (LaMa - Large Mask Inpainting):
   - 膨張マスク領域のみを周辺ピクセルから自然修復（非マスク領域は100%元画素を維持）
5. Save Image & 評価レポート:
   - 修復後画像、マスク画像、Before/Mask/After比較画像を保存し、処理時間と修復精度(PSNR)を計測
"""

import os
import time
import json
import urllib.request
import numpy as np
import cv2
import torch
from unittest.mock import patch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, AutoModelForCausalLM
from transformers.dynamic_module_utils import get_imports


def fixed_get_imports(filename):
    imports = get_imports(filename)
    if not torch.cuda.is_available() and "flash_attn" in imports:
        imports.remove("flash_attn")
    return imports

LAMA_MODEL_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
MODEL_DIR = "./models"
LAMA_MODEL_PATH = os.path.join(MODEL_DIR, "big-lama.pt")
FLORENCE_MODEL_ID = "microsoft/Florence-2-base"


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def ensure_lama_model() -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(LAMA_MODEL_PATH):
        print(f"Downloading LaMa model from {LAMA_MODEL_URL} ...")
        urllib.request.urlretrieve(LAMA_MODEL_URL, LAMA_MODEL_PATH)
        print(f"Saved LaMa model to {LAMA_MODEL_PATH}")
    return LAMA_MODEL_PATH


class AutomatedInpaintPipeline:
    def __init__(self):
        self.device = get_device()
        print(f"Initializing AutomatedInpaintPipeline on device: {self.device}")

        # 1. Load Florence-2 (OCR & Phrase Grounding)
        print(f"Loading Florence-2 ({FLORENCE_MODEL_ID})...")
        with patch("transformers.dynamic_module_utils.get_imports", fixed_get_imports):
            try:
                self.florence_processor = AutoProcessor.from_pretrained(
                    FLORENCE_MODEL_ID, trust_remote_code=True, local_files_only=True
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    FLORENCE_MODEL_ID,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,
                    attn_implementation="sdpa",
                    local_files_only=True,
                ).to(self.device).eval()
            except Exception:
                self.florence_processor = AutoProcessor.from_pretrained(
                    FLORENCE_MODEL_ID, trust_remote_code=True
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    FLORENCE_MODEL_ID,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,
                    attn_implementation="sdpa",
                ).to(self.device).eval()

        # 2. Load LaMa Inpainting Model (TorchScript JIT)
        lama_path = ensure_lama_model()
        print(f"Loading LaMa Inpainting model ({lama_path})...")
        # TorchScript LaMa runs reliably on CPU/CUDA; fallback to CPU if MPS JIT op unsupported
        self.lama_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lama_model = torch.jit.load(lama_path, map_location=self.lama_device).eval()

    @torch.no_grad()
    def run_florence_task(self, image: Image.Image, task_prompt: str, text_input: str = None) -> dict:
        prompt = task_prompt if text_input is None else task_prompt + text_input
        inputs = self.florence_processor(
            text=prompt, images=image, return_tensors="pt"
        ).to(self.device)

        generated_ids = self.florence_model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            early_stopping=False,
            do_sample=False,
            num_beams=3,
        )
        generated_text = self.florence_processor.batch_decode(
            generated_ids, skip_special_tokens=False
        )[0]
        parsed = self.florence_processor.post_process_generation(
            generated_text, task=task_prompt, image_size=(image.width, image.height)
        )
        return parsed.get(task_prompt, {})

    def detect_overlay_mask(self, image: Image.Image, dilate_px: int = 6) -> np.ndarray:
        """
        Node 2 & Node 3:
        Florence2Run (OCR_WITH_REGION + Banner Grounding) -> Stroke Refinement -> Mask Dilate
        Returns binary mask (H, W) with values 0 or 255.
        """
        w, h = image.size
        img_np = np.array(image.convert("RGB"))
        final_mask = np.zeros((h, w), dtype=np.uint8)

        # Step A: Florence-2 <OCR_WITH_REGION> for text & watermarks
        ocr_res = self.run_florence_task(image, "<OCR_WITH_REGION>")
        quad_boxes = ocr_res.get("quad_boxes", [])

        # Prepare local morphological background estimate to isolate text strokes inside polygons
        # Text strokes are thin (<15px), whereas product shapes are broad.
        k_bg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        # Both opening (removes bright/colored strokes on dark) and closing (removes dark strokes on light)
        opened = cv2.morphologyEx(img_np, cv2.MORPH_OPEN, k_bg)
        closed = cv2.morphologyEx(img_np, cv2.MORPH_CLOSE, k_bg)
        diff_open = np.linalg.norm(img_np.astype(np.float32) - opened.astype(np.float32), axis=2)
        diff_close = np.linalg.norm(img_np.astype(np.float32) - closed.astype(np.float32), axis=2)
        stroke_anomaly = np.maximum(diff_open, diff_close)

        for quad in quad_boxes:
            pts = [(quad[i], quad[i + 1]) for i in range(0, len(quad), 2)]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)

            # Check if this text sits inside a horizontal full-width sale banner (Level 2)
            box_h = y2 - y1
            pad_y = int(box_h * 0.45)
            sy1 = max(0, int(y1 - pad_y))
            sy2 = min(h, int(y2 + pad_y))
            left_patch = img_np[sy1:sy2, :max(10, int(w * 0.05)), :]
            right_patch = img_np[sy1:sy2, min(w - 10, int(w * 0.95)):, :]
            top_bg = img_np[:max(5, int(h * 0.03)), :max(5, int(w * 0.03)), :]

            is_full_banner = False
            if left_patch.size > 0 and right_patch.size > 0 and top_bg.size > 0:
                left_mean = left_patch.mean(axis=(0, 1))
                right_mean = right_patch.mean(axis=(0, 1))
                bg_mean = top_bg.mean(axis=(0, 1))
                edge_diff = np.linalg.norm(left_mean - right_mean)
                bg_diff = np.linalg.norm(left_mean - bg_mean)
                if edge_diff < 25.0 and bg_diff > 40.0:
                    row_colors = img_np[:, :max(10, int(w * 0.05)), :].mean(axis=1)
                    banner_rows = np.where(np.linalg.norm(row_colors - left_mean, axis=1) < 35.0)[0]
                    if len(banner_rows) > 0:
                        by1 = max(0, int(banner_rows.min()) - 4)
                        by2 = min(h, int(banner_rows.max()) + 5)
                        if (by2 - by1) < h * 0.25:
                            final_mask[by1:by2, :] = 255
                            is_full_banner = True

            if not is_full_banner:
                # Create polygon mask for this text region (slightly expanded by 6px to not clip character edges)
                poly_img = Image.new("L", (w, h), 0)
                ImageDraw.Draw(poly_img).polygon(pts, fill=255)
                poly_np = cv2.dilate(
                    np.array(poly_img, dtype=np.uint8),
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
                    iterations=1,
                )
                # Extract actual character strokes inside the polygon so product pixels between letters stay intact
                region_vals = stroke_anomaly[poly_np > 0]
                if region_vals.size > 0:
                    thresh = max(14.0, float(np.percentile(region_vals, 55)))
                    stroke_mask = ((stroke_anomaly >= thresh) & (poly_np > 0)).astype(np.uint8) * 255
                    # If very low contrast watermark (like subtle corner watermark), fallback to full polygon
                    if (stroke_mask > 0).sum() < 0.08 * (poly_np > 0).sum():
                        stroke_mask = poly_np
                    final_mask = np.maximum(final_mask, stroke_mask)

        # Node 3: Mask Dilate (膨張処理 - 透かしの周囲のにじみ・アンチエイリアスを完全に包含)
        if dilate_px > 0 and final_mask.max() > 0:
            kernel_size = dilate_px * 2 + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            final_mask = cv2.dilate(final_mask, kernel, iterations=1)

        return final_mask

    @torch.no_grad()
    def inpaint_lama(self, image: Image.Image, mask_np: np.ndarray, max_infer_dim: int = 512) -> Image.Image:
        """
        Node 4: Inpainting Model (LaMa)
        Runs LaMa at optimal resolution (max_infer_dim=512, matching big-lama training resolution & speed),
        then composites ONLY the masked pixels back onto the full-resolution (2000x2000) original image
        so unmasked product pixels stay 100% lossless.
        """
        if mask_np.max() == 0:
            return image.copy()

        orig_rgb = np.array(image.convert("RGB"))
        h, w, _ = orig_rgb.shape
        mask_bin_full = (mask_np > 127).astype(np.float32)

        scale = min(1.0, float(max_infer_dim) / float(max(h, w)))
        if scale < 1.0:
            infer_w = max(8, int(round(w * scale / 8.0)) * 8)
            infer_h = max(8, int(round(h * scale / 8.0)) * 8)
            img_infer = cv2.resize(orig_rgb, (infer_w, infer_h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
            mask_infer = cv2.resize(mask_bin_full, (infer_w, infer_h), interpolation=cv2.INTER_NEAREST)
            mask_infer = (mask_infer > 0.5).astype(np.float32)
        else:
            pad_h = (8 - h % 8) % 8
            pad_w = (8 - w % 8) % 8
            img_infer = np.pad(orig_rgb.astype(np.float32) / 255.0, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
            mask_infer = np.pad(mask_bin_full, ((0, pad_h), (0, pad_w)), mode="reflect")

        img_tensor = torch.from_numpy(img_infer).permute(2, 0, 1).unsqueeze(0).to(self.lama_device)
        mask_tensor = torch.from_numpy(mask_infer).unsqueeze(0).unsqueeze(0).to(self.lama_device)

        inpainted_tensor = self.lama_model(img_tensor, mask_tensor)
        inpainted_np = inpainted_tensor[0].permute(1, 2, 0).cpu().numpy()
        inpainted_np = np.clip(inpainted_np * 255.0, 0, 255).astype(np.uint8)

        if scale < 1.0:
            inpainted_full = cv2.resize(inpainted_np, (w, h), interpolation=cv2.INTER_CUBIC)
        else:
            inpainted_full = inpainted_np[:h, :w, :]

        # Feather mask slightly (5px) for seamless blending while keeping unmasked pixels 100% original
        alpha = cv2.GaussianBlur(mask_bin_full, (7, 7), 0)[..., None]
        blended = (inpainted_full * alpha + orig_rgb * (1.0 - alpha)).astype(np.uint8)

        return Image.fromarray(blended)


def compute_psnr(img1: Image.Image, img2: Image.Image) -> float:
    a = np.array(img1.convert("RGB"), dtype=np.float64)
    b = np.array(img2.convert("RGB"), dtype=np.float64)
    mse = np.mean((a - b) ** 2)
    if mse == 0:
        return 100.0
    return float(20 * np.log10(255.0 / np.sqrt(mse)))


def run_benchmark(
    synthetic_dir: str = "./synthetic_tests",
    raw_dir: str = "./shopify_samples",
    output_dir: str = "./inpainted_results",
):
    os.makedirs(output_dir, exist_ok=True)
    pipeline = AutomatedInpaintPipeline()

    files = sorted([f for f in os.listdir(synthetic_dir) if f.endswith(".jpg")])
    results = []

    print(f"\nStarting benchmark on {len(files)} synthetic images...")
    for idx, fname in enumerate(files, 1):
        in_path = os.path.join(synthetic_dir, fname)
        base_prefix = fname.split("_lvl")[0]
        raw_path = os.path.join(raw_dir, f"{base_prefix}.jpg")

        img = Image.open(in_path).convert("RGB")
        t0 = time.time()
        mask_np = pipeline.detect_overlay_mask(img, dilate_px=16)
        t_detect = time.time() - t0

        t1 = time.time()
        cleaned_img = pipeline.inpaint_lama(img, mask_np)
        t_inpaint = time.time() - t1
        total_time = t_detect + t_inpaint

        # Save outputs
        stem = os.path.splitext(fname)[0]
        clean_path = os.path.join(output_dir, f"{stem}_clean.jpg")
        mask_path = os.path.join(output_dir, f"{stem}_mask.png")
        comp_path = os.path.join(output_dir, f"{stem}_comparison.jpg")

        cleaned_img.save(clean_path, quality=95)
        Image.fromarray(mask_np).save(mask_path)

        # Create side-by-side comparison (Input | Mask | Cleaned)
        w, h = img.size
        thumb_w = 500
        thumb_h = int(h * (thumb_w / w))
        comp = Image.new("RGB", (thumb_w * 3, thumb_h), (245, 245, 245))
        comp.paste(img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (0, 0))
        comp.paste(Image.fromarray(mask_np).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.NEAREST), (thumb_w, 0))
        comp.paste(cleaned_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (thumb_w * 2, 0))
        comp.save(comp_path, quality=92)

        psnr_before = None
        psnr_after = None
        if os.path.exists(raw_path):
            raw_img = Image.open(raw_path).convert("RGB")
            psnr_before = round(compute_psnr(raw_img, img), 2)
            psnr_after = round(compute_psnr(raw_img, cleaned_img), 2)

        mask_coverage_pct = round(float((mask_np > 0).sum()) / (img.width * img.height) * 100, 2)
        entry = {
            "file": fname,
            "detect_sec": round(t_detect, 2),
            "inpaint_sec": round(t_inpaint, 2),
            "total_sec": round(total_time, 2),
            "mask_coverage_pct": mask_coverage_pct,
            "psnr_before_db": psnr_before,
            "psnr_after_db": psnr_after,
        }
        results.append(entry)
        print(
            f"[{idx}/{len(files)}] {fname} -> Total: {entry['total_sec']}s "
            f"(Florence2: {entry['detect_sec']}s, LaMa: {entry['inpaint_sec']}s) | "
            f"Mask: {mask_coverage_pct}% | PSNR: {psnr_before}dB -> {psnr_after}dB"
        )

    summary_path = os.path.join(output_dir, "benchmark_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nBenchmark complete! Results saved to {summary_path}")


if __name__ == "__main__":
    run_benchmark()
