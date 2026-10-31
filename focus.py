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


# --- 3.4: the same care everywhere ---------------------------------------------------
# A "window" is a short camera move: in, hold (the centre can travel), out.

POINTS = {'win': ('+3 PT', COLORS['up']), 'draw': ('+1 PT', COLORS['same']), 'loss': ('+0 PT', COLORS['down'])}
STAMP = {'V': COLORS['up'], 'N': COLORS['same'], 'P': COLORS['down']}


def _layer(prepared, lid):
    return next((l for l in prepared[1] if l.id == lid), None)


def _window_zoom(p, zin, hold, zout, amount):
    if p < 0 or p > zin+hold+zout:
        return 1.0
    if p < zin:
        return 1+(amount-1)*_smooth(p/zin)
    if p > zin+hold:
        return 1+(amount-1)*_smooth((zin+hold+zout-p)/zout)
    return amount


def _path(p, keys):
    """Centre along keyframes [(time, x, y)], eased between them."""
    if p <= keys[0][0]:
        return keys[0][1:]
    for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
        if p <= t1:
            k = _smooth((p-t0)/max(1e-6, t1-t0))
            return x0+(x1-x0)*k, y0+(y1-y0)*k
    return keys[-1][1:]


def _row_centre(prepared, row):
    """Centre of a table row; `row` indexes row_edges (the classifica has the header at 0)."""
    s = prepared[0].width/540
    table = _layer(prepared, 'table')
    tx, ty = prepared[2]['table']
    y0, y1 = _row_y(table, ty, row, s)
    return tx, (y0+y1)/2


def windows(prepared, moments_list):
    """Camera windows [(start, zin, hold, zout, zoom, keys)] built from the scene's moments."""
    out = []
    positions = prepared[2]
    for at, kind, data in moments_list:
        if kind == 'climb':
            continue                      # the classifica camera has its own path (camera())
        if kind == 'focus_score':
            x, y = positions['score']
            out.append((at-.3, .35, 1.0, .5, 1.17, [(0, x, y)]))
        elif kind == 'stamp':
            x, y = _row_centre(prepared, data['row'])
            keys = [(0, x+40, y)]
            if data.get('next') is not None:
                nx, ny = _row_centre(prepared, data['next'])
                keys = [(0, x+40, y), (.95, x+40, y), (1.65, nx+40, ny)]
            out.append((at-.35, .4, 1.6 if data.get('next') is not None else .9, .5, 1.2, keys))
        elif kind == 'captain':
            layer = _layer(prepared, data['layer'])
            x, y = positions[data['layer']]
            out.append((at-.3, .35, 1.1, .45, 1.16, [(0, x+30, y)]))
    return out


def camera_at(prepared, moments_list, t):
    """(zoom, cx, cy) of every focus move at time t (the classifica climb included)."""
    for at, kind, data in moments_list:
        if kind == 'climb':
            p = t-(at-data['lead'])
            if 0 <= p <= length(data['mode']):
                return camera(prepared, data, p)
    for start, zin, hold, zout, amount, keys in windows(prepared, moments_list):
        p = t-start
        z = _window_zoom(p, zin, hold, zout, amount)
        if z > 1.0005:
            cx, cy = _path(p-zin*.5, keys)
            return z, cx, cy
    return 1.0, 270, 480


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


def overlays(canvas, prepared, moments_list, t):
    """The detail drawings of 3.4: points chip, calendar stamp, captain tag."""
    from animations import _put, _scaled
    s = canvas.width/540
    positions = prepared[2]
    for at, kind, data in moments_list:
        p = t-at
        if p < 0:
            continue
        if kind == 'points':
            text, colour = POINTS[data['outcome']]
            tab = chip(text, colour, s, 20)
            k = _back(p/.4)
            result = _layer(prepared, 'result')
            if result is not None:          # next to VITTORIA / PAREGGIO / SCONFITTA
                x, y = positions['result']
                x += result.image.width/s/2+tab.width/s/2+6
            else:
                x, y = positions['score'][0], positions['score'][1]+44
            pulse = 1+.05*math.sin(p*6)*max(0.0, 1-p/1.5)
            _put(canvas, _scaled(tab, max(.05, k*pulse)), None, (x, y), min(1.0, p/.12))
        elif kind == 'stamp':
            # The result box of the last match is stamped again: big, then down hard, with a ring.
            import calendario_renderer as cal
            table = _layer(prepared, 'table')
            tx, ty = positions['table']
            tw, th = table.image.width/s, table.image.height/s
            y0, y1 = table.image.info['row_edges'][data['row']]
            box = (round((cal.TABLE_W-80)*s), round(y0*s), round(cal.TABLE_W*s), round(y1*s))
            piece = table.image.crop(box)
            cx = tx-tw/2+cal.TABLE_W-40
            cy = ty-th/2+(y0+y1)/2
            if p < .6:
                k = 1+1.1*(1-_smooth(p/.2))
                _put(canvas, _scaled(piece, k), None, (cx, cy), min(1.0, p/.06))
                ring = max(0.0, (p-.18)/.4)
                if 0 < ring < 1:
                    d = ScaledDraw(canvas, s, 'RGBA')
                    r = 30+50*ring
                    d.ellipse((cx-r, cy-r*.6, cx+r, cy+r*.6), outline=(*STAMP[data['result']], round(200*(1-ring))), width=2)
        elif kind == 'captain':
            # The armband: a yellow C that pops on the left of the captain's row and stays.
            layer = _layer(prepared, data['layer'])
            x, y = positions[data['layer']]
            w = layer.image.width/s
            h = layer.image.height/s
            size = max(9.0, min(14.0, h*1.1))
            k = _back(p/.4)
            tab = Image.new('RGBA', (round(size*s), round(size*s)))
            ScaledDraw(tab, s).ellipse((0, 0, size-.5, size-.5), fill=(*COLORS['same'], 255))
            from animations import _label
            label = _label('C', (12, 16, 24), max(6, round(size*.6)), max(1, round(s)))
            if label is not None:
                tab.alpha_composite(label, (round((tab.width-label.width)/2), round((tab.height-label.height)/2)))
            _put(canvas, _scaled(tab, max(.05, k)), None, (x-w/2-size/2-2, y), min(1.0, p/.1))


