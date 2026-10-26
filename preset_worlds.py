"""Twelve more retro worlds for the CRT presets (12-23).

Each builder draws the full 540x960 frame at scale s around the shared screen
(77-463 x 315-673): the panels, veil and scanlines are added afterwards by
crt_presets._background(). Everything is drawn in code, no images, no brands.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageFilter

from render_utils import ScaledDraw

SCREEN = (77, 315, 463, 673)


def _cp():
    import crt_presets
    return crt_presets


def _layer(im, s, draw, blur=0):
    """Draw translucent shapes on their own layer, optionally blurred, and blend them in."""
    layer = Image.new('RGBA', im.size)
    draw(ScaledDraw(layer, s))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur*s))
    im.alpha_composite(layer)


def _noise(im, s, amount=6, seed=1):
    arr = np.asarray(im).astype(np.int16)
    grain = np.random.default_rng(seed).integers(-amount, amount+1, arr.shape[:2]+(1,), dtype=np.int16)
    arr[..., :3] = (arr[..., :3]+grain).clip(0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def _screen(d, color=(6, 8, 16)):
    d.rectangle(SCREEN, fill=(*color, 255))


# --- 12 Calcio da tavolo -------------------------------------------------------

def _figure(d, x, y, color, s=1.0):
    d.ellipse((x-11*s, y-4*s, x+11*s, y+6*s), fill=(*[round(c*.6) for c in color], 255))
    d.ellipse((x-11*s, y-7*s, x+11*s, y+3*s), fill=(*color, 255))
    d.rectangle((x-4*s, y-24*s, x+4*s, y-6*s), fill=(*color, 255))
    d.rectangle((x-4*s, y-14*s, x+4*s, y-10*s), fill=(250, 250, 250, 255))
    d.ellipse((x-4*s, y-32*s, x+4*s, y-24*s), fill=(236, 190, 160, 255))


def bg_tavolo(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (24, 110, 58), (14, 78, 40))
    im = _noise(im, s, 7, 12)
    d = ScaledDraw(im, s)
    line = (236, 250, 236, 255)
    for i, y in enumerate(range(0, 960, 80)):   # felt stripes
        if i % 2:
            _layer(im, s, lambda q, y=y: q.rectangle((0, y, 540, y+80), fill=(255, 255, 255, 12)))
    d.rectangle((14, 14, 526, 946), outline=line, width=3)
    d.line((14, 480, 526, 480), fill=line, width=3)
    d.ellipse((200, 410, 340, 550), outline=line, width=3)
    d.rectangle((150, 14, 390, 110), outline=line, width=3)
    d.rectangle((150, 850, 390, 946), outline=line, width=3)
    for gx, gy in ((270, 6), (270, 954)):          # goals with a net
        d.rectangle((gx-60, gy-6, gx+60, gy+6), fill=(250, 250, 250, 255))
        for x in range(gx-56, gx+60, 8):
            d.line((x, gy-5, x, gy+5), fill=(150, 160, 150, 255), width=1)
    # The wooden box around the screen.
    cp._box(d, (44, 252, 496, 728), (122, 74, 40, 255), (70, 40, 20, 255), 4, 10)
    for y in range(262, 720, 9):
        d.line((52, y, 488, y+2), fill=(138, 86, 48, 255), width=1)
    cp._box(d, (62, 298, 478, 690), (40, 22, 12, 255), (*yellow, 255), 3, 6)
    cp._box(d, (130, 230, 410, 276), (*yellow, 255), (70, 40, 20, 255), 3, 6)
    cp._label(im, 'CALCIO DA TAVOLO', 270, 253, 260, (60, 34, 16), 13, s, 'CRT Scoreboard')
    for x, col in ((80, pink), (150, cyan), (390, pink), (460, cyan)):
        _figure(d, x, 214 if x < 270 else 222, col, 1.6)
    for x, col in ((80, cyan), (160, pink), (240, cyan), (330, pink), (410, cyan), (470, pink)):
        _figure(d, x, 806+(10 if x % 3 else 0), col, 1.7)
    d.ellipse((282, 756, 302, 776), fill=(250, 250, 250, 255))
    d.ellipse((288, 762, 296, 770), fill=(30, 30, 30, 255))
    cp._label(im, 'FLAMINGOS EDITION / 7 GIOCATORI', 270, 712, 360, (250, 228, 190), 9, s)
    _screen(d, (6, 34, 20))
    return im


# --- 13 Album figurine ----------------------------------------------------------

def bg_figurine(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (232, 240, 250), (206, 222, 242))
    im = _noise(im, s, 4, 13)
    d = ScaledDraw(im, s)
    d.rectangle((0, 120, 540, 214), fill=(*pink, 255))
    d.rectangle((0, 214, 540, 222), fill=(*yellow, 255))
    cp._label(im, 'ALBUM FIGURINE', 270, 152, 440, (255, 255, 255), 22, s, 'CRT Scoreboard')
    cp._label(im, 'CALCIO A 7 / STAGIONE FLAMINGOS', 270, 190, 420, (255, 236, 246), 10, s)
    navy = (40, 52, 96)
    # Empty sticker slots, numbered, all around the page.
    slots = [(x, y) for y in (236, 736, 836) for x in (22, 152, 282, 412)]
    for i, (x, y) in enumerate(slots):
        d.rounded_rectangle((x, y, x+106, y+82 if y > 700 else y+52), radius=6, outline=(*navy, 150), width=1.4)
        cp._label(im, f'N.{i+3:02d}', x+53, y+(41 if y > 700 else 26), 80, (*navy,), 9, s)
    # The big sticker: white border, shadow, a peeling corner and a gloss stripe.
    _layer(im, s, lambda q: q.rounded_rectangle((60, 304, 488, 698), radius=14, fill=(20, 30, 70, 110)), 8)
    d.rounded_rectangle((52, 296, 480, 690), radius=14, fill=(255, 255, 255, 255))
    d.rounded_rectangle((64, 306, 468, 680), radius=8, fill=(*cyan, 255))
    _screen(d, (18, 22, 52))
    d.polygon([(480, 640), (480, 690), (430, 690)], fill=(206, 222, 242, 255))
    d.polygon([(430, 690), (480, 640), (440, 650)], fill=(236, 236, 240, 255))
    d.line((430, 690, 480, 640), fill=(170, 180, 200, 255), width=1.5)
    _layer(im, s, lambda q: q.polygon([(300, 296), (360, 296), (180, 690), (120, 690)], fill=(255, 255, 255, 34)))
    cp._label(im, 'FLAMINGOS', 140, 712, 160, (*pink,), 14, s, 'CRT Scoreboard')
    cp._label(im, 'N.01 / SPECIALE', 384, 712, 180, navy, 10, s)
    return im


# --- 14 Radiolina ----------------------------------------------------------------

def bg_radio(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (238, 214, 176), (204, 170, 128))
    d = ScaledDraw(im, s)
    for y in range(0, 960, 28):   # wallpaper diamonds
        for x in range(0 if (y//28) % 2 else 14, 540, 28):
            d.polygon([(x, y-5), (x+5, y), (x, y+5), (x-5, y)], fill=(214, 182, 140, 255))
    _layer(im, s, lambda q: q.rounded_rectangle((40, 196, 512, 850), radius=40, fill=(40, 20, 6, 120)), 12)
    d.rounded_rectangle((30, 186, 510, 840), radius=40, fill=(118, 66, 32, 255))
    for i, y in enumerate(range(196, 830, 6)):   # wood grain
        wave = 3*math.sin(i*.7)
        d.line((48, y+wave, 492, y-wave), fill=(132, 76, 38, 255) if i % 3 else (102, 56, 26, 255), width=1)
    d.rounded_rectangle((30, 186, 510, 840), radius=40, outline=(70, 36, 14, 255), width=4)
    # Tuning dial with frequencies and the red needle.
    d.rounded_rectangle((64, 214, 476, 284), radius=10, fill=(250, 236, 200, 255), outline=(200, 160, 90, 255), width=3)
    for i, f in enumerate(('88', '92', '96', '100', '104', '108')):
        x = 96+i*70
        d.line((x, 258, x, 270), fill=(80, 50, 30, 255), width=2)
        cp._label(im, f, x, 244, 50, (80, 50, 30), 10, s)
    for x in range(96, 446, 14):
        d.line((x, 264, x, 270), fill=(120, 90, 60, 255), width=1)
    d.line((322, 220, 322, 278), fill=(220, 40, 40, 255), width=3)
    cp._box(d, (62, 298, 478, 690), (24, 16, 10, 255), (210, 170, 100, 255), 3, 8)
    _screen(d, (22, 14, 10))
    # Knobs and speaker grille.
    for x in (100, 440):
        d.ellipse((x-36, 728, x+36, 800), fill=(60, 34, 18, 255), outline=(210, 170, 100, 255), width=3)
        d.ellipse((x-22, 742, x+22, 786), fill=(90, 56, 30, 255))
        d.line((x, 744, x, 762), fill=(250, 236, 200, 255), width=3)
    for y in range(724, 806, 9):
        d.rounded_rectangle((160, y, 380, y+4), radius=2, fill=(52, 28, 12, 255))
    cp._label(im, 'FLAMINGOS FM', 270, 818, 260, (250, 228, 180), 11, s)
    cp._label(im, 'ONDE MEDIE / RADIOCRONACA DEL CAMPO', 270, 150, 460, (110, 66, 30), 11, s)
    return im


# --- 15 PC anni 90 -------------------------------------------------------------

def bg_pc90(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (34, 96, 104), (18, 56, 64))
    d = ScaledDraw(im, s)
    beige, shade, dark = (214, 206, 182, 255), (176, 166, 140, 255), (120, 112, 92, 255)
    # Desk, keyboard at the bottom.
    d.rectangle((0, 840, 540, 960), fill=(92, 64, 44, 255))
    cp._box(d, (40, 864, 500, 950), beige, shade, 3, 6)
    for row in range(3):
        for k in range(14):
            x, y = 54+k*31, 874+row*24
            d.rectangle((x, y, x+26, y+18), fill=(232, 226, 206, 255), outline=dark, width=1)
    # Monitor: beige bezel, plastic shading, label and power LED.
    _layer(im, s, lambda q: q.rounded_rectangle((34, 206, 516, 806), radius=26, fill=(0, 0, 0, 110)), 10)
    d.rounded_rectangle((26, 196, 514, 796), radius=26, fill=beige)
    d.rounded_rectangle((26, 196, 514, 796), radius=26, outline=shade, width=4)
    d.rounded_rectangle((52, 270, 488, 716), radius=18, fill=shade)
    d.rounded_rectangle((60, 278, 480, 708), radius=14, fill=(30, 30, 34, 255))
    _screen(d, (10, 12, 110))
    # DOS-like title line on the bezel and prompt (no real product names).
    d.rectangle((77, 288, 463, 310), fill=(10, 12, 110, 255))
    cp._label(im, 'C:\\FLAMINGOS> PARTITA.EXE', 236, 299, 300, (255, 255, 255), 9, s)
    cp._label(im, 'FLAMINGOS 486 DX', 160, 744, 220, (90, 84, 70), 12, s, 'CRT Scoreboard')
    d.ellipse((440, 738, 452, 750), fill=(60, 230, 90, 255))
    d.rectangle((400, 740, 430, 748), fill=dark)
    for x in (300, 324, 348):
        d.rectangle((x, 736, x+16, 752), fill=shade)
    d.rectangle((210, 796, 330, 840), fill=shade)   # monitor stand
    # A sticky note with the kick-off.
    d.rectangle((388, 130, 488, 220), fill=(255, 236, 110, 255))
    d.rectangle((388, 130, 488, 140), fill=(240, 214, 80, 255))
    cp._label(im, 'PARTITA!', 438, 166, 90, (60, 50, 20), 10, s)
    cp._label(im, 'NON SCORDARE', 438, 190, 92, (60, 50, 20), 7, s)
    cp._label(im, 'CALCIO A 7 / SETUP', 140, 160, 220, (200, 240, 240), 11, s)
    return im


# --- 16 Bar Sport al neon -------------------------------------------------------

def bg_barsport(pink, cyan, yellow, s):
    cp = _cp()
    im = Image.new('RGBA', (540*s, 960*s), (40, 18, 22, 255))
    d = ScaledDraw(im, s)
    rnd = random.Random(16)
    for row, y in enumerate(range(0, 960, 22)):    # dark brick wall
        offset = 0 if row % 2 else 24
        for x in range(-24+offset, 540, 48):
            tone = rnd.randrange(-8, 9)
            d.rectangle((x+2, y+2, x+46, y+20), fill=(70+tone, 30+tone//2, 32+tone//2, 255))
    _layer(im, s, lambda q: q.rectangle((0, 0, 540, 960), fill=(10, 4, 14, 120)))
    # Neon sign and neon frame, glowing.
    def tubes(q, glow=False):
        w = 10 if glow else 3
        q.rounded_rectangle((58, 296, 482, 694), radius=18, outline=(*cyan, 255), width=w)
        q.rounded_rectangle((100, 150, 440, 250), radius=22, outline=(*pink, 255), width=w)
        # a neon cocktail glass
        q.line((468, 140, 520, 140, 494, 168, 468, 140), fill=(*yellow, 255), width=w)
        q.line((494, 168, 494, 190), fill=(*yellow, 255), width=w)
        q.line((482, 192, 506, 192), fill=(*yellow, 255), width=w)
    _layer(im, s, lambda q: tubes(q, True), 14)
    _layer(im, s, tubes)
    sign = Image.new('RGBA', im.size)
    cp._label(sign, 'BAR SPORT', 270, 200, 320, pink, 34, s, 'CRT Scoreboard')
    im.alpha_composite(sign.filter(ImageFilter.GaussianBlur(6*s)))
    im.alpha_composite(sign.filter(ImageFilter.GaussianBlur(2*s)))
    cp._label(im, 'BAR SPORT', 270, 200, 320, (255, 230, 245), 34, s, 'CRT Scoreboard')
    _screen(d, (10, 6, 16))
    # The counter, with a scarf and a glass.
    d.rectangle((0, 760, 540, 800), fill=(110, 60, 30, 255))
    d.rectangle((0, 800, 540, 960), fill=(70, 36, 18, 255))
    for x in range(0, 540, 40):
        d.rectangle((x, 760, x+20, 772), fill=(*pink, 255))
        d.rectangle((x+20, 760, x+40, 772), fill=(250, 250, 250, 255))
    d.rectangle((420, 700, 452, 760), fill=(255, 200, 80, 220))
    d.rectangle((420, 700, 452, 712), fill=(255, 250, 240, 255))
    cp._label(im, 'APERTO TUTTE LE DOMENICHE', 270, 860, 440, (*yellow,), 11, s)
    return im


# --- 17 Flipper ----------------------------------------------------------------

def bg_flipper(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (30, 10, 50), (10, 4, 24))
    d = ScaledDraw(im, s)
    # Backglass with a sunburst.
    d.rounded_rectangle((22, 110, 518, 296), radius=20, fill=(60, 14, 70, 255), outline=(220, 220, 230, 255), width=4)
    _layer(im, s, lambda q: [q.polygon([(270, 210), (270+300*math.cos(a), 210+300*math.sin(a)),
                                         (270+300*math.cos(a+.13), 210+300*math.sin(a+.13))],
                                        fill=(*yellow, 60)) for a in np.arange(0, 2*math.pi, .26)])
    d.rectangle((0, 296, 540, 1000), fill=(10, 4, 24, 255))
    d.rectangle((0, 0, 540, 108), fill=(30, 10, 50, 255))
    cp._label(im, 'FLAMINGOS', 270, 186, 420, (255, 255, 255), 34, s, 'CRT Scoreboard')
    cp._label(im, 'SUPER 7 / SPECIAL', 270, 240, 300, (*cyan,), 12, s)
    for i in range(16):   # chasing lights
        x = 40+i*30.6
        d.ellipse((x-5, 120, x+5, 130), fill=(*(yellow if i % 2 else pink), 255))
    # Chrome rails and the dot-matrix display.
    for x in (30, 498):
        d.rectangle((x, 296, x+12, 960), fill=(200, 204, 214, 255))
    cp._box(d, (58, 300, 482, 690), (12, 6, 2, 255), (255, 140, 30, 255), 4, 8)
    _screen(d, (12, 6, 2))
    dots = Image.new('RGBA', im.size)
    dd = ScaledDraw(dots, s)
    for y in range(318, 672, 5):
        for x in range(80, 462, 5):
            dd.rectangle((x, y, x+2, y+2), fill=(255, 140, 30, 30))
    im.alpha_composite(dots)
    # Playfield: bumpers, slingshots, flippers and the ball.
    for x, y, col in ((150, 790, pink), (270, 764, cyan), (390, 790, yellow)):
        d.ellipse((x-30, y-30, x+30, y+30), fill=(*col, 255), outline=(255, 255, 255, 255), width=3)
        d.ellipse((x-14, y-14, x+14, y+14), fill=(255, 255, 255, 255))
    d.polygon([(70, 846), (110, 916), (70, 916)], fill=(*cyan, 255))
    d.polygon([(470, 846), (430, 916), (470, 916)], fill=(*cyan, 255))
    d.polygon([(150, 914), (250, 940), (250, 952), (150, 930)], fill=(250, 250, 250, 255))
    d.polygon([(390, 914), (290, 940), (290, 952), (390, 930)], fill=(250, 250, 250, 255))
    d.ellipse((322, 856, 340, 874), fill=(230, 230, 240, 255))
    cp._label(im, 'BALL 1   CREDIT 7', 270, 712, 300, (255, 140, 30), 11, s)
    return im


# --- 18 Gioco LCD (light screen, dark ink) ---------------------------------------

def bg_lcd(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (40, 70, 80), (20, 40, 48))
    d = ScaledDraw(im, s)
    body = (214, 64, 40, 255)
    _layer(im, s, lambda q: q.rounded_rectangle((34, 160, 516, 880), radius=22, fill=(0, 0, 0, 120)), 10)
    d.rounded_rectangle((24, 150, 506, 870), radius=22, fill=body)
    for y in range(160, 862, 4):    # brushed metal plate
        d.line((40, y, 490, y), fill=(226, 80, 54, 255) if y % 8 else (200, 54, 34, 255), width=1)
    d.rounded_rectangle((44, 200, 486, 760), radius=10, fill=(236, 226, 200, 255))
    d.rounded_rectangle((52, 208, 478, 752), radius=8, outline=(40, 36, 30, 255), width=2)
    cp._label(im, 'LCD GOL 7', 160, 232, 200, (40, 36, 30), 14, s, 'CRT Scoreboard')
    cp._label(im, 'CALCIO A 7', 380, 232, 160, (214, 64, 40), 12, s)
    cp._box(d, (66, 292, 474, 696), (60, 64, 50, 255), (40, 36, 30, 255), 3, 4)
    _screen(d, (196, 204, 170))
    cp._label(im, 'GAME A', 130, 724, 100, (40, 36, 30), 10, s)
    cp._label(im, 'GAME B', 230, 724, 100, (40, 36, 30), 10, s)
    cp._label(im, 'TIME', 330, 724, 80, (40, 36, 30), 10, s)
    for x in (130, 230, 330):
        d.rounded_rectangle((x-22, 736, x+22, 746), radius=4, fill=(60, 56, 50, 255))
    for x, y in ((90, 812), (450, 812)):   # the two big round buttons
        d.ellipse((x-34, y-34, x+34, y+34), fill=(250, 240, 220, 255), outline=(120, 30, 20, 255), width=3)
        d.ellipse((x-24, y-24, x+24, y+24), fill=(214, 64, 40, 255))
    cp._label(im, 'WIDE SCREEN', 270, 812, 200, (250, 236, 210), 13, s, 'CRT Scoreboard')
    return im


# --- 19 Cinema -----------------------------------------------------------------

def bg_cinema(pink, cyan, yellow, s):
    cp = _cp()
    im = Image.new('RGBA', (540*s, 960*s), (40, 4, 12, 255))
    d = ScaledDraw(im, s)
    for x in range(0, 540, 18):     # velvet curtain folds
        k = (math.sin(x/18*1.2)+1)/2
        d.rectangle((x, 0, x+18, 960), fill=(round(110+70*k), round(10+12*k), round(24+16*k), 255))
    d.rectangle((0, 0, 540, 120), fill=(96, 8, 20, 255))
    for x in range(0, 540, 12):     # gold fringe
        d.polygon([(x, 120), (x+12, 120), (x+6, 140)], fill=(*yellow, 255))
    d.rectangle((0, 116, 540, 124), fill=(*yellow, 255))
    # Marquee with bulbs around the screen.
    cp._box(d, (40, 168, 500, 716), (24, 10, 16, 255), (*yellow, 255), 5, 12)
    d.rectangle((60, 188, 480, 286), fill=(250, 244, 226, 255))
    cp._label(im, 'PRIMA VISIONE', 270, 220, 400, (150, 14, 30), 24, s, 'CRT Scoreboard')
    cp._label(im, 'FLAMINGOS / CALCIO A 7', 270, 260, 400, (40, 20, 24), 12, s)
    glow = Image.new('RGBA', im.size)
    g = ScaledDraw(glow, s)
    bulbs = [(x, 178) for x in range(56, 490, 26)]+[(x, 706) for x in range(56, 490, 26)]
    bulbs += [(50, y) for y in range(200, 700, 26)]+[(490, y) for y in range(200, 700, 26)]
    for x, y in bulbs:
        g.ellipse((x-9, y-9, x+9, y+9), fill=(*yellow, 140))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6*s)))
    for x, y in bulbs:
        d.ellipse((x-4, y-4, x+4, y+4), fill=(255, 250, 220, 255))
    cp._box(d, (66, 300, 474, 690), (8, 6, 10, 255), (200, 160, 80, 255), 2, 4)
    _screen(d, (8, 6, 10))
    # Seats in silhouette.
    for row, y in enumerate((800, 860, 920)):
        for x in range(-20+(row % 2)*28, 560, 56):
            d.rounded_rectangle((x, y, x+48, y+70), radius=14, fill=(20+row*6, 4, 10, 255))
    cp._label(im, 'SPETTACOLO ORE 21:00', 270, 760, 360, (*yellow,), 12, s)
    return im


# --- 20 Spazio 8-bit ------------------------------------------------------------

ALIEN = ('..XXXX..', '.XXXXXX.', 'XX.XX.XX', 'XXXXXXXX', '.X.XX.X.', 'X......X')


def _sprite(d, x, y, rows, color, px=4):
    for j, row in enumerate(rows):
        for i, c in enumerate(row):
            if c == 'X':
                d.rectangle((x+i*px, y+j*px, x+(i+1)*px-1, y+(j+1)*px-1), fill=(*color, 255))


def bg_spazio(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (26, 16, 70), (70, 26, 104), (36, 20, 84))
    # Nebula clouds.
    _layer(im, s, lambda q: (q.ellipse((-120, 300, 300, 760), fill=(*pink, 70)), q.ellipse((260, 520, 680, 980), fill=(*cyan, 60)),
                             q.ellipse((80, -80, 460, 260), fill=(120, 80, 255, 60))), 50)
    d = ScaledDraw(im, s)
    rnd = random.Random(20)
    for _ in range(220):
        x, y = rnd.randrange(0, 540), rnd.randrange(0, 960)
        r = rnd.choice((1, 1, 1, 2))
        d.rectangle((x, y, x+r, y+r), fill=(255, 255, 255, rnd.randrange(80, 255)))
    # A ringed pixel planet.
    d.ellipse((400, 40, 500, 140), fill=(*pink, 255))
    d.ellipse((418, 50, 470, 92), fill=(*[min(255, c+40) for c in pink], 255))
    d.line((370, 112, 530, 72), fill=(*yellow, 255), width=5)
    # Rows of original little aliens.
    for row, (y, col) in enumerate(((176, cyan), (212, pink), (248, yellow))):
        for k in range(7):
            _sprite(d, 60+k*62+(row % 2)*14, y, ALIEN, col)
    # HUD frame.
    cp._box(d, (56, 296, 484, 692), (4, 4, 18, 255), (*cyan, 255), 3, 10)
    for x, y, dx, dy in ((56, 296, 1, 1), (484, 296, -1, 1), (56, 692, 1, -1), (484, 692, -1, -1)):
        d.line((x, y+dy*30, x, y, x+dx*30, y), fill=(*yellow, 255), width=4)
    _screen(d, (4, 4, 18))
    cp._label(im, 'SCORE 0007', 140, 140, 180, (255, 255, 255), 12, s)
    cp._label(im, 'HI 9999', 300, 140, 140, (*cyan,), 12, s)
    # The ship and its laser.
    d.rectangle((268, 730, 272, 790), fill=(*yellow, 255))
    ship = ('....XX....', '...XXXX...', '..XXXXXX..', 'XXXXXXXXXX', 'XX.XXXX.XX')
    _sprite(d, 250, 800, ship, (240, 240, 255))
    d.rectangle((0, 880, 540, 884), fill=(*cyan, 255))
    cp._label(im, 'LIVES  > > >', 120, 912, 200, (*pink,), 11, s)
    cp._label(im, 'CALCIO A 7 / STAGE 7', 390, 912, 220, (255, 255, 255), 10, s)
    return im


# --- 21 Tabellone partenze --------------------------------------------------------

def _flaps(im, d, s, text, x, y, cell=19, color=(242, 242, 242)):
    cp = _cp()
    for i, ch in enumerate(text):
        cx = x+i*(cell+2)
        d.rectangle((cx, y, cx+cell, y+26), fill=(26, 26, 30, 255))
        if ch != ' ':
            cp._label(im, ch, cx+cell/2, y+13, cell, color, 13, s, 'CRT Scoreboard')
        d.line((cx, y+13, cx+cell, y+13), fill=(8, 8, 10, 255), width=1)


def bg_stazione(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (92, 104, 124), (58, 64, 78))
    _layer(im, s, lambda q: q.ellipse((-100, 700, 640, 1100), fill=(255, 236, 190, 60)), 60)
    d = ScaledDraw(im, s)
    for x in range(0, 540, 90):   # roof girders
        d.line((x, 0, x+45, 60), fill=(80, 90, 104, 255), width=3)
        d.line((x+90, 0, x+45, 60), fill=(80, 90, 104, 255), width=3)
    d.rectangle((0, 60, 540, 66), fill=(80, 90, 104, 255))
    # The board.
    cp._box(d, (20, 100, 520, 720), (10, 10, 12, 255), (90, 90, 96, 255), 4, 6)
    d.rectangle((30, 110, 510, 146), fill=(*yellow, 255))
    cp._label(im, 'PARTENZE', 120, 128, 160, (10, 10, 12), 16, s, 'CRT Scoreboard')
    cp._label(im, 'ORA   DESTINAZIONE   BIN', 360, 128, 280, (10, 10, 12), 9, s)
    _flaps(im, d, s, '21:00 FLAMINGOS    7', 40, 160, color=(*yellow,))
    _flaps(im, d, s, '21:30 TERZO TEMPO  1', 40, 194)
    _flaps(im, d, s, 'RITARDO 0 MINUTI    ', 40, 228, color=(*cyan,))
    d.rectangle((30, 262, 510, 266), fill=(40, 40, 46, 255))
    _screen(d, (14, 14, 16))
    # Station clock and the platform.
    cx, cy = 450, 790
    d.rectangle((cx-3, 720, cx+3, 750), fill=(70, 76, 88, 255))
    d.ellipse((cx-44, cy-44, cx+44, cy+44), fill=(250, 250, 250, 255), outline=(30, 30, 34, 255), width=5)
    for k in range(12):
        a = k*math.pi/6
        d.line((cx+36*math.sin(a), cy-36*math.cos(a), cx+30*math.sin(a), cy-30*math.cos(a)),
               fill=(30, 30, 34, 255), width=3)
    d.line((cx, cy, cx, cy-30), fill=(30, 30, 34, 255), width=4)          # 21:00
    d.line((cx, cy, cx-24, cy), fill=(30, 30, 34, 255), width=5)
    d.line((cx, cy, cx+20, cy+20), fill=(220, 30, 30, 255), width=2)
    d.ellipse((cx+16, cy+16, cx+24, cy+24), fill=(220, 30, 30, 255))
    d.rectangle((0, 860, 540, 960), fill=(110, 112, 118, 255))
    d.rectangle((0, 860, 540, 870), fill=(*yellow, 255))
    for x in range(0, 540, 40):
        d.rectangle((x, 870, x+20, 874), fill=(40, 40, 44, 255))
    cp._label(im, 'BINARIO 7', 140, 790, 200, (250, 250, 250), 20, s, 'CRT Scoreboard')
    return im


# --- 22 Prima pagina rosa ----------------------------------------------------------

def bg_giornale(pink, cyan, yellow, s):
    cp = _cp()
    paper = np.random.default_rng(22).integers(-6, 7, (960*s, 540*s, 1), dtype=np.int16)
    base = np.array((248, 214, 226), np.int16)+paper
    arr = np.concatenate([base.clip(0, 255).astype(np.uint8), np.full((960*s, 540*s, 1), 255, np.uint8)], axis=2)
    im = Image.fromarray(arr, 'RGBA')
    d = ScaledDraw(im, s)
    ink = (34, 22, 30)
    cp._label(im, 'IL FLAMINGO SPORTIVO', 270, 150, 500, ink, 26, s, 'CRT Scoreboard')
    d.rectangle((20, 178, 520, 181), fill=(*ink, 255))
    d.rectangle((20, 184, 520, 185), fill=(*ink, 255))
    cp._label(im, 'QUOTIDIANO DEL CALCIO A 7', 140, 197, 240, ink, 8, s)
    cp._label(im, 'EDIZIONE STRAORDINARIA', 400, 197, 220, (200, 40, 90), 8, s)
    d.rectangle((20, 208, 520, 210), fill=(*ink, 255))
    cp._label(im, 'ROSA, CHE SETTIMANA!', 270, 246, 500, ink, 22, s, 'CRT Scoreboard')
    rnd = random.Random(22)
    def column(x1, x2, y1, y2):
        for y in range(y1, y2, 9):
            end = x2 if rnd.random() > .15 else x1+(x2-x1)*rnd.uniform(.4, .8)
            d.rectangle((x1, y, end, y+3), fill=(*ink, 120))
    # The photo: thick border, then text columns below.
    d.rectangle((60, 292, 480, 694), fill=(*ink, 255))
    _screen(d, (20, 16, 22))
    cp._label(im, 'FOTO: LA SQUADRA IN CAMPO', 270, 708, 300, ink, 8, s)
    for x1, x2 in ((20, 180), (190, 350), (360, 520)):
        column(x1, x2, 726, 950)
    for x1, x2 in ((20, 52), (488, 520)):
        column(x1, x2, 292, 694)
    d.line((185, 726, 185, 950), fill=(*ink, 255), width=1)
    d.line((355, 726, 355, 950), fill=(*ink, 255), width=1)
    cp._label(im, 'LUN', 40, 60, 60, ink, 10, s)
    cp._label(im, 'EURO 0,00', 470, 60, 120, ink, 10, s)
    return im


# --- 23 Spiaggia vaporwave -----------------------------------------------------------

def _palm(d, x, y, h, color, lean=1):
    steps = int(h/8)
    for k in range(steps):   # a curved, ringed trunk
        bend = lean*18*(k/steps)**2
        d.rectangle((x+bend, y-k*8, x+bend+13, y-k*8+7), fill=color)
    top = (x+lean*18+6, y-h)
    for angle in (-170, -140, -110, -70, -40, -10, 150, 30):
        a = math.radians(angle)
        tip = (top[0]+62*math.cos(a), top[1]+62*math.sin(a)+20)
        mid = (top[0]+34*math.cos(a), top[1]+34*math.sin(a)-6)
        nx, ny = -math.sin(a)*7, math.cos(a)*7
        d.polygon([top, (mid[0]+nx, mid[1]+ny), tip, (mid[0]-nx, mid[1]-ny)], fill=color)


def bg_vaporwave(pink, cyan, yellow, s):
    cp = _cp()
    im = cp._gradient((540*s, 960*s), (255, 120, 200), (40, 210, 230), (150, 90, 220))
    d = ScaledDraw(im, s)
    # Striped sun, sea, palms.
    d.ellipse((150, 70, 390, 310), fill=(*yellow, 255))
    for i, y in enumerate(range(200, 310, 18)):
        d.rectangle((140, y, 400, y+3+i*2), fill=(255, 140, 200, 255))
    d.rectangle((0, 300, 540, 840), fill=(40, 180, 210, 255))
    for i, y in enumerate(range(304, 840, 10)):
        d.rectangle((0, y, 540, y+2), fill=(80, 220, 240, 255) if i % 2 else (30, 150, 190, 255))
    palms = ((-6, 860, 560, 1), (520, 860, 520, -1))
    # Checkerboard floor in perspective.
    d.rectangle((0, 840, 540, 960), fill=(20, 10, 40, 255))
    for j in range(6):
        y1 = 840+j*j*3.6
        y2 = 840+(j+1)*(j+1)*3.6
        for i in range(-10, 11):
            if (i+j) % 2 == 0:
                continue
            x1a, x2a = 270+i*40*(1+j*.4), 270+(i+1)*40*(1+j*.4)
            x1b, x2b = 270+i*40*(1+(j+1)*.4), 270+(i+1)*40*(1+(j+1)*.4)
            d.polygon([(x1a, y1), (x2a, y1), (x2b, y2), (x1b, y2)], fill=(*pink, 255))
    # An old desktop window around the screen.
    _layer(im, s, lambda q: q.rectangle((54, 274, 494, 712), fill=(20, 0, 40, 120)), 8)
    d.rectangle((46, 264, 486, 704), fill=(200, 200, 214, 255))
    d.rectangle((46, 264, 486, 268), fill=(255, 255, 255, 255))
    d.rectangle((46, 264, 50, 704), fill=(255, 255, 255, 255))
    d.rectangle((482, 264, 486, 704), fill=(90, 90, 110, 255))
    d.rectangle((46, 700, 486, 704), fill=(90, 90, 110, 255))
    d.rectangle((54, 272, 478, 296), fill=(120, 40, 200, 255))
    cp._label(im, 'FLAMINGOS.EXE', 140, 284, 160, (255, 255, 255), 10, s)
    for i, x in enumerate((420, 442, 464)):
        d.rectangle((x-9, 276, x+9, 292), fill=(200, 200, 214, 255), outline=(60, 60, 80, 255), width=1)
    d.line((457, 279, 471, 289), fill=(40, 40, 60, 255), width=2)
    d.line((471, 279, 457, 289), fill=(40, 40, 60, 255), width=2)
    _screen(d, (20, 10, 40))
    for x, y, h, lean in palms:   # in front of the window edges, never over the screen
        _palm(d, x, y, h, (40, 20, 60, 255), lean)
    cp._label(im, 'A E S T H E T I C   7', 270, 768, 420, (255, 255, 255), 13, s)
    return im


BUILDERS = {'tavolo': bg_tavolo, 'figurine': bg_figurine, 'radio': bg_radio, 'pc90': bg_pc90,
            'barsport': bg_barsport, 'flipper': bg_flipper, 'lcd': bg_lcd, 'cinema': bg_cinema,
            'spazio': bg_spazio, 'stazione': bg_stazione, 'giornale': bg_giornale, 'vaporwave': bg_vaporwave}

PRESETS = {
    'tavolo': dict(name='12 / Calcio da tavolo', object='Scatola del gioco',
                   description='Panno verde con le linee del campo, omini sulle basette e scatola di legno.',
                   pink='#FF6FB0', cyan='#7FE0FF', yellow='#FFE066', white='#FFFDF2', font='CRT Scoreboard'),
    'figurine': dict(name='13 / Album figurine', object='Figurina speciale',
                     description='Pagina dell\'album con le caselle numerate e la figurina lucida che si stacca.',
                     pink='#FF5FA6', cyan='#5BC8F5', yellow='#FFD23F', white='#FFFFFF', font='CRT Scoreboard'),
    'radio': dict(name='14 / Radiolina', object='Radio a valvole',
                  description='Radio di legno con la scala delle frequenze, manopole e carta da parati.',
                  pink='#FF8FB1', cyan='#9EE6D8', yellow='#FFC76B', white='#FFF4E2', font='CRT Terminal'),
    'pc90': dict(name='15 / PC anni 90', object='Monitor beige',
                 description='Monitor beige, schermo blu con il prompt, tastiera e post-it della partita.',
                 pink='#FF79C6', cyan='#55FFFF', yellow='#FFFF55', white='#FFFFFF', font='CRT Terminal'),
    'barsport': dict(name='16 / Bar Sport', object='Insegna al neon',
                     description='Muro di mattoni, insegna al neon rosa e il bancone con la sciarpa.',
                     pink='#FF4FA3', cyan='#3FF3FF', yellow='#FFE45C', white='#FFF6FA', font='CRT Scoreboard'),
    'flipper': dict(name='17 / Flipper', object='Flipper',
                    description='Vetro illuminato, display a punti arancioni, bumper e palette.',
                    pink='#FF5FA8', cyan='#61E8FF', yellow='#FFA21C', white='#FFE9D2', font='CRT Scoreboard'),
    'lcd': dict(name='18 / Gioco LCD', object='Gioco tascabile a cristalli liquidi',
                description='Piastra rossa spazzolata e schermo LCD chiaro con le scritte scure: il preset al contrario.',
                pink='#8C1F45', cyan='#22406A', yellow='#4A3300', white='#1C2016', font='CRT Scoreboard'),
    'cinema': dict(name='19 / Cinema', object='Insegna con le lampadine',
                   description='Sipario di velluto, insegna PRIMA VISIONE con le lampadine e le poltrone.',
                   pink='#FF6F9F', cyan='#8FE3FF', yellow='#FFD36E', white='#FFF8EC', font='CRT Terminal'),
    'spazio': dict(name='20 / Spazio 8-bit', object='Sparatutto spaziale',
                   description='Stelle, pianeta con l\'anello, alieni pixel in fila e la navicella che spara.',
                   pink='#FF5CC8', cyan='#5CF2FF', yellow='#FFF35C', white='#F4F7FF', font='CRT Scoreboard'),
    'stazione': dict(name='21 / Tabellone partenze', object='Tabellone a palette',
                     description='Tabellone della stazione con le palette, orologio sulle 21 e binario 7.',
                     pink='#FF7EB6', cyan='#7FD8FF', yellow='#FFD84A', white='#F2F2F2', font='CRT Scoreboard'),
    'giornale': dict(name='22 / Prima pagina', object='Quotidiano sportivo rosa',
                     description='Carta rosa, testata, titolone e colonne di testo intorno alla foto.',
                     pink='#FF5C9E', cyan='#6CC6F5', yellow='#FFC93C', white='#FFF7FA', font='CRT Terminal'),
    'vaporwave': dict(name='23 / Vaporwave', object='Finestra del desktop',
                      description='Sole a righe, mare, palme e pavimento a scacchi, dentro una vecchia finestra.',
                      pink='#FF71CE', cyan='#01CDFE', yellow='#FFFB96', white='#FFFFFF', font='CRT Terminal'),
}

STYLE = {
    'tavolo': dict(panel=(6, 34, 20), border=None, scan=None, veil=30),
    'figurine': dict(panel=(18, 22, 52), border=None, scan=None, veil=30),
    'radio': dict(panel=(22, 14, 10), border=(210, 170, 100), scan=(255, 199, 107), veil=30),
    'pc90': dict(panel=(10, 12, 110), border=(200, 200, 200), scan=(255, 255, 255), veil=0),
    'barsport': dict(panel=(10, 6, 16), border=None, scan=None, veil=30),
    'flipper': dict(panel=(12, 6, 2), border=(255, 140, 30), scan=(255, 140, 30), veil=0),
    'lcd': dict(panel=(196, 204, 170), border=(60, 64, 50), scan=(40, 44, 30), veil=0),
    'cinema': dict(panel=(8, 6, 10), border=(200, 160, 80), scan=None, veil=40),
    'spazio': dict(panel=(4, 4, 18), border=None, scan=None, veil=40),
    'stazione': dict(panel=(14, 14, 16), border=(90, 90, 96), scan=(255, 216, 74), veil=0),
    'giornale': dict(panel=(20, 16, 22), border=(255, 92, 158), scan=(255, 255, 255), veil=0),
    'vaporwave': dict(panel=(20, 10, 40), border=None, scan=None, veil=30),
}
