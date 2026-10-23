"""Five editors, eleven CRT presets, shared match data and the browser vault."""
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
import fulltime_renderer as f
import convocati_renderer as c
import classifica_renderer as k
import calendario_renderer as cal
import captions as cap
import sounds
from classifica_data import MAX_TEAMS, empty_row, fetch_standings, parse_standings, sort_rows, bookmarklet, with_rows
from library import save_project
from render_utils import layout_warnings
from studio_state import BUILTIN_FONTS, MODULES, defaults, sanitize_config
from crt_presets import PRESETS, PRESET_IDS, FORMATS, CROPS, apply_preset, preset_for_round

ROOT = Path(__file__).resolve().parent
EDITOR = components.declare_component('flamingos_studio_editor',path=str(ROOT/'frontend'))
SLUGS={'Starting 7':'starting7','Matchday Screen':'matchday','Full Time':'fulltime','Convocati':'convocati','Classifica':'classifica','Calendario':'calendario'}


def show_studio(root: Path, template: str, library: dict):
    is_match=template=='Matchday Screen'
    is_full=template=='Full Time'
    is_squad=template=='Convocati'
    is_table=template=='Classifica'
    is_cal=template=='Calendario'
    is_crt=template!='Starting 7'
    has_opponent=is_match or is_full
    module=MODULES[template]
    models=st.session_state.setdefault('studio_models',{})
    if template not in models:
        models[template]=defaults(template)
        if library.get('preferred_font'):
            models[template]['font_choice']=library['preferred_font']
    else:
        # Also fills new fields when updating an app with a session still open.
        models[template]=sanitize_config(template,models[template])
    config=models[template]
    revisions=st.session_state.setdefault('studio_revisions',{})
    revision=revisions.setdefault(template,0)
    namespace=SLUGS[template]+f'_{revision}'
    assets=library['assets']

    def key(name):return namespace+'_'+name

    def restart(updated):
        models[template]=sanitize_config(template,updated)
        revisions[template]+=1
        st.session_state.pop('editor_event_'+template,None)
        st.rerun()

    def text(name,label,limit):
        config[name]=st.text_input(label,value=str(config[name]),max_chars=limit,key=key(name))
        return config[name]

    def slider(name,label,lo,hi):
        config[name]=st.slider(label,lo,hi,int(config[name]),key=key(name))
        return config[name]

    def number(name,label,lo,hi):
        config[name]=int(st.number_input(label,min_value=lo,max_value=hi,value=int(config[name]),step=1,key=key(name)))
        return config[name]

    def select(name,label,options,format_func=str):
        options=list(options)
        current=config.get(name)
        index=options.index(current) if current in options else 0
        config[name]=st.selectbox(label,options,index=index,format_func=format_func,key=key(name))
        return config[name]

    def check(name,label):
        config[name]=st.checkbox(label,value=bool(config[name]),key=key(name))
        return config[name]

    def color(name,label):config[name]=st.color_picker(label,config[name],key=key(name))

    st.subheader(template.upper())
    st.caption({
        'Matchday Screen':'PRIMA DELLA PARTITA / Avversari, orario e campo sul tuo CRT.',
        'Starting 7':'IN CAMPO / I sette titolari, con nomi, numeri e posizioni modificabili.',
        'Full Time':'DOPO IL FISCHIO FINALE / Risultato, marcatori e rigori nella stessa identita del Matchday.',
        'Convocati':'VERSO LA PARTITA / I convocati, inclusa la panchina, e le informazioni di ritrovo.',
        'Classifica':'IL GIRONE / La classifica dal sito CSI con un tocco: noi in rosa, promozione e spareggio colorati.',
        'Calendario':'IL MESE / Le partite del mese con risultati colorati e la prossima gara in evidenza.',
    }[template])

    with st.expander('Progetti salvati - riapri una grafica',expanded=False):
        saved={id_:p for id_,p in library['projects'].items() if p['template']==template}
        if saved:
            chosen=st.selectbox('Progetto',list(saved),format_func=lambda x:saved[x]['name'],key=key('open_project'))
            if st.button('Apri progetto selezionato',key=key('load_project')):
                restart(saved[chosen]['config'])
        else:
            st.caption('Nessun progetto per questo modello. Il pulsante Salva progetto si trova sotto l\'editor.')
        st.caption('Testi, colori, posizioni, preset e riferimenti ai file restano nel progetto. I backup 1.4 sono ancora leggibili.')

    if is_full or is_squad:
        with st.expander('Riusa i dati degli altri editor',expanded=False):
            if st.button('Copia squadre e partita dal Matchday',key=key('copy_matchday')):
                source=models.get('Matchday Screen',defaults('Matchday Screen'))
                updated=copy.deepcopy(config)
                if is_full:
                    for field in ('home_name','away_name','home_logo_id','away_logo_id','home_clear_white',
                                  'away_clear_white','date','our_side'):
                        updated[field]=source[field]
                else:
                    side='home' if source.get('our_side','Casa')=='Casa' else 'away'
                    other='away' if side=='home' else 'home'
                    updated.update(team_name=source[side+'_name'],opponent=source[other+'_name'],
                                   date=source['date'],kickoff=source['kickoff'],venue=source['venue'],
                                   logo_id=source[side+'_logo_id'] if source[side+'_logo_id']!='none' else 'default')
                restart(updated)
            if is_full:
                st.caption('Copia la partita presente nella sessione. Risultato e marcatori non vengono modificati.')
            else:
                if st.button('Copia i sette giocatori da Starting 7',key=key('copy_starting')):
                    source=models.get('Starting 7',defaults('Starting 7'))
                    updated=copy.deepcopy(config)
                    for i,player in enumerate(source['players']):
                        updated['roster'][i].update(number=player['number'],name=player['name'],role=('P','D','C','C','C','C','A')[i])
                    restart(updated)
                st.caption('Legge i valori presenti nella sessione, non un progetto non aperto. I giocatori dall\'ottavo in poi e l\'orario di ritrovo restano invariati.')

    with st.sidebar:
        if is_crt:
            with st.expander('Preset CRT e rotazione di stagione',expanded=True):
                select('rotation_mode','Scelta del preset',('Manuale','Per giornata'))
                number('season_round','Giornata della stagione',1,80)
                if config['rotation_mode']=='Per giornata':
                    target=preset_for_round(config['season_round'])
                    st.caption('Giornata '+str(config['season_round'])+' / '+PRESETS[target]['name'])
                else:
                    target=st.selectbox('Oggetto / preset',PRESET_IDS,index=PRESET_IDS.index(config['preset_id']),
                                        format_func=lambda x:PRESETS[x]['name'],key=key('preset_picker'))
                if target!=config['preset_id']:
                    restart(apply_preset(config,target))
                st.caption(PRESETS[config['preset_id']]['description'])
                if st.button('Preset successivo',key=key('next_preset'),width='stretch'):
                    target=PRESET_IDS[(PRESET_IDS.index(config['preset_id'])+1)%len(PRESET_IDS)]
                    updated=apply_preset(config,target);updated['rotation_mode']='Manuale'
                    restart(updated)
                if st.button('Abbina il font del preset',key=key('preset_font'),width='stretch'):
                    updated=copy.deepcopy(config);updated['font_choice']=PRESETS[config['preset_id']]['font']
                    restart(updated)
                st.caption(f'Il cambio di preset modifica solo cornice e palette. Testi, risultati, stemmi, font e posizioni rimangono tuoi. La rotazione riparte ogni {len(PRESET_IDS)} giornate.')
        st.subheader('Impostazioni del modello')
        with st.expander('Testi e contenuti',expanded=True):
            if has_opponent:
                text('title','Titolo',36);text('date','Data della partita',24)
                text('home_name','Squadra di casa / sinistra',42);text('away_name','Squadra ospite / destra',42)
                select('our_side','La nostra squadra e',('Casa','Ospiti'))
                if is_match:
                    text('kickoff','Orario',14);text('venue','Campo / indirizzo',72)
                    text('kickoff_label','Etichetta orario',40);text('venue_label','Etichetta luogo',22)
                else:
                    text('competition','Competizione / giornata',42)
                    check('show_result','Mostra esito automatico della nostra squadra')
            elif is_table:
                text('title','Titolo',36);text('group','Girone / campionato',48)
                text('round_label','Giornata',36);text('our_team','La nostra squadra (evidenziata)',34)
                select('table_detail','Colonne della tabella',k.DETAILS,
                       lambda x:'Completa - G V N P GF GS PT' if x=='Completa' else 'Compatta - G, differenza reti, PT')
                check('show_zones','Colora le zone promozione e spareggio')
                if config['show_zones']:
                    a,b=st.columns(2)
                    with a:number('promo_count','Posti promozione',0,8)
                    with b:number('playoff_count','Posti spareggio',0,8)
                    a,b=st.columns(2)
                    with a:text('promo_label','Etichetta 1',20)
                    with b:text('playoff_label','Etichetta 2',20)
            elif is_cal:
                text('title','Titolo',36);text('month_label','Mese',30);text('our_team','La nostra squadra',34)
            elif is_squad:
                text('title','Titolo',36);text('team_name','Nome squadra',50)
                text('opponent','Avversari / partita',42);text('date','Data',24)
                text('meeting_time','Ritrovo',14);text('kickoff','Calcio di inizio',14)
                text('venue','Campo / indirizzo',72)
            else:
                text('team_name','Nome squadra',50);text('headline','Titolo principale',60)
                text('footer','Scritta inferiore',80);text('formation_text','Testo del modulo',80)
        with st.expander('Font e tipografia',expanded=False):
            fonts=[id_ for id_,a in assets.items() if a['kind']=='font']
            if config.get('font_choice') not in BUILTIN_FONTS+fonts:
                st.warning('Il font salvato non e in archivio. Uso Sans Bold: reimporta il backup per ripristinarlo.')
            selected_font=select('font_choice','Carattere',BUILTIN_FONTS+fonts,
                                lambda x:('Salvato: '+assets[x]['name']) if x in assets else x)
            config['text_style']='Font salvato' if selected_font in fonts else selected_font
            font_bytes=assets[selected_font]['bytes'] if selected_font in fonts else None
            if selected_font=='CRT Terminal':
                st.caption('Alfabeto pixel 5 x 7: monospaziato, da terminale. Include numeri, punteggiatura e accenti italiani.')
            elif selected_font=='CRT Scoreboard':
                st.caption('Alfabeto pixel compatto 3 x 5, con proporzioni allargate da tabellone. Distinto da CRT Terminal.')
            elif selected_font=='Pixel Arcade':
                st.caption('Effetto a blocchi della versione precedente. I due nuovi font CRT sono disegnati direttamente in pixel.')
            else:
                st.caption('Caratteri ridisegnati alla risoluzione di uscita. I font personali si caricano dall\'archivio.')
            if is_match:
                slider('title_size','Dimensione titolo e data',18,42)
                slider('label_size','Dimensione nomi squadre',12,30)
                slider('info_size','Dimensione informazioni',12,25)
                slider('vs_size','Dimensione VS',24,58)
            elif is_full:
                slider('title_size','Dimensione titolo',18,42)
                slider('score_size','Dimensione risultato',30,76)
                slider('label_size','Dimensione squadre',10,24)
                slider('info_size','Dimensione competizione e data',9,20)
                slider('scorer_size','Dimensione marcatori',8,16)
                slider('result_size','Dimensione esito',10,24)
            elif is_cal:
                slider('title_size','Dimensione titolo',16,34)
                slider('info_size','Dimensione mese',8,16)
            elif is_table:
                slider('title_size','Dimensione titolo',16,34)
                slider('info_size','Dimensione girone e giornata',8,16)
                slider('table_size','Dimensione testo tabella',7,14)
            elif is_squad:
                slider('title_size','Dimensione titolo',18,36)
                slider('team_size','Dimensione squadra',9,20)
                slider('name_size','Dimensione convocati',9,16)
                slider('info_size','Dimensione informazioni',8,18)
            else:
                slider('title_size','Dimensione nome squadra',15,62)
                slider('subtitle_size','Dimensione titolo',12,56)
                slider('name_size','Dimensione nomi giocatori',10,35)
                slider('footer_size','Dimensione scritte inferiori',10,42)
            st.caption('Le dimensioni vengono ridotte quando necessario per non tagliare le righe. I font CRT trasformano il testo in maiuscolo.')
        with st.expander('Stemmi',expanded=False):
            logos=[id_ for id_,a in assets.items() if a['kind']=='logo']
            label=lambda x:{'default':'Flamingos - incluso','none':'Segnaposto (scudo con ?)'}.get(x,assets.get(x,{}).get('name',x))
            fields=('home_logo_id','away_logo_id') if has_opponent else ('logo_id',)
            for field in fields:
                if config.get(field) not in ['default','none']+logos:
                    st.warning('Uno stemma del progetto manca in archivio: viene sostituito. Reimporta il backup per recuperarlo.')
            if has_opponent:
                select('home_logo_id','Stemma squadra di casa',['default','none']+logos,label)
                select('away_logo_id','Stemma squadra ospite',['none','default']+logos,label)
                slider('home_logo_size','Dimensione stemma casa',45 if is_full else 60,85 if is_full else 150)
                slider('away_logo_size','Dimensione stemma ospiti',45 if is_full else 60,85 if is_full else 150)
                check('home_clear_white','Rimuovi bianco esterno - casa')
                check('away_clear_white','Rimuovi bianco esterno - ospiti')
            else:
                select('logo_id','Stemma',['default']+logos,label)
                slider('logo_size','Dimensione stemma',*((30,58) if is_squad else (26,56) if (is_table or is_cal) else (50,210)))
                check('remove_white','Rimuovi sfondo bianco esterno')
            st.caption('Stemmi riutilizzabili dall\'archivio. Il bianco interno degli scudi viene mantenuto.')
        with st.expander('Palette e atmosfera',expanded=False):
            if is_crt:
                color('pink','Rosa / colore casa');color('cyan','Neon / colore ospiti')
                color('yellow','Accento risultato');color('white','Testo chiaro')
                if is_table and config['show_zones']:
                    color('promo_color','Zona promozione');color('playoff_color','Zona spareggio')
                slider('brightness','Luminosita per Instagram',0,100)
                st.caption('Schiarisce sfondo e cornice senza toccare i testi. 55 e il valore consigliato per il feed; 0 riproduce la versione 1.5, piu scura.')
                slider('scanlines','Intensita scanline CRT',0,60)
            else:
                color('accent','Colore principale');color('background','Sfondo');color('text_color','Testo')
                slider('texture','Intensita texture di sfondo',0,100)

    default_logo=(root/'assets'/'flamingos_logo.jpg').read_bytes()
    home_id=config['home_logo_id'] if has_opponent else config['logo_id']
    home=assets[home_id]['bytes'] if home_id in assets else None if home_id=='none' else default_logo
    away_id=config.get('away_logo_id')
    away=default_logo if away_id=='default' else assets[away_id]['bytes'] if away_id in assets else None

    if is_crt:
        catalog=root/'assets'/'preset_catalog.jpg'
        if catalog.exists():
            with st.expander(f'Catalogo dei {len(PRESET_IDS)} preset CRT',expanded=False):
                st.image(str(catalog),caption='Esempi di stile. Scegli il preset nella barra laterale: i dati della tua grafica non cambiano.',width='stretch')
        if config.get('date')=='GG/MM/AAAA' or config.get('kickoff')=='HH:MM' or config.get('away_name',config.get('opponent'))=='AVVERSARI':
            st.info('Dati di esempio: aggiorna la partita prima di pubblicare.')

    if is_full:
        a,b=st.columns(2)
        with a:number('home_score',config['home_name']+' - gol',0,99)
        with b:number('away_score',config['away_name']+' - gol',0,99)
        with st.expander('Marcatori e rigori',expanded=True):
            check('show_scorers','Mostra marcatori')
            if config['show_scorers']:
                a,b=st.columns(2)
                for side,col in (('home',a),('away',b)):
                    with col:
                        field=side+'_scorers'
                        config[field]=st.text_area('Marcatori '+config[side+'_name'],value=config[field],height=122,
                            max_chars=1200,key=key(field),placeholder="ROSSI 12', 38'\nBIANCHI 44'")
                        if len(f.scorer_lines(config[field]))>6:
                            st.warning('Massimo 6 righe per squadra: le righe successive non entrano nella grafica. Raggruppa i gol dello stesso giocatore.')
                st.caption('Una riga per marcatore; puoi indicare piu minuti sulla stessa riga. I nomi sono testo libero: il totale dei gol non viene calcolato dai marcatori.')
            check('show_penalties','Partita decisa ai rigori')
            if config['show_penalties']:
                a,b=st.columns(2)
                with a:number('home_penalties','Rigori realizzati - casa',0,99)
                with b:number('away_penalties','Rigori realizzati - ospiti',0,99)
                if config['home_score']!=config['away_score']:
                    st.warning('Il punteggio prima dei rigori non e pari. La riga dei rigori non viene esportata finche non correggi il risultato.')
                elif config['home_penalties']==config['away_penalties']:
                    st.warning('I rigori sono ancora in parita: verifica il risultato finale.')
        if config['show_result']:st.caption('Esito per la nostra squadra ('+config['our_side'].lower()+'): '+f.result_text(config))

    if is_cal:
        with st.expander('Partite del mese',expanded=True):
            matches=st.session_state.get('csi_matches') or []
            if matches:
                from csi_page import fixtures_for_month, MONTHS
                months=sorted({(m['date'].year,m['date'].month) for m in matches})
                today=__import__('datetime').date.today()
                current=(today.year,today.month) if (today.year,today.month) in months else months[0]
                a,b=st.columns([2,1])
                with a:chosen=st.selectbox('Mese dal sito CSI',months,index=months.index(current),
                                           format_func=lambda x:f'{MONTHS[x[1]-1].capitalize()} {x[0]}',key=key('cal_month'))
                with b:
                    st.write('')
                    if st.button('Riempi dal sito',key=key('cal_fill'),type='primary',width='stretch'):
                        rows=fixtures_for_month(matches,config['our_team'],*chosen,limit=cal.MAX_FIXTURES)
                        updated=copy.deepcopy(config)
                        updated['fixtures']=rows+[cal.empty_fixture() for _ in range(len(rows),cal.MAX_FIXTURES)]
                        updated['fixture_count']=max(1,len(rows))
                        updated['month_label']=f'{MONTHS[chosen[1]-1]} {chosen[0]}'
                        restart(updated)
            else:
                st.caption('Usa il segnalibro Invia a Flamingos sulla pagina del girone (scheda della Classifica): '
                           'le partite arrivano qui e scegli il mese. Oppure compilale qui sotto.')
            number('fixture_count','Numero di partite',1,cal.MAX_FIXTURES)
            count=config['fixture_count']
            columns={'date':st.column_config.TextColumn('Data',max_chars=8,help='GG/MM'),
                     'day':st.column_config.TextColumn('Giorno',max_chars=3,help='LUN, MAR, MER...'),
                     'opponent':st.column_config.TextColumn('Avversari',max_chars=30),
                     'side':st.column_config.SelectboxColumn('Casa/Trasf.',options=['C','T'],required=True),
                     'time':st.column_config.TextColumn('Ora',max_chars=8),
                     'score':st.column_config.TextColumn('Risultato',max_chars=7,help='Gol casa-gol ospiti, es. 3-1. Vuoto se non giocata.')}
            edited=st.data_editor([dict(f) for f in config['fixtures'][:count]],column_config=columns,
                                  hide_index=True,num_rows='fixed',key=key('fixtures_editor'),width='stretch')
            rows=edited.to_dict('records') if hasattr(edited,'to_dict') else list(edited)
            for i,row in enumerate(rows[:count]):
                clean=cal.empty_fixture()
                for field,limit in (('date',8),('day',3),('opponent',30),('time',8),('score',7)):
                    clean[field]=str(row.get(field) or '')[:limit]
                clean['side']=row.get('side') if row.get('side') in ('C','T') else 'C'
                config['fixtures'][i]=clean
            st.caption('C = in casa, T = in trasferta. Il risultato va scritto come sul tabellone (casa-ospiti): '
                       'la grafica colora vittoria, pareggio e sconfitta dal nostro punto di vista. La prima partita senza risultato e la NEXT.')
            if any(f['opponent'].startswith('AVVERSARI ') for f in cal.active_fixtures(config)):
                st.info('Il calendario contiene ancora partite di esempio.')

    if is_table:
        def load_rows(rows,message):
            st.session_state['standings_message']=message
            restart(with_rows(config,rows))

        # Automatic refresh: once per session, when the page opens with a link set.
        auto_key='standings_auto_'+config.get('source_url','')
        if config.get('auto_update') and config.get('source_url') and not st.session_state.get(auto_key):
            st.session_state[auto_key]=True
            with st.spinner('Aggiorno la classifica dal CSI...'):
                try:
                    rows=fetch_standings(config['source_url'])
                    if config['team_count']!=len(rows) or rows!=[dict(r) for r in config['standings'][:len(rows)]]:
                        load_rows(rows,f'Classifica aggiornata in automatico: {len(rows)} squadre.')
                except ValueError as exc:
                    st.session_state['standings_auto_error']=str(exc)

        with st.expander('Dati della classifica',expanded=True):
            if st.session_state.get('standings_auto_error'):
                st.warning('Aggiornamento automatico non riuscito: '+st.session_state['standings_auto_error'])
            if st.session_state.get('standings_message'):
                st.success(st.session_state.pop('standings_message'))
            if st.session_state.get('standings_import_error'):
                st.error('Il segnalibro ha inviato una pagina senza classifica leggibile: '+st.session_state.pop('standings_import_error'))
            bookmark,paste,manual,link=st.tabs(['Dal sito CSI (un tocco)','Incolla la tabella','Modifica a mano','Lettura dal server'])
            with bookmark:
                code=bookmarklet()
                st.markdown('**Segnalibro "Invia a Flamingos"**: sulla pagina del girone su CSI LIVE lo tocchi e '
                            'l\'app si apre con **classifica, prossima partita e calendario del mese** gia compilati. '
                            'Funziona su Mac, iPhone e iPad.')
                st.info('Versione 2 del segnalibro: se avevi installato la prima, sostituiscila con questa una volta sola. '
                        'Da ora in poi i miglioramenti alla lettura arrivano senza reinstallare.')
                components.html('''<style>a{display:inline-block;padding:10px 18px;border-radius:9px;background:#e95396;color:#110d14;
                    font:600 15px system-ui,sans-serif;text-decoration:none;cursor:grab}p{color:#bca9c5;font:13px system-ui,sans-serif;margin:8px 0 0}</style>
                    <a href="'''+code.replace('"','&quot;')+'''" onclick="return false">Invia a Flamingos</a>
                    <p>Mac: trascina questo pulsante nella barra dei Preferiti di Safari o Chrome.</p>''',height=86)
                with st.expander('Installazione su iPhone o iPad, o se il trascinamento non va'):
                    st.markdown('1. Aggiungi ai segnalibri una pagina qualsiasi (anche questa) e chiamala **Invia a Flamingos**.\n'
                                '2. Apri *Modifica segnalibri*, tocca il nuovo segnalibro e sostituisci l\'indirizzo con il codice qui sotto.\n'
                                '3. Sulla pagina del girone apri i segnalibri e tocca **Invia a Flamingos**.')
                    st.code(code,language=None,wrap_lines=True)
                st.caption('Il segnalibro legge solo la tabella che il tuo browser sta mostrando e la passa all\'app: '
                           'non usa account, password o altri dati. Pagina del vostro girone: CSI LIVE, Serie C Girone D.')
                st.link_button('Apri la classifica del Girone D su CSI LIVE',config['source_url'] or 'https://live.centrosportivoitaliano.it',width='stretch')
            with link:
                text('source_url','Link del girone su CSI LIVE (live.centrosportivoitaliano.it)',300)
                check('auto_update','Prova a leggere dal server quando apro la pagina')
                if st.button('Leggi dal server',key=key('fetch')):
                    with st.spinner('Leggo la classifica...'):
                        try:
                            rows=fetch_standings(config['source_url'])
                            st.session_state.pop('standings_auto_error',None)
                            load_rows(rows,f'Classifica aggiornata dal link: {len(rows)} squadre.')
                        except ValueError as exc:
                            st.error(str(exc))
                st.caption('CSI LIVE e Tuttocampo oggi rifiutano le letture dal server dell\'app (errore 403): '
                           'usa il segnalibro. Questo link resta utile per il pulsante Apri la classifica e per altri siti.')
            with paste:
                pasted=st.text_area('Testo della classifica',height=180,key=key('paste'),
                    placeholder='Apri la classifica, seleziona la tabella dalla prima squadra all\'ultima, copia e incolla qui.')
                if st.button('Leggi la tabella incollata',key=key('parse')):
                    try:
                        rows=parse_standings(pasted)
                        load_rows(rows,f'Tabella letta: {len(rows)} squadre. Controlla i numeri nella scheda Modifica a mano.')
                    except ValueError as exc:
                        st.error(str(exc))
                st.caption('Va bene il testo copiato da Tuttocampo, dal sito CSI o da un foglio di calcolo. Riconosco da solo l\'ordine delle colonne.')
            with manual:
                number('team_count','Numero di squadre',2,MAX_TEAMS)
                count=config['team_count']
                columns={'pos':st.column_config.NumberColumn('Pos',min_value=1,max_value=99,step=1,width='small'),
                         'team':st.column_config.TextColumn('Squadra',max_chars=34),
                         **{f:st.column_config.NumberColumn(f.upper(),min_value=0,max_value=999,step=1,width='small')
                            for f in ('pt','g','v','n','p','gf','gs')}}
                edited=st.data_editor([dict(r) for r in config['standings'][:count]],column_config=columns,
                                      hide_index=True,num_rows='fixed',key=key('table_editor'),width='stretch')
                rows=edited.to_dict('records') if hasattr(edited,'to_dict') else list(edited)
                for i,row in enumerate(rows[:count]):
                    clean=empty_row(i+1)
                    for field in clean:
                        value=row.get(field,clean[field])
                        try:clean[field]=str(value or '')[:34] if field=='team' else max(0,min(999,int(value or 0)))
                        except (TypeError,ValueError):pass
                    config['standings'][i]=clean
                if st.button('Ordina per punti e differenza reti',key=key('sort')):
                    load_rows(sort_rows(config['standings'][:count]),'Classifica riordinata.')
            active=k.active_rows(config)
            wrong=[r['team'] for r in active if r['v']+r['n']+r['p']!=r['g']]
            if wrong:st.warning('Vinte + pareggiate + perse non torna con le giocate per: '+', '.join(wrong[:4])+'.')
            if not any(k.is_ours(r['team'],config['our_team']) for r in active):
                st.info('La tua squadra non e in tabella: controlla il nome in Testi e contenuti per evidenziarla.')
            if any(r['team'].startswith('SQUADRA ') for r in active):
                st.info('La classifica contiene ancora squadre di esempio.')

    if is_squad:
        with st.expander('Rosa convocata - titolari e panchina',expanded=True):
            number('roster_count','Numero di convocati',7,18)
            st.caption('P = portiere, D = difensore, C = centrocampista, A = attaccante. L\'asterisco * nella grafica identifica il capitano. I posti nascosti non vengono cancellati.')
            columns=st.columns(2)
            for i,entry in enumerate(config['roster'][:config['roster_count']]):
                with columns[i%2]:
                    a,b,d=st.columns([1,3,1])
                    with a:entry['number']=int(st.number_input(f'N. {i+1}',0,99,value=entry['number'],step=1,key=key(f'roster_number_{i}')))
                    with b:entry['name']=st.text_input(f'Giocatore {i+1}',entry['name'],max_chars=27,key=key(f'roster_name_{i}'))
                    with d:entry['role']=st.selectbox(f'Ruolo {i+1}',c.ROLES,index=c.ROLES.index(entry['role']),key=key(f'roster_role_{i}'))
                    entry['captain']=st.checkbox(f'Capitano - giocatore {i+1}',value=entry['captain'],key=key(f'captain_{i}'))
            active=config['roster'][:config['roster_count']]
            if len({x['number'] for x in active})<len(active):st.warning('Numeri di maglia duplicati tra i convocati.')
            if sum(x['captain'] for x in active)>1:st.warning('Hai selezionato piu di un capitano.')
            if any(not x['name'].strip() for x in active):st.warning('Uno o piu convocati non hanno un nome.')
            if any(x['name'].startswith('GIOCATORE ') for x in active):st.info('La rosa contiene ancora nomi di esempio.')
            if config['meeting_time']=='HH:MM':st.info('Completa l\'orario di ritrovo.')
    elif not is_crt:
        with st.expander('Rosa in campo - nomi e numeri dei 7 giocatori',expanded=False):
            columns=st.columns(2)
            for i,role in enumerate(r.DEFAULT_ROLES):
                with columns[i%2]:
                    a,b=st.columns([1,3])
                    with a:number_value=st.number_input(f'N. {i+1}',0,99,value=config['players'][i]['number'],step=1,key=key(f'number_{i}'))
                    with b:name=st.text_input(role,config['players'][i]['name'],max_chars=27,key=key(f'player_{i}'))
                    config['players'][i]={'number':int(number_value),'name':name}
            if len({p['number'] for p in config['players']})<7:st.warning('Ci sono numeri di maglia duplicati.')

    left,right=st.columns([1.25,1],gap='large')
    with right:
        st.subheader('Anteprima e file finali')
        if is_crt:select('export_format','Formato',FORMATS)
        select('png_quality','Qualita PNG',('Fine','Standard'),
               lambda x:'Fine - antialias 2x' if x=='Fine' else 'Standard - 1080 px nativi')
        st.caption('Fine compone a 2160 px e riduce a 1080. Standard lavora a 1080 px, utile anche per un pixel piu netto.')

    try:
        prepared=module.scene(config,home,away,font_bytes,2) if is_crt else r.scene(config,home,font_bytes,2)
        crop=CROPS[config['export_format']] if is_crt else None
        with left:
            st.subheader('Editor visuale')
            st.caption('Trascina testi, stemmi e giocatori. Le guide gialle delimitano il formato di esportazione; non finiscono nel file.')
            changed=EDITOR(**r.editor_data(prepared),crop=crop,key=key('canvas'),default=None)
            if isinstance(changed,dict) and changed.get('event_id')!=st.session_state.get('editor_event_'+template):
                st.session_state['editor_event_'+template]=changed.get('event_id')
                if isinstance(changed.get('positions'),dict):
                    updated={k:list(v) for k,v in module.normalized_positions({'positions':changed['positions']}).items()}
                    if updated!=config['positions']:
                        config['positions']=updated;st.rerun()
            for warning in layout_warnings(prepared,crop):st.warning(warning)
            with st.expander('Coordinate e ripristino',expanded=False):
                names={layer.id:layer.label for layer in prepared[1]}
                selected=st.selectbox('Elemento',list(names),format_func=lambda x:names[x],key=key('selected'))
                current=config['positions'][selected]
                with st.form(key('coordinates')):
                    a,b=st.columns(2)
                    x=a.number_input('X',0,540,value=int(current[0]),key=key(f'x_{selected}_{current[0]}'))
                    y=b.number_input('Y',0,960,value=int(current[1]),key=key(f'y_{selected}_{current[1]}'))
                    if st.form_submit_button('Applica coordinate'):
                        config['positions'][selected]=[x,y];st.rerun()
                if st.button('Ripristina la disposizione iniziale',key=key('reset')):
                    config['positions']={k:list(v) for k,v in module.DEFAULT_POSITIONS.items()};st.rerun()
            with st.expander('Salva progetto nel browser',expanded=False):
                project_name=st.text_input('Nome del progetto',value=template+' - nuova grafica',max_chars=80,key=key('project_name'))
                if st.button('Salva progetto',key=key('save'),type='primary'):
                    if not project_name.strip():st.error('Inserisci un nome.')
                    else:
                        matching=next((id_ for id_,p in library['projects'].items() if p['template']==template and p['name']==project_name.strip()),None)
                        save_project(project_name,template,copy.deepcopy(config),matching or uuid.uuid4().hex)
                st.caption('Lo stesso nome aggiorna il progetto precedente. Premi Salva prima di chiudere: non c\'e salvataggio automatico.')
                if st.session_state.get('vault_command'):st.info('Salvataggio in corso: attendi la conferma nell\'archivio.')
        with right:
            # Video-only controls are excluded from the PNG cache key.
            signature_config={k:v for k,v in config.items() if k not in ('duration','fps','video_scale','sound','volume')}
            signature=hashlib.sha256(json.dumps(signature_config,sort_keys=True).encode()+(home or b'')+(away or b'')+(font_bytes or b'')).hexdigest()
            cache_key='png_'+template;cached=st.session_state.get(cache_key)
            if not cached or cached['signature']!=signature:
                ss=2 if config['png_quality']=='Fine' else 1
                image=module.png_bytes(config,home,away,font_bytes,config['export_format'],2,ss) if is_crt else r.png_bytes(config,home,font_bytes,2,ss)
                cached={'signature':signature,'data':image};st.session_state[cache_key]=cached
            png=cached['data']
            height={'Post 1:1':1080,'Post 4:5':1350,'Story 9:16':1920}[config['export_format']]
            dimension=f'1080 x {height}'
            st.image(png,caption='PNG finale - '+dimension,width='stretch')
            basename='flamingos_'+SLUGS[template]
            st.download_button('Scarica PNG - '+dimension,png,file_name=basename+'.png',mime='image/png',type='primary',width='stretch',key=key('download_png'))
            st.caption('Apri il PNG al 100% per valutare il dettaglio. I formati Post sono ritagli centrali della stessa composizione, non layout separati.')
            texts=cap.captions(template,config)
            if texts:
                with st.expander(f'Didascalie per Instagram ({len(texts)} proposte)',expanded=False):
                    st.caption('Scegli quella che ti piace e copiala con l\'icona in alto a destra del riquadro.'
                               +(' Le proposte cambiano con il risultato.' if is_full else ' Le proposte cambiano con la posizione in classifica.' if is_table else ''))
                    for i,value in enumerate(texts):
                        st.code(value,language=None,wrap_lines=True)
            st.divider()
            with st.expander('Video MP4',expanded=False):
                slider('duration','Durata in secondi',5 if is_crt else 7,18)
                select('fps','Fotogrammi al secondo',(12,15,24,30))
                select('video_scale','Risoluzione video',(2,1),lambda x:'1080 px - Full HD' if x==2 else '540 px - rapido')
                if is_crt and config['export_format']=='Post 4:5' and config['video_scale']==1:
                    st.caption('MP4 ridotto 4:5: 540 x 676, con 1 px di bordo per il codec; nessuna deformazione.')
                check('sound','Suoni CRT (bip di comparsa e ronzio del tubo)')
                if config['sound']:slider('volume','Volume',0,100)
                video_signature=hashlib.sha256((signature+str(config['duration'])+str(config['fps'])+str(config['video_scale'])
                                                +str(config['sound'])+str(config['volume'])).encode()).hexdigest()
                if st.button('Genera video MP4',key=key('render_video'),width='stretch'):
                    progress=st.progress(0,text='Rendering video...')
                    try:
                        with tempfile.TemporaryDirectory() as directory:
                            path=Path(directory)/'export.mp4'
                            callback=lambda fraction:progress.progress(fraction,text=f'Rendering: {round(fraction*100)}%')
                            if is_crt:
                                module.render_video(config,home,away,path,font_bytes,config['fps'],config['duration'],config['export_format'],config['video_scale'],callback)
                            else:
                                r.render_video(config,home,path,font_bytes,config['fps'],config['duration'],config['video_scale'],callback)
                            if config['sound']:
                                progress.progress(1.0,text='Aggiungo i suoni CRT...')
                                sounds.add_scene_audio(path,prepared,module.compose,config['duration'],config['volume']/100)
                            st.session_state['video_'+template]={'signature':video_signature,'data':path.read_bytes()}
                    except Exception as exc:st.error(f'Video non generato: {exc}')
                    finally:progress.empty()
                video=st.session_state.get('video_'+template)
                if video and video['signature']==video_signature:
                    st.video(video['data'])
                    st.download_button('Scarica MP4',video['data'],file_name=basename+'.mp4',mime='video/mp4',key=key('download_video'),width='stretch')
                else:st.caption('Genera il video per attivare il download. Ogni modifica rende il video precedente non aggiornato.')
                st.caption('H.264 / CRF 18 / audio AAC con i suoni attivi. La risoluzione 1080 richiede piu tempo e memoria.')
    except Exception as exc:
        st.error(f'Impossibile creare la grafica: {exc}')
        st.caption('Controlla i file o prova un font predefinito. Le impostazioni rimangono disponibili.')
    st.divider()
    st.caption('Studio 1.6 / Font, stemmi e progetti nel browser. Scarica un backup prima di cambiare dispositivo o cancellare i dati del sito.')
