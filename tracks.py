"""Real music (3.8): CC0 tracks shipped with the app and the user's own track.

The synthesised tracks in music.py run at 120 bpm with the drop at 4 s. Real
tracks have their own tempo and their strongest moment somewhere in the middle,
so this module:

1. decodes any audio file with the ffmpeg that imageio-ffmpeg already ships
   (mp3, m4a, wav, ogg... no extra packages on Streamlit Cloud);
2. finds the "drop" (where the energy jumps and stays up) and the tempo;
3. cuts the track so the drop lands exactly on the drop of the video (4 s),
   loops it with a crossfade if the video is longer, fades the end;
4. tells the animations the real beat, so pulses and camera punches follow it.

The bundled clips (assets/music) are excerpts of CC0 tracks, already cut
around their drop: see assets/music/CREDITS.md.
"""
from __future__ import annotations

import hashlib
import subprocess
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent
FOLDER = ROOT/'assets'/'music'
DROP = 4.0              # where the video's drop is (animations.DROP)
TARGET_RMS = .15
MAX_UPLOAD = 25_000_000
UPLOAD_TYPES = ('mp3', 'm4a', 'aac', 'wav', 'ogg', 'oga', 'flac', 'opus', 'mp4')

# id -> clip file, credits, mood, tempo and where the drop is inside the clip (seconds).
LIBRARY = {
    'cc0_robots': dict(file='big_ass_robots.m4a', title='Big Ass Robots', artist='HoliznaCC0', mood='hip-hop pesante',
                       bpm=90.0, drop=6.01, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_club': dict(file='mutant_club.m4a', title='Mutant Club', artist='HoliznaCC0', mood='elettronica scura',
                     bpm=140.0, drop=6.007, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_ritmo': dict(file='lost_in_the_rythm.m4a', title='Lost In The Rythm', artist='HoliznaCC0', mood='boom bap',
                      bpm=105.0, drop=6.027, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_city': dict(file='city_lights.m4a', title='City Lights', artist='HoliznaCC0', mood='lo-fi hip-hop',
                     bpm=90.0, drop=5.99, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_sunglasses': dict(file='sunglasses.m4a', title='Sunglasses', artist='Loyalty Freak Music', mood='r&b beat',
                           bpm=87.5, drop=6.032, source='freemusicarchive.org/music/Loyalty_Freak_Music'),
    'cc0_funk': dict(file='funkeriffic.m4a', title='Funkeriffic', artist='FreePD', mood='funk',
                     bpm=112.0, drop=6.152, source='freepd.com'),
    'cc0_rush': dict(file='rush.m4a', title='Rush', artist='FreePD', mood='veloce, energica',
                     bpm=150.0, drop=6.0, source='freepd.com'),
    'cc0_battle': dict(file='battle_ready.m4a', title='Battle Ready', artist='FreePD', mood='cinematica',
                       bpm=88.0, drop=6.179, source='freepd.com'),
    # 3.13: ten more, for the genres that were missing (rock, fast electronics, epic, disco, synthwave, dub)
    'cc0_punk': dict(file='punk.m4a', title='Punk', artist='HoliznaCC0', mood='punk rock',
                      bpm=120.0, drop=6.0, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_snowboard': dict(file='snowboard_rock.m4a', title='Snowboard Rock', artist='Loyalty Freak Music', mood='rock',
                           bpm=85.0, drop=6.0, source='freemusicarchive.org/music/Loyalty_Freak_Music'),
    'cc0_uberpunch': dict(file='uberpunch.m4a', title='Uberpunch', artist='FreePD', mood='elettronica potente',
                           bpm=150.0, drop=6.0, source='freepd.com'),
    'cc0_hardmode': dict(file='hard_mode.m4a', title='Hard Mode', artist='HoliznaCC0', mood='elettronica veloce',
                          bpm=150.0, drop=6.0, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_hero': dict(file='rising_hero.m4a', title='Rising Hero', artist='HoliznaCC0', mood='eroica',
                      bpm=119.9, drop=6.0, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_blockbuster': dict(file='epic_blockbuster.m4a', title='Epic Blockbuster 2', artist='FreePD', mood='trailer epico',
                             bpm=120.0, drop=6.0, source='freepd.com'),
    'cc0_boogie': dict(file='downtown_boogie.m4a', title='Downtown Boogie', artist='FreePD', mood='disco boogie',
                        bpm=105.0, drop=6.0, source='freepd.com'),
    'cc0_retro': dict(file='retro_synths.m4a', title='Retro Synths', artist='HoliznaCC0', mood='synthwave',
                       bpm=119.9, drop=6.0, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_goodvibes': dict(file='good_vibes.m4a', title='Good Vibes', artist='HoliznaCC0', mood='positiva, rilassata',
                           bpm=90.0, drop=6.0, source='freemusicarchive.org/music/holiznacc0'),
    'cc0_dub': dict(file='sunday_dub.m4a', title='Sunday Dub', artist='FreePD', mood='reggae dub',
                     bpm=102.0, drop=6.0, source='freepd.com'),
}
CUSTOM = 'mio'          # the menu entry for the user's own track
_uploads: OrderedDict = OrderedDict()     # 'mio:<hash>' -> dict(samples, drop, bpm, name)


def is_real(track):
    return isinstance(track, str) and (track in LIBRARY or track.startswith(CUSTOM+':'))


# --- Decoding -------------------------------------------------------------------------------

def decode(data, sr=SR, seconds=None):
    """Mono float32 samples from audio bytes or a path (any format ffmpeg reads)."""
    import imageio_ffmpeg
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error']
    source = None
    if isinstance(data, (str, Path)):
        command += ['-i', str(data)]
    else:
        command += ['-i', 'pipe:0']
        source = bytes(data)
    if seconds:
        command += ['-t', str(seconds)]
    command += ['-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', 'pipe:1']
    result = subprocess.run(command, input=source, capture_output=True, timeout=120)
    if result.returncode != 0 or not result.stdout:
        raise ValueError('Il file non sembra un audio leggibile: '+result.stderr.decode('utf8', 'replace').strip()[-160:])
    samples = np.frombuffer(result.stdout, np.float32).astype(np.float64)
    if len(samples) < sr*3:
        raise ValueError('Il brano è troppo corto (servono almeno 3 secondi).')
    return samples


# --- Analysis: tempo and drop ------------------------------------------------------------------

def _frames(x, sr, hop=512, win=2048):
    n = max(1, (len(x)-win)//hop)
    index = np.arange(win)[None, :]+hop*np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[index]*np.hanning(win), axis=1))
    freqs = np.fft.rfftfreq(win, 1/sr)
    return spec, freqs, sr/hop


def _pulse(flux, fps, bpm, phases=24):
    """How strongly the onsets fall on a steady grid at `bpm` (best phase), relative to the average."""
    period = fps*60/bpm
    count = int((len(flux)-1)/period)
    if count < 8:
        return 0.0
    grid = period*np.arange(count)
    offsets = np.linspace(0, period, phases, endpoint=False)
    index = np.minimum((offsets[:, None]+grid[None, :]).astype(int), len(flux)-1)
    return float(flux[index].mean(1).max()/(flux.mean()+1e-9))


def _tempo(flux, fps):
    """Beats per minute: the steady grid that the onsets hit hardest (tempo is exact in produced music),
    folded into 80-160."""
    f = flux[:int(fps*75)]
    coarse = {bpm: _pulse(f, fps, bpm, 12) for bpm in np.arange(70, 180, .5)}
    tops = sorted(coarse, key=coarse.get, reverse=True)[:6]
    best, best_bpm = -1.0, 120.0
    for top in tops:
        for bpm in np.arange(top-.6, top+.6, .05):
            score = _pulse(f, fps, bpm)
            if score > best:
                best, best_bpm = score, float(bpm)
    if best_bpm < 80 and _pulse(f, fps, best_bpm*2) >= .75*best:
        best_bpm *= 2
    elif best_bpm > 160 and _pulse(f, fps, best_bpm/2) >= .75*best:
        best_bpm /= 2
    return best_bpm


def _on_grid(at, kick, flux, fps, bpm, span=30):
    """`at` moved onto the nearest beat of the track's grid (phase from the kicks around it)."""
    period = fps*60/bpm
    lo = max(0, int(at*fps-span*fps/2))
    hi = min(len(flux), lo+int(span*fps))
    weight = kick[lo:hi]/(kick[lo:hi].mean()+1e-9)+.5*flux[lo:hi]/(flux[lo:hi].mean()+1e-9)
    count = int((hi-lo-1)/period)
    if count < 4:
        return at
    offsets = np.linspace(0, period, 64, endpoint=False)
    index = np.minimum((offsets[:, None]+period*np.arange(count)[None, :]).astype(int), len(weight)-1)
    phase = lo+offsets[int(np.argmax(weight[index].mean(1)))]
    k = round((at*fps-phase)/period)
    return float((phase+k*period)/fps)


def analyse(samples, sr=SR, after=20, earliest=6):
    """{'drop': seconds, 'bpm': tempo, 'rise': dB} of a whole track (at most its first 5 minutes).

    after: seconds of music needed after the drop; earliest: the drop is searched from here."""
    x = samples[:sr*300]
    step = max(1, sr//22050)
    x = x[::step]
    rate = sr/step
    spec, freqs, fps = _frames(x, rate)
    logspec = np.log1p(spec*10)
    flux = np.maximum(0, np.diff(logspec, axis=0)).sum(1)
    flux = np.maximum(0, flux-np.convolve(flux, np.ones(16)/16, 'same'))
    kick = np.maximum(0, np.diff(np.log1p(spec[:, freqs < 160].sum(1)*10)))
    bpm = _tempo(flux, fps)
    energy = 10*np.log10((spec**2).sum(1)+1e-9)
    q = 4                                      # quarter-second blocks of energy
    edges = np.round(np.arange(0, len(energy)/fps*q)*fps/q).astype(int)
    e = np.array([energy[a:b].mean() for a, b in zip(edges, edges[1:]) if b > a])
    duration = len(x)/rate
    best, best_at = -1e9, None
    loud = np.median(e)
    first = max(int(earliest*q), 3*q)
    for i in range(first, max(first+1, len(e)-int(after*q))):
        rise = e[i:i+3*q].mean()-e[i-3*q:i].mean()
        level = e[i:i+8*q].mean()-loud
        score = rise+.35*level
        if score > best:
            best, best_at = score, i
    rise = e[best_at:best_at+3*q].mean()-e[best_at-3*q:best_at].mean() if best_at is not None else 0
    if best_at is None or rise < 1.5:          # no real drop: the loudest stretch
        window = int(10*q)
        if len(e) > window+first+int(after*q):
            sums = np.convolve(e, np.ones(window), 'valid')
            best_at = first+int(np.argmax(sums[first:len(e)-int(after*q)]))
        else:
            best_at = min(len(e)-1, first)
    at = best_at/q
    at = _on_grid(at, kick, flux, fps, bpm)
    return {'drop': round(float(min(at, duration-3)), 3), 'bpm': round(float(bpm), 1), 'rise': round(float(rise), 1)}


# --- Shaping a clip for a video ----------------------------------------------------------------

def _shape(samples, drop, seconds, drop_at=DROP, sr=SR):
    """The track moved so `drop` lands on `drop_at`, `seconds` long, looped and faded."""
    n = int(seconds*sr)+1
    start = int(round((drop-drop_at)*sr))
    if start >= 0:
        piece = samples[start:]
    else:                                       # the drop comes earlier than the video's: silence first
        piece = np.concatenate([np.zeros(-start), samples])
    if len(piece) < n:                          # loop the part after the drop, with a short crossfade
        loop = samples[int(drop*sr):] if drop*sr < len(samples)-sr*2 else samples
        fade = min(int(.08*sr), len(loop)//4)
        while len(piece) < n:
            ramp = np.linspace(0, 1, fade)
            joined = piece[-fade:]*(1-ramp)+loop[:fade]*ramp
            piece = np.concatenate([piece[:-fade], joined, loop[fade:]])
    out = piece[:n].copy()
    out -= out.mean()
    body = out[int(max(0, drop_at)*sr):] if len(out) > int(drop_at*sr)+sr else out
    rms = np.sqrt((body**2).mean()) or 1
    out *= TARGET_RMS/rms
    out = np.tanh(out*1.3)/1.3
    head = min(n, int((.35 if start > 0 else .01)*sr))
    out[:head] *= np.linspace(0, 1, head)**2
    tail = min(n, int(.9*sr))
    out[-tail:] *= np.linspace(1, 0, tail)**1.5
    return out


@lru_cache(maxsize=8)
def _clip(track):
    meta = LIBRARY[track]
    return decode(FOLDER/meta['file'])


def info(track):
    """(drop inside the samples, bpm) of a real track; None for the synthesised ones."""
    if track in LIBRARY:
        return LIBRARY[track]['drop'], LIBRARY[track]['bpm']
    if isinstance(track, str) and track in _uploads:
        return _uploads[track]['drop'], _uploads[track]['bpm']
    return None


def render(track, seconds, drop_at=DROP):
    """Mono samples at 44.1 kHz for a video `seconds` long, with the drop on `drop_at`."""
    if track in LIBRARY:
        samples, drop = _clip(track), LIBRARY[track]['drop']
    elif track in _uploads:
        samples, drop = _uploads[track]['samples'], _uploads[track]['drop']
    else:
        raise KeyError(f'Brano non disponibile: {track} (ricaricalo)')
    return _shape(samples, drop, max(1.0, float(seconds)), drop_at)


def beat(track):
    """(seconds per beat, a time on the beat) for a real track in a video; None otherwise."""
    found = info(track)
    if not found:
        return None
    return 60/found[1], DROP


def preview_wav(track, seconds=14.0):
    """A light WAV (22 kHz) of the part that will play, to listen to it in the editor."""
    import io
    import wave
    samples = render(track, seconds)[::2]
    data = (np.clip(samples*.95, -1, 1)*32767).astype('<i2')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR//2)
        w.writeframes(data.tobytes())
    return buffer.getvalue()


# --- The user's own track ---------------------------------------------------------------------

def register(data, name='Il mio brano', drop=None):
    """Decode and analyse an uploaded file once; returns its key ('mio:<hash>') and the analysis.

    drop: seconds into the track chosen by hand (None = found automatically)."""
    if len(data) > MAX_UPLOAD:
        raise ValueError('File troppo grande (massimo 25 MB): usa un mp3 o un m4a.')
    key = CUSTOM+':'+hashlib.sha256(bytes(data)).hexdigest()[:16]
    entry = _uploads.get(key)
    if entry is None:
        samples = decode(data, seconds=300)
        found = analyse(samples)
        entry = dict(samples=samples, auto=found['drop'], bpm=found['bpm'], rise=found['rise'],
                     duration=len(samples)/SR, name=str(name)[:80])
        _uploads[key] = entry
        while len(_uploads) > 6:
            _uploads.popitem(last=False)
    _uploads.move_to_end(key)
    entry['drop'] = float(min(max(0.0, drop), entry['duration']-1)) if drop is not None else entry['auto']
    return key, {k: entry[k] for k in ('drop', 'auto', 'bpm', 'rise', 'duration', 'name')}


def resolve(track, config):
    """The menu choice 'mio' becomes the key of the uploaded track (if there is one)."""
    if track == CUSTOM:
        key = config.get('music_custom') if isinstance(config, dict) else None
        return key if key in _uploads else None
    return track


def label(track):
    meta = LIBRARY.get(track)
    return f"{meta['title']} - {meta['artist']} ({meta['mood']})" if meta else track
