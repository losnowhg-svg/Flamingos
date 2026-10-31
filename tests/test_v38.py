"""3.8: real music (CC0 clips and the user's own track), cut on the drop and followed by the beat."""
import io
import sys
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animations
import motion
import sounds
import tracks
import variety
from studio_state import MODULES, defaults

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def synthetic_song(bpm=100.0, drop=20.0, seconds=60.0, sr=tracks.SR):
    """Quiet pad, then kicks and hats from `drop` on: an easy, known drop and tempo."""
    t = np.arange(int(seconds*sr))/sr
    x = .03*np.sin(2*np.pi*220*t)
    beat = 60/bpm
    kick = np.sin(2*np.pi*55*np.arange(int(.15*sr))/sr)*np.exp(-np.arange(int(.15*sr))/sr*25)
    hat = np.random.default_rng(1).normal(0, 1, int(.03*sr))*np.exp(-np.arange(int(.03*sr))/sr*120)
    k = 0
    while drop+k*beat < seconds-1:
        at = int((drop+k*beat)*sr)
        x[at:at+len(kick)] += .8*kick
        h = int((drop+(k+.5)*beat)*sr)
        x[h:h+len(hat)] += .15*hat
        x[at:at+int(beat*sr)] += .1*np.sin(2*np.pi*110*t[at:at+int(beat*sr)])
        k += 1
    return x


def wav_bytes(x, sr=tracks.SR):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1)*32767).astype('<i2').tobytes())
    return buffer.getvalue()


class Library(unittest.TestCase):
    def test_every_clip_decodes_with_its_drop_and_credits(self):
        credits = (ROOT/'assets'/'music'/'CREDITS.md').read_text()
        for key, meta in tracks.LIBRARY.items():
            path = ROOT/'assets'/'music'/meta['file']
            self.assertLess(path.stat().st_size, 900_000, key)
            samples = tracks._clip(key)
            self.assertGreater(len(samples)/tracks.SR, 30, key)
            self.assertTrue(4 < meta['drop'] < 8, key)
            self.assertTrue(80 <= meta['bpm'] <= 160, key)
            self.assertIn(meta['title'], credits)
            self.assertIn(key, variety.MUSIC_TRACKS)

    def test_render_lands_the_drop_on_four_seconds(self):
        for key in tracks.LIBRARY:
            x = sounds.chiptune(12, 0, track=key)
            self.assertAlmostEqual(len(x)/tracks.SR, 12, delta=.01)
            self.assertLess(np.abs(x).max(), 1.0)
            before = np.sqrt((x[int(2.5*tracks.SR):int(3.8*tracks.SR)]**2).mean())
            after = np.sqrt((x[int(4.0*tracks.SR):int(6*tracks.SR)]**2).mean())
            self.assertGreater(after, .05, key)
            self.assertGreater(after, before*.8, key)

    def test_long_videos_loop_without_gaps(self):
        x = tracks.render('cc0_rush', 60)
        self.assertAlmostEqual(len(x)/tracks.SR, 60, delta=.01)
        blocks = [np.sqrt((x[i:i+tracks.SR//2]**2).mean()) for i in range(tracks.SR*5, tracks.SR*58, tracks.SR//2)]
        self.assertGreater(min(blocks), .02)


class Analysis(unittest.TestCase):
    def test_drop_and_tempo_of_a_known_song(self):
        found = tracks.analyse(synthetic_song(100, 20))
        self.assertAlmostEqual(found['drop'], 20, delta=.15)
        self.assertAlmostEqual(found['bpm'], 100, delta=1.5)

    def test_upload_registers_and_renders(self):
        key, found = tracks.register(wav_bytes(synthetic_song(120, 30)), 'prova.wav')
        self.assertTrue(key.startswith('mio:'))
        self.assertAlmostEqual(found['drop'], 30, delta=.15)
        self.assertEqual(variety.music_track({'music_track': 'mio', 'music_custom': key}), key)
        self.assertNotEqual(variety.music_track({'music_track': 'mio'}), 'mio')      # nothing uploaded: automatic
        x = tracks.render(key, 10)
        quiet = np.sqrt((x[int(3*tracks.SR):int(3.9*tracks.SR)]**2).mean())
        loud = np.sqrt((x[int(4.05*tracks.SR):int(5*tracks.SR)]**2).mean())
        self.assertGreater(loud, 2*quiet)
        key2, moved = tracks.register(wav_bytes(synthetic_song(120, 30)), 'prova.wav', drop=12.0)
        self.assertEqual((key2, moved['drop']), (key, 12.0))

    def test_bad_files_are_refused_clearly(self):
        with self.assertRaises(ValueError):
            tracks.register(b'not audio at all', 'x.mp3')


class OnTheBeat(unittest.TestCase):
    def test_scene_follows_the_real_tempo(self):
        config = dict(defaults('Matchday Screen'), music=True, music_track='cc0_rush', theme='none',
                      fx_pulse=True, camera='ritmo')
        prepared = MODULES['Matchday Screen'].scene(config, LOGO, None, None, 1)
        info = prepared[0].info
        self.assertAlmostEqual(info['beat'][0], .4, places=3)
        quarter, zero = motion.beat_of(info)
        self.assertEqual((quarter, zero), (.4, 4.0))
        self.assertEqual(motion.beat_of({}), (motion.QUARTER, 0.0))
        drop = info.get('drop_at')
        if drop:
            self.assertAlmostEqual(((drop-4.0)/1.6) % 1, 0, places=6)      # on a bar of the real track

    def test_effects_step_back_under_real_music(self):
        base = dict(defaults('Full Time'), music=True, theme='none', home_score=2, away_score=0)
        real = MODULES['Full Time'].scene(dict(base, music_track='cc0_funk'), LOGO, None, None, 1)
        synth = MODULES['Full Time'].scene(dict(base, music_track='house'), LOGO, None, None, 1)
        loud = lambda p: max(np.abs(s).max() for at, s in sounds.scene_events(p, MODULES['Full Time'].compose, until=8)[:-1])
        self.assertLess(loud(real), loud(synth))


if __name__ == '__main__':
    unittest.main()
