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
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.github.com'
FILE = 'lavoro.json'
FOLDER = 'archivio'
VERSION = 1
MAX_ASSET = 4_000_000        # bytes: bigger fonts or logos stay in the browser that uploaded them

# What a friend needs to carry on. Data, plus a few widget values that are safe to set before the widget exists.
SHARE_KEYS = ('studio_models', 'shared_match', 'csi_matches', 'squad', 'season_games', 'season_scorers',
              'season_mvps', 'sponsor', 'sequence', 'captions', 'caption_context', 'pagelle_memory',
              'pagelle_payload', 'figurina_pick', 'figurina_ed', 'figurina_vote_pick', 'figurina_player',
              'figurina_edition', 'figurina_vote', 'figurina_from_pagelle', 'figurina_payload',
              'figurine_style_key', 'results_payload', 'results_title', 'results_format', 'results_style',
              'results_track', 'results_sound', 'results_fps')


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
    return {'version': VERSION, 'saved_at': (now or dt.datetime.now()).isoformat(timespec='seconds'),
            'author': str(author or '')[:40], 'page': str(page or '')[:40], 'state': shared,
            'assets': dict(assets or {}), 'skipped': skipped}


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

    def _call(self, method, path, payload=None, raw=False):
        url = f'{API}/repos/{self.repo}' + (f'/contents/{urllib.parse.quote(path)}' if path else '')
        if method == 'GET' and path:
            url += '?ref='+urllib.parse.quote(self.branch)
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

    def read(self, path):
        """(bytes, sha) of a file, or (None, None) if it does not exist yet."""
        status, body = self._call('GET', path)
        if status == 404:
            return None, None
        if status != 200:
            raise self._fail(status, body)
        meta = json.loads(body)
        if meta.get('encoding') == 'base64' and meta.get('content') is not None and meta.get('size', 0) <= 1_000_000:
            return base64.b64decode(meta['content']), meta['sha']
        status, data = self._call('GET', path, raw=True)       # files over 1 MB come raw
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
    def load(self):
        """(snapshot dict or None, sha)."""
        data, sha = self.read(FILE)
        if data is None:
            return None, None
        try:
            return json.loads(data.decode('utf8')), sha
        except ValueError as exc:
            raise StoreError('lavoro.json non è leggibile.') from exc

    def save(self, snap, sha=None):
        """(new sha, the snapshot that was overwritten if someone else had saved meanwhile, else None)."""
        data = json.dumps(snap, ensure_ascii=False, separators=(',', ':')).encode('utf8')
        who = snap.get('author') or 'qualcuno'
        message = f"Lavoro di {who} ({snap.get('page') or 'studio'})"
        try:
            return self.write(FILE, data, sha, message), None
        except Conflict:
            theirs, latest = self.load()
            return self.write(FILE, data, latest, message), theirs

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
