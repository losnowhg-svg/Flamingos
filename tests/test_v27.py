"""2.7: twelve new presets (12-23) and readable text on light screens."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import convocati_renderer as cv
import preset_worlds as pw
from crt_presets import BUILDERS, PRESETS, PRESET_IDS, STYLE, apply_preset, background
from render_utils import contrast_ink
from studio_state import MODULES, defaults

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
NEW = tuple(pw.PRESETS)


class NewPresets(unittest.TestCase):
    def test_registered_in_order_after_the_originals(self):
        self.assertEqual(len(NEW), 12)
        self.assertEqual(PRESET_IDS[11:], NEW)
        names = [PRESETS[p]['name'] for p in PRESET_IDS]
        self.assertEqual(len(names), len(set(names)))
        for i, preset in enumerate(PRESET_IDS):
            self.assertTrue(PRESETS[preset]['name'].startswith(f'{i+1:02d} /'), preset)

    def test_every_new_preset_is_complete(self):
        for preset in NEW:
            self.assertIn(preset, BUILDERS)
            self.assertIn(preset, STYLE)
            for key in ('pink', 'cyan', 'yellow', 'white'):
                self.assertRegex(PRESETS[preset][key], r'^#[0-9A-F]{6}$')

    def test_every_template_renders_on_every_new_preset(self):
        for preset in NEW:
            for template in ('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario'):
                with self.subTest(preset=preset, template=template):
                    module = MODULES[template]
                    config = dict(apply_preset(defaults(template), preset, typography=True), theme='none')
                    image = module.compose(module.scene(config, LOGO, None, None, 1), 999, False)
                    self.assertEqual(image.size, (540, 960))

    def test_text_panels_keep_the_panel_colour(self):
        # The text panels keep the preset's panel colour, whatever world is drawn around them.
        for preset in NEW:
            image = np.asarray(background(dict(apply_preset(defaults('Convocati'), preset), theme='none'),
                                          'convocati', 1).convert('RGB'), np.int16)
            panel = np.array(STYLE[preset]['panel'])
            inside = image[330:380, 100:440].reshape(-1, 3)
            close = (np.abs(inside-panel).sum(axis=1) < 60).mean()
            self.assertGreater(close, .8, preset)


class LightScreen(unittest.TestCase):
    def test_contrast_ink(self):
        self.assertEqual(contrast_ink((242, 104, 168)), (9, 11, 22))
        self.assertEqual(contrast_ink((140, 31, 69)), (246, 244, 236))

    def test_lcd_player_rows_are_light_with_dark_names(self):
        config = apply_preset(defaults('Convocati'), 'lcd')
        row = np.asarray(cv.make_player({'number': 7, 'name': 'TEU', 'role': 'A'}, 0, config, None, 1).image)
        background_pixel = row[2, 100, :3]
        self.assertGreater(background_pixel.mean(), 140)
        dark = cv.make_player({'number': 7, 'name': 'TEU', 'role': 'A'}, 0, apply_preset(defaults('Convocati'), 'crt'), None, 1)
        self.assertLess(np.asarray(dark.image)[2, 100, :3].mean(), 40)


if __name__ == '__main__':
    unittest.main()
