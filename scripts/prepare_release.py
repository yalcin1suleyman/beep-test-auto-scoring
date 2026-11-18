"""Validate all full-frame session outputs and publish a reproducible report.

Run analyses first: python scripts/start_full_batch.py
Then: python scripts/audit_session_sources.py
      python -m pytest -q --junitxml=data/outputs/hazirlik_2026-11-18/testler.xml
      python scripts/prepare_release.py
"""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from importlib import metadata as package_metadata
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_sessions import load_sessions, session_output_dir, session_paths, update_overview, parse_line
from scripts.verify_analysis_output import verify, canonical_table
from scripts.refresh_video_headers import refresh, reference_deadlines
from config import YOLO_MODEL, TRACKER_CONFIG, LATE_TOLERANCE_SEC, LINE_TOUCH_TOLERANCE_PX, MAX_CONSECUTIVE_LATE

REVIEW_DIR = ROOT/'data/outputs/hazirlik_2026-11-18'
REPORT_DIR = ROOT/'docs/reports/2026-11-18'


def analysis_code_hash():
    digest = hashlib.sha256()
    # Presentation can be regenerated independently of the expensive inference.
    for path in sorted([p for p in ROOT.glob('*.py') if p.name not in
                        {'video_dashboard.py', 'result_report.py', 'logger.py'}] + [ROOT/'mekik_sessions.json']):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_report():
    data, sessions = load_sessions()
    marker = json.loads((REVIEW_DIR/'batch_started.json').read_text(encoding='utf-8'))
    assert marker['analysis_code_sha256'] == analysis_code_hash(), 'Analizden sonra kod/ayar degisti; analizleri yenileyin'
    not_before = datetime.fromisoformat(marker['started_utc']).timestamp()
    audit = json.loads((REVIEW_DIR/'source_audit.json').read_text(encoding='utf-8'))
    assert len(audit) == 2*len(sessions)
    assert all(row['original_matches'] and row['decoded_frames'] == row['expected_frames'] for row in audit)
    for source in audit:
        with (ROOT/source['path']).open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest() == source['sha256'], 'Kaynak dosya analizden sonra degisti'
    xml = ET.parse(REVIEW_DIR/'testler.xml').getroot()
    suites = list(xml.iter('testsuite'))
    tests = sum(int(s.get('tests','0')) for s in suites)
    failures = sum(int(s.get('failures','0'))+int(s.get('errors','0')) for s in suites)
    assert tests > 0 and failures == 0, 'Otomatik testler gecmedi'
    results, participants = [], []
    deadlines = reference_deadlines()
    for session in sessions:
        folder = session_output_dir(session)
        meta = json.loads((folder/'teknik/run_metadata.json').read_text(encoding='utf-8'))
        assert (folder/'teknik/run_metadata.json').stat().st_mtime >= not_before, f"Eski calistirma: {session['name']}"
        assert not meta['approximate'] and meta['analyzed_frames'] == meta['processed_frames']
        assert meta['completion_reason'] in {'video_end','camera2_end'}
        assert meta['runner_count'] == session['runner_count'], f"Kosucu sayisi eksik: {session['name']}"
        assert meta['scoring_eligible'] == session.get('scoring_eligible',True)
        assert meta['start_line'] == [list(p) for p in parse_line(session['start_line'])]
        assert meta['far_line'] == [list(p) for p in parse_line(session['far_line'])]
        assert meta['run_zero_seconds'] == session['start_beep_time']
        expected_paths = session_paths(data, session)
        assert Path(meta['start_video']).resolve() == expected_paths[0].resolve()
        assert Path(meta['far_video']).resolve() == expected_paths[1].resolve()
        sources = [r for r in audit if r['path'] in [p.relative_to(ROOT).as_posix() for p in expected_paths]]
        a, b = sources
        overlap = min(a['decoded_frames']/a['fps'], b['decoded_frames']/b['fps']-session['cam2_offset']) - session.get('video_start_time',0)
        expected_frames = round(overlap*a['fps'])
        assert abs(expected_frames-meta['analyzed_frames']) <= 3, f"Ortak sure eksik: {session['name']}"
        # Never let presentation refresh turn a stale analysis into a fresh one.
        refresh(folder, session, deadlines)
        meta = json.loads((folder/'teknik/run_metadata.json').read_text(encoding='utf-8'))
        check = verify(folder)
        summary = pd.read_csv(folder/'sonuc_ozet.csv').fillna('-')
        for row in summary.to_dict(orient='records'):
            participants.append({'Kayıt':session['name'], **row})
        results.append(dict(id=session['id'], name=session['name'],
            scoring_eligible=meta['scoring_eligible'], frames=meta['analyzed_frames'],
            expected_overlap_frames=expected_frames, runners=meta['runner_count'],
            continued=int((summary['Sonuç']=='Devam etti').sum()),
            eliminated=int((summary['Sonuç']=='Elendi').sum()),
            unscored=int((summary['Sonuç']=='Puanlanmadı').sum()),
            elapsed_seconds=meta['elapsed_seconds'], validation=check, note=session.get('note',''),
            start_beep_time=session['start_beep_time'], cam2_offset=session['cam2_offset']))
        print(f"{session['name']}: {meta['analyzed_frames']} kare ve raporlar dogrulandi",flush=True)
    update_overview(sessions)
    source_files = sorted([*ROOT.glob('*.py'),ROOT/'mekik_sessions.json',*ROOT.glob('tests/*.py')])
    code_hash = hashlib.sha256()
    for file in source_files:
        code_hash.update(file.relative_to(ROOT).as_posix().encode())
        code_hash.update(file.read_bytes())
    manifest = dict(date='2026-11-18', generated_utc=datetime.now(timezone.utc).isoformat(),
        tests_passed=tests, failures=failures, source_videos=len(audit),
        source_frames=sum(r['decoded_frames'] for r in audit),
        analyzed_timeline_frames=sum(r['frames'] for r in results),
        scoring_sessions=sum(r['scoring_eligible'] for r in results),
        code_sha256=code_hash.hexdigest(), sessions=results, sources=audit)
    manifest['rules'] = {'late_tolerance_seconds':LATE_TOLERANCE_SEC,
        'line_touch_tolerance_pixels':LINE_TOUCH_TOLERANCE_PX, 'consecutive_late_limit':MAX_CONSECUTIVE_LATE}
    manifest['runtime'] = {'python':platform.python_version(), 'platform':platform.system(),
        'packages':{name:package_metadata.version(name) for name in
            ['ultralytics','torch','torchvision','opencv-python','numpy','pandas','openpyxl','scipy','imageio-ffmpeg','yt-dlp','lap','pytest']}}
    manifest['model_files'] = []
    for name in (YOLO_MODEL, TRACKER_CONFIG):
        path=(ROOT/name).resolve()
        with path.open('rb') as model_stream:
            digest=hashlib.file_digest(model_stream,'sha256').hexdigest()
        manifest['model_files'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest})
    REPORT_DIR.mkdir(parents=True,exist_ok=True)
    (REPORT_DIR/'dogrulama.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    pd.DataFrame(participants).to_csv(REPORT_DIR/'kosucu_sonuclari.csv',index=False,encoding='utf-8-sig')
    combined_excel = ROOT/'data/outputs/sonuclar/TUM_SONUCLAR.xlsx'
    pd.testing.assert_frame_equal(canonical_table(pd.DataFrame(participants)),
        canonical_table(pd.read_excel(combined_excel,sheet_name='Tüm kayıtlar')), check_dtype=False)
    shutil.copy2(combined_excel, REPORT_DIR/'TUM_SONUCLAR.xlsx')
    count_label = lambda value: format(value, ',').replace(',', '.')
    lines = ['# Mekik sistemi - teslim ve dogrulama raporu', '', 'Tarih: 18 Kasim 2026', '',
        f"- Otomatik test: {tests} gecti; {failures} hata.",
        f"- Kaynak kontrolu: {len(audit)} video, {count_label(manifest['source_frames'])} kare; masaustu asillariyla SHA-256 eslesmesi saglandi.",
        f"- Analiz: {len(results)} kamera cifti, {count_label(manifest['analyzed_timeline_frames'])} birinci kamera zaman cizelgesi karesi; kare atlama yok.",
        f"- Standart puanlama: {manifest['scoring_sessions']} kayit. Video 7 protokol disi gozlem olarak tamamlandi ve puanlanmadi.", '',
        '| Kayit | Analiz karesi | Kosucu | Devam etti | Elendi | Puanlanmadi | Sure (s) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"| {r['name']} | {r['frames']} | {r['runners']} | {r['continued']} | {r['eliminated']} | {r['unscored']} | {r['elapsed_seconds']:.1f} |")
    lines += ['', '## Dogrulamanin kapsami', '',
        '14 kaynak dosyanin tum kareleri okundu. Kamera cifti analizinde birinci kameranin her karesi islenir; ikinci kamera zaman damgasina gore eslenir. Farkli FPS kayitlarinda ikinci kameranin her kaynak karesine model uygulanmasi anlamina gelmez. Sadece iki kameranin ortak zaman araligi puanlanir.', '',
        'Goruntu kontrolunde kenardaki bir nesnenin kosucu kimligi alabildigi goruldu. Kulvar atamasi hedef cizginin yakinindaki tespitlerle sinirlandirildi; kamera hareketinde bu alan ve kulvar uclari cizgiyle birlikte tasinir. Referans sesli calismalarda hedef etiketinin bekleme durumunda kalmasi duzeltildi. Mevcut ciktilarin sadece bilgi basligi yeniden olusturuldu; puanlama ve kamera eslestirmesi degistirilmedi.', '',
        'Cikti videolari tekrar sonuna kadar cozuldu. CSV ve Excel verileri, toplamlar, basarili mekik kayitlarinin tekilligi, kosucu sayilari, cizgi ayarlari ve cikis bipi bilgisi kontrol edildi. Her videonun ve metadatanin SHA-256 degeri dogrulama kaydinda saklandi.', '',
        '## Sonuclarin yorumu', '',
        'Teknik analiz ve raporlama akisi dogrulanmistir. Sonuclar otomatik model kararlaridir; hakem/insan etiketleriyle bir dogruluk yuzdesi olculmemistir. Bu rapor kusursuz kisi kimligi, temas tespiti veya eleme dogrulugu iddiasi tasimaz.', '',
        'Video 1: Cikis bipi zayif oldugu icin baslangic zamani tahminidir. Notlardaki yaklasik +/-1 saniye belirsizlik eleme kararlarini etkileyebilir.',
        'Video 6: Kadraj kenarindaki kosucunun gorunurlugu sinirlidir.',
        'Video 7: Standart bip testi ritmine uymadigindan puan/mesafe/seviye ve eleme karari yayimlanmaz.', '',
        '## Dosyalar ve tekrar calistirma', '',
        '- Yerel tum sonuclar: `data/outputs/sonuclar/SONUCLAR.html` ve `TUM_SONUCLAR.xlsx`.',
        '- Kayit raporlari: `data/outputs/sonuclar/video_N/SONUC.html`, `SONUC.xlsx`, `analiz_videosu.mp4`.',
        '- Bu raporun makine kaydi: `dogrulama.json`; kosucu sonuclari: `kosucu_sonuclari.csv` ve `TUM_SONUCLAR.xlsx`.',
        '- Buyuk/ozel kaynak ve cikti videolari yeni GitHub commitine eklenmez. Rapor ve kod depoya dahil edilir.', '',
        '```powershell', 'python scripts/start_full_batch.py',
        'python scripts/audit_session_sources.py',
        'python -m pytest -q --junitxml=data/outputs/hazirlik_2026-11-18/testler.xml',
        'python scripts/prepare_release.py', '```', '']
    (REPORT_DIR/'RAPOR.md').write_text('\n'.join(lines),encoding='utf-8')
    return manifest


if __name__ == '__main__':
    build_report()
