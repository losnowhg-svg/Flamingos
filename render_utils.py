"""Resolution-independent drawing. All layout coordinates remain in 540x960 units."""
from __future__ import annotations

import math
from PIL import Image, ImageDraw


def checked_scale(value: int, maximum: int = 4) -> int:
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Fattore di rendering non valido.') from exc
    if number != value or not 1 <= number <= maximum:
        raise ValueError(f'Il fattore di rendering deve essere intero, da 1 a {maximum}.')
    return number


class ScaledDraw:
    """Draw vector primitives directly at output resolution (never enlarge a bitmap)."""

    def __init__(self, image: Image.Image, scale: int = 1):
        self.draw = ImageDraw.Draw(image)
        self.scale = scale

    def coords(self, value):
        if isinstance(value, (tuple, list)):
            return [self.coords(v) for v in value]
        return round(float(value) * self.scale)

    def _shape(self, kind, xy, **kwargs):
        for name in ('width', 'radius'):
            if name in kwargs:
                kwargs[name] = max(1, round(kwargs[name] * self.scale))
        return getattr(self.draw, kind)(self.coords(xy), **kwargs)

    def line(self, xy, **kwargs):
        return self._shape('line', xy, **kwargs)

    def rectangle(self, xy, **kwargs):
        return self._shape('rectangle', xy, **kwargs)

    def rounded_rectangle(self, xy, **kwargs):
        return self._shape('rounded_rectangle', xy, **kwargs)

    def ellipse(self, xy, **kwargs):
        return self._shape('ellipse', xy, **kwargs)

    def polygon(self, xy, **kwargs):
        return self._shape('polygon', xy, **kwargs)


def safe_positions(config, defaults, width=540, height=960):
    result = {}
    incoming = config.get('positions', {})
    for key, default in defaults.items():
        x, y = default
        raw = incoming.get(key) if isinstance(incoming, dict) else None
        if isinstance(raw, (tuple, list)) and len(raw) == 2:
            try:
                a, b = float(raw[0]), float(raw[1])
                if math.isfinite(a) and math.isfinite(b):
                    x, y = round(a), round(b)
            except (TypeError, ValueError, OverflowError):
                pass
        result[key] = (max(0, min(width, x)), max(0, min(height, y)))
    return result


def layout_warnings(prepared, crop=None):
    """Report actual clipping, not a generic warning about canvas resolution."""
    base, layers, positions = prepared
    s = base.width / 540
    bounds = crop or (0, 0, 540, base.height / s)
    warnings = []
    for layer in layers:
        x, y = positions[layer.id]
        x += layer.offset_x
        y += layer.offset_y
        w, h = layer.image.width / s, layer.image.height / s
        if x - w / 2 < bounds[0] or x + w / 2 > bounds[2] or y - h / 2 < bounds[1] or y + h / 2 > bounds[3]:
            warnings.append(f'{layer.label}: parte dell\'elemento e fuori dal formato esportato.')
    return warnings
