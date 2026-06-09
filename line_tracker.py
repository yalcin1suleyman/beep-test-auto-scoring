"""
line_tracker.py - Hafif kamera kaymalarina dayanikli yatay cizgi takibi.

Kalibrasyonda secilen Y koordinatini baslangic kabul eder. Her karede bu
koordinatin yakinindaki yatay, parlak/kenar yogunlugu yuksek cizgiyi arar ve
ani ziplamalari yumusatarak guncel cizgi Y degerini dondurur.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LineTrackerConfig:
    search_margin_px: int = 70
    roi_x_margin_ratio: float = 0.08
    min_confidence: float = 0.18
    smoothing_alpha: float = 0.25
    max_step_px: int = 8


class HorizontalLineTracker:
    """Kalibre edilen yatay hedef cizgiyi kareler arasinda takip eder."""

    def __init__(self, initial_y: int, config: LineTrackerConfig | None = None):
        self.initial_y = int(initial_y)
        self.current_y = int(initial_y)
        self.config = config or LineTrackerConfig()
        self.confidence = 1.0
        self._prev_motion_gray: np.ndarray | None = None

    def update(self, frame: np.ndarray) -> int:
        """Yeni kareye gore cizgi Y degerini gunceller."""
        h, w = frame.shape[:2]
        cfg = self.config

        y0 = max(0, self.current_y - cfg.search_margin_px)
        y1 = min(h, self.current_y + cfg.search_margin_px + 1)
        if y1 <= y0 + 3:
            return self.current_y

        x0 = int(w * cfg.roi_x_margin_ratio)
        x1 = int(w * (1.0 - cfg.roi_x_margin_ratio))
        roi = frame[y0:y1, x0:x1]
        if roi.size == 0:
            return self.current_y

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        motion_shift_y = self._estimate_vertical_motion(frame)

        edges = cv2.Canny(gray, 50, 150)
        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(15, int((x1 - x0) * 0.08)), 1),
        )
        horizontal = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)

        edge_scores = horizontal.mean(axis=1).astype(np.float32) / 255.0
        bright_scores = gray.mean(axis=1).astype(np.float32) / 255.0
        scores = 0.72 * edge_scores + 0.28 * bright_scores

        if scores.size == 0:
            return self.current_y

        best_local_y = int(np.argmax(scores))
        best_score = float(scores[best_local_y])
        median_score = float(np.median(scores))
        confidence = max(0.0, best_score - median_score)
        self.confidence = confidence

        if confidence < cfg.min_confidence:
            self._apply_motion_fallback(motion_shift_y, h)
            return self.current_y

        detected_y = y0 + best_local_y
        delta = detected_y - self.current_y
        delta = int(np.clip(delta, -cfg.max_step_px, cfg.max_step_px))
        limited_y = self.current_y + delta
        smoothed_y = (1.0 - cfg.smoothing_alpha) * self.current_y + cfg.smoothing_alpha * limited_y
        self.current_y = int(round(np.clip(smoothed_y, 0, h - 1)))
        return self.current_y

    def reset(self, y: int | None = None):
        self.current_y = int(self.initial_y if y is None else y)
        self.confidence = 1.0
        self._prev_motion_gray = None

    def _estimate_vertical_motion(self, frame: np.ndarray) -> float:
        """Kareler arasi genel dikey kamera kaymasini tahmin eder."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (0, 0), fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        small = small.astype(np.float32)

        if self._prev_motion_gray is None or self._prev_motion_gray.shape != small.shape:
            self._prev_motion_gray = small
            return 0.0

        (shift_x, shift_y), response = cv2.phaseCorrelate(self._prev_motion_gray, small)
        self._prev_motion_gray = small

        if response < 0.05:
            return 0.0
        return float(shift_y / 0.25)

    def _apply_motion_fallback(self, shift_y: float, frame_h: int):
        cfg = self.config
        if abs(shift_y) < 0.25:
            return
        limited = int(np.clip(round(shift_y), -cfg.max_step_px, cfg.max_step_px))
        self.current_y = int(np.clip(self.current_y + limited, 0, frame_h - 1))
