"""Instagram profile pictures and highlight covers, drawn in the Flamingos CRT style.

Everything stays inside the central circle Instagram shows (profile: 1080x1080,
covers: 1080x1920 with the icon in the middle circle).
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PINK = (242, 104, 168)
CYAN = (121, 220, 247)
INK = (16, 13, 22)
STYLES = {'neon': 'Neon CRT', 'synthwave': 'Synthwave', 'pixel': 'Stemma a pixel', 'rosa': 'Rosa pieno'}


def _gradient(size, top, bottom):
    w, h = size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    col = np.array(top, np.float32)+(np.array(bottom, np.float32)-np.array(top, np.float32))*t
    return Image.fromarray(np.repeat(col, w, axis=1).clip(0, 255).astype(np.uint8)).convert('RGBA')


def _crest(logo_bytes, height):
    from renderer import clean_logo
    crest = clean_logo(logo_bytes, 400, True, 1)
    k = height/crest.height
    return crest.resize((max(1, round(crest.width*k)), round(height)), Image.Resampling.LANCZOS)


def _glow(size, center, radius, color, alpha, blur):
    layer = Image.new('RGBA', size)
    ImageDraw.Draw(layer).ellipse((center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius),
                                  fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _scanlines(image, alpha=26, step=6):
    lines = Image.new('RGBA', image.size)
    d = ImageDraw.Draw(lines)
    for y in range(0, image.height, step):
        d.line((0, y, image.width, y), fill=(0, 0, 0, alpha), width=2)
    image.alpha_composite(lines)


def _ring(image, center, radius, color, width, blur):
    ring = Image.new('RGBA', image.size)
    d = ImageDraw.Draw(ring)
    box = (center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius)
    d.ellipse(box, outline=(*color, 255), width=width)
    image.alpha_composite(ring.filter(ImageFilter.GaussianBlur(blur)))
    image.alpha_composite(ring)


def _pixelate(img, cells):
    small = img.resize((cells, max(1, round(cells*img.height/img.width))), Image.Resampling.BOX)
    arr = np.array(small)
    arr[..., 3] = np.where(arr[..., 3] > 110, 255, 0)
    return Image.fromarray(arr, 'RGBA').resize(img.size, Image.Resampling.NEAREST)


def profile_picture(logo_bytes, style='neon', size=1080):
    s = size
    c = (s//2, s//2)
    if style == 'synthwave':
        im = _gradient((s, s), (24, 8, 52), (110, 24, 100))
        stars = Image.new('RGBA', (s, s))
        d = ImageDraw.Draw(stars)
        rnd = random.Random(4)
        for _ in range(120):
            x, y = rnd.randrange(s), rnd.randrange(int(s*.6))
            r = rnd.choice((1, 1, 2, 3))
            d.rectangle((x, y, x+r, y+r), fill=(255, 255, 255, rnd.randrange(80, 230)))
        im.alpha_composite(stars)
        sun = Image.new('RGBA', (s, s))
        sd = ImageDraw.Draw(sun)
        sd.ellipse((s*.22, s*.30, s*.78, s*.86), fill=(255, 200, 90, 255))
        for i, y in enumerate(range(int(s*.62), int(s*.86), int(s*.035))):
            sd.rectangle((0, y, s, y+6+i*2), fill=(0, 0, 0, 0))
        im.alpha_composite(_glow((s, s), (s//2, int(s*.58)), int(s*.3), (255, 120, 160), 120, s*.06))
        im.alpha_composite(sun)
        floor = Image.new('RGBA', (s, s))
        fd = ImageDraw.Draw(floor)
        horizon = int(s*.74)
        fd.rectangle((0, horizon, s, s), fill=(20, 6, 36, 255))
        for i in range(10):
            y = horizon+i*i*3.2
            fd.line((0, y, s, y), fill=(*PINK, 200), width=3)
        for x in range(-s, 2*s, s//9):
            fd.line((s//2, horizon, x, s), fill=(*PINK, 170), width=3)
        im.alpha_composite(floor)
        crest = _crest(logo_bytes, s*.58)
        im.alpha_composite(_glow((s, s), c, int(s*.27), (0, 0, 0), 150, s*.03))
        im.alpha_composite(crest, (c[0]-crest.width//2, int(s*.18)))
        _scanlines(im, 20)
    elif style == 'pixel':
        im = _gradient((s, s), (34, 18, 48), (16, 12, 24))
        checks = Image.new('RGBA', (s, s))
        cd = ImageDraw.Draw(checks)
        cell = s//36
        for y in range(0, s, cell):
            for x in range(0, s, cell):
                if (x//cell+y//cell) % 2 == 0:
                    cd.rectangle((x, y, x+cell-1, y+cell-1), fill=(255, 255, 255, 10))
        im.alpha_composite(checks)
        d = ImageDraw.Draw(im)
        im.alpha_composite(_glow((s, s), c, int(s*.33), PINK, 90, s*.08))
        crest = _pixelate(_crest(logo_bytes, s*.64), 52)
        im.alpha_composite(crest, (c[0]-crest.width//2, c[1]-crest.height//2))
        for i in range(48):  # pixel ring of alternating squares
            a = i/48*math.tau
            x, y = c[0]+math.cos(a)*s*.45, c[1]+math.sin(a)*s*.45
            col = PINK if i % 2 else CYAN
            d.rectangle((x-cell*.6, y-cell*.6, x+cell*.6, y+cell*.6), fill=(*col, 255))
    elif style == 'rosa':
        im = Image.new('RGBA', (s, s), (*PINK, 255))
        d = ImageDraw.Draw(im)
        cell = s//60
        for y in range(0, s, cell):  # dithered dark edge, light centre
            for x in range(0, s, cell):
                r = math.hypot(x-c[0], y-c[1])/(s*.5)
                if r > .78 and ((x//cell)+(y//cell)) % (2 if r > .9 else 3) == 0:
                    d.rectangle((x, y, x+cell-1, y+cell-1), fill=(*INK, 255))
        crest = _crest(logo_bytes, s*.66)
        outline = Image.new('RGBA', crest.size)
        outline.putalpha(crest.getchannel('A').filter(ImageFilter.MaxFilter(15)))
        white = Image.new('RGBA', crest.size, (255, 255, 255, 255))
        white.putalpha(outline.getchannel('A'))
        im.alpha_composite(white, (c[0]-crest.width//2, c[1]-crest.height//2))
        im.alpha_composite(crest, (c[0]-crest.width//2, c[1]-crest.height//2))
    else:  # neon CRT
        im = _gradient((s, s), (26, 14, 38), (12, 8, 18))
        im.alpha_composite(_glow((s, s), c, int(s*.36), PINK, 110, s*.09))
        im.alpha_composite(_glow((s, s), c, int(s*.2), CYAN, 50, s*.08))
        _ring(im, c, int(s*.44), PINK, 10, 14)
        _ring(im, c, int(s*.405), CYAN, 4, 8)
        crest = _crest(logo_bytes, s*.6)
        im.alpha_composite(crest, (c[0]-crest.width//2, c[1]-crest.height//2+6))
        _scanlines(im)
        vignette = Image.new('L', (s, s), 0)
        ImageDraw.Draw(vignette).ellipse((-s*.1, -s*.1, s*1.1, s*1.1), fill=255)
        dark = Image.new('RGBA', (s, s), (0, 0, 0, 160))
        dark.putalpha(Image.eval(vignette.filter(ImageFilter.GaussianBlur(s*.08)), lambda v: 160-v*160//255))
        im.alpha_composite(dark)
    return im.convert('RGB')


def circle_preview(image, size=360):
    """How Instagram shows it: a circle."""
    small = image.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size-1, size-1), fill=255)
    out = Image.new('RGBA', (size, size))
    out.paste(small, (0, 0), mask)
    return out


# --- Highlight covers ----------------------------------------------------------
# Pixel icons: X outline, w white, B dark, P pink, C cyan, Y yellow, G green, R red.

ICONS = {
    'partite': ('PARTITE', [
        '.....XXXXXX.....', '...XXwwwwwwXX...', '..XwwwwBBwwwwX..', '.XwwwwBBBBwwwwX.', '.XwwwwwBBwwwwwX.',
        'XwBBwwwwwwwwBBwX', 'XwBBBwwwwwwBBBwX', 'XwwBwwwBBwwwBwwX', 'XwwwwwBBBBwwwwwX', 'XwwwwwwBBwwwwwwX',
        'XwBBwwwwwwwwBBwX', '.XBBBwwwwwwBBBX.', '.XwBwwwBBwwwBwX.', '..XwwwBBBBwwwX..', '...XXwwBBwwXX...', '.....XXXXXX.....']),
    'risultati': ('RISULTATI', [
        'XXXXXXXXXXXXXXXX', 'XBBBBBBBBBBBBBBX', 'XBYYYBBBBBBYYYBX', 'XBBBYBBBBBBBBYBX', 'XBYYYBBYYBBBYYBX',
        'XBYBBBBBBBBBBYBX', 'XBYYYBBBBBBYYYBX', 'XBBBBBBBBBBBBBBX', 'XXXXXXXXXXXXXXXX', '.....XX..XX.....',
        '.....XX..XX.....', '....XXXXXXXX....']),
    'rosa': ('ROSA', [
        '...XXX....XXX...', '..XPPPXXXXPPPX..', '.XPPPPPwwPPPPPX.', 'XPPPPPPwwPPPPPPX', 'XPPXPPPPPPPPXPPX',
        '.XX.XPPPPPPX.XX.', '....XPPwwPPX....', '....XPwPPwPX....', '....XPPPwPPX....', '....XPPwPPPX....',
        '....XPwwwwPX....', '....XXXXXXXX....']),
    'classifica': ('CLASSIFICA', [
        '..XXXXXXXXXXXX..', 'XXXYYYYYYYYYYXXX', 'X.XYYYYYYYYYYX.X', 'X.XYYwYYYYYYYX.X', '.XXYYwYYYYYYYXX.',
        '...XYYYYYYYYX...', '....XYYYYYYX....', '.....XYYYYX.....', '......XYYX......', '......XYYX......',
        '.....XYYYYX.....', '....XXXXXXXX....', '....XPPPPPPX....', '....XXXXXXXX....']),
    'calendario': ('CALENDARIO', [
        '..XX......XX....', 'XXXXXXXXXXXXXXXX', 'XPPPPPPPPPPPPPPX', 'XPPPPPPPPPPPPPPX', 'XXXXXXXXXXXXXXXX',
        'XwwwwwwwwwwwwwwX', 'XwBwwBwwBwwBwwwX', 'XwwwwwwwwwwwwwwX', 'XwBwwBwwPPwBwwwX', 'XwwwwwwwPPwwwwwX',
        'XwBwwBwwBwwBwwwX', 'XwwwwwwwwwwwwwwX', 'XXXXXXXXXXXXXXXX']),
    'matchday': ('MATCHDAY', [
        '.....X....X.....', '......X..X......', 'XXXXXXXXXXXXXXXX', 'XwwwwwwwwwwwwwwX', 'XwCCCCCCCCCCwPwX',
        'XwCCCCCCCCCCwwwX', 'XwCCPPCCCCCCwPwX', 'XwCCCCCCCCCCwwwX', 'XwCCCCCCCCCCwwwX', 'XwwwwwwwwwwwwwwX',
        'XXXXXXXXXXXXXXXX', '..XX........XX..']),
    'allenamenti': ('ALLENAMENTI', [
        '........XXXX....', '.......XCCCCX...', '..XXXXXXCCCCX...', '.XwwwwwwXCCX....', 'XwwwwwwwwXX.....',
        'XwwBBwwwwwX.....', 'XwwBBwwwwwX.....', 'XwwwwwwwwwX.....', '.XwwwwwwwX......', '..XXXXXXX.......']),
    'foto': ('FOTO', [
        '....XXXX........', 'XXXXwwwwXXXXXXXX', 'XPPPPPPPPPPPPPPX', 'XPPPXXXXXXPPPwPX', 'XPPXCCCCCCXPPPPX',
        'XPPXCwCCCCXPPPPX', 'XPPXCCCCCCXPPPPX', 'XPPXCCCCCCXPPPPX', 'XPPPXXXXXXPPPPPX', 'XPPPPPPPPPPPPPPX',
        'XXXXXXXXXXXXXXXX']),
    'sponsor': ('SPONSOR', [
        '.......XX.......', '......XYYX......', '......XYYX......', '.....XYYYYX.....', 'XXXXXXYYYYXXXXXX',
        'XYYYYYYYYYYYYYYX', '.XYYYYYYYYYYYYX.', '..XYYYYYYYYYYX..', '...XYYYYYYYYX...', '...XYYYYYYYYX...',
        '..XYYYYXXYYYYX..', '..XYYYX..XYYYX..', '.XYYX......XYYX.', '.XXX........XXX.']),
    'stemma': ('FLAMINGOS', None),
}
ICON_COLORS = {'X': INK, 'w': (246, 244, 252), 'B': (40, 34, 52), 'P': PINK, 'C': CYAN, 'Y': (255, 201, 99),
               'G': (91, 230, 164), 'R': (255, 96, 110)}


def icon_image(name, pixel):
    rows = ICONS[name][1]
    width = max(len(r) for r in rows)
    img = Image.new('RGBA', (width*pixel, len(rows)*pixel))
    d = ImageDraw.Draw(img)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row.ljust(width, '.')):
            if ch in ICON_COLORS:
                d.rectangle((x*pixel, y*pixel, (x+1)*pixel-1, (y+1)*pixel-1), fill=(*ICON_COLORS[ch], 255))
    return img


def _cover_background(style, size):
    w, h = size
    if style == 'synthwave':
        return _gradient(size, (24, 8, 52), (110, 24, 100))
    if style == 'rosa':
        return Image.new('RGBA', size, (*PINK, 255))
    if style == 'pixel':
        im = _gradient(size, (34, 18, 48), (16, 12, 24))
        checks = Image.new('RGBA', size)
        d = ImageDraw.Draw(checks)
        cell = w//36
        for y in range(0, h, cell):
            for x in range(0, w, cell):
                if (x//cell+y//cell) % 2 == 0:
                    d.rectangle((x, y, x+cell-1, y+cell-1), fill=(255, 255, 255, 10))
        im.alpha_composite(checks)
        return im
    return _gradient(size, (26, 14, 38), (12, 8, 18))


def highlight_cover(name, style='neon', logo_bytes=None, label=True, size=(1080, 1920)):
    """A story-sized cover; Instagram shows the circle in the middle."""
    w, h = size
    c = (w//2, h//2)
    im = _cover_background(style, size)
    disc = int(w*.36)
    if style == 'rosa':
        d = ImageDraw.Draw(im)
        d.ellipse((c[0]-disc, c[1]-disc, c[0]+disc, c[1]+disc), fill=(*INK, 255))
    else:
        im.alpha_composite(_glow(size, c, disc, PINK if style != 'synthwave' else (255, 150, 120), 90, w*.06))
        disc_layer = Image.new('RGBA', size)
        ImageDraw.Draw(disc_layer).ellipse((c[0]-disc, c[1]-disc, c[0]+disc, c[1]+disc), fill=(14, 10, 22, 235))
        im.alpha_composite(disc_layer)
        _ring(im, c, disc, PINK if style != 'pixel' else CYAN, 8, 10)
    title, rows = ICONS[name]
    if rows is None:
        art = _crest(logo_bytes, disc*1.25) if logo_bytes else None
        if style == 'pixel' and art is not None:
            art = _pixelate(art, 40)
    else:
        pixel = int(disc*1.3/max(len(rows), max(len(r) for r in rows)))
        art = icon_image(name, pixel)
    if art is not None:
        dy = -int(disc*.14) if label else 0
        im.alpha_composite(art, (c[0]-art.width//2, c[1]-art.height//2+dy))
    if label:
        from pixel_fonts import pixel_text_runs
        scale = max(1, round(w/540))
        text = pixel_text_runs([(title, (246, 244, 252) if style != 'rosa' else (246, 244, 252))], 'CRT Scoreboard',
                               22 if len(title) <= 8 else 17, 300, scale)
        if text:
            im.alpha_composite(text, (c[0]-text.width//2, c[1]+int(disc*.66)-text.height//2))
    if style in ('neon', 'synthwave'):
        _scanlines(im, 18)
    return im.convert('RGB')
