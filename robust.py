"""3.18: a sturdier app. A page error never loses the work; videos and ZIPs never fill the memory.

- guard: if a page breaks (an odd file, an unexpected value), a short message with "Riprova" instead of
  the red Streamlit box, the technical details folded away, and the end of the run (season, shared work)
  still happens, so nothing typed just before is lost. Streamlit's own rerun/stop pass through.
- trim_outputs: every video or ZIP made stays in memory while the session is open. Streamlit Cloud has
  one memory budget for the whole app, so a few friends making videos could crash it for everyone.
  Only the newest ones are kept (a few, within a budget); an older one is made again with one tap.
"""
from __future__ import annotations

import itertools
import traceback

import streamlit as st

KEEP = 3                        # heavy outputs kept per session
BUDGET = 90_000_000             # bytes of heavy outputs per session
HEAVY = 1_000_000               # a value at least this big counts as a heavy output
_counter = itertools.count(1)


def is_control(exc):
    """Streamlit's rerun / stop travel as exceptions: they must pass."""
    names = {c.__name__ for c in type(exc).__mro__}
    return bool(names & {'ScriptControlException', 'RerunException', 'StopException', '_Rerun', '_Stop'})


def page_error(exc, page=''):
    st.session_state['last_error'] = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:]
    with st.container(border=True, key='page_error'):
        st.markdown('#### 😵 Questa pagina si è inceppata')
        st.caption('Il tuo lavoro è salvato: puoi riprovare o andare su un\'altra pagina dal menu. Se succede di nuovo, '
                   'manda a Claude il testo qui sotto.')
        if st.button('↻ Riprova', key='page_retry', type='primary'):
            st.rerun()
        with st.expander('Dettagli tecnici'):
            st.code(f'{page}: {type(exc).__name__}: {exc}\n\n'+st.session_state['last_error'], language=None)


def _size(value):
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    if isinstance(value, dict):
        return sum(len(v) for v in value.values() if isinstance(v, (bytes, bytearray)))
    return 0


def trim_outputs(state=None, keep=KEEP, budget=BUDGET):
    """Forget the oldest videos/ZIPs of this session beyond `keep` or `budget`. Returns the keys dropped."""
    state = st.session_state if state is None else state
    seen = state.setdefault('_heavy_seen', {})          # key -> (identity of the value, when it appeared)
    heavy = {}
    for key in list(state.keys()):
        if str(key).startswith('_'):
            continue
        size = _size(state[key])
        if size >= HEAVY:
            heavy[key] = size
            if seen.get(key, (None,))[0] != id(state[key]):
                seen[key] = (id(state[key]), next(_counter))
    for key in [k for k in seen if k not in heavy]:
        seen.pop(key)
    newest = sorted(heavy, key=lambda k: seen[k][1], reverse=True)
    dropped, total = [], 0
    for i, key in enumerate(newest):
        total += heavy[key]
        if i >= keep or total > budget:
            state.pop(key, None)
            seen.pop(key, None)
            dropped.append(key)
    return dropped
