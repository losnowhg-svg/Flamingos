"""Apertura bustina (3.9): the pack-opening video for a Flamingos card.

Timeline (the drop of the music is at 4 s, like every other video of the
studio, and the hints fall on the beats of the chosen track):

    0.1-0.9  the pack drops in over a synthwave floor, light rays behind
    3 beats  three hints pop above it, one per beat: role, number, crest
    ...-4.0  the pack shakes, glows in the colour of the rarity, tears open
    4.0      flash and shockwave: the card flies out of the pack face down and
             flips to its front, confetti for the epic and legendary ones
    then     the numbers count up, the caption slides in, the card breathes in
             3D while the foil shines; a full spin near the end, then the fade

Everything is drawn per frame from pieces prepared once (rays, floor, glow,
pack, card layers), so a 10 second Story renders in well under a minute.
"""
from __future__ import annotations

import math
import random
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import cards

DROP = 4.0
LENGTH = 10.0
COUNTABLE = ('GOL', 'PARAT', 'PARTIT', 'ASSIST', 'PRESENZ', 'MVP', 'MINUT', 'VITTORI', 'TIRI')
# Layout in 540-wide units: header, hints, pack, card, caption, floor horizon, card height.
LAYOUTS = {
    'Story 9:16': dict(h=960, label=150, title=186, slots=246, pack=515, pack_h=430, card=478, card_h=432,
                       pill=732, horizon=612),
    'Post 4:5': dict(h=675, label=46, title=80, slots=132, pack=392, pack_h=360, card=372, card_h=372, pill=598,
                     horizon=470),
    'Post 1:1': dict(h=540, label=34, title=64, slots=106, pack=318, pack_h=290, card=300, card_h=300, pill=486,
                     horizon=388),
}


# --- Easing -------------------------------------------------------------------------------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x*x*(3-2*x)


def out_cubic(x):
    x = clamp(x)
    return 1-(1-x)**3


def out_back(x, k=1.9):
    x = clamp(x)
    return 1+(k+1)*(x-1)**3+k*(x-1)**2


def spring(t, freq=2.4, damping=4.0):
    """0 -> 1 with a damped overshoot."""
    if t <= 0:
        return 0.0
    return 1-math.exp(-damping*t)*math.cos(2*math.pi*freq*t)


def window(t, start, end, fade=.2):
    """1 inside [start, end] with soft edges."""
    return clamp((t-start)/fade)*clamp((end-t)/fade) if fade else float(start <= t <= end)


# --- The show -----------------------------------------------------------------------------------

class Backdrop:
    """Night sky with light rays and glow around a point, synthwave sun and moving floor, dust.

    canvas(t, power) mixes a lit and an unlit still through a light mask computed at half resolution."""

    def __init__(self, size, u, centre_y, horizon, title_y, glow, sun=True, dust=46, phases=20, style=None):
        W, H = self.size = size
        self.u, self.horizon, self.title_y, self.glow = u, horizon, title_y, glow
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        if style and style.get('image') is not None:
            # A studio preset (TV, cassette, Game Boy...): its own background instead of the synthwave night.
            base = np.asarray(style['image'].convert('RGB').resize(size, Image.Resampling.LANCZOS), np.float32)/255
            sun, floor = False, False
        else:
            top, mid, bottom = (np.array(c, np.float32)/255 for c in ((20, 11, 36), (34, 14, 48), (6, 4, 10)))
            k = yy/H
            bg = np.where((k < .62)[..., None], top+(mid-top)*(k/.62)[..., None], mid+(bottom-mid)*((k-.62)/.38)[..., None])
            vig = np.clip(1-.55*(((xx-W/2)/(W*.75))**2+((yy-H*.45)/(H*.7))**2), .25, 1)[..., None]
            base = bg*vig
            floor = True
        self.styled = bool(style and style.get('image') is not None)
        glow_col = np.array(glow, np.float32)/255
        self.base_img = Image.fromarray((np.clip(base, 0, 1)*255).astype(np.uint8), 'RGB')
        self.lit_img = Image.fromarray((np.clip(base+glow_col*(1-base), 0, 1)*255).astype(np.uint8), 'RGB')
        hw, hh = W//2, H//2
        hy, hx = np.mgrid[0:hh, 0:hw].astype(np.float32)
        dx, dy = hx*2-W/2, hy*2-centre_y
        theta = np.arctan2(dy, dx)
        self.theta_idx = ((theta+math.pi)/(2*math.pi)*4095).astype(np.int16)
        radius = np.sqrt(dx*dx+dy*dy)/(max(W, H)*.62)
        self.ray_fall = (np.clip(1-radius, 0, 1)**1.6*np.clip(radius*3, 0, 1)).astype(np.float32)
        self.glow_field = np.exp(-(radius/.42)**2).astype(np.float32)
        self._theta_axis = np.linspace(-math.pi, math.pi, 4096, dtype=np.float32)
        if sun:
            self.sun, self.sun_pos = self._sun()
            self.stage_y = min(self.sun_pos[1], int(horizon))
        else:
            self.sun, self.stage_y = None, int(horizon)
        self.stage = []
        for i in range(phases if floor else 0):
            img = Image.new('RGBA', (W, H-self.stage_y))
            if self.sun is not None:
                img.alpha_composite(self.sun, (self.sun_pos[0], self.sun_pos[1]-self.stage_y))
            img.alpha_composite(self._floor(i/phases), (0, int(horizon)-self.stage_y))
            self.stage.append(img)
        self.scan_step = max(2, int(round(1.5*u)))
        rnd = random.Random(7)
        palette = (style or {}).get('palette') or (cards.PINK, cards.CYAN, cards.YELLOW, (255, 255, 255))
        self.dust = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(6, 22)*u, rnd.uniform(.6, 2.2)*u,
                      rnd.uniform(0, 6.28), rnd.choice(palette))
                     for _ in range(dust)]

    def plate(self, canvas, box):
        """A dark rounded plate under the words when the background is a preset (it may be light)."""
        if not self.styled:
            return
        x0, y0, x1, y1 = box
        layer = Image.new('RGBA', (int(x1-x0), int(y1-y0)), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((0, 0, layer.width-1, layer.height-1), radius=int(14*self.u),
                                                fill=(16, 12, 26, 205))
        canvas.paste(layer, (int(x0), int(y0)), layer)

    def canvas(self, t, power):
        blades = .5+.5*np.cos(14*(self._theta_axis-t*.21))
        lut = (np.clip((blades-.35)/.65, 0, 1)**1.8*(power*.42*255)).astype(np.float32)
        light = lut[self.theta_idx]*self.ray_fall+self.glow_field*(power*.62*255)
        mask = Image.fromarray(np.minimum(light, 255).astype(np.uint8), 'L').resize(self.size, Image.Resampling.BILINEAR)
        canvas = Image.composite(self.lit_img, self.base_img, mask)
        if self.stage:
            stage = self.stage[int((t*1.6 % 1)*len(self.stage)) % len(self.stage)]
            canvas.paste(stage, (0, self.stage_y), stage)
        d = ImageDraw.Draw(canvas, 'RGBA')
        H = self.size[1]
        for x, y, speed, r, ph, col in self.dust:
            yy = (y-speed*t) % H
            tw = .35+.65*(.5+.5*math.sin(ph+t*2.3))
            d.ellipse((x-r*2.2, yy-r*2.2, x+r*2.2, yy+r*2.2), fill=(*col, int(26*tw)))
            d.ellipse((x-r, yy-r, x+r, yy+r), fill=(*col, int(170*tw)))
        return canvas

    def _sun(self):
        W, H = self.size
        u = self.u
        r = int(min(W*.36, (self.horizon-self.title_y)*.55))
        size = 2*r
        ys = np.linspace(0, 1, size, dtype=np.float32)[:, None]
        top = np.array([min(255, c+60) for c in self.glow], np.float32)/255
        bottom = np.array((255, 70, 150), np.float32)/255
        col = top*(1-ys[..., None])+bottom*ys[..., None]
        col = np.repeat(col, size, axis=1)
        disk = Image.new('L', (size, size), 0)
        ImageDraw.Draw(disk).ellipse((0, 0, size-1, size-1), fill=255)
        cut = ImageDraw.Draw(disk)
        for i in range(7):                                  # the classic slats, thicker towards the bottom
            y = size*(.52+i*.075)
            hgt = size*(.012+i*.006)
            cut.rectangle((0, y, size, y+hgt), fill=0)
        sun = Image.fromarray((col*255).astype(np.uint8), 'RGB').convert('RGBA')
        sun.putalpha(disk.point(lambda v: v*200//255))
        pad = int(r*.6)
        halo_a = Image.new('L', (size+2*pad, size+2*pad), 0)
        ImageDraw.Draw(halo_a).ellipse((pad, pad, pad+size, pad+size), fill=150)
        halo_a = halo_a.filter(ImageFilter.GaussianBlur(r*.28))
        out = Image.new('RGBA', halo_a.size, (*self.glow, 0))
        out.putalpha(halo_a)
        out.alpha_composite(sun, (pad, pad))
        cy = self.horizon-r*.42
        return out, (int(W/2-out.width/2), int(cy-out.height/2))

    def _floor(self, phase):
        W, H = self.size
        u = self.u
        hz = int(self.horizon)
        img = Image.new('RGBA', (W, H-hz))
        d = ImageDraw.Draw(img)
        h = H-hz
        pink = (255, 92, 190)
        for i in range(-14, 15):                               # lines towards the vanishing point
            x_far = W/2+i*W*.035
            x_near = W/2+i*W*.28
            d.line((x_far, 0, x_near, h), fill=(*pink, 150), width=max(1, int(1.3*u)))
        for j in range(16):                                    # horizontal lines, closer and closer
            z = (j+phase)/16
            y = h*(z**2.2)
            alpha = int(60+160*z)
            d.line((0, y, W, y), fill=(*pink, alpha), width=max(1, int((1+1.6*z)*u)))
        glow = img.filter(ImageFilter.GaussianBlur(3*u))
        out = Image.new('RGBA', img.size)
        out.alpha_composite(glow)
        out.alpha_composite(glow)
        out.alpha_composite(img)
        fade = np.linspace(0, 1, h, dtype=np.float32)[:, None]**.7
        a = (np.asarray(out.getchannel('A'), np.float32)*fade).astype(np.uint8)
        out.putalpha(Image.fromarray(a))
        # Horizon haze.
        haze = Image.new('RGBA', (W, int(40*u)))
        hd = np.linspace(1, 0, haze.height, dtype=np.float32)[:, None]**2*np.ones((1, W), np.float32)
        haze = Image.new('RGBA', (W, int(40*u)), (*self.glow, 0))
        haze.putalpha(Image.fromarray((hd*110).astype(np.uint8)))
        out.alpha_composite(haze)
        return out



def finish(canvas, t, length, scan_step, flash=0.0):
    """Flash, scanlines and the fades in and out, in numpy: the frame for the video writer."""
    arr = np.array(canvas, dtype=np.uint8)
    if flash > 0:
        arr = (arr+(255-arr.astype(np.float32))*flash).astype(np.uint8)
    arr[::scan_step] = (arr[::scan_step].astype(np.uint16)*7//8).astype(np.uint8)
    black = max(1-clamp(t/.25), clamp((t-(length-.45))/.45))
    if black > 0:
        arr = (arr.astype(np.float32)*(1-black)).astype(np.uint8)
    return arr


class Show:
    def __init__(self, card, logo=None, format='Story 9:16', scale=2, track=None, caption='', length=LENGTH, still=False,
                 style=None, fades=True):
        self.format = format if format in LAYOUTS else 'Story 9:16'
        self.L = LAYOUTS[self.format]
        self.u = float(scale)
        self.size = (int(540*self.u), int(self.L['h']*self.u))
        self.spec = cards.spec_for(card)
        self.rarity = cards.RARITIES[self.spec['rarity']]
        self.logo = logo
        self.length = float(length)
        self.caption = caption
        self.track = track
        beat = None
        if track:
            import tracks
            found = tracks.beat(track)
            beat = found[0] if found else None
        self.beat = beat if beat and .3 <= beat <= .9 else .5
        step = self.beat*max(1, round(.66/self.beat))
        self.hints = [DROP-4*step, DROP-3*step, DROP-2*step]
        self.tear = DROP-.42
        self.still = still
        self.style = style
        self.fades = fades
        from preset_look import Look
        self.look = Look(style, self.u)     # words and chips follow the preset (3.13); the card stays the card
        self._prepare()

    # Prepared pieces -------------------------------------------------------------------------
    def _prepare(self):
        W, H = self.size
        u, L, rr = self.u, self.L, self.rarity
        glow = rr['glow']
        self.backdrop = Backdrop(self.size, u, L['card']*u, L['horizon']*u, L['title']*u, glow,
                                 phases=1 if self.still else 20, style=self.style)
        self.scan_step = self.backdrop.scan_step
        rnd = random.Random(7)
        # Card, back, pack.
        cs = L['card_h']/cards.H*u
        self.card = cards.Card(self.spec, cs, self.logo)
        self.back = cards.back(cs, self.logo, self.spec['rarity'], self.spec['team'], self.spec['season'])
        q = .25                                   # the shadow is soft: a quarter of the resolution is plenty
        pad = int(18*cs*q)
        small = self.card.alpha.resize((max(1, int(self.card.size[0]*q)), max(1, int(self.card.size[1]*q))))
        a = Image.new('L', (small.width+2*pad, small.height+2*pad), 0)
        a.paste(small.point(lambda v: v*150//255), (pad, pad))
        sil = Image.new('RGBA', a.size, (0, 0, 0, 0))
        sil.putalpha(a.filter(ImageFilter.GaussianBlur(9*cs*q)))
        self.shadow = sil
        self.shadow_q = q
        ps = L['pack_h']/500*u
        if self.still:                     # the still shows the card only
            self.pack_img, self.tear_px = None, 0
        else:
            self.pack_img, self.tear_px = cards.pack(ps, self.logo, self.spec['rarity'], self.spec['edition'],
                                                     self.spec['team'], self.spec['season'])
        # Words.
        ed = cards.EDITIONS[self.spec['edition']]
        look = self.look
        self.label = look.text(f"FIGURINE {self.spec['team']}  ·  {self.spec['season']}", 'heavy', 11,
                               look.yellow if look.preset else (*cards.WHITE, 220), tracking=2.6)
        self.title = look.text(ed['title'] or 'LA COLLEZIONE', 'black', 34, look.white, 500, shadow=(0, 3, 6, 200))
        self.title_glow = self.title.filter(ImageFilter.GaussianBlur(8*u)) if self.title else None
        self.slot_imgs = self._slots()
        self.pill = self._pill(self.caption) if self.caption else None
        # Confetti.
        colors = [self.look.pink, self.look.cyan, self.look.yellow, self.look.white, rr['metal'][1]]
        self.confetti = []
        if self.spec['rarity'] in ('epica', 'leggenda'):
            count = 130 if self.spec['rarity'] == 'leggenda' else 90
            for _ in range(count):
                ang = rnd.uniform(-math.pi*.95, -math.pi*.05)
                speed = rnd.uniform(240, 720)*u
                self.confetti.append(dict(vx=math.cos(ang)*speed, vy=math.sin(ang)*speed, rot=rnd.uniform(0, 6.28),
                                          vr=rnd.uniform(-12, 12), w=rnd.uniform(3, 7)*u, h=rnd.uniform(6, 13)*u,
                                          color=rnd.choice(colors)))
        # Count-up steps for the vote and the numeric stats.
        self.count_steps = self._count_steps()

    def _slots(self):
        """The three hints: role, number, crest (FUT-style walkout, our way)."""
        u, sp, rr = self.u, self.spec, self.rarity
        out = []
        look = self.look
        role = look.text(cards.ROLES[sp['role']][1], 'black', 15, look.white, 150, tracking=1.0)
        out.append(self._chip(role))
        number = look.text(f"#{sp['number']}" if sp['number'] else cards.ROLES[sp['role']][0], 'black', 22, look.white)
        out.append(self._chip(number))
        if self.logo:
            from renderer import clean_logo
            base = max(1, int(round(u)))
            crest = clean_logo(self.logo, 30, True, base)
            crest = crest.resize((max(1, int(crest.width*u/base)), max(1, int(crest.height*u/base))), Image.Resampling.LANCZOS)
        else:
            crest = look.text(sp['team'][:3], 'black', 18, look.white)
        out.append(self._chip(crest))
        return out

    def _chip(self, content):
        u, rr = self.u, self.rarity
        h = int(46*u)
        w = max(h, content.width+int(30*u))
        img = Image.new('RGBA', (w+int(20*u), h+int(20*u)))
        d = ImageDraw.Draw(img)
        x0, y0 = int(10*u), int(10*u)
        look = self.look
        d.rounded_rectangle((x0, y0, x0+w, y0+h), radius=look.radius(12),
                            fill=(*look.panel, 240) if look.preset else (16, 12, 26, 235),
                            outline=(*rr['metal'][1], 255), width=max(1, int(1.6*u)))
        glow = img.filter(ImageFilter.GaussianBlur(6*u))
        tinted = Image.new('RGBA', img.size, (*rr['glow'], 0))
        tinted.putalpha(glow.getchannel('A'))
        out = Image.new('RGBA', img.size)
        out.alpha_composite(tinted)
        out.alpha_composite(img)
        out.alpha_composite(content, (x0+(w-content.width)//2, y0+(h-content.height)//2))
        return out

    def _pill(self, caption):
        u, rr = self.u, self.rarity
        look = self.look
        words = look.text(caption.upper(), 'heavy', 13, look.white, 470, tracking=1.2)
        if words is None:
            return None
        h = int(34*u)
        w = words.width+int(36*u)
        img = Image.new('RGBA', (w, h))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w-1, h-1), radius=look.radius(h//2/u) if look.preset else h//2,
                            fill=(*look.panel, 236) if look.preset else (16, 12, 26, 230), outline=(*rr['accent'], 255),
                            width=max(1, int(1.4*u)))
        img.alpha_composite(words, ((w-words.width)//2, (h-words.height)//2))
        return img

    def _count_steps(self):
        sp = self.spec
        steps = []
        n = 8
        target_vote = sp['vote']
        numbers = []
        for label, value in sp['stats']:
            m = re.fullmatch(r'\s*(\d{1,3})\s*', str(value))
            countable = any(word in str(label).upper() for word in COUNTABLE)
            numbers.append(int(m.group(1)) if m and countable else None)
        for i in range(n+1):
            k = i/n
            vote = None
            if target_vote is not None:
                start = max(4.0, float(target_vote)-3.5)
                vote = round((start+(float(target_vote)-start)*k)*2)/2
            stats = None
            if any(v is not None for v in numbers):
                stats = tuple((label, str(round(v*k)) if v is not None else value)
                              for (label, value), v in zip(sp['stats'], numbers))
            steps.append((vote, stats))
        return steps

    # Pieces per frame --------------------------------------------------------------------------
    def _ink(self, t):
        """The card's ink at time t: count-up numbers, blinking, the pose on the beat."""
        frame, beat = None, 0
        local = t-DROP
        import pixel_character
        look = pixel_character.sanitize(self.spec['look']) if self.spec['look'] else None
        options = pixel_character.frames_for(look) if look else ()
        for at, name, dur in ((2.35, 'blink', .14), (3.4, 'smile', .7), (4.6, 'blink', .14), (5.1, 'wink', .35)):
            if at <= local < at+dur and name in options:
                frame = name
        if self.spec['pose'] in pixel_character.MOVING_POSES and local > .9:
            beat = int((local-.9)/self.beat) % 2
        vote, stats = None, None
        if self.count_steps and local < 1.75:
            k = int(clamp((local-.9)/.8)*(len(self.count_steps)-1))
            vote, stats = self.count_steps[k]
            if k == len(self.count_steps)-1:
                vote, stats = None, None
        if vote is not None and self.spec['vote'] is not None and float(vote) == float(self.spec['vote']) and stats is None:
            vote = None
        return self.card.ink_for(frame, beat, vote, stats)

    def frame(self, t, quality='fast'):
        """The frame at time t as a PIL RGB image."""
        return Image.fromarray(self.frame_array(t, quality), 'RGB')

    def frame_array(self, t, quality='fast'):
        W, H = self.size
        u, L = self.u, self.L
        self.quality = quality
        cx = W/2
        revealed = t >= DROP
        # Rays and glow: a hint before the reveal, full power after it, pulsing on the beat.
        pulse = .5+.5*math.cos(2*math.pi*((t-DROP)/self.beat))
        if revealed:
            power = .55+.45*math.exp(-(t-DROP)*1.6)+.08*pulse
        else:
            power = .12+.25*smooth((t-self.hints[0]+.3)/(DROP-self.hints[0]))
        canvas = self.backdrop.canvas(t, power)
        # Header.
        k = out_cubic((t-.15)/.6)
        if self.backdrop.styled and self.title:
            half = max(self.title.width, self.label.width if self.label else 0)/2+18*u
            self.look.plate(canvas, (cx-half, (L['label']-16)*u, cx+half, (L['title'])*u+self.title.height/2+10*u))
        if self.label:
            self._paste(canvas, self.label, cx, (L['label']-10*(1-k))*u, k)
        if self.title:
            pop = 1+.08*math.exp(-max(0.0, t-DROP)*6) if revealed else 1
            if revealed and t-DROP < 1.2:
                self._paste(canvas, self.title_glow, cx, L['title']*u, .7*math.exp(-(t-DROP)*2.5), pop)
            self._paste(canvas, self.title, cx, (L['title']+14*(1-k))*u, k, pop)
        # Hints before the reveal.
        if t < DROP+.35:
            gone = 1-clamp((t-DROP)/.3)
            for i, (at, img) in enumerate(zip(self.hints, self.slot_imgs)):
                if t < at:
                    continue
                p = t-at
                scale = 1+.45*math.exp(-p*9)*math.cos(p*20) if p < .6 else 1
                x = cx+(i-1)*150*u
                self._paste(canvas, img, x, L['slots']*u, clamp(p/.12)*gone, scale)
                if p < .25:
                    flash = Image.new('RGBA', img.size, (255, 255, 255, 0))
                    flash.putalpha(img.getchannel('A').point(lambda v, q=p: int(v*(1-q/.25)*.8)))
                    self._paste(canvas, flash, x, L['slots']*u, 1, scale)
        if t < DROP+1.0 and self.pack_img is not None:
            self._draw_pack(canvas, t)
        if revealed:
            self._draw_card(canvas, t)
            self._draw_burst(canvas, t)
        if self.pill and t > DROP+1.3:
            k = out_back((t-DROP-1.3)/.5, 1.4)
            self._paste(canvas, self.pill, cx, (L['pill']+24*(1-k))*u, clamp((t-DROP-1.3)/.25))
        flash = (1-(t-DROP)/.25)**2*.5 if revealed and t-DROP < .25 else 0.0
        canvas = self._camera(canvas, t)
        return finish(canvas, t if self.fades else 1.0, self.length if self.fades else 1e9, self.scan_step, flash)

    def camera_at(self, t):
        """(zoom, dx, dy): a slow push towards the pack before the drop, a punch and a shake on it."""
        zoom, dx, dy = 1.0, 0.0, 0.0
        if self.tear-.5 <= t < DROP:
            zoom = 1+.045*smooth((t-(self.tear-.5))/(DROP-self.tear+.5))
        elif DROP <= t < DROP+.9:
            p = t-DROP
            zoom = 1+.07*math.exp(-p*5)*math.cos(p*9)
            amp = 7*self.u*math.exp(-p*7)
            dx, dy = amp*math.sin(p*61), amp*math.cos(p*47)
        return zoom, dx, dy

    def _camera(self, canvas, t):
        zoom, dx, dy = self.camera_at(t)
        if abs(zoom-1) < 1e-3 and abs(dx) < .5 and abs(dy) < .5:
            return canvas
        W, H = self.size
        cx, cy = W/2, self.L['card']*self.u
        # Output pixel (x, y) samples the input at centre + (x - centre)/zoom - shake.
        a = 1/zoom
        coeffs = (a, 0, cx-cx*a-dx, 0, a, cy-cy*a-dy)
        return canvas.transform(canvas.size, Image.Transform.AFFINE, coeffs, Image.Resampling.BILINEAR)

    def _paste(self, canvas, img, x, y, alpha=1.0, scale=1.0):
        if img is None or alpha <= 0:
            return
        if abs(scale-1) > .01:
            img = img.resize((max(1, int(img.width*scale)), max(1, int(img.height*scale))), Image.Resampling.BILINEAR)
        mask = img.getchannel('A') if alpha >= 1 else img.getchannel('A').point(lambda v, a=alpha: int(v*a))
        canvas.paste(img, (int(x-img.width/2), int(y-img.height/2)), mask)

    def _draw_pack(self, canvas, t):
        u, L = self.u, self.L
        W, H = self.size
        if t < .1:
            return
        x, y = W/2, L['pack']*u
        enter = out_back((t-.1)/.8, 1.5)
        y -= (1-enter)*H*.7
        roll, yaw = 0.0, 0.0
        float_y = math.sin(t*2.2)*4*u
        for at in self.hints:                         # a shake on each hint
            p = t-at
            if 0 <= p < .45:
                roll += math.sin(p*55)*7*math.exp(-p*8)
        tension = clamp((t-self.hints[-1])/(self.tear-self.hints[-1]))
        if t < self.tear:
            roll += math.sin(t*61)*3.2*tension**2
            yaw = math.sin(t*1.7)*10*(1-tension)
        exit_ = clamp((t-DROP)/.7)
        y += out_cubic(exit_)*H*.55
        alpha = 1-smooth(exit_)
        if alpha <= 0:
            return
        img = self._pack_frame(t)
        if tension > 0 and t < DROP+.3:
            self._paste(canvas, self._pack_glow(), x, y+float_y, alpha*min(1.0, tension*1.4))
        q = getattr(self, 'quality', 'fast')
        if t < self.tear:
            self._paste_warp(canvas, cards.warp(img, (x, y+float_y), yaw, 0, roll, 1.0, quality=q), alpha)
            return
        body = img.crop((0, self.tear_px, img.width, img.height))
        top = img.crop((0, 0, img.width, self.tear_px))
        self._paste_warp(canvas, cards.warp(body, (x, y+float_y+self.tear_px/2), yaw, 0, roll, 1.0, quality=q), alpha)
        p = t-self.tear
        if p < 1.2:
            tx = x+p*260*u
            ty = y+float_y-img.height/2+self.tear_px/2-p*420*u+p*p*600*u
            strip = top.rotate(-p*260, expand=True, resample=Image.Resampling.BILINEAR)
            self._paste(canvas, strip, tx, ty, clamp(1.2-p)*alpha)
        k = clamp(p/.35)*(1-clamp((t-DROP)/.4))
        if k > 0:                                     # light pouring out of the opening
            beam_h, beam_w = int(H*.6), int(img.width*.8)
            self._paste(canvas, self._beam(beam_w, beam_h), x, y+float_y-img.height/2+self.tear_px-beam_h/2, k*alpha)

    def _paste_warp(self, canvas, warped, alpha=1.0):
        img, x0, y0 = warped
        if img is None:
            return
        mask = img.getchannel('A') if alpha >= 1 else img.getchannel('A').point(lambda v, a=alpha: int(v*a))
        canvas.paste(img, (x0, y0), mask)

    GLINTS = 14

    def _pack_frame(self, t):
        """The pack with a foil glint sweeping across it when it lands and on each hint."""
        p = None
        for start in [.85]+list(self.hints):
            if start <= t < start+.42:
                p = (t-start)/.42
        if p is None:
            return self.pack_img
        if getattr(self, '_glints', None) is None:
            img = self.pack_img
            w, h = img.size
            band_w = int(w*.5)
            xs = np.linspace(-1, 1, band_w, dtype=np.float32)
            column = np.exp(-xs*xs*5)
            self._glints = []
            for k in range(self.GLINTS):
                pos = -band_w+(w+2*band_w)*k/(self.GLINTS-1)
                shift = np.arange(h, dtype=np.float32)[:, None]*.55     # a diagonal band
                x = np.arange(w, dtype=np.float32)[None, :]-pos-shift
                inside = (x >= 0) & (x < band_w)
                alpha = np.zeros((h, w), np.float32)
                alpha[inside] = column[np.clip(x[inside].astype(int), 0, band_w-1)]
                band = Image.new('RGBA', (w, h), (255, 250, 240, 0))
                band.putalpha(Image.fromarray((alpha*np.asarray(img.getchannel('A'), np.float32)/255*150).astype(np.uint8)))
                shined = img.copy()
                shined.alpha_composite(band)
                self._glints.append(shined)
        return self._glints[min(self.GLINTS-1, int(p*self.GLINTS))]

    def _pack_glow(self):
        if getattr(self, '_glow_img', None) is None:
            u = self.u
            img = self.pack_img
            pad = int(48*u)
            a = Image.new('L', (img.width+2*pad, img.height+2*pad), 0)
            a.paste(img.getchannel('A'), (pad, pad))
            a = a.filter(ImageFilter.GaussianBlur(22*u)).point(lambda v: min(255, int(v*1.5)))
            glow = Image.new('RGBA', a.size, (*self.rarity['glow'], 0))
            glow.putalpha(a)
            self._glow_img = glow
        return self._glow_img

    def _beam(self, w, h):
        if getattr(self, '_beam_img', None) is None or self._beam_img.size != (w, h):
            xs = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
            ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
            a = np.exp(-(xs/(.25+.55*(1-ys)))**2*3)*ys**1.4
            img = Image.new('RGBA', (w, h), (255, 248, 236, 0))
            img.putalpha(Image.fromarray((a*230).astype(np.uint8)))
            tint = Image.new('RGBA', (w, h), (*self.rarity['glow'], 0))
            tint.putalpha(Image.fromarray((a*140).astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)))
            out = Image.new('RGBA', (w, h))
            out.alpha_composite(tint)
            out.alpha_composite(img)
            self._beam_img = out
        return self._beam_img

    def card_pose(self, t):
        """(dx, dy, yaw, pitch, roll, scale, light) of the card at time t (after the reveal)."""
        u, L = self.u, self.L
        p = t-DROP
        rise = out_back(p/.85, 1.25)
        dy = (1-rise)*(L['pack']-L['card']+120)*u
        flip = 180*(1-out_cubic(p/.75))
        scale = .55+.45*spring(p, 1.3, 5.0)
        yaw = flip
        pitch = 14*(1-out_cubic(p/.9))
        roll = -8*(1-out_cubic(p/.8))
        if p > .9:                                   # breathing in 3D
            q = p-.9
            ramp = clamp(q/.8)
            yaw += ramp*(10*math.sin(q*2*math.pi/4.4)+3*math.sin(q*2*math.pi/1.9))
            pitch += ramp*(4*math.sin(q*2*math.pi/5.6+.7))
            dy += ramp*math.sin(q*2*math.pi/3.1)*5*u
        spin_at = self.length-2.15
        if spin_at <= t < spin_at+.9:                 # a full spin as a flourish
            yaw += 360*smooth((t-spin_at)/.9)
        light = .62+.38*abs(math.cos(math.radians(yaw)))
        return 0.0, dy, yaw, pitch, roll, scale, light

    def _draw_card(self, canvas, t, quality=None):
        u, L = self.u, self.L
        W = self.size[0]
        dx, dy, yaw, pitch, roll, scale, light = self.card_pose(t)
        centre = (W/2+dx, L['card']*u+dy)
        q = self.shadow_q
        sh, sx, sy = cards.warp(self.shadow, ((centre[0]+10*u)*q, (centre[1]+16*u)*q), yaw*.6, pitch, roll, scale*1.02,
                                quality='fast')
        if sh is not None:
            big = sh.resize((int(sh.width/q), int(sh.height/q)), Image.Resampling.BILINEAR)
            canvas.paste(big, (int(sx/q), int(sy/q)), big)
        facing = math.cos(math.radians(yaw))*math.cos(math.radians(pitch)) >= 0
        if facing:
            holo_yaw = (yaw+180) % 360-180
            face = self.card.render(holo_yaw, pitch, t, light, self._ink(t))
        else:
            face = self.back
        self._paste_warp(canvas, cards.warp(face, centre, yaw, pitch, roll, scale,
                                            quality=quality or getattr(self, 'quality', 'fast')))

    def _draw_burst(self, canvas, t):
        u, L = self.u, self.L
        W = self.size[0]
        p = t-DROP
        cx, cy = W/2, L['card']*u
        d = ImageDraw.Draw(canvas, 'RGBA')
        if p < .7:                                    # shockwave ring
            r = (60+520*out_cubic(p/.7))*u
            alpha = int(230*(1-p/.7))
            width = max(1, int((10*(1-p/.7)+2)*u))
            d.ellipse((cx-r, cy-r*.82, cx+r, cy+r*.82), outline=(*self.rarity['glow'], alpha), width=width)
            d.ellipse((cx-r*.8, cy-r*.66, cx+r*.8, cy+r*.66), outline=(255, 255, 255, alpha//2), width=max(1, width//2))
        if self.confetti and p < 3.2:
            g = 900*u
            alpha = int(255*clamp((3.2-p)/.6))
            for c in self.confetti:
                x = cx+c['vx']*p*(1-.25*p)
                y = cy+c['vy']*p+.5*g*p*p
                rot = c['rot']+c['vr']*p
                w, h = c['w'], c['h']*abs(math.cos(rot*1.7))+u
                ca, sa = math.cos(rot), math.sin(rot)
                pts = [(x+ca*px-sa*py, y+sa*px+ca*py) for px, py in ((-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2))]
                d.polygon(pts, fill=(*c['color'], alpha))

    # Audio ------------------------------------------------------------------------------------
    def events(self):
        """[(seconds, samples)] for the effects (the music is added by render)."""
        import sounds
        from music import riser
        out = [(.12, sounds.whoosh(.5)*.8), (.82, sounds.impact(0)*.7)]
        for i, at in enumerate(self.hints):
            out.append((at, sounds.impact(0)*.55))
            out.append((at, sounds.ding(i)*.9))
        out.append((self.hints[-1]+.05, riser(DROP-self.hints[-1]-.05)*1.3))
        out.append((self.tear, _tear()))
        out.append((DROP, sounds.impact(1)*1.1))
        out.append((DROP+.02, sounds.whoosh(.4)*.7))
        out.append((DROP+.25, sounds.shine()*1.6))
        if self.spec['rarity'] in ('epica', 'leggenda'):
            out.append((DROP+.1, sounds.crown()*.9))
        for i in range(8):
            out.append((DROP+.9+i*.1, sounds.tick(i)*.8))
        out.append((DROP+1.75, sounds.ding(2)*.8))
        spin = self.length-2.15
        out.append((spin, sounds.whoosh(.6)*.6))
        return out


def _tear(seconds=.38, sr=44100):
    """Paper tearing: crackly noise, brighter as it rips."""
    n = int(seconds*sr)
    rnd = np.random.default_rng(31)
    noise = rnd.normal(0, 1, n)
    grains = (rnd.random(n) > .985).astype(float)*rnd.normal(0, 3, n)
    env = np.minimum(1, np.linspace(0, 8, n))*np.exp(-np.linspace(0, 4, n))
    hp = noise-np.convolve(noise, np.ones(6)/6, 'same')
    return (hp*.35+grains)*env*.35


# --- Exports -------------------------------------------------------------------------------------

POSTER_T = DROP+3.25


def poster(card, logo=None, format='Story 9:16', scale=2, caption='', style=None):
    """The still for the post: the card mid-breath, rays, floor, caption (PIL RGB)."""
    show = Show(card, logo, format, scale, None, caption, still=True, style=style)
    return show.frame(POSTER_T, quality='high')


def render_video(card, logo, path, fps=30, format='Story 9:16', scale=2, track=None, caption='', sound=True,
                 volume=.8, length=LENGTH, progress_callback=None, style=None):
    from crt_presets import even_video_frame
    from renderer import video_writer
    show = Show(card, logo, format, scale, track, caption, length, style=style)
    total = int(round(show.length*fps))
    writer = video_writer(path, fps)
    try:
        for i in range(total):
            frame = show.frame_array(i/fps)
            writer.append_data(frame if frame.shape[0] % 2 == 0 and frame.shape[1] % 2 == 0
                               else np.asarray(even_video_frame(Image.fromarray(frame))))
            if progress_callback and (i % fps == 0 or i == total-1):
                progress_callback((i+1)/total)
    finally:
        writer.close()
    if sound or track:
        import sounds
        events = show.events() if sound else []
        if track:
            events.append((0.0, sounds.chiptune(show.length, 0, track=track)*.9))
        sounds.mux(path, sounds.mix(events, show.length, volume, ambient=False))
    return str(path)
