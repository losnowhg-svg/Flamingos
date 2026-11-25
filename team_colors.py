"""3.25: the opponent's colours on their half of Matchday and Full Time.

The CSI site lists every team's colours as plain words ("GIALLO ROSSO", "BIANCA/ROSSA",
"FUCSIA E NERA"). They become two RGB colours that paint, on the opponent's side only:
a striped frame around their name box, a die-cut outline around their crest and their
name. Our half stays pink and black, the preset stays the same.
"""
from __future__ import annotations

import re
import unicodedata

from PIL import Image, ImageFilter

from render_utils import ScaledDraw

# Word stems (accents and apostrophes removed, upper case) -> colour.
STEMS = (
    ('BIANC', (245, 245, 242)), ('NER', (18, 18, 22)), ('ROSS', (222, 32, 44)), ('ROSA', (246, 120, 178)),
    ('FUCS', (232, 36, 146)), ('MAGENT', (220, 40, 160)), ('GIALL', (255, 208, 0)), ('ORO', (214, 172, 52)),
    ('DORAT', (214, 172, 52)), ('AZZURR', (64, 168, 240)), ('CELEST', (126, 202, 246)), ('BLU', (28, 72, 196)),
    ('VERD', (24, 156, 76)), ('ARANC', (255, 128, 24)), ('VIOL', (128, 52, 172)), ('GRANAT', (128, 22, 42)),
    ('AMARANT', (150, 22, 52)), ('BORDEAUX', (112, 16, 36)), ('GRIG', (140, 142, 152)), ('ARGENT', (192, 196, 206)),
    ('MARRON', (122, 72, 32)), ('TURCHES', (30, 196, 188)), ('LILL', (182, 140, 222)),
)
SKIP = {'E', 'ED', 'O', 'OD', 'CON', 'A', 'DI', 'MAGLIA', 'MAGLIE', 'STRISCE', 'RIGHE', 'BANDE', 'SCURO', 'CHIARO'}

# The girone as listed on the CSI site (team cards), for when the site has not been read yet.
GIRONE = {
    'as_ardens': 'GIALLO ROSSO', 'caste_united': 'BIANCA/ROSSA', 'castel_mella': 'BLU', 'galba_fc': 'BLU',
    'sporting_leno': 'BLU', 'fc_mustangs': 'FUCSIA E NERA', 'gso_poncarale': 'NERO', 'gso_verolan': "BLU'/AZZURRO",
    'lions_25': 'BIANCO BLU', 'pirati': 'ROSSA', 'umc': 'ROSSO-BLU', 'united_flero': 'NERA O BIANCA',
}


def _plain(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r"[^A-Z]+", ' ', text.upper()).split()


def parse(text):
    """Up to two colours from the CSI words, in order ('NERA O BIANCA' -> black, white)."""
    out = []
    for word in _plain(text):
        if word in SKIP:
            continue
        for stem, color in STEMS:
            if word.startswith(stem) and (stem != 'ROSA' or word in ('ROSA', 'ROSE')):
                if color not in out:
                    out.append(color)
                break
    return out[:2]


def to_hex(colors):
    return ','.join('#%02X%02X%02X' % tuple(c) for c in colors)


def from_hex(value):
    out = []
    for part in str(value or '').split(','):
        part = part.strip()
        if re.fullmatch(r'#[0-9A-Fa-f]{6}', part):
            out.append(tuple(bytes.fromhex(part[1:])))
    return out[:2]


def _lum(c):
    return (.2126*c[0]+.7152*c[1]+.0722*c[2])/255


def _sat(c):
    hi, lo = max(c), min(c)
    return 0 if hi == 0 else (hi-lo)/hi


def _mix(a, b, k):
    return tuple(round(x+(y-x)*k) for x, y in zip(a, b))


def readable(c, minimum=.5):
    """The same hue, lifted towards white until it reads on a dark panel."""
    k = 0
    out = tuple(c)
    while _lum(out) < minimum and k < 1:
        k += .08
        out = _mix(c, (255, 255, 255), k)
    return out


def pair(colors):
    """(main, second, text) for drawing: a single colour gets a darker or lighter twin."""
    if not colors:
        return None
    main = tuple(colors[0])
    second = tuple(colors[1]) if len(colors) > 1 else (_mix(main, (255, 255, 255), .55) if _lum(main) < .35
                                                       else _mix(main, (0, 0, 0), .55))
    chromatic = [c for c in (main, second) if _sat(c) > .3]
    text = readable(chromatic[0]) if chromatic else (246, 244, 240)
    return main, second, text


def opponent_side(config):
    return 'home' if config.get('our_side', 'Casa') == 'Ospiti' else 'away'


def opponent_name(config):
    return str(config.get(opponent_side(config)+'_name', '') or '')


def girone_words(name):
    import crests
    return GIRONE.get(crests.match(name) or '', '')


def colors_for(config):
    """The opponent's colours: the stored ones while they belong to this opponent, else the girone list."""
    name = opponent_name(config)
    owner = str(config.get('opponent_colors_for', '') or '')
    stored = from_hex(config.get('opponent_colors')) if owner in ('', name[:42]) else []
    return stored or parse(girone_words(name))


def for_config(config):
    """(main, second, text) for the opponent of this graphic, or None (switched off or unknown team)."""
    if not config.get('opp_colors_on', True):
        return None
    return pair(colors_for(config))


def lookup(name, csi_colors=None):
    """'#RRGGBB,#RRGGBB' for a team name: the CSI cards first ({team: words}), then the girone list."""
    from integration import same_team
    for team, words in (csi_colors or {}).items():
        if words and same_team(team, name):
            colors = parse(words)
            if colors:
                return to_hex(colors)
    return to_hex(parse(girone_words(name)))


# --- Drawing -------------------------------------------------------------------

def panel_for(config, template, panel_key):
    """The background panel holding the opponent's name in this layout (it never moves with the text)."""
    import layouts
    from crt_presets import PANEL_LAYOUTS
    x, y = layouts.default_positions(template, layouts.current(template, config))[opponent_side(config)+'_name']
    for rect in PANEL_LAYOUTS.get(panel_key, ()):
        x1, y1, x2, y2 = rect[:4]
        if x1 < x < x2 and y1 <= y <= y2 and x2-x1 > 20 and y2-y1 > 10:
            return tuple(rect[:4])
    return None


def frame_panel(image, rect, colors, s):
    """A scarf-striped frame just outside the opponent's name box (any panel style stays readable)."""
    main, second, _ = colors
    x1, y1, x2, y2 = rect
    gap, width = 2.5, 3
    ox1, oy1, ox2, oy2 = x1-gap-width, y1-gap-width, x2+gap+width, y2+gap+width
    left, top = int(ox1*s)-round(10*s), int(oy1*s)-round(10*s)
    size = (int((ox2-ox1+20)*s)+2, int((oy2-oy1+20)*s)+2)
    def local(box):
        return tuple(v-(left if i % 2 == 0 else top)/s for i, v in enumerate(box))
    ring = Image.new('L', size)
    d = ScaledDraw(ring, s)
    d.rounded_rectangle(local((ox1, oy1, ox2, oy2)), radius=6, fill=255)
    d.rounded_rectangle(local((x1-gap, y1-gap, x2+gap, y2+gap)), radius=4, fill=0)
    stripes = Image.new('RGBA', size, (*main, 255))
    sd = ScaledDraw(stripes, s)
    band = 7
    for k in range(-size[1], size[0]+size[1], round(2*band*s)):
        x = k/s
        sd.polygon([(x, 0), (x+band, 0), (x+band-size[1]/s, size[1]/s), (x-size[1]/s, size[1]/s)], fill=(*second, 255))
    glow = Image.new('RGBA', size, (*main, 0))
    glow.putalpha(ring.filter(ImageFilter.GaussianBlur(4*s)).point(lambda v: v*.55))
    edge = Image.new('RGBA', size, (250, 250, 250, 0))
    outline = Image.new('L', size)
    od = ScaledDraw(outline, s)
    od.rounded_rectangle(local((ox1, oy1, ox2, oy2)), radius=6, outline=150, width=.8)
    od.rounded_rectangle(local((x1-gap, y1-gap, x2+gap, y2+gap)), radius=4, outline=110, width=.6)
    edge.putalpha(outline)
    stripes.putalpha(ring)
    piece = Image.new('RGBA', size)
    for part in (glow, stripes, edge):
        piece.alpha_composite(part)
    image.alpha_composite(piece, (max(0, left), max(0, top)), (max(0, -left), max(0, -top)))
    return image


def outline_crest(crest, colors, s):
    """The crest with a die-cut outline in the opponent's colours (main inside, second outside) and a glow."""
    main, second, _ = colors
    pad = round(10*s)
    canvas = Image.new('RGBA', (crest.width+2*pad, crest.height+2*pad))
    alpha = Image.new('L', canvas.size)
    alpha.paste(crest.getchannel('A'), (pad, pad))

    def grow(mask, px):
        return mask.filter(ImageFilter.GaussianBlur(px*s*.6)).point(lambda v: 255 if v > 10 else 0)
    inner, outer = grow(alpha, 3.6), grow(alpha, 6.4)
    glow = Image.new('RGBA', canvas.size, (*main, 0))
    glow.putalpha(outer.filter(ImageFilter.GaussianBlur(5*s)).point(lambda v: v*.6))
    canvas.alpha_composite(glow)
    for mask, color in ((outer, second), (inner, main)):
        solid = Image.new('RGBA', canvas.size, (*color, 0))
        solid.putalpha(mask)
        canvas.alpha_composite(solid)
    canvas.alpha_composite(crest, (pad, pad))
    return canvas
