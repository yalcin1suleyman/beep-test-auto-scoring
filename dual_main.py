"""
dual_main.py - Çift Kamera + Ses Tabanlı Mekik Testi Değerlendirme Sistemi

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
import json
import math
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from config import (
    DATA_OUTPUTS,
    SAMPLE_INPUTS,
    REFERENCE_INPUTS,
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
    ENABLE_CAMERA_MOTION_COMPENSATION,
    MOTION_COMP_UPDATE_EVERY,
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
from camera_motion import CameraMotionCompensator, MotionCompensatorConfig
from line_calibrator import DualLineCalibrator
from validators import validate_video_file
from video_dashboard import render_dashboard
from result_report import TECH_DIR, write_readable_outputs

# Sistema de detecção dinâmica de cones
try:
    from cone_line_adapter import ConeLineAdapter
    CONE_DETECTOR_AVAILABLE = True
except ImportError:
    CONE_DETECTOR_AVAILABLE = False


# ==============================================================================
# Renk Sabitleri
# ==============================================================================
COLOR_START_LINE = (0, 220, 0)      # Yeşil - başlangıç (0m) çizgisi
COLOR_FAR_LINE   = (0, 140, 255)    # Turuncu - 20m çizgisi
COLOR_BIP_FLASH  = (0, 255, 255)    # Sarı - bip animasyonu


# ==============================================================================
# İki Nokta Çizgi Kalibrasyonu - Perspektif Çizgisi (2 tıklama)
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
        raise ValueError("Config cizgileri eksik. --start-line ve --far-line ile koordinat belirtin.")

    h1, w1 = frame1.shape[:2]
    h2, w2 = frame2.shape[:2]

    print("\n" + "=" * 70)
    print("KALIBRASYON 1/2 - KAMERA 1: Başlangıç (0m) çizgisi (2 TIKLAMA)")
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
            "KAMERA 1 - BASLANGIC CIZGISI (0m)",
            "Atletler kameraya YAKIN / BUYUK gorunur",
            "Conilerin alt kismini tanimlayan 2 noktayi secin (soldan saga)",
        ],
    )
    print(f"  → Başlangıç çizgisi: {start_points}")

    print("\n" + "=" * 70)
    print("KALIBRASYON 2/2 - KAMERA 2: 20m çizgisi (2 TIKLAMA)")
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
            "KAMERA 2 - 20m CIZGISI",
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


def filter_line_candidates(runners, line_profile, frame_height, margin_ratio=0.14):
    """Only runners near this camera's finish line can provide scoring evidence.

    Distant spectators and pose-like background objects must not steal lane IDs.
    Raw detections remain available to the camera-motion mask before this filter.
    """
    margin = max(40.0, frame_height * margin_ratio)
    return [r for r in runners
            if np.isfinite(r.ankle_mid_x) and np.isfinite(r.bbox[3])
            and line_profile.min_x <= r.ankle_mid_x <= line_profile.max_x
            and abs(float(r.bbox[3]) - line_profile.y_at(r.ankle_mid_x)) <= margin]


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
            strongest = sorted(candidates, key=lambda item: item[1].confidence, reverse=True)[:self.lane_count]
            ordered = sorted(strongest, key=lambda item: item[0])
            self._centers = [norm for norm, _runner in ordered]
            return [
                replace(runner, track_id=lane_id)
                for lane_id, (_norm, runner) in enumerate(ordered, start=1)
            ]

        # Match all detections jointly. Greedy confidence order can let the first
        # detection steal its neighbour's lane and swap two runner identities.
        strongest = sorted(candidates, key=lambda item: item[1].confidence, reverse=True)[:self.lane_count]
        ordered = sorted(strongest, key=lambda item: item[0])
        if not ordered:
            return []
        costs = np.abs(np.array([n for n, _ in ordered])[:, None] - np.array(self._centers)[None, :])
        _, indices = linear_sum_assignment(costs)
        assigned = [replace(runner, track_id=int(idx)+1)
                    for (_, runner), idx in zip(ordered, sorted(indices))]

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
        label = f"#{r.track_id}"
        label_y = max(22, y1)
        cv2.rectangle(frame, (max(0,x1), label_y-22), (max(0,x1)+40, label_y), (28,21,15), -1)
        cv2.putText(frame, label, (max(0,x1)+4, label_y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1, cv2.LINE_AA)


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
    if bip_active:
        cv2.rectangle(frame, (1, 1), (w-2, h-2), COLOR_BIP_FLASH, 4)
    return


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
    combined = np.hstack([f1, divider, f2])
    # mp4v requires even dimensions; preserve every source pixel with padding.
    return np.pad(combined, ((0, combined.shape[0] % 2), (0, 0), (0, 0)))


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
    if SAMPLE_INPUTS.is_dir():
        for f in sorted(SAMPLE_INPUTS.iterdir()):
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


def _reference_beeps_to_run_deadlines(raw_beep_times: list[float]) -> list[float]:
    """
    Referans bip kaydindaki bipleri cikis bipine gore deadline listesine cevirir.

    Referans kaydin ilk bipi cikis bipidir; deadline'lar ondan itibaren olculur.
    Seviye gecis sinyali farkli tonda caldigi icin bant filtresi onu kacirabilir.
    Iki bip arasi bosluk onceki aralik ile tam kat ise eksik bipler onceki
    tempoyla tamamlanir; aksi halde mekik sirasi (gidis/donus yonu) kayardi.
    """
    beeps = sorted(float(t) for t in raw_beep_times)
    if len(beeps) < 2:
        return []
    filled = [beeps[0]]
    for t in beeps[1:]:
        prev = filled[-1]
        interval = prev - filled[-2] if len(filled) >= 2 else t - prev
        gap = t - prev
        if interval > 0:
            missing = round(gap / interval) - 1
            if missing >= 1 and abs(gap - (missing + 1) * interval) < 0.3 * interval:
                filled.extend(prev + k * interval for k in range(1, missing + 1))
        filled.append(t)
    start = filled[0]
    return [round(t - start, 3) for t in filled[1:]]


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
    cam2_offset_sec: float | None = None,
    use_audio: bool = True,
    max_frames: int | None = None,
    beep_times_override: list[float] | None = None,
    beep_audio_url: str | None = None,
    start_beep_time_override: float | None = None,
    use_config_lines: bool = False,
    start_line_points: list[tuple[int, int]] | None = None,
    far_line_points: list[tuple[int, int]] | None = None,
    output_dir: Path | None = None,
    runner_count: int = EXPECTED_RUNNER_COUNT,
    hold_open: bool = False,
    realtime_preview: bool = False,
    motion_compensation: bool = ENABLE_CAMERA_MOTION_COMPENSATION,
    report_title: str = "Mekik testi sonucu",
    report_note: str = "",
    scoring_eligible: bool = True,
):
    start_video_path = validate_video_file(start_video_path)
    far_video_path = far_video_path or start_video_path
    far_video_path = validate_video_file(far_video_path)
    if cam2_offset_sec is None:
        cam2_offset_sec = 0.0 if real_dual_camera else CAM2_OFFSET_SEC
    if not math.isfinite(start_time_sec) or start_time_sec < 0 or not math.isfinite(cam2_offset_sec):
        raise ValueError("Baslangic ve ofset sonlu olmali; baslangic negatif olamaz.")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames pozitif olmalidir.")
    if runner_count <= 0:
        raise ValueError("Kosucu sayisi pozitif olmalidir.")
    if start_beep_time_override is not None and (
        not math.isfinite(start_beep_time_override) or start_beep_time_override < 0
    ):
        raise ValueError("Cikis bipi sonlu ve negatif olmayan bir saniye olmalidir.")
    output_dir = Path(output_dir) if output_dir is not None else DATA_OUTPUTS
    if not use_audio:
        beep_audio_url = None
    if not display and not (start_line_points and far_line_points):
        if not (use_config_lines and DUAL_START_LINE_POINTS and DUAL_FAR_LINE_POINTS):
            raise ValueError("Ekransiz mod icin --start-line ve --far-line veya dolu config cizgileri gerekir.")

    print(f"\n{'='*65}")
    print(f"  Çift Kamera Mekik Testi")
    print(f"{'='*65}")
    print(f"  Kamera 1   : {start_video_path.name} (0m / başlangıç)")
    print(f"  Kamera 2   : {far_video_path.name} (20m)")
    print(f"  Mod        : {'iki ayrı video' if real_dual_camera else 'tek video + ofset simülasyonu'}")
    print(f"  Kamera 1   : t={start_time_sec:.1f}s (başlangıç çizgisi)")
    print(f"  Kamera 2   : t={start_time_sec + cam2_offset_sec:.1f}s "
          f"({cam2_offset_sec:.1f}s ofset - 20m çizgisi)")
    print("  Zamanlayıcı: referans bip videosu" if beep_audio_url else "  Zamanlayıcı: resmi mekik temposu")
    print(f"  Ses tespiti: {'referans bip videosu' if beep_audio_url else ('sadece çıkış bipi' if use_audio else 'KAPALI')}")
    print(f"  Çizgi seçimi: {'config dosyasından' if use_config_lines else 'kullanıcı kalibrasyonu'}")
    print(f"  Çizgi takip: {'AÇIK' if ENABLE_AUTO_LINE_TRACKING else 'KAPALI'}")
    print(f"  Kamera kayma telafisi: {'AÇIK' if motion_compensation else 'KAPALI'}")
    run_zero_time_sec = start_time_sec

    # ------------------------------------------------------------------
    # 1. Kamera simülasyonu video kopyaları
    # ------------------------------------------------------------------
    if not real_dual_camera:
        create_dual_camera_videos(start_video_path, DATA_OUTPUTS)

    # ------------------------------------------------------------------
    # 2. İki bağımsız video akışı aç
    # ------------------------------------------------------------------
    with ExitStack() as resources:
        cap1 = cv2.VideoCapture(str(start_video_path))
        resources.callback(cap1.release)
        cap2 = cv2.VideoCapture(str(far_video_path))
        resources.callback(cap2.release)
        if display:
            resources.callback(cv2.destroyAllWindows)

        if not cap1.isOpened() or not cap2.isOpened():
            print("[HATA] Video açılamadı.")
            raise RuntimeError("Video veya ses kaynagi okunamadi.")

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
        if not (0 <= start_time_sec < duration and 0 <= cam2_start < duration2):
            raise ValueError("Baslangic zamani video suresinin disinda.")
        if min(w, h, w2, h2) <= 0 or not all(math.isfinite(v) and v > 0 for v in (fps, fps2)):
            raise ValueError("Gecersiz video boyutu veya FPS.")

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
                REFERENCE_INPUTS,
                "reference_beep_audio.mp4",
            )
            detector = BeepDetector()
            raw_beeps = detector.detect_beeps(beep_video)
            run_beep_times = _reference_beeps_to_run_deadlines(raw_beeps)
            if not run_beep_times:
                print("[HATA] Referans bip videosundan bip zamanı çıkarılamadı.")
                raise RuntimeError("Video veya ses kaynagi okunamadi.")
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
        # 4. Kalibrasyon - her kameranın ilk karesinden
        # ------------------------------------------------------------------
        print("\n[Kalibrasyon] İlk kareler alınıyor...")
        ret1, frame1_cal = cap1.read()
        ret2, frame2_cal = cap2.read()
        if not ret1 or not ret2:
            print("[HATA] İlk kareler okunamadı.")
            raise RuntimeError("Video veya ses kaynagi okunamadi.")

        # Kamera başlarını sıfırla
        cap1.set(cv2.CAP_PROP_POS_MSEC, start_time_sec * 1000)
        cap2.set(cv2.CAP_PROP_POS_MSEC, cam2_start * 1000)

        if start_line_points is None or far_line_points is None:
            start_line_points, far_line_points = calibrate_cameras(
                frame1_cal, frame2_cal, use_config_lines=use_config_lines,
            )
        start_line_profile_base = PerspectiveLine.from_points(start_line_points)
        far_line_profile_base = PerspectiveLine.from_points(far_line_points)
        for profile, width, height in ((start_line_profile_base, w, h), (far_line_profile_base, w2, h2)):
            if any(not (0 <= x < width and 0 <= y < height) for x, y in profile.points):
                raise ValueError("Kalibrasyon noktasi goruntu sinirlari disinda.")
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
            cv2.namedWindow("Mekik Testi - Cift Kamera Tek Ekran", cv2.WINDOW_NORMAL)
            cv2.imshow("Mekik Testi - Cift Kamera Tek Ekran", preview_dual)
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
            beep_times=run_beep_times if scoring_eligible else [],
            start_line_profile=start_line_profile_base,
            far_line_profile=far_line_profile_base,
            fallback_timer=fallback if scoring_eligible else None,
            start_target_side="below",
            far_target_side="below" if real_dual_camera else "above",
        )
        beep_times_list = evaluator.get_beep_times()
        evaluator.scoring_eligible = scoring_eligible

        start_lane_assigner = LaneAssigner(
            lane_count=runner_count,
            frame_width=w,
            reverse_view=False,
            lane_x_min=start_line_profile_base.min_x,
            lane_x_max=start_line_profile_base.max_x,
        )
        far_lane_assigner = LaneAssigner(
            lane_count=runner_count,
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

        start_motion = far_motion = None
        if motion_compensation:
            motion_cfg = MotionCompensatorConfig(update_every=MOTION_COMP_UPDATE_EVERY)
            start_motion = CameraMotionCompensator(frame1_cal, start_line_profile_base, motion_cfg)
            far_motion = CameraMotionCompensator(frame2_cal, far_line_profile_base, motion_cfg)

        # ------------------------------------------------------------------
        # 6. Çıktı video (yan yana, 640px per panel)
        # ------------------------------------------------------------------
        panel_w   = min(640, w)
        panel_h   = max(int(h * panel_w / w), int(h2 * panel_w / w2))
        panel_h += panel_h % 2
        out_w     = panel_w * 2 + 4
        out_h     = panel_h + 128 + 38 + 108 * max(1, math.ceil(runner_count / 5))
        out_path  = output_dir / "analiz_videosu.mp4"
        output_dir.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h)
        )
        resources.callback(writer.release)
        if not writer.isOpened():
            raise RuntimeError(f"Cikti videosu acilamadi: {out_path}")

        # ------------------------------------------------------------------
        # 7. Pencereler
        # ------------------------------------------------------------------
        WIN_DUAL = "Mekik Testi - Cift Kamera Tek Ekran"

        if display:
            cv2.namedWindow(WIN_DUAL, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WIN_DUAL, out_w, out_h)

        # ------------------------------------------------------------------
        # 8. İşleme döngüsü
        # ------------------------------------------------------------------
        print(f"\n[İşleme] Başlıyor - q veya ESC ile dur")
        if real_dual_camera:
            print("  ID eşleştirme: 0m soldan-sağa, 20m sağdan-sola ortak kulvar ID")
        else:
            print(f"  ID eşleştirme: {'tek video simülasyonu (ortak ID)' if CAM2_SHARE_TRACK_IDS else 'kamera ofsetli ID'}")
        frame_idx    = 0
        analyzed_frames = 0
        completion_reason = "video_end"
        dual = None
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

        cam2_frame_idx = int(round(cam2_start * fps2)) - 1
        frame2_cached = None
        while True:
            ret1, frame1 = cap1.read()
            if not ret1:
                break

            cam1_video_time = start_time_sec + frame_idx / fps
            target_cam2_idx = int(round((cam1_video_time + cam2_offset_sec) * fps2))
            ret2 = frame2_cached is not None
            while cam2_frame_idx < target_cam2_idx:
                ret2, frame2_cached = cap2.read()
                cam2_frame_idx += 1
                if not ret2:
                    break
            if not ret2:
                print("[Video] Kamera 2 sona erdi; ortak analiz araligi tamamlandi.")
                completion_reason = "camera2_end"
                break
            frame2 = frame2_cached.copy()

            t0 = time.time()

            # Zaman hesabı. CAP_PROP_POS_MSEC farklı FPS'li iki gerçek kamerada
            # frame index varsayımından daha doğru sonuç verir.
            cam2_video_time = cam2_frame_idx / fps2
            cam1_time = cam1_video_time - run_zero_time_sec
            cam2_time = cam2_video_time - run_zero_time_sec - (cam2_offset_sec if real_dual_camera else 0)

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

            # Telefon kamerasi kaymasi: cizgileri kalibrasyon karesinden guncel kareye tasi
            elif start_motion is not None:
                current_start_line_profile = start_motion.update(frame1)
                current_far_line_profile = far_motion.update(frame2)
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

            # Poz tespiti - iki tracker bağımsız
            runners1 = tracker1.process_frame(frame1)
            runners2 = tracker2.process_frame(frame2) if ret2 else []
            if real_dual_camera:
                start_lane_assigner.lane_x_min = current_start_line_profile.min_x
                start_lane_assigner.lane_x_max = current_start_line_profile.max_x
                far_lane_assigner.lane_x_min = current_far_line_profile.min_x
                far_lane_assigner.lane_x_max = current_far_line_profile.max_x
                runners1 = filter_line_candidates(runners1, current_start_line_profile, h)
                runners2 = filter_line_candidates(runners2, current_far_line_profile, h2)
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
                if real_dual_camera:
                    evaluator.check_beep_deadlines(cam1_time)
                else:
                    evaluator.check_beep_deadlines(cam1_time, expected_direction="to_near")
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
            draw_camera_overlay(ann1, "KAMERA 1 - BASLANGIC (0m)",
                                current_start_line_profile, COLOR_START_LINE,
                                cam1_time,
                                (start_flash1 > 0 or bip_flash1 > 0),
                                evaluator,
                                beep_times_list,
                                shuttle_info=shuttle_info1,
                                bip_label="CIKIS BIPI!" if start_flash1 > 0 else "BIP!")
            draw_camera_overlay(ann2, "KAMERA 2 - 20m CIZGISI",
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
            dual = render_dashboard(dual, evaluator, cam1_time, shuttle_info1,
                                    beep_times_list, runner_count,
                                    progress=(frame_idx+1)/max(1,remaining),
                                    approximate=realtime_preview)
            writer.write(dual)
            frame_idx += 1
            analyzed_frames += 1

            # Ekran gösterimi
            if display and frame_idx % DISPLAY_EVERY_N_FRAMES == 0:
                cv2.imshow(WIN_DUAL, dual)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    print("\n[Kullanıcı] Durduruldu.")
                    completion_reason = "user_stop"
                    break

            proc_fps  = 1.0 / (time.time() - t0 + 1e-9)

            if display and realtime_preview:
                target_frame_idx = int((time.time() - t_wall_start) * fps)
                # Islem videodan hizliysa bekle; video olagan hizinda aksin.
                ahead_sec = (frame_idx - target_frame_idx) / fps
                if ahead_sec > 0.002:
                    key = cv2.waitKey(max(1, int(ahead_sec * 1000))) & 0xFF
                    if key in (27, ord("q")):
                        print("\n[Kullanıcı] Durduruldu.")
                        completion_reason = "user_stop"
                        break
                skip_count = min(
                    MAX_REALTIME_FRAME_SKIP,
                    max(0, target_frame_idx - frame_idx),
                )
                if max_frames is not None:
                    skip_count = min(skip_count, max(0, max_frames - frame_idx))

                for _ in range(skip_count):
                    ret_skip1 = cap1.grab()
                    ret_skip2 = True
                    if not ret_skip1:
                        break
                    if not ret_skip2:
                        pass
                    writer.write(dual)
                    frame_idx += 1

            if max_frames is not None and frame_idx >= max_frames:
                print(f"\n[Test] max_frames={max_frames} sınırında duruldu.")
                completion_reason = "max_frames"
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

        elapsed = time.time() - t_wall_start
        print(f"\n{'='*65}")
        print(f"  Tamamlandı! {frame_idx} kare - {elapsed:.1f}s")
        print(f"  Çıktı : {out_path}")
        print(f"{'='*65}")

        print(f"\n  SONUÇ RAPORU")
        print(f"{'='*65}")
        df = evaluator.get_results_dataframe()
        print(df.to_string(index=False) if not df.empty else "  Koşucu tespit edilmedi.")

        evaluator.export_results(output_dir)
        metadata = {"processed_frames": frame_idx, "analyzed_frames": analyzed_frames,
                    "approximate": bool(display and realtime_preview),
                    "completion_reason": completion_reason,
                    "elapsed_seconds": round(elapsed, 3),
                    "output_video": str(out_path), "start_video": str(start_video_path),
                    "far_video": str(far_video_path), "run_zero_seconds": run_zero_time_sec,
                    "start_line": start_line_points, "far_line": far_line_points,
                    "runner_count": len(df), "mode": "real_dual" if real_dual_camera else "simulation",
                    "motion_compensation": None if start_motion is None else {
                        cam: {"ok_updates": m.ok_updates, "failed_updates": m.failed_updates,
                              "final_offset_px": round(m.offset_px, 1)}
                        for cam, m in (("start", start_motion), ("far", far_motion))}}
        metadata["analysis_status"] = "ok" if len(df) else "no_runners_detected"
        metadata["scoring_eligible"] = scoring_eligible
        (output_dir / TECH_DIR).mkdir(parents=True, exist_ok=True)
        (output_dir / TECH_DIR / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        final_frame = None
        if dual is not None:
            final_frame = render_dashboard(build_side_by_side(ann1, ann2, target_w=panel_w),
                evaluator, cam1_time, shuttle_info1, beep_times_list, runner_count,
                progress=frame_idx/max(1, remaining), approximate=realtime_preview, finished=True)
        write_readable_outputs(output_dir, evaluator, metadata, final_frame,
                               title=report_title, note=report_note)
        print(f"  Raporlar: {output_dir}")
        print(f"{'='*65}\n")
        if display and hold_open and completion_reason in {"video_end", "camera2_end"}:
            if final_frame is not None:
                cv2.imshow(WIN_DUAL, final_frame)
            print("[Goruntu] Raporlar hazir. Pencereyi kapatmak icin bir tusa basin.", flush=True)
            cv2.waitKey(0)
        if display:
            cv2.destroyAllWindows()
        return metadata


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
                        help="0m / başlangıç kamerası videosu (varsayılan: data/inputs/ornek_kayit/0metre.mp4)")
    parser.add_argument("--far-video", type=str, default=None,
                        help="20m kamerası videosu (varsayılan: data/inputs/ornek_kayit/20metre.mp4)")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--hold-open", action="store_true", help="Video sonunda goruntu penceresini acik tut")
    parser.add_argument("--realtime-preview", action="store_true",
                        help="Hizli on izleme icin kare atla; sonuclar yaklasik olarak isaretlenir")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Video ve raporlar icin ayri cikti klasoru")
    parser.add_argument("--runner-count", type=int, default=EXPECTED_RUNNER_COUNT,
                        help="Parkurdaki gercek kosucu sayisi")
    parser.add_argument("--start-line", type=str, help="0m cizgisi: x1,y1;x2,y2")
    parser.add_argument("--far-line", type=str, help="20m cizgisi: x1,y1;x2,y2")
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
    parser.add_argument("--no-motion-compensation", action="store_true",
                        help="Telefon kamerasi kayma telafisini kapat (sabit cizgi)")
    parser.add_argument("--use-config-lines", action="store_true",
                        help="Fareyle seçmek yerine config.py içindeki hazır çift kamera çizgilerini kullan")
    args = parser.parse_args()
    def parse_line(value):
        if value is None:
            return None
        try:
            points = [tuple(map(int, point.split(","))) for point in value.split(";")]
            if any(len(point) != 2 for point in points):
                raise ValueError
            PerspectiveLine.from_points(points)
            return points
        except (ValueError, TypeError):
            parser.error("Cizgi formati: x1,y1;x2,y2 (en az iki farkli X)")
    start_points = parse_line(args.start_line)
    far_points = parse_line(args.far_line)
    if bool(start_points) != bool(far_points):
        parser.error("--start-line ve --far-line birlikte verilmelidir.")

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
        start_line_points=start_points,
        far_line_points=far_points,
        output_dir=args.output_dir,
        runner_count=args.runner_count,
        hold_open=args.hold_open,
        realtime_preview=args.realtime_preview,
        motion_compensation=not args.no_motion_compensation,
    )


if __name__ == "__main__":
    main()
