"""Calendario: our matches of the month, results coloured, next match in pink."""
from __future__ import annotations

from PIL import Image

from render_utils import ScaledDraw, checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, rgb
from matchday_renderer import _decorate_text
from crt_presets import background
from crt_common import compose, export_png, export_video

MAX_FIXTURES = 8
TABLE_W, TABLE_H = 364, 287
DEFAULT_POSITIONS = {'logo': (118, 346), 'title': (294, 337), 'subtitle': (294, 360), 'table': (270, 527)}
LAYER_NAMES = {'logo': 'Stemma', 'title': 'Titolo calendario', 'subtitle': 'Mese', 'table': 'Partite del mese'}
WIN, DRAW, LOSS = (91, 230, 164), (255, 201, 99), (255, 107, 120)


def empty_fixture():
    return dict(date='', day='', opponent='', side='C', time='', score='')


def normalized_positions(config):
    return safe_positions(config, DEFAULT_POSITIONS)


def active_fixtures(config):
    count = max(1, min(MAX_FIXTURES, int(config.get('fixture_count', 4))))
    return [f for f in config.get('fixtures', [])[:count] if str(f.get('opponent', '')).strip()]


def result_of(fixture):
    """'V', 'N', 'P' from our side, or None if not played."""
    try:
        home, away = (int(x) for x in str(fixture.get('score', '')).replace(' ', '').split('-'))
    except ValueError:
        return None
    us, them = (home, away) if fixture.get('side', 'C') == 'C' else (away, home)
    return 'V' if us > them else 'N' if us == them else 'P'


def table_image(config, font_bytes=None, s=1):
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    pink = rgb(config.get('pink', '#F268A8')); cyan = rgb(config.get('cyan', '#79DCF7'))
    white = rgb(config.get('white', '#F6F4FC')); yellow = rgb(config.get('yellow', '#FFC963'))
    ink = (9, 11, 22)
    rows = active_fixtures(config)
    image = Image.new('RGBA', (TABLE_W*s, TABLE_H*s))
    d = ScaledDraw(image, s)
    if not rows:
        im = text_image('NESSUNA PARTITA', style, 12, cyan, 300, font_bytes, s, 14)
        if im:
            image.alpha_composite(im, ((image.width-im.width)//2, (image.height-im.height)//2))
        return image
    gap = 5
    row_h = min(52, (TABLE_H-gap*(len(rows)-1))/len(rows))
    big = max(8, min(15, row_h*.34))
    small = max(6, min(9, row_h*.2))
    next_index = next((i for i, f in enumerate(rows) if result_of(f) is None), None)

    def put(value, color, x, y, width, size, align='center', height=None):
        im = text_image(str(value), style, size, color, width, font_bytes, s, height or size+2)
        if not im:
            return
        left = round(x*s) if align == 'left' else round((x+width/2)*s-im.width/2)
        image.alpha_composite(im, (left, round(y*s-im.height/2)))

    offset = (TABLE_H-(row_h*len(rows)+gap*(len(rows)-1)))/2
    for i, f in enumerate(rows):
        top = offset+i*(row_h+gap)
        mid = top+row_h/2
        is_next = i == next_index
        result = result_of(f)
        body = (*pink, 245) if is_next else (255, 255, 255, 18)
        d.rectangle((0, top, TABLE_W, top+row_h), fill=body)
        text = ink if is_next else white
        accent = ink if is_next else cyan
        # Date block.
        d.rectangle((0, top, 66, top+row_h), fill=(*(ink if is_next else cyan), 255 if is_next else 40))
        put(str(f.get('day', '')).upper()[:3], pink if is_next else yellow, 0, mid-row_h*.2, 66, small)
        put(f.get('date', ''), white if is_next else white, 0, mid+row_h*.14, 66, big*.92)
        # Home / away badge and opponent.
        side = 'CASA' if f.get('side', 'C') == 'C' else 'TRASFERTA'
        put(side, accent, 76, mid-row_h*.22, 120, small, 'left')
        put('VS '+str(f.get('opponent', '')).upper(), text, 76, mid+row_h*.13, 196, big, 'left')
        # Time, or the score with a coloured result.
        if result:
            colour = {'V': WIN, 'N': DRAW, 'P': LOSS}[result]
            d.rectangle((TABLE_W-78, top+4, TABLE_W-4, top+row_h-4), fill=(*colour, 255))
            put(f.get('score', ''), ink, TABLE_W-78, mid-row_h*.08, 74, big)
            put({'V': 'VITTORIA', 'N': 'PAREGGIO', 'P': 'SCONFITTA'}[result], ink, TABLE_W-78, mid+row_h*.26, 74, small*.85)
        else:
            if is_next:
                put('NEXT', ink, TABLE_W-78, mid-row_h*.22, 74, small)
            put(f.get('time', '') or '--:--', ink if is_next else yellow, TABLE_W-78, mid+row_h*.1, 74, big)
    return image


def get_layers(config, home_logo, away_logo=None, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    pink = rgb(config.get('pink', '#F268A8')); white = rgb(config.get('white', '#F6F4FC'))
    layers = [Layer('logo', LAYER_NAMES['logo'], clean_logo(home_logo, config.get('logo_size', 40), config.get('remove_white', True), s))]
    title = _decorate_text(text_image(config.get('title', 'CALENDARIO'), style, config.get('title_size', 24), white, 280, font_bytes, s, 24), s)
    if title:
        layers.append(Layer('title', LAYER_NAMES['title'], title))
    sub = _decorate_text(text_image(config.get('month_label', ''), style, config.get('info_size', 10), pink, 280, font_bytes, s, 13), s)
    if sub:
        layers.append(Layer('subtitle', LAYER_NAMES['subtitle'], sub))
    layers.append(Layer('table', LAYER_NAMES['table'], table_image(config, font_bytes, s)))
    return layers


def scene(config, home_logo, away_logo=None, font_bytes=None, render_scale=2):
    s = checked_scale(render_scale)
    return background(config, 'classifica', s), get_layers(config, home_logo, away_logo, font_bytes, s), normalized_positions(config)


def png_bytes(config, home_logo, away_logo=None, font_bytes=None, format='Story 9:16', scale=2, supersample=2):
    return export_png(scene, config, home_logo, away_logo, font_bytes, format, scale, supersample)


def render_video(config, home_logo, away_logo, path, font_bytes=None, fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None):
    return export_video(scene, config, home_logo, away_logo, path, font_bytes, fps, duration, format, scale, progress_callback)
