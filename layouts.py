"""Alternative page layouts (impaginazioni) for the CRT graphics.

A layout is a set of panels drawn on the screen, default positions for the
layers and a few size defaults. Choosing a layout in the editor resets the
positions to that layout's own (they can still be moved by hand afterwards).
'Cambia impaginazione a ogni giornata' picks one per round when the match of
the week is applied.

Panels are (x1, y1, x2, y2, flags) in 540x960 units; flags may contain
'soft' (lighter border), 'line' (a thin divider instead of a box) and
'scorers' (dropped when the scorers are hidden).
"""
from __future__ import annotations

import copy

KINDS = {'Matchday Screen': 'matchday', 'Full Time': 'fulltime', 'Convocati': 'convocati', 'Classifica': 'classifica'}

LAYOUTS = {
    'Matchday Screen': {
        'classica': dict(label='Classica', description='Stemmi affiancati con il VS in mezzo, nomi e info sotto.'),
        'duello': dict(
            label='Duello', description='Le due squadre una sopra l\'altra, in diagonale, come una sfida da picchiaduro.',
            panels=((112, 322, 428, 390, ''), (214, 425, 449, 463, ''), (91, 548, 326, 586, ''), (93, 612, 448, 672, '')),
            positions={'title': (270, 344), 'date': (270, 370), 'home_logo': (146, 446), 'home_name': (331, 444),
                       'vs': (270, 503), 'away_name': (208, 567), 'away_logo': (394, 560),
                       'kickoff': (270, 631), 'venue': (270, 655)},
            sizes={'home_logo_size': 76, 'away_logo_size': 76}),
        'locandina': dict(
            label='Locandina', description='Stemmi grandi in alto, la data in evidenza nel riquadro sotto.',
            panels=((108, 322, 432, 362, ''), (91, 500, 242, 538, ''), (297, 500, 449, 538, ''), (93, 550, 448, 672, '')),
            positions={'title': (270, 342), 'home_logo': (158, 430), 'away_logo': (382, 430), 'vs': (270, 432),
                       'home_name': (166, 519), 'away_name': (374, 519), 'date': (270, 580),
                       'kickoff': (270, 621), 'venue': (270, 648)},
            sizes={'home_logo_size': 86, 'away_logo_size': 86, 'title_size': 24}),
    },
    'Full Time': {
        'classica': dict(label='Classica', description='Stemmi e risultato in fila, esito e marcatori sotto.'),
        'tabellone': dict(
            label='Tabellone', description='Il risultato gigante in un tabellone, stemmi piccoli ai lati.',
            panels=((107, 322, 433, 366, ''), (150, 392, 390, 482, ''), (91, 492, 237, 528, ''), (303, 492, 449, 528, ''),
                    (87, 566, 453, 673, 'soft scorers'), (270, 580, 270, 660, 'line scorers')),
            positions={'title': (270, 344), 'details': (270, 380), 'home_logo': (112, 437), 'away_logo': (428, 437),
                       'score': (270, 437), 'penalties': (270, 474), 'home_name': (164, 510), 'away_name': (376, 510),
                       'result': (270, 547), 'home_scorers': (174, 621), 'away_scorers': (366, 621)},
            sizes={'score_size': 72, 'home_logo_size': 48, 'away_logo_size': 48}),
        'esito': dict(
            label='Esito in alto', description='Vittoria, pareggio o sconfitta subito sotto il titolo, poi la partita.',
            panels=((107, 322, 433, 384, ''), (150, 392, 390, 424, ''), (91, 516, 237, 550, ''), (303, 516, 449, 550, ''),
                    (87, 562, 453, 673, 'soft scorers'), (270, 576, 270, 660, 'line scorers')),
            positions={'title': (270, 343), 'details': (270, 371), 'result': (270, 409), 'home_logo': (150, 470),
                       'away_logo': (390, 470), 'score': (270, 470), 'penalties': (270, 505), 'home_name': (164, 533),
                       'away_name': (376, 533), 'home_scorers': (174, 618), 'away_scorers': (366, 618)},
            sizes={'home_logo_size': 60, 'away_logo_size': 60, 'result_size': 18}),
    },
    'Convocati': {
        'classica': dict(label='Classica', description='Lista dei convocati al centro, ritrovo e campo in fondo.'),
        'logistica': dict(
            label='Logistica in alto', description='Avversari, ritrovo e campo subito sotto il titolo, poi la lista.',
            panels=((84, 321, 456, 388, ''), (84, 393, 456, 452, '')),
            positions={'match': (270, 406), 'meeting': (270, 423), 'venue': (270, 440), 'legend': (270, 664),
                       **{f'player_{i}': (174 if i % 2 == 0 else 366, 470+(i//2)*21) for i in range(18)}}),
    },
    'Classifica': {
        'classica': dict(label='Classica', description='Titolo e stemma in alto, tabella sotto.'),
        'piede': dict(
            label='Titolo in fondo', description='La tabella prende la parte alta dello schermo, il titolo chiude in basso.',
            panels=((84, 321, 456, 614, 'soft'), (84, 622, 456, 673, '')),
            positions={'table': (270, 467), 'logo': (118, 647), 'title': (294, 639), 'subtitle': (294, 661)}),
    },
}


def options(template):
    return tuple(LAYOUTS.get(template, {'classica': {}}))


def label(template, layout_id):
    return LAYOUTS.get(template, {}).get(layout_id, {}).get('label', 'Classica')


def current(template, config):
    layout = config.get('layout', 'classica')
    return layout if layout in LAYOUTS.get(template, {}) else 'classica'


def default_positions(template, layout_id='classica'):
    from studio_state import MODULES
    positions = {k: tuple(v) for k, v in MODULES[template].DEFAULT_POSITIONS.items()}
    positions.update(LAYOUTS.get(template, {}).get(layout_id, {}).get('positions', {}))
    return positions


def apply(template, config, layout_id):
    """A copy of config switched to layout_id: positions reset, layout sizes applied."""
    from studio_state import defaults
    out = copy.deepcopy(config)
    if layout_id not in LAYOUTS.get(template, {}):
        layout_id = 'classica'
    base = defaults(template)
    previous = LAYOUTS.get(template, {}).get(out.get('layout', 'classica'), {}).get('sizes', {})
    for key in previous:   # sizes set by the previous layout go back to their default
        out[key] = base.get(key, out.get(key))
    out.update(LAYOUTS[template][layout_id].get('sizes', {}))
    out['layout'] = layout_id
    out['positions'] = {k: list(v) for k, v in default_positions(template, layout_id).items()}
    return out


def for_round(template, round_number):
    ids = options(template)
    try:
        n = max(1, int(round_number))
    except (TypeError, ValueError):
        n = 1
    return ids[(n-1) % len(ids)]


def panel_key(base, template, config):
    """The PANEL_LAYOUTS key for this layout (base: 'matchday', 'fulltime', 'fulltime_clean'...)."""
    layout = current(template, config)
    return base if layout == 'classica' else f'{base}@{layout}'


def _register():
    from crt_presets import PANEL_LAYOUTS
    for template, variants in LAYOUTS.items():
        kind = KINDS[template]
        for layout_id, spec in variants.items():
            if 'panels' not in spec:
                continue
            PANEL_LAYOUTS[f'{kind}@{layout_id}'] = spec['panels']
            if kind == 'fulltime':
                PANEL_LAYOUTS[f'fulltime_clean@{layout_id}'] = tuple(p for p in spec['panels'] if 'scorers' not in p[4])


_register()
