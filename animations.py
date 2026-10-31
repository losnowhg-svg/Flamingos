"""Richer CRT animations for videos ("Retro" style).

Entrances by role: text typed like a terminal, crests with an RGB glitch,
Matchday crests that crash into each other, a slot-machine Full Time score,
tables filled row by row, department cards that dive, drop or dash in.

Strong moments on top: screen shake and flash on impacts, a GOAL! burst,
STAGE CLEAR / DRAW GAME / GAME OVER banners, our standings row climbing,
a crown for first place, a shine over the captain. Living details: blinking
and bobbing avatars, the NEXT match flashing, a VHS REC dot, time code and
tracking glitches. Optional intro (PRESS START), CRT power-on, ending
(power-off or seamless loop) and beat-snapped timing for the chiptune.

The scene functions annotate their layers with prepare(); the compose
functions of each renderer hand animated frames to compose() here. Still
images (PNG, editor preview) are never affected.
"""
from __future__ import annotations

import copy
import math
from functools import lru_cache

import numpy as np
from PIL import Image

import motion
import themes

STYLES = ('Retro', 'Classica')
ENDINGS = ('nessuno', 'spegnimento', 'loop')+motion.NEW_ENDINGS
POWER_ON = .55
INTRO = 1.6
BEAT = .25            # an eighth note at 120 bpm: the chiptune grid
ROW_STEP = .17

TIMELINES = {
    'matchday': {'title': .2, 'date': .6, 'home_logo': 1.25, 'away_logo': 1.25, 'vs': 1.72,
                 'home_name': 2.4, 'away_name': 2.7, 'kickoff': 3.2, 'venue': 3.55},
    'fulltime': {'title': .2, 'details': .6, 'home_logo': 1.0, 'away_logo': 1.25, 'home_name': 1.6,
                 'away_name': 1.8, 'score': 2.1, 'penalties': 3.6, 'result': 3.7,
                 'home_scorers': 4.0, 'away_scorers': 4.3},
    'convocati': {'logo': .15, 'title': .4, 'team': .8, 'match': 1.05},
    'classifica': {'logo': .15, 'title': .4, 'subtitle': .85, 'table': 1.15},
    'calendario': {'logo': .15, 'title': .4, 'subtitle': .85, 'table': 1.15},
    'reparto': {'logo': .15, 'title': .4, 'subtitle': .8},
    'sponsor': {'title': .3, 'subtitle': .7, 'logo': 1.1, 'name': 1.9, 'line': 2.4},
    'wrapped': {'logo': .15, 'title': .35, 'subtitle': .7, 'big': 1.0, 'label': 1.9, 'bar': 2.2, 'left': 1.2,
                'right': 1.5, 'list': 1.1, 'line1': 2.5, 'line2': 2.8},
}
CARD_ENTRANCE = {'P': 'dive', 'D': 'drop', 'C': 'glitch', 'A': 'dash', 'STAFF': 'pop'}


def _kind(layer, kind):
    if kind == 'matchday' and layer.id in ('home_logo', 'away_logo'):
        return 'slide_left' if layer.id == 'home_logo' else 'slide_right'
    if layer.id.startswith('card_'):
        return CARD_ENTRANCE.get(getattr(layer, 'group', ''), 'glitch')
    if layer.id in ('logo', 'home_logo', 'away_logo'):
        return 'glitch'
    if layer.id == 'vs':
        return 'pop'
    if layer.id in ('score', 'big'):
        if getattr(layer, 'replay', None):
            return 'replay'
        return 'count' if getattr(layer, 'variants', None) else 'pop'
    if layer.id == 'result':
        return 'pop'
    if layer.id == 'table':
        return 'rows' if layer.image.info.get('row_edges') else 'type'
    if layer.id in ('bar', 'left', 'right', 'list'):
        return 'glitch' if layer.id == 'list' else 'pop'
    return 'type'


def _duration(layer, kind):
    if kind == 'type':
        h = max(1, layer.image.height)
        chars = layer.image.width/(h*.62)
        return max(.22, min(.8, chars*.035))
    if kind in ('glitch', 'dive'):
        return .6
    if kind in ('slide_left', 'slide_right', 'drop'):
        return .42
    if kind == 'dash':
        return .35
    if kind == 'pop':
        return .45
    if kind == 'count':
        return len(layer.variants)*.12+.1
    if kind == 'replay':
        import focus
        return focus.replay_length(layer.replay)
    if kind in ('pixelate', 'bounce', 'wipe', 'zoom'):
        return {'pixelate': .55, 'bounce': .75, 'wipe': .5, 'zoom': .5}[kind]
    if kind == 'rows':
        return len(layer.image.info['row_edges'])*ROW_STEP+.25
    return .46


def prepare(prepared, config, kind):
    """Mark layers with entrance kind, start and duration; store the video options."""
    base, layers, positions = prepared
    info = base.info
    info['anim'] = config.get('animation') if config.get('animation') in STYLES else 'Retro'
    info['power_on'] = bool(config.get('power_on', True))
    info['intro'] = bool(config.get('intro', False))
    import variety
    info['intro_style'] = variety.intro_style(config, kind)
    info['level'] = int(config.get('season_round', 1) or 1)
    if kind in ('matchday', 'fulltime'):
        away_us = config.get('our_side', 'Casa') == 'Ospiti'
        home, away = str(config.get('home_name', 'FLAMINGOS')), str(config.get('away_name', 'AVVERSARI'))
        info['intro_names'] = (away, home) if away_us else (home, away)
    info['details'] = bool(config.get('details', True))
    info['music'] = bool(config.get('music', False))
    info['ending'] = config.get('ending') if config.get('ending') in ENDINGS else 'nessuno'
    info['kind'] = kind
    info.setdefault('theme', '')
    import frames
    frames.store(info, config)
    info['highlight'] = config.get('highlight', 'auto')
    info['our_side'] = config.get('our_side', 'Casa')
    stakes = config.get('stakes')
    info['stakes'] = stakes if kind == 'matchday' and isinstance(stakes, dict) and {'home', 'away'} <= set(stakes) else None
    info['camera'] = motion.camera(config)
    info['fx'] = motion.ambient(config)
    info['crest'] = _crest(layers, config, kind)
    family = motion.entrance(config)
    info['music_track'] = variety.music_track(config, kind, info.get('outcome'), info.get('theme', ''))
    timeline = TIMELINES.get(kind, {})
    last = max(timeline.values(), default=0)
    players = [l for l in layers if l.id.startswith('player_')]
    for layer in layers:
        layer.anim = motion.override(layer, _kind(layer, kind), family)
        if layer.id in timeline:
            layer.start = timeline[layer.id]
        elif layer.id.startswith('player_'):
            layer.start = 1.4+max(0, layer.sequence)*.13
        elif kind == 'convocati':
            layer.start = 1.6+len(players)*.13+{'legend': 0, 'meeting': .25, 'venue': .5}.get(layer.id, .7)
        elif layer.id.startswith('card_'):
            layer.start = 1.1+max(0, layer.sequence)*.28
        else:
            last += .3
            layer.start = last
        if info['music']:
            layer.start = round(layer.start/BEAT)*BEAT
        layer.dur = _duration(layer, layer.anim)
    score = next((l for l in layers if l.id == 'score' and l.anim == 'replay'), None)
    if score is not None:   # the goal replay takes longer than the slot machine: what follows waits for it
        extra = score.dur-(len(getattr(score, 'variants', [])) or 1)*.12-.1
        for layer in layers:
            if layer is not score and layer.start > score.start:
                layer.start += max(0.0, extra)
    if info['music']:
        sync_to_music(prepared)
    return prepared


DROP = 4.0          # every track has two bars of intro, then the drop (music.py); a bar lasts 2 s
MUSIC_BAR = 2.0


def _anchor(prepared):
    """(layer, seconds after its start) of the scene's strongest moment, or None."""
    layers = prepared[1]
    by_id = {l.id: l for l in layers}
    offset = _offset(prepared)
    owners = {'impact': None, 'goal': 'score', 'climb': 'table', 'crown': 'table'}
    for at, kind, data in moments(prepared):
        if kind not in owners:
            continue
        if kind == 'impact':
            owner = 'home_logo' if prepared[0].info.get('kind') == 'matchday' and 'home_logo' in by_id else None
            if owner is None and 'score' in by_id and getattr(by_id['score'], 'anim', '') in ('count', 'replay'):
                owner = 'score'
            if owner is None:
                continue
        else:
            owner = owners[kind]
        layer = by_id.get(owner)
        if layer is not None:
            return layer, at-offset-layer.start
    for lid in ('table', 'big'):
        if lid in by_id:
            return by_id[lid], 0.0
    firsts = [l for l in layers if l.id.startswith(('card_', 'player_'))]
    if firsts:
        return min(firsts, key=lambda l: l.start), 0.0
    return None


def sync_to_music(prepared):
    """Move the timeline so the strongest moment lands on the drop (4 s) or on the next downbeat."""
    found = _anchor(prepared)
    if not found:
        return
    layer, extra = found
    offset = _offset(prepared)
    old = layer.start
    moment = offset+old+extra
    target = DROP
    while target < moment-.3:
        target += MUSIC_BAR

    def valid(at):
        start = at-offset-extra
        return start >= 0 and ((old > 0 and .6 <= start/old <= 2.6) or (old == 0 and start <= 1.5))
    if not valid(target):
        target = MUSIC_BAR        # too early for the drop: the first downbeat of the intro
        if target < moment-.3 or not valid(target):
            return
    new = target-offset-extra
    factor = new/old if old > 0 else 1.0
    for item in prepared[1]:
        if item is layer:
            continue
        if item.start == old:            # starts together with the anchor (the other crest)
            item.start = new
        elif item.start < old:
            item.start = round(item.start*factor/BEAT)*BEAT if old > 0 else item.start+new
        else:
            item.start = round((new+item.start-old)/BEAT)*BEAT
    layer.start = new
    prepared[0].info['drop_at'] = target


def _crest(layers, config, kind):
    """Our crest, for the logo intro (the opponents' never)."""
    by_id = {l.id: l for l in layers}
    if kind in ('matchday', 'fulltime'):
        layer = by_id.get('away_logo' if config.get('our_side', 'Casa') == 'Ospiti' else 'home_logo')
    elif kind == 'sponsor':
        layer = None
    else:
        layer = by_id.get('logo')
    return layer.image if layer is not None else None


def focus_treatment(info, kind):
    import focus
    return focus.treatment(info, kind)


def rich(prepared):
    return prepared[0].info.get('anim') == 'Retro' and all(hasattr(l, 'start') for l in prepared[1])


def _offset(prepared):
    info = prepared[0].info
    if info.get('anim') != 'Retro':
        return 0
    return (INTRO if info.get('intro') else 0)+(POWER_ON if info.get('power_on') else 0)


def _power_start(prepared):
    return INTRO if prepared[0].info.get('intro') else 0


# --- Strong moments ---------------------------------------------------------

def moments(prepared):
    """Timed effects: [(time, type, data)], times in seconds from the video start."""
    base, layers, positions = prepared
    info = base.info
    offset = _offset(prepared)
    out = []
    by_id = {l.id: l for l in layers}
    if info.get('kind') == 'matchday' and by_id.get('home_logo') and getattr(by_id['home_logo'], 'anim', '') == 'slide_left':
        l = by_id['home_logo']
        out.append((offset+l.start+l.dur, 'impact', dict(strength=1.0, flash=True)))
    names = [by_id[n] for n in ('home_name', 'away_name') if n in by_id]
    if info.get('kind') == 'matchday' and info.get('stakes') and names:
        import focus
        ready = max(offset+n.start+n.dur for n in names)
        crash = offset+by_id['home_logo'].start+by_id['home_logo'].dur if 'home_logo' in by_id else 0
        out.append((max(ready, crash)+.6, 'stakes', dict(info['stakes'], style=focus.stake_style(info))))
    for l in layers:
        if getattr(l, 'anim', '') == 'drop':
            out.append((offset+l.start+l.dur, 'impact', dict(strength=.45, flash=False)))
        if getattr(l, 'captain', False) and l.id.startswith('player_'):
            out.append((offset+l.start+l.dur+.1, 'shine', dict(layer=l.id)))
            if info.get('kind') == 'convocati':
                out.append((offset+l.start+l.dur+.15, 'captain', dict(layer=l.id)))
    score = by_id.get('score')
    if score is not None and getattr(score, 'anim', '') == 'replay':
        import focus
        for at, side, name in focus.replay_goals(score.replay):
            out.append((offset+score.start+at, 'replay_goal', dict(side=side)))
    if score is not None and getattr(score, 'anim', '') in ('count', 'replay'):
        end = offset+score.start+score.dur
        out.append((end, 'impact', dict(strength=1.0, flash=True)))
        out.append((end, 'focus_score', {}))
        if info.get('outcome') in ('win', 'draw', 'loss'):
            import focus
            out.append((end+2.4, 'points', dict(outcome=info['outcome'], style=focus.chip_style(info))))
        if info.get('our_goals', 0) > 0 and score.anim == 'count':   # the replay celebrates each goal itself
            out.append((end, 'goal', dict(layer='score')))
        if info.get('outcome'):
            out.append((end+1.0, 'banner', dict(outcome=info['outcome'])))
    table = by_id.get('table')
    if table is not None and getattr(table, 'anim', '') == 'rows':
        end = offset+table.start+table.dur
        meta = table.image.info
        landing = 0
        if info.get('kind') == 'classifica' and meta.get('ours') and meta.get('prev'):
            import focus
            mode = focus.mode_of(meta['prev'], meta['ours'])
            landing = focus.lead(mode)          # the moment is the landing: that goes on the drop
            out.append((end+landing, 'climb', dict(ours=meta['ours'], prev=meta['prev'], mode=mode, lead=landing)))
        if info.get('kind') == 'classifica' and meta.get('first'):
            out.append((end+(landing+.35 if landing else 0), 'crown', dict(ours=meta['ours'])))
        if info.get('kind') == 'classifica' and meta.get('gap'):
            out.append((end+(landing+1.0 if landing else .4), 'gap', dict(meta['gap'])))
        if info.get('kind') == 'calendario' and meta.get('tally') and 'subtitle' in by_id:
            out.append((end+(4.4 if meta.get('next_row') is not None else 1.2), 'tally', dict(meta['tally'])))
        if info.get('kind') == 'calendario':
            results = meta.get('row_results') or []
            nxt = meta.get('next_row')
            played = [i for i, r in enumerate(results) if r and (nxt is None or i < nxt)]
            if played:   # the last result gets stamped, then the camera glides to the next match
                out.append((end+.35, 'stamp', dict(row=played[-1], result=results[played[-1]], next=nxt)))
            if nxt is not None:
                out.append((end+(2.3 if played else 0), 'next', dict(row=nxt)))
    return sorted(out, key=lambda m: m[0])


def intro_length(prepared):
    """Seconds until every element is on screen (and the big moments are over)."""
    layers = prepared[1]
    if not layers or not all(hasattr(l, 'start') for l in layers):
        return None
    end = _offset(prepared)+max(l.start+l.dur for l in layers)
    for t, kind, _ in moments(prepared):
        end = max(end, t+{'banner': 1.3, 'climb': 1.3, 'crown': 1.0, 'goal': .8, 'points': .8, 'stamp': 2.6,
                          'captain': 1.5, 'focus_score': 1.4, 'stakes': 3.2, 'gap': .9, 'tally': 3.2}.get(kind, .3))
    return end


def events(prepared):
    """(time, sound kind, index) for the soundtrack, matching compose()."""
    info = prepared[0].info
    out = []
    offset = _offset(prepared)
    if info.get('intro') and info.get('anim') == 'Retro':
        import intros
        out += intros.sound_events(info.get('intro_style', 'press_start'), info.get('level', 1))
    if info.get('power_on') and info.get('anim') == 'Retro':
        out.append((_power_start(prepared), 'power', 0))
    for i, layer in enumerate(sorted(prepared[1], key=lambda l: l.start)):
        t = offset+layer.start
        if layer.anim == 'glitch':
            out.append((t, 'glitch', i))
        elif layer.anim in ('slide_left', 'slide_right', 'dash', 'dive'):
            out.append((t, 'whoosh', i))
        elif layer.anim in ('drop', 'bounce', 'wipe'):
            out.append((t, 'whoosh', i))
        elif layer.anim == 'pixelate':
            out.append((t, 'glitch', i))
        elif layer.anim == 'count':
            for k in range(len(layer.variants)):
                out.append((t+k*.12, 'tick', k))
        elif layer.anim == 'rows':
            results = layer.image.info.get('row_results')
            for k in range(len(layer.image.info['row_edges'])):
                result = results[k] if results and k < len(results) else None
                out.append((t+k*ROW_STEP, 'ding' if result else 'blip', {'V': 2, 'N': 1, 'P': 0}.get(result, k)))
        else:
            out.append((t, 'blip', i))
    seen_impact = set()
    for t, kind, data in moments(prepared):
        if kind == 'impact':
            key = round(t, 2)
            if key not in seen_impact:
                seen_impact.add(key)
                out.append((t, 'impact', 1 if data['strength'] > .6 else 0))
        elif kind == 'goal':
            out.append((t, 'goal', 0))
        elif kind == 'banner':
            out.append((t, data['outcome'], 0))
        elif kind == 'points':
            if data.get('style') == 'conta':
                for k in range({'win': 3, 'draw': 1, 'loss': 0}[data['outcome']]):
                    out.append((t+(k+1)*.18, 'tick', k))
            out.append((t+(.6 if data.get('style') == 'vola' else .55 if data.get('style') == 'conta' else 0), 'ding',
                        {'win': 2, 'draw': 1, 'loss': 0}[data['outcome']]))
        elif kind == 'stamp':
            out.append((t, 'impact' if focus_treatment(info, 'calendario') == 'timbro' else 'blip', 0))
            if data.get('next') is not None:
                out.append((t+.95, 'whoosh', 0))
        elif kind == 'captain':
            out.append((t, 'whoosh', 0))
        elif kind == 'replay_goal':
            out.append((t, 'goal' if data['side'] == ('away' if info.get('our_side') == 'Ospiti' else 'home') else 'impact', 0))
        elif kind == 'stakes':
            out.append((t, 'glitch' if data['style'] == 'glitch' else 'blip', 3))
            out.append((t+2.6, 'blip', 1))
        elif kind == 'gap':
            out.append((t+.45, 'tick', 2))
        elif kind == 'tally':
            out.append((t, 'blip', 4))
            out.append((t+2.6, 'blip', 1))
        elif kind == 'climb':
            out.append((t-data['lead']+.75, 'whoosh', 0))
            out.append((t, {'up': 'climb', 'same': 'ding', 'down': 'impact'}[data['mode']], 0))
        elif kind in ('crown', 'shine'):
            out.append((t, kind, 0))
    if info.get('ending') == 'spegnimento' and info.get('duration'):
        out.append((info['duration']-.65, 'power_off', 0))
    if info.get('ending') in motion.NEW_ENDINGS and info.get('duration'):
        sound = {'pixel': 'pixelate', 'glitch': 'glitch', 'zoom': 'whoosh', 'tendina': 'wipe'}[info['ending']]
        out.append((info['duration']-.8, sound, 0))
    return out


def particles(canvas, prepared, t, animated):
    theme = prepared[0].info.get('theme')
    if theme:
        themes.draw_particles(canvas, theme, t if animated else themes.STILL_TIME)


def still_base(prepared):
    """Background with the theme particles frozen (and the frame and texture), for the drag editor."""
    import frames
    base = prepared[0]
    if not base.info.get('theme') and not frames.active(base.info):
        return base
    image = base.copy()
    particles(image, prepared, 0, False)
    return frames.apply(image, base.info, 0, False)


# --- Drawing helpers --------------------------------------------------------

def _ease(a):
    return 1-(1-a)**3


def _back(a):
    c = 1.9
    return 1+(c+1)*(a-1)**3+c*(a-1)**2


def _put(canvas, img, layer, pos, alpha=1.0, dx=0.0, dy=0.0):
    if img is None or alpha <= 0:
        return
    s = canvas.width/540
    if alpha < .999:
        img = img.copy()
        img.putalpha(img.getchannel('A').point(lambda v: round(v*alpha)))
    ox, oy = (layer.offset_x, layer.offset_y) if layer is not None else (0, 0)
    x = round((pos[0]+ox+dx)*s-img.width/2)
    y = round((pos[1]+oy+dy)*s-img.height/2)
    # Clip to the canvas: alpha_composite refuses negative destinations.
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(img.width, canvas.width-x), min(img.height, canvas.height-y)
    if right <= left or bottom <= top:
        return
    if (left, top, right, bottom) != (0, 0, img.width, img.height):
        img = img.crop((left, top, right, bottom))
    if canvas.mode == 'RGB':
        canvas.paste(img, (x+left, y+top), img)   # straight-alpha blend onto the opaque frame
    else:
        canvas.alpha_composite(img, (x+left, y+top))


def _typed(img, a):
    w, h = img.size
    char = max(2, round(h*.62))
    steps = max(1, math.ceil(w/char))
    shown = min(w, math.ceil(a*steps)*char)
    out = Image.new('RGBA', img.size)
    if shown > 0:
        out.paste(img.crop((0, 0, shown, h)), (0, 0))
    if a < 1:
        x = min(w-1, shown)
        cursor = Image.new('RGBA', (max(1, round(char*.55)), max(1, round(h*.72))), (250, 250, 255, 235))
        out.alpha_composite(cursor, (min(w-cursor.width, x), round(h*.14)))
    return out


def _tinted(img, color, alpha):
    ghost = Image.new('RGBA', img.size, (*color, 0))
    ghost.putalpha(img.getchannel('A').point(lambda v: round(v*alpha)))
    return ghost


def _glitched(img, a, seed, s):
    rng = np.random.default_rng(seed)
    if rng.random() > .3+.7*a:
        return None  # flicker: this frame the crest is off
    k = 1-a
    off = round(k*9*s)
    out = Image.new('RGBA', (img.width+2*off, img.height))
    if off:
        out.alpha_composite(_tinted(img, (255, 40, 120), .75*k+.1), (0, 0))
        out.alpha_composite(_tinted(img, (60, 230, 255), .75*k+.1), (2*off, 0))
    out.alpha_composite(img, (off, 0))
    arr = np.array(out)
    h, w = arr.shape[:2]
    for _ in range(int(2+7*k)):
        y = int(rng.integers(0, h))
        bh = int(rng.integers(max(1, h//30), max(2, h//7)))
        arr[y:y+bh] = np.roll(arr[y:y+bh], int(rng.integers(-1, 2)*k*16*s*rng.random()), axis=1)
    return Image.fromarray(arr, 'RGBA')


def _whiten(img, amount, color=(255, 255, 255)):
    if amount <= 0:
        return img
    arr = np.asarray(img).astype(np.float32)
    arr[..., :3] += (np.array(color, np.float32)-arr[..., :3])*amount
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')


def _scaled(img, k):
    if abs(k-1) < .01:
        return img
    size = (max(1, round(img.width*k)), max(1, round(img.height*k)))
    return img.resize(size, Image.Resampling.BILINEAR)


def _rows(img, edges, local, s):
    out = Image.new('RGBA', img.size)
    for i, (y0, y1) in enumerate(edges):
        pr = (local-i*ROW_STEP)/.22
        if pr <= 0:
            break
        pr = min(1, pr)
        band = img.crop((0, round(y0*s), img.width, round(y1*s)))
        if pr < 1:
            e = _ease(pr)
            shift = round((1-e)*40*s)
            band = _whiten(band, (1-pr)*.6)
            band = band.crop((shift, 0, band.width, band.height))
            band.putalpha(band.getchannel('A').point(lambda v: round(v*e)))
        out.alpha_composite(band, (0, round(y0*s)))
    return out


@lru_cache(maxsize=64)
def _label(text, color, size, scale, style='CRT Scoreboard'):
    from pixel_fonts import pixel_text_runs
    return pixel_text_runs([(text, color)], style, size, 520, scale)


def _outlined(label, s, color=(16, 10, 24)):
    """A pixel label with a dark outline, readable over anything."""
    if label is None:
        return None
    pad = max(1, round(s*1.5))
    out = Image.new('RGBA', (label.width+2*pad, label.height+2*pad))
    shadow = _tinted(label, color, 1)
    for dx in (-pad, 0, pad):
        for dy in (-pad, 0, pad):
            if dx or dy:
                out.alpha_composite(shadow, (pad+dx, pad+dy))
    out.alpha_composite(label, (pad, pad))
    return out


SPECIAL_EVERY = 5.3      # seconds between a card's special idle moves
HOP = .36                # the little jump after a card lands


def _idle_card(layer, t, index):
    """The card's frame while it waits: blinks, a rotating special move
    (wink / smile / brows / glint) and a gentle bob."""
    alive = getattr(layer, 'alive', None)
    if not alive:
        return layer.image
    if 'blink' in alive and (t+index*.83) % 2.7 < .13:
        return alive['blink']
    specials = [k for k in ('wink', 'smile', 'brows', 'glint') if k in alive]
    if specials:
        phase = t+index*1.9
        if phase % SPECIAL_EVERY < .55:
            return alive[specials[int(phase//SPECIAL_EVERY+index) % len(specials)]]
    if (t*2+index*.37) % 1 < .5:
        return alive.get('pose') or alive.get('bob') or layer.image   # the pose's second frame, or a bob
    return layer.image


def _card_hop(layer, local, t):
    """Vertical offset: a hop right after landing and a tiny one with each special move."""
    after = local-layer.dur
    dy = 0.0
    if 0 <= after < HOP:
        dy -= 9*math.sin(math.pi*after/HOP)
    phase = t+layer.sequence*1.9
    if getattr(layer, 'alive', None) and len(layer.alive) > 2 and phase % SPECIAL_EVERY < .3:
        dy -= 4*math.sin(math.pi*(phase % SPECIAL_EVERY)/.3)
    return dy


def _motion_offsets(kind, a):
    """(dx, dy, alpha) of the falling and diving entrances at progress a."""
    if kind == 'dive':
        return -(1-_back(a))*70, -(1-_ease(a))*150, min(1, a*3)
    if kind == 'drop':
        return 0.0, -(1-a*a)*190, min(1, a*3)
    return 0.0, -(1-motion.bounce(a))*130, min(1, a*4)     # bounce


def _blurred(canvas, layer, pos, kind, a):
    """Fast moves with a short motion blur: two faint copies where the element was a moment ago."""
    dx, dy, alpha = _motion_offsets(kind, a)
    step = (1/72)/max(.1, layer.dur)
    for k, ghost in ((2, .14), (1, .28)):
        px, py, _ = _motion_offsets(kind, max(0.0, a-k*step))
        if abs(px-dx)+abs(py-dy) > 2:
            _put(canvas, layer.image, layer, pos, alpha*ghost, px, py)
    _put(canvas, layer.image, layer, pos, alpha, dx, dy)


def _draw(canvas, layer, pos, local, frame_index, t, info):
    if local <= 0:
        return
    a = min(1.0, local/layer.dur)
    s = canvas.width/540
    kind = layer.anim
    if kind == 'replay':
        import focus
        focus.draw_replay(canvas, layer, pos, local, info)
        return
    if kind == 'count':
        if a < 1:
            # Slot machine: the digits roll down between values.
            step = local/.12
            idx = min(len(layer.variants)-1, int(step))
            frac = step-int(step)
            img = layer.variants[idx]
            _put(canvas, img, layer, pos, 1, 0, (frac-.5)*-10)
            if idx+1 < len(layer.variants):
                _put(canvas, layer.variants[idx+1], layer, pos, frac*.45, 0, (frac-.5)*-10-20)
        else:
            after = local-layer.dur
            k = 1+.22*max(0, 1-after/.3)
            _put(canvas, _whiten(_scaled(layer.image, k), max(0, .5-after*1.6)), layer, pos)
        return
    if a >= 1:
        img = layer.image
        dy = 0.0
        if layer.id.startswith('card_'):
            img = _idle_card(layer, t, layer.sequence)
            dy = _card_hop(layer, local, t)
        dx = 0.0
        if kind in ('slide_left', 'slide_right'):  # recoil after the crash
            after = local-layer.dur
            if after < .3:
                dx = (1 if kind == 'slide_left' else -1)*22*(1-_ease(after/.3))
        _put(canvas, img, layer, pos, 1, dx, dy)
        return
    if kind == 'type':
        _put(canvas, _typed(layer.image, a), layer, pos)
    elif kind == 'glitch':
        _put(canvas, _glitched(layer.image, a, frame_index*31+len(layer.id), s), layer, pos)
    elif kind == 'pop':
        e = _back(a)
        _put(canvas, _whiten(_scaled(layer.image, 1.7-.7*e), (1-a)*.8), layer, pos, min(1, a*2.5))
    elif kind in ('slide_left', 'slide_right'):
        sign = -1 if kind == 'slide_left' else 1
        e = a*a  # accelerating into the crash, a little past the mark
        dx = sign*(1-e)*330-sign*e*22
        for k, alpha in ((2, .18), (1, .32)):
            _put(canvas, _tinted(layer.image, (255, 92, 190) if sign < 0 else (80, 230, 255), alpha), layer, pos, 1,
                 dx+sign*k*26*(1-a))
        _put(canvas, layer.image, layer, pos, 1, dx)
    elif kind == 'dash':
        e = _ease(a)
        dx = (1-e)*280
        for k, alpha in ((3, .15), (2, .25), (1, .35)):
            _put(canvas, _tinted(layer.image, (80, 230, 255), alpha), layer, pos, 1, dx+k*22*(1-a))
        _put(canvas, layer.image, layer, pos, 1, dx)
    elif kind in ('dive', 'drop', 'bounce'):
        _blurred(canvas, layer, pos, kind, a)
    elif kind == 'rows':
        _put(canvas, _rows(layer.image, layer.image.info['row_edges'], local, s), layer, pos)
    elif kind == 'pixelate':
        _put(canvas, motion.pixelated(layer.image, a, s), layer, pos, min(1, a*2.2))
    elif kind == 'wipe':
        _put(canvas, motion.wiped(layer.image, a, s), layer, pos)
    elif kind == 'zoom':
        _put(canvas, _scaled(layer.image, motion.zoom_scale(a)), layer, pos, min(1, a*3))
    else:
        e = _ease(a)
        _put(canvas, layer.image, layer, pos, e, 0, (1-e)*12)


def _band(layer, row):
    """(y0, y1) of a table row, in layout units of the layer image."""
    return layer.image.info['row_edges'][row]


def _moment_overlay(canvas, prepared, t, local, kind, data):
    """Draw one strong moment on the RGBA canvas (local = seconds since it started)."""
    base, layers, positions = prepared
    s = canvas.width/540
    by_id = {l.id: l for l in layers}
    from render_utils import ScaledDraw
    if kind == 'goal' and local < .9:
        layer = by_id[data['layer']]
        cx, cy = positions[layer.id]
        d = ScaledDraw(canvas, s, 'RGBA')
        k = local/.9
        rng = np.random.default_rng(7)
        for i in range(18):
            ang = i/18*math.tau+rng.random()*.2
            r = 20+k*130*(.7+rng.random()*.5)
            x, y = cx+math.cos(ang)*r, cy+math.sin(ang)*r*.8
            col = ((255, 214, 90), (255, 92, 190), (80, 230, 255))[i % 3]
            size = 4*(1-k)+1
            d.rectangle((x, y, x+size, y+size), fill=(*col, round(255*(1-k))))
        label = _outlined(_label('GOAL!', (255, 228, 92), 30, max(1, round(s))), s)
        if label:
            pop = 1.6-.6*_back(min(1, local/.3))
            _put(canvas, _scaled(label, pop), None, (cx, cy-58), min(1, (1-k)*2.2))
    elif kind == 'banner' and local < 1.3:
        outcome = data['outcome']
        text, colour = {'win': ('STAGE CLEAR!', (140, 255, 150)), 'draw': ('DRAW GAME', (255, 214, 90)),
                        'loss': ('GAME OVER', (255, 96, 110))}[outcome]
        slide = 0
        if local < .15:
            slide = -(1-_ease(local/.15))*540
        elif local > 1.15:
            slide = _ease((local-1.15)/.15)*540
        y = 470
        d = ScaledDraw(canvas, s, 'RGBA')
        h = 34 if outcome != 'loss' else 46
        d.rectangle((78+slide, y-h/2, 462+slide, y+h/2), fill=(10, 8, 18, 235))
        d.rectangle((78+slide, y-h/2, 462+slide, y-h/2+2), fill=(*colour, 255))
        d.rectangle((78+slide, y+h/2-2, 462+slide, y+h/2), fill=(*colour, 255))
        label = _label(text, colour, 20, max(1, round(s)))
        _put(canvas, label, None, (270+slide, y-(6 if outcome == 'loss' else 0)))
        if outcome == 'loss':
            count = max(7, 9-int(local/.35))
            small = _label(f'CONTINUE? {count}', (250, 248, 255), 9, max(1, round(s)))
            if int(local*6) % 2 == 0:
                _put(canvas, small, None, (270+slide, y+13))
    elif kind == 'climb':
        import focus
        focus.draw(canvas, prepared, data, local+data['lead'], data.get('backdrop', canvas))
    elif kind == 'crown' and local < 1.2:
        table = by_id['table']
        tx, ty = positions['table']
        th, tw = table.image.height/s, table.image.width/s
        y0, _ = _band(table, data['ours'])
        cx, cy = tx-tw/2+16, ty-th/2+y0-10
        pop = _back(min(1, local/.3))
        d = ScaledDraw(canvas, s, 'RGBA')
        gold = (255, 214, 90, round(255*min(1, (1.2-local)*3)))
        w = 13*pop
        d.polygon([(cx-w, cy+5*pop), (cx-w, cy-3*pop), (cx-w/2, cy+1*pop), (cx, cy-6*pop), (cx+w/2, cy+1*pop),
                   (cx+w, cy-3*pop), (cx+w, cy+5*pop)], fill=gold)
        rng = np.random.default_rng(3)
        for i in range(14):
            ang = rng.random()*math.tau
            r = 6+local*60*(.5+rng.random())
            x, y = cx+math.cos(ang)*r, cy+math.sin(ang)*r+local*local*20
            col = ((255, 92, 190), (80, 230, 255), (255, 214, 90), (140, 255, 150))[i % 4]
            d.rectangle((x, y, x+2.5, y+2.5), fill=(*col, gold[3]))
    elif kind == 'next':
        if int(local*2) % 2 == 0:
            table = by_id['table']
            tx, ty = positions['table']
            th, tw = table.image.height/s, table.image.width/s
            y0, y1 = table.image.info['row_edges'][data['row']]
            ScaledDraw(canvas, s, 'RGBA').rectangle((tx-tw/2, ty-th/2+y0+2, tx+tw/2, ty-th/2+y1-2), fill=(255, 255, 255, 46))
    elif kind == 'shine' and local < .45:
        layer = by_id[data['layer']]
        img = layer.image
        arr = np.asarray(img).astype(np.float32)
        w = img.width
        x = (local/.45)*(w*1.4)-w*.2
        cols = np.arange(w)[None, :]-np.arange(img.height)[:, None]*.6
        stripe = np.clip(1-np.abs(cols-x)/(w*.08), 0, 1)[..., None]
        arr[..., :3] += (np.array((255, 236, 150))-arr[..., :3])*stripe*.85
        _put(canvas, Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA'), layer, positions[layer.id])


def _sparkles(canvas, prepared, t):
    """Twinkles on the captain's card."""
    base, layers, positions = prepared
    s = canvas.width/540
    from render_utils import ScaledDraw
    d = ScaledDraw(canvas, s, 'RGBA')
    for layer in layers:
        if not (layer.id.startswith('card_') and getattr(layer, 'captain', False)):
            continue
        if t < _offset(prepared)+layer.start+layer.dur:
            continue
        x, y = positions[layer.id]
        w, h = layer.image.width/s, layer.image.height/s
        for i, (dx, dy) in enumerate(((w/2-6, -h/2+4), (w/2-16, -h/2+14), (w/2+2, -h/2+20))):
            k = .5+.5*math.sin(t*5+i*2.1)
            if k < .3:
                continue
            L = 1.5+3.5*k
            col = (255, 228, 120, round(255*k))
            d.rectangle((x+dx-.6, y+dy-L, x+dx+.6, y+dy+L), fill=col)
            d.rectangle((x+dx-L, y+dy-.6, x+dx+L, y+dy+.6), fill=col)


def _details(canvas, t):
    """VHS REC dot and running time code, outside the screen area."""
    s = max(1, round(canvas.width/540))
    if int(t*2) % 2 == 0:
        from render_utils import ScaledDraw
        ScaledDraw(canvas, canvas.width/540, 'RGBA').ellipse((84, 298, 92, 306), fill=(255, 60, 70, 255))
        _put(canvas, _label('REC', (255, 245, 245), 8, s), None, (106, 302))
    frames = int(t*25)
    code = f'SP {frames//(25*60):d}:{(frames//25) % 60:02d}:{frames % 25:02d}'
    _put(canvas, _label(code, (230, 240, 255), 8, s), None, (420, 686))


def _tracking(frame, t):
    """Every few seconds a band of the picture slips sideways, like a worn tape."""
    phase = t % 3.4
    if phase > .28:
        return frame
    arr = np.array(frame)
    h, w = arr.shape[:2]
    center = int((.2+.6*((int(t/3.4)*.37) % 1))*h+phase*h*.4)
    band = max(4, h//40)
    rng = np.random.default_rng(int(t*100))
    for y in range(max(0, center-band), min(h, center+band)):
        arr[y] = np.roll(arr[y], int(rng.integers(-w//40, w//40+1)), axis=0)
    noise = rng.integers(0, 255, (min(h, center+2)-max(0, center-2), w, 1)).astype(np.uint8)
    if len(noise):
        arr[max(0, center-2):min(h, center+2)] = (arr[max(0, center-2):min(h, center+2)]*.5+noise*.5).astype(np.uint8)
    return Image.fromarray(arr)


def _shake(frame, t, impacts, s):
    dx = dy = 0.0
    flash = 0.0
    for at, data in impacts:
        local = t-at
        if 0 <= local < .35:
            k = (1-local/.35)*data['strength']
            dx += math.sin(local*90)*7*k
            dy += math.cos(local*70)*5*k
            if data.get('flash') and local < .18:
                flash = max(flash, (1-local/.18)*.6)
    if not dx and not dy and not flash:
        return frame
    arr = np.asarray(frame)
    ox, oy = round(dx*s), round(dy*s)
    shifted = np.roll(np.roll(arr, oy, axis=0), ox, axis=1)
    if flash:
        shifted = (shifted.astype(np.float32)+(255-shifted.astype(np.float32))*flash).astype(np.uint8)
    return Image.fromarray(shifted)


def _squash(arr, sy, glow, sx=1.0):
    h, w = arr.shape[:2]
    nh, nw = max(1, round(h*sy)), max(1, round(w*sx))
    img = Image.fromarray(arr.astype(np.uint8)).resize((nw, nh), Image.Resampling.BILINEAR)
    part = np.asarray(img, np.float32)
    part = part+(255-part)*glow
    out = np.zeros_like(arr, dtype=np.float32)
    y, x = (h-nh)//2, (w-nw)//2
    out[y:y+nh, x:x+nw] = part
    return out


def power_on(frame, p):
    """CRT switching on: a dot, a line, then the picture opening vertically."""
    if p >= 1.6:
        return frame
    arr = np.asarray(frame, np.float32)
    h, w = arr.shape[:2]
    if p < .18:
        out = np.zeros_like(arr)
        r = max(1, round(w*.004+w*.5*(p/.18)**2))
        t = max(1, round(h*.0015))
        out[h//2-t:h//2+t, max(0, w//2-r):w//2+r] = 255
    elif p < .42:
        out = np.zeros_like(arr)
        t = max(1, round(h*.002))
        out[h//2-t:h//2+t] = 255
    elif p < 1:
        q = (p-.42)/.58
        out = _squash(arr, max(.004, _ease(q)), (1-q)*.7)
    else:
        k = (1.6-p)/.6  # fading afterglow
        out = arr+(255-arr)*.12*k
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def power_off(frame, p):
    """CRT switching off: the picture collapses to a line, the line to a dot."""
    arr = np.asarray(frame, np.float32)
    if p < .5:
        q = _ease(p/.5)
        out = _squash(arr, max(.004, 1-q), q*.8)
    elif p < .85:
        q = _ease((p-.5)/.35)
        out = _squash(np.full_like(arr, 255), .004, max(.01, 1-q), 0)
    else:
        h, w = arr.shape[:2]
        out = np.zeros_like(arr)
        r = max(1, round(w*.006*(1-(p-.85)/.15)))
        out[h//2-r:h//2+r, w//2-r:w//2+r] = 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _intro(frame, t):
    """Black screen: PRESS START blinking, then PLAYER 1 READY."""
    out = Image.new('RGBA', frame.size, (6, 4, 12, 255))
    s = max(1, round(frame.width/540))
    if t < 1.0:
        if (t % .5) < .3:
            _put(out, _label('PRESS START', (255, 92, 190), 22, s), None, (270, 480))
        _put(out, _label('FLAMINGOS / CALCIO A 7', (120, 220, 255), 9, s), None, (270, 520))
    else:
        _put(out, _label('PLAYER 1', (120, 220, 255), 14, s), None, (270, 462))
        _put(out, _label('READY', (255, 228, 92), 26, s), None, (270, 494))
    arr = np.array(out.convert('RGB'))
    arr[::max(2, 2*s)] = (arr[::max(2, 2*s)]*.6).astype(np.uint8)  # scanlines
    return Image.fromarray(arr)


def compose(prepared, t=999, animated=True):
    import frames
    return frames.apply(_compose(prepared, t, animated), prepared[0].info, t, animated)


def _compose(prepared, t=999, animated=True):
    base, layers, positions = prepared
    info = base.info
    if animated and info.get('intro') and t < INTRO:
        import intros
        return intros.frame(base, t, info)
    # The whole frame is built on an opaque RGB canvas: overlays blend in place,
    # no full-frame transparent layers to allocate and merge on every frame.
    parallax = animated and info.get('camera') == 'parallasse'
    canvas = motion.parallax_base(base, t, info) if parallax else base.convert('RGB')
    particles(canvas, prepared, t, animated)
    if not animated:
        for layer in layers:
            _put(canvas, layer.image, layer, positions[layer.id])
        return canvas
    offset = _offset(prepared)
    frame_index = int(t*24)
    all_moments = moments(prepared)
    placed = positions
    if parallax:   # the text floats a little above the panels
        _, (lx, ly), _ = motion.parallax_offsets(t)
        placed = {k: (x+lx, y+ly) for k, (x, y) in positions.items()}
    focus_moment = next(((at, d) for at, k, d in all_moments if k == 'climb'), None)
    backdrop = canvas.copy() if focus_moment and t >= focus_moment[0]-focus_moment[1]['lead'] else None
    stamping = any(k in ('stamp', 'focus_score', 'captain') and 0 <= t-at < .8 for at, k, _ in all_moments)
    stakes_moment = next(((at, d) for at, k, d in all_moments if k in ('stakes', 'tally') and 0 <= t-at <= 3.2), None)
    clean = canvas.copy() if stakes_moment else None      # the background, to lift the names off the panels
    for layer in layers:
        shown = layer
        if focus_moment and getattr(layer, 'before', None) is not None:
            shown = copy.copy(layer)       # last week's order until our row lands, then the clean table
            shown.image = layer.before if t < focus_moment[0] else getattr(layer, 'clean', layer.image)
        _draw(canvas, shown, placed[layer.id], t-offset-layer.start, frame_index, t, info)
    if stamping and backdrop is None:
        backdrop = None   # filled below, after the layers: the stamp lifts what is on screen
    for at, kind, data in all_moments:
        early = data.get('lead', 0) if isinstance(data, dict) else 0
        if t >= at-early:
            if kind == 'climb':
                data = dict(data, backdrop=backdrop)
            _moment_overlay(canvas, prepared, t, t-at, kind, data)
    _sparkles(canvas, prepared, t)
    s = canvas.width/540
    if stamping:
        backdrop = canvas.copy()
    import focus
    focus.overlays(canvas, prepared, all_moments, t, backdrop)
    if stakes_moment and 'pt' in stakes_moment[1]:
        focus.tally_overlay(canvas, prepared, stakes_moment[1], t-stakes_moment[0], clean)
    elif stakes_moment:
        focus.stakes_overlay(canvas, prepared, stakes_moment[1], t-stakes_moment[0], clean)
    for at, kind, data in all_moments:
        if kind == 'gap':
            focus.gap_overlay(canvas, prepared, data, t-at)
    z, cx, cy = focus.camera_at(prepared, all_moments, t)
    if z > 1.0005:
        canvas = motion._affine(canvas, z, 0, 0, 0, cx*s, cy*s)
    from render_utils import ScaledDraw
    y = 318+((t*.6) % 1)*354
    ScaledDraw(canvas, s, 'RGBA').rectangle((78, y, 462, y+6), fill=(255, 255, 255, 10))
    motion.ambient_effects(canvas, t, info)
    if parallax:
        motion.foreground(canvas, t, info)
    if info.get('details', True):
        _details(canvas, t)
    frame = canvas
    if info.get('details', True):
        frame = _tracking(frame, t)
    impacts = [(at, d) for at, k, d in all_moments if k == 'impact']
    drop = info.get('drop_at') if info.get('music') else None
    if drop and not any(abs(at-drop) < .15 for at, _ in impacts):
        impacts.append((drop, dict(strength=.35, flash=True)))   # the drop of the music is felt on screen too
    frame = _shake(frame, t, impacts, s)
    frame = motion.camera_frame(frame, t, info)
    if 'fx_flicker' in info.get('fx', ()):
        frame = motion.flicker(frame, t)
    start = _power_start(prepared)
    if info.get('power_on') and t < start+POWER_ON*1.6:
        frame = power_on(frame, (t-start)/POWER_ON)
    elif t < offset+1.2 and int(t*24) % 7 == 3:
        frame = Image.fromarray((np.asarray(frame, np.float32)*.93).astype(np.uint8))
    duration = info.get('duration')
    ending = info.get('ending', 'nessuno')
    if duration and ending == 'spegnimento' and t > duration-.65:
        frame = power_off(frame, min(1, (t-(duration-.65))/.62))
    elif duration and ending in motion.NEW_ENDINGS and t > duration-.8:
        frame = motion.ending_frame(frame, ending, min(1, (t-(duration-.8))/.78))
    elif duration and ending == 'loop':
        fade = 1.0
        if t > duration-.45:
            fade = max(0, (duration-t)/.45)
        if not info.get('power_on') and not info.get('intro') and t < .3:
            fade = min(fade, t/.3)
        if fade < 1:
            frame = Image.fromarray((np.asarray(frame, np.float32)*fade).astype(np.uint8))
    return frame
