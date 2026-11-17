"""3.21: the opponent at a glance for the Matchday graphic, from the girone's results.

encode() -> 'VPNVV|8|3-3|N': their last five results (oldest first, from their side), their place in
the table, our first-leg result (our goals first) and its outcome for us. decode() reads it back.
Stored as a short text in the Matchday editor, so it travels with the project like any other field.
"""
from __future__ import annotations

import datetime as dt


def _outcome(scored, conceded):
    return 'V' if scored > conceded else 'N' if scored == conceded else 'P'


def form(matches, rows, opponent, ours='FLAMINGOS', before=None):
    """dict(last=['V', 'P', ...], pos=8 or 0, first_leg='3-3' or '', first_leg_outcome='N' or '')."""
    from integration import parse_date, same_team
    before = parse_date(before) if before else None
    played = [m for m in matches or [] if m.get('score') is not None
              and (before is None or (parse_date(m.get('date')) or dt.date.max) < before)]
    played.sort(key=lambda m: (parse_date(m.get('date')) or dt.date.min, m.get('time', '')))
    theirs = [m for m in played if same_team(m['home'], opponent) or same_team(m['away'], opponent)]
    last = []
    for m in theirs[-5:]:
        home = same_team(m['home'], opponent)
        a, b = m['score']
        last.append(_outcome(a, b) if home else _outcome(b, a))
    pos = next((int(r.get('pos') or i+1) for i, r in enumerate(rows or []) if same_team(r.get('team'), opponent)), 0)
    first_leg, outcome = '', ''
    ours_vs = [m for m in theirs if same_team(m['home'], ours) or same_team(m['away'], ours)]
    if ours_vs:
        m = ours_vs[-1]
        us, them = m['score'] if same_team(m['home'], ours) else m['score'][::-1]
        first_leg, outcome = f'{us}-{them}', _outcome(us, them)
    return dict(last=last, pos=pos, first_leg=first_leg, first_leg_outcome=outcome)


def encode(data):
    if not data or not (data.get('last') or data.get('pos')):
        return ''
    return '|'.join([''.join(data.get('last') or []), str(data.get('pos') or 0), data.get('first_leg') or '',
                     data.get('first_leg_outcome') or ''])


def decode(text):
    parts = str(text or '').split('|')
    if len(parts) != 4:
        return None
    last = [c for c in parts[0] if c in 'VNP'][:5]
    try:
        pos = max(0, min(99, int(parts[1])))
    except ValueError:
        pos = 0
    first_leg = parts[2] if len(parts[2]) <= 7 else ''
    if not last and not pos:
        return None
    return dict(last=last, pos=pos, first_leg=first_leg, first_leg_outcome=parts[3] if parts[3] in ('V', 'N', 'P') else '')
