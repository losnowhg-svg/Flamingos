"""3.20: when the app takes the girone from the CSI site by itself, what it changes and what it leaves alone.

Pure functions on plain dicts (tested without Streamlit):
- due():          the last try is older than an hour (or there was none): time to download again.
- match_step():   our next match on the site vs the "Partita della settimana" in the app:
                  apply it, update only what the site changed, hold it (the match just played keeps
                  the graphics for two days, for the Full Time), or keep everything as it is.
- fulltime_score(): the played result on the site goes into the Full Time editor, unless a friend
                  typed a different score by hand.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

STALE = dt.timedelta(hours=1)
HOLD_DAYS = 2                           # days after our match when the app does not move on by itself
FIELDS = ('opponent', 'our_side', 'date', 'kickoff', 'meeting_time', 'venue', 'round')


def signature(value):
    return hashlib.sha1(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def due(sync, now, stale=STALE):
    """True if the girone was never downloaded, or the last try (good or not) is older than `stale`."""
    try:
        last = dt.datetime.fromisoformat(str((sync or {}).get('tried_at')))
    except ValueError:
        return True
    if last.tzinfo is None and now.tzinfo is not None:
        last = last.replace(tzinfo=now.tzinfo)
    return now-last >= stale


def parse_date(text):
    from integration import parse_date as _parse
    return _parse(text)


def _same_match(a, b):
    from integration import same_team
    return bool(a and b) and same_team(a.get('opponent'), b.get('opponent')) and \
        parse_date(a.get('date')) == parse_date(b.get('date'))


def held_until(match, hold_days=HOLD_DAYS):
    date = parse_date((match or {}).get('date'))
    return date+dt.timedelta(days=hold_days) if date else None


def match_step(current, fields, last, today, hold_days=HOLD_DAYS):
    """('apply' | 'update' | 'hold' | 'keep', fields to write).

    current: the shared match in the app; fields: our next match on the site (csi_page.match_fields);
    last: the fields the site gave the previous time (what a friend may have corrected since)."""
    if not fields:
        return 'keep', {}
    if _same_match(current, fields):
        # the same match: only what the site changed since last time (a friend's correction stays)
        if last and _same_match(last, fields):
            keys = [k for k in FIELDS if k in fields and last.get(k) != fields[k]]
        else:                                            # first time from the site: only the hard facts
            keys = [k for k in ('kickoff', 'round', 'our_side') if k in fields]
        changed = {k: fields[k] for k in keys if current.get(k) != fields[k]}
        return ('update', changed) if changed else ('keep', {})
    if last and _same_match(last, fields):
        return 'keep', {}                                # the site has not moved on: a friend chose another match
    date = parse_date(current.get('date'))
    real =str(current.get('opponent') or '').strip().upper() not in ('', 'AVVERSARI')
    if real and date and date <= today <= date+dt.timedelta(days=hold_days):
        return 'hold', dict(fields)
    return 'apply', dict(fields)


def _our_scores(match, ours):
    from csi_page import is_ours
    a, b = match['score']
    return (a, b) if is_ours(match['home'], ours) else (b, a)


def fulltime_score(fulltime, matches, ours='FLAMINGOS', last=None):
    """(home_score, away_score) to write into the Full Time editor, or None.

    Only when the editor shows a match the site has a score for, and its score is still 0-0 or the
    one the site gave last time (`last`): a score typed by hand is never covered."""
    from csi_page import is_ours
    from integration import same_team
    home = fulltime.get('our_side', 'Casa') == 'Casa'
    opp = str(fulltime.get('away_name' if home else 'home_name') or '')
    date = parse_date(fulltime.get('date'))
    if not date or not opp.strip():
        return None
    for m in matches or []:
        if m.get('score') is None or parse_date(m.get('date')) != date:
            continue
        if not (is_ours(m['home'], ours) or is_ours(m['away'], ours)):
            continue
        other = m['away'] if is_ours(m['home'], ours) else m['home']
        if not same_team(other, opp):
            continue
        us, them = _our_scores(m, ours)
        wanted = (us, them) if home else (them, us)
        now = (int(fulltime.get('home_score') or 0), int(fulltime.get('away_score') or 0))
        if now == wanted:
            return None
        if now == (0, 0) or (last and tuple(last) == now):
            return wanted
        return None
    return None
