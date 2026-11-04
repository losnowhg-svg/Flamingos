"""3.17: the integration between screens, on the page (see integration.py for the rules)."""
from __future__ import annotations

import streamlit as st

import integration as ig
from studio_state import sanitize_config, sanitize_match

SKIP = 'season_ledger_skip'


def _ours():
    return sanitize_match(st.session_state.get('shared_match')).get('our_name', 'FLAMINGOS')


def _fulltime():
    from sequence_ui import current_config
    return current_config('Full Time')


def _save():
    try:
        from week_ui import save_week
        save_week()
    except Exception:                      # the browser archive is a convenience: never block on it
        pass


def sync(fulltime=None):
    """Full Time -> season, on its own: a played, filled-in result is recorded (or corrected)."""
    result, _ = ig.fulltime_result(fulltime or _fulltime(), _ours())
    if not result or not ig.worth_recording(result) or (st.session_state.get(SKIP) or {}).get(result['key']):
        return result
    if ig.record(st.session_state, result, _ours()):
        _save()
    return result


def _undo(key):
    ig.unrecord(st.session_state, key)
    st.session_state[SKIP] = dict(st.session_state.get(SKIP) or {}, **{key: True})
    _save()


def _redo(key):
    skip = dict(st.session_state.get(SKIP) or {})
    skip.pop(key, None)
    st.session_state[SKIP] = skip
    result, _ = ig.fulltime_result(_fulltime(), _ours())
    if result and result['key'] == key:
        ig.record(st.session_state, result, _ours())
        _save()


def season_box(config):
    """In the Full Time editor, under the scorers: what went into the season."""
    result = sync(config)
    if not result:
        _, why = ig.fulltime_result(config, _ours())
        st.caption(f'📒 Stagione: questo risultato non è ancora registrato ({why}). Si aggiunge da solo a partita giocata.')
        return
    ledger = (st.session_state.get(ig.LEDGER) or {}).get(result['key'])
    skipped = (st.session_state.get(SKIP) or {}).get(result['key'])
    if ledger and not skipped:
        goals = ', '.join(f'{n} {g}' if g > 1 else n for n, g in ledger['goals'].items()) or 'nessun marcatore'
        a, b = st.columns([3, 1], vertical_alignment='center')
        a.caption(f"📒 **Nella stagione**: {result['us']}-{result['them']} con {result['opp'].title()} · {goals}. "
                  'Wrapped, album e figurine lo contano già; se correggi qui, si corregge anche lì.')
        b.button('Togli', key='season_undo', on_click=_undo, args=(result['key'],), width='stretch',
                 help='Toglie questa partita (e i suoi gol) dalla stagione.')
    elif skipped:
        a, b = st.columns([3, 1], vertical_alignment='center')
        a.caption('📒 Questa partita è stata tolta dalla stagione.')
        b.button('Rimetti', key='season_redo', on_click=_redo, args=(result['key'],), width='stretch')
    else:                                  # 0-0 without scorers: maybe untouched, so it waits for a tap
        a, b = st.columns([3, 1], vertical_alignment='center')
        a.caption(f"📒 {result['us']}-{result['them']} senza marcatori: se è il risultato vero, aggiungilo alla stagione.")
        if b.button('Aggiungi', key='season_add', width='stretch'):
            ig.record(st.session_state, result, _ours())
            _save()
            st.rerun()


# --- Full Time -> Classifica provvisoria -----------------------------------------------------------

def _apply(template, result):
    models = st.session_state.setdefault('studio_models', {})
    config = models[template]
    updated = ig.apply_provisional(config, result, _ours())
    if updated is None:
        return
    count = config['team_count']
    st.session_state['classifica_backup'] = dict(key=result['key'], label=config.get('round_label', ''),
                                                 rows=[dict(r) for r in config['standings'][:count]],
                                                 prev_pos=config.get('prev_pos', 0),
                                                 provisional=[dict(r) for r in updated['standings'][:count]])
    models[template] = sanitize_config(template, updated)
    revisions = st.session_state.setdefault('studio_revisions', {})
    revisions[template] = revisions.get(template, 0)+1
    _save()


def _remove(template):
    models = st.session_state.setdefault('studio_models', {})
    backup = st.session_state.pop('classifica_backup', None) or {}
    config = dict(models[template])
    if backup.get('rows'):
        config['standings'] = backup['rows']+[dict(r) for r in config['standings'][len(backup['rows']):]]
        config['prev_pos'] = backup.get('prev_pos', config.get('prev_pos', 0))
    config['round_label'] = ig.plain_label(backup.get('label') or config.get('round_label'))
    models[template] = sanitize_config(template, config)
    revisions = st.session_state.setdefault('studio_revisions', {})
    revisions[template] = revisions.get(template, 0)+1
    _save()


def provisional_box(template, config):
    """In the Classifica editor: add our Full Time result before the CSI site does."""
    result, _ = ig.fulltime_result(_fulltime(), _ours())
    backup = st.session_state.get('classifica_backup')
    count = config['team_count']
    rows = config['standings'][:count]
    if backup and backup.get('provisional') != [dict(r) for r in rows]:
        # the table changed since (new data from the CSI site, or typed by hand): the provisional one is over
        st.session_state.pop('classifica_backup', None)
        if ig.PROVISIONAL in str(config.get('round_label', '')):
            config['round_label'] = ig.plain_label(config['round_label'])
        backup = None
    if backup:
        a, b = st.columns([3, 1], vertical_alignment='center')
        a.caption('🕒 **Classifica provvisoria**: c\'è già il nostro risultato del Full Time, il resto è quello del sito '
                  'CSI. Quando aggiorni dal CSI torna quella ufficiale.')
        b.button('Togli', key='provisional_off', on_click=_remove, args=(template,), width='stretch')
        return
    if not result or ig.standings_have(rows, result, _ours(), st.session_state.get('csi_matches')):
        return
    if ig.provisional(rows, result, _ours()) is None:
        st.caption(f"Classifica provvisoria: non trovo {result['opp'].title()} o noi in tabella.")
        return
    a, b = st.columns([3, 1], vertical_alignment='center')
    a.caption(f"🕒 Il sito CSI non ha ancora {result['us']}-{result['them']} con {result['opp'].title()}: puoi "
              'pubblicare subito una classifica provvisoria con i nostri punti.')
    b.button('Aggiungi', key='provisional_on', on_click=_apply, args=(template, result), type='primary', width='stretch')


# --- Full Time -> Risultati della giornata ----------------------------------------------------------

def round_matches():
    """The CSI matches with our score from the Full Time where the site does not have it yet."""
    result, _ = ig.fulltime_result(_fulltime(), _ours())
    return ig.with_fulltime(st.session_state.get('csi_matches') or [], result, _ours())
