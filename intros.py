"""Intro screens shown before a graphic in videos (Intro option).

Every intro lasts animations.INTRO seconds on a black screen and is a pure
function of the time, so preview, PNG and video match:

- press_start  PRESS START blinking, then PLAYER 1 READY (the original)
- cartuccia    a cartridge drops into the console, then the boot logo
- caricamento  LOADING bar with a percentage and a tip
- versus       fighting-game split screen: us against them, VS, FIGHT!
- mappa        a world map of levels: the marker hops to this round's level
- logo         our crest assembles from flying pixels, flash, FLAMINGOS (3.0)
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

PINK, CYAN, YELLOW, WHITE = (255, 92, 190), (120, 220, 255), (255, 228, 92), (246, 244, 252)
BLACK = (6, 4, 12)
TIPS = ('SUGGERIMENTO: IL TERZO TEMPO E OBBLIGATORIO', 'SUGGERIMENTO: IN 7 SI CORRE IL DOPPIO',
        'SUGGERIMENTO: RISCALDATI PRIMA DI TIRARE', 'SUGGERIMENTO: IL ROSA FA PAURA',
        'SUGGERIMENTO: CHI SEGNA PORTA LE BIRRE', 'SUGGERIMENTO: PARLATEVI IN CAMPO')


def _ease(a):
    a = max(0.0, min(1.0, a))
    return a*a*(3-2*a)


def _label(text, color, size, s):
    from animations import _label as cached
    return cached(text, color, size, s)


def _put(canvas, img, pos, alpha=1.0):
    from animations import _put as put
    put(canvas, img, None, pos, alpha)


class _Draw:
    """ImageDraw in 540x960 units on an RGB canvas (RGBA fills blend)."""

    def __init__(self, image):
        self.s = image.width/540
        self.d = ImageDraw.Draw(image, 'RGBA')

    def rect(self, x1, y1, x2, y2, fill):
        s = self.s
        self.d.rectangle((round(x1*s), round(y1*s), round(x2*s)-1, round(y2*s)-1), fill=fill)

    def poly(self, points, fill):
        self.d.polygon([(round(x*self.s), round(y*self.s)) for x, y in points], fill=fill)


def _finish(out, s):
    arr = np.array(out)
    step = max(2, 2*s)
    arr[::step] = (arr[::step]*.6).astype(np.uint8)   # scanlines
    return Image.fromarray(arr)


# --- cartuccia ---------------------------------------------------------------

def _cartuccia(out, t, info, s):
    d = _Draw(out)
    # Console top and slot.
    d.rect(110, 600, 430, 700, (34, 30, 48, 255))
    d.rect(110, 600, 430, 606, (70, 64, 92, 255))
    d.rect(180, 592, 360, 604, (10, 8, 16, 255))
    for i in range(6):
        d.rect(140+i*10, 650, 146+i*10, 680, (20, 18, 30, 255))
    d.rect(370, 640, 392, 662, (*PINK, 255))
    # Cartridge: falls into the slot by 0.7 s, little bounce.
    fall = _ease(min(1, t/.62))
    y = -140+(600-150+140)*fall
    if .62 < t < .8:
        y += -6*math.sin((t-.62)/.18*math.pi)
    body, edge = (150, 148, 160, 255), (110, 108, 122, 255)
    d.rect(195, y, 345, y+150, body)
    d.poly([(330, y), (345, y), (345, y+15)], (6, 4, 12, 255))
    for i in range(5):
        d.rect(205, y+8+i*6, 330, y+10+i*6, edge)
    d.rect(210, y+45, 330, y+130, (24, 18, 40, 255))
    d.rect(214, y+49, 326, y+126, (*PINK, 255))
    _put(out, _label('FLAMINGOS', BLACK, 12, s), (270, y+76))
    _put(out, _label('CALCIO A 7', BLACK, 8, s), (270, y+100))
    if .7 <= t < .78:   # click: white flash
        d.rect(0, 0, 540, 960, (255, 255, 255, 120))
    if t >= .8:
        # Boot logo drops from above, then a blinking LOADING.
        k = _ease((t-.8)/.45)
        _put(out, _label('FLAMINGOS STUDIO', CYAN, 20, s), (270, 250+120*k))
        if t > 1.25:
            _put(out, _label('(C) 2026 SQUADRA ROSA', WHITE, 8, s), (270, 400))
            if (t % .3) < .18:
                _put(out, _label('LOADING...', YELLOW, 11, s), (270, 424))


# --- caricamento -------------------------------------------------------------

def _caricamento(out, t, info, s):
    d = _Draw(out)
    _put(out, _label('LOADING', CYAN, 26, s), (270, 400))
    p = min(1.0, max(0.0, (t-.1)/1.2))
    segments = 20
    filled = int(p*segments)
    d.rect(118, 452, 422, 492, (*WHITE, 255))
    d.rect(122, 456, 418, 488, (*BLACK, 255))
    for i in range(filled):
        color = PINK if i < segments-1 or p < 1 else YELLOW
        d.rect(126+i*14.5, 460, 126+i*14.5+11.5, 484, (*color, 255))
    percent = 100 if p >= 1 else int(p*100)
    _put(out, _label(f'{percent}%', YELLOW if p >= 1 else WHITE, 14, s), (270, 516))
    tip = TIPS[(int(info.get('level', 1))-1) % len(TIPS)]
    _put(out, _label(tip, (170, 160, 200), 8, s), (270, 560))
    if p >= 1 and (t % .24) < .16:
        _put(out, _label('COMPLETE!', YELLOW, 18, s), (270, 600))


# --- versus ------------------------------------------------------------------

def _versus(out, t, info, s):
    d = _Draw(out)
    ours, other = info.get('intro_names') or ('FLAMINGOS', 'AVVERSARI')
    k = _ease(t/.45)
    # Two diagonal halves slide in from the sides.
    left, right = -540*(1-k), 540*(1-k)
    d.poly([(left, 300), (left+330, 300), (left+210, 660), (left, 660)], (*PINK, 230))
    d.poly([(right+330, 300), (right+540, 300), (right+540, 660), (right+210, 660)], (*CYAN, 230))
    for y in range(300, 660, 6):   # speed lines
        if (y//6+int(t*24)) % 5 == 0:
            d.rect(0, y, 540, y+1, (255, 255, 255, 40))
    if t > .3:
        a = _ease((t-.3)/.25)
        _put(out, _label('P1', WHITE, 10, s), (110-40*(1-a), 340))
        _put(out, _label(str(ours)[:14], WHITE, 18, s), (150-120*(1-a), 380), a)
        _put(out, _label('P2', BLACK, 10, s), (430+40*(1-a), 600))
        _put(out, _label(str(other)[:14], BLACK, 18, s), (390+120*(1-a), 620), a)
    if t > .62:
        a = min(1.0, (t-.62)/.12)
        size = 72-28*a
        _put(out, _label('VS', YELLOW, round(size), s), (270, 480))
        if t < .72:
            d.rect(0, 0, 540, 960, (255, 255, 255, 150))
    if t > 1.05:
        word = f"ROUND {int(info.get('level', 1))}" if t < 1.3 else 'FIGHT!'
        if (t % .2) < .15 or t >= 1.3:
            _put(out, _label(word, YELLOW if t >= 1.3 else WHITE, 22 if t >= 1.3 else 14, s), (270, 720))


# --- mappa -------------------------------------------------------------------

def _mappa(out, t, info, s):
    d = _Draw(out)
    level = max(1, int(info.get('level', 1)))
    _put(out, _label('WORLD MAP', CYAN, 16, s), (270, 330))
    _put(out, _label('STAGIONE FLAMINGOS', (150, 140, 180), 8, s), (270, 354))
    first = max(1, level-3)
    nodes = []
    for i in range(6):
        n = first+i
        x = 110+i*64
        y = 520+(-60 if i % 2 else 40)
        nodes.append((n, x, y))
    for (_, x1, y1), (_, x2, y2) in zip(nodes, nodes[1:]):   # dotted path
        for k in range(1, 8):
            px, py = x1+(x2-x1)*k/8, y1+(y2-y1)*k/8
            d.rect(px-2, py-2, px+2, py+2, (90, 80, 120, 255))
    for n, x, y in nodes:
        done = n < level
        color = PINK if done else (YELLOW if n == level else (70, 62, 96))
        d.rect(x-18, y-18, x+18, y+18, (*color, 255))
        d.rect(x-13, y-13, x+13, y+13, (*BLACK, 255))
        _put(out, _label(str(n), color, 12, s), (x, y))
        if done:
            _put(out, _label('OK', PINK, 6, s), (x, y+26))
    # The marker hops from the previous level to this one.
    current = [(x, y) for n, x, y in nodes if n == level][0]
    previous = [(x, y) for n, x, y in nodes if n == level-1]
    start = previous[0] if previous else (current[0]-64, current[1])
    a = _ease((t-.3)/.7)
    mx = start[0]+(current[0]-start[0])*a
    my = start[1]+(current[1]-start[1])*a-38-30*math.sin(min(1.0, max(0.0, (t-.3)/.7))*math.pi)
    d.poly([(mx-9, my-8), (mx+9, my-8), (mx, my+6)], (*PINK, 255))
    d.rect(mx-4, my-18, mx+4, my-8, (*PINK, 255))
    if t > 1.05:
        _put(out, _label(f'LEVEL {level}', YELLOW, 18, s), (270, 650))
        if (t % .24) < .16:
            _put(out, _label('START!', WHITE, 12, s), (270, 684))


def _press_start(out, t, info, s):
    if t < 1.0:
        if (t % .5) < .3:
            _put(out, _label('PRESS START', PINK, 22, s), (270, 480))
        _put(out, _label('FLAMINGOS / CALCIO A 7', CYAN, 9, s), (270, 520))
    else:
        _put(out, _label('PLAYER 1', CYAN, 14, s), (270, 462))
        _put(out, _label('READY', YELLOW, 26, s), (270, 494))


def _crest(info, s):
    crest = info.get('crest')
    if crest is None:   # no crest in the scene: the team's own logo
        from pathlib import Path
        from renderer import clean_logo
        data = (Path(__file__).resolve().parent/'assets'/'flamingos_logo.jpg').read_bytes()
        crest = clean_logo(data, 200, True, s)
    return crest


def _logo_parts(info, s):
    """The crest at intro size and one particle per 6-unit cell of it (cached on the scene)."""
    cached = info.get('_logo_parts')
    if cached and cached[0] == s:
        return cached[1]
    crest = _crest(info, s)
    k = 210*s/max(crest.size)
    img = crest.resize((max(1, round(crest.width*k)), max(1, round(crest.height*k))), Image.Resampling.LANCZOS)
    cell = 6
    small = np.asarray(img.resize((max(1, img.width//(cell*s)), max(1, img.height//(cell*s))), Image.Resampling.BOX))
    h, w = small.shape[:2]
    x0, y0 = 270-w*cell/2, 440-h*cell/2
    rnd = random.Random(7)
    parts = []
    for j in range(h):
        for i in range(w):
            r, g, b, a = (int(v) for v in small[j, i])
            if a < 110:
                continue
            ang = rnd.uniform(0, math.tau)
            dist = rnd.uniform(330, 560)
            parts.append((270+math.cos(ang)*dist, 440+math.sin(ang)*dist*1.3, x0+i*cell, y0+j*cell, (r, g, b),
                          rnd.uniform(0, .3)))
    result = (img, parts)
    info['_logo_parts'] = (s, result)
    return result


def _logo(out, t, info, s):
    img, parts = _logo_parts(info, s)
    d = _Draw(out)
    for k in range(6):   # a soft glow that grows behind the crest
        r = (60+k*34)*min(1, .3+t)
        d.d.ellipse([round(v*d.s) for v in (270-r, 440-r, 270+r, 440+r)], fill=(*PINK, 7))
    if t < 1.05:
        for sx, sy, tx, ty, col, delay in parts:
            a = max(0.0, min(1.0, (t-delay)/.62))
            if a <= 0:
                continue
            e = 1-(1-a)**3
            vx, vy = sx-tx, sy-ty
            rot = (1-e)*1.4                      # they spiral in
            cr, sr = math.cos(rot), math.sin(rot)
            px, py = tx+(vx*cr-vy*sr)*(1-e), ty+(vx*sr+vy*cr)*(1-e)
            size = 6*(.45+.55*e)
            d.rect(px, py, px+size, py+size, (*col, round(255*min(1, a*3))))
    if t >= .95:
        _put(out, img, (270, 440), min(1, (t-.95)/.1))
    if .95 <= t < 1.3:
        k = (1-(t-.95)/.35)*.85
        arr = np.asarray(out, np.float32)
        out.paste(Image.fromarray((arr+(255-arr)*k).astype(np.uint8)))
    if t >= 1.1:
        word = 'FLAMINGOS'
        shown = word[:max(1, math.ceil(len(word)*min(1, (t-1.1)/.25)))]
        _put(out, _label(shown, PINK, 30, s), (270-(len(word)-len(shown))*9, 600))
    if t >= 1.35:
        _put(out, _label('CALCIO A 7', CYAN, 12, s), (270, 636))


DRAW = {'press_start': _press_start, 'cartuccia': _cartuccia, 'caricamento': _caricamento,
        'versus': _versus, 'mappa': _mappa, 'logo': _logo}


def frame(base, t, info):
    out = Image.new('RGB', base.size, BLACK)
    s = max(1, round(base.width/540))
    DRAW.get(info.get('intro_style', 'press_start'), _press_start)(out, t, info, s)
    return _finish(out, s)


def sound_events(style, level=1):
    """(time, sound kind, index) for the intro."""
    if style == 'cartuccia':
        return [(0.0, 'whoosh', 0), (.68, 'impact', 0), (.8, 'climb', 0), (1.25, 'ready', 0)]
    if style == 'caricamento':
        return [(.1+k*.12, 'tick', k) for k in range(10)]+[(1.3, 'ready', 0)]
    if style == 'versus':
        return [(0.0, 'whoosh', 0), (.3, 'whoosh', 1), (.62, 'impact', 1), (1.05, 'start', 0), (1.3, 'ready', 0)]
    if style == 'mappa':
        return [(.3, 'blip', 0), (.65, 'blip', 2), (1.0, 'ding', 2), (1.3, 'start', 1)]
    if style == 'logo':
        return [(0.0, 'whoosh', 0), (.4, 'whoosh', 1), (.95, 'impact', 1), (1.0, 'shine', 0), (1.15, 'start', 2)]
    return [(k*.5, 'start', k) for k in range(3)]+[(1.0, 'ready', 0)]
