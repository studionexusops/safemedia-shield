"""
RunPod Serverless AI Cleanup Worker for SafeMedia Shield (AdFeed Clean)
Supports:
1. `task: "inpaint_clean"` (Default for Dual-Feed Smart Routing):
   - Florence-2 (<OCR_WITH_REGION>) text & watermark polygon detection
   - Full-width promotional banner strip detection + morphological character stroke isolation
   - Mask Dilate (6px) + Feather blending (7px)
   - LaMa Fast Fourier Convolution Inpainting (lossless unmasked product pixel preservation)
"""

import io
import os
import ssl
import time
import base64
import hashlib
import http.client
import ipaddress
import logging
import socket
import urllib.parse
import urllib.request
import re
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import numpy as np
import cv2
import torch
from PIL import Image, ImageDraw, ImageOps

Image.MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_DIMENSION = 4096

try:
    import runpod
except ImportError:
    runpod = None

from transformers import AutoProcessor, AutoModelForCausalLM
from transformers.dynamic_module_utils import get_imports

LAMA_MODEL_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
LAMA_MODEL_SHA256 = os.environ.get("LAMA_MODEL_SHA256", "")
MODEL_DIR = os.environ.get("MODEL_DIR", "./models")
LAMA_MODEL_PATH = os.path.join(MODEL_DIR, "big-lama.pt")
FLORENCE_MODEL_ID = os.environ.get("FLORENCE_MODEL_ID", "microsoft/Florence-2-base")
FLORENCE_MODEL_REVISION = os.environ.get("FLORENCE_MODEL_REVISION", "")
ALLOW_RUNTIME_MODEL_DOWNLOAD = os.environ.get("ALLOW_RUNTIME_MODEL_DOWNLOAD", "false").lower() == "true"

logger = logging.getLogger(__name__)


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


def _verify_file_sha256(file_path: str, expected_hex: str) -> None:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    actual_hex = hasher.hexdigest().lower()
    if actual_hex != expected_hex.strip().lower():
        raise RuntimeError("LaMa model integrity verification failed (SHA-256 mismatch).")


def ensure_lama_model() -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(LAMA_MODEL_PATH):
        if not ALLOW_RUNTIME_MODEL_DOWNLOAD:
            raise RuntimeError(
                f"LaMa model not found at {LAMA_MODEL_PATH} and ALLOW_RUNTIME_MODEL_DOWNLOAD is disabled."
            )
        urllib.request.urlretrieve(LAMA_MODEL_URL, LAMA_MODEL_PATH)
    if LAMA_MODEL_SHA256:
        _verify_file_sha256(LAMA_MODEL_PATH, LAMA_MODEL_SHA256)
    return LAMA_MODEL_PATH


_PROMO_KEYWORDS_RE = re.compile(
    r"(?:"
    r"\b(?:sale|off|discount|clearance|outlet|deal|deals|promo|promotion|promotional|"
    r"special|limited|offer|save|bargain|markdown|flash|hot|exclusive|bonus|gift|"
    r"free|shipping|delivery|warranty|guarantee|authentic|bestseller|best\s*seller|"
    r"new\s*arrival|must\s*have|today\s*only|hurry|order\s*now|shop\s*now|buy\s*now|"
    r"winter\s*sale|summer\s*sale|spring\s*sale|autumn\s*sale|black\s*friday|cyber\s*monday|"
    r"confidential|watermark|sample|draft|copyright|all\s*rights\s*reserved|store\s*name)\b"
    r"|%"
    r"|[¥$€£]\s*\d"
    r"|\d+\s*(?:円|％|off)\b"
    r"|©"
    r"|(?:セール|割引|限定|特価|送料無料|クーポン|オフ|半額|無断転載)"
    r")",
    re.IGNORECASE,
)


def _clean_ocr_label(raw_label: str) -> str:
    """Normalizes Florence-2 OCR label strings by stripping special tokens and whitespace."""
    return raw_label.replace("</s>", "").replace("<s>", "").strip()


def _is_promo_or_watermark_text(label: str) -> bool:
    """Returns True if the OCR text matches promotional banner, badge, price, or watermark patterns."""
    cleaned = _clean_ocr_label(label)
    if not cleaned:
        return False
    return bool(_PROMO_KEYWORDS_RE.search(cleaned))


def _is_noise_ocr_label(label: str) -> bool:
    """Filters out hallucinated non-ASCII/punctuation-only OCR noise on clean product textures."""
    cleaned = _clean_ocr_label(label)
    if not cleaned:
        return True
    alnum_chars = [c for c in cleaned if c.isalnum()]
    if len(alnum_chars) == 0:
        return "©" not in cleaned and "%" not in cleaned
    # Filter out spurious Arabic/Indic digit hallucinations on clean graphics
    ascii_or_cjk_alnum = sum(
        1 for c in cleaned
        if c.isalnum() and (ord(c) < 128 or ("\u3000" <= c <= "\u9fff") or ("\uff00" <= c <= "\uffef"))
    )
    return ascii_or_cjk_alnum == 0


class SafeMediaInpaintEngine:
    def __init__(self):
        self.device = get_device()
        hf_kwargs: Dict[str, Any] = {"trust_remote_code": True}
        if FLORENCE_MODEL_REVISION:
            hf_kwargs["revision"] = FLORENCE_MODEL_REVISION

        with patch("transformers.dynamic_module_utils.get_imports", fixed_get_imports):
            try:
                self.florence_processor = AutoProcessor.from_pretrained(
                    FLORENCE_MODEL_ID, local_files_only=True, **hf_kwargs
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    FLORENCE_MODEL_ID,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    attn_implementation="sdpa",
                    local_files_only=True,
                    **hf_kwargs,
                ).to(self.device).eval()
            except Exception:
                if not ALLOW_RUNTIME_MODEL_DOWNLOAD:
                    raise
                self.florence_processor = AutoProcessor.from_pretrained(
                    FLORENCE_MODEL_ID, **hf_kwargs
                )
                self.florence_model = AutoModelForCausalLM.from_pretrained(
                    FLORENCE_MODEL_ID,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    attn_implementation="sdpa",
                    **hf_kwargs,
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

    @staticmethod
    def _estimate_background_color(img_np: np.ndarray) -> np.ndarray:
        """
        Robustly estimates the dominant store background color from the outer vertical edges
        (excluding potential top/bottom banners by taking the dominant cluster across all rows).
        """
        h, w, _ = img_np.shape
        edge_w = max(2, int(w * 0.03))
        left_strip = img_np[:, :edge_w, :].reshape(-1, 3).astype(np.float32)
        right_strip = img_np[:, max(0, w - edge_w):, :].reshape(-1, 3).astype(np.float32)
        samples = np.concatenate([left_strip, right_strip], axis=0)
        if samples.shape[0] == 0:
            return np.array([255.0, 255.0, 255.0], dtype=np.float32)

        # Quantize colors to 16-unit bins to find the dominant background mode (immune to top/bottom banners)
        quantized = (samples // 16).astype(np.int32)
        keys = quantized[:, 0] * 256 + quantized[:, 1] * 16 + quantized[:, 2]
        unique_keys, counts = np.unique(keys, return_counts=True)
        best_key = unique_keys[int(np.argmax(counts))]
        in_mode = samples[keys == best_key]
        return np.median(in_mode, axis=0).astype(np.float32)

    @staticmethod
    def _detect_horizontal_banners(
        img_np: np.ndarray,
        bg_color: np.ndarray,
        promo_boxes: List[Tuple[int, int, int, int]],
    ) -> np.ndarray:
        """
        Detects full-width horizontal sale/promotional banners (including top/bottom edge banners,
        border lines, and drop shadows) without falsely masking the product itself.
        """
        h, w, _ = img_np.shape
        banner_mask = np.zeros((h, w), dtype=np.uint8)
        if h < 16 or w < 16:
            return banner_mask

        edge_w = max(4, int(w * 0.04))
        left_rows = img_np[:, :edge_w, :].mean(axis=1).astype(np.float32)
        right_rows = img_np[:, max(0, w - edge_w):, :].mean(axis=1).astype(np.float32)

        # A horizontal banner spans both left and right edges with a consistent non-background color
        edge_diff = np.linalg.norm(left_rows - right_rows, axis=1)
        left_bg_diff = np.linalg.norm(left_rows - bg_color[None, :], axis=1)
        right_bg_diff = np.linalg.norm(right_rows - bg_color[None, :], axis=1)

        # Also check horizontal uniformity across the row (at least at 15% and 85% width) to avoid
        # false positives on wide dark products touching both edges
        x15 = min(w - 1, max(0, int(w * 0.15)))
        x85 = min(w - 1, max(0, int(w * 0.85)))
        row_uniformity = np.linalg.norm(
            img_np[:, x15, :].astype(np.float32) - left_rows, axis=1
        ) + np.linalg.norm(
            img_np[:, x85, :].astype(np.float32) - right_rows, axis=1
        )

        is_banner_row = (
            (edge_diff < 32.0)
            & (left_bg_diff > 28.0)
            & (right_bg_diff > 28.0)
            & (row_uniformity < 90.0)
        )

        # Find contiguous row segments
        segments: List[Tuple[int, int]] = []
        in_seg = False
        seg_start = 0
        for y in range(h):
            if is_banner_row[y] and not in_seg:
                in_seg = True
                seg_start = y
            elif not is_banner_row[y] and in_seg:
                in_seg = False
                segments.append((seg_start, y - 1))
        if in_seg:
            segments.append((seg_start, h - 1))

        max_banner_h = int(h * 0.28)
        min_banner_h = max(6, int(h * 0.02))
        border_scan_px = max(10, int(h * 0.018))

        for sy1, sy2 in segments:
            seg_h = sy2 - sy1 + 1
            if seg_h < min_banner_h or seg_h > max_banner_h:
                continue

            # Confirm segment contains promotional text OR is a high-contrast colored edge strip
            near_top_or_bottom = sy1 <= int(h * 0.25) or sy2 >= int(h * 0.75)
            contains_promo_text = any(
                not (by2 < sy1 - 4 or by1 > sy2 + 4)
                for (_, by1, _, by2) in promo_boxes
            )
            seg_bg_diff = float(np.mean(left_bg_diff[sy1:sy2 + 1]))
            if not (contains_promo_text or (near_top_or_bottom and seg_bg_diff > 55.0)):
                continue

            # Expand outward to capture colored border lines (gold/yellow/white) and drop shadows
            # until the row edges return close to bg_color
            exp_y1 = sy1
            for _ in range(border_scan_px):
                if exp_y1 <= 0:
                    break
                prev_y = exp_y1 - 1
                if (
                    np.linalg.norm(left_rows[prev_y] - bg_color) < 10.0
                    and np.linalg.norm(right_rows[prev_y] - bg_color) < 10.0
                ):
                    break
                exp_y1 = prev_y

            exp_y2 = sy2
            for _ in range(border_scan_px):
                if exp_y2 >= h - 1:
                    break
                next_y = exp_y2 + 1
                if (
                    np.linalg.norm(left_rows[next_y] - bg_color) < 10.0
                    and np.linalg.norm(right_rows[next_y] - bg_color) < 10.0
                ):
                    break
                exp_y2 = next_y

            # Add 3px safety margin for anti-aliased edges
            by1 = max(0, exp_y1 - 3)
            by2 = min(h, exp_y2 + 4)
            banner_mask[by1:by2, :] = 255

        return banner_mask

    @staticmethod
    def _estimate_foreground_mask(
        img_np: np.ndarray, bg_color: np.ndarray, exclude_mask: np.ndarray
    ) -> np.ndarray:
        """
        Estimates the main product silhouette by finding non-background regions connected
        away from the image borders (or large central components).
        """
        h, w, _ = img_np.shape
        diff = np.linalg.norm(img_np.astype(np.float32) - bg_color[None, None, :], axis=2)
        non_bg = ((diff > 18.0) & (exclude_mask == 0)).astype(np.uint8) * 255
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        non_bg = cv2.morphologyEx(non_bg, cv2.MORPH_CLOSE, k)
        return non_bg

    @staticmethod
    def _extract_badge_region_mask(
        img_np: np.ndarray,
        bg_color: np.ndarray,
        pts: List[Tuple[float, float]],
    ) -> Optional[np.ndarray]:
        """
        Attempts to segment a solid/gradient promotional badge or sticker surrounding a promo OCR box.
        Returns a full-resolution binary mask of the entire badge (including outer border & shadow)
        if a distinct badge background is found, or None if the text sits directly on the store background.
        """
        h, w, _ = img_np.shape
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bx1 = max(0, int(min(xs)))
        by1 = max(0, int(min(ys)))
        bx2 = min(w, int(max(xs)))
        by2 = min(h, int(max(ys)))
        bw = max(1, bx2 - bx1)
        bh = max(1, by2 - by1)

        # Sample a ring around the text box to find the badge fill color
        pad = max(6, int(min(bw, bh) * 0.35))
        rx1 = max(0, bx1 - pad)
        ry1 = max(0, by1 - pad)
        rx2 = min(w, bx2 + pad)
        ry2 = min(h, by2 + pad)

        ring_mask = np.zeros((h, w), dtype=np.uint8)
        ring_mask[ry1:ry2, rx1:rx2] = 255
        ring_mask[by1:by2, bx1:bx2] = 0
        ring_pixels = img_np[ring_mask > 0].astype(np.float32)
        if ring_pixels.shape[0] < 16:
            return None

        badge_color = np.median(ring_pixels, axis=0)
        # If surrounding ring is basically the store background, this is floating text/watermark, not a badge
        if np.linalg.norm(badge_color - bg_color) < 28.0:
            return None

        # Work within a bounded ROI around the text box so region growing cannot leak across the whole image
        roi_margin_x = max(bw * 2, int(w * 0.25))
        roi_margin_y = max(bh * 3, int(h * 0.25))
        ox1 = max(0, bx1 - roi_margin_x)
        oy1 = max(0, by1 - roi_margin_y)
        ox2 = min(w, bx2 + roi_margin_x)
        oy2 = min(h, by2 + roi_margin_y)

        roi = img_np[oy1:oy2, ox1:ox2].astype(np.float32)
        color_dist = np.linalg.norm(roi - badge_color[None, None, :], axis=2)
        similar = (color_dist < 42.0).astype(np.uint8)

        # Seed from the ring pixels inside the ROI that match badge_color
        ring_roi = ring_mask[oy1:oy2, ox1:ox2] > 0
        seed_mask = (similar > 0) & ring_roi
        if not np.any(seed_mask):
            return None

        num_labels, labels = cv2.connectedComponents(similar, connectivity=8)
        seed_labels = np.unique(labels[seed_mask])
        seed_labels = seed_labels[seed_labels > 0]
        if seed_labels.size == 0:
            return None

        comp_mask = np.isin(labels, seed_labels).astype(np.uint8) * 255

        # Fill interior holes (such as text strokes and inner white rings)
        contours, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        filled_roi = np.zeros_like(comp_mask)
        cv2.drawContours(filled_roi, contours, -1, 255, thickness=cv2.FILLED)

        area_ratio = float((filled_roi > 0).sum()) / float(h * w)
        # Safety guard: if region grew into a large product body (>20% of image), reject badge expansion
        if area_ratio > 0.20:
            return None

        # Dilate outward to completely swallow outer badge borders (white rim) and drop shadows
        # so LaMa only sees clean background around the mask perimeter.
        rim_px = max(16, int(min(w, h) * 0.022))
        rim_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rim_px * 2 + 1, rim_px * 2 + 1))
        filled_roi = cv2.dilate(filled_roi, rim_kernel, iterations=1)

        full_badge_mask = np.zeros((h, w), dtype=np.uint8)
        full_badge_mask[oy1:oy2, ox1:ox2] = filled_roi
        return full_badge_mask

    def detect_overlay_mask(self, image: Image.Image, dilate_px: int = 6) -> np.ndarray:
        w, h = image.size
        img_np = np.array(image.convert("RGB"))
        final_mask = np.zeros((h, w), dtype=np.uint8)

        ocr_res = self.run_florence_ocr(image)
        quad_boxes = ocr_res.get("quad_boxes", [])
        raw_labels = ocr_res.get("labels", [])

        bg_color = self._estimate_background_color(img_np)

        # Classify OCR detections into promotional/watermark vs product-printed text
        promo_entries: List[Tuple[List[Tuple[float, float]], Tuple[int, int, int, int], str]] = []
        non_promo_entries: List[Tuple[List[Tuple[float, float]], Tuple[int, int, int, int], str]] = []

        for idx, quad in enumerate(quad_boxes):
            label = raw_labels[idx] if idx < len(raw_labels) else ""
            if _is_noise_ocr_label(label):
                continue
            pts = [(quad[i], quad[i + 1]) for i in range(0, len(quad), 2)]
            if len(pts) < 3:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

            if _is_promo_or_watermark_text(label):
                promo_entries.append((pts, bbox, label))
            else:
                non_promo_entries.append((pts, bbox, label))

        # Step 1: Detect full-width horizontal banners (works even at y=0 and captures borders/shadows)
        promo_bboxes = [b for (_, b, _) in promo_entries]
        banner_mask = self._detect_horizontal_banners(img_np, bg_color, promo_bboxes)
        final_mask = np.maximum(final_mask, banner_mask)

        # Step 2: Estimate foreground (product) silhouette excluding already-detected banners
        fg_mask = self._estimate_foreground_mask(img_np, bg_color, banner_mask)

        # Prepare morphological stroke anomaly map for floating text/watermarks
        k_bg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        opened = cv2.morphologyEx(img_np, cv2.MORPH_OPEN, k_bg)
        closed = cv2.morphologyEx(img_np, cv2.MORPH_CLOSE, k_bg)
        diff_open = np.linalg.norm(img_np.astype(np.float32) - opened.astype(np.float32), axis=2)
        diff_close = np.linalg.norm(img_np.astype(np.float32) - closed.astype(np.float32), axis=2)
        stroke_anomaly = np.maximum(diff_open, diff_close)

        # Step 3: Process promotional / watermark OCR detections (skipping ones already inside banners)
        for pts, (bx1, by1, bx2, by2), _ in promo_entries:
            cx = min(w - 1, max(0, (bx1 + bx2) // 2))
            cy = min(h - 1, max(0, (by1 + by2) // 2))
            if banner_mask[cy, cx] > 0:
                continue

            # Try full badge/sticker segmentation first (e.g., circular/rectangular sale stickers)
            badge_mask = self._extract_badge_region_mask(img_np, bg_color, pts)
            if badge_mask is not None:
                final_mask = np.maximum(final_mask, badge_mask)
                continue

            # Otherwise, remove the promotional text / floating watermark strokes
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

        # Step 4: Protect product-printed text & graphics!
        # Non-promotional text (brand logos like SOLARIS, AEROX, SMITH, GORE-TEX, VELOCITY)
        # is ONLY masked if it sits completely outside the product silhouette in a corner watermark zone.
        for pts, (bx1, by1, bx2, by2), _ in non_promo_entries:
            cx = min(w - 1, max(0, (bx1 + bx2) // 2))
            cy = min(h - 1, max(0, (by1 + by2) // 2))
            if banner_mask[cy, cx] > 0:
                continue

            # Check if this text overlaps with the product foreground
            rx1, ry1 = max(0, bx1), max(0, by1)
            rx2, ry2 = min(w, bx2), min(h, by2)
            if rx2 <= rx1 or ry2 <= ry1:
                continue

            fg_overlap = float((fg_mask[ry1:ry2, rx1:rx2] > 0).sum()) / float((rx2 - rx1) * (ry2 - ry1))
            in_corner = (cx < w * 0.20 or cx > w * 0.80) and (cy < h * 0.15 or cy > h * 0.85)
            # Only remove non-promo text if it is isolated on background in an image corner (watermark)
            if fg_overlap < 0.15 and in_corner:
                poly_img = Image.new("L", (w, h), 0)
                ImageDraw.Draw(poly_img).polygon(pts, fill=255)
                final_mask = np.maximum(final_mask, np.array(poly_img, dtype=np.uint8))

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


MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_BASE64_CHARS = (MAX_IMAGE_BYTES * 4 // 3) + 4
ALLOWED_DATA_URI_PREFIXES = (
    "data:image/jpeg;base64,",
    "data:image/jpg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,",
    "data:image/gif;base64,",
)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connects directly to a validated public IP while preserving hostname for TLS SNI/certificate checks."""

    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float = 15.0) -> None:
        super().__init__(host=host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_sock = socket.create_connection((self._pinned_ip, self.port), self.timeout, self.source_address)
        try:
            self.sock = self._context.wrap_socket(raw_sock, server_hostname=self.host)
        except Exception:
            raw_sock.close()
            raise


def _validate_public_https_url(url: str) -> Tuple[urllib.parse.ParseResult, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only valid https:// image URLs are allowed.")
    raw_host = parsed.hostname.strip("[]").lower()

    if (
        raw_host == "localhost"
        or raw_host == "metadata.google.internal"
        or raw_host.endswith(".internal")
        or raw_host.endswith(".local")
        or raw_host.endswith(".localhost")
        or raw_host.endswith(".localdomain")
        or raw_host.endswith(".home.arpa")
    ):
        raise ValueError(f"Blocked local or internal hostname: {raw_host}")

    try:
        addr_info = socket.getaddrinfo(parsed.hostname, parsed.port or 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except Exception as e:
        raise ValueError(f"DNS resolution failed for hostname '{parsed.hostname}': {e}")

    pinned_ip: Optional[str] = None
    for res in addr_info:
        ip_str = res[4][0]
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise ValueError(f"Blocked non-public IP address: {ip}")
        if pinned_ip is None:
            pinned_ip = ip_str

    if not pinned_ip:
        raise ValueError(f"No public IP resolved for hostname '{parsed.hostname}'")
    return parsed, pinned_ip


def fetch_image_bytes(image_source: str) -> bytes:
    if image_source.startswith("data:") and ";base64," in image_source:
        lower_prefix = image_source[:64].lower()
        if not any(lower_prefix.startswith(p) for p in ALLOWED_DATA_URI_PREFIXES):
            raise ValueError("Unsupported data URI image MIME type; allowed: jpeg, png, webp, gif.")
        _, base64_data = image_source.split(";base64,", 1)
        if len(base64_data) > MAX_BASE64_CHARS:
            raise ValueError(f"Image payload exceeds maximum limit of {MAX_IMAGE_BYTES} bytes.")
        data = base64.b64decode(base64_data)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image payload exceeds maximum limit of {MAX_IMAGE_BYTES} bytes.")
        return data
    elif image_source.startswith("https://"):
        parsed, pinned_ip = _validate_public_https_url(image_source)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        conn = _PinnedHTTPSConnection(
            host=parsed.hostname or "",
            port=parsed.port or 443,
            pinned_ip=pinned_ip,
            timeout=15.0,
        )
        try:
            conn.request(
                "GET",
                path,
                headers={
                    "Host": parsed.netloc,
                    "User-Agent": "SafeMediaShield-RunPod/1.0",
                    "Accept": "image/*,*/*;q=0.8",
                },
            )
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise ValueError("HTTP redirects are prohibited for SSRF protection.")
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"Upstream image fetch failed with HTTP {response.status}")
            data = response.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError(f"Image payload exceeds maximum limit of {MAX_IMAGE_BYTES} bytes.")
            return data
        finally:
            conn.close()
    elif image_source.startswith("http://"):
        raise ValueError("Insecure 'http://' URLs are not permitted. Use 'https://'.")
    else:
        if len(image_source) > MAX_BASE64_CHARS:
            raise ValueError(f"Image payload exceeds maximum limit of {MAX_IMAGE_BYTES} bytes.")
        data = base64.b64decode(image_source)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image payload exceeds maximum limit of {MAX_IMAGE_BYTES} bytes.")
        return data


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
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
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

        return {
            "status": "error",
            "message": f"Unsupported task: '{task}'. Only 'inpaint_clean' is supported.",
        }
    except ValueError as e:
        logger.warning("RunPod job rejected due to validation error: %s", e)
        return {"status": "error", "message": f"Invalid input image or parameters: {e}"}
    except Image.DecompressionBombError:
        logger.warning("RunPod job rejected: decompression bomb pixel threshold exceeded.")
        return {"status": "error", "message": "Image resolution exceeds safe processing limits."}
    except Exception:
        logger.exception("RunPod inference job failed unexpectedly.")
        return {"status": "error", "message": "Inference processing failed."}


if __name__ == "__main__":
    if runpod is not None:
        runpod.serverless.start({"handler": handler})
    else:
        print("RunPod SDK not installed; SafeMediaInpaintEngine handler ready for local import.")
