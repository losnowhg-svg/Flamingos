"""1.9: TV mockup, Retro entrance animations, event and seasonal themes."""
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

import animations
import mockup
import sounds
import themes
from crt_presets import output_image
from studio_state import (CRT_TEMPLATES, MODULES, apply_match, defaults, sanitize_config, sanitize_match)
from transitions import render_sequence

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def scene(template, **changes):
    config = defaults(template)
    config.update(theme='none')
    config.update(changes)
    return MODULES[template].scene(config, LOGO, None, None, 1)


class ThemeTests(unittest.TestCase):
    def test_seasons(self):
        self.assertEqual(themes.seasonal(dt.date(2026, 10, 31)), 'halloween')
        self.assertEqual(themes.seasonal(dt.date(2026, 12, 20)), 'natale')
        self.assertEqual(themes.seasonal(dt.date(2027, 1, 3)), 'capodanno')
        self.assertIsNone(themes.seasonal(dt.date(2026, 3, 10)))

    def test_resolve_order(self):
        base = dict(theme='auto', event_theme='', date='20/12/2026')
        self.assertEqual(themes.resolve(base), 'natale')
        self.assertEqual(themes.resolve(dict(base, event_theme='derby')), 'derby')
        self.assertEqual(themes.resolve(dict(base, theme='none')), None)
        self.assertEqual(themes.resolve(dict(base, theme='bigmatch')), 'bigmatch')
        self.assertIsNone(themes.resolve(dict(theme='auto', date='GG/MM/AAAA'), dt.date(2026, 4, 1)))

    def test_effective_keeps_pink_and_white(self):
        config = defaults('Matchday Screen')
        config['theme'] = 'halloween'
        out = themes.effective(config)
        self.assertEqual(out['pink'], config['pink'])
        self.assertEqual(out['white'], config['white'])
        self.assertNotEqual(out['yellow'], config['yellow'])
        self.assertEqual(defaults('Matchday Screen')['yellow'], config['yellow'])  # input untouched

    def test_auto_event(self):
        rows = [dict(pos=i+1, team=t) for i, t in enumerate(['LIONS', 'FLAMINGOS', 'TIGERS', 'A', 'B', 'C', 'D', 'E'])]
        match = dict(event='auto', our_name='FLAMINGOS', opponent='LIONS', date='30/10/2026')
        self.assertEqual(themes.auto_event(match, rows), 'bigmatch')
        self.assertEqual(themes.auto_event(dict(match, opponent='E'), rows), '')
        self.assertEqual(themes.auto_event(dict(match, event='derby'), rows), 'derby')
        self.assertEqual(themes.auto_event(dict(match, event='normale'), rows), '')
        games = [dict(home='FLAMINGOS', away='A', date=dt.date(2026, 10, 2)),
                 dict(home='E', away='FLAMINGOS', date=dt.date(2026, 10, 30))]
        self.assertEqual(themes.auto_event(dict(match, opponent='E'), rows, games), 'ultima')

    def test_state_and_match(self):
        config = sanitize_config('Full Time', dict(defaults('Full Time'), theme='nope', animation='x', event_theme='bad', mockup='yes'))
        self.assertEqual((config['theme'], config['animation'], config['event_theme'], config['mockup']), ('auto', 'Retro', '', False))
        match = sanitize_match(dict(event='derby', opponent='LIONS'))
        self.assertEqual(match['event'], 'derby')
        self.assertEqual(sanitize_match(dict(event='zzz'))['event'], 'auto')
        out = apply_match('Matchday Screen', defaults('Matchday Screen'), match)
        self.assertEqual(out['event_theme'], 'derby')
        self.assertEqual(apply_match('Classifica', defaults('Classifica'), match, 'bigmatch')['event_theme'], 'bigmatch')

    def test_every_theme_on_every_editor(self):
        for theme in themes.THEME_IDS:
            for template in CRT_TEMPLATES:
                prepared = scene(template, theme=theme)
                self.assertEqual(prepared[0].info['theme'], theme)
                still = MODULES[template].compose(prepared, 999, False)
                plain = MODULES[template].compose(scene(template), 999, False)
                self.assertGreater(np.abs(np.asarray(still, int)-np.asarray(plain, int)).mean(), .5)

    def test_particles_move(self):
        prepared = scene('Matchday Screen', theme='natale', animation='Classica')
        a = MODULES['Matchday Screen'].compose(prepared, 5.0, True)
        b = MODULES['Matchday Screen'].compose(prepared, 5.5, True)
        self.assertGreater(np.abs(np.asarray(a, int)-np.asarray(b, int)).sum(), 0)


class AnimationTests(unittest.TestCase):
    def test_kinds(self):
        prepared = scene('Matchday Screen')
        kinds = {l.id: l.anim for l in prepared[1]}
        self.assertEqual(kinds['title'], 'type')
        self.assertEqual(kinds['home_logo'], 'slide_left')
        self.assertEqual(kinds['away_logo'], 'slide_right')
        self.assertEqual(kinds['vs'], 'pop')
        self.assertTrue(animations.rich(prepared))
        self.assertFalse(animations.rich(scene('Matchday Screen', animation='Classica')))

    def test_score_counts_up(self):
        prepared = scene('Full Time', home_score=5, away_score=1)
        score = next(l for l in prepared[1] if l.id == 'score')
        self.assertEqual(score.anim, 'count')
        self.assertEqual(len(score.variants), 6)

    def test_tables_fill_by_rows(self):
        for template in ('Classifica', 'Calendario'):
            table = next(l for l in scene(template)[1] if l.id == 'table')
            self.assertEqual(table.anim, 'rows')
            edges = table.image.info['row_edges']
            self.assertTrue(all(a < b for a, b in edges))

    def test_power_on_starts_black(self):
        prepared = scene('Convocati')
        compose = MODULES['Convocati'].compose
        self.assertLess(np.asarray(compose(prepared, 0.0, True)).mean(), 5)
        self.assertGreater(np.asarray(compose(prepared, 3.0, True)).mean(), 20)
        off = scene('Convocati', power_on=False)
        self.assertGreater(np.asarray(compose(off, 0.0, True)).mean(), 20)

    def test_everything_visible_at_the_end(self):
        for template in CRT_TEMPLATES:
            prepared = scene(template)
            compose = MODULES[template].compose
            end = animations.intro_length(prepared)+.3
            moving = np.asarray(compose(prepared, end, True), int)
            still = np.asarray(compose(prepared, 999, False), int)
            self.assertLess(np.abs(moving-still).mean(), 3, template)

    def test_sound_events(self):
        events = animations.events(scene('Full Time', home_score=3, away_score=0))
        kinds = [k for _, k, _ in events]
        self.assertEqual(kinds[0], 'power')
        self.assertIn('tick', kinds)
        self.assertIn('glitch', kinds)
        sound_events = sounds.scene_events(scene('Classifica'), MODULES['Classifica'].compose)
        self.assertGreater(len(sound_events), 8)


class MockupTests(unittest.TestCase):
    def test_sizes(self):
        frame = MODULES['Matchday Screen'].compose(scene('Matchday Screen'), 999, False)
        for format, height in (('Story 9:16', 960), ('Post 4:5', 675), ('Post 1:1', 540)):
            self.assertEqual(mockup.frame(frame, format, 1).size, (540, height))

    def test_knob_turns_and_light_follows_picture(self):
        frame = MODULES['Matchday Screen'].compose(scene('Matchday Screen'), 999, False)
        a = np.asarray(mockup.frame(frame, 'Story 9:16', 1, 0), int)
        b = np.asarray(mockup.frame(frame, 'Story 9:16', 1, 90), int)
        self.assertGreater(np.abs(a-b).sum(), 0)
        dark = np.asarray(mockup.frame(Image.new('RGB', frame.size), 'Story 9:16', 1, 0), int)
        self.assertGreater(a[880:].mean(), dark[880:].mean())  # screen light on the floor

    def test_png_export(self):
        config = dict(defaults('Classifica'), mockup=True, theme='none')
        data = MODULES['Classifica'].png_bytes(config, LOGO, None, None, 'Post 4:5', 1, 1)
        self.assertEqual(Image.open(io.BytesIO(data)).size, (540, 675))

    def test_sequence_on_tv(self):
        scenes = [(scene(t), MODULES[t].compose) for t in ('Matchday Screen', 'Convocati')]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'tv.mp4'
            render_sequence(scenes, ['channel'], path, fps=12, hold=2, transition_seconds=.5,
                            format='Post 1:1', scale=1, mockup=True)
            self.assertGreater(path.stat().st_size, 10_000)
        self.assertFalse(scenes[1][0][0].info['power_on'])


if __name__ == '__main__':
    unittest.main()
