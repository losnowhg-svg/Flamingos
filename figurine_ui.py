"""🃏 Figurine e pagelle: the match ratings, the holographic cards and the season album."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st

import album
import card_video
import cards
import figurine_data as fd
import pagelle
from sequence_ui import current_config
from studio_state import sanitize_match
from ui_utils import progress_with_eta

FORMATS = ('Story 9:16', 'Post 4:5', 'Post 1:1')


# --- Shared bits ---------------------------------------------------------------------------------

def _squad(library):
    squad = st.session_state.get('squad') or library.get('squad') or []
    if squad:
        return squad, False
    from team_looks import OFFICIAL_SQUAD
    return [dict(p) for p in OFFICIAL_SQUAD], True


def _logo(root, library, match):
    assets = library.get('assets', {})
    chosen = match.get('our_logo_id')
    if chosen in assets and assets[chosen].get('kind') == 'logo':
        return assets[chosen]['bytes']
    return (Path(root)/'assets'/'flamingos_logo.jpg').read_bytes()


def _sig(*parts):
    data = json.dumps([p for p in parts if not isinstance(p, bytes)], sort_keys=True, default=str).encode()
    for p in parts:
        if isinstance(p, bytes):
            data += hashlib.sha256(p).digest()
    return hashlib.sha256(data).hexdigest()[:24]


@st.cache_data(show_spinner=False, max_entries=24)
def _poster_png(spec_json, logo, format, scale, caption, style_key=None):
    import io
    image = card_video.poster(json.loads(spec_json), logo, format, scale, caption, _style(style_key, format, scale))
    out = io.BytesIO()
    image.save(out, 'PNG', optimize=True)
    return out.getvalue()


@st.cache_data(show_spinner=False, max_entries=24)
def _card_png(spec_json, logo, height):
    return cards.card_png(json.loads(spec_json), logo, height)


@st.cache_data(show_spinner=False, max_entries=12)
def _pagelle_png(rows_json, match_json, logo, format, scale, style_key=None):
    return pagelle.png_bytes(json.loads(rows_json), json.loads(match_json), logo, format, scale,
                             _style(style_key, format, scale))


@st.cache_data(show_spinner=False, max_entries=8)
def _album_png(members_json, logo, format, scale, season, team, style_key=None):
    return album.png_bytes(json.loads(members_json), logo, format, scale, season=season, team=team,
                           style=_style(style_key, format, scale))


def _style(style_key, format, scale):
    import figurine_style
    return figurine_style.build(style_key, format, int(540*scale)) if style_key else None


@st.cache_data(show_spinner=False, max_entries=4)
def _album_zip(members_json, logo):
    return album.zip_bytes(json.loads(members_json), logo)


def _video_controls(prefix, default_track):
    """Music, sounds, fps and resolution for a video of this page."""
    import variety
    import music_ui
    with st.expander('Impostazioni video', expanded=False):
        a, b = st.columns(2)
        tracks = [t for t in variety.MUSIC_TRACKS if t != 'auto']
        track = a.selectbox('Musica', ['nessuna']+tracks, index=(['nessuna']+tracks).index(default_track)
                            if default_track in tracks else 0, format_func=lambda x: 'Nessuna' if x == 'nessuna'
                            else variety.MUSIC_TRACKS.get(x, x), key=prefix+'_track')
        sound = b.checkbox('Effetti (strappo, colpi, scintille)', True, key=prefix+'_sound')
        fps = a.selectbox('Fotogrammi al secondo', (30, 60), key=prefix+'_fps',
                          format_func=lambda x: '30 (consigliato)' if x == 30 else '60 (fluidissimo, più lento)')
        scale = b.selectbox('Risoluzione', (2, 1), key=prefix+'_scale',
                            format_func=lambda x: '1080 px' if x == 2 else '540 px (rapido)')
        if track == 'mio':
            holder = {}
            music_ui.uploader(holder, prefix+'_my_music')
            track = holder.get('music_custom') or None
        elif track == 'nessuna':
            track = None
        st.caption('Il momento clou (la carta che esce, l\'MVP) cade sul drop della musica, a 4 secondi.')
    return track, sound, fps, scale


def _context(match, fulltime, squad):
    return dict(fulltime=fulltime, round=match.get('round', 0), scorers=st.session_state.get('season_scorers') or [],
                games=st.session_state.get('season_games') or [], mvps=st.session_state.get('season_mvps') or [],
                season=fd.season_label(fulltime.get('date') if 'GG' not in str(fulltime.get('date')) else match.get('date')),
                team=match.get('our_name', 'FLAMINGOS'))


# --- Page ------------------------------------------------------------------------------------------

def show_figurine(root, library):
    st.subheader('🃏 FIGURINE E PAGELLE')
    st.caption('Le pagelle della partita, le figurine olografiche dei Flamingos (il migliore in campo esce da una '
               'bustina, in video) e l\'album della stagione, che diventa più raro a ogni MVP.')
    match = sanitize_match(st.session_state.get('shared_match'))
    fulltime = current_config('Full Time')
    squad, official = _squad(library)
    if official:
        st.caption('Uso la rosa ufficiale 2026/27 con i suoi sprite: per personalizzarla salvala nella Settimana.')
    logo = _logo(root, library, match)
    ctx = _context(match, fulltime, squad)
    import figurine_style as fs
    from crt_presets import PRESET_IDS
    choices = [fs.FOLLOW, fs.SYNTHWAVE]+list(PRESET_IDS)
    choice = st.selectbox('Stile', choices, key='figurine_style', format_func=lambda c: fs.label(c, fulltime),
                          help='Lo sfondo di pagelle, figurine e album: quello del preset (TV, cassetta, Game Boy...) '
                               'oppure la notte synthwave delle figurine. La carta resta la stessa.')
    ctx['style'] = fs.key_for(choice, fulltime)
    st.session_state['figurine_style_key'] = ctx['style']
    t_pag, t_card, t_album = st.tabs(['📝 Pagelle', '🃏 Figurina', '📒 Album'])
    with t_pag:
        _pagelle_tab(match, fulltime, squad, logo, ctx)
    with t_card:
        _card_tab(match, fulltime, squad, logo, ctx)
    with t_album:
        _album_tab(squad, logo, ctx)


# --- Pagelle -----------------------------------------------------------------------------------------

def _pagelle_tab(match, fulltime, squad, logo, ctx):
    players = fd.played(current_config('Convocati'), squad)
    line = fd.score_line(fulltime)
    st.caption(f'Partita: **{line}** (dall\'editor Full Time). Chi ha giocato arriva dai Convocati; i gol dai marcatori.')
    goals = fd.goals_by_player(fulltime)
    memory = st.session_state.setdefault('pagelle_memory', {})
    rows = [dict(giocatore=p['name'], voto=memory.get(p['name'], {}).get('voto', ''),
                 nota=memory.get(p['name'], {}).get('nota', ''),
                 gol=int(memory.get(p['name'], {}).get('gol', goals.get(p['name'], 0)))) for p in players]
    preview, controls = st.columns([1, 1.15], gap='large')
    with controls:
        st.markdown('**I voti**')
        edited = st.data_editor(rows, hide_index=True, width='stretch', key='pagelle_editor_'+_sig([p['name'] for p in players]),
                                column_config={
                                    'giocatore': st.column_config.TextColumn('Giocatore', disabled=True),
                                    'voto': st.column_config.SelectboxColumn('Voto', options=fd.VOTE_OPTIONS, width='small',
                                                                             help='Vuoto = senza voto (non compare)'),
                                    'nota': st.column_config.TextColumn('Commento', max_chars=60),
                                    'gol': st.column_config.NumberColumn('Gol', min_value=0, max_value=9, step=1, width='small')})
        edited = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
        for r in edited:
            memory[r['giocatore']] = dict(voto=r.get('voto') or '', nota=r.get('nota') or '', gol=int(r.get('gol') or 0))
        by_name = {p['name']: p for p in players}
        voted = [dict(by_name[r['giocatore']], vote=fd.parse_vote(r.get('voto')), note=str(r.get('nota') or '')[:60],
                      goals=int(r.get('gol') or 0)) for r in edited if fd.parse_vote(r.get('voto')) is not None]
        auto = pagelle.best(voted) if voted else None
        names = [r['name'] for r in voted]
        mvp = st.selectbox('Migliore in campo (MVP)', ['auto']+names, key='pagelle_mvp',
                           format_func=lambda x: f'Automatico: {auto}' if x == 'auto' and auto else
                           ('Automatico' if x == 'auto' else x)) if voted else 'auto'
        mvp = auto if mvp == 'auto' else mvp
        for r in voted:
            r['mvp'] = r['name'] == mvp
        fmt = st.selectbox('Formato', FORMATS, key='pagelle_format')
        round_ = int(match.get('round') or 0)
        info = dict(line=line, sub=' · '.join(x for x in (f'GIORNATA {round_}' if round_ else '',
                                                           fulltime.get('date', '') if 'GG' not in str(fulltime.get('date')) else '') if x))
        from fulltime_renderer import outcome
        result = outcome(fulltime)[0]
        track, sound, fps, scale = _video_controls('pagelle', {'win': 'cc0_funk', 'draw': 'cc0_sunglasses'}.get(result, 'cc0_city'))
    with preview:
        if not voted:
            st.info('Dai almeno un voto nella tabella: le pagelle compaiono qui.')
            return
        hd = _pagelle_png(json.dumps(voted, sort_keys=True, default=str), json.dumps(info, sort_keys=True), logo, fmt, 2,
                          ctx['style'])
        st.session_state['pagelle_payload'] = {'rows': voted, 'info': info}
        st.image(hd, width='stretch')
        signature = _sig(voted, info, fmt, track, sound, fps, scale, logo, ctx['style'])
        a, b = st.columns(2)
        a.download_button('⬇ Pagelle PNG', hd, file_name='flamingos_pagelle.png', mime='image/png', width='stretch',
                          key='pagelle_png')
        if b.button('🎬 Video delle pagelle', type='primary', width='stretch', key='pagelle_video'):
            bar = st.progress(0, text='Le pagelle in video...')
            try:
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)/'pagelle.mp4'
                    pagelle.render_video(voted, info, logo, path, fps, fmt, scale, track, sound,
                                         progress_callback=progress_with_eta(bar, 'Pagelle'),
                                         style=_style(ctx['style'], fmt, scale))
                    st.session_state['pagelle_mp4'] = {'signature': signature, 'data': path.read_bytes()}
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                bar.empty()
        video = st.session_state.get('pagelle_mp4')
        if video and video['signature'] == signature:
            st.video(video['data'])
            st.download_button('⬇ Scarica il video', video['data'], file_name='flamingos_pagelle.mp4', mime='video/mp4',
                               width='stretch', key='pagelle_mp4_dl')
            import share
            share.button(video['data'], 'flamingos_pagelle.mp4', 'video/mp4', key='pagelle_share_mp4')
        import share
        share.button(hd, 'flamingos_pagelle.png', 'image/png', key='pagelle_share_png')
        with st.expander('✍️ Didascalia pronta'):
            tags = {p['name']: p.get('ig') for p in squad}
            st.code(fd.pagelle_caption([dict(r, ig=tags.get(r['name'])) for r in voted], mvp, fulltime), language=None,
                    wrap_lines=True)
        if mvp:
            best_row = next(r for r in voted if r['name'] == mvp)
            st.markdown(f"**MVP: {mvp} {cards.vote_text(best_row['vote'])}**")
            a, b = st.columns(2)
            if a.button('🃏 Prepara la sua figurina', width='stretch', key='pagelle_to_card',
                        help='La trovi nella scheda Figurina, già compilata.'):
                st.session_state['figurina_player'] = mvp
                st.session_state['figurina_edition'] = 'mvp'
                st.session_state['figurina_vote'] = cards.vote_text(best_row['vote'])
                st.session_state['figurina_from_pagelle'] = True
                st.rerun()
            if b.button('⭐ Segna nella collezione', width='stretch', key='pagelle_collect',
                        help='Conta per l\'album: 1 MVP rara, 2 epica, 3 o più leggendaria. Salvato nel browser.'):
                _collect(mvp, best_row['vote'], match, fulltime)
            if st.session_state.get('figurina_from_pagelle'):
                st.success('Figurina pronta: apri la scheda 🃏 Figurina qui sopra.')


def _collect(name, vote, match, fulltime):
    from week_ui import save_week
    entry = dict(name=name, vote=vote, date=fd.award_date(fulltime.get('date'), match.get('date')),
                 opp=fd.opponent(fulltime), score=fd.score_for_us(fulltime), round=match.get('round', 0))
    st.session_state['season_mvps'] = fd.add_mvp(st.session_state.get('season_mvps') or [], entry)
    save_week()
    st.toast(f'{name} nella collezione della stagione ⭐')


# --- Figurina ------------------------------------------------------------------------------------------

def _card_tab(match, fulltime, squad, logo, ctx):
    people = list(squad)          # everybody, staff too: a role not set prints as a midfielder
    if not people:
        st.info('La rosa è vuota: caricala nella Settimana.')
        return
    names = [p['name'] for p in people]
    preview, controls = st.columns([1, 1.15], gap='large')
    with controls:
        wanted = st.session_state.pop('figurina_player', None)
        if wanted in names:
            st.session_state['figurina_pick'] = wanted
        a, b = st.columns(2)
        name = a.selectbox('Giocatore', names, key='figurina_pick',
                           format_func=lambda n: next((f"{p['number']:>2}  {n}" if p.get('number') else n)
                                                      for p in people if p['name'] == n))
        editions = list(cards.EDITIONS)
        wanted_ed = st.session_state.pop('figurina_edition', None)
        if wanted_ed in editions:
            st.session_state['figurina_ed'] = wanted_ed
        edition = b.selectbox('Edizione', editions, key='figurina_ed', format_func=lambda e: cards.EDITIONS[e]['name'])
        member = next(p for p in people if p['name'] == name)
        a, b = st.columns(2)
        rarity = a.selectbox('Rarità', ['auto']+list(cards.RARITIES), key='figurina_rarity',
                             format_func=lambda r: f"Automatica ({cards.RARITIES[cards.EDITIONS[edition]['rarity']]['name']})"
                             if r == 'auto' else cards.RARITIES[r]['name'])
        wanted_vote = st.session_state.pop('figurina_vote', None)
        if wanted_vote in fd.VOTE_OPTIONS:
            st.session_state['figurina_vote_pick'] = wanted_vote
        vote_text = b.selectbox('Voto in pagella', fd.VOTE_OPTIONS, key='figurina_vote_pick',
                                format_func=lambda v: v or 'Nessuno (mostra il numero)',
                                index=fd.VOTE_OPTIONS.index('8') if edition == 'mvp' and 'figurina_vote_pick' not in st.session_state else 0)
        st.markdown('**Statistiche sulla carta**')
        defaults = fd.stats_for(edition, member, ctx)
        stats = []
        columns = st.columns(3)
        for i, (label, value) in enumerate(defaults):
            with columns[i]:
                key = f'figurina_stat_{edition}_{name}_{i}'
                label = st.text_input('Voce', label, max_chars=12, key=key+'_l')
                value = st.text_input('Valore', value, max_chars=12, key=key+'_v')
                stats.append((label.upper(), value))
        caption = st.text_input('Scritta sotto la carta', fd.caption_for(edition, member, ctx), max_chars=60,
                                key=f'figurina_caption_{edition}_{name}')
        fmt = st.selectbox('Formato', FORMATS, key='figurina_format')
        default_track = {'leggenda': 'cc0_battle', 'epica': 'cc0_robots', 'rara': 'cc0_ritmo'}.get(
            cards.EDITIONS[edition]['rarity'] if rarity == 'auto' else rarity, 'cc0_sunglasses')
        track, sound, fps, scale = _video_controls('figurina', default_track)
    spec = dict(name=member['name'], number=member.get('number', 0), role=member.get('role'), look=member.get('look'),
                avatar=member.get('avatar', ''), edition=edition, rarity=None if rarity == 'auto' else rarity,
                vote=fd.parse_vote(vote_text), stats=stats, season=ctx['season'], team=ctx['team'],
                captain=bool(member.get('captain')) or edition == 'capitano',
                serial=(names.index(name)+1, len(names)))
    spec_json = json.dumps(spec, sort_keys=True, default=str)
    with preview:
        post = _poster_png(spec_json, logo, fmt, 2, caption, ctx['style'])
        st.session_state['figurina_payload'] = {'spec': spec, 'caption': caption}
        st.image(post, width='stretch')
        a, b = st.columns(2)
        a.download_button('⬇ Post PNG', post, file_name=f"figurina_{member['name'].lower()}_post.png", mime='image/png',
                          width='stretch', key='figurina_post_png')
        card_sig = _sig(spec, logo)
        if b.button('🖼 Solo la carta (sfondo trasparente)', width='stretch', key='figurina_card_make',
                    help='Senza sfondo: per WhatsApp, sticker, stampa.'):
            st.session_state['figurina_card'] = {'signature': card_sig, 'data': _card_png(spec_json, logo, 1500)}
        alone = st.session_state.get('figurina_card')
        if alone and alone['signature'] == card_sig:
            st.download_button('⬇ Scarica la carta PNG', alone['data'], file_name=f"figurina_{member['name'].lower()}.png",
                               mime='image/png', width='stretch', key='figurina_card_png')
        signature = _sig(spec, caption, fmt, track, sound, fps, scale, logo, ctx['style'])
        if st.button('🎬 Apri la bustina (video)', type='primary', width='stretch', key='figurina_video'):
            bar = st.progress(0, text='Preparo la bustina...')
            try:
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)/'figurina.mp4'
                    card_video.render_video(spec, logo, path, fps, fmt, scale, track, caption, sound,
                                            progress_callback=progress_with_eta(bar, 'Bustina'),
                                            style=_style(ctx['style'], fmt, scale))
                    st.session_state['figurina_mp4'] = {'signature': signature, 'data': path.read_bytes(),
                                                        'name': member['name'].lower()}
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                bar.empty()
        video = st.session_state.get('figurina_mp4')
        if video and video['signature'] == signature:
            st.video(video['data'])
            st.download_button('⬇ Scarica il video', video['data'], file_name=f"figurina_{video['name']}.mp4",
                               mime='video/mp4', width='stretch', key='figurina_mp4_dl')
            import share
            share.button(video['data'], f"figurina_{video['name']}.mp4", 'video/mp4', key='figurina_share')
        with st.expander('✍️ Didascalia pronta'):
            st.code(fd.card_caption(edition, member, ctx, spec['vote'], cards.spec_for(spec)['rarity']), language=None,
                    wrap_lines=True)
        if edition == 'mvp' and st.button('⭐ Segna questo MVP nella collezione', width='stretch', key='figurina_collect'):
            _collect(member['name'], spec['vote'], match, fulltime)
        st.caption('La bustina: tre indizi a tempo di musica (ruolo, numero, stemma), lo strappo, la carta che esce '
                   'girandosi sul drop, coriandoli per le epiche e le leggendarie.')


# --- Album -------------------------------------------------------------------------------------------------

def _album_tab(squad, logo, ctx):
    mvps = st.session_state.get('season_mvps') or []
    preview, controls = st.columns([1, 1.15], gap='large')
    with controls:
        st.markdown('**La collezione della stagione**')
        st.caption('Ogni MVP segnato rende la figurina più rara: 1 rara, 2 epica, 3 o più leggendaria. '
                   'I gol arrivano dai marcatori della stagione (pagina Wrapped).')
        rows = [dict(data=m.get('date', ''), giocatore=m['name'], avversari=m.get('opp', ''),
                     voto=cards.vote_text(m['vote']) if m.get('vote') is not None else '') for m in mvps] \
            or [dict(data='', giocatore='', avversari='', voto='')]
        edited = st.data_editor(rows, num_rows='dynamic', hide_index=True, width='stretch', key='album_mvps',
                                column_config={'data': st.column_config.TextColumn('Data', max_chars=10),
                                               'giocatore': st.column_config.SelectboxColumn(
                                                   'MVP', options=[p['name'] for p in squad]),
                                               'avversari': st.column_config.TextColumn('Avversari', max_chars=40),
                                               'voto': st.column_config.SelectboxColumn('Voto', options=fd.VOTE_OPTIONS)})
        edited = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
        if st.button('Salva la collezione', key='album_save', width='stretch'):
            from week_ui import save_week
            clean = fd.sanitize_mvps([dict(name=r.get('giocatore') or '', date=r.get('data') or '', opp=r.get('avversari') or '',
                                           vote=r.get('voto')) for r in edited])
            st.session_state['season_mvps'] = clean
            save_week()
            st.rerun()
        staff = st.checkbox('Anche il mister', True, key='album_staff')
        fmt = st.selectbox('Formato', FORMATS, key='album_format', index=1)
    members = album.members_for(squad, mvps, ctx['scorers'], staff, ctx['season'], ctx['team'])
    members_json = json.dumps(members, sort_keys=True, default=str)
    with preview:
        if not members:
            st.info('La rosa è vuota: caricala nella Settimana.')
            return
        hd = _album_png(members_json, logo, fmt, 2, ctx['season'], ctx['team'], ctx['style'])
        st.image(hd, width='stretch')
        a, b = st.columns(2)
        a.download_button('⬇ Album PNG', hd, file_name='flamingos_album.png', mime='image/png', width='stretch',
                          key='album_png')
        if b.button('📦 Tutte le figurine (ZIP)', width='stretch', key='album_zip_make'):
            with st.spinner('Stampo le figurine...'):
                st.session_state['album_zip'] = {'signature': _sig(members, logo), 'data': _album_zip(members_json, logo)}
        pack = st.session_state.get('album_zip')
        if pack and pack['signature'] == _sig(members, logo):
            st.download_button('⬇ Scarica le figurine (PNG trasparenti)', pack['data'], file_name='flamingos_figurine.zip',
                               mime='application/zip', type='primary', width='stretch', key='album_zip_dl')
        import share
        share.button(hd, 'flamingos_album.png', 'image/png', key='album_share')
