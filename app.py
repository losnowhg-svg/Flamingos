"""Flamingos Studio 1.6 - CRT graphics, standings, transitions and a match kit."""
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
@media (max-width:640px){.block-container{padding-left:.8rem;padding-right:.8rem}h1{font-size:1.6rem!important}}
</style>''',unsafe_allow_html=True)
st.title('FLAMINGOS STUDIO')
st.caption('1.6 / 11 preset CRT / Classifica / Sequenze video con transizioni / Kit partita')

from library import show_library
from studio_ui import show_studio
from sequence_ui import show_match_panel, show_sequence

PAGES = {
    'Matchday Screen':'Matchday - prima della partita',
    'Convocati':'Convocati - la rosa',
    'Starting 7':'Starting 7 - in campo',
    'Full Time':'Full Time - il risultato',
    'Classifica':'Classifica - il girone',
    'Sequenza video':'Sequenza video e kit',
}

with st.sidebar:
    st.header('Il tuo studio')
    template = st.radio('Cosa vuoi creare',list(PAGES),format_func=PAGES.get,key='studio_template')

library = show_library()
if library is None:
    st.info('Caricamento dell\'archivio font e stemmi dal browser. Se il browser lo blocca, usa Continua senza archivio nella barra laterale.')
    st.stop()
show_match_panel(library)
root = Path(__file__).resolve().parent
if template == 'Sequenza video':
    show_sequence(root,library)
else:
    show_studio(root,template,library)
