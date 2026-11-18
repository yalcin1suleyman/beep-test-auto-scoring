"""Regenerate presentation-only target labels without repeating inference.

Version-1 dashboards displayed 'waiting for start' throughout reference-audio
analyses. Only the metric header is repainted; all camera panels and scores stay
as originally analyzed. Version-2 application outputs need no regeneration.
"""
import json
import csv
from pathlib import Path
import cv2

from config import REFERENCE_INPUTS
from audio_detector import BeepDetector
from dual_main import _reference_beeps_to_run_deadlines
from video_dashboard import BG, TEXT, text


def reference_deadlines():
    return _reference_beeps_to_run_deadlines(BeepDetector().detect_beeps(REFERENCE_INPUTS/'reference_beep_audio.mp4'))


def refresh(folder, session, deadlines):
    folder=Path(folder)
    metadata_path=folder/'teknik/run_metadata.json'
    meta=json.loads(metadata_path.read_text(encoding='utf-8'))
    if meta.get('dashboard_version',1) >= 2:
        return
    if not meta['scoring_eligible']:
        meta['dashboard_version']=2
        metadata_path.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
        return
    schedule_file=folder/'sonuc_mekikler.csv'
    if schedule_file.is_file():
        with schedule_file.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                number=int(row['Mekik'])
                assert abs(deadlines[number-1]-float(row['Bip (s)'])) < .02, 'Referans takvimi raporla eslesmiyor'
    def paint(frame,t):
        w=frame.shape[1]
        step=w/4
        index=next((i for i,deadline in enumerate(deadlines) if deadline >= t),None)
        target='20m' if index is not None and index%2==0 else '0m'
        label='CIKIS BEKLENIYOR' if t<0 else (f'HEDEF  {target}' if index is not None else 'TAKVIM SONU')
        cv2.rectangle(frame,(round(step*2),60),(round(step*3)-1,96),BG,-1)
        text(frame,label,int(step*2)+18,86,.56,max_width=int(step)-28)
        if t<0:
            cv2.rectangle(frame,(round(step*3),60),(w-1,96),BG,-1)
            text(frame,f'CIKIS BIPI  {-t:.1f} s',int(step*3)+18,86,.56,max_width=int(step)-28)
        return frame
    video=Path(meta['output_video'])
    temporary=folder/'teknik/header_refresh.tmp.mp4'
    cap=cv2.VideoCapture(str(video))
    fps=cap.get(cv2.CAP_PROP_FPS)
    size=(int(cap.get(3)),int(cap.get(4)))
    writer=cv2.VideoWriter(str(temporary),cv2.VideoWriter_fourcc(*'mp4v'),fps,size)
    if not writer.isOpened():
        cap.release()
        raise RuntimeError('Baslik videosu yazicisi acilamadi')
    count=0
    try:
        while True:
            ok,frame=cap.read()
            if not ok:
                break
            t=session.get('video_start_time',0)+count/fps-meta['run_zero_seconds']
            writer.write(paint(frame,t))
            count+=1
    finally:
        cap.release()
        writer.release()
    assert count == meta['processed_frames']
    check=cv2.VideoCapture(str(temporary))
    try:
        assert int(check.get(cv2.CAP_PROP_FRAME_COUNT)) == count and check.read()[0]
    finally:
        check.release()
    temporary.replace(video)
    final_image=folder/'son_durum.jpg'
    frame=cv2.imread(str(final_image))
    if frame is not None:
        t=session.get('video_start_time',0)+(count-1)/fps-meta['run_zero_seconds']
        cv2.imencode('.jpg',paint(frame,t))[1].tofile(str(final_image))
    meta['dashboard_version']=2
    meta['header_regenerated']=True
    metadata_path.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
