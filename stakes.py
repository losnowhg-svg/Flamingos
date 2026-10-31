"""What is at stake (3.5): the standings brought into the Matchday.

The Matchday knows only the two names; the Classifica editor knows positions and
points. attach() looks both teams up in the standings and stores them on the
Matchday config (recomputed every time, never saved), so the video can show
"3° · 17 PT" for each side and the gap between them.
"""
from __future__ import annotations


def _same(a, b):
    import crests
    import re
    ka, kb = crests.key(a), crests.key(b)
    if len(ka) < 3 or len(kb) < 3:      # names made only of common words: compare them as written
        plain = lambda v: re.sub(r'[^A-Z0-9]', '', str(v).upper())
        return bool(plain(a)) and plain(a) == plain(b)
    slug_a, slug_b = crests.match(a), crests.match(b)
    if slug_a and slug_b:
        return slug_a == slug_b
    shorter, longer = sorted((ka, kb), key=len)
    return shorter in longer and len(shorter) >= .6*len(longer)


def lookup(classifica, home_name, away_name, our_side='Casa'):
    """{'home': {'pos', 'pt'}, 'away': {...}} or None when a team is not in the table."""
    from classifica_renderer import active_rows, is_ours
    rows = active_rows(classifica)
    if not rows:
        return None
    ours = classifica.get('our_team', 'FLAMINGOS')
    us = next((r for r in rows if is_ours(r.get('team', ''), ours)), None)
    opponent = away_name if our_side != 'Ospiti' else home_name
    them = next((r for r in rows if not is_ours(r.get('team', ''), ours) and _same(r.get('team', ''), opponent)), None)
    if us is None or them is None:
        return None

    def card(row):
        return {'pos': int(row.get('pos', 0) or 0), 'pt': int(row.get('pt', 0) or 0)}
    home, away = (card(us), card(them)) if our_side != 'Ospiti' else (card(them), card(us))
    return {'home': home, 'away': away}


def attach(template, config, models):
    """Put the standings of both teams on a Matchday config (in place); other templates untouched."""
    if template != 'Matchday Screen' or not isinstance(config, dict):
        return config
    config.pop('stakes', None)
    classifica = (models or {}).get('Classifica')
    if not classifica:
        return config
    found = lookup(classifica, config.get('home_name', ''), config.get('away_name', ''), config.get('our_side', 'Casa'))
    if found:
        config['stakes'] = found
    return config
