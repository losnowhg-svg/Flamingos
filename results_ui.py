"""📋 Risultati della giornata: every match of the girone, ours lit up (PNG and video)."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st

import results_round as rr
from sequence_ui import current_config
from studio_state import sanitize_match
from ui_utils import progress_with_eta

FORMATS = ('Story 9:16', 'Post 4:5', 'Post 1:1')


def _logo(root, library, match):
    assets = library.get('assets', {})
    chosen = match.get('our_logo_id')
    if chosen in assets and assets[chosen].get('kind') == 'logo':
        return assets[chosen]['bytes']
    return (Path(root)/'assets'/'flamingos_logo.jpg').read_bytes()


@st.cache_data(show_spinner=False, max_entries=12)
def _png(rows_json, title, subtitle, date, logo, ours, fmt, style_key):
    import figurine_style
    style = figurine_style.build(style_key, fmt, 1080) if style_key else None
    return rr.png_bytes(json.loads(rows_json), logo, fmt, 2, style, title=title, subtitle=subtitle, date=date, ours=ours)


def _rows_table(rows):
    return [dict(casa=r['home'], gol_casa=r['score'][0] if r['score'] else None, gol_ospiti=r['score'][1] if r['score'] else None,
                 ospiti=r['away'], quando=r['when']) for r in rows]


def _rows_back(table, ours):
    from csi_page import is_ours
    out = []
    for r in table:
        home, away = str(r.get('casa') or '').strip().upper(), str(r.get('ospiti') or '').strip().upper()
        if not home or not away:
            continue
        a, b = r.get('gol_casa'), r.get('gol_ospiti')
        try:
            score = [int(a), int(b)] if a is not None and b is not None and str(a) != 'nan' and str(b) != 'nan' else None
        except (TypeError, ValueError):
            score = None
        out.append(dict(home=home, away=away, score=score, when=str(r.get('quando') or '')[:12],
                        ours=is_ours(home, ours) or is_ours(away, ours)))
    return out


def show_results(root, library):
    st.subheader('📋 RISULTATI DELLA GIORNATA')
    st.caption('Tutte le partite del girone in una grafica, la nostra illuminata. Le partite arrivano dal sito CSI '
               '(segnalibro o pagina incollata nella Settimana); qui puoi correggere o completare.')
    match = sanitize_match(st.session_state.get('shared_match'))
    ours = match.get('our_name', 'FLAMINGOS')
    groups = rr.rounds(st.session_state.get('csi_matches') or [])
    preview, controls = st.columns([1, 1.15], gap='large')
    with controls:
        if groups:
            index = st.selectbox('Giornata', range(len(groups)), index=rr.default_round(groups), key='results_round',
                                 format_func=lambda i: f"{groups[i]['label'].title()} · {groups[i]['played']}/"
                                                       f"{len(groups[i]['matches'])} giocate")
            group = groups[index]
            rows = rr.rows_for(group, ours)
            label, date = group['label'], rr.date_line(group)
        else:
            st.info('Nessuna partita dal sito CSI: aggiornale nella Settimana (① Aggiorna dal sito CSI), oppure '
                    'scrivile qui sotto.')
            rows, label, date, index = [], 'GIORNATA', '', 'manuale'
        st.markdown('**Le partite**')
        edited = st.data_editor(_rows_table(rows) or [dict(casa='', gol_casa=None, gol_ospiti=None, ospiti='', quando='')],
                                num_rows='dynamic', hide_index=True, width='stretch', key=f'results_table_{index}',
                                column_config={'casa': st.column_config.TextColumn('Casa', max_chars=34),
                                               'gol_casa': st.column_config.NumberColumn('Gol', min_value=0, max_value=99,
                                                                                         step=1, width='small'),
                                               'gol_ospiti': st.column_config.NumberColumn('Gol ', min_value=0,
                                                                                           max_value=99, step=1,
                                                                                           width='small'),
                                               'ospiti': st.column_config.TextColumn('Ospiti', max_chars=34),
                                               'quando': st.column_config.TextColumn('Giorno e ora', max_chars=12,
                                                                                     help='Per le partite da giocare')})
        edited = edited.to_dict('records') if hasattr(edited, 'to_dict') else list(edited)
        rows = _rows_back(edited, ours)
        a, b = st.columns(2)
        title = a.text_input('Titolo', 'RISULTATI', max_chars=24, key='results_title').upper()
        subtitle = b.text_input('Sottotitolo', f'{label} · CSI BRESCIA', max_chars=40, key=f'results_sub_{index}').upper()
        fmt = st.selectbox('Formato', FORMATS, key='results_format')
        import figurine_style as fs
        from crt_presets import PRESET_IDS, PRESETS
        classifica = current_config('Classifica')
        choice = st.selectbox('Stile', [fs.FOLLOW, fs.SYNTHWAVE]+list(PRESET_IDS), key='results_style',
                              format_func=lambda c: f"Come la Classifica ({PRESETS.get(classifica.get('preset_id', 'crt'), PRESETS['crt'])['name'].split('/ ')[-1]})"
                              if c == fs.FOLLOW else fs.label(c, classifica))
        style_key = fs.key_for(choice, classifica)
        with st.expander('Impostazioni video'):
            import variety
            tracks = [t for t in variety.MUSIC_TRACKS if t not in ('auto', 'mio')]
            track = st.selectbox('Musica', tracks, index=tracks.index('cc0_ritmo') if 'cc0_ritmo' in tracks else 0,
                                 format_func=variety.MUSIC_TRACKS.get, key='results_track')
            sound = st.checkbox('Effetti', True, key='results_sound')
            fps = st.selectbox('Fotogrammi al secondo', (30, 60), key='results_fps')
            st.caption('Le partite entrano una alla volta; la nostra arriva sul drop della musica.')
    st.session_state['results_payload'] = {'rows': rows, 'title': title, 'subtitle': subtitle, 'date': date, 'ours': ours}
    with preview:
        if not rows:
            st.info('Scrivi almeno una partita.')
            return
        logo = _logo(root, library, match)
        rows_json = json.dumps(rows, sort_keys=True)
        png = _png(rows_json, title, subtitle, date, logo, ours, fmt, style_key)
        st.image(png, width='stretch')
        a, b = st.columns(2)
        a.download_button('⬇ PNG', png, file_name='flamingos_risultati.png', mime='image/png', width='stretch',
                          key='results_png')
        signature = hashlib.sha256((rows_json+title+subtitle+date+fmt+track+str(sound)+str(fps)+style_key).encode()
                                   + logo).hexdigest()[:20]
        if b.button('🎬 Video', type='primary', width='stretch', key='results_video'):
            bar = st.progress(0, text='I risultati in video...')
            try:
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)/'risultati.mp4'
                    style = fs.build(style_key, fmt, 1080)
                    rr.render_video(rows, logo, path, fps, fmt, 2, track, sound, progress_callback=progress_with_eta(bar, 'Video'),
                                    style=style, title=title, subtitle=subtitle, date=date, ours=ours)
                    st.session_state['results_mp4'] = {'signature': signature, 'data': path.read_bytes()}
            except Exception as exc:
                st.error(f'Video non generato: {exc}')
            finally:
                bar.empty()
        import share
        video = st.session_state.get('results_mp4')
        if video and video['signature'] == signature:
            st.video(video['data'])
            st.download_button('⬇ Scarica il video', video['data'], file_name='flamingos_risultati.mp4', mime='video/mp4',
                               width='stretch', key='results_mp4_dl')
            share.button(video['data'], 'flamingos_risultati.mp4', 'video/mp4', key='results_share_mp4')
        share.button(png, 'flamingos_risultati.png', 'image/png', key='results_share_png')
