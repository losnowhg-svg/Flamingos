"""Atmospheres and rotating details for the CRT presets.

Atmosphere: the same world by day, at sunset, at night or under club neon. It
grades only the art around the screen (applied in crt_presets._background()
before the veil, scanlines and text panels), so readability never changes.

Details: stickers, stars, confetti, grids or edge lettering drawn outside the
screen. Their positions follow the round, so they change every week.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from render_utils import ScaledDraw

ATMOSPHERES = {'standard': 'Come disegnato', 'giorno': 'Giorno', 'tramonto': 'Tramonto', 'notte': 'Notte',
               'neon': 'Luci neon', 'rotazione': 'A rotazione (cambia ogni giornata)'}
DETAILS = {'nessuno': 'Nessuno', 'stelle': 'Stelle', 'coriandoli': 'Coriandoli', 'griglia': 'Griglia',
           'adesivi': 'Adesivi', 'scritte': 'Scritte sui bordi', 'rotazione': 'A rotazione (cambia ogni giornata)'}
KEEP_OUT = (56, 288, 484, 702)      # the screen and its bezel: details never go there
SCREEN = (78, 316, 462, 674)
_CYCLE_ATMOSPHERE = ('standard', 'tramonto', 'notte', 'giorno', 'neon')
_CYCLE_DETAILS = ('stelle', 'adesivi', 'coriandoli', 'scritte', 'griglia')


def _round(config):
    try:
        return max(1, int(config.get('season_round', 1) or 1))
    except (TypeError, ValueError):
        return 1


def seed(config):
    return _round(config)


def resolve_atmosphere(config):
    mode = config.get('atmosphere', 'standard')
    if mode == 'rotazione':
        return _CYCLE_ATMOSPHERE[(_round(config)-1) % len(_CYCLE_ATMOSPHERE)]
    return mode if mode in ATMOSPHERES else 'standard'


def resolve_details(config):
    mode = config.get('decor', 'nessuno')
    if mode == 'rotazione':
        return _CYCLE_DETAILS[(_round(config)-1) % len(_CYCLE_DETAILS)]
    return mode if mode in DETAILS else 'nessuno'


# --- Atmospheres -------------------------------------------------------------

def _glow(size, s, shapes, blur):
    layer = Image.new('RGBA', size)
    d = ScaledDraw(layer, s)
    for kind, box, color in shapes:
        getattr(d, kind)(box, fill=color)
    return np.asarray(layer.filter(ImageFilter.GaussianBlur(blur*s)), np.float32)


def _ramp(lum, stops):
    """Map 0-1 light values (h, w, 1) to colours along (position, rgb) stops."""
    out = np.zeros(lum.shape[:2]+(3,), np.float32)
    for (p1, c1), (p2, c2) in zip(stops, stops[1:]):
        k = np.clip((lum-p1)/(p2-p1), 0, 1)
        inside = (lum >= p1) & (lum <= p2)
        out = np.where(inside, np.array(c1, np.float32)+(np.array(c2, np.float32)-np.array(c1, np.float32))*k, out)
    return out


def grade(im, mode, s):
    """The world around the screen in another light (RGBA in, RGBA out)."""
    if mode not in ('giorno', 'tramonto', 'notte', 'neon'):
        return im
    arr = np.asarray(im).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3:]
    h, w = rgb.shape[:2]
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    size = im.size
    if mode == 'giorno':
        # Brighter midtones, more colour, a sky tint at the top and the sun from the top right.
        a = (rgb/255)**.8
        gray = a.mean(axis=2, keepdims=True)
        rgb = (gray+(a-gray)*1.25)*255
        sky = np.clip(1-y/.45, 0, 1)*.32
        rgb = rgb*(1-sky)+np.array((140, 206, 255), np.float32)*sky
        g = _glow(size, s, [('ellipse', (360, -180, 760, 180), (255, 246, 210, 240)),
                           ('polygon', [(540, 0), (470, 0), (0, 700), (0, 820)], (255, 250, 220, 70))], 40)
        rgb = rgb+(255-rgb)*(g[..., 3:]/255)*.6
    elif mode == 'tramonto':
        # Gradient map on the light: violet shadows, magenta midtones, golden highlights.
        lum = (rgb @ np.array((.299, .587, .114), np.float32))[..., None]/255
        toned = _ramp(lum, ((0, (44, 18, 76)), (.42, (196, 58, 122)), (.72, (255, 138, 78)), (1, (255, 232, 170))))
        rgb = rgb*.4+toned*.6
        g = _glow(size, s, [('ellipse', (40, 760, 500, 1080), (255, 170, 90, 220))], 70)
        rgb = rgb+(np.array((255, 196, 130), np.float32)-rgb)*(g[..., 3:]/255)*.4
    elif mode == 'notte':
        rgb = rgb*np.array((.42, .48, .72), np.float32)+np.array((4, 6, 22), np.float32)
        rnd = random.Random(7)
        shapes = []
        for _ in range(16):   # bokeh lights in the dark
            x, yy, r = rnd.randrange(0, 540), rnd.choice((rnd.randrange(20, 260), rnd.randrange(720, 940))), rnd.randrange(10, 26)
            col = rnd.choice(((255, 92, 190, 150), (90, 220, 255, 140), (255, 214, 120, 130)))
            shapes.append(('ellipse', (x-r, yy-r, x+r, yy+r), col))
        g = _glow(size, s, shapes, 6)
        rgb = rgb+g[..., :3]*(g[..., 3:]/255)*.9
        stars = np.random.default_rng(3).random((h, w)) > .9993
        stars[int(h*.3):] = False
        rgb[stars] = 245
    elif mode == 'neon':
        rgb = rgb*.6
        g = _glow(size, s, [('rectangle', (-120, 0, 120, 960), (255, 40, 170, 190)),
                           ('rectangle', (420, 0, 660, 960), (40, 220, 255, 170)),
                           ('rectangle', (0, -80, 540, 60), (180, 60, 255, 150))], 70)
        rgb = rgb+g[..., :3]*(g[..., 3:]/255)*.85
        lines = (np.arange(h) % max(2, 6*s) == 0)[:, None]
        rgb = np.where(lines[..., None], rgb*1.12, rgb)
    x1, y1, x2, y2 = (round(v*s) for v in SCREEN)
    rgb[y1:y2, x1:x2] = arr[y1:y2, x1:x2, :3]      # the screen itself never changes
    out = np.concatenate([rgb.clip(0, 255), alpha], axis=2).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


# --- Details -----------------------------------------------------------------

def _free_point(rnd, margin=10, zone=None):
    """A random point outside the screen area (and inside an optional zone)."""
    x1, y1, x2, y2 = KEEP_OUT
    for _ in range(200):
        x, y = rnd.uniform(margin, 540-margin), rnd.uniform(margin, 960-margin)
        if zone and not (zone[0] <= x <= zone[2] and zone[1] <= y <= zone[3]):
            continue
        if not (x1-margin < x < x2+margin and y1-margin < y < y2+margin):
            return x, y
    return 30, 30


STICKERS = {
    'cuore': ('.XX.XX.', 'XXXXXXX', 'XXXXXXX', '.XXXXX.', '..XXX..', '...X...'),
    'stella': ('...X...', '..XXX..', 'XXXXXXX', '.XXXXX.', '.XX.XX.', 'X.....X'),
    'fulmine': ('...XXX', '..XXX.', '.XXXX.', 'XXXXX.', '..XX..', '.XX...', 'XX....'),
    'pallone': ('.XXXX.', 'XX..XX', 'X.XX.X', 'X.XX.X', 'XX..XX', '.XXXX.'),
    'corona': ('X..X..X', 'XX.X.XX', 'XXXXXXX', 'XXXXXXX', '.XXXXX.'),
    'sette': ('XXXXXX', '....XX', '...XX.', '..XX..', '..XX..', '..XX..'),
}


def _sticker(name, color, cell):
    rows = STICKERS[name]
    w, h = len(rows[0]), len(rows)
    pad = 2
    im = Image.new('RGBA', ((w+2*pad)*cell, (h+2*pad)*cell))
    d = ImageDraw.Draw(im)
    mask = np.zeros((h+2*pad, w+2*pad), bool)
    for j, row in enumerate(rows):
        for i, c in enumerate(row):
            if c == 'X':
                mask[j+pad, i+pad] = True
    grown = mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grown |= np.roll(np.roll(mask, dy, 0), dx, 1)
    for j, i in zip(*np.nonzero(grown)):            # white die-cut border
        d.rectangle((i*cell, j*cell, (i+1)*cell-1, (j+1)*cell-1), fill=(250, 250, 250, 255))
    for j, i in zip(*np.nonzero(mask)):
        d.rectangle((i*cell, j*cell, (i+1)*cell-1, (j+1)*cell-1), fill=(*color, 255))
    return im


def draw_details(image, mode, colors, s, seed):
    """Draw the chosen details on a background (RGBA, in place)."""
    if mode not in ('stelle', 'coriandoli', 'griglia', 'adesivi', 'scritte'):
        return image
    pink, cyan, yellow, white = colors
    rnd = random.Random(seed*7919+len(mode))
    layer = Image.new('RGBA', image.size)
    d = ScaledDraw(layer, s)
    if mode == 'stelle':
        for _ in range(22):
            x, y = _free_point(rnd, 14)
            r = rnd.choice((5, 6, 8, 10, 12))
            col = (*rnd.choice((white, yellow, cyan, white, pink)), 255)
            d.polygon([(x, y-r), (x+r*.22, y-r*.22), (x+r, y), (x+r*.22, y+r*.22), (x, y+r), (x-r*.22, y+r*.22),
                       (x-r, y), (x-r*.22, y-r*.22)], fill=col)
        for _ in range(50):
            x, y = _free_point(rnd, 4)
            d.rectangle((x, y, x+1.5, y+1.5), fill=(*white, rnd.randrange(120, 230)))
    elif mode == 'coriandoli':
        for _ in range(90):
            x, y = _free_point(rnd, 6)
            w, h = rnd.uniform(3, 7), rnd.uniform(6, 13)
            a = rnd.uniform(0, math.pi)
            cx, cy = math.cos(a), math.sin(a)
            pts = [(x+cx*w-cy*h, y+cy*w+cx*h), (x-cx*w-cy*h, y-cy*w+cx*h), (x-cx*w+cy*h, y-cy*w-cx*h),
                   (x+cx*w+cy*h, y+cy*w-cx*h)]
            d.polygon([(px/2+x/2, py/2+y/2) for px, py in pts], fill=(*rnd.choice((pink, cyan, yellow, white)), 235))
        for _ in range(6):   # streamers
            x, y = _free_point(rnd, 30)
            col = (*rnd.choice((pink, cyan, yellow)), 220)
            pts = [(x+k*6, y+math.sin(k*.9)*7) for k in range(9)]
            d.line(pts, fill=col, width=2.2)
    elif mode == 'griglia':
        col = (*cyan, 120)
        for top, bottom, flip in ((0, KEEP_OUT[1]-6, True), (KEEP_OUT[3]+6, 960, False)):
            horizon = bottom if flip else top
            for i in range(1, 9):
                k = (i/8)**1.7
                yy = horizon-k*(bottom-top) if flip else horizon+k*(bottom-top)
                d.line((0, yy, 540, yy), fill=col, width=1)
            for xx in range(-600, 1141, 60):
                far = (bottom if flip else top)
                near = (top if flip else bottom)
                d.line((270+(xx-270)*.25, far, xx, near), fill=col, width=1)
        for x in (18, 522):   # side rails
            d.line((x, KEEP_OUT[1]-6, x, KEEP_OUT[3]+6), fill=(*pink, 130), width=2)
    elif mode == 'adesivi':
        names = list(STICKERS)
        rnd.shuffle(names)
        post = [(30, 250), (510, 262), (26, 600), (514, 640), (96, 728), (444, 736)]     # visible in every format
        story = [(84, 120), (456, 136), (130, 860), (410, 880), (270, 60), (270, 900)]
        rnd.shuffle(post)
        rnd.shuffle(story)
        for name, (x, y) in zip(names, post[:3]+story[:3]):
            st = _sticker(name, rnd.choice((pink, cyan, yellow)), max(1, round(5*s)))
            st = st.rotate(rnd.uniform(-18, 18), expand=True, resample=Image.Resampling.NEAREST)
            shadow = Image.new('RGBA', st.size, (0, 0, 0, 0))
            shadow.putalpha(st.getchannel('A').point(lambda v: v*.45))
            px, py = round(x*s-st.width/2), round(y*s-st.height/2)
            layer.alpha_composite(shadow, (max(0, px+round(3*s)), max(0, py+round(3*s))))
            layer.alpha_composite(st, (max(0, px), max(0, py)))
    elif mode == 'scritte':
        # A marquee around the four edges of the frame.
        from pixel_fonts import pixel_text_runs
        phrase = 'FLAMINGOS * CALCIO A 7 * CSI BRESCIA * '
        strip = pixel_text_runs([(phrase*8, white)], 'CRT Terminal', 11, 0, s)
        if strip is not None:
            strip.putalpha(strip.getchannel('A').point(lambda v: v*.85))
            off = rnd.randrange(0, 240)*s
            band = Image.new('RGBA', (strip.width, strip.height+round(8*s)), (*pink, 200))
            band.alpha_composite(strip, (0, round(4*s)))
            for angle, pos in ((0, 'top'), (180, 'bottom'), (90, 'left'), (-90, 'right')):
                piece = band.rotate(angle, expand=True)
                if pos in ('top', 'bottom'):
                    piece = piece.crop((off, 0, off+540*s, piece.height))
                    layer.alpha_composite(piece, (0, 0 if pos == 'top' else 960*s-piece.height))
                else:
                    piece = piece.crop((0, off, piece.width, off+960*s))
                    layer.alpha_composite(piece, (0 if pos == 'left' else 540*s-piece.width, 0))
    image.alpha_composite(layer)
    return image
