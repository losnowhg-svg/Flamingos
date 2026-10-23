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
