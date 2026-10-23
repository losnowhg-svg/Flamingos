"""La tua settimana: the home page, the squad register and the week memory."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import renderer as r
from classifica_data import bookmarklet, with_rows
from crt_presets import output_image
from library import queue_save
from sequence_ui import apply_match_everywhere, current_config, resolve_assets, show_kit
from studio_state import (DEFAULTS, MODULES, SQUAD_ID, SQUAD_ROLES, WEEK_ID, defaults, matches_from_week,
                          matches_to_week, sanitize_config, sanitize_match, sanitize_squad, sanitize_week)

STEPS = (
    ('Matchday Screen', 'Matchday', 'Prima della partita'),
    ('Convocati', 'Convocati', 'Chi viene'),
    ('Starting 7', 'Starting 7', 'In campo'),
    ('Full Time', 'Full Time', 'Il risultato'),
    ('Classifica', 'Classifica', 'Il girone'),
    ('Calendario', 'Calendario', 'Il mese'),
)
CSI_GIRONE = ('https://live.centrosportivoitaliano.it/26/Calcio-a-7/Lombardia/Brescia/C102/'
              '?j=NEU9REZJJjRGPVBOSyY0Rz1FREYmNEg9RCY0ST1RJjRMPURGSSY0Mj1l')
EXAMPLE_NAMES = {p['name'] for p in defaults('Starting 7')['players']}


def go(template):
    """Navigation callback: runs before the next script run, so the radio can change."""
    st.session_state['studio_template'] = template


# --- Week memory -------------------------------------------------------------

def save_week():
    """Store match, standings, calendar and CSI matches in the browser archive."""
    models = st.session_state.get('studio_models', {})
    table = models.get('Classifica')
    calendar = models.get('Calendario')
    week = dict(
        match=sanitize_match(st.session_state.get('shared_match')),
        updated=dt.datetime.now().isoformat(timespec='minutes'),
        standings=[dict(r_) for r_ in table['standings'][:table['team_count']]] if table else [],
        fixtures=[dict(f) for f in calendar['fixtures'][:calendar['fixture_count']]] if calendar else [],
        month_label=calendar['month_label'] if calendar else '',
        matches=matches_to_week(st.session_state.get('csi_matches') or []),
    )
    st.session_state['week_saved'] = week['updated']
    queue_save('Settimana', 'Settimana', sanitize_week(week), WEEK_ID)


def restore_week(library):
    """Once per session: bring back last week's match, standings and calendar."""
    if st.session_state.get('week_restored'):
        return
    st.session_state['week_restored'] = True
    week = library.get('week')
    if not week or st.session_state.get('shared_match'):
        return
    models = st.session_state.setdefault('studio_models', {})
    revisions = st.session_state.setdefault('studio_revisions', {})
    apply_match_everywhere(week['match'])
    if week['standings']:
        models['Classifica'] = sanitize_config('Classifica', with_rows(current_config('Classifica'), week['standings']))
    if week['fixtures']:
        cal = current_config('Calendario')
        cal['fixtures'] = week['fixtures']+cal['fixtures'][len(week['fixtures']):]
        cal['fixture_count'] = len(week['fixtures'])
        if week['month_label']:
            cal['month_label'] = week['month_label']
        models['Calendario'] = sanitize_config('Calendario', cal)
    for template in ('Classifica', 'Calendario'):
        revisions[template] = revisions.get(template, 0)+1
    st.session_state['csi_matches'] = matches_from_week(week)
    st.session_state['week_saved'] = week['updated']


# --- Squad register ----------------------------------------------------------

def squad(library):
    if 'squad' not in st.session_state:
        st.session_state['squad'] = list(library.get('squad') or [])
    return st.session_state['squad']


def save_squad(players):
    players = sanitize_squad(players)
    st.session_state['squad'] = players
    queue_save('Rosa', 'Rosa', {'players': players}, SQUAD_ID)
    return players


def player_label(p):
    return f"{p['number']:>2}  {p['name']}" + (f"  ({p['role']})" if p['role'] != '-' else '')


# --- What is still missing ---------------------------------------------------

def data_status(template, config):
    """Short list of what still looks like example data."""
    todo = []
    if template == 'Matchday Screen':
        if config['date'] == 'GG/MM/AAAA': todo.append('data')
        if config['kickoff'] == 'HH:MM': todo.append('orario')
        if 'AVVERSARI' in (config['home_name'], config['away_name']): todo.append('avversari')
    elif template == 'Convocati':
        active = config['roster'][:config['roster_count']]
        if any(p['name'].startswith('GIOCATORE ') for p in active): todo.append('nomi dei convocati')
        if config['meeting_time'] == 'HH:MM': todo.append('ritrovo')
        if config['opponent'] == 'AVVERSARI': todo.append('avversari')
    elif template == 'Starting 7':
        if any(p['name'] in EXAMPLE_NAMES for p in config['players']): todo.append('i sette titolari')
    elif template == 'Full Time':
        if config['date'] == 'GG/MM/AAAA': todo.append('data')
        if 'AVVERSARI' in (config['home_name'], config['away_name']): todo.append('avversari')
        if not config['home_scorers'].strip() and not config['away_scorers'].strip() and config['home_score']+config['away_score'] > 0:
            todo.append('marcatori')
    elif template == 'Classifica':
        if any(r_['team'].startswith('SQUADRA ') for r_ in config['standings'][:config['team_count']]): todo.append('classifica vera')
    elif template == 'Calendario':
        if any(f['opponent'].startswith('AVVERSARI ') for f in config['fixtures'][:config['fixture_count']]): todo.append('partite vere')
    return todo


def thumbnail(root, template, library):
    config, home, away, font_bytes = resolve_assets(root, template, current_config(template), library['assets'])
    signature = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()+(home or b'')+(away or b'')
                               + (font_bytes or b'')).hexdigest()
    cache = st.session_state.setdefault('thumbs', {})
    if cache.get(template, {}).get('signature') != signature:
        module = MODULES[template]
        if template == 'Starting 7':
            image = r.compose(r.scene(config, home, font_bytes, 1), animated=False)
        else:
            image = output_image(module.compose(module.scene(config, home, away, font_bytes, 1), animated=False),
                                 'Post 4:5', 1)
        image.thumbnail((300, 380))
        cache[template] = {'signature': signature, 'image': image}
    return cache[template]['image']


# --- Page --------------------------------------------------------------------

def show_csi(library):
    with st.container(border=True):
        st.markdown('#### ① Aggiorna dal sito CSI')
        saved = st.session_state.get('week_saved')
        st.caption(('Ultimo aggiornamento: '+saved.replace('T', ' alle ')) if saved else
                   'Nessun aggiornamento in questa settimana: apri il girone e tocca il segnalibro.')
        st.markdown('Apri il girone su CSI LIVE e tocca il segnalibro **Invia a Flamingos**: arrivano '
                    'classifica, prossima partita e calendario del mese, in tutte le grafiche.')
        st.link_button('Apri il Girone D su CSI LIVE', CSI_GIRONE, type='primary', width='stretch')
        with st.expander('Installa o aggiorna il segnalibro'):
            code = bookmarklet()
            components.html('''<style>a{display:inline-block;padding:10px 18px;border-radius:9px;background:#e95396;color:#110d14;
                font:600 15px system-ui,sans-serif;text-decoration:none;cursor:grab}p{color:#bca9c5;font:13px system-ui,sans-serif;margin:8px 0 0}</style>
                <a href="'''+code.replace('"', '&quot;')+'''" onclick="return false">Invia a Flamingos</a>
                <p>Mac: trascina il pulsante nella barra dei Preferiti di Safari o Chrome.</p>''', height=86)
            st.markdown('**iPhone / iPad:** aggiungi un segnalibro qualsiasi chiamato *Invia a Flamingos*, poi in '
                        '*Modifica* sostituisci l\'indirizzo con questo codice.')
            st.code(code, language=None, wrap_lines=True)


def show_match_form(library):
    assets = library['assets']
    match = sanitize_match(st.session_state.get('shared_match'))
    logos = [id_ for id_, a in assets.items() if a['kind'] == 'logo']
    label = lambda x: {'default': 'Flamingos - incluso', 'none': 'Scudo con ?'}.get(x, assets.get(x, {}).get('name', x))
    with st.container(border=True):
        st.markdown('#### ② Partita della settimana')
        st.caption('Arriva dal segnalibro; puoi correggerla qui. Va in tutte le grafiche, senza toccare stile e posizioni.')
        with st.form('shared_match_form', border=False):
            values = {}
            a, b = st.columns([3, 2])
            values['opponent'] = a.text_input('Avversari', match['opponent'], max_chars=42)
            values['our_side'] = b.radio('Giochiamo', ('Casa', 'Ospiti'), index=0 if match['our_side'] == 'Casa' else 1, horizontal=True)
            a, b, c_ = st.columns(3)
            values['date'] = a.text_input('Data', match['date'], max_chars=24)
            values['meeting_time'] = b.text_input('Ritrovo', match['meeting_time'], max_chars=14)
            values['kickoff'] = c_.text_input('Calcio d\'inizio', match['kickoff'], max_chars=14)
            values['venue'] = st.text_input('Campo / indirizzo', match['venue'], max_chars=72)
            a, b, c_ = st.columns([2, 1, 2])
            options = ['none', 'default']+logos
            values['opponent_logo_id'] = a.selectbox('Stemma avversari', options, format_func=label,
                index=options.index(match['opponent_logo_id']) if match['opponent_logo_id'] in options else 0)
            values['round'] = b.number_input('Giornata', 1, 80, match['round'], step=1)
            values['our_name'] = c_.text_input('La nostra squadra', match['our_name'], max_chars=42)
            if st.form_submit_button('Applica a tutte le grafiche', type='primary', width='stretch'):
                values['our_logo_id'] = match['our_logo_id']
                apply_match_everywhere(values)
                save_week()
                st.session_state['match_applied'] = True
                st.rerun()
        if st.session_state.pop('match_applied', False):
            st.success('Fatto: partita copiata in tutte le grafiche e salvata nel browser.')


def show_squad(library):
    with st.container(border=True):
        st.markdown('#### ③ La rosa')
        players = squad(library)
        st.caption(f'{len(players)} giocatori salvati nel browser. Li scegli con un clic in Convocati, Starting 7 e marcatori.'
                   if players else 'Scrivi qui i giocatori una volta sola: poi li scegli con un clic in Convocati, Starting 7 e marcatori.')
        with st.expander('Modifica la rosa', expanded=not players):
            rows = players or [dict(number=0, name='', role='-')]
            edited = st.data_editor(rows, num_rows='dynamic', hide_index=True, width='stretch', key='squad_editor',
                column_config={'number': st.column_config.NumberColumn('N.', min_value=0, max_value=99, step=1, width='small'),
                               'name': st.column_config.TextColumn('Nome', max_chars=27),
                               'role': st.column_config.SelectboxColumn('Ruolo', options=list(SQUAD_ROLES), width='small')})
            edited = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
            a, b = st.columns(2)
            if a.button('Salva la rosa', type='primary', width='stretch', key='squad_save'):
                saved = save_squad(edited)
                st.session_state['squad_msg'] = f'Rosa salvata: {len(saved)} giocatori.'
                st.rerun()
            if b.button('Prendi i nomi dai Convocati', width='stretch', key='squad_from_roster'):
                roster = current_config('Convocati')
                found = [dict(number=p['number'], name=p['name'], role=p['role']) for p in roster['roster']
                         if p['name'].strip() and not p['name'].startswith('GIOCATORE ')]
                saved = save_squad(players+found)
                st.session_state['squad_msg'] = f'Rosa aggiornata: {len(saved)} giocatori.'
                st.rerun()
            st.caption('P portiere / D difensore / C centrocampista / A attaccante. Aggiungi righe con il + in fondo alla tabella.')
        if st.session_state.get('squad_msg'):
            st.success(st.session_state.pop('squad_msg'))


def show_graphics(root, library):
    st.markdown('#### ④ Le grafiche della settimana')
    st.caption('Tocca **Apri** per modificare. In giallo quello che sembra ancora un dato di esempio.')
    for row in (STEPS[:3], STEPS[3:]):
        columns = st.columns(3)
        for column, (template, title, subtitle) in zip(columns, row):
            with column, st.container(border=True):
                config = current_config(template)
                todo = data_status(template, config)
                st.markdown(f'**{title}** · {subtitle}')
                try:
                    st.image(thumbnail(root, template, library), width='stretch')
                except Exception as exc:  # a broken asset must not hide the whole page
                    st.caption(f'Anteprima non disponibile: {exc}')
                if todo:
                    st.warning('Da completare: '+', '.join(todo), icon='✏️')
                else:
                    st.success('Pronta', icon='✅')
                st.button('Apri', key='open_'+template, on_click=go, args=(template,), width='stretch')


def show_week(root: Path, library):
    st.subheader('LA TUA SETTIMANA')
    st.caption('Tutto in ordine: aggiorna dal CSI, controlla la partita, poi apri le grafiche una alla volta.')
    if st.session_state.get('standings_message'):
        st.success(st.session_state.pop('standings_message'), icon='📡')
    if st.session_state.get('standings_import_error'):
        st.error('Il segnalibro ha inviato una pagina senza classifica leggibile: '+st.session_state.pop('standings_import_error'))
    left, right = st.columns(2, gap='large')
    with left:
        show_csi(library)
        show_squad(library)
    with right:
        show_match_form(library)
    st.divider()
    show_graphics(root, library)
    st.divider()
    show_kit(root, library)
