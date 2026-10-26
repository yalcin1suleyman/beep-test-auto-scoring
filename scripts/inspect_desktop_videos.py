"""Inventory and contact sheets for the user's local shuttle recordings."""
import json
from pathlib import Path
import cv2
import numpy as np

source = Path.home() / 'Desktop' / 'MEKİK VİDEO'
out = Path(__file__).resolve().parents[1] / 'data/outputs/verification'
out.mkdir(parents=True, exist_ok=True)
inventory = []
tiles = []
for i, path in enumerate(sorted(source.rglob('*.mp4')), 1):
    cap = cv2.VideoCapture(str(path))
    fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    inventory.append(dict(index=i, path=str(path), fps=fps, frames=count,
                          width=int(cap.get(3)), height=int(cap.get(4)), duration=count/fps))
    for sec in (0, 8):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec*1000)
        ok, frame = cap.read()
        if ok:
            frame = cv2.resize(frame, (480, 270))
            cv2.putText(frame, f'{i}: {path.parent.name} / {sec}s', (8, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, .65, (0,255,255), 2)
            tiles.append(frame)
    cap.release()
for page in range(2):
    section = tiles[page*14:(page+1)*14]
    sheet = np.vstack([np.hstack(section[j:j+2]) for j in range(0,len(section),2)])
    cv2.imwrite(str(out/f'desktop_contact_{page+1}.jpg'), sheet)
(out/'desktop_inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(inventory,indent=2,ensure_ascii=True))
