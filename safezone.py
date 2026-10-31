"""Instagram safe zone for Reels and Stories (9:16).

In a Reel the app draws over the video: the header at the top, account name,
caption and music at the bottom, the like / comment / share column on the
right. Stories cover less. The zone below is the union of the two, in
540x960 layout units, so what stays inside is readable in both.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

TOP, BOTTOM, LEFT, RIGHT = 120, 200, 24, 66
SAFE = (LEFT, TOP, 540-RIGHT, 960-BOTTOM)
ZONES = (('alto: intestazione', (0, 0, 540, TOP)),
         ('basso: nome, didascalia, musica', (0, 960-BOTTOM, 540, 960)),
         ('destra: mi piace, commenti, condividi', (540-RIGHT, TOP, 540, 960-BOTTOM)),
         ('sinistra', (0, TOP, LEFT, 960-BOTTOM)))


def applies(format):
    return format == 'Story 9:16'


def editor_zones(format):
    """Rectangles for the drag editor overlay (only for 9:16)."""
    return [list(rect) for _, rect in ZONES] if applies(format) else None


def _box(layer, pos, s):
    x, y = pos[0]+layer.offset_x, pos[1]+layer.offset_y
    w, h = layer.image.width/s, layer.image.height/s
    return x-w/2, y-h/2, x+w/2, y+h/2


def covered(prepared, format):
    """Labels of the elements that end up (even partly) under Instagram's interface."""
    if not applies(format):
        return []
    base, layers, positions = prepared
    s = base.width/540
    out = []
    for layer in layers:
        if layer.id not in positions:
            continue
        x1, y1, x2, y2 = _box(layer, positions[layer.id], s)
        if x1 < SAFE[0]-.5 or y1 < SAFE[1]-.5 or x2 > SAFE[2]+.5 or y2 > SAFE[3]+.5:
            out.append(layer.label)
    return out


def fit(prepared, positions):
    """Positions moved the least needed to bring every element inside the safe zone."""
    base, layers, _ = prepared
    s = base.width/540
    moved = {k: list(v) for k, v in positions.items()}
    for layer in layers:
        if layer.id not in moved:
            continue
        x1, y1, x2, y2 = _box(layer, moved[layer.id], s)
        dx = (SAFE[0]-x1 if x1 < SAFE[0] else SAFE[2]-x2 if x2 > SAFE[2] else 0)
        dy = (SAFE[1]-y1 if y1 < SAFE[1] else SAFE[3]-y2 if y2 > SAFE[3] else 0)
        if x2-x1 > SAFE[2]-SAFE[0]:    # wider than the zone: centre it
            dx = (SAFE[0]+SAFE[2])/2-(x1+x2)/2
        if y2-y1 > SAFE[3]-SAFE[1]:
            dy = (SAFE[1]+SAFE[3])/2-(y1+y2)/2
        moved[layer.id] = [round(moved[layer.id][0]+dx), round(moved[layer.id][1]+dy)]
    return moved


def mock(image):
    """The PNG with a generic Reel interface drawn on top (only to check, never exported)."""
    im = image.convert('RGBA')
    w, h = im.size
    s = w/540
    over = Image.new('RGBA', im.size)
    d = ImageDraw.Draw(over)
    # Shadows the app puts behind its text.
    for y in range(int(h-BOTTOM*1.3*s), h):
        k = (y-(h-BOTTOM*1.3*s))/(BOTTOM*1.3*s)
        d.line((0, y, w, y), fill=(0, 0, 0, int(150*k)))
    for y in range(int(TOP*s)):
        d.line((0, y, w, y), fill=(0, 0, 0, int(90*(1-y/(TOP*s)))))
    white = (255, 255, 255, 235)

    def u(*v):
        return [round(x*s) for x in v]
    d.rectangle(u(22, 62, 110, 70), fill=white)                       # header text
    d.ellipse(u(500, 56, 512, 68), outline=white, width=max(1, round(2*s)))
    for i, y in enumerate((560, 630, 700, 770)):                      # right column
        cx = 506
        if i == 0:
            d.polygon(u(cx, y+14, cx-14, y, cx-9, y-8, cx, y-3, cx+9, y-8, cx+14, y), fill=white)
        elif i == 1:
            d.ellipse(u(cx-14, y-12, cx+14, y+12), outline=white, width=max(1, round(2.5*s)))
        elif i == 2:
            d.polygon(u(cx-15, y-2, cx+15, y-14, cx+4, y+14, cx, y+3), outline=white, width=max(1, round(2.5*s)))
        else:
            for k in (-9, 0, 9):
                d.ellipse(u(cx+k-2.5, y-2.5, cx+k+2.5, y+2.5), fill=white)
        d.rectangle(u(cx-12, y+22, cx+12, y+27), fill=(255, 255, 255, 170))
    d.ellipse(u(22, 812, 52, 842), fill=(242, 104, 168, 255), outline=white, width=max(1, round(2*s)))
    d.rectangle(u(62, 820, 170, 832), fill=white)                     # account name
    d.rounded_rectangle(u(182, 815, 250, 837), radius=round(6*s), outline=white, width=max(1, round(1.5*s)))
    d.rectangle(u(22, 856, 380, 866), fill=(255, 255, 255, 200))      # caption
    d.rectangle(u(22, 876, 300, 886), fill=(255, 255, 255, 160))
    d.rectangle(u(22, 906, 220, 914), fill=(255, 255, 255, 150))      # music line
    im.alpha_composite(over)
    return im.convert('RGB')
