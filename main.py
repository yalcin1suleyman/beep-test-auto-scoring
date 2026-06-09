"""
main.py — Otomatik Mekik Testi Değerlendirme Sistemi (v3)
TEK ÇİZGİ gidiş-dönüş tespiti + matematiksel zamanlayıcı.
Senkronize başlatma + performans optimize.

v3.1: Error handling, logging, validation eklendi.

Kullanım:
    python main.py                                    # YouTube'dan indir + işle
    python main.py --video path/to/video.mp4          # Yerel video
    python main.py --video path/to/video.mp4 --no-display
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from config import (
    DATA_INPUTS,
    DATA_OUTPUTS,
    DEFAULT_VIDEO_URL,
    VIDEO_START_TIME_SEC,
    DISPLAY_EVERY_N_FRAMES,
    DETECTION_LINE_Y,
    LINE_COLOR_DETECT,
    LINE_THICKNESS,
    FONT_SCALE,
    FONT_THICKNESS,
    ANKLE_CIRCLE_RADIUS,
    ANKLE_CIRCLE_COLOR,
    COLOR_ACTIVE,
    COLOR_WARNING,
    COLOR_ELIMINATED,
    COLOR_TEXT_BG,
    RunnerState,
)
from tracker import PoseTracker
from timer import ShuttleTimer
from analyser import ShuttleEvaluator
from logger import get_logger, setup_logger
from validators import (
    validate_file_exists,
    validate_video_file,
    validate_directory_exists,
    validate_environment,
    validate_project_setup,
)

log = get_logger(__name__)


# ==============================================================================
# YouTube Video İndirme
# ==============================================================================

def download_video(url: str, output_dir: Path) -> Path:
    """yt-dlp ile YouTube videosunu indirir."""
    output_dir = validate_directory_exists(
        output_dir, 
        description="Video çıktı klasörü",
        create_if_missing=True
    )
    output_path = output_dir / "mekik_test_video.mp4"

    if output_path.exists():
        log.info(f"Video zaten mevcut: {output_path}")
        return output_path

    log.info(f"Video indiriliyor: {url}")
    try:
        import yt_dlp
    except ImportError:
        log.error("yt-dlp kurulu değil")
        raise RuntimeError(
            "yt-dlp kurulu değil. Kurmak için: pip install yt-dlp"
        )
    
    try:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": str(output_path),
            "quiet": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        log.info(f"✓ Video indirildi: {output_path}")
        return output_path
    except Exception as e:
        log.error(f"Video indirilemedi: {e}")
        raise RuntimeError(f"Video indirilemedi: {url}\n{e}") from e


# ==============================================================================
# Fare Kalibrasyonu — Y Ekseni Yatay Çizgiler
# ==============================================================================
_calibration_clicks: list[int] = []


def _mouse_callback(event, x, y, flags, param):
    """Fare tıklaması ile çizgi Y koordinatlarını yakalar."""
    if event == cv2.EVENT_LBUTTONDOWN:
        _calibration_clicks.append(y)
        print(f"  Cizgi noktasi secildi: Y = {y}")


def calibrate_line(frame: np.ndarray) -> int:
    """
    İlk kare üzerinde fare ile TEK yatay çizgiyi kalibre eder.
    Returns: detection_line_y
    """
    global _calibration_clicks
    _calibration_clicks = []

    win = "Kalibrasyon - TEK cizgi: Kosucular gorunur oldugu yere tiklayin"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, _mouse_callback)

    display = frame.copy()
    h, w = display.shape[:2]

    # Önerilen bölge: ekranın %55-%70 arası (koşucular kameraya yakınken)
    suggested_y = int(h * 0.60)

    # Önerilen çizgi (noktalı)
    for x_pos in range(0, w, 20):
        cv2.line(display, (x_pos, suggested_y), (x_pos + 10, suggested_y),
                 (0, 255, 255), 2)
    cv2.putText(display, f"Onerilen: Y={suggested_y}", (w - 250, suggested_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    instructions = [
        "TEK CIZGI SISTEMI (v3)",
        "Her gecis (yukari veya asagi) = 1 mekik",
        "",
        "Cizgiyi kosucular NET GORUNDUGU yere koyun.",
        "Sari noktali cizgi = onerilen konum",
        "",
        "Tiklayin: Tespit cizgisi",
        "ESC: Iptal | R: Sifirla",
    ]
    for i, text in enumerate(instructions):
        color = (0, 255, 255) if i == 0 else (255, 255, 255)
        cv2.putText(display, text, (10, 25 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    print("\n" + "=" * 60)
    print("KALIBRASYON: TEK cizgi — kosucular gorunur oldugu yere koyun.")
    print(f"  Onerilen Y = {suggested_y} (ekranin %60'i)")
    print("  Her gecis (yukari/asagi) = 1 mekik tamamlandi.")
    print("=" * 60)

    while len(_calibration_clicks) < 1:
        show = display.copy()
        for cy in _calibration_clicks:
            cv2.line(show, (0, cy), (w, cy), (0, 255, 0), 3)
            cv2.putText(show, f"TESPIT CIZGISI Y={cy}", (10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow(win, show)
        key = cv2.waitKey(30) & 0xFF
        if key == 27:
            print("[Kalibrasyon] Iptal.")
            cv2.destroyWindow(win)
            sys.exit(0)
        elif key in (ord("r"), ord("R")):
            _calibration_clicks = []
            print("[Kalibrasyon] Sifirlandi.")

    cv2.destroyWindow(win)
    line_y = _calibration_clicks[0]
    print(f"[Kalibrasyon] Tespit cizgisi: Y={line_y}")
    return line_y


# ==============================================================================
# Görselleştirme
# ==============================================================================

def draw_detection_line(frame, line_y):
    """Tek yatay tespit çizgisini çizer."""
    w = frame.shape[1]
    cv2.line(frame, (0, line_y), (w, line_y), LINE_COLOR_DETECT, LINE_THICKNESS)
    cv2.putText(frame, f"Tespit Cizgisi (Y={line_y})", (10, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, LINE_COLOR_DETECT, 2)


def get_color(state: RunnerState):
    if state == RunnerState.ACTIVE:
        return COLOR_ACTIVE
    elif state == RunnerState.WARNING:
        return COLOR_WARNING
    return COLOR_ELIMINATED


def draw_runner(frame, tid, ax, ay, bbox, state, crossings):
    """Koşucu overlay: bbox, ayak noktası, ID, durum."""
    color = get_color(state)
    x1, y1, x2, y2 = [int(v) for v in bbox]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.circle(frame, (int(ax), int(ay)), ANKLE_CIRCLE_RADIUS,
               ANKLE_CIRCLE_COLOR, -1)

    label = f"ID:{tid} [{state.value}] G:{crossings}"
    sz, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX,
                            FONT_SCALE, FONT_THICKNESS)
    cv2.rectangle(frame, (x1, y1 - sz[1] - 10),
                  (x1 + sz[0] + 5, y1), COLOR_TEXT_BG, -1)
    cv2.putText(frame, label, (x1 + 2, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, color, FONT_THICKNESS)


def draw_hud(frame, total, active, level, shuttle, fps, t, deadline_t):
    """Sol üst köşe durum bilgisi."""
    lines = [
        f"Zaman: {t:.1f}s",
        f"Seviye: {level} | Mekik: {shuttle}",
        f"Kosucu: {active}/{total} aktif",
        f"Sonraki bip: {deadline_t:.1f}s" if deadline_t > 0 else "Test bitti",
        f"FPS: {fps:.1f}",
    ]
    y = 25
    for line in lines:
        sz, _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (5, y - sz[1] - 4),
                      (5 + sz[0] + 10, y + 4), (0, 0, 0), -1)
        cv2.putText(frame, line, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        y += 28


# ==============================================================================
# Video Keşfi
# ==============================================================================

def find_video(video_arg: str | None, auto_download: bool = True) -> Path:
    """Video bulur; yoksa YouTube'dan indirir."""
    exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}

    if video_arg:
        try:
            return validate_video_file(video_arg)
        except Exception as e:
            log.error(f"Video doğrulama başarısız: {e}")
            raise

    # data/inputs içinde ara
    try:
        input_dir = validate_directory_exists(
            DATA_INPUTS,
            description="Giriş klasörü",
            create_if_missing=True
        )
        for f in sorted(input_dir.iterdir()):
            if f.suffix.lower() in exts:
                log.info(f"Video bulundu: {f}")
                return f
    except Exception as e:
        log.warning(f"Giriş klasörü taraması başarısız: {e}")

    # Otomatik indir
    if auto_download:
        log.info("Yerel video bulunamadı, YouTube'dan indiriliyor...")
        return download_video(DEFAULT_VIDEO_URL, DATA_INPUTS)

    log.error("Video bulunamadı")
    raise FileNotFoundError(
        "Video bulunamadı. Lütfen --video argümanını kullanın veya "
        "data/inputs klasörüne video yerleştirin."
    )


# ==============================================================================
# Ana İşleme Döngüsü
# ==============================================================================

def process_video(video_path: Path, display: bool = True,
                  start_time_sec: float = VIDEO_START_TIME_SEC):
    """Video işle ve mekik testini otomatik değerlendir."""
    log.info(f"\n{'='*60}")
    log.info(f"  Otomatik Mekik Testi v3 (Tek Çizgi + Matematik Zamanlayıcı)")
    log.info(f"{'='*60}")
    log.info(f"  Video: {video_path.name}")
    log.info(f"  Koşu başlangıcı: {start_time_sec:.1f}s")

    # 1. Video aç
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise IOError(f"Video açılamadı veya arızalı: {video_path}")
        log.info(f"✓ Video açıldı: {video_path}")
    except Exception as e:
        log.error(f"Video açma başarısız: {e}")
        raise

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0
        
        if fps <= 0 or w <= 0 or h <= 0:
            raise ValueError(f"Geçersiz video parametreleri: {w}x{h} @ {fps} FPS")
        
        log.info(f"  {w}x{h} @ {fps:.1f} FPS, {duration:.1f}s, {total_frames} kare")

        # 2. Matematiksel zamanlayıcı (0. saniyeden başlar)
        log.info(f"\n[1/4] Zamanlayıcı hesaplanıyor...")
        timer = ShuttleTimer(start_offset_sec=0.0)
        timer.print_schedule(max_levels=3)

        # 3. TEK çizgi kalibrasyonu
        log.info(f"\n[2/4] Çizgi kalibrasyonu (TEK çizgi)...")
        cap.set(cv2.CAP_PROP_POS_MSEC, start_time_sec * 1000)
        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            raise RuntimeError("Başlangıç karesini okuyamadı")
        
        log.info(f"✓ Başlangıç karesini oku")

        if DETECTION_LINE_Y is not None:
            det_line_y = DETECTION_LINE_Y
            log.info(f"  Config'den: tespit çizgisi Y={det_line_y}")
        else:
            try:
                det_line_y = calibrate_line(first_frame)
            except KeyboardInterrupt:
                log.info("Kullanıcı kalibrasyon iptal etti")
                raise
            except Exception as e:
                log.error(f"Kalibrasyon başarısız: {e}")
                raise

        # Videoyu koşu başlangıcına geri sar
        cap.set(cv2.CAP_PROP_POS_MSEC, start_time_sec * 1000)

        # 4. Modüller
        log.info(f"\n[3/4] Modüller başlatılıyor...")
        try:
            tracker = PoseTracker()
            log.info("✓ PoseTracker başlatıldı")
        except Exception as e:
            log.error(f"Tracker başlatma başarısız: {e}")
            raise
        
        try:
            evaluator = ShuttleEvaluator(
                detection_line_y=det_line_y,
                shuttle_timer=timer,
            )
            log.info("✓ ShuttleEvaluator başlatıldı")
        except Exception as e:
            log.error(f"Evaluator başlatma başarısız: {e}")
            raise

        # 5. Çıktı video
        output_dir = validate_directory_exists(
            DATA_OUTPUTS,
            description="Çıkış klasörü",
            create_if_missing=True
        )
        out_path = output_dir / f"{video_path.stem}_analyzed.mp4"
        
        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError("VideoWriter açılamadı")
            log.info(f"✓ Çıktı video başlatıldı: {out_path}")
        except Exception as e:
            log.error(f"Çıktı video başlatma başarısız: {e}")
            raise

        # 6. Kare kare işleme (koşu başlangıcından itibaren)
        log.info(f"\n[4/4] Video işleniyor (başlangıç: {start_time_sec:.1f}s)...")
        frame_idx = 0
        proc_fps = 0.0
        t_start = time.time()
        remaining_frames = total_frames - int(start_time_sec * fps) if fps > 0 else total_frames

        if display:
            cv2.namedWindow("Mekik Testi v3", cv2.WINDOW_NORMAL)

        while True:
            ret, frame = cap.read()
            if not ret:
                log.info("Video sonuna ulaşıldı")
                break
            
            if frame is None:
                log.warning(f"Kare {frame_idx} None, atlanıyor")
                frame_idx += 1
                continue

            try:
                t0 = time.time()
                # Zaman: koşu başlangıcından itibaren geçen süre
                current_time = frame_idx / fps if fps > 0 else 0.0

                # Poz + Takip
                runners = tracker.process_frame(frame)

                # Değerlendirme
                for r in runners:
                    evaluator.update(r.track_id, r.ankle_mid_y, current_time)
                evaluator.check_deadlines(current_time)

                # Görselleştirme (çıktı videoya HER kare yazılır)
                ann = frame.copy()
                draw_detection_line(ann, det_line_y)

                for r in runners:
                    st = evaluator.get_runner_status(r.track_id)
                    state = st.state if st else RunnerState.ACTIVE
                    crossings = st.total_crossings if st else 0
                    draw_runner(ann, r.track_id, r.ankle_mid_x, r.ankle_mid_y,
                                r.bbox, state, crossings)

                # HUD
                lvl, sh_in_lvl = timer.get_level_info(current_time)
                sh = timer.get_current_shuttle(current_time)
                deadline_t = sh["deadline_sec"] if sh else 0
                all_st = evaluator.get_all_runner_statuses()
                draw_hud(ann, len(all_st), evaluator.get_active_count(),
                         lvl, sh_in_lvl, proc_fps, current_time, deadline_t)

                writer.write(ann)

                # Ekranda göster — her N karede bir (FPS optimizasyonu)
                if display and (frame_idx % DISPLAY_EVERY_N_FRAMES == 0):
                    cv2.imshow("Mekik Testi v3", ann)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27 or key == ord("q"):
                        log.info("Kullanıcı işlemi durdurdu")
                        break

                dt = time.time() - t0
                proc_fps = 1.0 / dt if dt > 0 else 0
                frame_idx += 1

                if frame_idx % 100 == 0:
                    pct = frame_idx / remaining_frames * 100 if remaining_frames > 0 else 0
                    log.debug(f"  {frame_idx}/{remaining_frames} ({pct:.1f}%) | "
                             f"{proc_fps:.1f} FPS | {time.time()-t_start:.1f}s")
            
            except Exception as e:
                log.error(f"Kare {frame_idx} işlemesi başarısız: {e}")
                # Devam et, bu frame'i atla
                frame_idx += 1
                continue

        # Temizlik
        cap.release()
        writer.release()
        if display:
            cv2.destroyAllWindows()

        elapsed = time.time() - t_start
        log.info(f"\n{'='*60}")
        log.info(f"  Tamamlandı! {frame_idx} kare, {elapsed:.1f}s")
        log.info(f"  Çıktı video: {out_path}")

        # Rapor
        log.info(f"\n{'='*60}")
        log.info(f"  SONUÇ RAPORU")
        log.info(f"{'='*60}")
        df = evaluator.get_results_dataframe()
        if not df.empty:
            log.info(f"\n{df.to_string(index=False)}")
        else:
            log.info("  Koşucu tespit edilmedi")
        
        try:
            evaluator.export_results(output_dir)
            log.info(f"✓ Sonuçlar dışa aktarıldı: {output_dir}")
        except Exception as e:
            log.error(f"Sonuçlar dışa aktarılırken hata: {e}")
        
        log.info(f"{'='*60}\n")
    
    except Exception as e:
        log.error(f"Video işlemesi kritik hataya uğradı: {e}")
        cap.release()
        try:
            writer.release()
        except:
            pass
        if display:
            cv2.destroyAllWindows()
        raise


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """CLI ana giriş noktası."""
    parser = argparse.ArgumentParser(
        description="Otomatik Mekik Testi v3 (Tek Çizgi + Senkronize)")
    parser.add_argument("--video", "-v", type=str, default=None,
                        help="Video dosyası yolu")
    parser.add_argument("--url", "-u", type=str, default=None,
                        help="YouTube video URL'si")
    parser.add_argument("--no-display", action="store_true",
                        help="Görüntüleme penceresi gösterme (max FPS)")
    parser.add_argument("--start-time", type=float, default=VIDEO_START_TIME_SEC,
                        help=f"Koşunun videoda başladığı saniye (varsayılan: {VIDEO_START_TIME_SEC})")
    args = parser.parse_args()

    try:
        # Sistem kontrol
        log.info("Sistem bağımlılıkları kontrol ediliyor...")
        validate_environment()
        validate_project_setup(Path(__file__).parent)
        
        # Video URL verilmişse indir
        if args.url:
            log.info(f"YouTube URL'si sağlandı: {args.url}")
            video_path = download_video(args.url, DATA_INPUTS)
        else:
            video_path = find_video(args.video)

        log.info(f"\nVideo dosyası seçildi: {video_path}")
        
        process_video(
            video_path=video_path,
            display=not args.no_display,
            start_time_sec=args.start_time,
        )
        
        log.info("✓ İşlem başarıyla tamamlandı")
    
    except KeyboardInterrupt:
        log.warning("\nKullanıcı işlemi durdurdu (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log.error(f"\nKritik hata: {e}", exc_info=True)
        log.error("\nLog dosyasını kontrol edin: data/logs/")
        sys.exit(1)


if __name__ == "__main__":
    main()
