"""The graphic shown on a real tube TV in a dark room.

frame() takes a full 9:16 frame of any CRT editor, crops the shared screen
area (all text and crests live there), bends it like curved glass and puts
it inside a code-drawn television: bezel, speaker, channel knob, antenna,
cabinet with a VCR. The screen's own colour spills onto the room, so the
light changes with the picture. The channel knob angle can be animated:
sequence videos turn it at every channel change.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from crt_presets import FORMATS

SOURCE = (78, 316, 462, 674)          # the shared screen area of every editor
HEIGHTS = {'Post 1:1': 540, 'Post 4:5': 675, 'Story 9:16': 960}
# TV geometry in its own units; the body's top-left corner is (0, 0).
BODY = (0, 0, 480, 372)
SCREEN = (30, 30, 360, 336)
GROUP = (-30, -125, 510, 452)
KNOB = (425, 100, 27)
VOLUME = (425, 178, 18)


def layout(format):
    """(k, ox, oy): TV units -> output units for a format."""
    height = HEIGHTS.get(format, 960)
    gw, gh = GROUP[2]-GROUP[0], GROUP[3]-GROUP[1]
    k = min(1.0, (height-36)/gh, 520/gw)
    ox = 270-(BODY[2]/2)*k
    oy = (height-gh*k)/2-GROUP[1]*k
    if height == 960:
        oy -= 20
    return k, ox, oy


class _Map:
    def __init__(self, format, scale):
        self.k, self.ox, self.oy = layout(format)
        self.f = self.k*scale
        self.scale = scale

    def p(self, x, y):
        return ((self.ox+x*self.k)*self.scale, (self.oy+y*self.k)*self.scale)

    def box(self, x1, y1, x2, y2):
        a, b = self.p(x1, y1)
        c, d = self.p(x2, y2)
        return [a, b, c, d]

    def r(self, value):
        return value*self.f


def _gradient(size, top, bottom):
    w, h = size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    col = np.array(top, np.float32)+(np.array(bottom, np.float32)-np.array(top, np.float32))*t
    return np.repeat(col, w, axis=1)


@lru_cache(maxsize=3)
def _room(format, scale):
    """Room, TV and cabinet with a black screen (RGB), plus the screen mask."""
    height = HEIGHTS.get(format, 960)
    size = (540*scale, height*scale)
    m = _Map(format, scale)
    floor_y = m.p(0, 440)[1]
    arr = _gradient(size, (22, 16, 30), (12, 9, 17))
    fy = int(max(0, min(size[1], floor_y)))
    if fy < size[1]:
        arr[fy:] = _gradient((size[0], size[1]-fy), (30, 22, 28), (9, 7, 10))
    # Faint wallpaper stripes.
    for x in range(0, size[0], max(2, round(36*scale))):
        arr[:fy, x:x+max(1, round(scale))] *= 1.06
    room = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert('RGBA')

    shadow = Image.new('RGBA', size)
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(m.box(-60, 405, 540, 490), fill=(0, 0, 0, 200))
    room.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(m.r(18))))

    d = ImageDraw.Draw(room)
    # Cabinet with a VCR.
    d.rectangle(m.box(-30, 384, 510, 452), fill=(46, 30, 28))
    d.rectangle(m.box(-30, 384, 510, 390), fill=(78, 52, 44))
    d.rectangle(m.box(128, 402, 352, 436), fill=(16, 15, 18))
    d.rectangle(m.box(140, 412, 250, 418), fill=(6, 6, 8))
    d.rectangle(m.box(300, 413, 340, 425), fill=(10, 30, 14))
    _text(room, '12:00', m.p(320, 419), m.r(9), (110, 255, 140))
    for x in (270, 282):
        d.rectangle(m.box(x, 413, x+7, 419), fill=(70, 70, 76))
    # Antenna.
    for tip in ((140, -112), (352, -122)):
        d.line([m.p(240, -8), m.p(*tip)], fill=(150, 150, 160), width=max(1, round(m.r(2.4))))
        d.ellipse(m.box(tip[0]-4, tip[1]-4, tip[0]+4, tip[1]+4), fill=(190, 190, 200))
    d.pieslice(m.box(205, -22, 275, 22), 180, 360, fill=(40, 36, 44))
    # Feet and body.
    for x in (60, 390):
        d.rectangle(m.box(x, 368, x+30, 384), fill=(24, 22, 26))
    d.rounded_rectangle(m.box(*BODY), radius=m.r(30), fill=(44, 40, 50))
    d.rounded_rectangle(m.box(378, 18, 466, 348), radius=m.r(14), fill=(34, 31, 40))
    body_light = Image.new('RGBA', size)
    bd = ImageDraw.Draw(body_light)
    bd.rounded_rectangle(m.box(6, 4, 474, 120), radius=m.r(26), fill=(255, 255, 255, 18))
    bd.rounded_rectangle(m.box(*BODY), radius=m.r(30), outline=(255, 255, 255, 34), width=max(1, round(m.r(2))))
    room.alpha_composite(body_light.filter(ImageFilter.GaussianBlur(m.r(3))))
    d = ImageDraw.Draw(room)
    # Screen recess and bezel.
    d.rounded_rectangle(m.box(16, 16, 374, 350), radius=m.r(30), fill=(20, 18, 24))
    d.rounded_rectangle(m.box(22, 22, 368, 344), radius=m.r(28), fill=(6, 6, 8))
    # Control strip: speaker grille, badge, knobs, LED.
    for row in range(10):
        for col in range(7):
            x, y = 393+col*10, 228+row*11
            d.ellipse(m.box(x, y, x+4, y+4), fill=(18, 16, 22))
    _text(room, 'FLAMINGOS', m.p(422, 40), m.r(8), (214, 200, 220))
    for cx, cy, r in (KNOB, VOLUME):
        d.ellipse(m.box(cx-r-3, cy-r-3, cx+r+3, cy+r+3), fill=(22, 20, 26))
        d.ellipse(m.box(cx-r, cy-r, cx+r, cy+r), fill=(70, 66, 76))
        d.ellipse(m.box(cx-r*.7, cy-r*.7, cx+r*.7, cy+r*.7), fill=(86, 82, 94))
        for i in range(12):
            a = i/12*math.tau
            d.line([m.p(cx+math.cos(a)*r*.78, cy+math.sin(a)*r*.78), m.p(cx+math.cos(a)*r, cy+math.sin(a)*r)],
                   fill=(40, 38, 46), width=max(1, round(m.r(1.4))))
    for i in range(1, 13):  # channel numbers around the knob
        a = -math.pi/2+(i-1)/12*math.tau
        x = KNOB[0]+math.cos(a)*(KNOB[2]+11)
        y = KNOB[1]+math.sin(a)*(KNOB[2]+11)
        d.ellipse(m.box(x-1.2, y-1.2, x+1.2, y+1.2), fill=(150, 146, 160))
    d.ellipse(m.box(422, 208, 428, 214), fill=(255, 60, 60))

    mask = Image.new('L', size)
    ImageDraw.Draw(mask).rounded_rectangle(m.box(*SCREEN), radius=m.r(18), fill=255)
    return room.convert('RGB'), mask


def _text(image, value, center, size, color):
    from pixel_fonts import pixel_text_runs
    label = pixel_text_runs([(value, color)], 'CRT Scoreboard', max(6, size/max(1, image.width/540)),
                            400, max(1, round(image.width/540)))
    if label:
        image.alpha_composite(label, (round(center[0]-label.width/2), round(center[1]-label.height/2)))


@lru_cache(maxsize=3)
def _lens(width, height):
    """Barrel distortion lookup plus vignette for the curved glass."""
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    u, v = (x-width/2)/(width/2), (y-height/2)/(height/2)
    r2 = u*u+v*v
    k = .05
    f = (1+k*r2)/(1+k)
    sx, sy = (u*f+1)*width/2, (v*f+1)*height/2
    valid = (sx >= 0) & (sx < width) & (sy >= 0) & (sy < height)
    sx = np.clip(sx, 0, width-1).astype(np.int32)
    sy = np.clip(sy, 0, height-1).astype(np.int32)
    shade = (1-.38*np.clip(r2/2, 0, 1)**1.4)*valid
    return sy, sx, shade[..., None].astype(np.float32)


@lru_cache(maxsize=3)
def _glass(format, scale):
    """Reflections on the glass (RGBA, full frame)."""
    height = HEIGHTS.get(format, 960)
    size = (540*scale, height*scale)
    m = _Map(format, scale)
    glass = Image.new('RGBA', size)
    d = ImageDraw.Draw(glass)
    x1, y1, x2, y2 = SCREEN
    d.polygon([m.p(x1+10, y1+8), m.p(x1+190, y1+8), m.p(x1+70, y2-60), m.p(x1+10, y2-120)], fill=(255, 255, 255, 22))
    d.ellipse(m.box(x2-120, y1+12, x2-30, y1+40), fill=(255, 255, 255, 26))
    glass = glass.filter(ImageFilter.GaussianBlur(m.r(10)))
    rim = Image.new('RGBA', size)
    ImageDraw.Draw(rim).rounded_rectangle(m.box(*SCREEN), radius=m.r(22), outline=(255, 255, 255, 40), width=max(1, round(m.r(1.5))))
    glass.alpha_composite(rim.filter(ImageFilter.GaussianBlur(m.r(1.5))))
    return glass


@lru_cache(maxsize=3)
def _spill(format, scale):
    """Where the screen light falls: around the TV, the cabinet and the floor."""
    height = HEIGHTS.get(format, 960)
    size = (540*scale, height*scale)
    m = _Map(format, scale)
    mask = Image.new('L', size)
    d = ImageDraw.Draw(mask)
    x1, y1, x2, y2 = SCREEN
    d.rounded_rectangle(m.box(x1-60, y1-70, x2+60, y2+60), radius=m.r(80), fill=110)
    d.ellipse(m.box(-80, 400, 560, 580), fill=150)
    d.rectangle(m.box(-30, 384, 510, 402), fill=200)
    mask = mask.filter(ImageFilter.GaussianBlur(m.r(48)))
    return np.asarray(mask, np.float32)[..., None]/255


def frame(source, format='Story 9:16', scale=2, knob=0.0):
    """The TV scene for one full 540x960-proportioned frame. knob in degrees."""
    format = format if format in FORMATS else 'Story 9:16'
    source = source.convert('RGB')
    fs = source.width/540
    room, mask = _room(format, scale)
    m = _Map(format, scale)
    box = [round(v) for v in m.box(*SCREEN)]
    w, h = box[2]-box[0], box[3]-box[1]
    crop = source.crop(tuple(round(v*fs) for v in SOURCE)).resize((w, h), Image.Resampling.LANCZOS)
    sy, sx, shade = _lens(w, h)
    screen = np.asarray(crop, np.float32)[sy, sx]*shade
    # Light spill tinted by the picture.
    color = np.asarray(crop.resize((1, 1), Image.Resampling.BOX), np.float32).reshape(1, 1, 3)
    level = float(color.mean())/255
    lit = np.asarray(room, np.float32)
    lit = lit+_spill(format, scale)*(color*.55+12)*(.35+level)
    out = Image.fromarray(lit.clip(0, 255).astype(np.uint8))
    glow = Image.fromarray(screen.clip(0, 255).astype(np.uint8))
    halo = glow.resize((max(1, w//8), max(1, h//8)), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    halo = halo.resize((w, h), Image.Resampling.BILINEAR)
    out.paste(Image.blend(glow, halo, .12), (box[0], box[1]), mask.crop(tuple(box)))
    out = out.convert('RGBA')
    out.alpha_composite(_glass(format, scale))
    # Channel knob pointer.
    d = ImageDraw.Draw(out)
    cx, cy, r = KNOB
    a = math.radians(knob-90)
    d.line([m.p(cx, cy), m.p(cx+math.cos(a)*r*.85, cy+math.sin(a)*r*.85)], fill=(236, 230, 240),
           width=max(1, round(m.r(3))))
    d.ellipse(m.box(cx-3, cy-3, cx+3, cy+3), fill=(40, 38, 46))
    a = math.radians(-30-90)
    vx, vy, vr = VOLUME
    d.line([m.p(vx, vy), m.p(vx+math.cos(a)*vr*.8, vy+math.sin(a)*vr*.8)], fill=(236, 230, 240),
           width=max(1, round(m.r(2.4))))
    return out.convert('RGB')
