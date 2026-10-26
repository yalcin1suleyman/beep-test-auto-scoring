"""Independently decode an analysis and reconcile its video, CSV and XLSX.

Usage: python scripts/verify_analysis_output.py data/outputs/quality_review/validated
"""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import pandas as pd


def verify(folder):
    folder = Path(folder)
    meta = json.loads((folder/'run_metadata.json').read_text(encoding='utf-8'))
    summary = pd.read_csv(folder/'sonuc_ozet.csv').fillna('-')
    detail = pd.read_csv(folder/'sonuc_detay.csv').fillna('-')
    excel = pd.read_excel(folder/'sonuc_rapor.xlsx', sheet_name=None)
    pd.testing.assert_frame_equal(summary, excel['Ozet'].fillna('-'), check_dtype=False)
    pd.testing.assert_frame_equal(detail, excel['Detay'].fillna('-'), check_dtype=False)
    assert len(summary) == meta['runner_count']
    assert (summary['Toplam Gecis'] == summary['20m Gecis']+summary['Baslangic Gecis']).all()
    assert (summary['Zamaninda'] <= summary['Toplam Gecis']).all()
    for _, row in summary.iterrows():
        events = detail[detail['Kosucu ID'] == row['Kosucu ID']]
        completions = events[events['Sonuc'].str.startswith('Gecti -')]
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
    for filename in ('analiz_raporu.html','sonuc_paneli.jpg'):
        assert (folder/filename).stat().st_size > 0
    if len(thumbnails) % 2:
        thumbnails.append(np.zeros_like(thumbnails[0]))
    if thumbnails:
        sheet = np.vstack([np.hstack(thumbnails[i:i+2]) for i in range(0,len(thumbnails),2)])
        cv2.imencode('.jpg',sheet)[1].tofile(str(folder/'goruntu_kontrol.jpg'))
    result = dict(ok=True, decoded_output_frames=count, analyzed_frames=meta['analyzed_frames'],
                  output_shape=list(next(iter(sizes))), runners=len(summary), detail_rows=len(detail),
                  csv_excel_match=True, duplicate_completions=False,
                  completion_reason=meta['completion_reason'], approximate=meta['approximate'])
    (folder/'output_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(json.dumps(verify(parser.parse_args().folder),indent=2))
