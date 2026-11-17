"""3.21: the table round by round, rebuilt from the girone's results.

- positions():   our place after every round with results (for the Wrapped trend line).
- previous():    where we were before the latest round: the Classifica graphic shows the move
                 from there to now by itself (prev_pos), no number to type.

The table of each round is computed from the matches (3 points a win, 1 a draw), sorted like the
site (points, goal difference, goals scored); whatever the site counts on top of the results
(penalties, forfeits) is carried over as a fixed correction, so the last round equals the real table.
"""
from __future__ import annotations

STATS = ('pt', 'g', 'v', 'n', 'p', 'gf', 'gs')


def _blank():
    return dict.fromkeys(STATS, 0)


def _add(row, scored, conceded):
    row['g'] += 1
    row['gf'] += scored
    row['gs'] += conceded
    if scored > conceded:
        row['v'] += 1
        row['pt'] += 3
    elif scored == conceded:
        row['n'] += 1
        row['pt'] += 1
    else:
        row['p'] += 1


def _team(name, teams):
    from integration import same_team
    return next((t for t in teams if same_team(t, name)), None)


def table(matches, teams, upto=None, correction=None):
    """{team: stats} after the matches with a score up to round `upto` (all if None), plus the correction."""
    out = {t: _blank() for t in teams}
    for m in matches:
        if m.get('score') is None or (upto is not None and (m.get('round') or 0) > upto):
            continue
        home, away = _team(m['home'], teams), _team(m['away'], teams)
        if not home or not away or home == away:
            continue
        _add(out[home], *m['score'])
        _add(out[away], *m['score'][::-1])
    for team, fix in (correction or {}).items():
        for k in STATS:
            out[team][k] += fix.get(k, 0)
    return out


def order(stats, teams):
    """Teams sorted like the site: points, goal difference, goals scored, then the site's own order."""
    rank = {t: i for i, t in enumerate(teams)}
    return sorted(teams, key=lambda t: (-stats[t]['pt'], -(stats[t]['gf']-stats[t]['gs']), -stats[t]['gf'], rank[t]))


def rounds_played(matches):
    return sorted({m['round'] for m in matches if m.get('score') is not None and m.get('round')})


def positions(matches, rows, ours='FLAMINGOS'):
    """[{'round', 'pos', 'pt'}] for every round with results; rows: the real table now (site + pending)."""
    teams = [r['team'] for r in rows if str(r.get('team', '')).strip()]
    me = _team(ours, teams)
    if not me:
        return []
    computed = table(matches, teams)
    correction = {t: {k: int(r.get(k) or 0)-computed[t][k] for k in STATS}
                  for t, r in zip(teams, [r for r in rows if str(r.get('team', '')).strip()])}
    correction = {t: fix for t, fix in correction.items() if any(fix.values())}
    if any(fix[k] for fix in correction.values() for k in STATS if k != 'pt'):
        return []                                        # results missing from the list: no reliable history
    out = []
    for rnd in rounds_played(matches):
        stats = table(matches, teams, rnd, correction)
        out.append(dict(round=rnd, pos=order(stats, teams).index(me)+1, pt=stats[me]['pt']))
    return out


def previous(history):
    """Our place before the latest round with results (None for the first round)."""
    return history[-2]['pos'] if len(history) >= 2 else None
