"""Le pagelle (3.9): the match ratings, one row per player, the MVP revealed on the drop.

A row: pixel face, number and name, goals as little balls, a short note, the
vote in a badge coloured by how good it was (8 and up cyan, 6 yellow, below 6
pink). Rows enter one after the other on the beat; the best one (MVP) waits
for the drop of the music and lights up. The still is the last frame.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import cards
from card_video import Backdrop, DROP, clamp, finish, out_cubic

ROLE_ORDER = {'P': 0, 'D': 1, 'C': 2, 'A': 3, 'ALL': 4, 'DIR': 5, '-': 2}
VOTES = [x/2 for x in range(8, 21)]          # 4 .. 10, half points
LENGTH = 8.0
LAYOUTS = {
    'Story 9:16': dict(h=960, title=176, line=214, sub=236, top=268, bottom=900, max_row=46),
    'Post 4:5': dict(h=675, title=58, line=94, sub=114, top=140, bottom=652, max_row=40),
    'Post 1:1': dict(h=540, title=46, line=80, sub=99, top=122, bottom=522, max_row=36),
}


def ball(d, x, y, r, u=1.0):
    """A small football: white, a black pentagon in the middle and the seams to the edge."""
    ink = (20, 16, 28, 255)
    d.ellipse((x-r, y-r, x+r, y+r), fill=(250, 250, 250, 255), outline=ink, width=max(1, int(.9*u)))
    inner = r*.4
    d.regular_polygon((x, y, inner), 5, rotation=0, fill=ink)
    for k in range(5):
        a = math.radians(-90+72*k)
        d.line((x+math.cos(a)*inner, y+math.sin(a)*inner, x+math.cos(a)*r*.95, y+math.sin(a)*r*.95), fill=ink,
               width=max(1, int(.8*u)))
        b = math.radians(-54+72*k)
        d.regular_polygon((x+math.cos(b)*r*.86, y+math.sin(b)*r*.86, r*.2), 5, rotation=-math.degrees(b), fill=ink)


def vote_color(vote):
    if vote >= 8:
        return cards.CYAN
    if vote >= 6.5:
        return cards.WHITE
    if vote >= 6:
        return cards.YELLOW
    return cards.PINK


def order(rows):
    """Lineup order: goalkeepers, defenders, midfielders, forwards, then the staff; by number inside."""
    return sorted(rows, key=lambda r: (ROLE_ORDER.get(r.get('role', '-'), 2), int(r.get('number') or 99) or 99, r['name']))


def best(rows):
    """The MVP: highest vote, then more goals, then the first in the list."""
    voted = [r for r in rows if r.get('vote') is not None]
    if not voted:
        return None
    return max(voted, key=lambda r: (float(r['vote']), int(r.get('goals') or 0), -rows.index(r)))['name']


class Pagelle:
    def __init__(self, rows, match=None, logo=None, format='Story 9:16', scale=2, track=None, length=LENGTH,
                 still=False, style=None, fades=True):
        self.format = format if format in LAYOUTS else 'Story 9:16'
        self.L = LAYOUTS[self.format]
        self.u = float(scale)
        self.size = (int(540*self.u), int(self.L['h']*self.u))
        self.rows = order([dict(r) for r in rows if r.get('vote') is not None])[:20]
        self.mvp = next((r['name'] for r in self.rows if r.get('mvp')), None) or best(self.rows)
        self.match = match or {}
        self.logo = logo
        self.length = float(length)
        self.still = still
        self.style = style
        self.fades = fades
        beat = None
        if track:
            import tracks
            found = tracks.beat(track)
            beat = found[0] if found else None
        self.beat = beat if beat and .3 <= beat <= .9 else .5
        self._prepare()

    def _prepare(self):
        W, H = self.size
        u, L = self.u, self.L
        glow = (self.style or {}).get('glow') or cards.PINK
        self.backdrop = Backdrop(self.size, u, H*.42, L['h']*u*.9, L['title']*u, glow, sun=False, dust=30,
                                 phases=1 if self.still else 20, style=self.style)
        self.title = cards.text(self.match.get('title') or 'LE PAGELLE', 'black', 40, cards.WHITE, u, max_width=480,
                                shadow=(0, 3, 6, 200))
        self.line = cards.text(self.match.get('line', ''), 'black', 15, cards.YELLOW, u, max_width=480, tracking=.6)
        self.sub = cards.text(self.match.get('sub', ''), 'heavy', 9.5, (*cards.WHITE, 200), u, max_width=480, tracking=2)
        n = max(1, len(self.rows))
        self.row_h = min(L['max_row'], (L['bottom']-L['top'])/n)
        gap = 4 if self.row_h > 34 else 3
        self.gap = gap
        span = n*self.row_h
        self.top = L['top']+max(0, (L['bottom']-L['top']-span)/2*.35)
        self.panels, self.votes = [], []
        for r in self.rows:
            panel, vote = self._row(r, self.row_h-gap)
            self.panels.append(panel)
            self.votes.append(vote)
        # Timeline: everybody but the MVP before the drop, the MVP on it.
        others = [i for i, r in enumerate(self.rows) if r['name'] != self.mvp]
        start, end = .9, DROP-.55
        step = min(.42, (end-start)/max(1, len(others)-1)) if len(others) > 1 else 0
        self.times = {}
        for k, i in enumerate(others):
            self.times[i] = start+k*step
        for i, r in enumerate(self.rows):
            if r['name'] == self.mvp:
                self.times[i] = DROP
        self.scan_step = self.backdrop.scan_step

    def _row(self, r, h):
        u = self.u
        w = 480
        mvp = r['name'] == self.mvp
        img = Image.new('RGBA', (int((w+24)*u), int((h+24)*u)))
        d = ImageDraw.Draw(img)
        x0, y0 = 12*u, 12*u
        gold = cards.RARITIES['leggenda']['metal'][1]
        fill = (30, 20, 40, 232) if mvp else (18, 13, 28, 214)
        d.rounded_rectangle((x0, y0, x0+w*u, y0+h*u), radius=int(10*u), fill=fill,
                            outline=(*gold, 255) if mvp else (255, 255, 255, 34), width=max(1, int((1.8 if mvp else 1)*u)))
        if mvp:                                          # a golden glow around the MVP row
            glow = img.filter(ImageFilter.GaussianBlur(7*u))
            tint = Image.new('RGBA', img.size, (*gold, 0))
            tint.putalpha(glow.getchannel('A').point(lambda v: min(255, v*2)))
            base = Image.new('RGBA', img.size)
            base.alpha_composite(tint)
            base.alpha_composite(img)
            img = base
            d = ImageDraw.Draw(img)
        # Pixel face.
        import pixel_character
        face = pixel_character.picture(dict(look=r.get('look'), avatar=r.get('avatar', '')), 'crt')
        side = (h-6)*u
        factor = max(1, int(side//face.height))
        big = face.resize((face.width*factor, face.height*factor), Image.Resampling.NEAREST)
        fx = int(x0+8*u)
        fy = int(y0+(h*u-big.height)/2)
        d.rounded_rectangle((fx-2*u, y0+3*u, fx+big.width+2*u, y0+h*u-3*u), radius=int(6*u),
                            fill=(46, 30, 62, 255))
        img.alpha_composite(big, (fx, fy))
        nx = fx+big.width+12*u
        # Number, name, goals, note.
        cy = y0+h*u/2
        two_lines = h >= 34 and r.get('note')
        name_y = cy-(6*u if two_lines else 0)
        number = int(r.get('number') or 0)
        if number:
            num = cards.text(f'{number}', 'black', 12, (*cards.WHITE, 150), u)
            img.alpha_composite(num, (int(nx), int(name_y-num.height/2)))
            nx += num.width+6*u
        size = min(19, h*.46)
        name = cards.text(r['name'], 'black', size, cards.WHITE, u, max_width=210)
        img.alpha_composite(name, (int(nx), int(name_y-name.height/2)))
        gx = nx+name.width+8*u
        for k in range(min(int(r.get('goals') or 0), 6)):   # the goals as little footballs
            rad = 6.0*u
            ball(d, gx+k*14.5*u+rad, name_y, rad, u)
        if mvp:
            star = cards.text('★ MVP', 'black', 11, cards.INK, u, tracking=.6)
            sw = star.width+14*u
            sx = x0+w*u-74*u-sw
            d.rounded_rectangle((sx, cy-10*u, sx+sw, cy+10*u), radius=int(10*u), fill=(*gold, 255))
            img.alpha_composite(star, (int(sx+7*u), int(cy-star.height/2)))
        if two_lines:
            note = cards.text(str(r['note'])[:60], 'bold', 9.5, (198, 182, 210), u,
                              max_width=(w-120-(74 if mvp else 0))-(nx-x0)/u+40)
            if note:
                img.alpha_composite(note, (int(nx), int(cy+8*u-note.height/2)))
        # Vote badge, separate so it can pop.
        vote = float(r['vote'])
        col = vote_color(vote)
        bh = min(34, h-6)
        badge = Image.new('RGBA', (int(66*u), int((bh+12)*u)))
        bd = ImageDraw.Draw(badge)
        bd.rounded_rectangle((6*u, 6*u, 60*u, (bh+6)*u), radius=int(9*u), fill=(12, 9, 20, 255), outline=(*col, 255),
                             width=max(1, int(1.6*u)))
        v = cards.text(cards.vote_text(vote), 'black', min(25, bh*.78), col, u, max_width=50)
        badge.alpha_composite(v, (int(33*u-v.width/2), int((bh/2+6)*u-v.height/2)))
        if vote >= 8:
            glow = badge.filter(ImageFilter.GaussianBlur(5*u))
            out = Image.new('RGBA', badge.size)
            tint = Image.new('RGBA', badge.size, (*col, 0))
            tint.putalpha(glow.getchannel('A'))
            out.alpha_composite(tint)
            out.alpha_composite(badge)
            badge = out
        return img, badge

    def frame(self, t):
        return Image.fromarray(self.frame_array(t), 'RGB')

    def frame_array(self, t):
        W, H = self.size
        u, L = self.u, self.L
        pulse = .5+.5*math.cos(2*math.pi*((t-DROP)/self.beat))
        power = .35+.2*clamp((t-DROP)*2)+.05*pulse
        canvas = self.backdrop.canvas(t, power)
        k = out_cubic((t-.1)/.6)
        if self.backdrop.styled and self.title:
            half = max(self.title.width, self.line.width if self.line else 0)/2+18*u
            self.backdrop.plate(canvas, (W/2-half, L['title']*u-self.title.height/2-10*u, W/2+half, (L['sub']+12)*u))
        self._paste(canvas, self.title, W/2, (L['title']+12*(1-k))*u, k)
        k2 = out_cubic((t-.3)/.6)
        self._paste(canvas, self.line, W/2, (L['line']+10*(1-k2))*u, k2)
        self._paste(canvas, self.sub, W/2, L['sub']*u, k2)
        for i, (panel, badge) in enumerate(zip(self.panels, self.votes)):
            at = self.times[i]
            if t < at:
                continue
            p = t-at
            mvp = self.rows[i]['name'] == self.mvp
            slide = out_cubic(p/.4)
            y = (self.top+i*self.row_h+(self.row_h-self.gap)/2)*u
            x = W/2+(1-slide)*60*u
            self._paste(canvas, panel, x, y, clamp(p/.25), 1+(.06*math.exp(-p*6) if mvp else 0))
            q = p-.12
            if q >= 0:
                pop = 1+.5*math.exp(-q*10)*math.cos(q*24) if q < .5 else 1
                self._paste(canvas, badge, x+(480/2-36)*u, y, clamp(q/.1), pop)
            if mvp and p < 1.2:                      # sparkles on the MVP row
                d = ImageDraw.Draw(canvas, 'RGBA')
                rnd = np.random.default_rng(i)
                for _ in range(26):
                    sx = W/2+rnd.uniform(-250, 250)*u
                    sy = y+rnd.uniform(-30, 30)*u-p*rnd.uniform(20, 80)*u
                    rad = rnd.uniform(1.2, 3.2)*u*(1-p/1.2)
                    col = cards.RARITIES['leggenda']['metal'][1]
                    d.ellipse((sx-rad, sy-rad, sx+rad, sy+rad), fill=(*col, int(230*(1-p/1.2))))
        flash = (1-(t-DROP)/.3)**2*.35 if 0 <= t-DROP < .3 else 0.0
        return finish(canvas, t if self.fades else 1.0, self.length if self.fades else 1e9, self.scan_step, flash)

    def _paste(self, canvas, img, x, y, alpha=1.0, scale=1.0):
        if img is None or alpha <= 0:
            return
        if abs(scale-1) > .01:
            img = img.resize((max(1, int(img.width*scale)), max(1, int(img.height*scale))), Image.Resampling.BILINEAR)
        mask = img.getchannel('A') if alpha >= 1 else img.getchannel('A').point(lambda v, a=alpha: int(v*a))
        canvas.paste(img, (int(x-img.width/2), int(y-img.height/2)), mask)

    def still_frame(self):
        return self.frame(self.length-1.0)

    def events(self):
        import sounds
        out = [(.1, sounds.whoosh(.4)*.6)]
        for i, at in self.times.items():
            if self.rows[i]['name'] == self.mvp:
                out += [(at, sounds.impact(1)), (at+.05, sounds.crown()*.9), (at+.2, sounds.shine()*1.5)]
            else:
                out += [(at, sounds.whoosh(.18)*.35), (at+.12, sounds.tick(i)*.9)]
        return out


def png_bytes(rows, match, logo=None, format='Story 9:16', scale=2, style=None):
    import io
    out = io.BytesIO()
    Pagelle(rows, match, logo, format, scale, still=True, style=style).still_frame().save(out, 'PNG', compress_level=5)
    return out.getvalue()


def render_video(rows, match, logo, path, fps=30, format='Story 9:16', scale=2, track=None, sound=True, volume=.8,
                 length=LENGTH, progress_callback=None, style=None):
    from crt_presets import even_video_frame
    from renderer import video_writer
    show = Pagelle(rows, match, logo, format, scale, track, length, style=style)
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
