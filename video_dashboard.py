"""Readable video dashboard and self-contained local result report."""
from html import escape
import math
from pathlib import Path

import cv2
import numpy as np

BG = (28, 21, 15)
SURFACE = (47, 37, 27)
TEXT = (243, 239, 231)
MUTED = (175, 163, 144)
ACCENT = (189, 220, 65)


def text(frame, label, x, y, scale=.55, color=TEXT, thickness=1, max_width=None):
    if max_width:
        while scale > .25 and cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0][0] > max_width:
            scale -= .025
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def render_dashboard(panels, evaluator, current_time, shuttle, beep_times,
                     runner_count, progress=0., approximate=False, finished=False):
    """Keep video unobstructed; reserve fixed areas for metrics and runner cards."""
    h, w = panels.shape[:2]
    rows = max(1, math.ceil(runner_count / 5))
    header, footer = 128, 38 + rows * 108
    canvas = np.full((h + header + footer, w, 3), BG, dtype=np.uint8)
    canvas[header:header+h] = panels
    text(canvas, 'MEKIK / ANALIZ', 18, 30, .8, ACCENT, 2)
    text(canvas, 'CIFT KAMERA  |  20 METRE PARKUR', 18, 53, .42, MUTED)
    state = 'TAMAMLANDI' if finished else ('ON IZLEME / KARE ATLANIYOR' if approximate else 'TUM KARELER ANALIZ EDILIYOR')
    text(canvas, state, max(18, w-350), 27, .45, ACCENT, max_width=330)
    next_beep = next((t for t in beep_times if t >= current_time), None)
    target = '20m' if shuttle and shuttle['global_idx'] % 2 else '0m'
    metrics = [f"YARIS  {max(0,current_time):.1f} s",
               f"AKTIF  {evaluator.get_active_count()} / {runner_count}",
               f"HEDEF  {target}" if shuttle else 'CIKIS BEKLENIYOR',
               f"SONRAKI BIP  {max(0,next_beep-current_time):.1f} s" if next_beep is not None else 'BIP TAKVIMI BITTI']
    step = w / 4
    for i, label in enumerate(metrics):
        text(canvas, label, int(i*step)+18, 86, .56, max_width=int(step)-28)
    cv2.rectangle(canvas, (0, 98), (int(w*max(0,min(1,progress))), 101), ACCENT, -1)
    text(canvas, '01 / BASLANGIC KAMERASI', 18, 120, .44, MUTED)
    text(canvas, '02 / 20m KAMERASI', w//2+18, 120, .44, MUTED)
    statuses = evaluator.get_all_runner_statuses()
    for i in range(runner_count):
        col, row = i % 5, i // 5
        card_w = (w-36)//min(5,runner_count)
        x, y = 12+col*card_w, header+h+14+row*108
        cv2.rectangle(canvas, (x,y), (x+card_w-8,y+94), SURFACE, -1)
        runner = statuses.get(i+1)
        label = runner.state.value.upper() if runner else 'TESPIT BEKLENIYOR'
        color = ((95, 205, 104) if label == 'AKTIF' else
                 (100, 205, 255) if label == 'UYARI' else
                 (110, 110, 250) if label == 'ELENDI' else MUTED)
        text(canvas, f'KOSUCU {i+1:02}', x+12, y+23, .52, TEXT, 1, card_w-30)
        text(canvas, label, x+12, y+44, .44, color, 1, card_w-30)
        stats = f"Gecis {runner.total_crossings}   Zamaninda {runner.on_time_count}" if runner else 'Henuz veri yok'
        text(canvas, stats, x+12, y+65, .39, MUTED, 1, card_w-30)
        if runner:
            text(canvas, f'Gec {runner.late_count}   Ardisik {runner.consecutive_late}', x+12, y+83, .39, MUTED, 1, card_w-30)
    text(canvas, 'Q / ESC: durdur     |     Cizgiler ve cikis bipi kayda ozel kalibre edilmelidir.', 18, canvas.shape[0]-10, .38, MUTED, max_width=w-36)
    return canvas


def export_visual_report(output_dir, metadata, evaluator, final_frame):
    output_dir = Path(output_dir)
    if final_frame is not None:
        cv2.imencode('.jpg', final_frame)[1].tofile(str(output_dir/'sonuc_paneli.jpg'))
    table = evaluator.get_results_dataframe().to_html(index=False, border=0, escape=True)
    mode = ('Kare atlamali on izleme — puanlama kesin analiz olarak kullanilamaz.' if metadata['approximate']
            else 'Secilen analiz araligindaki tum kareler islendi.')
    if metadata['analysis_status'] == 'no_runners_detected':
        mode += ' Kosucu tespit edilemedi; bu calistirmada puanlama sonucu yoktur.'
    html = f'''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mekik Analiz Raporu</title><style>
body{{margin:0;background:#0f151c;color:#e7eff3;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1280px;margin:auto;padding:36px 24px}}
small{{color:#adc6d2}}h1{{font-size:36px;margin:8px 0}}.accent{{color:#bddd41}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}
.card{{background:#1b252f;border:1px solid #304454;padding:16px 24px;border-radius:12px}}strong{{display:block;font-size:28px}}
img{{width:100%;border-radius:12px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #304454;white-space:nowrap}}th{{color:#bddd41}}
a{{color:#bddd41}}.note{{padding:16px;border-left:3px solid #bddd41;background:#1b252f;margin:24px 0}}</style>
<main><small class="accent">MEKIK / CIFT KAMERA ANALIZI</small><h1>Test sonuc raporu</h1>
<p>{escape(mode)}</p><div class="cards"><div class="card">Analiz edilen kare<strong>{metadata['analyzed_frames']}</strong></div>
<div class="card">Kosucu<strong>{metadata['runner_count']}</strong></div><div class="card">Islem suresi<strong>{metadata['elapsed_seconds']:.1f} s</strong></div></div>
<img src="sonuc_paneli.jpg" alt="Son durum paneli"><h2>Kosucu sonuclari</h2><div class="table">{table}</div>
<p><a href="{escape(Path(metadata['output_video']).name,quote=True)}">Analiz videosu</a> · <a href="sonuc_rapor.xlsx">Excel raporu</a> · <a href="sonuc_detay.csv">Gecis kayitlari</a></p>
<div class="note">Bu sonuclar secilen cizgilere, kamera senkronizasyonuna ve cikis bipi ayarina baglidir. Modelin kisi kimligi ve ayak tespiti insan etiketleriyle dogrulanmadan yuzde yuz puanlama dogrulugu varsayilamaz.</div>
<small>Kaynak 1: {escape(metadata['start_video'])}<br>Kaynak 2: {escape(metadata['far_video'])}<br>Bitis nedeni: {escape(metadata['completion_reason'])}</small></main></html>'''
    (output_dir/'analiz_raporu.html').write_text(html, encoding='utf-8')
