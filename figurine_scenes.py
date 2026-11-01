"""The figurine screens inside a video sequence (3.10): Pagelle, Figurina MVP, Album (and the round results, 3.12).

render_sequence() speaks (prepared, compose) like every CRT editor. Here
prepared[0] is a 1x1 placeholder whose .info carries what the sequence sets
(format, beat of the soundtrack, start time, hold) and compose() draws the
screen in that format inside the 540x960 frame the sequence crops. The
timelines are folded into the hold: the card comes out of the pack on a beat
of the sequence's music, the MVP row of the ratings likewise.
"""
from __future__ import annotations

import math

from PIL import Image

EXTRA = ('Pagelle', 'Figurina MVP', 'Album', 'Risultati')
LABELS = {'Pagelle': '📝 Pagelle', 'Figurina MVP': '🃏 Figurina MVP (bustina)', 'Album': '📒 Album della stagione',
          'Risultati': '📋 Risultati della giornata'}


def _on_beat(info, fraction):
    """Local time near hold*fraction that falls on a beat of the sequence's soundtrack."""
    hold = float(info.get('hold') or 4.0)
    target = hold*fraction
    beat = info.get('seq_beat') or .5
    start = float(info.get('seq_start') or 0.0)
    k = round((start+target-4.0)/beat)
    local = 4.0+k*beat-start
    return local if .25 <= local <= hold-.6 else target


def _place(frame, fmt, scale):
    """The format-sized frame inside the 540x960 canvas, where output_image will crop it."""
    from crt_presets import CROPS
    W, H = round(540*scale), round(960*scale)
    crop = CROPS.get(fmt)
    if not crop:
        return frame if frame.size == (W, H) else frame.resize((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (W, H), (0, 0, 0))
    top = math.floor(crop[1]*scale)
    size = (round((crop[2]-crop[0])*scale), round((crop[3]-crop[1])*scale))
    canvas.paste(frame if frame.size == size else frame.resize(size, Image.Resampling.LANCZOS), (round(crop[0]*scale), top))
    return canvas


def scene(kind, payload, logo, scale=2, style_key=None):
    """(prepared, compose) for one of EXTRA. payload: card spec + caption, rows + info, or album members."""
    holder = Image.new('RGB', (1, 1))
    holder.info.update(kind=kind, payload=payload, logo=logo, scale=scale, style_key=style_key, anim='',
                       music_track='cc0_robots', built={})
    holder.info['sequence_events'] = lambda hold, info=holder.info: _events(info, hold)
    return (holder, [], {}), compose


def _build(info, fmt):
    import figurine_style
    built = info['built']
    if fmt not in built:
        scale, logo, payload = info['scale'], info['logo'], info['payload']
        style = figurine_style.build(info['style_key'], fmt, int(540*scale)) if info.get('style_key') else None
        if info['kind'] == 'Figurina MVP':
            import card_video
            built.clear()
            built[fmt] = card_video.Show(payload['spec'], logo, fmt, scale, info.get('music_track'), payload.get('caption', ''),
                                         style=style, fades=False)
        elif info['kind'] == 'Pagelle':
            import pagelle
            built.clear()
            built[fmt] = pagelle.Pagelle(payload['rows'], payload['info'], logo, fmt, scale, info.get('music_track'),
                                         style=style, fades=False)
        elif info['kind'] == 'Risultati':
            import results_round
            built.clear()
            built[fmt] = results_round.RoundShow(payload['rows'], payload.get('title', 'RISULTATI'),
                                                 payload.get('subtitle', ''), payload.get('date', ''), logo,
                                                 payload.get('ours', 'FLAMINGOS'), fmt, scale, info.get('music_track'),
                                                 style=style, fades=False)
        else:
            import album
            built.clear()
            built[fmt] = album.poster(payload['members'], logo, fmt, scale, season=payload.get('season', '2026/27'),
                                      team=payload.get('team', 'FLAMINGOS'), style=style)
    return built[fmt]


def offset(info):
    """Show time minus local time: where the screen's own timeline starts within the hold."""
    import card_video
    if info['kind'] == 'Figurina MVP':
        return card_video.DROP-_on_beat(info, .38)
    if info['kind'] == 'Pagelle':
        return card_video.DROP-_on_beat(info, .55)
    if info['kind'] == 'Risultati':
        return card_video.DROP-_on_beat(info, .6)
    return 0.0


def compose(prepared, t=999, animated=True):
    info = prepared[0].info
    fmt = info.get('format', 'Story 9:16')
    obj = _build(info, fmt)
    if isinstance(obj, Image.Image):
        frame = obj
    else:
        hold = float(info.get('hold') or 4.0)
        local = min(t, hold) if animated else hold
        frame = obj.frame(offset(info)+local)
    return _place(frame, fmt, info['scale'])


def _events(info, hold):
    """Effects of the screen, relative to its start in the sequence."""
    fmt = info.get('format', 'Story 9:16')
    obj = _build(info, fmt)
    if isinstance(obj, Image.Image):
        return []
    shift = offset(info)
    return [(at-shift, sound) for at, sound in obj.events() if 0 <= at-shift < hold]


def payloads(state, squad, mvps, scorers, ctx):
    """What each screen shows: from the Figurine page of this session, or sensible defaults."""
    import album
    import cards
    import figurine_data as fd
    out = {}
    card = state.get('figurina_payload')
    if not card:
        people = squad or []
        member = next((p for p in people if p.get('role') == 'A'), people[0] if people else dict(name='GIOCATORE'))
        spec = dict(name=member['name'], number=member.get('number', 0), role=member.get('role'), look=member.get('look'),
                    avatar=member.get('avatar', ''), edition='mvp', vote=8.0,
                    stats=fd.stats_for('mvp', member, ctx), season=ctx.get('season', '2026/27'),
                    team=ctx.get('team', 'FLAMINGOS'))
        card = {'spec': spec, 'caption': fd.caption_for('mvp', member, ctx)}
    out['Figurina MVP'] = card
    out['Pagelle'] = state.get('pagelle_payload')
    out['Album'] = {'members': album.members_for(squad or [], mvps, scorers, True, ctx.get('season', '2026/27'),
                                                 ctx.get('team', 'FLAMINGOS')),
                    'season': ctx.get('season', '2026/27'), 'team': ctx.get('team', 'FLAMINGOS')}
    out['Risultati'] = state.get('results_payload') or _results_default(state.get('csi_matches'), ctx.get('team', 'FLAMINGOS'))
    del cards
    return out


def _results_default(matches, ours):
    """The last played round from the CSI site, when the Risultati page was not opened in this session."""
    import results_round as rr
    groups = rr.rounds(matches or [])
    if not groups:
        return None
    group = groups[rr.default_round(groups)]
    return {'rows': rr.rows_for(group, ours), 'title': 'RISULTATI', 'subtitle': f"{group['label']} · CSI BRESCIA",
            'date': rr.date_line(group), 'ours': ours}
