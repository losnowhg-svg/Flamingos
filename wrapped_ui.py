"""🎁 Flamingos Wrapped: the season (or a month) in retro slides."""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

import season_stats as ss
import wrapped_renderer as wr
from crt_presets import FORMATS, output_image
from sequence_ui import current_config, resolve_assets, sponsor_scene
from studio_state import sanitize_match
from transitions import render_sequence
from ui_utils import progress_with_eta
from week_ui import save_week


def _games_from_sources(ours):
    """CSI calendar results merged with the games typed in this page."""
    games = {(g['date'], g['opp'].upper()): g for g in ss.our_games(st.session_state.get('csi_matches') or [], ours)}
    for g in st.session_state.get('season_games') or []:
        games[(g['date'], g['opp'].upper())] = dict(g)
    return sorted(games.values(), key=lambda g: g['date'])


def _rows(games):
    return [dict(data=g['date'].strftime('%d/%m/%Y'), avversari=g['opp'], casa=bool(g['home']), noi=int(g['us']),
                 loro=int(g['them'])) for g in games] or [dict(data='', avversari='', casa=True, noi=0, loro=0)]


def _parse(rows):
    games = []
    for r in rows:
        try:
            date = dt.datetime.strptime(str(r.get('data', '')).strip(), '%d/%m/%Y').date()
        except ValueError:
            continue
        opp = str(r.get('avversari') or '').strip().upper()
        if not opp:
            continue
        games.append(dict(date=date, opp=opp, home=bool(r.get('casa')), us=max(0, int(r.get('noi') or 0)),
                          them=max(0, int(r.get('loro') or 0)), round=None))
    return sorted(games, key=lambda g: g['date'])


def show_wrapped(root: Path, library):
    st.subheader('🎁 FLAMINGOS WRAPPED')
    st.caption('La stagione (o un mese) raccontata in slide retrò: partite, gol, la vittoria più bella, la serie, '
               'casa e trasferta, i bomber, la classifica. Stile, tema e formato vengono dall\'editor Classifica.')
    match = sanitize_match(st.session_state.get('shared_match'))
    ours = match['our_name']
    squad = st.session_state.get('squad') or library.get('squad') or []
    games = _games_from_sources(ours)

    with st.expander(f'📋 Partite della stagione ({len(games)})', expanded=not games):
        st.caption('Arrivano dal sito CSI (segnalibro o pagina incollata). Puoi correggere, aggiungere righe con il + '
                   'o scrivere quelle che mancano. Data GG/MM/AAAA, Casa spuntato se giocavamo in casa.')
        edited = st.data_editor(_rows(games), num_rows='dynamic', hide_index=True, width='stretch', key='wrapped_games',
                                column_config={'data': st.column_config.TextColumn('Data', max_chars=10),
                                               'avversari': st.column_config.TextColumn('Avversari', max_chars=40),
                                               'casa': st.column_config.CheckboxColumn('Casa'),
                                               'noi': st.column_config.NumberColumn('Noi', min_value=0, max_value=99, step=1),
                                               'loro': st.column_config.NumberColumn('Loro', min_value=0, max_value=99, step=1)})
        rows = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
        if st.button('Salva le partite', key='wrapped_save_games'):
            st.session_state['season_games'] = _parse(rows)
            save_week()
            st.rerun()
    games = _parse(rows) if rows else games

    with st.expander('⚽ Marcatori della stagione', expanded=False):
        known = {s['name']: s['goals'] for s in st.session_state.get('season_scorers') or []}
        players = [p['name'] for p in squad if p.get('role') not in ('ALL', 'DIR')]
        base = [dict(nome=n, gol=int(known.get(n, 0))) for n in players]+[dict(nome=n, gol=g) for n, g in known.items()
                                                                           if n not in players]
        scorer_rows = st.data_editor(base or [dict(nome='', gol=0)], num_rows='dynamic', hide_index=True, width='stretch',
                                     key='wrapped_scorers',
                                     column_config={'nome': st.column_config.TextColumn('Giocatore', max_chars=27),
                                                    'gol': st.column_config.NumberColumn('Gol', min_value=0, max_value=999, step=1)})
        scorer_rows = scorer_rows.to_dict('records') if hasattr(scorer_rows, 'to_dict') else list(scorer_rows)
        if st.button('Salva i marcatori', key='wrapped_save_scorers'):
            st.session_state['season_scorers'] = [dict(name=str(r['nome']).strip().upper(), goals=int(r.get('gol') or 0))
                                                  for r in scorer_rows if str(r.get('nome') or '').strip()]
            save_week()
            st.rerun()
    scorers = [(str(r['nome']).strip().upper(), int(r.get('gol') or 0)) for r in scorer_rows if str(r.get('nome') or '').strip()]

    a, b, c = st.columns(3)
    period = a.selectbox('Periodo', list(ss.PERIODS), format_func=ss.PERIODS.get, key='wrapped_period')
    month = None
    if period == 'mese':
        months = sorted({(g['date'].year, g['date'].month) for g in games})
        if months:
            month = b.selectbox('Mese', months, index=len(months)-1, key='wrapped_month',
                                format_func=lambda m: f'{ss.MONTHS[m[1]-1].title()} {m[0]}')
    fmt = c.selectbox('Formato', FORMATS, index=FORMATS.index('Story 9:16'), key='wrapped_format')
    chosen_games = ss.select(games, period, month, st.session_state.get('csi_matches'), ours)
    numbers = ss.stats(chosen_games)
    label = ss.period_label(period, month, chosen_games)
    table = current_config('Classifica')
    mine = next((r for r in table['standings'][:table['team_count']] if ours.upper() in str(r['team']).upper()), None)
    slides_all = wr.slides(numbers, label, table, scorers, mine if period != 'mese' else None, squad)
    keys = [k for k, _ in slides_all]
    picked = st.multiselect('Slide', keys, default=keys, format_func=wr.SLIDE_NAMES.get, key='wrapped_slides')
    slides = [(k, cfg) for k, cfg in slides_all if k in picked]
    if not numbers:
        st.warning('Nessuna partita con risultato nel periodo scelto: aggiorna dal CSI o aggiungile nella tabella qui sopra.')
    else:
        st.caption(f"{numbers['played']} partite · {numbers['w']}V {numbers['d']}N {numbers['l']}P · "
                   f"gol {numbers['gf']}-{numbers['ga']} · {len(slides)} slide")
    if not slides:
        return

    _, home, _, font_bytes = resolve_assets(root, 'Classifica', table, library['assets'])
    signature = hashlib.sha256(json.dumps([[k, c] for k, c in slides]+[fmt], sort_keys=True, default=str).encode()
                               + (home or b'')+(font_bytes or b'')).hexdigest()
    cache = st.session_state.setdefault('wrapped_thumbs', {})
    if cache.get('signature') != signature:
        thumbs = []
        for key, cfg in slides:
            prepared = wr.scene(cfg, home, None, font_bytes, 1)
            prepared[0].info['format'] = fmt
            image = output_image(wr.compose(prepared, 999, False), fmt, 1)
            image.thumbnail((300, 540))
            thumbs.append((key, image))
        cache.clear()
        cache.update(signature=signature, thumbs=thumbs)
    columns = st.columns(5)
    for i, (key, image) in enumerate(cache['thumbs']):
        columns[i % 5].image(image, caption=wr.SLIDE_NAMES[key], width='stretch')

    a, b = st.columns(2)
    if a.button('Crea carosello ZIP', key='wrapped_zip', width='stretch'):
        bar = st.progress(0, text='Creo le slide...')
        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                update = progress_with_eta(bar, 'Slide')
                for i, (key, cfg) in enumerate(slides):
                    archive.writestr(f'{i+1:02d}_wrapped_{key}.png', wr.png_bytes(cfg, home, None, font_bytes, fmt, 2, 2))
                    update((i+1)/len(slides))
            st.session_state['wrapped_zip'] = {'signature': signature, 'data': buffer.getvalue()}
        finally:
            bar.empty()
    if b.button('🎬 Genera video Wrapped', key='wrapped_video', type='primary', width='stretch'):
        bar = st.progress(0, text='Preparo le slide...')
        try:
            scale = table['video_scale']
            scenes = [(wr.scene(cfg, home, None, font_bytes, scale), wr.compose) for _, cfg in slides]
            closing = sponsor_scene(table, scale, font_bytes)
            if closing:
                scenes.append(closing)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'wrapped.mp4'
                from transitions import varied
                render_sequence(scenes, varied(len(scenes)-1), path, table['fps'], 3.2, .8, fmt, scale,
                                progress_with_eta(bar), sound=table['sound'], volume=table['volume']/100,
                                mockup=table.get('mockup', False))
                st.session_state['wrapped_mp4'] = {'signature': signature, 'data': path.read_bytes()}
        except Exception as exc:
            st.error(f'Video non generato: {exc}')
        finally:
            bar.empty()
    pack = st.session_state.get('wrapped_zip')
    if pack and pack['signature'] == signature:
        st.download_button('⬇ Scarica carosello ZIP', pack['data'], file_name='flamingos_wrapped.zip', mime='application/zip',
                           type='primary', width='stretch', key='wrapped_zip_dl')
    video = st.session_state.get('wrapped_mp4')
    if video and video['signature'] == signature:
        st.video(video['data'])
        st.download_button('⬇ Scarica video Wrapped', video['data'], file_name='flamingos_wrapped.mp4', mime='video/mp4',
                           width='stretch', key='wrapped_mp4_dl')
    st.caption('Per musica, televisore e animazioni usa le impostazioni video dell\'editor Classifica.')
