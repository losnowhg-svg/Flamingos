"""Original background music for the videos (3.1): six full-sounding tracks.

Synthwave, lo-fi, house, trap, disco and a stadium rock anthem, all written
here and synthesised in pure NumPy (no samples, no licences, no SciPy: the cloud app
does not install it). Everything runs
at 120 bpm on a 16-step grid, like the original chiptunes, so the entrances of
the graphics keep landing on the beat.

Every track has the same shape: two bars of intro (filtered, lighter), a riser,
the drop at 4 seconds with a crash, then 8-bar phrases where the hook comes in
and out. Mono, normalised to the loudness of the other tracks.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

SR = 44100
BEAT = .5
STEP = BEAT/4
BAR = BEAT*4
TARGET_RMS = .14

TRACKS = ('synthwave', 'lofi', 'house', 'trap', 'disco', 'carica')


# --- Building blocks -------------------------------------------------------------

def midi(n):
    return 440.0*2**((n-69)/12)


def _t(seconds):
    return np.arange(max(1, int(seconds*SR)))/SR


def _rng(seed):
    return np.random.default_rng(seed)


def _env(n, a=.005, d=.1, s=.75, r=.06):
    env = np.full(n, float(s))
    ai = min(n, int(a*SR))
    di = min(n-ai, int(d*SR))
    if ai:
        env[:ai] = np.linspace(0, 1, ai, endpoint=False)
    if di:
        env[ai:ai+di] = np.linspace(1, s, di, endpoint=False)
    ri = min(n, int(r*SR))
    if ri:
        env[-ri:] *= np.linspace(1, 0, ri)
    return env


def _size(n):
    """A fast FFT length with room for the filter tails."""
    return 1 << int(n+4096-1).bit_length()


def _gain(freqs, kind, hz, order):
    """Butterworth magnitude response (zero phase)."""
    hz = max(1.0, min(hz, SR*.45))
    ratio = np.maximum(freqs, 1e-6)/hz
    if kind == 'low':
        return 1/np.sqrt(1+ratio**(2*order))
    return 1/np.sqrt(1+ratio**(-2*order))


def _filter(x, kind, hz, order=2):
    x = np.asarray(x, float)
    size = _size(len(x))
    freqs = np.fft.rfftfreq(size, 1/SR)
    if kind == 'band':
        lo, hi = hz
        gain = _gain(freqs, 'high', lo, order)*_gain(freqs, 'low', hi, order)
    else:
        gain = _gain(freqs, kind, hz, order)
    return np.fft.irfft(np.fft.rfft(x, size)*gain, size)[:len(x)]


def _convolve(x, ir):
    size = 1 << int(len(x)+len(ir)-2).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size)*np.fft.rfft(ir, size), size)[:len(x)]


def lp(x, hz, order=2):
    return _filter(x, 'low', hz, order)


def hp(x, hz, order=2):
    return _filter(x, 'high', hz, order)


def bp(x, lo, hi, order=2):
    return _filter(x, 'band', (lo, hi), order)


def _saw(f, t, phase=0.0):
    return 2*((f*t+phase) % 1)-1


def _square(f, t, duty=.5):
    return np.where((f*t) % 1 < duty, 1.0, -1.0)


def _tri(f, t):
    return 2*np.abs(2*((f*t) % 1)-1)-1


def _sine(f, t):
    return np.sin(2*np.pi*f*t)


def _noise(n, seed):
    return _rng(seed).uniform(-1, 1, n)


def place(out, sound, at):
    i = int(round(at*SR))
    if 0 <= i < len(out):
        end = min(len(out), i+len(sound))
        out[i:end] += sound[:end-i]


# --- Drums -------------------------------------------------------------------------

@lru_cache(maxsize=16)
def kick(tight=1.0):
    t = _t(.4)
    f = 46+120*np.exp(-t*30*tight)
    body = np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*7*tight)
    click = hp(_noise(len(t), 1), 1500)*np.exp(-t*260)*.35
    return np.tanh((body+click)*1.8)*.9


@lru_cache(maxsize=16)
def snare(tone=190, seed=2, length=.25):
    t = _t(length)
    noise = bp(_noise(len(t), seed), 1200, 8000)*np.exp(-t*15)
    body = _sine(tone, t)*np.exp(-t*24)
    return (noise*.85+body*.55)*.8


@lru_cache(maxsize=8)
def clap(seed=4):
    t = _t(.3)
    raw = _noise(len(t), seed)
    env = np.exp(-t*20)*.6
    for k in (0, .011, .023):
        env += np.where(t >= k, np.exp(-(t-k)*220), 0)
    return bp(raw, 900, 6000)*env*.55


@lru_cache(maxsize=16)
def hat(open_=False, seed=20):
    t = _t(.32 if open_ else .05)
    return hp(_noise(len(t), seed), 7000, 4)*np.exp(-t*(9 if open_ else 70))*.42


@lru_cache(maxsize=4)
def rim():
    t = _t(.06)
    return (_sine(1700, t)*.6+_sine(820, t)*.4+hp(_noise(len(t), 9), 3000)*.3)*np.exp(-t*90)*.5


@lru_cache(maxsize=4)
def crash():
    t = _t(1.8)
    return hp(_noise(len(t), 33), 3500, 2)*np.exp(-t*2.3)*.32


@lru_cache(maxsize=8)
def tom(note=45):
    t = _t(.35)
    f = midi(note)*(1+.5*np.exp(-t*25))
    return np.tanh(np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*9)*1.5)*.6


@lru_cache(maxsize=4)
def shaker(seed=40):
    t = _t(.06)
    env = np.minimum(1, t/.012)*np.exp(-t*60)
    return hp(_noise(len(t), seed), 5000)*env*.25


def riser(seconds, seed=50):
    """White noise that opens up and grows into the drop."""
    t = _t(seconds)
    x = _noise(len(t), seed)
    half = len(x)//2
    out = np.concatenate([bp(x[:half], 800, 3000), bp(x[half:], 2000, 9000)])
    return out*(t/seconds)**2*.35


# --- Instruments ---------------------------------------------------------------------

def supersaw(f, seconds, cutoff=2600, a=.02, r=.18, voices=5, detune=.011):
    t = _t(seconds)
    x = sum(_saw(f*(1+detune*(k-(voices-1)/2)/((voices-1)/2)), t, k*.37) for k in range(voices))/voices
    return lp(x, cutoff)*_env(len(t), a, .3, .8, r)


def pluck(f, seconds, cutoff=3200, decay=9.0, duty=None):
    t = _t(seconds)
    x = _square(f, t, duty) if duty else _saw(f, t)
    x = lp(x, cutoff)*.6+lp(x, cutoff*.35)*.4
    return x*np.exp(-t*decay)*_env(len(t), .002, 0, 1, .02)


def epiano(f, seconds):
    t = _t(seconds)
    tone = _sine(f, t)+.35*_sine(2*f, t)*np.exp(-t*4)+.12*_sine(3.01*f, t)*np.exp(-t*9)
    tremolo = 1+.12*_sine(4.5, t)
    return tone*tremolo*np.exp(-t*1.4)*_env(len(t), .004, 0, 1, .12)*.5


def bell(f, seconds):
    t = _t(seconds)
    mod = 2.2*np.exp(-t*5)*_sine(f*3.5, t)
    return np.sin(2*np.pi*f*t+mod)*np.exp(-t*3.2)*_env(len(t), .002, 0, 1, .05)


def lead(f, seconds, cutoff=3600, wave='saw', glide_from=None):
    t = _t(seconds)
    vib = 1+.006*_sine(5.5, t)*np.clip((t-.15)/.2, 0, 1)
    freq = np.full(len(t), f)*vib
    if glide_from:
        g = np.clip(t/.06, 0, 1)
        freq *= (glide_from/f)**(1-g)
    phase = np.cumsum(freq)/SR
    x = (2*(phase % 1)-1) if wave == 'saw' else np.where(phase % 1 < .5, 1.0, -1.0)
    x = x*.6+(2*((phase*1.004) % 1)-1)*.4
    return lp(x, cutoff)*_env(len(t), .01, .15, .8, .08)


def brass(f, seconds):
    t = _t(seconds)
    x = _saw(f, t)*.5+_saw(f*1.005, t, .3)*.5
    dark, bright = lp(x, 700), lp(x, 3400)
    opening = np.clip(t/.07, 0, 1)
    return (dark+(bright-dark)*opening)*_env(len(t), .015, .2, .75, .07)


def organ(f, seconds):
    t = _t(seconds)
    x = _sine(f, t)+.5*_sine(2*f, t)+.3*_sine(3*f, t)+.2*_sine(4*f, t)
    return lp(np.tanh(x*.8), 4000)*_env(len(t), .003, .08, .55, .04)*.6


def bass(f, seconds, cutoff=700, drive=1.5, wave='saw'):
    t = _t(seconds)
    x = (_saw(f, t) if wave == 'saw' else _square(f, t))*.5+_sine(f, t)*.7
    return np.tanh(lp(x, cutoff)*drive)*_env(len(t), .004, .1, .85, .03)*.8


def sub808(f, seconds, glide_from=None):
    t = _t(seconds)
    freq = np.full(len(t), f)
    if glide_from:
        g = np.clip(t/.09, 0, 1)
        freq = f*(glide_from/f)**(1-g)
    x = np.sin(2*np.pi*np.cumsum(freq)/SR)
    # Distortion gives the harmonics a phone speaker can play.
    return np.tanh(x*2.6)*np.exp(-t*.9)*_env(len(t), .003, 0, 1, .05)*.75


def power_chord(root, seconds):
    t = _t(seconds)
    x = sum(_saw(midi(n), t, k*.21)+_saw(midi(n)*1.004, t) for k, n in enumerate((root, root+7, root+12)))
    return lp(np.tanh(x*1.6), 3200)*_env(len(t), .004, .06, .8, .03)*.35


# --- Effects ----------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _impulse(seconds, seed):
    t = _t(seconds)
    ir = lp(_noise(len(t), seed), 5000)*np.exp(-t*4.2/seconds)
    return ir/np.sqrt((ir**2).sum())


def reverb(x, seconds=1.6, wet=.3, seed=7):
    tail = _convolve(x, _impulse(seconds, seed))
    return x+tail*wet*3


def delay(x, time=.375, feedback=.38, wet=.32):
    out = x.copy()
    shift = int(time*SR)
    echo = x*wet
    pos = shift
    while pos < len(x) and np.abs(echo).max() > 1e-3:
        out[pos:] += echo[:len(x)-pos]
        echo = lp(echo, 3000, 1)*feedback
        pos += shift
    return out


def sidechain(n, kick_times, depth=.6, release=7.0):
    env = np.ones(n)
    for at in kick_times:
        i = int(at*SR)
        if i >= n:
            continue
        m = min(n-i, int(.45*SR))
        env[i:i+m] = np.minimum(env[i:i+m], 1-depth*np.exp(-np.arange(m)/SR*release))
    return env


def sweep_open(x, start_hz, end_hz, until):
    """Low-pass that opens from start_hz to end_hz over the first `until` seconds (intro filter)."""
    n = min(len(x), int(until*SR))
    if n <= 0:
        return x
    steps = 6
    cutoffs = [start_hz*(end_hz/start_hz)**(k/(steps-1)) for k in range(steps)]
    versions = [lp(x[:n+int(.5*SR)], hz)[:n] for hz in cutoffs]
    position = (np.linspace(0, 1, n)**2)*(steps-1)
    low = np.minimum(position.astype(int), steps-2)
    frac = position-low
    stack = np.stack(versions)
    head = stack[low, np.arange(n)]*(1-frac)+stack[low+1, np.arange(n)]*frac
    out = x.copy()
    out[:n] = head
    return out


# --- Arrangement helpers ----------------------------------------------------------------

def _notes(bar_start, phrase, render, out, transpose=0):
    for step, note, length in phrase:
        if note:
            place(out, render(midi(note+transpose), length*STEP), bar_start+step*STEP)


def _lead_on(b):
    return b >= 4 and (b-4) % 8 < 4


def _finish(buses, seconds):
    """Sum the buses, fade the end, normalise loudness and keep the peaks soft."""
    n = int(seconds*SR)+1
    mixdown = np.zeros(n)
    for bus in buses:
        mixdown[:len(bus)] += bus[:n]
    mixdown -= mixdown.mean()
    rms = np.sqrt((mixdown**2).mean()) or 1
    mixdown *= TARGET_RMS/rms
    mixdown = np.tanh(mixdown*1.25)/1.25
    fade = min(n, int(.5*SR))
    mixdown[-fade:] *= np.linspace(1, 0, fade)
    start = min(n, int(.01*SR))
    mixdown[:start] *= np.linspace(0, 1, start)
    return mixdown


def _drums_basic(out, b, t0, kicks, snares, hats, open_hats=(), claps=(), kick_times=None):
    for s in kicks:
        place(out, kick(), t0+s*STEP)
        if kick_times is not None:
            kick_times.append(t0+s*STEP)
    for s in snares:
        place(out, snare(), t0+s*STEP)
    for s in claps:
        place(out, clap(), t0+s*STEP)
    for i, s in enumerate(hats):
        place(out, hat(False, 20+(b*16+i) % 7)*(.75 if s % 4 else .5), t0+s*STEP)
    for s in open_hats:
        place(out, hat(True, 27), t0+s*STEP)


def _intro_tail(out, b, t0, seconds):
    """Riser and snare roll into the drop at bar 2; crash on every 4th bar from the drop."""
    if b == 1 and seconds > 5:
        place(out, riser(BAR), t0)
        for k in range(8):
            place(out, snare()*(.15+.07*k), t0+BAR/2+k*STEP)
    if b >= 2 and (b-2) % 4 == 0:
        place(out, crash(), t0)


# --- The tracks ------------------------------------------------------------------------------

def _synthwave(seconds):
    n = int(seconds*SR)+1
    drums, bass_bus, pads, arp, leads = (np.zeros(n) for _ in range(5))
    chords = ((57, 60, 64), (57, 60, 65), (55, 60, 64), (55, 59, 62))       # Am F C G
    roots = (33, 29, 36, 31)
    melody = (((0, 76, 4), (4, 74, 2), (6, 72, 2), (8, 74, 4), (12, 76, 4)),
              ((0, 77, 6), (6, 76, 2), (8, 72, 8)),
              ((0, 79, 4), (4, 76, 4), (8, 72, 2), (10, 74, 2), (12, 76, 4)),
              ((0, 74, 6), (6, 71, 2), (8, 74, 4), (12, 79, 4)))
    kicks = []
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, b % 4
        for k in range(8):
            note = roots[c]+(12 if k % 2 else 0)
            place(bass_bus, bass(midi(note), STEP*1.8, 900 if b >= 2 else 500), t0+k*BEAT/2)
        for note in chords[c]:
            place(pads, supersaw(midi(note), BAR, 2200, .25, .3), t0)
        if b >= 2:
            for k in range(16):
                note = chords[c][(0, 1, 2, 1)[k % 4]]+12+(12 if k % 8 >= 4 else 0)
                place(arp, pluck(midi(note), STEP*.9, 2600, 14, .25)*.55, t0+k*STEP)
            _drums_basic(drums, b, t0, (0, 8), (4, 12), (2, 6, 10, 14), kick_times=kicks)
            if b % 4 == 3:
                for k, s in enumerate((12, 13, 14, 15)):
                    place(drums, tom(52-k*3), t0+s*STEP)
        else:
            _drums_basic(drums, b, t0, (), (), (2, 6, 10, 14))
        if _lead_on(b):
            _notes(t0, melody[c], lambda f, d: lead(f, d, 3400)*.5, leads)
        _intro_tail(drums, b, t0, seconds)
    duck = sidechain(n, kicks, .55)
    pads = sweep_open(reverb(pads*duck, 2.2, .35), 500, 4000, 2*BAR)
    return _finish((drums*.95, bass_bus*duck*.55, pads*.22, delay(arp, .375)*.5,
                    reverb(delay(leads, .375, .3, .25), 1.8, .25)*.55), seconds)


def _lofi(seconds):
    n = int(seconds*SR)+1
    drums, keys, low, melody_bus = (np.zeros(n) for _ in range(4))
    chords = ((53, 57, 60, 64), (52, 55, 59, 62), (50, 53, 57, 60), (48, 52, 55, 59))   # Fmaj7 Em7 Dm7 Cmaj7
    roots = (41, 40, 38, 36)
    melody = (((2, 72, 2), (4, 76, 4), (10, 74, 2), (12, 72, 4)),
              ((0, 71, 4), (6, 67, 2), (8, 69, 8)),
              ((2, 65, 2), (4, 69, 2), (6, 72, 4), (12, 74, 4)),
              ((0, 76, 6), (8, 79, 4), (12, 76, 4)))
    swing = STEP*.33
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, b % 4
        for hit, length in ((0, 7), (7, 9)):
            for i, note in enumerate(chords[c]):
                place(keys, epiano(midi(note), length*STEP)*(.9 if hit == 0 else .6), t0+hit*STEP+i*.018)
        place(low, bass(midi(roots[c]), 6*STEP, 380, 1.1, 'square')*.9, t0)
        place(low, bass(midi(roots[c]+(7 if b % 2 else 12)), 4*STEP, 380, 1.1, 'square')*.7, t0+10*STEP)
        if b >= 1:
            for s in (0, 10) if b % 2 == 0 else (0, 3, 10):
                place(drums, kick(1.3)*(.8 if s else 1), t0+s*STEP)
            place(drums, snare(210, 5, .2)*.9, t0+8*STEP)
            place(drums, rim()*.6, t0+14*STEP)
            for k in range(8):
                place(drums, hat(False, 31+k)*(.55 if k % 2 else .8), t0+k*2*STEP+(swing if k % 2 else 0))
        if b >= 2:
            _notes(t0, melody[c], lambda f, d: bell(f, d)*.32, melody_bus)
    crackle = np.zeros(n)
    rng = _rng(77)
    for at in rng.uniform(0, seconds, int(seconds*9)):
        place(crackle, rng.uniform(.04, .16)*np.exp(-np.arange(80)/12)*rng.choice((-1, 1)), at)
    hiss = lp(_noise(n, 78), 6000)*.012
    mix_ = _finish((lp(drums, 6500)*1.0, reverb(keys, 1.8, .3)*.4, low*.5, reverb(delay(melody_bus, .375, .35, .3), 2.0, .35),
                    crackle+hiss), seconds)
    return mix_


def _house(seconds):
    n = int(seconds*SR)+1
    drums, stabs, bass_bus, hook = (np.zeros(n) for _ in range(4))
    chords = ((57, 60, 64, 67), (57, 60, 62, 65))     # Am7 Dm7
    roots = (45, 38)
    phrases = (((0, 76, 1), (2, 76, 1), (3, 79, 2), (6, 76, 2), (8, 74, 2), (10, 72, 2), (12, 74, 3)),
               ((0, 77, 1), (2, 77, 1), (3, 81, 2), (6, 77, 2), (8, 76, 2), (10, 74, 2), (12, 72, 3)))
    kicks = []
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, (b//2) % 2
        _drums_basic(drums, b, t0, (0, 4, 8, 12), (), tuple(range(1, 16, 2)) if b >= 2 else (),
                     (2, 6, 10, 14) if b >= 2 else (), (4, 12) if b >= 1 else (), kicks)
        if b >= 2:
            for s in range(16):
                place(drums, shaker(40+s % 5)*(.8 if s % 2 else .4), t0+s*STEP)
        for s in (0, 3, 6, 10, 12):
            for note in chords[c]:
                place(stabs, organ(midi(note), 2*STEP), t0+s*STEP)
        for s in (2, 6, 10, 14):
            place(bass_bus, bass(midi(roots[c]+(12 if s == 14 else 0)), 1.6*STEP, 600, 2.0), t0+s*STEP)
        if _lead_on(b):
            _notes(t0, phrases[c], lambda f, d: pluck(f, max(d, .2), 4200, 7, .4)*.7, hook)
        _intro_tail(drums, b, t0, seconds)
    duck = sidechain(n, kicks, .7, 9)
    stabs = sweep_open(reverb(stabs*duck, 1.2, .25), 350, 6000, 2*BAR)
    return _finish((drums*.85, stabs*.42, sweep_open(bass_bus*duck, 200, 900, 2*BAR)*.5,
                    reverb(delay(hook, .25, .3, .3), 1.5, .3)*.5), seconds)


def _trap(seconds):
    n = int(seconds*SR)+1
    drums, low, bells, pads = (np.zeros(n) for _ in range(4))
    chords = ((60, 63, 67), (60, 63, 68), (60, 65, 68), (59, 62, 67))     # Cm Ab Fm G
    roots = (36, 32, 41, 43)
    melody = (((0, 72, 2), (2, 75, 2), (4, 79, 4), (10, 77, 2), (12, 75, 4)),
              ((0, 72, 2), (2, 75, 2), (4, 80, 4), (10, 79, 2), (12, 75, 4)),
              ((0, 72, 2), (2, 77, 2), (4, 80, 4), (10, 79, 2), (12, 77, 4)),
              ((0, 74, 2), (2, 77, 2), (4, 79, 4), (8, 83, 4), (12, 79, 4)))
    previous = None
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, b % 4
        for note in chords[c]:
            place(pads, supersaw(midi(note), BAR, 1300, .4, .4, 3, .007), t0)
        _notes(t0, melody[c], lambda f, d: bell(f, d)*.45, bells)
        if b < 2:
            continue
        pattern = ((0, 7), (7, 3), (10, 6)) if b % 2 == 0 else ((0, 6), (6, 2), (8, 2), (11, 5))
        for i, (s, length) in enumerate(pattern):
            root = roots[c]+(12 if (b % 2 and i == 2) else 0)
            place(low, sub808(midi(root), length*STEP, midi(previous) if previous and previous != root else None),
                  t0+s*STEP)
            place(drums, kick(1.2)*.8, t0+s*STEP)
            previous = root
        place(drums, clap(), t0+8*STEP)
        place(drums, snare(220, 6, .2)*.7, t0+8*STEP)
        times = [t0+k*2*STEP for k in range(8)]
        if b % 2:   # rolls: triplets on the last beat, 32nds every fourth bar
            times = [x for x in times if x < t0+12*STEP]
            sub = 6 if b % 4 == 1 else 8
            times += [t0+12*STEP+k*BEAT/sub for k in range(sub)]
        for i, at in enumerate(times):
            place(drums, hat(False, 50+i % 9)*(.7 if i % 2 else .9), at)
        if b % 4 == 3:
            place(drums, hat(True, 59)*.6, t0+14*STEP)
        _intro_tail(drums, b, t0, seconds)
    return _finish((drums*1.05, low*.6, reverb(delay(bells, .375, .35, .3), 2.4, .4)*.42,
                    sweep_open(reverb(pads, 2.5, .4), 300, 2500, 2*BAR)*.22), seconds)


def _disco(seconds):
    n = int(seconds*SR)+1
    drums, bass_bus, gtr, strings, horns = (np.zeros(n) for _ in range(5))
    chords = ((57, 60, 62, 65), (55, 59, 62, 65), (55, 59, 62, 64), (55, 57, 61, 64))   # Dm7 G7 Em7 A7
    roots = (38, 43, 40, 45)
    hook = (((0, 74, 2), (2, 77, 2), (4, 81, 3), (8, 79, 2), (10, 77, 2), (12, 74, 4)),
            ((0, 74, 2), (2, 77, 2), (4, 79, 4), (10, 77, 2), (12, 74, 2), (14, 72, 2)),
            ((0, 71, 2), (2, 74, 2), (4, 79, 4), (8, 76, 4), (12, 74, 4)),
            ((0, 73, 4), (4, 76, 4), (8, 79, 2), (10, 81, 6)))
    kicks = []
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, b % 4
        _drums_basic(drums, b, t0, (0, 4, 8, 12), (), (), (2, 6, 10, 14) if b >= 2 else (), (4, 12), kicks)
        if b >= 2:
            for s in range(16):
                place(drums, shaker(41+s % 3)*(1 if s % 4 == 2 else .45), t0+s*STEP)
        r = roots[c]
        for s, note in ((0, r), (2, r+12), (4, r), (6, r+12), (8, r), (10, r+12), (12, r), (13, r+12), (14, r+10), (15, r+12)):
            place(bass_bus, bass(midi(note), STEP*(1.6 if s < 12 else .9), 1100, 2.2, 'square'), t0+s*STEP)
        top = chords[c][-2:]
        for s in range(16):
            if s % 4 == 2:
                for note in top:
                    place(gtr, pluck(midi(note+12), .09, 2400, 30)*.6, t0+s*STEP)
            elif s % 2:
                place(gtr, bp(_noise(int(.03*SR), 60+s), 1500, 3000)*np.exp(-np.arange(int(.03*SR))/SR*90)*.25, t0+s*STEP)
        if b >= 2:
            for note in chords[c]:
                place(strings, supersaw(midi(note+12), BAR*.95, 4200, .08, .2, 5, .009), t0)
            if b % 2:
                place(strings, supersaw(midi(chords[c][0]+24), 2*STEP, 5000, .005, .05)*1.2, t0+14*STEP)
        if _lead_on(b):
            _notes(t0, hook[c], lambda f, d: brass(f, d)*.6, horns)
        _intro_tail(drums, b, t0, seconds)
    duck = sidechain(n, kicks, .35)
    return _finish((drums*.85, bass_bus*.36, sweep_open(gtr, 600, 5000, 2*BAR)*1.1, reverb(strings*duck, 1.8, .3)*.22,
                    reverb(horns, 1.4, .25)*.7), seconds)


def _carica(seconds):
    n = int(seconds*SR)+1
    drums, guitars, leads = (np.zeros(n) for _ in range(3))
    roots = (40, 36, 43, 38)      # Em C G D
    chant = (((0, 71, 4), (4, 71, 2), (6, 74, 2), (8, 76, 6), (14, 74, 2)),
             ((0, 72, 4), (4, 72, 2), (6, 74, 2), (8, 76, 4), (12, 79, 4)),
             ((0, 79, 4), (4, 78, 2), (6, 76, 2), (8, 74, 6), (14, 71, 2)),
             ((0, 74, 6), (6, 76, 2), (8, 78, 4), (12, 74, 4)))
    for b in range(int(seconds/BAR)+1):
        t0, c = b*BAR, b % 4
        if b < 2:   # intro: muted chugs and a floor tom pulse
            for k in range(8):
                place(guitars, lp(power_chord(roots[c], STEP*.8), 900)*.8, t0+k*BEAT/2)
            for k in range(4):
                place(drums, tom(40)*.7, t0+k*BEAT)
        else:
            for k in range(8):
                length = STEP*(1.9 if k % 2 == 0 else 1.6)
                place(guitars, power_chord(roots[c], length), t0+k*BEAT/2)
            _drums_basic(drums, b, t0, (0, 6, 8, 10) if b % 2 else (0, 8, 10), (4, 12), (0, 2, 4, 6, 8, 10, 12, 14))
            if b % 4 == 3:
                for k, s in enumerate((12, 13, 14, 15)):
                    place(drums, tom(50-k*3), t0+s*STEP)
            for s in (0, 4, 8, 12):   # the hand claps of the crowd
                if s in (4, 12):
                    place(drums, clap()*.7, t0+s*STEP)
        if _lead_on(b):
            previous = None
            for step, note, length in chant[c]:
                place(leads, lead(midi(note), length*STEP, 3000, 'square', midi(previous) if previous else None)*.5,
                      t0+step*STEP)
                previous = note
        _intro_tail(drums, b, t0, seconds)
    return _finish((drums*.75, reverb(guitars, .9, .15)*.7, reverb(delay(leads, .25, .25, .2), 1.6, .3)*.65), seconds)


RENDER = {'synthwave': _synthwave, 'lofi': _lofi, 'house': _house, 'trap': _trap, 'disco': _disco,
          'carica': _carica}


@lru_cache(maxsize=12)
def _cached(track, seconds):
    return RENDER[track](seconds)


def render(track, seconds):
    """The track as mono samples at 44.1 kHz, `seconds` long (it loops in 8-bar phrases)."""
    return _cached(track, round(max(1.0, float(seconds)), 2)).copy()


@lru_cache(maxsize=12)
def preview_wav(track, seconds=14.0):
    """A light WAV (22 kHz, bytes) of a track, to listen to it in the editor."""
    import io
    import wave
    import sounds
    samples = lp(sounds.chiptune(seconds, 0, track=track)*.9, 10000, 4)[::2]
    data = (np.clip(np.tanh(samples*1.4)*.8, -1, 1)*32767).astype('<i2')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR//2)
        w.writeframes(data.tobytes())
    return buffer.getvalue()
