from pathlib import Path

import cv2
import numpy as np
import pytest

from camera_motion import CameraMotionCompensator, MotionCompensatorConfig
from dual_camera_analyser import DualLineEvaluator
from dual_main import _reference_beeps_to_run_deadlines
from line_geometry import PerspectiveLine
from run_sessions import load_sessions, parse_line, session_paths


def test_reference_deadlines_start_from_first_beep():
    assert _reference_beeps_to_run_deadlines([9.5, 18.0, 26.5]) == [8.5, 17.0]


def test_reference_deadlines_fill_missed_level_change_beep():
    # 4. bip (farkli tonlu seviye sinyali) kacmis; sira kaymamali.
    deadlines = _reference_beeps_to_run_deadlines([10.0, 18.5, 27.0, 44.0, 52.0])
    assert deadlines == [8.5, 17.0, 25.5, 34.0, 42.0]


def test_reference_deadlines_need_start_and_one_target():
    assert _reference_beeps_to_run_deadlines([12.0]) == []


def _textured_frame(seed=0, size=(480, 640)):
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (size[0] // 8, size[1] // 8), dtype=np.uint8)
    frame = cv2.resize(small, (size[1], size[0]), interpolation=cv2.INTER_NEAREST)
    return cv2.cvtColor(cv2.GaussianBlur(frame, (3, 3), 0), cv2.COLOR_GRAY2BGR)


def test_motion_compensator_follows_camera_shift():
    ref = _textured_frame()
    line = PerspectiveLine.from_points([(40, 300), (600, 310)])
    comp = CameraMotionCompensator(ref, line, MotionCompensatorConfig(update_every=1, smoothing_alpha=1.0))
    shifted = cv2.warpAffine(ref, np.float32([[1, 0, 0], [0, 1, 25]]), (ref.shape[1], ref.shape[0]),
                             borderMode=cv2.BORDER_REFLECT)
    moved = comp.update(shifted)
    assert comp.offset_px == pytest.approx(25, abs=2)
    assert moved.points[0][1] == pytest.approx(325, abs=2)


def test_motion_compensator_keeps_line_when_frame_is_featureless():
    ref = _textured_frame()
    line = PerspectiveLine.from_points([(40, 300), (600, 310)])
    comp = CameraMotionCompensator(ref, line, MotionCompensatorConfig(update_every=1))
    moved = comp.update(np.zeros_like(ref))
    assert moved.points == line.points
    assert comp.failed_updates == 1


def test_touching_line_counts_as_reaching_it():
    ev = DualLineEvaluator(200, 100, [10., 20.], start_target_side="below", far_target_side="below",
                           touch_tolerance_px=10)
    assert ev._line_side(95, "far") == "target"      # cizginin 5 px onunde: temas
    assert ev._line_side(85, "far") == "mid"
    strict = DualLineEvaluator(200, 100, [10., 20.], start_target_side="below", far_target_side="below",
                               touch_tolerance_px=0)
    assert strict._line_side(95, "far") == "mid"


def test_session_file_is_consistent():
    data, sessions = load_sessions()
    assert [s["id"] for s in sessions] == list(range(1, len(sessions) + 1))
    for s in sessions:
        assert s["runner_count"] > 0
        assert s.get("video_start_time", 0.0) + s["cam2_offset"] >= 0
        for key in ("start_line", "far_line"):
            PerspectiveLine.from_points(parse_line(s[key]))


def test_session_lines_fit_inside_videos():
    data, sessions = load_sessions()
    checked = 0
    for s in sessions:
        for video, key in zip(session_paths(data, s), ("start_line", "far_line")):
            if not Path(video).is_file():
                continue
            cap = cv2.VideoCapture(str(video))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            assert all(0 <= x < w and 0 <= y < h for x, y in parse_line(s[key])), (s["name"], key)
            checked += 1
    if not checked:
        pytest.skip("MEKİK VİDEO klasoru bu bilgisayarda yok")


def test_departure_found_when_runners_leave_line():
    from run_start import find_departure_time
    samples = [(t / 10, [600.0, 605.0, 598.0]) for t in range(30)]
    samples += [(3.0 + k / 10, [600.0 - 15 * k] * 3) for k in range(1, 15)]
    assert find_departure_time(samples, line_y=600) == pytest.approx(3.0, abs=0.11)


def test_departure_not_found_while_runners_wait():
    from run_start import find_departure_time
    samples = [(t / 10, [600.0 + (t % 3)]) for t in range(80)]
    assert find_departure_time(samples, line_y=600) is None
