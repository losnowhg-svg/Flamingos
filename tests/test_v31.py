"""3.1: six new full-sounding music tracks, automatic rotation, listening preview."""
import io
import sys
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import music
import sounds
import variety
from studio_state import defaults, sanitize_config

SR = music.SR


def rms(x):
    return float(np.sqrt((x**2).mean()))


class Tracks(unittest.TestCase):
    def test_every_track_is_clean_and_as_loud_as_the_others(self):
        reference = rms(sounds.chiptune(12, 0, track='arcade'))
        for track in music.TRACKS:
            with self.subTest(track):
                x = sounds.chiptune(12, 0, track=track)
                self.assertEqual(len(x), int(12*SR)+1)
                self.assertTrue(np.isfinite(x).all())
                self.assertLess(np.abs(x).max(), .95)
                self.assertLess(abs(x.mean()), .01)
                self.assertGreater(rms(x), reference*.9)
                self.assertLess(rms(x), reference*2)

    def test_intro_then_the_drop(self):
        for track in music.TRACKS:
            with self.subTest(track):
                x = music.render(track, 12)
                intro, drop = x[int(.3*SR):int(3.5*SR)], x[int(4*SR):int(8*SR)]
                self.assertLess(rms(intro), rms(drop))

    def test_on_the_120_bpm_grid(self):
        # The kick of the four-on-the-floor tracks lands on every beat (every 0.5 s).
        for track in ('house', 'disco'):
            low = music.lp(music.render(track, 10), 120, 4)
            energy = np.abs(low)
            for beat in range(8, 18):
                at = int(beat*.5*SR)
                self.assertGreater(energy[at:at+int(.06*SR)].max(), energy[at-int(.2*SR):at-int(.12*SR)].max())

    def test_tracks_sound_different(self):
        renders = {t: music.render(t, 10) for t in music.TRACKS}
        spectra = {t: np.abs(np.fft.rfft(x))[:SR*4] for t, x in renders.items()}
        for a in music.TRACKS:
            for b in music.TRACKS:
                if a < b:
                    sa, sb = spectra[a], spectra[b]
                    similarity = float(sa @ sb/np.linalg.norm(sa)/np.linalg.norm(sb))
                    self.assertLess(similarity, .9, (a, b))

    def test_deterministic_and_any_length(self):
        self.assertTrue(np.array_equal(music.render('trap', 7.3), music.render('trap', 7.3)))
        self.assertEqual(len(music.render('lofi', 25)), int(25*SR)+1)
        self.assertEqual(len(music.render('carica', 2)), int(2*SR)+1)


class CloudDependencies(unittest.TestCase):
    def test_music_and_videos_work_without_scipy(self):
        # Streamlit Cloud installs only requirements.txt: no SciPy there.
        import subprocess
        code = ("import sys; sys.modules['scipy'] = None; sys.path.insert(0, %r)\n"
                "import music, sounds\n"
                "for t in music.TRACKS: assert len(sounds.chiptune(3, 0, track=t)) > 0\n"
                "assert len(music.preview_wav('house')) > 1000\n") % str(ROOT)
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr[-800:])

    def test_requirements_cover_the_imports(self):
        requirements = (ROOT/'requirements.txt').read_text().lower()
        self.assertNotIn('scipy', (ROOT/'music.py').read_text().split('\n\n', 1)[1].split('def ')[0])
        for module in ('numpy', 'pillow', 'imageio'):
            self.assertIn(module, requirements)


class Choice(unittest.TestCase):
    def test_every_track_can_be_chosen_and_saved(self):
        for track in variety.MUSIC_TRACKS:
            config = sanitize_config('Convocati', dict(defaults('Convocati'), music_track=track))
            self.assertEqual(config['music_track'], track)
            if track != 'auto':
                self.assertEqual(variety.music_track(config, 'convocati'), track)

    def test_automatic_rotates_by_round_and_starts_as_before(self):
        self.assertEqual(variety.music_track({'season_round': 1}, 'fulltime', 'win'), 'festa')
        self.assertEqual(variety.music_track({'season_round': 1}, 'matchday'), 'epica')
        picked = {variety.music_track({'season_round': n}, 'matchday') for n in range(1, 11)}
        self.assertGreaterEqual(len(picked), 4)
        self.assertTrue(picked & set(music.TRACKS))
        for pool in variety.AUTO_TRACKS.values():
            for track in pool:
                self.assertIn(track, variety.MUSIC_TRACKS)

    def test_listening_preview_is_a_light_wav(self):
        data = music.preview_wav('disco')
        with wave.open(io.BytesIO(data)) as w:
            self.assertEqual((w.getnchannels(), w.getframerate()), (1, SR//2))
            self.assertAlmostEqual(w.getnframes()/w.getframerate(), 14, delta=.1)
        self.assertLess(len(data), 700_000)

    def test_the_soundtrack_of_a_video_uses_the_track(self):
        mixed = sounds.mix([(0.0, sounds.chiptune(6, 0, track='synthwave')*.9)], 6, .8, ambient=False)
        self.assertGreater(rms(mixed), .05)
        self.assertLess(np.abs(mixed).max(), .81)


if __name__ == '__main__':
    unittest.main()
