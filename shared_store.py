"""Lavoro condiviso (3.14): the studio's work in a private GitHub repo, so any friend can carry on.

One JSON file (lavoro.json) holds the snapshot: the shared match, the CSI
matches, the squad, every editor's settings, the votes of the ratings, the
figurine being made, the sequence, the captions, the page being worked on.
Uploaded fonts and logos go next to it in archivio/, named by their hash
(written once, never changed). Every save is a commit, so the GitHub history
keeps every version: nothing is ever lost, even if two friends save at once.

Plain urllib (nothing to install). The transport can be swapped in tests.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.github.com'
FILE = 'lavoro.json'
FOLDER = 'archivio'
VERSION = 1
try:                                     # Streamlit Cloud runs in UTC: the times we show are Italian
    from zoneinfo import ZoneInfo
    ZONE = ZoneInfo('Europe/Rome')
except Exception:                        # no time-zone database: Italian winter time
    ZONE = dt.timezone(dt.timedelta(hours=1))


def now():
    return dt.datetime.now(ZONE)


MAX_ASSET = 4_000_000        # bytes: bigger fonts or logos stay in the browser that uploaded them

# What a friend needs to carry on. Data, plus a few widget values that are safe to set before the widget exists.
SHARE_KEYS = ('studio_models', 'shared_match', 'csi_matches', 'squad', 'season_games', 'season_scorers',
              'season_mvps', 'sponsor', 'sequence', 'captions', 'caption_context', 'pagelle_memory',
              'pagelle_payload', 'figurina_pick', 'figurina_ed', 'figurina_vote_pick', 'figurina_player',
              'figurina_edition', 'figurina_vote', 'figurina_from_pagelle', 'figurina_payload',
              'figurine_style_key', 'results_payload', 'results_title', 'results_format', 'results_style',
              'results_track', 'results_sound', 'results_fps', 'shared_note', 'shared_note_meta',
              'season_ledger', 'season_ledger_skip', 'classifica_backup', 'csi_sync', 'season_positions')
GAP = dt.timedelta(minutes=30)      # saves by the same friend closer than this are one working session
THROTTLE = 25.0                     # seconds: at most one save every this often; closer changes are folded in


class StoreError(Exception):
    pass


class Conflict(StoreError):
    """Someone else saved since we last read the file."""


# --- JSON with dates ---------------------------------------------------------------------------

class _Skip(Exception):
    pass


def encode(value):
    """Plain JSON from session values: dates tagged, tuples as lists; bytes are not shared."""
    if isinstance(value, dt.datetime):
        return {'$dt': value.isoformat()}
    if isinstance(value, dt.date):
        return {'$date': value.isoformat()}
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [encode(v) for v in value]
    if hasattr(value, 'item') and not isinstance(value, (bytes, bytearray)):      # numpy numbers
        return encode(value.item())
    raise _Skip(type(value).__name__)


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'$date'}:
            return dt.date.fromisoformat(value['$date'])
        if set(value) == {'$dt'}:
            return dt.datetime.fromisoformat(value['$dt'])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def snapshot(state, page='', author='', assets=None, now=None):
    """The dict saved in lavoro.json, from a session-state-like mapping."""
    shared, skipped = {}, []
    for key in SHARE_KEYS:
        if key in state:
            try:
                shared[key] = encode(state[key])
            except _Skip:
                skipped.append(key)
    return {'version': VERSION, 'saved_at': (now or globals()['now']()).isoformat(timespec='seconds'),
            'author': str(author or '')[:40], 'page': str(page or '')[:40], 'state': shared,
            'assets': dict(assets or {}), 'skipped': skipped}


def parse_message(message):
    """('LUCA', 'Figurine') from 'Lavoro di LUCA (Figurine)'; ('', '') for anything else."""
    message = str(message or '').split('\n')[0]
    if not message.startswith('Lavoro di ') or not message.endswith(')') or ' (' not in message:
        return '', ''
    who, _, rest = message[len('Lavoro di '):].partition(' (')
    page = rest[:-1].split(' · ')[0]
    return ('' if who == 'qualcuno' else who), page


def sessions(commits, limit=8):
    """Saves grouped into working sessions, newest first: one friend, saves less than GAP apart.

    commits: [{'sha', 'author', 'page', 'at'}] newest first. Each session ends with its last save,
    which is the version a restore brings back."""
    out = []
    for c in commits:
        at = c['at']
        last = out[-1] if out else None
        if last and last['author'] == c['author'] and last['first'] - at <= GAP:
            last['first'] = at
            last['count'] += 1
            if c['page'] and c['page'] not in last['pages']:
                last['pages'].append(c['page'])
            continue
        if len(out) == limit:
            break
        out.append(dict(sha=c['sha'], author=c['author'], at=at, first=at, count=1,
                        pages=[c['page']] if c['page'] else []))
    return out


# --- 3.22: two friends saving at the same time: the work is joined, not covered -----------------------

_MISSING = object()


def merge_values(base, mine, theirs):
    """Three-way join of two saved values that started from `base`.

    Whoever changed something wins on that thing; if both changed the same thing, this save (the newer)
    wins. Dicts are joined key by key (all the way down), so two friends working on different graphics,
    different matches of the season or different settings keep both their work."""
    if mine == theirs:
        return mine
    if mine == base:
        return theirs
    if theirs == base:
        return mine
    if all(isinstance(v, dict) or v is _MISSING for v in (base, mine, theirs)) and \
            isinstance(mine, dict) and isinstance(theirs, dict):
        base = base if isinstance(base, dict) else {}
        out = {}
        for key in list(mine)+[k for k in theirs if k not in mine]:
            value = merge_values(base.get(key, _MISSING), mine.get(key, _MISSING), theirs.get(key, _MISSING))
            if value is not _MISSING:
                out[key] = value
        return out
    return mine


def merge_state(base, mine, theirs):
    """The encoded shared state (snapshot['state']) of this save joined with a friend's newer one."""
    joined = merge_values(dict(base or {}), dict(mine or {}), dict(theirs or {}))
    return {k: v for k, v in joined.items() if k in SHARE_KEYS}


def fingerprint(snap):
    """What changed, ignoring the time and the author."""
    core = {k: snap.get(k) for k in ('page', 'state', 'assets')}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def restore(snap):
    """{key: value} to put back in the session (only known keys)."""
    if not isinstance(snap, dict) or snap.get('version') != VERSION:
        return {}
    state = snap.get('state') or {}
    return {k: decode(state[k]) for k in SHARE_KEYS if k in state}


def shareable(asset_id, data):
    """Only files uploaded to the archive (named kind:sha256 of their bytes) travel; built-in crests do not."""
    kind, _, digest = str(asset_id).partition(':')
    return (kind in ('font', 'logo') and len(digest) == 64 and isinstance(data, (bytes, bytearray))
            and len(data) <= MAX_ASSET and hashlib.sha256(data).hexdigest() == digest)


def asset_path(asset_id):
    kind, _, digest = str(asset_id).partition(':')
    if kind not in ('font', 'logo') or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise StoreError('Nome file non valido')
    return f'{FOLDER}/{kind}-{digest}'


# --- GitHub ------------------------------------------------------------------------------------

def _urllib(method, url, headers, body=None, timeout=15):
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise StoreError(f'GitHub non raggiungibile ({exc}).') from exc


class GitHubStore:
    def __init__(self, token, repo, branch='main', transport=None):
        repo = str(repo or '').strip().strip('/')
        if repo.count('/') != 1 or not token:
            raise StoreError('Manca il token o il nome del repo (proprietario/nome).')
        self.repo, self.branch, self.token = repo, branch, str(token).strip()
        self.transport = transport or _urllib

    def _call(self, method, path, payload=None, raw=False, ref=None, query=None):
        url = f'{API}/repos/{self.repo}' + (f'/contents/{urllib.parse.quote(path)}' if path else '')
        if query:
            url = f'{API}/repos/{self.repo}/{query}'
        elif method == 'GET' and path:
            url += '?ref='+urllib.parse.quote(ref or self.branch)
        headers = {'Authorization': f'Bearer {self.token}', 'X-GitHub-Api-Version': '2022-11-28',
                   'Accept': 'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
                   'User-Agent': 'flamingos-studio'}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
        return self.transport(method, url, headers, body)

    def _fail(self, status, body):
        try:
            message = json.loads(body or b'{}').get('message', '')
        except ValueError:
            message = ''
        if status in (401, 403):
            return StoreError('Token non valido o senza permesso di scrittura sul repo.')
        if status == 404:
            return StoreError('Repo non trovato: controlla il nome e che il token lo veda.')
        return StoreError(f'GitHub ha risposto {status}: {message[:120]}')

    def read(self, path, ref=None):
        """(bytes, sha) of a file (at a past commit with ref), or (None, None) if it does not exist."""
        status, body = self._call('GET', path, ref=ref)
        if status == 404:
            return None, None
        if status != 200:
            raise self._fail(status, body)
        meta = json.loads(body)
        if meta.get('encoding') == 'base64' and meta.get('content') is not None and meta.get('size', 0) <= 1_000_000:
            return base64.b64decode(meta['content']), meta['sha']
        status, data = self._call('GET', path, raw=True, ref=ref)       # files over 1 MB come raw
        if status != 200:
            raise self._fail(status, data)
        return data, meta['sha']

    def write(self, path, data, sha=None, message='Salvataggio'):
        """The new sha. Conflict if the file changed since `sha` (or exists when sha is None)."""
        payload = {'message': message[:200], 'content': base64.b64encode(data).decode(), 'branch': self.branch}
        if sha:
            payload['sha'] = sha
        status, body = self._call('PUT', path, payload)
        if status in (200, 201):
            return json.loads(body)['content']['sha']
        if status in (409, 422) and (sha or b'sha' in (body or b'')):
            raise Conflict('Il file è cambiato nel frattempo.')
        raise self._fail(status, body)

    def check(self):
        """Raise a clear StoreError if the repo cannot be reached with this token."""
        status, body = self._call('GET', '')
        if status != 200:
            raise self._fail(status, body)
        if not json.loads(body).get('private', False):
            raise StoreError('Il repo dei salvataggi deve essere privato.')

    # The work file.
    def load(self, ref=None):
        """(snapshot dict or None, sha); with ref, the version saved in that commit."""
        data, sha = self.read(FILE, ref)
        if data is None:
            return None, None
        try:
            return json.loads(data.decode('utf8')), sha
        except ValueError as exc:
            raise StoreError('lavoro.json non è leggibile.') from exc

    def save(self, snap, sha=None, base=None):
        """(new sha, the friend's snapshot if someone else had saved meanwhile, else None).

        3.22: with `base` (the shared state this session started from) a friend's newer save is joined
        with this one (snap['state'] is updated in place); without it, this save covers theirs (going back
        to an old version)."""
        who = snap.get('author') or 'qualcuno'
        page = snap.get('page') or 'studio'
        if snap.get('event'):
            page += ' · '+str(snap['event'])[:80]
        message = f"Lavoro di {who} ({page})"
        encode_snap = lambda: json.dumps(snap, ensure_ascii=False, separators=(',', ':')).encode('utf8')
        try:
            return self.write(FILE, encode_snap(), sha, message), None
        except Conflict:
            for _ in range(3):                           # a friend saved meanwhile: join and try again
                theirs, latest = self.load()
                if base is not None and theirs:
                    snap['state'] = merge_state(base, snap['state'], theirs.get('state') or {})
                    snap['assets'] = dict(theirs.get('assets') or {}, **(snap.get('assets') or {}))
                    base = dict(theirs.get('state') or {})
                    message = message.replace('Lavoro di', 'Lavoro unito di', 1)
                try:
                    return self.write(FILE, encode_snap(), latest, message), theirs
                except Conflict:
                    continue
            raise StoreError('Troppi salvataggi insieme: riprovo alla prossima modifica.')

    def history(self, count=100):
        """The last saves of lavoro.json, newest first: [{'sha', 'author', 'page', 'at'}]."""
        status, body = self._call('GET', '', query=f'commits?path={FILE}&per_page={int(count)}&sha='
                                  + urllib.parse.quote(self.branch))
        if status == 409:                               # empty repo
            return []
        if status != 200:
            raise self._fail(status, body)
        out = []
        for item in json.loads(body):
            commit = item.get('commit') or {}
            who, page = parse_message(commit.get('message'))
            stamp = str((commit.get('author') or {}).get('date') or '').replace('Z', '+00:00')
            try:
                at = dt.datetime.fromisoformat(stamp).astimezone(ZONE)
            except ValueError:
                continue
            out.append(dict(sha=item.get('sha', ''), author=who, page=page, at=at))
        return out

    # Fonts and logos.
    def put_asset(self, asset_id, data):
        path = asset_path(asset_id)
        try:
            self.write(path, data, None, 'Archivio: '+path)
        except Conflict:
            pass                                    # already there: same name, same bytes
        return path

    def get_asset(self, asset_id):
        data, _ = self.read(asset_path(asset_id))
        if data is None:
            return None
        kind, _, digest = asset_id.partition(':')
        if hashlib.sha256(data).hexdigest() != digest:
            raise StoreError('File dell\'archivio alterato.')
        return data


# --- Saving in the background, at a calm pace -----------------------------------------------------

class Saver:
    """Saves one session's work in its own thread, at most one save every `throttle` seconds (3.15.1).

    The first change after a quiet moment goes out at once; changes that come closer are folded into
    the next save (the newest snapshot wins, uploads add up, an 'event' is kept), which leaves when
    the interval is over even if nobody touches the app again. So nothing is lost and the history
    holds one save per burst of work instead of one per click. Results go into `meta` (sha,
    saved_at, error, overwrote, hash), the dict the sidebar reads; no Streamlit calls here.
    """

    def __init__(self, meta, throttle=None, clock=time.monotonic, sleep=time.sleep):
        self.meta, self.throttle = meta, THROTTLE if throttle is None else float(throttle)
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.job, self.alive, self.last, self.thread = None, False, -1e9, None

    @property
    def pending(self):
        return self.alive

    def submit(self, store_factory, snap, uploads=()):
        uploads = list(uploads)
        with self.lock:
            if self.job:
                old_snap, old_uploads, _ = self.job
                if old_snap.get('event') and not snap.get('event'):
                    snap['event'] = old_snap['event']
                seen = {asset_id for asset_id, _ in uploads}
                uploads += [u for u in old_uploads if u[0] not in seen]
            self.job = (snap, uploads, store_factory)
            if self.alive:
                return
            self.alive = True
            self.thread = threading.Thread(target=self._run, daemon=True, name='flamingos-save')
        self.thread.start()

    def cancel(self):
        """Forget a save that has not left yet (after taking the friends' latest work, or an old version)."""
        with self.lock:
            self.job = None

    def wait(self, timeout=30.0):
        """For tests: until the queue is empty."""
        end = time.monotonic()+timeout
        while self.alive and time.monotonic() < end:
            time.sleep(.01)
        return not self.alive

    def _run(self):
        while True:
            with self.lock:                              # nothing waiting: done (pending is False right away)
                if self.job is None:
                    self.alive = False
                    return
            wait = self.last+self.throttle-self.clock()
            if wait > 0:                                 # too soon after the last save: changes keep folding in
                self.sleep(wait)
            with self.lock:
                job, self.job = self.job, None
            if job is None:                              # cancelled while waiting
                continue
            self.last = self.clock()
            self._save(*job)

    def _save(self, snap, uploads, store_factory):
        meta = self.meta
        try:
            store = store_factory()
            for asset_id, data in uploads:
                try:
                    store.put_asset(asset_id, data)
                except StoreError:                       # one file that does not go up does not stop the save
                    snap['assets'].pop(asset_id, None)
            mine = json.loads(json.dumps(snap['state']))
            base = meta.get('base')
            sha, theirs = store.save(snap, meta.get('sha'), base)
            meta.update(sha=sha, saved_at=snap['saved_at'], error=None)
            if base is not None:
                meta['base'] = snap['state']             # what everybody has now: the next join starts here
            if theirs and snap['state'] != mine:         # 3.22: the friend's work, to bring into this session
                incoming = dict(meta.get('incoming') or {})
                incoming.update({k: (mine.get(k), v) for k, v in snap['state'].items() if mine.get(k) != v})
                meta['incoming'] = incoming
                meta['merged'] = dict(author=theirs.get('author') or '', saved_at=theirs.get('saved_at') or '')
                meta['hash_after'] = fingerprint(snap)
            elif theirs and base is None and (theirs.get('author') or '') != snap.get('author'):
                meta['overwrote'] = dict(author=theirs.get('author') or '', saved_at=theirs.get('saved_at') or '')
        except Exception as exc:                          # shown in the sidebar, retried at the next change
            meta['error'] = str(exc)[:200]
            meta['hash'] = None
