"""Flamingos Wrapped: the season (or a month) told in retro slides.

Every slide uses the Classifica editor's style (preset, theme, colours,
font, format, animations, TV mockup) and the shared header + body panels.
Big numbers count up in videos, like the Full Time score.
"""
from __future__ import annotations

import copy

from PIL import Image

from render_utils import ScaledDraw, checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, rgb
from matchday_renderer import _decorate_text
from crt_presets import background
from crt_common import compose, export_png, export_video

POSITIONS = {'logo': (118, 346), 'title': (294, 337), 'subtitle': (294, 360), 'big': (270, 478),
             'label': (270, 545), 'bar': (270, 588), 'line1': (270, 626), 'line2': (270, 651),
             'left': (178, 520), 'right': (362, 520), 'list': (270, 530)}
SLIDES = ('intro', 'partite', 'gol', 'piu_bella', 'serie', 'casa_trasferta', 'bomber', 'classifica', 'outro')
SLIDE_NAMES = {'intro': 'Intro', 'partite': 'Partite', 'gol': 'Gol', 'piu_bella': 'La più bella', 'serie': 'La serie',
               'casa_trasferta': 'Casa e trasferta', 'bomber': 'Bomber', 'classifica': 'Classifica', 'outro': 'Finale'}
WIN, DRAW, LOSS = (91, 230, 164), (255, 201, 99), (255, 107, 120)


def normalized_positions(config):
    return safe_positions({}, POSITIONS)


def _txt(config, value, size, color, width, font_bytes, s, height=None):
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    return _decorate_text(text_image(str(value), style, size, color, width, font_bytes, s, height or size+2), s)


def _bar(w, d, l, s, width=300, height=16):
    total = max(1, w+d+l)
    img = Image.new('RGBA', (width*s, height*s))
    dr = ScaledDraw(img, s)
    x = 0
    for count, col in ((w, WIN), (d, DRAW), (l, LOSS)):
        if count:
            span = width*count/total
            dr.rectangle((x, 0, x+span-1, height), fill=(*col, 255))
            x += span
    dr.rectangle((0, 0, width-1, height-1), outline=(255, 255, 255, 140), width=1)
    return img


def _column(config, title, record, font_bytes, s):
    cyan = rgb(config.get('cyan', '#79DCF7')); white = rgb(config.get('white', '#F6F4FC'))
    yellow = rgb(config.get('yellow', '#FFC963'))
    img = Image.new('RGBA', (170*s, 130*s))
    rows = [(title, cyan, 14), (f"{record['w']}V {record['d']}N {record['l']}P", white, 16),
            (f"{3*record['w']+record['d']} PUNTI", yellow, 14), (f"GOL {record['gf']}-{record['ga']}", white, 12)]
    y = 10
    for value, color, size in rows:
        t = _txt(config, value, size, color, 166, font_bytes, s)
        if t:
            img.alpha_composite(t, ((img.width-t.width)//2, round(y*s)))
        y += size+16
    return img


def _scorer_list(config, scorers, squad, font_bytes, s):
    import pixel_character
    white = rgb(config.get('white', '#F6F4FC')); yellow = rgb(config.get('yellow', '#FFC963'))
    pink = rgb(config.get('pink', '#F268A8'))
    rows = scorers[:5]
    img = Image.new('RGBA', (360*s, 200*s))
    looks = {p['name'].upper(): p for p in squad or []}
    for i, (name, goals) in enumerate(rows):
        y = i*38+4
        member = looks.get(str(name).upper(), {})
        sprite = pixel_character.picture(member, config.get('preset_id', 'crt'))
        k = max(1, int(32*s//sprite.width))
        sprite = sprite.resize((sprite.width*k, sprite.height*k), Image.Resampling.NEAREST)
        img.alpha_composite(sprite, (round(30*s), round(y*s)))
        rank = _txt(config, f'{i+1}.', 16, pink, 30, font_bytes, s)
        if rank:
            img.alpha_composite(rank, (0, round((y+8)*s)))
        nm = _txt(config, str(name).upper(), 16, white, 200, font_bytes, s)
        if nm:
            img.alpha_composite(nm, (round(72*s), round((y+8)*s)))
        gl = _txt(config, f'{goals} GOL', 16, yellow, 80, font_bytes, s)
        if gl:
            img.alpha_composite(gl, (img.width-gl.width, round((y+8)*s)))
    return img


def get_layers(config, home_logo, away_logo=None, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    slide = config.get('slide', {})
    pink = rgb(config.get('pink', '#F268A8')); white = rgb(config.get('white', '#F6F4FC'))
    yellow = rgb(config.get('yellow', '#FFC963')); cyan = rgb(config.get('cyan', '#79DCF7'))
    layers = [Layer('logo', 'Stemma', clean_logo(home_logo, 40, True, s))]

    def add(id_, value, size, color, width=300, height=None):
        img = _txt(config, value, size, color, width, font_bytes, s, height)
        if img:
            layers.append(Layer(id_, id_, img))
        return img

    add('title', slide.get('title', 'WRAPPED'), 24, white, 280, 24)
    add('subtitle', slide.get('subtitle', ''), 10, pink, 280, 13)
    if slide.get('big') is not None:
        big = str(slide['big'])
        layer_img = _txt(config, big, slide.get('big_size', 84), yellow, 340, font_bytes, s, slide.get('big_size', 84)+6)
        if layer_img:
            layer = Layer('big', 'Numero', layer_img)
            if slide.get('count') and big.isdigit() and int(big) > 0:
                n = int(big)
                steps = sorted({round(k*n/min(n, 12)) for k in range(min(n, 12)+1)})
                layer.variants = [_txt(config, str(v), slide.get('big_size', 84), yellow, 340, font_bytes, s,
                                       slide.get('big_size', 84)+6) for v in steps]
            layers.append(layer)
    if slide.get('label'):
        add('label', slide['label'], 16, cyan, 330)
    if slide.get('bar'):
        layers.append(Layer('bar', 'Barra', _bar(*slide['bar'], s)))
    for key in ('line1', 'line2'):
        if slide.get(key):
            add(key, slide[key], 12, white, 340)
    if slide.get('columns'):
        left, right = slide['columns']
        layers.append(Layer('left', 'Casa', _column(config, 'CASA', left, font_bytes, s)))
        layers.append(Layer('right', 'Trasferta', _column(config, 'TRASFERTA', right, font_bytes, s)))
    if slide.get('scorers'):
        layers.append(Layer('list', 'Marcatori', _scorer_list(config, slide['scorers'], config.get('squad', []), font_bytes, s)))
    return layers


def scene(config, home_logo, away_logo=None, font_bytes=None, render_scale=2):
    import themes
    from crt_common import finish
    s = checked_scale(render_scale)
    config = themes.effective(config)
    return finish((background(config, 'classifica', s), get_layers(config, home_logo, away_logo, font_bytes, s),
                   normalized_positions(config)), config, 'wrapped')


def png_bytes(config, home_logo, away_logo=None, font_bytes=None, format='Story 9:16', scale=2, supersample=2):
    return export_png(scene, config, home_logo, away_logo, font_bytes, format, scale, supersample)


def render_video(config, home_logo, away_logo, path, font_bytes=None, fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None):
    return export_video(scene, config, home_logo, away_logo, path, font_bytes, fps, duration, format, scale, progress_callback)


# --- From season numbers to slides -------------------------------------------

def _title(value):
    return ' '.join(w if (len(w) <= 3 and w.isupper()) or any(c.isdigit() for c in w) else w.capitalize()
                    for w in str(value).split())


def slides(numbers, label, base_config, scorers=None, standings_row=None, squad=None, chosen=SLIDES):
    """[(slide id, config)] for the slides that have something to say."""
    out = []
    n = numbers

    def add(key, **slide):
        if key in chosen:
            config = copy.deepcopy(base_config)
            config['slide'] = slide
            config['squad'] = squad or []
            out.append((key, config))

    add('intro', title='WRAPPED', subtitle=label, big='FLAMINGOS', big_size=40, label='PRESS START',
        line1='LA NOSTRA STAGIONE IN PIXEL' if 'STAGIONE' in label else f'IL NOSTRO {label}')
    if not n:
        add('outro', title='GAME SAVED', subtitle=label, big='GRAZIE', big_size=48, label='SEE YOU NEXT LEVEL')
        return out
    add('partite', title='PARTITE', subtitle=label, big=n['played'], count=True, label='PARTITE GIOCATE',
        bar=(n['w'], n['d'], n['l']), line1=f"{n['w']} VITTORIE / {n['d']} PAREGGI / {n['l']} SCONFITTE",
        line2=f"{n['points']} PUNTI CONQUISTATI")
    add('gol', title='GOL', subtitle=label, big=n['gf'], count=True, label='GOL FATTI',
        line1=f"{n['avg']} A PARTITA / {n['ga']} SUBITI", line2=(f"{n['clean']} {'VOLTA' if n['clean'] == 1 else 'VOLTE'} PORTA INVIOLATA" if n['clean'] else
                                                              f"DIFFERENZA RETI {n['gd']:+d}"))
    if n.get('best'):
        b = n['best']
        add('piu_bella', title='LA PIÙ BELLA', subtitle=label, big=f"{b['us']}-{b['them']}", big_size=68,
            label=f"VS {_title(b['opp']).upper()}", line1=f"{'IN CASA' if b['home'] else 'IN TRASFERTA'} / {b['date'].strftime('%d/%m')}",
            line2='HIGH SCORE SBLOCCATO')
    if n['win_streak'] >= 2 or n['unbeaten'] >= 3:
        wins = n['win_streak'] >= 2
        add('serie', title='LA SERIE', subtitle=label, big=n['win_streak'] if wins else n['unbeaten'], count=True,
            label='VITTORIE DI FILA' if wins else 'RISULTATI UTILI DI FILA',
            line1='COMBO x'+str(n['win_streak'] if wins else n['unbeaten']), line2='NESSUNO CI FERMAVA')
    if n['home']['played'] and n['away']['played']:
        add('casa_trasferta', title='CASA / TRASFERTA', subtitle=label, columns=(n['home'], n['away']))
    if scorers:
        top = sorted([s for s in scorers if s[1] > 0], key=lambda s: -s[1])
        if top:
            add('bomber', title='BOMBER', subtitle=label, scorers=top)
    if standings_row:
        pos = int(standings_row.get('pos', 0) or 0)
        if pos:
            add('classifica', title='CLASSIFICA', subtitle=label, big=str(pos), big_size=96,
                label='POSTO IN CLASSIFICA', line1=f"{int(standings_row.get('pt', 0))} PUNTI",
                line2='E NON È FINITA' if pos > 1 else 'PRIMI. PUNTO.')
    add('outro', title='GAME SAVED', subtitle=label, big='GRAZIE', big_size=48, label='SEE YOU NEXT LEVEL',
        line1='A CHI HA GIOCATO, TIFATO, ASPETTATO', line2='FORZA FLAMINGOS')
    return out
