"""Flamingos Studio 1.4 - HD graphics and a persistent per-browser asset library."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='Flamingos Studio',page_icon='F',layout='wide')
st.markdown('''<style>
.stApp{background:#100d16;color:#f4edf5}
[data-testid="stSidebar"]{background:#19131f}
h1{letter-spacing:.035em;font-weight:800!important}
h2,h3{color:#f2dce8!important}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"]{background:#e95396;border:0;color:#110d14}
[data-testid="stCaptionContainer"]{color:#bca9c5}
[data-testid="stExpander"]{border-color:#3c2d44}
.block-container{padding-top:2.2rem}
</style>''',unsafe_allow_html=True)
st.title('FLAMINGOS STUDIO')
st.caption('1.4 / Grafica HD / Font riutilizzabili / Progetti e backup')

from library import show_library
from studio_ui import show_studio

with st.sidebar:
    st.header('Il tuo studio')
    template = st.radio('Modello',['Starting 7','Matchday Screen'],key='studio_template')

library = show_library()
if library is None:
    st.info('Caricamento dell\'archivio font e stemmi dal browser. Se il browser lo blocca, usa Continua senza archivio nella barra laterale.')
    st.stop()
show_studio(Path(__file__).resolve().parent,template,library)
