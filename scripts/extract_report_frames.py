from pathlib import Path

import cv2


def main():
    video = Path("data/outputs/0metre_20metre_dual_camera.mp4")
    out_dir = Path("data/outputs/report_assets/generated")
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Video acilamadi: {video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total / fps if fps else 0.0
    times = [5, 12, 20, 35, 55, 75]
    saved = []

    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        path = out_dir / f"dual_analysis_{int(t):02d}s.jpg"
        cv2.imwrite(str(path), frame)
        saved.append(path)

    cap.release()
    print(f"duration={duration:.2f}s")
    for path in saved:
        print(path)


if __name__ == "__main__":
    main()
