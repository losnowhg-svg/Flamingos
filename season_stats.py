"""Season numbers for Flamingos Wrapped, from the CSI calendar."""
from __future__ import annotations

import datetime as dt

PERIODS = {'stagione': 'Tutta la stagione', 'andata': "Girone d'andata", 'mese': 'Un mese'}
MONTHS = ('GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO', 'AGOSTO',
          'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE')


def _ours(team, ours):
    from csi_page import is_ours
    return is_ours(team, ours)


def our_games(matches, ours):
    """Played games from our side: [{date, opp, home, us, them, round}] oldest first."""
    games = []
    for m in matches or []:
        if not m.get('score'):
            continue
        home = _ours(m['home'], ours)
        if not home and not _ours(m['away'], ours):
            continue
        a, b = m['score']
        games.append(dict(date=m['date'], opp=m['away'] if home else m['home'], home=home,
                          us=a if home else b, them=b if home else a, round=m.get('round')))
    games.sort(key=lambda g: g['date'])
    return games


def months_with_games(matches, ours):
    return sorted({(g['date'].year, g['date'].month) for g in our_games(matches, ours)})


def select(games, period='stagione', month=None, all_matches=None, ours='FLAMINGOS'):
    if period == 'mese' and month:
        return [g for g in games if (g['date'].year, g['date'].month) == tuple(month)]
    if period == 'andata':
        total_rounds = max([m.get('round') or 0 for m in all_matches or []] or [0])
        ours_total = len([m for m in all_matches or [] if _ours(m['home'], ours) or _ours(m['away'], ours)])
        half = (ours_total+1)//2 if ours_total else len(games)
        if total_rounds and all(g.get('round') for g in games):
            return [g for g in games if g['round'] <= (total_rounds+1)//2]
        return games[:half]
    return list(games)


def period_label(period, month=None, games=None):
    if period == 'mese' and month:
        return f'{MONTHS[month[1]-1]} {month[0]}'
    if period == 'andata':
        return "GIRONE D'ANDATA"
    if games:
        a, b = games[0]['date'], games[-1]['date']
        start = a.year if a.month >= 8 else a.year-1
        return f'STAGIONE {start}/{str(start+1)[-2:]}'
    return 'STAGIONE'


def _streak(games, test):
    best = run = 0
    for g in games:
        run = run+1 if test(g) else 0
        best = max(best, run)
    return best


def stats(games):
    """All the Wrapped numbers for a list of our games. Empty dict when no games."""
    if not games:
        return {}
    w = sum(g['us'] > g['them'] for g in games)
    d = sum(g['us'] == g['them'] for g in games)
    l = len(games)-w-d
    gf, ga = sum(g['us'] for g in games), sum(g['them'] for g in games)
    wins = [g for g in games if g['us'] > g['them']]
    best = max(wins, key=lambda g: (g['us']-g['them'], g['us'])) if wins else None
    most = max(games, key=lambda g: g['us'])

    def record(side):
        gs = [g for g in games if g['home'] == side]
        return dict(played=len(gs), w=sum(g['us'] > g['them'] for g in gs), d=sum(g['us'] == g['them'] for g in gs),
                    l=sum(g['us'] < g['them'] for g in gs), gf=sum(g['us'] for g in gs), ga=sum(g['them'] for g in gs))
    return dict(played=len(games), w=w, d=d, l=l, points=3*w+d, gf=gf, ga=ga, gd=gf-ga,
                avg=round(gf/len(games), 1), avg_against=round(ga/len(games), 1),
                clean=sum(g['them'] == 0 for g in games),
                best=best, most=most, win_streak=_streak(games, lambda g: g['us'] > g['them']),
                unbeaten=_streak(games, lambda g: g['us'] >= g['them']),
                home=record(True), away=record(False), first=games[0]['date'], last=games[-1]['date'])
