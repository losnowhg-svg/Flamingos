"""☁️ Lavoro condiviso (3.14): pick up where a friend left off, save on its own while you work.

At the start of a session the last work saved by anyone is loaded (match, CSI
matches, squad, editors, votes, figurine, sequence, captions, the page).
Then every change is saved in the background to the private repo set in the
Streamlit secrets:

    [condivisione]
    token = "github_pat_..."
    repo = "proprietario/Flamingos-dati"

Without those secrets the app works as before (browser only).
"""
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

import shared_store as ss

_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix='flamingos-save')   # saves go out one at a time
DAYS = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')


def settings():
    """(token, repo) from the secrets, or None when sharing is not set up."""
    try:
        conf = st.secrets.get('condivisione')
    except Exception:                        # no secrets file at all
        return None
    if not conf or not conf.get('token') or not conf.get('repo'):
        return None
    return str(conf['token']), str(conf['repo'])


def _meta():
    return st.session_state.setdefault('shared_meta', {'status': 'off'})


def when(iso):
    """'oggi 18:42', 'ieri 21:05', 'sab 25/10 18:40'."""
    try:
        at = dt.datetime.fromisoformat(str(iso))
    except ValueError:
        return ''
    today = dt.date.today()
    if at.date() == today:
        return f'oggi {at:%H:%M}'
    if at.date() == today-dt.timedelta(days=1):
        return f'ieri {at:%H:%M}'
    return f'{DAYS[at.weekday()]} {at:%d/%m %H:%M}'


def author():
    return str(st.session_state.get('shared_author') or '').strip().upper()[:24]


def _apply(snap, meta):
    """Put a saved snapshot back in this session."""
    for key, value in ss.restore(snap).items():
        st.session_state[key] = value
    page = snap.get('page')
    if page:
        st.session_state['studio_template'] = page
    st.session_state['week_restored'] = True           # the browser's own week must not cover the shared one
    revisions = st.session_state.setdefault('studio_revisions', {})
    for template in list((st.session_state.get('studio_models') or {})):
        revisions[template] = revisions.get(template, 0)+1     # editors redraw from the loaded settings
    for key in [k for k in st.session_state if str(k).startswith('png_') or str(k).endswith(('_mp4', '_zip'))]:
        st.session_state.pop(key, None)                 # renders of the old state
    meta['assets'] = dict(snap.get('assets') or {})
    meta['loaded'] = dict(author=snap.get('author') or '', saved_at=snap.get('saved_at') or '', page=page or '')
    meta['baseline'] = True                              # the first run after loading only sets the reference


def start():
    """Once per session, before the menu: load the last shared work."""
    meta = _meta()
    if st.session_state.get('shared_started'):
        return meta
    st.session_state['shared_started'] = True
    if 'shared_author' not in st.session_state and st.query_params.get('chi'):
        st.session_state['shared_author'] = str(st.query_params.get('chi'))[:24]
    conf = settings()
    if not conf:
        meta['status'] = 'off'
        return meta
    try:
        store = ss.GitHubStore(*conf)
        snap, sha = store.load()
    except ss.StoreError as exc:
        meta.update(status='error', error=str(exc))
        return meta
    meta.update(status='on', sha=sha, assets={}, error=None)
    if snap:
        _apply(snap, meta)
        loaded = meta['loaded']
        who = loaded['author'].title() or 'un amico'
        st.toast(f"Ripreso il lavoro di {who} ({when(loaded['saved_at'])})", icon='☁️')
    return meta


def reload():
    """Button callback: take the latest work saved by anyone, now."""
    meta, conf = _meta(), settings()
    if not conf:
        return
    try:
        snap, sha = ss.GitHubStore(*conf).load()
    except ss.StoreError as exc:
        meta['error'] = str(exc)
        return
    meta['sha'] = sha
    if snap:
        _apply(snap, meta)
        meta.pop('overwrote', None)


def merge_assets(library):
    """Fonts and logos uploaded by friends, added to this session's archive."""
    meta = _meta()
    if meta.get('status') != 'on' or not library:
        return
    cache = st.session_state.setdefault('shared_asset_cache', {})
    conf = settings()
    for asset_id, info in (meta.get('assets') or {}).items():
        if asset_id in library['assets']:
            continue
        if asset_id not in cache:
            cache[asset_id] = None
            try:
                data = ss.GitHubStore(*conf).get_asset(asset_id)
                kind = asset_id.split(':')[0]
                import renderer
                (renderer.validate_font if kind == 'font' else renderer.validate_logo)(data)
                cache[asset_id] = {'kind': kind, 'name': str(info.get('name', 'File'))[:100], 'bytes': data}
            except Exception:                        # missing or not valid: the editors fall back to the default
                pass
        if cache[asset_id]:
            library['assets'][asset_id] = cache[asset_id]


def _save(conf, snap, uploads, meta):
    """In the background worker: no Streamlit calls here, only the meta dict."""
    try:
        store = ss.GitHubStore(*conf)
        for asset_id, data in uploads:
            try:
                store.put_asset(asset_id, data)
            except ss.StoreError:                        # one file that does not go up does not stop the save
                snap['assets'].pop(asset_id, None)
        sha, theirs = store.save(snap, meta.get('sha'))
        meta.update(sha=sha, saved_at=snap['saved_at'], error=None)
        if theirs and (theirs.get('author') or '') != snap.get('author'):     # a friend saved in the meantime
            meta['overwrote'] = dict(author=theirs.get('author') or '', saved_at=theirs.get('saved_at') or '')
    except Exception as exc:                          # StoreError or anything odd: shown in the sidebar, retried later
        meta['error'] = str(exc)[:200]
        meta['hash'] = None
    finally:
        meta['pending'] = max(0, meta.get('pending', 1)-1)


def _known(asset_id):
    """An archive name (font:/logo: + sha256), not a built-in crest: the index keeps only those."""
    try:
        ss.asset_path(asset_id)
        return True
    except ss.StoreError:
        return False


def autosave(library):
    """At the end of every run: if anything changed, save it (in the background)."""
    meta, conf = _meta(), settings()
    if meta.get('status') != 'on' or not conf:
        return
    index = {k: v for k, v in (meta.get('assets') or {}).items() if _known(k)}
    uploads = []
    for asset_id, asset in ((library or {}).get('assets') or {}).items():
        if asset_id not in index and ss.shareable(asset_id, asset.get('bytes')):
            index[asset_id] = {'kind': asset['kind'], 'name': asset['name']}
            uploads.append((asset_id, asset['bytes']))
    snap = ss.snapshot(st.session_state, st.session_state.get('studio_template', ''), author(), index)
    mark = ss.fingerprint(snap)
    if meta.pop('baseline', False) and not uploads:
        meta['hash'] = mark
        return
    if mark == meta.get('hash') or not snap['state']:
        return
    meta['hash'], meta['assets'] = mark, index
    meta['pending'] = meta.get('pending', 0)+1
    _WORKER.submit(_save, conf, snap, uploads, meta)


def _remember_author():
    name = str(st.session_state.get('shared_author') or '').strip()
    if name:
        st.query_params['chi'] = name[:24]
    elif 'chi' in st.query_params:
        del st.query_params['chi']


def sidebar():
    """The small ☁️ box in the sidebar: who is working, last save, take the friends' latest."""
    meta = _meta()
    if meta.get('status') == 'off':
        st.caption('☁️ Lavoro condiviso non attivo: si salva solo in questo browser.')
        return
    with st.container(border=True, key='shared_box'):
        st.markdown('**☁️ Lavoro condiviso**')
        if meta.get('status') == 'error':
            st.warning(f"Non riesco a leggere i salvataggi: {meta.get('error')}")
            return
        st.text_input('Chi sta lavorando?', key='shared_author', max_chars=24, placeholder='Il tuo nome',
                      on_change=_remember_author, help='Compare nei salvataggi, così gli amici sanno di chi è il lavoro.')
        if meta.get('error'):
            st.warning(f"Ultimo salvataggio non riuscito: {meta['error'].rstrip('.')}. Riprovo alla prossima modifica.")
        elif meta.get('pending'):
            st.caption('Salvataggio in corso...')
        elif meta.get('saved_at'):
            st.caption(f"✓ Salvato per tutti ({when(meta['saved_at'])})")
        elif meta.get('loaded'):
            loaded = meta['loaded']
            st.caption(f"Ripreso il lavoro di {loaded['author'].title() or 'un amico'} ({when(loaded['saved_at'])}). "
                       'Ogni modifica si salva da sola.')
        else:
            st.caption('Ogni modifica si salva da sola per tutti.')
        if meta.get('overwrote'):
            other = meta['overwrote']
            st.info(f"Anche {other['author'].title() or 'un amico'} ha salvato ({when(other['saved_at'])}): ora vale il "
                    'tuo lavoro, il suo resta nella cronologia del repo. Per prendere il suo usa il pulsante qui sotto.')
        st.button("↻ Prendi l'ultimo lavoro degli amici", key='shared_reload', on_click=reload, width='stretch',
                  help='Carica adesso l\'ultimo salvataggio (anche di un amico che sta lavorando in questo momento).')
