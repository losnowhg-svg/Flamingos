"""Eight more retro worlds for the CRT presets (24-31), added in 3.0.

Same contract as preset_worlds.py: each builder draws the full 540x960 frame at
scale s around the shared screen (77-463 x 315-673); crt_presets adds the veil,
scanlines and text panels afterwards. Everything is drawn in code, no images,
no brands.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image

from preset_worlds import _cp, _layer, _noise, _screen
from render_utils import ScaledDraw


def _pix(d, x, y, rows, colors, px=4, flip=False):
    """Pixel sprite from strings; each character maps to a colour (missing = transparent)."""
    for j, row in enumerate(rows):
        row = row[::-1] if flip else row
        for i, c in enumerate(row):
            if c in colors:
                d.rectangle((x+i*px, y+j*px, x+(i+1)*px-.01, y+(j+1)*px-.01), fill=(*colors[c], 255))


def _outlined(im, text, x, y, width, fill, outline, size, s, style='CRT Scoreboard', shadow=None, depth=4):
    """Big lettering with a thick outline and an optional drop shadow."""
    cp = _cp()
    if shadow:
        for k in range(1, depth+1):
            cp._label(im, text, x+k, y+k, width, shadow, size, s, style)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        cp._label(im, text, x+dx, y+dy, width, outline, size, s, style)
    cp._label(im, text, x, y, width, fill, size, s, style)


def _ball(d, x, y, r=14):
    d.ellipse((x-r, y-r, x+r, y+r), fill=(250, 250, 250, 255), outline=(20, 20, 24, 255), width=max(1, r/7))
    p = r*.42
    d.polygon([(x+p*math.cos(a), y+p*math.sin(a)) for a in [math.radians(-90+72*k) for k in range(5)]],
              fill=(20, 20, 24, 255))
    for k in range(5):
        a = math.radians(-90+72*k)
        d.line((x+p*math.cos(a), y+p*math.sin(a), x+r*.95*math.cos(a), y+r*.95*math.sin(a)),
               fill=(20, 20, 24, 255), width=max(1, r/9))


# --- 24 Acquario ---------------------------------------------------------------------

FISH = ('...XXXX..XX',
        '.XXXXXXXXXX',
        'XoXXsXXXXX.',
        'XXXXsXXXXXX',
        '.XXXXXXXXXX',
        '...XXXX..XX')


def _weed(d, x, base, h, color, phase=0):
    for k in range(int(h/8)):
        off = 6*math.sin(k*.55+phase)
        d.rectangle((x+off, base-k*8-8, x+off+9, base-k*8), fill=(*color, 255))
        if k % 3 == 1:
            d.rectangle((x+off+9, base-k*8-6, x+off+15, base-k*8-2), fill=(*color, 255))


def bg_acquario(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (84, 206, 222), (12, 62, 104), (26, 128, 166))
    # Light rays from the surface and a few ripples.
    _layer(im, s, lambda q: [q.polygon([(x-14, 0), (x+30, 0), (x+150, 960), (x+60, 960)], fill=(255, 255, 255, 34))
                             for x in (-40, 120, 300, 430)], 8)
    _layer(im, s, lambda q: [q.line([(x+k*6, y+3*math.sin(k*.9+y)) for k in range(8)], fill=(220, 252, 255, 110), width=1.4)
                             for y in range(14, 90, 16) for x in range(-20, 560, 70)])
    d = ScaledDraw(im, s)
    rnd = random.Random(24)
    for _ in range(46):   # bubbles along the sides and at the top
        x = rnd.choice((rnd.uniform(8, 60), rnd.uniform(480, 532), rnd.uniform(70, 470)))
        y = rnd.uniform(110, 700) if x < 70 or x > 470 else rnd.uniform(110, 270)
        r = rnd.choice((2.5, 3.5, 5, 7))
        d.ellipse((x-r, y-r, x+r, y+r), outline=(205, 244, 250, 255), width=1.2)
        d.rectangle((x-r*.45, y-r*.55, x-r*.1, y-r*.2), fill=(250, 255, 255, 255))
    # Sand, rocks, seaweed and something that fell in.
    d.polygon([(0, 960), *[(x, 872+8*math.sin(x/38)) for x in range(0, 541, 20)], (540, 960)], fill=(228, 198, 136, 255))
    for _ in range(140):
        x, y = rnd.uniform(0, 540), rnd.uniform(890, 958)
        d.rectangle((x, y, x+2, y+2), fill=(*rnd.choice(((196, 164, 104), (246, 222, 170))), 255))
    for x, y, w in ((-10, 880, 90), (470, 872, 90), (190, 900, 50)):
        d.ellipse((x, y, x+w, y+w*.55), fill=(92, 104, 118, 255))
        d.ellipse((x+w*.18, y+w*.06, x+w*.6, y+w*.26), fill=(126, 140, 154, 255))
    for x, h, ph, col in ((12, 300, 0, (40, 170, 96)), (36, 210, 2, (60, 200, 110)), (498, 280, 1, (40, 170, 96)),
                          (516, 190, 3, (60, 200, 110)), (330, 120, 1.5, (40, 170, 96)), (150, 90, 4, (60, 200, 110))):
        _weed(d, x, 900, h, col, ph)
    # The little chest and the lost ball.
    d.rectangle((92, 884, 148, 920), fill=(126, 74, 38, 255))
    d.rectangle((88, 872, 152, 890), fill=(150, 92, 48, 255))
    d.rectangle((88, 888, 152, 892), fill=(*yellow, 255))
    d.rectangle((116, 884, 124, 900), fill=(*yellow, 255))
    _ball(d, 420, 902, 15)
    # Fish: a school at the top, a couple at the bottom.
    for i, (x, y, col, flip, px) in enumerate(((60, 120, pink, False, 4), (120, 150, pink, False, 3), (40, 180, pink, False, 3),
                                               (330, 196, yellow, True, 5), (430, 120, cyan, True, 3),
                                               (90, 760, cyan, True, 4), (380, 800, pink, False, 4), (250, 740, yellow, False, 3))):
        body = tuple(min(255, round(c)) for c in col)
        _pix(d, x, y, FISH, {'X': body, 's': tuple(round(c*.7) for c in body), 'o': (20, 24, 40)}, px, flip)
    # A brass porthole around the screen.
    cp._box(d, (52, 290, 488, 698), (30, 42, 56, 255), (200, 160, 74, 255), 5, 14)
    for k in range(12):
        for x, y in ((64+k*37.5, 298), (64+k*37.5, 690)):
            d.ellipse((x-3, y-3, x+3, y+3), fill=(120, 88, 34, 255))
    for k in range(10):
        for x, y in ((60, 330+k*37), (480, 330+k*37)):
            d.ellipse((x-3, y-3, x+3, y+3), fill=(120, 88, 34, 255))
    _screen(d, (4, 26, 40))
    cp._box(d, (172, 258, 368, 290), (200, 160, 74, 255), (110, 78, 28, 255), 2, 4)
    cp._label(im, 'PROFONDITA 7 M', 270, 274, 180, (60, 36, 10), 10, s)
    return im


# --- 25 Spogliatoio ------------------------------------------------------------------

def _locker(d, im, s, x1, y1, x2, y2, body, number=None):
    cp = _cp()
    dark = tuple(round(c*.6) for c in body)
    light = tuple(min(255, round(c*1.18)+12) for c in body)
    d.rectangle((x1, y1, x2, y2), fill=(*dark, 255))
    d.rectangle((x1+3, y1+3, x2-3, y2-3), fill=(*body, 255))
    d.rectangle((x1+3, y1+3, x1+7, y2-3), fill=(*light, 255))
    for k in range(4):
        y = y1+22+k*9
        d.rectangle((x1+20, y, x2-20, y+4), fill=(*dark, 255))
    if number is not None:
        d.rectangle(((x1+x2)/2-14, y1+68, (x1+x2)/2+14, y1+90), fill=(246, 244, 236, 255))
        cp._label(im, str(number), (x1+x2)/2, y1+79, 24, (30, 30, 34), 12, s, 'CRT Scoreboard')
    d.rectangle((x2-18, y1+110, x2-12, y1+150), fill=(222, 222, 228, 255))


def bg_spogliatoio(pink, cyan, yellow, s):
    cp = _cp()
    im = Image.new('RGBA', (540*s, 960*s), (238, 238, 232, 255))
    d = ScaledDraw(im, s)
    for y in range(0, 40, 14):   # wall tiles above the lockers
        d.line((0, y, 540, y), fill=(200, 202, 200, 255), width=1)
    for x in range(0, 540, 14):
        d.line((x, 0, x, 30), fill=(200, 202, 200, 255), width=1)
    orange = (236, 124, 46)
    for i, x in enumerate(range(0, 540, 90)):
        number = (1, 3, 5, 7, 9, 10)[i]
        _locker(d, im, s, x, 30, x+90, 300, pink if number == 7 else orange, number)
        _locker(d, im, s, x, 300, x+90, 580, orange)
        _locker(d, im, s, x, 580, x+90, 860, orange)
    # A jersey on a hanger on the left, a towel on the right.
    d.line((28, 352, 28, 362), fill=(60, 60, 64, 255), width=2)
    d.line((8, 372, 28, 360, 48, 372), fill=(60, 60, 64, 255), width=2)
    jersey = [(10, 372), (46, 372), (56, 392), (48, 398), (44, 392), (44, 470), (12, 470), (12, 392), (8, 398), (0, 392)]
    d.polygon(jersey, fill=(*pink, 255))
    d.rectangle((22, 372, 34, 378), fill=(250, 250, 250, 255))
    cp._label(im, '7', 28, 420, 20, (250, 250, 250), 20, s, 'CRT Scoreboard')
    d.rectangle((494, 360, 540, 520), fill=(*cyan, 255))
    for y in range(372, 520, 12):
        d.line((494, y, 540, y), fill=(250, 250, 250, 255), width=2)
    # The bench, the boots and the ball.
    d.rectangle((0, 860, 540, 960), fill=(126, 146, 160, 255))
    for x in range(0, 540, 36):
        d.line((x, 860, x, 960), fill=(104, 122, 136, 255), width=1)
    for y in range(860, 960, 24):
        d.line((0, y, 540, y), fill=(104, 122, 136, 255), width=1)
    _layer(im, s, lambda q: q.rectangle((40, 846, 500, 870), fill=(60, 50, 44, 90)), 3)
    d.rectangle((30, 790, 510, 812), fill=(176, 116, 64, 255))
    d.rectangle((30, 808, 510, 814), fill=(132, 84, 44, 255))
    for x in (60, 470):
        d.rectangle((x, 814, x+12, 870), fill=(70, 70, 76, 255))
    for x in (140, 176):
        d.polygon([(x, 840), (x+22, 840), (x+34, 856), (x+34, 866), (x, 866)], fill=(26, 26, 30, 255))
        d.line((x+8, 846, x+20, 846), fill=(*pink, 255), width=2)
        for k in range(4):
            d.rectangle((x+4+k*8, 866, x+7+k*8, 870), fill=(200, 200, 204, 255))
    _ball(d, 410, 900, 22)
    # The TV on the wall.
    cp._box(d, (52, 292, 488, 696), (26, 26, 30, 255), (70, 70, 78, 255), 5, 8)
    _screen(d, (20, 14, 10))
    cp._box(d, (180, 244, 360, 282), (246, 244, 236, 255), (70, 70, 78, 255), 3, 4)
    cp._label(im, 'SPOGLIATOIO', 270, 263, 160, (30, 30, 34), 13, s, 'CRT Scoreboard')
    cp._label(im, 'CASA', 270, 720, 80, (250, 250, 250), 10, s)
    return im


# --- 26 Fumetto ----------------------------------------------------------------------

def _halftone(d, box, bg, dot, step=9, r=2.6):
    x1, y1, x2, y2 = box
    d.rectangle(box, fill=(*bg, 255))
    for j, y in enumerate(np.arange(y1+step/2, y2, step)):
        for x in np.arange(x1+step/2+(j % 2)*step/2, x2, step):
            d.ellipse((x-r, y-r, x+r, y+r), fill=(*dot, 255))


def _burst(d, x, y, r1, r2, n, fill, outline):
    pts = [(x+(r1 if k % 2 == 0 else r2)*math.cos(math.pi*k/n), y+(r1 if k % 2 == 0 else r2)*.78*math.sin(math.pi*k/n))
           for k in range(2*n)]
    d.polygon(pts, fill=(*outline, 255))
    inner = [(x+(px-x)*.86, y+(py-y)*.86) for px, py in pts]
    d.polygon(inner, fill=(*fill, 255))


def _speed_lines(d, box, cx, cy, color, n=30):
    x1, y1, x2, y2 = box
    for k in range(n):
        a = 2*math.pi*k/n
        r = 400
        d.polygon([(cx+40*math.cos(a), cy+40*math.sin(a)), (cx+r*math.cos(a-.03), cy+r*math.sin(a-.03)),
                   (cx+r*math.cos(a+.03), cy+r*math.sin(a+.03))], fill=(*color, 255))


def _panel_frame(d, box, ink=(16, 16, 20)):
    d.rectangle(box, outline=(*ink, 255), width=5)


def bg_fumetto(pink, cyan, yellow, s):
    cp = _cp()
    im = _noise(Image.new('RGBA', (540*s, 960*s), (250, 247, 236, 255)), s, 4, 26)
    ink = (16, 16, 20)
    light_pink = tuple(min(255, round(c*.55+255*.45)) for c in pink)
    light_cyan = tuple(min(255, round(c*.55+255*.45)) for c in cyan)
    # Each panel is drawn on its own image so lines never leak into the next one.
    def panel(box, draw):
        layer = Image.new('RGBA', im.size)
        draw(ScaledDraw(layer, s))
        x1, y1, x2, y2 = (round(v*s) for v in box)
        im.alpha_composite(layer.crop((x1, y1, x2, y2)), (x1, y1))
    panel((12, 12, 262, 272), lambda q: (_halftone(q, (12, 12, 262, 272), light_cyan, cyan),
                                         _burst(q, 137, 142, 112, 70, 12, yellow, ink)))
    panel((272, 12, 528, 272), lambda q: (q.rectangle((272, 12, 528, 272), fill=(*yellow, 255)),
                                          _speed_lines(q, (272, 12, 528, 272), 410, 150, (255, 255, 255))))
    panel((12, 284, 528, 704), lambda q: _halftone(q, (12, 284, 528, 704), light_pink, pink, 10, 3))
    panel((12, 716, 180, 948), lambda q: (_halftone(q, (12, 716, 180, 948), light_cyan, cyan),
                                          _burst(q, 96, 832, 74, 46, 10, pink, ink)))
    panel((190, 716, 350, 948), lambda q: _speed_lines(q, (190, 716, 350, 948), 270, 832, (40, 40, 46), 36))
    panel((360, 716, 528, 948), lambda q: _halftone(q, (360, 716, 528, 948), yellow, (255, 170, 40)))
    d = ScaledDraw(im, s)
    for box in ((12, 12, 262, 272), (272, 12, 528, 272), (12, 284, 528, 704), (12, 716, 180, 948),
                (190, 716, 350, 948), (360, 716, 528, 948)):
        _panel_frame(d, box, ink)
    cp._label(im, 'SBAM!', 137, 140, 150, (210, 30, 60), 26, s, 'CRT Scoreboard')
    cp._label(im, 'POW!', 96, 830, 110, (250, 250, 250), 18, s, 'CRT Scoreboard')
    # The ball flying across the yellow panel.
    for k, (y, x) in enumerate(((132, 318), (148, 300), (164, 322))):
        d.rectangle((x, y, x+70, y+4), fill=(*ink, 255))
    _ball(d, 430, 150, 26)
    # Speech bubble in the middle panel and in the last one.
    d.ellipse((380, 760, 520, 860), fill=(255, 255, 255, 255), outline=(*ink, 255), width=3)
    d.polygon([(410, 846), (396, 900), (440, 852)], fill=(255, 255, 255, 255))
    d.line((410, 848, 396, 900, 440, 856), fill=(*ink, 255), width=3)
    cp._label(im, 'GOL!!', 450, 810, 110, ink, 20, s, 'CRT Scoreboard')
    cp._label(im, 'ZAC!', 270, 832, 110, ink, 20, s, 'CRT Scoreboard')
    # The screen sits inside the big panel, with the classic caption box.
    cp._box(d, (60, 300, 480, 690), (16, 16, 20, 255), (*ink, 255), 4, 4)
    _screen(d, (14, 14, 18))
    d.rectangle((24, 292, 230, 314), fill=(*yellow, 255), outline=(*ink, 255), width=2)
    cp._label(im, 'INTANTO, AL CAMPO...', 127, 303, 196, ink, 8, s)
    return im


# --- 27 Distributore ----------------------------------------------------------------

def bg_distributore(pink, cyan, yellow, s):
    cp = _cp()
    im = Image.new('RGBA', (540*s, 960*s), (46, 32, 64, 255))
    d = ScaledDraw(im, s)
    for y in range(0, 960, 30):   # wall tiles
        d.line((0, y, 540, y), fill=(34, 22, 50, 255), width=1.5)
    for x in range(0, 540, 30):
        d.line((x, 0, x, 960), fill=(34, 22, 50, 255), width=1.5)
    body = tuple(round(c*.92) for c in pink)
    d.rectangle((24, 26, 516, 944), fill=(*body, 255))
    d.rectangle((24, 26, 42, 944), fill=(*[min(255, c+40) for c in body], 255))
    d.rectangle((498, 26, 516, 944), fill=(*[round(c*.78) for c in body], 255))
    # Lit header.
    _layer(im, s, lambda q: q.rectangle((40, 40, 500, 140), fill=(255, 255, 255, 120)), 10)
    cp._box(d, (48, 48, 492, 132), (252, 248, 252, 255), (60, 30, 50, 255), 3, 6)
    cp._label(im, 'BIBITE FRESCHE', 270, 80, 400, tuple(round(c*.8) for c in pink), 22, s, 'CRT Scoreboard')
    cp._label(im, 'ACQUA / TE / ARANCIATA / ENERGY', 270, 114, 380, (90, 70, 90), 8, s)
    # The product window with two shelves of cans.
    d.rectangle((48, 146, 492, 284), fill=(30, 26, 40, 255))
    cans = (cyan, yellow, (250, 250, 250), pink, (120, 230, 120))
    for row, y in enumerate((156, 218)):
        for k, x in enumerate(range(62, 480, 47)):
            col = cans[(k+row*2) % len(cans)]
            d.rectangle((x, y, x+26, y+40), fill=(190, 192, 200, 255))
            d.rectangle((x+2, y+8, x+24, y+34), fill=(*col, 255))
            d.rectangle((x+2, y+18, x+24, y+22), fill=(246, 246, 246, 255))
            for t in range(4):
                d.line((x+2+t*6, y+44, x+5+t*6, y+50), fill=(150, 150, 160, 255), width=1.5)
        d.rectangle((52, y+52, 488, y+56), fill=(120, 120, 130, 255))
    _layer(im, s, lambda q: [q.polygon([(x, 146), (x+40, 146), (x-30, 284), (x-70, 284)], fill=(255, 255, 255, 34))
                             for x in (160, 330, 470)])
    # Display window (the screen), keypad, coin slot and the pickup tray.
    cp._box(d, (52, 292, 488, 696), (40, 40, 48, 255), (210, 210, 220, 255), 5, 6)
    _screen(d, (24, 10, 26))
    cp._box(d, (60, 712, 480, 800), (54, 52, 64, 255), (210, 210, 220, 255), 3, 6)
    for k, key in enumerate(('A', 'B', 'C', '1', '2', '3')):
        x = 80+k*38
        d.rectangle((x, 728, x+28, 756), fill=(230, 230, 236, 255), outline=(20, 20, 24, 255), width=1.5)
        cp._label(im, key, x+14, 742, 20, (30, 30, 34), 11, s, 'CRT Scoreboard')
    d.rectangle((316, 726, 460, 750), fill=(18, 40, 24, 255))
    cp._label(im, 'INSERIRE MONETA', 388, 738, 136, (120, 255, 150), 8, s)
    d.rectangle((420, 762, 450, 792), fill=(200, 200, 210, 255))
    d.rectangle((432, 766, 438, 788), fill=(20, 20, 24, 255))
    d.rectangle((100, 820, 440, 902), fill=(18, 16, 22, 255))
    d.rectangle((108, 826, 432, 862), fill=(62, 58, 72, 255))
    cp._label(im, 'SPINGERE', 270, 844, 120, (210, 210, 220), 10, s)
    d.rectangle((180, 874, 220, 896), fill=(*cyan, 255))
    for x in (44, 456):
        d.rectangle((x, 944, x+40, 956), fill=(20, 18, 24, 255))
    return im


# --- 28 Graffiti -----------------------------------------------------------------------

def bg_graffiti(pink, cyan, yellow, s):
    cp = _cp()
    im = _noise(Image.new('RGBA', (540*s, 960*s), (156, 154, 148, 255)), s, 12, 28)
    d = ScaledDraw(im, s)
    for x in (90, 450):   # concrete slabs and tie holes
        d.line((x, 0, x, 890), fill=(120, 118, 114, 255), width=2)
    for y in (240, 770):
        d.line((0, y, 540, y), fill=(120, 118, 114, 255), width=2)
    for x in (30, 150, 390, 510):
        for y in (40, 200, 810):
            d.ellipse((x-4, y-4, x+4, y+4), fill=(96, 94, 90, 255))
    rnd = random.Random(28)
    # Spray splats.
    _layer(im, s, lambda q: [q.ellipse((x-r, y-r, x+r, y+r), fill=(*c, 150)) for x, y, r, c in
                             ((40, 560, 46, pink), (500, 420, 40, cyan), (470, 880, 60, yellow), (60, 260, 30, cyan))], 6)
    # The piece: a cloud behind big outlined letters, with drips.
    for x, y, r in ((90, 130, 70), (190, 100, 80), (300, 110, 86), (410, 130, 76), (150, 180, 60), (360, 190, 64)):
        d.ellipse((x-r-5, y-r*.7-5, x+r+5, y+r*.7+5), fill=(20, 20, 24, 255))
    for x, y, r in ((90, 130, 70), (190, 100, 80), (300, 110, 86), (410, 130, 76), (150, 180, 60), (360, 190, 64)):
        d.ellipse((x-r, y-r*.7, x+r, y+r*.7), fill=(*yellow, 255))
    _outlined(im, 'FLAMINGOS', 270, 140, 470, pink, (20, 20, 24), 52, s, shadow=tuple(round(c*.55) for c in cyan), depth=6)
    for _ in range(14):
        x = rnd.uniform(70, 470)
        y = rnd.uniform(190, 230)
        d.line((x, y, x, y+rnd.uniform(12, 46)), fill=(*pink, 255), width=2.5)
    _outlined(im, 'CALCIO A 7', 270, 760, 380, cyan, (20, 20, 24), 26, s, shadow=(30, 30, 36), depth=4)
    # Tags.
    for _ in range(10):
        x, y = rnd.choice(((rnd.uniform(4, 50), rnd.uniform(300, 700)), (rnd.uniform(490, 536), rnd.uniform(300, 700)),
                           (rnd.uniform(40, 500), rnd.uniform(800, 860))))
        col = rnd.choice(((20, 20, 24), (250, 250, 250), (220, 40, 60)))
        d.line([(x+k*5, y+rnd.uniform(-7, 7)) for k in range(rnd.randrange(4, 8))], fill=(*col, 255), width=2)
    # The screen is a paste-up with tape on the corners.
    d.rectangle((54, 292, 486, 696), fill=(242, 240, 232, 255))
    _screen(d, (16, 16, 18))
    for x, y, k in ((54, 292, 1), (486, 292, -1), (54, 696, -1), (486, 696, 1)):
        d.polygon([(x-18, y-6*k), (x-6, y-18*k), (x+18, y+6*k), (x+6, y+18*k)], fill=(226, 214, 170, 255))
    # Pavement and a spray can.
    d.rectangle((0, 890, 540, 960), fill=(98, 98, 102, 255))
    d.rectangle((0, 890, 540, 900), fill=(132, 132, 136, 255))
    for x in range(0, 540, 60):
        d.line((x, 900, x-20, 960), fill=(84, 84, 88, 255), width=1.5)
    d.rectangle((96, 916, 160, 940), fill=(*pink, 255))
    d.rectangle((160, 920, 172, 936), fill=(210, 210, 216, 255))
    d.rectangle((172, 924, 178, 932), fill=(30, 30, 34, 255))
    d.rectangle((96, 922, 160, 926), fill=(255, 220, 236, 255))
    return im


# --- 29 Cartolina -----------------------------------------------------------------------

def bg_cartolina(pink, cyan, yellow, s):
    cp = _cp()
    im = Image.new('RGBA', (540*s, 960*s), (250, 246, 232, 255))
    sky = cp._gradient((508*s, 920*s), (96, 168, 236), (214, 236, 250))
    im.paste(sky, (round(16*s), round(16*s)))
    d = ScaledDraw(im, s)
    for x, y in ((80, 170), (350, 150), (470, 200)):   # pixel clouds
        for dx, dy, w in ((0, 0, 60), (14, -10, 34), (30, 6, 46)):
            d.rectangle((x+dx, y+dy, x+dx+w, y+dy+14), fill=(255, 255, 255, 255))
    far = [(16, 330), (70, 250), (120, 286), (190, 214), (250, 270), (320, 196), (390, 262), (450, 228), (524, 296), (524, 420), (16, 420)]
    d.polygon(far, fill=(150, 170, 204, 255))
    for (x1, y1), (x2, y2), (x3, y3) in zip(far[:-3], far[1:-2], far[2:-1]):
        if y2 < y1 and y2 < y3:   # snow on the peaks
            d.polygon([(x2, y2), (x2-(x2-x1)*.3, y2+(y1-y2)*.3), (x2+(x3-x2)*.3, y2+(y3-y2)*.3)], fill=(250, 252, 255, 255))
    d.polygon([(16, 380), (100, 300), (170, 340), (260, 290), (360, 350), (440, 300), (524, 350), (524, 700), (16, 700)],
              fill=(84, 120, 150, 255))
    # Lake with reflections, the shore and pines.
    d.rectangle((16, 690, 524, 870), fill=(60, 132, 196, 255))
    rnd = random.Random(29)
    for _ in range(40):
        x, y = rnd.uniform(20, 500), rnd.uniform(700, 860)
        d.rectangle((x, y, x+rnd.uniform(8, 30), y+2), fill=(170, 220, 250, 255))
    d.polygon([(110, 790), (170, 790), (160, 802), (120, 802)], fill=(120, 70, 40, 255))
    d.polygon([(140, 788), (140, 730), (172, 786)], fill=(255, 255, 255, 255))
    d.polygon([(136, 788), (136, 744), (112, 786)], fill=(*pink, 255))
    d.rectangle((16, 860, 524, 944), fill=(76, 146, 74, 255))
    for x in range(16, 524, 9):
        d.rectangle((x, 856, x+4, 862), fill=(76, 146, 74, 255))
    for x, base, h in ((40, 460, 120), (30, 640, 150), (500, 480, 130), (510, 660, 140), (60, 900, 60), (470, 910, 70)):
        for k in range(4):
            w = h*.32*(1-k*.18)
            y = base-k*h*.22
            d.polygon([(x, y-h*.34), (x-w, y), (x+w, y)], fill=(30, 92, 56, 255))
        d.rectangle((x-3, base, x+3, base+10), fill=(90, 60, 40, 255))
    # The photo around the screen, with corners.
    d.rectangle((58, 294, 482, 694), fill=(255, 253, 245, 255))
    _screen(d, (12, 30, 54))
    for x, y, kx, ky in ((58, 294, 1, 1), (482, 294, -1, 1), (58, 694, 1, -1), (482, 694, -1, -1)):
        d.polygon([(x, y), (x+kx*26, y), (x, y+ky*26)], fill=(40, 40, 46, 255))
    # Greeting lettering.
    cp._label(im, 'SALUTI DA', 270, 46, 200, (255, 255, 255), 14, s, 'CRT Scoreboard')
    _outlined(im, 'BRESCIA', 270, 98, 420, yellow, (40, 30, 60), 40, s, shadow=(220, 80, 60), depth=5)
    # Stamp and postmark.
    d.rectangle((410, 830, 506, 930), fill=(255, 255, 255, 255))
    for k in range(9):
        for x, y in ((410+k*12, 830), (410+k*12, 930), (410, 830+k*12.5), (506, 830+k*12.5)):
            d.ellipse((x-3, y-3, x+3, y+3), fill=(76, 146, 74, 255))
    d.rectangle((418, 838, 498, 922), fill=(*pink, 255))
    cp._label(im, '7', 458, 872, 40, (255, 255, 255), 34, s, 'CRT Scoreboard')
    cp._label(im, 'CSI', 458, 910, 40, (255, 255, 255), 9, s)
    _layer(im, s, lambda q: (q.ellipse((330, 840, 420, 930), outline=(40, 40, 50, 170), width=2),
                             q.ellipse((342, 852, 408, 918), outline=(40, 40, 50, 170), width=1.5),
                             [q.line([(250+k2*8, 860+r*14+3*math.sin(k2)) for k2 in range(12)], fill=(40, 40, 50, 150), width=1.5)
                              for r in range(4)]))
    return im


# --- 30 Cruciverba -----------------------------------------------------------------------

CW_COLS, CW_X, CW_Y, CW = 17, 15, 110, 30
CW_TOP = ('#FLAMINGOS#GOL#..',
          '..#....#.....#...',
          'SETTE#.....#RETE.',
          '...#.....#.....#.',
          '#PALLA#..#MISTER#',
          '..#...#.....#....')
CW_BOTTOM = ('...#.....#.......',
             '#BRESCIA#..#CSI#.',
             '..#...#.....#....',
             'TIFO#.....#ROSA#.',
             '...#....#....#...',
             '#..#CALCIO#..#..#',
             '....#.....#......',
             '#.....#.....#...#')
CW_LEFT = '#DERBY#..#....'
CW_RIGHT = '#..#PORTA#...#'


def _crossword():
    grid = [[' ']*CW_COLS for _ in range(28)]
    for r, row in enumerate(CW_TOP):
        grid[r] = list(row)
    for r, row in enumerate(CW_BOTTOM):
        grid[20+r] = list(row)
    for k in range(14):
        grid[6+k][0] = CW_LEFT[k]
        grid[6+k][16] = CW_RIGHT[k]
    return grid


def bg_cruciverba(pink, cyan, yellow, s):
    cp = _cp()
    im = _noise(Image.new('RGBA', (540*s, 960*s), (246, 240, 222, 255)), s, 5, 30)
    d = ScaledDraw(im, s)
    d.rectangle((0, 0, 540, 96), fill=(28, 58, 140, 255))
    d.rectangle((0, 92, 540, 96), fill=(*yellow, 255))
    cp._label(im, 'CRUCIVERBA', 270, 40, 360, (255, 255, 255), 28, s, 'CRT Scoreboard')
    cp._label(im, 'SCHEMA LIBERO N. 7', 270, 76, 240, yellow, 9, s)
    grid = _crossword()
    number = 0
    ink = (30, 60, 170)
    def open_(r, c):
        return 0 <= r < 28 and 0 <= c < CW_COLS and grid[r][c] not in ('#', ' ')
    for r in range(28):
        for c in range(CW_COLS):
            ch = grid[r][c]
            if ch == ' ':
                continue
            x, y = CW_X+c*CW, CW_Y+r*CW
            if ch == '#':
                d.rectangle((x, y, x+CW, y+CW), fill=(22, 22, 26, 255))
                continue
            d.rectangle((x, y, x+CW, y+CW), fill=(252, 250, 244, 255), outline=(40, 40, 44, 255), width=1)
            starts = (open_(r, c+1) and not open_(r, c-1)) or (open_(r+1, c) and not open_(r-1, c))
            if starts:
                number += 1
                cp._label(im, str(number), x+3+2.2*len(str(number)), y+5, 14, (40, 40, 44), 5, s, 'CRT Scoreboard')
            if ch != '.':
                cp._label(im, ch, x+CW/2, y+CW/2+2, 20, ink, 14, s)
    # The picture box in the middle of the grid, where the screen goes.
    d.rectangle((50, 290, 490, 702), fill=(22, 22, 26, 255))
    _screen(d, (18, 20, 34))
    cp._label(im, 'SOLUZIONE NEL PROSSIMO NUMERO', 270, 954, 300, (90, 86, 80), 6, s)
    return im


# --- 31 Curva ---------------------------------------------------------------------------

def bg_curva(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (16, 18, 52), (40, 30, 70))
    # The choreography: one card per fan, as a mosaic of diagonal stripes.
    cw, ch = 9, 8
    cols, rows = 540//cw+1, (870-90)//ch+1
    rnd = np.random.default_rng(31)
    yy, xx = np.mgrid[0:rows, 0:cols]
    stripe = ((xx*cw+yy*ch*.7)//64).astype(int) % 2
    colors = np.where(stripe[..., None] == 0, np.array(pink, np.float32), np.array((246, 246, 246), np.float32))
    band = (yy*ch < 46) | (yy*ch > 730)
    colors[band] = np.array(cyan, np.float32)
    colors *= rnd.uniform(.86, 1.06, (rows, cols, 1)).astype(np.float32)
    off = rnd.random((rows, cols)) < .03
    colors[off] = np.array((40, 30, 50), np.float32)
    tile = np.zeros((rows*ch, cols*cw, 4), np.uint8)
    tile[..., 3] = 255
    tile[..., :3] = (36, 26, 44)
    cells = np.repeat(np.repeat(colors.clip(0, 255).astype(np.uint8), ch, 0), cw, 1)
    inner = np.ones((ch, cw), bool)
    inner[-1, :] = False
    inner[:, -1] = False
    mask = np.tile(inner, (rows, cols))
    tile[..., :3][mask] = cells[mask]
    mosaic = Image.fromarray(tile, 'RGBA').crop((0, 0, 540, 870-90)).resize((540*s, 780*s), Image.Resampling.NEAREST)
    im.paste(mosaic, (0, round(90*s)))
    d = ScaledDraw(im, s)
    # Floodlights.
    _layer(im, s, lambda q: (q.ellipse((-120, -120, 200, 160), fill=(255, 250, 220, 150)),
                             q.ellipse((340, -120, 660, 160), fill=(255, 250, 220, 150))), 40)
    for x in (40, 404):
        for j in range(3):
            for i in range(4):
                d.rectangle((x+i*24, 18+j*18, x+i*24+20, 18+j*18+14), fill=(255, 252, 236, 255))
        d.rectangle((x-4, 14, x+96, 72), outline=(70, 70, 80, 255), width=2)
    # Flags and flare smoke.
    for x, col, k in ((26, cyan, 1), (514, yellow, -1)):
        d.line((x, 110, x, 330), fill=(220, 220, 228, 255), width=3)
        d.polygon([(x, 112), (x+k*60, 120+8), (x+k*44, 150), (x+k*64, 182), (x, 176)], fill=(*col, 255))
    _layer(im, s, lambda q: [q.ellipse((x-r, y-r, x+r, y+r), fill=(*pink, 110)) for x, y, r in
                             ((20, 760, 70), (60, 700, 50), (520, 740, 76), (480, 690, 46), (270, 150, 40))], 22)
    # The giant screen.
    cp._box(d, (52, 292, 488, 696), (30, 30, 36, 255), (70, 70, 80, 255), 5, 6)
    for x, y in ((52, 292), (488, 292), (52, 696), (488, 696)):
        d.ellipse((x-6, y-6, x+6, y+6), fill=(*yellow, 255))
    _screen(d, (14, 8, 22))
    # Banner on the railing, the railing and the edge of the pitch.
    d.rectangle((16, 856, 524, 912), fill=(250, 250, 250, 255), outline=(*pink, 255), width=4)
    cp._label(im, 'FORZA FLAMINGOS', 270, 885, 470, tuple(round(c*.85) for c in pink), 24, s, 'CRT Scoreboard')
    d.rectangle((0, 914, 540, 922), fill=(150, 150, 160, 255))
    for x in range(0, 540, 30):
        d.rectangle((x, 900, x+4, 930), fill=(150, 150, 160, 255))
    d.rectangle((0, 930, 540, 960), fill=(46, 140, 70, 255))
    d.rectangle((0, 944, 540, 947), fill=(240, 240, 240, 255))
    return im


BUILDERS = {'acquario': bg_acquario, 'spogliatoio': bg_spogliatoio, 'fumetto': bg_fumetto, 'distributore': bg_distributore,
            'graffiti': bg_graffiti, 'cartolina': bg_cartolina, 'cruciverba': bg_cruciverba, 'curva': bg_curva}

PRESETS = {
    'acquario': dict(name='24 / Acquario', object='Oblò sul fondale',
                     description='Acqua turchese, raggi di luce, pesci pixel, alghe e un pallone finito sulla sabbia.',
                     pink='#FF7AB8', cyan='#6BF0E6', yellow='#FFE27A', white='#F2FFFD', font='CRT Terminal'),
    'spogliatoio': dict(name='25 / Spogliatoio', object='Armadietti',
                        description='Armadietti arancioni (il 7 è rosa), maglia appesa, panca, scarpini e pallone.',
                        pink='#FF6FAE', cyan='#7FD6FF', yellow='#FFC24D', white='#FFF8F0', font='CRT Scoreboard'),
    'fumetto': dict(name='26 / Fumetto', object='Tavola a fumetti',
                    description='Vignette con i retini, SBAM e POW, linee cinetiche e il riquadro della didascalia.',
                    pink='#FF4F9A', cyan='#3FC7F2', yellow='#FFE14D', white='#FFFFFF', font='CRT Scoreboard'),
    'distributore': dict(name='27 / Distributore', object='Distributore di bibite',
                         description='Macchinetta rosa con le lattine in vetrina, tastierino, gettoniera e sportello.',
                         pink='#FF5FA2', cyan='#6FE7FF', yellow='#FFE36E', white='#FFF5FA', font='CRT Scoreboard'),
    'graffiti': dict(name='28 / Graffiti', object='Muro di cemento',
                     description='Pezzo FLAMINGOS con le colature, tag, spruzzi e il manifesto attaccato col nastro.',
                     pink='#FF4FB0', cyan='#40E0FF', yellow='#FFE53D', white='#FFFFFF', font='CRT Scoreboard'),
    'cartolina': dict(name='29 / Cartolina', object='Cartolina illustrata',
                      description='Montagne innevate, lago con la barca a vela, pini, francobollo e timbro postale.',
                      pink='#FF7FAF', cyan='#7FD3FF', yellow='#FFD95C', white='#FFFDF5', font='CRT Terminal'),
    'cruciverba': dict(name='30 / Cruciverba', object='Schema di parole crociate',
                       description='Griglia con le caselle nere e le parole della squadra scritte a penna.',
                       pink='#FF6FA5', cyan='#7FCBFF', yellow='#FFE066', white='#FFFFFF', font='CRT Terminal'),
    'curva': dict(name='31 / Curva', object='Coreografia in curva',
                  description='Mosaico di cartoncini rosa e bianchi, bandiere, fumogeni, riflettori e striscione.',
                  pink='#FF5FAE', cyan='#5FE3FF', yellow='#FFE45C', white='#FFFFFF', font='CRT Scoreboard'),
}

STYLE = {
    'acquario': dict(panel=(4, 26, 40), border=None, scan=None, veil=40),
    'spogliatoio': dict(panel=(20, 14, 10), border=(255, 194, 77), scan=None, veil=30),
    'fumetto': dict(panel=(14, 14, 18), border=(250, 250, 250), scan=(255, 255, 255), veil=0),
    'distributore': dict(panel=(24, 10, 26), border=None, scan=None, veil=30),
    'graffiti': dict(panel=(16, 16, 18), border=None, scan=None, veil=30),
    'cartolina': dict(panel=(12, 30, 54), border=(255, 253, 245), scan=None, veil=30),
    'cruciverba': dict(panel=(18, 20, 34), border=(246, 240, 222), scan=None, veil=0),
    'curva': dict(panel=(14, 8, 22), border=None, scan=None, veil=40),
}
