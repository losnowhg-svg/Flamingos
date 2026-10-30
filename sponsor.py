"""Sponsor: a small sticker under the screen of every CRT graphic, on the TV
cabinet in the mockup, and an optional thank-you slide at the end of videos.

The sponsor logo is a logo from the browser archive (+ Stemmi). Assets are
content-addressed (their id is the SHA-256 of the bytes), so a process-wide
registry from id to bytes is safe to share.
"""
from __future__ import annotations

from functools import lru_cache

from PIL import Image

from render_utils import ScaledDraw, checked_scale, safe_positions

REGISTRY: dict[str, bytes] = {}
STICKER_Y = 685           # centre of the sticker, in 540x960 units, just under the screen
POSITIONS = {'title': (270, 337), 'subtitle': (270, 360), 'logo': (270, 500), 'name': (270, 610), 'line': (270, 645)}


def register(assets):
    for id_, item in (assets or {}).items():
        if item.get('kind') == 'logo':
            REGISTRY[id_] = item['bytes']


def active(config):
    return bool(config.get('sponsor_on')) and config.get('sponsor_logo_id') in REGISTRY


@lru_cache(maxsize=16)
def _logo(logo_id, height_px):
    from renderer import clean_logo
    img = clean_logo(REGISTRY[logo_id], 400, True, 1)
    k = height_px/max(1, img.height)
    return img.resize((max(1, round(img.width*k)), max(1, round(height_px))), Image.Resampling.LANCZOS)


def sticker(config, s=1):
    """The sponsor pill as an RGBA image at scale s, or None."""
    if not active(config):
        return None
    from crt_presets import _rgb
    from pixel_fonts import pixel_text_runs
    cyan = tuple(_rgb(config.get('cyan', '#79DCF7')))
    logo = _logo(config['sponsor_logo_id'], round(13*s))
    label = pixel_text_runs([('SPONSOR', cyan)], 'CRT Terminal', 7, 100, s)
    name = str(config.get('sponsor_name', '')).strip().upper()[:24]
    name_img = pixel_text_runs([(name, (246, 244, 252))], 'CRT Terminal', 8, 140, s) if name else None
    pad, gap = round(6*s), round(5*s)
    width = pad*2+(label.width if label else 0)+gap+logo.width+((gap+name_img.width) if name_img else 0)
    height = round(18*s)
    pill = Image.new('RGBA', (width, height))
    d = ScaledDraw(pill, s)
    d.rounded_rectangle((0, 0, width/s-1, 17), radius=4, fill=(10, 8, 18, 235), outline=(*cyan, 220), width=1)
    x = pad
    for part in (label, logo, name_img):
        if part is None:
            continue
        pill.alpha_composite(part, (x, (height-part.height)//2))
        x += part.width+gap
    return pill


def decorate(image, config):
    """Add the sticker under the screen of a background (RGBA, any scale)."""
    pill = sticker(config, max(1, round(image.width/540)))
    if pill is None:
        return image
    s = image.width/540
    image.alpha_composite(pill, (round(270*s-pill.width/2), round(STICKER_Y*s-pill.height/2)))
    image.info['sponsor'] = config['sponsor_logo_id']
    return image


# --- Thank-you slide ---------------------------------------------------------

def normalized_positions(config):
    return safe_positions({}, POSITIONS)


def get_layers(config, home_logo=None, away_logo=None, font_bytes=None, render_scale=1):
    from renderer import Layer, text_image, rgb
    from matchday_renderer import _decorate_text
    s = checked_scale(render_scale)
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    white = rgb(config.get('white', '#F6F4FC')); pink = rgb(config.get('pink', '#F268A8'))
    cyan = rgb(config.get('cyan', '#79DCF7'))
    layers = []

    def add(id_, value, size, color, width=340):
        import title_fx
        raw = text_image(value, style, size, color, width, font_bytes, s, size+2)
        img = title_fx.title(raw, config, s) if id_ == 'title' else _decorate_text(raw, s)
        if img:
            layers.append(Layer(id_, id_, img))
    add('title', 'GRAZIE A', 24, white)
    add('subtitle', 'SPONSOR UFFICIALE FLAMINGOS', 10, pink)
    if active(config):
        logo = _logo(config['sponsor_logo_id'], round(170*s))
        if logo.width > 330*s:
            logo = logo.resize((round(330*s), round(logo.height*330*s/logo.width)), Image.Resampling.LANCZOS)
        layers.append(Layer('logo', 'Sponsor', logo))
    name = str(config.get('sponsor_name', '')).strip().upper()
    if name:
        add('name', name, 18, cyan)
    add('line', 'PRESS START TO SUPPORT', 10, white)
    return layers


def scene(config, home_logo=None, away_logo=None, font_bytes=None, render_scale=2):
    import themes
    from crt_common import finish
    from crt_presets import background
    s = checked_scale(render_scale)
    config = themes.effective(dict(config, sponsor_on=True))
    prepared = (background(config, 'classifica', s),
                get_layers(config, home_logo, away_logo, font_bytes, s), normalized_positions(config))
    return finish(prepared, config, 'sponsor')


def compose(prepared, t=999, animated=True):
    from crt_common import compose as crt_compose
    return crt_compose(prepared, t, animated)
