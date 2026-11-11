"""🎞 Intro della partita: the animated pixel intro that ends on the match poster (see intro.py)."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st

import intro
from studio_state import sanitize_match
from ui_utils import progress_with_eta

FORMATS = tuple(intro.FORMATS)


def _crests(library, opponent, chosen):
    """({id: label}, default id) of the logos to choose from: the girone's crests and the archive's."""
    import crests
    logos = {k: v['name'] for k, v in library.get('assets', {}).items() if v.get('kind') == 'logo'}
    auto = chosen if chosen in logos else crests.logo_id_for(opponent)
    return logos, auto if auto in logos else None


@st.cache_data(show_spinner=False, max_entries=8)
def _poster(texts_json, crest, fmt, look):
    return intro.poster_png(json.loads(texts_json), crest, fmt, 2, look)


def show_intro(root, library):
    st.subheader('🎞 INTRO DELLA PARTITA')
    st.caption('Un\'intro animata in pixel che finisce sulla locandina: il nostro fenicottero al neon, lo stemma avversario '
               'che entra in scena, il faccia a faccia con il VS sul drop della musica, poi giorno, ora e campo. '
               'Si costruisce da sola con la partita della settimana.')
    match = sanitize_match(st.session_state.get('shared_match'))
    base = intro.texts_for(match)
    tag = hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()[:8]     # new match: fresh fields
    preview, controls = st.columns([1, 1.15], gap='large')
    with controls:
        if not base['opponent'] or base['opponent'] == 'AVVERSARI':
            st.info('Manca l\'avversario: scegli la partita nella Settimana (② La partita), oppure scrivilo qui.')
        st.markdown('**Le scritte** (solo informazioni: squadre, giorno, ora, campo)')
        a, b = st.columns(2)
        ours = a.text_input('Noi', base['ours'], max_chars=24, key=f'intro_ours_{tag}').upper()
        opponent = b.text_input('Avversari', '' if base['opponent'] == 'AVVERSARI' else base['opponent'], max_chars=28,
                                key=f'intro_opp_{tag}').upper()
        home = st.radio('Giochiamo', ('In casa', 'In trasferta'), index=0 if base['home'] else 1, horizontal=True,
                        key=f'intro_side_{tag}', help='La squadra di casa sta a sinistra ed è scritta per prima.') == 'In casa'
        a, b = st.columns([2, 1])
        date = a.text_input('Giorno', base['date'] if 'GG/' not in base['date'] else '', max_chars=28, key=f'intro_date_{tag}',
                            help='Senza accenti (il carattere pixel non li ha): GIOVEDI, non GIOVEDÌ.').upper()
        kickoff = b.text_input('Ora', base['kickoff'], max_chars=5, key=f'intro_time_{tag}')
        place = st.text_input('Campo', base['place'], max_chars=40, key=f'intro_place_{tag}').upper()
        competition = st.text_input('Campionato e giornata', base['competition'], max_chars=44, key=f'intro_comp_{tag}').upper()
        texts = dict(ours=ours or 'FLAMINGOS', opponent=opponent or 'AVVERSARI', home=home, date=date, kickoff=kickoff.strip(),
                     place=place, competition=competition)
        st.markdown('**Lo stile**')
        logos, auto = _crests(library, opponent, match.get('opponent_logo_id'))
        options = ['auto']+list(logos)+['none']
        pick = st.selectbox('Stemma avversario', options, key=f'intro_crest_{tag}',
                            format_func=lambda k: (f"Automatico ({logos[auto]})" if auto else 'Automatico (scudo con le iniziali)')
                            if k == 'auto' else ('Nessuno: scudo con le iniziali' if k == 'none' else logos[k]),
                            help='Lo stemma viene ridisegnato in pixel; i colori della sua metà arrivano dallo stemma.')
        crest_id = auto if pick == 'auto' else (None if pick == 'none' else pick)
        crest = library['assets'][crest_id]['bytes'] if crest_id else None
        a, b = st.columns(2)
        fmt = a.selectbox('Formato', FORMATS, key='intro_format')
        look = b.selectbox('Fenicottero', list(intro.LOOK_LABELS), format_func=intro.LOOK_LABELS.get, key='intro_look')
        with st.expander('Impostazioni video'):
            import variety
            tracks = [t for t in variety.MUSIC_TRACKS if t not in ('auto', 'mio')]
            track = st.selectbox('Musica', tracks, index=tracks.index('cc0_robots') if 'cc0_robots' in tracks else 0,
                                 format_func=variety.MUSIC_TRACKS.get, key='intro_track')
            sound = st.checkbox('Effetti', True, key='intro_sound')
            fps = st.selectbox('Fotogrammi al secondo', (30, 60), key='intro_fps')
            hd = st.checkbox('Alta definizione (1080 px)', True, key='intro_hd')
            st.caption(f'Dura {intro.LENGTH:g} secondi; il VS cade sul drop del brano.')
    with preview:
        texts_json = json.dumps(texts, sort_keys=True)
        png = _poster(texts_json, crest, fmt, look)
        st.image(png, caption='La locandina su cui finisce l\'intro', width='stretch')
        a, b = st.columns(2)
        a.download_button('⬇ Locandina PNG', png, file_name='flamingos_locandina.png', mime='image/png', width='stretch',
                          key='intro_png')
        signature = hashlib.sha256((texts_json+fmt+look+track+str(sound)+str(fps)+str(hd)).encode()+(crest or b'')).hexdigest()[:20]
        if b.button('🎬 Video', type='primary', width='stretch', key='intro_video'):
            bar = st.progress(0, text='L\'intro in video...')
            try:
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)/'intro.mp4'
                    intro.render_video(texts, crest, path, fps, fmt, 2 if hd else 1, track, sound, look=look,
                                       progress_callback=progress_with_eta(bar, 'Video'))
                    st.session_state['intro_mp4'] = {'signature': signature, 'data': path.read_bytes()}
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                bar.empty()
        import share
        video = st.session_state.get('intro_mp4')
        if video and video['signature'] == signature:
            st.video(video['data'])
            st.download_button('⬇ Scarica il video', video['data'], file_name='flamingos_intro.mp4', mime='video/mp4',
                               width='stretch', key='intro_mp4_dl')
            share.button(video['data'], 'flamingos_intro.mp4', 'video/mp4', key='intro_share_mp4')
        share.button(png, 'flamingos_locandina.png', 'image/png', key='intro_share_png')
