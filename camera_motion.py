"""
camera_motion.py - Elde tutulan telefon kameralarinda cizgi kaymasi telafisi.

Kalibrasyon karesi referans alinir. Her N karede bir guncel kare ile referans
arasinda ORB oznitelikleri eslestirilir ve RANSAC ile homografi bulunur.
Telefon egildiginde/kaydiginda kalibre edilen cizgi bu homografiyle guncel
kareye tasinir. Kosucular hareketli oldugu icin RANSAC disinda kalir; kisi
kutulari ayrica maskelenir.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from line_geometry import PerspectiveLine


@dataclass
class MotionCompensatorConfig:
    update_every: int = 3            # Kac karede bir homografi hesaplanir
    max_width: int = 640             # Hesaplama icin kucultulmus genislik
    n_features: int = 1500
    min_inliers: int = 25
    max_line_shift_px: float = 200.0  # Cizgi noktasinin referanstan max kaymasi
    smoothing_alpha: float = 0.5


class CameraMotionCompensator:
    """Referans kareye gore kamera hareketini izler ve cizgiyi tasir."""

    def __init__(self, reference_frame: np.ndarray, base_line: PerspectiveLine,
                 config: MotionCompensatorConfig | None = None):
        self.config = config or MotionCompensatorConfig()
        self.base_line = base_line
        h, w = reference_frame.shape[:2]
        self.scale = min(1.0, self.config.max_width / float(w))
        self._orb = cv2.ORB_create(self.config.n_features)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        self._ref_kp, self._ref_des = self._features(reference_frame, None)
        self._base_pts = np.array(base_line.points, dtype=np.float32).reshape(-1, 1, 2)
        self._current_pts = self._base_pts.reshape(-1, 2).copy()
        self._frame_count = 0
        self.last_inliers = 0
        self.ok_updates = 0
        self.failed_updates = 0

    def _features(self, frame: np.ndarray, person_boxes):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        if self.scale != 1.0:
            gray = cv2.resize(gray, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        mask = np.full(gray.shape, 255, dtype=np.uint8)
        for box in person_boxes or []:
            x1, y1, x2, y2 = [int(round(v * self.scale)) for v in box[:4]]
            pad = 6
            mask[max(0, y1 - pad):max(0, y2 + pad), max(0, x1 - pad):max(0, x2 + pad)] = 0
        return self._orb.detectAndCompute(gray, mask)

    @property
    def offset_px(self) -> float:
        """Cizginin referansa gore ortalama dikey kaymasi (piksel)."""
        return float(np.mean(self._current_pts[:, 1] - self._base_pts.reshape(-1, 2)[:, 1]))

    def current_line(self) -> PerspectiveLine:
        return PerspectiveLine(tuple((float(x), float(y)) for x, y in self._current_pts))

    def update(self, frame: np.ndarray, person_boxes=None) -> PerspectiveLine:
        self._frame_count += 1
        if (self._frame_count - 1) % self.config.update_every == 0:
            self._estimate(frame, person_boxes)
        return self.current_line()

    def _estimate(self, frame: np.ndarray, person_boxes) -> None:
        cfg = self.config
        if self._ref_des is None or len(self._ref_kp) < cfg.min_inliers:
            self.failed_updates += 1
            return
        kp, des = self._features(frame, person_boxes)
        if des is None or len(kp) < cfg.min_inliers:
            self.failed_updates += 1
            return
        pairs = self._matcher.knnMatch(self._ref_des, des, k=2)
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < cfg.min_inliers:
            self.failed_updates += 1
            return
        src = np.float32([self._ref_kp[m.queryIdx].pt for m in good]) / self.scale
        dst = np.float32([kp[m.trainIdx].pt for m in good]) / self.scale
        H, inlier_mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
        self.last_inliers = inliers
        if H is None or inliers < cfg.min_inliers:
            self.failed_updates += 1
            return
        moved = cv2.perspectiveTransform(self._base_pts, H).reshape(-1, 2)
        base = self._base_pts.reshape(-1, 2)
        if not np.all(np.isfinite(moved)) or np.max(np.abs(moved - base)) > cfg.max_line_shift_px:
            self.failed_updates += 1
            return
        # X sirasi korunmali; aksi halde PerspectiveLine bozulur.
        if np.any(np.diff(moved[:, 0]) <= 0):
            self.failed_updates += 1
            return
        a = cfg.smoothing_alpha
        self._current_pts = (1.0 - a) * self._current_pts + a * moved
        self.ok_updates += 1
