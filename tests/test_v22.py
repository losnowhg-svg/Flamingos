"""2.2: faster exports and editor, quick preview, smarter file names, countdown."""
import base64
import datetime as dt
import io
import sys
import time
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import renderer as r
import ui_utils
from studio_state import MODULES, defaults

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


class SpeedTests(unittest.TestCase):
    def test_editor_payload_is_light(self):
        prepared = MODULES['Matchday Screen'].scene(dict(defaults('Matchday Screen'), theme='none'), LOGO, None, None, 2)
        data = r.editor_data(prepared)
        self.assertEqual(data['background_type'], 'image/jpeg')
        self.assertLess(len(data['background']), 450_000)
        self.assertEqual(Image.open(io.BytesIO(base64.b64decode(data['background']))).size, (1080, 1920))
        layer = Image.open(io.BytesIO(base64.b64decode(data['layers'][0]['image'])))
        self.assertEqual(layer.mode, 'RGBA')

    def test_png_is_fast_and_valid(self):
        config = dict(defaults('Convocati'), theme='none')
        module = MODULES['Convocati']
        module.png_bytes(config, LOGO, None, None, 'Post 4:5', 2, 2)  # warm caches
        start = time.time()
        data = module.png_bytes(config, LOGO, None, None, 'Post 4:5', 2, 2)
        self.assertLess(time.time()-start, 1.5)
        image = Image.open(io.BytesIO(data))
        self.assertEqual((image.format, image.size), ('PNG', (1080, 1350)))

    def test_rgb_pipeline_matches_still(self):
        import numpy as np
        prepared = MODULES['Classifica'].scene(dict(defaults('Classifica'), theme='natale'), LOGO, None, None, 1)
        compose = MODULES['Classifica'].compose
        moving = np.asarray(compose(prepared, 30.0, True), int)
        still = np.asarray(compose(prepared, 999, False), int)
        self.assertEqual(compose(prepared, 30.0, True).mode, 'RGB')
        self.assertLess(np.abs(moving-still).mean(), 6)


class HelperTests(unittest.TestCase):
    def test_file_stem(self):
        stem = ui_utils.file_stem('Matchday Screen', dict(our_side='Ospiti', home_name='UNITED FLERO', date='29/10/2026'))
        self.assertEqual(stem, 'flamingos_matchday_vs-united-flero_29-10')
        self.assertEqual(ui_utils.file_stem('Full Time', dict(our_side='Casa', away_name='AVVERSARI', date='GG/MM/AAAA')),
                         'flamingos_fulltime')
        self.assertEqual(ui_utils.file_stem('Calendario', dict(month_label='OTTOBRE 2026')), 'flamingos_calendario_ottobre-2026')

    def test_countdown(self):
        match = dict(date='29/10/2026', opponent='UNITED FLERO', kickoff='21:15')
        today = dt.date(2026, 10, 25)
        self.assertIn('Mancano 4 giorni', ui_utils.countdown(match, today))
        self.assertIn('Domani', ui_utils.countdown(match, dt.date(2026, 10, 28)))
        self.assertIn('Oggi', ui_utils.countdown(match, dt.date(2026, 10, 29)))
        self.assertIn('Full Time', ui_utils.countdown(match, dt.date(2026, 10, 30)))
        self.assertIsNone(ui_utils.countdown(match, dt.date(2026, 11, 20)))
        self.assertIsNone(ui_utils.countdown(dict(date='GG/MM/AAAA'), today))

    def test_progress_eta(self):
        calls = []

        class Bar:
            def progress(self, value, text=''):
                calls.append(text)
        update = ui_utils.progress_with_eta(Bar())
        time.sleep(.05)
        update(.5)
        update(1.0)
        self.assertIn('circa', calls[0])
        self.assertNotIn('circa', calls[1])


if __name__ == '__main__':
    unittest.main()
