"""Streamlit adapter for a per-browser IndexedDB font / logo / project library."""
from __future__ import annotations

import uuid
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from studio_state import empty_library, validate_library

ROOT = Path(__file__).resolve().parent
VAULT = components.declare_component('flamingos_studio_library',path=str(ROOT/'library_frontend'))


def show_library():
    with st.sidebar.expander('Archivio font, stemmi e backup',expanded=True):
        result = VAULT(command=st.session_state.get('vault_command'),key='studio_library_v1',default=None)
        if isinstance(result,dict) and result.get('event_id') != st.session_state.get('vault_event'):
            try:
                library,messages = validate_library(result.get('library'))
                st.session_state['studio_library'] = library
                st.session_state['vault_errors'] = messages
                st.session_state['vault_storage_ok'] = bool(result.get('storage_ok'))
            except ValueError as exc:
                st.session_state['vault_errors'] = [str(exc)]
            st.session_state['vault_event'] = result.get('event_id')
            pending = st.session_state.get('vault_command')
            if pending and result.get('command_id') == pending['id']:
                st.session_state.pop('vault_command',None)
                if result.get('error'):
                    st.session_state['vault_errors'] = [str(result['error'])]
        for message in st.session_state.get('vault_errors',[]):
            st.warning(message)
        if 'studio_library' not in st.session_state:
            st.caption('Attendo il caricamento dell\'archivio browser...')
            if st.button('Continua senza archivio',key='vault_bypass'):
                st.session_state['studio_library'] = empty_library()
            else:
                return None
    return st.session_state['studio_library']


def save_project(name, template, config, project_id):
    if st.session_state.get('vault_command'):
        st.warning('Attendi il completamento del salvataggio precedente.')
        return
    st.session_state['vault_command'] = {'id':uuid.uuid4().hex,'type':'save_project',
        'project_id':project_id,'project':{'name':name.strip()[:80],'template':template,'config':config}}
    st.rerun()
