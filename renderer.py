"""Flamingos Studio 1.5: native high-resolution typography, layout, PNG and MP4."""
from __future__ import annotations

import base64
import io
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin

from render_utils import ScaledDraw, checked_scale, safe_positions
from scene_styles import atmosphere, blend

W, H = 540, 960
DEFAULT_PINK = (242, 72, 139)
DEFAULT_WHITE = (246, 238, 246)
DEFAULT_POSITIONS = {
    'logo': (91, 94), 'team': (310, 65), 'title': (310, 114),
    'footer': (270, 864), 'formation': (270, 898),
    'player_0': (270, 746), 'player_1': (270, 650), 'player_2': (270, 544),
    'player_3': (113, 407), 'player_4': (270, 407), 'player_5': (427, 407),
    'player_6': (270, 284),
}
DEFAULT_ROLES = ['Portiere', 'Difensore', 'Mediano', 'Esterno sinistro',
                 'Trequartista', 'Esterno destro', 'Attaccante']
FONT_FALLBACK = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf',
]


def rgb(hex_color, fallback=DEFAULT_PINK):
    try:
        h = str(hex_color).lstrip('#')
        return tuple(bytes.fromhex(h)) if len(h) == 6 else fallback
    except (ValueError, TypeError):
        return fallback


def font_from_bytes(data, size):
    return ImageFont.truetype(io.BytesIO(data), max(1, round(size)))


@lru_cache(maxsize=128)
def standard_font(size, style='Sans Bold'):
    size = max(1, round(size))
    mono = style == 'Monospace Bold'
    name = 'DejaVuSansMono-Bold.ttf' if mono else 'DejaVuSans-Bold.ttf'
    liberation = 'LiberationMono-Bold.ttf' if mono else 'LiberationSans-Bold.ttf'
    win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    paths = [f'/usr/share/fonts/truetype/dejavu/{name}',
             f'/usr/share/fonts/truetype/liberation2/{liberation}',
             f'/usr/share/fonts/truetype/liberation/{liberation}',
             '/System/Library/Fonts/Supplemental/Courier New Bold.ttf' if mono else
             '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
             str(win / ('courbd.ttf' if mono else 'arialbd.ttf')), name]
    for file in paths:
        try:
            return ImageFont.truetype(file, size)
        except OSError:
            continue
    # Pillow's scalable built-in fallback: no bundled font files required.
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=16)
def validate_font(data: bytes) -> None:
    if not isinstance(data, bytes) or not data or len(data) > 5_000_000:
        raise ValueError('Il font deve essere un TTF/OTF valido, massimo 5 MB.')
    if data[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'):
        raise ValueError('Formato non riconosciuto: usa un file .ttf o .otf standard.')
    try:
        font = font_from_bytes(data, 24)
        font.getmask('Flamingos 123')
    except Exception as exc:
        raise ValueError('Font non leggibile con il motore di esportazione.') from exc


def _font(style, size, data):
    if style in ('Font caricato', 'Font salvato') and data:
        return font_from_bytes(data, size)
    return standard_font(size, style)


def text_runs(parts, font_style, size, max_width, font_bytes=None,
              render_scale=1, max_height=None):
    """Fit the actual font, then rasterize once; colored runs share one baseline."""
    s = checked_scale(render_scale)
    parts = [(str(txt)[:512], tuple(color)) for txt, color in parts if str(txt)]
    if not parts or not ''.join(txt for txt, _ in parts).strip():
        return None
    logical_size = max(1, min(115, float(size)))
    if font_style == 'Pixel Arcade':
        # Intentional aesthetic only, never used for smooth or uploaded fonts.
        chunks = []
        ft = ImageFont.load_default(size=10)
        for value, color in parts:
            value = value.upper()
            bb = ft.getbbox(value)
            img = Image.new('RGBA', (max(1, bb[2] - bb[0] + 2), max(1, bb[3] - bb[1] + 2)))
            ImageDraw.Draw(img).text((1 - bb[0], 1 - bb[1]), value, font=ft, fill=(*color, 255))
            img.putalpha(img.getchannel('A').point(lambda x: 255 if x >= 100 else 0))
            chunks.append(img)
        joined = Image.new('RGBA', (sum(c.width for c in chunks), max(c.height for c in chunks)))
        x = 0
        for chunk in chunks:
            joined.alpha_composite(chunk, (x, joined.height - chunk.height))
            x += chunk.width
        factor = max(1, round(logical_size / 10)) * s
        width, height = joined.width * factor, joined.height * factor
        ratio = min(1, (max_width * s / width) if max_width else 1,
                    (max_height * s / height) if max_height else 1)
        return joined.resize((max(1, round(width * ratio)), max(1, round(height * ratio))), Image.Resampling.NEAREST)

    pad = s
    width_limit = round(max_width * s) if max_width else None
    height_limit = round(max_height * s) if max_height else None

    def measure(font):
        x = 0.0
        boxes = []
        for txt, _ in parts:
            left, top, right, bottom = font.getbbox(txt, anchor='ls')
            boxes.append((x + left, top, x + right, bottom))
            x += font.getlength(txt)
        left = math.floor(min(b[0] for b in boxes))
        top = math.floor(min(b[1] for b in boxes))
        right = math.ceil(max(b[2] for b in boxes))
        bottom = math.ceil(max(b[3] for b in boxes))
        return left, top, right, bottom

    low, high, selected = 1, max(1, round(logical_size * s)), None
    while low <= high:
        point_size = (low + high) // 2
        ft = _font(font_style, point_size, font_bytes)
        bb = measure(ft)
        fits = ((not width_limit or bb[2] - bb[0] + 2 * pad <= width_limit) and
                (not height_limit or bb[3] - bb[1] + 2 * pad <= height_limit))
        if fits:
            selected = (ft, bb)
            low = point_size + 1
        else:
            high = point_size - 1
    if selected is None:
        ft = _font(font_style, 1, font_bytes)
        selected = (ft, measure(ft))
    ft, bb = selected
    image = Image.new('RGBA', (max(1, bb[2] - bb[0] + 2 * pad), max(1, bb[3] - bb[1] + 2 * pad)))
    dr = ImageDraw.Draw(image)
    x = pad - bb[0]
    for txt, color in parts:
        dr.text((x, pad - bb[1]), txt, font=ft, fill=(*color, 255), anchor='ls')
        x += ft.getlength(txt)
    return image


def text_image(value, font_style, size, color, max_width, font_bytes=None,
               render_scale=1, max_height=None):
    return text_runs([(str(value).strip(), color)], font_style, size, max_width,
                     font_bytes, render_scale, max_height)


@lru_cache(maxsize=16)
def validate_logo(data: bytes) -> tuple[int, int]:
    if not isinstance(data, bytes) or not data or len(data) > 12_000_000:
        raise ValueError('Stemma non valido o superiore a 12 MB.')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG', 'JPEG', 'WEBP') or im.width * im.height > 20_000_000:
                raise ValueError('Usa PNG, JPEG o WebP, massimo 20 megapixel.')
            size = im.size
            im.verify()
        return size
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError('Il file non contiene un\'immagine leggibile.') from exc


@lru_cache(maxsize=8)
def clean_logo(image_bytes: bytes, width: int, remove_white: bool, render_scale=1):
    validate_logo(image_bytes)
    s = checked_scale(render_scale)
    with Image.open(io.BytesIO(image_bytes)) as opened:
        logo = ImageOps.exif_transpose(opened).convert('RGBA')
        logo.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    a = np.asarray(logo)
    if np.any(a[:, :, 3] < 32):
        box = logo.getchannel('A').getbbox()
    else:
        visible = np.min(a[:, :, :3], axis=2) < 225
        box = None
        if visible.any():
            ys, xs = np.nonzero(visible)
            box = (max(0, int(xs.min()) - 6), max(0, int(ys.min()) - 6),
                   min(logo.width, int(xs.max()) + 7), min(logo.height, int(ys.max()) + 7))
    if box:
        logo = logo.crop(box)
    if remove_white:
        # Exterior connected white only. Shield interiors and lettering remain intact.
        for corner in ((0, 0), (logo.width - 1, 0), (0, logo.height - 1), (logo.width - 1, logo.height - 1)):
            px = logo.getpixel(corner)
            if min(px[:3]) > 210 and px[3] > 100:
                ImageDraw.floodfill(logo, corner, (255, 255, 255, 0), thresh=24)
    target = max(30, min(230, int(width))) * s
    # Keep the requested logical dimensions even with a small source, using LANCZOS.
    ratio = min(target / logo.width, target * 1.55 / logo.height)
    return logo.resize((max(1, round(logo.width * ratio)), max(1, round(logo.height * ratio))), Image.Resampling.LANCZOS)


@dataclass
class Layer:
    id: str
    label: str
    image: Image.Image
    offset_x: float = 0
    offset_y: float = 0
    sequence: int = -1


def make_player_layer(entry, index, config, font_bytes, render_scale=1):
    s = render_scale
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    white = rgb(config.get('text_color'), DEFAULT_WHITE)
    style = config.get('text_style', config.get('font_choice', 'Sans Bold'))
    target = Image.new('RGBA', (150 * s, 111 * s))
    dr = ScaledDraw(target, s)
    dr.ellipse((45, 8, 105, 68), fill=(*rgb(config.get('panel_color'),(11,11,22)),255), outline=(*accent, 255), width=3)
    number = text_image(str(entry.get('number', index + 1))[:3], style, 22, white, 52, font_bytes, s, 44)
    if number:
        target.alpha_composite(number, (75 * s - number.width // 2, 38 * s - number.height // 2))
    dr.rounded_rectangle((2, 75, 148, 107), radius=4, fill=(*rgb(config.get('panel_color'),(8,7,16)),240), outline=(*accent, 230), width=1.4)
    name = text_image(str(entry.get('name', 'GIOCATORE'))[:27], style,
                      config.get('name_size', 17), white, 136, font_bytes, s, 26)
    if name:
        target.alpha_composite(name, (75 * s - name.width // 2, 91 * s - name.height // 2))
    return Layer(f'player_{index}', f'{index + 1}. {DEFAULT_ROLES[index]}', target, 0, 15, index)


def get_layers(config, logo_bytes, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    white = rgb(config.get('text_color'), DEFAULT_WHITE)
    style = config.get('text_style', config.get('font_choice', 'Sans Bold'))
    layers = [Layer('logo', 'Stemma', clean_logo(logo_bytes, config.get('logo_size', 95), config.get('remove_white', True), s))]
    for id_, label, value, size, clr, maximum in [
        ('team', 'Nome squadra', config.get('team_name', 'FLAMINGOS'), config.get('title_size', 34), accent, 368),
        ('title', 'Titolo principale', config.get('headline', 'STARTING 7'), config.get('subtitle_size', 26), white, 368),
        ('footer', 'Scritta inferiore', config.get('footer', 'CSI BRESCIA'), config.get('footer_size', 19), accent, 475),
        ('formation', 'Scritta modulo', config.get('formation_text', 'MODULO 1-1-3-1'), config.get('footer_size', 19), white, 475),
    ]:
        asset = text_image(value, style, size, clr, maximum, font_bytes, s)
        if asset:
            layers.append(Layer(id_, label, asset))
    for i, player in enumerate(config.get('players', [])[:7]):
        layers.append(make_player_layer(player, i, config, font_bytes, s))
    return layers


def base_image(config, render_scale=1):
    s = checked_scale(render_scale)
    accent = rgb(config.get('accent'), DEFAULT_PINK)
    bg = rgb(config.get('background'), (13, 11, 20))
    panel = rgb(config.get('panel_color'), (15,12,24))
    pitch = rgb(config.get('pitch_color'), (14,32,33))
    im = atmosphere(W,H,bg,accent,accent,config.get('pattern','Pulito'),s,config.get('texture',25))
    effects = Image.new('RGBA', im.size)
    d = ScaledDraw(effects, s)
    amount = max(0, min(100, int(config.get('texture', 25)))) / 100
    for yy in range(0, H, 7):
        d.line((0, yy, W, yy), fill=(255, 255, 255, round(20 * amount)), width=0.5)
    for xx in range(25, W - 24, 27):
        for yy in range(195, 831, 27):
            d.rectangle((xx, yy, xx + 2, yy + 2), fill=(*accent, round(55 * amount)))
    im.alpha_composite(effects)
    d = ScaledDraw(im, s)
    d.rounded_rectangle((25, 28, 515, 158), radius=13, fill=(*panel,255), outline=(*accent, 235), width=2)
    x1, y1, x2, y2 = 38, 193, 502, 827
    d.rounded_rectangle((x1, y1, x2, y2), radius=13, fill=(*pitch,255), outline=(*accent, 250), width=3)
    for yy in range(y1 + 9, y2 - 9, 37):
        d.line((x1 + 5, yy, x2 - 5, yy), fill=(*blend(pitch,accent,.07),255), width=9)
    line = (110, 111, 116, 255)
    d.rectangle((x1 + 17, y1 + 18, x2 - 17, y2 - 18), outline=line, width=1.5)
    mid = (y1 + y2) // 2
    d.line((x1 + 17, mid, x2 - 17, mid), fill=line, width=1.5)
    d.ellipse((W // 2 - 63, mid - 63, W // 2 + 63, mid + 63), outline=line, width=1.5)
    d.rectangle((W // 2 - 91, y1 + 18, W // 2 + 91, y1 + 96), outline=line, width=1.5)
    d.rectangle((W // 2 - 91, y2 - 96, W // 2 + 91, y2 - 18), outline=line, width=1.5)
    d.rounded_rectangle((25, 843, 515, 929), radius=9, fill=(*panel,255), outline=(*accent, 230), width=1.5)
    d.line((25, 946, 515, 946), fill=(*accent, 100), width=1)
    return im


def normalized_positions(config):
    return safe_positions(config, DEFAULT_POSITIONS)


def composite_layer(canvas, layer, pos, alpha=1.0, drop=0):
    if alpha <= 0:
        return
    s = canvas.width / W
    img = layer.image
    if alpha < .999:
        img = img.copy()
        img.putalpha(img.getchannel('A').point(lambda v: round(v * alpha)))
    x = round((pos[0] + layer.offset_x) * s - img.width / 2)
    y = round((pos[1] + layer.offset_y + drop) * s - img.height / 2)
    # Correct straight-alpha composition, avoiding dark / translucent glyph edges.
    canvas.alpha_composite(img, (x, y))


def scene(config, logo_bytes, font_bytes=None, render_scale=2):
    s = checked_scale(render_scale)
    return base_image(config, s), get_layers(config, logo_bytes, font_bytes, s), normalized_positions(config)


def progress(t, start, length=.42):
    v = max(0., min(1., (t - start) / length))
    return 1 - (1 - v) ** 3


def compose(prepared, t=999, animated=True):
    base, layers, positions = prepared
    im = base.copy()
    for layer in layers:
        if not animated:
            a, drop = 1, 0
        elif layer.id == 'logo':
            a = progress(t, .05, .5); drop = (1 - a) * 15
        elif layer.id in ('team', 'title'):
            a = progress(t, .35 if layer.id == 'team' else .75); drop = (1 - a) * 15
        elif layer.id in ('footer', 'formation'):
            a = progress(t, 5.15 if layer.id == 'footer' else 5.45); drop = (1 - a) * 9
        else:
            a = progress(t, 1.20 + layer.sequence * .53, .44); drop = (1 - a) * 44
        composite_layer(im, layer, positions[layer.id], a, drop)
    return im.convert('RGB')


def frame(t, config, logo_bytes, font_bytes=None):
    return compose(scene(config, logo_bytes, font_bytes), t)


def encode_png(image):
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add(b'sRGB', b'\x00')
    image.save(output, format='PNG', optimize=True, pnginfo=metadata)
    return output.getvalue()


def png_bytes(config, logo_bytes, font_bytes=None, scale=2, supersample=2):
    scale = checked_scale(scale)
    ss = checked_scale(supersample, 2)
    internal = min(4, scale * ss)
    image = compose(scene(config, logo_bytes, font_bytes, internal), animated=False)
    target = (W * scale, H * scale)
    if image.size != target:
        image = image.resize(target, Image.Resampling.LANCZOS)
    return encode_png(image)


def video_writer(filename, fps):
    return imageio.get_writer(str(filename), fps=fps, codec='libx264', quality=None,
                             ffmpeg_log_level='error', macro_block_size=2,
                             output_params=['-pix_fmt', 'yuv420p', '-crf', '18',
                                            '-preset', 'fast', '-movflags', '+faststart'])


def video_settings(fps, duration, scale):
    fps, duration = int(fps), float(duration)
    checked_scale(scale, 2)
    if not 1 <= fps <= 60 or not .1 <= duration <= 30:
        raise ValueError('Durata o FPS fuori intervallo.')
    return fps, duration


def render_video(config, logo_bytes, filename, font_bytes=None, fps=24, duration=8, scale=2, progress_callback=None):
    fps, duration = video_settings(fps, duration, scale)
    prepared = scene(config, logo_bytes, font_bytes, scale)
    writer = video_writer(filename, fps)
    count = round(duration * fps)
    try:
        for i in range(count):
            writer.append_data(np.asarray(compose(prepared, t=i / fps)))
            if progress_callback and (i % fps == 0 or i == count - 1):
                progress_callback((i + 1) / count)
    finally:
        writer.close()
    return str(filename)


def image_base64(image):
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


def editor_data(prepared):
    bg, layers, positions = prepared
    s = bg.width / W
    return {'canvas_width': W, 'canvas_height': round(bg.height/s), 'background': image_base64(bg), 'layers': [
        {'id': item.id, 'label': item.label, 'image': image_base64(item.image),
         'width': item.image.width / s, 'height': item.image.height / s,
         'dx': item.offset_x, 'dy': item.offset_y} for item in layers],
        'positions': {key: list(value) for key, value in positions.items()}}
