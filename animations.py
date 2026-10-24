"""Richer CRT entrance animations for videos ("Retro" style).

Every layer gets an entrance by its role: text is typed like a terminal,
crests arrive with an RGB glitch, VS pops in, the Full Time score counts up,
tables fill row by row; the whole set can start with a CRT power-on.

The scene functions annotate their layers with prepare(); the compose
functions of each renderer hand animated frames to compose() here. Still
images (PNG, editor preview) are never affected.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

import themes

STYLES = ('Retro', 'Classica')
POWER_ON = .55

TIMELINES = {
    'matchday': {'title': .2, 'date': .6, 'home_logo': 1.25, 'away_logo': 1.55, 'vs': 2.05,
                 'home_name': 2.6, 'away_name': 2.9, 'kickoff': 3.4, 'venue': 3.75},
    'fulltime': {'title': .2, 'details': .6, 'home_logo': 1.0, 'away_logo': 1.25, 'home_name': 1.6,
                 'away_name': 1.8, 'score': 2.1, 'penalties': 3.5, 'result': 3.6,
                 'home_scorers': 4.0, 'away_scorers': 4.3},
    'convocati': {'logo': .15, 'title': .4, 'team': .8, 'match': 1.05},
    'classifica': {'logo': .15, 'title': .4, 'subtitle': .85, 'table': 1.15},
    'calendario': {'logo': .15, 'title': .4, 'subtitle': .85, 'table': 1.15},
}
ROW_STEP = .17


def _kind(layer):
    if layer.id in ('logo', 'home_logo', 'away_logo'):
        return 'glitch'
    if layer.id == 'vs':
        return 'pop'
    if layer.id == 'score':
        return 'count' if getattr(layer, 'variants', None) else 'pop'
    if layer.id == 'result':
        return 'pop'
    if layer.id == 'table':
        return 'rows' if layer.image.info.get('row_edges') else 'type'
    return 'type'


def _duration(layer, kind):
    if kind == 'type':
        h = max(1, layer.image.height)
        chars = layer.image.width/(h*.62)
        return max(.22, min(.8, chars*.035))
    if kind == 'glitch':
        return .6
    if kind == 'pop':
        return .45
    if kind == 'count':
        return len(layer.variants)*.12+.1
    if kind == 'rows':
        return len(layer.image.info['row_edges'])*ROW_STEP+.25
    return .46


def prepare(prepared, config, kind):
    """Mark layers with entrance kind, start and duration; return the scene."""
    base, layers, positions = prepared
    base.info['anim'] = config.get('animation', 'Retro') if config.get('animation') in STYLES else 'Retro'
    base.info['power_on'] = bool(config.get('power_on', True))
    base.info.setdefault('theme', '')
    timeline = TIMELINES.get(kind, {})
    last = max(timeline.values(), default=0)
    players = [l for l in layers if l.id.startswith('player_')]
    for i, layer in enumerate(layers):
        layer.anim = _kind(layer)
        if layer.id in timeline:
            layer.start = timeline[layer.id]
        elif layer.id.startswith('player_'):
            layer.start = 1.4+max(0, layer.sequence)*.13
        elif kind == 'convocati':
            layer.start = 1.6+len(players)*.13+{'legend': 0, 'meeting': .25, 'venue': .5}.get(layer.id, .7)
        else:
            last += .3
            layer.start = last
        layer.dur = _duration(layer, layer.anim)
    return prepared


def rich(prepared):
    return prepared[0].info.get('anim') == 'Retro' and all(hasattr(l, 'start') for l in prepared[1])


def _offset(prepared):
    return POWER_ON if prepared[0].info.get('power_on') and prepared[0].info.get('anim') == 'Retro' else 0


def intro_length(prepared):
    """Seconds until every element is on screen."""
    layers = prepared[1]
    if not layers or not all(hasattr(l, 'start') for l in layers):
        return None
    return _offset(prepared)+max(l.start+l.dur for l in layers)


def events(prepared):
    """(time, sound kind, index) for the soundtrack, matching compose()."""
    out = []
    offset = _offset(prepared)
    if offset:
        out.append((0.0, 'power', 0))
    for i, layer in enumerate(sorted(prepared[1], key=lambda l: l.start)):
        t = offset+layer.start
        if layer.anim == 'glitch':
            out.append((t, 'glitch', i))
        elif layer.anim == 'count':
            for k in range(len(layer.variants)):
                out.append((t+k*.12, 'tick', k))
            out.append((t+layer.dur, 'blip', 7))
        elif layer.anim == 'rows':
            for k in range(len(layer.image.info['row_edges'])):
                out.append((t+k*ROW_STEP, 'blip', k))
        else:
            out.append((t, 'blip', i))
    return out


def particles(canvas, prepared, t, animated):
    theme = prepared[0].info.get('theme')
    if theme:
        themes.draw_particles(canvas, theme, t if animated else themes.STILL_TIME)


def still_base(prepared):
    """Background with the theme particles frozen, for the drag editor."""
    base = prepared[0]
    if not base.info.get('theme'):
        return base
    image = base.copy()
    particles(image, prepared, 0, False)
    return image


# --- Entrance effects -----------------------------------------------------

def _ease(a):
    return 1-(1-a)**3


def _back(a):
    c = 1.9
    return 1+(c+1)*(a-1)**3+c*(a-1)**2


def _put(canvas, img, layer, pos, alpha=1.0, dx=0.0, dy=0.0):
    if img is None or alpha <= 0:
        return
    s = canvas.width/540
    if alpha < .999:
        img = img.copy()
        img.putalpha(img.getchannel('A').point(lambda v: round(v*alpha)))
    x = round((pos[0]+layer.offset_x+dx)*s-img.width/2)
    y = round((pos[1]+layer.offset_y+dy)*s-img.height/2)
    # Clip to the canvas: alpha_composite refuses negative destinations.
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(img.width, canvas.width-x), min(img.height, canvas.height-y)
    if right <= left or bottom <= top:
        return
    if (left, top, right, bottom) != (0, 0, img.width, img.height):
        img = img.crop((left, top, right, bottom))
    canvas.alpha_composite(img, (x+left, y+top))


def _typed(img, a):
    w, h = img.size
    char = max(2, round(h*.62))
    steps = max(1, math.ceil(w/char))
    shown = min(w, math.ceil(a*steps)*char)
    out = Image.new('RGBA', img.size)
    if shown > 0:
        out.paste(img.crop((0, 0, shown, h)), (0, 0))
    if a < 1:
        x = min(w-1, shown)
        cursor = Image.new('RGBA', (max(1, round(char*.55)), max(1, round(h*.72))), (250, 250, 255, 235))
        out.alpha_composite(cursor, (min(w-cursor.width, x), round(h*.14)))
    return out


def _tinted(img, color, alpha):
    ghost = Image.new('RGBA', img.size, (*color, 0))
    ghost.putalpha(img.getchannel('A').point(lambda v: round(v*alpha)))
    return ghost


def _glitched(img, a, seed, s):
    rng = np.random.default_rng(seed)
    if rng.random() > .3+.7*a:
        return None  # flicker: this frame the crest is off
    k = 1-a
    off = round(k*9*s)
    out = Image.new('RGBA', (img.width+2*off, img.height))
    if off:
        out.alpha_composite(_tinted(img, (255, 40, 120), .75*k+.1), (0, 0))
        out.alpha_composite(_tinted(img, (60, 230, 255), .75*k+.1), (2*off, 0))
    out.alpha_composite(img, (off, 0))
    arr = np.array(out)
    h, w = arr.shape[:2]
    for _ in range(int(2+7*k)):
        y = int(rng.integers(0, h))
        bh = int(rng.integers(max(1, h//30), max(2, h//7)))
        arr[y:y+bh] = np.roll(arr[y:y+bh], int(rng.integers(-1, 2)*k*16*s*rng.random()), axis=1)
    return Image.fromarray(arr, 'RGBA')


def _whiten(img, amount):
    if amount <= 0:
        return img
    arr = np.asarray(img).astype(np.float32)
    arr[..., :3] += (255-arr[..., :3])*amount
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')


def _scaled(img, k):
    if abs(k-1) < .01:
        return img
    size = (max(1, round(img.width*k)), max(1, round(img.height*k)))
    return img.resize(size, Image.Resampling.BILINEAR)


def _rows(img, edges, local, s):
    out = Image.new('RGBA', img.size)
    for i, (y0, y1) in enumerate(edges):
        pr = (local-i*ROW_STEP)/.22
        if pr <= 0:
            break
        pr = min(1, pr)
        band = img.crop((0, round(y0*s), img.width, round(y1*s)))
        if pr < 1:
            e = _ease(pr)
            shift = round((1-e)*40*s)
            band = _whiten(band, (1-pr)*.6)
            band = band.crop((shift, 0, band.width, band.height))
            band.putalpha(band.getchannel('A').point(lambda v: round(v*e)))
        out.alpha_composite(band, (0, round(y0*s)))
    return out


def _draw(canvas, layer, pos, local, frame_index):
    if local <= 0:
        return
    a = min(1.0, local/layer.dur)
    s = canvas.width/540
    kind = layer.anim
    if kind == 'count':
        if a < 1:
            idx = min(len(layer.variants)-1, int(local/.12))
            _put(canvas, layer.variants[idx], layer, pos)
        else:
            after = local-layer.dur
            k = 1+.22*max(0, 1-after/.3)
            _put(canvas, _whiten(_scaled(layer.image, k), max(0, .5-after*1.6)), layer, pos)
        return
    if a >= 1:
        _put(canvas, layer.image, layer, pos)
        return
    if kind == 'type':
        _put(canvas, _typed(layer.image, a), layer, pos)
    elif kind == 'glitch':
        _put(canvas, _glitched(layer.image, a, frame_index*31+len(layer.id), s), layer, pos)
    elif kind == 'pop':
        e = _back(a)
        _put(canvas, _whiten(_scaled(layer.image, 1.7-.7*e), (1-a)*.8), layer, pos, min(1, a*2.5))
    elif kind == 'rows':
        _put(canvas, _rows(layer.image, layer.image.info['row_edges'], local, s), layer, pos)
    else:
        e = _ease(a)
        _put(canvas, layer.image, layer, pos, e, 0, (1-e)*12)


def _squash(arr, sy, glow):
    h = arr.shape[0]
    nh = max(1, round(h*sy))
    img = Image.fromarray(arr.astype(np.uint8)).resize((arr.shape[1], nh), Image.Resampling.BILINEAR)
    part = np.asarray(img, np.float32)
    part = part+(255-part)*glow
    out = np.zeros_like(arr, dtype=np.float32)
    y = (h-nh)//2
    out[y:y+nh] = part
    return out


def power_on(frame, p):
    """CRT switching on: a dot, a line, then the picture opening vertically."""
    if p >= 1.6:
        return frame
    arr = np.asarray(frame, np.float32)
    h, w = arr.shape[:2]
    if p < .18:
        out = np.zeros_like(arr)
        r = max(1, round(w*.004+w*.5*(p/.18)**2))
        t = max(1, round(h*.0015))
        out[h//2-t:h//2+t, max(0, w//2-r):w//2+r] = 255
    elif p < .42:
        out = np.zeros_like(arr)
        t = max(1, round(h*.002))
        out[h//2-t:h//2+t] = 255
    elif p < 1:
        q = (p-.42)/.58
        out = _squash(arr, max(.004, _ease(q)), (1-q)*.7)
    else:
        k = (1.6-p)/.6  # fading afterglow
        out = arr+(255-arr)*.12*k
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def compose(prepared, t=999, animated=True):
    base, layers, positions = prepared
    canvas = base.copy()
    particles(canvas, prepared, t, animated)
    if not animated:
        for layer in layers:
            _put(canvas, layer.image, layer, positions[layer.id])
        return canvas.convert('RGB')
    offset = _offset(prepared)
    frame_index = int(t*24)
    for layer in layers:
        _draw(canvas, layer, positions[layer.id], t-offset-layer.start, frame_index)
    s = canvas.width/540
    # Slow scan bar, plus a slight flicker while the tube warms up.
    from render_utils import ScaledDraw
    overlay = Image.new('RGBA', canvas.size)
    y = 318+((t*.6) % 1)*354
    ScaledDraw(overlay, s).rectangle((78, y, 462, y+6), fill=(255, 255, 255, 10))
    canvas.alpha_composite(overlay)
    frame = canvas.convert('RGB')
    if offset and t < offset*1.6:
        frame = power_on(frame, t/offset)
    elif t < offset+1.2 and int(t*24) % 7 == 3:
        frame = Image.fromarray((np.asarray(frame, np.float32)*.93).astype(np.uint8))
    return frame
