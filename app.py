"""Flamingos Studio 1.2 - Streamlit drag editor, custom font, PNG & MP4."""
import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from renderer import (
    DEFAULT_POSITIONS, DEFAULT_ROLES, W, H, editor_data,
    normalized_positions, png_bytes, render_video, scene, validate_font,
)

ROOT = Path(__file__).parent
st.set_page_config(page_title='Flamingos Studio', page_icon='🦩', layout='wide')
st.markdown('''
<style>
.stApp{background:#0c0b12;color:#f5edf2}
h1,h2,h3{color:#f04e91!important}
.stButton button[kind="primary"]{background:#e9438a;border:0}
[data-testid="stSidebar"]{background:#17121d}
</style>
''', unsafe_allow_html=True)
st.title('FLAMINGOS STUDIO')
st.caption('Pixel Arcade Edition · Editor visuale · Starting 7 · PNG + MP4')

if 'positions' not in st.session_state:
    st.session_state.positions = {k:list(v) for k,v in DEFAULT_POSITIONS.items()}
if 'canvas_reset' not in st.session_state:
    st.session_state.canvas_reset = 0

with st.sidebar:
    st.header('Personalizza')
    logo_upload = st.file_uploader('Stemma (PNG, JPG)', type=['png','jpg','jpeg'], key='logo_input')
    clear_white = st.checkbox('Rimuovi sfondo bianco dallo stemma', value=True)
    logo_size = st.slider('Dimensione stemma', min_value=50, max_value=210, value=95, step=5)
    font_upload = st.file_uploader('Carica il tuo font (.ttf o .otf)', type=['ttf','otf'], key='font_input', help='Massimo 5 MB. Il font viene usato nei PNG e MP4 esportati.')
    font_bytes = font_upload.getvalue() if font_upload else None
    if font_bytes:
        try:
            validate_font(font_bytes)
            st.success('Font valido: '+font_upload.name)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
    available_fonts = ['Pixel Arcade', 'Monospace Bold']
    if font_bytes:
        available_fonts.insert(0, 'Font caricato')
    text_style = st.selectbox('Font per tutte le scritte', available_fonts)
    st.divider()
    st.subheader('Titoli e scritte')
    team_name = st.text_input('Nome squadra','FLAMINGOS',max_chars=50)
    headline = st.text_input('Titolo principale','STARTING 7',max_chars=60)
    footer = st.text_input('Scritta in basso','CSI BRESCIA',max_chars=80)
    formation_text = st.text_input('Testo modulo','MODULO 1-1-3-1',max_chars=80)
    title_size = st.slider('Dimensione nome squadra',15,62,34)
    subtitle_size = st.slider('Dimensione titolo',12,56,27)
    footer_size = st.slider('Dimensione scritte inferiori',10,42,20)
    name_size = st.slider('Dimensione nomi giocatori',10,35,17)
    st.divider()
    st.subheader('Colori')
    accent = st.color_picker('Rosa / colore principale','#F2488B')
    background = st.color_picker('Sfondo','#0D0B14')
    text_color = st.color_picker('Testo','#F6EEF6')
    st.divider()
    st.subheader('Video')
    duration = st.slider('Durata MP4 (secondi)',7,18,9)
    fps = st.select_slider('Fotogrammi al secondo',[12,15,24],value=15)
    video_quality = st.radio('Risoluzione MP4',['540 × 960 (veloce)','1080 × 1920 (Full HD)'],index=0)
    st.caption('Il PNG viene sempre esportato a 1080 × 1920; il video Full HD richiede più tempo.')

with st.expander('Giocatori — modifica nomi e numeri',expanded=True):
    st.caption('Modulo predefinito 1-1-3-1. Trascina ciascun giocatore sul campo per modificare la disposizione.')
    columns = st.columns(2)
    players=[]
    for i, role in enumerate(DEFAULT_ROLES):
        with columns[i%2]:
            st.markdown(f'**{i+1}. {role}**')
            number_col,name_col = st.columns([1,3])
            with number_col:
                number = st.number_input('N°',0,99,value=i+1,step=1,key=f'number_{i}')
            with name_col:
                name = st.text_input('Nome',role.upper().split(' ')[0],max_chars=27,key=f'name_{i}')
            players.append(dict(number=number,name=name))

logo_bytes=(logo_upload.getvalue() if logo_upload else (ROOT/'assets'/'flamingos_logo.jpg').read_bytes())
if len(logo_bytes)>12_000_000:
    st.error('Logo troppo grande: massimo 12 MB.')
    st.stop()

config = dict(accent=accent, background=background, text_color=text_color,
              team_name=team_name,headline=headline,footer=footer,formation_text=formation_text,
              title_size=title_size,subtitle_size=subtitle_size,footer_size=footer_size,
              name_size=name_size,text_style=text_style,logo_size=logo_size,
              remove_white=clear_white,players=players,positions=st.session_state.positions)

editor_col, controls_col=st.columns([1.28,1],gap='large')
with editor_col:
    st.subheader('Editor: trascina gli elementi')
    st.caption('Clicca o tocca gli elementi e spostali sul campo. Le posizioni vengono applicate sia al PNG sia al video.')
    editor=components.declare_component('flamingos_editor',path=str(ROOT/'frontend'))
    try:
        content=editor_data(scene(config,logo_bytes,font_bytes))
        changed=editor(background=content['background'],layers=content['layers'],positions=content['positions'],
                       key=f'canvas_{st.session_state.canvas_reset}',default=None)
        if changed and isinstance(changed,dict):
            sanitized=normalized_positions({'positions':changed})
            clean={k:list(v) for k,v in sanitized.items()}
            if clean != st.session_state.positions:
                st.session_state.positions=clean
                st.rerun()
    except Exception as exc:
        st.error(f'Non riesco a mostrare l’editor: {exc}')

with controls_col:
    st.subheader('Regolazioni e download')
    if st.button('Ripristina disposizione 1-1-3-1',use_container_width=True):
        st.session_state.positions={k:list(v) for k,v in DEFAULT_POSITIONS.items()}
        st.session_state.canvas_reset+=1
        st.rerun()
    pick=st.selectbox('Elemento da regolare al pixel',list(DEFAULT_POSITIONS),
                      format_func=lambda k: {'team':'Nome squadra','title':'Titolo','footer':'Scritta in basso',
                         'formation':'Testo modulo','logo':'Stemma'}.get(k,DEFAULT_ROLES[int(k.split('_')[1])] if k.startswith('player_') else k))
    current=st.session_state.positions.get(pick,list(DEFAULT_POSITIONS[pick]))
    ca,cb=st.columns(2)
    with ca:
        px=st.number_input('Posizione X',0,W,value=int(current[0]),key=f'coord_x_{pick}_{current[0]}')
    with cb:
        py=st.number_input('Posizione Y',0,H,value=int(current[1]),key=f'coord_y_{pick}_{current[1]}')
    if st.button('Applica coordinate',use_container_width=True):
        st.session_state.positions[pick]=[px,py]
        st.session_state.canvas_reset+=1
        st.rerun()

    st.markdown('**Immagine statica**')
    try:
        png=png_bytes(config,logo_bytes,font_bytes,scale=2)
        st.image(png,caption='PNG 1080 × 1920 — tutte le posizioni visibili',width=280)
        st.download_button('Scarica immagine PNG',png,file_name='flamingos_starting7.png',
                           mime='image/png',type='primary',use_container_width=True)
    except Exception as exc:
        st.error(f'Errore PNG: {exc}')

    st.divider()
    st.markdown('**Video animato**')
    signature=hashlib.sha256((json.dumps(config,sort_keys=True)+str(duration)+str(fps)+video_quality).encode()+logo_bytes+(font_bytes or b'')).hexdigest()
    if st.button('Genera video MP4',use_container_width=True):
        with st.spinner('Creo il video, attendi il termine del rendering...'):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    output=Path(tmp)/'flamingos_starting7.mp4'
                    render_video(config,logo_bytes,output,font_bytes,fps,duration,
                                 scale=2 if video_quality.startswith('1080') else 1)
                    st.session_state['exported_video']={'signature':signature,'data':output.read_bytes()}
            except Exception as exc:
                st.error(f'Errore MP4: {exc}')
    previous=st.session_state.get('exported_video')
    if previous and previous['signature']==signature:
        st.video(previous['data'])
        st.download_button('Scarica video MP4',previous['data'],file_name='flamingos_starting7.mp4',
                           mime='video/mp4',type='primary',use_container_width=True)
    else:
        st.caption('Il video sarà generato con le impostazioni e le posizioni attuali.')

st.divider()
st.caption('Le posizioni sono conservate nella sessione browser corrente. Per condividerle o riutilizzarle, si può aggiungere un sistema di preset salvati.')
