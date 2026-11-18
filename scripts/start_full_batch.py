"""Start a fresh full-frame batch and record its source-code fingerprint."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.prepare_release import REVIEW_DIR, analysis_code_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mark-only',action='store_true',help='Mark an already running batch; do not start another process')
    parser.add_argument('--started-utc',help='Actual start timestamp of an existing batch')
    args=parser.parse_args()
    stamp=args.started_utc or datetime.now(timezone.utc).isoformat()
    parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        parser.error('Timestamp must include UTC offset')
    REVIEW_DIR.mkdir(parents=True,exist_ok=True)
    (REVIEW_DIR/'batch_started.json').write_text(json.dumps({
        'started_utc':parsed.isoformat(), 'analysis_code_sha256':analysis_code_hash()},indent=2),encoding='utf-8')
    if not args.mark_only:
        return subprocess.call([sys.executable,str(ROOT/'run_sessions.py'),'--all','--no-display'],cwd=ROOT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
