"""Convocati editor: the department slides (preview, carousel ZIP, video)."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

import convocati_renderer as c
import reparti_renderer as rr
from crt_presets import output_image
from transitions import render_sequence
from ui_utils import progress_with_eta

TITLES = dict(rr.GROUPS)


def _signature(config, squad, home, font_bytes, extra=''):
    data = json.dumps([config, squad], sort_keys=True, default=str).encode()
    return hashlib.sha256(data+(home or b'')+(font_bytes or b'')+extra.encode()).hexdigest()


def show_departments(config, squad, home, font_bytes, key):
    # The audio switches live further down the Esporta tab: read their current
    # widget state so a change made just now is already used here.
    config = dict(config, **{name: st.session_state[key(name)] for name in ('sound', 'music', 'volume')
                             if key(name) in st.session_state})
    st.markdown('**Presentazione per reparti**')
    st.caption('Dopo il riepilogo, una schermata per reparto con le facce pixel: portieri, difensori, '
               'centrocampisti, attaccanti, staff. Gli avatar si creano nella Settimana, nella card La rosa.')
    slides = rr.slides(config, squad)
    missing = rr.unassigned(config, squad)
    if missing:
        st.warning('Senza ruolo, quindi in nessun reparto: '+', '.join(missing)+'. Dai loro P, D, C o A.')
    if not slides:
        st.info('Scegli i convocati (con il ruolo) nella scheda Contenuti.')
        return
    no_face = [m['name'] for _, s in slides for m in s['members'] if not m.get('look') and not m.get('avatar')]
    if no_face:
        st.caption('Ancora senza avatar: '+', '.join(no_face)+'.')
    signature = _signature(config, squad, home, font_bytes)
    # One cache entry per slide: changing a goalkeeper redraws only the goalkeepers.
    cache = st.session_state.setdefault('reparti_slide_thumbs', {})
    thumbs, keep = [], {}
    for group, slide in slides:
        slide_key = _signature(slide, [], home, font_bytes)
        image = cache.get(slide_key)
        if image is None:
            image = output_image(rr.compose(rr.scene(slide, home, None, font_bytes, 1), 999, False), config['export_format'], 1)
            image.thumbnail((360, 640))
        keep[slide_key] = image
        thumbs.append((group, image))
    st.session_state['reparti_slide_thumbs'] = keep
    columns = st.columns(3)
    for i, (group, image) in enumerate(thumbs):
        columns[i % 3].image(image, caption=TITLES[group].title(), width='stretch')

    audio = {(True, True): 'musica chiptune + suoni CRT', (False, True): 'solo musica chiptune',
             (True, False): 'solo suoni CRT', (False, False): 'muto'}[(bool(config.get('sound')), bool(config.get('music')))]
    st.caption(f'Audio del video: **{audio}**. Si cambia più sotto, in Video MP4: Musica chiptune e, in '
               'Impostazioni video, Suoni CRT.')
    a, b = st.columns(2)
    if a.button('Crea carosello ZIP', key=key('reparti_zip'), width='stretch'):
        ss = 2 if config.get('png_quality') == 'Fine' else 1
        progress = st.progress(0, text='Creo le schermate...')
        buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('01_convocati.png', c.png_bytes(config, home, None, font_bytes, config['export_format'], 2, ss))
                for i, (group, slide) in enumerate(slides):
                    archive.writestr(f'{i+2:02d}_{TITLES[group].lower()}.png',
                                     rr.png_bytes(slide, home, None, font_bytes, config['export_format'], 2, ss))
                    progress.progress((i+1)/len(slides), text=f'{TITLES[group].title()} pronta')
            st.session_state['reparti_zip'] = {'signature': signature, 'data': buffer.getvalue()}
        except Exception as exc:
            st.error(f'Carosello non creato: {exc}')
        finally:
            progress.empty()
    if b.button('Genera video presentazione', key=key('reparti_video'), width='stretch'):
        progress = st.progress(0, text='Preparo le schermate...')
        try:
            scale = config['video_scale']
            scenes = [(c.scene(config, home, None, font_bytes, scale), c.compose)]
            scenes += [(rr.scene(slide, home, None, font_bytes, scale), rr.compose) for _, slide in slides]
            from sequence_ui import sponsor_scene
            closing = sponsor_scene(config, scale, font_bytes)
            if closing:
                scenes.append(closing)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'reparti.mp4'
                render_sequence(scenes, ['channel']*(len(scenes)-1), path, config['fps'], 3.5, .9,
                                config['export_format'], scale,
                                progress_with_eta(progress),
                                sound=config['sound'], volume=config['volume']/100, mockup=config.get('mockup', False))
                st.session_state['reparti_mp4'] = {'signature': signature, 'data': path.read_bytes()}
        except Exception as exc:
            st.error(f'Video non generato: {exc}')
        finally:
            progress.empty()
    pack = st.session_state.get('reparti_zip')
    if pack and pack['signature'] == signature:
        st.download_button('⬇ Scarica carosello ZIP', pack['data'], file_name='flamingos_convocati_reparti.zip',
                           mime='application/zip', type='primary', width='stretch', key=key('reparti_zip_dl'))
    video = st.session_state.get('reparti_mp4')
    if video and video['signature'] == signature:
        st.video(video['data'])
        st.download_button('⬇ Scarica video presentazione', video['data'], file_name='flamingos_convocati_reparti.mp4',
                           mime='video/mp4', width='stretch', key=key('reparti_mp4_dl'))
