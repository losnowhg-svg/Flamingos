"""Flamingos Studio 1.9 - CRT graphics, standings, transitions, TV mockup and event themes."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='Flamingos Studio',page_icon='F',layout='wide')
st.markdown('''<style>
.stApp{background:#100d16;color:#f4edf5}
[data-testid="stSidebar"]{background:#19131f}
h1{letter-spacing:.035em;font-weight:800!important}
h2,h3{color:#f2dce8!important}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"]{background:#e95396;border:0;color:#110d14}
[data-testid="stCaptionContainer"]{color:#bca9c5}
[data-testid="stExpander"]{border-color:#3c2d44}
.block-container{padding-top:2.2rem}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#3c2d44!important;border-radius:14px}
button[data-baseweb="tab"] p{font-size:1rem;font-weight:650}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:5px 0}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:1rem}
h4{margin-bottom:.2rem!important}
@media (max-width:640px){.block-container{padding-left:.8rem;padding-right:.8rem}h1{font-size:1.6rem!important}}
</style>''',unsafe_allow_html=True)
st.title('FLAMINGOS STUDIO')
st.caption('1.9 / la settimana in ordine: aggiorna dal CSI, controlla, scarica')

from library import show_library
from studio_ui import show_studio
from sequence_ui import show_sequence, apply_match_everywhere
from week_ui import show_week, restore_week, save_week
from classifica_data import QUERY_KEY, with_rows
from csi_page import decode_payload, read_page, fixtures_for_month, month_name
from calendario_renderer import empty_fixture
from studio_state import defaults, sanitize_config, sanitize_match

PAGES = {
    'Settimana':'🏠  La tua settimana',
    'Matchday Screen':'Matchday - prima della partita',
    'Convocati':'Convocati - la rosa',
    'Starting 7':'Starting 7 - in campo',
    'Full Time':'Full Time - il risultato',
    'Classifica':'Classifica - il girone',
    'Calendario':'Calendario - il mese',
    'Sequenza video':'🎬  Video con transizioni',
}

# Girone page sent by the "Invia a Flamingos" bookmark: standings, next match, calendar.
incoming = st.query_params.get(QUERY_KEY)
if incoming:
    try:
        page = read_page(decode_payload(incoming), sanitize_match(st.session_state.get('shared_match'))['our_name'])
        if not page['standings']:
            raise ValueError('nessuna classifica nella pagina inviata.')
        models = st.session_state.setdefault('studio_models',{})
        revisions = st.session_state.setdefault('studio_revisions',{})
        current = sanitize_config('Classifica',models.get('Classifica',defaults('Classifica')))
        models['Classifica'] = sanitize_config('Classifica',with_rows(current,page['standings']))
        revisions['Classifica'] = revisions.get('Classifica',0)+1
        st.session_state.pop('png_Classifica',None)
        parts = [f"classifica ({len(page['standings'])} squadre)"]
        st.session_state['csi_matches'] = page['matches']
        if page['fields']:
            match = dict(sanitize_match(st.session_state.get('shared_match')),**page['fields'])
            apply_match_everywhere(match)
            parts.append(f"prossima partita: vs {page['fields']['opponent']} il {page['fields']['date']} alle {page['fields']['kickoff']}")
            if page['matches']:
                when = page['next']['date']
                fixtures = fixtures_for_month(page['matches'],match['our_name'],when.year,when.month,8)
                if fixtures:
                    cal_config = sanitize_config('Calendario',models.get('Calendario',defaults('Calendario')))
                    cal_config['fixtures'] = fixtures+[empty_fixture() for _ in range(len(fixtures),8)]
                    cal_config['fixture_count'] = len(fixtures)
                    cal_config['month_label'] = f'{month_name(when.month)} {when.year}'
                    models['Calendario'] = sanitize_config('Calendario',cal_config)
                    revisions['Calendario'] = revisions.get('Calendario',0)+1
                    parts.append(f'calendario di {month_name(when.month).lower()}')
        elif page['matches']:
            parts.append(f"{len(page['matches'])} partite (nessuna prossima gara dei Flamingos trovata)")
        st.session_state['standings_message'] = 'Dal sito CSI: '+'; '.join(parts)+'. Salvato nel browser.'
        st.session_state['week_restored'] = True
        save_week()
    except ValueError as exc:
        st.session_state['standings_import_error'] = str(exc)
    st.session_state['studio_template'] = 'Settimana'
    st.query_params.clear()

with st.sidebar:
    st.header('Il tuo studio')
    if st.session_state.get('studio_template') not in PAGES:
        st.session_state['studio_template'] = 'Settimana'
    template = st.radio('Vai a',list(PAGES),format_func=PAGES.get,key='studio_template')

library = show_library()
if library is None:
    st.info('Caricamento dell\'archivio font e stemmi dal browser. Se il browser lo blocca, usa Continua senza archivio nella barra laterale.')
    st.stop()
restore_week(library)
root = Path(__file__).resolve().parent
if template == 'Settimana':
    show_week(root,library)
elif template == 'Sequenza video':
    show_sequence(root,library)
else:
    show_studio(root,template,library)
