"""La tua settimana: the home page, the squad register and the week memory."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

import streamlit as st
import themes
import streamlit.components.v1 as components

import renderer as r
from classifica_data import bookmarklet, with_rows
from crt_presets import output_image
from library import queue_save
from sequence_ui import apply_match_everywhere, current_config, resolve_assets, show_kit
import avatars
from ui_utils import countdown
from studio_state import (DEFAULTS, MODULES, SQUAD_ID, SQUAD_ROLES, STAFF_ROLES, WEEK_ID, defaults, matches_from_week,
                          matches_to_week, sanitize_config, sanitize_match, sanitize_squad, sanitize_week)

STEPS = (
    ('Matchday Screen', 'Matchday', 'Prima della partita'),
    ('Convocati', 'Convocati', 'Chi viene'),
    ('Full Time', 'Full Time', 'Il risultato'),
    ('Classifica', 'Classifica', 'Il girone'),
    ('Calendario', 'Calendario', 'Il mese'),
)
CSI_GIRONE = ('https://live.centrosportivoitaliano.it/26/Calcio-a-7/Lombardia/Brescia/C102/'
              '?j=NEU9REZJJjRGPVBOSyY0Rz1FREYmNEg9RCY0ST1RJjRMPURGSSY0Mj1l')
EXAMPLE_NAMES = {p['name'] for p in defaults('Starting 7')['players']}
from team_looks import OFFICIAL_SQUAD
ROLE_HELP = 'P portiere / D difensore / C centrocampista / A attaccante / ALL allenatore / DIR dirigente.'


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
        sponsor=st.session_state.get('sponsor') or {},
        season=[dict(g, date=g['date'].isoformat() if hasattr(g['date'], 'isoformat') else g['date'])
                for g in st.session_state.get('season_games') or []],
        scorers=st.session_state.get('season_scorers') or [],
    )
    st.session_state['week_saved'] = week['updated']
    queue_save('Settimana', 'Settimana', sanitize_week(week), WEEK_ID)


def restore_week(library):
    """Once per session: bring back last week's match, standings and calendar."""
    if st.session_state.get('week_restored'):
        return
    st.session_state['week_restored'] = True
    week = library.get('week')
    if week:
        st.session_state.setdefault('sponsor', week.get('sponsor') or {})
        st.session_state.setdefault('season_games', [dict(g, date=dt.date.fromisoformat(g['date'])) for g in week.get('season', [])])
        st.session_state.setdefault('season_scorers', week.get('scorers', []))
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


# --- CSI import: bookmark or pasted page --------------------------------------

def import_csi(payload):
    """Standings, next match and month calendar from a girone page; returns the message."""
    from classifica_data import with_rows as _with_rows
    from csi_page import read_page, fixtures_for_month, month_name
    from calendario_renderer import empty_fixture
    page = read_page(payload, sanitize_match(st.session_state.get('shared_match'))['our_name'])
    if not page['standings']:
        raise ValueError('nessuna classifica nella pagina.')
    models = st.session_state.setdefault('studio_models', {})
    revisions = st.session_state.setdefault('studio_revisions', {})
    current = sanitize_config('Classifica', models.get('Classifica', defaults('Classifica')))
    models['Classifica'] = sanitize_config('Classifica', _with_rows(current, page['standings']))
    revisions['Classifica'] = revisions.get('Classifica', 0)+1
    st.session_state.pop('png_Classifica', None)
    parts = [f"classifica ({len(page['standings'])} squadre)"]
    st.session_state['csi_matches'] = page['matches']
    if page['fields']:
        match = dict(sanitize_match(st.session_state.get('shared_match')), **page['fields'])
        apply_match_everywhere(match)
        parts.append(f"prossima partita: vs {page['fields']['opponent']} il {page['fields']['date']} alle {page['fields']['kickoff']}")
        when = page['next']['date']
        fixtures = fixtures_for_month(page['matches'], match['our_name'], when.year, when.month, 8)
        if fixtures:
            cal_config = sanitize_config('Calendario', models.get('Calendario', defaults('Calendario')))
            cal_config['fixtures'] = fixtures+[empty_fixture() for _ in range(len(fixtures), 8)]
            cal_config['fixture_count'] = len(fixtures)
            cal_config['month_label'] = f'{month_name(when.month)} {when.year}'
            models['Calendario'] = sanitize_config('Calendario', cal_config)
            revisions['Calendario'] = revisions.get('Calendario', 0)+1
            parts.append(f'calendario di {month_name(when.month).lower()}')
    elif page['matches']:
        parts.append(f"{len(page['matches'])} partite (nessuna prossima gara dei Flamingos trovata)")
    st.session_state['week_restored'] = True
    save_week()
    return 'Dal sito CSI: '+'; '.join(parts)+'. Salvato nel browser.'


# --- Squad register ----------------------------------------------------------

def squad(library):
    if 'squad' not in st.session_state:
        st.session_state['squad'] = list(library.get('squad') or [])
    return st.session_state['squad']


def save_squad(players):
    """Save the squad; avatars follow their player by name when the table drops them."""
    old = {p['name']: p for p in st.session_state.get('squad', [])}
    players = [dict(p) for p in players]
    for p in players:
        name = ' '.join(str(p.get('name', '')).upper().split())
        for field in ('avatar', 'look', 'ig'):
            if field not in p and old.get(name, {}).get(field):
                p[field] = old[name][field]
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
                   'Nessun aggiornamento in questa settimana.')
        st.markdown('Arrivano classifica, prossima partita e calendario del mese, in tutte le grafiche.')
        st.link_button('Apri il Girone D su CSI LIVE', CSI_GIRONE, type='primary', width='stretch')
        mark, paste = st.tabs(['🔖 Con il segnalibro', '📋 Incolla la pagina'])
        with mark:
            st.caption('Sulla pagina del girone tocca il segnalibro **Invia a Flamingos**: torni qui con tutto aggiornato.')
            with st.expander('Installa o aggiorna il segnalibro'):
                code = bookmarklet()
                components.html('''<style>a{display:inline-block;padding:10px 18px;border-radius:9px;background:#e95396;color:#110d14;
                    font:600 15px system-ui,sans-serif;text-decoration:none;cursor:grab}p{color:#bca9c5;font:13px system-ui,sans-serif;margin:8px 0 0}</style>
                    <a href="'''+code.replace('"', '&quot;')+'''" onclick="return false">Invia a Flamingos</a>
                    <p>Computer: trascina il pulsante nella barra dei preferiti (Safari, Chrome, Edge, Firefox).</p>''', height=86)
                st.markdown(
                    '**Mac:** in Safari o Chrome mostra la barra dei preferiti (*Vista > Mostra barra dei preferiti*, '
                    'oppure Cmd+Maiusc+B) e trascinaci il pulsante rosa.\n\n'
                    '**Windows (Chrome, Edge, Firefox):** mostra la barra dei preferiti con **Ctrl+Maiusc+B** e '
                    'trascinaci il pulsante rosa. Se il trascinamento non va: tasto destro sulla barra > *Aggiungi '
                    'pagina* (Chrome) o *Aggiungi preferito* (Edge, Firefox), nome *Invia a Flamingos*, e come indirizzo '
                    'incolla il codice qui sotto.\n\n'
                    '**iPhone / iPad:** aggiungi un segnalibro qualsiasi chiamato *Invia a Flamingos*, poi in '
                    '*Modifica* sostituisci l\'indirizzo con il codice qui sotto. Sulla pagina del girone aprilo dai '
                    'Preferiti.\n\n'
                    '**Android (Chrome):** aggiungi la pagina ai preferiti (stellina nel menu ⋮), poi in *Preferiti* > '
                    '*Modifica* chiamalo *Invia a Flamingos* e come URL incolla il codice qui sotto. Per usarlo, sulla '
                    'pagina del girone **scrivi Invia a Flamingos nella barra degli indirizzi** e tocca il segnalibro che '
                    'compare tra i suggerimenti (aprirlo dall\'elenco dei preferiti non funziona).')
                st.code(code, language=None, wrap_lines=True)
        with paste:
            st.caption('Apri il girone, tieni premuto sul testo > **Seleziona tutto** > **Copia**, poi incolla qui sotto. '
                       'Va bene anche solo la tabella della classifica.')
            pasted = st.text_area('Pagina del girone', height=130, key='csi_paste', label_visibility='collapsed',
                                  placeholder='Incolla qui il testo della pagina del girone')
            if st.button('Leggi la pagina', key='csi_paste_read', type='primary', width='stretch', disabled=not pasted.strip()):
                try:
                    st.session_state['standings_message'] = import_csi({'u': '', 't': '', 'x': pasted})
                except ValueError as exc:
                    st.error(f'Non riesco a leggere la pagina: {exc} Copia di nuovo, partendo dalla classifica.')
                else:
                    st.rerun()


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
                index=options.index(match['opponent_logo_id']) if match['opponent_logo_id'] in options else 0,
                help='Per le squadre del girone lo stemma si mette da solo quando arriva la partita dal CSI.')
            values['round'] = b.number_input('Giornata', 1, 80, match['round'], step=1)
            values['our_name'] = c_.text_input('La nostra squadra', match['our_name'], max_chars=42)
            values['event'] = st.selectbox('Che partita è?', themes.MATCH_EVENTS, format_func=themes.event_label,
                index=themes.MATCH_EVENTS.index(match.get('event', 'auto')),
                help='Cambia il tema delle grafiche. Automatico: big match se siamo entrambe in alto in classifica, '
                     'ultima giornata se il calendario CSI non ha altre partite; altrimenti il tema di stagione.')
            if st.form_submit_button('Applica a tutte le grafiche', type='primary', width='stretch'):
                values['our_logo_id'] = match['our_logo_id']
                apply_match_everywhere(values)
                save_week()
                st.session_state['match_applied'] = True
                st.rerun()
        if st.session_state.pop('match_applied', False):
            st.success('Fatto: partita copiata in tutte le grafiche e salvata nel browser.')
        import crests
        with st.expander(f'🛡️ Stemmi del girone ({len(crests.builtin_assets())})'):
            st.caption('Già pronti nell\'app, su qualsiasi dispositivo: quando l\'avversario è una di queste squadre '
                       'lo stemma va da solo in Matchday, Full Time e nelle altre grafiche.')
            items = list(crests.builtin_assets().items())
            for row in range(0, len(items), 4):
                for column, (_, asset) in zip(st.columns(4), items[row:row+4]):
                    column.image(asset['bytes'], caption=asset['name'].replace(' (girone)', ''), width='stretch')


def show_sponsor(library):
    import sponsor
    from studio_state import sanitize_sponsor
    with st.expander('🤝 Sponsor', expanded=False):
        settings = sanitize_sponsor(st.session_state.get('sponsor'))
        logos = {id_: a['name'] for id_, a in library['assets'].items() if a['kind'] == 'logo' and not a.get('builtin')}
        st.caption('Il logo dello sponsor va in un piccolo adesivo sotto lo schermo di tutte le grafiche, sul televisore '
                   'del mockup e, se vuoi, in una slide finale dei video.')
        if not logos:
            st.info('Carica prima il logo dello sponsor con **+ Stemmi** nella barra laterale (Archivio).')
            return
        options = ['none']+list(logos)
        with st.form('sponsor_form', border=False):
            on = st.toggle('Mostra lo sponsor', settings['on'])
            logo_id = st.selectbox('Logo', options, index=options.index(settings['logo_id']) if settings['logo_id'] in options else 0,
                                   format_func=lambda x: 'Scegli...' if x == 'none' else logos[x])
            name = st.text_input('Nome (facoltativo)', settings['name'], max_chars=24, placeholder='es. Pizzeria Da Mario')
            end = st.checkbox('Slide di ringraziamento alla fine dei video', settings['end_slide'])
            if st.form_submit_button('Applica a tutte le grafiche', type='primary', width='stretch'):
                st.session_state['sponsor'] = sanitize_sponsor(dict(on=on and logo_id != 'none', logo_id=logo_id, name=name,
                                                                    end_slide=end))
                for key in [k for k in st.session_state if k.startswith(('png_', 'preview_', 'thumbs'))]:
                    st.session_state.pop(key, None)
                save_week()
                st.rerun()
        current = dict(sponsor_on=True, sponsor_logo_id=settings['logo_id'], sponsor_name=settings['name'])
        sponsor.register(library['assets'])
        pill = sponsor.sticker(current, 2) if settings['logo_id'] != 'none' else None
        if pill is not None:
            st.image(pill, caption='L\'adesivo sotto lo schermo' + ('' if settings['on'] else ' (spento)'))


def show_squad(library):
    with st.container(border=True):
        st.markdown('#### ③ La rosa')
        players = squad(library)
        staff = [p for p in players if p['role'] in STAFF_ROLES]
        faces = sum(1 for p in players if p.get('look') or p.get('avatar'))
        st.caption(f'{len(players)-len(staff)} giocatori e {len(staff)} dello staff salvati nel browser, {faces} con avatar. '
                   'Li scegli con un clic in Convocati e marcatori.' if players else
                   'Scrivi qui la rosa una volta sola (o carica quella ufficiale): poi la scegli con un clic.')
        with st.expander('Modifica la rosa', expanded=not players):
            rows = [dict(number=p['number'], name=p['name'], role=p['role'], ig=p.get('ig', '')) for p in players] \
                or [dict(number=0, name='', role='-', ig='')]
            edited = st.data_editor(rows, num_rows='dynamic', hide_index=True, width='stretch', key='squad_editor',
                column_config={'number': st.column_config.NumberColumn('N.', min_value=0, max_value=99, step=1, width='small'),
                               'name': st.column_config.TextColumn('Nome', max_chars=27),
                               'role': st.column_config.SelectboxColumn('Ruolo', options=list(SQUAD_ROLES), width='small'),
                               'ig': st.column_config.TextColumn('Instagram', max_chars=31, help='Senza @: serve per taggarli nelle didascalie')})
            edited = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
            a, b = st.columns(2)
            if a.button('Salva la rosa', type='primary', width='stretch', key='squad_save'):
                saved = save_squad(edited)
                st.session_state['squad_msg'] = f'Rosa salvata: {len(saved)} persone.'
                st.rerun()
            if b.button('Carica la rosa ufficiale', width='stretch', key='squad_official',
                        help='Giocatori, mister e dirigenti 2026/27 con i loro sprite già pronti. '
                             'Gli sprite che hai già personalizzato restano.'):
                mine = {p['name']: p for p in players}
                official = []
                for entry in OFFICIAL_SQUAD:
                    entry = dict(entry)
                    if mine.get(entry['name'], {}).get('look'):
                        entry['look'] = mine[entry['name']]['look']   # keep the customised sprite
                    if mine.get(entry['name'], {}).get('ig'):
                        entry['ig'] = mine[entry['name']]['ig']
                    official.append(entry)
                others = [p for p in players if p['name'] not in {e['name'] for e in OFFICIAL_SQUAD}]
                saved = save_squad(official+others)
                st.session_state['squad_msg'] = f'Rosa ufficiale caricata: {len(saved)} persone, con gli sprite.'
                st.rerun()
            if players and st.button('Rimetti gli sprite ufficiali a tutti', width='stretch', key='squad_official_looks',
                                     help='Sovrascrive gli sprite personalizzati di chi è nella rosa ufficiale.'):
                looks = {e['name']: e['look'] for e in OFFICIAL_SQUAD}
                save_squad([dict(p, look=looks[p['name']]) if p['name'] in looks else dict(p) for p in players])
                st.session_state.pop('look_loaded', None)
                st.session_state['squad_msg'] = 'Sprite ufficiali rimessi.'
                st.rerun()
            st.caption(ROLE_HELP+' Aggiungi righe con il + in fondo alla tabella; N. 0 = senza numero.')
        show_avatar_maker(players)
        if st.session_state.get('squad_msg'):
            st.success(st.session_state.pop('squad_msg'))


def show_avatar_maker(players):
    import pixel_character as pc
    with st.expander('🕹️ Avatar pixel dei giocatori', expanded=False):
        if not players:
            st.caption('Prima salva la rosa.')
            return
        done = [p for p in players if p.get('look')]
        if done:
            columns = st.columns(6)
            for i, p in enumerate(done):
                columns[i % 6].image(avatars.enlarge(pc.image(p['look']), 128), caption=p['name'], width='stretch')
        st.caption('Personaggi stilizzati: scegli capelli, barba e occhiali. Una foto (facoltativa) suggerisce '
                   'i colori di pelle, capelli e barba; la foto non viene salvata.')
        names = [p['name'] for p in players]
        who = st.selectbox('Chi', names, format_func=lambda n: n+('  ✓' if any(p['name'] == n and p.get('look') for p in players) else ''),
                           key='look_who')
        person = next(p for p in players if p['name'] == who)
        if st.session_state.get('look_loaded') != who:
            # Switching person: load their saved look into the controls.
            look = pc.sanitize(person.get('look')) or dict(pc.DEFAULT_LOOK)
            st.session_state.update({'look_'+k: v for k, v in look.items()}, look_loaded=who)
        upload = st.file_uploader('Foto per i colori (facoltativa)', type=['jpg', 'jpeg', 'png', 'webp'], key='look_photo')
        if upload:
            digest = hashlib.sha256(upload.getvalue()).hexdigest()[:12]
            if st.session_state.get('look_digest') != digest+who:
                try:
                    colors = pc.colors_from_photo(avatars.load_photo(upload.getvalue()))
                except ValueError as exc:
                    st.error(str(exc)); colors = {}
                if colors:
                    st.session_state.update({'look_'+k: v for k, v in colors.items()})
                else:
                    st.caption('Non ho trovato il viso nella foto: scegli i colori a mano.')
                st.session_state['look_digest'] = digest+who
        a, b = st.columns(2)
        with a:
            st.selectbox('Capelli', list(pc.HAIR_STYLES), format_func=pc.HAIR_STYLES.get, key='look_hair')
            st.selectbox('Barba', list(pc.BEARDS), format_func=pc.BEARDS.get, key='look_beard')
            st.selectbox('Occhiali', list(pc.GLASSES), format_func=pc.GLASSES.get, key='look_glasses')
            st.selectbox('Sopracciglia', list(pc.BROWS), format_func=pc.BROWS.get, key='look_brows')
            st.selectbox('Viso', list(pc.FACES), format_func=pc.FACES.get, key='look_face')
            st.selectbox('Espressione', list(pc.EXPRESSIONS), format_func=pc.EXPRESSIONS.get, key='look_expression')
        with b:
            st.color_picker('Pelle', key='look_skin')
            st.color_picker('Capelli e sopracciglia', key='look_hair_color')
            st.color_picker('Barba', key='look_beard_color')
            st.selectbox('Occhi', list(pc.EYES), format_func=pc.EYES.get, key='look_eyes')
            if st.session_state.get('look_accessory') == 'orecchini':   # old looks: earrings are a checkbox now
                st.session_state.update(look_accessory='nessuno', look_earrings=True)
            st.selectbox('Accessorio', [k for k in pc.ACCESSORIES if k != 'orecchini'], format_func=pc.ACCESSORIES.get,
                         key='look_accessory')
            if st.session_state.get('look_accessory', 'nessuno') != 'nessuno':
                st.color_picker('Colore accessorio', key='look_accessory_color')
            st.checkbox('Orecchini', key='look_earrings')
        look = pc.sanitize({k: st.session_state.get('look_'+k) for k in pc.DEFAULT_LOOK})
        a, b = st.columns(2)
        a.image(pc.idle_gif(look, 'arcade', 256), caption='Arcade luce neon (tutti i preset)', width='stretch')
        b.image(pc.idle_gif(look, 'gameboy', 256), caption='Game Boy (preset Pocket verde)', width='stretch')
        st.caption('Anteprima animata: così si muovono nei video (palpebre, occhiolino, sorriso, riflesso sugli occhiali).')
        import variety
        columns = st.columns(len(pc.POSES)-1)
        for column, pose in zip(columns, [p for p in pc.POSES if p != 'ferma']):
            column.image(avatars.enlarge(pc.image(look, 'arcade', pose=pose), 128), caption=variety.POSES[pose],
                         width='stretch')
        st.caption('Le pose compaiono nei reparti e nella foto di squadra (si scelgono lì).')
        a, b = st.columns(2)
        if a.button(f'Salva avatar di {who}', type='primary', width='stretch', key='look_save'):
            save_squad([dict(p, look=look) if p['name'] == who else dict(p) for p in players])
            st.session_state['squad_msg'] = f'Avatar di {who} salvato.'
            st.rerun()
        if person.get('look') and b.button('Togli il suo avatar', width='stretch', key='look_drop'):
            st.session_state['squad'] = [{k: v for k, v in p.items() if k not in ('look', 'avatar')} if p['name'] == who else p
                                         for p in players]
            save_squad(st.session_state['squad'])
            st.rerun()
        from instagram_ui import team_photo_png
        st.download_button('🖼 Scarica la foto di squadra pixel', team_photo_png(players, 'crt'),
                           file_name='flamingos_foto_squadra.png', mime='image/png', width='stretch', key='team_photo_week',
                           help='Tutta la rosa in sprite, per reparto (1080 x 1350). Altri formati e stile Game Boy '
                                'nella pagina Instagram.')


def show_graphics(root, library):
    st.markdown('#### ④ Le grafiche della settimana')
    ready = sum(1 for template, _, _ in STEPS if not data_status(template, current_config(template)))
    st.progress(ready/len(STEPS), text=f'{ready} su {len(STEPS)} pronte')
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
    line = countdown(sanitize_match(st.session_state.get('shared_match')))
    if line:
        st.info(line)
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
        show_sponsor(library)
    st.divider()
    show_graphics(root, library)
    st.divider()
    show_kit(root, library)
