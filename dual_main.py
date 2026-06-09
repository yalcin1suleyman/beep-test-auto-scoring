"""
dual_main.py — Çift Kamera + Ses Tabanlı Mekik Testi Değerlendirme Sistemi

MİMARİ:
  Aynı video dosyasından iki bağımsız kamera akışı simüle edilir:

    Kamera 1 (Başlangıç / 0m):
      → Video normal başlangıç noktasından oynatılır
      → Atletler BÜYÜK görünür (kameraya yakın)
      → Başlangıç (0m) çizgisi kalibre edilir

    Kamera 2 (20m):
      → Aynı video CAM2_OFFSET_SEC (varsayılan 9s) sonrasından oynatılır
      → Bu ofset, atletlerin ilk kez 20m çizgisine ulaştığı zamana karşılık gelir
      → 20m çizgisi kalibre edilir

  Her kamera kendi penceresinde gösterilir.
  Paylaşımlı değerlendirici her iki kameranın geçişlerini bip zamanlarına göre değerlendirir.

  İleride: iki ayrı fiziksel kamera bağlandığında, video akışları değiştirilerek
  bu mimari doğrudan kullanılabilir.

Kullanım:
    python dual_main.py
    python dual_main.py --video video.mp4
    python dual_main.py --video video.mp4 --cam2-offset 9.0
    python dual_main.py --video video.mp4 --no-audio
    python dual_main.py --video video.mp4 --no-display
"""

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from config import (
    DATA_INPUTS,
    DATA_OUTPUTS,
    DEFAULT_START_CAMERA_VIDEO,
    DEFAULT_FAR_CAMERA_VIDEO,
    DEFAULT_BEEP_AUDIO_URL,
    VIDEO_START_TIME_SEC,
    DEFAULT_START_BEEP_TIME_SEC,
    DISPLAY_EVERY_N_FRAMES,
    REALTIME_PREVIEW,
    MAX_REALTIME_FRAME_SKIP,
    DUAL_START_LINE_Y,
    DUAL_FAR_LINE_Y,
    DUAL_START_LINE_POINTS,
    DUAL_FAR_LINE_POINTS,
    CAM2_OFFSET_SEC,
    FIRST_BEEP_DEADLINE_SEC,
    CAM2_SHARE_TRACK_IDS,
    CAM2_ID_OFFSET,
    LINE_THICKNESS,
    ENABLE_AUTO_LINE_TRACKING,
    LINE_TRACK_SEARCH_MARGIN_PX,
    LINE_TRACK_MIN_CONFIDENCE,
    LINE_TRACK_SMOOTHING_ALPHA,
    LINE_TRACK_MAX_STEP_PX,
    EXPECTED_RUNNER_COUNT,
    FONT_SCALE,
    FONT_THICKNESS,
    ANKLE_CIRCLE_RADIUS,
    COLOR_ACTIVE,
    COLOR_WARNING,
    COLOR_ELIMINATED,
    COLOR_TEXT_BG,
    RunnerState,
    ENABLE_CONE_DETECTION,
    CONE_HSV_LOWER,
    CONE_HSV_UPPER,
    CONE_HSV_SECONDARY_LOWER,
    CONE_HSV_SECONDARY_UPPER,
    CONE_MIN_AREA_PX,
    CONE_MAX_AREA_PX,
    CONE_MIN_CIRCULARITY,
    CONE_LINE_SMOOTHING_ALPHA,
    CONE_DEBUG_DRAW,
)
from tracker import PoseTracker
from timer import ShuttleTimer
from audio_detector import BeepDetector
from video_splitter import create_dual_camera_videos
from dual_camera_analyser import DualLineEvaluator
from line_tracker import HorizontalLineTracker, LineTrackerConfig
from line_geometry import PerspectiveLine
from line_calibrator import DualLineCalibrator

# Sistema de detecção dinâmica de cones
try:
    from cone_line_adapter import ConeLineAdapter
    CONE_DETECTOR_AVAILABLE = True
except ImportError:
    CONE_DETECTOR_AVAILABLE = False


# ==============================================================================
# Renk Sabitleri
# ==============================================================================
COLOR_START_LINE = (0, 220, 0)      # Yeşil — başlangıç (0m) çizgisi
COLOR_FAR_LINE   = (0, 140, 255)    # Turuncu — 20m çizgisi
COLOR_BIP_FLASH  = (0, 255, 255)    # Sarı — bip animasyonu


# ==============================================================================
# İki Nokta Çizgi Kalibrasyonu — Perspektif Çizgisi (2 tıklama)
# ==============================================================================


def _calibrate_perspective_line(
    frame: np.ndarray,
    win_title: str,
    line_color: tuple,
    suggested_points: list[tuple[int, int]] | None,
    header_lines: list[str],
) -> list[tuple[int, int]]:
    """
    İKİ NOKTA çizgi kalibrasyonu. Ayrı pencere açar, 2 tıklama bekler.
    İlk tıklama sol ucu, ikinci tıklama sağ ucu belirler.
    Onay gösterip pencereyi kapatır ve iki nokta döndürür: [(x1, y1), (x2, y2)]
    """
    h, w = frame.shape[:2]
    preview_scale = min(900 / w, 650 / h, 1.0)
    preview_w = max(1, int(w * preview_scale))
    preview_h = max(1, int(h * preview_scale))

    def _to_preview_coords(real_x: int, real_y: int) -> tuple[int, int]:
        px = max(0, min(preview_w - 1, int(real_x * preview_scale)))
        py = max(0, min(preview_h - 1, int(real_y * preview_scale)))
        return px, py

    def _to_real_coords(preview_x: int, preview_y: int) -> tuple[int, int]:
        rx = max(0, min(w - 1, int(preview_x / preview_scale)))
        ry = max(0, min(h - 1, int(preview_y / preview_scale)))
        return rx, ry

    # Başlangıç noktaları öner
    if suggested_points is None or len(suggested_points) < 2:
        p1 = (50, int(h * 0.85))
        p2 = (w - 50, int(h * 0.88))
        suggested_points = [p1, p2]

    mouse_state = {
        "points": list(suggested_points[:2]),  # [p1, p2]
        "click_count": 0,  # 0, 1, veya 2
        "confirmed": False,
        "hovering_point": -1,  # -1: hiçbiri, 0: p1, 1: p2
        "dragging": False,
    }

    def _on_calibration_mouse(event, px, py, _flags, param):
        state = param
        rx, ry = _to_real_coords(px, py)

        if event == cv2.EVENT_LBUTTONDOWN:
            # Sadece kullanicinin daha once sectigi gorunur noktalar tasinabilir.
            # Oneri noktalarini gizli tuttugumuz icin ilk tiklamalarda secimi
            # engellememeleri gerekir.
            hovering = -1
            for i, (px_stored, py_stored) in enumerate(state["points"][:state["click_count"]]):
                if abs(px - int(px_stored * preview_scale)) < 15 and abs(py - int(py_stored * preview_scale)) < 15:
                    hovering = i
                    break
            
            if hovering >= 0 and state["click_count"] >= 2:
                state["hovering_point"] = hovering
                state["dragging"] = True
            elif state["click_count"] < 2:
                # Yeni nokta ekle
                state["points"][state["click_count"]] = (rx, ry)
                state["click_count"] += 1
                if state["click_count"] == 2:
                    state["confirmed"] = True

        elif event == cv2.EVENT_MOUSEMOVE and state["dragging"]:
            idx = state["hovering_point"]
            if idx >= 0:
                state["points"][idx] = (rx, ry)

        elif event == cv2.EVENT_LBUTTONUP:
            state["dragging"] = False

    cv2.namedWindow(win_title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(win_title, _on_calibration_mouse, mouse_state)

    err = ""
    while True:
        mouse_state["confirmed"] = False
        # 2 nokta veya onay bekle
        while not mouse_state["confirmed"]:
            img = cv2.resize(frame, (preview_w, preview_h), interpolation=cv2.INTER_AREA)

            # Çizgi çiz
            if mouse_state["click_count"] >= 1:
                p1_px, p1_py = _to_preview_coords(*mouse_state["points"][0])
                if mouse_state["click_count"] >= 2:
                    p2_px, p2_py = _to_preview_coords(*mouse_state["points"][1])
                    cv2.line(img, (p1_px, p1_py), (p2_px, p2_py), line_color, LINE_THICKNESS)
                cv2.circle(img, (p1_px, p1_py), 6, line_color, -1)
                cv2.putText(img, "1", (p1_px - 3, p1_py + 4),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            if mouse_state["click_count"] >= 2:
                p2_px, p2_py = _to_preview_coords(*mouse_state["points"][1])
                cv2.circle(img, (p2_px, p2_py), 6, line_color, -1)
                cv2.putText(img, "2", (p2_px - 3, p2_py + 4),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Başlık
            for i, txt in enumerate(header_lines):
                col = (0, 255, 255) if i == 0 else (200, 200, 200)
                cv2.putText(img, txt, (10, 28 + i * 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)

            # Durum mesajı
            status_msg = f"Tiklamalar: {mouse_state['click_count']}/2"
            if mouse_state["click_count"] >= 1:
                p1_x, p1_y = mouse_state["points"][0]
                status_msg += f"  | Nokta 1: ({p1_x}, {p1_y})"
            if mouse_state["click_count"] >= 2:
                p2_x, p2_y = mouse_state["points"][1]
                status_msg += f"  | Nokta 2: ({p2_x}, {p2_y})"

            cv2.putText(img, status_msg, (10, preview_h - 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            # Alt yönerge
            if mouse_state["click_count"] < 2:
                guide = "SOL TIK: 2 nokta sec (soldan saga)  |  ESC: Cikis"
            else:
                guide = "ENTER: Onayla  |  SOL TIK: Noktayi tasi  |  ESC: Cikis"
            cv2.putText(img, guide, (10, preview_h - 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Hata
            if err:
                esz, _ = cv2.getTextSize(err, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                ex = preview_w // 2 - esz[0] // 2
                cv2.rectangle(img, (ex - 4, preview_h - 60), (ex + esz[0] + 4, preview_h - 38), (0, 0, 160), -1)
                cv2.putText(img, err, (ex, preview_h - 43),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow(win_title, img)
            key = cv2.waitKeyEx(30)
            if key == 27:
                cv2.destroyAllWindows()
                sys.exit(0)
            if key in (13, 10) and mouse_state["click_count"] == 2:
                mouse_state["confirmed"] = True
                break

        # Onay göster
        confirm = cv2.resize(frame, (preview_w, preview_h), interpolation=cv2.INTER_AREA)
        p1_px, p1_py = _to_preview_coords(*mouse_state["points"][0])
        p2_px, p2_py = _to_preview_coords(*mouse_state["points"][1])
        cv2.line(confirm, (p1_px, p1_py), (p2_px, p2_py), line_color, LINE_THICKNESS + 2)
        cv2.circle(confirm, (p1_px, p1_py), 7, line_color, -1)
        cv2.circle(confirm, (p2_px, p2_py), 7, line_color, -1)
        p1_x, p1_y = mouse_state["points"][0]
        p2_x, p2_y = mouse_state["points"][1]
        cv2.putText(confirm, f"SECILDI: ({p1_x},{p1_y}) -> ({p2_x},{p2_y}) - kapatiliyor...",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, line_color, 2)
        cv2.imshow(win_title, confirm)
        cv2.waitKey(800)
        break

    cv2.destroyWindow(win_title)
    return mouse_state["points"]


def calibrate_cameras(
    frame1: np.ndarray,
    frame2: np.ndarray,
    use_config_lines: bool = False,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    İKİ KAMERA ÖN AYARI: Her kameradan 2 nokta seçerek perspektif çizgisi tanımla.
    
    Kamera 1 (başlangıç): Soldan sağa gidiş
    Kamera 2 (20m): Soldan sağa gidiş
    
    Döndürür: (start_line_points, far_line_points)
    Burada her biri [(x1, y1), (x2, y2)] formatında iki noktadır.
    """
    if use_config_lines and DUAL_START_LINE_POINTS is not None and DUAL_FAR_LINE_POINTS is not None:
        print(f"  Config'den: başlangıç={DUAL_START_LINE_POINTS}, 20m={DUAL_FAR_LINE_POINTS}")
        return DUAL_START_LINE_POINTS, DUAL_FAR_LINE_POINTS

    if use_config_lines:
        print("  Config çizgileri eksik; interaktif kalibrasyona geçiliyor.")

    h1, w1 = frame1.shape[:2]
    h2, w2 = frame2.shape[:2]

    print("\n" + "=" * 70)
    print("KALIBRASYON 1/2 — KAMERA 1: Başlangıç (0m) çizgisi (2 TIKLAMA)")
    print("  Konilerin alt kısmından geçen çizgiyi belirleyin.")
    print("  1. tıklama: Solda, 2. tıklama: Sağda")
    print("=" * 70)

    suggested_start = [
        (70, int(h1 * 0.85)),
        (max(1, w1 - 70), int(h1 * 0.88))
    ]

    start_points = _calibrate_perspective_line(
        frame=frame1,
        win_title="CALIBRATION_CAM_1_START_LINE",
        line_color=COLOR_START_LINE,
        suggested_points=suggested_start,
        header_lines=[
            "KAMERA 1 — BASLANGIC CIZGISI (0m)",
            "Atletler kameraya YAKIN / BUYUK gorunur",
            "Conilerin alt kismini tanimlayan 2 noktayi secin (soldan saga)",
        ],
    )
    print(f"  → Başlangıç çizgisi: {start_points}")

    print("\n" + "=" * 70)
    print("KALIBRASYON 2/2 — KAMERA 2: 20m çizgisi (2 TIKLAMA)")
    print("  Konilerin alt kısmından geçen çizgiyi belirleyin.")
    print("  1. tıklama: Solda, 2. tıklama: Sağda")
    print("=" * 70)

    suggested_far = [
        (170, int(h2 * 0.80)),
        (max(1, w2 - 170), int(h2 * 0.83))
    ]

    far_points = _calibrate_perspective_line(
        frame=frame2,
        win_title="CALIBRATION_CAM_2_FAR_LINE",
        line_color=COLOR_FAR_LINE,
        suggested_points=suggested_far,
        header_lines=[
            "KAMERA 2 — 20m CIZGISI",
            "Atletler UZAKTA / KUCUK gorunur",
            "Conilerin alt kismini tanimlayan 2 noktayi secin (soldan saga)",
        ],
    )
    print(f"  → 20m çizgisi: {far_points}")

    print(f"\n  Başlangıç çizgisi = {start_points}")
    print(f"  20m çizgisi = {far_points}")
    return start_points, far_points


# ==============================================================================
# Görselleştirme Yardımcıları
# ==============================================================================

def assign_lane_ids(
    runners,
    frame_width: int,
    lane_count: int | None = None,
    reverse_view: bool = False,
    lane_x_min: float | None = None,
    lane_x_max: float | None = None,
):
    """
    Gercek iki kamera modunda iki bagimsiz tracker ID'sini ortak kulvar ID'sine cevirir.

    0m kamerasinda soldan saga, 20m kamerasinda sagdan sola siralanir.
    Boylece 0m'de en sagdaki yarismaci 20m'de en solda gorunuyorsa ayni ID'yi alir.
    Eksik tespitlerde ID'lerin sikismamasi icin bilinen kulvar sayisina gore
    ekrandaki yatay konuma en yakin kulvar korunur.
    """
    if not runners:
        return []

    count = lane_count or len(runners)
    if count <= 0:
        return runners

    left = 0.0 if lane_x_min is None else float(lane_x_min)
    right = float(frame_width - 1) if lane_x_max is None else float(lane_x_max)
    if right <= left:
        left, right = 0.0, float(frame_width - 1)
    width = max(1.0, right - left)

    def normalized_lane_x(runner) -> float | None:
        x = float(runner.ankle_mid_x)
        if x < left or x > right:
            return None
        norm = (x - left) / width
        return 1.0 - norm if reverse_view else norm

    best_by_lane = {}
    for r in runners:
        norm = normalized_lane_x(r)
        if norm is None:
            continue
        lane_id = int(norm * count) + 1
        lane_id = max(1, min(count, lane_id))
        existing = best_by_lane.get(lane_id)
        if existing is None or r.confidence > existing.confidence:
            best_by_lane[lane_id] = r

    return [
        replace(r, track_id=lane_id)
        for lane_id, r in sorted(best_by_lane.items())
    ]


class LaneAssigner:
    """ByteTrack ID yerine sabit kulvar merkezlerinden yarışmacı ID'si üretir."""

    def __init__(
        self,
        lane_count: int,
        frame_width: int,
        reverse_view: bool,
        lane_x_min: float,
        lane_x_max: float,
    ):
        self.lane_count = lane_count
        self.frame_width = frame_width
        self.reverse_view = reverse_view
        self.lane_x_min = lane_x_min
        self.lane_x_max = lane_x_max
        self._centers: list[float] | None = None

    def assign(self, runners):
        candidates = []
        for runner in runners:
            norm = self._normalized_x(runner.ankle_mid_x)
            if norm is not None:
                candidates.append((norm, runner))

        if self._centers is None:
            if len(candidates) < self.lane_count:
                return []
            ordered = sorted(candidates, key=lambda item: item[0])[:self.lane_count]
            self._centers = [norm for norm, _runner in ordered]
            return [
                replace(runner, track_id=lane_id)
                for lane_id, (_norm, runner) in enumerate(ordered, start=1)
            ]

        available = set(range(self.lane_count))
        assigned = []
        for norm, runner in sorted(candidates, key=lambda item: item[1].confidence, reverse=True):
            if not available:
                break
            idx = min(available, key=lambda candidate: abs(self._centers[candidate] - norm))
            available.remove(idx)
            assigned.append(replace(runner, track_id=idx + 1))

        return sorted(assigned, key=lambda runner: runner.track_id)

    def _normalized_x(self, x: float) -> float | None:
        left = float(self.lane_x_min)
        right = float(self.lane_x_max)
        if right <= left:
            left, right = 0.0, float(self.frame_width - 1)
        if x < left or x > right:
            return None
        norm = (float(x) - left) / max(1.0, right - left)
        return 1.0 - norm if self.reverse_view else norm


def _runner_color(state: RunnerState) -> tuple:
    return {
        RunnerState.ACTIVE: COLOR_ACTIVE,
        RunnerState.WARNING: COLOR_WARNING,
        RunnerState.ELIMINATED: COLOR_ELIMINATED,
    }.get(state, COLOR_ACTIVE)


def draw_runners_on_frame(
    frame: np.ndarray,
    runners,
    evaluator: DualLineEvaluator,
    current_time: float,
    id_offset: int = 0,
):
    """Koşucuları kare üzerine çizer."""
    for r in runners:
        eid = r.track_id + id_offset
        st = evaluator.get_runner_status(eid)
        if st is None:
            continue
        display_state = evaluator.get_runner_display_state(eid, current_time) or st.state.value
        is_passed = display_state.startswith("GECTI")
        color = (80, 255, 80) if is_passed else _runner_color(st.state)
        x1, y1, x2, y2 = (int(v) for v in r.bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (int(r.ankle_mid_x), int(r.ankle_mid_y)),
                   ANKLE_CIRCLE_RADIUS, (0, 180, 255), -1)
        label = f"ID:{r.track_id} [{display_state}] G:{st.total_crossings}"
        sz, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, FONT_THICKNESS)
        cv2.rectangle(frame, (x1, y1 - sz[1] - 8), (x1 + sz[0] + 4, y1), COLOR_TEXT_BG, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, color, FONT_THICKNESS)


def draw_camera_overlay(
    frame: np.ndarray,
    cam_name: str,
    line_profile: PerspectiveLine,
    line_color: tuple,
    current_time: float,
    bip_active: bool,
    evaluator: DualLineEvaluator,
    beep_times: list[float],
    shuttle_info: dict | None = None,
    bip_label: str = "BIP!",
):
    """Kamera penceresine HUD + çizgi + bip animasyonu çizer."""
    h, w = frame.shape[:2]

    # Tespit çizgisi
    line_profile.draw(frame, line_color, LINE_THICKNESS)
    mid_x = w // 2
    mid_y = int(round(line_profile.y_at(mid_x)))
    cv2.putText(frame, f"{cam_name}  perspektif cizgi",
                (10, max(20, mid_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, line_color, 2)

    # Bip flash
    if bip_active:
        cv2.rectangle(frame, (0, 0), (w, h), COLOR_BIP_FLASH, 8)
        label_size, _ = cv2.getTextSize(bip_label, cv2.FONT_HERSHEY_SIMPLEX, 1.8, 5)
        cv2.putText(frame, bip_label, (max(10, w // 2 - label_size[0] // 2), h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.8, COLOR_BIP_FLASH, 5)

    # Kamera etiketi
    cv2.rectangle(frame, (0, 0), (len(cam_name) * 14 + 20, 28), (0, 0, 0), -1)
    cv2.putText(frame, cam_name, (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, line_color, 2)

    # HUD — sol üst
    if current_time < 0:
        bip_idx = 0
        next_bip_t = -current_time
    else:
        bip_idx = sum(1 for bt in beep_times if current_time > bt)
        next_bip_t = (beep_times[bip_idx] - current_time
                      if bip_idx < len(beep_times) else 0.0)
    active = evaluator.get_active_count()
    total = len(evaluator.get_all_runner_statuses())
    if current_time < 0:
        hud_lines = [
            f"Cikis bekleniyor: {next_bip_t:.1f}s",
            f"Kosucu: {active}/{total} aktif",
            "Bip: CIKIS",
        ]
    else:
        hud_lines = [
            f"Yaris zamani: {current_time:.1f}s",
            f"Kosucu: {active}/{total} aktif",
            f"Bip: {bip_idx}/{len(beep_times)}",
            f"Sonraki: {next_bip_t:.1f}s" if next_bip_t > 0 else "Bitti",
        ]
    if shuttle_info:
        target = "20m" if shuttle_info["global_idx"] % 2 == 1 else "0m"
        hud_lines.extend([
            f"Kademe: {shuttle_info['level']}  Mekik: {shuttle_info['shuttle_in_level']}",
            f"Hiz: {shuttle_info['speed_kmh']:.1f} km/h  Hedef: {target}",
        ])
    y_hud = 55
    for line in hud_lines:
        sz, _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (5, y_hud - sz[1] - 3), (5 + sz[0] + 8, y_hud + 3), (0, 0, 0), -1)
        cv2.putText(frame, line, (9, y_hud),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_hud += 22


def build_side_by_side(frame1: np.ndarray, frame2: np.ndarray,
                       target_w: int = 640) -> np.ndarray:
    """İki kareyi yan yana birleştirir. Her biri target_w genişliğine scale edilir."""
    def _resize_to_width(img, tw):
        h, w = img.shape[:2]
        th = int(h * tw / w)
        return cv2.resize(img, (tw, th))

    f1 = _resize_to_width(frame1, target_w)
    f2 = _resize_to_width(frame2, target_w)

    # Yükseklikleri eşitle (küçük olanı pad'le)
    h1, h2 = f1.shape[0], f2.shape[0]
    if h1 != h2:
        max_h = max(h1, h2)
        if h1 < max_h:
            f1 = np.pad(f1, ((0, max_h - h1), (0, 0), (0, 0)))
        else:
            f2 = np.pad(f2, ((0, max_h - h2), (0, 0), (0, 0)))

    divider = np.full((f1.shape[0], 4, 3), 180, dtype=np.uint8)
    return np.hstack([f1, divider, f2])


# ==============================================================================
# Video Bulma
# ==============================================================================

def find_video(video_arg: str | None) -> Path:
    exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
    if video_arg:
        p = Path(video_arg)
        if p.is_file():
            return p
        print(f"[HATA] Video bulunamadı: {p}")
        sys.exit(1)
    if DATA_INPUTS.is_dir():
        for f in sorted(DATA_INPUTS.iterdir()):
            if f.suffix.lower() in exts and "camera_" not in f.name:
                print(f"[Video] Bulundu: {f}")
                return f
    print("[HATA] Video bulunamadı. --video ile belirtin.")
    sys.exit(1)


def find_dual_videos(
    video_arg: str | None,
    start_video_arg: str | None,
    far_video_arg: str | None,
) -> tuple[Path, Path, bool]:
    """
    Girdi videolarini bulur.

    Returns:
        (start_video, far_video, is_real_dual)
        is_real_dual=False ise eski tek video + zaman ofseti simulasyonu kullanilir.
    """
    if video_arg:
        video = find_video(video_arg)
        return video, video, False

    start_video = Path(start_video_arg) if start_video_arg else DEFAULT_START_CAMERA_VIDEO
    far_video = Path(far_video_arg) if far_video_arg else DEFAULT_FAR_CAMERA_VIDEO

    if start_video.is_file() and far_video.is_file():
        return start_video, far_video, True

    if start_video_arg or far_video_arg:
        missing = []
        if not start_video.is_file():
            missing.append(str(start_video))
        if not far_video.is_file():
            missing.append(str(far_video))
        print(f"[HATA] Kamera videosu bulunamadı: {', '.join(missing)}")
        sys.exit(1)

    video = find_video(None)
    return video, video, False


def download_youtube_video(url: str, output_dir: Path, filename: str) -> Path:
    """yt-dlp ile YouTube videosunu indirir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    if output_path.exists():
        print(f"[Video] Zaten mevcut: {output_path}")
        return output_path

    print(f"[Video] İndiriliyor: {url}")
    try:
        import yt_dlp

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": str(output_path),
            "quiet": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except ImportError:
        print("[HATA] yt-dlp kurulu değil. Kurmak için: pip install yt-dlp")
        sys.exit(1)
    except Exception as exc:
        print(f"[HATA] Video indirilemedi: {exc}")
        sys.exit(1)

    print(f"[Video] İndirildi: {output_path}")
    return output_path


def _audio_beeps_to_run_deadlines(
    raw_beep_times: list[float],
    start_time_sec: float,
) -> tuple[list[float], float | None]:
    """
    Video başından ölçülen bipleri yarış süresindeki mekik bitiş biplerine çevirir.

    Video basindan olculen bipleri yaris suresindeki deadline'lara cevirir.

    Eger ilk ses bipi video baslangicina cok yakinsa start bipi kabul edilip
    degerlendirmeden cikarilir. Ilk ses bipi daha gec geliyorsa bu video
    start bipinden sonra baslamis demektir; ilk bip ilk hedef deadline'i sayilir.
    """
    if not raw_beep_times:
        return [], None

    raw = sorted(raw_beep_times)
    rel = sorted(round(t - start_time_sec, 3) for t in raw if t >= start_time_sec)
    if rel and rel[0] <= 2.0:
        print(f"[Ses] Start bipi değerlendirmeden çıkarıldı: {rel[0]:.3f}s")
        rel = rel[1:]
    return rel, None


def _merge_beep_times(*beep_lists: list[float], merge_window_sec: float = 0.75) -> list[float]:
    """Iki kamera sesinden gelen yakin bipleri tek zaman cizelgesinde birlestirir."""
    merged: list[float] = []
    for t in sorted(t for times in beep_lists for t in times):
        if not merged or abs(t - merged[-1]) > merge_window_sec:
            merged.append(float(t))
        else:
            merged[-1] = (merged[-1] + float(t)) / 2.0
    return [round(t, 3) for t in merged]


def _build_directional_beep_schedule(
    start_camera_beeps: list[float],
    far_camera_beeps: list[float],
    start_time_sec: float,
) -> list[float]:
    """
    Cift kamera seslerinden sirali hedef deadline listesi kurar.

    Tek sayili mekikler 20m kamerasindan, cift sayili mekikler 0m kamerasindan
    gelen bir sonraki bip adayi ile eslestirilir. Bu, her iki kameranin ayni
    global sesi farkli kalitede kaydettigi videolarda yanlis erken adaylari
    azaltir.
    """
    start_rel = [round(t - start_time_sec, 3) for t in sorted(start_camera_beeps) if t >= start_time_sec + 1.0]
    far_rel = [round(t - start_time_sec, 3) for t in sorted(far_camera_beeps) if t >= start_time_sec + 1.0]
    if not far_rel and not start_rel:
        return []

    schedule: list[float] = []
    i_start = 0
    i_far = 0
    last_t = 0.0
    for shuttle_idx in range(len(start_rel) + len(far_rel)):
        use_far = shuttle_idx % 2 == 0
        source = far_rel if use_far else start_rel
        idx = i_far if use_far else i_start
        while idx < len(source) and source[idx] <= last_t + 1.0:
            idx += 1
        if idx >= len(source):
            break
        t = source[idx]
        schedule.append(t)
        last_t = t
        if use_far:
            i_far = idx + 1
        else:
            i_start = idx + 1

    return schedule


# ==============================================================================
# Ana İşleme Döngüsü
# ==============================================================================

def process_dual_camera(
    start_video_path: Path,
    far_video_path: Path | None = None,
    real_dual_camera: bool = True,
    display: bool = True,
    start_time_sec: float = VIDEO_START_TIME_SEC,
    cam2_offset_sec: float = CAM2_OFFSET_SEC,
    use_audio: bool = True,
    max_frames: int | None = None,
    beep_times_override: list[float] | None = None,
    beep_audio_url: str | None = None,
    start_beep_time_override: float | None = None,
    use_config_lines: bool = False,
):
    far_video_path = far_video_path or start_video_path
    if real_dual_camera and cam2_offset_sec == CAM2_OFFSET_SEC:
        cam2_offset_sec = 0.0

    print(f"\n{'='*65}")
    print(f"  Çift Kamera Mekik Testi")
    print(f"{'='*65}")
    print(f"  Kamera 1   : {start_video_path.name} (0m / başlangıç)")
    print(f"  Kamera 2   : {far_video_path.name} (20m)")
    print(f"  Mod        : {'iki ayrı video' if real_dual_camera else 'tek video + ofset simülasyonu'}")
    print(f"  Kamera 1   : t={start_time_sec:.1f}s (başlangıç çizgisi)")
    print(f"  Kamera 2   : t={start_time_sec + cam2_offset_sec:.1f}s "
          f"({cam2_offset_sec:.1f}s ofset — 20m çizgisi)")
    print("  Zamanlayıcı: referans bip videosu" if beep_audio_url else "  Zamanlayıcı: resmi mekik temposu")
    print(f"  Ses tespiti: {'referans bip videosu' if beep_audio_url else ('sadece çıkış bipi' if use_audio else 'KAPALI')}")
    print(f"  Çizgi seçimi: {'config dosyasından' if use_config_lines else 'kullanıcı kalibrasyonu'}")
    print(f"  Çizgi takip: {'AÇIK' if ENABLE_AUTO_LINE_TRACKING else 'KAPALI'}")
    run_zero_time_sec = start_time_sec

    # ------------------------------------------------------------------
    # 1. Kamera simülasyonu video kopyaları
    # ------------------------------------------------------------------
    if not real_dual_camera:
        create_dual_camera_videos(start_video_path, DATA_OUTPUTS)

    # ------------------------------------------------------------------
    # 2. İki bağımsız video akışı aç
    # ------------------------------------------------------------------
    cap1 = cv2.VideoCapture(str(start_video_path))
    cap2 = cv2.VideoCapture(str(far_video_path))

    if not cap1.isOpened() or not cap2.isOpened():
        print("[HATA] Video açılamadı.")
        sys.exit(1)

    fps        = cap1.get(cv2.CAP_PROP_FPS) or 30.0
    fps2       = cap2.get(cv2.CAP_PROP_FPS) or fps
    total_f    = int(cap1.get(cv2.CAP_PROP_FRAME_COUNT))
    total_f2   = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT))
    w          = int(cap1.get(cv2.CAP_PROP_FRAME_WIDTH))
    h          = int(cap1.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w2         = int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH))
    h2         = int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration   = total_f / fps
    duration2  = total_f2 / fps2 if fps2 else 0.0
    cam2_start = start_time_sec + cam2_offset_sec

    print(f"  Kamera 1   : {w}x{h} @ {fps:.1f} FPS, {duration:.1f}s")
    print(f"  Kamera 2   : {w2}x{h2} @ {fps2:.1f} FPS, {duration2:.1f}s")

    # Kamera 1: koşu başından
    cap1.set(cv2.CAP_PROP_POS_MSEC, start_time_sec * 1000)
    # Kamera 2: 9s sonradan (20m çizgisine ilk varış zamanı)
    cap2.set(cv2.CAP_PROP_POS_MSEC, cam2_start * 1000)

    # ------------------------------------------------------------------
    # 3. Çıkış bipi + resmi mekik zamanlayıcı
    # ------------------------------------------------------------------
    run_beep_times: list[float] = []
    official_timer: ShuttleTimer | None = None
    if beep_times_override:
        run_beep_times = sorted(beep_times_override)
        print(f"[Ses] Manuel bip çizelgesi kullanılıyor: {[round(t, 2) for t in run_beep_times[:10]]}")
    elif beep_audio_url:
        beep_video = download_youtube_video(
            beep_audio_url,
            DATA_INPUTS,
            "reference_beep_audio.mp4",
        )
        detector = BeepDetector()
        raw_beeps = detector.detect_beeps(beep_video)
        run_beep_times, _unused_start = _audio_beeps_to_run_deadlines(raw_beeps, 0.0)
        if not run_beep_times:
            print("[HATA] Referans bip videosundan bip zamanı çıkarılamadı.")
            sys.exit(1)
        print(f"[Ses] Referans bip çizelgesi kullanılıyor: {[round(t, 2) for t in run_beep_times[:10]]}")
        start_beep_time = (
            start_beep_time_override
            if start_beep_time_override is not None
            else DEFAULT_START_BEEP_TIME_SEC
        )
        if start_beep_time is not None:
            run_zero_time_sec = start_beep_time
            print(
                f"[Timer] Yarış saati {run_zero_time_sec:.3f}s çıkış bipiyle sıfırlanacak; "
                "hedef bipleri referans videodan alınacak."
            )
    else:
        start_beep_time = (
            start_beep_time_override
            if start_beep_time_override is not None
            else DEFAULT_START_BEEP_TIME_SEC
        )
        if start_beep_time is not None:
            print(f"[Timer] Çıkış bipi sabit: {start_beep_time:.3f}s")
        elif use_audio:
            detector = BeepDetector()
            raw_start = detector.detect_beeps(start_video_path)
            raw_far = []
            if far_video_path != start_video_path:
                raw_far = detector.detect_beeps(far_video_path)
            all_start_candidates = sorted(
                t for t in [*raw_start, *raw_far] if t >= start_time_sec
            )
            if all_start_candidates:
                start_beep_time = all_start_candidates[0]
                print(f"[Ses] Çıkış bipi algılandı: {start_beep_time:.3f}s")
                print(f"[Ses] Adaylar: {[round(t, 2) for t in all_start_candidates[:8]]}")
            else:
                print("[Ses] Çıkış bipi bulunamadı; video başlangıcı yarış başlangıcı kabul ediliyor.")

        if start_beep_time is not None:
            run_zero_time_sec = start_beep_time
            print(
                f"[Timer] Yarış saati {run_zero_time_sec:.3f}s çıkış bipiyle sıfırlanacak; "
                f"video {start_time_sec:.3f}s'den oynayacak."
            )

        official_timer = ShuttleTimer(0.0)
        preview_deadlines = official_timer.get_deadline_times()
        print(f"[Timer] İlk hedef deadline: {preview_deadlines[0]:.3f}s (çıkıştan sonra)")
        official_timer.print_schedule(max_levels=2)

    fallback = official_timer

    # ------------------------------------------------------------------
    # 4. Kalibrasyon — her kameranın ilk karesinden
    # ------------------------------------------------------------------
    print("\n[Kalibrasyon] İlk kareler alınıyor...")
    ret1, frame1_cal = cap1.read()
    ret2, frame2_cal = cap2.read()
    if not ret1 or not ret2:
        print("[HATA] İlk kareler okunamadı.")
        sys.exit(1)

    # Kamera başlarını sıfırla
    cap1.set(cv2.CAP_PROP_POS_MSEC, start_time_sec * 1000)
    cap2.set(cv2.CAP_PROP_POS_MSEC, cam2_start * 1000)

    start_line_points, far_line_points = calibrate_cameras(
        frame1_cal,
        frame2_cal,
        use_config_lines=use_config_lines,
    )
    start_line_profile_base = PerspectiveLine.from_points(start_line_points)
    far_line_profile_base = PerspectiveLine.from_points(far_line_points)
    start_line_y = start_line_profile_base.median_y
    far_line_y = far_line_profile_base.median_y
    print(f"  Perspektif başlangıç çizgisi: {[(int(x), int(y)) for x, y in start_line_profile_base.points]}")
    print(f"  Perspektif 20m çizgisi      : {[(int(x), int(y)) for x, y in far_line_profile_base.points]}")

    if display:
        preview1 = frame1_cal.copy()
        preview2 = frame2_cal.copy()
        start_line_profile_base.draw(preview1, COLOR_START_LINE, LINE_THICKNESS)
        cv2.putText(preview1, "KAMERA 1 - BASLANGIC (0m)",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_START_LINE, 2)
        far_line_profile_base.draw(preview2, COLOR_FAR_LINE, LINE_THICKNESS)
        cv2.putText(preview2, "KAMERA 2 - 20m",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_FAR_LINE, 2)
        preview_dual = build_side_by_side(preview1, preview2, target_w=min(640, w))
        cv2.namedWindow("Mekik Testi — Cift Kamera Tek Ekran", cv2.WINDOW_NORMAL)
        cv2.imshow("Mekik Testi — Cift Kamera Tek Ekran", preview_dual)
        cv2.waitKey(500)

    # ------------------------------------------------------------------
    # 5. Modüller
    # ------------------------------------------------------------------
    print("\n[Modüller] Başlatılıyor...")
    tracker1 = PoseTracker()
    tracker2 = PoseTracker()
    
    # Adaptadores de cone (se habilitado)
    start_cone_adapter = None
    far_cone_adapter = None
    if ENABLE_CONE_DETECTION and CONE_DETECTOR_AVAILABLE:
        print(f"[Cones] Detecção dinamica habilitada")
        start_cone_adapter = ConeLineAdapter(w, h)
        far_cone_adapter = ConeLineAdapter(w2, h2)
    elif ENABLE_CONE_DETECTION and not CONE_DETECTOR_AVAILABLE:
        print("[AVISO] cone_detector nao disponivel, usando linhas fixas")

    evaluator = DualLineEvaluator(
        start_line_y=start_line_y,
        far_line_y=far_line_y,
        beep_times=run_beep_times,
        start_line_profile=start_line_profile_base,
        far_line_profile=far_line_profile_base,
        fallback_timer=fallback,
        start_target_side="below",
        far_target_side="below",
    )
    beep_times_list = evaluator.get_beep_times()

    start_lane_assigner = LaneAssigner(
        lane_count=EXPECTED_RUNNER_COUNT,
        frame_width=w,
        reverse_view=False,
        lane_x_min=start_line_profile_base.min_x,
        lane_x_max=start_line_profile_base.max_x,
    )
    far_lane_assigner = LaneAssigner(
        lane_count=EXPECTED_RUNNER_COUNT,
        frame_width=w2,
        reverse_view=True,
        lane_x_min=far_line_profile_base.min_x,
        lane_x_max=far_line_profile_base.max_x,
    )

    line_tracker_cfg = LineTrackerConfig(
        search_margin_px=LINE_TRACK_SEARCH_MARGIN_PX,
        min_confidence=LINE_TRACK_MIN_CONFIDENCE,
        smoothing_alpha=LINE_TRACK_SMOOTHING_ALPHA,
        max_step_px=LINE_TRACK_MAX_STEP_PX,
    )
    start_line_tracker = HorizontalLineTracker(start_line_y, line_tracker_cfg)
    far_line_tracker = HorizontalLineTracker(far_line_y, line_tracker_cfg)

    # ------------------------------------------------------------------
    # 6. Çıktı video (yan yana, 640px per panel)
    # ------------------------------------------------------------------
    panel_w   = min(640, w)
    panel_h   = int(h * panel_w / w)
    out_w     = panel_w * 2 + 4
    out_h     = panel_h
    out_stem = f"{start_video_path.stem}_{far_video_path.stem}" if real_dual_camera else start_video_path.stem
    out_path  = DATA_OUTPUTS / f"{out_stem}_dual_camera.mp4"
    DATA_OUTPUTS.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h)
    )

    # ------------------------------------------------------------------
    # 7. Pencereler
    # ------------------------------------------------------------------
    WIN_DUAL = "Mekik Testi — Cift Kamera Tek Ekran"

    if display:
        cv2.namedWindow(WIN_DUAL, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_DUAL, out_w, out_h)

    # ------------------------------------------------------------------
    # 8. İşleme döngüsü
    # ------------------------------------------------------------------
    print(f"\n[İşleme] Başlıyor — q veya ESC ile dur")
    if real_dual_camera:
        print("  ID eşleştirme: 0m soldan-sağa, 20m sağdan-sola ortak kulvar ID")
    else:
        print(f"  ID eşleştirme: {'tek video simülasyonu (ortak ID)' if CAM2_SHARE_TRACK_IDS else 'kamera ofsetli ID'}")
    frame_idx    = 0
    proc_fps     = 0.0
    t_wall_start = time.time()
    remaining    = total_f - int(start_time_sec * fps)

    bip_flash1 = 0   # Kamera 1 bip animasyon sayacı
    bip_flash2 = 0   # Kamera 2 bip animasyon sayacı
    BIP_DUR    = max(1, int(fps * 0.4))
    last_bip_i1 = 0
    last_bip_i2 = 0
    start_flash1 = 0
    start_flash2 = 0
    start_bip_fired1 = False
    start_bip_fired2 = False

    while True:
        ret1, frame1 = cap1.read()
        if not ret1:
            break

        ret2, frame2 = cap2.read()
        # Kamera 2 bitti ama kamera 1 devam ediyorsa siyah kare
        if not ret2:
            frame2 = np.zeros_like(frame1)

        t0 = time.time()

        # Zaman hesabı. CAP_PROP_POS_MSEC farklı FPS'li iki gerçek kamerada
        # frame index varsayımından daha doğru sonuç verir.
        cam1_video_time = cap1.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        cam2_video_time = cap2.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        cam1_time = cam1_video_time - run_zero_time_sec
        cam2_time = cam2_video_time - run_zero_time_sec

        current_start_line_profile = start_line_profile_base
        current_far_line_profile = far_line_profile_base
        
        # Detecção dinâmica de cones (substitui linha fixa se habilitada)
        if ENABLE_CONE_DETECTION and start_cone_adapter is not None:
            try:
                cone_start_line = start_cone_adapter.detect_and_create_line(frame1)
                if cone_start_line is not None:
                    current_start_line_profile = cone_start_line
            except Exception as e:
                print(f"[Dual] Erro na detecção de cones da câmera 1: {e}")
            
            if ret2 and far_cone_adapter is not None:
                try:
                    cone_far_line = far_cone_adapter.detect_and_create_line(frame2)
                    if cone_far_line is not None:
                        current_far_line_profile = cone_far_line
                except Exception as e:
                    print(f"[Dual] Erro na detecção de cones da câmera 2: {e}")
            
            # Atualiza evaluador com as linhas detectadas (quer sejam de cones ou base)
            evaluator.start_line_y = current_start_line_profile.median_y
            evaluator.far_line_y = current_far_line_profile.median_y
            evaluator.start_line_profile = current_start_line_profile
            evaluator.far_line_profile = current_far_line_profile
        
        # Rastreamento automático de linha (se habilitado e cones desabilitados)
        elif ENABLE_AUTO_LINE_TRACKING:
            current_start_line_y = start_line_tracker.update(frame1)
            current_start_line_profile = start_line_profile_base.shifted(
                current_start_line_y - start_line_profile_base.median_y
            )
            if ret2:
                current_far_line_y = far_line_tracker.update(frame2)
                current_far_line_profile = far_line_profile_base.shifted(
                    current_far_line_y - far_line_profile_base.median_y
                )
            evaluator.start_line_y = current_start_line_profile.median_y
            evaluator.far_line_y = current_far_line_profile.median_y
            evaluator.start_line_profile = current_start_line_profile
            evaluator.far_line_profile = current_far_line_profile

        if not start_bip_fired1 and cam1_time >= 0:
            start_flash1 = BIP_DUR
            start_bip_fired1 = True
        if not start_bip_fired2 and cam2_time >= 0:
            start_flash2 = BIP_DUR
            start_bip_fired2 = True

        # Poz tespiti — iki tracker bağımsız
        runners1 = tracker1.process_frame(frame1)
        runners2 = tracker2.process_frame(frame2) if ret2 else []
        if real_dual_camera:
            runners1 = start_lane_assigner.assign(runners1)
            runners2 = far_lane_assigner.assign(runners2)

        # Değerlendirici güncelleme. Çıkış bipinden önceki hareketler sayılmaz.
        if cam1_time >= 0:
            for r in runners1:
                foot_y = float(r.bbox[3])
                evaluator.update_camera_line(
                    r.track_id,
                    r.ankle_mid_x,
                    foot_y,
                    cam1_time,
                    target_line="start",
                )

            # Başlangıç çizgisi yalnızca dönüş mekiği deadline'larını kapatır.
            evaluator.check_beep_deadlines(cam1_time, expected_direction="to_near")

        if cam2_time >= 0:
            for r in runners2:
                # Tek video simülasyonunda aynı track ID aynı yarışmacı kabul edilir.
                eval_id = r.track_id if (real_dual_camera or CAM2_SHARE_TRACK_IDS) else r.track_id + CAM2_ID_OFFSET
                foot_y = float(r.bbox[3])
                evaluator.update_camera_line(
                    eval_id,
                    r.ankle_mid_x,
                    foot_y,
                    cam2_time,
                    target_line="far",
                )

            # 20m kamerası 9s ileriden okunduğu için sadece 20m varışlarını kontrol eder.
            evaluator.check_beep_deadlines(cam2_time, expected_direction="to_far")

        # Bip flash animasyonu
        while last_bip_i1 < len(beep_times_list):
            bt = beep_times_list[last_bip_i1]
            if cam1_time >= bt:
                bip_flash1 = BIP_DUR
                last_bip_i1 += 1
            else:
                break

        while last_bip_i2 < len(beep_times_list):
            bt = beep_times_list[last_bip_i2]
            if cam2_time >= bt:
                bip_flash2 = BIP_DUR
                last_bip_i2 += 1
            else:
                break

        bip_flash1 = max(0, bip_flash1 - 1)
        bip_flash2 = max(0, bip_flash2 - 1)
        start_flash1 = max(0, start_flash1 - 1)
        start_flash2 = max(0, start_flash2 - 1)

        # ----------------------------------------------------------
        # Görselleştirme
        # ----------------------------------------------------------
        ann1 = frame1.copy()
        ann2 = frame2.copy()

        # Koşucuları çiz
        draw_runners_on_frame(ann1, runners1, evaluator, cam1_time, id_offset=0)
        draw_runners_on_frame(
            ann2,
            runners2,
            evaluator,
            cam2_time,
            id_offset=0 if (real_dual_camera or CAM2_SHARE_TRACK_IDS) else CAM2_ID_OFFSET,
        )

        # Çizgi + HUD
        shuttle_info1 = official_timer.get_current_shuttle(cam1_time) if official_timer and cam1_time >= 0 else None
        shuttle_info2 = official_timer.get_current_shuttle(cam2_time) if official_timer and cam2_time >= 0 else None
        draw_camera_overlay(ann1, "KAMERA 1 — BASLANGIC (0m)",
                            current_start_line_profile, COLOR_START_LINE,
                            cam1_time,
                            (start_flash1 > 0 or bip_flash1 > 0),
                            evaluator,
                            beep_times_list,
                            shuttle_info=shuttle_info1,
                            bip_label="CIKIS BIPI!" if start_flash1 > 0 else "BIP!")
        draw_camera_overlay(ann2, "KAMERA 2 — 20m CIZGISI",
                            current_far_line_profile, COLOR_FAR_LINE,
                            cam2_time,
                            (start_flash2 > 0 or bip_flash2 > 0),
                            evaluator,
                            beep_times_list,
                            shuttle_info=shuttle_info2,
                            bip_label="CIKIS BIPI!" if start_flash2 > 0 else "BIP!")
        
        # Debug: desenha cones detectados (se habilitado)
        if CONE_DEBUG_DRAW:
            if start_cone_adapter is not None:
                start_cone_adapter.draw_debug_cones(ann1)
            if ret2 and far_cone_adapter is not None:
                far_cone_adapter.draw_debug_cones(ann2)

        # Yan yana panel (çıktı video)
        dual = build_side_by_side(ann1, ann2, target_w=panel_w)
        writer.write(dual)

        # Ekran gösterimi
        if display and frame_idx % DISPLAY_EVERY_N_FRAMES == 0:
            cv2.imshow(WIN_DUAL, dual)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                print("\n[Kullanıcı] Durduruldu.")
                break

        proc_fps  = 1.0 / (time.time() - t0 + 1e-9)
        frame_idx += 1

        if display and REALTIME_PREVIEW:
            target_frame_idx = int((time.time() - t_wall_start) * fps)
            skip_count = min(
                MAX_REALTIME_FRAME_SKIP,
                max(0, target_frame_idx - frame_idx),
            )
            if max_frames is not None:
                skip_count = min(skip_count, max(0, max_frames - frame_idx))

            for _ in range(skip_count):
                ret_skip1 = cap1.grab()
                ret_skip2 = cap2.grab()
                if not ret_skip1:
                    break
                if not ret_skip2:
                    pass
                writer.write(dual)
                frame_idx += 1

        if max_frames is not None and frame_idx >= max_frames:
            print(f"\n[Test] max_frames={max_frames} sınırında duruldu.")
            break

        if frame_idx % 150 == 0:
            pct = frame_idx / remaining * 100 if remaining > 0 else 0
            print(f"  {frame_idx}/{remaining} ({pct:.1f}%) | "
                  f"{proc_fps:.1f} FPS | {time.time()-t_wall_start:.0f}s")

    # ------------------------------------------------------------------
    # 9. Temizlik + Rapor
    # ------------------------------------------------------------------
    cap1.release()
    cap2.release()
    writer.release()
    if display:
        cv2.destroyAllWindows()

    elapsed = time.time() - t_wall_start
    print(f"\n{'='*65}")
    print(f"  Tamamlandı! {frame_idx} kare — {elapsed:.1f}s")
    print(f"  Çıktı : {out_path}")
    print(f"{'='*65}")

    print(f"\n  SONUÇ RAPORU")
    print(f"{'='*65}")
    df = evaluator.get_results_dataframe()
    print(df.to_string(index=False) if not df.empty else "  Koşucu tespit edilmedi.")

    evaluator.export_results(DATA_OUTPUTS)
    print(f"  Raporlar: {DATA_OUTPUTS}")
    print(f"{'='*65}\n")


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Çift Kamera + Ses Tabanlı Mekik Testi"
    )
    parser.add_argument("--video", "-v", type=str, default=None,
                        help="Eski mod: tek video + kamera 2 zaman ofseti simülasyonu")
    parser.add_argument("--start-video", type=str, default=None,
                        help="0m / başlangıç kamerası videosu (varsayılan: 0metre.mp4)")
    parser.add_argument("--far-video", type=str, default=None,
                        help="20m kamerası videosu (varsayılan: 20metre.mp4)")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--start-time", type=float, default=VIDEO_START_TIME_SEC,
                        help=f"Koşu başlangıcı (varsayılan: {VIDEO_START_TIME_SEC}s)")
    parser.add_argument("--cam2-offset", type=float, default=None,
                        help="Kamera 2 zaman ofseti. İki ayrı videoda varsayılan 0.0, tek videoda 9.0")
    parser.add_argument("--max-frames", type=int, default=None,
                        help="Test/debug için işlenecek maksimum kare sayısı")
    parser.add_argument("--beep-times", type=str, default=None,
                        help="Manuel bip saniyeleri, virgülle: 12.8,19.6,28.5")
    parser.add_argument("--beep-audio-url", type=str, default=DEFAULT_BEEP_AUDIO_URL,
                        help="Referans bip sesini içeren YouTube URL'si")
    parser.add_argument("--start-beep-time", type=float, default=None,
                        help="Manuel çıkış bipi video saniyesi; sonrası resmi mekik temposuyla hesaplanır")
    parser.add_argument("--use-config-lines", action="store_true",
                        help="Fareyle seçmek yerine config.py içindeki hazır çift kamera çizgilerini kullan")
    args = parser.parse_args()

    start_video, far_video, real_dual_camera = find_dual_videos(
        args.video,
        args.start_video,
        args.far_video,
    )
    cam2_offset = args.cam2_offset
    if cam2_offset is None:
        cam2_offset = 0.0 if real_dual_camera else CAM2_OFFSET_SEC
    beep_times_override = None
    if args.beep_times:
        beep_times_override = [
            float(part.strip())
            for part in args.beep_times.split(",")
            if part.strip()
        ]

    process_dual_camera(
        start_video_path=start_video,
        far_video_path=far_video,
        real_dual_camera=real_dual_camera,
        display=not args.no_display,
        start_time_sec=args.start_time,
        cam2_offset_sec=cam2_offset,
        use_audio=not args.no_audio,
        max_frames=args.max_frames,
        beep_times_override=beep_times_override,
        beep_audio_url=args.beep_audio_url,
        start_beep_time_override=args.start_beep_time,
        use_config_lines=args.use_config_lines,
    )


if __name__ == "__main__":
    main()
