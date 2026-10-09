"""Versioned project schema and validation. Does not depend on Streamlit."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import re

import renderer as starting
import matchday_renderer as matchday

SCHEMA_VERSION = 1
MAX_LIBRARY_BYTES = 44_000_000  # JSON / base64 limit; raw assets capped at 32 MB in browser.
BUILTIN_FONTS = ['Sans Bold', 'Monospace Bold', 'Pixel Arcade']

START_DEFAULT = dict(
    team_name='FLAMINGOS', headline='STARTING 7', footer='CSI BRESCIA', formation_text='MODULO 1-1-3-1',
    title_size=34, subtitle_size=27, footer_size=20, name_size=17, logo_size=95, remove_white=True,
    accent='#F2488B', background='#0D0B14', text_color='#F6EEF6', texture=25,
    font_choice='Sans Bold', logo_id='default', export_format='Story 9:16',
    duration=9, fps=24, video_scale=2, png_quality='Fine',
    positions={k:list(v) for k,v in starting.DEFAULT_POSITIONS.items()},
    players=[{'number':i+1,'name':role.upper().split()[0]} for i,role in enumerate(starting.DEFAULT_ROLES)],
)
MATCH_DEFAULT = dict(
    title='MATCHDAY SCREEN', date='GG/MM/AAAA', home_name='FLAMINGOS', away_name='AVVERSARI',
    kickoff='HH:MM', venue='VIA FORNACI, 82', kickoff_label="CALCIO D'INIZIO:", venue_label='LUOGO:',
    title_size=27, label_size=18, info_size=16, vs_size=43, home_logo_size=103, away_logo_size=103,
    home_clear_white=True, away_clear_white=True, pink='#F268A8', cyan='#79DCF7', yellow='#FFC963', white='#F6F4FC',
    font_choice='Sans Bold', home_logo_id='default', away_logo_id='none',
    export_format='Post 1:1', duration=8, fps=24, video_scale=2, png_quality='Fine',
    positions={k:list(v) for k,v in matchday.DEFAULT_POSITIONS.items()},
)
RANGES = {
    'Starting 7': dict(title_size=(15,62),subtitle_size=(12,56),footer_size=(10,42),name_size=(10,35),logo_size=(50,210),texture=(0,100),duration=(7,18)),
    'Matchday Screen': dict(title_size=(18,42),label_size=(12,30),info_size=(12,25),vs_size=(24,58),home_logo_size=(60,150),away_logo_size=(60,150),duration=(5,18)),
}
DEFAULTS = {'Starting 7':START_DEFAULT,'Matchday Screen':MATCH_DEFAULT}
TEXT_LIMITS = dict(team_name=50,headline=60,footer=80,formation_text=80,title=36,date=24,home_name=42,away_name=42,kickoff=14,venue=72,kickoff_label=40,venue_label=22)


def defaults(template):
    if template not in DEFAULTS:
        raise ValueError('Modello sconosciuto.')
    return copy.deepcopy(DEFAULTS[template])


def _integer(value, default, lo, hi):
    try:
        n = float(value)
        return max(lo,min(hi,int(n))) if math.isfinite(n) else default
    except (ValueError,TypeError,OverflowError):
        return default


def sanitize_config(template, raw):
    """Ignore unknown fields and bound every value imported from an archive."""
    config = defaults(template)
    if not isinstance(raw,dict):
        raise ValueError('Il progetto non contiene impostazioni valide.')
    for key,default in config.items():
        value = raw.get(key,default)
        if key == 'positions':
            module = starting if template == 'Starting 7' else matchday
            config[key] = {k:list(v) for k,v in module.normalized_positions({'positions':value}).items()}
        elif key == 'players':
            if isinstance(value,list):
                for i,item in enumerate(value[:7]):
                    if isinstance(item,dict):
                        config[key][i] = {'number':_integer(item.get('number'),i+1,0,99),
                                          'name':str(item.get('name','GIOCATORE'))[:27]}
        elif key in RANGES[template]:
            config[key] = _integer(value,default,*RANGES[template][key])
        elif key in ('fps','video_scale'):
            valid = [12,15,24,30] if key == 'fps' else [1,2]
            config[key] = value if type(value) is int and value in valid else default
        elif key == 'png_quality':
            config[key] = value if value in ('Fine','Standard') else default
        elif key == 'export_format':
            valid = ['Story 9:16','Post 1:1'] if template == 'Matchday Screen' else ['Story 9:16']
            config[key] = value if value in valid else default
        elif isinstance(default,bool):
            config[key] = value if isinstance(value,bool) else default
        elif isinstance(default,str) and default.startswith('#'):
            config[key] = value if isinstance(value,str) and re.fullmatch(r'#[0-9A-Fa-f]{6}',value) else default
        elif isinstance(default,str):
            config[key] = str(value)[:TEXT_LIMITS.get(key,128)]
    return config


def empty_library():
    return dict(schema=SCHEMA_VERSION,assets={},projects={},preferred_font=None)


def validate_library(raw):
    """Decode and validate browser assets before Pillow ever sees them."""
    if not isinstance(raw,dict) or raw.get('schema') != SCHEMA_VERSION:
        raise ValueError('Versione archivio non supportata.')
    # This cap is checked before decoding the potentially large base64 strings.
    if len(json.dumps(raw,ensure_ascii=True)) > MAX_LIBRARY_BYTES:
        raise ValueError('Archivio troppo grande (massimo 32 MB di file).')
    library, messages = empty_library(), []
    assets = raw.get('assets',{})
    if not isinstance(assets,dict) or len(assets)>24:
        raise ValueError('Troppi file nell\'archivio (massimo 24).')
    total = 0
    for id_, item in assets.items():
        try:
            if not isinstance(item,dict) or item.get('kind') not in ('font','logo'):
                raise ValueError('Tipo file non valido.')
            kind, payload = item['kind'],item.get('data')
            limit = 5_000_000 if kind == 'font' else 12_000_000
            if not isinstance(payload,str) or len(payload) > 4*((limit+2)//3):
                raise ValueError('File oltre il limite consentito.')
            data = base64.b64decode(payload,validate=True)
            total += len(data)
            if total > 32_000_000:
                raise ValueError('Limite totale di 32 MB superato.')
            if id_ != kind+':'+hashlib.sha256(data).hexdigest():
                raise ValueError('Firma del file non valida.')
            if kind == 'font':
                starting.validate_font(data)
            else:
                starting.validate_logo(data)
            library['assets'][id_] = {'kind':kind,'name':str(item.get('name','File'))[:100],'bytes':data}
        except (ValueError,TypeError) as exc:
            name = str(item.get('name','File'))[:100] if isinstance(item,dict) else 'File'
            messages.append(f'{name}: {exc} Rimuovi il file non valido dall\'archivio.')
    projects = raw.get('projects',{})
    if not isinstance(projects,dict) or len(projects)>50:
        raise ValueError('L\'archivio supporta al massimo 50 progetti.')
    for id_,project in projects.items():
        try:
            if not isinstance(project,dict) or project.get('template') not in DEFAULTS:
                raise ValueError('Modello progetto non valido.')
            config = sanitize_config(project['template'],project.get('config'))
            library['projects'][str(id_)[:128]] = {'name':str(project.get('name','Progetto'))[:80],
                                                  'template':project['template'],'config':config}
        except (ValueError,TypeError) as exc:
            messages.append(f'Progetto ignorato: {exc}')
    preferred = raw.get('preferred_font')
    if isinstance(preferred,str) and preferred in library['assets'] and library['assets'][preferred]['kind']=='font':
        library['preferred_font'] = preferred
    return library,messages
