"""Retro CRT sound design, synthesised in NumPy: no audio files, no licences.

Sounds are placed as timed events (blips when elements appear, a transition
sound between scenes, a faint tube hum underneath) and muxed into the MP4 with
the ffmpeg binary that imageio-ffmpeg already ships.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
# Major pentatonic, so any run of entrance blips sounds like a game menu.
SCALE = (523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.51)


def _t(seconds):
    return np.arange(max(1, int(seconds*SR)))/SR


def _env(n, attack=.004, release=None):
    env = np.ones(n)
    a = max(1, int(attack*SR))
    env[:a] = np.linspace(0, 1, a)
    r = n-a if release is None else max(1, min(n-a, int(release*SR)))
    env[-r:] *= np.linspace(1, 0, r)**2
    return env


def _square(freq, t):
    return np.sign(np.sin(2*np.pi*freq*t))


def _noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, n)


def _lowpass(x, amount=.2):
    """One-pole low-pass filter."""
    try:
        from scipy.signal import lfilter
        return lfilter([amount], [1, amount-1], x)
    except ImportError:  # SciPy is optional: plain loop fallback
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += amount*(v-acc)
            y[i] = acc
        return y


def blip(index=0):
    t = _t(.085)
    f = SCALE[index % len(SCALE)]
    tone = _square(f, t)*.6+_square(f*2, t)*.15
    return tone*_env(len(t), .002, .07)*.32


def channel_change(seconds):
    n = int(seconds*SR)
    noise = _noise(n, 1)
    noise = noise-_lowpass(noise, .05)  # thin, hissy static
    t = _t(seconds)
    env = np.minimum(1, np.minimum(t/.06, (seconds-t)/.12))
    click = np.zeros(n); click[:300] = np.linspace(1, 0, 300)*.8
    return noise*env*.45+click


def power_cycle(seconds):
    half = seconds/2
    t = _t(half)
    sweep = np.sin(2*np.pi*np.cumsum(np.linspace(1400, 60, len(t)))/SR)*_env(len(t), .002, half*.9)*.35
    thunk = np.sin(2*np.pi*55*t)*np.exp(-t*14)*.7
    whine = np.sin(2*np.pi*7800*t)*np.minimum(1, t/.25)*.05
    on = thunk+whine+_noise(len(t), 2)*np.exp(-t*30)*.25
    return np.concatenate([sweep, on])


def glitch(seconds):
    n = int(seconds*SR)
    out = np.zeros(n)
    rng = np.random.default_rng(3)
    pos = 0
    while pos < n:
        length = int(rng.uniform(.015, .07)*SR)
        t = _t(length/SR)
        f = rng.choice((110, 220, 440, 880, 1760, 3520))
        burst = _square(f, t) if rng.random() < .6 else _noise(len(t), int(rng.integers(1e6)))
        crushed = np.round(burst*4)/4  # bit crush
        out[pos:pos+len(t)] += crushed[:n-pos]*rng.uniform(.15, .4)
        pos += length+int(rng.uniform(0, .03)*SR)
    return out*np.minimum(1, np.sin(np.linspace(0, np.pi, n))*2.5)


def rewind(seconds):
    t = _t(seconds)
    freq = 900+700*np.sin(2*np.pi*11*t)+np.linspace(0, 1200, len(t))
    chirp = np.sign(np.sin(2*np.pi*np.cumsum(freq)/SR))*.18
    tape = (_noise(len(t), 4)-_lowpass(_noise(len(t), 4), .3))*.12
    return (chirp+tape)*np.minimum(1, np.minimum(t/.05, (seconds-t)/.1))


def roll(seconds):
    t = _t(seconds)
    hum = (np.sin(2*np.pi*60*t)+.5*np.sin(2*np.pi*120*t))*.25
    whoosh = _lowpass(_noise(len(t), 5), .08)*3
    return (hum+whoosh*.3)*np.sin(np.linspace(0, np.pi, len(t)))


def cut(seconds):
    n = int(seconds*SR)
    out = np.zeros(n)
    mid = n//2
    out[mid:mid+500] = np.linspace(.9, 0, min(500, n-mid))
    return out


TRANSITION_SOUNDS = {'channel': channel_change, 'poweroff': power_cycle, 'glitch': glitch,
                     'rewind': rewind, 'roll': roll, 'cut': cut}


def hum(seconds):
    t = _t(seconds)
    return (np.sin(2*np.pi*50*t)*.012+np.sin(2*np.pi*15625*t)*.004)


def tick(index=0):
    t = _t(.03)
    return _square(1700+index*90, t)*_env(len(t), .001, .025)*.18


def power_on():
    t = _t(.6)
    thunk = np.sin(2*np.pi*55*t)*np.exp(-t*12)*.6
    whine = np.sin(2*np.pi*7800*t)*np.minimum(1, t/.2)*np.exp(-t*2)*.05
    crackle = _noise(len(t), 9)*np.exp(-t*18)*.3
    return thunk+whine+crackle


def _note(freq, seconds, duty=.5, volume=.3, release=.05):
    t = _t(seconds)
    wave_ = np.where((t*freq) % 1 < duty, 1.0, -1.0)
    return wave_*_env(len(t), .003, min(seconds*.8, release))*volume


def _seq(notes, step, duty=.5, volume=.3):
    """Notes (Hz, 0 = rest) one after another, step seconds each."""
    out = [(_note(f, step, duty, volume) if f else np.zeros(int(step*SR))) for f in notes]
    return np.concatenate(out)


C4, D4, E4, F4, G4, A4, B4 = 261.63, 293.66, 329.63, 349.23, 392.0, 440.0, 493.88
C5, E5, G5, C6 = 523.25, 659.25, 783.99, 1046.5


def impact(strong=1):
    t = _t(.35)
    thud = np.sin(2*np.pi*(70-30*t/.35)*t)*np.exp(-t*(10 if strong else 18))*(.9 if strong else .5)
    crack = _noise(len(t), 11)*np.exp(-t*40)*(.4 if strong else .2)
    return thud+crack


def whoosh(seconds=.32):
    n = int(seconds*SR)
    noise = _noise(n, 12)
    swept = noise-_lowpass(noise, .02+.25*np.linspace(0, 1, n).mean())
    return swept*np.sin(np.linspace(0, np.pi, n))*.35


def goal():
    arp = _seq([C5, E5, G5, C6, G5, C6], .07, .25, .28)
    cheer = _lowpass(_noise(int(.9*SR), 13), .12)*4*np.minimum(1, np.linspace(1.5, 0, int(.9*SR)))
    out = np.zeros(max(len(arp), len(cheer)))
    out[:len(arp)] += arp
    out[:len(cheer)] += cheer*.35
    return out


def fanfare():
    return _seq([G4, G4, G4, C5, 0, A4, C5, E5, 0, C6], .11, .5, .25)


def draw_jingle():
    return _seq([E5, C5, E5, C5, G4], .12, .25, .22)


def game_over():
    notes = _seq([C5, B4, A4, G4, F4, E4, D4, C4], .13, .5, .22)
    return notes*np.linspace(1, .6, len(notes))


def ding(level=1):
    freq = (880.0, 1174.66, 1567.98)[max(0, min(2, level))]
    t = _t(.4)
    return (np.sin(2*np.pi*freq*t)+.3*np.sin(2*np.pi*freq*2.01*t))*np.exp(-t*9)*.3


def climb():
    t = _t(.55)
    freq = 300+900*(t/.55)**1.5
    return np.sign(np.sin(2*np.pi*np.cumsum(freq)/SR))*_env(len(t), .005, .1)*.18


def crown():
    return _seq([C6, G5, C6, E5*2, C6*1.5], .06, .25, .2)


def shine():
    t = _t(.3)
    return np.sin(2*np.pi*(2000+3000*t/.3)*t)*np.exp(-t*8)*.1


def press_start(index=0):
    return _note(988 if index % 2 == 0 else 1319, .09, .25, .25)


def ready():
    return _seq([C5, G5, C6], .08, .25, .25)


def power_down():
    t = _t(.6)
    sweep = np.sin(2*np.pi*np.cumsum(np.linspace(900, 40, len(t)))/SR)*np.linspace(.35, 0, len(t))
    return sweep+_noise(len(t), 14)*np.exp(-(.6-t)*30)*.2


def chiptune(seconds, seed=0, bpm=120):
    """An original 8-bit loop: bass, arpeggio, kick and hi-hat. Quiet, under the effects."""
    beat = 60/bpm
    progressions = (((C4, E4, G4), (A4/2*2, C5, E5), (F4, A4, C5), (G4, B4, D4*2)),
                    ((A4/2*2, C5, E5), (F4, A4, C5), (C4, E4, G4), (G4, B4, D4*2)))
    chords = progressions[seed % len(progressions)]
    n = int(seconds*SR)+1
    out = np.zeros(n)
    bar = 4*beat
    for b in range(int(seconds/bar)+1):
        chord = chords[b % 4]
        start = int(b*bar*SR)
        for k in range(8):  # eighth-note arpeggio
            note = _note(chord[k % 3]*2, beat/2, .25, .07)
            i = start+int(k*beat/2*SR)
            out[i:i+len(note)] += note[:max(0, n-i)]
        for k in range(4):  # bass on the beat
            note = _note(chord[0]/2, beat*.9, .5, .1)
            i = start+int(k*beat*SR)
            out[i:i+len(note)] += note[:max(0, n-i)]
            if k in (0, 2):
                t = _t(.12)
                kick = np.sin(2*np.pi*(120-80*t/.12)*t)*np.exp(-t*30)*.25
                out[i:i+len(kick)] += kick[:max(0, n-i)]
            hat = _noise(int(.03*SR), 20+k)*np.linspace(.06, 0, int(.03*SR))
            j = i+int(beat/2*SR)
            out[j:j+len(hat)] += hat[:max(0, n-j)]
    fade = min(n, int(.4*SR))
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


SOUNDS = {'power': lambda i: power_on(), 'glitch': lambda i: glitch(.22)*.6, 'tick': lambda i: tick(i),
          'impact': lambda i: impact(i), 'whoosh': lambda i: whoosh(), 'goal': lambda i: goal(),
          'win': lambda i: fanfare(), 'draw': lambda i: draw_jingle(), 'loss': lambda i: game_over(),
          'ding': lambda i: ding(i), 'climb': lambda i: climb(), 'crown': lambda i: crown(),
          'shine': lambda i: shine(), 'start': lambda i: press_start(i), 'ready': lambda i: ready(),
          'power_off': lambda i: power_down()}


def entrance_times(prepared, compose):
    """When each element of a scene starts appearing, in seconds (mirrors each compose)."""
    layers = prepared[1]
    module = getattr(compose, '__module__', '')
    if module == 'matchday_renderer':
        timeline = {'title': .2, 'date': .6, 'home_logo': 1.25, 'away_logo': 1.55, 'vs': 2.05,
                    'home_name': 2.6, 'away_name': 2.9, 'kickoff': 3.4, 'venue': 3.75}
        return sorted(timeline.get(l.id, 0) for l in layers)
    if module == 'renderer':
        times = []
        for l in layers:
            times.append({'logo': .05, 'team': .35, 'title': .75, 'footer': 5.15, 'formation': 5.45}.get(
                l.id, 1.2+getattr(l, 'sequence', 0)*.53))
        return sorted(times)
    return sorted(1.0 if l.id == 'score' else .18+i*.12 for i, l in enumerate(layers))


def scene_events(prepared, compose, start=0.0, speed=1.0, until=None):
    import animations
    if animations.rich(prepared):
        out = []
        for t, kind, i in animations.events(prepared):
            at = start+t/speed
            if until is not None and at >= until:
                continue
            maker = SOUNDS.get(kind)
            out.append((at, maker(i) if maker else blip(i if isinstance(i, int) else 0)))
        if prepared[0].info.get('music'):
            length = (until-start) if until is not None else 12
            out.append((start, chiptune(max(1.0, length), len(prepared[1]))*.9))
        return out
    events = []
    for i, t in enumerate(entrance_times(prepared, compose)):
        at = start+t/speed
        if until is None or at < until:
            events.append((at, blip(i)))
    return events


def mix(events, seconds, volume=.8, ambient=True):
    n = int(seconds*SR)+1
    track = hum(seconds)[:n] if ambient else np.zeros(n)
    track = np.pad(track, (0, n-len(track)))
    for at, sound in events:
        start = int(at*SR)
        if start >= n:
            continue
        end = min(n, start+len(sound))
        track[start:end] += sound[:end-start]
    return np.tanh(track*1.4)*volume


def write_wav(path, samples):
    data = (np.clip(samples, -1, 1)*32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())


def mux(video_path, samples):
    """Replace the silent MP4 at video_path with one carrying the audio track."""
    import imageio_ffmpeg
    video_path = Path(video_path)
    wav = video_path.with_suffix('.wav')
    out = video_path.with_name(video_path.stem+'_audio.mp4')
    write_wav(wav, samples)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-i', str(video_path), '-i', str(wav),
               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError('Audio non aggiunto: '+result.stderr.strip()[:200])
    out.replace(video_path)
    wav.unlink(missing_ok=True)
    return str(video_path)


def add_scene_audio(video_path, prepared, compose, seconds, volume=.8, ambient=True):
    """Blips for a single editor's MP4."""
    return mux(video_path, mix(scene_events(prepared, compose, until=seconds), seconds, volume, ambient))
