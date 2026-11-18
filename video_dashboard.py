"""Readable video dashboard drawn on the analysis frames."""
import math

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
    evaluator.dashboard_version = 2
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
    next_index = next((i for i,t in enumerate(beep_times) if t >= current_time), None)
    shuttle_no = shuttle['global_idx'] if shuttle else (next_index+1 if next_index is not None else None)
    target = '20m' if shuttle_no and shuttle_no % 2 else '0m'
    metrics = [f"YARIS  {max(0,current_time):.1f} s",
               f"AKTIF  {evaluator.get_active_count()} / {runner_count}",
               'CIKIS BEKLENIYOR' if current_time < 0 else (f"HEDEF  {target}" if shuttle_no else 'TAKVIM SONU'),
               f"CIKIS BIPI  {-current_time:.1f} s" if current_time < 0 else
               (f"SONRAKI BIP  {max(0,next_beep-current_time):.1f} s" if next_beep is not None else 'BIP TAKVIMI BITTI')]
    step = w / 4
    for i, label in enumerate(metrics):
        text(canvas, label, int(i*step)+18, 86, .56, max_width=int(step)-28)
    cv2.rectangle(canvas, (0, 98), (int(w*max(0,min(1,progress))), 101), ACCENT, -1)
    text(canvas, '01 / BASLANGIC KAMERASI', 18, 120, .44, MUTED)
    text(canvas, '02 / 20m KAMERASI', w//2+18, 120, .44, MUTED)
    statuses = evaluator.get_all_runner_statuses()
    eligible = getattr(evaluator, 'scoring_eligible', True)
    if not eligible:
        cv2.rectangle(canvas, (0, 0), (w, 101), BG, -1)
        text(canvas, 'MEKIK / GOZLEM', 18, 30, .8, ACCENT, 2)
        text(canvas, 'PROTOKOL DISI KAYIT - STANDART PUANLAMA YAPILMADI', 18, 64, .5, MUTED, max_width=w-36)
    for i in range(runner_count):
        col, row = i % 5, i // 5
        card_w = (w-36)//min(5,runner_count)
        x, y = 12+col*card_w, header+h+14+row*108
        cv2.rectangle(canvas, (x,y), (x+card_w-8,y+94), SURFACE, -1)
        runner = statuses.get(i+1)
        label = runner.state.value.upper() if runner else 'TESPIT BEKLENIYOR'
        if not eligible:
            label = 'PUANLANMADI'
        color = ((95, 205, 104) if label == 'AKTIF' else
                 (100, 205, 255) if label == 'UYARI' else
                 (110, 110, 250) if label == 'ELENDI' else MUTED)
        text(canvas, f'KOSUCU {i+1:02}', x+12, y+23, .52, TEXT, 1, card_w-30)
        text(canvas, label, x+12, y+44, .44, color, 1, card_w-30)
        stats = f"Gecis {runner.total_crossings}   Zamaninda {runner.on_time_count}" if runner else 'Henuz veri yok'
        if not eligible:
            stats = 'Standart bip testi degil'
        text(canvas, stats, x+12, y+65, .39, MUTED, 1, card_w-30)
        if runner and eligible:
            text(canvas, f'Gec {runner.late_count}   Ardisik {runner.consecutive_late}', x+12, y+83, .39, MUTED, 1, card_w-30)
    text(canvas, 'Q / ESC: durdur     |     Cizgiler ve cikis bipi kayda ozel kalibre edilmelidir.', 18, canvas.shape[0]-10, .38, MUTED, max_width=w-36)
    return canvas
