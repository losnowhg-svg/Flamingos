"""3.19, Intro della partita: an animated pixel-retro intro that ends on the match poster.

Built from the week's match alone, for any opponent (the hand-made Caste United intro, generalised):
1. the CRT switches on; our flamingo, a neon sign cut from the club crest, flickers on; FLAMINGOS is typed;
2. the opponent's crest, redrawn in pixels, rolls in with a trail in its own colours; its name is typed;
3. face-off on a diagonal split; VS slams in on the drop of the music; the picture breaks up;
4. the poster assembles: the bar with the two names and the kick-off time, VS, the band with day, time and place.

Words are informative only (teams, VS, day, time, place, competition), as agreed for the posters.
Everything is low-resolution pixel art (one cell = 4 px at scale 1) enlarged with NEAREST, drawn with
Pillow and NumPy only, so it renders on Streamlit Cloud. The last frame is the poster (PNG).
"""
from __future__ import annotations

import io
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from pixel_fonts import pixel_text_runs

ROOT = Path(__file__).resolve().parent
C = 4                                        # px per cell at scale 1 (the frame is 540 px wide)
FORMATS = {'Story 9:16': 960, 'Post 4:5': 675}
LENGTH = 11.5
T_ON, T_WHIP, T_THEM, T_FACE, T_BUILD, T_CARD = .35, 2.45, 2.7, 4.7, 6.3, 7.0
DROP = 5.6                                   # VS lands here: the music's drop is put here
T_BOUNCE, T_TOP, T_BAND, T_BARS, T_STAMP = 3.6, 7.35, 7.5, 7.75, 8.3
HOT, PINK, DPINK = (255, 40, 140), (255, 92, 176), (150, 20, 90)
INK, WHITE, YELLOW, MUTED = (14, 8, 24), (250, 246, 255), (255, 222, 110), (150, 140, 190)
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])/16
LOOKS = {'rosa': (HOT, WHITE), 'bianco': (WHITE, HOT), 'sagoma': (None, HOT)}       # body, line
LOOK_LABELS = {'auto': 'Automatico (cambia ogni partita)', 'rosa': 'Rosa', 'bianco': 'Bianco',
               'sagoma': 'Sagoma al neon'}
WEEKDAYS = ('LUNEDI', 'MARTEDI', 'MERCOLEDI', 'GIOVEDI', 'VENERDI', 'SABATO', 'DOMENICA')
MONTHS = ('GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO', 'AGOSTO', 'SETTEMBRE', 'OTTOBRE',
          'NOVEMBRE', 'DICEMBRE')


# --- words -----------------------------------------------------------------------------------------

def date_line(date_text, kickoff=''):
    """'12/11/2026' -> 'GIOVEDI 12 NOVEMBRE' (no accents: the pixel font has none)."""
    import datetime as dt
    try:
        day = dt.datetime.strptime(str(date_text).strip(), '%d/%m/%Y').date()
        text = f'{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month-1]}'
    except ValueError:
        text = str(date_text or '').upper()
    time = str(kickoff or '').strip()
    return f'{text} / ORE {time}' if time and time.upper() != 'HH:MM' else text


def texts_for(match, competition='CSI BRESCIA'):
    """The words of the intro from the week's match (all editable on the page)."""
    home = match.get('our_side', 'Casa') == 'Casa'
    comp = ' / '.join(x for x in (str(competition or '').strip().upper(),
                                  f"GIORNATA {match['round']}" if match.get('round') else '') if x)
    kickoff = str(match.get('kickoff') or '').strip()
    return dict(ours=str(match.get('our_name') or 'FLAMINGOS').upper(), opponent=str(match.get('opponent') or '').upper(),
                home=home, date=date_line(match.get('date')), kickoff='' if kickoff.upper() == 'HH:MM' else kickoff,
                place=str(match.get('venue') or '').upper(), competition=comp)


# --- small tools -------------------------------------------------------------------------------------

def clamp(x, a=0., b=1.):
    return max(a, min(b, x))


def seg(t, t0, t1):
    return clamp((t-t0)/(t1-t0))


def ease_in(x):
    return x**3


def ease_out(x):
    return 1-(1-x)**3


def ease_io(x):
    return 3*x*x-2*x**3


def with_alpha(img, k):
    if k >= 1:
        return img
    out = img.copy()
    out.putalpha(out.getchannel('A').point(lambda v: int(v*k)))
    return out


def outline(mask):
    a = np.asarray(mask) > 0
    g = a.copy()
    g[1:] |= a[:-1]
    g[:-1] |= a[1:]
    g[:, 1:] |= a[:, :-1]
    g[:, :-1] |= a[:, 1:]
    return Image.fromarray(((g & ~a)*255).astype(np.uint8))


def tinted(mask, color):
    out = Image.new('RGBA', mask.size, (*color, 255))
    out.putalpha(mask)
    return out


@lru_cache(maxsize=1)
def flamingo_mask():
    return Image.open(ROOT/'assets'/'flamingo_mask.png').convert('L')


def flamingo_cells(cols, mirror):
    """The club flamingo as a low-res mask, `cols` cells wide, with one empty cell around."""
    m = flamingo_mask()
    if mirror:
        m = m.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    small = m.resize((cols, round(m.height*cols/m.width)), Image.Resampling.BOX).point(lambda v: 255 if v > 110 else 0)
    pad = Image.new('L', (small.width+4, small.height+4))
    pad.paste(small, (2, 2))
    return pad


def crest_cells(data, size):
    """(sprite, c1, c2): the opponent's crest in pixels (fits `size` cells) and its two main colours."""
    im = Image.open(io.BytesIO(data)).convert('RGBA')
    box = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
    if box:
        im = im.crop(box)
    k = size/max(im.size)
    small = im.resize((max(1, round(im.width*k)), max(1, round(im.height*k))), Image.Resampling.BOX)
    alpha = small.getchannel('A').point(lambda v: 255 if v > 120 else 0)
    quant = small.convert('RGB').quantize(20, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    flat = quant.convert('RGB')
    pixels = np.asarray(flat)[np.asarray(alpha) > 0]
    colours, numbers = np.unique(pixels, axis=0, return_counts=True) if len(pixels) else (np.zeros((0, 3), int), [])
    counts = {tuple(int(v) for v in colour): int(n) for colour, n in zip(colours, numbers)}

    def vivid(c):
        return max(c)-min(c) > 60 and 50 < sum(c)/3 < 235

    ranked = sorted(counts, key=counts.get, reverse=True)
    main = [c for c in ranked if vivid(c)]
    c1 = main[0] if main else (120, 190, 255)
    c2 = next((c for c in main[1:] if sum(abs(a-b) for a, b in zip(c, c1)) > 120), None) \
        or next((c for c in ranked if sum(c)/3 >= 200), WHITE)
    sprite = Image.new('RGBA', (small.width+4, small.height+4))
    body = flat.convert('RGBA')
    body.putalpha(alpha)
    sprite.alpha_composite(body, (2, 2))
    pad = Image.new('L', sprite.size)
    pad.paste(alpha, (2, 2))
    lum = [sum(c)/3*n for c, n in counts.items()]
    dim_crest = sum(lum)/max(1, sum(counts.values())) < 105
    sprite.alpha_composite(tinted(outline(pad), WHITE if dim_crest else INK))     # a dark crest gets a light edge
    if dim_crest and not main:
        c1, c2 = (150, 150, 170), WHITE                                          # and a neutral steel night
    return sprite, c1, c2


def shield_cells(name, size, color=(120, 190, 255)):
    """No crest in the archive: a plain pixel shield with the team's initials."""
    w, h = int(size*.82), size
    im = Image.new('RGBA', (w+4, h+4))
    d = ImageDraw.Draw(im)
    shape = [(2, 5), (w//2+2, 2), (w+1, 5), (w+1, int(h*.62)), (w//2+2, h+1), (2, int(h*.62))]
    d.polygon(shape, fill=(*WHITE, 255))
    inner = [(4, 7), (w//2+2, 4), (w-1, 7), (w-1, int(h*.6)), (w//2+2, h-2), (4, int(h*.6))]
    d.polygon(inner, fill=(*color, 255))
    initials = ''.join(word[0] for word in str(name).split()[:3]) or '?'
    t = pixel_text_runs([(initials, WHITE)], 'CRT Scoreboard', max(5, w//(len(initials)+1)), w-8)
    if t is not None:
        im.alpha_composite(t, (im.width//2-t.width//2, int(h*.36)-t.height//2))
    pad = im.getchannel('A').point(lambda v: 255 if v > 0 else 0)
    im.alpha_composite(tinted(outline(pad), INK))
    return im, color, WHITE


def dark(color, k):
    return tuple(int(v*k) for v in color)


class Intro:
    def __init__(self, texts, crest=None, format='Story 9:16', scale=2, track=None, look='auto', seed=None):
        self.t, self.format = dict(texts), format if format in FORMATS else 'Story 9:16'
        self.scale = float(scale)
        self.c = max(1, int(round(C*self.scale)))
        self.W, self.H = int(540*self.scale), int(FORMATS[self.format]*self.scale)
        self.GW, self.GH = self.W//self.c, math.ceil(self.H/self.c)
        self.track, self.length = track, LENGTH
        self.rng_seed = seed if seed is not None else sum(ord(ch) for ch in self.t['opponent']+self.t['date'])
        self.look = look if look in LOOKS else ('rosa', 'bianco', 'sagoma')[self.rng_seed % 3]
        self.left_ours = bool(self.t.get('home', True))                   # the home team is on the left
        self._prepare(crest)

    # ----------------------------------------------------------------- building blocks
    def up(self, low):
        return low.resize((low.width*self.c, low.height*self.c), Image.Resampling.NEAREST)

    def text(self, value, color, size, width=500, style='CRT Scoreboard'):
        return pixel_text_runs([(str(value), color)], style, size, width, self.scale) if value else None

    def label(self, value, color, size, glow, width=500):
        """A word with its shadow and a coloured glow (cached)."""
        key = (value, color, size, glow, width)
        if key in self._labels:
            return self._labels[key]
        im = self.text(value, color, size, width)
        if im is None:
            self._labels[key] = None
            return None
        pad = int(20*self.scale)
        out = Image.new('RGBA', (im.width+2*pad, im.height+2*pad))
        halo = Image.new('RGBA', out.size)
        halo.alpha_composite(tinted(im.getchannel('A'), glow), (pad, pad))
        halo = halo.filter(ImageFilter.GaussianBlur(7*self.scale))
        out.alpha_composite(halo)
        out.alpha_composite(halo)
        off = max(1, int(3*self.scale))
        out.alpha_composite(tinted(im.getchannel('A'), INK), (pad+off, pad+off))
        out.alpha_composite(im, (pad, pad))
        self._labels[key] = out
        return out

    def night(self, top, bottom, haze, seed):
        """A dithered night with stars and a pixel floor grid, in two colours."""
        GW, GH = self.GW, self.GH
        gy, gx = np.mgrid[0:GH, 0:GW]
        horizon = int(GH*.72)
        a = np.zeros((GH, GW, 3), np.uint8)
        t = np.clip(gy/max(1, horizon), 0, 1)**1.6
        sky = BAYER[gy % 4, gx % 4] < t*.9
        a[...] = top
        a[sky] = bottom
        glow = (gy < horizon) & (gy > horizon-26) & (BAYER[gy % 4, gx % 4] < (gy-(horizon-26))/26*.75)
        a[glow] = haze
        rng = np.random.default_rng(seed)
        for _ in range(GW*GH//260):
            x, y = int(rng.integers(0, GW)), int(rng.integers(0, max(1, horizon-30)))
            a[y, x] = WHITE if rng.random() < .7 else haze
        floor = gy >= horizon
        a[floor] = dark(bottom, .55)
        depth = (gy-horizon)/max(1, GH-horizon)
        rows = floor & ((np.floor(np.sqrt(np.clip(depth, 0, 1))*9) != np.floor(np.sqrt(np.clip(depth-1/GH*3, 0, 1))*9)))
        spread = (gx-GW/2)/(.25+depth*1.6)
        cols = floor & (np.abs(spread/9-np.round(spread/9)) < .07)
        a[rows | cols] = haze
        a[gy == horizon] = WHITE
        return self.up(Image.fromarray(a).convert('RGBA')).crop((0, 0, self.W, self.H))

    def _prepare(self, crest):
        W, H, c = self.W, self.H, self.c
        self._labels = {}
        ours_on_left = self.left_ours
        # --- them: the crest in pixels and its colours
        size = 62 if self.format == 'Story 9:16' else 54
        if crest:
            try:
                sprite, c1, c2 = crest_cells(crest, size)
            except Exception:
                sprite, c1, c2 = shield_cells(self.t['opponent'], size)
        else:
            sprite, c1, c2 = shield_cells(self.t['opponent'], size)
        self.c1, self.c2 = c1, c2
        self.name_col = c1 if sum(c1)/3 > 110 else tuple(min(255, int(v*1.6)+40) for v in c1)
        self.crest = self.up(sprite)
        # --- us: the flamingo as a neon sign (looking towards the middle of the face-off)
        cols = 74 if self.format == 'Story 9:16' else 60
        mask = flamingo_cells(cols, mirror=ours_on_left)
        body, line = LOOKS[self.look]
        on = Image.new('RGBA', mask.size)
        if body:
            on.alpha_composite(tinted(mask, body))
        on.alpha_composite(tinted(outline(mask), line))
        if not body:                                    # a hollow neon tube: a second line inside
            inner = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
            on.alpha_composite(tinted(inner, PINK))
        off = Image.new('RGBA', mask.size)
        off.alpha_composite(tinted(mask, (46, 30, 58)))
        off.alpha_composite(tinted(outline(mask), (84, 60, 100)))
        self.fl_on, self.fl_off = self.up(on), self.up(off)
        card = Image.new('RGBA', mask.size)                # on the poster's pink side: white with a dark line
        card.alpha_composite(tinted(mask, WHITE))
        card.alpha_composite(tinted(outline(mask), INK))
        self.fl_card = self.up(card)
        halo = Image.new('RGBA', (self.fl_on.width+int(120*self.scale), self.fl_on.height+int(120*self.scale)))
        halo.alpha_composite(tinted(self.up(mask), HOT), (int(60*self.scale), int(60*self.scale)))
        self.fl_glow = halo.filter(ImageFilter.GaussianBlur(22*self.scale))
        # --- the two nights
        self.bg_us = self.night((30, 12, 44), INK, HOT, self.rng_seed)
        self.bg_them = self.night(dark(c1, .32), dark(c1, .10), c1, self.rng_seed+7)
        # --- face-off masks
        yy, xx = np.mgrid[0:H, 0:W]
        edge = W/2+(yy-H/2)*.32
        step = c*2
        edge = np.round(edge/step)*step                                   # stepped, like pixel lightning
        self.split = Image.fromarray(((xx < edge)*255).astype(np.uint8))
        line_mask = (np.abs(xx-edge) < max(2, c*.75))
        self.split_line = tinted(Image.fromarray((line_mask*255).astype(np.uint8)), WHITE)
        self.split_glow = tinted(Image.fromarray((line_mask*255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(8*self.scale)).point(lambda v: min(255, v*3)), HOT)
        # --- CRT finish
        scan = np.where(yy % 4 == 0, .8, np.where(yy % 4 == 1, .9, 1.0))
        vig = 1-.42*(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)/2
        mult = (scan*vig*255).clip(0, 255).astype(np.uint8)
        self.mult = Image.merge('RGB', [Image.fromarray(mult)]*3)
        self.bayer_big = BAYER[(yy//(4*c)) % 4, (xx//(4*c)) % 4]
        # --- words
        self.vs = self.label('VS', YELLOW, 70 if self.format == 'Story 9:16' else 58, (236, 180, 40))
        self._card()

    def _card(self):
        """The poster: the split background, the bar on top, the band below (each a layer, to animate)."""
        W, H, c, s = self.W, self.H, self.c, self.scale
        GW, GH = self.GW, self.GH
        story = self.format == 'Story 9:16'
        gy, gx = np.mgrid[0:GH, 0:GW]
        left = (gx-GW*.5)+(gy-GH*.5)*.32 < 0
        t = gy/GH
        a = np.zeros((GH, GW, 3), np.uint8)
        mine, theirs = (left, ~left) if self.left_ours else (~left, left)
        dith = BAYER[gy % 4, gx % 4]
        a[mine & (dith < 1-t*.9)] = HOT
        a[mine & ~(dith < 1-t*.9)] = DPINK
        a[theirs & (dith < t*.8)] = self.c1
        a[theirs & ~(dith < t*.8)] = dark(self.c1, .34)
        for row in range(GH):
            x = int(GW*.5-(row-GH*.5)*.32)
            a[row, max(0, x-1):x+1] = WHITE
        rng = np.random.default_rng(self.rng_seed+3)
        for _ in range(60):
            x, y = int(rng.integers(0, GW)), int(rng.integers(int(GH*.16), int(GH*.6)))
            a[y, x] = YELLOW if rng.random() < .5 else WHITE
        scene = self.up(Image.fromarray(a).convert('RGBA')).crop((0, 0, W, H))
        top_h = int((196 if story else 132)*s)
        band_y = int((700 if story else 498)*s)
        self.band_y, self.top_h = band_y, top_h
        mid_y = (top_h+band_y)//2
        k = min(1.0, (band_y-top_h-int(40*s))/max(self.fl_on.height, self.crest.height),
                W*.44/max(self.fl_on.width, self.crest.width))        # each stays on its own half
        glow, crest = self.fl_glow, self.crest

        def fit(im):
            cells = (max(1, round(im.width*k/c)), max(1, round(im.height*k/c)))
            return im.resize(cells, Image.Resampling.NEAREST).resize((cells[0]*c, cells[1]*c), Image.Resampling.NEAREST)
        if k < 1:
            crest = fit(crest)
            glow = glow.resize((round(glow.width*k), round(glow.height*k)))
        fl = self.fl_card if k >= 1 else fit(self.fl_card)
        x_us, x_them = (int(W*.27), int(W*.73)) if self.left_ours else (int(W*.73), int(W*.27))
        self.card_fl_pos = (x_us-glow.width//2, mid_y-glow.height//2)
        self.card_glow = glow
        shadow = tinted(fl.getchannel('A').point(lambda v: v*.55), INK)
        scene.alpha_composite(shadow, (x_us-fl.width//2+int(5*s), mid_y-fl.height//2+int(5*s)))
        scene.alpha_composite(fl, (x_us-fl.width//2, mid_y-fl.height//2))
        scene.alpha_composite(tinted(crest.getchannel('A').point(lambda v: v*.55), INK),
                              (x_them-crest.width//2+int(5*s), mid_y-crest.height//2+int(5*s)))
        scene.alpha_composite(crest, (x_them-crest.width//2, mid_y-crest.height//2))
        self.card_scene = scene
        self.vs_pos = (W//2, mid_y)
        # the bar on top: two energy bars, the kick-off time between them, the names (home first)
        top = Image.new('RGBA', (W, top_h), (*INK, 255))
        d = ImageDraw.Draw(top)
        d.rectangle((0, top_h-int(3*s), W, top_h), fill=YELLOW)
        bar_y, bar_h = int((70 if story else 26)*s), int(26*s)
        self.bars = []
        home, away = (self.t['ours'], self.t['opponent']) if self.left_ours else (self.t['opponent'], self.t['ours'])
        cols = (PINK, self.name_col) if self.left_ours else (self.name_col, PINK)
        for x0, x1, name, anchor, col in ((int(15*s), int(232*s), home, 'l', cols[0]), (int(308*s), int(525*s), away, 'r', cols[1])):
            d.rectangle((x0, bar_y, x1, bar_y+bar_h), fill=(60, 10, 30))
            d.rectangle((x0, bar_y, x1, bar_y+bar_h), outline=WHITE, width=max(1, int(2*s)))
            self.bars.append((x0+int(3*s), bar_y+int(3*s), x1-int(3*s), bar_y+bar_h-int(3*s), anchor))
            word = self.text(name, col, 27, 217)
            if word is not None:
                top.alpha_composite(word, (x0 if anchor == 'l' else x1-word.width, bar_y+bar_h+int(16*s)))
        clock = self.text(self.t.get('kickoff') or 'VS', WHITE, 24, 68)
        if clock is not None:
            top.alpha_composite(clock, (W//2-clock.width//2, bar_y+bar_h//2-clock.height//2))
        self.card_top = top
        # the band below: day and time, place, competition
        band = Image.new('RGBA', (W, H-band_y), (*INK, 255))
        d = ImageDraw.Draw(band)
        d.rectangle((0, 0, W, int(3*s)), fill=YELLOW)
        hour = f"ORE {self.t['kickoff']}" if self.t.get('kickoff') else ''
        rows = [(self.t.get('date'), WHITE, 34 if story else 28), (hour, YELLOW, 34 if story else 28),
                (self.t.get('place'), PINK, 19 if story else 16), (self.t.get('competition'), MUTED, 13 if story else 11)]
        words = [self.text(value, col, size, 506) for value, col, size in rows]
        words = [w for w in words if w is not None]
        free = band.height-int(3*s)-sum(w.height for w in words)
        gap = free/(len(words)+1)
        y = int(3*s)+gap
        for word in words:
            band.alpha_composite(word, (W//2-word.width//2, int(y)))
            y += word.height+gap
        self.card_band = band

    # ----------------------------------------------------------------- camera and effects
    def cam(self, img, P, S, z, dx=0., dy=0.):
        a = 1/z
        return img.transform((self.W, self.H), Image.Transform.AFFINE,
                             (a, 0, P[0]-(S[0]+dx)*a, 0, a, P[1]-(S[1]+dy)*a), Image.Resampling.NEAREST)

    def paste(self, base, spr, centre, s=1.0, alpha=1.0, nearest=False):
        if s <= 0 or alpha <= 0:
            return
        if abs(s-1) > 1e-3:
            spr = spr.resize((max(1, round(spr.width*s)), max(1, round(spr.height*s))),
                             Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR)
        spr = with_alpha(spr, alpha)
        x, y = round(centre[0]-spr.width/2), round(centre[1]-spr.height/2)
        if x >= self.W or y >= self.H or x+spr.width <= 0 or y+spr.height <= 0:
            return
        cx, cy = max(0, -x), max(0, -y)
        spr = spr.crop((cx, cy, min(spr.width, self.W-x), min(spr.height, self.H-y)))
        if spr.width > 0 and spr.height > 0:
            base.alpha_composite(spr, (max(0, x), max(0, y)))

    def typed(self, base, word, t, t0, t1, col, glow, y, size):
        if t < t0 or not word:
            return
        n = int(len(word)*seg(t, t0, t1)+.999)
        full, part = self.label(word, col, size, glow), self.label(word[:n], col, size, glow)
        if full is not None and part is not None:
            base.alpha_composite(part, (self.W//2-full.width//2, int(y-part.height/2)))

    def shake(self, t, hit, amp, decay=6.0):
        if t < hit:
            return 0., 0., 0.
        k = amp*self.scale*math.exp(-(t-hit)*decay)
        return k*math.sin(t*97.), k*math.cos(t*83.), k

    def glitch(self, img, rng, strength):
        a = np.array(img)
        H = self.H
        for _ in range(int(rng.integers(4, 10))):
            y0, h = int(rng.integers(0, H-40)), int(rng.integers(8, 60)*self.scale)
            a[y0:y0+h] = np.roll(a[y0:y0+h], int(rng.integers(-36, 36)*strength*self.scale), axis=1)
        return Image.fromarray(a)

    def mosaic(self, img, block):
        b = int(block)
        if b <= 1:
            return img
        small = img.resize((max(1, self.W//b), max(1, self.H//b)), Image.Resampling.BOX)
        return small.resize((self.W, self.H), Image.Resampling.NEAREST)

    def finish(self, img, split, flash=0., flash_col=WHITE):
        img = img.convert('RGB')
        if flash > 0:
            img = Image.blend(img, Image.new('RGB', img.size, flash_col), min(1., flash))
        img = ImageChops.multiply(img, self.mult)
        s = int(round(split*self.scale/2))
        if s:
            r, g, b = img.split()
            img = Image.merge('RGB', (ImageChops.offset(r, s, 0), g, ImageChops.offset(b, -s, 0)))
        return img

    # ----------------------------------------------------------------- shots
    def neon(self, t, i):
        """How lit the sign is: flickers on between T_ON and 1.3 s, a blink before the whip."""
        if t < T_ON+.1:
            return 0.
        if t < 1.3:
            rng = np.random.default_rng(5000+i//3)
            return 1. if rng.random() < .12+.88*seg(t, T_ON+.1, 1.25)**.7 else .08
        if 2.18 <= t < 2.24:
            return .25
        return 1.

    def shot_us(self, t, i, z, S):
        W, H = self.W, self.H
        img = self.bg_us.copy()
        centre = (W//2, int(H*.47))
        k = self.neon(t, i)
        if k > .5:
            self.paste(img, self.fl_glow, centre, 1.0, k*.9)
        self.paste(img, self.fl_on if k > .5 else self.fl_off, centre)
        return self.cam(img, centre, S, z)

    def them_state(self, t):
        """(x offset, bounce, angle, lit) of the crest rolling in from the side."""
        W = self.W
        side = -1 if self.left_ours is False else 1                       # it comes from its own side
        roll = 1-ease_out(seg(t, T_THEM, T_BOUNCE))
        x = side*(W*.5+self.crest.width)*roll
        bounce = -18*self.scale*abs(math.sin(seg(t, T_BOUNCE, T_BOUNCE+.4)*math.pi*2))*(1-seg(t, T_BOUNCE, T_BOUNCE+.4)) \
            if t >= T_BOUNCE else 0
        angle = -side*roll*200
        return x, bounce, angle, t >= T_BOUNCE+.12

    def trail(self, x, strength, side):
        """A striped speed trail in the opponent's colours, at low resolution."""
        if strength <= 0:
            return None
        GW, GH, c = self.GW, self.GH, self.c
        cy, r = int(GH*.47), self.crest.height//c//2-2
        gy, gx = np.mgrid[0:GH, 0:GW]
        head = x/c
        rel = (gx-head)/GW*side
        on = (np.abs(gy-cy) < r) & (rel > 0) & (BAYER[gy % 4, gx % 4] < (1-rel*1.6)*strength*1.2)
        a = np.zeros((GH, GW, 4), np.uint8)
        stripes = ((gy-cy+r)//4) % 2 == 0
        a[on & stripes] = (*self.c1, 255)
        a[on & ~stripes] = (*self.c2, 255)
        return self.up(Image.fromarray(a)).crop((0, 0, self.W, self.H))

    def scene_them(self, t):
        W, H = self.W, self.H
        img = self.bg_them.copy()
        x, bounce, angle, lit = self.them_state(t)
        centre = (W//2+x, int(H*.47)+bounce)
        side = -1 if self.left_ours is False else 1
        tr = self.trail(centre[0], 1-seg(t, T_BOUNCE, T_BOUNCE+.8), side)
        if tr is not None:
            img.alpha_composite(tr)
        spr = self.crest if abs(angle) < .5 else self.crest.rotate(angle, resample=Image.Resampling.NEAREST)
        if not lit:
            spr = Image.merge('RGBA', (*[ch.point(lambda v: int(v*.45)) for ch in spr.split()[:3]], spr.getchannel('A')))
        self.paste(img, spr, centre)
        return img

    def frame(self, t):
        """The frame at second t, as an RGB image."""
        W, H, s = self.W, self.H, self.scale
        i = int(round(t*30))
        rng = np.random.default_rng(i)
        split, flash, flash_col = 2.0, 0., WHITE
        story = self.format == 'Story 9:16'
        name_y, name_size = int(H*(.2 if story else .13)), 44 if story else 38
        if t < T_ON:                                                       # ---- static, the CRT switches on
            noise = (rng.random((H//(2*self.c)+1, W//(2*self.c)+1))*200).astype(np.uint8)
            full = Image.fromarray(noise).resize((W, H), Image.Resampling.NEAREST)
            hh = max(4, int(H*ease_out(seg(t, 0, .2))))
            out = Image.new('L', (W, H))
            out.paste(full.resize((W, hh)), (0, H//2-hh//2))
            return self.finish(Image.merge('RGB', [out]*3), 3)
        if t < T_THEM:                                                     # ---- our neon flamingo
            z = 2.1-.85*ease_out(seg(t, T_ON, T_WHIP))
            dx, dy, k = self.shake(t, 1.3, 7)
            img = self.shot_us(t, i, z*(1+2.4*k/W), (W/2+dx, H*.5+dy))
            if 1.3 <= t < 1.6:
                flash, flash_col = .35*(1-seg(t, 1.3, 1.6)), HOT
            self.typed(img, self.t['ours'], t, 1.45, 1.95, PINK, HOT, name_y, name_size)
            if t >= T_WHIP:                                                # whip-glitch out
                w = ease_in(seg(t, T_WHIP, T_THEM))
                split += 26*w
                img = self.glitch(ImageChops.offset(img, -int(W*.85*w)*(1 if self.left_ours else -1), 0), rng, 1+2*w)
        elif t < T_FACE:                                                   # ---- the opponent rolls in
            img = self.scene_them(t)
            z = 1.2+.12*ease_io(seg(t, T_THEM, T_FACE))
            dx, dy, k = self.shake(t, T_BOUNCE, 12)
            d2x, d2y, k2 = self.shake(t, T_BOUNCE+.12, 8)
            img = self.cam(img, (W//2, int(H*.47)), (W/2, H*.52), z*(1+2.4*max(k, k2)/W), dx+d2x, dy+d2y)
            if T_BOUNCE+.12 <= t < T_BOUNCE+.42:
                flash, flash_col = .32*(1-seg(t, T_BOUNCE+.12, T_BOUNCE+.42)), self.c1
            self.typed(img, self.t['opponent'], t, T_BOUNCE+.3, T_BOUNCE+.85, self.name_col, self.c1, name_y, name_size)
            if t < T_THEM+.15:
                split += 20*(1-seg(t, T_THEM, T_THEM+.15))
                img = self.glitch(img, rng, 1.5)
        elif t < T_CARD:                                                   # ---- face-off, VS on the drop, build-up
            grow = ease_io(seg(t, T_FACE, T_CARD-.1))
            build = seg(t, T_BUILD, T_CARD)
            jx = 11*s*ease_in(build)*math.sin(t*131)
            jy = 11*s*ease_in(build)*math.cos(t*117)
            dx, dy, k = self.shake(t, DROP, 15)
            # the diagonal leaves more room low on the left and high on the right
            pos = ((W*.29+dx+jx, H*.60+dy+jy), (W*.71+dx-jx, H*.38+dy-jy))
            size = (1.0+.14*grow)*(1+2.4*k/W)                              # the nights stay still: only the two grow
            us = self.bg_us.copy()
            at = pos[0] if self.left_ours else pos[1]
            self.paste(us, self.fl_glow, at, size, .9)
            self.paste(us, self.fl_on, at, size, nearest=True)
            them = self.bg_them.copy()
            self.paste(them, self.crest, pos[1] if self.left_ours else pos[0], size, nearest=True)
            img = Image.composite(*((us, them) if self.left_ours else (them, us)), self.split)
            img.alpha_composite(self.split_glow)
            img.alpha_composite(self.split_line)
            if t < T_FACE+.25:
                split += 18*(1-seg(t, T_FACE, T_FACE+.25))
            if t >= DROP-.18:
                size = 3.0-1.7*ease_in(seg(t, DROP-.18, DROP)) if t < DROP else 1.3*(1-.06*math.sin(math.pi*seg(t, DROP, DROP+.14)))
                self.paste(img, self.vs, (W/2+dx, H/2+dy), size)
            if DROP <= t < DROP+.32:
                flash = .6*(1-seg(t, DROP, DROP+.32))
                split += 14*(1-seg(t, DROP, DROP+.4))
            split += 18*ease_in(build)
            if build > 0:
                img = self.mosaic(img, 1+23*s*ease_in(build)/self.c*self.c)
                if build > .4 and rng.random() < .7:
                    img = self.glitch(img, rng, .7+build)
            if t >= T_CARD-.04:
                flash = 1.
        else:                                                              # ---- the poster assembles, then holds
            img = self.card_frame(t)
            dx, dy, k = self.shake(t, T_STAMP+.16, 14)
            z = 1.12-.12*ease_out(seg(t, T_CARD, T_CARD+1.1))+.025*ease_io(seg(t, T_STAMP+.4, LENGTH))
            if abs(z-1) > 1e-3 or k > .3:
                img = img.transform((W, H), Image.Transform.AFFINE,
                                    (1/z, 0, W/2-(W/2+dx)/z, 0, 1/z, H/2-(H/2+dy)/z), Image.Resampling.NEAREST)
            if t < T_CARD+.42:                                             # it resolves out of big blocks and white
                img = self.mosaic(img, 1+int(23*s*(1-ease_out(seg(t, T_CARD, T_CARD+.42)))))
                white = Image.fromarray(((self.bayer_big >= ease_out(seg(t, T_CARD, T_CARD+.4)))*255).astype(np.uint8))
                img.paste(WHITE, (0, 0), white)
            if T_STAMP+.16 <= t < T_STAMP+.45:
                flash, flash_col = .45*(1-seg(t, T_STAMP+.16, T_STAMP+.45)), HOT
                split += 14*(1-seg(t, T_STAMP+.16, T_STAMP+.5))
            if 10.0 <= t < 10.06:
                img = self.glitch(img, rng, 1.0)
        return self.finish(img, split, flash, flash_col)

    def card_frame(self, t):
        W, H, s = self.W, self.H, self.scale
        img = self.card_scene.copy()
        if t >= T_STAMP+.7:                                                # the flamingo's glow breathes
            k = .35+.3*math.sin((t-T_STAMP-.7)*4)
            img.alpha_composite(with_alpha(self.card_glow, k*.5), self.card_fl_pos)
        if t >= T_TOP:
            top_dy = int(-self.top_h*(1-ease_out(seg(t, T_TOP, T_TOP+.4))))
            img.alpha_composite(self.card_top, (0, top_dy))
            fill = ease_io(seg(t, T_BARS, T_BARS+.55))
            d = ImageDraw.Draw(img)
            for x0, y0, x1, y1, anchor in self.bars:                       # the energy bars charge from the middle out
                width = int((x1-x0)*fill)
                if width > 0:
                    box = (x1-width, y0+top_dy, x1, y1+top_dy) if anchor == 'l' else (x0, y0+top_dy, x0+width, y1+top_dy)
                    d.rectangle(box, fill=YELLOW)
        if t >= T_BAND:
            band_dy = int((H-self.band_y)*(1-ease_out(seg(t, T_BAND, T_BAND+.4))))
            img.alpha_composite(self.card_band, (0, self.band_y+band_dy))
        if t >= T_STAMP:
            size = 3.0-2.0*ease_in(seg(t, T_STAMP, T_STAMP+.16)) if t < T_STAMP+.16 \
                else 1-.06*math.sin(math.pi*seg(t, T_STAMP+.16, T_STAMP+.3))
            self.paste(img, self.vs, self.vs_pos, size)
        return img

    def poster(self):
        """The finished poster (the last frame, without camera moves)."""
        return self.finish(self.card_frame(LENGTH), 2.0)

    def events(self):
        """(second, samples) sound effects that follow the pictures."""
        import sounds
        out = [(0.0, sounds.power_on()), (1.3, sounds.impact(.7)), (T_WHIP, sounds.whoosh(.28)),
               (T_BOUNCE, sounds.impact(1)), (T_FACE, sounds.glitch(.3)), (DROP, sounds.impact(1.4)),
               (T_BUILD, sounds.pixelate(T_CARD-T_BUILD)), (T_TOP, sounds.whoosh(.3)), (T_BAND, sounds.whoosh(.3)),
               (T_BARS, sounds.ding(1)), (T_STAMP+.16, sounds.impact(1.2))]
        for n in range(len(self.t['ours'])):
            out.append((1.45+n*.5/max(1, len(self.t['ours'])), sounds.blip(n)*.5))
        for n in range(len(self.t['opponent'])):
            out.append((T_BOUNCE+.3+n*.55/max(1, len(self.t['opponent'])), sounds.blip(n+3)*.5))
        return out


def poster_png(texts, crest=None, format='Story 9:16', scale=2, look='auto'):
    out = io.BytesIO()
    Intro(texts, crest, format, scale, look=look).poster().save(out, 'PNG', optimize=True)
    return out.getvalue()


def render_video(texts, crest, path, fps=30, format='Story 9:16', scale=2, track=None, sound=True, volume=.8,
                 look='auto', progress_callback=None):
    from renderer import video_writer
    show = Intro(texts, crest, format, scale, track, look)
    total = int(round(show.length*fps))
    writer = video_writer(path, fps)
    try:
        for i in range(total):
            frame = show.frame(i/fps)
            if frame.width % 2 or frame.height % 2:
                frame = frame.crop((0, 0, frame.width-frame.width % 2, frame.height-frame.height % 2))
            writer.append_data(np.asarray(frame))
            if progress_callback and (i % fps == 0 or i == total-1):
                progress_callback((i+1)/total)
    finally:
        writer.close()
    if sound or track:
        import sounds
        events = show.events() if sound else []
        if track:
            import tracks
            music = tracks.render(track, show.length, DROP) if tracks.is_real(track) else sounds.chiptune(show.length, 0, track=track)
            events.append((0.0, music*.9))
        sounds.mux(path, sounds.mix(events, show.length, volume, ambient=False))
    return str(path)
