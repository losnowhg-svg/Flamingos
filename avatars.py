"""Retro pixel avatars made from a player's photo.

Pipeline: square crop around the face (guessed from skin tones, adjustable),
background removal by region growing from the edges (the face area is
protected), reduction to a small grid, a short palette (k-means), a dark
outline and, optionally, a pink team shirt drawn over the shoulders.

Only the finished avatar (a few KB of PNG) is kept, in the squad saved in
the browser: the original photo is never stored.
"""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

SIZE = 40                 # avatar grid, in pixels
MAX_PHOTO = 20_000_000    # bytes
MAX_AVATAR = 24_000       # bytes of stored PNG
OUTLINE = (24, 16, 30)


def load_photo(data):
    if not data or len(data) > MAX_PHOTO:
        raise ValueError('Foto mancante o troppo grande (massimo 20 MB).')
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.width*im.height > 60_000_000:
                raise ValueError('Foto con troppi pixel.')
            photo = ImageOps.exif_transpose(im).convert('RGB')
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Il file non sembra una foto leggibile (JPG o PNG).') from exc
    return _trim_bars(photo)


def _trim_bars(photo):
    """Drop the black bands of phone screenshots."""
    arr = np.asarray(photo.resize((max(1, photo.width//8), max(1, photo.height//8))), np.float32)
    rows = arr.mean(axis=(1, 2))
    dark = rows < 14
    top = int(np.argmax(~dark)) if (~dark).any() else 0
    bottom = len(rows)-int(np.argmax(~dark[::-1])) if (~dark).any() else len(rows)
    if top == 0 and bottom == len(rows):
        return photo
    return photo.crop((0, top*8, photo.width, min(photo.height, bottom*8)))


def _skin(arr):
    """Classic YCbCr skin box."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    cb = 128-.168736*r-.331264*g+.5*b
    cr = 128+.5*r-.418688*g-.081312*b
    return (cb > 77) & (cb < 127) & (cr > 136) & (cr < 175) & (r > 60)


def _rect(ii, x1, y1, x2, y2):
    return ii[y2, x2]-ii[y1, x2]-ii[y2, x1]+ii[y1, x1]


def find_face(photo):
    """(cx, cy, face_height) in photo pixels, by searching the box that is most
    skin inside, with no skin just above it (hair) and little at its sides."""
    small = photo.copy()
    small.thumbnail((120, 120))
    mask = _skin(np.asarray(small, np.float32)).astype(np.float64)
    h, w = mask.shape
    ii = np.zeros((h+1, w+1))
    ii[1:, 1:] = mask.cumsum(0).cumsum(1)
    best, found = -9.0, None
    for s in range(max(8, int(w*.18)), max(10, int(w*.7)), 2):
        cw, ch, hair, side = int(s*.62), int(s*.8), int(s*.3), max(2, int(s*.22))
        for cy in range(ch//2+hair, int(h*.75)-ch//2, 2):
            y1, y2 = cy-ch//2, cy+ch//2
            if y2 >= h:
                continue
            for cx in range(cw//2+1, w-cw//2-1, 2):
                x1, x2 = cx-cw//2, cx+cw//2
                core = _rect(ii, x1, y1, x2, y2)/(cw*ch)
                top = _rect(ii, x1, y1-hair, x2, y1)/(cw*hair)
                left = _rect(ii, max(0, x1-side), y1, x1, y2)/max(1, (x1-max(0, x1-side))*ch)
                right = _rect(ii, x2, y1, min(w, x2+side), y2)/max(1, (min(w, x2+side)-x2)*ch)
                score = core-.9*top-.35*(left+right)+.002*s
                if score > best:
                    best, found = score, (cx, cy, ch)
    if not found or best < .25:
        return None
    k = photo.width/w
    return found[0]*k, found[1]*k, found[2]*k


def guess_face(photo):
    """(cx, cy, zoom) as fractions of the photo, framing head and shoulders."""
    face = find_face(photo)
    if not face:
        return .5, .38, 1.6
    cx, cy, face_h = face
    side = face_h*2.0
    zoom = float(np.clip(min(photo.width, photo.height)/side, 1, 8))
    return round(cx/photo.width, 3), round((cy+face_h*.12)/photo.height, 3), round(zoom, 2)


def crop(photo, cx=.5, cy=.4, zoom=1.6):
    """Square crop: zoom 1 = the full short side."""
    side = min(photo.width, photo.height)/max(1.0, float(zoom))
    x = min(max(0, cx*photo.width-side/2), photo.width-side)
    y = min(max(0, cy*photo.height-side/2), photo.height-side)
    return photo.crop((round(x), round(y), round(x+side), round(y+side)))


def _bust(size):
    """Head-and-shoulders silhouette for a crop framed by guess_face()."""
    yy, xx = np.mgrid[0:size, 0:size]/size
    head = ((xx-.5)/.31)**2+((yy-.40)/.35)**2 <= 1
    neck = (np.abs(xx-.5) < .13) & (yy > .55) & (yy < .86)
    shoulders = (yy > .80) & (np.abs(xx-.5) < .2+(yy-.80)*2.5)
    face = ((xx-.5)/.2)**2+((yy-.46)/.25)**2 <= 1
    return head | neck | shoulders, face


def _background(arr, tolerance, protected):
    """True where the pixel is background: grown from the borders, never into `protected`."""
    h, w = arr.shape[:2]
    seen = np.zeros((h, w), bool)
    # Seeds on the top and on the sides above the shoulders: the bottom edge is the body.
    stack = [(y, x) for y in range(int(h*.72)) for x in (0, w-1)]+[(0, x) for x in range(w)]
    for y, x in stack:
        seen[y, x] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y+1, x), (y-1, x), (y, x+1), (y, x-1)):
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not protected[ny, nx]:
                if np.abs(arr[ny, nx]-arr[y, x]).sum() < tolerance:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
    return seen


def _kmeans(pixels, k, iterations=14):
    pixels = pixels.astype(np.float32)
    if len(pixels) <= k:
        return pixels, np.arange(len(pixels))
    order = np.argsort(pixels.sum(axis=1))
    centers = pixels[order[np.linspace(0, len(pixels)-1, k).astype(int)]].copy()
    for _ in range(iterations):
        labels = np.argmin(((pixels[:, None, :]-centers[None])**2).sum(axis=2), axis=1)
        for i in range(k):
            members = pixels[labels == i]
            if len(members):
                centers[i] = members.mean(axis=0)
    labels = np.argmin(((pixels[:, None, :]-centers[None])**2).sum(axis=2), axis=1)
    return centers, labels


def _shirt(rgba, color, size):
    """A simple jersey over the shoulders: V collar, darker seams, a stripe."""
    base = np.array(color, np.float32)
    dark = (base*.66).astype(np.uint8)
    light = np.minimum(255, base*1.1+22).astype(np.uint8)
    top = round(size*.82)
    for y in range(top, size):
        half = min(size//2, round(size*.24)+(y-top)*3)
        x1, x2 = max(0, size//2-half), min(size, size//2+half)
        rgba[y, x1:x2] = (*color, 255)
        rgba[y, x1] = (*dark, 255)
        rgba[y, x2-1] = (*dark, 255)
    mid = size//2
    for i in range(3):
        y = top+i
        if y < size:
            rgba[y, mid-3+i:mid+3-i] = (*OUTLINE, 255)
    for y in range(top+2, size):
        rgba[y, max(0, mid-round(size*.2)):max(0, mid-round(size*.2))+1] = (*light, 255)
    return rgba


def _outline(rgba):
    subject = rgba[..., 3] > 0
    grown = subject.copy()
    grown[1:] |= subject[:-1]; grown[:-1] |= subject[1:]
    grown[:, 1:] |= subject[:, :-1]; grown[:, :-1] |= subject[:, 1:]
    rgba[grown & ~subject] = (*OUTLINE, 255)
    return rgba


def make_avatar(photo, cx=.5, cy=.4, zoom=1.6, colors=8, remove_background=True, tolerance=40,
                shirt=True, shirt_color=(242, 104, 168), size=SIZE):
    """The avatar as an RGBA image of size x size pixels (transparent background)."""
    k = 4
    big = size*k
    square = crop(photo, cx, cy, zoom).resize((big, big), Image.Resampling.LANCZOS)
    square = ImageEnhance.Color(ImageEnhance.Contrast(square).enhance(1.2)).enhance(1.25)
    square = square.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.UnsharpMask(3, 120, 2))
    arr = np.asarray(square, np.float32)
    bust, face = _bust(size)
    if remove_background:
        small = np.asarray(square.resize((size, size), Image.Resampling.BOX), np.float32)
        subject = bust & ~_background(small, tolerance, face)
        try:
            from scipy import ndimage
            labels, count = ndimage.label(subject)
            if count > 1:
                sizes = ndimage.sum(subject, labels, range(1, count+1))
                subject = labels == (int(np.argmax(sizes))+1)
            subject = ndimage.binary_fill_holes(subject)
            subject = ndimage.binary_opening(subject, iterations=1) | face
        except ImportError:
            pass
    else:
        subject = np.ones((size, size), bool)
    # Palette from the subject only, then one colour per cell by majority -
    # with dark details (eyes, brows, mouth) winning when they fill enough of it.
    cells = subject.repeat(k, 0).repeat(k, 1)
    centers, labels = _kmeans(arr[cells].reshape(-1, 3), colors)
    lum = centers @ np.array([.299, .587, .114], np.float32)
    rank = np.argsort(np.argsort(lum))
    full = np.full((big, big), -1, np.int32)
    full[cells] = labels
    blocks = full.reshape(size, k, size, k).transpose(0, 2, 1, 3).reshape(size, size, k*k)
    rgba = np.zeros((size, size, 4), np.uint8)
    for y in range(size):
        for x in range(size):
            if not subject[y, x]:
                continue
            values = blocks[y, x][blocks[y, x] >= 0]
            if not len(values):
                continue
            counts = np.bincount(values, minlength=len(centers))
            choice = int(np.argmax(counts))
            dark = [i for i in np.nonzero(counts)[0] if rank[i] < 2]
            if dark and face[y, x]:
                d = min(dark, key=lambda i: rank[i])
                if counts[d] >= k*k*.3:
                    choice = d
            rgba[y, x, :3] = np.clip(centers[choice], 0, 255).astype(np.uint8)
            rgba[y, x, 3] = 255
    if shirt:
        rgba = _shirt(rgba, shirt_color, size)
    if remove_background:
        rgba = _outline(rgba)
    return Image.fromarray(rgba, 'RGBA')


def encode(avatar):
    out = io.BytesIO()
    avatar.save(out, 'PNG', optimize=True)
    data = out.getvalue()
    if len(data) > MAX_AVATAR:
        raise ValueError('Avatar troppo grande.')
    return base64.b64encode(data).decode('ascii')


def decode(value):
    """Validated avatar from storage, or None."""
    if not isinstance(value, str) or not value or len(value) > MAX_AVATAR*4//3+8:
        return None
    try:
        data = base64.b64decode(value, validate=True)
        with Image.open(io.BytesIO(data)) as im:
            if im.format != 'PNG' or im.width > 128 or im.height > 128:
                return None
            im.load()
            return im.convert('RGBA')
    except (ValueError, OSError):
        return None


def enlarge(avatar, pixels):
    """Crisp nearest-neighbour enlargement to (about) pixels wide."""
    factor = max(1, round(pixels/avatar.width))
    return avatar.resize((avatar.width*factor, avatar.height*factor), Image.Resampling.NEAREST)


def placeholder(size=SIZE, color=(242, 104, 168)):
    """Generic pixel silhouette for players without a photo."""
    rgba = np.zeros((size, size, 4), np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]
    head = ((xx-size/2+.5)/(size*.22))**2+((yy-size*.42)/(size*.27))**2 <= 1
    rgba[head] = (74, 66, 92, 255)
    neck = (np.abs(xx-size/2+.5) < size*.1) & (yy > size*.6)
    rgba[neck] = (74, 66, 92, 255)
    return Image.fromarray(_outline(_shirt(rgba, color, size)), 'RGBA')
