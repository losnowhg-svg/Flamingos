"""3.12: risultati della giornata, from the CSI matches to a PNG, a video and a sequence screen."""
import datetime as dt
import io
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import card_video
import figurine_scenes as fsc
import figurine_style as fs
import results_round as rr
import transitions as tr
from studio_state import defaults

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
MATCHES = [dict(home='GALBA F.C.', away='FLAMINGOS', date='2026-10-24', time='20:45', score=[2, 4], venue='', round=5),
           dict(home='REAL BRESCIA', away='ATLETICO OSPITALETTO', date='2026-10-25', time='21:00', score=(1, 1), venue='',
                round=5),
           dict(home='SPORTING ROVATO', away='CHIARI UNITED', date='2026-10-26', time='20:30', score=None, venue='', round=5),
           dict(home='FLAMINGOS', away='REAL BRESCIA', date='2026-10-31', time='20:45', score=None, venue='', round=6)]


class Data(unittest.TestCase):
    def test_rounds_and_default(self):
        groups = rr.rounds(MATCHES)
        self.assertEqual([g['label'] for g in groups], ['GIORNATA 5', 'GIORNATA 6'])
        self.assertEqual([g['played'] for g in groups], [2, 0])
        self.assertEqual(rr.default_round(groups), 0)      # the last round with a result, not the next one
        self.assertIsInstance(groups[0]['first'], dt.date)

    def test_weeks_when_the_round_is_missing(self):
        loose = [dict(m, round=None) for m in MATCHES]
        labels = [g['label'] for g in rr.rounds(loose)]
        self.assertTrue(labels and all(label.startswith('SETTIMANA DEL') for label in labels))

    def test_rows(self):
        rows = rr.rows_for(rr.rounds(MATCHES)[0])
        ours = [r for r in rows if r['ours']]
        self.assertEqual(len(ours), 1)
        self.assertEqual(ours[0]['score'], [2, 4])
        unplayed = next(r for r in rows if r['score'] is None)
        self.assertTrue(unplayed['when'].endswith('20:30'))


class Render(unittest.TestCase):
    def setUp(self):
        self.rows = rr.rows_for(rr.rounds(MATCHES)[0])

    def test_png_sizes(self):
        for fmt, size in (('Story 9:16', (1080, 1920)), ('Post 4:5', (1080, 1350)), ('Post 1:1', (1080, 1080))):
            img = Image.open(io.BytesIO(rr.png_bytes(self.rows, LOGO, fmt, 2, subtitle='GIORNATA 5')))
            self.assertEqual(img.size, size, fmt)

    def test_our_row_is_pink(self):
        show = rr.RoundShow(self.rows, logo=LOGO, scale=1, still=True)
        frame = np.asarray(show.still_frame(), np.int16)
        pink = (frame[..., 0] > 200) & (frame[..., 2] > 110) & (frame[..., 1] < 120)
        self.assertGreater(pink.sum(), 300)

    def test_our_match_lands_on_the_drop(self):
        show = rr.RoundShow(self.rows, logo=LOGO, scale=1)
        before = np.asarray(show.frame(card_video.DROP-.2), np.int16)
        after = np.asarray(show.frame(card_video.DROP+.4), np.int16)
        self.assertGreater(np.abs(after-before).mean(), 3)
        self.assertTrue(all(0 <= at < show.length for at, _ in show.events()))

    def test_style_changes_the_background(self):
        night = np.asarray(rr.RoundShow(self.rows, logo=LOGO, scale=1, still=True).still_frame(), np.int16)
        style = fs.build(fs.key_for('poster', defaults('Classifica')), 'Story 9:16', 540)
        light = np.asarray(rr.RoundShow(self.rows, logo=LOGO, scale=1, still=True, style=style).still_frame(), np.int16)
        self.assertGreater(np.abs(night-light)[:120].mean(), 20)

    def test_preset_rows_follow_the_preset(self):
        style = fs.build(fs.key_for('gameboy', defaults('Classifica')), 'Story 9:16', 540)
        self.assertEqual(style['font'], 'CRT Scoreboard')
        show = rr.RoundShow(self.rows, logo=LOGO, scale=1, still=True, style=style)
        self.assertEqual(show.font, 'CRT Scoreboard')
        self.assertEqual(show.panel, tuple(style['panel']))
        mine = show.panels[next(i for i, r in enumerate(self.rows) if r['ours'])]
        pixels = np.asarray(mine)
        inside = pixels[pixels[..., 3] > 240][:, :3]
        typical = np.median(inside, axis=0)
        self.assertLess(np.abs(typical-np.array(style['palette'][0])).max(), 40)   # our row: filled with the accent
        self.assertIsNone(rr.RoundShow(self.rows, logo=LOGO, scale=1, still=True).font)       # synthwave: Inter

    def test_video(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'r.mp4'
            rr.render_video(self.rows, LOGO, path, 8, 'Post 1:1', .5, 'cc0_ritmo', True)
            self.assertGreater(path.stat().st_size, 20_000)


class Sequence(unittest.TestCase):
    def test_scene_and_transition(self):
        self.assertIn('Risultati', fsc.EXTRA)
        self.assertEqual(tr.special_for('Full Time', 'Risultati'), 'righe')
        payload = fsc.payloads({'csi_matches': MATCHES}, [], [], [], dict(team='FLAMINGOS'))['Risultati']
        self.assertEqual(payload['subtitle'], 'GIORNATA 5 · CSI BRESCIA')
        self.assertIsNone(fsc.payloads({}, [], [], [], {})['Risultati'])
        prepared, compose = fsc.scene('Risultati', payload, LOGO, 1, None)
        prepared[0].info.update(format='Post 4:5', hold=4.0, seq_start=5.0, seq_beat=60/90)
        self.assertEqual(compose(prepared, 2.0).size, (540, 960))
        self.assertTrue(0 < card_video.DROP-fsc.offset(prepared[0].info) < 4.0)


if __name__ == '__main__':
    unittest.main()
