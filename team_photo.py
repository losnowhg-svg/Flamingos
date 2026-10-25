"""Pixel team photo: the whole squad as sprites, grouped by department.

A 1080x1350 (Instagram 4:5) or 1080x1920 (story) poster: title on top, the
players by department (portieri, difensori, centrocampisti, attaccanti) and
the staff row, each with number and name. Arcade neon, or Game Boy greens
when the preset is Pocket.
"""
from __future__ import annotations

import datetime as dt
import io

from PIL import Image, ImageDraw

import pixel_character as pc
from pixel_fonts import pixel_text_runs

SIZES = {'Post 4:5': (1080, 1350), 'Story 9:16': (1080, 1920), 'Quadrato 1:1': (1080, 1080)}
GROUPS = (('P', 'PORTIERI'), ('D', 'DIFENSORI'), ('C', 'CENTROCAMPISTI'), ('A', 'ATTACCANTI'), ('STAFF', 'STAFF'))
STAFF_LABEL = {'ALL': 'MISTER', 'DIR': 'DIRIGENTE'}
NEON = dict(bg=(14, 10, 30), bg2=(40, 14, 52), pink=(242, 104, 168), cyan=(121, 220, 247), white=(246, 244, 252),
            yellow=(255, 201, 99), tile=(26, 20, 48), line=(80, 230, 255))
POCKET = dict(bg=tuple(pc.GAMEBOY[0]), bg2=tuple(pc.GAMEBOY[1]), pink=tuple(pc.GAMEBOY[3]), cyan=tuple(pc.GAMEBOY[2]),
              white=tuple(pc.GAMEBOY[3]), yellow=tuple(pc.GAMEBOY[3]), tile=tuple(pc.GAMEBOY[1]),
              line=tuple(pc.GAMEBOY[2]))


def season_label(today=None):
    today = today or dt.date.today()
    start = today.year if today.month >= 8 else today.year-1
    return f'{start}/{str(start+1)[-2:]}'


def groups(squad):
    """[(label, [members])] in department order; people without a role are left out."""
    out = []
    for key, label in GROUPS:
        if key == 'STAFF':
            people = [p for p in squad if p.get('role') == 'ALL']+[p for p in squad if p.get('role') == 'DIR']
        else:
            people = sorted((p for p in squad if p.get('role') == key),
                            key=lambda p: (int(p.get('number') or 0) == 0, int(p.get('number') or 0), p.get('name', '')))
        if people:
            out.append((label, people))
    return out


def _pack(sections, cols):
    """Pack sections into rows of `cols` cells. Small sections share a row;
    big ones wrap. Each row is a list of (label or None, member)."""
    rows, row = [], []
    for label, people in sections:
        if row and len(row)+len(people) > cols:
            rows.append(row); row = []
        for i, person in enumerate(people):
            if len(row) == cols:
                rows.append(row); row = []
            row.append((label if i == 0 else None, person))
    if row:
        rows.append(row)
    return rows


def _text(value, size, color, width):
    return pixel_text_runs([(str(value).upper(), color)], 'CRT Terminal', size, width)


def _background(w, h, c):
    img = Image.new('RGB', (w, h), c['bg'])
    d = ImageDraw.Draw(img, 'RGBA')
    for y in range(h):  # soft vertical glow
        k = max(0.0, 1-abs(y-h*.55)/(h*.6))
        if k:
            d.line((0, y, w, y), fill=(*c['bg2'], round(150*k)))
    horizon = round(h*.80)
    for i in range(1, 14):  # perspective floor grid
        y = horizon+(h-horizon)*(i/13)**1.8
        d.line((0, y, w, y), fill=(*c['line'], 50))
    for i in range(-12, 13):
        d.line((w/2+i*28, horizon, w/2+i*170, h), fill=(*c['line'], 40))
    for y in range(0, h, 4):  # scanlines
        d.line((0, y, w, y), fill=(0, 0, 0, 36))
    return img


def team_photo(squad, preset_id='crt', logo=None, title='FLAMINGOS', subtitle=None, size='Post 4:5'):
    """The poster as an RGB PIL image."""
    w, h = SIZES.get(size, SIZES['Post 4:5'])
    c = POCKET if pc.style_for(preset_id) == 'gameboy' else NEON
    img = _background(w, h, c)
    d = ImageDraw.Draw(img, 'RGBA')
    subtitle = subtitle or f'ROSA {season_label()} · CSI BRESCIA'

    # Title block.
    top = 70
    if logo:
        try:
            from renderer import clean_logo
            mark = clean_logo(logo, 400, True, 1)
            mark.thumbnail((130, 130))
            img.paste(mark, (70, top-10), mark)
        except Exception:
            pass
    t = _text(title, 64, c['pink'], w-320)
    if t:
        img.paste(t, ((w-t.width)//2, top), t)
    st = _text(subtitle, 22, c['cyan'], w-200)
    if st:
        img.paste(st, ((w-st.width)//2, top+90), st)
    d.line((140, top+136, w-140, top+136), fill=(*c['cyan'], 120), width=2)

    sections = groups(squad)
    if not sections:
        msg = _text('CARICA LA ROSA', 30, c['white'], w-100)
        if msg:
            img.paste(msg, ((w-msg.width)//2, h//2), msg)
        return img

    # Pick the biggest tile that fits.
    area_top, area_bottom = top+170, h-90
    for cols in (4, 5, 6, 7, 8, 9, 10):
        rows = _pack(sections, cols)
        cell = min(210, (w-100)//cols)
        tile = cell-22
        row_h = 30+tile+56
        if row_h*len(rows) <= area_bottom-area_top:
            break
    y = area_top+(area_bottom-area_top-row_h*len(rows))//2
    name_size = max(14, min(22, tile//7))
    for row in rows:
        x0 = (w-cell*len(row))//2
        for i, (label, person) in enumerate(row):
            x = x0+i*cell+11
            if label:
                lab = _text(label, 14, c['yellow'], cell*3)
                if lab:
                    img.paste(lab, (x, y+4), lab)
            ty = y+30
            d.rectangle((x, ty, x+tile, ty+tile), fill=(*c['tile'], 230), outline=(*c['cyan'], 220), width=3)
            sprite = pc.picture(person, preset_id)
            k = max(1, (tile-6)//sprite.width)
            big = sprite.resize((sprite.width*k, sprite.height*k), Image.Resampling.NEAREST)
            img.paste(big, (x+(tile-big.width)//2, ty+tile-big.height-3), big)
            number = int(person.get('number') or 0)
            if number and person.get('role') not in STAFF_LABEL:
                bw = max(30, tile//4)
                d.rectangle((x, ty, x+bw, ty+bw*.8), fill=(*c['pink'], 255))
                n = _text(number, round(bw*.5), c['bg'], bw-6)
                if n:
                    img.paste(n, (x+(bw-n.width)//2, ty+round(bw*.4)-n.height//2), n)
            nm = _text(person.get('name', ''), name_size, c['white'], cell-6)
            if nm:
                img.paste(nm, (x+tile//2-nm.width//2, ty+tile+10), nm)
            role = STAFF_LABEL.get(person.get('role'))
            if role:
                r = _text(role, 11, c['cyan'], cell-6)
                if r:
                    img.paste(r, (x+tile//2-r.width//2, ty+tile+16+name_size), r)
        y += row_h
    foot = _text('FORZA FLAMINGOS', 16, c['pink'], w-200)
    if foot:
        img.paste(foot, ((w-foot.width)//2, h-56), foot)
    return img


def png_bytes(*args, **kwargs):
    out = io.BytesIO()
    team_photo(*args, **kwargs).save(out, 'PNG', optimize=True)
    return out.getvalue()
