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
HAIR_STYLES = {'ciuffo': 'Ciuffo alzato', 'corti': 'Corti', 'spettinati': 'Spettinati', 'frangia': 'Frangia',
               'mossi': 'Mossi', 'ricci': 'Ricci', 'ricci_lunghi': 'Ricci lunghi', 'lunghi': 'Lunghi',
               'rasati': 'Rasati', 'stempiato': 'Stempiato', 'pelato': 'Pelato'}
BEARDS = {'nessuna': 'Nessuna', 'corta': 'Corta / incolta', 'piena': 'Piena', 'pizzetto': 'Pizzetto', 'baffi': 'Baffi',
          'baffi_pizzetto': 'Baffi e pizzetto'}
GLASSES = {'nessuno': 'Nessuno', 'vista': 'Da vista', 'spessi': 'Montatura spessa', 'sole': 'Da sole'}
BROWS = {'folte': 'Folte', 'sottili': 'Sottili'}
FACES = {'normale': 'Normale', 'tondo': 'Tondo', 'magro': 'Magro'}
EYES = {'scuri': 'Scuri', 'azzurri': 'Azzurri', 'verdi': 'Verdi'}
ACCESSORIES = {'nessuno': 'Nessuno', 'bucket': 'Cappello da pescatore', 'cappellino': 'Cappellino al contrario',
               'cappuccio': 'Cappuccio', 'fascia': 'Fascia', 'orecchini': 'Orecchini'}
EXPRESSIONS = {'serio': 'Serio', 'sorriso': 'Sorriso'}
FRAMES = ('blink', 'wink', 'smile', 'glint', 'brows')
DEFAULT_LOOK = dict(hair='corti', beard='nessuna', glasses='nessuno', brows='folte',
                    skin='#E6B098', hair_color='#30221E', beard_color='#966C60',
                    face='normale', eyes='scuri', accessory='nessuno', accessory_color='#2F4FC8', expression='serio',
                    earrings=False)
SKIN_TONES = ('#F3D0B8', '#E6B098', '#D49A78', '#B67A58', '#8D5A3E', '#5E3A28')
GAMEBOY = np.array([(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)])
PINK = (242, 104, 168)

(EMPTY, SKIN, SHADE, EAR, HAIR, HAIRL, BUZZ, BROW, EYE, WHITE, STUBBLE, BEARD, MOUTH, NOSE,
 SHIRT, SHIRTD, COLLAR, FRAME, LENS, LENSL, SHINE, LID, FRAMED, ACC, ACCD, ACCL, GOLD,
 BALL, BALLD, GLOVE, GLOVED) = range(31)
POSES = ('ferma', 'esultanza', 'conserte', 'pollice', 'palleggio', 'saluto', 'guanti')
MOVING_POSES = ('esultanza', 'pollice', 'palleggio', 'saluto', 'guanti')   # these have a second frame


def sanitize(raw):
    """A clean look, or None."""
    if not isinstance(raw, dict):
        return None
    look = dict(DEFAULT_LOOK)
    for key, options in (('hair', HAIR_STYLES), ('beard', BEARDS), ('glasses', GLASSES), ('brows', BROWS),
                         ('face', FACES), ('eyes', EYES), ('accessory', ACCESSORIES), ('expression', EXPRESSIONS)):
        if raw.get(key) in options:
            look[key] = raw[key]
    look['earrings'] = raw.get('earrings') is True
    for key in ('skin', 'hair_color', 'beard_color', 'accessory_color'):
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            look[key] = value.upper()
    return look


def _rgb(value):
    return np.array(list(bytes.fromhex(value.lstrip('#'))), np.float32)


def _arm(g, rows, mirror=False):
    """rows: (y, x1, x2, code) for the left arm; mirror draws the right one."""
    n = g.shape[1]
    for y, x1, x2, code in rows:
        if mirror:
            x1, x2 = n-1-x2, n-1-x1
        x1, x2 = max(0, x1), min(n-1, x2)
        if 0 <= y < g.shape[0] and x1 <= x2:
            g[y, x1:x2+1] = code


def _pose(g, pose, beat=0):
    """Arms, hands and props for a pose; beat 1 is the second animation frame."""
    if pose == 'esultanza':
        lift = 0 if beat == 0 else 2          # fists pumping
        arm = [(31, 3, 6, SHIRT), (30, 3, 6, SHIRT), (29, 2, 5, SHIRT), (28, 2, 4, SHIRT), (27, 2, 4, SHIRTD)]
        arm += [(y, 1, 3, SKIN) for y in range(19+lift, 27)]
        arm += [(y, 0, 4, SKIN) for y in range(15+lift, 19+lift)]+[(15+lift, 0, 4, SHADE), (18+lift, 4, 4, SHADE)]
        _arm(g, arm); _arm(g, arm, True)
    elif pose == 'conserte':
        _arm(g, [(y, 3, 6, SHIRTD) for y in range(27, 32)]); _arm(g, [(y, 3, 6, SHIRTD) for y in range(27, 32)], True)
        g[28, 7:25] = SHIRTD
        g[29, 6:26] = SKIN
        g[30, 6:26] = SHADE
        g[29, 6:8] = SHADE; g[29, 24:26] = SHADE
    elif pose == 'pollice':
        arm = [(31, 3, 7, SHIRT), (30, 2, 6, SHIRT), (29, 2, 5, SHIRT), (28, 2, 5, SHIRTD)]
        arm += [(y, 2, 4, SKIN) for y in range(23, 28)]
        # A sideways fist (curled fingers on the outer side) with the thumb up along the inner edge.
        arm += [(y, 0, 5, SKIN) for y in range(18, 23)]
        arm += [(19, 0, 2, SHADE), (21, 0, 2, SHADE), (22, 0, 5, SHADE)]
        arm += [(y, 4, 6, SKIN) for y in range(14, 18)]+[(14, 4, 6, SHINE), (17, 4, 4, SHADE)]
        _arm(g, arm, True)
        if beat:
            g[12, 29] = LENSL; g[11, 30] = LENSL; g[13, 28] = LENSL   # a sparkle by the thumb
    elif pose == 'palleggio':
        y0 = 19 if beat == 0 else 11
        for y, x1, x2 in ((0, 2, 4), (1, 1, 5), (2, 1, 5), (3, 1, 5), (4, 1, 5), (5, 2, 4)):
            g[y0+y, x1:x2+1] = BALL
        g[y0+2, 3] = BALLD; g[y0+3, 2] = BALLD; g[y0+3, 4] = BALLD; g[y0+1, 1] = BALLD; g[y0+4, 5] = BALLD
        if beat == 0:   # the knee/foot that kicks it, as a shirt-coloured block under the ball
            _arm(g, [(29, 1, 5, SHIRTD), (30, 1, 5, SHIRT), (31, 1, 5, SHIRT)])
    elif pose == 'saluto':
        tilt = 0 if beat == 0 else 1
        arm = [(31, 3, 7, SHIRT), (30, 2, 6, SHIRT), (29, 2, 5, SHIRT), (28, 2, 5, SHIRTD)]
        arm += [(y, 2, 4, SKIN) for y in range(21, 28)]
        arm += [(y, 1-tilt, 5-tilt, SKIN) for y in range(16, 21)]+[(20, 1, 5, SHADE)]
        arm += [(15, 1-tilt, 1-tilt, SKIN), (15, 3-tilt, 3-tilt, SKIN), (15, 5-tilt, 5-tilt, SKIN),
                (14, 1-tilt, 1-tilt, SKIN), (14, 3-tilt, 3-tilt, SKIN), (14, 5-tilt, 5-tilt, SKIN)]
        _arm(g, arm)
    elif pose == 'guanti':
        k = 0 if beat == 0 else 1             # gloves come together a little
        arm = [(31, 3, 6, SHIRT), (30, 2, 5, SHIRT), (29, 2, 4, SHIRT), (28, 2, 4, SHIRT)]
        arm += [(y, 2, 4, SHIRTD) for y in range(21, 28)]
        arm += [(y, 0+k, 5+k, GLOVE) for y in range(15, 21)]+[(20, 0+k, 5+k, GLOVED), (15, 0+k, 0+k, GLOVED),
                                                            (17, 2+k, 4+k, GLOVED)]
        _arm(g, arm); _arm(g, arm, True)
    return g


def build(look, frame=None, pose=None, beat=0):
    """The character as a grid of part codes. frame: an idle animation frame (blink, wink, smile, glint, brows);
    pose: arms and props (POSES); beat: 0 or 1, the pose's two animation frames."""
    look = dict(DEFAULT_LOOK, **look)
    face = look['face']
    n, top, cx = SIZE, 8, 16
    hw = {'tondo': 8, 'magro': 6}.get(face, 7)
    jaw = {'tondo': {4: 0, 3: 0, 2: 1, 1: 1, 0: 3}, 'magro': {4: 1, 3: 1, 2: 2, 1: 3, 0: 4}}.get(
        face, {4: 0, 3: 1, 2: 1, 1: 2, 0: 4})
    g = np.zeros((n, n), np.int8)

    def put(y, x1, x2, code):
        x1, x2 = max(0, x1), min(n-1, x2)
        if 0 <= y < n and x1 <= x2:
            g[y, x1:x2+1] = code

    bottom = top+16
    for y in range(top, bottom+1):
        k = bottom-y
        inset = 0 if k > 4 else jaw[k]
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
    if frame == 'blink':
        put(ey, lx, lx+1, LID); put(ey, rx, rx+1, LID)
    elif frame == 'wink':
        put(ey, rx, rx+1, LID)
    by = ey-2-(1 if frame == 'brows' else 0)
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
    elif beard in ('pizzetto', 'baffi', 'baffi_pizzetto'):
        put(my-1, cx-3, cx+2, BEARD)
        if beard == 'baffi_pizzetto':
            put(my, cx-3, cx-3, BEARD); put(my, cx+2, cx+2, BEARD)
            put(my+1, cx-3, cx+2, BEARD)
            for y in range(my+2, bottom+1):
                put(y, cx-2, cx+1, BEARD)
        if beard == 'pizzetto':
            put(my, cx-3, cx-3, BEARD); put(my, cx+2, cx+2, BEARD)
            for y in range(my+1, bottom+1):
                put(y, cx-2, cx+1, BEARD)

    if look['expression'] == 'sorriso' or frame == 'smile':
        put(my, cx-2, cx+1, MOUTH)
        g[my-1, cx-3] = MOUTH
        g[my-1, cx+2] = MOUTH
        if frame == 'smile':
            put(my, cx-1, cx, WHITE)   # a toothy grin for a moment

    glasses = look['glasses']
    if glasses == 'spessi':
        for x0 in (lx-1, rx-1):
            put(ey-1, x0, x0+3, FRAMED)
            put(ey+1, x0, x0+3, FRAMED)
            g[ey, x0] = FRAMED; g[ey, x0+3] = FRAMED
        put(ey-1, lx+3, rx-2, FRAMED)
        g[ey, lx-2] = FRAMED; g[ey, rx+3] = FRAMED
    elif glasses == 'vista':
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
    elif hair == 'spettinati':
        for y, x1, x2 in ((top-2, cx-hw+1, cx+hw-2), (top-1, cx-hw, cx+hw-1), (top, cx-hw, cx+hw-1),
                          (top+1, cx-hw, cx-hw+2), (top+1, cx+hw-3, cx+hw-1), (top+1, cx-1, cx+1)):
            put(y, x1, x2, HAIR)
        for i, x in enumerate(range(cx-hw+1, cx+hw-1, 2)):   # tufts sticking out
            h = (2, 3, 1, 3, 2, 4, 1)[i % 7]
            for y in range(top-2-h, top-2):
                g[y, x] = HAIR
        for y in range(top+2, top+5):
            g[y, cx-hw] = HAIR
            g[y, cx+hw-1] = HAIR
        put(top-3, cx-2, cx, HAIRL)
    elif hair == 'frangia':
        for y, x1, x2 in ((top-3, cx-hw+2, cx+hw-3), (top-2, cx-hw, cx+hw-1), (top-1, cx-hw-1, cx+hw),
                          (top, cx-hw-1, cx+hw), (top+1, cx-hw-1, cx+hw), (top+2, cx-hw-1, cx+hw-2)):
            put(y, x1, x2, HAIR)
        for x in range(cx-hw, cx+hw-2, 3):        # uneven fringe edge
            g[top+3, x] = HAIR
            g[top+3, x+1] = HAIR
        for y in range(top+3, top+7):
            put(y, cx-hw-1, cx-hw, HAIR)
            put(y, cx+hw-1, cx+hw, HAIR)
        put(top-2, cx-3, cx+1, HAIRL)
    elif hair == 'mossi':
        for y, x1, x2 in ((top-4, cx-3, cx+3), (top-3, cx-hw+1, cx+hw-1), (top-2, cx-hw, cx+hw), (top-1, cx-hw-1, cx+hw),
                          (top, cx-hw-1, cx+hw), (top+1, cx-hw-1, cx-hw+2), (top+1, cx+hw-3, cx+hw)):
            put(y, x1, x2, HAIR)
        for y in range(top+2, top+8):
            put(y, cx-hw-1, cx-hw, HAIR)
            put(y, cx+hw-1, cx+hw, HAIR)
        for k, (y, x) in enumerate(((top-3, cx-4), (top-3, cx+2), (top-2, cx-1), (top-1, cx+4), (top-1, cx-5))):
            put(y, x, x+1, HAIRL)
    elif hair == 'ricci_lunghi':
        for x in range(cx-hw-1, cx+hw+1, 3):
            put(top-4, x, x+1, HAIR)
        for y, x1, x2 in ((top-3, cx-hw-1, cx+hw), (top-2, cx-hw-2, cx+hw+1), (top-1, cx-hw-2, cx+hw+1),
                          (top, cx-hw-2, cx+hw+1), (top+1, cx-hw-2, cx-hw+1), (top+1, cx+hw-2, cx+hw+1)):
            put(y, x1, x2, HAIR)
        for y in range(top+2, top+11):
            put(y, cx-hw-2, cx-hw, HAIR)
            put(y, cx+hw-1, cx+hw+1, HAIR)
        yy, xx = np.mgrid[0:n, 0:n]
        curls = (g == HAIR) & ((xx+2*yy) % 4 == 0)
        g[curls] = HAIRL
    elif hair == 'stempiato':
        put(top-1, cx-2, cx+1, BUZZ)               # what is left on top
        put(top-2, cx-3, cx+2, SKIN)
        put(top-1, cx-hw+1, cx-3, SKIN); put(top-1, cx+2, cx+hw-2, SKIN)
        g[top-1, cx-hw+2] = SHINE
        for y in range(top, top+6):
            put(y, cx-hw, cx-hw, HAIR if y > top+1 else BUZZ)
            put(y, cx+hw-1, cx+hw-1, HAIR if y > top+1 else BUZZ)
    elif hair == 'pelato':
        put(top-2, cx-hw+3, cx+hw-4, SKIN)
        put(top-1, cx-hw+1, cx+hw-2, SKIN)
        put(top-1, cx-hw+3, cx-hw+4, SHINE)
        for y in range(top+3, top+6):
            g[y, cx-hw] = BUZZ
            g[y, cx+hw-1] = BUZZ
    if frame == 'glint' and glasses != 'nessuno':
        for k in range(3):
            if g[ey-1+k, lx+k-1] in (LENS, FRAME, FRAMED, EYE, WHITE, SKIN):
                g[ey-1+k, lx+k-1] = LENSL

    acc = look['accessory']
    if acc == 'bucket':
        for y in range(top-5, top):
            put(y, cx-hw+1+(1 if y == top-5 else 0), cx+hw-2-(1 if y == top-5 else 0), ACC)
        put(top-2, cx-hw+1, cx+hw-2, ACCD)
        put(top, cx-hw-2, cx+hw+1, ACC)
        put(top+1, cx-hw-3, cx+hw+2, ACCD)
        put(top-4, cx-2, cx+1, ACCL)
    elif acc == 'cappellino':
        put(top-4, cx-hw+3, cx+hw-4, ACC)
        for y in range(top-3, top+1):
            put(y, cx-hw, cx+hw-1, ACC)
        put(top-3, cx-hw+2, cx-hw+4, ACCL)
        put(top, cx-2, cx+1, ACCD)          # the strap opening of a backwards cap
        put(top-1, cx-1, cx, ACCD)
        put(top+1, cx-hw, cx+hw-1, ACCD)
    elif acc == 'cappuccio':
        for y in range(top-4, bottom+3):
            width = 2 if y > top-2 else 1
            put(y, cx-hw-1-width, cx-hw-1, ACC)
            put(y, cx+hw, cx+hw+width, ACC)
        put(top-4, cx-hw, cx+hw-1, ACC)
        for y in range(top-3, top+1):
            put(y, cx-hw, cx+hw-1, ACC)
        put(top+1, cx-hw, cx+hw-1, ACCL)              # the inner rim of the hood around the face
        for y in range(top+2, bottom+1):
            g[y, cx-hw-1] = ACCL; g[y, cx+hw] = ACCL
        put(top-3, cx-hw+2, cx-hw+4, ACCL)
        for y in range(bottom+1, bottom+5):            # drawstrings
            g[y, cx-2] = WHITE
            g[y, cx+1] = WHITE
    elif acc == 'fascia':
        put(top+1, cx-hw, cx+hw-1, ACC)
        put(top+2, cx-hw, cx+hw-1, ACCD)
    if acc == 'orecchini' or look.get('earrings'):
        if g[top+8, cx-hw-1] in (EAR, EMPTY, SKIN):
            g[top+8, cx-hw-1] = GOLD
        if g[top+8, cx+hw] in (EAR, EMPTY, SKIN):
            g[top+8, cx+hw] = GOLD
    if pose and pose != 'ferma':
        _pose(g, pose, beat)
    return g


def _palette(look):
    look = dict(DEFAULT_LOOK, **look)
    skin, hair, beard = _rgb(look['skin']), _rgb(look['hair_color']), _rgb(look['beard_color'])
    acc = _rgb(look['accessory_color'])
    pink = np.array(PINK, np.float32)
    eye = {'azzurri': (70, 140, 215), 'verdi': (70, 150, 90)}.get(look['eyes'], (34, 24, 30))
    return {SKIN: skin, SHADE: skin*.82, EAR: skin*.88, HAIR: hair, HAIRL: np.minimum(255, hair*1.5+34),
            BUZZ: hair*.55+skin*.45, BROW: hair*.9, EYE: eye, WHITE: (250, 248, 244), LID: skin*.55,
            FRAMED: (20, 18, 24), ACC: acc, ACCD: acc*.62, ACCL: np.minimum(255, acc*1.25+30), GOLD: (255, 214, 90),
            STUBBLE: beard, BEARD: beard*.9, MOUTH: skin*.62+np.array((40, 0, 0)), NOSE: skin*.78,
            SHIRT: pink, SHIRTD: pink*.68, COLLAR: (30, 20, 34), FRAME: (96, 84, 110), LENS: (22, 18, 34),
            LENSL: (150, 210, 240), SHINE: np.minimum(255, skin*1.12+20),
            BALL: (250, 248, 244), BALLD: (30, 24, 36), GLOVE: (196, 240, 72), GLOVED: (110, 150, 40)}


def _outline(rgba, color=(28, 18, 34)):
    subject = rgba[..., 3] > 0
    grown = subject.copy()
    grown[1:] |= subject[:-1]; grown[:-1] |= subject[1:]
    grown[:, 1:] |= subject[:, :-1]; grown[:, :-1] |= subject[:, 1:]
    rgba[grown & ~subject] = (*color, 255)
    return rgba


def _paint(look, frame=None, pose=None, beat=0):
    g = build(look, frame, pose, beat)
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
    body = np.isin(g, (SKIN, SHADE, EAR, HAIR, HAIRL, BUZZ, STUBBLE, BEARD, SHINE, ACC, ACCD, ACCL))
    for y in range(SIZE):
        xs = np.nonzero(body[y])[0]
        if len(xs):
            rgba[y, xs[0], :3] = (rgba[y, xs[0], :3]*.55+np.array(left)*.45).astype(np.uint8)
            rgba[y, xs[-1], :3] = (rgba[y, xs[-1], :3]*.55+np.array(right)*.45).astype(np.uint8)
    return rgba


GB_TONES = {SKIN: 3, SHINE: 3, WHITE: 3, LENSL: 3, SHADE: 2, EAR: 2, NOSE: 2, SHIRT: 2, BUZZ: 1, STUBBLE: 1,
            BEARD: 1, HAIRL: 1, MOUTH: 1, SHIRTD: 1, FRAME: 1, HAIR: 0, BROW: 0, EYE: 0, COLLAR: 0, LENS: 0,
            LID: 1, FRAMED: 0, ACC: 1, ACCD: 0, ACCL: 2, GOLD: 3, BALL: 3, BALLD: 0, GLOVE: 3, GLOVED: 1}


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


@lru_cache(maxsize=1024)
def _image(items, style, frame=None, pose=None, beat=0):
    look = dict(items)
    g, rgba = _paint(look, frame, pose, beat)
    rgba = _gameboy(rgba, g) if style == 'gameboy' else _rim(rgba, g)
    return Image.fromarray(rgba, 'RGBA')


def frames_for(look):
    """The idle frames that make sense for a look (no blinking behind sunglasses...)."""
    look = sanitize(look) or dict(DEFAULT_LOOK)
    out = ['smile', 'brows']
    if look['glasses'] != 'sole':
        out = ['blink', 'wink']+out
    if look['glasses'] != 'nessuno':
        out.append('glint')
    return out


def image(look, style='arcade', blink=False, frame=None, pose=None, beat=0):
    """The character as a 32x32 RGBA image. frame: blink, wink, smile, glint or brows; pose: one of POSES."""
    look = sanitize(look) or dict(DEFAULT_LOOK)
    frame = 'blink' if blink and not frame else frame
    if frame not in frames_for(look):
        frame = None
    pose = pose if pose in POSES and pose != 'ferma' else None
    beat = 1 if beat and pose in MOVING_POSES else 0
    return _image(tuple(sorted(look.items())), 'gameboy' if style == 'gameboy' else 'arcade', frame, pose, beat).copy()


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


def picture(member, preset_id='crt', blink=False, frame=None, pose=None, beat=0):
    """The sprite for a squad member: their look, an older photo avatar, or a silhouette."""
    import avatars
    style = style_for(preset_id)
    if member.get('look'):
        return image(member['look'], style, blink, frame, pose, beat)
    picture = avatars.decode(member.get('avatar')) or avatars.placeholder(size=SIZE)
    return gameboy_image(picture) if style == 'gameboy' else picture


def idle_gif(look, style='arcade', size=256):
    """An animated GIF of the idle loop, for the editor preview."""
    import io
    look = sanitize(look) or dict(DEFAULT_LOOK)
    available = frames_for(look)
    sequence = [None]*6
    for k in available:
        sequence += [k, k, None, None, None, None]
    if 'blink' in available:
        sequence += ['blink', None, None, None]
    bg = (14, 10, 30) if style != 'gameboy' else tuple(GAMEBOY[3])
    frames = []
    for i, frame in enumerate(sequence):
        sprite = image(look, style, frame=frame)
        if frame is None and i % 4 in (2, 3):   # the little bob
            moved = Image.new('RGBA', sprite.size)
            moved.paste(sprite.crop((0, 1, SIZE, SIZE)), (0, 0))
            sprite = moved
        canvas = Image.new('RGB', sprite.size, bg)
        canvas.paste(sprite, (0, 0), sprite)
        frames.append(canvas.resize((size, size), Image.Resampling.NEAREST))
    out = io.BytesIO()
    frames[0].save(out, 'GIF', save_all=True, append_images=frames[1:], duration=120, loop=0, disposal=2)
    return out.getvalue()


# --- Pixel scenes behind the sprites -------------------------------------------

SCENES = ('sfumato', 'stadio', 'notte', 'pioggia', 'neve')


def _vgrad(top, bottom, n=SIZE):
    k = np.linspace(0, 1, n)[:, None, None]
    return np.repeat(np.array(top, np.float32)*(1-k)+np.array(bottom, np.float32)*k, n, axis=1)


@lru_cache(maxsize=16)
def _scene(name, style):
    rng = np.random.default_rng({'stadio': 1, 'notte': 2, 'pioggia': 3, 'neve': 4}.get(name, 0))
    n = SIZE
    if name == 'stadio':
        img = _vgrad((10, 14, 40), (40, 30, 80))
        img[13:20] = (34, 28, 52)                       # the stands
        crowd = rng.random((7, n)) < .45
        colors = np.array([(242, 104, 168), (121, 220, 247), (246, 244, 252), (255, 201, 99)], np.float32)
        picks = colors[rng.integers(0, 4, (7, n))]
        img[13:20][crowd] = picks[crowd]*.75
        img[20:] = (40, 120, 60)
        img[20::4] = (52, 140, 72)                     # mowing stripes
        img[21::4] = (52, 140, 72)
        img[24, :] = (220, 230, 220)                    # a pitch line
        for x in (2, 29):                               # floodlights
            img[3:13, x] = (90, 90, 110)
            img[1:4, x-2:x+3] = (255, 250, 210)
            img[4:9, x-3:x+4] = img[4:9, x-3:x+4]*.7+np.array((255, 250, 210))*.3
    elif name == 'notte':
        img = _vgrad((6, 8, 30), (30, 24, 70))
        stars = rng.random((n, n)) < .05
        stars[18:] = False
        img[stars] = (246, 244, 252)
        yy, xx = np.mgrid[0:n, 0:n]
        moon = (xx-25)**2+(yy-5)**2 <= 9
        img[moon] = (250, 238, 190)
        img[(xx-26)**2+(yy-4)**2 <= 1] = (220, 206, 160)
        hills = yy > 25+2*np.sin(xx/4)
        img[hills] = (16, 14, 36)
    elif name == 'pioggia':
        img = _vgrad((40, 48, 70), (70, 80, 104))
        yy, xx = np.mgrid[0:n, 0:n]
        for _ in range(26):   # short diagonal streaks
            x, y = int(rng.integers(0, n)), int(rng.integers(0, 27))
            for k in range(3):
                if 0 <= x-k < n and y+k < 29:
                    img[y+k, x-k] = (170, 200, 230) if k else (210, 228, 245)
        img[29:] = (50, 58, 80)
        img[30, 3:12] = (120, 150, 190); img[31, 18:27] = (120, 150, 190)   # puddles
    elif name == 'neve':
        img = _vgrad((20, 22, 60), (60, 56, 110))
        flakes = rng.random((n, n)) < .07
        img[flakes] = (240, 244, 255)
        img[28:] = (230, 236, 250)
        img[28, ::3] = (180, 196, 230)
    else:   # sfumato: the Flamingos colours, as a soft gradient
        img = _vgrad((40, 40, 90), (110, 50, 110))
    img = np.clip(img, 0, 255).astype(np.uint8)
    if style == 'gameboy':
        lum = img.astype(np.float32) @ np.array([.3, .59, .11])
        tones = np.digitize(lum, (55, 110, 170))
        img = GAMEBOY[tones].astype(np.uint8)
    return Image.fromarray(img, 'RGB')


def scene(name, style='arcade'):
    """A 32x32 pixel background for a sprite tile."""
    return _scene(name if name in SCENES else 'sfumato', 'gameboy' if style == 'gameboy' else 'arcade').copy()
