"""☁️ Lavoro condiviso (3.14): pick up where a friend left off, save on its own while you work.

3.15, passaggio di consegne: a note for the friends ("pagelle fatte, manca il video") shown to
whoever opens the app next, the past versions (grouped by working session) to go back to, and
the name picked from the squad with one tap.

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

import streamlit as st

import shared_store as ss

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


def saver():
    """This session's background saver (one save at most every ss.THROTTLE seconds)."""
    meta = _meta()
    if not isinstance(meta.get('saver'), ss.Saver):
        meta['saver'] = ss.Saver(meta)
    return meta['saver']


def _pending():
    found = _meta().get('saver')
    return bool(found and found.pending)


def when(iso):
    """'oggi 18:42', 'ieri 21:05', 'sab 25/10 18:40', in Italian time (old saves without a zone were UTC)."""
    try:
        at = dt.datetime.fromisoformat(str(iso))
    except ValueError:
        return ''
    if at.tzinfo is None:
        at = at.replace(tzinfo=dt.timezone.utc)
    at = at.astimezone(ss.ZONE)
    today = ss.now().date()
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
        if str(st.session_state.get('shared_note') or '').strip():
            st.toast(f"Nota di {_note_author()}: {st.session_state['shared_note'].strip()[:90]}", icon='📝')
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
    saver().cancel()                                     # a change still waiting must not cover what we take
    meta['sha'] = sha
    if snap:
        _apply(snap, meta)
        meta.pop('overwrote', None)


# --- 3.15: note for the friends, past versions ------------------------------------------------

def _note_author():
    meta = st.session_state.get('shared_note_meta') or {}
    return str(meta.get('author') or '').title() or 'un amico'


def _note_changed():
    note = str(st.session_state.get('shared_note') or '').strip()
    st.session_state['shared_note_meta'] = {'author': author(), 'at': ss.now().isoformat(timespec='minutes')} if note else {}


def _clear_note():
    st.session_state['shared_note'] = ''
    st.session_state['shared_note_meta'] = {}


def note_banner(template):
    """The note on top of the page: always on the home, once on any other page after opening the app."""
    note = str(st.session_state.get('shared_note') or '').strip()
    if not note or _meta().get('status') != 'on':
        return
    first = not st.session_state.get('shared_note_seen')
    st.session_state['shared_note_seen'] = True
    if template != 'Settimana' and not first:
        return
    meta = st.session_state.get('shared_note_meta') or {}
    stamp = f" ({when(meta['at'])})" if meta.get('at') else ''
    with st.container(border=True, key='note_banner'):
        a, b = st.columns([4, 1], vertical_alignment='center')
        a.markdown(f"📝 **Nota di {_note_author()}**{stamp}: {note}")
        b.button('✓ Fatto', key='note_done', on_click=_clear_note, width='stretch',
                 help='Toglie la nota per tutti (puoi scriverne una nuova nella barra laterale).')


def session_label(group, latest=False):
    who = group['author'].title() or 'qualcuno'
    pages = ', '.join(group['pages'][:3])
    count = f" · {group['count']} salvataggi" if group['count'] > 1 else ''
    return f"{when(group['at'].isoformat())} · {who}" + (f" · {pages}" if pages else '') + count + \
        (' (la versione di adesso)' if latest else '')


def load_history():
    """Button callback: the last working sessions, from the repo history."""
    meta, conf = _meta(), settings()
    if not conf:
        return
    try:
        st.session_state['shared_history'] = ss.sessions(ss.GitHubStore(*conf).history())
        st.session_state.pop('shared_history_pick', None)
    except ss.StoreError as exc:
        meta['error'] = str(exc)


def restore_version(index):
    """Button callback: go back to the end of a past working session; the next save makes it the current one."""
    meta, conf = _meta(), settings()
    groups = st.session_state.get('shared_history') or []
    if not conf or not 0 <= index < len(groups):
        return
    group = groups[index]
    try:
        snap, _ = ss.GitHubStore(*conf).load(ref=group['sha'])     # the old file's sha is not the current one
    except ss.StoreError as exc:
        meta['error'] = str(exc)
        return
    if not snap:
        return
    saver().cancel()
    _apply(snap, meta)
    meta.pop('baseline', None)                           # save it now: it becomes everybody's current version
    who = group['author'].title() or 'qualcuno'
    meta['event'] = f"tornato alla versione di {who} {when(group['at'].isoformat())}"
    meta['flash'] = f"Sei tornato alla versione di {who} ({when(group['at'].isoformat())}). Quella di prima " \
                    'resta tra le versioni precedenti.'
    st.session_state['shared_history'] = None


def merge_squad(library):
    """Once per session: sprites, photo avatars and Instagram names this browser has and the shared squad lacks.

    So a device that opens a save made elsewhere never loses what it had; the next save shares it with everyone."""
    if st.session_state.get('shared_squad_merged') or not library:
        return
    st.session_state['shared_squad_merged'] = True
    local = {p['name']: p for p in library.get('squad') or []}
    shared = st.session_state.get('squad')
    if not shared or not local:
        return
    merged, changed = [], False
    for person in shared:
        person = dict(person)
        mine = local.get(person.get('name'), {})
        if not person.get('look') and not person.get('avatar'):
            for field in ('look', 'avatar'):
                if mine.get(field):
                    person[field], changed = mine[field], True
        if not person.get('ig') and mine.get('ig'):
            person['ig'], changed = mine['ig'], True
        merged.append(person)
    if changed:
        st.session_state['squad'] = merged
        _meta().pop('baseline', None)                    # save it right away: the others get the sprites too


def merge_assets(library):
    """Fonts and logos uploaded by friends, added to this session's archive."""
    meta = _meta()
    if meta.get('status') != 'on' or not library:
        return
    merge_squad(library)
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
    if meta.get('event'):
        snap['event'] = meta.pop('event')                 # e.g. 'tornato alla versione di Luca', in the commit message
    saver().submit(lambda: ss.GitHubStore(*conf), snap, uploads)


def _remember_author():
    name = str(st.session_state.get('shared_author') or '').strip()
    if st.session_state.get('shared_note') and not (st.session_state.get('shared_note_meta') or {}).get('author'):
        _note_changed()
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
        names = [p['name'] for p in st.session_state.get('squad') or [] if p.get('name')]
        current = str(st.session_state.get('shared_author') or '').strip()
        if current and current not in names:
            names.append(current)
        empty = {} if 'shared_author' in st.session_state else {'index': None}   # no default next to a set value
        st.selectbox('Chi sta lavorando?', names, **empty, key='shared_author', placeholder='Tocca e scegli il tuo nome',
                     accept_new_options=True, format_func=lambda n: str(n).title(), on_change=_remember_author,
                     help='Compare nei salvataggi e nelle note, così gli amici sanno di chi è il lavoro. '
                          'Se non sei nella rosa, scrivi il nome.')
        if meta.get('error'):
            st.warning(f"Ultimo salvataggio non riuscito: {meta['error'].rstrip('.')}. Riprovo alla prossima modifica.")
        elif _pending():
            st.caption('Salvo per tutti tra pochi secondi...')
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
        if meta.get('flash'):
            st.success(meta.pop('flash'))
        st.button("↻ Prendi l'ultimo lavoro degli amici", key='shared_reload', on_click=reload, width='stretch',
                  help='Carica adesso l\'ultimo salvataggio (anche di un amico che sta lavorando in questo momento).')
        st.text_area('📝 Nota per gli amici', key='shared_note', max_chars=280, height=90, on_change=_note_changed,
                     placeholder='Es. Pagelle fatte, manca il video. Convocati da finire.',
                     help='Chi apre l\'app dopo di te la vede in alto. Toglila con ✓ Fatto quando è tutto a posto.')
        note_meta = st.session_state.get('shared_note_meta') or {}
        if str(st.session_state.get('shared_note') or '').strip() and note_meta.get('at'):
            st.caption(f"Scritta da {_note_author()} ({when(note_meta['at'])})")
        with st.popover('🕘 Versioni precedenti', width='stretch'):
            groups = st.session_state.get('shared_history')
            if groups is None:
                st.caption('Le ultime sessioni di lavoro di tutti. Tornare a una versione non cancella niente: '
                           'anche quella di adesso resta qui.')
                st.button('Mostra le versioni', key='shared_history_load', on_click=load_history, width='stretch')
            elif not groups:
                st.caption('Ancora nessun salvataggio.')
            else:
                pick = st.radio('Versione', range(len(groups)), key='shared_history_pick',
                                format_func=lambda i: session_label(groups[i], latest=i == 0))
                st.button('↩ Torna a questa versione', key='shared_history_go', on_click=restore_version, args=(pick,),
                          type='primary', width='stretch', disabled=pick == 0)
                st.button('↻ Aggiorna l\'elenco', key='shared_history_load', on_click=load_history, width='stretch')
