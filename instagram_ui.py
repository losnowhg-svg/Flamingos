"""📱 Profilo e copertine: Instagram profile picture and highlight covers."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import streamlit as st

import json

import profile_pics as pp
import team_photo as tp


def _logo(root, library, key):
    logos = {id_: a for id_, a in library['assets'].items() if a['kind'] == 'logo'}
    options = ['default']+list(logos)
    choice = st.selectbox('Stemma', options, key=key,
                          format_func=lambda x: 'Flamingos - incluso' if x == 'default' else logos[x]['name'])
    return logos[choice]['bytes'] if choice in logos else (Path(root)/'assets'/'flamingos_logo.jpg').read_bytes()


def _png(image):
    out = io.BytesIO()
    image.save(out, 'PNG', compress_level=4)
    return out.getvalue()


@st.cache_data(show_spinner=False, max_entries=24)
def _profile(logo, style):
    return _png(pp.profile_picture(logo, style))


@st.cache_data(show_spinner=False, max_entries=64)
def _cover(name, style, logo, label):
    return _png(pp.highlight_cover(name, style, logo, label))


@st.cache_data(show_spinner=False, max_entries=16)
def _team_photo(squad_json, preset_id, logo, size):
    return tp.png_bytes(json.loads(squad_json), preset_id, logo, size=size)


def team_photo_png(squad, preset_id='crt', logo=None, size='Post 4:5'):
    keep = [{k: p.get(k) for k in ('name', 'number', 'role', 'look', 'avatar')} for p in squad or []]
    return _team_photo(json.dumps(keep, sort_keys=True), preset_id, logo, size)


def show_instagram(root, library):
    st.subheader('📱 PROFILO E COPERTINE')
    st.caption('La foto profilo, le copertine delle storie in evidenza e la foto di squadra pixel. Foto profilo e copertine '
               'restano dentro il cerchio che mostra Instagram.')
    profile, covers, team = st.tabs(['🦩 Foto profilo', '⭕ Copertine in evidenza', '👾 Foto di squadra'])
    with team:
        squad = st.session_state.get('squad') or library.get('squad') or []
        st.caption('Tutta la rosa in sprite pixel, divisa per reparto, con numeri e staff. Gli sprite si '
                   'personalizzano nella Settimana, card La rosa.')
        if not squad:
            st.info('Prima carica la rosa nella Settimana (Carica la rosa ufficiale).')
        else:
            logo = _logo(root, library, 'team_logo')
            a, b = st.columns(2)
            look = a.radio('Stile', ['crt', 'gameboy'], horizontal=True, key='team_style',
                           format_func={'crt': 'Arcade neon', 'gameboy': 'Game Boy'}.get)
            size = b.radio('Formato', list(tp.SIZES), horizontal=True, key='team_size')
            data = team_photo_png(squad, look, logo, size)
            st.image(data, width='stretch')
            st.download_button('⬇ Scarica foto di squadra', data, file_name=f'flamingos_squadra_{look}.png',
                               mime='image/png', type='primary', width='stretch', key='team_download')
    with profile:
        logo = _logo(root, library, 'ig_logo')
        style = st.radio('Stile', list(pp.STYLES), format_func=pp.STYLES.get, horizontal=True, key='ig_style')
        data = _profile(logo, style)
        a, b = st.columns(2)
        from PIL import Image
        a.image(pp.circle_preview(Image.open(io.BytesIO(data)), 360), caption='Come la vedi su Instagram', width='stretch')
        b.image(data, caption='Il file 1080 x 1080', width='stretch')
        st.download_button('⬇ Scarica foto profilo', data, file_name=f'flamingos_profilo_{style}.png', mime='image/png',
                           type='primary', width='stretch', key='ig_download')
        st.caption('Su Instagram: Modifica profilo > Modifica immagine > carica il file.')
    with covers:
        logo = _logo(root, library, 'cover_logo')
        a, b = st.columns([2, 1])
        style = a.radio('Stile', list(pp.STYLES), format_func=pp.STYLES.get, horizontal=True, key='cover_style')
        label = b.toggle('Scritta sotto l\'icona', True, key='cover_label')
        names = st.multiselect('Copertine', list(pp.ICONS), default=list(pp.ICONS), key='cover_names',
                               format_func=lambda n: pp.ICONS[n][0].title())
        if not names:
            st.info('Scegli almeno una copertina.')
            return
        from PIL import Image
        columns = st.columns(5)
        files = {}
        for i, name in enumerate(names):
            data = _cover(name, style, logo, label)
            files[f'{i+1:02d}_copertina_{name}.png'] = data
            preview = pp.circle_preview(Image.open(io.BytesIO(data)).crop((0, 420, 1080, 1500)), 200)
            columns[i % 5].image(preview, caption=pp.ICONS[name][0].title(), width='stretch')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename, data in files.items():
                archive.writestr(filename, data)
        st.download_button(f'⬇ Scarica {len(files)} copertine (ZIP)', buffer.getvalue(), file_name=f'flamingos_copertine_{style}.zip',
                           mime='application/zip', type='primary', width='stretch', key='cover_download')
        st.caption('Sono immagini da storia (1080 x 1920): su Instagram apri una storia in evidenza > Modifica > '
                   'Modifica copertina > scegli la foto dal rullino.')
