"""Shared interface for both templates, with a persistent browser asset library."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import renderer as r
import matchday_renderer as m
from library import save_project
from render_utils import layout_warnings
from studio_state import BUILTIN_FONTS, defaults, sanitize_config

ROOT = Path(__file__).resolve().parent
EDITOR = components.declare_component('flamingos_studio_editor',path=str(ROOT/'frontend'))


def show_studio(root: Path, template: str, library: dict):
    is_match = template == 'Matchday Screen'
    module = m if is_match else r
    models = st.session_state.setdefault('studio_models',{})
    if template not in models:
        models[template] = defaults(template)
        if library.get('preferred_font'):
            models[template]['font_choice'] = library['preferred_font']
    config = models[template]
    revisions = st.session_state.setdefault('studio_revisions',{})
    revision = revisions.setdefault(template,0)
    namespace = ('md' if is_match else 's7')+f'_{revision}'
    assets = library['assets']

    def key(name):
        return namespace+'_'+name

    def text(name,label,limit):
        config[name] = st.text_input(label,value=str(config[name]),max_chars=limit,key=key(name))
        return config[name]

    def slider(name,label,lo,hi,step=1):
        config[name] = st.slider(label,lo,hi,int(config[name]),step,key=key(name))
        return config[name]

    def select(name,label,options,format_func=str):
        current = config.get(name)
        index = options.index(current) if current in options else 0
        config[name] = st.selectbox(label,options,index=index,format_func=format_func,key=key(name))
        return config[name]

    def check(name,label):
        config[name] = st.checkbox(label,value=bool(config[name]),key=key(name))

    def color(name,label):
        config[name] = st.color_picker(label,config[name],key=key(name))

    # Project controls precede the model widgets, so loading can rebuild them cleanly.
    with st.expander('Progetti salvati - riapri una grafica',expanded=False):
        saved = {id_:p for id_,p in library['projects'].items() if p['template']==template}
        if saved:
            chosen = st.selectbox('Progetto',list(saved),format_func=lambda x:saved[x]['name'],key=key('open_project'))
            if st.button('Apri progetto selezionato',key=key('load_project')):
                models[template] = sanitize_config(template,saved[chosen]['config'])
                revisions[template] += 1
                st.session_state.pop('editor_event_'+template,None)
                st.rerun()
        else:
            st.caption('Nessun progetto salvato per questo modello. Il pulsante Salva progetto si trova sotto l\'editor.')
        st.caption('Un progetto conserva testi, colori, posizioni e riferimenti ai file in archivio. Il backup trasferisce tutto su un altro browser.')

    with st.sidebar:
        st.subheader('Impostazioni del modello')
        with st.expander('Testi e contenuti',expanded=True):
            if is_match:
                text('title','Titolo',36);text('date','Data della partita',24)
                text('home_name','Squadra di casa / sinistra',42);text('away_name','Avversari / destra',42)
                text('kickoff','Orario',14);text('venue','Campo / indirizzo',72)
                text('kickoff_label','Etichetta orario',40);text('venue_label','Etichetta luogo',22)
            else:
                text('team_name','Nome squadra',50);text('headline','Titolo principale',60)
                text('footer','Scritta inferiore',80);text('formation_text','Testo del modulo',80)
        with st.expander('Font e tipografia',expanded=True):
            fonts = [id_ for id_,a in assets.items() if a['kind']=='font']
            old_font = config.get('font_choice')
            if old_font not in BUILTIN_FONTS+fonts:
                st.warning('Il font del progetto non e presente in archivio. Uso Sans Bold: reimporta il backup per ripristinarlo.')
            selected_font = select('font_choice','Carattere',BUILTIN_FONTS+fonts,
                                   lambda x: ('Salvato: '+assets[x]['name']) if x in assets else x)
            config['text_style'] = 'Font salvato' if selected_font in fonts else selected_font
            font_bytes = assets[selected_font]['bytes'] if selected_font in fonts else None
            if selected_font == 'Pixel Arcade':
                st.caption('Effetto a pixel intenzionale. Scegli Sans Bold o un font salvato per bordi levigati.')
            else:
                st.caption('Testo ridisegnato alla risoluzione di uscita, non ingrandito da un\'immagine piccola.')
            if is_match:
                slider('title_size','Dimensione titolo e data',18,42)
                slider('label_size','Dimensione nomi squadre',12,30)
                slider('info_size','Dimensione informazioni',12,25)
                slider('vs_size','Dimensione VS',24,58)
            else:
                slider('title_size','Dimensione nome squadra',15,62)
                slider('subtitle_size','Dimensione titolo',12,56)
                slider('name_size','Dimensione nomi giocatori',10,35)
                slider('footer_size','Dimensione scritte inferiori',10,42)
        with st.expander('Stemmi',expanded=False):
            logos = [id_ for id_,a in assets.items() if a['kind']=='logo']
            label = lambda x: {'default':'Flamingos - incluso','none':'Segnaposto avversario'}.get(x,assets.get(x,{}).get('name',x))
            if is_match:
                select('home_logo_id','Stemma squadra di casa',['default']+logos,label)
                select('away_logo_id','Stemma avversario',['none']+logos,label)
                slider('home_logo_size','Dimensione stemma casa',60,150)
                slider('away_logo_size','Dimensione stemma avversario',60,150)
                check('home_clear_white','Rimuovi bianco esterno - casa');check('away_clear_white','Rimuovi bianco esterno - avversari')
            else:
                select('logo_id','Stemma',['default']+logos,label)
                slider('logo_size','Dimensione stemma',50,210)
                check('remove_white','Rimuovi sfondo bianco esterno')
            st.caption('Carica e riutilizza i loghi nell\'archivio qui sopra. Il bianco interno degli scudi non viene rimosso.')
        with st.expander('Palette e atmosfera',expanded=False):
            if is_match:
                color('pink','Rosa Flamingos');color('cyan','Azzurro neon');color('yellow','Giallo');color('white','Testo chiaro')
            else:
                color('accent','Colore principale');color('background','Sfondo');color('text_color','Testo')
                slider('texture','Intensita texture di sfondo',0,100)

    default_logo = (root/'assets'/'flamingos_logo.jpg').read_bytes()
    home_id = config['home_logo_id'] if is_match else config['logo_id']
    home = assets[home_id]['bytes'] if home_id in assets else default_logo
    away_id = config.get('away_logo_id')
    away = assets[away_id]['bytes'] if away_id in assets else None

    if is_match:
        st.caption('MATCHDAY SCREEN / CRT fotografico / caratteri ad alta definizione')
        if config['date']=='GG/MM/AAAA' or config['kickoff']=='HH:MM' or config['away_name']=='AVVERSARI':
            st.info('Dati di esempio: aggiorna data, orario e avversario prima di pubblicare.')
    else:
        st.caption('STARTING 7 / formazione personalizzabile / PNG e video Full HD')
        with st.expander('Rosa in campo - nomi e numeri dei 7 giocatori',expanded=False):
            columns = st.columns(2)
            for i,role in enumerate(r.DEFAULT_ROLES):
                with columns[i%2]:
                    a,b = st.columns([1,3])
                    with a:
                        number = st.number_input(f'N. {i+1}',0,99,value=config['players'][i]['number'],step=1,key=key(f'number_{i}'))
                    with b:
                        name = st.text_input(role,config['players'][i]['name'],max_chars=27,key=key(f'player_{i}'))
                    config['players'][i] = {'number':int(number),'name':name}
            numbers = [p['number'] for p in config['players']]
            if len(set(numbers)) != len(numbers):
                st.warning('Ci sono numeri di maglia duplicati. Verifica prima di esportare.')

    left,right = st.columns([1.25,1],gap='large')
    with right:
        st.subheader('Anteprima e file finali')
        if is_match:
            select('export_format','Formato',['Post 1:1','Story 9:16'])
        select('png_quality','Qualita PNG',['Fine','Standard'],
               lambda x: 'Fine - antialias 2x' if x=='Fine' else 'Standard - 1080 px nativi')
        st.caption('Fine disegna a 2160 px di larghezza e riduce a 1080. Standard disegna direttamente a 1080.')

    try:
        prepared = (m.scene(config,home,away,font_bytes,2) if is_match else r.scene(config,home,font_bytes,2))
        crop = m.FEED_CROP if is_match and config['export_format'].startswith('Post') else None
        with left:
            st.subheader('Editor visuale')
            st.caption('Trascina gli elementi. Le guide gialle delimitano il ritaglio quadrato quando e selezionato.')
            data = r.editor_data(prepared)
            changed = EDITOR(**data,crop=crop,key=key('canvas'),default=None)
            if isinstance(changed,dict) and changed.get('event_id') != st.session_state.get('editor_event_'+template):
                st.session_state['editor_event_'+template] = changed.get('event_id')
                if isinstance(changed.get('positions'),dict):
                    updated = {k:list(v) for k,v in module.normalized_positions({'positions':changed['positions']}).items()}
                    if updated != config['positions']:
                        config['positions'] = updated
                        st.rerun()
            for warning in layout_warnings(prepared,crop):
                st.warning(warning)
            with st.expander('Coordinate e ripristino',expanded=False):
                names = m.LAYER_NAMES if is_match else {**{k:k for k in r.DEFAULT_POSITIONS},
                    'team':'Nome squadra','title':'Titolo','footer':'Scritta inferiore','formation':'Modulo','logo':'Stemma',
                    **{f'player_{i}':role for i,role in enumerate(r.DEFAULT_ROLES)}}
                selected = st.selectbox('Elemento',list(module.DEFAULT_POSITIONS),format_func=lambda x:names[x],key=key('selected'))
                current = config['positions'][selected]
                with st.form(key('coordinates')):
                    a,b = st.columns(2)
                    x = a.number_input('X',0,540,value=int(current[0]),key=key(f'x_{selected}_{current[0]}'))
                    y = b.number_input('Y',0,960,value=int(current[1]),key=key(f'y_{selected}_{current[1]}'))
                    if st.form_submit_button('Applica coordinate'):
                        config['positions'][selected] = [x,y]
                        st.rerun()
                if st.button('Ripristina la disposizione iniziale',key=key('reset')):
                    config['positions'] = {k:list(v) for k,v in module.DEFAULT_POSITIONS.items()}
                    st.rerun()
            with st.expander('Salva progetto nel browser',expanded=False):
                project_name = st.text_input('Nome del progetto',value=template+' - nuova grafica',max_chars=80,key=key('project_name'))
                if st.button('Salva progetto',key=key('save'),type='primary'):
                    if not project_name.strip():
                        st.error('Inserisci un nome.')
                    else:
                        matching = next((id_ for id_,p in library['projects'].items() if p['template']==template and p['name']==project_name.strip()),None)
                        project_id = matching or uuid.uuid4().hex
                        save_project(project_name,template,copy.deepcopy(config),project_id)
                st.caption('Lo stesso nome aggiorna il progetto precedente. I progetti non si salvano automaticamente: premi Salva prima di chiudere.')
                if st.session_state.get('vault_command'):
                    st.info('Salvataggio in corso: attendi la conferma nell\'archivio.')

        with right:
            signature = hashlib.sha256(json.dumps(config,sort_keys=True).encode()+home+(away or b'')+(font_bytes or b'')).hexdigest()
            cache_key = 'png_'+template
            cached = st.session_state.get(cache_key)
            if not cached or cached['signature']!=signature:
                ss = 2 if config['png_quality']=='Fine' else 1
                image = (m.png_bytes(config,home,away,font_bytes,config['export_format'],2,ss) if is_match else r.png_bytes(config,home,font_bytes,2,ss))
                cached = {'signature':signature,'data':image}
                st.session_state[cache_key] = cached
            png = cached['data']
            dimension = '1080 x 1080' if crop else '1080 x 1920'
            st.image(png,caption='PNG finale - '+dimension,use_container_width=True)
            basename = 'flamingos_matchday' if is_match else 'flamingos_starting7'
            st.download_button('Scarica PNG - '+dimension,png,file_name=basename+'.png',mime='image/png',type='primary',use_container_width=True,key=key('download_png'))
            st.caption('Per valutare il dettaglio, apri il PNG scaricato al 100%: l\'anteprima viene adattata allo spazio disponibile.')
            st.divider()
            with st.expander('Video MP4',expanded=False):
                slider('duration','Durata in secondi',5 if is_match else 7,18)
                select('fps','Fotogrammi al secondo',[12,15,24,30])
                select('video_scale','Risoluzione video',[2,1],lambda x:'1080 px - Full HD' if x==2 else '540 px - rapido')
                video_signature = hashlib.sha256((signature+str(config['duration'])+str(config['fps'])+str(config['video_scale'])).encode()).hexdigest()
                if st.button('Genera video MP4',key=key('render_video'),use_container_width=True):
                    progress = st.progress(0,text='Rendering video...')
                    try:
                        with tempfile.TemporaryDirectory() as directory:
                            path = Path(directory)/'export.mp4'
                            callback = lambda fraction: progress.progress(fraction,text=f'Rendering: {round(fraction*100)}%')
                            if is_match:
                                m.render_video(config,home,away,path,font_bytes,config['fps'],config['duration'],config['export_format'],config['video_scale'],callback)
                            else:
                                r.render_video(config,home,path,font_bytes,config['fps'],config['duration'],config['video_scale'],callback)
                            st.session_state['video_'+template] = {'signature':video_signature,'data':path.read_bytes()}
                    except Exception as exc:
                        st.error(f'Video non generato: {exc}')
                    finally:
                        progress.empty()
                video = st.session_state.get('video_'+template)
                if video and video['signature']==video_signature:
                    st.video(video['data'])
                    st.download_button('Scarica MP4',video['data'],file_name=basename+'.mp4',mime='video/mp4',key=key('download_video'),use_container_width=True)
                else:
                    st.caption('Il download appare dopo la generazione. Le modifiche rendono il video precedente non aggiornato.')
                st.caption('H.264 / CRF 18. Audio non incluso. La risoluzione 1080 richiede piu tempo e memoria.')
    except Exception as exc:
        st.error(f'Impossibile creare la grafica: {exc}')
        st.caption('Controlla i file caricati o passa a un font predefinito. Le impostazioni rimangono disponibili.')

    st.divider()
    st.caption('Studio 1.4 - Font e stemmi nell\'archivio browser; progetti salvati esplicitamente. Scarica un backup prima di cambiare dispositivo o cancellare i dati del sito.')
