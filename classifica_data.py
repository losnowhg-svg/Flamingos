"""Standings import: pasted text (Tuttocampo, CSI, spreadsheets) or a page URL.

No Streamlit here. The parser reads the page as a stream of tokens, so it works
whether a copied table arrives one row per line, tab separated, or one cell per
line. The column order is taken from the header when one is present, otherwise
it is chosen as the order that makes V + N + P = G for the most teams.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from collections import Counter

MAX_TEAMS = 16
FIELDS = ('pt', 'g', 'v', 'n', 'p', 'gf', 'gs')
HEADER_ALIASES = {
    'pt': {'PT', 'PTI', 'PUNTI', 'P.TI', 'PTS'},
    'g': {'G', 'PG', 'GIOC', 'GIOCATE', 'GG', 'PJ', 'GP'},
    'v': {'V', 'VINTE', 'W'},
    'n': {'N', 'PAREGGI', 'PAR', 'X', 'D'},
    'p': {'P', 'PERSE', 'L', 'S'},
    'gf': {'GF', 'RF', 'F', 'GOL F', 'FATTI'},
    'gs': {'GS', 'RS', 'S', 'SUBITI', 'GA'},
    'dr': {'DR', 'DIFF', 'DG', 'D.R.', '+/-', 'DIFF.'},
}
FORM_LETTERS = {'V', 'N', 'P', 'S', 'W', 'L', 'D', '-'}
NOISE = {'SQUADRA', 'SQUADRE', 'CLASSIFICA', 'POS', 'POS.', '#', 'CASA', 'FUORI', 'TOTALE',
         'ULTIME', 'FORMA', 'MI', 'MEDIA', 'INGLESE', 'PEN', 'PENALITA', 'PENALIZZAZIONE'}
CANDIDATE_ORDERS = (
    ('pt', 'g', 'v', 'n', 'p', 'gf', 'gs'),
    ('g', 'v', 'n', 'p', 'gf', 'gs', 'pt'),
    ('pt', 'g', 'v', 'p', 'n', 'gf', 'gs'),
    ('g', 'v', 'n', 'p', 'gf', 'gs', 'dr', 'pt'),
    ('pt', 'g', 'v', 'n', 'p', 'gf', 'gs', 'dr'),
)
NUMBER = re.compile(r'^[+-]?\d{1,3}$')


def empty_row(position=1):
    return dict(pos=position, team='', pt=0, g=0, v=0, n=0, p=0, gf=0, gs=0)


def _header_order(lines):
    """Return (index of header line, ordered list of stat fields) if a header exists."""
    for index, line in enumerate(lines[:40]):
        cells = [c.strip().upper() for c in re.split(r'\t|\s{2,}|\s', line) if c.strip()]
        found = []
        for cell in cells:
            for field, aliases in HEADER_ALIASES.items():
                if cell in aliases and (field not in found or field in ('p', 'gs')):
                    found.append(field)
                    break
        # P/S are ambiguous (persa / subiti): resolve by position after the core columns.
        if {'g', 'v', 'n'} <= set(found) and len(found) >= 5:
            order, seen = [], set()
            for field in found:
                if field == 'p' and 'p' in seen:
                    field = 'gs'
                if field == 'gs' and 'gf' not in seen and 'p' not in seen:
                    field = 'p'
                if field not in seen:
                    order.append(field); seen.add(field)
            return index, order
    return None, None


def _tokens(text):
    out = []
    for raw in re.split(r'[\t\n\r|;]+', text):
        raw = raw.strip()
        if not raw:
            continue
        words = [w for w in raw.split(' ') if w]
        numeric = sum(1 for w in words if NUMBER.match(w.replace('°', '').replace('.', '')))
        if len(words) > 1 and numeric < 3 and re.search(r'[A-Za-zÀ-ÿ]', raw):
            out.append(' '.join(words))  # a real table cell: keep "ATLETICO 7" whole
        else:
            out.extend(words)  # a whole row pasted as plain text
    return out


def _blocks(tokens):
    """Group the stream into [name words] followed by the numbers after them."""
    leading, rows, name, numbers = [], [], [], []
    for token in tokens:
        clean = token.strip('.,:()°ª').upper()
        if NUMBER.match(token.replace('°', '').replace('.', '')):
            value = int(token.replace('°', '').replace('.', ''))
            if name:
                numbers.append(value)
            else:
                leading.append(value)
            continue
        if not clean or clean in NOISE or (clean in FORM_LETTERS and (numbers or not name)):
            continue
        if numbers:  # a new name starts: close the previous row
            rows.append((name, numbers)); name, numbers = [], []
        name.append(token)
    if name:
        rows.append((name, numbers))
    return leading, rows


def _score(order, stats_rows):
    good = 0
    for stats in stats_rows:
        row = dict(zip(order, stats))
        if all(k in row for k in ('g', 'v', 'n', 'p')) and row['v']+row['n']+row['p'] == row['g'] and row['g'] > 0:
            good += 2
        if 'pt' in row and 'v' in row and 'n' in row and row['pt'] == 3*row['v']+row['n']:
            good += 1
    return good


def parse_standings(text):
    """Return a list of standings rows (dicts). Raises ValueError when nothing fits."""
    text = html.unescape(str(text or ''))
    lines = [line for line in text.splitlines() if line.strip()]
    header_index, header = _header_order(lines)
    if header_index is not None:
        lines = lines[header_index+1:]
    leading, blocks = _blocks(_tokens('\n'.join(lines)))
    if not blocks:
        raise ValueError('Nessuna squadra riconosciuta nel testo incollato.')
    # Between two names the last number is the next team's position, so inside
    # the table each block holds K stats + 1. The last row (or a row followed by
    # other page text) holds just the K stats.
    sizes = Counter(len(numbers) for _, numbers in blocks if len(numbers) >= 6)
    if not sizes:
        raise ValueError('Ho trovato i nomi ma non i numeri della classifica (servono almeno G, V, N, P e punti).')
    # With a position before the first team, every inner block also carries the
    # next team's position: one number more than the stat columns.
    width = sizes.most_common(1)[0][0]-(1 if leading else 0)
    parsed = []
    position = leading[-1] if leading else None
    for name, numbers in blocks:
        next_position = None
        if len(numbers) == width+1:
            stats, next_position = numbers[:width], numbers[-1]
        else:
            stats = numbers[:width]
        parsed.append((position, ' '.join(name), stats))
        position = next_position if next_position and 0 < next_position <= 99 else None
    rows_stats = [stats for _, _, stats in parsed if len(stats) >= width]
    if header:
        order = tuple(header[:width])
    else:
        candidates = [o for o in CANDIDATE_ORDERS if len(o) <= width]
        order = max(candidates, key=lambda o: (_score(o, rows_stats), len(o)))
    rows = []
    for position, team, stats in parsed:
        if len(stats) < len(order) or len(rows) >= MAX_TEAMS:
            continue
        row = empty_row(len(rows)+1)
        row['team'] = re.sub(r'\s+', ' ', team).strip(' -*')[:34].upper()
        for field, value in zip(order, stats):
            if field in FIELDS:
                row[field] = max(0, min(999, value))
        if position and 0 < position <= 99:
            row['pos'] = position
        rows.append(row)
    if not rows:
        raise ValueError('Il formato del testo non e stato riconosciuto.')
    if not any(r['g'] for r in rows) and not any(r['pt'] for r in rows):
        raise ValueError('I numeri letti sono tutti zero: controlla di aver copiato la tabella intera.')
    return sort_rows(rows, keep_positions=True)


def sort_rows(rows, keep_positions=False):
    """Order by position when imported; otherwise by points, goal difference, goals for."""
    rows = [dict(r) for r in rows if str(r.get('team', '')).strip()][:MAX_TEAMS]
    if keep_positions and len({r['pos'] for r in rows}) == len(rows):
        return sorted(rows, key=lambda r: r['pos'])
    rows.sort(key=lambda r: (-int(r['pt']), -(int(r['gf'])-int(r['gs'])), -int(r['gf']), r['team']))
    for i, r in enumerate(rows):
        r['pos'] = i+1
    return rows


def html_to_text(page):
    page = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', page)
    page = re.sub(r'(?i)</t[dh]\s*>', '\t', page)
    page = re.sub(r'(?i)</tr\s*>|<br\s*/?>|</(p|div|li)\s*>', '\n', page)
    page = re.sub(r'<[^>]+>', ' ', page)
    return html.unescape(page)


def _best_table(page):
    tables = re.findall(r'(?is)<table.*?</table>', page)
    best, best_count = None, 0
    for table in tables:
        try:
            rows = parse_standings(html_to_text(table))
        except ValueError:
            continue
        if len(rows) > best_count:
            best, best_count = rows, len(rows)
    return best


def fetch_standings(url, timeout=12):
    """Download a standings page and parse its largest valid table."""
    url = str(url or '').strip()
    if not re.match(r'^https?://[\w.-]+(/|$)', url):
        raise ValueError('Inserisci un link completo che inizi con https://')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (FlamingosStudio; uso personale squadra)',
        'Accept-Language': 'it-IT,it;q=0.9'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(3_000_000)
            charset = response.headers.get_content_charset() or 'utf-8'
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise ValueError('Il sito non permette la lettura automatica (errore '+str(exc.code)+'). '
                             'Apri la classifica nel browser, copia la tabella e incollala nella scheda Incolla la tabella.') from exc
        raise ValueError(f'Il sito ha risposto con errore {exc.code}. Usa il copia e incolla della tabella.') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError('Il sito non e raggiungibile dal server dell\'app. Usa il copia e incolla della tabella.') from exc
    page = raw.decode(charset, errors='replace')
    rows = _best_table(page)
    if not rows:
        rows = parse_standings(html_to_text(page))
    return rows


# --- One-tap import from the viewer's own browser ---------------------------
# CSI LIVE and Tuttocampo refuse requests from cloud servers (403). The
# bookmarklet runs on the page the user already has open, reads the standings
# table their browser is showing and opens the app with it in the address.
APP_URL = 'https://flamingos-studio.streamlit.app/'
QUERY_KEY = 'classifica'
MAX_QUERY_CHARS = 6000
MAX_PAGE_TEXT = 24000

_BOOKMARKLET = r"""(()=>{const w=window.open('','_blank');(async()=>{const clean=s=>s.replace(/\s+/g,' ').trim();
let tb=[...document.querySelectorAll('table')].find(x=>/squadra/i.test(x.innerText)&&/\bpt\b|punti/i.test(x.innerText));
let t='',names=[];if(tb){const rows=[...tb.rows].map(r=>[...r.cells].map(c=>clean(c.innerText)));t=rows.map(r=>r.join('\t')).join('\n');
names=rows.slice(1).map(r=>(r.find(c=>/[a-z]{2}/i.test(c))||'').toLowerCase()).filter(n=>n.length>1)}
let ls=(document.querySelector('main')||document.body).innerText.split('\n').map(l=>l.replace(/[^\S\n]+/g,' ').trim()).filter(l=>l);
const hit=l=>{const s=l.toLowerCase();return /\d{1,2}[\/.-]\d{1,2}|giornata|colori|giorno|squadra|classifica/.test(s)||names.some(n=>s.includes(n))};
let keep=ls.map(hit);if(names.length)ls=ls.filter((l,i)=>keep.slice(Math.max(0,i-3),i+4).some(Boolean));
let x=ls.join('\n').slice(0,__TEXT__);if(!/squadra/i.test(t+x)){if(w)w.close();alert('Flamingos Studio: classifica non trovata. Apri la pagina del girone e riprova.');return}
let p=t;try{const j=JSON.stringify({v:2,u:location.href,t:t,x:x});const r=new Response(new Blob([j]).stream().pipeThrough(new CompressionStream('gzip')));
const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=8192)s+=String.fromCharCode.apply(null,b.subarray(i,i+8192));
p='z'+btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}catch(e){p=(t||x).slice(0,__MAX__)}
const u='__APP__?__KEY__='+encodeURIComponent(p);if(w)w.location=u;else location.href=u})()})()"""


def bookmarklet(app_url=APP_URL):
    code = (_BOOKMARKLET.replace('__APP__', app_url).replace('__KEY__', QUERY_KEY)
            .replace('__MAX__', str(MAX_QUERY_CHARS)).replace('__TEXT__', str(MAX_PAGE_TEXT)))
    return 'javascript:' + ''.join(line.strip() for line in code.splitlines())


def with_rows(config, rows):
    """A Classifica config with imported rows, padded to the fixed table size."""
    import copy
    updated = copy.deepcopy(config)
    rows = [dict(r) for r in rows[:MAX_TEAMS]]
    updated['standings'] = rows + [empty_row(i+1) for i in range(len(rows), MAX_TEAMS)]
    updated['team_count'] = max(2, len(rows))
    return updated
