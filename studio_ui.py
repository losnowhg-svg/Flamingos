"""Streamlit workspace with explicit exports and a shared per-browser project vault."""
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
import match_result_renderer as mr
from library import save_project
from presets import PRESETS, apply_preset
from scene_styles import PATTERNS
from studio_state import BUILTIN_FONTS, RANGES, RENDERERS, defaults, sanitize_config
from studio_tools import (switch_result_format, matchday_to_result, signature,
                          png_export, export_pack, export_basename, build_caption, preflight)

ROOT = Path(__file__).resolve().parent
EDITOR = components.declare_component('flamingos_studio_editor', path=str(ROOT/'frontend'))


def show_studio(root: Path, template: str, library: dict):
    is_result = template == 'Match Result'
    is_match = template == 'Matchday Screen'
    teams = is_result or is_match
    module = RENDERERS[template]
    models = st.session_state.setdefault('studio_models', {})
    if template not in models:
        models[template] = defaults(template)
        if library.get('preferred_font'):
            models[template]['font_choice'] = library['preferred_font']
    config = models[template]
    revisions = st.session_state.setdefault('studio_revisions', {})
    revision = revisions.setdefault(template, 0)
    namespace = {'Starting 7':'s7','Matchday Screen':'md','Match Result':'mr'}[template] + f'_{revision}'
    assets = library['assets']

    def key(name):
        return namespace+'_'+name

    def replace(new_config, message=None):
        models[template] = sanitize_config(template, new_config)
        revisions[template] += 1
        st.session_state.pop('editor_event_'+template, None)
        if message:
            st.session_state['studio_notice'] = message
        st.rerun()

    def text(name, label, limit=80, area=False, help=None):
        widget = st.text_area if area else st.text_input
        config[name] = widget(label, value=str(config[name]), max_chars=limit, key=key(name), help=help)
        return config[name]

    def slider(name, label):
        lo, hi = RANGES[template][name]
        config[name] = st.slider(label, lo, hi, int(config[name]), key=key(name))

    def select(name, label, options, format_func=str):
        current = config.get(name)
        config[name] = st.selectbox(label, options, index=options.index(current) if current in options else 0,
                                    format_func=format_func, key=key(name))
        return config[name]

    def check(name, label):
        config[name] = st.checkbox(label, value=bool(config[name]), key=key(name))

    def color(name, label):
        config[name] = st.color_picker(label, config[name], key=key(name))

    def score(name, label):
        config[name] = st.number_input(label, min_value=0, max_value=99, value=int(config[name]), step=1, key=key(name))

    if st.session_state.get('studio_notice'):
        st.success(st.session_state.pop('studio_notice'))
    if st.session_state.get('studio_save_feedback'):
        message, ok = st.session_state.pop('studio_save_feedback')
        (st.success if ok else st.warning)(message)

    create_tab, export_tab, project_tab = st.tabs(['Crea la grafica', 'Esporta e pubblica', 'Progetti'])

    # Load before constructing editable widgets; save only after they have been read.
    with project_tab:
        st.subheader('Riapri un progetto')
        saved = {id_:p for id_,p in library['projects'].items() if p['template']==template}
        if saved:
            chosen = st.selectbox('Progetti di '+template, list(saved), format_func=lambda x:saved[x]['name'], key=key('open_project'))
            if st.button('Apri progetto', key=key('load_project')):
                st.session_state.setdefault('studio_project_names', {})[template] = saved[chosen]['name']
                replace(saved[chosen]['config'], 'Progetto aperto. Le modifiche successive richiedono un nuovo salvataggio.')
        else:
            st.info('Nessun progetto salvato per questo modello.')

    with create_tab:
        st.subheader(template)
        if is_result:
            old_format = config['export_format']
            fmt = st.selectbox('Formato di lavoro', list(mr.FORMATS), index=list(mr.FORMATS).index(old_format), key=key('format'))
            if fmt != old_format:
                replace(switch_result_format(config, fmt))
            st.caption('Ogni formato ha una propria impaginazione. Gli spostamenti sono conservati separatamente, anche nel progetto salvato.')
        elif is_match:
            select('export_format', 'Formato di lavoro', ['Post 1:1','Story 9:16'])
            st.caption('Post 1:1 usa il ritaglio centrale del Matchday originale. Il nuovo Match Result ha invece layout dedicati.')
        left, right = st.columns([1, 1.38], gap='large')
        with left:
            if is_result:
                with st.expander('Riparti dai dati del Matchday', expanded=False):
                    sources = {}
                    if 'Matchday Screen' in models:
                        sources['session'] = ('Matchday aperto in questa sessione', models['Matchday Screen'])
                    sources.update({pid:(p['name'],p['config']) for pid,p in library['projects'].items() if p['template']=='Matchday Screen'})
                    if sources:
                        source_id = st.selectbox('Sorgente', list(sources), format_func=lambda x:sources[x][0], key=key('source'))
                        st.caption('Copia squadre, data, competizione, stemmi, font e palette. Azzera punteggio, marcatori e MVP; ripristina i layout del risultato.')
                        confirmed = st.checkbox('Confermo la sostituzione dei dati del risultato corrente', key=key('confirm_import'))
                        if st.button('Importa dati dal Matchday', disabled=not confirmed, key=key('import_match')):
                            replace(matchday_to_result(sources[source_id][1]), 'Dati importati. Inserisci il risultato prima di esportare.')
                    else:
                        st.caption('Compila prima un Matchday o riapri un suo progetto. Non sono presenti sorgenti da importare.')

            with st.expander('1. Contenuti', expanded=True):
                if teams:
                    if is_result:
                        a, b = st.columns(2)
                        with a: score('home_score', 'Gol casa')
                        with b: score('away_score', 'Gol ospiti')
                    text('home_name', 'Squadra di casa / sinistra', 42)
                    text('away_name', 'Squadra ospite / destra', 42)
                    if is_result:
                        select('match_status', 'Stato partita', ['FINALE','INTERVALLO','DOPO SUPPLEMENTARI','DOPO I RIGORI'])
                        if config['match_status'] == 'DOPO I RIGORI':
                            st.caption('I gol sopra sono quelli prima della serie. Inserisci qui il solo esito dei rigori.')
                            a, b = st.columns(2)
                            with a: score('home_penalties', 'Rigori casa')
                            with b: score('away_penalties', 'Rigori ospiti')
                        select('team_side', 'La tua squadra gioca', ['Casa','Ospiti'])
                        check('show_outcome', 'Mostra vittoria, pareggio o sconfitta')
                    text('title', 'Titolo della grafica', 36)
                    text('date', 'Data della partita', 24)
                    if is_match:
                        text('kickoff', 'Orario', 14)
                        text('venue', 'Campo / indirizzo', 72)
                    text('competition', 'Competizione', 64, help='Nel Matchday questo dato entra nella didascalia; nel Match Result appare anche sulla grafica.')
                    text('round_label', 'Giornata / turno', 40)
                    if is_result:
                        text('scorers_home', 'Marcatori casa', 600, area=True,
                             help="Una riga per giocatore, per esempio Rossi 12', 47'. La grafica mostra al massimo sei righe per squadra.")
                        text('scorers_away', 'Marcatori ospiti', 600, area=True,
                             help='Lascia vuoto per non mostrare il blocco. Massimo sei righe nella grafica.')
                        text('mvp', 'MVP / migliore in campo', 64)
                        check('show_mvp', 'Mostra MVP sulla grafica e nella didascalia')
                        text('footer', 'Testo in fondo alla grafica', 80)
                else:
                    text('team_name', 'Nome squadra', 50)
                    text('headline', 'Titolo principale', 60)
                    text('formation_text', 'Testo del modulo', 80)
                    text('footer', 'Testo in fondo alla grafica', 80)
            if not teams:
                with st.expander('Rosa in campo: nomi e numeri', expanded=False):
                    st.caption('I ruoli sono riferimenti iniziali: puoi spostare ogni giocatore nel campo.')
                    for i, role in enumerate(r.DEFAULT_ROLES):
                        a, b = st.columns([1,3])
                        with a:
                            number = st.number_input(f'N. {i+1}',0,99,value=config['players'][i]['number'],step=1,key=key(f'number_{i}'))
                        with b:
                            name = st.text_input(role,config['players'][i]['name'],max_chars=27,key=key(f'player_{i}'))
                        config['players'][i] = {'number':int(number),'name':name}

            with st.expander('2. Preset stagionali e colori', expanded=False):
                selected_preset = st.selectbox('Preset', list(PRESETS), index=list(PRESETS).index(config.get('preset_id','flamingos')),
                    format_func=lambda x:PRESETS[x]['name'], key=key('preset_choice'))
                st.caption(PRESETS[selected_preset]['when'])
                st.caption('Cambia palette e atmosfera. Mantiene testi, punteggio, giocatori, font, stemmi e posizioni.')
                a, b = st.columns(2)
                with a:
                    if st.button('Applica preset', key=key('apply_preset'), use_container_width=True):
                        st.session_state['before_preset_'+template] = copy.deepcopy(config)
                        replace(apply_preset(template,config,selected_preset), 'Preset applicato: '+PRESETS[selected_preset]['name'])
                with b:
                    previous = st.session_state.get('before_preset_'+template)
                    if st.button('Annulla preset', disabled=previous is None, key=key('undo_preset'), use_container_width=True):
                        # Undo only the style, not content edited after the preset was applied.
                        style_fields = ('preset_id','pattern','texture','panel_color','background','accent','secondary','text_color','pitch_color','pink','cyan','yellow','white','backdrop')
                        restored = {**config, **{k:v for k,v in previous.items() if k in style_fields}}
                        st.session_state.pop('before_preset_'+template,None)
                        replace(restored,'Stile precedente ripristinato. Contenuti mantenuti.')
                if is_match:
                    select('backdrop','Fondale',['CRT originale','Studio grafico'])
                    color('pink','Colore casa'); color('cyan','Colore ospiti'); color('yellow','Colore informazioni'); color('white','Testo')
                else:
                    color('accent','Colore principale')
                    if is_result: color('secondary','Colore secondario')
                    color('text_color','Testo')
                color('background','Sfondo'); color('panel_color','Pannelli')
                if not teams: color('pitch_color','Campo')
                select('pattern','Motivo grafico',list(PATTERNS))
                slider('texture','Intensità del motivo')
                if is_match and config['backdrop']=='CRT originale':
                    st.caption('La foto CRT originale non cambia con sfondo, pannelli o motivo. Seleziona Studio grafico per usare questi controlli.')

            with st.expander('3. Font e dimensioni', expanded=False):
                fonts = [id_ for id_,a in assets.items() if a['kind']=='font']
                if config.get('font_choice') not in BUILTIN_FONTS+fonts:
                    st.warning('Font del progetto mancante: viene usato Sans Bold. Reimporta il backup per ripristinare il font.')
                selected_font = select('font_choice','Carattere',BUILTIN_FONTS+fonts,
                    lambda x:'Salvato: '+assets[x]['name'] if x in assets else x)
                config['text_style'] = 'Font salvato' if selected_font in fonts else selected_font
                font_bytes = assets[selected_font]['bytes'] if selected_font in fonts else None
                if selected_font == 'Pixel Arcade':
                    st.caption('Pixel Arcade produce un effetto a blocchi intenzionale, non bordi levigati.')
                if teams:
                    slider('title_size','Titolo'); slider('label_size','Nomi squadre'); slider('info_size','Informazioni')
                    slider('score_size' if is_result else 'vs_size','Punteggio' if is_result else 'VS')
                    if is_match:
                        text('kickoff_label','Etichetta orario',40); text('venue_label','Etichetta luogo',22)
                else:
                    slider('title_size','Nome squadra'); slider('subtitle_size','Titolo'); slider('name_size','Nomi giocatori'); slider('footer_size','Scritte inferiori')
                st.caption('Le dimensioni si adattano allo spazio disponibile. Un testo molto lungo viene ridotto per non uscire dai margini.')

            with st.expander('4. Stemmi', expanded=False):
                logos = [id_ for id_,a in assets.items() if a['kind']=='logo']
                label = lambda x:{'default':'Flamingos - incluso','none':'Segnaposto avversario'}.get(x,assets.get(x,{}).get('name',x))
                for field in (['home_logo_id','away_logo_id'] if teams else ['logo_id']):
                    if config[field] not in ['default','none']+logos:
                        st.warning('Uno stemma del progetto manca in archivio. Reimporta il backup oppure scegli un sostituto.')
                if teams:
                    select('home_logo_id','Stemma casa',['default']+logos,label)
                    select('away_logo_id','Stemma ospiti',['none','default']+logos,label)
                    slider('home_logo_size','Dimensione casa'); slider('away_logo_size','Dimensione ospiti')
                    check('home_clear_white','Rimuovi bianco esterno - casa'); check('away_clear_white','Rimuovi bianco esterno - ospiti')
                else:
                    select('logo_id','Stemma',['default']+logos,label); slider('logo_size','Dimensione stemma')
                    check('remove_white','Rimuovi bianco esterno')
                st.caption('Carica i file in Archivio nella barra laterale. Viene rimosso solo il bianco collegato agli angoli, non quello interno dello scudo.')

        default_logo = (root/'assets'/'flamingos_logo.jpg').read_bytes()
        home_id = config['home_logo_id'] if teams else config['logo_id']
        home = assets[home_id]['bytes'] if home_id in assets else default_logo
        away_id = config.get('away_logo_id')
        away = assets[away_id]['bytes'] if away_id in assets else default_logo if away_id=='default' else None
        prepared = None
        crop = m.FEED_CROP if is_match and config['export_format']=='Post 1:1' else None
        with right:
            st.subheader('Editor visuale')
            st.caption('Trascina un elemento oppure selezionalo dal menu. Blocca i livelli già sistemati; usa Centra X per allinearli.')
            try:
                prepared = module.scene(config,home,away,font_bytes,2) if teams else r.scene(config,home,font_bytes,2)
                changed = EDITOR(**r.editor_data(prepared),crop=crop,locked_layers=config.get('locked_layers',[]),key=key('canvas'),default=None)
                event_key = 'editor_event_'+template
                if isinstance(changed,dict) and changed.get('event_id') and changed['event_id'] != st.session_state.get(event_key):
                    st.session_state[event_key] = changed['event_id']
                    if isinstance(changed.get('positions'),dict):
                        updated = sanitize_config(template,{**config,'positions':changed['positions'],
                            'locked_layers':changed.get('locked_layers',config.get('locked_layers',[]))})
                        if updated['positions']!=config['positions'] or updated['locked_layers']!=config['locked_layers']:
                            config['positions'],config['locked_layers'] = updated['positions'],updated['locked_layers']
                            st.rerun()
                with st.expander('Coordinate precise e ripristino', expanded=False):
                    names = module.LAYER_NAMES if teams else {
                        'team':'Nome squadra','title':'Titolo','footer':'Scritta inferiore','formation':'Modulo','logo':'Stemma',
                        **{f'player_{i}':role for i,role in enumerate(r.DEFAULT_ROLES)}}
                    selected = st.selectbox('Elemento',list(config['positions']),format_func=lambda x:names.get(x,x),key=key('selected'))
                    current = config['positions'][selected]
                    locked = selected in config['locked_layers']
                    if locked: st.caption('Elemento bloccato: sbloccalo nel menu dell\'editor per modificarlo.')
                    with st.form(key('coordinates')):
                        a,b = st.columns(2)
                        x = a.number_input('X',0,540,value=int(current[0]),key=key(f'x_{selected}_{current[0]}'),disabled=locked)
                        max_y = mr.canvas_height(config) if is_result else 960
                        y = b.number_input('Y',0,max_y,value=int(current[1]),key=key(f'y_{selected}_{current[1]}'),disabled=locked)
                        if st.form_submit_button('Applica coordinate',disabled=locked):
                            config['positions'][selected] = [x,y]
                            st.rerun()
                    if st.button('Ripristina layout e sblocca livelli',key=key('reset')):
                        points = mr.default_positions(config['export_format']) if is_result else module.DEFAULT_POSITIONS
                        config['positions'] = {k:list(v) for k,v in points.items()}
                        config['locked_layers'] = []
                        st.rerun()
            except Exception as exc:
                st.error(f'Anteprima non disponibile: {exc}')
                st.caption('Verifica font e stemmi. I controlli del progetto restano disponibili.')
            warnings = preflight(template,config,prepared,crop)
            if warnings:
                with st.expander(f'Controllo pubblicazione: {len(warnings)} avvisi',expanded=False):
                    for warning in warnings: st.warning(warning)
            else:
                st.caption('Nessun avviso automatico. Controlla comunque punteggio, nomi e date prima di pubblicare.')
            st.caption('Anteprima di lavoro a 1080 px. Il PNG Fine viene generato solo nella scheda Esporta, non a ogni spostamento.')

    with export_tab:
        st.subheader('File pronti per i social')
        formats = config['export_format']
        h = mr.canvas_height(config)*2 if is_result else 1080 if crop else 1920
        st.caption(f'Formato attivo: {formats} / 1080 x {h} px')
        if warnings:
            st.warning(f'Ci sono {len(warnings)} avvisi da verificare nella scheda Crea. L\'esportazione resta disponibile per le bozze.')
        select('png_quality','Qualità PNG',['Fine','Standard'],lambda x:'Fine - antialias 2x' if x=='Fine' else 'Standard - 1080 px nativi')
        st.caption('Fine disegna a 2160 px di larghezza e riduce a 1080. Standard riduce il carico del server.')
        sig = signature(config,home,away,font_bytes)
        basename = export_basename(template,config)
        png_key = 'png_'+template
        if st.button('Genera / aggiorna PNG',key=key('generate_png'),type='primary'):
            try:
                with st.spinner('Generazione del PNG...'):
                    st.session_state[png_key] = {'signature':sig,'data':png_export(template,config,home,away,font_bytes)}
            except Exception as exc:
                st.error(f'PNG non generato: {exc}')
        cached = st.session_state.get(png_key)
        if cached and cached['signature']==sig:
            a,b = st.columns([1,1])
            with a: st.image(cached['data'],caption=f'PNG finale / 1080 x {h}',use_container_width=True)
            with b:
                st.download_button('Scarica PNG',cached['data'],file_name=basename+'.png',mime='image/png',type='primary',key=key('download_png'))
                st.caption('Apri il file scaricato al 100% per controllare il dettaglio.')
        elif cached:
            st.info('La grafica è cambiata: genera di nuovo il PNG. Il vecchio download non viene proposto.')
        else:
            st.caption('Genera il PNG per vedere e scaricare il file finale.')

        if teams:
            with st.expander('Pacchetto PNG multiformato',expanded=False):
                st.caption('Match Result: Story, post 4:5 e quadrato con layout dedicati. Matchday: Story e ritaglio quadrato. I layout degli altri formati vanno comunque controllati.')
                pack_sig = hashlib.sha256((sig+json.dumps(config.get('layouts',{}),sort_keys=True)).encode()).hexdigest()
                if st.button('Genera pacchetto ZIP',key=key('generate_pack')):
                    try:
                        with st.spinner('Generazione dei formati...'):
                            data,notes = export_pack(template,config,home,away,font_bytes)
                            st.session_state['pack_'+template] = {'signature':pack_sig,'data':data,'notes':notes}
                    except Exception as exc:
                        st.error(f'Pacchetto non generato: {exc}')
                pack = st.session_state.get('pack_'+template)
                if pack and pack['signature']==pack_sig:
                    st.download_button('Scarica pacchetto PNG',pack['data'],file_name=basename+'_pack.zip',mime='application/zip',key=key('download_pack'))
                    for note in pack['notes']: st.warning(note)
                elif pack:
                    st.caption('Impostazioni modificate: rigenera il pacchetto.')

        with st.expander('Video MP4',expanded=False):
            slider('duration','Durata in secondi')
            select('fps','Fotogrammi al secondo',[12,15,24,30])
            select('video_scale','Risoluzione video',[2,1],lambda x:'1080 px - Full HD' if x==2 else '540 px - rapido')
            video_sig = signature(config,home,away,font_bytes,video=True)
            if st.button('Genera video MP4',key=key('render_video')):
                progress = st.progress(0,text='Rendering video...')
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory)/'export.mp4'
                        callback = lambda fraction:progress.progress(fraction,text=f'Rendering: {round(fraction*100)}%')
                        if is_result:
                            mr.render_video(config,home,away,path,font_bytes,config['fps'],config['duration'],config['video_scale'],callback)
                        elif is_match:
                            m.render_video(config,home,away,path,font_bytes,config['fps'],config['duration'],config['export_format'],config['video_scale'],callback)
                        else:
                            r.render_video(config,home,path,font_bytes,config['fps'],config['duration'],config['video_scale'],callback)
                        st.session_state['video_'+template] = {'signature':video_sig,'data':path.read_bytes()}
                except Exception as exc:
                    st.error(f'Video non generato: {exc}')
                finally:
                    progress.empty()
            video = st.session_state.get('video_'+template)
            if video and video['signature']==video_sig:
                st.video(video['data'])
                st.download_button('Scarica MP4',video['data'],file_name=basename+'.mp4',mime='video/mp4',key=key('download_video'))
            else:
                st.caption('Il download appare dopo la generazione. Le modifiche rendono il video precedente non aggiornato.')
            st.caption('H.264 / CRF 18, senza audio. Nel solo 4:5 a 540 px, il video misura 540 x 676 per il requisito dei pixel pari del codec; Full HD è 1080 x 1350.')

        with st.expander('Didascalia social modificabile',expanded=False):
            caption_sig = hashlib.sha256(build_caption(template,config).encode()).hexdigest()[:12]
            caption_key = key('caption_'+caption_sig)
            caption = st.text_area('Bozza da copiare',value=build_caption(template,config),height=250,key=caption_key)
            st.download_button('Scarica didascalia TXT',caption.encode('utf-8'),file_name=basename+'.txt',mime='text/plain',key=key('download_caption'))
            st.caption('Bozza generata dai dati inseriti, senza AI e senza pubblicazione automatica. Cambiando i dati viene creata una nuova bozza: scarica le modifiche che vuoi conservare.')

    with project_tab:
        st.divider()
        st.subheader('Salva la grafica corrente')
        project_names = st.session_state.setdefault('studio_project_names',{})
        project_name = st.text_input('Nome del progetto',value=project_names.get(template,template+' - nuova grafica'),max_chars=80,key=key('project_name'))
        a,b = st.columns(2)
        with a:
            if st.button('Salva / aggiorna progetto',key=key('save'),type='primary'):
                if not project_name.strip():
                    st.error('Inserisci un nome.')
                else:
                    project_names[template] = project_name.strip()
                    matching = next((id_ for id_,p in library['projects'].items() if p['template']==template and p['name']==project_name.strip()),None)
                    save_project(project_name,template,sanitize_config(template,config),matching or uuid.uuid4().hex)
        with b:
            if st.button('Salva come nuova copia',key=key('duplicate')):
                name = project_name.strip() or template
                project_names[template] = name
                save_project((name[:65]+' - copia '+uuid.uuid4().hex[:4]),template,sanitize_config(template,config),uuid.uuid4().hex)
        st.caption('Lo stesso nome aggiorna il progetto esistente. La copia crea un nuovo progetto senza sovrascriverlo. Il salvataggio non è automatico.')
        if st.session_state.get('vault_command'):
            st.info('Salvataggio richiesto al browser. La conferma apparirà al completamento della scrittura.')
        st.info('Archivio locale, non cloud: resta nello stesso browser e indirizzo dell\'app. Scarica il backup prima di aggiornare il sito, cambiare dispositivo o cancellare i dati del browser.')
        st.caption('Il backup comprende i progetti e i file caricati. Le didascalie modificate e gli export PNG/MP4 vanno scaricati separatamente.')

    st.divider()
    st.caption('Flamingos Studio 1.5 / Nessun salvataggio automatico / Font e stemmi personali nel browser / Controlla sempre i dati prima di pubblicare')
