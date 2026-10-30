"""Frames (cornici) and textures over the whole picture.

Both are drawn on the composed 540x960 frame, aligned to the crop of the
export format (Story, Post 4:5, Post 1:1), so a Polaroid border always sits on
the real edges of the post. They are off on the TV mockup (the TV is the frame).
Textures that move (grain, VHS, dust) change every frame in videos.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter

from render_utils import ScaledDraw

FRAMES = {'nessuna': 'Nessuna', 'polaroid': 'Polaroid', 'pellicola': 'Pellicola', 'arrotondata': 'Angoli arrotondati',
          'neon': 'Tubo al neon', 'biglietto': 'Biglietto', 'pixel': 'Pixel art',
          'rotazione': 'A rotazione (cambia ogni giornata)'}
TEXTURES = {'nessuna': 'Nessuna', 'grana': 'Grana da pellicola', 'retino': 'Retino da stampa', 'carta': 'Carta',
            'vhs': 'Nastro VHS', 'polvere': 'Polvere e graffi', 'rotazione': 'A rotazione (cambia ogni giornata)'}
FRAME_CYCLE = ('polaroid', 'pixel', 'neon', 'pellicola', 'biglietto', 'arrotondata')
TEXTURE_CYCLE = ('grana', 'carta', 'vhs', 'retino', 'polvere')
CROPS = {'Post 1:1': (0, 210, 540, 750), 'Post 4:5': (0, 142.5, 540, 817.5), 'Story 9:16': (0, 0, 540, 960)}
DARK = (12, 9, 20)


def _round(config):
    try:
        return max(1, int(config.get('season_round', 1) or 1))
    except (TypeError, ValueError):
        return 1


def resolve_frame(config):
    mode = config.get('frame_style', 'nessuna')
    if mode == 'rotazione':
        return FRAME_CYCLE[(_round(config)-1) % len(FRAME_CYCLE)]
    return mode if mode in FRAMES else 'nessuna'


def resolve_texture(config):
    mode = config.get('texture_fx', 'nessuna')
    if mode == 'rotazione':
        return TEXTURE_CYCLE[(_round(config)-1) % len(TEXTURE_CYCLE)]
    return mode if mode in TEXTURES else 'nessuna'


def _hex(value, fallback):
    try:
        out = tuple(bytes.fromhex(str(value).lstrip('#')))
        return out if len(out) == 3 else fallback
    except (ValueError, TypeError):
        return fallback


def store(info, config):
    """Remember the frame, texture, format and colours on the scene (called by animations.prepare)."""
    info['frame_style'] = resolve_frame(config)
    info['texture_fx'] = resolve_texture(config)
    info['format'] = config.get('export_format', 'Story 9:16') if config.get('export_format') in CROPS else 'Story 9:16'
    info['mockup'] = bool(config.get('mockup', False))
    info['frame_colors'] = (_hex(config.get('pink'), (242, 104, 168)), _hex(config.get('cyan'), (121, 220, 247)),
                            _hex(config.get('yellow'), (255, 201, 99)))


def active(info):
    return not info.get('mockup') and (info.get('frame_style', 'nessuna') != 'nessuna'
                                       or info.get('texture_fx', 'nessuna') != 'nessuna')


def crop_box(format, width):
    """The pixel box of the format on a full frame `width` pixels wide (same maths as crt_presets.output_image)."""
    crop = CROPS.get(format, CROPS['Story 9:16'])
    s = width/540
    top = math.floor(crop[1]*s)
    return (round(crop[0]*s), top, round(crop[2]*s), top+round((crop[3]-crop[1])*s))


# --- Frames -------------------------------------------------------------------

def _label(im, text, x, y, width, color, size, s, style='CRT Terminal', angle=0):
    from pixel_fonts import pixel_text_runs
    label = pixel_text_runs([(text, color)], style, size, width, s)
    if label is None:
        return
    if angle:
        label = label.rotate(angle, expand=True)
    im.alpha_composite(label, (round(x*s-label.width/2), round(y*s-label.height/2)))


@lru_cache(maxsize=12)
def _frame_overlay(kind, w, h, s, colors):
    """The frame as an RGBA overlay of w x h pixels (h/s layout units tall)."""
    pink, cyan, yellow = colors
    W, H = w/s, h/s
    im = Image.new('RGBA', (w, h))
    d = ScaledDraw(im, s)
    if kind == 'polaroid':
        paper = (248, 246, 239, 255)
        m, bottom = 16, 66
        d.rectangle((0, 0, W, H), fill=paper)
        d.rectangle((m, m, W-m, H-bottom), fill=(0, 0, 0, 0))
        edge = Image.new('RGBA', im.size)
        e = ScaledDraw(edge, s)
        e.rectangle((m-1, m-1, W-m+1, H-bottom+1), outline=(40, 34, 30, 120), width=1.5)
        im.alpha_composite(edge)
        _label(im, 'FLAMINGOS / CALCIO A 7', W/2, H-bottom/2, 300, (70, 64, 80), 12, s)
        for x in (60, W-60):   # a little doodle of stars in marker
            d.line((x-7, H-bottom/2, x+7, H-bottom/2), fill=(*pink, 255), width=2)
            d.line((x, H-bottom/2-7, x, H-bottom/2+7), fill=(*pink, 255), width=2)
    elif kind == 'pellicola':
        band = 30
        d.rectangle((0, 0, band, H), fill=(*DARK, 255))
        d.rectangle((W-band, 0, W, H), fill=(*DARK, 255))
        d.rectangle((0, 0, W, 8), fill=(*DARK, 255))
        d.rectangle((0, H-8, W, H), fill=(*DARK, 255))
        for y in np.arange(14, H-14, 34):
            for x in (8, W-22):
                d.rounded_rectangle((x, y, x+14, y+18), radius=3, fill=(236, 230, 214, 255))
        amber = (255, 168, 60)
        for k, y in enumerate(np.arange(60, H-40, 170)):
            _label(im, f'{7+k}A', 26, y, 40, amber, 7, s, angle=90)
            _label(im, 'FLM 400', W-26, y+85, 80, amber, 7, s, angle=-90)
    elif kind == 'arrotondata':
        r = 42
        d.rectangle((0, 0, W, H), fill=(*DARK, 255))
        d.rounded_rectangle((7, 7, W-7, H-7), radius=r, fill=(0, 0, 0, 0))
        ring = Image.new('RGBA', im.size)
        ScaledDraw(ring, s).rounded_rectangle((12, 12, W-12, H-12), radius=r-5, outline=(*cyan, 170), width=1.5)
        im.alpha_composite(ring)
    elif kind == 'neon':
        glow = Image.new('RGBA', im.size)
        g = ScaledDraw(glow, s)
        g.rounded_rectangle((14, 14, W-14, H-14), radius=26, outline=(*pink, 255), width=9)
        glow = glow.filter(ImageFilter.GaussianBlur(7*s))
        im.alpha_composite(glow)
        im.alpha_composite(glow)
        core = tuple(round(255*.6+c*.4) for c in pink)
        d.rounded_rectangle((14, 14, W-14, H-14), radius=26, outline=(*core, 255), width=3)
        d.rounded_rectangle((15.5, 15.5, W-15.5, H-15.5), radius=25, outline=(255, 250, 252, 255), width=1)
        for x, y in ((14, H/2), (W-14, H/2)):   # the tube's clips
            d.rectangle((x-5, y-10, x+5, y+10), fill=(60, 60, 70, 255))
    elif kind == 'biglietto':
        paper = (*tuple(round(c*.2+245*.8) for c in yellow), 255)
        border, notch = 16, 20
        d.rectangle((0, 0, W, H), fill=paper)
        d.rectangle((border, border, W-border, H-border), fill=(0, 0, 0, 0))
        for x in np.arange(10, W, 20):        # perforated top and bottom edges
            d.ellipse((x-4, -4, x+4, 4), fill=(*DARK, 255))
            d.ellipse((x-4, H-4, x+4, H+4), fill=(*DARK, 255))
        for y in np.arange(10, H, 20):
            d.ellipse((-4, y-4, 4, y+4), fill=(*DARK, 255))
            d.ellipse((W-4, y-4, W+4, y+4), fill=(*DARK, 255))
        for x in (0, W):                        # the two big notches
            d.ellipse((x-notch, H*.62-notch, x+notch, H*.62+notch), fill=(*DARK, 255))
        ink = (84, 40, 56)
        _label(im, 'BIGLIETTO / INGRESSO', W/2, border/2+1, 260, ink, 9, s)
        _label(im, 'N. 0007 / CALCIO A 7 / FLAMINGOS', W/2, H-border/2-1, 340, ink, 9, s)
    elif kind == 'pixel':
        cell = 8
        colors_cycle = (pink, cyan, yellow)
        for i, x in enumerate(np.arange(0, W, cell)):
            for y, j in ((0, 0), (cell, 1), (H-cell, 0), (H-2*cell, 1)):
                if j == 1 and i % 2:
                    continue
                d.rectangle((x, y, x+cell, y+cell), fill=(*colors_cycle[(i+j) % 3], 255))
        for k, y in enumerate(np.arange(0, H, cell)):
            for x, j in ((0, 0), (cell, 1), (W-cell, 0), (W-2*cell, 1)):
                if j == 1 and k % 2:
                    continue
                d.rectangle((x, y, x+cell, y+cell), fill=(*colors_cycle[(k+j+1) % 3], 255))
        d.rectangle((2*cell, 2*cell, W-2*cell, H-2*cell), outline=(*DARK, 255), width=2)
        for cx, cy in ((0, 0), (W-3*cell, 0), (0, H-3*cell), (W-3*cell, H-3*cell)):   # corner blocks
            d.rectangle((cx, cy, cx+3*cell, cy+3*cell), fill=(*DARK, 255))
            d.rectangle((cx+cell, cy+cell, cx+2*cell, cy+2*cell), fill=(250, 250, 250, 255))
    return im


# --- Textures -----------------------------------------------------------------

@lru_cache(maxsize=6)
def _grain(w, h, s, k):
    rng = np.random.default_rng(100+k)
    cell = max(1, s)
    small = rng.normal(0, 5.5, ((h+cell-1)//cell, (w+cell-1)//cell, 1)).astype(np.float32)
    return np.repeat(np.repeat(small, cell, 0), cell, 1)[:h, :w]


@lru_cache(maxsize=3)
def _halftone(w, h, s):
    step = 5*s
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (xx % step)-step/2
    cy = ((yy+(xx//step % 2)*step/2) % step)-step/2
    dist = np.sqrt(cx*cx+cy*cy)/(step/2)
    return (1-.13*np.clip(1-dist, 0, 1))[..., None].astype(np.float32)


@lru_cache(maxsize=3)
def _paper(w, h, s):
    rng = np.random.default_rng(5)
    small = rng.normal(0, 1, (max(2, h//(6*s)), max(2, w//(6*s)))).astype(np.float32)
    fibres = np.asarray(Image.fromarray(small).resize((w, h), Image.Resampling.BICUBIC), np.float32)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vignette = ((xx/w-.5)**2+(yy/h-.5)**2*.6)
    add = (fibres*5+fine*3-vignette*55)[..., None]
    return add, np.array((1.0, .975, .93), np.float32)


@lru_cache(maxsize=8)
def _dust(w, h, s, k):
    im = Image.new('RGBA', (w, h))
    d = ScaledDraw(im, s)
    rnd = random.Random(40+k)
    W, H = w/s, h/s
    for _ in range(26):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice((.8, 1, 1.4, 2))
        col = rnd.choice(((20, 16, 14, 170), (250, 248, 240, 150)))
        d.ellipse((x-r, y-r, x+r, y+r), fill=col)
    for _ in range(rnd.choice((1, 1, 2))):   # a vertical scratch
        x = rnd.uniform(40, W-40)
        y1 = rnd.uniform(0, H*.4)
        d.line((x, y1, x+rnd.uniform(-3, 3), y1+rnd.uniform(H*.3, H*.8)), fill=(245, 242, 232, 110), width=.8)
    for _ in range(3):   # a hair
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        d.line([(x+i*3, y+6*math.sin(i*.7)) for i in range(8)], fill=(18, 14, 12, 120), width=.7)
    return im


def _texture(region, kind, s, t, animated):
    w, h = region.size
    frame_no = int(t*24) if animated else 0
    if kind == 'grana':
        # Coarse grain that changes twice a second: alive, but still light for the MP4 encoder.
        arr = np.asarray(region, np.float32)+_grain(w, h, round(s), (frame_no//12) % 3)
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if kind == 'retino':
        arr = np.asarray(region, np.float32)*_halftone(w, h, round(s))
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if kind == 'carta':
        add, tint = _paper(w, h, round(s))
        arr = np.asarray(region, np.float32)*tint+add
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if kind == 'vhs':
        arr = np.array(region)
        shift = max(1, round(1.5*s))
        arr[..., 0] = np.roll(arr[..., 0], shift, axis=1)
        arr[..., 2] = np.roll(arr[..., 2], -shift, axis=1)
        rng = np.random.default_rng(frame_no)
        for _ in range(3):   # noisy lines that move every frame
            y = int(rng.integers(0, h))
            band = max(1, round(s*rng.uniform(.5, 1.5)))
            arr[y:y+band] = (arr[y:y+band]*.55+rng.integers(120, 255)*.45).astype(np.uint8)
        y = int((t*90*s) % h) if animated else h//3   # the slow rolling bar
        band = max(2, round(10*s))
        arr[y:y+band] = np.minimum(255, arr[y:y+band].astype(np.int16)+14).astype(np.uint8)
        return Image.fromarray(arr)
    if kind == 'polvere':
        dust = _dust(w, h, round(s), (frame_no//2) % 6)
        out = region.copy()
        out.paste(dust, (0, 0), dust)
        return out
    return region


def apply(image, info, t=999, animated=False):
    """Frame and texture on a composed full frame (RGB), aligned to the format crop."""
    if not active(info):
        return image
    image = image.convert('RGB') if image.mode != 'RGB' else image.copy()
    s = image.width/540
    box = crop_box(info.get('format', 'Story 9:16'), image.width)
    frame = info.get('frame_style', 'nessuna')
    texture = info.get('texture_fx', 'nessuna')
    region = image.crop(box)
    if texture != 'nessuna':
        region = _texture(region, texture, s, t, animated)
    if frame != 'nessuna' and frame in FRAMES:
        colors = tuple(tuple(c) for c in info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99))))
        overlay = _frame_overlay(frame, region.width, region.height, max(1, round(s)), colors)
        region.paste(overlay, (0, 0), overlay)
    image.paste(region, box[:2])
    return image
