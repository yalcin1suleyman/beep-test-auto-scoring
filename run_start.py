"""
run_start.py - Ses duyulmayan kayitlarda cikis anini goruntuden bulur.

Baslangic kamerasinda kosucular cikis bipine kadar cizgide bekler, bipte
kameradan uzaklasir (ayak Y degeri kuculur). Cizgi yakinindaki kisilerin ayak
Y medyani ilk kez belirgin ve kalici bicimde azaldiginda kalkis ani bulunur.
Cikis bipi = kalkis ani - tepki suresi. Sonraki bipler resmi mekik
temposundan hesaplanir.
"""

from __future__ import annotations

import cv2
import numpy as np

# Sesin net oldugu kayitlarda (Video 2-6) olculen bip -> kalkis gecikmesi:
# 0.65, 1.20, 1.06, 0.78, 0.39 s (ortalama 0.82 s).
DEFAULT_REACTION_SEC = 0.8


def find_departure_time(samples: list[tuple[float, list[float]]], line_y: float,
                        near_px: float = 120.0, move_px: float = 25.0,
                        hold_sec: float = 0.6) -> float | None:
    """
    samples: (zaman, [cizgi yakinindaki kisilerin ayak Y'leri]) listesi.

    Kosucular kameradan uzaklastikca ayak Y'si kuculur. Medyan ayak Y'si
    bekleme seviyesinin move_px altina inip hold_sec boyunca orada kalirsa
    kalkis vardir; kalkis ani, medyanin bekleme seviyesinden ayrildigi son
    ornektir.
    """
    times: list[float] = []
    medians: list[float] = []
    for t, ys in samples:
        near = [y for y in ys if abs(y - line_y) <= near_px]
        if len(near) >= 1:
            times.append(float(t))
            medians.append(float(np.median(near)) if near else np.nan)
    if len(times) < 4:
        return None
    times_a = np.array(times)
    med = np.array(medians)
    for i in range(1, len(med)):
        baseline = float(np.median(med[max(0, i - 8):i]))
        if med[i] > baseline - move_px:
            continue
        hold = (times_a > times_a[i]) & (times_a <= times_a[i] + hold_sec)
        if hold.any() and np.all(med[hold] < baseline - move_px):
            # Ayrilmanin basladigi ornege geri git
            j = i
            while j > 0 and med[j - 1] < baseline - 5:
                j -= 1
            return float(times_a[j - 1] if j > 0 else times_a[j])
    return None


def detect_departure(video_path, line_y: float, start_sec: float = 0.0,
                     search_sec: float = 45.0, sample_hz: float = 10.0,
                     model=None) -> float | None:
    """Baslangic kamerasinda YOLO ile kosucularin kalkis anini (video saniyesi) bulur."""
    if model is None:
        from ultralytics import YOLO
        from config import PROJECT_ROOT, YOLO_MODEL
        model = YOLO(str(PROJECT_ROOT / YOLO_MODEL))
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(fps / sample_hz)))
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
        idx = int(round(start_sec * fps))
        end_idx = int((start_sec + search_sec) * fps)
        samples = []
        while idx < end_idx:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                result = model.predict(frame, imgsz=640, conf=0.3, classes=[0], verbose=False)[0]
                boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else []
                ys = [float(b[3]) for b in boxes if (b[3] - b[1]) > 0.12 * frame.shape[0]]
                samples.append((idx / fps, ys))
                found = find_departure_time(samples, line_y)
                if found is not None and samples[-1][0] - found > 2.0:
                    return found
            idx += 1
        return find_departure_time(samples, line_y)
    finally:
        cap.release()
