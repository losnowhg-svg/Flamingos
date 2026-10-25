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
