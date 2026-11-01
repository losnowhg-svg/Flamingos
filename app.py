"""Flamingos Studio 2.0 - CRT graphics, standings, TV mockup, themes, pixel avatars and department slides."""
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
/* --- 3.6 phone layout ------------------------------------------------------------- */
.st-key-mobile_nav,.st-key-mobile_preview{display:none}
@media (max-width:640px){
 .block-container{padding-top:1rem!important}
 .st-key-app_head h1{font-size:1.15rem!important;margin:0!important;padding:.2rem 0!important}
 .st-key-app_head [data-testid="stCaptionContainer"]{display:none}
 .st-key-mobile_nav{display:block}
 .st-key-mobile_nav label{display:none}
 .st-key-page_head [data-testid="stCaptionContainer"]{display:none}
 .st-key-page_head h3{font-size:1.25rem!important;padding:.1rem 0!important}
 .st-key-mobile_preview{display:block;background:#100d16;padding:.35rem 0 .45rem;border-bottom:1px solid #3c2d44}
 /* sticky goes on the wrapper Streamlit puts around the container (the container alone has nowhere to slide) */
 div:has(> .st-key-mobile_preview){position:sticky!important;top:3.6rem;z-index:50;background:#100d16}
 .st-key-mobile_preview img{max-height:34vh;width:100%!important;object-fit:contain;display:block;border-radius:8px}
 .st-key-mobile_preview [data-testid="stCaptionContainer"]{text-align:center;margin-top:.15rem}
 .stButton button,.stDownloadButton button{min-height:44px}
 [data-testid="stSidebar"] [role="radiogroup"] label{padding:9px 0}
 .st-key-week_grid img{max-height:230px;object-fit:contain}
 button[data-baseweb="tab"]{padding-left:.4rem!important;padding-right:.4rem!important}
}
</style>''',unsafe_allow_html=True)
with st.container(key='app_head'):
    st.title('FLAMINGOS STUDIO')
    st.caption('3.13 / figurine e pagelle nello stile del preset, 10 brani nuovi')

from library import show_library
from studio_ui import show_studio
from sequence_ui import show_sequence, apply_match_everywhere
from week_ui import show_week, restore_week, import_csi
from classifica_data import QUERY_KEY
from csi_page import decode_payload

PAGES = {
    'Settimana':'🏠  La tua settimana',
    'Matchday Screen':'Matchday - prima della partita',
    'Convocati':'Convocati - la rosa',
    'Full Time':'Full Time - il risultato',
    'Classifica':'Classifica - il girone',
    'Calendario':'Calendario - il mese',
    'Figurine':'🃏  Figurine e pagelle',
    'Risultati':'📋  Risultati della giornata',
    'Sequenza video':'🎬  Video con transizioni',
    'Didascalie':'✍️  Didascalie',
    'Wrapped':'🎁  Flamingos Wrapped',
    'Instagram':'📱  Squadra e copertine',
}

# Girone page sent by the "Invia a Flamingos" bookmark: standings, next match, calendar.
incoming = st.query_params.get(QUERY_KEY)
if incoming:
    try:
        st.session_state['standings_message'] = import_csi(decode_payload(incoming))
    except ValueError as exc:
        st.session_state['standings_import_error'] = str(exc)
    st.session_state['studio_template'] = 'Settimana'
    st.query_params.clear()

def _from_phone_menu():
    st.session_state['studio_template'] = st.session_state['mobile_nav_select']


with st.sidebar:
    st.header('Il tuo studio')
    if st.session_state.get('studio_template') not in PAGES:
        st.session_state['studio_template'] = 'Settimana'
    template = st.radio('Vai a',list(PAGES),format_func=PAGES.get,key='studio_template')
# On a phone the sidebar hides behind a button: the same menu, one tap away at the top (CSS shows it only there).
if st.session_state.get('mobile_nav_select') != template:
    st.session_state['mobile_nav_select'] = template
with st.container(key='mobile_nav'):
    st.selectbox('Vai a', list(PAGES), format_func=PAGES.get, key='mobile_nav_select', on_change=_from_phone_menu)

library = show_library()
if library is None:
    st.info('Caricamento dell\'archivio font e stemmi dal browser. Se il browser lo blocca, usa Continua senza archivio nella barra laterale.')
    st.stop()
import crests
crests.register(library)        # the girone crests, next to the archive's own logos
import sponsor
sponsor.register(library['assets'])
restore_week(library)
root = Path(__file__).resolve().parent
if template == 'Settimana':
    show_week(root,library)
elif template == 'Sequenza video':
    show_sequence(root,library)
elif template == 'Didascalie':
    from caption_ui import show_captions
    show_captions(library)
elif template == 'Wrapped':
    from wrapped_ui import show_wrapped
    show_wrapped(root,library)
elif template == 'Instagram':
    from instagram_ui import show_instagram
    show_instagram(root,library)
elif template == 'Figurine':
    from figurine_ui import show_figurine
    show_figurine(root,library)
elif template == 'Risultati':
    from results_ui import show_results
    show_results(root,library)
else:
    show_studio(root,template,library)
