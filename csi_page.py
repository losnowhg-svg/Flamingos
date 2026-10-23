"""Read a whole girone page sent by the "Invia a Flamingos" bookmark.

The bookmark (v2) sends {u: page url, t: standings table as TSV, x: page text}
as gzip + base64url in the app address. Everything is parsed here, in Python,
so the reading can improve without anyone reinstalling the bookmark.

Matches are found by looking for two known team names (taken from the
standings) close to a date; the team cards ("Colori", "Giorno e Ora", address)
give each team's usual home ground and kick-off time.
"""
from __future__ import annotations

import base64
import datetime as dt
import gzip
import json
import re

from classifica_data import parse_standings

MAX_PAYLOAD = 400_000
DATE = re.compile(r'\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b')
TIME = re.compile(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)\b')
SCORE = re.compile(r'^\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*$')
ROUND = re.compile(r'\b(?:giornata|g\.)\s*(\d{1,2})\b|\b(\d{1,2})\s*[°ªa]?\s*giornata\b', re.I)
WEEKDAYS = ('LUNEDI', 'MARTEDI', 'MERCOLEDI', 'GIOVEDI', 'VENERDI', 'SABATO', 'DOMENICA')
MONTHS = ('GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO', 'AGOSTO',
          'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE')


def decode_payload(value):
    """'z' + base64url(gzip(json)) from bookmark v2; plain TSV from bookmark v1."""
    value = str(value or '')
    if not value.startswith('z'):
        return {'t': value, 'x': '', 'u': ''}
    raw = value[1:]
    raw += '='*(-len(raw) % 4)
    try:
        data = gzip.decompress(base64.urlsafe_b64decode(raw))
    except (ValueError, OSError, EOFError) as exc:
        raise ValueError('Dati del segnalibro illeggibili: reinstalla il segnalibro dall\'app.') from exc
    if len(data) > MAX_PAYLOAD:
        raise ValueError('La pagina inviata e troppo grande.')
    payload = json.loads(data.decode('utf-8', errors='replace'))
    if not isinstance(payload, dict):
        raise ValueError('Dati del segnalibro non validi.')
    return {k: str(payload.get(k, ''))[:MAX_PAYLOAD] for k in ('u', 't', 'x')}


def _norm(value):
    value = str(value).upper().replace('À', 'A').replace('È', 'E').replace('É', 'E').replace('Ì', 'I').replace('Ò', 'O').replace('Ù', 'U')
    return re.sub(r'[^A-Z0-9]+', ' ', value).strip()


def _lines(text):
    return [re.sub(r'\s+', ' ', line).strip() for line in str(text).splitlines() if line.strip()]


class Teams:
    """Find known team names inside free text, longest names first."""

    def __init__(self, names):
        self.names = sorted({str(n).strip() for n in names if str(n).strip()}, key=len, reverse=True)
        self.keys = {_norm(n): n for n in self.names}

    def find(self, line):
        """All team names in a line, in reading order."""
        text = ' '+_norm(line)+' '
        found = []
        for key in sorted(self.keys, key=len, reverse=True):
            index = text.find(' '+key+' ')
            if index >= 0:
                found.append((index, self.keys[key]))
                text = text[:index]+' '+'#'*len(key)+' '+text[index+len(key)+2:]
        return [name for _, name in sorted(found)]

    def exact(self, line):
        return self.keys.get(_norm(line))


def _date(text, today):
    match = DATE.search(text)
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    if year:
        year = int(year)+(2000 if len(year) == 2 else 0)
    else:  # season dates without a year: Aug-Dec belong to the season's first year
        season_start = today.year if today.month >= 8 else today.year-1
        year = season_start if month >= 8 else season_start+1
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_team_cards(text, teams):
    """{team: {'colors','day','time','venue'}} from the 'Squadre' cards."""
    lines = _lines(text)
    cards = {}
    for i, line in enumerate(lines):
        name = teams.exact(line)
        if not name:
            continue
        window = lines[i+1:i+7]
        if not any(l.lower().startswith(('colori', 'giorno')) for l in window[:3]):
            continue
        card = {}
        for j, item in enumerate(window):
            low = item.lower()
            if teams.exact(item) or (low.startswith('colori') and 'colors' in card):
                break
            if low.startswith('colori'):
                card['colors'] = item.split(':', 1)[-1].strip()
            elif low.startswith('giorno'):
                value = item.split(':', 1)[-1].strip()
                time = TIME.search(value)
                card['time'] = f'{int(time.group(1)):02d}:{time.group(2)}' if time else ''
                card['day'] = TIME.sub('', value).strip(' ,-')
            elif card and 'venue' not in card and not low.startswith(('colori', 'giorno')):
                card['venue'] = item
        if card:
            cards[name] = card
    return cards


def parse_matches(text, teams, today=None):
    """Every fixture or result found in the page text."""
    today = today or dt.date.today()
    lines = _lines(text)
    matches, seen = [], set()
    current_round = None
    for i, line in enumerate(lines):
        r = ROUND.search(line)
        if r and not teams.find(line):
            current_round = int(r.group(1) or r.group(2))
        names = teams.find(line)
        if not names:
            continue
        # Skip standings rows (many numbers) and team cards.
        if len(re.findall(r'-?\d+', TIME.sub('', DATE.sub('', line)))) >= 5:
            continue
        if any(l.lower().startswith(('colori', 'giorno e ora')) for l in lines[i+1:i+3]):
            continue
        if len(names) >= 2:
            home, away, middle, end = names[0], names[1], line, i
        else:
            # Away team within the next few lines; only scores or separators in between.
            home, away, end = names[0], None, i
            between = []
            for j in range(i+1, min(len(lines), i+5)):
                found = teams.find(lines[j])
                if found:
                    away, end = found[0], j
                    break
                between.append(lines[j])
            if not away or any(len(b) > 12 or re.search(r'[A-Za-z]{3,}', b) for b in between):
                continue
            middle = ' '.join([line]+between+[lines[end]])
        if home == away:
            continue
        context = ' '.join(lines[max(0, i-3):i]+[middle]+lines[end+1:end+3])
        date = _date(DATE.search(middle) and middle or context, today)
        if not date:
            continue
        clock = TIME.search(middle) or TIME.search(context)
        score = None
        core = middle
        for name in (home, away):
            core = re.sub(re.escape(name), ' ', core, flags=re.I)
        core = DATE.sub(' ', TIME.sub(' ', core))
        found = re.search(r'(?<![\d/])(\d{1,2})\s*[-–:]\s*(\d{1,2})(?![\d/])', core)
        if found:
            score = (int(found.group(1)), int(found.group(2)))
        after = lines[end+1] if end+1 < len(lines) else ''
        venue = after if (after and len(after.split()) >= 2 and not teams.find(after) and not DATE.search(after)
                          and re.search(r'[A-Za-z]{4,}', after) and not ROUND.search(after)
                          and not after.lower().startswith(('colori', 'giorno'))) else ''
        key = (home, away, date)
        if key in seen:
            continue
        seen.add(key)
        matches.append(dict(home=home, away=away, date=date, time=f'{int(clock.group(1)):02d}:{clock.group(2)}' if clock else '',
                            score=score, venue=venue, round=current_round))
    matches.sort(key=lambda m: (m['date'], m['time']))
    return matches


def is_ours(team, ours):
    a, b = _norm(team), _norm(ours)
    return bool(a and b) and (a == b or b in a or a in b)


def our_matches(matches, ours):
    return [m for m in matches if is_ours(m['home'], ours) or is_ours(m['away'], ours)]


def next_match(matches, ours, today=None):
    today = today or dt.date.today()
    upcoming = [m for m in our_matches(matches, ours) if m['score'] is None and m['date'] >= today]
    return upcoming[0] if upcoming else None


def _minus(clock, minutes):
    try:
        h, m = map(int, clock.split(':'))
    except ValueError:
        return ''
    total = (h*60+m-minutes) % (24*60)
    return f'{total//60:02d}:{total % 60:02d}'


def match_fields(match, ours, cards=None, meeting_minutes=60):
    """Fields for the shared 'Partita della settimana' panel."""
    cards = cards or {}
    home = is_ours(match['home'], ours)
    opponent = match['away'] if home else match['home']
    host = cards.get(match['home'], {})
    clock = match['time'] or host.get('time', '')
    venue = match['venue'] or host.get('venue', '')
    venue = re.sub(r'\s+', ' ', re.sub(r'\b\d{5}\b', ' ', venue)).strip(' ,-')  # drop the CAP: shorter on the graphic
    fields = dict(opponent=opponent.upper(), our_side='Casa' if home else 'Ospiti',
                  date=match['date'].strftime('%d/%m/%Y'), kickoff=clock or 'HH:MM',
                  meeting_time=_minus(clock, meeting_minutes) if clock else 'HH:MM', venue=venue.upper()[:72])
    if match.get('round'):
        fields['round'] = match['round']
    return fields


def read_page(payload, ours='FLAMINGOS', today=None):
    """Everything useful in one call: standings, matches, cards, next match."""
    today = today or dt.date.today()
    rows = None
    for source in (payload.get('t'), payload.get('x')):
        if source:
            try:
                rows = parse_standings(source)
                break
            except ValueError:
                continue
    names = [r['team'] for r in rows] if rows else []
    teams = Teams(names)
    text = payload.get('x', '')
    matches = parse_matches(text, teams, today) if names and text else []
    cards = parse_team_cards(text, teams) if names and text else {}
    upcoming = next_match(matches, ours, today)
    return dict(standings=rows, matches=matches, cards=cards, next=upcoming,
                fields=match_fields(upcoming, ours, cards) if upcoming else None, url=payload.get('u', ''))


def month_name(month):
    return MONTHS[month-1]


def fixtures_for_month(matches, ours, year, month, limit=8):
    """Calendar rows for one month, from our point of view."""
    rows = []
    for m in our_matches(matches, ours):
        if m['date'].year != year or m['date'].month != month:
            continue
        home = is_ours(m['home'], ours)
        score = ''
        if m['score']:
            score = f'{m["score"][0]}-{m["score"][1]}'
        rows.append(dict(date=m['date'].strftime('%d/%m'), day=WEEKDAYS[m['date'].weekday()][:3],
                         opponent=(m['away'] if home else m['home']).upper()[:30], side='C' if home else 'T',
                         time=m['time'], score=score))
    return rows[:limit]
