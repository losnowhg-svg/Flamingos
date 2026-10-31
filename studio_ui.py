"""The editor: Contenuti / Stile / Esporta on the left, live preview on the right."""
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
import animations
import atmospheres
import frames
import motion
import themes
import safezone
import title_fx
from classifica_data import MAX_TEAMS, empty_row, parse_standings, sort_rows, with_rows
from library import save_project
from render_utils import layout_warnings
from studio_state import BUILTIN_FONTS, MODULES, defaults, sanitize_config
from crt_presets import PANEL_STYLES, PRESETS, PRESET_IDS, FORMATS, CROPS, apply_preset, preset_for_round
from ui_utils import file_stem, progress_with_eta
from week_ui import CSI_GIRONE, data_status, go, player_label, save_week, squad

ROOT = Path(__file__).resolve().parent
EDITOR = components.declare_component('flamingos_studio_editor', path=str(ROOT/'frontend'))
SLUGS = {'Starting 7': 'starting7', 'Matchday Screen': 'matchday', 'Full Time': 'fulltime', 'Convocati': 'convocati',
         'Classifica': 'classifica', 'Calendario': 'calendario'}
HEADERS = {
    'Matchday Screen': ('MATCHDAY', 'Prima della partita: avversari, orario e campo.'),
    'Starting 7': ('STARTING 7', 'I sette in campo, scelti dalla rosa.'),
    'Full Time': ('FULL TIME', 'Dopo il fischio finale: risultato, marcatori, rigori.'),
    'Convocati': ('CONVOCATI', 'Chi viene: titolari, panchina, ritrovo.'),
    'Classifica': ('CLASSIFICA', 'Il girone dal sito CSI: noi in rosa, promozione e spareggio colorati.'),
    'Calendario': ('CALENDARIO', 'Le partite del mese, risultati colorati e prossima gara in evidenza.'),
}
LOGO_LABELS = {'default': 'Flamingos - incluso', 'none': 'Scudo con ?'}
VIDEO_ONLY = ('duration', 'fps', 'video_scale', 'sound', 'volume', 'intro', 'music', 'ending', 'details', 'power_on', 'animation',
              'intro_style', 'music_track', 'entrance', 'camera', 'fx_pulse', 'fx_flicker', 'fx_particles', 'fx_sweep',
              'highlight')
STYLE_MIX = {'atmosphere': atmospheres.ATMOSPHERES, 'decor': atmospheres.DETAILS, 'panel_style': PANEL_STYLES,
             'title_fx': title_fx.EFFECTS, 'frame_style': frames.FRAMES, 'texture_fx': frames.TEXTURES}


KINDS = {'Matchday Screen': 'matchday', 'Full Time': 'fulltime', 'Convocati': 'convocati', 'Classifica': 'classifica',
         'Calendario': 'calendario'}


def r_output(image, config):
    from crt_presets import output_image
    return output_image(image, config.get('export_format', 'Story 9:16'), 1)


def listen_track(config, template=None, key_name='listen'):
    """▶ Ascolta: the chosen track (or the one 'Automatica' picks now), without rendering a video."""
    import music
    import variety
    template = template or st.session_state.get('studio_template')
    outcome = f.outcome(config)[0] if template == 'Full Time' else None
    track = variety.music_track(config, KINDS.get(template, ''), outcome, themes.resolve(config) or '')
    if st.toggle('▶ Ascolta il brano', key=f'{key_name}_{template}'):
        if config.get('music_track', 'auto') == 'auto':
            st.caption(f'Automatica, questa settimana: {variety.MUSIC_TRACKS.get(track, track)}')
        try:
            st.audio(music.preview_wav(track), format='audio/wav')
        except Exception as exc:
            st.caption(f'Anteprima non disponibile: {exc}')


def shuffled_style(config, seed=None):
    """🎲 A new combination of atmosphere, details, panels, title, frame and texture."""
    import random
    rnd = random.Random(seed)
    updated = copy.deepcopy(config)
    for name, options in STYLE_MIX.items():
        choices = [o for o in options if o not in ('rotazione', updated.get(name))]
        if name in ('frame_style', 'texture_fx', 'decor'):   # often none: one accent at a time looks better
            choices += ['nessuna' if name != 'decor' else 'nessuno']*2
        updated[name] = rnd.choice(choices)
    return updated


def _open_captions(template):
    st.session_state['caption_context'] = template
    st.session_state['studio_template'] = 'Didascalie'


def show_studio(root: Path, template: str, library: dict):
    is_match = template == 'Matchday Screen'
    is_full = template == 'Full Time'
    is_squad = template == 'Convocati'
    is_table = template == 'Classifica'
    is_cal = template == 'Calendario'
    is_crt = template != 'Starting 7'
    has_opponent = is_match or is_full
    module = MODULES[template]
    models = st.session_state.setdefault('studio_models', {})
    if template not in models:
        models[template] = defaults(template)
        if library.get('preferred_font'):
            models[template]['font_choice'] = library['preferred_font']
    else:
        models[template] = sanitize_config(template, models[template])
    config = models[template]
    from sequence_ui import apply_sponsor
    apply_sponsor(config)
    import stakes
    stakes.attach(template, config, models)      # standings of both teams, for the Matchday video
    revisions = st.session_state.setdefault('studio_revisions', {})
    revision = revisions.setdefault(template, 0)
    namespace = SLUGS[template]+f'_{revision}'
    assets = library['assets']
    full_squad = squad(library)
    players = [p for p in full_squad if p['role'] not in ('ALL', 'DIR')]
    logos = [id_ for id_, a in assets.items() if a['kind'] == 'logo']

    def key(name): return namespace+'_'+name

    def restart(updated):
        models[template] = sanitize_config(template, updated)
        revisions[template] += 1
        st.session_state.pop('editor_event_'+template, None)
        st.rerun()

    def text(name, label, limit, **kw):
        config[name] = st.text_input(label, value=str(config[name]), max_chars=limit, key=key(name), **kw)
        return config[name]

    def title_field():
        """Title with a 🎲 for a different one and the per-round rotation."""
        import variety
        per_round = bool(config.get('title_rotation'))
        text('title', 'Titolo', 36, disabled=per_round,
             help='In rotazione cambia da solo quando applichi la partita della settimana.' if per_round else None)
        a_, b_ = st.columns([1, 2])
        if a_.button('🎲 Altro titolo', key=key('title_roll'), width='stretch', disabled=per_round):
            updated = copy.deepcopy(config)
            updated['title'] = variety.random_title(template, config['title'], config.get('season_round', 1))
            restart(updated)
        rotate = b_.toggle('Titolo diverso a ogni giornata', value=per_round, key=key('title_rotation'))
        if rotate != per_round:
            updated = copy.deepcopy(config); updated['title_rotation'] = rotate
            if rotate:
                updated['title'] = variety.title_for_round(template, config.get('season_round', 1)) or config['title']
            restart(updated)

    def slider(name, label, lo, hi):
        config[name] = st.slider(label, lo, hi, int(config[name]), key=key(name))
        return config[name]

    def number(name, label, lo, hi):
        config[name] = int(st.number_input(label, min_value=lo, max_value=hi, value=int(config[name]), step=1, key=key(name)))
        return config[name]

    def select(name, label, options, format_func=str, **kw):
        options = list(options)
        current = config.get(name)
        index = options.index(current) if current in options else 0
        config[name] = st.selectbox(label, options, index=index, format_func=format_func, key=key(name), **kw)
        return config[name]

    def check(name, label):
        config[name] = st.checkbox(label, value=bool(config[name]), key=key(name))
        return config[name]

    def color(name, label): config[name] = st.color_picker(label, config[name], key=key(name))

    def logo_label(x): return LOGO_LABELS.get(x, assets.get(x, {}).get('name', x))

    def section(title, caption=None):
        st.markdown(f'**{title}**')
        if caption:
            st.caption(caption)

    def records(edited):
        return edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)

    # ---------------------------------------------------------------- header
    title, subtitle = HEADERS[template]
    with st.container(key='page_head'):
        head, back = st.columns([5, 1])
        with head:
            st.subheader(title)
            st.caption(subtitle)
        with back:
            st.button('← Settimana', key=key('home'), on_click=go, args=('Settimana',), width='stretch')
    todo = data_status(template, config)
    if todo:
        st.info('Ancora da completare: '+', '.join(todo)+'.', icon='✏️')
    # Phone only (CSS): a small preview that stays at the top while the controls scroll under it.
    mobile_slot = st.container(key='mobile_preview')

    controls, preview_column = st.columns([1, 1.1], gap='large')
    with controls:
        t_content, t_style, t_export = st.tabs(['✏️ Contenuti', '🎨 Stile', '📤 Esporta'])

    # ============================================================ CONTENUTI
    with t_content:
        def logos_block():
            with st.expander('Stemmi'):
                fields = ('home_logo_id', 'away_logo_id') if has_opponent else ('logo_id',)
                if any(config.get(field) not in ['default', 'none']+logos for field in fields):
                    st.warning('Uno stemma del progetto manca in archivio: viene sostituito. Reimporta il backup per recuperarlo.')
                if has_opponent:
                    a, b = st.columns(2)
                    with a:
                        select('home_logo_id', 'Stemma casa', ['default', 'none']+logos, logo_label)
                        slider('home_logo_size', 'Dimensione', 45 if is_full else 60, 85 if is_full else 150)
                        check('home_clear_white', 'Togli il bianco esterno')
                    with b:
                        select('away_logo_id', 'Stemma ospiti', ['none', 'default']+logos, logo_label)
                        slider('away_logo_size', 'Dimensione ', 45 if is_full else 60, 85 if is_full else 150)
                        check('away_clear_white', 'Togli il bianco esterno ')
                else:
                    select('logo_id', 'Stemma', ['default']+logos, logo_label)
                    slider('logo_size', 'Dimensione stemma', *((30, 58) if is_squad else (26, 56) if (is_table or is_cal) else (50, 210)))
                    check('remove_white', 'Togli lo sfondo bianco esterno')
                st.caption('Nuovi stemmi: + Stemmi nell\'archivio della barra laterale.')

        if is_match:
            section('Partita', 'Arriva dalla pagina Settimana; qui puoi ritoccarla solo per questa grafica.')
            a, b = st.columns(2)
            with a: text('home_name', 'Casa (sinistra)', 42)
            with b: text('away_name', 'Ospiti (destra)', 42)
            a, b, d = st.columns(3)
            with a: text('date', 'Data', 24)
            with b: text('kickoff', 'Orario', 14)
            with d: select('our_side', 'Noi siamo', ('Casa', 'Ospiti'))
            text('venue', 'Campo / indirizzo', 72)
            with st.expander('Titolo ed etichette'):
                title_field()
                a, b = st.columns(2)
                with a: text('kickoff_label', 'Etichetta orario', 40)
                with b: text('venue_label', 'Etichetta luogo', 22)
            logos_block()

        elif is_full:
            section('Risultato')
            a, b = st.columns(2)
            with a: number('home_score', config['home_name'].title() or 'Casa', 0, 99)
            with b: number('away_score', config['away_name'].title() or 'Ospiti', 0, 99)
            if config['show_result']:
                st.caption(f"Esito per noi ({config['our_side'].lower()}): **{f.result_text(config)}**")
            st.divider()
            section('Marcatori')
            if check('show_scorers', 'Mostra i marcatori'):
                ours = 'home' if config['our_side'] == 'Casa' else 'away'
                if players:
                    a, b, d = st.columns([3, 1.2, 1.2])
                    with a: who = st.selectbox('Chi ha segnato', [p['name'] for p in players], key=key('scorer_pick'))
                    with b: minute = st.number_input('Minuto', 1, 99, 10, key=key('scorer_minute'))
                    with d:
                        st.write('')
                        if st.button('+ Gol', key=key('scorer_add'), type='primary', width='stretch'):
                            lines = f.scorer_lines(config[ours+'_scorers'])
                            for i, line in enumerate(lines):
                                if line.upper().startswith(who+' '):
                                    lines[i] = f"{line}, {minute}'"
                                    break
                            else:
                                lines.append(f"{who} {minute}'")
                            updated = copy.deepcopy(config); updated[ours+'_scorers'] = '\n'.join(lines)
                            restart(updated)
                else:
                    st.caption('Salva la rosa nella pagina Settimana per aggiungere i gol con un clic.')
                a, b = st.columns(2)
                for side, col in (('home', a), ('away', b)):
                    with col:
                        field = side+'_scorers'
                        config[field] = st.text_area(config[side+'_name'].title() or side, value=config[field], height=110,
                                                     max_chars=1200, key=key(field), placeholder="ROSSI 12', 38'\nBIANCHI 44'")
                        if len(f.scorer_lines(config[field])) > 6:
                            st.warning('Massimo 6 righe: raggruppa i gol dello stesso giocatore.')
            if check('show_penalties', 'Decisa ai rigori'):
                a, b = st.columns(2)
                with a: number('home_penalties', 'Rigori segnati casa', 0, 99)
                with b: number('away_penalties', 'Rigori segnati ospiti', 0, 99)
                if config['home_score'] != config['away_score']:
                    st.warning('Il risultato prima dei rigori non e pari: la riga dei rigori non viene esportata.')
                elif config['home_penalties'] == config['away_penalties']:
                    st.warning('I rigori sono ancora in parita.')
            with st.expander('Partita, titolo e competizione'):
                a, b = st.columns(2)
                with a: text('home_name', 'Casa', 42)
                with b: text('away_name', 'Ospiti', 42)
                a, b = st.columns(2)
                with a: text('date', 'Data', 24)
                with b: select('our_side', 'Noi siamo', ('Casa', 'Ospiti'))
                text('competition', 'Competizione / giornata', 42)
                title_field()
                check('show_result', 'Mostra l\'esito (vittoria, pareggio, sconfitta)')
            logos_block()

        elif is_squad:
            section('Chi viene questa settimana')
            if players:
                labels = {player_label(p): p for p in players}
                current = [player_label(p) for p in players if p['name'] in {x['name'] for x in config['roster'][:config['roster_count']]}]
                chosen = st.multiselect('Scegli dalla rosa, nell\'ordine in cui vuoi vederli', list(labels), default=current,
                                        key=key('roster_pick'), placeholder='Tocca per scegliere i convocati')
                a, b = st.columns([2, 1])
                names = [labels[x]['name'] for x in chosen]
                old_captain = next((p['name'] for p in config['roster'][:config['roster_count']] if p['captain']), None)
                with a:
                    captain = st.selectbox('Capitano', ['nessuno']+names,
                                           index=(names.index(old_captain)+1) if old_captain in names else 0, key=key('captain_pick'))
                with b:
                    st.write('')
                    if st.button('Usa questi', key=key('roster_apply'), type='primary', width='stretch', disabled=not chosen):
                        updated = copy.deepcopy(config)
                        for i, label in enumerate(chosen[:c.MAX_PLAYERS]):
                            p = labels[label]
                            role = p['role'] if p['role'] in c.ROLES else '-'
                            updated['roster'][i] = dict(number=p['number'], name=p['name'], role=role, captain=p['name'] == captain)
                        updated['roster_count'] = max(7, min(c.MAX_PLAYERS, len(chosen)))
                        restart(updated)
                if chosen and len(chosen) < 7:
                    st.caption('La grafica parte da 7 posti: completa i nomi nella tabella qui sotto.')
            else:
                st.caption('Salva la rosa nella pagina Settimana: poi qui scegli i convocati con un clic.')
            number('roster_count', 'Numero di convocati', 7, c.MAX_PLAYERS)
            count = config['roster_count']
            edited = st.data_editor([dict(x) for x in config['roster'][:count]], hide_index=True, num_rows='fixed',
                                    width='stretch', key=key('roster_table'),
                                    column_config={'number': st.column_config.NumberColumn('N.', min_value=0, max_value=99, step=1, width='small'),
                                                   'name': st.column_config.TextColumn('Nome', max_chars=27),
                                                   'role': st.column_config.SelectboxColumn('Ruolo', options=list(c.ROLES), width='small'),
                                                   'captain': st.column_config.CheckboxColumn('Cap.', width='small')})
            for i, row in enumerate(records(edited)[:count]):
                config['roster'][i] = dict(number=max(0, min(99, int(row.get('number') or 0))), name=str(row.get('name') or '')[:27],
                                           role=row.get('role') if row.get('role') in c.ROLES else '-', captain=bool(row.get('captain')))
            active = config['roster'][:count]
            if len({x['number'] for x in active}) < len(active): st.warning('Numeri di maglia duplicati.')
            if sum(x['captain'] for x in active) > 1: st.warning('Piu di un capitano.')
            if any(not x['name'].strip() for x in active): st.warning('Alcuni convocati non hanno il nome.')
            st.caption('P portiere / D difensore / C centrocampista / A attaccante. Il capitano ha l\'asterisco * nella grafica. '
                       'Le schermate per reparto con gli avatar sono in Esporta.')
            with st.expander('Partita e ritrovo'):
                a, b = st.columns(2)
                with a: text('opponent', 'Avversari', 42)
                with b: text('date', 'Data', 24)
                a, b = st.columns(2)
                with a: text('meeting_time', 'Ritrovo', 14)
                with b: text('kickoff', 'Calcio d\'inizio', 14)
                text('venue', 'Campo / indirizzo', 72)
                text('team_name', 'Nome squadra', 50)
                title_field()
            logos_block()

        elif is_table:
            section('Dati della classifica')
            if st.session_state.get('standings_message'):
                st.success(st.session_state.pop('standings_message'))
            if st.session_state.get('standings_import_error'):
                st.error('Il segnalibro ha inviato una pagina senza classifica leggibile: '+st.session_state.pop('standings_import_error'))

            def load_rows(rows, message):
                st.session_state['standings_message'] = message
                models[template] = sanitize_config(template, with_rows(config, rows))
                save_week()
                revisions[template] += 1
                st.rerun()

            site, paste, manual = st.tabs(['Dal sito CSI', 'Incolla', 'A mano'])
            with site:
                st.markdown('Apri il girone e tocca il segnalibro **Invia a Flamingos**, oppure incolla la pagina intera '
                            'nella Settimana: arrivano anche prossima partita e calendario.')
                st.link_button('Apri il Girone D su CSI LIVE', CSI_GIRONE, type='primary', width='stretch')
                st.button('Vai ad Aggiorna dal sito CSI (Settimana)', key=key('to_week'), on_click=go, args=('Settimana',), width='stretch')
            with paste:
                pasted = st.text_area('Testo della classifica', height=150, key=key('paste'),
                                      placeholder='Seleziona la tabella dalla prima squadra all\'ultima, copia e incolla qui.')
                if st.button('Leggi la tabella', key=key('parse'), type='primary'):
                    try:
                        rows = parse_standings(pasted)
                        load_rows(rows, f'Tabella letta: {len(rows)} squadre.')
                    except ValueError as exc:
                        st.error(str(exc))
            with manual:
                number('team_count', 'Numero di squadre', 2, MAX_TEAMS)
                count = config['team_count']
                edited = st.data_editor([dict(x) for x in config['standings'][:count]], hide_index=True, num_rows='fixed',
                                        width='stretch', key=key('table_editor'),
                                        column_config={'pos': st.column_config.NumberColumn('Pos', min_value=1, max_value=99, step=1, width='small'),
                                                       'team': st.column_config.TextColumn('Squadra', max_chars=34),
                                                       **{x: st.column_config.NumberColumn(x.upper(), min_value=0, max_value=999, step=1, width='small')
                                                          for x in ('pt', 'g', 'v', 'n', 'p', 'gf', 'gs')}})
                for i, row in enumerate(records(edited)[:count]):
                    clean = empty_row(i+1)
                    for field in clean:
                        value = row.get(field, clean[field])
                        try:
                            clean[field] = str(value or '')[:34] if field == 'team' else max(0, min(999, int(value or 0)))
                        except (TypeError, ValueError):
                            pass
                    config['standings'][i] = clean
                if st.button('Ordina per punti', key=key('sort')):
                    load_rows(sort_rows(config['standings'][:count]), 'Classifica riordinata.')
            active = k.active_rows(config)
            wrong = [x['team'] for x in active if x['v']+x['n']+x['p'] != x['g']]
            if wrong: st.warning('V + N + P non torna con le giocate per: '+', '.join(wrong[:4])+'.')
            if not any(k.is_ours(x['team'], config['our_team']) for x in active):
                st.info('La tua squadra non e in tabella: controlla il nome qui sotto.')
            st.divider()
            section('Testi e zone')
            a, b = st.columns(2)
            with a: text('round_label', 'Giornata', 36)
            with b: text('our_team', 'La nostra squadra', 34)
            number('prev_pos', 'Nostra posizione la settimana scorsa (0 = non mostrare la freccia)', 0, 30)
            if check('show_zones', 'Colora promozione e spareggio'):
                a, b = st.columns(2)
                with a: number('promo_count', 'Posti promozione', 0, 8)
                with b: number('playoff_count', 'Posti spareggio', 0, 8)
            with st.expander('Altri testi'):
                title_field()
                text('group', 'Girone / campionato', 48)
                select('table_detail', 'Colonne', k.DETAILS,
                       lambda x: 'Complete: G V N P GF GS PT' if x == 'Completa' else 'Compatte: G, DR, PT')
                if config['show_zones']:
                    a, b = st.columns(2)
                    with a: text('promo_label', 'Etichetta zona 1', 20)
                    with b: text('playoff_label', 'Etichetta zona 2', 20)
            logos_block()

        elif is_cal:
            section('Partite del mese')
            matches = st.session_state.get('csi_matches') or []
            if matches:
                from csi_page import fixtures_for_month, MONTHS
                months = sorted({(m['date'].year, m['date'].month) for m in matches})
                today = __import__('datetime').date.today()
                current = (today.year, today.month) if (today.year, today.month) in months else months[0]
                a, b = st.columns([2, 1])
                with a:
                    chosen = st.selectbox('Mese dal sito CSI', months, index=months.index(current),
                                          format_func=lambda x: f'{MONTHS[x[1]-1].capitalize()} {x[0]}', key=key('cal_month'))
                with b:
                    st.write('')
                    if st.button('Riempi', key=key('cal_fill'), type='primary', width='stretch'):
                        rows = fixtures_for_month(matches, config['our_team'], *chosen, limit=cal.MAX_FIXTURES)
                        updated = copy.deepcopy(config)
                        updated['fixtures'] = rows+[cal.empty_fixture() for _ in range(len(rows), cal.MAX_FIXTURES)]
                        updated['fixture_count'] = max(1, len(rows))
                        updated['month_label'] = f'{MONTHS[chosen[1]-1]} {chosen[0]}'
                        models[template] = sanitize_config(template, updated)
                        save_week()
                        restart(updated)
            else:
                st.caption('Con il segnalibro Invia a Flamingos le partite arrivano da sole. Oppure scrivile qui.')
            number('fixture_count', 'Numero di partite', 1, cal.MAX_FIXTURES)
            count = config['fixture_count']
            edited = st.data_editor([dict(x) for x in config['fixtures'][:count]], hide_index=True, num_rows='fixed',
                                    width='stretch', key=key('fixtures_editor'),
                                    column_config={'date': st.column_config.TextColumn('Data', max_chars=8, help='GG/MM'),
                                                   'day': st.column_config.TextColumn('Giorno', max_chars=3),
                                                   'opponent': st.column_config.TextColumn('Avversari', max_chars=30),
                                                   'side': st.column_config.SelectboxColumn('C/T', options=['C', 'T'], required=True, width='small'),
                                                   'time': st.column_config.TextColumn('Ora', max_chars=8),
                                                   'score': st.column_config.TextColumn('Risultato', max_chars=7, help='Casa-ospiti, es. 3-1')})
            for i, row in enumerate(records(edited)[:count]):
                clean = cal.empty_fixture()
                for field, limit in (('date', 8), ('day', 3), ('opponent', 30), ('time', 8), ('score', 7)):
                    clean[field] = str(row.get(field) or '')[:limit]
                clean['side'] = row.get('side') if row.get('side') in ('C', 'T') else 'C'
                config['fixtures'][i] = clean
            st.caption('C in casa, T in trasferta. Risultato come sul tabellone (casa-ospiti); la prima partita senza risultato e la NEXT.')
            with st.expander('Titolo e mese'):
                title_field()
                text('month_label', 'Mese', 30)
                text('our_team', 'La nostra squadra', 34)
            logos_block()

        else:  # Starting 7
            section('I sette in campo')
            if players:
                options = ['—']+[p['name'] for p in players]
                by_name = {p['name']: p for p in players}
                a, b = st.columns(2)
                for i, role in enumerate(r.DEFAULT_ROLES):
                    with (a if i % 2 == 0 else b):
                        current = config['players'][i]['name']
                        pick = st.selectbox(role, options, index=options.index(current) if current in options else 0, key=key(f'pick_{i}'))
                        if pick != '—':
                            config['players'][i] = {'number': by_name[pick]['number'], 'name': pick}
                st.caption('Oppure scrivi a mano nella tabella qui sotto.')
            else:
                st.caption('Salva la rosa nella pagina Settimana per scegliere i titolari con un clic.')
            edited = st.data_editor([dict(role=role, **config['players'][i]) for i, role in enumerate(r.DEFAULT_ROLES)],
                                    hide_index=True, num_rows='fixed', width='stretch', key=key('starting_table'),
                                    disabled=['role'],
                                    column_config={'role': st.column_config.TextColumn('Ruolo'),
                                                   'number': st.column_config.NumberColumn('N.', min_value=0, max_value=99, step=1, width='small'),
                                                   'name': st.column_config.TextColumn('Nome', max_chars=27)})
            for i, row in enumerate(records(edited)[:7]):
                config['players'][i] = {'number': max(0, min(99, int(row.get('number') or 0))), 'name': str(row.get('name') or '')[:27]}
            if len({p['number'] for p in config['players']}) < 7: st.warning('Numeri di maglia duplicati.')
            with st.expander('Testi'):
                text('team_name', 'Nome squadra', 50)
                text('headline', 'Titolo principale', 60)
                text('formation_text', 'Modulo', 80)
                text('footer', 'Scritta in basso', 80)
            logos_block()

    # ================================================================ STILE
    with t_style:
        if is_crt:
            section('Preset')
            a, b = st.columns([3, 1])
            per_round = config['rotation_mode'] == 'Per giornata'
            with a:
                if per_round:
                    target = preset_for_round(config['season_round'])
                    st.selectbox('Preset', [target], format_func=lambda x: PRESETS[x]['name'], disabled=True, key=key('preset_locked'))
                else:
                    target = st.selectbox('Preset', PRESET_IDS, index=PRESET_IDS.index(config['preset_id']),
                                          format_func=lambda x: PRESETS[x]['name'], key=key('preset_picker'))
            with b:
                st.write('')
                if st.button('Prossimo ▶', key=key('next_preset'), width='stretch'):
                    nxt = PRESET_IDS[(PRESET_IDS.index(config['preset_id'])+1) % len(PRESET_IDS)]
                    updated = apply_preset(config, nxt); updated['rotation_mode'] = 'Manuale'
                    restart(updated)
            if target != config['preset_id']:
                restart(apply_preset(config, target))
            st.caption(PRESETS[config['preset_id']]['description'])
            rotate = st.toggle('Cambia preset da solo a ogni giornata', value=per_round, key=key('rotation'))
            if rotate != per_round:
                updated = copy.deepcopy(config); updated['rotation_mode'] = 'Per giornata' if rotate else 'Manuale'
                if rotate:
                    updated = apply_preset(updated, preset_for_round(updated['season_round']))
                restart(updated)
            if rotate:
                number('season_round', 'Giornata', 1, 80)
            a, b = st.columns(2)
            with a:
                if st.button('Usa il font del preset', key=key('preset_font'), width='stretch'):
                    updated = copy.deepcopy(config); updated['font_choice'] = PRESETS[config['preset_id']]['font']
                    restart(updated)
            catalog = root/'assets'/'preset_catalog.jpg'
            if catalog.exists():
                with st.expander(f'Guarda tutti i {len(PRESET_IDS)} preset'):
                    st.image(str(catalog), width='stretch')
            import layouts
            if len(layouts.options(template)) > 1:
                st.divider()
                section('Impaginazione', 'Cambia la disposizione degli elementi sullo schermo. '
                        'Le posizioni tornano quelle dell\'impaginazione scelta.')
                ids = layouts.options(template)
                per_round_layout = bool(config.get('layout_rotation'))
                current_layout = layouts.current(template, config)
                chosen_layout = st.radio('Impaginazione', ids, index=ids.index(current_layout), horizontal=True,
                                         format_func=lambda x: layouts.label(template, x), key=key('layout'),
                                         disabled=per_round_layout, label_visibility='collapsed')
                if chosen_layout != current_layout:
                    restart(layouts.apply(template, config, chosen_layout))
                st.caption(layouts.LAYOUTS[template][current_layout]['description'])
                rotate_layout = st.toggle('Cambia impaginazione da sola a ogni giornata', value=per_round_layout,
                                          key=key('layout_rotation'))
                if rotate_layout != per_round_layout:
                    updated = copy.deepcopy(config); updated['layout_rotation'] = rotate_layout
                    if rotate_layout:
                        updated = layouts.apply(template, updated, layouts.for_round(template, updated['season_round']))
                    restart(updated)
            st.divider()
            section('Atmosfera e dettagli', 'Lo stesso preset di giorno, al tramonto, di notte o sotto i neon, '
                    'con stelle, coriandoli, adesivi o scritte intorno allo schermo (mai sopra i testi).')
            a, b = st.columns(2)
            with a: select('atmosphere', 'Atmosfera', atmospheres.ATMOSPHERES, atmospheres.ATMOSPHERES.get)
            with b: select('decor', 'Dettagli', atmospheres.DETAILS, atmospheres.DETAILS.get)
            section('Design', 'Riquadri, effetto del titolo, cornice e texture. "A rotazione" cambia da solo a ogni giornata.')
            a, b = st.columns(2)
            with a:
                select('panel_style', 'Riquadri', PANEL_STYLES, PANEL_STYLES.get)
                select('frame_style', 'Cornice', frames.FRAMES, frames.FRAMES.get)
            with b:
                select('title_fx', 'Effetto del titolo', title_fx.EFFECTS, title_fx.EFFECTS.get)
                select('texture_fx', 'Texture', frames.TEXTURES, frames.TEXTURES.get)
            if config.get('mockup') and config['frame_style'] != 'nessuna':
                st.caption('Con il televisore attivo cornice e texture non si vedono: la cornice e il televisore.')
            if st.button('🎲 Mischia lo stile', key=key('shuffle_style'), width='stretch',
                         help='Una combinazione nuova di atmosfera, dettagli, riquadri, titolo, cornice e texture. '
                              'Il preset e i colori restano.'):
                restart(shuffled_style(config, uuid.uuid4().int))
            st.divider()
            section('Tema per eventi e stagioni', 'Derby, big match, ultima giornata, Halloween, Natale, Capodanno: '
                    'cambiano accenti e dettagli, la grafica resta Flamingos.')
            chosen_theme = select('theme', 'Tema', themes.CHOICES, themes.label)
            active_theme = themes.resolve(config)
            st.caption(themes.why(config)+(' '+themes.THEMES[active_theme]['description'] if active_theme else ''))
            if chosen_theme == 'auto' and not active_theme:
                st.caption('Per derby, big match e ultima giornata scegli il tipo di partita nella pagina Settimana, '
                           'oppure scegli il tema qui a mano.')
            st.divider()
            section('Luce e colori')
            slider('brightness', 'Luminosita per Instagram', 0, 100)
            st.caption('55 e il valore consigliato per il feed; 0 = aspetto originale, piu scuro.')
            with st.expander('Colori e scanline'):
                a, b = st.columns(2)
                with a:
                    color('pink', 'Rosa / casa'); color('yellow', 'Accento')
                with b:
                    color('cyan', 'Neon / ospiti'); color('white', 'Testo chiaro')
                if is_table and config['show_zones']:
                    a, b = st.columns(2)
                    with a: color('promo_color', 'Zona promozione')
                    with b: color('playoff_color', 'Zona spareggio')
                slider('scanlines', 'Scanline CRT', 0, 60)
        else:
            section('Colori')
            a, b, d = st.columns(3)
            with a: color('accent', 'Principale')
            with b: color('background', 'Sfondo')
            with d: color('text_color', 'Testo')
            slider('texture', 'Texture di sfondo', 0, 100)
        st.divider()
        section('Carattere')
        fonts = [id_ for id_, a in assets.items() if a['kind'] == 'font']
        if config.get('font_choice') not in BUILTIN_FONTS+fonts:
            st.warning('Il font salvato non e in archivio: uso Sans Bold. Reimporta il backup per ripristinarlo.')
        selected_font = select('font_choice', 'Font', BUILTIN_FONTS+fonts,
                               lambda x: ('Salvato: '+assets[x]['name']) if x in assets else x)
        config['text_style'] = 'Font salvato' if selected_font in fonts else selected_font
        font_bytes = assets[selected_font]['bytes'] if selected_font in fonts else None
        with st.expander('Dimensioni del testo'):
            if is_match:
                slider('title_size', 'Titolo e data', 18, 42); slider('label_size', 'Nomi squadre', 12, 30)
                slider('info_size', 'Informazioni', 12, 25); slider('vs_size', 'VS', 24, 58)
            elif is_full:
                slider('title_size', 'Titolo', 18, 42); slider('score_size', 'Risultato', 30, 76)
                slider('label_size', 'Squadre', 10, 24); slider('info_size', 'Competizione e data', 9, 20)
                slider('scorer_size', 'Marcatori', 8, 16); slider('result_size', 'Esito', 10, 24)
            elif is_cal:
                slider('title_size', 'Titolo', 16, 34); slider('info_size', 'Mese', 8, 16)
            elif is_table:
                slider('title_size', 'Titolo', 16, 34); slider('info_size', 'Girone e giornata', 8, 16)
                slider('table_size', 'Testo tabella', 7, 14)
            elif is_squad:
                slider('title_size', 'Titolo', 18, 36); slider('team_size', 'Squadra', 9, 20)
                slider('name_size', 'Convocati', 9, 16); slider('info_size', 'Informazioni', 8, 18)
            else:
                slider('title_size', 'Nome squadra', 15, 62); slider('subtitle_size', 'Titolo', 12, 56)
                slider('name_size', 'Nomi giocatori', 10, 35); slider('footer_size', 'Scritte in basso', 10, 42)
            st.caption('Se una riga non entra, la dimensione viene ridotta da sola.')

    # ======================================================== ESPORTA (setup)
    with t_export:
        section('Formato')
        a, b = st.columns(2)
        with a:
            if is_crt:
                select('export_format', 'Formato', FORMATS)
            else:
                st.selectbox('Formato', ['Story 9:16'], disabled=True, key=key('format_locked'))
        with b:
            select('png_quality', 'Qualita', ('Fine', 'Standard'),
                   lambda x: 'Fine (antialias)' if x == 'Fine' else 'Standard (pixel netti)')
        if is_crt:
            check('mockup', '📺 Dentro un vecchio televisore (PNG e video)')
            if config['mockup']:
                st.caption('La grafica va sullo schermo di un TV a tubo in una stanza buia: la luce dello schermo '
                           'colora la stanza. Il ritaglio del formato vale per tutta la scena.')

    default_logo = (root/'assets'/'flamingos_logo.jpg').read_bytes()
    home_id = config['home_logo_id'] if has_opponent else config['logo_id']
    home = assets[home_id]['bytes'] if home_id in assets else None if home_id == 'none' else default_logo
    away_id = config.get('away_logo_id')
    away = default_logo if away_id == 'default' else assets[away_id]['bytes'] if away_id in assets else None

    try:
        # Same settings as the previous run (a tab click, an expander...): reuse scene and editor payload.
        preview_key = hashlib.sha256(json.dumps({k_: v for k_, v in config.items() if k_ not in VIDEO_ONLY}, sort_keys=True).encode()
                                     + (home or b'')+(away or b'')+(font_bytes or b'')).hexdigest()
        memo = st.session_state.get('preview_'+template)
        if memo and memo['key'] == preview_key:
            prepared, editor_payload = memo['prepared'], memo['payload']
        else:
            prepared = module.scene(config, home, away, font_bytes, 2) if is_crt else r.scene(config, home, font_bytes, 2)
            editor_scene = (animations.still_base(prepared),)+tuple(prepared[1:]) if is_crt else prepared
            editor_payload = r.editor_data(editor_scene)
            st.session_state['preview_'+template] = {'key': preview_key, 'prepared': prepared, 'payload': editor_payload}
        crop = CROPS[config['export_format']] if is_crt else None
        with mobile_slot:
            small = st.session_state.get('mobile_png_'+template)
            if not small or small[0] != preview_key:
                still = module.compose(prepared, 999, False) if is_crt else r.compose(prepared, animated=False)
                image = r_output(still, config) if is_crt else still
                image.thumbnail((480, 480))
                small = (preview_key, image)
                st.session_state['mobile_png_'+template] = small
            st.image(small[1], width='stretch')
            st.caption('Anteprima · le modifiche si vedono qui')
        # ------------------------------------------------------ PREVIEW
        with preview_column:
            zones = safezone.editor_zones(config['export_format']) if is_crt else None
            changed = EDITOR(**editor_payload, crop=crop, zones=zones, key=key('canvas'), default=None)
            if isinstance(changed, dict) and changed.get('event_id') != st.session_state.get('editor_event_'+template):
                st.session_state['editor_event_'+template] = changed.get('event_id')
                if isinstance(changed.get('positions'), dict):
                    updated = {k_: list(v) for k_, v in module.normalized_positions({'positions': changed['positions']}).items()}
                    if updated != config['positions']:
                        config['positions'] = updated; st.rerun()
            st.caption('Trascina testi e stemmi. Le linee gialle mostrano il ritaglio del formato scelto'
                       + ('; le fasce a righe sono coperte dall\'interfaccia di Instagram nei Reel e nelle Storie.' if zones else '.'))
            for warning in layout_warnings(prepared, crop): st.warning(warning)
            hidden = safezone.covered(prepared, config['export_format']) if is_crt else []
            if hidden:
                st.warning('Nei Reel e nelle Storie l\'interfaccia di Instagram copre: '+', '.join(hidden)+'.')
                if st.button('📲 Sposta dentro la zona sicura', key=key('safe_fit'), width='stretch'):
                    config['positions'] = safezone.fit(prepared, config['positions']); st.rerun()
            with st.expander('Posizioni precise e ripristino'):
                names = {layer.id: layer.label for layer in prepared[1]}
                selected = st.selectbox('Elemento', list(names), format_func=lambda x: names[x], key=key('selected'))
                current = config['positions'][selected]
                with st.form(key('coordinates')):
                    a, b = st.columns(2)
                    x = a.number_input('X', 0, 540, value=int(current[0]), key=key(f'x_{selected}_{current[0]}'))
                    y = b.number_input('Y', 0, 960, value=int(current[1]), key=key(f'y_{selected}_{current[1]}'))
                    if st.form_submit_button('Applica'):
                        config['positions'][selected] = [x, y]; st.rerun()
                if st.button('Rimetti tutto al posto iniziale', key=key('reset')):
                    import layouts
                    if template in layouts.LAYOUTS:
                        positions = layouts.default_positions(template, layouts.current(template, config))
                    else:
                        positions = module.DEFAULT_POSITIONS
                    config['positions'] = {k_: list(v) for k_, v in positions.items()}; st.rerun()

        # ------------------------------------------------------- EXPORT
        with t_export:
            signature_config = {k_: v for k_, v in config.items() if k_ not in ('duration', 'fps', 'video_scale', 'sound', 'volume')}
            signature = hashlib.sha256(json.dumps(signature_config, sort_keys=True).encode()+(home or b'')+(away or b'')
                                       + (font_bytes or b'')).hexdigest()
            cache_key = 'png_'+template; cached = st.session_state.get(cache_key)
            if not cached or cached['signature'] != signature:
                ss = 2 if config['png_quality'] == 'Fine' else 1
                image = module.png_bytes(config, home, away, font_bytes, config['export_format'], 2, ss) if is_crt else r.png_bytes(config, home, font_bytes, 2, ss)
                cached = {'signature': signature, 'data': image}; st.session_state[cache_key] = cached
            png = cached['data']
            height = {'Post 1:1': 1080, 'Post 4:5': 1350, 'Story 9:16': 1920}[config['export_format']]
            basename = file_stem(template, config)
            st.download_button(f'⬇ Scarica PNG  ·  1080 x {height}  ·  {len(png)/1e6:.1f} MB', png, file_name=basename+'.png', mime='image/png',
                               type='primary', width='stretch', key=key('download_png'))
            import share
            share.button(png, basename+'.png', 'image/png', key='png_'+template)
            if is_crt and config['mockup']:
                st.image(png, width='stretch')
            else:
                with st.expander('Guarda il PNG finale'):
                    if is_crt and safezone.applies(config['export_format']) and st.toggle(
                            'Mostra l\'interfaccia di un Reel sopra (solo per controllare)', key=key('ig_mock')):
                        from PIL import Image as _Image
                        import io as _io
                        st.image(safezone.mock(_Image.open(_io.BytesIO(png))), width='stretch')
                    else:
                        st.image(png, width='stretch')
            st.divider()
            if is_squad:
                from reparti_ui import show_departments
                show_departments(config, full_squad, home, font_bytes, key)
                st.divider()
            if template != 'Starting 7':
                from caption_ui import quick
                with st.expander('✍️ Didascalia per il post (tre proposte)'):
                    st.caption('Tocca l\'icona in alto a destra di un riquadro per copiarla. Centinaia di altre nella pagina Didascalie.')
                    for item in quick(template, 3, st.session_state.get('caption_quick_seed', 0), library):
                        st.code(item['text'], language=None, wrap_lines=True)
                    a, b = st.columns(2)
                    if a.button('🎲 Altre tre', key=key('caption_roll'), width='stretch'):
                        st.session_state['caption_quick_seed'] = st.session_state.get('caption_quick_seed', 0)+1
                        st.rerun()
                    b.button('✍️ Apri Didascalie', key=key('caption_page'), width='stretch', on_click=_open_captions, args=(template,))
                st.divider()
            section('Video MP4')
            if is_crt:
                if st.button('⚡ Modalità Reel', key=key('reel_mode'), width='stretch',
                             help='Un clic per un Reel: intro col logo che si compone, parallasse 3D, particelle, bagliore '
                                  'a ritmo, musica, finale in loop, Story 9:16, 10 secondi.'):
                    updated = copy.deepcopy(config); updated.update(motion.REEL)
                    restart(updated)
                a, b = st.columns(2)
                with a:
                    select('animation', 'Animazione', animations.STYLES,
                           lambda x: 'Retro: scrittura, glitch, contatore' if x == 'Retro' else 'Classica: dissolvenza')
                with b:
                    st.write('')
                    if config['animation'] == 'Retro':
                        check('power_on', 'Accensione del TV all\'inizio')
                if config['animation'] == 'Retro':
                    st.caption({'Matchday Screen': 'Gli stemmi arrivano dai lati e si scontrano: lampo, schermo che trema, poi il VS.',
                                'Full Time': 'Punteggio a slot machine, GOAL! se segniamo, poi STAGE CLEAR, DRAW GAME o GAME OVER.',
                                'Classifica': 'La tabella si riempie riga per riga; la nostra riga sale o scende dalla posizione '
                                              'della settimana scorsa; corona se siamo primi.',
                                'Calendario': 'Ogni risultato entra con un ding; la prossima partita lampeggia.',
                                'Convocati': 'Lista scritta come su un terminale, luce dorata sul capitano. '
                                             'Nei reparti gli avatar sbattono le palpebre.'}.get(template, ''))
                    if template == 'Matchday Screen':
                        if config.get('stakes'):
                            st.caption('Nel video i riquadri dei nomi mostrano posizione e punti delle due squadre, '
                                       'con la distanza sotto il VS (dalla Classifica).')
                        else:
                            st.caption('Aggiorna la Classifica (con questo avversario dentro) e nel video compariranno '
                                       'posizione e punti delle due squadre.')
                    a, b = st.columns(2)
                    with a:
                        import variety
                        if check('intro', 'Intro'):
                            select('intro_style', 'Che intro', variety.INTRO_STYLES, variety.INTRO_STYLES.get)
                        if check('music', 'Musica'):
                            select('music_track', 'Brano', variety.MUSIC_TRACKS, variety.MUSIC_TRACKS.get)
                            listen_track(config)
                    with b:
                        check('details', 'Dettagli VHS: REC, contatore, disturbi')
                        select('ending', 'Finale', animations.ENDINGS, motion.ENDING_NAMES.get)
                    a, b = st.columns(2)
                    with a: select('entrance', 'Ingresso degli elementi', motion.ENTRANCES, motion.ENTRANCES.get)
                    with b: select('camera', 'Movimento di camera', motion.CAMERAS, motion.CAMERAS.get)
                    if template in ('Full Time', 'Calendario', 'Convocati'):
                        import focus
                        select('highlight', 'Messa in evidenza (punteggio, ultimo risultato, capitano)', focus.HIGHLIGHTS,
                               focus.HIGHLIGHTS.get)
                    st.caption('Effetti continui')
                    cols = st.columns(2)
                    for i, (name, label) in enumerate(motion.AMBIENT.items()):
                        with cols[i % 2]: check(name, label)
            with st.expander('Impostazioni video'):
                slider('duration', 'Durata (secondi)', 5 if is_crt else 7, 18)
                if is_crt and config['animation'] == 'Retro':
                    st.caption('Se intro, animazioni e finale non ci stanno, il video si allunga da solo.')
                a, b = st.columns(2)
                with a: select('fps', 'Fotogrammi al secondo', (12, 15, 24, 30, 60),
                               lambda x: {24: '24 (cinema)', 30: '30 (consigliato per i Reel)', 60: '60 (fluidissimo, file piu pesante)'}.get(x, str(x)))
                with b: select('video_scale', 'Risoluzione', (2, 1), lambda x: '1080 px' if x == 2 else '540 px (rapido)')
                check('sound', 'Suoni CRT')
                if config['sound'] or config.get('music'): slider('volume', 'Volume', 0, 100)
            video_signature = hashlib.sha256((signature+str(config['duration'])+str(config['fps'])+str(config['video_scale'])
                                              + str(config['sound'])+str(config.get('music'))+str(config['volume'])).encode()).hexdigest()
            a, b = st.columns(2)
            quick = a.button('⚡ Anteprima veloce', key=key('quick_video'), width='stretch',
                             help='540 px, 12 fotogrammi al secondo, senza audio: per controllare le animazioni in pochi secondi.')
            full = b.button('🎬 Genera video HD', key=key('render_video'), width='stretch', type='primary')
            if quick:
                bar = st.progress(0, text='Anteprima...')
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory)/'quick.mp4'
                        if is_crt:
                            module.render_video(config, home, away, path, font_bytes, 12, config['duration'],
                                                config['export_format'], 1, progress_with_eta(bar, 'Anteprima'))
                        else:
                            r.render_video(config, home, path, font_bytes, 12, config['duration'], 1, progress_with_eta(bar, 'Anteprima'))
                        st.session_state['quick_'+template] = {'signature': video_signature, 'data': path.read_bytes()}
                except Exception as exc:
                    st.error(f'Anteprima non generata: {exc}')
                finally:
                    bar.empty()
            preview = st.session_state.get('quick_'+template)
            video_now = st.session_state.get('video_'+template)
            if preview and preview['signature'] == video_signature and not (video_now and video_now['signature'] == video_signature):
                st.video(preview['data'], loop=True, autoplay=True, muted=True)
                st.caption('Anteprima a bassa risoluzione: per pubblicare usa Genera video HD.')
            if full:
                progress = st.progress(0, text='Rendering video...')
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory)/'export.mp4'
                        callback = progress_with_eta(progress)
                        if is_crt:
                            module.render_video(config, home, away, path, font_bytes, config['fps'], config['duration'],
                                                config['export_format'], config['video_scale'], callback)
                        else:
                            r.render_video(config, home, path, font_bytes, config['fps'], config['duration'], config['video_scale'], callback)
                        if config['sound'] or config.get('music'):
                            progress.progress(1.0, text='Aggiungo l\'audio...')
                            seconds = config['duration']
                            if is_crt:
                                from crt_common import video_length
                                seconds = video_length(prepared, config['duration'])
                                prepared[0].info['duration'] = seconds
                            sounds.add_scene_audio(path, prepared, module.compose, seconds, config['volume']/100,
                                                   effects=config['sound'])
                        st.session_state['video_'+template] = {'signature': video_signature, 'data': path.read_bytes()}
                except Exception as exc:
                    st.error(f'Video non generato: {exc}')
                finally:
                    progress.empty()
            video = st.session_state.get('video_'+template)
            if video and video['signature'] == video_signature:
                st.video(video['data'])
                st.download_button('⬇ Scarica MP4', video['data'], file_name=basename+'.mp4', mime='video/mp4',
                                   key=key('download_video'), width='stretch')
                import share
                share.button(video['data'], basename+'.mp4', 'video/mp4', key='mp4_'+template)
            st.divider()
            section('Progetti')
            with st.expander('Salva o riapri questa grafica'):
                project_name = st.text_input('Nome', value=title.title()+' - nuova', max_chars=80, key=key('project_name'))
                if st.button('Salva nel browser', key=key('save'), type='primary', width='stretch'):
                    if not project_name.strip():
                        st.error('Inserisci un nome.')
                    else:
                        matching = next((id_ for id_, p in library['projects'].items()
                                         if p['template'] == template and p['name'] == project_name.strip()), None)
                        save_project(project_name, template, copy.deepcopy(config), matching or uuid.uuid4().hex)
                saved = {id_: p for id_, p in library['projects'].items() if p['template'] == template}
                if saved:
                    chosen_project = st.selectbox('Progetti salvati', list(saved), format_func=lambda x: saved[x]['name'], key=key('open_project'))
                    if st.button('Apri', key=key('load_project'), width='stretch'):
                        restart(saved[chosen_project]['config'])
                st.caption('Stesso nome = aggiorna il progetto. Partita, classifica, calendario e rosa si salvano da soli.')
                if st.session_state.get('vault_command'): st.info('Salvataggio in corso...')
    except Exception as exc:
        st.error(f'Impossibile creare la grafica: {exc}')
        st.caption('Controlla i file o prova un font predefinito. Le impostazioni rimangono disponibili.')
