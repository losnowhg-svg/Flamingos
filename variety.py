"""Varietà: the choices that keep the weekly posts from looking all the same.

Rotating titles, intro styles, chiptune tracks, sprite poses and sprite
scenes. Everything is deterministic (by round, index or seed), so a graphic
renders the same in the preview, the PNG and the video.
"""
from __future__ import annotations

import random

INTRO_STYLES = {'press_start': 'PRESS START', 'cartuccia': 'Cartuccia', 'caricamento': 'Caricamento',
                'versus': 'VS da picchiaduro', 'mappa': 'Mappa dei livelli', 'logo': 'Logo che si compone',
                'rotazione': 'A rotazione (cambia ogni giornata)'}
MUSIC_TRACKS = {'auto': 'Automatica (in base a grafica e risultato)', 'arcade': 'Arcade, allegra', 'epica': 'Epica',
                'tensione': 'Tensione', 'festa': 'Festa'}
POSES = {'ferma': 'Ferma', 'esultanza': 'Esultanza', 'conserte': 'Braccia conserte', 'pollice': 'Pollice su',
         'palleggio': 'Palleggio', 'saluto': 'Saluto', 'guanti': 'Guanti da portiere'}
POSE_MODES = {'variate': 'Variate (in base al ruolo)', **POSES}
SCENES = {'sfumato': 'Sfumato', 'stadio': 'Stadio', 'notte': 'Notte', 'pioggia': 'Pioggia', 'neve': 'Neve'}
SCENE_MODES = {'sfumato': 'Sfumato', 'variate': 'Una diversa per reparto', **{k: v for k, v in SCENES.items() if k != 'sfumato'}}

TITLES = {
    'Matchday Screen': ('MATCHDAY SCREEN', 'GAME DAY', 'MATCH DAY', 'SI GIOCA', 'NEXT MATCH', 'PRESS START',
                        'READY? FIGHT!', 'LEVEL {n}', 'GIORNATA {n}', 'NEW CHALLENGER'),
    'Full Time': ('FULL TIME', 'FINE PARTITA', 'FINAL SCORE', 'RISULTATO FINALE', 'TIME UP', 'STAGE {n} END',
                  'GIORNATA {n}', 'TRIPLICE FISCHIO'),
    'Convocati': ('CONVOCATI', 'PLAYER SELECT', 'SQUAD LOADED', 'TEAM SELECT', 'LA SQUADRA', 'IN CAMPO',
                  'CHOOSE YOUR TEAM', 'PARTY READY'),
    'Classifica': ('CLASSIFICA', 'HIGH SCORES', 'LEADERBOARD', 'RANKING', 'LA CLASSIFICA', 'SCOREBOARD',
                   'TOP PLAYERS'),
    'Calendario': ('CALENDARIO', 'LEVEL SELECT', 'STAGE LIST', 'PROSSIMI LIVELLI', 'IL MESE', 'WORLD MAP'),
}
DEFAULT_TITLES = {k: v[0] for k, v in TITLES.items()}
GROUP_SCENES = {'P': 'stadio', 'D': 'pioggia', 'C': 'notte', 'A': 'stadio', 'STAFF': 'neve'}
ROLE_POSES = {'P': ('guanti', 'conserte'), 'D': ('conserte', 'pollice'), 'C': ('palleggio', 'pollice', 'saluto'),
              'A': ('esultanza', 'pollice', 'palleggio'), 'ALL': ('conserte', 'saluto'), 'DIR': ('saluto', 'pollice', 'conserte')}


def _round(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def fill(title, round_number):
    return title.replace('{n}', str(_round(round_number)))


def title_for_round(template, round_number):
    pool = TITLES.get(template)
    if not pool:
        return None
    n = _round(round_number)
    return fill(pool[(n-1) % len(pool)], n)


def random_title(template, current='', round_number=1, seed=None):
    """A different title from the pool (🎲)."""
    pool = [fill(t, round_number) for t in TITLES.get(template, ())]
    others = [t for t in pool if t != str(current).strip().upper()] or pool
    return random.Random(seed).choice(others) if others else current


def intro_style(config, kind=''):
    style = config.get('intro_style', 'press_start')
    if style not in INTRO_STYLES:
        style = 'press_start'
    if style == 'rotazione':
        cycle = ['press_start', 'cartuccia', 'caricamento', 'mappa']
        if kind in ('matchday', 'fulltime'):
            cycle.insert(2, 'versus')
        style = cycle[(_round(config.get('season_round', 1))-1) % len(cycle)]
    if style == 'versus' and kind not in ('matchday', 'fulltime'):
        style = 'press_start'
    return style


def music_track(config, kind='', outcome=None, theme=''):
    track = config.get('music_track', 'auto')
    if track in MUSIC_TRACKS and track != 'auto':
        return track
    if kind == 'fulltime':
        return {'win': 'festa', 'loss': 'tensione'}.get(outcome, 'arcade')
    if kind == 'matchday':
        return 'tensione' if theme in ('derby', 'bigmatch', 'ultima') else 'epica'
    if kind in ('convocati', 'reparto'):
        return 'epica'
    if kind == 'wrapped':
        return 'festa'
    return 'arcade'


def pose_for(member, index, mode='variate'):
    if mode in POSES:
        return mode
    if mode != 'variate':
        return 'ferma'
    options = ROLE_POSES.get(member.get('role'), ('pollice', 'conserte'))
    return options[index % len(options)]


def scene_for(group, mode='sfumato'):
    if mode in SCENES:
        return mode
    if mode == 'variate':
        return GROUP_SCENES.get(group, 'notte')
    return 'sfumato'
