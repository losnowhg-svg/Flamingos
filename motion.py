"""Video motion for the CRT graphics (3.0): entrance families, camera moves,
continuous effects and the new endings.

Everything is a pure function of the time t, so previews and exports match.
Used by animations.compose(); still images are never affected.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageFilter

from render_utils import ScaledDraw

ENTRANCES = {'misto': 'Misto (ogni elemento il suo)', 'glitch': 'Glitch', 'pixel': 'Pixel che si compongono',
             'scrivere': 'Macchina da scrivere', 'rimbalzo': 'Caduta con rimbalzo', 'tendina': 'Tendina',
             'zoom': 'Zoom', 'rotazione': 'A rotazione (cambia ogni giornata)'}
ENTRANCE_CYCLE = ('misto', 'pixel', 'rimbalzo', 'tendina', 'zoom', 'glitch', 'scrivere')
FAMILY_KIND = {'glitch': 'glitch', 'pixel': 'pixelate', 'scrivere': 'type', 'rimbalzo': 'bounce',
               'tendina': 'wipe', 'zoom': 'zoom'}
SIGNATURE = ('count', 'rows', 'slide_left', 'slide_right')   # moves that tell the story: they always stay

CAMERAS = {'fermo': 'Fissa', 'zoom': 'Zoom lento', 'oscillazione': 'Oscillazione', 'carrellata': 'Carrellata',
           'parallasse': 'Parallasse 3D', 'ritmo': 'A ritmo di musica', 'rotazione': 'A rotazione (cambia ogni giornata)'}
CAMERA_CYCLE = ('zoom', 'parallasse', 'oscillazione', 'ritmo', 'carrellata')

AMBIENT = {'fx_pulse': 'Bagliore che pulsa', 'fx_flicker': 'Sfarfallio CRT', 'fx_particles': 'Particelle',
           'fx_sweep': 'Riflesso di luce'}

ENDING_NAMES = {'nessuno': 'Nessuno', 'spegnimento': 'TV che si spegne', 'loop': 'Loop per Reel (dissolvenza al nero)',
                'pixel': 'Si sgretola in pixel', 'glitch': 'Glitch finale', 'zoom': 'Zoom nello schermo',
                'tendina': 'Tendina che si chiude'}
ENDING_LENGTH = {'spegnimento': .6, 'pixel': .8, 'glitch': .8, 'zoom': .8, 'tendina': .8}
NEW_ENDINGS = ('pixel', 'glitch', 'zoom', 'tendina')
BAR = 2.0          # four beats at 120 bpm
QUARTER = .5
SCREEN_CENTRE = (270, 495)


def beat_of(info):
    """(seconds per beat, a time on the beat): the real track's when there is one, else 120 bpm."""
    beat = (info or {}).get('beat')
    if beat and beat[0] > .2:
        return float(beat[0]), float(beat[1])
    return QUARTER, 0.0

REEL = dict(animation='Retro', intro=True, intro_style='logo', camera='parallasse', entrance='misto',
            fx_pulse=True, fx_particles=True, fx_sweep=True, fx_flicker=False, ending='loop', music=True,
            power_on=True, details=True, export_format='Story 9:16', duration=10, fps=30)


def _round(config):
    try:
        return max(1, int(config.get('season_round', 1) or 1))
    except (TypeError, ValueError):
        return 1


def entrance(config):
    mode = config.get('entrance', 'misto')
    if mode == 'rotazione':
        return ENTRANCE_CYCLE[(_round(config)-1) % len(ENTRANCE_CYCLE)]
    return mode if mode in ENTRANCES else 'misto'


def camera(config):
    mode = config.get('camera', 'fermo')
    if mode == 'rotazione':
        return CAMERA_CYCLE[(_round(config)-1) % len(CAMERA_CYCLE)]
    return mode if mode in CAMERAS else 'fermo'


def ambient(config):
    return tuple(key for key in AMBIENT if config.get(key))


def override(layer, kind_now, family):
    """The entrance a layer gets with a family chosen (signature moves and cards keep theirs)."""
    if family == 'misto' or family not in FAMILY_KIND:
        return kind_now
    if kind_now in SIGNATURE or layer.id.startswith('card_'):
        return kind_now
    return FAMILY_KIND[family]


def _smooth(p):
    p = max(0.0, min(1.0, p))
    return p*p*(3-2*p)


def ease_out(a):
    return 1-(1-a)**3


def back(a):
    c = 1.9
    return 1+(c+1)*(a-1)**3+c*(a-1)**2


def bounce(a):
    n, d = 7.5625, 2.75
    if a < 1/d:
        return n*a*a
    if a < 2/d:
        a -= 1.5/d
        return n*a*a+.75
    if a < 2.5/d:
        a -= 2.25/d
        return n*a*a+.9375
    a -= 2.625/d
    return n*a*a+.984375


# --- Entrances ------------------------------------------------------------------

def pixelated(img, a, s):
    e = ease_out(a)
    block = max(1, round((1-e)*22*s))
    if block <= 1:
        return img
    small = img.resize((max(1, img.width//block), max(1, img.height//block)), Image.Resampling.BOX)
    return small.resize(img.size, Image.Resampling.NEAREST)


def wiped(img, a, s):
    e = ease_out(a)
    shown = max(1, round(img.width*e))
    out = Image.new('RGBA', img.size)
    out.paste(img.crop((0, 0, shown, img.height)), (0, 0))
    if a < 1:
        bar = Image.new('RGBA', (max(1, round(2*s)), img.height), (255, 255, 255, 230))
        out.alpha_composite(bar, (min(img.width-bar.width, shown), 0))
    return out


def zoom_scale(a):
    return max(.06, .1+.9*back(a))


# --- Camera -----------------------------------------------------------------------

def _affine(frame, zoom, angle, dx, dy, cx, cy):
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    a, b = cos/zoom, sin/zoom
    d, e = -sin/zoom, cos/zoom
    c = cx-(a*(cx+dx)+b*(cy+dy))
    f = cy-(d*(cx+dx)+e*(cy+dy))
    return frame.transform(frame.size, Image.Transform.AFFINE, (a, b, c, d, e, f),
                           resample=Image.Resampling.BILINEAR, fillcolor=(6, 4, 12))


def camera_frame(frame, t, info):
    """Whole-frame camera moves (the parallax works on the planes instead, in parallax_base)."""
    mode = info.get('camera', 'fermo')
    if mode in ('fermo', 'parallasse') or mode not in CAMERAS:
        return frame
    s = frame.width/540
    cx, cy = SCREEN_CENTRE[0]*s, SCREEN_CENTRE[1]*s
    duration = info.get('duration') or 8
    p = _smooth(t/duration)
    zoom, angle, dx, dy = 1.0, 0.0, 0.0, 0.0
    if mode == 'zoom':
        zoom = 1+.075*p
    elif mode == 'oscillazione':
        zoom = 1.05
        angle = .8*math.sin(t*1.25)
        dx, dy = 4*math.sin(t*.9)*s, 3*math.cos(t*1.1)*s
    elif mode == 'carrellata':
        zoom = 1.1
        dy = (40-80*p)*s
        dx = 10*math.sin(t*.5)*s
    elif mode == 'ritmo':
        quarter, zero = beat_of(info)
        local = t-zero+64*quarter
        bar = int(local/(4*quarter))
        phase = (local % quarter)/quarter
        zoom = (1.07 if bar % 2 else 1.0)+.035*(1-phase)**3   # a jump cut every bar, a punch every beat
        if local % (4*quarter) < .12:
            zoom += .03*(1-(local % (4*quarter))/.12)
        drop = info.get('drop_at')
        if drop and 0 <= t-drop < .3:                          # the big one, on the drop of the music
            zoom += .06*(1-(t-drop)/.3)
    return _affine(frame, zoom, angle, dx, dy, cx, cy)


def parallax_offsets(t):
    """(back plane, layers, foreground) offsets in layout units: three depths moving apart."""
    sx, sy = math.sin(t*.7), math.cos(t*.53)
    return (-6*sx, -5*sy), (3*sx, 2.5*sy), (16*sx, 12*sy)


def parallax_base(base, t, info):
    """The background as the far plane: it slides against the text, never showing an edge."""
    s = base.width/540
    pad = round(10*s)
    padded = info.get('_parallax_pad')
    if padded is None or padded.shape[1] != base.width+2*pad:
        padded = np.pad(np.asarray(base.convert('RGB')), ((pad, pad), (pad, pad), (0, 0)), mode='reflect')
        info['_parallax_pad'] = padded
    (bx, by), _, _ = parallax_offsets(t)
    x, y = pad-round(bx*s), pad-round(by*s)
    return Image.fromarray(np.ascontiguousarray(padded[y:y+base.height, x:x+base.width]))


def _bokeh(info):
    rnd = random.Random(77)
    pink, cyan, yellow = info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99)))
    return [(rnd.uniform(0, 540), rnd.uniform(0, 960), rnd.uniform(10, 26), rnd.choice((pink, cyan, yellow, (255, 255, 255))),
             rnd.uniform(.4, 1)) for _ in range(9)]


def foreground(canvas, t, info):
    """Big soft out-of-focus lights in front, moving faster than everything else."""
    s = canvas.width/540
    _, _, (fx, fy) = parallax_offsets(t)
    d = ScaledDraw(canvas, s, 'RGBA')
    for x, y, r, col, speed in _bokeh(info):
        yy = (y-t*14*speed+fy) % 1000-20
        xx = x+fx*speed
        for k, alpha in ((1.0, 22), (.7, 26), (.4, 30)):
            d.ellipse((xx-r*k, yy-r*k, xx+r*k, yy+r*k), fill=(*col, alpha))


# --- Continuous effects -------------------------------------------------------------

def _pulse_glow(info, size, s):
    cached = info.get('_pulse_glow')
    if cached is not None and cached[0].size == size:
        return cached
    pink, cyan, _ = info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99)))
    layer = Image.new('RGBA', size)
    d = ScaledDraw(layer, s)
    d.rounded_rectangle((64, 302, 476, 688), radius=18, outline=(*pink, 255), width=12)
    d.rounded_rectangle((74, 312, 466, 678), radius=12, outline=(*cyan, 200), width=4)
    layer = layer.filter(ImageFilter.GaussianBlur(10*s))
    rgb = layer.convert('RGB')
    alpha = layer.getchannel('A').point(lambda v: min(255, round(v*1.8)))
    info['_pulse_glow'] = (rgb, alpha)
    return rgb, alpha


def ambient_effects(canvas, t, info):
    """Bagliore, particelle, riflesso: drawn on the opaque frame, before the camera."""
    fx = info.get('fx', ())
    if not fx:
        return canvas
    s = canvas.width/540
    if 'fx_pulse' in fx:
        rgb, alpha = _pulse_glow(info, canvas.size, s)
        quarter, zero = beat_of(info)
        k = .25+.75*(1-((t-zero) % quarter)/quarter)**2       # on the beat (of the real track, if any)
        canvas.paste(rgb, (0, 0), alpha.point(lambda v: round(v*k)))
    if 'fx_particles' in fx:
        d = ScaledDraw(canvas, s, 'RGBA')
        pink, cyan, yellow = info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99)))
        rnd = random.Random(5)
        for i in range(46):
            x0, y0, speed, size = rnd.uniform(0, 540), rnd.uniform(0, 960), rnd.uniform(14, 40), rnd.choice((2, 2, 3, 4))
            col = (pink, cyan, yellow, (255, 255, 255))[i % 4]
            y = (y0-t*speed) % 980-10
            x = x0+6*math.sin(t*.8+i)
            twinkle = .5+.5*math.sin(t*3+i*1.7)
            d.rectangle((x, y, x+size, y+size), fill=(*col, round(90+150*twinkle)))
    if 'fx_sweep' in fx:
        period = 3.5
        phase = (t % period)/1.1
        if phase < 1:
            x = -200+phase*940
            d = ScaledDraw(canvas, s, 'RGBA')
            d.polygon([(x, 0), (x+70, 0), (x-250, 960), (x-320, 960)], fill=(255, 255, 255, 34))
            d.polygon([(x+90, 0), (x+104, 0), (x-216, 960), (x-230, 960)], fill=(255, 255, 255, 46))
    return canvas


def flicker(frame, t):
    rng = np.random.default_rng(int(t*24))
    k = .95+.06*rng.random()
    if (t % 3.1) < .09:   # now and then a quick dip
        k *= .82
    lut = [min(255, round(v*k)) for v in range(256)]*3
    return frame.point(lut)


# --- Endings --------------------------------------------------------------------------

def ending_frame(frame, kind, p):
    """The last part of the video (p from 0 to 1) for the new endings."""
    arr = np.asarray(frame, np.float32)
    h, w = arr.shape[:2]
    s = w/540
    if kind == 'pixel':
        block = max(1, round((2+p*p*46)*s))
        small = frame.resize((max(1, w//block), max(1, h//block)), Image.Resampling.BOX)
        out = np.asarray(small.resize((w, h), Image.Resampling.NEAREST), np.float32)
        out *= 1-max(0, (p-.55)/.45)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if kind == 'glitch':
        rng = np.random.default_rng(int(p*1000))
        out = arr.copy()
        shift = round(p*26*s)
        if shift:
            out[..., 0] = np.roll(arr[..., 0], shift, axis=1)
            out[..., 2] = np.roll(arr[..., 2], -shift, axis=1)
        for _ in range(int(3+p*14)):
            y = int(rng.integers(0, h))
            band = int(rng.integers(max(1, h//80), max(2, h//18)))
            out[y:y+band] = np.roll(out[y:y+band], int(rng.integers(-w//5, w//5+1)*p), axis=1)
        if p > .7:
            out *= 1-(p-.7)/.3
            if p < .92:
                out[h//2-max(1, round(s)):h//2+max(1, round(s))] = 255
        return Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if kind == 'zoom':
        zoom = 1+2.6*p*p
        cx, cy = SCREEN_CENTRE[0]*s, SCREEN_CENTRE[1]*s
        out = np.asarray(_affine(frame, zoom, 0, 0, 0, cx, cy), np.float32)
        out = out+(255-out)*min(1, p*1.6)*.35
        out *= 1-max(0, (p-.6)/.4)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if kind == 'tendina':
        out = arr.copy()
        bands = 8
        bh = h/bands
        for i in range(bands):
            k = _smooth(p*1.4-i*.05)
            covered = round(w*k)
            y1, y2 = round(i*bh), round((i+1)*bh)
            if i % 2:
                out[y1:y2, w-covered:] = (6, 4, 12)
            else:
                out[y1:y2, :covered] = (6, 4, 12)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8))
    return frame
