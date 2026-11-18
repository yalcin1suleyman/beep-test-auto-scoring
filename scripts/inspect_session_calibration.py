"""Show configured lines on each camera's actual calibration reference frame."""
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_sessions import load_sessions,session_paths,parse_line
from line_geometry import PerspectiveLine


def main():
    data,sessions = load_sessions()
    out = ROOT/'data/outputs/hazirlik_2026-11-18/kalibrasyon'
    out.mkdir(parents=True,exist_ok=True)
    for session in sessions:
        panels = []
        for i,path in enumerate(session_paths(data,session)):
            t = session.get('video_start_time',0)+(session['cam2_offset'] if i else 0)
            cap = cv2.VideoCapture(str(path))
            try:
                cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
                ok,frame=cap.read()
                assert ok
            finally:
                cap.release()
            key='far_line' if i else 'start_line'
            line=PerspectiveLine.from_points(parse_line(session[key]))
            line.draw(frame,(0,255,180),3)
            for x,y in line.points:
                cv2.circle(frame,(round(x),round(y)),6,(0,255,180),-1)
            frame=cv2.resize(frame,(480,round(frame.shape[0]*480/frame.shape[1])))
            header=np.full((65,480,3),(28,21,15),np.uint8)
            cv2.putText(header,f"{session['name']} - {'20m' if i else '0m'}",(10,25),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
            cv2.putText(header,f"Referans: {t:.2f}s / {session['runner_count']} kosucu",(10,50),cv2.FONT_HERSHEY_SIMPLEX,.45,(180,220,200),1)
            panels.append(np.vstack([header,frame]))
        height=max(p.shape[0] for p in panels)
        panels=[np.pad(p,((0,height-p.shape[0]),(0,0),(0,0))) for p in panels]
        cv2.imencode('.jpg',np.hstack(panels))[1].tofile(str(out/f"video_{session['id']}.jpg"))


if __name__ == '__main__':
    main()
