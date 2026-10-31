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
import fulltime_renderer as fulltime
import convocati_renderer as convocati
import classifica_renderer as classifica
import calendario_renderer as calendario
import datetime as _dt
import themes
from classifica_data import MAX_TEAMS, empty_row
from pixel_fonts import PIXEL_FONTS
from crt_presets import PRESETS, FORMATS, DEFAULT_BRIGHTNESS

SCHEMA_VERSION = 1
MAX_LIBRARY_BYTES = 44_000_000  # JSON / base64 limit; raw assets capped at 32 MB in browser.
BUILTIN_FONTS = ['Sans Bold', 'Monospace Bold', 'Pixel Arcade', *PIXEL_FONTS]

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
CRT_DEFAULT = dict(preset_id='crt',rotation_mode='Manuale',season_round=1,scanlines=16,brightness=DEFAULT_BRIGHTNESS,
                   theme='auto',event_theme='',animation='Retro',power_on=True,mockup=False,
                   intro=False,details=True,music=False,ending='nessuno',
                   layout='classica',layout_rotation=False,title_rotation=False,intro_style='press_start',music_track='auto',
                   sponsor_on=False,sponsor_logo_id='none',sponsor_name='',
                   atmosphere='standard',decor='nessuno',panel_style='smussato',title_fx='ombra',
                   frame_style='nessuna',texture_fx='nessuna',entrance='misto',camera='fermo',
                   fx_pulse=False,fx_flicker=False,fx_particles=False,fx_sweep=False,highlight='auto')
MATCH_DEFAULT.update(CRT_DEFAULT)
MATCH_DEFAULT.update(font_choice='CRT Terminal',our_side='Casa')
FULLTIME_DEFAULT = dict(
    **CRT_DEFAULT,
    title='FULL TIME',date='GG/MM/AAAA',competition='CSI BRESCIA',
    home_name='FLAMINGOS',away_name='AVVERSARI',our_side='Casa',
    home_score=0,away_score=0,home_penalties=0,away_penalties=0,
    show_penalties=False,show_result=True,show_scorers=True,home_scorers='',away_scorers='',
    title_size=30,label_size=15,info_size=12,score_size=54,result_size=16,scorer_size=11,
    home_logo_size=66,away_logo_size=66,home_clear_white=True,away_clear_white=True,
    pink='#F268A8',cyan='#79DCF7',yellow='#FFC963',white='#F6F4FC',
    font_choice='CRT Terminal',home_logo_id='default',away_logo_id='none',
    export_format='Post 1:1',duration=8,fps=24,video_scale=2,png_quality='Fine',
    positions={k:list(v) for k,v in fulltime.DEFAULT_POSITIONS.items()},
)
CONVOCATI_DEFAULT = dict(
    **CRT_DEFAULT,
    title='CONVOCATI',team_name='FLAMINGOS',opponent='AVVERSARI',date='GG/MM/AAAA',
    meeting_time='HH:MM',kickoff='HH:MM',venue='CAMPO / INDIRIZZO',
    roster_count=12,title_size=25,team_size=12,info_size=11,name_size=11,logo_size=45,remove_white=True,
    pink='#F268A8',cyan='#79DCF7',yellow='#FFC963',white='#F6F4FC',
    font_choice='CRT Terminal',logo_id='default',export_format='Post 4:5',
    duration=8,fps=24,video_scale=2,png_quality='Fine',
    roster=[{'number':i+1,'name':f'GIOCATORE {i+1:02d}',
             'role':'P' if i==0 else '-','captain':False} for i in range(convocati.MAX_PLAYERS)],
    positions={k:list(v) for k,v in convocati.DEFAULT_POSITIONS.items()},
    sprite_pose='variate',sprite_scene='sfumato',
)
SAMPLE_STANDINGS = [
    ('SQUADRA A',19,8,6,1,1,31,12),('FLAMINGOS',17,8,5,2,1,28,15),('SQUADRA B',15,8,5,0,3,24,19),
    ('SQUADRA C',12,8,4,0,4,22,22),('SQUADRA D',10,8,3,1,4,17,21),('SQUADRA E',8,8,2,2,4,15,24),
    ('SQUADRA F',6,8,2,0,6,13,27),('SQUADRA G',4,8,1,1,6,11,31)]
CLASSIFICA_DEFAULT = dict(
    **CRT_DEFAULT,
    title='CLASSIFICA',group='GIRONE D / SERIE C',round_label='GIORNATA 8',our_team='FLAMINGOS',
    source_url='https://live.centrosportivoitaliano.it/26/Calcio-a-7/Lombardia/Brescia/C102/?j=NEU9REZJJjRGPVBOSyY0Rz1FREYmNEg9RCY0ST1RJjRMPURGSSY0Mj1l',auto_update=False,
    table_detail='Completa',team_count=8,show_zones=True,promo_count=3,playoff_count=2,
    promo_color='#5BE6A4',playoff_color='#B98CFF',promo_label='PROMOZIONE',playoff_label='SPAREGGIO',
    title_size=24,info_size=10,table_size=10,logo_size=40,remove_white=True,
    pink='#F268A8',cyan='#79DCF7',yellow='#FFC963',white='#F6F4FC',
    font_choice='CRT Terminal',logo_id='default',export_format='Post 4:5',
    duration=8,fps=24,video_scale=2,png_quality='Fine',
    prev_pos=0,
    standings=[dict(pos=i+1,team=t,pt=pt,g=g,v=v,n=n,p=p,gf=gf,gs=gs) for i,(t,pt,g,v,n,p,gf,gs) in enumerate(SAMPLE_STANDINGS)]
              +[empty_row(i+1) for i in range(len(SAMPLE_STANDINGS),MAX_TEAMS)],
    positions={k:list(v) for k,v in classifica.DEFAULT_POSITIONS.items()},
)
_MONTHS = ('GENNAIO','FEBBRAIO','MARZO','APRILE','MAGGIO','GIUGNO','LUGLIO','AGOSTO','SETTEMBRE','OTTOBRE','NOVEMBRE','DICEMBRE')
_TODAY = _dt.date.today()
CALENDARIO_DEFAULT = dict(
    **CRT_DEFAULT,
    title='CALENDARIO',month_label=f'{_MONTHS[_TODAY.month-1]} {_TODAY.year}',our_team='FLAMINGOS',
    fixture_count=4,title_size=24,info_size=11,logo_size=40,remove_white=True,
    pink='#F268A8',cyan='#79DCF7',yellow='#FFC963',white='#F6F4FC',
    font_choice='CRT Terminal',logo_id='default',export_format='Post 4:5',
    duration=8,fps=24,video_scale=2,png_quality='Fine',
    fixtures=[dict(date='02/10',day='GIO',opponent='AVVERSARI A',side='C',time='20:45',score='3-1'),
              dict(date='09/10',day='SAB',opponent='AVVERSARI B',side='T',time='15:00',score='2-2'),
              dict(date='16/10',day='GIO',opponent='AVVERSARI C',side='C',time='20:45',score=''),
              dict(date='23/10',day='VEN',opponent='AVVERSARI D',side='T',time='20:45',score='')]
             +[calendario.empty_fixture() for _ in range(calendario.MAX_FIXTURES-4)],
    positions={k:list(v) for k,v in calendario.DEFAULT_POSITIONS.items()},
)
RANGES = {
    'Starting 7': dict(title_size=(15,62),subtitle_size=(12,56),footer_size=(10,42),name_size=(10,35),logo_size=(50,210),texture=(0,100),duration=(7,18)),
    'Matchday Screen': dict(title_size=(18,42),label_size=(12,30),info_size=(12,25),vs_size=(24,58),home_logo_size=(60,150),away_logo_size=(60,150),duration=(5,18)),
}
RANGES['Full Time'] = dict(title_size=(18,42),label_size=(10,24),info_size=(9,20),
    score_size=(30,76),result_size=(10,24),scorer_size=(8,16),home_logo_size=(45,85),away_logo_size=(45,85),
    home_score=(0,99),away_score=(0,99),home_penalties=(0,99),away_penalties=(0,99),duration=(5,18))
RANGES['Convocati'] = dict(title_size=(18,36),team_size=(9,20),info_size=(8,18),name_size=(9,16),
    logo_size=(30,58),roster_count=(7,18),duration=(5,18))
RANGES['Classifica'] = dict(prev_pos=(0,30),promo_count=(0,8),playoff_count=(0,8),title_size=(16,34),info_size=(8,16),table_size=(7,14),logo_size=(26,56),
    team_count=(2,MAX_TEAMS),duration=(5,18))
RANGES['Calendario'] = dict(title_size=(16,34),info_size=(8,16),logo_size=(26,56),fixture_count=(1,calendario.MAX_FIXTURES),duration=(5,18))
CRT_TEMPLATES = ('Matchday Screen','Full Time','Convocati','Classifica','Calendario')
for model in CRT_TEMPLATES:
    RANGES[model].update(season_round=(1,80),scanlines=(0,60),brightness=(0,100))
for _model in (START_DEFAULT,MATCH_DEFAULT,FULLTIME_DEFAULT,CONVOCATI_DEFAULT,CLASSIFICA_DEFAULT,CALENDARIO_DEFAULT):
    _model.update(sound=True,volume=80)
DEFAULTS = {'Starting 7':START_DEFAULT,'Matchday Screen':MATCH_DEFAULT,
            'Full Time':FULLTIME_DEFAULT,'Convocati':CONVOCATI_DEFAULT,'Classifica':CLASSIFICA_DEFAULT,
            'Calendario':CALENDARIO_DEFAULT}
for _model in RANGES.values():
    _model['volume'] = (0,100)
MODULES = {'Starting 7':starting,'Matchday Screen':matchday,'Full Time':fulltime,'Convocati':convocati,
           'Classifica':classifica,'Calendario':calendario}
TEXT_LIMITS = dict(team_name=50,headline=60,footer=80,formation_text=80,title=36,date=24,home_name=42,away_name=42,kickoff=14,venue=72,kickoff_label=40,venue_label=22,competition=42,home_scorers=1200,away_scorers=1200,opponent=42,meeting_time=14,
                   group=48,round_label=36,our_team=34,source_url=300,
                   promo_label=20,playoff_label=20,month_label=30,sponsor_name=24,sponsor_logo_id=80)


def _choice_fields():
    import atmospheres, focus, frames, layouts, motion, title_fx, variety
    from crt_presets import PANEL_STYLES
    return {'layout': layouts.options, 'intro_style': lambda t: tuple(variety.INTRO_STYLES),
            'music_track': lambda t: tuple(variety.MUSIC_TRACKS), 'sprite_pose': lambda t: tuple(variety.POSE_MODES),
            'sprite_scene': lambda t: tuple(variety.SCENE_MODES),
            'atmosphere': lambda t: tuple(atmospheres.ATMOSPHERES), 'decor': lambda t: tuple(atmospheres.DETAILS),
            'panel_style': lambda t: tuple(PANEL_STYLES), 'title_fx': lambda t: tuple(title_fx.EFFECTS),
            'frame_style': lambda t: tuple(frames.FRAMES), 'texture_fx': lambda t: tuple(frames.TEXTURES),
            'entrance': lambda t: tuple(motion.ENTRANCES), 'camera': lambda t: tuple(motion.CAMERAS),
            'ending': lambda t: tuple(motion.ENDING_NAMES), 'highlight': lambda t: tuple(focus.HIGHLIGHTS)}


CHOICE_FIELDS = _choice_fields()


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
            module = MODULES[template]
            config[key] = {k:list(v) for k,v in module.normalized_positions({'positions':value}).items()}
        elif key == 'players':
            if isinstance(value,list):
                for i,item in enumerate(value[:7]):
                    if isinstance(item,dict):
                        config[key][i] = {'number':_integer(item.get('number'),i+1,0,99),
                                          'name':str(item.get('name','GIOCATORE'))[:27]}
        elif key == 'roster':
            if isinstance(value,list):
                for i,item in enumerate(value[:convocati.MAX_PLAYERS]):
                    if isinstance(item,dict):
                        role=item.get('role','-')
                        config[key][i] = dict(number=_integer(item.get('number'),i+1,0,99),
                            name=str(item.get('name','GIOCATORE'))[:27],
                            role=role if isinstance(role,str) and role in convocati.ROLES else '-',
                            captain=item.get('captain') is True)
        elif key == 'standings':
            if isinstance(value,list):
                for i in range(MAX_TEAMS):
                    item = value[i] if i < len(value) and isinstance(value[i],dict) else {}
                    row = empty_row(i+1)
                    row['pos'] = _integer(item.get('pos'),i+1,1,99)
                    row['team'] = str(item.get('team',''))[:34]
                    for field in ('pt','g','v','n','p','gf','gs'):
                        row[field] = _integer(item.get(field),0,0,999)
                    config[key][i] = row
        elif key == 'fixtures':
            if isinstance(value,list):
                for i in range(calendario.MAX_FIXTURES):
                    item = value[i] if i < len(value) and isinstance(value[i],dict) else {}
                    row = calendario.empty_fixture()
                    for field,limit in (('date',8),('day',3),('opponent',30),('time',8),('score',7)):
                        row[field] = str(item.get(field,'') or '')[:limit]
                    row['side'] = item.get('side') if item.get('side') in ('C','T') else 'C'
                    config[key][i] = row
        elif key == 'table_detail':
            config[key] = value if value in classifica.DETAILS else default
        elif key == 'preset_id':
            config[key] = value if isinstance(value,str) and value in PRESETS else default
        elif key == 'rotation_mode':
            config[key] = value if value in ('Manuale','Per giornata') else default
        elif key == 'our_side':
            config[key] = value if value in ('Casa','Ospiti') else default
        elif key == 'theme':
            config[key] = value if value in themes.CHOICES else default
        elif key == 'event_theme':
            config[key] = value if value in themes.EVENTS else ''
        elif key == 'animation':
            config[key] = value if value in ('Retro','Classica') else default
        elif key in CHOICE_FIELDS:
            config[key] = value if value in CHOICE_FIELDS[key](template) else default
        elif key in RANGES[template]:
            config[key] = _integer(value,default,*RANGES[template][key])
        elif key in ('fps','video_scale'):
            valid = [12,15,24,30,60] if key == 'fps' else [1,2]
            config[key] = value if type(value) is int and value in valid else default
        elif key == 'png_quality':
            config[key] = value if value in ('Fine','Standard') else default
        elif key == 'export_format':
            valid = FORMATS if template != 'Starting 7' else ['Story 9:16']
            config[key] = value if value in valid else default
        elif isinstance(default,bool):
            config[key] = value if isinstance(value,bool) else default
        elif isinstance(default,str) and default.startswith('#'):
            config[key] = value if isinstance(value,str) and re.fullmatch(r'#[0-9A-Fa-f]{6}',value) else default
        elif isinstance(default,str):
            config[key] = str(value)[:TEXT_LIMITS.get(key,128)]
    return config


def empty_library():
    return dict(schema=SCHEMA_VERSION,assets={},projects={},preferred_font=None,squad=[],week=None)


# --- Squad register and week memory (stored as special browser projects) ----
SQUAD_ID, WEEK_ID = 'rosa', 'settimana'
MAX_SQUAD = 30
SQUAD_ROLES = ('P','D','C','A','ALL','DIR','-')
STAFF_ROLES = ('ALL','DIR')


def sanitize_squad(raw):
    players = raw.get('players',[]) if isinstance(raw,dict) else raw
    squad, seen = [], set()
    for item in (players if isinstance(players,list) else [])[:200]:
        if len(squad) >= MAX_SQUAD:
            break
        if not isinstance(item,dict):
            continue
        name = re.sub(r'\s+',' ',str(item.get('name',''))).strip().upper()[:27]
        if not name or name in seen:
            continue
        seen.add(name)
        role = item.get('role','-')
        entry = dict(number=_integer(item.get('number'),0,0,99),name=name,role=role if role in SQUAD_ROLES else '-')
        handle = re.sub(r'[^A-Za-z0-9._]','',str(item.get('ig') or '').lstrip('@'))[:30]
        if handle:
            entry['ig'] = handle
        if item.get('look'):
            import pixel_character
            look = pixel_character.sanitize(item['look'])
            if look:
                entry['look'] = look
        avatar = item.get('avatar')
        if avatar:
            import avatars
            if avatars.decode(avatar) is not None:
                entry['avatar'] = avatar
        squad.append(entry)
    return squad


def sanitize_week(raw):
    """Shared match, standings, month fixtures and CSI matches, as plain JSON."""
    if not isinstance(raw,dict):
        return None
    week = dict(match=sanitize_match(raw.get('match')),updated=str(raw.get('updated',''))[:32],
                standings=[],fixtures=[],month_label=str(raw.get('month_label',''))[:30],matches=[],
                sponsor=sanitize_sponsor(raw.get('sponsor')),season=[],scorers=[])
    for item in (raw.get('season') or [])[:120] if isinstance(raw.get('season'),list) else []:
        if not isinstance(item,dict):
            continue
        try:
            date = _dt.date.fromisoformat(str(item.get('date',''))[:10]).isoformat()
        except ValueError:
            continue
        opp = re.sub(r'\s+',' ',str(item.get('opp',''))).strip()[:40]
        if opp:
            week['season'].append(dict(date=date,opp=opp,home=item.get('home') is True,
                                       us=_integer(item.get('us'),0,0,99),them=_integer(item.get('them'),0,0,99)))
    for item in (raw.get('scorers') or [])[:40] if isinstance(raw.get('scorers'),list) else []:
        if isinstance(item,dict) and str(item.get('name','')).strip():
            week['scorers'].append(dict(name=str(item['name']).strip().upper()[:27],goals=_integer(item.get('goals'),0,0,999)))
    for i,item in enumerate((raw.get('standings') or [])[:classifica.MAX_TEAMS] if isinstance(raw.get('standings'),list) else []):
        if isinstance(item,dict) and str(item.get('team','')).strip():
            row = dict(pos=_integer(item.get('pos'),i+1,1,99),team=str(item['team'])[:34])
            for field in ('pt','g','v','n','p','gf','gs'):
                row[field] = _integer(item.get(field),0,0,999)
            week['standings'].append(row)
    for item in (raw.get('fixtures') or [])[:calendario.MAX_FIXTURES] if isinstance(raw.get('fixtures'),list) else []:
        if isinstance(item,dict) and str(item.get('opponent','')).strip():
            row = calendario.empty_fixture()
            for field,limit in (('date',8),('day',3),('opponent',30),('time',8),('score',7)):
                row[field] = str(item.get(field,'') or '')[:limit]
            row['side'] = item.get('side') if item.get('side') in ('C','T') else 'C'
            week['fixtures'].append(row)
    for item in (raw.get('matches') or [])[:400] if isinstance(raw.get('matches'),list) else []:
        if not isinstance(item,dict):
            continue
        try:
            date = _dt.date.fromisoformat(str(item.get('date',''))[:10]).isoformat()
        except ValueError:
            continue
        score = item.get('score')
        if isinstance(score,(list,tuple)) and len(score)==2:
            score = [_integer(score[0],0,0,99),_integer(score[1],0,0,99)]
        else:
            score = None
        week['matches'].append(dict(home=str(item.get('home',''))[:40],away=str(item.get('away',''))[:40],date=date,
                                    time=str(item.get('time',''))[:5],score=score,venue=str(item.get('venue',''))[:80],
                                    round=_integer(item.get('round'),0,0,80) or None))
    return week


def sanitize_sponsor(raw):
    raw = raw if isinstance(raw,dict) else {}
    logo = raw.get('logo_id')
    return dict(on=raw.get('on') is True, logo_id=logo if isinstance(logo,str) and logo.startswith('logo:') else 'none',
                name=str(raw.get('name',''))[:24], end_slide=raw.get('end_slide',True) is not False)


def matches_from_week(week):
    """Back to the parser's shape: real dates and tuple scores."""
    out = []
    for m in (week or {}).get('matches',[]):
        item = dict(m)
        item['date'] = _dt.date.fromisoformat(m['date'])
        item['score'] = tuple(m['score']) if m.get('score') else None
        out.append(item)
    return out


def matches_to_week(matches):
    return [dict(m,date=m['date'].isoformat(),score=list(m['score']) if m.get('score') else None) for m in matches]


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
        if isinstance(project,dict) and project.get('template') == 'Rosa':
            library['squad'] = sanitize_squad(project.get('config'))
            continue
        if isinstance(project,dict) and project.get('template') == 'Settimana':
            library['week'] = sanitize_week(project.get('config'))
            continue
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


# --- Shared match: type the fixture once, every editor receives it ----------
MATCH_FIELDS = dict(our_name='FLAMINGOS', opponent='AVVERSARI', our_side='Casa', date='GG/MM/AAAA',
                    kickoff='HH:MM', meeting_time='HH:MM', venue='VIA FORNACI, 82', round=1,
                    our_logo_id='default', opponent_logo_id='none', event='auto')
CRT_TEMPLATES_SET = set(CRT_TEMPLATES)


def default_match():
    return dict(MATCH_FIELDS)


def sanitize_match(raw):
    match = default_match()
    if not isinstance(raw, dict):
        return match
    for key, default in MATCH_FIELDS.items():
        value = raw.get(key, default)
        if key == 'round':
            match[key] = _integer(value, 1, 1, 80)
        elif key == 'our_side':
            match[key] = value if value in ('Casa', 'Ospiti') else default
        elif key == 'event':
            match[key] = value if value in themes.MATCH_EVENTS else default
        else:
            match[key] = str(value)[:72]
    return match


def apply_match(template, config, raw_match, event_theme=None):
    """Copy the fixture into one editor without touching layout, sizes or colours.
    event_theme: derby / bigmatch / ultima worked out from the CSI data, if known."""
    from crt_presets import apply_preset, preset_for_round
    match = sanitize_match(raw_match)
    output = copy.deepcopy(config)
    ours, other = match['our_name'], match['opponent']
    if template in ('Matchday Screen', 'Full Time'):
        home = match['our_side'] == 'Casa'
        output.update(home_name=ours if home else other, away_name=other if home else ours,
                      home_logo_id=match['our_logo_id'] if home else match['opponent_logo_id'],
                      away_logo_id=match['opponent_logo_id'] if home else match['our_logo_id'],
                      date=match['date'], our_side=match['our_side'])
        if template == 'Matchday Screen':
            output.update(kickoff=match['kickoff'], venue=match['venue'])
    elif template == 'Convocati':
        output.update(team_name=ours, opponent=other, date=match['date'], kickoff=match['kickoff'],
                      meeting_time=match['meeting_time'], venue=match['venue'],
                      logo_id=match['our_logo_id'] if match['our_logo_id'] != 'none' else 'default')
    elif template == 'Classifica':
        output.update(our_team=ours, round_label=f"GIORNATA {match['round']}",
                      logo_id=match['our_logo_id'] if match['our_logo_id'] != 'none' else 'default')
    elif template == 'Calendario':
        output.update(our_team=ours, logo_id=match['our_logo_id'] if match['our_logo_id'] != 'none' else 'default')
    elif template == 'Starting 7':
        output.update(team_name=ours)
    if template in CRT_TEMPLATES_SET:
        output['season_round'] = match['round']
        output['event_theme'] = event_theme if event_theme is not None else themes.auto_event(match)
        if output.get('rotation_mode') == 'Per giornata':
            output = apply_preset(output, preset_for_round(match['round']))
        import layouts, variety
        if output.get('layout_rotation') and len(layouts.options(template)) > 1:
            output = layouts.apply(template, output, layouts.for_round(template, match['round']))
        if output.get('title_rotation'):
            output['title'] = variety.title_for_round(template, match['round']) or output['title']
    return sanitize_config(template, output)
