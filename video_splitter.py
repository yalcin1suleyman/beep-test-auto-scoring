"""
video_splitter.py — Çift Kamera Simülasyonu için Video Kopyalama

Tek video dosyasını iki kamera dosyası olarak kopyalar:
  - camera_baslangic.mp4  → Başlangıç çizgisi kamerası (0 m)
  - camera_20m.mp4        → 20 metre çizgisi kamerası

Gerçek çift kamera entegrasyon hazır olduğunda bu modül,
kopyalama yerine iki ayrı video akışını kabul edecek şekilde
güncellenecektir.
"""

import shutil
from pathlib import Path


def create_dual_camera_videos(
    source_video: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """
    Tek video dosyasını iki kamera simülasyonu için kopyalar.

    Args:
        source_video: Kaynak video dosyası.
        output_dir: Kopyaların yazılacağı klasör.

    Returns:
        (start_cam_path, far_cam_path)
          start_cam_path: Başlangıç (0 m) kamera simülasyonu
          far_cam_path  : 20 m kamera simülasyonu
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = source_video.stem
    suffix = source_video.suffix

    start_cam = output_dir / f"{stem}_camera_baslangic{suffix}"
    far_cam = output_dir / f"{stem}_camera_20m{suffix}"

    print("\n[VideoSplitter] Çift kamera dosyaları hazırlanıyor...")

    for cam_path, label in [(start_cam, "Başlangıç kamerası"), (far_cam, "20m kamerası")]:
        if cam_path.exists():
            print(f"  {label} mevcut: {cam_path.name}")
        else:
            print(f"  {label} kopyalanıyor → {cam_path.name}")
            shutil.copy2(source_video, cam_path)
            print(f"  Kopyalandı ({cam_path.stat().st_size / 1024 / 1024:.1f} MB)")

    print(f"[VideoSplitter] Başlangıç: {start_cam.name}")
    print(f"[VideoSplitter] 20m      : {far_cam.name}")
    return start_cam, far_cam
