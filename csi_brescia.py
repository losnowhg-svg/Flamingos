"""3.20: the girone straight from the CSI Brescia results site, with no bookmark and no copy-paste.

risultati.csi.brescia.it fills its "Risultati / Classifiche / Squadre" tabs with three small POSTs
(the same ones its own page sends): plain HTML tables, no cookies and no login. Here they are read
into the shapes the app already uses (csi_page.read_page): standings rows, matches, team cards,
our next match and its fields for the "Partita della settimana" panel.

Only the scores the site shows count (official, or "ufficiosi" in red, which the site's own table
already counts); a result typed by a team and still hidden on the site is left out, like the site does.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import html
import re
import urllib.parse
import urllib.request

ENDPOINT = 'https://risultati.csi.brescia.it/public/ajax/filtri.php'
PAGE = 'https://risultati.csi.brescia.it/albo/risultati-calendario-classifiche-squadre.html?campionato={campionato}'
CAMPIONATO, GIRONE = '102', 'D'          # Calcio a 7, Serie C, girone D (2026/27)
KINDS = ('classifiche', 'risultati', 'squadre')
TIMEOUT = 8
AGENT = 'Mozilla/5.0 (compatible; FlamingosStudio/3.20; +https://flamingos-studio.streamlit.app)'


class CSIError(Exception):
    """The site did not answer, or answered with something that is not the girone."""


def page_url(campionato=CAMPIONATO):
    return PAGE.format(campionato=campionato)


# --- Download --------------------------------------------------------------------------------------

def _post(kind, campionato, girone, timeout, opener):
    body = urllib.parse.urlencode({'albo': 'ok', kind: 'ok', 'campionato': campionato, 'squadra': '',
                                   'girone': girone}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method='POST', headers={
        'User-Agent': AGENT, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest', 'Referer': page_url(campionato)})
    with opener(request, timeout=timeout) as response:
        raw = response.read(3_000_000)
        charset = response.headers.get_content_charset() if hasattr(response, 'headers') else None
    for encoding in filter(None, (charset, 'utf-8', 'cp1252')):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode('latin-1')


def fetch_all(campionato=CAMPIONATO, girone=GIRONE, timeout=TIMEOUT, opener=urllib.request.urlopen):
    """{'classifiche': html, 'risultati': html, 'squadre': html}, the three downloads side by side."""
    with cf.ThreadPoolExecutor(len(KINDS)) as pool:
        jobs = {kind: pool.submit(_post, kind, campionato, girone, timeout, opener) for kind in KINDS}
        out = {}
        for kind, job in jobs.items():
            try:
                out[kind] = job.result()
            except Exception as exc:                     # network, timeout, HTTP error: one clear message
                raise CSIError(_why(exc)) from exc
    return out


def _why(exc):
    text = str(getattr(exc, 'reason', '') or exc)
    if 'timed out' in text.lower() or isinstance(exc, TimeoutError):
        return 'il sito CSI non risponde (tempo scaduto)'
    code = getattr(exc, 'code', None)
    if code:
        return f'il sito CSI ha risposto con un errore ({code})'
    return f'il sito CSI non è raggiungibile ({text[:80]})'


# --- Reading the tables ----------------------------------------------------------------------------

def _text(fragment):
    fragment = re.sub(r'<br\s*/?>', ', ', fragment or '', flags=re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', fragment))).strip(' ,')


def _cell(row, css):
    found = re.search(r'<td[^>]*class="[^"]*\b'+css+r'\b[^"]*"[^>]*>(.*?)</td>', row, re.S | re.I)
    return found.group(1) if found else ''


def _teams(row):
    """The team names of a row, from the link title (or its text)."""
    names = []
    for cell in re.findall(r'<td[^>]*class="squadra"[^>]*>(.*?)</td>', row, re.S | re.I):
        title = re.search(r'title="([^"]*)"', cell)
        name = html.unescape(title.group(1)) if title else _text(cell)
        names.append(re.sub(r'\s+', ' ', name).strip().upper())
    return [n for n in names if n]


def _rows(table):
    return re.findall(r'<tr\b([^>]*)>(.*?)</tr>', table, re.S | re.I)


def _int(text):
    found = re.search(r'-?\d+', _text(text))
    return int(found.group()) if found else 0


def parse_standings(text):
    """Standings rows (pos, team, pt, g, v, n, p, gf, gs) in the site's order."""
    from classifica_data import empty_row
    table = re.search(r'<table[^>]*class="[^"]*\bcharts\b[^"]*"[^>]*>(.*?)</table>', text or '', re.S | re.I)
    rows = []
    labels = {'punti': 'pt', 'giocate': 'g', 'vinte': 'v', 'perse': 'p', 'pareggiate': 'n',
              'reti fatte': 'gf', 'reti subite': 'gs'}
    for _, row in _rows(table.group(1) if table else ''):
        teams = _teams(row)
        if not teams:
            continue
        item = empty_row(len(rows)+1)
        item['team'] = teams[0][:34]
        for label, value in re.findall(r'data-label="([^"]*)"[^>]*>(.*?)</td>', row, re.S | re.I):
            field = labels.get(html.unescape(label).strip().lower())
            if field:
                item[field] = max(0, min(999, _int(value)))
        rows.append(item)
    if not rows:
        raise CSIError('il sito CSI non ha mandato la classifica del girone')
    return rows


CODE = re.compile(r'(\d{4})(\d+)([A-Z])([AR])(\d{2})(\d{2})$')


def parse_results(text):
    """Every match of the girone, results and fixtures, sorted by date and time."""
    matches = []
    for table in re.findall(r'<table[^>]*class="[^"]*\bresults\b[^"]*"[^>]*>(.*?)</table>', text or '', re.S | re.I):
        caption = re.search(r'<caption>(.*?)</caption>', table, re.S | re.I)
        leg = 'R' if caption and 'RITORNO' in caption.group(1).upper() else 'A'
        current = None
        for attrs, row in re.findall(r'<tr\b([^>]*)>(.*?)(?=<tr\b|$)', table, re.S | re.I):
            heading = re.search(r'GIORNATA\s*(\d+)', row, re.I)
            if heading and '<th' in row.lower():
                current = int(heading.group(1))
                continue
            teams = _teams(row)
            if len(teams) < 2:
                continue
            try:
                date = dt.datetime.strptime(_text(_cell(row, 'data')), '%d/%m/%Y').date()
            except ValueError:
                continue
            clock = re.search(r'(\d{1,2})[:.](\d{2})', _text(_cell(row, 'ora')))
            code = _text(_cell(row, 'codice'))
            parts = CODE.search(code)
            score = None
            shown = re.search(r'class="text-result"[^>]*>\s*(\d{1,2})\s*-\s*(\d{1,2})', row)
            if shown:
                score = (int(shown.group(1)), int(shown.group(2)))
            venue = re.search(r'<img[^>]*alt="Vai al dettaglio Campo"[^>]*title="([^"]*)"', row, re.I) or \
                re.search(r'<img[^>]*title="([^"]*)"[^>]*alt="Vai al dettaglio Campo"', row, re.I)
            matches.append(dict(home=teams[0], away=teams[1], date=date,
                                time=f'{int(clock.group(1)):02d}:{clock.group(2)}' if clock else '',
                                score=score, venue=_text(venue.group(1)) if venue else '',
                                round=int(parts.group(5)) if parts else current, leg=parts.group(4) if parts else leg,
                                official=score is not None and 'ufficiosa' not in attrs.lower(), code=code))
    first_leg = max([m['round'] or 0 for m in matches if m['leg'] == 'A'] or [0])
    for m in matches:                                    # ritorno: round 14, 15... after a 13-round andata
        if m['leg'] == 'R' and m['round']:
            m['round'] += first_leg
        m.pop('leg')
    matches.sort(key=lambda m: (m['date'], m['time'], m['code']))
    return matches


WEEKDAY = re.compile(r'(luned|marted|mercoled|gioved|venerd|sabato|domenica)\w*', re.I)


def parse_teams(text):
    """{team: {'venue', 'day', 'time', 'colors'}} from the 'Squadre' table."""
    cards = {}
    for _, row in _rows(text or ''):
        teams = _teams(row)
        if not teams:
            continue
        campo = _cell(row, 'campo')
        link = re.search(r'<a[^>]*>(.*?)</a>', campo, re.S | re.I)
        venue = _text(link.group(1) if link else campo)
        when = _text(_cell(row, 'giorno'))
        clock = re.search(r'(\d{1,2})[:.](\d{2})', when)
        day = WEEKDAY.search(when)
        cards[teams[0]] = dict(venue=venue, day=day.group(0).capitalize() if day else '',
                               time=f'{int(clock.group(1)):02d}:{clock.group(2)}' if clock else '',
                               colors=_text(_cell(row, 'colori')))
    return cards


def read(pages, ours='FLAMINGOS', today=None):
    """Same shape as csi_page.read_page: standings, matches, cards, next, fields, url."""
    from csi_page import match_fields, next_match
    standings = parse_standings(pages.get('classifiche'))
    matches = parse_results(pages.get('risultati'))
    cards = parse_teams(pages.get('squadre'))
    upcoming = next_match(matches, ours, today)
    return dict(standings=standings, matches=matches, cards=cards, next=upcoming,
                fields=match_fields(upcoming, ours, cards) if upcoming else None, url=page_url())


def download(ours='FLAMINGOS', today=None, **kwargs):
    """Fetch and read the girone in one call (a few seconds); CSIError with a short reason otherwise."""
    return read(fetch_all(**kwargs), ours, today)
