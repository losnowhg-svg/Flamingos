"""Title effects: the main title of every template, styled one of eight ways.

Works on the rendered text image (RGBA, glyphs on transparent) and keeps the
text centred: every effect pads the image evenly, so the layer positions of
the editors stay valid. 'ombra' is the classic look of the previous versions.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops, ImageFilter

EFFECTS = {'ombra': 'Ombra (classica)', 'contorno': 'Contorno spesso', 'ombra_lunga': 'Ombra lunga',
           '3d': 'Rilievo 3D', 'gradiente': 'Sfumato tramonto', 'neon': 'Neon', 'cromato': 'Cromato',
           'glitch': 'Glitch RGB', 'rotazione': 'A rotazione (cambia ogni giornata)'}
CYCLE = ('ombra', 'contorno', 'neon', 'ombra_lunga', 'gradiente', '3d', 'glitch', 'cromato')
INK = (12, 10, 24)


def resolve(config):
    mode = config.get('title_fx', 'ombra')
    if mode == 'rotazione':
        try:
            n = max(1, int(config.get('season_round', 1) or 1))
        except (TypeError, ValueError):
            n = 1
        return CYCLE[(n-1) % len(CYCLE)]
    return mode if mode in EFFECTS else 'ombra'


def _hex(value, fallback):
    try:
        out = tuple(bytes.fromhex(str(value).lstrip('#')))
        return out if len(out) == 3 else fallback
    except (ValueError, TypeError):
        return fallback


def _pad(asset, p):
    out = Image.new('RGBA', (asset.width+2*p, asset.height+2*p))
    out.alpha_composite(asset, (p, p))
    return out


def _solid(mask, color, alpha=1.0):
    out = Image.new('RGBA', mask.size, (*color, 0))
    out.putalpha(mask if alpha >= 1 else mask.point(lambda v: round(v*alpha)))
    return out


def _dilate(mask, r):
    return mask.filter(ImageFilter.MaxFilter(2*r+1)) if r > 0 else mask


def _boost(mask, k):
    return mask.point(lambda v: min(255, round(v*k)))


def _gradient_fill(mask, stops):
    """Colour the glyphs with a vertical gradient over the text's own height."""
    box = mask.getbbox()
    w, h = mask.size
    if not box:
        return _solid(mask, stops[0][1])
    y = np.clip((np.arange(h, dtype=np.float32)-box[1])/max(1, box[3]-box[1]-1), 0, 1)
    col = np.zeros((h, 3), np.float32)
    for (p1, c1), (p2, c2) in zip(stops, stops[1:]):
        k = np.clip((y-p1)/max(1e-6, p2-p1), 0, 1)[:, None]
        inside = ((y >= p1) & (y <= p2))[:, None]
        col = np.where(inside, np.array(c1, np.float32)+(np.array(c2, np.float32)-np.array(c1, np.float32))*k, col)
    rgb = np.repeat(col[:, None, :], w, axis=1).clip(0, 255).astype(np.uint8)
    out = Image.fromarray(np.concatenate([rgb, np.asarray(mask)[..., None]], axis=2), 'RGBA')
    return out


def _classic(asset, s):
    from matchday_renderer import _decorate_text
    return _decorate_text(asset, s)


def decorate(asset, s, effect, pink=(242, 104, 168), cyan=(121, 220, 247), yellow=(255, 201, 99)):
    if asset is None:
        return None
    if effect not in EFFECTS or effect in ('ombra', 'rotazione'):
        return _classic(asset, s)
    if effect == 'contorno':
        # Sticker outline: a coloured ring, then a dark one, then a soft shadow.
        inner, outer = max(1, round(1.3*s)), max(2, round(2.6*s))
        base = _pad(asset, outer+2*s)
        mask = base.getchannel('A')
        ring = _dilate(mask, outer)
        out = Image.new('RGBA', base.size)
        out.alpha_composite(_solid(ring, INK, .55), (s, s))
        out.alpha_composite(_solid(ring, INK))
        out.alpha_composite(_solid(_dilate(mask, inner), pink))
        out.alpha_composite(base)
        return out
    if effect == 'ombra_lunga':
        length = round(7*s)
        base = _pad(asset, length+s)
        mask = base.getchannel('A')
        shade = tuple(round(c*.42) for c in pink)
        out = Image.new('RGBA', base.size)
        step = _solid(mask, shade)
        for k in range(length, 0, -1):
            out.alpha_composite(step, (k, k))
        out.alpha_composite(_solid(_dilate(mask, max(1, round(.6*s))), INK, .9))
        out.alpha_composite(base)
        return out
    if effect == '3d':
        depth = round(4*s)
        base = _pad(asset, depth+2*s)
        mask = base.getchannel('A')
        union = mask.copy()
        side = tuple(round(c*.5) for c in cyan)
        extrusion = Image.new('RGBA', base.size)
        for k in range(depth, 0, -1):
            moved = Image.new('L', mask.size)
            moved.paste(mask, (k, k))
            union = ImageChops.lighter(union, moved)
            extrusion.alpha_composite(_solid(moved, side))
        out = _solid(_dilate(union, max(1, round(s))), INK)
        out.alpha_composite(extrusion)
        out.alpha_composite(base)
        return out
    if effect == 'gradiente':
        base = _pad(asset, 3*s)
        mask = base.getchannel('A')
        out = Image.new('RGBA', base.size)
        out.alpha_composite(_solid(mask, (4, 9, 19), .8), (2*s, 2*s))
        out.alpha_composite(_gradient_fill(mask, ((0, (255, 248, 196)), (.35, yellow), (1, pink))))
        return out
    if effect == 'neon':
        p = round(10*s)
        base = _pad(asset, p)
        mask = base.getchannel('A')
        out = _solid(_boost(mask, 1.0).filter(ImageFilter.GaussianBlur(6*s)), pink)
        out.putalpha(_boost(out.getchannel('A'), 2.4))
        tight = _solid(mask, pink).filter(ImageFilter.GaussianBlur(1.6*s))
        tight.putalpha(_boost(tight.getchannel('A'), 1.8))
        out.alpha_composite(tight)
        core = tuple(round(255*.78+c*.22) for c in pink)
        out.alpha_composite(_solid(mask, core))
        return out
    if effect == 'cromato':
        base = _pad(asset, 3*s)
        mask = base.getchannel('A')
        out = Image.new('RGBA', base.size)
        out.alpha_composite(_solid(_dilate(mask, max(1, round(s))), INK, .85), (s, s))
        out.alpha_composite(_solid(_dilate(mask, max(1, round(s))), INK))
        out.alpha_composite(_gradient_fill(mask, ((0, (255, 255, 255)), (.44, (176, 196, 226)), (.5, (64, 74, 116)),
                                                  (.58, (226, 214, 255)), (1, (150, 120, 196)))))
        return out
    if effect == 'glitch':
        shift = max(1, round(2*s))
        base = _pad(asset, shift+2*s)
        mask = base.getchannel('A')
        out = Image.new('RGBA', base.size)
        out.alpha_composite(_solid(mask, cyan, .9), (0, 0), (shift, 0))
        out.alpha_composite(_solid(mask, pink, .9), (shift, 0))
        out.alpha_composite(base)
        arr = np.array(out)
        h = arr.shape[0]
        rng = np.random.default_rng(int(np.asarray(mask).sum()) % 9973)
        for _ in range(3):   # a few displaced slices, always the same for the same text
            y = int(rng.integers(0, max(1, h-2)))
            band = max(1, h//9)
            arr[y:y+band] = np.roll(arr[y:y+band], int(rng.choice((-1, 1)))*shift, axis=1)
        return Image.fromarray(arr, 'RGBA')
    return _classic(asset, s)


def title(asset, config, s):
    """The decorated main title for a template, following the config."""
    pink = _hex(config.get('pink'), (242, 104, 168))
    cyan = _hex(config.get('cyan'), (121, 220, 247))
    yellow = _hex(config.get('yellow'), (255, 201, 99))
    return decorate(asset, s, resolve(config), pink, cyan, yellow)
