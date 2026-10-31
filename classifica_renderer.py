"""Classifica: the group standings on any CRT preset, with our team highlighted."""
from __future__ import annotations

from PIL import Image

from render_utils import ScaledDraw, checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, rgb
from matchday_renderer import _decorate_text
import title_fx
from crt_presets import background, STYLE, PRESETS
from crt_common import compose, export_png, export_video
from classifica_data import MAX_TEAMS

TABLE_W, TABLE_H = 364, 287
DEFAULT_POSITIONS = {'logo': (118, 346), 'title': (294, 337), 'subtitle': (294, 360), 'table': (270, 527)}
LAYER_NAMES = {'logo': 'Stemma', 'title': 'Titolo classifica', 'subtitle': 'Girone e giornata', 'table': 'Tabella'}
DETAILS = ('Completa', 'Compatta')
COLUMNS = {
    'Completa': (('G', 'g', 23), ('V', 'v', 23), ('N', 'n', 23), ('P', 'p', 23), ('GF', 'gf', 26), ('GS', 'gs', 26), ('PT', 'pt', 32)),
    'Compatta': (('G', 'g', 30), ('DR', 'dr', 38), ('PT', 'pt', 38)),
}


def normalized_positions(config):
    return safe_positions(config, DEFAULT_POSITIONS)


def is_ours(team, ours):
    a, b = str(team).strip().upper(), str(ours).strip().upper()
    return bool(a and b) and (b in a or a in b)


def active_rows(config):
    count = max(2, min(MAX_TEAMS, int(config.get('team_count', 8))))
    rows = [r for r in config.get('standings', [])[:count] if str(r.get('team', '')).strip()]
    return rows


def last_week(config):
    """(config with our team back at last week's place, after->before row map), or None.

    For the video: the table enters in last week's order, then our row moves.
    Points and goals are this week's (only the order of last week is known)."""
    rows = active_rows(config)
    ours = config.get('our_team', 'FLAMINGOS')
    index = next((i for i, r in enumerate(rows) if is_ours(r.get('team', ''), ours)), None)
    try:
        prev = int(config.get('prev_pos', 0) or 0)
    except (TypeError, ValueError):
        prev = 0
    if index is None or not 1 <= prev <= len(rows) or prev == index+1:
        return None
    order = rows[:index]+rows[index+1:]
    order.insert(prev-1, rows[index])
    ids = [id(r) for r in order]
    mapping = [ids.index(id(r)) for r in rows]
    old = [dict(r, pos=i+1) for i, r in enumerate(order)]
    return dict(config, standings=old, team_count=len(old), prev_pos=0), mapping


def zone_of(position, config):
    """'promo' for direct promotion, 'playoff' for the play-off places, else None."""
    if not config.get('show_zones', True):
        return None
    promo = max(0, int(config.get('promo_count', 3)))
    playoff = max(0, int(config.get('playoff_count', 2)))
    if position <= promo:
        return 'promo'
    if position <= promo+playoff:
        return 'playoff'
    return None


def _value(row, key):
    if key == 'dr':
        diff = int(row.get('gf', 0))-int(row.get('gs', 0))
        return f'+{diff}' if diff > 0 else str(diff)
    return str(int(row.get(key, 0)))


def table_image(config, font_bytes=None, s=1):
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    preset = config.get('preset_id', 'crt')
    panel = STYLE.get(preset, STYLE['crt'])['panel']
    pink = rgb(config.get('pink', '#F268A8')); cyan = rgb(config.get('cyan', '#79DCF7'))
    white = rgb(config.get('white', '#F6F4FC')); yellow = rgb(config.get('yellow', '#FFC963'))
    dim = tuple(round(w*.78+p*.22) for w, p in zip(white, panel))
    from render_utils import contrast_ink
    ink = contrast_ink(pink)
    rows = active_rows(config)
    columns = COLUMNS.get(config.get('table_detail', 'Completa'), COLUMNS['Completa'])
    size = int(config.get('table_size', 10))
    image = Image.new('RGBA', (TABLE_W*s, TABLE_H*s))
    d = ScaledDraw(image, s)
    header_h = 18
    zones = {'promo': rgb(config.get('promo_color', '#5BE6A4')), 'playoff': rgb(config.get('playoff_color', '#B98CFF'))}
    show_legend = bool(config.get('show_zones', True)) and any(zone_of(int(r.get('pos', i+1)), config) for i, r in enumerate(rows))
    legend_h = 15 if show_legend else 0
    row_h = min(33, (TABLE_H-header_h-legend_h-2)/max(1, len(rows)))
    text_h = max(6, min(size+2, row_h-5))
    stats_w = sum(w for _, _, w in columns)
    team_x, team_w = 30, TABLE_W-30-stats_w-6

    def cell(value, color, x, y, width, align='center', h=None):
        im = text_image(value, style, size, color, width, font_bytes, s, h or text_h)
        if not im:
            return
        if align == 'left':
            left = round(x*s)
        else:
            left = round((x+width/2)*s-im.width/2)
        image.alpha_composite(im, (left, round(y*s-im.height/2)))

    # Column header.
    d.rectangle((0, 0, TABLE_W, header_h-3), fill=(*cyan, 46))
    cell('#', cyan, 0, header_h/2-1, 26, h=9)
    cell('SQUADRA', cyan, team_x, header_h/2-1, team_w, 'left', 9)
    x = TABLE_W-stats_w
    for label, _, width in columns:
        cell(label, yellow if label == 'PT' else cyan, x, header_h/2-1, width, h=9)
        x += width
    ours = config.get('our_team', 'FLAMINGOS')
    ours_index = None
    for i, row in enumerate(rows):
        top = header_h+i*row_h
        mid = top+row_h/2
        highlight = is_ours(row.get('team', ''), ours)
        pos = int(row.get('pos', i+1))
        zone = zone_of(pos, config)
        if highlight:
            ours_index = i if ours_index is None else ours_index
            d.rectangle((0, top+1, TABLE_W, top+row_h-1), fill=(*pink, 245))
        elif zone:
            d.rectangle((0, top+1, TABLE_W, top+row_h-1), fill=(*zones[zone], 38))
        elif i % 2 == 0:
            d.rectangle((0, top+1, TABLE_W, top+row_h-1), fill=(255, 255, 255, 16))
        if zone:
            # Zone colour on the position badge, also on our own pink row.
            d.rectangle((0, top+1, 3, top+row_h-1), fill=(*zones[zone], 255))
            d.rectangle((5, top+3, 26, top+row_h-3), fill=(*zones[zone], 255))
        cell(str(pos), contrast_ink(zones[zone]) if zone else (ink if highlight else cyan), 2, mid, 28)
        cell(str(row.get('team', '')).upper(), ink if highlight else white, team_x, mid, team_w, 'left')
        x = TABLE_W-stats_w
        for label, key, width in columns:
            color = ink if highlight else (yellow if key == 'pt' else dim)
            cell(_value(row, key), color, x, mid, width)
            x += width
        if not highlight and i < len(rows)-1:
            d.line((4, top+row_h, TABLE_W-4, top+row_h), fill=(*cyan, 30), width=.5)
    if show_legend:
        y = TABLE_H-legend_h/2
        x = 4
        for zone, label in (('promo', config.get('promo_label', 'PROMOZIONE')),
                            ('playoff', config.get('playoff_label', 'SPAREGGIO'))):
            if zone == 'promo' and not int(config.get('promo_count', 3)) or zone == 'playoff' and not int(config.get('playoff_count', 2)):
                continue
            d.rectangle((x, y-4, x+8, y+4), fill=(*zones[zone], 255))
            im = text_image(str(label).upper(), style, 8, white, 150, font_bytes, s, 8)
            if im:
                image.alpha_composite(im, (round((x+13)*s), round(y*s-im.height/2)))
                x += 13+im.width/s+16
    # Arrow with the places gained or lost since last week.
    prev = int(config.get('prev_pos', 0) or 0)
    if ours_index is not None and prev:
        now = int(rows[ours_index].get('pos', ours_index+1))
        if prev == now:   # same place as last week: a small yellow =
            top = header_h+ours_index*row_h
            mid = top+row_h/2
            ax = team_x+team_w-16
            d.rectangle((ax-3, top+3, ax+14, top+row_h-3), fill=(9, 11, 22, 255))
            cell('=', (255, 201, 99), ax-3, mid, 17)
        if prev != now:
            up = prev > now
            colour = (91, 230, 164) if up else (255, 107, 120)
            top = header_h+ours_index*row_h
            mid = top+row_h/2
            ax = team_x+team_w-24
            size_a = min(5, row_h*.22)
            d.rectangle((ax-3, top+3, ax+22, top+row_h-3), fill=(9, 11, 22, 255))
            if up:
                d.polygon([(ax, mid+size_a*.7), (ax+size_a, mid-size_a*.7), (ax+2*size_a, mid+size_a*.7)], fill=(*colour, 255))
            else:
                d.polygon([(ax, mid-size_a*.7), (ax+size_a, mid+size_a*.7), (ax+2*size_a, mid-size_a*.7)], fill=(*colour, 255))
            cell(str(abs(prev-now)), colour, ax+2*size_a+1, mid, 22-2*size_a, 'left')
    edges = [(0, header_h)]+[(header_h+i*row_h, header_h+(i+1)*row_h) for i in range(len(rows))]
    if show_legend:
        edges.append((TABLE_H-legend_h, TABLE_H))
    image.info['row_edges'] = edges
    if ours_index is not None:
        image.info['ours'] = ours_index+1          # index in row_edges (0 is the header)
        if prev and 1 <= prev <= len(rows):
            image.info['prev'] = prev
        image.info['first'] = int(rows[ours_index].get('pos', ours_index+1)) == 1
        # Points to the team above (or our lead over the second), for the video.
        if len(rows) > 1:
            other = ours_index-1 if ours_index > 0 else 1
            points = abs(int(rows[other].get('pt', 0) or 0)-int(rows[ours_index].get('pt', 0) or 0))
            image.info['gap'] = dict(ours=ours_index+1, other=other+1, points=points, lead=ours_index == 0)
    return image


def get_layers(config, home_logo, away_logo=None, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    style = config.get('text_style', config.get('font_choice', 'CRT Terminal'))
    pink = rgb(config.get('pink', '#F268A8')); white = rgb(config.get('white', '#F6F4FC'))
    layers = [Layer('logo', LAYER_NAMES['logo'], clean_logo(home_logo, config.get('logo_size', 40), config.get('remove_white', True), s))]
    title = title_fx.title(text_image(config.get('title', 'CLASSIFICA'), style, config.get('title_size', 24), white, 280, font_bytes, s, 24), config, s)
    if title:
        layers.append(Layer('title', LAYER_NAMES['title'], title))
    parts = [str(config.get(k, '')).strip() for k in ('group', 'round_label')]
    subtitle = ' / '.join(p for p in parts if p)
    sub = _decorate_text(text_image(subtitle, style, config.get('info_size', 10), pink, 280, font_bytes, s, 13), s)
    if sub:
        layers.append(Layer('subtitle', LAYER_NAMES['subtitle'], sub))
    table = Layer('table', LAYER_NAMES['table'], table_image(config, font_bytes, s))
    previous = last_week(config)
    if previous:
        table.before = table_image(previous[0], font_bytes, s)
        table.image.info['before_rows'] = previous[1]
        # In the video the badge on the right tells the change: the row itself stays clean.
        table.clean = table_image(dict(config, prev_pos=0), font_bytes, s)
        table.clean.info.update(table.image.info)
    layers.append(table)
    return layers


def scene(config,home_logo,away_logo=None,font_bytes=None,render_scale=2):
    import themes
    from crt_common import finish
    s=checked_scale(render_scale)
    config=themes.effective(config)
    import layouts
    return finish((background(config, layouts.panel_key('classifica', 'Classifica', config), s), get_layers(config, home_logo, away_logo, font_bytes, s), normalized_positions(config)),config,'classifica')


def png_bytes(config, home_logo, away_logo=None, font_bytes=None, format='Story 9:16', scale=2, supersample=2):
    return export_png(scene, config, home_logo, away_logo, font_bytes, format, scale, supersample)


def render_video(config, home_logo, away_logo, path, font_bytes=None, fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None):
    return export_video(scene, config, home_logo, away_logo, path, font_bytes, fps, duration, format, scale, progress_callback)
