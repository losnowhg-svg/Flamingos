"""Event and seasonal themes laid over any preset.

A theme never replaces the preset: it shifts the accent colours (Flamingos
pink and the text colour stay) and adds details around the screen - fairy
lights, cobwebs, hazard tape, gold brackets, a chequered flag - plus particles
(snow, bats, embers, sparkles, confetti) that move in videos.

'auto' picks the theme by itself: an event set on the match (derby, big match,
last round) wins, otherwise the season (Halloween, Christmas, New Year) from
the match date, or from today.
"""
from __future__ import annotations

import datetime as dt
import math
import random
import re
from functools import lru_cache

from PIL import Image, ImageFilter

from render_utils import ScaledDraw

THEMES = {
    'derby': dict(name='Derby', badge='DERBY', cyan='#FF5A4E', yellow='#FFE45C', particles='embers',
                  description='Nastro di pericolo rosso e giallo e scintille che salgono.'),
    'bigmatch': dict(name='Big match', badge='BIG MATCH', cyan='#A8ECFF', yellow='#FFD045', particles='sparkles',
                     description='Angoli dorati, fasci di luce e scintillii.'),
    'ultima': dict(name='Ultima giornata', badge='ULTIMA GIORNATA', cyan='#F2F6FF', yellow='#FFD045', particles='confetti',
                   description='Bandiera a scacchi e coriandoli.'),
    'halloween': dict(name='Halloween', badge='HALLOWEEN', cyan='#B48CFF', yellow='#FF9A3C', particles='bats',
                      description='Viola e arancio, ragnatele negli angoli e pipistrelli.'),
    'natale': dict(name='Natale', badge='BUON NATALE', cyan='#7CF0B0', yellow='#FFE27A', particles='snow',
                   description='Lucine colorate sullo schermo e neve che cade.'),
    'capodanno': dict(name='Capodanno', badge='BUON ANNO', cyan='#E9E4FF', yellow='#FFD45C', particles='fireworks',
                      description='Oro e argento, fuochi d\'artificio a pixel.'),
}
THEME_IDS = tuple(THEMES)
CHOICES = ('auto', 'none')+THEME_IDS
EVENTS = ('derby', 'bigmatch', 'ultima')
MATCH_EVENTS = ('auto', 'normale')+EVENTS
SCREEN = (78, 316, 462, 674)


def label(choice):
    if choice == 'auto':
        return 'Automatico (evento o stagione)'
    if choice == 'none':
        return 'Nessuno'
    return THEMES[choice]['name']


def event_label(choice):
    return {'auto': 'Automatico', 'normale': 'Partita normale'}.get(choice) or THEMES[choice]['name']


def parse_date(value):
    m = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', str(value or ''))
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year += 2000 if year < 100 else 0
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def seasonal(date):
    """Season theme for a date, or None."""
    if date is None:
        return None
    md = (date.month, date.day)
    if (10, 24) <= md <= (11, 2):
        return 'halloween'
    if (12, 1) <= md <= (12, 28):
        return 'natale'
    if md >= (12, 29) or md <= (1, 6):
        return 'capodanno'
    return None


def resolve(config, today=None):
    """The theme actually drawn for this config, or None."""
    choice = config.get('theme', 'auto')
    if choice in THEMES:
        return choice
    if choice != 'auto':
        return None
    event = config.get('event_theme', '')
    if event in EVENTS:
        return event
    return seasonal(parse_date(config.get('date')) or today or dt.date.today())


def why(config, today=None):
    """One line for the editor: which theme is on and why."""
    theme = resolve(config, today)
    if not theme:
        return 'Nessun tema attivo: grafica normale.'
    if config.get('theme') in THEMES:
        return f'Tema {THEMES[theme]["name"]}, scelto a mano.'
    if theme in EVENTS:
        return f'Tema {THEMES[theme]["name"]}: viene dalla partita della settimana.'
    return f'Tema {THEMES[theme]["name"]}: scelto dal calendario.'


def auto_event(match, standings=None, matches=None, today=None):
    """Event theme for the shared match: '' for an ordinary game.

    derby is only ever chosen by hand; 'ultima' when the CSI calendar has no
    later game of ours; 'bigmatch' when both teams sit in the top places."""
    choice = match.get('event', 'auto')
    if choice in EVENTS:
        return choice
    if choice != 'auto':
        return ''
    from csi_page import is_ours
    ours, other = match.get('our_name', ''), match.get('opponent', '')
    date = parse_date(match.get('date'))
    if matches and date:
        ours_games = [m for m in matches if is_ours(m['home'], ours) or is_ours(m['away'], ours)]
        if ours_games and all(m['date'] <= date for m in ours_games) and any(m['date'] == date for m in ours_games):
            return 'ultima'
    rows = [r for r in (standings or []) if str(r.get('team', '')).strip()]
    if len(rows) >= 6:
        top = max(3, len(rows)//3)
        def place(name):
            from csi_page import _norm
            exact = [r for r in rows if _norm(r['team']) == _norm(name)]
            for r in exact or [r for r in rows if is_ours(r['team'], name)]:
                return int(r.get('pos', 99))
            return 99
        if place(ours) <= top and place(other) <= top:
            return 'bigmatch'
    return ''


def _rgb(value):
    return tuple(bytes.fromhex(value.lstrip('#')))


def _hex(color):
    return '#%02X%02X%02X' % color


def _blend(a, b, k):
    return tuple(round(x+(y-x)*k) for x, y in zip(a, b))


def effective(config, today=None):
    """Config with the theme's accents mixed in. Pink and text colours stay."""
    theme = resolve(config, today)
    if not theme:
        return config
    out = dict(config)
    spec = THEMES[theme]
    for key, k in (('cyan', .7), ('yellow', .85)):
        try:
            mine = _rgb(config.get(key, spec[key]))
        except (ValueError, TypeError, AttributeError):
            mine = _rgb(spec[key])
        out[key] = _hex(_blend(mine, _rgb(spec[key]), k))
    out['_theme'] = theme
    return out


# --- Static details around the screen -------------------------------------

def _badge(im, text, color, s):
    from pixel_fonts import pixel_text_runs
    label = pixel_text_runs([(text, (12, 10, 18))], 'CRT Scoreboard', 10, 240, s)
    if not label:
        return
    w = label.width/s+18
    x1, y1 = 270-w/2, 297
    d = ScaledDraw(im, s)
    d.rectangle((x1+2, y1+2, x1+w+2, y1+17), fill=(0, 0, 0, 150))
    d.rectangle((x1, y1, x1+w, y1+15), fill=(*color, 255))
    d.rectangle((x1-3, y1+5, x1, y1+10), fill=(*color, 255))
    d.rectangle((x1+w, y1+5, x1+w+3, y1+10), fill=(*color, 255))
    im.alpha_composite(label, (round((270)*s-label.width/2), round((y1+7.5)*s-label.height/2)))


def _lights(d, glow, y, s, phase=0):
    colors = ((255, 70, 70), (90, 240, 120), (255, 220, 80), (110, 190, 255), (255, 110, 200))
    x1, x2 = SCREEN[0]-10, SCREEN[2]+10
    points = []
    for i in range(0, 25):
        x = x1+(x2-x1)*i/24
        points.append((x, y+6*math.sin(i*math.pi/2+phase)+(4 if i % 2 else 0)))
    d.line(points, fill=(30, 50, 34, 255), width=1.6)
    for i, (x, yy) in enumerate(points[1:-1:2]):
        c = colors[i % len(colors)]
        d.rectangle((x-2.5, yy+1, x+2.5, yy+8), fill=(*c, 255))
        d.rectangle((x-1.5, yy-1, x+1.5, yy+1), fill=(40, 40, 40, 255))
        glow.ellipse((x-9, yy-5, x+9, yy+14), fill=(*c, 150))


def _web(d, corner, size, color):
    x, y, sx, sy = corner
    for i in range(6):
        a = i/5*math.pi/2
        d.line((x, y, x+sx*size*math.cos(a), y+sy*size*math.sin(a)), fill=color, width=.8)
    for r in (size*.35, size*.62, size*.9):
        pts = [(x+sx*r*math.cos(i/5*math.pi/2), y+sy*r*math.sin(i/5*math.pi/2)) for i in range(6)]
        d.line(pts, fill=color, width=.8)


def _hazard(im, box, s, a=(255, 210, 40), b=(20, 18, 22)):
    x1, y1, x2, y2 = box
    tape = Image.new('RGBA', (round((x2-x1)*s), round((y2-y1)*s)), (*a, 255))
    d = ScaledDraw(tape, s)
    h = y2-y1
    for x in range(-40, round(x2-x1)+40, 16):
        d.polygon([(x, h), (x+8, h), (x+8+h, 0), (x+h, 0)], fill=(*b, 255))
    im.alpha_composite(tape, (round(x1*s), round(y1*s)))


def _checker(d, box, cell=6):
    x1, y1, x2, y2 = box
    rows = round((y2-y1)/cell)
    for r in range(rows):
        for i, x in enumerate(range(round(x1), round(x2), cell)):
            black = (i+r) % 2
            d.rectangle((x, y1+r*cell, min(x2, x+cell), y1+(r+1)*cell), fill=(16, 16, 20, 255) if black else (244, 244, 248, 255))


def _brackets(d, color, s):
    x1, y1, x2, y2 = SCREEN
    L, w = 34, 4
    for x, y, sx, sy in ((x1-8, y1-8, 1, 1), (x2+8, y1-8, -1, 1), (x1-8, y2+8, 1, -1), (x2+8, y2+8, -1, -1)):
        d.rectangle((min(x, x+sx*L), min(y, y+sy*w), max(x, x+sx*L), max(y, y+sy*w)), fill=(*color, 255))
        d.rectangle((min(x, x+sx*w), min(y, y+sy*L), max(x, x+sx*w), max(y, y+sy*L)), fill=(*color, 255))


@lru_cache(maxsize=8)
def _overlay(theme, s):
    """Full-frame transparent details for one theme, at scale s."""
    size = (540*s, 960*s)
    im = Image.new('RGBA', size)
    glow_layer = Image.new('RGBA', size)
    d, glow = ScaledDraw(im, s), ScaledDraw(glow_layer, s)
    spec = THEMES[theme]
    yellow, cyan = _rgb(spec['yellow']), _rgb(spec['cyan'])
    x1, y1, x2, y2 = SCREEN
    if theme == 'natale':
        _lights(d, glow, y1-14, s)
        _lights(d, glow, y2+4, s, 1.3)
        # Snow resting on the top of the frame.
        rnd = random.Random(12)
        for x in range(round(x1)-14, round(x2)+14, 3):
            h = 3+2.5*math.sin(x/9)+rnd.random()*1.5
            d.rectangle((x, y1-17-h, x+3, y1-17), fill=(250, 252, 255, 255))
    elif theme == 'halloween':
        web = (235, 230, 255, 170)
        for corner in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
            _web(d, corner, 46, web)
        # A spider hanging from the top-right web.
        d.line((x2-26, y1, x2-26, y1+40), fill=web, width=.7)
        d.rectangle((x2-30, y1+40, x2-22, y1+47), fill=(20, 14, 26, 255))
        for k in (-1, 1):
            for j in range(3):
                d.line((x2-26, y1+43, x2-26+k*9, y1+38+j*5), fill=(20, 14, 26, 255), width=.8)
        glow.rectangle((x1-20, y1-20, x2+20, y2+20), outline=(*yellow, 110), width=10)
    elif theme == 'derby':
        _hazard(im, (x1-14, y1-26, x2+14, y1-12), s, (255, 210, 40), (200, 30, 36))
        _hazard(im, (x1-14, y2+10, x2+14, y2+24), s, (255, 210, 40), (200, 30, 36))
        glow.rectangle((x1-20, y1-20, x2+20, y2+20), outline=(255, 60, 50, 140), width=12)
    elif theme == 'bigmatch':
        _brackets(d, yellow, s)
        for x, k in ((40, 1), (500, -1)):  # two spotlight beams
            glow.polygon([(x, 0), (x+k*30, 0), (270+k*40, 520), (270-k*90, 520)], fill=(255, 238, 190, 40))
        glow.rectangle((x1-14, y1-14, x2+14, y2+14), outline=(*yellow, 120), width=8)
    elif theme == 'ultima':
        _checker(d, (x1-14, y1-28, x2+14, y1-10))
        _checker(d, (x1-14, y2+10, x2+14, y2+28))
        glow.rectangle((x1-16, y1-16, x2+16, y2+16), outline=(*yellow, 110), width=8)
    elif theme == 'capodanno':
        _brackets(d, (232, 232, 245), s)
        glow.rectangle((x1-14, y1-14, x2+14, y2+14), outline=(*yellow, 120), width=8)
    _badge(im, spec['badge'], yellow if theme not in ('derby',) else (255, 210, 40), s)
    out = glow_layer.filter(ImageFilter.GaussianBlur(7*s))
    out.alpha_composite(im)
    return out


def decorate_background(image, theme):
    """Add the static details to a background (RGBA, any scale)."""
    if theme not in THEMES:
        return image
    s = max(1, round(image.width/540))
    image.alpha_composite(_overlay(theme, s))
    return image


# --- Particles: moving in videos, frozen in PNGs ---------------------------

def _particles(kind):
    rnd = random.Random(sum(map(ord, kind)))
    count = {'snow': 70, 'bats': 7, 'embers': 40, 'sparkles': 26, 'confetti': 55, 'fireworks': 5}[kind]
    return [(rnd.uniform(0, 540), rnd.uniform(0, 960), rnd.uniform(.6, 1.4), rnd.uniform(0, 6.28), rnd.random())
            for _ in range(count)]


BAT = ('X.....X', 'XX.X.XX', 'XXXXXXX', '.X.X.X.')
BAT_UP = ('X.....X', '.X...X.', '.XXXXX.', '..X.X..')


def draw_particles(canvas, theme, t):
    """Draw the theme's particles on an RGBA canvas at time t (seconds)."""
    if theme not in THEMES:
        return
    kind = THEMES[theme]['particles']
    s = canvas.width/540
    layer = Image.new('RGBA', canvas.size)
    d = ScaledDraw(layer, s)
    spec = THEMES[theme]
    yellow, cyan = _rgb(spec['yellow']), _rgb(spec['cyan'])

    def inside(x, y):
        return SCREEN[0] < x < SCREEN[2] and SCREEN[1] < y < SCREEN[3]

    for i, (x0, y0, speed, phase, r) in enumerate(_particles(kind)):
        if kind == 'snow':
            y = (y0+t*38*speed) % 980-10
            x = x0+math.sin(t*1.3*speed+phase)*10
            size = 1.5+r*2
            a = 110 if inside(x, y) else 230
            d.rectangle((x, y, x+size, y+size), fill=(250, 252, 255, a))
        elif kind == 'embers':
            y = 960-((960-y0)+t*55*speed) % 980
            x = x0+math.sin(t*2*speed+phase)*8
            a = round((90 if inside(x, y) else 220)*(.5+.5*math.sin(t*6+phase)))
            col = (255, 170, 60) if r > .4 else (255, 80, 50)
            d.rectangle((x, y, x+2, y+2), fill=(*col, a))
        elif kind == 'sparkles':
            k = .5+.5*math.sin(t*3*speed+phase)
            if k < .35:
                continue
            x, y = x0, y0
            if inside(x, y):
                continue
            L = 2+5*k
            col = (*yellow, round(255*k))
            d.rectangle((x-.7, y-L, x+.7, y+L), fill=col)
            d.rectangle((x-L, y-.7, x+L, y+.7), fill=col)
        elif kind == 'confetti':
            y = (y0+t*60*speed) % 980-10
            x = x0+math.sin(t*2.4*speed+phase)*14
            palette = ((255, 110, 180), yellow, cyan, (120, 240, 140), (250, 250, 255))
            col = palette[i % len(palette)]
            flip = abs(math.sin(t*5*speed+phase))
            w, h = 2+3*flip, 4.5
            a = 120 if inside(x, y) else 240
            d.rectangle((x, y, x+w, y+h), fill=(*col, a))
        elif kind == 'bats':
            x = (x0+t*45*speed*(1 if i % 2 else -1)) % 620-40
            band = (150, 290) if i % 2 else (700, 860)
            y = band[0]+(y0 % (band[1]-band[0]))+math.sin(t*3+phase)*10
            sprite = BAT if int(t*8+i) % 2 else BAT_UP
            px = 2.6+r*1.4
            for row, line in enumerate(sprite):
                for col_, ch in enumerate(line):
                    if ch == 'X':
                        d.rectangle((x+col_*px, y+row*px, x+(col_+1)*px, y+(row+1)*px), fill=(18, 10, 26, 235))
        elif kind == 'fireworks':
            period = 2.4
            local = (t+phase) % period
            cx = 60+(x0 % 420)
            cy = 120+(y0 % 160) if i % 2 else 720+(y0 % 160)
            if local > 1.4:
                continue
            radius = 8+local*40
            a = round(255*max(0, 1-local/1.4))
            palette = ((255, 110, 180), yellow, cyan, (255, 255, 255))
            col = palette[i % len(palette)]
            for k in range(12):
                ang = k/12*math.tau
                px, py = cx+math.cos(ang)*radius, cy+math.sin(ang)*radius+local*local*10
                d.rectangle((px, py, px+2.5, py+2.5), fill=(*col, a))
    canvas.alpha_composite(layer)


STILL_TIME = 2.3
