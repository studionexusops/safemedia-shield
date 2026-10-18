"""
RunPod Serverless AI Cleanup & Image Optimization Worker for SafeMedia Shield
Supports:
1. `task: "inpaint_clean"` (Default for Dual-Feed Smart Routing):
   - Florence-2 (<OCR_WITH_REGION>) text & watermark polygon detection
   - Full-width promotional banner strip detection + morphological character stroke isolation
   - Mask Dilate (6px) + Feather blending (7px)
   - LaMa Fast Fourier Convolution Inpainting (lossless unmasked product pixel preservation)
2. `task: "optimize"` (WebP non-destructive compression)
"""

import io
import os
import time
import base64
import urllib.request
from typing import Any, Dict, Optional
from unittest.mock import patch

import numpy as np
import cv2
import torch
from PIL import Image, ImageDraw, ImageOps

try:
    import runpod
except ImportError:
    runpod = None

from transformers import AutoProcessor, AutoModelForCausalLM
from transformers.dynamic_module_utils import get_imports

LAMA_MODEL_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
MODEL_DIR = os.environ.get("MODEL_DIR", "./models")
LAMA_MODEL_PATH = os.path.join(MODEL_DIR, "big-lama.pt")
FLORENCE_MODEL_ID = os.environ.get("FLORENCE_MODEL_ID", "microsoft/Florence-2-base")


def fixed_get_imports(filename):
    imports = get_imports(filename)
    if "flash_attn" in imports:
        imports.remove("flash_attn")
    return imports


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def ensure_lama_model() -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(LAMA_MODEL_PATH):
        urllib.request.urlretrieve(LAMA_MODEL_URL, LAMA_MODEL_PATH)
    return LAMA_MODEL_PATH


class SafeMediaInpaintEngine:
    def __init__(self):
        self.device = get_device()
        with patch("transformers.dynamic_module_utils.get_imports", fixed_get_imports):
            try:
                self.florence_processor = AutoProcessor.from_pretrained(
                    FLORENCE_MODEL_ID, trust_remote_code=True, local_files_only=True
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    FLORENCE_MODEL_ID,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
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
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    attn_implementation="sdpa",
                ).to(self.device).eval()

        lama_path = ensure_lama_model()
        self.lama_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.lama_model = torch.jit.load(lama_path, map_location=self.lama_device).eval()

    @torch.no_grad()
    def run_florence_ocr(self, image: Image.Image) -> dict:
        task_prompt = "<OCR_WITH_REGION>"
        img_resized = image.convert("RGB").resize((768, 768), resample=Image.Resampling.BICUBIC)
        arr = np.asarray(img_resized, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        pixel_values = (
            torch.from_numpy(np.ascontiguousarray(arr.transpose(2, 0, 1)))
            .unsqueeze(0)
            .to(self.device)
        )
        if self.device == "cuda":
            pixel_values = pixel_values.to(torch.float16)

        prompt_text = "What is the text in the image, with regions?"
        if hasattr(self.florence_processor, "_construct_prompts"):
            prompt_text = self.florence_processor._construct_prompts([task_prompt])[0]
        tok_out = self.florence_processor.tokenizer(
            [prompt_text], return_tensors=None, padding=False
        )
        input_ids = torch.tensor(tok_out["input_ids"], dtype=torch.long, device=self.device)

        generated_ids = self.florence_model.generate(
            input_ids=input_ids,
            pixel_values=pixel_values,
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
        w, h = image.size
        img_np = np.array(image.convert("RGB"))
        final_mask = np.zeros((h, w), dtype=np.uint8)

        ocr_res = self.run_florence_ocr(image)
        quad_boxes = ocr_res.get("quad_boxes", [])

        k_bg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
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
                poly_img = Image.new("L", (w, h), 0)
                ImageDraw.Draw(poly_img).polygon(pts, fill=255)
                poly_np = cv2.dilate(
                    np.array(poly_img, dtype=np.uint8),
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
                    iterations=1,
                )
                region_vals = stroke_anomaly[poly_np > 0]
                if region_vals.size > 0:
                    thresh = max(14.0, float(np.percentile(region_vals, 55)))
                    stroke_mask = ((stroke_anomaly >= thresh) & (poly_np > 0)).astype(np.uint8) * 255
                    if (stroke_mask > 0).sum() < 0.08 * (poly_np > 0).sum():
                        stroke_mask = poly_np
                    final_mask = np.maximum(final_mask, stroke_mask)

        if dilate_px > 0 and final_mask.max() > 0:
            kernel_size = dilate_px * 2 + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            final_mask = cv2.dilate(final_mask, kernel, iterations=1)

        return final_mask

    @torch.no_grad()
    def inpaint_lama(self, image: Image.Image, mask_np: np.ndarray, max_infer_dim: int = 512) -> Image.Image:
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

        alpha = cv2.GaussianBlur(mask_bin_full, (7, 7), 0)[..., None]
        blended = (inpainted_full * alpha + orig_rgb * (1.0 - alpha)).astype(np.uint8)
        return Image.fromarray(blended)


_ENGINE_SINGLETON: Optional[SafeMediaInpaintEngine] = None


def get_engine() -> SafeMediaInpaintEngine:
    global _ENGINE_SINGLETON
    if _ENGINE_SINGLETON is None:
        _ENGINE_SINGLETON = SafeMediaInpaintEngine()
    return _ENGINE_SINGLETON


def fetch_image_bytes(image_source: str) -> bytes:
    if image_source.startswith("data:") and ";base64," in image_source:
        _, base64_data = image_source.split(";base64,", 1)
        return base64.b64decode(base64_data)
    elif image_source.startswith("http://") or image_source.startswith("https://"):
        req = urllib.request.Request(
            image_source,
            headers={"User-Agent": "SafeMediaShield-RunPod/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read()
    else:
        return base64.b64decode(image_source)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_input = job.get("input", {})
    task = job_input.get("task", "inpaint_clean")
    image_source = job_input.get("image_url") or job_input.get("image_base64")

    if not image_source:
        return {"status": "error", "message": "Missing 'image_url' or 'image_base64' in job input."}

    try:
        t0 = time.time()
        raw_bytes = fetch_image_bytes(image_source)
        img = Image.open(io.BytesIO(raw_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img_rgb = img.convert("RGB")

        if task == "inpaint_clean":
            dilate_px = int(job_input.get("dilate_px", 6))
            engine = get_engine()
            mask_np = engine.detect_overlay_mask(img_rgb, dilate_px=dilate_px)
            cleaned_img = engine.inpaint_lama(img_rgb, mask_np)

            out_buf = io.BytesIO()
            cleaned_img.save(out_buf, format="JPEG", quality=95)
            cleaned_bytes = out_buf.getvalue()

            mask_pct = round(float((mask_np > 127).sum()) / float(mask_np.size) * 100.0, 2)
            proc_sec = round(time.time() - t0, 2)

            return {
                "status": "success",
                "task": "inpaint_clean",
                "image_base64": base64.b64encode(cleaned_bytes).decode("utf-8"),
                "mime_type": "image/jpeg",
                "mask_coverage_pct": mask_pct,
                "processing_sec": proc_sec,
                "width": cleaned_img.width,
                "height": cleaned_img.height,
            }

        # Fallback: standard WebP optimization
        quality = int(job_input.get("quality", 82))
        out_buf = io.BytesIO()
        img_rgb.save(out_buf, format="WEBP", quality=quality, method=6)
        opt_bytes = out_buf.getvalue()
        savings_pct = round(((len(raw_bytes) - len(opt_bytes)) / len(raw_bytes)) * 100, 1) if raw_bytes else 0

        return {
            "status": "success",
            "task": "optimize",
            "format": "webp",
            "original_bytes": len(raw_bytes),
            "optimized_bytes": len(opt_bytes),
            "savings_percentage": savings_pct,
            "image_base64": base64.b64encode(opt_bytes).decode("utf-8"),
            "mime_type": "image/webp",
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": f"{e}\n{traceback.format_exc()}"}


if __name__ == "__main__":
    if runpod is not None:
        runpod.serverless.start({"handler": handler})
    else:
        print("RunPod SDK not installed; SafeMediaInpaintEngine handler ready for local import.")
