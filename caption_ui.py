"""✍️ Didascalie: the caption studio page."""
from __future__ import annotations

import streamlit as st

import caption_studio as cs
from sequence_ui import current_config
from studio_state import sanitize_match


def facts_for(context, library=None):
    template = 'Convocati' if context == 'Reparti' else context
    config = current_config(template)
    table = current_config('Classifica')
    standings = table['standings'][:table['team_count']]
    squad = st.session_state.get('squad') or (library or {}).get('squad') or []
    return cs.build_facts(context, config if context != 'Classifica' else table,
                          sanitize_match(st.session_state.get('shared_match')), squad,
                          st.session_state.get('csi_matches') or [], standings if context != 'Classifica' else None)


def summary(facts):
    bits = []
    if facts.get('opp'):
        bits.append('vs '+facts['opp']+(f" ({facts['where']})" if facts.get('where') else ''))
    for key in ('date', 'time', 'score', 'pos_ord', 'event', 'season', 'streak'):
        if facts.get(key):
            bits.append({'time': 'ore ', 'pos_ord': 'in classifica ', 'score': 'risultato '}.get(key, '')+str(facts[key]))
    if facts.get('scorers'):
        bits.append('marcatori '+facts['scorers'])
    if facts.get('count'):
        bits.append(facts['count']+' convocati')
    return ' · '.join(bits)


def quick(context, n=3, seed=0, library=None):
    """A few captions for the editors' Export tab."""
    return cs.generate(context, facts_for(context, library), count=n, seed=seed)


def show_captions(library):
    st.subheader('✍️ DIDASCALIE')
    st.caption('Centinaia di didascalie dai dati della settimana: scegli la grafica, il tono e quante ne vuoi. '
               'Tocca l\'icona in alto a destra di un riquadro per copiarla.')
    state = st.session_state.setdefault('captions', {'seed': 0, 'favs': []})
    context = st.segmented_control('Per quale grafica', list(cs.CONTEXTS), format_func=cs.CONTEXTS.get,
                                   default=st.session_state.get('caption_context', 'Matchday Screen'), key='cap_context') \
        or 'Matchday Screen'
    st.session_state['caption_context'] = context
    facts = facts_for(context, library)
    line = summary(facts)
    if line:
        st.info('Uso questi dati: '+line, icon='📡')
    else:
        st.warning('Mancano i dati della partita: compilali nella Settimana o nell\'editor, poi torna qui.')

    with st.container(border=True):
        tones = st.pills('Toni', list(cs.TONES), format_func=cs.TONES.get, selection_mode='multi',
                         default=list(cs.TONES), key='cap_tones') or list(cs.TONES)
        a, b, c = st.columns(3)
        length = a.radio('Lunghezza', list(cs.LENGTHS), index=1, format_func=cs.LENGTHS.get, horizontal=True, key='cap_len')
        tags = b.radio('Hashtag', list(cs.HASHTAG_LEVELS), index=1, format_func=cs.HASHTAG_LEVELS.get, horizontal=True, key='cap_tags')
        emoji = c.toggle('Emoji', True, key='cap_emoji')
        a, b = st.columns([3, 1])
        count = a.slider('Quante', 6, 60, 24, step=6, key='cap_count')
        b.write('')
        if b.button('🎲 Altre', type='primary', width='stretch', key='cap_roll'):
            state['seed'] += 1
        search = st.text_input('Cerca una parola', '', key='cap_search', placeholder='es. vittoria, capitano, pixel...')

    results = cs.generate(context, facts, tones, count, state['seed'], length, emoji, tags)
    if search.strip():
        results = [r for r in results if search.strip().lower() in r['text'].lower()]
    total = sum(cs.variety(context, facts, t) for t in tones)
    st.caption(f'{len(results)} proposte · oltre {total:,} combinazioni possibili con questi toni'.replace(',', '.'))

    if state['favs']:
        with st.expander(f'⭐ Preferite ({len(state["favs"])})', expanded=True):
            for i, text in enumerate(state['favs']):
                st.code(text, language=None, wrap_lines=True)
                if st.button('Togli', key=f'cap_unfav_{i}'):
                    state['favs'].pop(i)
                    st.rerun()

    if not results:
        st.info('Nessuna proposta con questi filtri: prova altri toni o togli la ricerca.')
        return
    columns = st.columns(2)
    for i, item in enumerate(results):
        with columns[i % 2], st.container(border=True):
            text = item['text']
            st.markdown(f"**{cs.TONES[item['tone']]}** · {len(text)} caratteri")
            st.code(text, language=None, wrap_lines=True)
            if st.button('⭐ Preferita', key=f'cap_fav_{state["seed"]}_{i}', disabled=text in state['favs']):
                state['favs'].append(text)
                st.rerun()
