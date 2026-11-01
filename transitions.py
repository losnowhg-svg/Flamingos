"""Retro CRT transitions and multi-scene video sequences.

Every transition is a pure function of two equal-sized RGB frames and a
progress value p in [0, 1], so it renders the same in preview and in the MP4.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image

TRANSITIONS = {
    'channel': 'Cambio canale',
    'poweroff': 'Spegni e riaccendi',
    'glitch': 'Glitch RGB',
    'rewind': 'Riavvolgimento VHS',
    'roll': 'Rolling verticale',
    'cut': 'Taglio netto',
    'pixel': 'Pixel che si sgranano',
    'iris': 'Cerchio (fine livello)',
    'blocks': 'Blocchi che cadono',
    'wipe': 'Tendina a scalini',
    'carta': '✨ Diventa una figurina (si gira)',
    'strappo': '✨ Strappo della bustina',
    'olografica': '✨ Lampo olografico',
    'pioggia': '✨ Pioggia di figurine',
    'pagina': '✨ Pagina dell\'album',
}
SPECIAL = ('carta', 'strappo', 'olografica', 'pioggia', 'pagina')
VARIED = ('channel', 'pixel', 'blocks', 'iris', 'glitch', 'wipe', 'rewind', 'roll')
TRANSITION_IDS = tuple(TRANSITIONS)
OSD_GREEN = (120, 255, 140)


def _ease(p):
    return p*p*(3-2*p)


def _seed(p, salt=0):
    return int(p*10_000)+salt*7919


def _osd(width, text, color=OSD_GREEN, size_ratio=.06):
    from pixel_fonts import pixel_text_runs
    scale = max(1, round(width/540))
    size = max(12, width*size_ratio/scale)
    return pixel_text_runs([(text, color)], 'CRT Terminal', size, 540, scale)


def _paste_osd(frame, text, anchor='topright', color=OSD_GREEN):
    label = _osd(frame.width, text, color)
    if not label:
        return frame
    # A dark, slightly offset copy keeps the OSD legible on bright static.
    shadow = Image.new('RGBA', label.size, (0, 0, 0, 0))
    shadow.putalpha(label.getchannel('A').point(lambda a: a*.7))
    margin = round(frame.width*.06)
    x = frame.width-label.width-margin if anchor == 'topright' else margin
    y = round(frame.height*.06)
    canvas = frame.convert('RGBA')
    canvas.alpha_composite(shadow, (x+3, y+3))
    canvas.alpha_composite(label, (x, y))
    return canvas.convert('RGB')


def _static(height, width, p, salt=0, level=1.0):
    rng = np.random.default_rng(_seed(p, salt))
    # Static is generated at quarter resolution and enlarged: chunkier, faster.
    small = rng.integers(0, 256, (max(1, height//3), max(1, width//3)), dtype=np.uint8)
    noise = np.repeat(np.repeat(small, 3, axis=0), 3, axis=1)[:height, :width]
    noise = np.pad(noise, ((0, height-noise.shape[0]), (0, width-noise.shape[1])), mode='edge')
    # A darker rolling band, as on an untuned set.
    band = (np.arange(height)/height+p*1.7) % 1
    dark = 1-.45*np.exp(-((band-.5)**2)/.004)
    return (noise*dark[:, None]*level).astype(np.float32)


def _channel(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    h, w = A.shape[:2]
    noise = _static(h, w, p)[..., None]
    if p < .3:
        k = p/.3
        src = A
    elif p < .62:
        k = 1
        src = A if p < .46 else B
    else:
        k = 1-(p-.62)/.38
        src = B
    k = _ease(min(1, max(0, k)))
    shift = int(w*.04*k*math.sin(p*90))
    src = np.roll(src, shift, axis=1)
    out = src*(1-k)+noise*k
    frame = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if .18 < p < .92:
        frame = _paste_osd(frame, f'CH {channel:02d}')
    return frame


def _squash(src, sy, sx, glow):
    h, w = src.shape[:2]
    out = np.zeros_like(src)
    nh, nw = max(1, round(h*sy)), max(1, round(w*sx))
    img = Image.fromarray(src.astype(np.uint8)).resize((nw, nh), Image.Resampling.BILINEAR)
    arr = np.asarray(img, np.float32)
    arr = arr+(255-arr)*glow
    y, x = (h-nh)//2, (w-nw)//2
    out[y:y+nh, x:x+nw] = arr
    return out


def _poweroff(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if p < .5:
        q = p/.5
        src = A
    else:
        q = 1-(p-.5)/.5
        src = B
    # q: 0 = full picture, 1 = gone. Collapse to a line, then the line to a dot.
    if q < .55:
        t = _ease(q/.55)
        out = _squash(src, max(.004, 1-t), 1, t*.8)
    elif q < .9:
        t = _ease((q-.55)/.35)
        out = _squash(np.full_like(src, 255), .004, max(.01, 1-t), 0)
    else:
        out = np.zeros_like(src)
        h, w = src.shape[:2]
        r = max(1, round(w*.006*(1-(q-.9)/.1)))
        out[h//2-r:h//2+r, w//2-r:w//2+r] = 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _glitch(a, b, p, channel=2):
    src = np.asarray(a if p < .5 else b, np.float32).copy()
    h, w = src.shape[:2]
    k = 1-abs(p-.5)*2  # strongest at the cut
    rng = np.random.default_rng(_seed(p, 3))
    off = int(w*.03*k)+1
    out = src.copy()
    out[..., 0] = np.roll(src[..., 0], off, axis=1)
    out[..., 2] = np.roll(src[..., 2], -off, axis=1)
    for _ in range(int(3+12*k)):
        y = rng.integers(0, h)
        bh = int(rng.integers(max(2, h//120), max(3, h//18)))
        dx = int(rng.integers(-w//6, w//6)*k)
        out[y:y+bh] = np.roll(out[y:y+bh], dx, axis=1)
        if rng.random() < .3*k:
            out[y:y+bh] = out[y:y+bh]*.4+np.array([255, 60, 200])*.6*rng.random()
    if .4 < p < .6:
        out = out*.6+_static(h, w, p, 5)[..., None]*.4
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _rewind(a, b, p, channel=2):
    src = np.asarray(a if p < .5 else b, np.float32)
    h, w = src.shape[:2]
    k = 1-abs(p-.5)*2
    rows = np.arange(h)
    # Horizontal skew that grows toward the bottom of the frame, as on a VCR.
    skew = (k*w*.09*np.sin(rows/h*math.pi*3+p*40)).astype(int)
    idx = (np.arange(w)[None, :]-skew[:, None]) % w
    out = src[rows[:, None], idx]
    # Fast-moving tracking bands.
    for i in range(3):
        center = ((p*5+i*.37) % 1)*h
        band = np.exp(-((rows-center)**2)/(2*(h*.012)**2))[:, None]
        noise = _static(h, w, p, 11+i)
        out = out*(1-band[..., None]*k)+noise[..., None]*band[..., None]*k
    out = out*(1-.25*k)+np.array([20, 40, 160])*.25*k
    frame = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if .1 < p < .9:
        frame = _paste_osd(frame, '<< REW' if p < .5 else 'PLAY >', 'topleft', (255, 255, 255))
    return frame


def _roll(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    h = A.shape[0]
    bar = np.zeros((max(2, h//14),)+A.shape[1:], np.float32)
    strip = np.concatenate([A, bar, B], axis=0)
    offset = int(_ease(p)*(h+bar.shape[0]))
    out = strip[offset:offset+h]
    # Slight jitter and brightness pumping while the picture rolls.
    k = math.sin(p*math.pi)
    out = np.roll(out, int(k*6*math.sin(p*70)), axis=1)*(1-.15*k)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _cut(a, b, p, channel=2):
    if .45 < p < .55:
        return Image.new('RGB', a.size, (255, 255, 255))
    return a if p <= .45 else b


def _pixel(a, b, p, channel=2):
    """Mosaic: the picture breaks into bigger and bigger pixels, then rebuilds as the next one."""
    src = a if p < .5 else b
    k = 1-abs(p-.5)*2   # 0 at the ends, 1 in the middle
    block = max(1, int(round(2+k*k*(src.width/14))))
    if block <= 1:
        return src
    small = src.resize((max(1, src.width//block), max(1, src.height//block)), Image.Resampling.BILINEAR)
    small = small.quantize(32, dither=Image.Dither.NONE).convert('RGB') if k > .4 else small
    return small.resize(src.size, Image.Resampling.NEAREST)


def _iris(a, b, p, channel=2):
    """A circle closes on the centre (end of level), black, then opens on the next scene."""
    w, h = a.size
    src = a if p < .5 else b
    q = 1-p/.5 if p < .5 else (p-.5)/.5
    radius = _ease(max(0.0, min(1.0, q)))*math.hypot(w, h)/2
    yy, xx = np.ogrid[:h, :w]
    inside = (xx-w/2)**2+(yy-h*.48)**2 <= radius**2
    out = np.asarray(src).copy()
    out[~inside] = (6, 4, 12)
    return Image.fromarray(out)


def _blocks(a, b, p, channel=2):
    """Tetris-like blocks fall row by row and stack into the next scene."""
    A, B = np.asarray(a), np.asarray(b)
    h, w = A.shape[:2]
    cols, rows = 8, 14
    bw, bh = math.ceil(w/cols), math.ceil(h/rows)
    out = A.copy()
    rng = np.random.default_rng(42)
    delays = rng.uniform(0, .45, (rows, cols))
    for r in range(rows):
        for c in range(cols):
            # bottom rows land first; each block falls for .35 of the transition
            start = (rows-1-r)/rows*.5+delays[r, c]*.3
            q = (p-start)/.35
            if q <= 0:
                continue
            y1, x1 = r*bh, c*bw
            if q >= 1:
                out[y1:y1+bh, x1:x1+bw] = B[y1:y1+bh, x1:x1+bw]
                continue
            dy = int((1-q*q)*(y1+bh))   # accelerating fall from above
            top = y1-dy
            tile = B[y1:y1+bh, x1:x1+bw]
            t0 = max(0, top)
            if t0 < h and top+tile.shape[0] > 0:
                part = tile[t0-top:min(tile.shape[0], h-top)]
                out[t0:t0+part.shape[0], x1:x1+part.shape[1]] = part
    return Image.fromarray(out)


def _wipe(a, b, p, channel=2):
    """A diagonal staircase of pixel steps sweeps the next scene in, with a bright edge."""
    A, B = np.asarray(a), np.asarray(b)
    h, w = A.shape[:2]
    step = max(8, w//24)
    stair = _stairs(h, w, step)
    edge = _ease(p)*(w+h+step*2)-step
    out = np.where((stair < edge)[..., None], B, A)
    band = np.abs(stair-edge) < step*1.5   # only the pixels near the edge get the pink glow
    if band.any():
        glow = np.exp(-((stair[band]-edge)/(step*.9))**2)[:, None]*.6
        out = out.copy()
        out[band] = (out[band]*(1-glow)+np.array([255, 92, 190])*glow).astype(np.uint8)
    return Image.fromarray(out)


@lru_cache(maxsize=4)
def _stairs(h, w, step):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((xx//step)*step+(yy//step)*step).astype(np.int32)


# --- 3.10: transitions from the figurine collection --------------------------------------------

@lru_cache(maxsize=4)
def _stage(w, h):
    """Dark backdrop with a pink glow, behind a frame that becomes a card."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx-w/2)/(w*.6))**2+((yy-h*.48)/(h*.5))**2)
    glow = np.exp(-r*r*2.2)[..., None]
    base = np.array((14, 10, 22), np.float32)
    pink = np.array((242, 104, 168), np.float32)
    return Image.fromarray((base*(1-glow*.8)+pink*glow*.55).clip(0, 255).astype(np.uint8))


def _as_card(src, scale, radius_k, border_k, shine=None):
    """The frame shrunk into a card: rounded corners, a metallic edge, a gloss band."""
    from PIL import ImageDraw
    w, h = src.size
    cw, ch = max(4, int(w*scale)), max(4, int(h*scale))
    card = src.resize((cw, ch), Image.Resampling.BILINEAR).convert('RGBA')
    radius = int(min(cw, ch)*.07*radius_k)
    if border_k > 0:
        d = ImageDraw.Draw(card)
        edge = max(1, int(min(cw, ch)*.028*border_k))
        d.rounded_rectangle((0, 0, cw-1, ch-1), radius=radius, outline=(255, 214, 236, 255), width=edge)
        d.rounded_rectangle((edge, edge, cw-1-edge, ch-1-edge), radius=max(0, radius-edge),
                            outline=(242, 104, 168, 255), width=max(1, edge//2))
    if shine is not None:
        xs = np.arange(cw, dtype=np.float32)[None, :]/cw
        ys = np.arange(ch, dtype=np.float32)[:, None]/ch
        band = np.exp(-((xs+ys*.6-shine*1.9+.3)/.09)**2)*120
        layer = Image.new('RGBA', (cw, ch), (255, 255, 255, 0))
        layer.putalpha(Image.fromarray(band.astype(np.uint8)))
        card.alpha_composite(layer)
    mask = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw-1, ch-1), radius=radius, fill=255)
    card.putalpha(mask)
    return card


def _carta(a, b, p, channel=2):
    """The frame shrinks into a card, flips over, and the next scene is its other side, growing back."""
    import cards
    w, h = a.size
    canvas = _stage(w, h).copy()
    small = .62
    if p < .3:
        k = _ease(p/.3)
        card, yaw, scale = _as_card(a, 1-(1-small)*k, k, k, k*.4), 0.0, 1.0
    elif p < .72:
        k = _ease((p-.3)/.42)
        yaw = 180*k
        src = a if yaw < 90 else b
        card, scale = _as_card(src, small, 1, 1, .4+k*.6), 1.0
        if yaw >= 90:
            yaw -= 180                              # the far side, the right way round
    else:
        k = _ease((p-.72)/.28)
        card, yaw, scale = _as_card(b, small+(1-small)*k, 1-k, 1-k, None), 0.0, 1.0
    light = .55+.45*abs(math.cos(math.radians(yaw)))
    if light < .99:
        rgb = np.asarray(card, np.float32)
        rgb[..., :3] *= light
        card = Image.fromarray(rgb.astype(np.uint8), 'RGBA')
    warped, x0, y0 = cards.warp(card, (w/2, h/2), yaw, 4*math.sin(p*math.pi), 0, scale, quality='fast')
    if warped is not None:
        canvas.paste(warped, (x0, y0), warped)
    return canvas


def _jagged(w, h, seed):
    rng = np.random.default_rng(seed)
    xs = np.linspace(0, w, 26)
    ys = h*.4+rng.uniform(-1, 1, len(xs))*h*.025
    return list(zip(xs, ys))


def _strappo(a, b, p, channel=2):
    """The frame tears like the top of a pack: the upper piece flies off, the lower one drops, light behind."""
    from PIL import ImageDraw
    w, h = a.size
    line = _jagged(w, h, 7)
    top_mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(top_mask).polygon([(0, 0), (w, 0)]+line[::-1], fill=255)
    bottom_mask = Image.eval(top_mask, lambda v: 255-v)
    flash = max(0.0, 1-abs(p-.22)/.22)
    base = np.asarray(b, np.float32)
    base = base+(255-base)*flash*.6
    canvas = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    if p < .12:                                     # the crack runs across
        k = p/.12
        frame = a.copy()
        d = ImageDraw.Draw(frame)
        n = max(2, int(len(line)*k))
        d.line(line[:n], fill=(255, 255, 255), width=max(2, w//180))
        return frame
    q = _ease((p-.12)/.88)
    top = a.convert('RGBA')
    top.putalpha(top_mask)
    top = top.rotate(-q*28, center=(w*.85, h*.4), resample=Image.Resampling.BILINEAR)
    canvas.paste(top, (int(q*w*.35), int(-q*h*.75)), top)
    bottom = a.convert('RGBA')
    bottom.putalpha(bottom_mask)
    canvas.paste(bottom, (0, int(q*q*h*.9)), bottom)
    d = ImageDraw.Draw(canvas)                      # white paper fibre along the torn edge
    edge = [(x+q*w*.35*0, y+q*q*h*.9) for x, y in line]
    d.line(edge, fill=(255, 250, 240), width=max(2, w//200))
    return canvas


def _olografica(a, b, p, channel=2):
    """A diagonal holographic band sweeps across: rainbow foil and sparkles, the next scene behind it."""
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    h, w = A.shape[:2]
    d = _diag(h, w)
    width = (w+h*.6)
    edge = -width*.15+_ease(p)*width*1.3
    out = np.where((d < edge)[..., None], B, A)
    band = np.exp(-((d-edge)/(w*.09))**2)[..., None]
    hue = (d/width*2.2+p)[..., None]*6.283
    rainbow = 127.5+127.5*np.cos(hue+np.array([0, 2.094, 4.189], np.float32))
    out = 255-(255-out)*(1-rainbow/255*band*.85)
    rng = np.random.default_rng(_seed(p, 3))
    sparks = rng.random((h//4+1, w//4+1)) > .992
    sparks = np.repeat(np.repeat(sparks, 4, 0), 4, 1)[:h, :w]
    out[sparks & (band[..., 0] > .25)] = 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


@lru_cache(maxsize=4)
def _diag(h, w):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx+yy*.6


def _pioggia(a, b, p, channel=2):
    """A shower of cards flies up over the frame; behind them the scene changes."""
    from PIL import ImageDraw
    w, h = a.size
    canvas = (a if p < .5 else b).copy()
    d = ImageDraw.Draw(canvas, 'RGBA')
    rng = np.random.default_rng(11)
    cw, ch = w*.3, w*.42
    colors = ((242, 104, 168), (121, 220, 247), (255, 201, 99), (190, 140, 255))
    for i in range(34):
        x0 = rng.uniform(-.1, 1.1)*w
        delay = rng.uniform(0, .35)
        spin0, spin = rng.uniform(-40, 40), rng.uniform(-120, 120)
        q = (p-delay)/.65
        if not 0 <= q <= 1:
            continue
        y = h+ch-(h+2*ch)*q
        x = x0+math.sin(q*3+i)*w*.04
        ang = math.radians(spin0+spin*q)
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(x+ca*px-sa*py, y+sa*px+ca*py) for px, py in ((-cw/2, -ch/2), (cw/2, -ch/2), (cw/2, ch/2), (-cw/2, ch/2))]
        col = colors[i % len(colors)]
        d.polygon(pts, fill=(*col, 255), outline=(255, 255, 255, 255), width=max(2, int(w/160)))
        inner = [(x+(px-x)*.78, y+(py-y)*.78) for px, py in pts]
        d.polygon(inner, fill=(20, 14, 30, 235))
        stripe = [(x+(px-x)*.5, y+(py-y)*.5) for px, py in pts]
        d.polygon(stripe, fill=(*col, 160))
    return canvas


def _pagina(a, b, p, channel=2):
    """The frame turns away like an album page hinged on the left, over a soft shadow."""
    w, h = a.size
    ang = math.radians(92*_ease(p))
    out = np.asarray(b, np.float32).copy()
    edge = w*math.cos(ang)
    # Shadow cast by the page on the next scene, strongest near the turning edge.
    xs = np.arange(w, dtype=np.float32)
    shade = 1-.55*(1-p)*np.exp(-np.maximum(0, xs-edge)/(w*.25))
    out *= shade[None, :, None]
    canvas = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if ang < math.radians(89.5):
        dist = 3.2*w
        pts = []
        for x, y in ((0, 0), (w, 0), (w, h), (0, h)):
            px, pz = x*math.cos(ang), x*math.sin(ang)
            f = dist/(dist+pz)
            pts.append((px*f, (y-h/2)*f+h/2))
        import cards
        page = np.asarray(a, np.float32)*(.55+.45*math.cos(ang))
        img = Image.fromarray(page.clip(0, 255).astype(np.uint8)).convert('RGBA')
        coeffs = cards._coeffs([(0, 0), (w, 0), (w, h), (0, h)], pts)
        warped = img.transform((w, h), Image.Transform.PERSPECTIVE, tuple(coeffs), Image.Resampling.BILINEAR)
        canvas.paste(warped, (0, 0), warped)
    return canvas


def special_for(previous, following):
    """The collection transition that suits two screens of a sequence (by name)."""
    if following == 'Figurina MVP':
        return 'carta' if previous in ('Full Time', 'Pagelle') else 'strappo'
    if following == 'Album' or previous == 'Album':
        return 'pagina'
    if following == 'Pagelle':
        return 'olografica'
    if previous == 'Figurina MVP':
        return 'pioggia'
    return 'olografica'


FUNCTIONS = {'channel': _channel, 'poweroff': _poweroff, 'glitch': _glitch,
             'rewind': _rewind, 'roll': _roll, 'cut': _cut, 'pixel': _pixel, 'iris': _iris,
             'blocks': _blocks, 'wipe': _wipe, 'carta': _carta, 'strappo': _strappo, 'olografica': _olografica,
             'pioggia': _pioggia, 'pagina': _pagina}


def varied(count, start=0):
    """count transitions, all different in a row: for carousels and Wrapped."""
    return [VARIED[(start+i) % len(VARIED)] for i in range(count)]


def transition_frame(kind, a, b, p, channel=2):
    """Blend frame a into frame b; p runs from 0 (all a) to 1 (all b)."""
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.LANCZOS)
    a, b = a.convert('RGB'), b.convert('RGB')
    p = max(0.0, min(1.0, float(p)))
    return FUNCTIONS.get(kind, _channel)(a, b, p, channel)


def intro_length(prepared, compose):
    """Seconds the scene's own entrance animation needs before everything is on screen."""
    import animations
    rich = animations.intro_length(prepared) if animations.rich(prepared) else None
    if rich:
        return rich
    if getattr(compose, '__module__', '') == 'matchday_renderer':
        return 4.3
    return .6+.12*max(1, len(prepared[1]))


def render_sequence(scenes, transitions, path, fps=24, hold=4.0, transition_seconds=1.0,
                    format='Story 9:16', scale=2, progress_callback=None, sound=False, volume=.8, mockup=False):
    """scenes: list of (prepared, compose_function). One transition between each pair.
    With sound=True a synthesised CRT soundtrack is muxed into the MP4.
    With mockup=True everything plays on a tube TV whose knob turns at each change."""
    from crt_presets import output_image, even_video_frame
    from renderer import video_writer, video_settings
    if not scenes:
        raise ValueError('Scegli almeno una grafica per la sequenza.')
    fps, _ = video_settings(fps, 8, scale)
    hold_frames = max(1, round(hold*fps))
    trans_frames = max(2, round(transition_seconds*fps))
    total = hold_frames*len(scenes)+trans_frames*(len(scenes)-1)
    writer = video_writer(path, fps)
    done = 0

    # Each entrance is sped up when needed so it completes in 65% of the hold:
    # the transition always starts from a finished graphic.
    for prepared, _ in scenes[1:]:
        prepared[0].info['power_on'] = False  # only the first scene switches the set on
        prepared[0].info['intro'] = False
    for prepared, _ in scenes:
        prepared[0].info['ending'] = 'nessuno'
        prepared[0].info.pop('duration', None)
        prepared[0].info['format'] = format     # frames and textures follow the sequence's format
        prepared[0].info['mockup'] = mockup
    music = any(p[0].info.get('music') for p, _ in scenes)
    track = next((p[0].info.get('music_track') for p, _ in scenes if p[0].info.get('music')), 'arcade')
    for prepared, _ in scenes:
        prepared[0].info['music'] = False  # one soundtrack for the whole sequence, below
    speeds = [max(1.0, intro_length(p, c)/(hold*.65)) for p, c in scenes]
    import tracks
    beat = tracks.beat(track) if music else None
    for index, (prepared, _) in enumerate(scenes):   # pulses follow the one soundtrack, in each scene's own clock
        start = index*(hold_frames+trans_frames)/fps
        prepared[0].info['beat'] = (beat[0]*speeds[index], (beat[1]-start)*speeds[index]) if beat else None
        prepared[0].info.update(hold=hold, seq_start=start, seq_beat=beat[0] if beat else .5)
        if music:
            prepared[0].info['music_track'] = track

    def frame_at(index, t, animated=True):
        prepared, compose = scenes[index]
        image = compose(prepared, t*speeds[index], animated)
        return image if mockup else output_image(image, format, scale)

    def emit(image):
        nonlocal done
        if mockup:
            import mockup as tv
            from crt_common import sponsor_sticker
            image = tv.frame(image, format, scale, knob[0], sponsor_sticker(scenes[0][0], scale))
        writer.append_data(np.asarray(even_video_frame(image)))
        done += 1
        if progress_callback and (done % fps == 0 or done == total):
            progress_callback(done/total)

    events = []
    knob = [0.0]
    try:
        for index in range(len(scenes)):
            last = None
            own = scenes[index][0][0].info.get('sequence_events')
            if sound and own:   # the figurine screens bring their own effects (tear, reveal, MVP)
                events += [(done/fps+at, s) for at, s in own(hold)]
            elif sound:   # CRT effects; the music is added once, below
                from sounds import scene_events
                events += scene_events(*scenes[index], start=done/fps, speed=speeds[index], until=done/fps+hold)
            for i in range(hold_frames):
                last = frame_at(index, i/fps)
                emit(last)
            if index < len(scenes)-1:
                kind = transitions[index] if index < len(transitions) else 'channel'
                nxt = frame_at(index+1, 0)
                if sound:
                    from sounds import TRANSITION_SOUNDS
                    events.append((done/fps, TRANSITION_SOUNDS.get(kind, TRANSITION_SOUNDS['channel'])(trans_frames/fps)))
                for i in range(trans_frames):
                    p = (i+1)/(trans_frames+1)
                    knob[0] = 30.0*(index+_ease(min(1, p*1.6)))
                    emit(transition_frame(kind, last, nxt, p, index+2))
    finally:
        writer.close()
    if sound or music:   # the chiptune plays even with the CRT effects off
        from sounds import mix, mux, chiptune
        if music:
            events.append((0.0, chiptune(total/fps, len(scenes), track=track or 'arcade')*.9))
        mux(path, mix(events, total/fps, volume, ambient=sound))
    return str(path)


def preview_strip(a, b, kind, steps=6, width=180):
    """A small storyboard of the transition, for the editor."""
    height = round(a.height*width/a.width)
    small_a = a.resize((width, height), Image.Resampling.LANCZOS)
    small_b = b.resize((width, height), Image.Resampling.LANCZOS)
    sheet = Image.new('RGB', (width*steps+4*(steps-1), height), (16, 13, 22))
    for i in range(steps):
        frame = transition_frame(kind, small_a, small_b, i/(steps-1))
        sheet.paste(frame, (i*(width+4), 0))
    return sheet
