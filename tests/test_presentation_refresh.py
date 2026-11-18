import json
import hashlib
import cv2
import numpy as np
from scripts.refresh_video_headers import refresh


def test_header_refresh_preserves_frames_and_scoring_data(tmp_path):
    (tmp_path/'teknik').mkdir()
    video=tmp_path/'analiz_videosu.mp4'
    frame=np.full((400,900,3),50,np.uint8)
    frame[150:350,50:850]=(20,170,50)
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),2,(900,400))
    for _ in range(3):
        writer.write(frame)
    writer.release()
    cv2.imwrite(str(tmp_path/'son_durum.jpg'),frame)
    meta={'processed_frames':3,'run_zero_seconds':0.,'output_video':str(video),'scoring_eligible':True}
    (tmp_path/'teknik/run_metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    scores=tmp_path/'sonuc_ozet.csv'
    scores.write_text('Kosucu,Sonuc\n1,Ornek\n',encoding='utf-8')
    before=hashlib.sha256(scores.read_bytes()).hexdigest()
    refresh(tmp_path,{'video_start_time':0.},[.5,1.5,2.5])
    assert hashlib.sha256(scores.read_bytes()).hexdigest()==before
    updated=json.loads((tmp_path/'teknik/run_metadata.json').read_text(encoding='utf-8'))
    assert updated['dashboard_version']==2 and updated['processed_frames']==3
    capture=cv2.VideoCapture(str(video))
    try:
        assert capture.get(cv2.CAP_PROP_FRAME_COUNT)==3
        ok,observed=capture.read()
        assert ok
        assert np.mean(np.abs(observed[170:330,70:830].astype(float)-frame[170:330,70:830]))<8
    finally:
        capture.release()
    digest=hashlib.sha256(video.read_bytes()).hexdigest()
    refresh(tmp_path,{'video_start_time':0.},[.5,1.5,2.5])
    assert hashlib.sha256(video.read_bytes()).hexdigest()==digest


def test_unscored_recording_with_empty_events_can_be_verified(tmp_path):
    from dual_camera_analyser import DualLineEvaluator
    from result_report import write_readable_outputs
    from scripts.verify_analysis_output import verify
    ev=DualLineEvaluator(30,20,[])
    ev.update_camera_line(1,10,10,0,'start')
    ev.export_results(tmp_path)
    frame=np.zeros((100,200,3),np.uint8)
    video=tmp_path/'analiz_videosu.mp4'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),2,(200,100))
    for _ in range(2):
        writer.write(frame)
    writer.release()
    meta={'processed_frames':2,'analyzed_frames':2,'approximate':False,
          'completion_reason':'video_end','runner_count':1,'scoring_eligible':False,
          'output_video':str(video)}
    (tmp_path/'teknik/run_metadata.json').write_text(json.dumps(meta),encoding='utf-8')
    write_readable_outputs(tmp_path,ev,meta,frame)
    result=verify(tmp_path)
    assert result['ok'] and result['detail_rows']==0
