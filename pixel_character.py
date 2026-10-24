"""Stylised pixel characters for the squad: a few traits, drawn in two styles.

A "look" is a small dict - hair style, beard, glasses, brows and three
colours - so every player gets the same graphic language whatever the photo.
A photo is optional: it only suggests the colours.

Styles: 'arcade' (32x32, Flamingos pink shirt, cyan/pink rim light, for every
preset) and 'gameboy' (the same drawing in four greens, for the Pocket preset).
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
from PIL import Image

SIZE = 32
HAIR_STYLES = {'ciuffo': 'Ciuffo alzato', 'corti': 'Corti', 'rasati': 'Rasati', 'lunghi': 'Lunghi',
               'ricci': 'Ricci', 'pelato': 'Pelato'}
BEARDS = {'nessuna': 'Nessuna', 'corta': 'Corta / incolta', 'piena': 'Piena', 'pizzetto': 'Pizzetto', 'baffi': 'Baffi'}
GLASSES = {'nessuno': 'Nessuno', 'vista': 'Da vista', 'sole': 'Da sole'}
BROWS = {'folte': 'Folte', 'sottili': 'Sottili'}
DEFAULT_LOOK = dict(hair='corti', beard='nessuna', glasses='nessuno', brows='folte',
                    skin='#E6B098', hair_color='#30221E', beard_color='#966C60')
SKIN_TONES = ('#F3D0B8', '#E6B098', '#D49A78', '#B67A58', '#8D5A3E', '#5E3A28')
GAMEBOY = np.array([(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)])
PINK = (242, 104, 168)

(EMPTY, SKIN, SHADE, EAR, HAIR, HAIRL, BUZZ, BROW, EYE, WHITE, STUBBLE, BEARD, MOUTH, NOSE,
 SHIRT, SHIRTD, COLLAR, FRAME, LENS, LENSL, SHINE) = range(21)


def sanitize(raw):
    """A clean look, or None."""
    if not isinstance(raw, dict):
        return None
    look = dict(DEFAULT_LOOK)
    for key, options in (('hair', HAIR_STYLES), ('beard', BEARDS), ('glasses', GLASSES), ('brows', BROWS)):
        if raw.get(key) in options:
            look[key] = raw[key]
    for key in ('skin', 'hair_color', 'beard_color'):
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            look[key] = value.upper()
    return look


def _rgb(value):
    return np.array(list(bytes.fromhex(value.lstrip('#'))), np.float32)


def build(look):
    """The character as a grid of part codes."""
    n, top, cx, hw = SIZE, 8, 16, 7
    g = np.zeros((n, n), np.int8)

    def put(y, x1, x2, code):
        x1, x2 = max(0, x1), min(n-1, x2)
        if 0 <= y < n and x1 <= x2:
            g[y, x1:x2+1] = code

    bottom = top+16
    for y in range(top, bottom+1):
        k = bottom-y
        inset = 0 if k > 4 else {4: 0, 3: 1, 2: 1, 1: 2, 0: 4}[k]
        put(y, cx-hw+inset, cx+hw-1-inset, SKIN)
    for y in range(top+4, bottom):
        row = np.nonzero(g[y] == SKIN)[0]
        if len(row):
            g[y, row[-1]] = SHADE
    for y in range(top+5, top+9):
        put(y, cx-hw-1, cx-hw-1, EAR)
        put(y, cx+hw, cx+hw, EAR)
    neck = bottom+1
    for y in range(neck, neck+3):
        put(y, cx-3, cx+2, SHADE if y == neck else SKIN)
    for i, y in enumerate(range(neck+3, n)):
        half = 5+i*3
        put(y, cx-half, cx+half-1, SHIRT)
        put(y, cx-half, cx-half, SHIRTD)
        put(y, cx+half-1, cx+half-1, SHIRTD)
    for i in range(3):
        put(neck+3+i, cx-3+i, cx+2-i, COLLAR)

    ey = top+7
    lx, rx = cx-hw+3, cx+1+(hw-4)
    put(ey, lx, lx+1, EYE)
    put(ey, rx, rx+1, EYE)
    g[ey, lx] = WHITE
    g[ey, rx+1] = WHITE
    by = ey-2
    if look['brows'] == 'folte':
        put(by, lx-1, lx+2, BROW); put(by, rx-1, rx+2, BROW)
        put(by-1, lx, lx+2, BROW); put(by-1, rx-1, rx+1, BROW)
    else:
        put(by, lx, lx+1, BROW); put(by, rx, rx+1, BROW)
    put(ey+2, cx-1, cx-1, NOSE)
    put(ey+3, cx-1, cx, NOSE)
    my = ey+6
    put(my, cx-2, cx+1, MOUTH)

    beard = look['beard']
    if beard in ('corta', 'piena'):
        code = STUBBLE if beard == 'corta' else BEARD
        for y in range(my-1, bottom+1):
            row = np.nonzero(np.isin(g[y], (SKIN, SHADE)))[0]
            if y == my-1:
                put(y, cx-3, cx+2, code)
            else:
                for x in row:
                    if y > my or x < cx-2 or x > cx+1:
                        g[y, x] = code
        for y in range(ey+1, my):
            g[y, cx-hw] = code
            g[y, cx+hw-1] = code
    elif beard in ('pizzetto', 'baffi'):
        put(my-1, cx-3, cx+2, BEARD)
        if beard == 'pizzetto':
            put(my, cx-3, cx-3, BEARD); put(my, cx+2, cx+2, BEARD)
            for y in range(my+1, bottom+1):
                put(y, cx-2, cx+1, BEARD)

    glasses = look['glasses']
    if glasses == 'vista':
        for x0 in (lx-1, rx-1):
            put(ey-1, x0, x0+3, FRAME)
            g[ey, x0] = FRAME; g[ey, x0+3] = FRAME
            put(ey+1, x0+1, x0+2, FRAME)
        put(ey-1, lx+3, rx-2, FRAME)
    elif glasses == 'sole':
        for x0 in (lx-1, rx-1):
            for y in (ey-1, ey, ey+1):
                put(y, x0, x0+3, LENS)
            g[ey-1, x0+1] = LENSL
        put(ey-1, lx+3, rx-2, FRAME)

    hair = look['hair']
    if hair == 'ciuffo':
        for y, x1, x2 in ((top-4, cx-2, cx+4), (top-3, cx-5, cx+6), (top-2, cx-hw+1, cx+hw-1), (top-1, cx-hw, cx+hw-1),
                          (top, cx-hw, cx+hw-1), (top+1, cx-hw, cx-hw+1), (top+1, cx+hw-2, cx+hw-1),
                          (top+2, cx-hw, cx-hw), (top+2, cx+hw-1, cx+hw-1)):
            put(y, x1, x2, HAIR)
        put(top-4, cx+1, cx+3, HAIRL); put(top-3, cx+2, cx+5, HAIRL); put(top-2, cx+4, cx+5, HAIRL)
        put(top-3, cx-3, cx-2, HAIRL)
        for y in range(top+3, top+6):
            for x in (cx-hw, cx+hw-1):
                if g[y, x] in (SKIN, SHADE):
                    g[y, x] = HAIRL
    elif hair == 'corti':
        for y, x1, x2 in ((top-2, cx-hw+2, cx+hw-3), (top-1, cx-hw, cx+hw-1), (top, cx-hw, cx+hw-1),
                          (top+1, cx-hw, cx-hw+1), (top+1, cx+hw-2, cx+hw-1)):
            put(y, x1, x2, HAIR)
        for y in range(top+2, top+5):
            g[y, cx-hw] = HAIR
            g[y, cx+hw-1] = HAIR
        put(top-2, cx-1, cx+2, HAIRL)
    elif hair == 'rasati':
        put(top-2, cx-hw+2, cx+hw-3, BUZZ)
        for y in range(top-1, top+1):
            put(y, cx-hw, cx+hw-1, BUZZ)
        for y in range(top+1, top+4):
            g[y, cx-hw] = BUZZ
            g[y, cx+hw-1] = BUZZ
    elif hair == 'lunghi':
        for y, x1, x2 in ((top-3, cx-hw+2, cx+hw-3), (top-2, cx-hw, cx+hw-1), (top-1, cx-hw-1, cx+hw),
                          (top, cx-hw-1, cx+hw), (top+1, cx-hw-1, cx-hw+2), (top+1, cx+hw-3, cx+hw)):
            put(y, x1, x2, HAIR)
        for y in range(top+2, bottom-2):
            put(y, cx-hw-2, cx-hw, HAIR)
            put(y, cx+hw-1, cx+hw+1, HAIR)
        put(top-3, cx-2, cx+1, HAIRL)
        put(top-2, cx-4, cx-3, HAIRL)
    elif hair == 'ricci':
        for x in range(cx-hw, cx+hw, 4):
            put(top-4, x+1, x+2, HAIR)
        for y, x1, x2 in ((top-3, cx-hw, cx+hw-1), (top-2, cx-hw-1, cx+hw), (top-1, cx-hw-1, cx+hw),
                          (top, cx-hw-1, cx+hw), (top+1, cx-hw-1, cx-hw+1), (top+1, cx+hw-2, cx+hw)):
            put(y, x1, x2, HAIR)
        for y in range(top+2, top+5):
            put(y, cx-hw-1, cx-hw, HAIR)
            put(y, cx+hw-1, cx+hw, HAIR)
        yy, xx = np.mgrid[0:n, 0:n]
        curls = (g == HAIR) & ((xx+2*yy) % 4 == 0) & (yy < top+1)
        g[curls] = HAIRL
    elif hair == 'pelato':
        put(top-2, cx-hw+3, cx+hw-4, SKIN)
        put(top-1, cx-hw+1, cx+hw-2, SKIN)
        put(top-1, cx-hw+3, cx-hw+4, SHINE)
        for y in range(top+3, top+6):
            g[y, cx-hw] = BUZZ
            g[y, cx+hw-1] = BUZZ
    return g


def _palette(look):
    skin, hair, beard = _rgb(look['skin']), _rgb(look['hair_color']), _rgb(look['beard_color'])
    pink = np.array(PINK, np.float32)
    return {SKIN: skin, SHADE: skin*.82, EAR: skin*.88, HAIR: hair, HAIRL: np.minimum(255, hair*1.5+34),
            BUZZ: hair*.55+skin*.45, BROW: hair*.9, EYE: (34, 24, 30), WHITE: (250, 248, 244),
            STUBBLE: beard, BEARD: beard*.9, MOUTH: skin*.62+np.array((40, 0, 0)), NOSE: skin*.78,
            SHIRT: pink, SHIRTD: pink*.68, COLLAR: (30, 20, 34), FRAME: (96, 84, 110), LENS: (22, 18, 34),
            LENSL: (150, 210, 240), SHINE: np.minimum(255, skin*1.12+20)}


def _outline(rgba, color=(28, 18, 34)):
    subject = rgba[..., 3] > 0
    grown = subject.copy()
    grown[1:] |= subject[:-1]; grown[:-1] |= subject[1:]
    grown[:, 1:] |= subject[:, :-1]; grown[:, :-1] |= subject[:, 1:]
    rgba[grown & ~subject] = (*color, 255)
    return rgba


def _paint(look):
    g = build(look)
    pal = _palette(look)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    for code, col in pal.items():
        rgba[g == code] = (*np.clip(col, 0, 255).astype(int), 255)
    # Stubble: sparse on the cheeks, fuller on chin and moustache.
    rows = np.nonzero((g == STUBBLE).any(axis=1))[0]
    if len(rows):
        yy, xx = np.mgrid[0:SIZE, 0:SIZE]
        sparse = (g == STUBBLE) & (yy < rows.max()-1) & ((yy+xx) % 2 == 0)
        rgba[sparse] = (*np.clip(pal[SKIN]*.9, 0, 255).astype(int), 255)
    return g, _outline(rgba)


def _rim(rgba, g, left=(80, 230, 255), right=(255, 92, 190)):
    body = np.isin(g, (SKIN, SHADE, EAR, HAIR, HAIRL, BUZZ, STUBBLE, BEARD, SHINE))
    for y in range(SIZE):
        xs = np.nonzero(body[y])[0]
        if len(xs):
            rgba[y, xs[0], :3] = (rgba[y, xs[0], :3]*.55+np.array(left)*.45).astype(np.uint8)
            rgba[y, xs[-1], :3] = (rgba[y, xs[-1], :3]*.55+np.array(right)*.45).astype(np.uint8)
    return rgba


GB_TONES = {SKIN: 3, SHINE: 3, WHITE: 3, LENSL: 3, SHADE: 2, EAR: 2, NOSE: 2, SHIRT: 2, BUZZ: 1, STUBBLE: 1,
            BEARD: 1, HAIRL: 1, MOUTH: 1, SHIRTD: 1, FRAME: 1, HAIR: 0, BROW: 0, EYE: 0, COLLAR: 0, LENS: 0}


def _gameboy(rgba, g):
    """Four greens by part, like a real handheld sprite: features never vanish."""
    out = rgba.copy()
    for code, tone in GB_TONES.items():
        out[g == code, :3] = GAMEBOY[tone]
    stubble = (g == STUBBLE) & (rgba[..., :3].sum(axis=2) > 0)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    rows = np.nonzero((g == STUBBLE).any(axis=1))[0]
    if len(rows):
        out[stubble & (yy < rows.max()-1) & ((yy+xx) % 2 == 0), :3] = GAMEBOY[3]
    edge = (rgba[..., 3] > 0) & (g == EMPTY)      # the outline
    out[edge, :3] = GAMEBOY[0]
    return out


@lru_cache(maxsize=256)
def _image(items, style, blink=False):
    look = dict(items)
    g, rgba = _paint(look)
    if blink:  # closed eyes: a darker lid line, no highlight
        lid = np.clip(_rgb(look['skin'])*.55, 0, 255).astype(np.uint8)
        rgba[np.isin(g, (EYE, WHITE))] = (*lid, 255)
    rgba = _gameboy(rgba, g) if style == 'gameboy' else _rim(rgba, g)
    return Image.fromarray(rgba, 'RGBA')


def image(look, style='arcade', blink=False):
    """The character as a 32x32 RGBA image (blink=True: eyes closed)."""
    look = sanitize(look) or dict(DEFAULT_LOOK)
    if look['glasses'] == 'sole':
        blink = False
    return _image(tuple(sorted(look.items())), 'gameboy' if style == 'gameboy' else 'arcade', bool(blink)).copy()


def style_for(preset_id):
    return 'gameboy' if preset_id == 'gameboy' else 'arcade'


# --- Colours from a photo ----------------------------------------------------

def _hex(color):
    return '#%02X%02X%02X' % tuple(int(max(0, min(255, c))) for c in color)


def colors_from_photo(photo):
    """{'skin','hair_color','beard_color'} suggested by a photo, or {} if no face is found."""
    from avatars import find_face, _skin
    face = find_face(photo)
    if not face:
        return {}
    cx, cy, h = face
    w = h*.78
    arr = np.asarray(photo, np.float32)
    H, W = arr.shape[:2]

    def region(x1, y1, x2, y2):
        x1, x2 = int(max(0, x1)), int(min(W, x2))
        y1, y2 = int(max(0, y1)), int(min(H, y2))
        return arr[y1:y2, x1:x2].reshape(-1, 3) if x2 > x1 and y2 > y1 else np.zeros((0, 3), np.float32)

    face_px = region(cx-w*.35, cy-h*.3, cx+w*.35, cy+h*.3)
    skin_px = face_px[_skin(face_px[None])[0]] if len(face_px) else face_px
    if len(skin_px) < 20:
        return {}
    skin = np.median(skin_px, axis=0)
    lum = lambda p: p @ np.array([.299, .587, .114], np.float32)
    # Lift dim photos so the character is not grey.
    skin = skin*min(1.35, max(1.0, 200/max(1.0, float(lum(skin)))))
    # Halfway to the nearest standard tone: photos are often too red or too grey.
    tones = np.array([_rgb(t) for t in SKIN_TONES])
    skin = skin*.5+tones[int(np.argmin(((tones-skin)**2).sum(axis=1)))]*.5
    above = region(cx-w*.5, cy-h*1.05, cx+w*.5, cy-h*.45)
    dark = above[lum(above) < lum(skin)*.55] if len(above) else above
    hair = np.median(dark, axis=0) if len(dark) > 30 else np.array((48, 34, 30), np.float32)
    jaw = region(cx-w*.25, cy+h*.35, cx+w*.25, cy+h*.6)
    beard = np.median(jaw, axis=0) if len(jaw) else skin*.7
    if lum(beard) > lum(skin)*.85:     # no visible beard: a darker skin tone for stubble
        beard = skin*.62+hair*.38
    return dict(skin=_hex(skin), hair_color=_hex(hair), beard_color=_hex(beard))


def gameboy_image(img):
    """Any RGBA sprite (e.g. the placeholder) in the four greens, by brightness."""
    arr = np.asarray(img.convert('RGBA')).copy()
    lum = arr[..., :3].astype(np.float32) @ np.array([.299, .587, .114], np.float32)
    arr[..., :3] = GAMEBOY[np.clip((lum/64).astype(int), 0, 3)]
    return Image.fromarray(arr, 'RGBA')


def picture(member, preset_id='crt', blink=False):
    """The sprite for a squad member: their look, an older photo avatar, or a silhouette."""
    import avatars
    style = style_for(preset_id)
    if member.get('look'):
        return image(member['look'], style, blink)
    picture = avatars.decode(member.get('avatar')) or avatars.placeholder(size=SIZE)
    return gameboy_image(picture) if style == 'gameboy' else picture
