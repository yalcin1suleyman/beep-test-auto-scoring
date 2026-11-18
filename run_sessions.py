"""
run_sessions.py - Masaustundeki 'MEKİK VİDEO' kayitlarini analiz eden baslatici.

Her klasorde iki telefon kaydi vardir: 0m (baslangic) ve 20m kameralari.
Kamera rolleri, cizgiler, kosucu sayisi, cikis bipi ve iki kamera arasindaki
zaman farki mekik_sessions.json dosyasinda tutulur.

Kullanim:
    python run_sessions.py                      # Menuden kayit sec, goruntulu calistir
    python run_sessions.py --list               # Kayitlari listele
    python run_sessions.py --session 2          # Video 2'yi goruntulu analiz et
    python run_sessions.py --session 2 --no-display
    python run_sessions.py --session 2 --full-frames   # goruntulu ama her kare (yavas)
    python run_sessions.py --all --no-display   # Tum kayitlar + toplu ozet
    python run_sessions.py --session 2 --recalibrate   # Cizgileri fareyle yeniden sec
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from config import DATA_OUTPUTS, DEFAULT_BEEP_AUDIO_URL
from dual_main import process_dual_camera
from line_geometry import PerspectiveLine
from result_report import HTML_FILE, READABLE_SUMMARY_FILE, write_overview
from run_start import DEFAULT_REACTION_SEC, detect_departure

PROJECT_DIR = Path(__file__).resolve().parent
SESSIONS_FILE = PROJECT_DIR / "mekik_sessions.json"
SESSIONS_OUTPUT_DIR = DATA_OUTPUTS / "sonuclar"


def load_sessions(path: Path = SESSIONS_FILE) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, data["sessions"]


def parse_line(value: str) -> list[tuple[int, int]]:
    return [tuple(int(v) for v in point.split(",")) for point in value.split(";")]


def format_line(points) -> str:
    return ";".join(f"{int(round(x))},{int(round(y))}" for x, y in points)


def session_paths(data: dict, session: dict) -> tuple[Path, Path]:
    root = Path(data["video_root"]).expanduser()
    if not root.is_absolute():
        root = PROJECT_DIR / root
    return root / session["start_video"], root / session["far_video"]


def session_output_dir(session: dict) -> Path:
    return SESSIONS_OUTPUT_DIR / session["name"].lower().replace(" ", "_")


def print_sessions(data: dict, sessions: list[dict]) -> None:
    print(f"\nKayit klasoru: {Path(data['video_root']).expanduser()}\n")
    for s in sessions:
        start, far = session_paths(data, s)
        ok = "ok" if start.is_file() and far.is_file() else "VIDEO EKSIK"
        beep = s["start_beep_time"]
        beep_text = f"{beep:>5.2f}s" if isinstance(beep, (int, float)) else "kalkistan"
        print(f"  [{s['id']}] {s['name']:<8} {s['runner_count']} kosucu  "
              f"cikis bipi {beep_text}  ofset {s['cam2_offset']:+.2f}s  ({ok})")
        if s.get("note"):
            print(f"        not: {s['note']}")
    print()


def resolve_start_beep(session: dict, start_video: Path) -> float:
    """
    Cikis bipi saniyesi. "kalkis" verilirse ses kullanilmaz: kosucularin
    baslangic cizgisinden kalkis ani goruntuden bulunur, tepki suresi cikarilir.
    Sonraki bipler resmi mekik temposundan hesaplanir.
    """
    value = session["start_beep_time"]
    if isinstance(value, (int, float)):
        return float(value)
    if value != "kalkis":
        raise ValueError(f"start_beep_time sayi veya 'kalkis' olmali: {value!r}")
    line_y = PerspectiveLine.from_points(parse_line(session["start_line"])).median_y
    departure = detect_departure(start_video, line_y, start_sec=float(session.get("video_start_time", 0.0)))
    if departure is None:
        raise RuntimeError("Kosucularin kalkis ani goruntuden bulunamadi; start_beep_time'i elle girin.")
    beep = max(0.0, departure - DEFAULT_REACTION_SEC)
    print(f"[Kalkis] Kosucular {departure:.2f}s'de kalkti; cikis bipi {beep:.2f}s kabul edildi.")
    return beep


def run_session(data: dict, session: dict, display: bool, max_frames: int | None = None,
                hold_open: bool = False, recalibrate: bool = False,
                realtime_preview: bool = False) -> dict:
    start_video, far_video = session_paths(data, session)
    for path in (start_video, far_video):
        if not path.is_file():
            raise FileNotFoundError(f"Video bulunamadi: {path}")
    output_dir = session_output_dir(session)
    print(f"\n{'#' * 65}\n  {session['name']}  ->  {output_dir}\n{'#' * 65}")
    if session.get("note"):
        print(f"  NOT: {session['note']}")

    metadata = process_dual_camera(
        start_video_path=start_video,
        far_video_path=far_video,
        real_dual_camera=True,
        display=display,
        start_time_sec=float(session.get("video_start_time", 0.0)),
        cam2_offset_sec=float(session["cam2_offset"]),
        use_audio=True,
        max_frames=max_frames,
        beep_audio_url=DEFAULT_BEEP_AUDIO_URL,
        start_beep_time_override=resolve_start_beep(session, start_video),
        start_line_points=None if recalibrate else parse_line(session["start_line"]),
        far_line_points=None if recalibrate else parse_line(session["far_line"]),
        output_dir=output_dir,
        runner_count=int(session["runner_count"]),
        hold_open=hold_open,
        realtime_preview=realtime_preview,
        report_title=f"{session['name']} – mekik testi sonucu",
        report_note=session.get("note", ""),
        scoring_eligible=session.get("scoring_eligible", True),
    )
    if recalibrate and metadata:
        session["start_line"] = format_line(metadata["start_line"])
        session["far_line"] = format_line(metadata["far_line"])
        SESSIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[Kalibrasyon] Yeni cizgiler {SESSIONS_FILE.name} dosyasina kaydedildi.")
    return metadata


def update_overview(sessions: list[dict]) -> Path | None:
    """Analizi bulunan tum kayitlari SONUCLAR.html ve TUM_SONUCLAR.xlsx'e toplar."""
    results = []
    for session in sessions:
        folder = session_output_dir(session)
        summary_csv = folder / READABLE_SUMMARY_FILE
        if summary_csv.is_file() and (folder / HTML_FILE).is_file():
            results.append((session["name"], folder, pd.read_csv(summary_csv), session.get("note", "")))
    if not results:
        return None
    _excel, page = write_overview(results, SESSIONS_OUTPUT_DIR)
    return page


def choose_interactively(sessions: list[dict]) -> list[dict]:
    ids = {str(s["id"]): s for s in sessions}
    while True:
        answer = input("Analiz edilecek kayit numarasi (1-7, 'h' = hepsi, 'q' = cikis): ").strip().lower()
        if answer in {"q", "cikis", ""}:
            return []
        if answer in {"h", "hepsi", "all"}:
            return list(sessions)
        if answer in ids:
            return [ids[answer]]
        print("Gecersiz secim.")


def main() -> int:
    parser = argparse.ArgumentParser(description="MEKİK VİDEO kayitlarini analiz et")
    parser.add_argument("--session", "-s", type=int, action="append",
                        help="Kayit numarasi (birden fazla kez verilebilir)")
    parser.add_argument("--all", action="store_true", help="Tum kayitlari analiz et")
    parser.add_argument("--list", action="store_true", help="Kayitlari listele ve cik")
    parser.add_argument("--no-display", action="store_true", help="Pencere acmadan analiz et")
    parser.add_argument("--hold-open", action="store_true", help="Video sonunda pencereyi acik tut")
    parser.add_argument("--full-frames", action="store_true",
                        help="Goruntulu modda da her kareyi analiz et (video gercek hizdan yavas akar)")
    parser.add_argument("--max-frames", type=int, default=None, help="Deneme icin kare siniri")
    parser.add_argument("--recalibrate", action="store_true",
                        help="Cizgileri fareyle yeniden sec ve dosyaya kaydet")
    args = parser.parse_args()

    data, sessions = load_sessions()
    if args.list:
        print_sessions(data, sessions)
        return 0
    if args.recalibrate and args.no_display:
        parser.error("--recalibrate fareyle secim icin goruntu ister; --no-display ile kullanilamaz.")

    if args.all:
        selected = list(sessions)
    elif args.session:
        by_id = {s["id"]: s for s in sessions}
        unknown = [i for i in args.session if i not in by_id]
        if unknown:
            parser.error(f"Bilinmeyen kayit numarasi: {unknown}")
        selected = [by_id[i] for i in args.session]
    else:
        print_sessions(data, sessions)
        selected = choose_interactively(sessions)
    if not selected:
        return 0

    failures = []
    for session in selected:
        try:
            run_session(data, session, display=not args.no_display,
                                   max_frames=args.max_frames, hold_open=args.hold_open,
                                   recalibrate=args.recalibrate,
                                   realtime_preview=not args.no_display and not args.full_frames)
        except Exception as exc:  # Bir kayit hatasi digerlerini durdurmasin
            print(f"[HATA] {session['name']}: {exc}")
            failures.append(session["name"])

    page = update_overview(sessions)
    if page:
        print(f"\nTum sonuclar: {page}")
    if failures:
        print(f"Basarisiz kayitlar: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
