"""Shared match panel, transition sequences and the one-click match kit."""
from __future__ import annotations

import copy
import io
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

import renderer as r
from crt_presets import FORMATS, PRESETS, PRESET_IDS, apply_preset, output_image
from studio_state import (CRT_TEMPLATES, DEFAULTS, MODULES, apply_match, defaults,
                          sanitize_config, sanitize_match)
from transitions import TRANSITIONS, TRANSITION_IDS, preview_strip, render_sequence
from ui_utils import progress_with_eta

SLUGS = {'Calendario': 'calendario', 'Matchday Screen': 'matchday', 'Full Time': 'fulltime',
         'Convocati': 'convocati', 'Classifica': 'classifica'}


def apply_sponsor(config):
    """The sponsor is one setting for the whole studio (Settimana > Sponsor)."""
    settings = st.session_state.get('sponsor')
    if settings and 'sponsor_on' in config:
        config.update(sponsor_on=bool(settings.get('on')), sponsor_logo_id=settings.get('logo_id', 'none'),
                      sponsor_name=settings.get('name', ''))
    return config


def current_config(template):
    models = st.session_state.setdefault('studio_models', {})
    if template not in models:
        models[template] = defaults(template)
    return apply_sponsor(sanitize_config(template, models[template]))


def resolve_assets(root: Path, template, config, assets):
    """Logo and font bytes for any editor, plus the config with its text style set."""
    config = copy.deepcopy(config)
    default_logo = (root/'assets'/'flamingos_logo.jpg').read_bytes()

    def logo(logo_id):
        if logo_id == 'none':
            return None
        if logo_id in assets and assets[logo_id]['kind'] == 'logo':
            return assets[logo_id]['bytes']
        return default_logo

    if template in ('Matchday Screen', 'Full Time'):
        home, away = logo(config.get('home_logo_id', 'default')), logo(config.get('away_logo_id', 'none'))
    else:
        home, away = logo(config.get('logo_id', 'default')) or default_logo, None
    font = config.get('font_choice')
    font_bytes = None
    if font in assets and assets[font]['kind'] == 'font':
        font_bytes = assets[font]['bytes']
        config['text_style'] = 'Font salvato'
    else:
        from studio_state import BUILTIN_FONTS
        config['text_style'] = font if font in BUILTIN_FONTS else 'Sans Bold'
    return config, home, away, font_bytes


def match_event(match):
    """derby / bigmatch / ultima for the shared match, using standings and CSI calendar."""
    import themes
    from studio_state import matches_from_week
    models = st.session_state.get('studio_models', {})
    standings = models.get('Classifica', {}).get('standings', [])
    matches = st.session_state.get('csi_matches') or []
    try:
        if matches and isinstance(matches[0].get('date'), str):
            matches = matches_from_week({'matches': matches})
    except (ValueError, TypeError, KeyError):
        matches = []
    return themes.auto_event(match, standings, matches)


def apply_match_everywhere(match):
    """Store the shared match and copy it into every editor."""
    import crests
    match = crests.auto_opponent_logo(sanitize_match(match))   # known opponent: its crest, automatically
    st.session_state['shared_match'] = match
    models = st.session_state.setdefault('studio_models', {})
    revisions = st.session_state.setdefault('studio_revisions', {})
    event = match_event(match)
    for template in DEFAULTS:
        models[template] = apply_match(template, current_config(template), match, event)
        revisions[template] = revisions.get(template, 0)+1
        st.session_state.pop('png_'+template, None)
    return match


def _scene(root, template, library, preset_override, scale):
    config, home, away, font_bytes = resolve_assets(root, template, current_config(template), library['assets'])
    if preset_override in PRESETS:
        config = apply_preset(config, preset_override)
    module = MODULES[template]
    return module.scene(config, home, away, font_bytes, scale), module.compose


def sponsor_scene(base_config, scale, font_bytes=None):
    """(prepared, compose) for the sponsor thank-you slide, or None when it is off."""
    import sponsor
    settings = st.session_state.get('sponsor') or {}
    if not (settings.get('on') and settings.get('end_slide', True)):
        return None
    config = dict(base_config, sponsor_on=True, sponsor_logo_id=settings.get('logo_id'), sponsor_name=settings.get('name', ''))
    if not sponsor.active(config):
        return None
    return sponsor.scene(config, None, None, font_bytes, scale), sponsor.compose


def _still(root, template, library, preset_override, format):
    prepared, compose = _scene(root, template, library, preset_override, 1)
    prepared[0].info['format'] = format     # frames and textures follow the sequence's format
    return output_image(compose(prepared, animated=False), format, 1)


def show_sequence(root: Path, library):
    st.subheader('SEQUENZA VIDEO')
    st.caption('Le grafiche una dopo l\'altra, unite da transizioni retrò: cambio canale, glitch, VHS, pixel, '
               'cerchio, blocchi, tendina. '
               'Ogni grafica usa i dati e il preset che hai impostato nel suo editor.')
    state = st.session_state.setdefault('sequence', {
        'items': ['Matchday Screen', 'Convocati'], 'transitions': ['channel'], 'format': 'Story 9:16',
        'hold': 4.0, 'transition_seconds': 1.0, 'fps': 24, 'scale': 2, 'preset': 'own', 'sound': True, 'volume': 80,
        'mockup': False})
    state.setdefault('sound', True); state.setdefault('volume', 80); state.setdefault('mockup', False)
    left, right = st.columns([1.1, 1], gap='large')
    with left:
        count = st.slider('Numero di grafiche', 2, 5, len(state['items']), key='seq_count')
        if st.button('🎲 Transizioni tutte diverse', key='seq_shuffle', width='stretch',
                     help='Sceglie a caso una transizione diversa per ogni passaggio.'):
            import random
            from transitions import VARIED
            state['transitions'] = random.sample(VARIED, min(len(VARIED), max(1, count-1)))
            for i in range(5):
                st.session_state.pop(f'seq_trans_{i}', None)
            st.rerun()
        items, transitions = [], []
        for i in range(count):
            current = state['items'][i] if i < len(state['items']) else CRT_TEMPLATES[i % len(CRT_TEMPLATES)]
            items.append(st.selectbox(f'Grafica {i+1}', CRT_TEMPLATES, index=CRT_TEMPLATES.index(current), key=f'seq_item_{i}'))
            if i < count-1:
                current = state['transitions'][i] if i < len(state['transitions']) else 'channel'
                transitions.append(st.selectbox(f'Transizione {i+1} > {i+2}', TRANSITION_IDS,
                    index=TRANSITION_IDS.index(current), format_func=TRANSITIONS.get, key=f'seq_trans_{i}'))
        state['items'], state['transitions'] = items, transitions
        state['mockup'] = st.toggle('📺 Tutto dentro un vecchio televisore', state['mockup'], key='seq_mockup',
                                    help='La manopola dei canali gira a ogni transizione.')
        with st.expander('Tempi, formato e stile', expanded=False):
            state['format'] = st.selectbox('Formato', FORMATS, index=FORMATS.index(state['format']), key='seq_format')
            state['hold'] = st.slider('Secondi per grafica', 2.0, 8.0, float(state['hold']), .5, key='seq_hold')
            state['transition_seconds'] = st.slider('Durata transizione', .5, 2.0, float(state['transition_seconds']), .1, key='seq_tdur')
            state['fps'] = st.selectbox('Fotogrammi al secondo', (24, 30), index=(24, 30).index(state['fps']), key='seq_fps')
            state['scale'] = st.selectbox('Risoluzione', (2, 1), index=(2, 1).index(state['scale']),
                format_func=lambda x: '1080 px - Full HD' if x == 2 else '540 px - rapido', key='seq_scale')
            state['sound'] = st.checkbox('Suoni CRT (cambio canale, accensione, glitch, nastro, bip)', state['sound'], key='seq_sound')
            state['music'] = st.checkbox('Musica sotto tutta la sequenza', state.get('music', False), key='seq_music')
            if state['music']:
                import variety
                tracks = list(variety.MUSIC_TRACKS)
                state['music_track'] = st.selectbox('Brano', tracks, index=tracks.index(state.get('music_track', 'auto'))
                                                    if state.get('music_track', 'auto') in tracks else 0,
                                                    format_func=variety.MUSIC_TRACKS.get, key='seq_music_track')
                if state['music_track'] != 'auto' and st.toggle('▶ Ascolta il brano', key='seq_listen'):
                    import music
                    st.audio(music.preview_wav(state['music_track']), format='audio/wav')
            if state['sound'] or state['music']:
                state['volume'] = st.slider('Volume', 0, 100, int(state['volume']), key='seq_volume')
            choices = ('own',)+PRESET_IDS
            state['preset'] = st.selectbox('Preset', choices, index=choices.index(state['preset']),
                format_func=lambda x: 'Ognuna il suo preset' if x == 'own' else 'Tutte con '+PRESETS[x]['name'], key='seq_preset')
        total = state['hold']*count+state['transition_seconds']*(count-1)
        st.caption(f'Durata totale circa {total:.1f} secondi. Reel e Storie accettano fino a 60 secondi.')
    with right:
        st.markdown('**Anteprima delle transizioni**')
        try:
            if state['mockup']:
                import mockup as tv
                prepared, compose = _scene(root, items[0], library, state['preset'], 1)
                st.image(tv.frame(compose(prepared, 999, False), state['format'], 1, 0), caption='Così appare sul televisore',
                         width='stretch')
            stills = [_still(root, t, library, state['preset'], state['format']) for t in items]
            for i, kind in enumerate(transitions):
                st.image(preview_strip(stills[i], stills[i+1], kind, 5, 150),
                         caption=f'{items[i]} > {items[i+1]} / {TRANSITIONS[kind]}', width='stretch')
        except Exception as exc:
            st.error(f'Anteprima non disponibile: {exc}')
        if st.button('Genera video MP4', type='primary', width='stretch', key='seq_render'):
            progress = st.progress(0, text='Preparo le grafiche...')
            try:
                scenes = [_scene(root, t, library, state['preset'], state['scale']) for t in items]
                closing = sponsor_scene(current_config(items[-1]), state['scale'])
                if closing:
                    scenes.append(closing)
                    transitions = list(transitions)+['channel']
                for prepared, _ in scenes:
                    prepared[0].info['music'] = bool(state.get('music'))
                    if state.get('music_track', 'auto') != 'auto':
                        prepared[0].info['music_track'] = state['music_track']
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'sequenza.mp4'
                    render_sequence(scenes, transitions, path, state['fps'], state['hold'], state['transition_seconds'],
                                    state['format'], state['scale'],
                                    progress_with_eta(progress),
                                    sound=state['sound'], volume=state['volume']/100, mockup=state['mockup'])
                    st.session_state['sequence_video'] = path.read_bytes()
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                progress.empty()
        video = st.session_state.get('sequence_video')
        if video:
            st.video(video)
            st.download_button('Scarica MP4', video, file_name='flamingos_sequenza.mp4', mime='video/mp4', width='stretch')


def show_kit(root: Path, library):
    st.subheader('KIT PARTITA')
    st.caption('Tutte le grafiche della settimana in un file ZIP, pronte da pubblicare. Usano i dati della Partita della settimana e le modifiche fatte negli editor.')
    a, b = st.columns([2, 1])
    chosen = a.multiselect('Grafiche', list(CRT_TEMPLATES), default=['Matchday Screen', 'Convocati', 'Classifica'], key='kit_items')
    format = b.selectbox('Formato post', FORMATS, index=1, key='kit_format')
    if st.button('Crea kit ZIP', key='kit_build', width='stretch', disabled=not chosen):
        progress = st.progress(0, text='Creo le grafiche...')
        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                for i, template in enumerate(chosen):
                    config, home, away, font_bytes = resolve_assets(root, template, current_config(template), library['assets'])
                    data = MODULES[template].png_bytes(config, home, away, font_bytes, format, 2, 2)
                    archive.writestr(f'{i+1:02d}_flamingos_{SLUGS[template]}.png', data)
                    progress.progress((i+1)/len(chosen), text=f'{template} pronto')
            st.session_state['kit_zip'] = buffer.getvalue()
        except Exception as exc:
            st.error(f'Kit non creato: {exc}')
        finally:
            progress.empty()
    if st.session_state.get('kit_zip'):
        st.download_button('Scarica kit ZIP', st.session_state['kit_zip'], file_name='flamingos_kit_partita.zip',
                           mime='application/zip', type='primary', width='stretch')
