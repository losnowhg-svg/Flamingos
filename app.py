"""Flamingos Studio 1.5: lineups, matchday and editable match results."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='Flamingos Studio', page_icon='F', layout='wide')
st.markdown('''<style>
.stApp{background:#10131c;color:#f7f8fc}
[data-testid="stSidebar"]{background:#191e2b;border-right:1px solid #364052}
.block-container{padding-top:1.8rem;max-width:1500px;padding-bottom:2rem}
h1{font-size:2rem!important;letter-spacing:.025em;font-weight:800!important}
h2,h3{color:#f7f8fc!important;letter-spacing:0!important}
[data-testid="stCaptionContainer"]{color:#c9d0df!important;font-size:.91rem;line-height:1.55}
[data-testid="stWidgetLabel"] p{font-size:.95rem!important;font-weight:600}
[data-testid="stExpander"]{border:1px solid #414c60;border-radius:12px;background:#171d29}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{border-color:#566278!important}
.stButton button,.stDownloadButton button{min-height:42px;border-radius:9px;font-weight:600}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"]{background:#ff86b7;color:#15121b;border:1px solid #ff86b7}
[data-baseweb="tab"]{font-size:1rem!important;min-height:46px;padding-left:16px;padding-right:16px}
[data-baseweb="tab-list"]{gap:8px;border-bottom:1px solid #414c60}
button:focus-visible,input:focus-visible{outline:2px solid #a3e7ff!important;outline-offset:3px}
.studio-kicker{font-size:.78rem;font-weight:700;letter-spacing:.16em;color:#ffadcf;margin-bottom:.25rem}
@media(max-width:760px){.block-container{padding-left:1rem;padding-right:1rem}h1{font-size:1.65rem!important}}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="studio-kicker">FLAMINGOS / SOCIAL GRAPHICS</div>', unsafe_allow_html=True)
st.title('Il tuo studio, dalla formazione al risultato.')
st.caption('Versione 1.5  /  Starting 7, Matchday e Match Result  /  PNG e MP4 senza servizi a pagamento')

from library import show_library
from studio_ui import show_studio

with st.sidebar:
    st.header('Flamingos Studio')
    template = st.radio('Scegli la grafica', ['Starting 7','Matchday Screen','Match Result'], key='studio_template')
    st.caption('1. Compila i contenuti\n\n2. Scegli stile e disposizione\n\n3. Genera i file nella scheda Esporta')
    st.divider()

library = show_library()
if library is None:
    st.info("Caricamento dell'archivio locale. Se il browser lo blocca, apri Archivio nella barra laterale e premi Continua senza archivio.")
    st.stop()
show_studio(Path(__file__).resolve().parent, template, library)
