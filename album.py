"""L'album (3.9): the whole squad as a collection of cards.

Every player gets his card; the rarity grows with the MVP awards collected
during the season (1 rara, 2 epica, 3+ leggendaria), so the album changes
week after week. Stats on each card: MVP awards, season goals, shirt number.
"""
from __future__ import annotations

import io
import math
import zipfile

from PIL import Image

import cards
from card_video import Backdrop, finish

LAYOUTS = {'Story 9:16': dict(h=960, title=176, sub=212, top=250, bottom=900),
           'Post 4:5': dict(h=675, title=52, sub=86, top=112, bottom=655),
           'Post 1:1': dict(h=540, title=42, sub=74, top=98, bottom=526)}
PLAYER_ROLES = ('P', 'D', 'C', 'A')


def rarity_for(mvp_count):
    return 'leggenda' if mvp_count >= 3 else 'epica' if mvp_count == 2 else 'rara' if mvp_count == 1 else 'base'


def mvp_counts(mvps):
    counts = {}
    for item in mvps or []:
        name = str(item.get('name', '')).strip().upper()
        if name:
            counts[name] = counts.get(name, 0)+1
    return counts


def members_for(squad, mvps=None, scorers=None, staff=True, season='2026/27', team='FLAMINGOS'):
    """Card specs for the album, in lineup order; numbered like a collection (01/16...)."""
    counts = mvp_counts(mvps)
    goals = {str(s.get('name', '')).upper(): int(s.get('goals') or 0) for s in scorers or []}
    order = {'P': 0, 'D': 1, 'C': 2, '-': 2, 'A': 3, 'ALL': 4, 'DIR': 5}
    people = [p for p in squad if p.get('role') in PLAYER_ROLES+('-',) or (staff and p.get('role') == 'ALL')]
    people.sort(key=lambda p: (order.get(p.get('role'), 9), int(p.get('number') or 99) or 99, p['name']))
    out = []
    for i, p in enumerate(people):
        name = str(p['name']).upper()
        n = counts.get(name, 0)
        if p.get('role') == 'ALL':
            stats = [('RUOLO', 'MISTER'), ('MVP', str(n)), ('STAGIONE', season[-5:])]
        else:
            stats = [('MVP', str(n)), ('GOL', str(goals.get(name, 0))), ('MAGLIA', f"#{p['number']}" if p.get('number') else '-')]
        out.append(dict(name=name, number=p.get('number', 0), role=p.get('role') if p.get('role') in cards.ROLES else 'C',
                        look=p.get('look'),
                        avatar=p.get('avatar', ''), edition='base', rarity=rarity_for(n), stats=stats,
                        serial=(i+1, len(people)), season=season, team=team, captain=bool(p.get('captain'))))
    return out


def grid(n, width, height, gap=10):
    """(columns, card width) that make the biggest cards fitting the area."""
    best = (1, 0.0)
    for cols in range(2, 8):
        rows = math.ceil(n/cols)
        w = min((width-gap*(cols-1))/cols, ((height-gap*(rows-1))/rows)*cards.W/cards.H)
        if w > best[1]:
            best = (cols, w)
    return best


def poster(members, logo=None, format='Story 9:16', scale=2, title='LA COLLEZIONE', season='2026/27', team='FLAMINGOS'):
    """The album page (PIL RGB)."""
    format = format if format in LAYOUTS else 'Story 9:16'
    L = LAYOUTS[format]
    u = float(scale)
    size = (int(540*u), int(L['h']*u))
    backdrop = Backdrop(size, u, size[1]*.45, L['h']*u*.93, L['title']*u, cards.PINK, sun=False, dust=24, phases=1)
    canvas = backdrop.canvas(0.0, .45)
    area_w, area_h = 500, L['bottom']-L['top']
    gap = 10
    if members:
        cols, w = grid(len(members), area_w, area_h)
        h = w*cards.H/cards.W
        rows = math.ceil(len(members)/cols)
        slack = area_h-(rows*h+(rows-1)*gap)
    else:
        cols = w = h = rows = 0
        slack = 0
    shift = slack*.4                      # the title comes down with the cards: one block, centred
    t = cards.text(title, 'black', 38, cards.WHITE, u, max_width=480, shadow=(0, 3, 6, 200))
    canvas.paste(t, (int(size[0]/2-t.width/2), int((L['title']+shift)*u-t.height/2)), t)
    special = sum(1 for m in members if m['rarity'] != 'base')
    sub = cards.text(f'FIGURINE {team}  ·  {season}  ·  {len(members)} CARTE'+(f'  ·  {special} SPECIALI' if special else ''),
                     'heavy', 10, cards.YELLOW, u, max_width=500, tracking=2)
    canvas.paste(sub, (int(size[0]/2-sub.width/2), int((L['sub']+shift)*u-sub.height/2)), sub)
    if not members:
        return canvas.convert('RGB')
    top = L['top']+shift
    for i, m in enumerate(members):
        r, c = divmod(i, cols)
        in_row = min(cols, len(members)-r*cols)
        left = 270-(in_row*w+(in_row-1)*gap)/2
        cx = left+c*(w+gap)+w/2
        cy = top+r*(h+gap)+h/2
        card = cards.Card(m, w/cards.W*u, logo)
        img = card.render(-6+(i % 3)*6, 3)
        shadow = Image.new('RGBA', img.size, (0, 0, 0, 0))
        shadow.putalpha(img.getchannel('A').point(lambda v: v*110//255))
        canvas.paste(shadow, (int(cx*u-img.width/2+3*u), int(cy*u-img.height/2+4*u)), shadow)
        canvas.paste(img, (int(cx*u-img.width/2), int(cy*u-img.height/2)), img)
    arr = finish(canvas, 5.0, 99.0, backdrop.scan_step)
    return Image.fromarray(arr, 'RGB')


def png_bytes(members, logo=None, format='Story 9:16', scale=2, **kw):
    out = io.BytesIO()
    poster(members, logo, format, scale, **kw).save(out, 'PNG', compress_level=5)
    return out.getvalue()


def zip_bytes(members, logo=None, height=1000):
    """Every card as a transparent PNG, numbered like the collection."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for m in members:
            a, b = m.get('serial') or (0, 0)
            archive.writestr(f"{int(a):02d}_{m['name'].lower().replace(' ', '_')}.png", cards.card_png(m, logo, height))
    return buffer.getvalue()
