"""Small helpers shared by the Streamlit pages."""
from __future__ import annotations


def progress_with_eta(bar, label='Rendering'):
    """Progress callback that also shows the seconds left."""
    import time
    start = time.time()

    def update(fraction):
        elapsed = time.time()-start
        left = elapsed/fraction-elapsed if fraction > .04 else None
        text = f'{label}: {round(fraction*100)}%'+(f' · circa {max(1, round(left))} s' if left is not None and fraction < 1 else '')
        bar.progress(min(1.0, fraction), text=text)
    return update


SLUGS = {'Starting 7': 'starting7', 'Matchday Screen': 'matchday', 'Full Time': 'fulltime', 'Convocati': 'convocati',
         'Classifica': 'classifica', 'Calendario': 'calendario'}


def file_stem(template, config):
    """flamingos_matchday_vs-united-flero_29-10: easy to find among the downloads."""
    import re
    parts = ['flamingos', SLUGS.get(template, 'grafica')]
    if template in ('Matchday Screen', 'Full Time'):
        ours = config.get('our_side', 'Casa') == 'Casa'
        rival = config.get('away_name' if ours else 'home_name', '')
    else:
        rival = config.get('opponent', '') if template == 'Convocati' else ''
    if rival and 'AVVERSARI' not in rival.upper():
        parts.append('vs-'+rival)
    date = str(config.get('date', ''))
    m = re.match(r'(\d{1,2})[/.-](\d{1,2})', date)
    if m:
        parts.append(f'{int(m.group(1)):02d}-{int(m.group(2)):02d}')
    elif template == 'Calendario' and config.get('month_label'):
        parts.append(config['month_label'])
    elif template == 'Classifica' and config.get('round_label'):
        parts.append(config['round_label'])
    stem = '_'.join(parts).lower()
    return re.sub(r'[^a-z0-9_-]+', '-', stem).strip('-')[:80]


DAYS = ('lunedi', 'martedi', 'mercoledi', 'giovedi', 'venerdi', 'sabato', 'domenica')


def countdown(match, today=None):
    """One line about the next match, or None when the date is not set."""
    import themes
    when = themes.parse_date(match.get('date'))
    if not when:
        return None
    import datetime as dt
    today = today or dt.date.today()
    days = (when-today).days
    rival = match.get('opponent', '')
    clock = match.get('kickoff', '')
    at = f' alle {clock}' if clock and clock != 'HH:MM' else ''
    if days > 1:
        return f'⚽ Mancano {days} giorni: vs {rival}, {DAYS[when.weekday()]} {when.day}/{when.month}{at}. Pubblica Matchday e Convocati.'
    if days == 1:
        return f'⚽ Domani si gioca: vs {rival}{at}. Ultimo giro di Convocati!'
    if days == 0:
        return f'🔥 Oggi si gioca: vs {rival}{at}. In bocca al lupo!'
    if days >= -3:
        return f'📣 Partita giocata contro {rival}: inserisci il risultato nel Full Time e aggiorna la classifica.'
    return None


def auto_table(name, rows, save, rows_after=None, clean=None, **editor_kw):
    """3.18: a table that saves by itself (no "Salva" button to forget). Returns (records, saved_now).

    rows: the table as the stored data looks now; save(records) stores an edit, called only when the
    cleaned records really change; rows_after(): the table as it will look from the stored data after a
    save (by default: the records themselves). The editor keeps its own starting rows and starts again
    only when the data changes from outside (a friend's work, the official squad...): reloading it from
    what was just saved would apply the edits a second time (rows added twice)."""
    import hashlib
    import json
    import streamlit as st

    def fp(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

    clean = clean or (lambda value: value)
    table = st.session_state.setdefault('_tables', {}).setdefault(name, {'ver': 0})
    now = fp(rows)
    if table.get('base') is None or now not in (table.get('base_fp'), table.get('own_fp')):
        table.update(base=[dict(r) for r in rows], base_fp=now, own_fp=None, ver=table['ver']+1)
        table['last'] = fp(clean(table['base']))
    edited = st.data_editor(table['base'], key=f"{name}_{table['ver']}", **editor_kw)
    records = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
    mark = fp(clean(records))
    if mark == table['last']:
        return records, False
    save(records)
    table['last'] = mark
    table['own_fp'] = fp(rows_after() if rows_after else records)
    return records, True
