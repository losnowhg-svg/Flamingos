"""Retro CRT transitions and multi-scene video sequences.

Every transition is a pure function of two equal-sized RGB frames and a
progress value p in [0, 1], so it renders the same in preview and in the MP4.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

TRANSITIONS = {
    'channel': 'Cambio canale',
    'poweroff': 'Spegni e riaccendi',
    'glitch': 'Glitch RGB',
    'rewind': 'Riavvolgimento VHS',
    'roll': 'Rolling verticale',
    'cut': 'Taglio netto',
}
TRANSITION_IDS = tuple(TRANSITIONS)
OSD_GREEN = (120, 255, 140)


def _ease(p):
    return p*p*(3-2*p)


def _seed(p, salt=0):
    return int(p*10_000)+salt*7919


def _osd(width, text, color=OSD_GREEN, size_ratio=.06):
    from pixel_fonts import pixel_text_runs
    scale = max(1, round(width/540))
    size = max(12, width*size_ratio/scale)
    return pixel_text_runs([(text, color)], 'CRT Terminal', size, 540, scale)


def _paste_osd(frame, text, anchor='topright', color=OSD_GREEN):
    label = _osd(frame.width, text, color)
    if not label:
        return frame
    # A dark, slightly offset copy keeps the OSD legible on bright static.
    shadow = Image.new('RGBA', label.size, (0, 0, 0, 0))
    shadow.putalpha(label.getchannel('A').point(lambda a: a*.7))
    margin = round(frame.width*.06)
    x = frame.width-label.width-margin if anchor == 'topright' else margin
    y = round(frame.height*.06)
    canvas = frame.convert('RGBA')
    canvas.alpha_composite(shadow, (x+3, y+3))
    canvas.alpha_composite(label, (x, y))
    return canvas.convert('RGB')


def _static(height, width, p, salt=0, level=1.0):
    rng = np.random.default_rng(_seed(p, salt))
    # Static is generated at quarter resolution and enlarged: chunkier, faster.
    small = rng.integers(0, 256, (max(1, height//3), max(1, width//3)), dtype=np.uint8)
    noise = np.repeat(np.repeat(small, 3, axis=0), 3, axis=1)[:height, :width]
    noise = np.pad(noise, ((0, height-noise.shape[0]), (0, width-noise.shape[1])), mode='edge')
    # A darker rolling band, as on an untuned set.
    band = (np.arange(height)/height+p*1.7) % 1
    dark = 1-.45*np.exp(-((band-.5)**2)/.004)
    return (noise*dark[:, None]*level).astype(np.float32)


def _channel(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    h, w = A.shape[:2]
    noise = _static(h, w, p)[..., None]
    if p < .3:
        k = p/.3
        src = A
    elif p < .62:
        k = 1
        src = A if p < .46 else B
    else:
        k = 1-(p-.62)/.38
        src = B
    k = _ease(min(1, max(0, k)))
    shift = int(w*.04*k*math.sin(p*90))
    src = np.roll(src, shift, axis=1)
    out = src*(1-k)+noise*k
    frame = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if .18 < p < .92:
        frame = _paste_osd(frame, f'CH {channel:02d}')
    return frame


def _squash(src, sy, sx, glow):
    h, w = src.shape[:2]
    out = np.zeros_like(src)
    nh, nw = max(1, round(h*sy)), max(1, round(w*sx))
    img = Image.fromarray(src.astype(np.uint8)).resize((nw, nh), Image.Resampling.BILINEAR)
    arr = np.asarray(img, np.float32)
    arr = arr+(255-arr)*glow
    y, x = (h-nh)//2, (w-nw)//2
    out[y:y+nh, x:x+nw] = arr
    return out


def _poweroff(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if p < .5:
        q = p/.5
        src = A
    else:
        q = 1-(p-.5)/.5
        src = B
    # q: 0 = full picture, 1 = gone. Collapse to a line, then the line to a dot.
    if q < .55:
        t = _ease(q/.55)
        out = _squash(src, max(.004, 1-t), 1, t*.8)
    elif q < .9:
        t = _ease((q-.55)/.35)
        out = _squash(np.full_like(src, 255), .004, max(.01, 1-t), 0)
    else:
        out = np.zeros_like(src)
        h, w = src.shape[:2]
        r = max(1, round(w*.006*(1-(q-.9)/.1)))
        out[h//2-r:h//2+r, w//2-r:w//2+r] = 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _glitch(a, b, p, channel=2):
    src = np.asarray(a if p < .5 else b, np.float32).copy()
    h, w = src.shape[:2]
    k = 1-abs(p-.5)*2  # strongest at the cut
    rng = np.random.default_rng(_seed(p, 3))
    off = int(w*.03*k)+1
    out = src.copy()
    out[..., 0] = np.roll(src[..., 0], off, axis=1)
    out[..., 2] = np.roll(src[..., 2], -off, axis=1)
    for _ in range(int(3+12*k)):
        y = rng.integers(0, h)
        bh = int(rng.integers(max(2, h//120), max(3, h//18)))
        dx = int(rng.integers(-w//6, w//6)*k)
        out[y:y+bh] = np.roll(out[y:y+bh], dx, axis=1)
        if rng.random() < .3*k:
            out[y:y+bh] = out[y:y+bh]*.4+np.array([255, 60, 200])*.6*rng.random()
    if .4 < p < .6:
        out = out*.6+_static(h, w, p, 5)[..., None]*.4
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _rewind(a, b, p, channel=2):
    src = np.asarray(a if p < .5 else b, np.float32)
    h, w = src.shape[:2]
    k = 1-abs(p-.5)*2
    rows = np.arange(h)
    # Horizontal skew that grows toward the bottom of the frame, as on a VCR.
    skew = (k*w*.09*np.sin(rows/h*math.pi*3+p*40)).astype(int)
    idx = (np.arange(w)[None, :]-skew[:, None]) % w
    out = src[rows[:, None], idx]
    # Fast-moving tracking bands.
    for i in range(3):
        center = ((p*5+i*.37) % 1)*h
        band = np.exp(-((rows-center)**2)/(2*(h*.012)**2))[:, None]
        noise = _static(h, w, p, 11+i)
        out = out*(1-band[..., None]*k)+noise[..., None]*band[..., None]*k
    out = out*(1-.25*k)+np.array([20, 40, 160])*.25*k
    frame = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if .1 < p < .9:
        frame = _paste_osd(frame, '<< REW' if p < .5 else 'PLAY >', 'topleft', (255, 255, 255))
    return frame


def _roll(a, b, p, channel=2):
    A, B = np.asarray(a, np.float32), np.asarray(b, np.float32)
    h = A.shape[0]
    bar = np.zeros((max(2, h//14),)+A.shape[1:], np.float32)
    strip = np.concatenate([A, bar, B], axis=0)
    offset = int(_ease(p)*(h+bar.shape[0]))
    out = strip[offset:offset+h]
    # Slight jitter and brightness pumping while the picture rolls.
    k = math.sin(p*math.pi)
    out = np.roll(out, int(k*6*math.sin(p*70)), axis=1)*(1-.15*k)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _cut(a, b, p, channel=2):
    if .45 < p < .55:
        return Image.new('RGB', a.size, (255, 255, 255))
    return a if p <= .45 else b


FUNCTIONS = {'channel': _channel, 'poweroff': _poweroff, 'glitch': _glitch,
             'rewind': _rewind, 'roll': _roll, 'cut': _cut}


def transition_frame(kind, a, b, p, channel=2):
    """Blend frame a into frame b; p runs from 0 (all a) to 1 (all b)."""
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.LANCZOS)
    a, b = a.convert('RGB'), b.convert('RGB')
    p = max(0.0, min(1.0, float(p)))
    return FUNCTIONS.get(kind, _channel)(a, b, p, channel)


def intro_length(prepared, compose):
    """Seconds the scene's own entrance animation needs before everything is on screen."""
    if getattr(compose, '__module__', '') == 'matchday_renderer':
        return 4.3
    return .6+.12*max(1, len(prepared[1]))


def render_sequence(scenes, transitions, path, fps=24, hold=4.0, transition_seconds=1.0,
                    format='Story 9:16', scale=2, progress_callback=None, sound=False, volume=.8):
    """scenes: list of (prepared, compose_function). One transition between each pair.
    With sound=True a synthesised CRT soundtrack is muxed into the MP4."""
    from crt_presets import output_image, even_video_frame
    from renderer import video_writer, video_settings
    if not scenes:
        raise ValueError('Scegli almeno una grafica per la sequenza.')
    fps, _ = video_settings(fps, 8, scale)
    hold_frames = max(1, round(hold*fps))
    trans_frames = max(2, round(transition_seconds*fps))
    total = hold_frames*len(scenes)+trans_frames*(len(scenes)-1)
    writer = video_writer(path, fps)
    done = 0

    # Each entrance is sped up when needed so it completes in 65% of the hold:
    # the transition always starts from a finished graphic.
    speeds = [max(1.0, intro_length(p, c)/(hold*.65)) for p, c in scenes]

    def frame_at(index, t, animated=True):
        prepared, compose = scenes[index]
        return output_image(compose(prepared, t*speeds[index], animated), format, scale)

    def emit(image):
        nonlocal done
        writer.append_data(np.asarray(even_video_frame(image)))
        done += 1
        if progress_callback and (done % fps == 0 or done == total):
            progress_callback(done/total)

    events = []
    try:
        for index in range(len(scenes)):
            last = None
            if sound:
                from sounds import scene_events
                events += scene_events(*scenes[index], start=done/fps, speed=speeds[index], until=done/fps+hold)
            for i in range(hold_frames):
                last = frame_at(index, i/fps)
                emit(last)
            if index < len(scenes)-1:
                kind = transitions[index] if index < len(transitions) else 'channel'
                nxt = frame_at(index+1, 0)
                if sound:
                    from sounds import TRANSITION_SOUNDS
                    events.append((done/fps, TRANSITION_SOUNDS.get(kind, TRANSITION_SOUNDS['channel'])(trans_frames/fps)))
                for i in range(trans_frames):
                    emit(transition_frame(kind, last, nxt, (i+1)/(trans_frames+1), index+2))
    finally:
        writer.close()
    if sound:
        from sounds import mix, mux
        mux(path, mix(events, total/fps, volume))
    return str(path)


def preview_strip(a, b, kind, steps=6, width=180):
    """A small storyboard of the transition, for the editor."""
    height = round(a.height*width/a.width)
    small_a = a.resize((width, height), Image.Resampling.LANCZOS)
    small_b = b.resize((width, height), Image.Resampling.LANCZOS)
    sheet = Image.new('RGB', (width*steps+4*(steps-1), height), (16, 13, 22))
    for i in range(steps):
        frame = transition_frame(kind, small_a, small_b, i/(steps-1))
        sheet.paste(frame, (i*(width+4), 0))
    return sheet
