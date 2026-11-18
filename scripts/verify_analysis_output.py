"""Independently decode an analysis and reconcile its video, CSV and XLSX.

Usage: python scripts/verify_analysis_output.py data/outputs/sonuclar/video_2
"""
import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import pandas as pd


def canonical_table(frame):
    """Compare CSV text/numbers with Excel's typed values without rounding data."""
    def canonical(value):
        if pd.isna(value):
            return '-'
        try:
            return format(float(value), '.12g')
        except (ValueError, TypeError):
            return str(value)
    return frame.apply(lambda column: column.map(canonical))


def verify(folder):
    folder = Path(folder)
    meta = json.loads((folder/'teknik'/'run_metadata.json').read_text(encoding='utf-8'))
    summary = pd.read_csv(folder/'teknik'/'ham_ozet.csv').fillna('-')
    detail = pd.read_csv(folder/'teknik'/'ham_gecisler.csv').fillna('-')
    readable = pd.read_csv(folder/'sonuc_ozet.csv').fillna('-')
    shuttles = pd.read_csv(folder/'sonuc_mekikler.csv').fillna('-')
    excel = pd.read_excel(folder/'SONUC.xlsx', sheet_name=None)
    same = lambda a, b: pd.testing.assert_frame_equal(canonical_table(a), canonical_table(b), check_dtype=False)
    same(readable, excel['Sonuç'])
    same(shuttles, excel['Mekik mekik'])
    assert len(readable) == len(summary)
    assert len(summary) == meta['runner_count']
    assert (summary['Toplam Gecis'] == summary['20m Gecis']+summary['Baslangic Gecis']).all()
    assert (summary['Zamaninda'] <= summary['Toplam Gecis']).all()
    for _, row in summary.iterrows():
        events = detail[detail['Kosucu ID'] == row['Kosucu ID']]
        completions = events[events['Sonuc'].astype(str).str.startswith('Gecti -', na=False).astype(bool)]
        assert len(completions) == row['Zamaninda']
        assert not completions['Mekik No'].duplicated().any()
    cap = cv2.VideoCapture(meta['output_video'])
    count, sizes, thumbnails = 0, set(), []
    target_indices = {int(meta['processed_frames']*fraction) for fraction in (.05,.25,.5,.75,.95)}
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            sizes.add(frame.shape)
            if count in target_indices:
                thumb = cv2.resize(frame,(642,317))
                cv2.putText(thumb, f'KARE {count}', (8,305), cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
                thumbnails.append(thumb)
            count += 1
    finally:
        cap.release()
    assert count == meta['processed_frames'] and len(sizes) == 1
    assert meta['approximate'] or count == meta['analyzed_frames']
    if meta.get('scoring_eligible') is False:
        assert (readable['Sonuç'] == 'Puanlanmadı').all()
        assert (readable['Tamamlanan mekik'] == '-').all()
        assert shuttles.empty
    for filename in ('SONUC.html','son_durum.jpg'):
        assert (folder/filename).stat().st_size > 0
    if len(thumbnails) % 2:
        thumbnails.append(np.zeros_like(thumbnails[0]))
    if thumbnails:
        sheet = np.vstack([np.hstack(thumbnails[i:i+2]) for i in range(0,len(thumbnails),2)])
        cv2.imencode('.jpg',sheet)[1].tofile(str(folder/'teknik'/'goruntu_kontrol.jpg'))
    result = dict(ok=True, decoded_output_frames=count, analyzed_frames=meta['analyzed_frames'],
                  output_shape=list(next(iter(sizes))), runners=len(summary), detail_rows=len(detail),
                  csv_excel_match=True, duplicate_completions=False,
                  completion_reason=meta['completion_reason'], approximate=meta['approximate'])
    result['validated_at_utc'] = datetime.now(timezone.utc).isoformat()
    with Path(meta['output_video']).open('rb') as video_stream:
        result['video_sha256'] = hashlib.file_digest(video_stream, 'sha256').hexdigest()
    result['metadata_sha256'] = hashlib.sha256((folder/'teknik'/'run_metadata.json').read_bytes()).hexdigest()
    (folder/'teknik'/'output_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(json.dumps(verify(parser.parse_args().folder),indent=2))
