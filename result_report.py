"""
result_report.py - Analiz sonuclarini herkesin okuyabilecegi tablolara cevirir.

Her video klasorune yazilanlar:
    SONUC.html          okunur rapor (tarayicida acilir)
    SONUC.xlsx          "Sonuc" ve "Mekik mekik" sayfalari
    sonuc_ozet.csv      kosucu basina tek satir
    sonuc_mekikler.csv  kosucu ve mekik basina tek satir
    son_durum.jpg       videonun son ekrani
    teknik/             ham veriler (ham_ozet.csv, ham_gecisler.csv, run_metadata.json)
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

import cv2
import pandas as pd

from config import SHUTTLES_PER_LEVEL, SHUTTLE_DISTANCE_M, RunnerState

READABLE_SUMMARY_FILE = "sonuc_ozet.csv"
READABLE_SHUTTLES_FILE = "sonuc_mekikler.csv"
EXCEL_FILE = "SONUC.xlsx"
HTML_FILE = "SONUC.html"
FINAL_FRAME_FILE = "son_durum.jpg"
TECH_DIR = "teknik"

ON_TIME = "Zamanında"
LATE_WARNING = "Geç kaldı (uyarı)"
LATE_ARRIVAL = "Geç ulaştı (uyarı)"
ELIMINATED = "Ulaşamadı → elendi"

SUMMARY_COLUMNS = ["Koşucu", "Sonuç", "Tamamlanan mekik", "Koşulan mesafe (m)",
                   "Ulaştığı seviye", "Son hız (km/sa)", "Uyarı (geç kalma)",
                   "Elendiği an", "Açıklama"]
SHUTTLE_COLUMNS = ["Koşucu", "Mekik", "Seviye", "Hedef çizgi", "Bip (s)",
                   "Çizgiye ulaştı (s)", "Sonuç"]


def shuttle_schedule(beep_times: list[float]) -> list[dict]:
    """Bip listesinden her mekigin seviyesini, hizini ve hedef cizgisini cikarir."""
    rows = []
    prev = 0.0
    level, in_level = 1, 0
    for index, deadline in enumerate(beep_times, start=1):
        in_level += 1
        limit = SHUTTLES_PER_LEVEL[level - 1] if level <= len(SHUTTLES_PER_LEVEL) else in_level
        if in_level > limit:
            level, in_level = level + 1, 1
        interval = float(deadline) - prev
        prev = float(deadline)
        speed = round(SHUTTLE_DISTANCE_M * 3.6 / interval * 2) / 2 if interval > 0 else 0.0
        rows.append({
            "no": index,
            "level": level,
            "in_level": in_level,
            "label": f"Seviye {level} – {in_level}. mekik",
            "speed_kmh": speed,
            "deadline": round(float(deadline), 2),
            "target": "20 m" if index % 2 == 1 else "Başlangıç (0 m)",
        })
    return rows


def _shuttle_outcomes(runner) -> dict[int, tuple[str, float | None]]:
    """Kosucunun mekik numarasina gore son karari: (sonuc, cizgiye ulasma zamani)."""
    outcomes: dict[int, tuple[str, float | None]] = {}
    for entry in runner.crossing_log:
        status = entry["status"]
        no = int(entry["shuttle_no"])
        if status.startswith("AKTIF") or status.startswith("Atlandi"):
            continue
        if status.startswith("Gecti"):
            outcomes[no] = (ON_TIME, round(entry["time"], 2))
        elif status.startswith("ELENDI"):
            reached = entry["time"] if "gec gecis" in status else None
            outcomes[no] = (ELIMINATED, round(reached, 2) if reached is not None else None)
        elif "gec gecis" in status:
            outcomes[no] = (LATE_ARRIVAL, round(entry["time"], 2))
        elif status.startswith("GEC"):
            outcomes.setdefault(no, (LATE_WARNING, None))
    return outcomes


def readable_tables(evaluator) -> tuple[pd.DataFrame, pd.DataFrame]:
    schedule = shuttle_schedule(evaluator.get_beep_times())
    by_no = {row["no"]: row for row in schedule}
    summary_rows, shuttle_rows = [], []
    for track_id, runner in sorted(evaluator._runners.items()):
        name = f"Koşucu {track_id}"
        outcomes = _shuttle_outcomes(runner)
        completed = sorted(no for no, (result, _t) in outcomes.items() if result in (ON_TIME, LATE_ARRIVAL))
        last = by_no.get(completed[-1]) if completed else None
        eliminated = runner.state == RunnerState.ELIMINATED
        elim_no = max((no for no, (r, _t) in outcomes.items() if r == ELIMINATED), default=None)
        if eliminated:
            target = by_no[elim_no]["target"] if elim_no in by_no else "hedef"
            seconds = f"{runner.elimination_time:.1f}".replace(".", ",")
            when = f"{seconds}. saniye – {elim_no}. mekik" if elim_no else f"{seconds}. saniye"
            note = f"Üst üste 2. kez bip çaldığında {target} çizgisine ulaşamadı."
        else:
            when = "-"
            note = "Kayıt bitene kadar testi sürdürdü."
        summary_rows.append({
            "Koşucu": name,
            "Sonuç": "Elendi" if eliminated else "Devam etti",
            "Tamamlanan mekik": len(completed),
            "Koşulan mesafe (m)": int(len(completed) * SHUTTLE_DISTANCE_M),
            "Ulaştığı seviye": last["label"] if last else "-",
            "Son hız (km/sa)": last["speed_kmh"] if last else "-",
            "Uyarı (geç kalma)": sum(1 for r, _t in outcomes.values() if r in (LATE_WARNING, LATE_ARRIVAL)),
            "Elendiği an": when,
            "Açıklama": note,
        })
        last_evaluated = max(outcomes, default=0)
        for no in range(1, last_evaluated + 1):
            info = by_no.get(no)
            if info is None:
                continue
            result, reached = outcomes.get(no, ("Değerlendirilmedi", None))
            shuttle_rows.append({
                "Koşucu": name,
                "Mekik": no,
                "Seviye": info["label"],
                "Hedef çizgi": info["target"],
                "Bip (s)": info["deadline"],
                "Çizgiye ulaştı (s)": reached if reached is not None else "-",
                "Sonuç": result,
            })
    return (pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS),
            pd.DataFrame(shuttle_rows, columns=SHUTTLE_COLUMNS))


def _style_excel(path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill

    fills = {"Elendi": "F8D7DA", ELIMINATED: "F8D7DA", "Devam etti": "D4EDDA", ON_TIME: "D4EDDA",
             LATE_WARNING: "FFF3CD", LATE_ARRIVAL: "FFF3CD"}
    wb = load_workbook(path)
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for column in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
            ws.column_dimensions[column[0].column_letter].width = min(60, width + 2)
        ws.freeze_panes = "A2"
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                color = fills.get(str(cell.value))
                if color:
                    cell.fill = PatternFill("solid", fgColor=color)
    wb.save(path)


def _html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>Kayıt yok.</p>"
    classes = {"Elendi": "bad", ELIMINATED: "bad", "Devam etti": "ok", ON_TIME: "ok",
               LATE_WARNING: "warn", LATE_ARRIVAL: "warn"}
    head = "".join(f"<th>{escape(str(c))}</th>" for c in df.columns)
    body = []
    for _, row in df.iterrows():
        cells = "".join(f'<td class="{classes.get(str(v), "")}">{escape(str(v))}</td>' for v in row)
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table"><table><tr>{head}</tr>{"".join(body)}</table></div>'


PAGE_STYLE = """body{margin:0;background:#f6f7f9;color:#1d2731;font:16px/1.55 system-ui,'Segoe UI',sans-serif}
main{max-width:1180px;margin:auto;padding:32px 20px}h1{margin:4px 0 8px}h2{margin-top:36px}
.muted{color:#5b6b78}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
.card{background:#fff;border:1px solid #dde3e8;border-radius:10px;padding:12px 18px}.card b{display:block;font-size:26px}
.note{background:#fff8e1;border-left:4px solid #e0a800;padding:12px 16px;margin:16px 0}
.table{overflow:auto;background:#fff;border:1px solid #dde3e8;border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #eef1f4;white-space:nowrap}
th{background:#eef2f5}td.ok{color:#11692c;font-weight:600}td.bad{color:#a4161a;font-weight:600}td.warn{color:#8a6100;font-weight:600}
img{max-width:100%;border-radius:10px;border:1px solid #dde3e8}a{color:#0b5cad}"""


def write_readable_outputs(output_dir, evaluator, metadata: dict, final_frame=None,
                           title: str = "Mekik testi sonucu", note: str = "") -> pd.DataFrame:
    """Okunur CSV, Excel ve HTML raporlarini yazar; ozet tabloyu dondurur."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata['dashboard_version'] = getattr(evaluator, 'dashboard_version', 1)
    metadata_path = output_dir / TECH_DIR / 'run_metadata.json'
    if metadata_path.is_file():
        metadata_path.write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
    summary, shuttles = readable_tables(evaluator)
    if not metadata.get("scoring_eligible", True):
        summary["Sonuç"] = "Puanlanmadı"
        for column in ("Tamamlanan mekik", "Koşulan mesafe (m)", "Ulaştığı seviye", "Son hız (km/sa)",
                       "Uyarı (geç kalma)", "Elendiği an"):
            summary[column] = "-"
        summary["Açıklama"] = "Standart bip testi protokolüne uymayan kayıt; puan ve eleme kararı üretilmedi."
        shuttles = pd.DataFrame(columns=SHUTTLE_COLUMNS)
    summary.to_csv(output_dir / READABLE_SUMMARY_FILE, index=False, encoding="utf-8-sig")
    shuttles.to_csv(output_dir / READABLE_SHUTTLES_FILE, index=False, encoding="utf-8-sig")
    excel = output_dir / EXCEL_FILE
    with pd.ExcelWriter(excel, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Sonuç", index=False)
        shuttles.to_excel(writer, sheet_name="Mekik mekik", index=False)
    _style_excel(excel)
    if final_frame is not None:
        cv2.imencode(".jpg", final_frame)[1].tofile(str(output_dir / FINAL_FRAME_FILE))

    notes = []
    if metadata.get("approximate"):
        notes.append("Bu çalıştırma görüntülü modda (video kendi hızında, kareler atlanarak) yapıldı. "
                     "Kesin puan için ekransız modda tekrar çalıştırın.")
    if metadata.get("analysis_status") == "no_runners_detected":
        notes.append("Koşucu tespit edilemedi; bu çalıştırmada puan yok.")
    if note:
        notes.append(note)
    notes_html = "".join(f'<div class="note">{escape(n)}</div>' for n in notes)
    finished = int((summary["Sonuç"] == "Devam etti").sum()) if not summary.empty else 0
    eliminated = int((summary["Sonuç"] == "Elendi").sum()) if not summary.empty else 0
    video_name = Path(metadata.get("output_video", "")).name
    html = f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>{PAGE_STYLE}</style><main>
<div class="muted">20 m mekik koşusu · çift kamera analizi</div><h1>{escape(title)}</h1>
<div class="cards"><div class="card">Koşucu<b>{len(summary)}</b></div>
<div class="card">Testi sürdüren<b>{finished}</b></div>
<div class="card">Elenen<b>{eliminated}</b></div></div>
{notes_html}
<h2>Sonuç</h2>{_html_table(summary)}
<p class="muted">Koşucu numaraları başlangıç kamerasından bakınca soldan sağa sıralıdır.
Bip çaldığında hedef çizgiye ulaşamayan koşucu uyarı alır; üst üste ikinci kez ulaşamayan elenir.</p>
{f'<h2>Son durum</h2><img src="{FINAL_FRAME_FILE}" alt="Son durum">' if final_frame is not None else ''}
<h2>Mekik mekik</h2>{_html_table(shuttles)}
<p><a href="{escape(video_name, quote=True)}">Analiz videosu</a> · <a href="{EXCEL_FILE}">Excel</a></p>
<p class="muted">Sonuçlar otomatik değerlendirmedir; çizgi, kamera senkronu ve çıkış bipi ayarlarına bağlıdır.</p>
</main></html>"""
    (output_dir / HTML_FILE).write_text(html, encoding="utf-8")
    return summary


def write_overview(results: list[tuple[str, Path, pd.DataFrame, str]], out_dir) -> tuple[Path, Path]:
    """Tum kayitlarin ozetini tek Excel ve tek HTML sayfasina yazar.

    results: (kayit adi, video klasoru, ozet tablo, not) listesi
    """
    out_dir = Path(out_dir)
    frames = []
    sections = []
    for name, folder, summary, note in results:
        df = summary.copy()
        df.insert(0, "Kayıt", name)
        frames.append(df)
        rel = Path(folder).name + "/" + HTML_FILE
        note_html = f'<div class="note">{escape(note)}</div>' if note else ""
        sections.append(f'<h2>{escape(name)} <a href="{escape(rel, quote=True)}">ayrıntılı rapor →</a></h2>'
                        f"{note_html}{_html_table(summary)}")
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["Kayıt", *SUMMARY_COLUMNS])
    excel = out_dir / "TUM_SONUCLAR.xlsx"
    with pd.ExcelWriter(excel, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="Tüm kayıtlar", index=False)
    _style_excel(excel)
    html = f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mekik testi sonuçları</title>
<style>{PAGE_STYLE}</style><main><div class="muted">20 m mekik koşusu · çift kamera analizi</div>
<h1>Tüm kayıtların sonuçları</h1><p><a href="TUM_SONUCLAR.xlsx">Excel olarak indir</a></p>
{''.join(sections)}</main></html>"""
    page = out_dir / "SONUCLAR.html"
    page.write_text(html, encoding="utf-8")
    return excel, page
