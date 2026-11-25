"""3.24: how long every run of the app takes, step by step (only when FLAMINGOS_PERF is set).

FLAMINGOS_PERF=1 -> one line per run in the log: '[perf] Full Time 412ms | avvio=3 condiviso=20 ...'
FLAMINGOS_PERF=2 -> the same plus the 25 slowest functions of runs over 300 ms (cProfile).
Off (the default, Streamlit Cloud): every call returns at once.
"""
from __future__ import annotations

import os
import threading
import time

LEVEL = os.environ.get('FLAMINGOS_PERF', '')
ON = LEVEL in ('1', '2')
_local = threading.local()          # Streamlit runs each session's script in its own thread


def start():
    if not ON:
        return
    _local.t0 = _local.last = time.perf_counter()
    _local.marks = []
    _local.prof = None
    if LEVEL == '2':
        import cProfile
        _local.prof = cProfile.Profile()
        _local.prof.enable()


def mark(name):
    if not ON or not hasattr(_local, 't0'):
        return
    now = time.perf_counter()
    _local.marks.append((name, (now-_local.last)*1000))
    _local.last = now


def stop(page):
    if not ON or not hasattr(_local, 't0'):
        return
    total = (time.perf_counter()-_local.t0)*1000
    steps = ' '.join(f'{name}={ms:.0f}' for name, ms in _local.marks)
    print(f'[perf] {page} {total:.0f}ms | {steps}', flush=True)
    prof = _local.prof
    del _local.t0
    if prof is None:
        return
    prof.disable()
    if total < 300:
        return
    import io
    import pstats
    out = io.StringIO()
    stats = pstats.Stats(prof, stream=out)
    stats.sort_stats('cumulative').print_stats(r'flamingos|Flamingos|/app\.py|/[a-z_]+\.py', 25)
    print('[perf-profile] '+page+'\n'+'\n'.join(out.getvalue().splitlines()[-40:]), flush=True)
