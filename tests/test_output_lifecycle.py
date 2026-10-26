"""Real video writer regression: exports must be ready before a GUI waits."""
import json
from unittest.mock import Mock
import cv2
import numpy as np
import pytest
import dual_main


@pytest.mark.parametrize('stop_key,expected_frames,expect_hold', [(-1, 2, True), (ord('q'), 1, False)])
def test_video_and_reports_ready_before_hold(tmp_path, monkeypatch, stop_key, expected_frames, expect_hold):
    source = tmp_path / 'input.mp4'
    out = tmp_path / 'output'
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'mp4v'), 2, (64, 48))
    for _ in range(2):
        writer.write(np.zeros((48,64,3), np.uint8))
    writer.release()
    monkeypatch.setattr(dual_main, 'PoseTracker', lambda: Mock(process_frame=Mock(return_value=[])))
    for name in ('namedWindow', 'resizeWindow', 'imshow', 'destroyAllWindows'):
        monkeypatch.setattr(cv2, name, Mock())
    holds = []
    def wait(delay):
        if delay == 0:
            meta = json.loads((out/'run_metadata.json').read_text())
            assert (out/'analiz_raporu.html').is_file()
            assert (out/'sonuc_rapor.xlsx').is_file()
            capture = cv2.VideoCapture(meta['output_video'])
            try:
                assert capture.read()[0]
                assert capture.get(cv2.CAP_PROP_FRAME_COUNT) == expected_frames
            finally:
                capture.release()
            holds.append(True)
        return stop_key if delay == 1 else -1
    monkeypatch.setattr(cv2, 'waitKey', wait)
    result = dual_main.process_dual_camera(source, source, display=True, use_audio=False,
        runner_count=1, hold_open=True, start_beep_time_override=0, output_dir=out,
        start_line_points=[(0,30),(63,30)], far_line_points=[(0,30),(63,30)])
    assert result['processed_frames'] == result['analyzed_frames'] == expected_frames
    assert bool(holds) == expect_hold
    assert result['approximate'] is False
    assert result['completion_reason'] == ('video_end' if expect_hold else 'user_stop')
