"""The words and panels around the figurine screens, on the synthwave night or on a preset (3.13).

On the synthwave night: Inter Display, dark violet panels, the pink/cyan/yellow
of the collection. On a studio preset the same pieces follow the CRT graphics,
like the Classifica: the preset's pixel font, its four colours, its panel and
border, square-ish corners. The cards themselves never change.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

import cards

SYNTH_PANEL = (18, 13, 28)


class Look:
    def __init__(self, style, u):
        style = style or {}
        self.u = float(u)
        self.font = style.get('font') if style.get('panel') else None
        self.pink, self.cyan, self.yellow, self.white = style.get('palette') or (cards.PINK, cards.CYAN, cards.YELLOW,
                                                                               cards.WHITE)
        self.panel = tuple(style.get('panel') or SYNTH_PANEL)
        self.border = tuple(style.get('border') or self.white)

    @property
    def preset(self):
        return bool(self.font)

    @staticmethod
    def mix(a, b, k):
        return tuple(round(x*k+y*(1-k)) for x, y in zip(a[:3], b[:3]))

    def ink(self, color):
        """Text that reads on a filled accent: dark on light accents, light on dark ones."""
        from render_utils import contrast_ink
        return contrast_ink(color)

    def text(self, value, kind, size, color, max_width=None, **kw):
        """Inter Display on the synthwave night, the preset's pixel font on a preset (tracking and shadow: Inter only)."""
        if not self.font:
            return cards.text(value, kind, size, color, self.u, max_width=max_width, **kw)
        value = str(value or '').replace('★', '').replace('·', '-').strip()
        if not value:
            return None
        from renderer import text_image
        r = max(1, min(4, round(self.u)))
        img = text_image(value, self.font, max(7.0, size*.62), tuple(color[:3]), max_width, None, r)   # 7: digits stay whole
        if img is not None and r != self.u:
            k = self.u/r
            img = img.resize((max(1, round(img.width*k)), max(1, round(img.height*k))), Image.Resampling.NEAREST)
        return img

    def radius(self, synth):
        """Corner radius in pixels: rounded on the night, almost square on a preset."""
        return int((min(4, synth) if self.font else synth)*self.u)

    def box_fill(self, alpha=255):
        """The darker box for a score or a vote, inside a panel."""
        if not self.font:
            return (8, 6, 14, alpha)
        from render_utils import is_light
        return (*self.mix(self.panel, (0, 0, 0), .88 if is_light(self.panel) else .7), alpha)

    def dim(self, k=.62):
        """Secondary text: white pulled towards the panel."""
        return self.mix(self.white, self.panel, k)

    def plate(self, canvas, box, styled=True):
        """The plate under a title on a preset background (nothing on the synthwave night)."""
        if not styled:
            return
        x0, y0, x1, y1 = box
        layer = Image.new('RGBA', (max(1, int(x1-x0)), max(1, int(y1-y0))))
        d = ImageDraw.Draw(layer)
        if self.font:
            d.rounded_rectangle((0, 0, layer.width-1, layer.height-1), radius=int(6*self.u), fill=(*self.panel, 222),
                                outline=(*self.border, 90), width=max(1, int(self.u)))
        else:
            d.rounded_rectangle((0, 0, layer.width-1, layer.height-1), radius=int(14*self.u), fill=(16, 12, 26, 205))
        canvas.paste(layer, (int(x0), int(y0)), layer)
