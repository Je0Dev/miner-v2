"""Advanced image preprocessing: deblur, deskew, binarization."""
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from scipy.ndimage import gaussian_filter, median_filter
from log import log

def deblur_image(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Reduce blur using unsharp masking."""
    arr = np.array(img).astype(np.float32)
    blurred = gaussian_filter(arr, sigma=strength)
    sharpened = arr + (arr - blurred) * 1.5
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    return Image.fromarray(sharpened)

def deskew_image(img: Image.Image) -> Image.Image:
    """Auto-detect and correct text skew."""
    arr = np.array(img)
    # Find text angle using projection profile
    edges = np.abs(np.diff(arr, axis=1))
    angles = np.arange(-5, 5, 0.5)
    best_angle = 0
    best_score = 0
    for angle in angles:
        rotated = img.rotate(angle, expand=True)
        r_arr = np.array(rotated)
        # Score: variance of horizontal projection
        proj = np.var(np.mean(r_arr, axis=1))
        if proj > best_score:
            best_score = proj
            best_angle = angle
    if abs(best_angle) > 0.5:
        log.info(f"Deskewing: {best_angle}°")
        return img.rotate(best_angle, expand=True)
    return img

def adaptive_binarize(img: Image.Image) -> Image.Image:
    """Adaptive binarization using local thresholding."""
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape
    block_size = max(15, min(h, w) // 20)
    if block_size % 2 == 0: block_size += 1
    # Local mean thresholding
    from scipy.ndimage import uniform_filter
    local_mean = uniform_filter(arr, size=block_size)
    binary = arr > (local_mean * 0.9)
    return Image.fromarray((binary * 255).astype(np.uint8))

def preprocess_advanced(image_path: Path, lang: str) -> Image.Image:
    """Full preprocessing pipeline for difficult images."""
    from pathlib import Path
    img = Image.open(image_path).convert("L")
    # Step 1: Deblur
    img = deblur_image(img)
    # Step 2: Deskew
    img = deskew_image(img)
    # Step 3: Contrast enhancement
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    # Step 4: Adaptive binarization
    img = adaptive_binarize(img)
    return img
