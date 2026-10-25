"""Seasonal CRT art direction: eleven distinct, code-drawn retro worlds.

Every preset only changes the art direction (frame, background, panels and
palette). Match data, assets, fonts and positions always stay the user's.
The shared screen area is 78-462 x 316-674 in 540x960 layout units, so all
editors keep working on every preset.
"""
from __future__ import annotations

import copy
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from render_utils import ScaledDraw, checked_scale

PRESETS = {
    'crt': dict(name='01 / TV CRT originale', object='Televisore Matchday',
                description='La tele originale del Matchday, ora piu luminosa per il feed.',
                pink='#F268A8', cyan='#79DCF7', yellow='#FFC963', white='#F6F4FC', font='CRT Terminal'),
    'handheld': dict(name='02 / Console portatile', object='Console 8-bit',
                description='Scocca lilla su sfondo pastello a righe diagonali.',
                pink='#F6A6D6', cyan='#BEACFF', yellow='#D6FF91', white='#FAF4FF', font='CRT Scoreboard'),
    'cassette': dict(name='03 / Mixtape', object='Musicassetta',
                description='Nastro e bobine su fondo corallo caldo a bande.',
                pink='#FF8EAF', cyan='#FFBC98', yellow='#FFE08A', white='#FFF5EC', font='CRT Terminal'),
    'arcade': dict(name='04 / Arcade club', object='Cabinato arcade',
                description='Cabinato su notte synthwave, stelle e griglia al neon.',
                pink='#FF89CC', cyan='#83E8FF', yellow='#FFF083', white='#FBF8E9', font='CRT Scoreboard'),
    'floppy': dict(name='05 / Save the game', object='Floppy disk',
                description='Floppy turchese su carta millimetrata digitale.',
                pink='#FFAECF', cyan='#83E6CD', yellow='#C7FF9A', white='#EEFFF9', font='CRT Terminal'),
    'tactics': dict(name='06 / Tactics board', object='Lavagna tattica',
                description='Lavagna magnetica appoggiata sul prato a strisce.',
                pink='#FFB1CE', cyan='#A6EAA3', yellow='#FFE58C', white='#F6FFF1', font='CRT Scoreboard'),
    'vhs': dict(name='07 / VHS Play', object='Videoregistratore',
                description='Il blu del videoregistratore, scritte PLAY e disturbi di tracking.',
                pink='#FF8AD0', cyan='#A8EEFF', yellow='#FFF27A', white='#FFFFFF', font='CRT Terminal'),
    'teletext': dict(name='08 / Televideo', object='Pagina Televideo',
                description='Pagina 101: blocchi a mosaico e i quattro tasti colorati.',
                pink='#FF5CE1', cyan='#45F4FF', yellow='#FFF545', white='#FFFFFF', font='CRT Terminal'),
    'gameboy': dict(name='09 / Pocket verde', object='Console tascabile',
                description='Scocca grigio chiaro e schermo a quattro toni di verde.',
                pink='#E2F59B', cyan='#BCDD5E', yellow='#F6FFD6', white='#F6FFD6', font='CRT Scoreboard'),
    'stadium': dict(name='10 / Tabellone stadio', object='Tabellone LED',
                description='Tabellone in acciaio, LED ambra e riflettori accesi.',
                pink='#FF74AC', cyan='#86E6FF', yellow='#FFB524', white='#FFEBC7', font='CRT Scoreboard'),
    'poster': dict(name='11 / Poster riso', object='Poster stampato',
                description='Carta crema, retini e inchiostri sfalsati: il preset chiaro.',
                pink='#FF82B5', cyan='#88DBFF', yellow='#FFDA55', white='#FFF7E8', font='CRT Terminal'),
}
PRESET_IDS = tuple(PRESETS)
FORMATS = ('Post 1:1', 'Post 4:5', 'Story 9:16')
CROPS = {'Post 1:1': (0, 210, 540, 750), 'Post 4:5': (0, 142.5, 540, 817.5), 'Story 9:16': None}
DEFAULT_BRIGHTNESS = 55

# Panel fill / border and scanline tint for each world. None = use the palette cyan.
STYLE = {
    'crt': dict(panel=(5, 13, 31), border=None, scan=None, veil=165),
    'handheld': dict(panel=(14, 10, 34), border=None, scan=None, veil=30),
    'cassette': dict(panel=(30, 10, 16), border=None, scan=None, veil=30),
    'arcade': dict(panel=(12, 6, 30), border=None, scan=None, veil=30),
    'floppy': dict(panel=(4, 24, 28), border=None, scan=None, veil=30),
    'tactics': dict(panel=(8, 30, 20), border=None, scan=None, veil=30),
    'vhs': dict(panel=(10, 22, 112), border=(236, 242, 255), scan=(200, 220, 255), veil=0),
    'teletext': dict(panel=(6, 6, 22), border=(69, 244, 255), scan=(255, 255, 255), veil=0),
    'gameboy': dict(panel=(15, 56, 15), border=(155, 188, 15), scan=(155, 188, 15), veil=0),
    'stadium': dict(panel=(10, 9, 8), border=(255, 181, 36), scan=(255, 181, 36), veil=0),
    'poster': dict(panel=(22, 28, 66), border=(255, 130, 181), scan=(136, 219, 255), veil=0),
}

PANEL_LAYOUTS = {
    'matchday': ((115, 322, 425, 394), (91, 559, 242, 600), (297, 559, 449, 600), (93, 608, 448, 672)),
    'fulltime': ((107, 324, 433, 390), (91, 503, 237, 539), (303, 503, 449, 539), (87, 577, 453, 673)),
    'fulltime_clean': ((107, 324, 433, 390), (91, 503, 237, 539), (303, 503, 449, 539)),
    'convocati': ((84, 321, 456, 388), (84, 621, 456, 673)),
    'classifica': ((84, 321, 456, 372), (84, 380, 456, 673)),
}


def preset_for_round(round_number):
    try:
        value = max(1, int(round_number))
    except (TypeError, ValueError, OverflowError):
        value = 1
    return PRESET_IDS[(value-1) % len(PRESET_IDS)]


def apply_preset(config, preset_id, typography=False):
    """Only art direction changes: never overwrite match data, assets or positions."""
    selected = preset_id if preset_id in PRESETS else 'crt'
    output = copy.deepcopy(config)
    output['preset_id'] = selected
    output.update({key: PRESETS[selected][key] for key in ('pink', 'cyan', 'yellow', 'white')})
    if typography:
        output['font_choice'] = PRESETS[selected]['font']
        output['text_style'] = output['font_choice']
    return output


def _rgb(value):
    return tuple(bytes.fromhex(value.lstrip('#')))


def _mix(a, b, amount):
    return tuple(round(x+(y-x)*amount) for x, y in zip(a, b))


def _box(d, xy, fill, border, thickness=2, bevel=5):
    x1,y1,x2,y2 = xy
    points = [(x1+bevel,y1),(x2-bevel,y1),(x2,y1+bevel),(x2,y2-bevel),
              (x2-bevel,y2),(x1+bevel,y2),(x1,y2-bevel),(x1,y1+bevel)]
    d.polygon(points, fill=border)
    n=thickness
    inner=[(x1+bevel,y1+n),(x2-bevel,y1+n),(x2-n,y1+bevel),(x2-n,y2-bevel),
           (x2-bevel,y2-n),(x1+bevel,y2-n),(x1+n,y2-bevel),(x1+n,y1+bevel)]
    d.polygon(inner, fill=fill)


def _label(im, value, x, y, width, color, size=11, scale=1, style='CRT Terminal'):
    from pixel_fonts import pixel_text_runs
    label = pixel_text_runs([(value,color)], style, size, width, scale)
    if label:
        im.alpha_composite(label,(round(x*scale-label.width/2),round(y*scale-label.height/2)))


def _gradient(size, top, bottom, middle=None):
    """Vertical RGBA gradient built with NumPy, at output resolution."""
    w, h = size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    a, b = np.array(top, np.float32), np.array(bottom, np.float32)
    if middle is None:
        col = a+(b-a)*t
    else:
        m = np.array(middle, np.float32)
        col = np.where(t < .5, a+(m-a)*(t*2), m+(b-m)*((t-.5)*2))
    rgb = np.repeat(col[:, None, :], w, axis=1).clip(0, 255).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), 'RGBA')


def _lift(image, amount):
    """Instagram-safe shadow lift: a gamma curve that opens up near-black areas
    (the feed's compression crushes them) without clipping the highlights."""
    if amount <= 0:
        return image
    arr = np.asarray(image).astype(np.float32)
    gamma = 1/(1+1.25*amount)
    arr[..., :3] = 255*np.power(arr[..., :3]/255, gamma)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')


def _pixel_hardware(preset_id, pink, cyan, yellow, s):
    # Design on a real coarse grid; only the original hardware art is enlarged.
    art = Image.new('RGBA',(180,320))
    d=ScaledDraw(art,1/3)
    edge=(*cyan,255); dark=(13,16,28,255); ink=(4,10,22,255)
    body=(*_mix(cyan,(16,16,29),.70),255)
    muted=(*_mix(cyan,(16,16,29),.45),255)
    bright=(*pink,255)
    if preset_id=='handheld':
        _box(d,(31,230,509,738),body,edge,5,18)
        d.rectangle((46,243,493,296),fill=muted)
        d.rectangle((61,251,479,286),fill=ink)
        d.rectangle((78,699,129,716),fill=ink); d.rectangle((96,682,112,731),fill=ink)
        d.rectangle((383,692,404,713),fill=bright);d.rectangle((431,679,452,700),fill=(*yellow,255))
        d.rectangle((242,706,266,712),fill=edge); d.rectangle((284,706,308,712),fill=edge)
        for x in (362,374,386):d.rectangle((x,719,x+5,729),fill=muted)
    elif preset_id=='cassette':
        _box(d,(28,233,512,737),body,edge,5,15)
        for x in (43,490):
            for y in (248,714):d.rectangle((x,y,x+6,y+6),fill=edge)
        d.rectangle((67,251,471,291),fill=bright)
        d.rectangle((73,257,465,285),fill=ink)
        d.rectangle((67,686,471,727),fill=ink)
        for x in (167,373):
            d.ellipse((x-29,681,x+29,730),fill=muted,outline=edge,width=4)
            d.rectangle((x-8,694,x+8,713),fill=ink)
        d.rectangle((204,698,336,713),fill=muted)
        d.rectangle((227,704,313,708),fill=(*pink,255))
    elif preset_id=='arcade':
        d.polygon([(74,233),(466,233),(505,287),(501,678),(521,717),(494,739),
                   (46,739),(19,717),(39,678),(35,287)], fill=body)
        d.line((74,235,466,235,504,287,500,678,520,717,494,737,46,737,20,717,40,678,36,287,74,235),fill=edge,width=5)
        _box(d,(71,247,469,289),ink,(*yellow,255),3,6)
        for x in range(46,64,6):d.rectangle((x,325,x+2,654),fill=bright)
        for x in range(478,496,6):d.rectangle((x,325,x+2,654),fill=bright)
        d.polygon([(44,681),(496,681),(510,718),(30,718)],fill=muted)
        d.rectangle((132,695,175,704),fill=ink);d.rectangle((151,681,157,698),fill=edge)
        d.rectangle((142,678,166,688),fill=(*yellow,255))
        for x,y,col in ((348,696,bright),(392,690,edge),(434,699,(*yellow,255))):
            d.rectangle((x,y,x+16,y+9),fill=col)
    elif preset_id=='floppy':
        d.polygon([(35,234),(475,234),(508,267),(508,737),(32,737),(32,234)],fill=body)
        d.line((36,235,475,235,507,267,507,735,33,735,33,235),fill=edge,width=5)
        d.rectangle((91,239,415,298),fill=muted)
        d.rectangle((292,246,371,287),fill=ink)
        d.rectangle((106,251,251,257),fill=edge)
        d.rectangle((111,694,429,737),fill=muted)
        d.rectangle((131,705,310,720),fill=ink)
        d.rectangle((47,702,67,722),fill=ink);d.rectangle((473,702,493,722),fill=ink)
    else:  # magnetic tactics board
        _box(d,(33,257,507,737),(16,39,31,255),edge,6,12)
        _box(d,(190,230,350,292),body,(*yellow,255),4,9)
        d.rectangle((210,246,330,257),fill=ink)
        d.rectangle((218,235,322,242),fill=(*yellow,255))
        d.line((73,710,464,710),fill=(*cyan,160),width=2)
        for x,y,col in ((98,710,bright),(161,699,edge),(217,716,bright),(283,700,edge),(343,715,bright),(404,699,edge),(456,716,bright)):
            d.rectangle((x-5,y-5,x+5,y+5),fill=col)
    _box(d,(68,306,472,682),ink,edge,4,12)
    d.rectangle((77,315,463,673),fill=(5,14,27,255))
    return art.resize((540*s,960*s),Image.Resampling.NEAREST)




# --- Backgrounds -----------------------------------------------------------
# Each builder returns the full-frame art at scale s, before brightness, screen
# veil, scanlines and text panels are added by _background().

def _glow_lines(im, pink, cyan, s, ellipse=True):
    glow = Image.new('RGBA', im.size)
    gd = ScaledDraw(glow, s)
    if ellipse:
        gd.ellipse((60, 250, 480, 709), fill=(*cyan, 38))
    gd.line((90, 187, 450, 187), fill=(*cyan, 115), width=3)
    gd.line((90, 774, 450, 774), fill=(*pink, 105), width=3)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(25*s)))


def _bg_crt(pink, cyan, yellow, s):
    from matchday_renderer import _shell
    sh = _shell()
    dark = sh.resize((540*s, 960*s), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(50*s))
    im = ImageEnhance.Brightness(dark).enhance(.44).convert('RGBA')
    _glow_lines(im, pink, cyan, s)
    tv = sh.resize((520*s, 520*s), Image.Resampling.LANCZOS)
    tv = ImageEnhance.Contrast(ImageEnhance.Brightness(tv).enhance(1.12)).enhance(1.06).convert('RGBA')
    im.alpha_composite(tv, (10*s, 220*s))
    return im


def _pattern(preset_id, pink, cyan, yellow, s):
    """A different world behind each of the original hardware objects."""
    size = (540*s, 960*s)
    if preset_id == 'handheld':
        im = _gradient(size, _mix(cyan, (22, 14, 44), .45), _mix(pink, (30, 14, 40), .55))
        layer = Image.new('RGBA', size); d = ScaledDraw(layer, s)
        for x in range(-960, 540, 34):
            d.line((x, 960, x+960, 0), fill=(255, 255, 255, 26), width=9)
        im.alpha_composite(layer)
    elif preset_id == 'cassette':
        im = _gradient(size, _mix(pink, (40, 12, 22), .40), _mix(cyan, (46, 18, 16), .50))
        layer = Image.new('RGBA', size); d = ScaledDraw(layer, s)
        for i, y in enumerate(range(40, 960, 46)):
            d.rectangle((0, y, 540, y+12), fill=(*(yellow if i % 2 else pink), 46))
        im.alpha_composite(layer)
    elif preset_id == 'arcade':
        im = _gradient(size, (20, 8, 46), (88, 22, 96), (44, 12, 70))
        layer = Image.new('RGBA', size); d = ScaledDraw(layer, s)
        rnd = random.Random(4)
        for _ in range(140):
            x, y = rnd.randrange(0, 540), rnd.randrange(0, 760)
            r = rnd.choice((1, 1, 1.5, 2))
            d.rectangle((x, y, x+r, y+r), fill=(255, 255, 255, rnd.randrange(90, 230)))
        # Synthwave sun and perspective floor.
        d.ellipse((150, 650, 390, 890), fill=(*yellow, 70))
        for y in (720, 740, 760, 780):
            d.rectangle((150, y, 390, y+6), fill=(88, 22, 96, 255))
        d.rectangle((0, 800, 540, 960), fill=(18, 6, 34, 255))
        for i in range(9):
            d.line((0, 800+i*i*2.2, 540, 800+i*i*2.2), fill=(*pink, 150), width=1.4)
        for x in range(-600, 1141, 60):
            d.line((270, 800, x, 960), fill=(*pink, 130), width=1.2)
        im.alpha_composite(layer)
    elif preset_id == 'floppy':
        im = _gradient(size, _mix(cyan, (6, 40, 44), .42), _mix(cyan, (4, 26, 34), .70))
        layer = Image.new('RGBA', size); d = ScaledDraw(layer, s)
        for x in range(0, 541, 18):
            d.line((x, 0, x, 960), fill=(255, 255, 255, 40 if x % 90 == 0 else 16), width=1)
        for y in range(0, 961, 18):
            d.line((0, y, 540, y), fill=(255, 255, 255, 40 if y % 90 == 0 else 16), width=1)
        im.alpha_composite(layer)
    else:  # tactics: a mowed pitch under the board
        im = Image.new('RGBA', size, (34, 112, 60, 255))
        layer = Image.new('RGBA', size); d = ScaledDraw(layer, s)
        for i, y in enumerate(range(0, 960, 64)):
            if i % 2:
                d.rectangle((0, y, 540, y+64), fill=(44, 132, 72, 255))
        line = (240, 255, 240, 150)
        d.rectangle((20, 20, 520, 940), outline=line, width=3)
        d.line((20, 480, 520, 480), fill=line, width=3)
        d.ellipse((190, 400, 350, 560), outline=line, width=3)
        d.rectangle((150, 20, 390, 120), outline=line, width=3)
        d.rectangle((150, 840, 390, 940), outline=line, width=3)
        im.alpha_composite(layer)
    return im


def _bg_legacy(preset_id, pink, cyan, yellow, s):
    im = _pattern(preset_id, pink, cyan, yellow, s)
    _glow_lines(im, pink, cyan, s)
    shadow = Image.new('RGBA', im.size)
    ScaledDraw(shadow, s).rectangle((40, 248, 512, 752), fill=(0, 0, 0, 120))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14*s)))
    im.alpha_composite(_pixel_hardware(preset_id, pink, cyan, yellow, s))
    labels = {'arcade': ('FLAMINGOS / ARCADE', 270, 271, 320, 10),
              'handheld': ('7-A-SIDE / PLAYER ONE', 270, 269, 380, 10),
              'cassette': ('SIDE A / MATCH TAPE', 270, 271, 340, 10),
              'floppy': ('SAVE GAME', 183, 275, 174, 9),
              'tactics': ('TACTICS', 270, 277, 140, 10)}
    label, x, y, width, size = labels[preset_id]
    _label(im, label, x, y, width, yellow, size, s)
    _label(im, 'CALCIO A 7', 270, 185, 390, (255, 255, 255), 11, s)
    _label(im, 'PRESS START / PLAY TOGETHER', 270, 777, 420, (255, 255, 255), 10, s)
    return im


def _noise_band(d, y1, y2, rnd, color, density=.35):
    for y in range(y1, y2, 2):
        x = 0
        while x < 540:
            run = rnd.randrange(4, 40)
            if rnd.random() < density:
                d.rectangle((x, y, x+run, y+1), fill=(*color, rnd.randrange(60, 200)))
            x += run


def _bg_vhs(pink, cyan, yellow, s):
    size = (540*s, 960*s)
    im = _gradient(size, (34, 62, 214), (14, 30, 140), (26, 50, 190))
    d = ScaledDraw(im, s)
    rnd = random.Random(7)
    _noise_band(d, 892, 920, rnd, (230, 236, 255), .45)
    _noise_band(d, 60, 72, rnd, (230, 236, 255), .25)
    _noise_band(d, 742, 750, rnd, (230, 236, 255), .3)
    # Screen inset with a soft bezel.
    _box(d, (64, 300, 476, 690), (10, 22, 120, 255), (190, 206, 255, 255), 3, 10)
    d.rectangle((77, 315, 463, 673), fill=(16, 34, 150, 255))
    white = (255, 255, 255)
    _label(im, 'PLAY  >', 112, 252, 160, white, 18, s)
    _label(im, 'SP', 448, 252, 60, white, 18, s)
    _label(im, 'CH 07', 436, 718, 120, white, 15, s)
    _label(im, '0:12:47', 116, 718, 160, white, 15, s)
    _label(im, 'CALCIO A 7 / FLAMINGOS', 270, 150, 420, yellow, 13, s)
    # Tracking tear: one displaced stripe of the frame.
    strip = im.crop((0, 760*s, 540*s, 772*s))
    im.paste(strip, (10*s, 762*s))
    glow = Image.new('RGBA', size)
    ScaledDraw(glow, s).rectangle((64, 300, 476, 690), outline=(*cyan, 120), width=6)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12*s)))
    return im


def _bg_teletext(pink, cyan, yellow, s):
    size = (540*s, 960*s)
    im = Image.new('RGBA', size, (24, 44, 206, 255))
    d = ScaledDraw(im, s)
    pure = [(255, 40, 40), (40, 230, 70), (255, 240, 40), (40, 240, 255), (255, 60, 230), (255, 255, 255)]
    # Header row, page number and clock.
    d.rectangle((0, 150, 540, 206), fill=(*cyan, 255))
    _label(im, 'CALCIO A 7 / FLAMINGOS', 270, 178, 440, (0, 0, 0), 15, s)
    d.rectangle((0, 226, 540, 274), fill=(0, 0, 0, 255))
    _label(im, 'P101', 62, 250, 90, (255, 255, 255), 16, s)
    _label(im, 'TELEVIDEO 7', 222, 250, 220, yellow, 16, s)
    _label(im, '21:00:07', 452, 250, 140, cyan, 14, s)
    # Mosaic (sixel) side graphics.
    rnd = random.Random(101)
    for side in (0, 1):
        for row in range(0, 21):
            for col in range(0, 3):
                if rnd.random() < .55:
                    x = 10+col*16 if side == 0 else 482+col*16
                    y = 280+row*20
                    d.rectangle((x, y, x+14, y+18), fill=(*pure[(row+col+side*2) % 5], 255))
    d.rectangle((70, 300, 470, 690), fill=(14, 14, 40, 255))
    # The four Fastext keys.
    names = ('PARTITA', 'ROSA', 'RISULTATI', 'GIRONE')
    for i, (name, color) in enumerate(zip(names, pure[:4])):
        x = 8+i*132
        d.rectangle((x, 700, x+128, 742), fill=(*color, 255))
        _label(im, name, x+64, 721, 118, (0, 0, 0), 12, s)
    _label(im, 'PAGINA SEGUENTE  >>>  102', 270, 790, 420, (255, 255, 255), 12, s)
    return im


def _bg_gameboy(pink, cyan, yellow, s):
    size = (540*s, 960*s)
    im = _gradient(size, (208, 207, 200), (178, 176, 172))
    d = ScaledDraw(im, s)
    d.rectangle((0, 0, 540, 40), fill=(160, 158, 154, 255))
    for x in (60, 480):
        d.rectangle((x-2, 0, x+2, 40), fill=(140, 138, 134, 255))
    # Bezel with the classic asymmetrical corner.
    d.polygon([(40, 236), (500, 236), (500, 690), (456, 734), (40, 734)], fill=(86, 88, 110, 255))
    d.rectangle((77, 315, 463, 673), fill=(48, 98, 48, 255))
    d.line((60, 262, 200, 262), fill=(136, 30, 72, 255), width=2.5)
    d.line((340, 262, 480, 262), fill=(40, 40, 120, 255), width=2.5)
    _label(im, 'DOT MATRIX / 7-A-SIDE', 270, 262, 150, (200, 200, 214), 8, s)
    d.ellipse((52, 470, 62, 480), fill=(220, 30, 40, 255))
    _label(im, 'PWR', 57, 492, 26, (190, 190, 200), 6, s)
    _label(im, 'FLAMINGOS', 150, 770, 200, (40, 40, 120), 18, s)
    _label(im, 'POCKET', 290, 770, 110, (40, 40, 120), 12, s)
    # D-pad and A/B buttons.
    d.rectangle((92, 830, 112, 900), fill=(30, 30, 34, 255))
    d.rectangle((67, 855, 137, 875), fill=(30, 30, 34, 255))
    d.ellipse((380, 846, 424, 890), fill=(136, 30, 72, 255))
    d.ellipse((440, 822, 484, 866), fill=(136, 30, 72, 255))
    for x in (226, 290):
        d.rounded_rectangle((x, 900, x+44, 910), radius=5, fill=(120, 118, 128, 255))
    for i in range(6):
        d.line((400+i*14, 930, 430+i*14, 900), fill=(140, 138, 134, 255), width=3)
    return im


def _bg_stadium(pink, cyan, yellow, s):
    size = (540*s, 960*s)
    im = _gradient(size, (16, 26, 58), (30, 44, 66), (34, 54, 92))
    glow = Image.new('RGBA', size)
    g = ScaledDraw(glow, s)
    for x in (40, 500):
        g.ellipse((x-150, -80, x+150, 220), fill=(255, 246, 214, 200))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40*s)))
    d = ScaledDraw(im, s)
    for x in (40, 500):  # floodlight heads
        for i in range(3):
            for j in range(4):
                d.rectangle((x-36+j*18, 30+i*16, x-22+j*18, 42+i*16), fill=(255, 252, 236, 255))
    # Crowd and pitch.
    d.rectangle((0, 800, 540, 960), fill=(30, 120, 64, 255))
    rnd = random.Random(10)
    for y in range(756, 812, 7):
        for x in range(0, 540, 7):
            tint = rnd.choice(((255, 116, 172), (240, 240, 240), (60, 64, 90), (30, 32, 50), (134, 230, 255)))
            d.rectangle((x, y, x+5, y+5), fill=(*tint, 255))
    # Steel scoreboard on two legs.
    for x in (150, 380):
        d.rectangle((x, 700, x+18, 800), fill=(70, 76, 88, 255))
    _box(d, (46, 256, 494, 712), (78, 84, 96, 255), (150, 158, 172, 255), 4, 6)
    d.rectangle((70, 234, 470, 268), fill=(30, 32, 36, 255))
    _label(im, 'STADIO COMUNALE / CALCIO A 7', 270, 251, 380, yellow, 12, s)
    for x, y in ((58, 280), (482, 280), (58, 696), (482, 696)):
        d.ellipse((x-4, y-4, x+4, y+4), fill=(190, 196, 206, 255))
    d.rectangle((77, 315, 463, 673), fill=(10, 9, 8, 255))
    dots = Image.new('RGBA', size)
    dd = ScaledDraw(dots, s)
    for y in range(318, 672, 6):
        for x in range(80, 462, 6):
            dd.rectangle((x, y, x+2, y+2), fill=(*yellow, 34))
    im.alpha_composite(dots)
    return im


def _bg_poster(pink, cyan, yellow, s):
    size = (540*s, 960*s)
    paper = np.random.default_rng(11).integers(-7, 8, (960*s, 540*s, 1), dtype=np.int16)
    base = np.array((244, 234, 214), np.int16)+paper
    arr = np.concatenate([base.clip(0, 255).astype(np.uint8), np.full((960*s, 540*s, 1), 255, np.uint8)], axis=2)
    im = Image.fromarray(arr, 'RGBA')
    ink = Image.new('RGBA', size)
    d = ScaledDraw(ink, s)
    # Two risograph spot colours, slightly misregistered.
    d.ellipse((300, -60, 640, 280), fill=(255, 92, 160, 210))
    d.ellipse((-120, 690, 230, 1040), fill=(60, 150, 230, 200))
    for y in range(40, 960, 16):
        for x in range(10, 540, 16):
            r = 1+3*abs(math.sin((x+y)/90))
            d.ellipse((x-r, y-r, x+r, y+r), fill=(255, 92, 160, 70))
    im.alpha_composite(ink)
    d = ScaledDraw(im, s)
    d.rectangle((70, 306, 478, 690), fill=(255, 92, 160, 255))   # off-register plate
    d.rectangle((62, 298, 470, 682), fill=(22, 28, 66, 255))
    d.rectangle((77, 315, 463, 673), fill=(28, 36, 82, 255))
    navy = (22, 28, 66)
    _label(im, 'FLAMINGOS', 270, 170, 460, navy, 34, s)
    _label(im, 'CALCIO A 7 / CLUB PRINT', 270, 226, 380, navy, 12, s)
    _label(im, 'PRESS START / PLAY TOGETHER', 270, 742, 420, navy, 11, s)
    d.rectangle((40, 790, 500, 794), fill=(*navy, 255))
    _label(im, 'N.07 / EDIZIONE LIMITATA', 270, 818, 300, navy, 10, s)
    return im


BUILDERS = {'crt': _bg_crt, 'vhs': _bg_vhs, 'teletext': _bg_teletext,
            'gameboy': _bg_gameboy, 'stadium': _bg_stadium, 'poster': _bg_poster}


@lru_cache(maxsize=4)
def _background(preset_id, pink_hex, cyan_hex, yellow_hex, layout, intensity, s, brightness=DEFAULT_BRIGHTNESS):
    pink, cyan, yellow = _rgb(pink_hex), _rgb(cyan_hex), _rgb(yellow_hex)
    style = STYLE[preset_id]
    builder = BUILDERS.get(preset_id)
    im = builder(pink, cyan, yellow, s) if builder else _bg_legacy(preset_id, pink, cyan, yellow, s)
    im = _lift(im, brightness/100)
    veil_alpha = style['veil'] if (layout != 'matchday' or preset_id != 'crt') else 0
    if veil_alpha:
        veil = Image.new('RGBA', im.size)
        ScaledDraw(veil, s).rectangle((78, 316, 462, 674), fill=(*style['panel'], veil_alpha))
        im.alpha_composite(veil)
    scan_color = style['scan'] or cyan
    scan = Image.new('RGBA', im.size)
    sd = ScaledDraw(scan, s)
    for y in range(318, 674, 4):
        sd.line((80, y, 460, y), fill=(*scan_color, intensity), width=.5)
    im.alpha_composite(scan)
    d = ScaledDraw(im, s)
    border = style['border'] or cyan
    for i, rect in enumerate(PANEL_LAYOUTS.get(layout, PANEL_LAYOUTS['convocati'])):
        soft = (layout == 'fulltime' and i == 3) or (layout in ('convocati', 'classifica') and i == 1)
        _box(d, rect, (*style['panel'], 255), (*border, 190 if soft else 255), 1.2 if layout != 'matchday' else 1.4, 5)
    if layout == 'fulltime':
        d.line((270, 590, 270, 660), fill=(*border, 90), width=.5)
    return im


def background(config, layout='matchday', render_scale=2):
    s = checked_scale(render_scale)
    preset = config.get('preset_id', 'crt')
    if preset not in PRESETS:
        preset = 'crt'
    palette = PRESETS[preset]
    colors = []
    for key in ('pink', 'cyan', 'yellow'):
        value = config.get(key, palette[key])
        try:
            if len(_rgb(value)) != 3:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            value = palette[key]
        colors.append(value)
    try:
        brightness = max(0, min(100, int(config.get('brightness', DEFAULT_BRIGHTNESS))))
    except (TypeError, ValueError):
        brightness = DEFAULT_BRIGHTNESS
    intensity = max(0, min(60, int(config.get('scanlines', 16))))
    image = _background(preset, *colors, layout, intensity, s, brightness).copy()
    import themes
    theme = themes.resolve(config)
    if theme:
        themes.decorate_background(image, theme)
    image.info['theme'] = theme or ''
    return image


def output_image(image, format='Story 9:16', scale=2):
    scale=checked_scale(scale)
    format=format if format in FORMATS else 'Story 9:16'
    crop=CROPS[format]
    source_scale=image.width/540
    if crop:
        top=math.floor(crop[1]*source_scale)
        box=(round(crop[0]*source_scale),top,round(crop[2]*source_scale),
             top+round((crop[3]-crop[1])*source_scale))
        image=image.crop(box)
    height=540 if format=='Post 1:1' else 675 if format=='Post 4:5' else 960
    target=(540*scale,height*scale)
    return image.resize(target,Image.Resampling.LANCZOS) if image.size!=target else image


def even_video_frame(image):
    """H.264/yuv420p needs even dimensions: pad, never stretch an odd crop."""
    width,height=image.size
    if width%2 or height%2:
        result=Image.new('RGB',(width+width%2,height+height%2))
        result.paste(image,(0,0))
        if height%2:result.paste(image.crop((0,height-1,width,height)),(0,height))
        if width%2:result.paste(result.crop((width-1,0,width,result.height)),(width,0))
        return result
    return image
