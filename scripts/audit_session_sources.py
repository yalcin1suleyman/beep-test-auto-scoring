"""Decode every source frame and check copies against original desktop files."""
import hashlib
import json
import sys
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_sessions import load_sessions, session_paths


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    cv2.setNumThreads(1)
    data, sessions = load_sessions()
    rows = []
    for session in sessions:
        for path in session_paths(data, session):
            provenance = path.parent / 'kaynak.txt'
            original = None
            for line in provenance.read_text(encoding='utf-8-sig').splitlines():
                if line.startswith(path.name + ' <- '):
                    original = Path.home() / 'Desktop' / line.split(' <- ', 1)[1]
            digest = sha256(path)
            same = original is not None and original.is_file() and sha256(original) == digest
            if not same:
                raise RuntimeError(f'Kaynak eslesmiyor: {path}')
            cap = cv2.VideoCapture(str(path))
            expected, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
            shape = [int(cap.get(4)), int(cap.get(3))]
            count = 0
            try:
                while cap.read()[0]:
                    count += 1
            finally:
                cap.release()
            if count != expected:
                raise RuntimeError(f'Video eksik okundu: {path}: {count}/{expected}')
            rows.append(dict(session_id=session['id'], path=path.relative_to(ROOT).as_posix(),
                expected_frames=expected, decoded_frames=count, fps=fps, shape=shape,
                sha256=digest, original_matches=True))
            print(f"Video {session['id']} / {path.name}: {count} kare OK", flush=True)
    out = ROOT / 'data/outputs/hazirlik_2026-11-18/source_audit.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')


if __name__ == '__main__':
    main()
