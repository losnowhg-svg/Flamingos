"""3.10: figurine screens on the studio presets, in the video sequence, with collection transitions."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import album
import card_video
import figurine_scenes as fsc
import figurine_style as fs
import transitions as tr
from crt_presets import output_image
from studio_state import defaults
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
SQUAD = {p['name']: p for p in OFFICIAL_SQUAD}
TEU = dict(SQUAD['TEU'], edition='mvp', vote=8.5, stats=[('GOL', '2'), ('RISULTATO', '3-1'), ('GIORNATA', '7')])
FT = dict(defaults('Full Time'), preset_id='gameboy', theme='none')


class Style(unittest.TestCase):
    def test_keys_and_backgrounds(self):
        self.assertIsNone(fs.build(fs.key_for(fs.SYNTHWAVE, FT)))
        follow = fs.build(fs.key_for(fs.FOLLOW, FT), 'Post 4:5', 540)
        self.assertEqual(follow['preset'], 'gameboy')
        self.assertAlmostEqual(follow['image'].width/follow['image'].height, 540/675, places=2)
        self.assertEqual(fs.build(fs.key_for('stadium', FT), 'Story 9:16', 540)['preset'], 'stadium')
        self.assertIn('Come il Full Time', fs.label(fs.FOLLOW, FT))

    def test_card_on_a_preset_looks_different_and_keeps_the_card(self):
        night = np.asarray(card_video.poster(TEU, LOGO, 'Story 9:16', .5), np.int16)
        styled = np.asarray(card_video.poster(TEU, LOGO, 'Story 9:16', .5,
                                              style=fs.build(fs.key_for('poster', FT), 'Story 9:16', 270)), np.int16)
        self.assertGreater(np.abs(night-styled)[:60].mean(), 20)          # the background changed (light poster)
        self.assertLess(np.abs(night-styled)[200:300, 100:170].mean(), 40)  # the card in the middle did not


class Transitions(unittest.TestCase):
    def test_collection_transitions_start_on_a_and_end_on_b(self):
        a = Image.new('RGB', (108, 192), (20, 40, 160))
        b = Image.new('RGB', (108, 192), (200, 30, 90))
        for kind in tr.SPECIAL:
            self.assertIn(kind, tr.TRANSITIONS)
            import sounds
            self.assertGreater(len(sounds.TRANSITION_SOUNDS[kind](.8)), 1000)
            start = np.asarray(tr.transition_frame(kind, a, b, .02), np.int16)
            end = np.asarray(tr.transition_frame(kind, a, b, .99), np.int16)
            self.assertLess(np.abs(start-np.asarray(a, np.int16)).mean(), np.abs(start-np.asarray(b, np.int16)).mean(), kind)
            self.assertLess(np.abs(end-np.asarray(b, np.int16)).mean(), np.abs(end-np.asarray(a, np.int16)).mean(), kind)

    def test_special_for(self):
        self.assertEqual(tr.special_for('Full Time', 'Figurina MVP'), 'carta')
        self.assertEqual(tr.special_for('Matchday Screen', 'Figurina MVP'), 'strappo')
        self.assertEqual(tr.special_for('Figurina MVP', 'Pagelle'), 'olografica')
        self.assertEqual(tr.special_for('Pagelle', 'Album'), 'pagina')
        self.assertEqual(tr.special_for('Figurina MVP', 'Classifica'), 'pioggia')
        self.assertEqual(tr.special_for('Matchday Screen', 'Convocati'), 'spogliatoio')
        self.assertEqual(tr.special_for('Convocati', 'Matchday Screen'), 'spogliatoio')
        self.assertEqual(tr.special_for('Convocati', 'Full Time'), 'cronometro')
        self.assertEqual(tr.special_for('Full Time', 'Classifica'), 'righe')
        self.assertEqual(tr.special_for('Classifica', 'Calendario'), 'calendario')
        self.assertEqual(tr.special_for('Calendario', 'Matchday Screen'), 'countdown')


class Sequence(unittest.TestCase):
    def scene(self, kind, payload, fmt='Story 9:16'):
        prepared, compose = fsc.scene(kind, payload, LOGO, 1, fs.key_for(fs.FOLLOW, FT))
        prepared[0].info.update(format=fmt, hold=4.0, seq_start=5.0, seq_beat=60/90)
        return prepared, compose

    def test_frames_fit_the_sequence_crop(self):
        prepared, compose = self.scene('Figurina MVP', {'spec': TEU, 'caption': 'prova'}, 'Post 4:5')
        frame = compose(prepared, 1.0)
        self.assertEqual(frame.size, (540, 960))
        self.assertEqual(output_image(frame, 'Post 4:5', 1).size, (540, 675))
        still = compose(prepared, animated=False)
        self.assertEqual(still.size, (540, 960))

    def test_reveal_on_a_beat_of_the_sequence_music(self):
        prepared, _ = self.scene('Figurina MVP', {'spec': TEU})
        info = prepared[0].info
        reveal = info['seq_start']+card_video.DROP-fsc.offset(info)
        steps = (reveal-4.0)/(60/90)
        self.assertAlmostEqual(steps, round(steps), places=6)
        self.assertTrue(0 < card_video.DROP-fsc.offset(info) < 4.0)
        events = info['sequence_events'](4.0)
        self.assertTrue(events and all(0 <= at < 4.0 for at, _ in events))

    def test_payload_defaults(self):
        ctx = dict(fulltime=FT, round=3, scorers=[], games=[], mvps=[], season='2026/27', team='FLAMINGOS')
        out = fsc.payloads({}, OFFICIAL_SQUAD, [], [], ctx)
        self.assertEqual(out['Figurina MVP']['spec']['edition'], 'mvp')
        self.assertIsNone(out['Pagelle'])
        self.assertEqual(len(out['Album']['members']), len(album.members_for(OFFICIAL_SQUAD)))

    def test_render_sequence_with_figurine_screens(self):
        rows = [dict(SQUAD['TEU'], vote=8.5, goals=2), dict(SQUAD['CAVA'], vote=7)]
        scenes = [fsc.scene('Pagelle', {'rows': rows, 'info': {'line': 'A 1-0 B'}}, LOGO, 1, None),
                  fsc.scene('Figurina MVP', {'spec': TEU, 'caption': 'prova'}, LOGO, 1, fs.key_for('vhs', FT))]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'s.mp4'
            tr.render_sequence(scenes, ['strappo'], path, 8, 2.0, .5, 'Post 1:1', 1, sound=True)
            self.assertGreater(path.stat().st_size, 20_000)


if __name__ == '__main__':
    unittest.main()
