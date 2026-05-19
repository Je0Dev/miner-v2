"""MSSIM Image Stability Detection - Avoid OCR during animations/transitions."""
import time
import numpy as np
from pathlib import Path
try:
    from PIL import Image
    from scipy.ndimage import uniform_filter
except ImportError:
    pass
from log import log

class MSSIMStabilityDetector:
    """Detect if screen content is stable using Multi-Scale Structural Similarity."""

    def __init__(self, threshold=0.92, window_size=7, history_size=3):
        self.threshold = threshold
        self.window_size = window_size
        self.history_size = history_size
        self._prev_frame = None
        self._stable_count = 0

    def _gaussian_window(self, size, sigma=1.5):
        """Create a 1D Gaussian window."""
        ax = np.arange(size)
        gauss = np.exp(-((ax - size // 2) ** 2) / (2.0 * sigma ** 2))
        return gauss / gauss.sum()

    def _compute_mssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Compute Multi-Scale Structural Similarity Index."""
        K1, K2 = 0.01, 0.03
        L = 255
        C1 = (K1 * L) ** 2
        C2 = (K2 * L) ** 2
        C3 = C2 / 2

        window = self._gaussian_window(self.window_size)
        window = np.outer(window, window)

        def filter2d(x):
            return uniform_filter(x, size=self.window_size)

        mu1 = filter2d(img1)
        mu2 = filter2d(img2)
        mu1_sq = mu1 * mu1
        mu2_sq = mu2 * mu2
        mu1_mu2 = mu1 * mu2
        sigma1_sq = filter2d(img1 * img1) - mu1_sq
        sigma2_sq = filter2d(img2 * img2) - mu2_sq
        sigma12 = filter2d(img1 * img2) - mu1_mu2

        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
                   ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
        return float(np.mean(ssim_map))

    def check_stability(self, image_path: Path) -> bool:
        """Check if current frame is stable compared to previous."""
        try:
            img = Image.open(image_path).convert("L")
            img = img.resize((img.width // 4, img.height // 4), Image.LANCZOS)
            current = np.array(img, dtype=np.float64)

            if self._prev_frame is None:
                self._prev_frame = current
                return True

            mssim = self._compute_mssim(self._prev_frame, current)
            self._prev_frame = current

            if mssim >= self.threshold:
                self._stable_count += 1
                return self._stable_count >= 2
            else:
                self._stable_count = 0
                return False
        except Exception as e:
            log.warning(f"MSSIM check failed: {e}")
            return True

    def reset(self):
        """Reset stability state."""
        self._prev_frame = None
        self._stable_count = 0
