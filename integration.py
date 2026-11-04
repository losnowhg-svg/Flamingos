"""3.17, integrazione tra schermate: what one screen knows, the others use (no typing things twice).

- Full Time -> stagione: a played result (and our scorers) goes into the season games and scorers
  (Wrapped, album, figurine) by itself. One ledger entry per match: correcting the Full Time
  corrects the season by the difference, the same match never counts twice, and it can be undone.
- Full Time -> Risultati della giornata: our score when the CSI site does not have it yet.
- Full Time -> Classifica provvisoria: our result added to our row and the opponent's, on request.

Pure functions on plain dicts (the session state is a dict too), so everything here is tested
without Streamlit.
"""
from __future__ import annotations

import datetime as dt
import re

LEDGER = 'season_ledger'                 # {match key: {'goals': {NAME: n}, 'game': {...}, 'added_game': bool}}


# --- Names and dates --------------------------------------------------------------------------------

def norm(name):
    """'A.S.D. United Flero 2002' -> 'UNITEDFLERO2002': letters and digits only, for comparing team names."""
    text = re.sub(r'\b(A\.?S\.?D\.?|S\.?S\.?D\.?|U\.?S\.?|G\.?S\.?|A\.?C\.?|F\.?C\.?|POL\.?)\b', ' ', str(name or '').upper())
    return re.sub(r'[^A-Z0-9]', '', text)


def same_team(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or a in b or b in a)


def parse_date(text):
    if isinstance(text, dt.date):
        return text
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
        try:
            return dt.datetime.strptime(str(text or '').strip(), fmt).date()
        except ValueError:
            pass
    return None


# --- 1. Full Time -> season ---------------------------------------------------------------------------

def fulltime_result(fulltime, ours='FLAMINGOS', today=None):
    """Our played match in the Full Time editor, or (None, why not).

    {'key', 'date', 'opp', 'home', 'us', 'them', 'goals': {NAME: n}} when the date is real and not in
    the future and the opponent is a real name."""
    today = today or dt.date.today()
    date = parse_date(fulltime.get('date'))
    if not date:
        return None, 'manca la data della partita'
    if date > today:
        return None, 'la partita non è ancora stata giocata'
    home = fulltime.get('our_side', 'Casa') == 'Casa'
    opp = str(fulltime.get('away_name' if home else 'home_name') or '').strip().upper()
    if not opp or opp == 'AVVERSARI' or same_team(opp, ours):
        return None, 'manca il nome degli avversari'
    a, b = int(fulltime.get('home_score') or 0), int(fulltime.get('away_score') or 0)
    from figurine_data import goals_by_player
    return dict(key=f'{date.isoformat()}|{norm(opp)}', date=date, opp=opp, home=home,
                us=a if home else b, them=b if home else a, goals=goals_by_player(fulltime)), ''


def worth_recording(result):
    """A 0-0 without scorers looks like an untouched editor: that one waits for a tap."""
    return bool(result) and (result['us'] or result['them'] or result['goals'])


def _game(result):
    return dict(date=result['date'], opp=result['opp'], home=result['home'], us=result['us'], them=result['them'],
                round=None, source='fulltime')


def _add_goals(scorers, goals, sign):
    totals = {str(s['name']).upper(): int(s.get('goals') or 0) for s in scorers or []}
    order = [str(s['name']).upper() for s in scorers or []]
    for name, count in goals.items():
        if name not in totals:
            totals[name] = 0
            order.append(name)
        totals[name] = max(0, totals[name]+sign*int(count))
    return [dict(name=name, goals=totals[name]) for name in order if totals[name]]


def _csi_has(state, result, ours):
    """The CSI calendar already has this match with a score (then it is the source of the result)."""
    from season_stats import our_games
    return any(g['date'] == result['date'] and same_team(g['opp'], result['opp'])
               for g in our_games(state.get('csi_matches') or [], ours))


def record(state, result, ours='FLAMINGOS'):
    """Put a played Full Time result into the season. Returns True if something changed.

    Goals go into season_scorers by the difference with what this match had already given,
    the game into season_games unless the CSI calendar already has it."""
    ledger = dict(state.get(LEDGER) or {})
    before = ledger.get(result['key'])
    old_goals = (before or {}).get('goals') or {}
    if before and before['goals'] == result['goals'] and before['game'] == _game(result):
        return False
    scorers = _add_goals(state.get('season_scorers') or [], old_goals, -1)
    state['season_scorers'] = _add_goals(scorers, result['goals'], +1)
    games = [g for g in state.get('season_games') or []
             if not (g.get('date') == result['date'] and same_team(g.get('opp'), result['opp']))]
    added = not _csi_has(state, result, ours)
    if added:
        games.append(_game(result))
    elif before and before.get('added_game'):
        pass                                             # the CSI has it now: our copy is not needed any more
    state['season_games'] = sorted(games, key=lambda g: g['date'])
    ledger[result['key']] = dict(goals=dict(result['goals']), game=_game(result), added_game=added)
    state[LEDGER] = ledger
    return True


def unrecord(state, key):
    """Take a match back out of the season (its goals, and its game if we had added it)."""
    ledger = dict(state.get(LEDGER) or {})
    entry = ledger.pop(key, None)
    if not entry:
        return False
    state['season_scorers'] = _add_goals(state.get('season_scorers') or [], entry['goals'], -1)
    if entry.get('added_game'):
        game = entry['game']
        state['season_games'] = [g for g in state.get('season_games') or []
                                 if not (g.get('date') == game['date'] and same_team(g.get('opp'), game['opp']))]
    state[LEDGER] = ledger
    return True


def merge_games(csi_games, typed):
    """Season games: the CSI ones plus the typed/recorded ones, the same match (same day, same opponent
    even if spelled differently) only once; a typed game wins over the CSI one."""
    out = [dict(g) for g in csi_games]
    for game in typed or []:
        out = [g for g in out if not (g['date'] == game['date'] and same_team(g['opp'], game['opp']))]
        out.append(dict(game))
    return sorted(out, key=lambda g: g['date'])


# --- 2. Full Time -> Risultati della giornata -------------------------------------------------------

def with_fulltime(matches, result, ours='FLAMINGOS'):
    """(matches, filled): a copy of the CSI matches where our game without a score takes the Full Time one."""
    if not result:
        return list(matches or []), False
    out, filled = [], False
    from csi_page import is_ours
    for m in matches or []:
        m = dict(m)
        date = parse_date(m.get('date'))
        if not filled and m.get('score') is None and date == result['date']:
            home_ours, away_ours = is_ours(m.get('home', ''), ours), is_ours(m.get('away', ''), ours)
            other = m.get('away') if home_ours else m.get('home')
            if (home_ours or away_ours) and same_team(other, result['opp']):
                m['score'] = (result['us'], result['them']) if home_ours else (result['them'], result['us'])
                m['from_fulltime'] = True
                filled = True
        out.append(m)
    return out, filled


# --- 3. Full Time -> Classifica provvisoria --------------------------------------------------------

def _row_index(rows, team):
    return next((i for i, r in enumerate(rows) if same_team(r.get('team'), team)), None)


def provisional(rows, result, ours='FLAMINGOS'):
    """The standings with our result added to our row and the opponent's (points, games, W/D/L, goals),
    sorted again. None if our team or the opponent is not in the table."""
    rows = [dict(r) for r in rows]
    mine, theirs = _row_index(rows, ours), _row_index(rows, result['opp'])
    if mine is None or theirs is None or mine == theirs:
        return None
    for index, scored, conceded in ((mine, result['us'], result['them']), (theirs, result['them'], result['us'])):
        row = rows[index]
        row['g'] = int(row.get('g') or 0)+1
        row['gf'] = int(row.get('gf') or 0)+scored
        row['gs'] = int(row.get('gs') or 0)+conceded
        if scored > conceded:
            row['v'], row['pt'] = int(row.get('v') or 0)+1, int(row.get('pt') or 0)+3
        elif scored == conceded:
            row['n'], row['pt'] = int(row.get('n') or 0)+1, int(row.get('pt') or 0)+1
        else:
            row['p'] = int(row.get('p') or 0)+1
    from classifica_data import sort_rows
    return sort_rows(rows)


def standings_have(rows, result, ours, matches):
    """The CSI table already counts this match: our games played equal our scored CSI matches up to that day."""
    from season_stats import our_games
    mine = _row_index(rows, ours)
    if mine is None:
        return False
    played = len([g for g in our_games(matches or [], ours) if g['date'] <= result['date']])
    has_it = any(g['date'] == result['date'] and same_team(g['opp'], result['opp']) for g in our_games(matches or [], ours))
    return has_it and int(rows[mine].get('g') or 0) >= played


PROVISIONAL = ' · PROVVISORIA'


def provisional_label(label):
    label = str(label or '').replace(PROVISIONAL, '').strip()
    return (label+PROVISIONAL)[:36] if label else 'PROVVISORIA'


def plain_label(label):
    return str(label or '').replace(PROVISIONAL, '').strip() or str(label or '')


def apply_provisional(config, result, ours='FLAMINGOS'):
    """A Classifica config with the provisional table (and its label), or None if it cannot be done."""
    count = int(config.get('team_count') or 0)
    rows = provisional(config.get('standings', [])[:count], result, ours)
    if rows is None:
        return None
    from classifica_data import with_rows
    updated = with_rows(config, rows)                 # remembers where we were: the video shows the climb
    updated['round_label'] = provisional_label(config.get('round_label'))
    return updated
