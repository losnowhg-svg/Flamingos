"""Two original bitmap alphabets, drawn in code; no TTF/OTF assets or network.

CRT Terminal is a 5x7 monospaced alphabet. CRT Scoreboard uses a separate
compact 3x5 alphabet with extended cells. Both support Italian accents,
common punctuation and colored runs with a shared baseline.
"""
from __future__ import annotations

import math
import unicodedata
from PIL import Image, ImageDraw

PIXEL_FONTS = ('CRT Terminal', 'CRT Scoreboard')

# Each hexadecimal digit stores one row of pixels, most significant bit first.
TERMINAL = {
    'A':'0e11111f111111', 'B':'1e11111e11111e', 'C':'0f10101010100f',
    'D':'1e11111111111e', 'E':'1f10101e10101f', 'F':'1f10101e101010',
    'G':'0f10101711110f', 'H':'1111111f111111', 'I':'0e04040404040e',
    'J':'0702020212120c', 'K':'11121418141211', 'L':'1010101010101f',
    'M':'111b1515111111', 'N':'11191915131311', 'O':'0e11111111110e',
    'P':'1e11111e101010', 'Q':'0e11111115120d', 'R':'1e11111e141211',
    'S':'0f10100e01011e', 'T':'1f040404040404', 'U':'1111111111110e',
    'V':'11111111110a04', 'W':'11111115151b11', 'X':'11110a040a1111',
    'Y':'11110a04040404', 'Z':'1f01020408101f',
    '0':'0e11131519110e', '1':'040c040404040e', '2':'0e11010204081f',
    '3':'1e01010e01011e', '4':'02060a121f0202', '5':'1f101e0101110e',
    '6':'0610101e11110e', '7':'1f010204080808', '8':'0e11110e11110e',
    '9':'0e11110f01020c',
    ' ':'00000000000000', '-':'0000001f000000', '.':'00000000000c0c',
    ':':'000c0c000c0c00', ',':'00000000000c08', ';':'000c0c00000c08',
    "'":'0c0c0800000000', '"':'0a0a0000000000', '/':'01010204081010',
    '(':'02040808080402', ')':'08040202020408', '[':'0e08080808080e',
    ']':'0e02020202020e', '+':'0004041f040400', '=':'00001f001f0000',
    '!':'04040404040004', '?':'0e110102040004', '#':'0a1f0a0a1f0a00',
    '&':'0c12140c15120d', '%':'19190204081313', '*':'0015040e041500',
    '_':'0000000000001f', '@':'0e11171517100f', '|':'04040404040404',
    '>':'10080402040810', '<':'01020408040201', '\\':'10100804020101',
}
COMPACT = {
    'A':'25755', 'B':'65656', 'C':'34443', 'D':'65556', 'E':'74647',
    'F':'74644', 'G':'34553', 'H':'55755', 'I':'72227', 'J':'11152',
    'K':'55655', 'L':'44447', 'M':'57755', 'N':'57555', 'O':'25552',
    'P':'65644', 'Q':'25573', 'R':'65655', 'S':'34216', 'T':'72222',
    'U':'55557', 'V':'55552', 'W':'55775', 'X':'55255', 'Y':'55222',
    'Z':'71247', '0':'75557', '1':'26227', '2':'71247', '3':'71217',
    '4':'55711', '5':'74617', '6':'74657', '7':'71111', '8':'75757',
    '9':'75717', ' ':'00000', '-':'00700', '.':'00002', ':':'02020',
    ',':'00024', ';':'02024', "'":'22000', '"':'55000', '/':'11244',
    '(':'24442', ')':'21112', '[':'64446', ']':'31113', '+':'02720',
    '=':'07070', '!':'22202', '?':'71202', '#':'57575', '&':'25653',
    '%':'51245', '*':'05250', '_':'00007', '@':'75743', '|':'22222',
    '>':'42124', '<':'12421', '\\':'44211',
}
TRANSLATE = str.maketrans({'\u2019':"'", '\u2018':"'", '\u2032':"'", '\u201c':'"',
                           '\u201d':'"', '\u2013':'-', '\u2014':'-', '\u00d7':'X',
                           '\u2022':'.', '\u00b7':'.', '\u2026':'...', '\u00a0':' '})


def _glyphs(value, table, width, height):
    for char in str(value).translate(TRANSLATE).upper():
        decomposed = unicodedata.normalize('NFD', char)
        base = decomposed[0] if decomposed else '?'
        accent = decomposed[1:]
        encoded = table.get(base, table['?'])
        rows = [int(encoded[i:i+2], 16) for i in range(0, len(encoded), 2)] if width == 5 else [int(row, 16) for row in encoded]
        yield rows, accent


def pixel_text_runs(parts, style, size, max_width, render_scale=1, max_height=None):
    """Rasterize bitmap strokes directly at the requested output resolution."""
    compact = style == 'CRT Scoreboard'
    table, width, height, aspect = (COMPACT, 3, 5, 1.12) if compact else (TERMINAL, 5, 7, 1.0)
    glyphs = [(rows, accent, color) for text, color in parts for rows, accent in _glyphs(text, table, width, height)]
    if not glyphs:
        return None
    top = 2 if any(accent for _, accent, _ in glyphs) else 0
    units_w, units_h = len(glyphs) * (width+1)-1, height+top
    cell_y = max(.25, float(size) / height) * render_scale
    cell_x = cell_y * aspect
    ratio = min(1., (max_width*render_scale/(units_w*cell_x)) if max_width else 1.,
                (max_height*render_scale/(units_h*cell_y)) if max_height else 1.)
    cell_x *= ratio
    cell_y *= ratio
    out_w=max(1,math.ceil(units_w*cell_x-1e-9))
    out_h=max(1,math.ceil(units_h*cell_y-1e-9))
    if max_width:out_w=min(out_w,max(1,round(max_width*render_scale)))
    if max_height:out_h=min(out_h,max(1,round(max_height*render_scale)))
    im = Image.new('RGBA', (out_w,out_h))
    draw = ImageDraw.Draw(im)

    def dot(x, y, color):
        x1, y1 = round(x*cell_x), round(y*cell_y)
        x2, y2 = round((x+1)*cell_x)-1, round((y+1)*cell_y)-1
        if x2 >= x1 and y2 >= y1:
            draw.rectangle((x1, y1, x2, y2), fill=tuple(color[:3])+(255,))

    for i, (rows, accent, color) in enumerate(glyphs):
        x = i*(width+1)
        for y, bits in enumerate(rows):
            for col in range(width):
                if bits & (1 << (width-col-1)):
                    dot(x+col, y+top, color)
        if accent:
            middle = width//2
            if '\u0300' in accent:
                dot(x+middle-1, 0, color); dot(x+middle, 1, color)
            elif '\u0308' in accent:
                dot(x, 0, color); dot(x+width-1, 0, color)
            else:
                dot(x+middle+1, 0, color); dot(x+middle, 1, color)
    return im
