"""Focus moments (3.3): the camera goes close on what matters and shows the change.

Classifica: the table enters in last week's order; the camera zooms on our row,
the row climbs (or slips) past the others, which make room, lands with a flash
and a badge on the right: green ▲ places gained, yellow = same place, red ▼
places lost. Then the camera pulls back and the badge stays.

All functions are pure in the time: `p` is the seconds since the focus started.
"""
from __future__ import annotations

import math

from PIL import Image

from render_utils import ScaledDraw

ZOOM_IN, MOVE_AT, MOVE, SAME_PULSE, HOLD, ZOOM_OUT = .45, .75, .9, .5, .85, .45
ZOOM = 1.22
COLORS = {'up': (91, 230, 164), 'same': (255, 201, 99), 'down': (255, 107, 120)}


def lead(mode):
    """Seconds from the focus start to the landing (the moment that goes on the drop)."""
    return MOVE_AT+(SAME_PULSE if mode == 'same' else MOVE)


def length(mode):
    return lead(mode)+HOLD+ZOOM_OUT


def mode_of(prev, now):
    return 'same' if prev == now else ('up' if prev > now else 'down')


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x*x*x*(x*(x*6-15)+10)          # smootherstep: no jerk at start or end


def _back(x):
    x = max(0.0, min(1.0, x))
    c = 1.7
    return 1+(c+1)*(x-1)**3+c*(x-1)**2


def _rows(table):
    return table.image.info['row_edges']


def _row_y(table, ty, row_index, s):
    edges = _rows(table)
    th = table.image.height/s
    y0, y1 = edges[row_index]
    return ty-th/2+y0, ty-th/2+y1


def travel(p, mode):
    """0 -> 1 progress of the move."""
    if mode == 'same':
        return 1.0
    return _smooth((p-MOVE_AT)/MOVE)


def zoom(p, mode):
    """Zoom factor of the focus camera at p."""
    total = length(mode)
    if p < 0 or p > total:
        return 1.0
    if p < ZOOM_IN:
        return 1+(ZOOM-1)*_smooth(p/ZOOM_IN)
    if p > total-ZOOM_OUT:
        return 1+(ZOOM-1)*_smooth((total-p)/ZOOM_OUT)
    return ZOOM


def camera(prepared, data, p):
    """(zoom, centre x, centre y) in layout units: the camera follows the row while it moves."""
    base, layers, positions = prepared
    s = base.width/540
    table = next(l for l in layers if l.id == 'table')
    tx, ty = positions['table']
    tw = table.image.width/s
    mode = data['mode']
    k = travel(p, mode)
    a0, a1 = _row_y(table, ty, data['ours'], s)
    b0, b1 = _row_y(table, ty, data['prev'], s)
    cy = (b0+b1)/2+((a0+a1)/2-(b0+b1)/2)*k
    cx = tx+tw/2*.18                     # a little right of centre: the badge must fit
    return zoom(p, mode), cx, cy


def badge(mode, places, s, row_h):
    """The indicator: ▲ 2 / = / ▼ 1 on a rounded tab, at scale s."""
    from animations import _label
    colour = COLORS[mode]
    h = max(12, min(22, row_h-3))
    w = 34 if mode != 'same' else 24
    im = Image.new('RGBA', (round(w*s), round(h*s)))
    d = ScaledDraw(im, s)
    d.rounded_rectangle((0, 0, w-.5, h-.5), radius=h/2.6, fill=(*colour, 255))
    ink = (12, 16, 24)
    mid = h/2
    a = h*.22
    if mode == 'up':
        d.polygon([(5, mid+a), (5+a, mid-a), (5+2*a, mid+a)], fill=(*ink, 255))
    elif mode == 'down':
        d.polygon([(5, mid-a), (5+a, mid+a), (5+2*a, mid-a)], fill=(*ink, 255))
    text = '=' if mode == 'same' else str(places)
    label = _label(text, ink, max(8, round(h*.62)), max(1, round(s)))
    if label is not None:
        x = (w/2 if mode == 'same' else 5+2*a+(w-5-2*a)/2)*s-label.width/2
        im.alpha_composite(label, (max(0, round(x)), max(0, round(mid*s-label.height/2))))
    return im


def draw(canvas, prepared, data, p, backdrop):
    """Rows moving, landing flash and badge (p = seconds since the focus started)."""
    from animations import _put, _tinted, _whiten, _scaled
    base, layers, positions = prepared
    s = canvas.width/540
    table = next(l for l in layers if l.id == 'table')
    tx, ty = positions['table']
    th, tw = table.image.height/s, table.image.width/s
    mode, ours, prev = data['mode'], data['ours'], data['prev']
    land = lead(mode)
    edges = _rows(table)
    before = getattr(table, 'before', None)
    if mode != 'same' and before is not None and MOVE_AT <= p < land:
        k = travel(p, mode)
        mapping = table.image.info['before_rows']
        a, b = ours-1, prev-1                      # row indexes without the header
        lo, hi = min(a, b), max(a, b)
        top, bottom = edges[lo+1][0], edges[hi+1][1]
        # Clean the rows that move (their old pixels), then draw them where they are now.
        box = (round((tx-tw/2)*s), round((ty-th/2+top)*s), round((tx+tw/2)*s), round((ty-th/2+bottom)*s))
        canvas.paste(backdrop.crop(box), box[:2])
        for after in range(lo, hi+1):
            if after == a:
                continue
            old = mapping[after]
            y0, y1 = edges[old+1]
            band = before.crop((0, round(y0*s), before.width, round(y1*s)))
            y = y0+(edges[after+1][0]-y0)*k
            _put(canvas, band, None, (tx, ty-th/2+y+(y1-y0)/2))
        y0, y1 = edges[b+1]
        band = before.crop((0, round(y0*s), before.width, round(y1*s)))
        lift = 1+.05*math.sin(math.pi*k)
        for lag, alpha in ((.22, .18), (.11, .32)):             # a pink trail behind our row
            kk = max(0.0, k-lag)
            y = y0+(edges[a+1][0]-y0)*kk
            _put(canvas, _tinted(band, (255, 92, 190), 1), None, (tx, ty-th/2+y+(y1-y0)/2), alpha)
        y = y0+(edges[a+1][0]-y0)*k
        shadow = _tinted(_scaled(band, lift), (0, 0, 0), 1)
        _put(canvas, shadow, None, (tx+2, ty-th/2+y+(y1-y0)/2+3), .45)
        _put(canvas, _scaled(band, lift), None, (tx, ty-th/2+y+(y1-y0)/2))
    a0, a1 = edges[ours]
    after = getattr(table, 'clean', table.image)
    if p >= land and p < land+.4:                                 # landing flash
        band = after.crop((0, round(a0*s), after.width, round(a1*s)))
        pop = 1+.06*(1-_smooth((p-land)/.4))
        _put(canvas, _whiten(_scaled(band, pop), .55*(1-(p-land)/.4)), None, (tx, ty-th/2+(a0+a1)/2))
    if mode == 'same' and MOVE_AT <= p < land+.3:                 # same place: the row breathes twice
        band = after.crop((0, round(a0*s), after.width, round(a1*s)))
        glow = .35*max(0.0, math.sin((p-MOVE_AT)/(land+.3-MOVE_AT)*2*math.pi*2))
        _put(canvas, _whiten(band, glow, (255, 236, 170)), None, (tx, ty-th/2+(a0+a1)/2))
    show_at = land-(.15 if mode == 'same' else 0)
    if p >= show_at:                                              # the badge pops and stays
        row_h = a1-a0
        tab = badge(mode, abs(prev-ours), s, row_h)
        k = _back((p-show_at)/.35)
        x = tx+tw/2+tab.width/s/2+3
        _put(canvas, _scaled(tab, max(.05, k)), None, (x, ty-th/2+(a0+a1)/2), min(1.0, (p-show_at)/.12))


# --- 3.4: the same care everywhere, with sense and variety --------------------------------
# Every highlight answers "what changed?". The camera zooms only on what is small on screen
# (a table row, a name in the list) or moves (the classifica climb); big things (the score,
# a calendar row) get a spotlight, a highlighter or a stamp instead. The treatment changes
# with the round, so two weeks never look the same; it can also be fixed in the editor.

HIGHLIGHTS = {'auto': 'Automatica (cambia ogni giornata)', 'riflettore': 'Riflettore', 'evidenziatore': 'Evidenziatore',
              'timbro': 'Timbro', 'zoom': 'Zoom (solo su cose piccole)'}
TREATMENTS = {'fulltime': ('riflettore', 'timbro', 'evidenziatore'),
              'calendario': ('riflettore', 'evidenziatore', 'timbro'),
              'convocati': ('zoom', 'riflettore', 'evidenziatore')}
CHIPS = ('vola', 'conta', 'timbro')
SMALL = 22                 # layout units: below this height a zoom helps reading
POINTS = {'win': (3, COLORS['up']), 'draw': (1, COLORS['same']), 'loss': (0, COLORS['down'])}


def treatment(info, kind):
    options = TREATMENTS[kind]
    chosen = info.get('highlight', 'auto')
    if chosen in options:
        return chosen
    if chosen == 'zoom':           # zoom asked where the subject is big: the spotlight says the same
        return 'riflettore'
    level = int(info.get('level', 1) or 1)
    shift = {'calendario': 1}.get(kind, 0)      # the same week, different looks in different graphics
    return options[(level-1+shift) % len(options)]


def chip_style(info):
    level = int(info.get('level', 1) or 1)
    return CHIPS[(level-1) % len(CHIPS)]


def _layer(prepared, lid):
    return next((l for l in prepared[1] if l.id == lid), None)


def _box(prepared, lid, pad=6):
    layer = _layer(prepared, lid)
    s = prepared[0].width/540
    x, y = prepared[2][lid]
    w, h = layer.image.width/s, layer.image.height/s
    return (x-w/2-pad, y-h/2-pad, x+w/2+pad, y+h/2+pad)


def _row_box(prepared, row, pad=3):
    s = prepared[0].width/540
    table = _layer(prepared, 'table')
    tx, ty = prepared[2]['table']
    tw, th = table.image.width/s, table.image.height/s
    y0, y1 = table.image.info['row_edges'][row]
    return (tx-tw/2-pad, ty-th/2+y0-pad, tx+tw/2+pad, ty-th/2+y1+pad)


def subjects(prepared, kind, data, style=None):
    """[(time from the moment, box)] the highlight travels through."""
    if kind == 'focus_score' and style == 'evidenziatore' and _layer(prepared, 'result'):
        return [(0, _box(prepared, 'result', 4))]          # the pen underlines VITTORIA / PAREGGIO / SCONFITTA
    if kind == 'focus_score':      # the match: crests, score and result, as one band
        boxes = [_box(prepared, lid, 6) for lid in ('home_logo', 'score', 'away_logo', 'result') if _layer(prepared, lid)]
        return [(0, (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)))]
    if kind == 'stamp':
        keys = [(0, _row_box(prepared, data['row']))]
        if data.get('next') is not None:
            keys += [(.95, _row_box(prepared, data['row'])), (1.6, _row_box(prepared, data['next']))]
        return keys
    if kind == 'captain':
        return [(0, _box(prepared, data['layer'], 3))]
    return []


def _travel(keys, p):
    if p <= keys[0][0]:
        return keys[0][1]
    for (t0, b0), (t1, b1) in zip(keys, keys[1:]):
        if p <= t1:
            k = _smooth((p-t0)/max(1e-6, t1-t0))
            return tuple(u+(v-u)*k for u, v in zip(b0, b1))
    return keys[-1][1]


def _envelope(p, total, fade=.3):
    if p < 0 or p > total:
        return 0.0
    return _smooth(min(p/fade, (total-p)/fade, 1.0))


SPOT_HOLD = {'focus_score': 1.6, 'stamp': 2.3, 'captain': 1.7}
KINDS = {'focus_score': 'fulltime', 'stamp': 'calendario', 'captain': 'convocati'}


def camera_at(prepared, moments_list, t):
    """(zoom, cx, cy): the classifica climb, and the zoom treatment on small subjects only."""
    for at, kind, data in moments_list:
        if kind == 'climb':
            p = t-(at-data['lead'])
            if 0 <= p <= length(data['mode']):
                return camera(prepared, data, p)
    info = prepared[0].info
    for at, kind, data in moments_list:
        if kind not in KINDS or treatment(info, KINDS[kind]) != 'zoom':
            continue
        keys = subjects(prepared, kind, data)
        box = keys[0][1]
        if box[3]-box[1] > SMALL+8:      # not small: no zoom
            continue
        p = t-at+.2
        total = SPOT_HOLD[kind]+.4
        k = _envelope(p, total, .4)
        if k > 0:
            x0, y0, x1, y1 = _travel(keys, p)
            return 1+.2*k, (x0+x1)/2, (y0+y1)/2
    return 1.0, 270, 480


def _spotlight(canvas, box, k, s):
    if k <= 0:
        return
    small = 4
    w, h = canvas.width//small, canvas.height//small
    mask = Image.new('L', (w, h), 255)
    d = ScaledDraw(mask, s/small)
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0-4, y0-4, x1+4, y1+4), radius=10, fill=0)
    from PIL import ImageFilter
    mask = mask.filter(ImageFilter.GaussianBlur(3)).resize(canvas.size, Image.Resampling.BILINEAR)
    mask = mask.point(lambda v: round(v*.72*k))
    canvas.paste((6, 4, 14), (0, 0), mask)


def _highlighter(canvas, box, k, s, colour, sweep):
    if k <= 0:
        return
    x0, y0, x1, y1 = box
    right = x0+(x1-x0)*_smooth(sweep)
    d = ScaledDraw(canvas, s, 'RGBA')
    d.rectangle((x0, y1-(y1-y0)*.42, right, y1-1), fill=(*colour, round(110*k)))
    d.rectangle((x0, y1-3, right, y1-1), fill=(*colour, round(230*k)))


def _stamp(canvas, backdrop, box, p, s, colour):
    from animations import _put, _scaled
    if p < 0 or p > .7:
        return
    x0, y0, x1, y1 = (round(v*s) for v in box)
    piece = backdrop.crop((x0, y0, x1, y1)).convert('RGBA')
    k = 1+.55*(1-_smooth(p/.22))
    _put(canvas, _scaled(piece, k), None, ((box[0]+box[2])/2, (box[1]+box[3])/2), min(1.0, p/.05))
    ring = (p-.18)/.45
    if 0 < ring < 1:
        d = ScaledDraw(canvas, s, 'RGBA')
        cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
        rx, ry = (box[2]-box[0])/2+24*ring, (box[3]-box[1])/2+18*ring
        d.rounded_rectangle((cx-rx, cy-ry, cx+rx, cy+ry), radius=8, outline=(*colour, round(220*(1-ring))), width=2)


def chip(text, colour, s, h=18):
    """A rounded tab with dark text (points, results, tags)."""
    from animations import _label
    label = _label(text, (12, 16, 24), max(8, round(h*.6)), max(1, round(s)))
    w = (label.width/s if label is not None else 20)+14
    im = Image.new('RGBA', (round(w*s), round(h*s)))
    ScaledDraw(im, s).rounded_rectangle((0, 0, w-.5, h-.5), radius=h/2.4, fill=(*colour, 255))
    if label is not None:
        im.alpha_composite(label, (round((w*s-label.width)/2), round((h*s-label.height)/2)))
    return im


def _points_chip(canvas, prepared, data, p, s):
    from animations import _put, _scaled
    value, colour = POINTS[data['outcome']]
    style = data.get('style', 'vola')
    result = _layer(prepared, 'result')
    tab = chip(f'+{value} PT', colour, s, 20)
    if result is not None:
        rx, ry = prepared[2]['result']
        home = (rx+result.image.width/s/2+tab.width/s/2+6, ry)
    else:
        home = (prepared[2]['score'][0], prepared[2]['score'][1]+44)
    if style == 'vola':          # born on the score, flies down to the result
        sx, sy = prepared[2]['score']
        k = _smooth(p/.6)
        x = sx+(home[0]-sx)*k
        y = sy+(home[1]-sy)*k-28*math.sin(math.pi*k)
        _put(canvas, _scaled(tab, 1.6-.6*k), None, (x, y), min(1.0, p/.1))
    elif style == 'conta':       # counts up from +0
        shown = min(value, int(p/.18)) if value else 0
        tab = chip(f'+{shown} PT', colour if shown == value else (200, 200, 210), s, 20)
        bump = 1+.12*max(0.0, 1-((p % .18)/.18)) if shown < value or p < value*.18+.2 else 1
        _put(canvas, _scaled(tab, bump), None, home, min(1.0, p/.1))
    else:                        # stamp
        k = 1+.9*(1-_smooth(p/.22))
        _put(canvas, _scaled(tab, k), None, home, min(1.0, p/.06))


def overlays(canvas, prepared, moments_list, t, backdrop=None):
    """Highlights (spotlight / highlighter / stamp), points chip and captain armband."""
    from animations import _label, _put, _scaled
    s = canvas.width/540
    info = prepared[0].info
    pink, cyan, yellow = info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99)))
    for at, kind, data in moments_list:
        p = t-at
        if kind in KINDS and p >= -.3:
            style = treatment(info, KINDS[kind])
            keys = subjects(prepared, kind, data, style)
            total = SPOT_HOLD[kind]
            colour = STAMP_COLORS.get(data.get('result'), yellow) if kind == 'stamp' else yellow
            if style == 'riflettore':
                _spotlight(canvas, _travel(keys, p), _envelope(p+.3, total+.3), s)
            elif style == 'evidenziatore':
                k = _envelope(p, total)
                if len(keys) > 1 and p > keys[1][0]:     # second subject: a new stroke
                    seg = p-keys[1][0]
                    _highlighter(canvas, keys[-1][1], k, s, cyan, seg/.45)
                else:
                    _highlighter(canvas, keys[0][1], k, s, colour, p/.45)
            elif style == 'timbro' and backdrop is not None:
                _stamp(canvas, backdrop, keys[0][1], p, s, colour)
                if len(keys) > 1:
                    _highlighter(canvas, keys[-1][1], _envelope(p-keys[-1][0], total-keys[-1][0]), s, cyan,
                                 (p-keys[-1][0])/.45)
        if kind == 'points' and p >= 0:
            _points_chip(canvas, prepared, data, p, s)
        elif kind == 'captain' and p >= 0:
            # The armband: a yellow C that pops on the left of the captain's row and stays.
            layer = _layer(prepared, data['layer'])
            x, y = prepared[2][data['layer']]
            w, h = layer.image.width/s, layer.image.height/s
            size = max(9.0, min(14.0, h*1.1))
            k = _back(p/.4)
            tab = Image.new('RGBA', (round(size*s), round(size*s)))
            ScaledDraw(tab, s).ellipse((0, 0, size-.5, size-.5), fill=(*COLORS['same'], 255))
            label = _label('C', (12, 16, 24), max(6, round(size*.6)), max(1, round(s)))
            if label is not None:
                tab.alpha_composite(label, (round((tab.width-label.width)/2), round((tab.height-label.height)/2)))
            _put(canvas, _scaled(tab, max(.05, k)), None, (x-w/2-size/2-2, y), min(1.0, p/.1))


STAMP_COLORS = {'V': COLORS['up'], 'N': COLORS['same'], 'P': COLORS['down']}


# --- 3.5: what is at stake ----------------------------------------------------------------

STAKE_STYLES = ('gira', 'scorri', 'glitch')
STAKE_HOLD = 2.6


def stake_style(info):
    level = int(info.get('level', 1) or 1)
    return STAKE_STYLES[(level-1) % len(STAKE_STYLES)]


def _swap(old, new, p, style, s):
    """The name box turning into the stats and back: p 0..1 is the change."""
    from animations import _glitched
    w = max(old.width, new.width)
    h = max(old.height, new.height)
    out = Image.new('RGBA', (w, h))
    if style == 'gira':          # the box flips on its horizontal axis
        k = abs(math.cos(math.pi*p))
        img = old if p < .5 else new
        sh = max(1, round(img.height*k))
        out.alpha_composite(img.resize((img.width, sh)), ((w-img.width)//2, (h-sh)//2))
    elif style == 'scorri':      # the old text leaves upwards, the new one comes from below
        e = _smooth(p)
        for img, dy in ((old, -e), (new, 1-e)):
            y = round((h-img.height)/2+dy*h)
            layer = Image.new('RGBA', (w, h))
            layer.alpha_composite(img, ((w-img.width)//2, 0), (0, max(0, -y))) if y < 0 else \
                layer.alpha_composite(img.crop((0, 0, img.width, max(0, min(img.height, h-y)))), ((w-img.width)//2, y)) \
                if y < h else None
            out.alpha_composite(layer)
    else:                        # glitch: the name breaks into the stats
        img = old if p < .5 else new
        broken = _glitched(img, 1-abs(1-2*p), int(p*997), s)
        if broken is not None:
            out.alpha_composite(broken.crop((0, 0, min(w, broken.width), min(h, broken.height))),
                                ((w-min(w, broken.width))//2, 0))
    return out


def _stat_image(card, colour, s, max_w, max_h, accent=(255, 201, 99)):
    """'2°  17 PT': the position in the accent colour with a small drawn degree sign, the points in the team colour."""
    from pixel_fonts import pixel_text_runs
    scale = max(1, round(s))
    size = max_h*.62
    pos = pixel_text_runs([(str(card['pos']), accent)], 'CRT Scoreboard', size, 0, scale)
    pts = pixel_text_runs([(f"{card['pt']} PT", colour)], 'CRT Scoreboard', size, 0, scale)
    ring = max(2, round(pos.height*.32))
    gap = round(size*.9*scale)
    out = Image.new('RGBA', (pos.width+ring+round(scale)+gap+pts.width, max(pos.height, pts.height)))
    out.alpha_composite(pos, (0, 0))
    d = ScaledDraw(out, 1)
    x0 = pos.width+round(scale)
    d.ellipse((x0, 0, x0+ring, ring), outline=(*accent, 255), width=max(1, round(ring/3.2)))
    out.alpha_composite(pts, (pos.width+ring+round(scale)+gap, 0))
    limit = round(max_w*.9*s)
    if out.width > limit:
        out = out.resize((limit, max(1, round(out.height*limit/out.width))), Image.Resampling.LANCZOS)
    return out


def stakes_overlay(canvas, prepared, data, p, backdrop):
    """Matchday: both name boxes turn into position and points, a gap chip under the VS, then back."""
    from animations import _put, _scaled
    if backdrop is None or p < 0 or p > STAKE_HOLD+.5:
        return
    s = canvas.width/540
    info = prepared[0].info
    pink, cyan, yellow = info.get('frame_colors', ((242, 104, 168), (121, 220, 247), (255, 201, 99)))
    ours = 'away' if info.get('our_side') == 'Ospiti' else 'home'
    style = data['style']
    change = .35
    if p < change:
        k = p/change
    elif p > STAKE_HOLD:
        k = 1-(p-STAKE_HOLD)/.5
    else:
        k = 1.0
    for side in ('home', 'away'):
        layer = _layer(prepared, f'{side}_name')
        if layer is None:
            continue
        box = _box(prepared, f'{side}_name', 0)
        px = tuple(round(v*s) for v in box)
        canvas.paste(backdrop.crop(px), px[:2])           # the name off the panel, the panel stays
        stat = _stat_image(data[side], pink if side == ours else cyan, s, box[2]-box[0], box[3]-box[1], yellow)
        img = _swap(layer.image, stat, max(0.0, min(1.0, k)), style, s) if 0 < k < 1 else (stat if k >= 1 else layer.image)
        _put(canvas, img, None, ((box[0]+box[2])/2, (box[1]+box[3])/2))
    gap = data['home']['pt']-data['away']['pt']
    vs = _layer(prepared, 'vs')
    if vs is not None and k > 0:
        x, y = prepared[2]['vs']
        text = 'PARI' if gap == 0 else f'{abs(gap)} PT'
        tab = chip(text, yellow, s, 15)
        arrow = Image.new('RGBA', (round(10*s), round(12*s)))
        if gap:                                            # pointing at the team ahead
            d = ScaledDraw(arrow, s)
            d.polygon([(9, 1), (9, 11), (1, 6)] if gap > 0 else [(1, 1), (1, 11), (9, 6)], fill=(*yellow, 255))
        top = y+vs.image.height/s/2+2
        _put(canvas, _scaled(tab, max(.05, _back(min(1.0, k*1.3)))), None, (x, top), min(1.0, k*2))
        if gap:
            side_x = x-tab.width/s/2-8 if gap > 0 else x+tab.width/s/2+8
            _put(canvas, arrow, None, (side_x, top), min(1.0, k*2))


def gap_overlay(canvas, prepared, data, p):
    """Classifica: a bracket from our row to the one above with the points to close (or our lead)."""
    from animations import _put, _scaled
    if p < 0:
        return
    s = canvas.width/540
    table = _layer(prepared, 'table')
    tx, ty = prepared[2]['table']
    tw, th = table.image.width/s, table.image.height/s
    edges = table.image.info['row_edges']
    a0, a1 = edges[data['ours']]
    b0, b1 = edges[data['other']]
    ya, yb = ty-th/2+(a0+a1)/2, ty-th/2+(b0+b1)/2
    x = tx-tw/2-3                                   # just inside the screen, on the table's left edge
    fade = 1.0 if p < 2.6 else max(0.0, 1-(p-2.6)/.4)
    if fade <= 0:
        return
    k = _smooth(p/.45)
    d = ScaledDraw(canvas, s, 'RGBA')
    colour = COLORS['up'] if data['lead'] else (121, 220, 247)
    end = ya+(yb-ya)*k
    d.line((x+6, ya, x, ya, x, end), fill=(*colour, round(230*fade)), width=1.8)
    if k >= 1:
        d.line((x, yb, x+6, yb), fill=(*colour, round(230*fade)), width=1.8)
        text = f"+{data['points']} PT" if data['lead'] else f"-{data['points']} PT"
        tab = chip(text, colour, s, 14)
        q = _back((p-.45)/.3)
        _put(canvas, _scaled(tab, max(.05, q)), None, (x+tab.width/s/2+4, (ya+yb)/2), min(1.0, (p-.45)/.1)*fade)
