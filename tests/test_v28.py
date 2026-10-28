"""2.8: the girone crests built into the app, matched to the opponent automatically."""
import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import crests
from renderer import clean_logo
from studio_state import MODULES, apply_match, defaults, empty_library, sanitize_match


class Matching(unittest.TestCase):
    def test_names_as_written_anywhere(self):
        cases = {'UNITED FLERO': 'united_flero', 'United Flero': 'united_flero', 'ASD SPORTING LENO': 'sporting_leno',
                 'G.S.O. PONCARALE': 'gso_poncarale', 'FC MUSTANGS': 'fc_mustangs', 'A.S. ARDENS 2002': 'as_ardens',
                 'ORATORIO CASTELMELLA CALCIO': 'castel_mella', 'Castel Mella': 'castel_mella', 'LIONS 25': 'lions_25',
                 'LIONS25': 'lions_25', 'GALBA F.C.': 'galba_fc', 'CASTE UNITED': 'caste_united', 'UMC': 'umc',
                 'ASD PIRATI C.C.S.': 'pirati', 'GSO VEROLANUOVA': 'gso_verolan'}
        for name, slug in cases.items():
            self.assertEqual(crests.match(name), slug, name)

    def test_unknown_or_too_short(self):
        for name in ('REAL BOVEZZO', 'AVVERSARI', 'FLAMINGOS', '', 'FC', 'UNITED'):
            self.assertIsNone(crests.match(name), name)


class Assets(unittest.TestCase):
    def test_every_team_has_a_clean_transparent_crest(self):
        assets = crests.builtin_assets()
        self.assertEqual(len(assets), len(crests.TEAMS))
        for id_, asset in assets.items():
            with self.subTest(id_):
                self.assertTrue(id_.startswith('stemma:'))
                im = Image.open(io.BytesIO(asset['bytes'])).convert('RGBA')
                self.assertGreaterEqual(max(im.size), 480)
                alpha = np.asarray(im.getchannel('A'))
                corners = [alpha[0, 0], alpha[0, -1], alpha[-1, 0], alpha[-1, -1]]
                self.assertTrue(sum(c < 20 for c in corners) >= 2, 'background not removed')
                self.assertGreater((alpha > 200).mean(), .35)
                self.assertGreater(clean_logo(asset['bytes'], 100, True, 1).width, 50)

    def test_register_adds_builtins_without_touching_archive_logos(self):
        library = empty_library()
        library['assets']['logo:mine'] = {'kind': 'logo', 'name': 'Mio', 'bytes': b'x'}
        crests.register(library)
        self.assertIn('logo:mine', library['assets'])
        self.assertTrue(all(a.get('builtin') for k, a in library['assets'].items() if k.startswith('stemma:')))


class AutoOpponent(unittest.TestCase):
    def test_sets_and_updates_only_our_own_choices(self):
        m = crests.auto_opponent_logo(dict(sanitize_match({}), opponent='UNITED FLERO'))
        self.assertEqual(m['opponent_logo_id'], 'stemma:united_flero')
        m = crests.auto_opponent_logo(dict(m, opponent='LIONS 25'))
        self.assertEqual(m['opponent_logo_id'], 'stemma:lions_25')
        m = crests.auto_opponent_logo(dict(m, opponent='REAL BOVEZZO'))
        self.assertEqual(m['opponent_logo_id'], 'none')
        own = crests.auto_opponent_logo(dict(sanitize_match({}), opponent='UMC', opponent_logo_id='logo:abc'))
        self.assertEqual(own['opponent_logo_id'], 'logo:abc')    # a logo the user picked stays

    def test_matchday_away_uses_the_crest(self):
        match = crests.auto_opponent_logo(dict(sanitize_match({}), opponent='UNITED FLERO', our_side='Ospiti'))
        config = apply_match('Matchday Screen', defaults('Matchday Screen'), match)
        self.assertEqual(config['home_logo_id'], 'stemma:united_flero')
        crest = crests.builtin_assets()['stemma:united_flero']['bytes']
        logo = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
        module = MODULES['Matchday Screen']
        with_crest = np.asarray(module.compose(module.scene(dict(config, theme='none'), crest, logo, None, 1), 999, False), np.int16)
        without = np.asarray(module.compose(module.scene(dict(config, theme='none'), None, logo, None, 1), 999, False), np.int16)
        self.assertGreater(np.abs(with_crest-without).mean(), 1)


if __name__ == '__main__':
    unittest.main()
