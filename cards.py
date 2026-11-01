"""Figurine Flamingos (3.9): holographic player cards, pack and album.

A card is built once in three passes - the background that takes the foil, the
foil mask and the ink on top (avatar, numbers, words) - so the holographic
shine can be redrawn for any tilt in a few milliseconds: the video tilts and
flips the card in perspective, the PNG freezes it at its best angle.

Editions (MVP, bomber, porta inviolata, capitano, nuovo acquisto, auguri,
base) choose title, pose and rarity; rarity chooses metal, foil and sparkle.
Everything is drawn here: pixel avatars from pixel_character, the Flamingos
crest, Inter Display (OFL, assets/fonts). No photos.
"""
from __future__ import annotations

import io
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT/'assets'/'fonts'
W, H = 320, 448                 # card size in layout units (5:7)
INK = (16, 12, 24)
PINK, CYAN, YELLOW, WHITE = (242, 104, 168), (121, 220, 247), (255, 201, 99), (246, 244, 252)

RARITIES = {
    'base': dict(name='Base', metal=((70, 80, 96), (160, 172, 188), (52, 60, 74)), accent=CYAN,
                 holo=0.0, sat=.0, spec=.28, glitter=0.0, glow=(121, 220, 247), gems=1),
    'rara': dict(name='Rara', metal=((70, 190, 236), (220, 250, 255), (44, 128, 214)), accent=CYAN,
                 holo=.16, sat=.28, spec=.36, glitter=.25, glow=(160, 230, 255), gems=2),
    'epica': dict(name='Epica', metal=((214, 74, 150), (255, 190, 226), (122, 70, 220)), accent=PINK,
                  holo=.34, sat=.62, spec=.42, glitter=.55, glow=(242, 104, 168), gems=3),
    'leggenda': dict(name='Leggendaria', metal=((255, 186, 72), (255, 244, 196), (224, 120, 40)), accent=YELLOW,
                     holo=.48, sat=.85, spec=.5, glitter=.9, glow=(255, 201, 99), gems=4),
}
EDITIONS = {
    'mvp': dict(name='MVP della partita', title='MVP DELLA PARTITA', badge='MVP', rarity='epica', pose='esultanza'),
    'bomber': dict(name='Bomber', title='BOMBER', badge='BOMBER', rarity='leggenda', pose='palleggio'),
    'muro': dict(name='Porta inviolata', title='PORTA INVIOLATA', badge='MURO', rarity='epica', pose='guanti'),
    'capitano': dict(name='Capitano', title='CAPITANO', badge='C', rarity='rara', pose='conserte'),
    'benvenuto': dict(name='Nuovo acquisto', title='NUOVO ACQUISTO', badge='NEW', rarity='rara', pose='saluto'),
    'auguri': dict(name='Buon compleanno', title='BUON COMPLEANNO', badge='AUGURI', rarity='epica', pose='esultanza'),
    'base': dict(name='Base (album)', title='', badge='', rarity='base', pose='ferma'),
}
ROLES = {'P': ('POR', 'PORTIERE'), 'D': ('DIF', 'DIFENSORE'), 'C': ('CEN', 'CENTROCAMPISTA'), 'A': ('ATT', 'ATTACCANTE'),
         'ALL': ('MR', 'ALLENATORE'), 'DIR': ('DIR', 'DIRIGENTE')}


# --- Type ---------------------------------------------------------------------------------------

@lru_cache(maxsize=64)
def font(kind, size):
    """kind: 'black' (Black Italic), 'heavy' (ExtraBold) or 'bold'."""
    name = {'black': 'InterDisplay-BlackItalic.otf', 'heavy': 'InterDisplay-ExtraBold.otf'}.get(kind, 'InterDisplay-Bold.otf')
    try:
        return ImageFont.truetype(str(FONTS/name), max(1, int(round(size))))
    except OSError:      # never stop a card for a font
        from renderer import standard_font
        return standard_font(size)


SUPPORTED = set(map(chr, range(0x20, 0x7F))) | set(map(chr, range(0xA0, 0x100))) | set('–—‘’“”•…€№←↑→↓★☆½·°▲▼♥✓')


def printable(value):
    """Only the characters the bundled font has (emoji and the like would print as boxes)."""
    return ''.join(ch for ch in str(value) if ch in SUPPORTED).strip()


def text(value, kind, size, color, s=1.0, max_width=None, tracking=0.0, stroke=0.0, stroke_color=INK, shadow=None):
    """The words as a tight RGBA image (layout units x s). Shrinks to max_width; tracking in units."""
    value = printable(value)
    if not value.strip():
        return None
    px = size*s
    while True:
        f = font(kind, px)
        spacing = tracking*s*px/(size*s) if size else 0
        widths = [f.getlength(ch) for ch in value]
        total = sum(widths)+spacing*max(0, len(value)-1)
        if not max_width or total <= max_width*s or px <= 6:
            break
        px *= max(.7, min(.97, max_width*s/total))
    pad = int(math.ceil(stroke*s))+4
    ascent, descent = f.getmetrics()
    img = Image.new('RGBA', (int(math.ceil(total))+2*pad+int(px*.25), ascent+descent+2*pad))
    d = ImageDraw.Draw(img)
    x = pad
    for ch, w in zip(value, widths):
        if stroke:
            d.text((x, pad), ch, font=f, fill=(*stroke_color, 255), stroke_width=int(round(stroke*s)),
                   stroke_fill=(*stroke_color, 255))
        x += w+spacing
    x = pad
    for ch, w in zip(value, widths):
        d.text((x, pad), ch, font=f, fill=(*color[:3], color[3] if len(color) > 3 else 255))
        x += w+spacing
    box = img.getchannel('A').getbbox()
    img = img.crop(box) if box else img
    if shadow:
        dx, dy, blur, alpha = shadow
        base = Image.new('RGBA', (img.width+int(abs(dx)*s)+int(blur*s*3)+2, img.height+int(abs(dy)*s)+int(blur*s*3)+2))
        sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
        sh.putalpha(img.getchannel('A').point(lambda v: v*alpha//255))
        off = int(blur*s*1.5)+1
        base.alpha_composite(sh, (off+int(max(0, dx)*s), off+int(max(0, dy)*s)))
        base = base.filter(ImageFilter.GaussianBlur(blur*s)) if blur else base
        base.alpha_composite(img, (off+int(max(0, -dx)*s), off+int(max(0, -dy)*s)))
        img = base
    return img


def put(canvas, img, cx, cy, s=1.0, anchor='mm'):
    """Paste an RGBA image at a layout point (centre by default; 'lm' left-middle, 'rm' right-middle...)."""
    if img is None:
        return
    x = cx*s-(0 if anchor[0] == 'l' else img.width if anchor[0] == 'r' else img.width/2)
    y = cy*s-(0 if anchor[1] == 't' else img.height if anchor[1] == 'b' else img.height/2)
    canvas.alpha_composite(img, (int(round(x)), int(round(y))))


def vote_text(vote):
    """8.5 -> '8½', 7.0 -> '7'."""
    if vote is None:
        return ''
    whole = int(math.floor(float(vote)))
    return f'{whole}½' if float(vote)-whole >= .5 else str(whole)


# --- Shapes and gradients ---------------------------------------------------------------------------

def _grad(size, stops, angle=90.0):
    """RGB gradient (numpy float 0..1) along `angle` degrees (90 = top to bottom) through colour stops."""
    w, h = size
    a = math.radians(angle)
    xs = np.arange(w, dtype=np.float32)*math.cos(a)
    ys = np.arange(h, dtype=np.float32)*math.sin(a)
    u = ys[:, None]+xs[None, :]
    lo, hi = float(u.min()), float(u.max())
    bins = 2048
    index = ((u-lo)*((bins-1)/max(1e-6, hi-lo))).astype(np.int32)
    stops = np.array(stops, np.float32)/255
    pos = np.linspace(0, len(stops)-1, bins, dtype=np.float32)
    i = np.minimum(pos.astype(int), len(stops)-2)
    f = (pos-i)[:, None]
    table = stops[i]*(1-f)+stops[i+1]*f
    return table[index]


def _rounded_mask(size, radius, inset=0):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((inset, inset, size[0]-1-inset, size[1]-1-inset), radius=max(0, radius-inset), fill=255)
    return m


def _to_img(rgb, alpha=None):
    arr = np.clip(rgb*255, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, 'RGB').convert('RGBA')
    if alpha is not None:
        img.putalpha(alpha)
    return img


def _halftone(size, s, color, alpha=70, step=7.0, angle=-18):
    """A dotted screen that fades towards the bottom, rotated: the printed-card texture."""
    w, h = size
    img = Image.new('RGBA', (int(w*1.5), int(h*1.5)))
    d = ImageDraw.Draw(img)
    st = step*s
    for j in range(int(img.height/st)+1):
        for i in range(int(img.width/st)+1):
            r = st*.42*(1-min(1.0, j*st/img.height)*.85)
            if r < .6:
                continue
            x, y = i*st+(st/2 if j % 2 else 0), j*st
            d.ellipse((x-r, y-r, x+r, y+r), fill=(*color, alpha))
    img = img.rotate(angle, resample=Image.Resampling.BICUBIC)
    return img.crop(((img.width-w)//2, (img.height-h)//2, (img.width-w)//2+w, (img.height-h)//2+h))


# --- The card ---------------------------------------------------------------------------------------

def spec_for(card):
    """A complete card spec (defaults filled in) from a partial one."""
    edition = card.get('edition') if card.get('edition') in EDITIONS else 'base'
    ed = EDITIONS[edition]
    rarity = card.get('rarity') if card.get('rarity') in RARITIES else ed['rarity']
    role = card.get('role') if card.get('role') in ROLES else 'C'
    out = dict(name=str(card.get('name') or 'GIOCATORE').upper()[:18], number=int(card.get('number') or 0), role=role,
               look=card.get('look'), avatar=card.get('avatar', ''), edition=edition, rarity=rarity,
               vote=card.get('vote'), stats=list(card.get('stats') or [])[:3], serial=card.get('serial'),
               season=str(card.get('season') or '2026/27'), team=str(card.get('team') or 'FLAMINGOS').upper()[:16],
               pose=card.get('pose') or ed['pose'], title=card.get('title') or ed['title'],
               captain=bool(card.get('captain')))
    if role == 'P' and out['pose'] in ('palleggio', 'esultanza') and edition != 'auguri':
        out['pose'] = 'guanti'
    return out


class Card:
    """A built card: background that takes the foil, the foil mask, the sprite and the words.

    render() shades it for a tilt; ink_for() swaps the sprite frame (blink, pose) and the numbers (for the
    count-up), cached."""

    ART = (18, 18, 302, 300)

    def __init__(self, card, s=2.0, logo=None):
        self.spec = spec_for(card)
        self.s = s
        self.size = (int(round(W*s)), int(round(H*s)))
        self.rarity = RARITIES[self.spec['rarity']]
        self.logo = logo
        self.art_box = self.ART
        self._background()
        self.sprite = self._sprite()
        self.words = self._words(self.spec)
        ink = self.sprite.copy()
        ink.alpha_composite(self.words)
        self.ink = ink
        self.ink_arr = np.asarray(ink, np.float32)/255
        self._inks = {}
        self._fields()

    def _background(self):
        s, (w, h), sp, rr = self.s, self.size, self.spec, self.rarity
        metal = rr['metal']
        shape = _rounded_mask(self.size, int(20*s))
        self.alpha = shape
        frame = _grad(self.size, (metal[0], metal[1], metal[0], metal[2], metal[1]), 62)
        sheen = _grad(self.size, ((0, 0, 0), (60, 60, 60), (0, 0, 0)), 20)
        bg = _to_img(np.clip(frame+sheen*.35, 0, 1))
        inner = _rounded_mask(self.size, int(20*s), int(9*s))
        panel = _to_img(_grad(self.size, ((34, 24, 46), (18, 13, 27), (12, 9, 18)), 90))
        lines = Image.new('RGBA', self.size)
        ld = ImageDraw.Draw(lines)
        for k in range(-40, 60):                          # fine diagonal print lines on the dark panel
            x = k*7*s
            ld.line((x, 0, x+h*.5, h), fill=(255, 255, 255, 7), width=max(1, int(s)))
        panel.alpha_composite(lines)
        bg.paste(panel, (0, 0), inner)
        d = ImageDraw.Draw(bg)
        d.rounded_rectangle((int(9*s), int(9*s), w-1-int(9*s), h-1-int(9*s)), radius=int(11*s),
                            outline=(*[min(255, c+50) for c in metal[1]], 255), width=max(1, int(1.2*s)))
        d.rounded_rectangle((int(2*s), int(2*s), w-1-int(2*s), h-1-int(2*s)), radius=int(18*s),
                            outline=(255, 255, 255, 120), width=max(1, int(.8*s)))
        ax0, ay0, ax1, ay1 = self.ART
        aw, ah = int((ax1-ax0)*s), int((ay1-ay0)*s)
        glow = rr['glow']
        yy, xx = np.mgrid[0:ah, 0:aw].astype(np.float32)
        r = np.sqrt(((xx-aw*.6)/(aw*.6))**2+((yy-ah*.45)/(ah*.62))**2)
        base_col = np.array((26, 18, 38), np.float32)/255
        g = np.array(glow, np.float32)/255
        k = np.exp(-r*1.6)[..., None]
        art_img = _to_img(base_col[None, None]*(1-k)+(g*.55+base_col*.45)[None, None]*k)
        art_img.alpha_composite(_halftone((aw, ah), s, tuple(min(255, int(c*1.1)) for c in glow), 46, 6.5))
        streaks = Image.new('RGBA', (aw, ah))
        sd = ImageDraw.Draw(streaks)
        rnd = np.random.default_rng(len(sp['name'])*7+sp['number'])
        for _ in range(9):
            x = rnd.uniform(-.2, 1.2)*aw
            width = rnd.uniform(3, 14)*s
            sd.polygon([(x, 0), (x+width, 0), (x+width-ah*.55, ah), (x-ah*.55, ah)],
                       fill=(255, 255, 255, int(rnd.uniform(8, 22))))
        art_img.alpha_composite(streaks)
        if sp['number']:
            big = text(str(sp['number']), 'black', 200, (*glow, 0), s, stroke=2.2,
                       stroke_color=tuple(min(255, c+30) for c in glow))
            if big:
                big.putalpha(big.getchannel('A').point(lambda v: v*120//255))
                put(art_img, big, (ax1-ax0)*.66, (ay1-ay0)*.57, s)
        art_mask = _rounded_mask((aw, ah), int(10*s))
        bg.paste(art_img, (int(ax0*s), int(ay0*s)), art_mask)
        foil = Image.new('L', self.size, 0)
        foil.paste(255, (0, 0), shape)
        foil.paste(0, (0, 0), inner)
        foil.paste(art_mask.point(lambda v: v*170//255), (int(ax0*s), int(ay0*s)), art_mask)
        self.bg = (np.asarray(bg.convert('RGB'), np.float32)/255).astype(np.float32)
        self.foil = (np.asarray(foil, np.float32)/255).astype(np.float32)

    def _sprite(self, frame=None, beat=0):
        """The pixel player, clipped to the art window, a little right of centre (the numbers sit left)."""
        import pixel_character
        s, sp = self.s, self.spec
        ax0, ay0, ax1, ay1 = self.ART
        picture = pixel_character.picture(dict(look=sp['look'], avatar=sp['avatar']), 'crt', frame=frame,
                                          pose=sp['pose'], beat=beat)
        target = (ay1-ay0)*s*.8
        factor = max(1, int(target//picture.height))
        big = picture.resize((picture.width*factor, picture.height*factor), Image.Resampling.NEAREST)
        shadow = Image.new('RGBA', big.size, (0, 0, 0, 0))
        shadow.putalpha(big.getchannel('A').point(lambda v: v*120//255))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6*s))
        x = int((ax0+(ax1-ax0)*.585)*s-big.width/2)
        y = int(ay1*s-big.height)
        art = Image.new('RGBA', self.size)
        art.alpha_composite(shadow, (x+int(5*s), y+int(3*s)))
        art.alpha_composite(big, (x, y))
        window = Image.new('L', self.size, 0)
        ImageDraw.Draw(window).rounded_rectangle((int(ax0*s), int(ay0*s), int(ax1*s), int(ay1*s)), radius=int(10*s),
                                                 fill=255)
        art.putalpha(Image.fromarray(np.minimum(np.asarray(art.getchannel('A')), np.asarray(window))))
        return art

    def _words(self, sp):
        """Everything printed over the art and on the panel: numbers, badges, name, stats, footer."""
        s, rr = self.s, self.rarity
        metal, accent = rr['metal'], rr['accent']
        ax0, ay0, ax1, ay1 = self.ART
        ink = Image.new('RGBA', self.size)
        di = ImageDraw.Draw(ink)
        di.rounded_rectangle((int(ax0*s), int(ay0*s), int(ax1*s), int(ay1*s)), radius=int(10*s),
                             outline=(*[min(255, c+40) for c in metal[1]], 255), width=max(1, int(1.6*s)))
        # Top left: the vote (or the number), the role, the crest.
        voted = sp['vote'] is not None
        value = vote_text(sp['vote']) if voted else (str(sp['number']) if sp['number'] else ROLES[sp['role']][0])
        put(ink, text(value, 'black', 56, WHITE, s, max_width=96, shadow=(0, 2, 2.5, 150)), 30, 64, s, 'lm')
        label = 'VOTO' if voted else ROLES[sp['role']][1]
        put(ink, text(label, 'heavy', 10.5, accent, s, max_width=104, tracking=1.6, shadow=(0, 1, 1.5, 170)), 32, 101, s, 'lm')
        y = 116
        if voted:
            role = ROLES[sp['role']][0]+(f"  #{sp['number']}" if sp['number'] else '')
            put(ink, text(role, 'heavy', 10, WHITE, s, tracking=1.4, shadow=(0, 1, 1.5, 170)), 32, y, s, 'lm')
            y += 16
        if self.logo:
            from renderer import clean_logo
            base = max(1, int(round(s)))
            crest = clean_logo(self.logo, 32, True, base)
            crest = crest.resize((max(1, int(crest.width*s/base)), max(1, int(crest.height*s/base))), Image.Resampling.LANCZOS)
            put(ink, crest, 32, y+6, s, 'lt')
        ed = EDITIONS[sp['edition']]
        if ed['badge']:
            badge = text(ed['badge'], 'black', 14, INK, s, tracking=.8)
            bw = badge.width/s+20
            x1, y0 = ax1-10, ay0+12
            di.rounded_rectangle((int((x1-bw)*s), int(y0*s), int(x1*s), int((y0+25)*s)), radius=int(12.5*s),
                                 fill=(*metal[1], 255), outline=(255, 255, 255, 230), width=max(1, int(1.2*s)))
            put(ink, badge, x1-bw/2, y0+12.5, s)
        if sp['captain'] and sp['edition'] != 'capitano':
            cx, cy = ax1-23, ay0+(52 if ed['badge'] else 24)
            di.ellipse((int((cx-12)*s), int((cy-12)*s), int((cx+12)*s), int((cy+12)*s)), fill=(*YELLOW, 255),
                       outline=(255, 255, 255, 230), width=max(1, int(1.2*s)))
            put(ink, text('C', 'black', 15, INK, s), cx, cy, s)
        # Name plate and divider.
        put(ink, text(sp['name'], 'black', 40, WHITE, s, max_width=268, shadow=(0, 2, 3, 170)), 160, 327, s)
        y = 354
        di.line((int(46*s), int(y*s), int(146*s), int(y*s)), fill=(*accent, 255), width=max(1, int(1.6*s)))
        di.line((int(174*s), int(y*s), int(274*s), int(y*s)), fill=(*accent, 255), width=max(1, int(1.6*s)))
        di.polygon([(160*s, (y-5)*s), (165*s, y*s), (160*s, (y+5)*s), (155*s, y*s)], fill=(*accent, 255))
        stats = sp['stats'] or [('RUOLO', ROLES[sp['role']][0]), ('MAGLIA', f"#{sp['number']}" if sp['number'] else '-'),
                                ('STAGIONE', sp['season'][-5:])]
        n = len(stats)
        span = 268/max(1, n)
        for i, (label_, value_) in enumerate(stats):
            cx = 160+(i-(n-1)/2)*span
            put(ink, text(str(value_).upper(), 'black', 26, WHITE, s, max_width=span-12), cx, 380, s)
            put(ink, text(str(label_).upper(), 'heavy', 8.5, accent, s, max_width=span-8, tracking=1.3), cx, 401, s)
            if i:
                sx = cx-span/2
                di.line((int(sx*s), int(368*s), int(sx*s), int(406*s)), fill=(255, 255, 255, 46), width=max(1, int(s)))
        put(ink, text(f"{sp['team']}  {sp['season']}", 'heavy', 8, (*WHITE[:3], 190), s, tracking=1.2), 26, 424, s, 'lm')
        if sp['serial']:
            a, b = sp['serial']
            put(ink, text(f'{int(a):02d}/{int(b):02d}', 'heavy', 8, (*WHITE[:3], 190), s, tracking=1.2), 294, 424, s, 'rm')
        gems = rr['gems']
        for i in range(gems):
            cx = 160+(i-(gems-1)/2)*11
            di.polygon([(cx*s, 419*s), ((cx+4)*s, 424*s), (cx*s, 429*s), ((cx-4)*s, 424*s)], fill=(*metal[1], 255),
                       outline=(255, 255, 255, 200))
        return ink

    def _fields(self):
        w, h = self.size
        s = self.s
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.u = (xx/w*.8+yy/h*.6)
        self.v = (xx/w*.6-yy/h*.8)
        cell = max(1, int(3*s))
        rnd = np.random.default_rng(11)
        sparkle = rnd.random((h//cell+1, w//cell+1)).astype(np.float32)
        sparkle = np.repeat(np.repeat(sparkle, cell, 0), cell, 1)[:h, :w]
        self.sparkle = np.where(sparkle > .985, (sparkle-.985)/.015, 0).astype(np.float32)
        seed = rnd.random((h//cell+1, w//cell+1)).astype(np.float32)
        self.seed = np.repeat(np.repeat(seed, cell, 0), cell, 1)[:h, :w]*6.283

    def ink_for(self, frame=None, beat=0, vote=None, stats=None):
        """The ink with another sprite frame and/or other numbers (cached)."""
        key = (frame, beat, vote, tuple(map(tuple, stats)) if stats is not None else None)
        if key == (None, 0, None, None):
            return self.ink_arr
        if key not in self._inks:
            sprite = self._sprite(frame, beat) if (frame or beat) else self.sprite
            if vote is None and stats is None:
                words = self.words
            else:
                sp = dict(self.spec)
                if vote is not None:
                    sp['vote'] = vote
                if stats is not None:
                    sp['stats'] = list(stats)
                words = self._words(sp)
            ink = sprite.copy()
            ink.alpha_composite(words)
            if len(self._inks) > 40:
                self._inks.clear()
            self._inks[key] = np.asarray(ink, np.float32)/255
        return self._inks[key]

    # Shader ------------------------------------------------------------------------------------------
    BINS = 1024

    def _luts(self):
        """Per-pixel indices into 1D tables: the foil and the light only depend on two diagonal coordinates."""
        if getattr(self, '_u_idx', None) is None:
            n = self.BINS
            self._u_lo, self._u_hi = float(self.u.min()), float(self.u.max())
            self._v_lo, self._v_hi = float(self.v.min()), float(self.v.max())
            self._u_idx = np.clip(((self.u-self._u_lo)/(self._u_hi-self._u_lo+1e-9)*(n-1)).astype(np.int32), 0, n-1)
            self._v_idx = np.clip(((self.v-self._v_lo)/(self._v_hi-self._v_lo+1e-9)*(n-1)).astype(np.int32), 0, n-1)
            self._u_axis = np.linspace(self._u_lo, self._u_hi, n, dtype=np.float32)
            self._v_axis = np.linspace(self._v_lo, self._v_hi, n, dtype=np.float32)
            ys, xs = np.nonzero(self.sparkle > 0)
            self._sp_y, self._sp_x = ys, xs
            self._sp_val = self.sparkle[ys, xs]
            self._sp_seed = self.seed[ys, xs]
            self._foil3 = self.foil[..., None]
            self._ink_a = {}

    def render(self, yaw=0.0, pitch=0.0, t=0.0, light=1.0, ink=None):
        """The card for a tilt (degrees): foil rainbow, glitter and the specular band move with it."""
        self._luts()
        rr = self.rarity
        foil = self._foil3
        ty, tp = yaw/30.0, pitch/30.0
        out = self.bg.copy()
        if rr['holo'] > 0:
            hue = self._u_axis*1.7+ty*.55+tp*.35+t*.03
            phase = 6.2832*hue[:, None]+np.array([0, 2.094, 4.189], np.float32)[None, :]
            rainbow = (1-rr['sat'])+rr['sat']*(.5+.5*np.cos(phase))            # bins x 3
            amount = rr['holo']*(.65+.35*np.cos((self._v_axis+ty*.3)*6.2832))  # bins
            add = rainbow[self._u_idx]*amount[self._v_idx][..., None]
            out += (add*(1-out))*foil                                           # screen, only on the foil
        if rr['glitter'] > 0 and len(self._sp_y):
            tw = np.clip(np.sin(self._sp_seed+ty*9+tp*7+t*2.5), 0, 1)**3*self._sp_val*rr['glitter']
            g = np.minimum(1, tw*self.foil[self._sp_y, self._sp_x]*1.2)[:, None]
            out[self._sp_y, self._sp_x] = 1-(1-out[self._sp_y, self._sp_x])*(1-g)
        pos = .5+ty*.75-tp*.25
        d = self._u_axis/1.4-pos
        band_lut = (np.exp(-(d/.055)**2)+.35*np.exp(-(d/.22)**2))*rr['spec']
        band = band_lut[self._u_idx][..., None]
        out += band*(.55+.45*foil)*(1-out)
        ink_arr = self.ink_arr if ink is None else ink
        a = ink_arr[..., 3:4]
        out += (ink_arr[..., :3]-out)*a
        out += band*.18*a*(1-out)
        if light != 1.0:
            out *= light
        rgba = np.empty(out.shape[:2]+(4,), np.uint8)
        np.multiply(out, 255, out=out)
        np.clip(out, 0, 255, out=out)
        rgba[..., :3] = out
        rgba[..., 3] = self._alpha_arr()
        return Image.fromarray(rgba, 'RGBA')

    def _alpha_arr(self):
        if getattr(self, '_alpha_np', None) is None:
            self._alpha_np = np.asarray(self.alpha, np.uint8)
        return self._alpha_np

    def flat(self, yaw=-9.0, pitch=4.0):
        """The card frozen at its best angle, transparent outside the corners."""
        return self.render(yaw, pitch)


def _hsv(h, sat):
    """Vectorised HSV->RGB for value 1."""
    i = np.floor(h*6).astype(int) % 6
    f = h*6-np.floor(h*6)
    p = np.full_like(h, 1-sat)
    q = 1-sat*f
    t = 1-sat*(1-f)
    v = np.ones_like(h)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


# --- Back and pack ------------------------------------------------------------------------------------

def back(s=2.0, logo=None, rarity='base', team='FLAMINGOS', season='2026/27'):
    """The back of every card: crest, diagonal pattern, the collection's name."""
    size = (int(round(W*s)), int(round(H*s)))
    rr = RARITIES.get(rarity, RARITIES['base'])
    img = _to_img(_grad(size, ((36, 22, 52), (16, 11, 26), (40, 18, 46)), 70))
    pat = Image.new('RGBA', size)
    d = ImageDraw.Draw(pat)
    step = 22*s
    for k in range(-int(size[1]/step)-2, int(size[0]/step)+int(size[1]/step)+2):
        x = k*step
        d.line((x, 0, x+size[1]*.6, size[1]), fill=(*PINK, 34), width=max(1, int(5*s)))
    img.alpha_composite(pat)
    img.alpha_composite(_halftone(size, s, CYAN, 26, 9))
    d = ImageDraw.Draw(img)
    metal = rr['metal']
    d.rounded_rectangle((int(5*s), int(5*s), size[0]-1-int(5*s), size[1]-1-int(5*s)), radius=int(16*s),
                        outline=(*metal[1], 255), width=max(2, int(5*s)))
    d.rounded_rectangle((int(16*s), int(16*s), size[0]-1-int(16*s), size[1]-1-int(16*s)), radius=int(10*s),
                        outline=(*PINK, 200), width=max(1, int(1.4*s)))
    cx, cy = size[0]/2, size[1]*.45
    rad = 92*s
    d.ellipse((cx-rad, cy-rad, cx+rad, cy+rad), fill=(18, 12, 28, 255), outline=(*metal[1], 255), width=max(2, int(4*s)))
    d.ellipse((cx-rad+9*s, cy-rad+9*s, cx+rad-9*s, cy+rad-9*s), outline=(*PINK, 220), width=max(1, int(1.6*s)))
    if logo:
        from renderer import clean_logo
        crest = clean_logo(logo, 110, True, max(1, int(round(s))))
        k = 1.25*rad/max(crest.width, crest.height)
        crest = crest.resize((int(crest.width*k), int(crest.height*k)), Image.Resampling.LANCZOS)
        img.alpha_composite(crest, (int(cx-crest.width/2), int(cy-crest.height/2)))
    put(img, text('FIGURINE', 'black', 30, WHITE, s, tracking=1.5, shadow=(0, 2, 3, 170)), W/2, 352, s)
    put(img, text(f'{team}  {season}', 'heavy', 11, CYAN, s, tracking=2.4), W/2, 380, s)
    img.putalpha(_rounded_mask(size, int(20*s)))
    return img


def pack(s=2.0, logo=None, rarity='epica', edition='mvp', team='FLAMINGOS', season='2026/27'):
    """The foil pack (taller than a card, crimped ends). Returns (image, tear_y in pixels)."""
    pw, ph = 330, 500
    size = (int(pw*s), int(ph*s))
    rr = RARITIES.get(rarity, RARITIES['epica'])
    body = _grad(size, ((58, 20, 70), (226, 84, 160), (86, 40, 170), (30, 14, 48)), 75)
    sheen = _grad(size, ((0, 0, 0), (90, 90, 110), (0, 0, 0), (40, 40, 60), (0, 0, 0)), 15)
    img = _to_img(np.clip(body+sheen*.45, 0, 1))
    img.alpha_composite(_halftone(size, s, (255, 255, 255), 22, 6))
    d = ImageDraw.Draw(img)
    # Crimped ends.
    crimp = 26
    for y0 in (0, ph-crimp):
        d.rectangle((0, int(y0*s), size[0], int((y0+crimp)*s)), fill=(*rr['metal'][1], 255))
        for k in range(0, int(pw/6)+1):
            x = k*6*s
            d.line((x, int(y0*s), x, int((y0+crimp)*s)), fill=(*rr['metal'][2], 255), width=max(1, int(1.4*s)))
    # Logo and words.
    cx = size[0]/2
    if logo:
        from renderer import clean_logo
        crest = clean_logo(logo, 150, True, max(1, int(round(s))))
        k = 150*s/max(crest.width, crest.height)
        crest = crest.resize((int(crest.width*k), int(crest.height*k)), Image.Resampling.LANCZOS)
        glow = Image.new('RGBA', crest.size, (*rr['glow'], 0))
        glow.putalpha(crest.getchannel('A'))
        glow = glow.filter(ImageFilter.GaussianBlur(14*s))
        img.alpha_composite(glow, (int(cx-crest.width/2), int(150*s-crest.height/2)))
        img.alpha_composite(crest, (int(cx-crest.width/2), int(150*s-crest.height/2)))
    put(img, text('FIGURINE', 'black', 50, WHITE, s, tracking=1.0, shadow=(0, 3, 4, 190)), pw/2, 286, s)
    put(img, text(team, 'black', 30, YELLOW, s, tracking=1.5, shadow=(0, 2, 3, 190)), pw/2, 326, s)
    put(img, text(f'STAGIONE {season}', 'heavy', 12, WHITE, s, tracking=3), pw/2, 358, s)
    label = EDITIONS.get(edition, EDITIONS['mvp'])['title'] or 'EDIZIONE BASE'
    tag = text(f'1 CARTA  ·  {label}', 'heavy', 11, INK, s, tracking=1.4, max_width=270)
    tw = tag.width/s+28
    d.rounded_rectangle((int((pw/2-tw/2)*s), int(392*s), int((pw/2+tw/2)*s), int(418*s)), radius=int(13*s),
                        fill=(*rr['metal'][1], 255))
    put(img, tag, pw/2, 405, s)
    # Tear line: dashes under the top crimp.
    tear = 48
    for k in range(0, int(pw/10)):
        x = k*10*s
        d.line((x, int(tear*s), x+5*s, int(tear*s)), fill=(255, 255, 255, 150), width=max(1, int(1.2*s)))
    mask = Image.new('L', size, 0)
    md = ImageDraw.Draw(mask)
    md.rectangle((0, int(crimp*s*.35), size[0], size[1]-int(crimp*s*.35)), fill=255)
    for y0, sign in ((0, 1), (size[1], -1)):     # zigzag on the very ends
        pts = []
        for k in range(0, int(pw/8)+2):
            pts.append((k*8*s, y0+sign*(0 if k % 2 else crimp*s*.35)))
        md.polygon([(0, y0)]+pts+[(size[0], y0)], fill=255)
    img.putalpha(mask)
    return img, int(tear*s)


# --- Perspective ---------------------------------------------------------------------------------------

def _coeffs(src, dst):
    """PIL PERSPECTIVE coefficients mapping output points dst to input points src."""
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u*x, -u*y])
        m.append([0, 0, 0, x, y, 1, -v*x, -v*y])
    a = np.array(m, np.float64)
    b = np.array(src, np.float64).reshape(8)
    return np.linalg.solve(a, b)


def corners(w, h, yaw, pitch, roll=0.0, scale=1.0, distance=4.2):
    """Screen corners (relative to the centre) of a w x h card turned by yaw/pitch/roll degrees."""
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    d = distance*max(w, h)
    out = []
    for x, y in ((-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)):
        x, y = x*cr-y*sr, x*sr+y*cr
        x1, z1 = x*cy_, x*sy_
        y2, z2 = y*cp-z1*sp, y*sp+z1*cp
        f = d/(d+z2)
        out.append((x1*f*scale, y2*f*scale))
    return out


def warp(img, centre, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, back_img=None, quality='high'):
    """The card turned in 3D as (image, x, y) for pasting; past 90 degrees the back shows (mirrored)."""
    w, h = img.size
    pts = corners(w, h, yaw, pitch, roll, scale)
    facing = math.cos(math.radians(yaw))*math.cos(math.radians(pitch)) >= 0
    face = img if facing or back_img is None else back_img.resize(img.size)
    src = [(0, 0), (w, 0), (w, h), (0, h)] if facing else [(w, 0), (0, 0), (0, h), (w, h)]
    xs = [centre[0]+p[0] for p in pts]
    ys = [centre[1]+p[1] for p in pts]
    x0, y0 = int(math.floor(min(xs)))-2, int(math.floor(min(ys)))-2
    x1, y1 = int(math.ceil(max(xs)))+2, int(math.ceil(max(ys)))+2
    if x1-x0 < 3 or y1-y0 < 3:
        return None, x0, y0
    dst = [(x-x0, y-y0) for x, y in zip(xs, ys)]
    mode = Image.Resampling.BICUBIC if quality == 'high' else Image.Resampling.BILINEAR
    return face.transform((x1-x0, y1-y0), Image.Transform.PERSPECTIVE, tuple(_coeffs(src, dst)), mode), x0, y0


def project(img, canvas, centre, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, back_img=None, shadow=True, quality='high'):
    """Draw a card on an RGBA canvas turned in 3D (with a soft shadow). Returns the warped image."""
    warped, x0, y0 = warp(img, centre, yaw, pitch, roll, scale, back_img, quality)
    if warped is None:
        return None
    if shadow:
        sh = Image.new('RGBA', warped.size, (0, 0, 0, 0))
        sh.putalpha(warped.getchannel('A').point(lambda v: v*120//255))
        blur = max(2, int(min(img.size)*scale*.035))
        pad = blur*3
        big = Image.new('RGBA', (sh.width+2*pad, sh.height+2*pad))
        big.alpha_composite(sh, (pad, pad))
        big = big.filter(ImageFilter.GaussianBlur(blur))
        canvas.alpha_composite(big, (x0-pad+int(blur*.6), y0-pad+int(blur*1.4)))
    canvas.alpha_composite(warped, (x0, y0))
    return warped


# --- Stills -------------------------------------------------------------------------------------------

def card_png(card, logo=None, height=1500):
    """The card alone, transparent around the corners (stickers, WhatsApp)."""
    s = height/H
    built = Card(card, s, logo)
    out = io.BytesIO()
    built.flat().save(out, 'PNG', compress_level=5)
    return out.getvalue()
