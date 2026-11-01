"""Risultati della giornata (3.12): every match of the girone in one graphic, ours lit up.

The matches come from the CSI page (bookmark or pasted), grouped by round. A row:
home crest and name, the score (or day and time if not played yet), away name
and crest; the winner bright, the loser dimmer. In the video the rows enter
one by one with their score, and our match arrives last, on the drop.

Two looks: the synthwave night (Inter Display, pink glow), or a studio preset,
where the rows follow the CRT graphics like the Classifica: the preset's pixel
font, its colours, its panel and border, our row filled with its accent.
"""
from __future__ import annotations

import datetime as dt
import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import cards
from card_video import Backdrop, DROP, clamp, finish, out_cubic

LENGTH = 8.0
DAYS = ('LUN', 'MAR', 'MER', 'GIO', 'VEN', 'SAB', 'DOM')
LAYOUTS = {
    'Story 9:16': dict(h=960, title=176, sub=216, date=240, top=282, bottom=880, max_row=78),
    'Post 4:5': dict(h=675, title=58, sub=96, date=118, top=148, bottom=650, max_row=58),
    'Post 1:1': dict(h=540, title=46, sub=82, date=102, top=128, bottom=522, max_row=50),
}


# --- Data --------------------------------------------------------------------------------------

def normalise(matches):
    """CSI matches with real dates and tuple scores, whatever shape they were stored in."""
    out = []
    for m in matches or []:
        item = dict(m)
        if isinstance(item.get('date'), str):
            try:
                item['date'] = dt.date.fromisoformat(item['date'][:10])
            except ValueError:
                continue
        if item.get('score') is not None:
            item['score'] = tuple(item['score'])
        out.append(item)
    return out


def rounds(matches):
    """[{'key', 'label', 'matches', 'played'}] in order: by CSI round, or by week when rounds are missing."""
    groups = {}
    for m in normalise(matches):
        if m.get('round'):
            key = ('g', int(m['round']))
        else:
            year, week, _ = m['date'].isocalendar()
            key = ('w', year*100+week)
        groups.setdefault(key, []).append(m)
    out = []
    for key in sorted(groups, key=lambda k: (min(m['date'] for m in groups[k]), k)):
        ms = sorted(groups[key], key=lambda m: (m['date'], m.get('time') or ''))
        first, last = ms[0]['date'], ms[-1]['date']
        label = f'GIORNATA {key[1]}' if key[0] == 'g' else f"SETTIMANA DEL {first.strftime('%d/%m')}"
        out.append(dict(key=f'{key[0]}{key[1]}', label=label, matches=ms, played=sum(1 for m in ms if m.get('score')),
                        first=first, last=last))
    return out


def default_round(groups):
    """The last round with at least one result (else the first one)."""
    played = [i for i, g in enumerate(groups) if g['played']]
    return played[-1] if played else 0


def date_line(group):
    first, last = group['first'], group['last']
    if first == last:
        return first.strftime('%d/%m/%Y')
    return f"{first.strftime('%d/%m')} - {last.strftime('%d/%m/%Y')}"


def rows_for(group, ours='FLAMINGOS'):
    from csi_page import is_ours
    rows = []
    for m in group['matches']:
        when = f"{DAYS[m['date'].weekday()]} {m.get('time') or ''}".strip()
        rows.append(dict(home=str(m['home']).upper(), away=str(m['away']).upper(),
                         score=list(m['score']) if m.get('score') else None, when=when,
                         ours=is_ours(m['home'], ours) or is_ours(m['away'], ours)))
    return rows


def crest_for(name, ours_logo=None, is_ours=False):
    if is_ours and ours_logo:
        return ours_logo
    import crests
    asset = crests.builtin_assets().get(crests.logo_id_for(name) or '')
    return asset['bytes'] if asset else None


# --- Renderer -----------------------------------------------------------------------------------

class RoundShow:
    def __init__(self, rows, title='RISULTATI', subtitle='', date='', logo=None, ours='FLAMINGOS', format='Story 9:16',
                 scale=2, track=None, style=None, length=LENGTH, still=False, fades=True):
        self.rows = [dict(r) for r in rows][:10]
        self.title_text, self.subtitle, self.date = title, subtitle, date
        self.logo, self.ours = logo, ours
        self.format = format if format in LAYOUTS else 'Story 9:16'
        self.L = LAYOUTS[self.format]
        self.u = float(scale)
        self.size = (int(540*self.u), int(self.L['h']*self.u))
        self.style, self.length, self.still, self.fades = style, float(length), still, fades
        from preset_look import Look
        self.look = Look(style, self.u)
        self.font = self.look.font
        self.pink, self.cyan, self.yellow, self.white = self.look.pink, self.look.cyan, self.look.yellow, self.look.white
        self.panel, self.border = self.look.panel, self.look.border
        beat = None
        if track:
            import tracks
            found = tracks.beat(track)
            beat = found[0] if found else None
        self.beat = beat if beat and .3 <= beat <= .9 else .5
        self._prepare()

    def _prepare(self):
        u, L = self.u, self.L
        W, H = self.size
        glow = (self.style or {}).get('glow') or cards.CYAN
        self.backdrop = Backdrop(self.size, u, H*.45, L['h']*u*.92, L['title']*u, glow, sun=False, dust=26,
                                 phases=1 if self.still else 20, style=self.style)
        self.title = self._text(self.title_text, 'black', 44, self.white, 480, shadow=(0, 3, 6, 200))
        self.sub = self._text(self.subtitle, 'black', 15, self.yellow, 480, tracking=1)
        self.when = self._text(self.date, 'heavy', 10, self._mix(self.white, self.panel, .8), 480, tracking=2)
        n = max(1, len(self.rows))
        self.row_h = min(L['max_row'], (L['bottom']-L['top'])/n)
        self.gap = 6 if self.row_h > 44 else 4
        # Few matches: title and rows move down together, so the whole block sits in the middle.
        self.shift = max(0.0, (L['bottom']-L['top']-n*self.row_h)*.42)
        self.top = L['top']+self.shift
        self.panels = [self._row(r, self.row_h-self.gap) for r in self.rows]
        mine = next((i for i, r in enumerate(self.rows) if r['ours']), None)
        others = [i for i in range(len(self.rows)) if i != mine]
        start, end = .9, DROP-.5
        step = min(.45, (end-start)/max(1, len(others)-1)) if len(others) > 1 else 0
        self.times = {i: start+k*step for k, i in enumerate(others)}
        if mine is not None:
            self.times[mine] = DROP
        self.mine = mine
        self.scan_step = self.backdrop.scan_step

    def _text(self, value, kind, size, color, max_width, **kw):
        return self.look.text(value, kind, size, color, max_width, **kw)

    def _mix(self, a, b, k):
        return self.look.mix(a, b, k)

    def _crest(self, name, ours, size):
        data = crest_for(name, self.logo, ours)
        u = self.u
        if data:
            from renderer import clean_logo
            base = max(1, int(round(u)))
            img = clean_logo(data, 40, True, base)
            k = size*u/max(img.width, img.height)
            return img.resize((max(1, int(img.width*k)), max(1, int(img.height*k))), Image.Resampling.LANCZOS)
        # Unknown crest: a round badge with the initials.
        side = int(size*u)
        img = Image.new('RGBA', (side, side))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, side-1, side-1), fill=(*self._mix(self.white, self.panel, .18), 255),
                  outline=(*self.white, 120), width=max(1, int(u)))
        initials = ''.join(w[0] for w in name.split()[:2]) or '?'
        t = self._text(initials, 'black', size*.42, self.white, size)
        img.alpha_composite(t, ((side-t.width)//2, (side-t.height)//2))
        return img

    def _row(self, r, h):
        u = self.u
        w = 500
        img = Image.new('RGBA', (int((w+24)*u), int((h+24)*u)))
        d = ImageDraw.Draw(img)
        x0, y0 = 12*u, 12*u
        pink = self.pink
        if self.font:       # the preset look: its panel and border, our row filled with its accent (as in the Classifica)
            fill = (*pink, 245) if r['ours'] else (*self.panel, 232)
            line = (*self.border, 255) if r['ours'] else (*self.border, 70)
        else:
            fill = (34, 18, 40, 238) if r['ours'] else (18, 13, 28, 225)
            line = (*pink, 255) if r['ours'] else (255, 255, 255, 34)
        radius = int((4 if self.font else 12)*u)
        d.rounded_rectangle((x0, y0, x0+w*u, y0+h*u), radius=radius, fill=fill, outline=line,
                            width=max(1, int((2 if r['ours'] else 1)*u)))
        if r['ours']:
            glow = img.filter(ImageFilter.GaussianBlur(7*u))
            tint = Image.new('RGBA', img.size, (*pink, 0))
            tint.putalpha(glow.getchannel('A').point(lambda v: min(255, v*2)))
            base = Image.new('RGBA', img.size)
            base.alpha_composite(tint)
            base.alpha_composite(img)
            img = base
        cy = y0+h*u/2
        crest_size = min(36, h*.66)
        from csi_page import is_ours
        score = r['score']
        win_home = score and score[0] > score[1]
        win_away = score and score[1] > score[0]
        for side, name in (('home', r['home']), ('away', r['away'])):
            ours = is_ours(name, self.ours)
            crest = self._crest(name, ours, crest_size)
            cx = x0+(28 if side == 'home' else w-28)*u
            img.alpha_composite(crest, (int(cx-crest.width/2), int(cy-crest.height/2)))
            winner = win_home if side == 'home' else win_away
            loser = (win_away if side == 'home' else win_home)
            if self.font:
                color = self.look.ink(pink) if r['ours'] else (self.look.dim() if loser else self.white)
            else:
                color = pink if ours else (cards.WHITE if not loser else (176, 166, 192))
            label = self._text(name, 'black' if winner or ours else 'heavy', min(16, h*.32), color, 146)
            if label:                                  # names stop short of the score box in the middle
                if side == 'home':
                    img.alpha_composite(label, (int(x0+(w/2-48)*u-label.width), int(cy-label.height/2)))
                else:
                    img.alpha_composite(label, (int(x0+(w/2+48)*u), int(cy-label.height/2)))
        return img

    def _score(self, r, h):
        u = self.u
        if r['score']:
            a, b = r['score']
            t = self._text(f'{a} - {b}', 'black', min(24, h*.5), self.yellow if r['ours'] else self.white, 72)
        else:
            t = self._text(r['when'] or 'DA GIOCARE', 'heavy', min(11, h*.26), self.cyan, 72)
        box = Image.new('RGBA', (int(80*u), int((h-12)*u)))
        line = (*self.border, 110) if self.font else (255, 255, 255, 50)
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width-1, box.height-1), radius=self.look.radius(8),
                                              fill=self.look.box_fill(), outline=line, width=max(1, int(u)))
        if t:
            box.alpha_composite(t, ((box.width-t.width)//2, (box.height-t.height)//2))
        return box

    def frame(self, t):
        return Image.fromarray(self.frame_array(t), 'RGB')

    def frame_array(self, t):
        W, H = self.size
        u, L = self.u, self.L
        pulse = .5+.5*math.cos(2*math.pi*((t-DROP)/self.beat))
        canvas = self.backdrop.canvas(t, .32+.18*clamp((t-DROP)*2)+.05*pulse)
        k, s = out_cubic((t-.1)/.6), self.shift
        if self.backdrop.styled and self.title:
            half = max(self.title.width, self.sub.width if self.sub else 0)/2+18*u
            self.look.plate(canvas, (W/2-half, (L['title']+s)*u-self.title.height/2-10*u, W/2+half, (L['date']+s+12)*u))
        self._paste(canvas, self.title, W/2, (L['title']+s+12*(1-k))*u, k)
        k2 = out_cubic((t-.3)/.6)
        self._paste(canvas, self.sub, W/2, (L['sub']+s+10*(1-k2))*u, k2)
        self._paste(canvas, self.when, W/2, (L['date']+s)*u, k2)
        for i, (panel, r) in enumerate(zip(self.panels, self.rows)):
            at = self.times[i]
            if t < at:
                continue
            p = t-at
            slide = out_cubic(p/.4)
            y = (self.top+i*self.row_h+(self.row_h-self.gap)/2)*u
            x = W/2-(1-slide)*60*u*(1 if i % 2 else -1)
            self._paste(canvas, panel, x, y, clamp(p/.25), 1+(.05*math.exp(-p*6) if r['ours'] else 0))
            q = p-.15
            if q >= 0:
                pop = 1+.45*math.exp(-q*10)*math.cos(q*24) if q < .5 else 1
                self._paste(canvas, self._score_cached(i), x, y, clamp(q/.1), pop)
            if r['ours'] and p < 1.2:
                pink_dots = self.yellow if self.font else cards.PINK
                d = ImageDraw.Draw(canvas, 'RGBA')
                rnd = np.random.default_rng(i)
                for _ in range(24):
                    sx = W/2+rnd.uniform(-250, 250)*u
                    sy = y+rnd.uniform(-30, 30)*u-p*rnd.uniform(20, 80)*u
                    rad = rnd.uniform(1.2, 3.2)*u*(1-p/1.2)
                    d.ellipse((sx-rad, sy-rad, sx+rad, sy+rad), fill=(*pink_dots, int(230*(1-p/1.2))))
        flash = (1-(t-DROP)/.3)**2*.3 if self.mine is not None and 0 <= t-DROP < .3 else 0.0
        return finish(canvas, t if self.fades else 1.0, self.length if self.fades else 1e9, self.scan_step, flash)

    def _score_cached(self, i):
        cache = self.__dict__.setdefault('_scores', {})
        if i not in cache:
            cache[i] = self._score(self.rows[i], self.row_h-self.gap)
        return cache[i]

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
            if i == self.mine:
                out += [(at, sounds.impact(1)*.9), (at+.15, sounds.ding(2)*.8), (at+.2, sounds.shine()*1.3)]
            else:
                out += [(at, sounds.whoosh(.18)*.35), (at+.15, sounds.tick(i)*.9)]
        return out


def png_bytes(rows, logo=None, format='Story 9:16', scale=2, style=None, **kw):
    out = io.BytesIO()
    RoundShow(rows, logo=logo, format=format, scale=scale, style=style, still=True, **kw).still_frame().save(
        out, 'PNG', compress_level=5)
    return out.getvalue()


def render_video(rows, logo, path, fps=30, format='Story 9:16', scale=2, track=None, sound=True, volume=.8,
                 progress_callback=None, style=None, **kw):
    from crt_presets import even_video_frame
    from renderer import video_writer
    show = RoundShow(rows, logo=logo, format=format, scale=scale, track=track, style=style, **kw)
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
