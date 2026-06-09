"""
line_geometry.py - Perspektifli bitis/cikis cizgisi yardimcilari.

Kamera yere dik bakmadigi icin cizgi tek bir yatay Y degeri degildir. Bu
modul, konilerin alt noktalarindan gecen kirikli cizgide kosucunun X
konumuna karsilik gelen Y degerini hesaplar.
"""

from dataclasses import dataclass

import cv2
import numpy as np


Point = tuple[float, float]


@dataclass(frozen=True)
class PerspectiveLine:
    points: tuple[Point, ...]

    @classmethod
    def from_points(cls, points: list[tuple[int, int]] | tuple[tuple[int, int], ...]):
        ordered = tuple((float(x), float(y)) for x, y in sorted(points, key=lambda p: p[0]))
        if len(ordered) < 2:
            raise ValueError("PerspectiveLine en az iki nokta ister.")
        return cls(ordered)

    @classmethod
    def horizontal(cls, y: int, width: int):
        return cls.from_points([(0, int(y)), (max(1, int(width) - 1), int(y))])

    @property
    def median_y(self) -> int:
        return int(round(float(np.median([p[1] for p in self.points]))))

    @property
    def min_x(self) -> float:
        return self.points[0][0]

    @property
    def max_x(self) -> float:
        return self.points[-1][0]

    def shifted(self, dy: float):
        return PerspectiveLine(tuple((x, y + dy) for x, y in self.points))

    def y_at(self, x: float) -> float:
        pts = self.points
        if x <= pts[0][0]:
            return pts[0][1]
        if x >= pts[-1][0]:
            return pts[-1][1]

        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                if x1 == x0:
                    return y0
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return pts[-1][1]

    def draw(self, frame: np.ndarray, color: tuple[int, int, int], thickness: int):
        pts = np.array([(int(round(x)), int(round(y))) for x, y in self.points], dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=thickness)
