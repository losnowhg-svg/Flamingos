"""Deterministic, native-resolution graphic atmospheres. No network or AI assets."""
from PIL import Image
from render_utils import ScaledDraw, checked_scale

PATTERNS = ('Pulito', 'Diagonali', 'Griglia', 'Fasce', 'Coriandoli', 'Orbita')


def blend(first, second, amount):
    return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(first, second))


def atmosphere(width, height, background, accent, secondary, pattern='Pulito', scale=1, intensity=35):
    s = checked_scale(scale)
    image = Image.new('RGBA', (width*s, height*s), (*background, 255))
    overlay = Image.new('RGBA', image.size)
    draw = ScaledDraw(overlay, s)
    alpha = round(max(0, min(100, intensity)) * .65)
    if pattern == 'Diagonali':
        for offset, color in [(-90, accent), (75, secondary), (290, accent)]:
            draw.polygon([(offset, 0), (offset+94, 0), (width+offset+94, height), (width+offset, height)], fill=(*color, alpha))
    elif pattern == 'Griglia':
        for x in range(0, width+1, 30):
            draw.line((x, 0, x, height), fill=(*accent, max(5, alpha//2)), width=.6)
        for y in range(0, height+1, 30):
            draw.line((0, y, width, y), fill=(*secondary, max(5, alpha//2)), width=.6)
    elif pattern == 'Fasce':
        for y in range(0, height, 110):
            draw.polygon([(0, y), (width, y+48), (width, y+91), (0, y+43)], fill=(*accent, alpha))
    elif pattern == 'Coriandoli':
        # Fixed arithmetic, not randomness: previews and exports remain identical.
        for i in range(68):
            x, y = (i*79+17) % width, (i*137+29) % height
            color = accent if i % 2 else secondary
            draw.polygon([(x,y),(x+5,y+2),(x+3,y+11),(x-2,y+9)], fill=(*color, min(110, alpha*2)))
    elif pattern == 'Orbita':
        for radius in range(100, 801, 72):
            draw.ellipse((width-40-radius, -40-radius, width-40+radius, -40+radius), outline=(*accent, alpha), width=2)
    image.alpha_composite(overlay)
    return image
