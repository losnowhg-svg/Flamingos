"""Convocati by department: one slide each for goalkeepers, defenders,
midfielders, forwards and staff, with every player's pixel avatar.

The slides take everything else (preset, theme, colours, font, format,
animation, TV mockup) from the Convocati editor.
"""
from __future__ import annotations

import copy

from PIL import Image

import avatars
from render_utils import ScaledDraw, checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, rgb
from matchday_renderer import _decorate_text
from crt_presets import STYLE, background
from crt_common import compose, export_png, export_video

GROUPS = (('P', 'PORTIERI'), ('D', 'DIFENSORI'), ('C', 'CENTROCAMPISTI'), ('A', 'ATTACCANTI'), ('STAFF', 'STAFF'))
STAFF_ROLES = {'ALL': 'ALLENATORE', 'DIR': 'DIRIGENTE'}
MAX_CARDS = 12
BODY = (90, 386, 450, 667)
HEAD_POSITIONS = {'logo': (118, 346), 'title': (294, 337), 'subtitle': (294, 360)}
LAYER_NAMES = {'logo': 'Stemma', 'title': 'Reparto', 'subtitle': 'Partita'}


def grid(count):
    """(columns, rows) for a number of cards."""
    if count <= 3:
        return max(1, count), 1
    if count == 4:
        return 2, 2
    if count <= 6:
        return 3, 2
    if count <= 8:
        return 4, 2
    return 4, 3


def card_boxes(count, staff=False):
    """Card centres and size, in layout units. Cards are as tall as their content."""
    cols, rows = grid(count)
    x1, y1, x2, y2 = BODY
    gap = 8
    w = min(170, ((x2-x1)-gap*(cols-1))/cols)
    content = w+round(max(8, min(16, w*.11)))+12+(13 if staff else 0)
    h = min(content, ((y2-y1)-gap*(rows-1))/rows)
    total_w = w*cols+gap*(cols-1)
    total_h = h*rows+gap*(rows-1)
    left, top = x1+((x2-x1)-total_w)/2, y1+((y2-y1)-total_h)/2
    boxes = []
    for i in range(count):
        r, c = divmod(i, cols)
        in_row = min(cols, count-r*cols)
        row_left = x1+((x2-x1)-(w*in_row+gap*(in_row-1)))/2 if in_row < cols else left
        boxes.append((row_left+c*(w+gap)+w/2, top+r*(h+gap)+h/2))
    return boxes, w, h


def normalized_positions(config):
    members = config.get('members', [])[:MAX_CARDS]
    boxes, _, _ = card_boxes(len(members), any(m.get('role') in STAFF_ROLES for m in members))
    defaults = dict(HEAD_POSITIONS, **{f'card_{i}': box for i, box in enumerate(boxes)})
    return safe_positions({}, defaults)


def _card(member, config, w, h, font_bytes, s, blink=False, bob=False, frame=None, index=0, beat=0):
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    pink = rgb(config.get('pink', '#F268A8')); cyan = rgb(config.get('cyan', '#79DCF7'))
    white = rgb(config.get('white', '#F6F4FC')); yellow = rgb(config.get('yellow', '#FFC963'))
    panel = STYLE.get(config.get('preset_id', 'crt'), STYLE['crt'])['panel']
    staff = member.get('role') in STAFF_ROLES
    image = Image.new('RGBA', (round(w*s), round(h*s)))
    d = ScaledDraw(image, s)
    label_h = 13 if staff else 0
    name_size = round(max(8, min(16, w*.11)))
    text_h = name_size+6+label_h
    side = min(w-8, h-text_h-10)
    ax, ay = (w-side)/2, 4
    # Card and avatar tile.
    d.rectangle((0, 0, w-1, h-1), fill=(*[min(255, c+14) for c in panel], 235), outline=(*cyan, 170), width=1)
    tile = Image.new('RGBA', (round(side*s), round(side*s)))
    import pixel_character
    import variety
    scene_name = variety.scene_for(config.get('group', ''), config.get('sprite_scene', 'sfumato'))
    if scene_name == 'sfumato':
        td = ScaledDraw(tile, s)
        for i in range(12):  # soft vertical gradient behind the face
            t = i/11
            col = tuple(round(c*(.18+.22*(1-t))+p*(1-(.18+.22*(1-t)))) for c, p in zip(cyan, panel))
            td.rectangle((0, side*i/12, side, side*(i+1)/12+1), fill=(*col, 255))
    else:
        backdrop = pixel_character.scene(scene_name, pixel_character.style_for(config.get('preset_id', 'crt')))
        tile.paste(backdrop.resize(tile.size, Image.Resampling.NEAREST), (0, 0))
    pose = variety.pose_for(member, index, config.get('sprite_pose', 'ferma'))
    picture = pixel_character.picture(member, config.get('preset_id', 'crt'), blink, frame, pose, beat)
    factor = max(1, int(side*s//picture.width))
    big = picture.resize((picture.width*factor, picture.height*factor), Image.Resampling.NEAREST)
    tile.alpha_composite(big, ((tile.width-big.width)//2, tile.height-big.height-(factor if bob else 0)))
    image.alpha_composite(tile, (round(ax*s), round(ay*s)))
    d.rectangle((ax, ay, ax+side, ay+side), outline=(*cyan, 255), width=1.2)
    # Number badge and captain mark.
    number = int(member.get('number') or 0)
    if number and not staff:
        bw = max(16, min(30, side*.24))
        d.rectangle((ax, ay, ax+bw, ay+bw*.78), fill=(*pink, 255))
        from render_utils import contrast_ink
        n = text_image(str(number), style, round(bw*.52), contrast_ink(pink, (12, 10, 18)), bw-4, font_bytes, s, round(bw*.6))
        if n:
            image.alpha_composite(n, (round((ax+bw/2)*s-n.width/2), round((ay+bw*.39)*s-n.height/2)))
    if member.get('captain'):
        cw = max(14, min(24, side*.2))
        d.rectangle((ax+side-cw, ay, ax+side, ay+cw*.8), fill=(*yellow, 255))
        from render_utils import contrast_ink
        cap = text_image('C', style, round(cw*.55), contrast_ink(yellow, (12, 10, 18)), cw-2, font_bytes, s, round(cw*.6))
        if cap:
            image.alpha_composite(cap, (round((ax+side-cw/2)*s-cap.width/2), round((ay+cw*.4)*s-cap.height/2)))
    # Name and staff role.
    name_y = ay+side+4+name_size/2+1
    name = text_image(str(member.get('name', '')).upper(), style, name_size, white, w-6, font_bytes, s, round(name_size+2))
    if name:
        image.alpha_composite(name, (round(w/2*s-name.width/2), round(name_y*s-name.height/2)))
    if staff:
        role = text_image(STAFF_ROLES[member['role']], style, 8, cyan, w-6, font_bytes, s, 9)
        if role:
            image.alpha_composite(role, (round(w/2*s-role.width/2), round((name_y+name_size/2+7)*s-role.height/2)))
    return image


def get_layers(config, home_logo, away_logo=None, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    pink = rgb(config.get('pink', '#F268A8')); white = rgb(config.get('white', '#F6F4FC'))
    layers = [Layer('logo', LAYER_NAMES['logo'], clean_logo(home_logo, 40, config.get('remove_white', True), s))]
    title = _decorate_text(text_image(config.get('slide_title', 'CONVOCATI'), style, 24, white, 280, font_bytes, s, 24), s)
    if title:
        layers.append(Layer('title', LAYER_NAMES['title'], title))
    sub = _decorate_text(text_image(config.get('slide_subtitle', ''), style, 10, pink, 280, font_bytes, s, 13), s)
    if sub:
        layers.append(Layer('subtitle', LAYER_NAMES['subtitle'], sub))
    members = config.get('members', [])[:MAX_CARDS]
    _, w, h = card_boxes(len(members), any(m.get('role') in STAFF_ROLES for m in members))
    for i, member in enumerate(members):
        layer = Layer(f'card_{i}', str(member.get('name', '')), _card(member, config, w, h, font_bytes, s, index=i), sequence=i)
        # Idle frames for the video: blink, wink, smile, raised brows, glint on the
        # glasses (whatever suits the sprite) and the avatar one sprite pixel up.
        import pixel_character
        look = pixel_character.sanitize(member.get('look')) if member.get('look') else None
        frames = pixel_character.frames_for(look) if look else ('blink',)
        layer.alive = {f: _card(member, config, w, h, font_bytes, s, frame=f, index=i) for f in frames}
        import variety
        if look and variety.pose_for(member, i, config.get('sprite_pose', 'ferma')) in pixel_character.MOVING_POSES:
            layer.alive['pose'] = _card(member, config, w, h, font_bytes, s, index=i, beat=1)
        else:
            layer.alive['bob'] = _card(member, config, w, h, font_bytes, s, bob=True, index=i)
        layer.group = config.get('group', '')
        layer.captain = bool(member.get('captain'))
        layers.append(layer)
    return layers


def scene(config, home_logo, away_logo=None, font_bytes=None, render_scale=2):
    import themes
    from crt_common import finish
    s = checked_scale(render_scale)
    config = themes.effective(config)
    return finish((background(config, 'classifica', s), get_layers(config, home_logo, away_logo, font_bytes, s),
                   normalized_positions(config)), config, 'reparto')


def png_bytes(config, home_logo, away_logo=None, font_bytes=None, format='Story 9:16', scale=2, supersample=2):
    return export_png(scene, config, home_logo, away_logo, font_bytes, format, scale, supersample)


def render_video(config, home_logo, away_logo, path, font_bytes=None, fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None):
    return export_video(scene, config, home_logo, away_logo, path, font_bytes, fps, duration, format, scale, progress_callback)


# --- From the Convocati editor and the squad to slides ----------------------

def _key(name):
    return ' '.join(str(name).upper().split())


def slides(convocati, squad):
    """[(group, slide_config)] for every department with someone in it.

    Players come from the active Convocati list (role from that list, or the
    squad if it is '-'); avatars from the squad; staff from the squad."""
    by_name = {_key(p['name']): p for p in squad or []}
    active = [p for p in convocati.get('roster', [])[:convocati.get('roster_count', 0)]
              if str(p.get('name', '')).strip() and not str(p['name']).startswith('GIOCATORE ')]
    buckets = {g: [] for g, _ in GROUPS}
    for p in active:
        known = by_name.get(_key(p['name']), {})
        role = p.get('role') if p.get('role') in ('P', 'D', 'C', 'A') else known.get('role')
        if role in ('P', 'D', 'C', 'A'):
            buckets[role].append(dict(name=p['name'], number=p.get('number', 0), role=role,
                                      captain=bool(p.get('captain')), avatar=known.get('avatar', ''),
                                      look=known.get('look')))
    staff = [p for p in squad or [] if p.get('role') in STAFF_ROLES]
    staff.sort(key=lambda p: (p['role'] != 'ALL', p['name']))
    buckets['STAFF'] = [dict(name=p['name'], number=0, role=p['role'], captain=False, avatar=p.get('avatar', ''),
                             look=p.get('look')) for p in staff]
    opponent = str(convocati.get('opponent', '')).strip()
    match = ' / '.join(x for x in ('VS '+opponent if opponent and opponent != 'AVVERSARI' else '',
                                   str(convocati.get('date', '')) if 'GG' not in str(convocati.get('date', '')) else '') if x)
    out = []
    for group, title in GROUPS:
        members = buckets[group][:MAX_CARDS]
        if not members:
            continue
        config = copy.deepcopy(convocati)
        config['slide_title'] = title
        config['slide_subtitle'] = ('ALLENATORE E DIRIGENTI' if group == 'STAFF' else
                                    ('CONVOCATI / '+match) if match else 'CONVOCATI')
        config['members'] = members
        config['group'] = group
        out.append((group, config))
    return out


def unassigned(convocati, squad):
    """Names in the Convocati list without a department."""
    by_name = {_key(p['name']): p for p in squad or []}
    names = []
    for p in convocati.get('roster', [])[:convocati.get('roster_count', 0)]:
        if not str(p.get('name', '')).strip() or str(p['name']).startswith('GIOCATORE '):
            continue
        role = p.get('role') if p.get('role') in ('P', 'D', 'C', 'A') else by_name.get(_key(p['name']), {}).get('role')
        if role not in ('P', 'D', 'C', 'A'):
            names.append(p['name'])
    return names
