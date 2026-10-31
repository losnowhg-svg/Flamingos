"""Music controls shared by the editors (3.8): the user's own track and the listening preview."""
from __future__ import annotations

import streamlit as st

import tracks

SOURCES = ('Musica gratis per i video: Pixabay Music, YouTube Audio Library, Uppbeat (piano gratuito), FreePD. '
           'Per una canzone famosa: esporta il video senza "Musica" e aggiungila su Instagram dalla sua libreria.')


def custom_key():
    """The key of the track uploaded in this session (registered again if the server forgot it)."""
    saved = st.session_state.get('my_music')
    if not saved:
        return None
    try:
        key, _ = tracks.register(saved['bytes'], saved['name'], saved.get('drop'))
    except ValueError:
        return None
    return key


def uploader(config, key_name='my_music_file'):
    """'Il mio brano': upload, automatic drop, manual correction. Puts the key on config['music_custom']."""
    upload = st.file_uploader('Carica il brano (mp3, m4a, wav, ogg - massimo 25 MB)', type=list(tracks.UPLOAD_TYPES),
                              key=key_name)
    if upload is not None:
        data = upload.getvalue()
        saved = st.session_state.get('my_music')
        if not saved or saved['bytes'] != data:
            st.session_state['my_music'] = {'name': upload.name, 'bytes': data, 'drop': None}
    saved = st.session_state.get('my_music')
    if not saved:
        config.pop('music_custom', None)
        st.caption('L\'app trova da sola il momento forte del brano e lo fa cadere sul "drop" del video; '
                   'le pulsazioni e la camera seguono il suo ritmo. '+SOURCES)
        return None
    try:
        key, found = tracks.register(saved['bytes'], saved['name'], None)
    except ValueError as exc:
        st.error(str(exc))
        config.pop('music_custom', None)
        return None
    auto = found['auto']
    top = max(1.0, float(int(found['duration'])-1))
    chosen = st.slider('Momento forte (secondi nel brano)', 0.0, top, float(min(auto, top)), .25, key='my_drop_'+key,
                       help='Il punto del brano che cade sul momento clou del video (4 secondi dopo l\'inizio). '
                            'Lo trova da solo; spostalo se preferisci un altro pezzo.')
    saved['drop'] = None if abs(chosen-auto) < .01 else chosen
    key, found = tracks.register(saved['bytes'], saved['name'], saved['drop'])
    config['music_custom'] = key
    minutes, seconds = divmod(int(found['drop']), 60)
    st.caption(f"{found['name']}: circa {found['bpm']:.0f} bpm, momento forte a {minutes}:{seconds:02d}"
               + (' (trovato da solo).' if saved['drop'] is None else ' (scelto da te).'))
    return key


def signature(config):
    """What the soundtrack depends on, for the video cache."""
    key = config.get('music_custom')
    return f"{config.get('music_track')}|{key}|{tracks.info(key) if key else ''}"
