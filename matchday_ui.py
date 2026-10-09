"""Streamlit controls for the Flamingos Matchday Screen template."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from renderer import editor_data, validate_font
import matchday_renderer as m


def show_matchday(root: Path):
    st.caption('Matchday Screen CRT | Retro Pixel | PNG + MP4')
    st.info('I valori visualizzati sono un esempio, non la conferma di una partita in programma. Inserisci data e avversari corretti prima di pubblicare.')
    if 'match_positions' not in st.session_state:
        st.session_state.match_positions = {k:list(v) for k,v in m.DEFAULT_POSITIONS.items()}
    if 'match_reset' not in st.session_state:
        st.session_state.match_reset = 0

    with st.sidebar:
        st.header('MATCHDAY SCREEN')
        st.subheader('Partita')
        title=st.text_input('Titolo','MATCHDAY SCREEN',max_chars=36,key='md_title')
        date=st.text_input('Data (testo libero)','GG/MM/AAAA',max_chars=24,key='md_date')
        home_name=st.text_input('Squadra di casa / sinistra','FLAMINGOS',max_chars=42,key='md_home')
        away_name=st.text_input('Squadra avversaria / destra','AVVERSARI',max_chars=42,key='md_away')
        kickoff=st.text_input('Orario calcio di inizio','20:45',max_chars=14,key='md_kickoff')
        venue=st.text_input('Campo / indirizzo','VIA FORNACI, 82',max_chars=72,key='md_venue')
        with st.expander('Modifica etichette inferiori'):
            kickoff_label=st.text_input('Etichetta orario',"CALCIO D'INIZIO:",max_chars=40,key='md_kicklabel')
            venue_label=st.text_input('Etichetta luogo','LUOGO:',max_chars=22,key='md_venuelabel')
        st.divider()
        st.subheader('Stemmi')
        home_upload=st.file_uploader('Carica stemma Flamingos (opzionale)',type=['png','jpg','jpeg'],key='md_logo_home')
        away_upload=st.file_uploader('Carica stemma avversario',type=['png','jpg','jpeg'],key='md_logo_away')
        home_logo_size=st.slider('Dimensione stemma Flamingos',60,150,103,5,key='md_logo_size_home')
        away_logo_size=st.slider('Dimensione stemma avversario',60,150,103,5,key='md_logo_size_away')
        clear_home=st.checkbox('Rimuovi sfondo bianco stemma Flamingos',True,key='md_clear_home')
        clear_away=st.checkbox('Rimuovi sfondo bianco stemma avversario',True,key='md_clear_away')
        st.divider()
        st.subheader('Font personalizzati')
        font_upload=st.file_uploader('Carica font TTF/OTF (max 5 MB)',type=['ttf','otf'],key='md_font_upload')
        font_bytes=font_upload.getvalue() if font_upload else None
        if font_bytes:
            try:
                validate_font(font_bytes)
            except ValueError as exc:
                st.error(str(exc)); st.stop()
        font_options=['Pixel Arcade','Monospace Bold']
        if font_bytes:
            font_options.insert(0,'Font caricato')
        font_style=st.selectbox('Font per tutte le scritte',font_options,key='md_style')
        title_size=st.slider('Dimensione titolo / data',18,42,27,1,key='md_title_size')
        label_size=st.slider('Dimensione nomi',12,30,18,1,key='md_label_size')
        info_size=st.slider('Dimensione orario / luogo',12,25,16,1,key='md_info_size')
        vs_size=st.slider('Dimensione VS',24,58,43,1,key='md_vs_size')
        st.divider()
        st.subheader('Colori retro')
        pink=st.color_picker('Rosa Flamingos','#F268A8',key='md_pink')
        cyan=st.color_picker('Azzurro neon','#79DCF7',key='md_cyan')
        yellow=st.color_picker('Giallo VS / orario','#FFC963',key='md_yellow')
        white=st.color_picker('Bianco pixel','#F6F4FC',key='md_white')
        st.divider()
        st.subheader('Esportazione')
        export_format=st.radio('Formato finale',['Post 1:1','Story 9:16'],horizontal=True,key='md_export')
        duration=st.slider('Durata MP4 (secondi)',5,15,8,key='md_duration')
        fps=st.select_slider('FPS MP4',[10,12,15,24],value=15,key='md_fps')
        quality=st.radio('Risoluzione MP4',['540 px (veloce)','1080 px (Full HD)'],index=0,key='md_quality')

    home_logo=home_upload.getvalue() if home_upload else (root/'assets'/'flamingos_logo.jpg').read_bytes()
    away_logo=away_upload.getvalue() if away_upload else None
    if any(b is not None and len(b)>12_000_000 for b in (home_logo,away_logo)):
        st.error('Ogni stemma puo occupare al massimo 12 MB.')
        st.stop()

    config=dict(title=title,date=date,home_name=home_name,away_name=away_name,
                kickoff=kickoff,venue=venue,kickoff_label=kickoff_label,venue_label=venue_label,
                home_logo_size=home_logo_size,away_logo_size=away_logo_size,
                home_clear_white=clear_home,away_clear_white=clear_away,
                text_style=font_style,title_size=title_size,label_size=label_size,
                info_size=info_size,vs_size=vs_size,pink=pink,cyan=cyan,
                yellow=yellow,white=white,positions=st.session_state.match_positions)

    editor_col, downloads_col=st.columns([1.20,1.05],gap='large')
    with editor_col:
        st.subheader('Editor visuale')
        st.caption('Trascina i due stemmi, VS, data, titolo, nomi, orario e campo. Puoi regolare le coordinate anche numericamente.')
        editor=components.declare_component('flamingos_matchday_drag',path=str(root/'frontend'))
        try:
            e=editor_data(m.scene(config,home_logo,away_logo,font_bytes))
            changed=editor(background=e['background'],layers=e['layers'],positions=e['positions'],
                           key=f'match_editor_{st.session_state.match_reset}',default=None)
            if changed and isinstance(changed,dict):
                valid=m.normalized_positions({'positions':changed})
                new={k:list(v) for k,v in valid.items()}
                if new!=st.session_state.match_positions:
                    st.session_state.match_positions=new
                    st.rerun()
        except Exception as exc:
            st.error(f'Problema con editor a trascinamento: {exc}')

    with downloads_col:
        st.subheader('Anteprima e download')
        if st.button('Ripristina posizioni originali',use_container_width=True,key='md_reset'):
            st.session_state.match_positions={k:list(v) for k,v in m.DEFAULT_POSITIONS.items()}
            st.session_state.match_reset+=1
            st.rerun()
        which=st.selectbox('Elemento da regolare al pixel',list(m.DEFAULT_POSITIONS.keys()),
                           format_func=lambda x:m.LAYER_NAMES[x],key='md_selected_layer')
        current=st.session_state.match_positions.get(which,list(m.DEFAULT_POSITIONS[which]))
        a,b=st.columns(2)
        with a:
            px=st.number_input('Posizione X',0,540,value=int(current[0]),key=f'md_px_{which}_{current[0]}')
        with b:
            py=st.number_input('Posizione Y',0,960,value=int(current[1]),key=f'md_py_{which}_{current[1]}')
        if st.button('Applica coordinate',use_container_width=True,key='md_coords'):
            st.session_state.match_positions[which]=[px,py]
            st.session_state.match_reset+=1
            st.rerun()
        try:
            png=m.png_bytes(config,home_logo,away_logo,font_bytes,export_format,scale=2)
            st.image(png,caption='PNG finale - dati di esempio da personalizzare',width=340)
            st.download_button('Scarica immagine PNG',png,'flamingos_matchday.png',
                               mime='image/png',type='primary',use_container_width=True,key='md_dl_png')
        except Exception as exc:
            st.error(f'Errore esportazione PNG: {exc}')

        st.divider()
        signature=hashlib.sha256((json.dumps(config,sort_keys=True)+str(duration)+str(fps)+export_format+quality).encode('utf8')+
                                 home_logo+(away_logo or b'')+(font_bytes or b'')).hexdigest()
        if st.button('Genera video MP4',use_container_width=True,key='md_render'):
            with st.spinner('Creo il video Matchday, attendi qualche istante...'):
                try:
                    with tempfile.TemporaryDirectory() as folder:
                        path=Path(folder)/'flamingos_matchday.mp4'
                        m.render_video(config,home_logo,away_logo,path,font_bytes,int(fps),int(duration),
                                       export_format,scale=2 if quality.startswith('1080') else 1)
                        st.session_state['matchday_video']={'signature':signature,'data':path.read_bytes()}
                except Exception as exc:
                    st.error(f'Errore esportazione MP4: {exc}')
        cached=st.session_state.get('matchday_video')
        if cached and cached['signature']==signature:
            st.video(cached['data'])
            st.download_button('Scarica video MP4',cached['data'],file_name='flamingos_matchday.mp4',
                               mime='video/mp4',type='primary',use_container_width=True,key='md_dl_mp4')
        else:
            st.caption('Il video apparira qui dopo la generazione. Audio non incluso.')

    st.divider()
    st.caption('La versione 1.3 include anche Starting 7. Nessuna API AI a pagamento. I dati e le posizioni non vengono salvati tra le sessioni. I file esportati restano tuoi.')
