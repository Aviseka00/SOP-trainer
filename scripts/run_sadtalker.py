"""Run the unmodified upstream CLI in its isolated interpreter and record device metrics."""
import json
import os
import runpy
import sys
import time
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'external'/'SadTalker'))
torch.set_num_threads(2)
use_cuda = torch.cuda.is_available() and '--cpu' not in sys.argv
if use_cuda:
    torch.cuda.reset_peak_memory_stats()
started = time.monotonic()
successful = False
try:
    sys.argv[0] = str(ROOT/'external'/'SadTalker'/'inference.py')
    runpy.run_path(sys.argv[0], run_name='__main__')
    successful = True
finally:
    stats = {'device':'cuda' if use_cuda else 'cpu', 'torch':torch.__version__,
             'elapsed_seconds':round(time.monotonic()-started,2), 'success':successful,
             'peak_allocated_mb':round(torch.cuda.max_memory_allocated()/1024**2,2) if use_cuda else None}
    path = os.environ.get('SOP_AVATAR_STATS_PATH')
    if path:
        Path(path).write_text(json.dumps(stats, indent=2), encoding='utf-8')
    print(json.dumps(stats), flush=True)
