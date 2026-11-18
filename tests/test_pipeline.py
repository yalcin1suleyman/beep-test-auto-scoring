from pathlib import Path
from unittest.mock import Mock
import cv2
import numpy as np
import pytest
from scipy.io import wavfile
from audio_detector import BeepDetector
from line_geometry import PerspectiveLine
from tracker import PoseTracker
from dual_main import process_dual_camera, calibrate_cameras
from validators import validate_video_file, ValidationError


@pytest.mark.parametrize('points', [[(1, 2)], [(1, 2), (1, 3)], [(0, 1), (2, float('nan'))]])
def test_invalid_line_rejected(points):
    with pytest.raises(ValueError):
        PerspectiveLine.from_points(points)


@pytest.mark.parametrize('samples', [0, 10, 400, 8000])
def test_empty_short_silent_audio(tmp_path, samples):
    path = tmp_path / 'silent.wav'
    wavfile.write(path, 8000, np.zeros(samples, dtype=np.int16))
    assert BeepDetector()._analyze_wav(path) == []


def test_inference_failure_is_not_an_empty_detection():
    tracker = object.__new__(PoseTracker)
    tracker.model = Mock()
    tracker.model.track.side_effect = RuntimeError('inference failed')
    tracker.tracker_config = 'unused'
    tracker.confidence, tracker.iou, tracker.imgsz = .2, .4, 480
    with pytest.raises(RuntimeError, match='Poz takibi'):
        tracker.process_frame(np.zeros((32, 32, 3), dtype=np.uint8))


def test_corrupt_video_rejected(tmp_path):
    path = tmp_path / 'broken.mp4'
    path.write_bytes(b'not a video')
    with pytest.raises(ValidationError):
        validate_video_file(path)


def test_missing_config_does_not_open_interactive_window(monkeypatch):
    monkeypatch.setattr('dual_main.DUAL_START_LINE_POINTS', None)
    monkeypatch.setattr('dual_main.DUAL_FAR_LINE_POINTS', None)
    with pytest.raises(ValueError, match='Config'):
        calibrate_cameras(np.zeros((32, 32, 3)), np.zeros((32, 32, 3)), True)


def test_different_fps_are_synchronized_and_output_decodes(tmp_path, monkeypatch):
    videos = []
    for fps in (10, 20):
        path = tmp_path / f'camera{fps}.mp4'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (64, 48))
        for i in range(fps * 2):
            writer.write(np.full((48, 64, 3), int(i*160/(fps*2)), dtype=np.uint8))
        writer.release()
        videos.append(path)
    import dual_main
    observed = [[], []]
    def make_tracker():
        values = observed.pop(0)
        tracker = Mock()
        tracker.process_frame.side_effect = lambda frame: (values.append(float(frame.mean())) or [])
        return tracker
    first, second = observed
    monkeypatch.setattr(dual_main, 'PoseTracker', make_tracker)
    result = process_dual_camera(videos[0], videos[1], display=False, use_audio=False,
                                start_beep_time_override=0, output_dir=tmp_path / 'out',
                                start_line_points=[(0, 30), (63, 30)],
                                far_line_points=[(0, 30), (63, 30)])
    assert result['processed_frames'] == 20
    assert len(first) == len(second) == 20
    assert max(abs(a-b) for a,b in zip(first,second)) < 6
    assert result['analyzed_frames'] == 20
    assert result['approximate'] is False
    assert result['analysis_status'] == 'no_runners_detected'
    cap = cv2.VideoCapture(result['output_video'])
    try:
        assert cap.isOpened()
        assert cap.get(cv2.CAP_PROP_FRAME_COUNT) == 20
        assert cap.read()[0]
    finally:
        cap.release()
    assert (tmp_path / 'out' / 'SONUC.xlsx').is_file()
    assert (tmp_path / 'out' / 'SONUC.html').is_file()
    assert cv2.imread(str(tmp_path / 'out' / 'son_durum.jpg')) is not None
    import pandas as pd
    assert 'Koşucu' in pd.read_csv(tmp_path / 'out' / 'sonuc_ozet.csv').columns
    assert 'Kosucu ID' in pd.read_csv(tmp_path / 'out' / 'teknik' / 'ham_ozet.csv').columns


def test_mixed_aspect_panels_have_even_output_dimensions():
    from dual_main import build_side_by_side
    frame = build_side_by_side(np.zeros((51, 64, 3), np.uint8),
                               np.zeros((99, 64, 3), np.uint8), target_w=64)
    assert frame.shape == (100, 132, 3)


def test_synthetic_beeps_are_detected(tmp_path):
    sr = 8000
    data = np.zeros(sr * 15, dtype=np.float32)
    for t in (2, 9):
        n = int(.3 * sr)
        data[t * sr:t * sr+n] = .8 * np.sin(2*np.pi*600*np.arange(n)/sr)
    path = tmp_path / 'beeps.wav'
    wavfile.write(path, sr, data)
    times = BeepDetector()._analyze_wav(path)
    assert len(times) == 2
    assert times[0] == pytest.approx(2.15, abs=.3)
    assert times[1] == pytest.approx(9.15, abs=.3)


def test_reference_audio_dashboard_displays_target_without_math_timer(monkeypatch):
    import video_dashboard
    labels = []
    monkeypatch.setattr(video_dashboard,'text',lambda _frame,label,*args,**kwargs: labels.append(label))
    ev = Mock(get_active_count=Mock(return_value=0), get_all_runner_statuses=Mock(return_value={}))
    ev.scoring_eligible = True
    video_dashboard.render_dashboard(np.zeros((100,900,3),np.uint8),ev,12,None,[8.5,17,25.5],3)
    assert 'HEDEF  0m' in labels
    assert 'CIKIS BEKLENIYOR' not in labels
