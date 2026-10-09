"""Flamingos Studio renderer: custom fonts, drag layout, PNG and animated MP4."""
from __future__ import annotations

import io
import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 540, 960
DEFAULT_PINK = (242, 72, 139)
DEFAULT_WHITE = (246, 238, 246)
DEFAULT_POSITIONS = {
    'logo': (91, 94),
    'team': (310, 65),
    'title': (310, 114),
    'footer': (270, 864),
    'formation': (270, 898),
    'player_0': (270, 746),
    'player_1': (270, 650),
    'player_2': (270, 544),
    'player_3': (113, 407),
    'player_4': (270, 407),
    'player_5': (427, 407),
    'player_6': (270, 284),
}
DEFAULT_ROLES = [
    'Portiere', 'Difensore', 'Mediano', 'Esterno sinistro',
    'Trequartista', 'Esterno destro', 'Attaccante',
]
FONT_FALLBACK = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf',
]


def rgb(hex_color, fallback=DEFAULT_PINK):
    try:
        h = str(hex_color).lstrip('#')
        if len(h) != 6:
            return fallback
        return tuple(bytes.fromhex(h))
    except (ValueError, TypeError):
        return fallback


def font_from_bytes(data, size):
    return ImageFont.truetype(io.BytesIO(data), int(size))


def standard_font(size):
    for file in FONT_FALLBACK:
        if Path(file).is_file():
            return ImageFont.truetype(file, max(8, round(size)))
    return ImageFont.load_default()


def validate_font(data: bytes) -> None:
    if not data or len(data) > 5_000_000:
        raise ValueError('Il font deve essere un file TTF/OTF valido (massimo 5 MB).')
    try:
        font = font_from_bytes(data, 24)
        font.getbbox('Flamingos 123')
    except Exception as exc:
        raise ValueError('Font non leggibile. Usa un file .ttf o .otf standard.') from exc


def text_image(value, font_style, size, color, max_width, font_bytes=None):
    """Text asset with visible-glyph bounding box, no forced uppercase for custom fonts."""
    msg = str(value).strip()
    if not msg:
        return None
    size = max(9, min(115, round(size)))
    if font_style == 'Pixel Arcade':
        # Rasterize once at small scale then enlarge with nearest-neighbour pixels.
        msg = msg.upper()
        ft = ImageFont.load_default()
        factor = max(1, round(size / 10))
    elif font_style == 'Font caricato' and font_bytes:
        ft = font_from_bytes(font_bytes, size)
        factor = 1
    else:
        ft = standard_font(size)
        factor = 1
    tmp = Image.new('RGBA', (1, 1))
    bb = ImageDraw.Draw(tmp).textbbox((0, 0), msg, font=ft)
    width, height = max(1, bb[2] - bb[0]), max(1, bb[3] - bb[1])
    asset = Image.new('RGBA', (width + 2, height + 2))
    ImageDraw.Draw(asset).text((1 - bb[0], 1 - bb[1]), msg, font=ft, fill=(*color, 255))
    if factor > 1:
        asset = asset.resize((asset.width * factor, asset.height * factor), Image.Resampling.NEAREST)
    if max_width and asset.width > max_width:
        scale = max_width / asset.width
        asset = asset.resize((max(1, round(asset.width * scale)), max(1, round(asset.height * scale))),
                             Image.Resampling.NEAREST if font_style == 'Pixel Arcade' else Image.Resampling.LANCZOS)
    return asset


@lru_cache(maxsize=12)
def clean_logo(image_bytes: bytes, width: int, remove_white: bool):
    if not image_bytes or len(image_bytes) > 12_000_000:
        raise ValueError('Logo non valido o troppo grande.')
    with Image.open(io.BytesIO(image_bytes)) as opened:
        opened.thumbnail((1600, 1600))
        logo = opened.convert('RGBA')
    # Crop away the surrounding background, but preserve the white in the shield.
    a = np.asarray(logo)
    if np.any(a[:, :, 3] < 32):
        box = logo.getchannel('A').getbbox()
    else:
        rgb_array = a[:, :, :3]
        visible = np.min(rgb_array, axis=2) < 225
        if visible.any():
            ys, xs = np.nonzero(visible)
            pad = 6
            box = (max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
                   min(logo.width, int(xs.max()) + pad + 1), min(logo.height, int(ys.max()) + pad + 1))
        else:
            box = logo.getbbox()
    if box:
        logo = logo.crop(box)
    if remove_white and logo.width and logo.height:
        corner = logo.getpixel((0, 0))
        if min(corner[:3]) > 210 and corner[3] > 100:
            # Flood fill only the connected background. Logo's white lettering remains.
            ImageDraw.floodfill(logo, (0, 0), (255, 255, 255, 0), thresh=24)
    target = max(30, min(230, int(width)))
    logo.thumbnail((target, round(target * 1.55)), Image.Resampling.LANCZOS)
    return logo.copy()


@dataclass
class Layer:
    id: str
    label: str
    image: Image.Image
    offset_x: float = 0
    offset_y: float = 0
    sequence: int = -1


def make_player_layer(entry, index, config, font_bytes):
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    white = rgb(config.get('text_color'), DEFAULT_WHITE)
    scale = float(config.get('name_size', 17))
    style = config.get('text_style', 'Pixel Arcade')
    # origin = centre of player marker at (75, 38)
    target = Image.new('RGBA', (150, 111))
    dr = ImageDraw.Draw(target)
    dr.ellipse((45, 8, 105, 68), fill=(11, 11, 22, 255), outline=(*accent, 255), width=4)
    number = text_image(str(entry.get('number', index + 1))[:3], style, 19, white, 52, font_bytes)
    if number:
        target.alpha_composite(number, (75 - number.width // 2, 38 - number.height // 2))
    dr.rounded_rectangle((2, 75, 148, 107), radius=4, fill=(8, 7, 16, 235), outline=(*accent, 230), width=2)
    name = text_image(str(entry.get('name', 'GIOCATORE'))[:27], style, scale, white, 136, font_bytes)
    if name:
        target.alpha_composite(name, (75 - name.width // 2, 91 - name.height // 2))
    return Layer(f'player_{index}', f'{index + 1}. {DEFAULT_ROLES[index]}', target, 0, 15, index)


def get_layers(config, logo_bytes, font_bytes=None):
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    white = rgb(config.get('text_color'), DEFAULT_WHITE)
    style = config.get('text_style', 'Pixel Arcade')
    title_size = int(config.get('title_size', 34))
    subtitle_size = int(config.get('subtitle_size', 26))
    footer_size = int(config.get('footer_size', 19))
    layers = []
    layers.append(Layer('logo', 'Stemma', clean_logo(logo_bytes, config.get('logo_size', 95), config.get('remove_white', True))))
    for id_, label, value, size, clr, maximum in [
        ('team', 'Nome squadra', config.get('team_name', 'FLAMINGOS'), title_size, accent, 368),
        ('title', 'Titolo principale', config.get('headline', 'STARTING 7'), subtitle_size, white, 368),
        ('footer', 'Scritta inferiore', config.get('footer', 'CSI BRESCIA'), footer_size, accent, 475),
        ('formation', 'Scritta modulo', config.get('formation_text', 'MODULO 1-1-3-1'), footer_size, white, 475),
    ]:
        asset = text_image(value, style, size, clr, maximum, font_bytes)
        if asset is not None:
            layers.append(Layer(id_, label, asset))
    for i, player in enumerate(config.get('players', [])[:7]):
        layers.append(make_player_layer(player, i, config, font_bytes))
    return layers


def base_image(config):
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    bg = rgb(config.get('background'), (13, 11, 20))
    im = Image.new('RGBA', (W, H), (*bg, 255))
    effects = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(effects)
    for yy in range(0, H, 7):
        d.line((0, yy, W, yy), fill=(255, 255, 255, 12), width=1)
    for xx in range(25, W - 24, 27):
        for yy in range(195, 831, 27):
            d.rectangle((xx, yy, xx + 2, yy + 2), fill=(*accent, 55))
    im.alpha_composite(effects)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((25, 28, 515, 158), radius=13, fill=(15, 12, 24, 255), outline=(*accent, 235), width=3)
    x1, y1, x2, y2 = 38, 193, 502, 827
    d.rounded_rectangle((x1, y1, x2, y2), radius=13, fill=(14, 32, 33, 255), outline=(*accent, 250), width=4)
    for yy in range(y1 + 9, y2 - 9, 37):
        d.line((x1 + 5, yy, x2 - 5, yy), fill=(20, 43, 37, 255), width=9)
    line = (110, 111, 116, 255)
    d.rectangle((x1 + 17, y1 + 18, x2 - 17, y2 - 18), outline=line, width=2)
    mid = (y1 + y2) // 2
    d.line((x1 + 17, mid, x2 - 17, mid), fill=line, width=2)
    d.ellipse((W // 2 - 63, mid - 63, W // 2 + 63, mid + 63), outline=line, width=2)
    d.rectangle((W // 2 - 91, y1 + 18, W // 2 + 91, y1 + 96), outline=line, width=2)
    d.rectangle((W // 2 - 91, y2 - 96, W // 2 + 91, y2 - 18), outline=line, width=2)
    d.rounded_rectangle((25, 843, 515, 929), radius=9, fill=(15, 12, 24, 255), outline=(*accent, 230), width=2)
    d.line((25, 946, 515, 946), fill=(*accent, 100), width=2)
    return im


def normalized_positions(config):
    result = {}
    incoming = config.get('positions', {})
    for key, (x, y) in DEFAULT_POSITIONS.items():
        raw = incoming.get(key) if isinstance(incoming, dict) else None
        try:
            if raw and len(raw) == 2:
                x, y = int(float(raw[0])), int(float(raw[1]))
        except (TypeError, ValueError, OverflowError):
            pass
        result[key] = (max(0, min(W, x)), max(0, min(H, y)))
    return result


def composite_layer(canvas, layer, pos, alpha=1.0, drop=0):
    if alpha <= 0:
        return
    img = layer.image
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel('A').point(lambda v: round(v * alpha)))
    x = round(pos[0] + layer.offset_x - img.width / 2)
    y = round(pos[1] + layer.offset_y - img.height / 2 + drop)
    canvas.paste(img, (x, y), img)


def scene(config, logo_bytes, font_bytes=None):
    return base_image(config), get_layers(config, logo_bytes, font_bytes), normalized_positions(config)


def progress(t, start, length=0.42):
    v = max(0.0, min(1.0, (t - start) / length))
    return 1 - (1 - v) ** 3


def compose(prepared, t=999, animated=True):
    base, layers, positions = prepared
    im = base.copy()
    for layer in layers:
        if not animated:
            a, drop = 1, 0
        elif layer.id == 'logo':
            a = progress(t, 0.05, 0.5)
            drop = int((1 - a) * 15)
        elif layer.id in ('team', 'title'):
            a = progress(t, 0.35 if layer.id == 'team' else 0.75)
            drop = int((1 - a) * 15)
        elif layer.id in ('footer', 'formation'):
            a = progress(t, 5.15 if layer.id == 'footer' else 5.45)
            drop = int((1 - a) * 9)
        else:
            a = progress(t, 1.20 + layer.sequence * 0.53, 0.44)
            drop = int((1 - a) * 44)
        composite_layer(im, layer, positions[layer.id], a, drop)
    if animated and t < 0.60:
        dr = ImageDraw.Draw(im, 'RGBA')
        pink = rgb('#F2488B')
        for k in range(5):
            yy = 210 + 127 * k
            dr.rectangle((21, yy, 21 + int((0.6 - t) * 160), yy + 4), fill=(*pink, 165))
    return im.convert('RGB')


def frame(t, config, logo_bytes, font_bytes=None):
    return compose(scene(config, logo_bytes, font_bytes), t)


def png_bytes(config, logo_bytes, font_bytes=None, scale=2):
    image = compose(scene(config, logo_bytes, font_bytes), animated=False)
    if scale != 1:
        image = image.resize((W * scale, H * scale), Image.Resampling.NEAREST)
    result = io.BytesIO()
    image.save(result, format='PNG', optimize=True)
    return result.getvalue()


def render_video(config, logo_bytes, filename, font_bytes=None, fps=15, duration=8, scale=1):
    prepared = scene(config, logo_bytes, font_bytes)
    writer = imageio.get_writer(str(filename), fps=int(fps), codec='libx264', quality=7,
                                ffmpeg_log_level='error', macro_block_size=4,
                                output_params=['-pix_fmt', 'yuv420p', '-movflags', '+faststart'])
    try:
        for i in range(round(float(duration) * int(fps))):
            image = compose(prepared, t=i / fps)
            if scale != 1:
                image = image.resize((W * scale, H * scale), Image.Resampling.NEAREST)
            writer.append_data(np.asarray(image))
    finally:
        writer.close()
    return str(filename)


def image_base64(image):
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


def editor_data(prepared):
    bg, layers, positions = prepared
    return {
        'background': image_base64(bg),
        'layers': [
            {
                'id': item.id, 'label': item.label, 'image': image_base64(item.image),
                'width': item.image.width, 'height': item.image.height,
                'dx': item.offset_x, 'dy': item.offset_y,
            }
            for item in layers
        ],
        'positions': {key: list(value) for key, value in positions.items()},
    }
