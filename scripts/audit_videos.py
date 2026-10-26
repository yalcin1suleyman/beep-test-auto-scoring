"""Decode every frame and sample pose inference across every desktop recording.

Run from any directory: python scripts/audit_videos.py [--interval 1]
This checks technical robustness, not scoring accuracy against human labels.
"""
import argparse
import json
import sys
import time
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tracker import PoseTracker
from audio_detector import BeepDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home()/'Desktop'/'MEKİK VİDEO')
    parser.add_argument('--interval', type=float, default=1.0)
    args = parser.parse_args()
    out = ROOT/'data/outputs/verification'
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(args.source.rglob('*.mp4')):
        started = time.perf_counter()
        cap = cv2.VideoCapture(str(path))
        expected = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        tracker = PoseTracker()
        count, samples, positives, max_people = 0, 0, 0, 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if count % max(1, round(fps*args.interval)) == 0:
                    people = tracker.process_frame(frame)
                    samples += 1
                    positives += bool(people)
                    max_people = max(max_people, len(people))
                count += 1
        finally:
            cap.release()
        beeps = BeepDetector().detect_beeps(path)
        result = dict(path=str(path), expected_frames=expected, decoded_frames=count,
                      decode_ok=count == expected, inference_samples=samples,
                      samples_with_people=positives, max_people=max_people,
                      beep_times=beeps, elapsed_seconds=round(time.perf_counter()-started,2))
        results.append(result)
        (out/'desktop_audit.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True),flush=True)
    if not results or any(not r['decode_ok'] for r in results):
        raise SystemExit('Missing videos or incomplete decoding')


if __name__ == '__main__':
    main()
