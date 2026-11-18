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


def test_readable_tables_explain_levels_and_elimination():
    from config import RunnerState
    from result_report import ELIMINATED, LATE_WARNING, ON_TIME, readable_tables, shuttle_schedule
    beeps = [8.43, 16.89, 25.39, 33.88, 42.34, 50.85, 59.37, 67.34, 75.37]
    schedule = shuttle_schedule(beeps)
    assert schedule[0]["label"] == "Seviye 1 – 1. mekik" and schedule[0]["target"] == "20 m"
    assert schedule[7]["label"] == "Seviye 2 – 1. mekik" and schedule[7]["speed_kmh"] == 9.0
    ev = DualLineEvaluator(200, 100, beeps, start_target_side="below", far_target_side="below",
                           tolerance_sec=0.0, min_shuttle_interval_sec=0)
    ev.update_camera_line(1, 50, 90, 0.0, "far")          # kosucu kaydedilsin
    status = ev.get_runner_status(1)
    status.crossing_log += [
        {"time": 7.9, "camera": "20m", "direction": "to_far", "status": "Gecti - bipten once tamamlandi", "shuttle_no": 1},
        {"time": 16.9, "camera": "baslangic", "direction": "to_near", "status": "GEC - bipten once cizgi gecilmedi", "shuttle_no": 2},
        {"time": 25.4, "camera": "20m", "direction": "to_far", "status": "ELENDI - bipten once cizgi gecilmedi", "shuttle_no": 3},
    ]
    status.state, status.elimination_time = RunnerState.ELIMINATED, 25.4
    summary, shuttles = readable_tables(ev)
    row = summary.iloc[0]
    assert row["Sonuç"] == "Elendi" and row["Tamamlanan mekik"] == 1
    assert row["Koşulan mesafe (m)"] == 20 and row["Ulaştığı seviye"] == "Seviye 1 – 1. mekik"
    assert "3. mekik" in row["Elendiği an"] and "20 m" in row["Açıklama"]
    assert list(shuttles["Sonuç"]) == [ON_TIME, LATE_WARNING, ELIMINATED]


def test_nonstandard_session_is_explicitly_unscored():
    _data, sessions = load_sessions()
    assert sessions[6]["scoring_eligible"] is False


def test_nonstandard_report_does_not_publish_elimination_scores(tmp_path):
    import pandas as pd
    from config import RunnerState
    from result_report import write_readable_outputs
    ev = DualLineEvaluator(200, 100, [10., 20.])
    ev.update_camera_line(1, 50, 150, 0, "start")
    status = ev.get_runner_status(1)
    status.state, status.elimination_time = RunnerState.ELIMINATED, 21
    result = write_readable_outputs(tmp_path, ev,
        {"scoring_eligible": False, "output_video": "analiz_videosu.mp4"})
    assert result.iloc[0]["Sonuç"] == "Puanlanmadı"
    assert result.iloc[0]["Tamamlanan mekik"] == "-"
    assert result.iloc[0]["Elendiği an"] == "-"
    assert pd.read_csv(tmp_path / "sonuc_mekikler.csv").empty
    assert "Elenen<b>0</b>" in (tmp_path / "SONUC.html").read_text(encoding="utf-8")


def test_csv_and_excel_numeric_types_compare_without_losing_values():
    import pandas as pd
    from scripts.verify_analysis_output import canonical_table
    pd.testing.assert_frame_equal(canonical_table(pd.DataFrame({'hiz': ['9.0', '-', '8.5']})),
                                  canonical_table(pd.DataFrame({'hiz': [9, None, 8.5]})))
