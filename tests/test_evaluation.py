"""Scoring regressions: timing, missed deadlines and gradual line crossings."""
import pytest
from config import RunnerState
from dual_camera_analyser import DualLineEvaluator
from analyser import ShuttleEvaluator
from timer import ShuttleTimer


def evaluator(**kwargs):
    kwargs.setdefault('tolerance_sec', 0.0)
    return DualLineEvaluator(200, 100, [10., 20., 30., 40.],
                             min_shuttle_interval_sec=0, **kwargs)


def test_crossing_within_late_tolerance_is_on_time():
    ev = evaluator(tolerance_sec=0.5)
    ev.update_camera_line(1, 50, 150, 0, 'far')
    ev.update_camera_line(1, 50, 90, 10.3, 'far')
    ev.check_beep_deadlines(10.6)
    status = ev.get_runner_status(1)
    assert status.on_time_count == 1 and status.late_count == 0


def test_warning_then_elimination_without_detections():
    ev = evaluator()
    ev.update_camera_line(1, 50, 150, 0, 'start')
    ev.check_beep_deadlines(10.1)
    assert ev.get_runner_status(1).state == RunnerState.WARNING
    ev.check_beep_deadlines(20.1)
    assert ev.get_runner_status(1).state == RunnerState.ELIMINATED
    assert ev.get_runner_status(1).late_count == 2


def test_time_jump_processes_all_expired_deadlines():
    ev = evaluator()
    ev.update_camera_line(1, 50, 150, 0, 'start')
    ev.check_beep_deadlines(25)
    assert ev.get_runner_status(1).state == RunnerState.ELIMINATED


def test_on_time_not_double_counted_and_resets_warning():
    ev = evaluator()
    ev.update_camera_line(1, 50, 150, 0, 'start')
    ev.check_beep_deadlines(11)
    ev.update_camera_line(1, 50, 210, 19, 'start')
    ev.update_camera_line(1, 50, 215, 19.5, 'start')
    runner = ev.get_runner_status(1)
    assert runner.on_time_count == 1
    assert runner.state == RunnerState.ACTIVE
    ev.check_beep_deadlines(20.1)
    assert runner.expected_shuttle_idx == 2
    assert runner.consecutive_late == 0


def test_same_camera_can_score_after_opposite_end_was_missed():
    ev = evaluator()
    ev.update_camera_line(1, 50, 90, 9, 'far')
    ev.check_beep_deadlines(10.1)
    ev.check_beep_deadlines(20.1)
    ev.update_camera_line(1, 50, 150, 25, 'far')
    ev.update_camera_line(1, 50, 90, 29, 'far')
    assert ev.get_runner_status(1).on_time_count == 2


def test_standing_at_far_end_cannot_score_another_shuttle():
    ev = evaluator()
    ev.update_camera_line(1, 50, 90, 9, 'far')
    ev.check_beep_deadlines(10.1)
    ev.check_beep_deadlines(20.1)
    ev.update_camera_line(1, 50, 90, 29, 'far')
    assert ev.get_runner_status(1).on_time_count == 1


def test_schedule_end_cannot_create_extra_shuttles():
    ev = DualLineEvaluator(200, 100, [10.], min_shuttle_interval_sec=0)
    ev.update_camera_line(1, 50, 90, 9, 'far')
    ev.check_beep_deadlines(11)
    ev.update_camera_line(1, 50, 210, 12, 'start')
    assert ev.get_runner_status(1).total_crossings == 1


def test_exact_deadline_is_accepted():
    ev = evaluator()
    ev.update_camera_line(1, 50, 90, 10, 'far')
    ev.check_beep_deadlines(10.01)
    assert ev.get_runner_status(1).on_time_count == 1
    assert ev.get_runner_status(1).late_count == 0


@pytest.mark.parametrize('times', [[0], [-1], [float('nan')], [20, 10], [10, 10]])
def test_invalid_schedule_rejected(times):
    with pytest.raises(ValueError):
        DualLineEvaluator(200, 100, times)


def test_single_line_gradual_crossing_survives_hysteresis_band():
    ev = ShuttleEvaluator(100, ShuttleTimer(), hysteresis_px=15)
    for t, y in enumerate([130, 120, 114, 110, 105, 100, 99, 98]):
        ev.update(1, y, t * .1)
    assert ev.get_runner_status(1).total_crossings == 1
    for t, y in enumerate([80, 85, 90, 95, 100]):
        ev.update(1, y, 2 + t * .1)
    assert ev.get_runner_status(1).total_crossings == 2


def test_beep_schedule_cannot_be_mutated_by_caller():
    ev = evaluator()
    ev.get_beep_times().clear()
    assert len(ev.get_beep_times()) == 4
