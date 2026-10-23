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

SLUGS = {'Starting 7': 'starting7', 'Matchday Screen': 'matchday', 'Full Time': 'fulltime',
         'Convocati': 'convocati', 'Classifica': 'classifica'}


def current_config(template):
    models = st.session_state.setdefault('studio_models', {})
    if template not in models:
        models[template] = defaults(template)
    return sanitize_config(template, models[template])


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


def apply_match_everywhere(match):
    """Store the shared match and copy it into every editor."""
    match = sanitize_match(match)
    st.session_state['shared_match'] = match
    models = st.session_state.setdefault('studio_models', {})
    revisions = st.session_state.setdefault('studio_revisions', {})
    for template in DEFAULTS:
        models[template] = apply_match(template, current_config(template), match)
        revisions[template] = revisions.get(template, 0)+1
        st.session_state.pop('png_'+template, None)
    return match


def show_match_panel(library):
    """Type the fixture once; every editor receives it with one click."""
    assets = library['assets']
    match = sanitize_match(st.session_state.get('shared_match'))
    logos = [id_ for id_, a in assets.items() if a['kind'] == 'logo']
    label = lambda x: {'default': 'Flamingos - incluso', 'none': 'Segnaposto (scudo con ?)'}.get(x, assets.get(x, {}).get('name', x))
    with st.sidebar.expander('Partita della settimana', expanded=not st.session_state.get('shared_match')):
        st.caption('Scrivi i dati una volta sola, oppure usa il segnalibro Invia a Flamingos sulla pagina del girone CSI: '
                   'la prossima partita si compila da sola. Li copio in tutti gli editor.')
        with st.form('shared_match_form', border=False):
            values = {}
            values['our_name'] = st.text_input('La nostra squadra', match['our_name'], max_chars=42)
            values['opponent'] = st.text_input('Avversari', match['opponent'], max_chars=42)
            values['our_side'] = st.radio('Giochiamo', ('Casa', 'Ospiti'), index=0 if match['our_side'] == 'Casa' else 1, horizontal=True)
            a, b = st.columns(2)
            values['date'] = a.text_input('Data', match['date'], max_chars=24)
            values['round'] = b.number_input('Giornata', 1, 80, match['round'], step=1)
            a, b = st.columns(2)
            values['meeting_time'] = a.text_input('Ritrovo', match['meeting_time'], max_chars=14)
            values['kickoff'] = b.text_input('Calcio d\'inizio', match['kickoff'], max_chars=14)
            values['venue'] = st.text_input('Campo / indirizzo', match['venue'], max_chars=72)
            options = ['none', 'default']+logos
            values['opponent_logo_id'] = st.selectbox('Stemma avversari', options,
                index=options.index(match['opponent_logo_id']) if match['opponent_logo_id'] in options else 0, format_func=label)
            if st.form_submit_button('Applica a tutte le grafiche', type='primary', width='stretch'):
                values['our_logo_id'] = match['our_logo_id']
                apply_match_everywhere(values)
                st.session_state['match_applied'] = True
                st.rerun()
        if st.session_state.pop('match_applied', False):
            st.success('Dati copiati in tutte le grafiche. Layout, colori e preset restano quelli scelti.')


def _scene(root, template, library, preset_override, scale):
    config, home, away, font_bytes = resolve_assets(root, template, current_config(template), library['assets'])
    if preset_override in PRESETS:
        config = apply_preset(config, preset_override)
    module = MODULES[template]
    return module.scene(config, home, away, font_bytes, scale), module.compose


def _still(root, template, library, preset_override, format):
    prepared, compose = _scene(root, template, library, preset_override, 1)
    return output_image(compose(prepared, animated=False), format, 1)


def show_sequence(root: Path, library):
    st.subheader('SEQUENZA VIDEO')
    st.caption('Le grafiche una dopo l\'altra, unite da transizioni CRT: cambio canale, spegnimento, glitch, VHS. '
               'Ogni grafica usa i dati e il preset che hai impostato nel suo editor.')
    state = st.session_state.setdefault('sequence', {
        'items': ['Matchday Screen', 'Convocati'], 'transitions': ['channel'], 'format': 'Story 9:16',
        'hold': 4.0, 'transition_seconds': 1.0, 'fps': 24, 'scale': 2, 'preset': 'own', 'sound': True, 'volume': 80})
    state.setdefault('sound', True); state.setdefault('volume', 80)
    left, right = st.columns([1.1, 1], gap='large')
    with left:
        count = st.slider('Numero di grafiche', 2, 5, len(state['items']), key='seq_count')
        items, transitions = [], []
        for i in range(count):
            current = state['items'][i] if i < len(state['items']) else CRT_TEMPLATES[i % len(CRT_TEMPLATES)]
            items.append(st.selectbox(f'Grafica {i+1}', CRT_TEMPLATES, index=CRT_TEMPLATES.index(current), key=f'seq_item_{i}'))
            if i < count-1:
                current = state['transitions'][i] if i < len(state['transitions']) else 'channel'
                transitions.append(st.selectbox(f'Transizione {i+1} > {i+2}', TRANSITION_IDS,
                    index=TRANSITION_IDS.index(current), format_func=TRANSITIONS.get, key=f'seq_trans_{i}'))
        state['items'], state['transitions'] = items, transitions
        with st.expander('Tempi, formato e stile', expanded=False):
            state['format'] = st.selectbox('Formato', FORMATS, index=FORMATS.index(state['format']), key='seq_format')
            state['hold'] = st.slider('Secondi per grafica', 2.0, 8.0, float(state['hold']), .5, key='seq_hold')
            state['transition_seconds'] = st.slider('Durata transizione', .5, 2.0, float(state['transition_seconds']), .1, key='seq_tdur')
            state['fps'] = st.selectbox('Fotogrammi al secondo', (24, 30), index=(24, 30).index(state['fps']), key='seq_fps')
            state['scale'] = st.selectbox('Risoluzione', (2, 1), index=(2, 1).index(state['scale']),
                format_func=lambda x: '1080 px - Full HD' if x == 2 else '540 px - rapido', key='seq_scale')
            state['sound'] = st.checkbox('Suoni CRT (cambio canale, accensione, glitch, nastro, bip)', state['sound'], key='seq_sound')
            if state['sound']:
                state['volume'] = st.slider('Volume', 0, 100, int(state['volume']), key='seq_volume')
            choices = ('own',)+PRESET_IDS
            state['preset'] = st.selectbox('Preset', choices, index=choices.index(state['preset']),
                format_func=lambda x: 'Ognuna il suo preset' if x == 'own' else 'Tutte con '+PRESETS[x]['name'], key='seq_preset')
        total = state['hold']*count+state['transition_seconds']*(count-1)
        st.caption(f'Durata totale circa {total:.1f} secondi. Reel e Storie accettano fino a 60 secondi.')
    with right:
        st.markdown('**Anteprima delle transizioni**')
        try:
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
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'sequenza.mp4'
                    render_sequence(scenes, transitions, path, state['fps'], state['hold'], state['transition_seconds'],
                                    state['format'], state['scale'],
                                    lambda f: progress.progress(f, text=f'Rendering: {round(f*100)}%'),
                                    sound=state['sound'], volume=state['volume']/100)
                    st.session_state['sequence_video'] = path.read_bytes()
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                progress.empty()
        video = st.session_state.get('sequence_video')
        if video:
            st.video(video)
            st.download_button('Scarica MP4', video, file_name='flamingos_sequenza.mp4', mime='video/mp4', width='stretch')
    st.divider()
    show_kit(root, library)


def show_kit(root: Path, library):
    st.subheader('KIT PARTITA')
    st.caption('Tutte le grafiche della settimana in un file ZIP, pronte da pubblicare. Usano i dati della Partita della settimana e le modifiche fatte negli editor.')
    a, b = st.columns([2, 1])
    chosen = a.multiselect('Grafiche', list(DEFAULTS), default=['Matchday Screen', 'Convocati', 'Starting 7'], key='kit_items')
    format = b.selectbox('Formato post', FORMATS, index=1, key='kit_format',
                         help='Starting 7 ha un solo formato verticale e resta 9:16.')
    if st.button('Crea kit ZIP', key='kit_build', width='stretch', disabled=not chosen):
        progress = st.progress(0, text='Creo le grafiche...')
        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                for i, template in enumerate(chosen):
                    config, home, away, font_bytes = resolve_assets(root, template, current_config(template), library['assets'])
                    if template == 'Starting 7':
                        data = r.png_bytes(config, home, font_bytes, 2, 2)
                    else:
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
