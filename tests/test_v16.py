"""Version 1.6: brighter presets, new worlds, standings, shared match and transitions."""
import io
import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageStat

import classifica_renderer as k
import matchday_renderer as m
from classifica_data import parse_standings, sort_rows, html_to_text, _best_table, MAX_TEAMS
from crt_presets import PRESET_IDS, PRESETS, CROPS, FORMATS, apply_preset, background
from render_utils import layout_warnings
from studio_state import (defaults, sanitize_config, apply_match, validate_library, empty_library,
                          MODULES, CRT_TEMPLATES)
from transitions import TRANSITION_IDS, transition_frame, render_sequence, preview_strip

ROOT = Path(__file__).resolve().parents[1]
LOGO = (ROOT/'assets/flamingos_logo.jpg').read_bytes()


def luminance(image):
    return ImageStat.Stat(image.convert('L')).mean[0]


class PresetTests(unittest.TestCase):
    def test_eleven_distinct_worlds(self):
        self.assertEqual(len(PRESET_IDS), 11)
        backgrounds = {}
        for preset in PRESET_IDS:
            image = background(apply_preset(defaults('Matchday Screen'), preset), 'matchday', 1)
            backgrounds[preset] = np.asarray(image.convert('RGB').resize((54, 96)), np.float32)
        # Outside the shared screen, every pair of worlds must look clearly different.
        for i, a in enumerate(PRESET_IDS):
            for b in PRESET_IDS[i+1:]:
                difference = np.abs(backgrounds[a]-backgrounds[b]).mean()
                self.assertGreater(difference, 12, (a, b))

    def test_brightness_lifts_every_preset_for_instagram(self):
        for preset in PRESET_IDS:
            with self.subTest(preset=preset):
                config = apply_preset(defaults('Matchday Screen'), preset)
                dark = dict(config, brightness=0)
                bright = dict(config, brightness=55)
                a = Image.open(io.BytesIO(m.png_bytes(dark, LOGO, None, None, 'Post 1:1', 1, 1)))
                b = Image.open(io.BytesIO(m.png_bytes(bright, LOGO, None, None, 'Post 1:1', 1, 1)))
                self.assertGreater(luminance(b), luminance(a))
                self.assertGreater(luminance(b), 55)

    def test_old_projects_get_default_brightness(self):
        old = defaults('Full Time'); old.pop('brightness')
        self.assertEqual(sanitize_config('Full Time', old)['brightness'], 55)
        self.assertEqual(sanitize_config('Full Time', dict(old, brightness=500))['brightness'], 100)


class StandingsTests(unittest.TestCase):
    TAB = ("Pos\tSquadra\tPT\tG\tV\tN\tP\tGF\tGS\tDR\n1\tREAL BOVEZZO\t21\t8\t7\t0\t1\t40\t12\t28\n"
           "2\tFLAMINGOS\t18\t8\t6\t0\t2\t33\t20\t13\n3\tATLETICO 7\t15\t8\t5\t0\t3\t25\t22\t3")

    def test_parse_tabbed_with_header_and_digit_in_name(self):
        rows = parse_standings(self.TAB)
        self.assertEqual([r['team'] for r in rows], ['REAL BOVEZZO', 'FLAMINGOS', 'ATLETICO 7'])
        self.assertEqual((rows[2]['pt'], rows[2]['g'], rows[2]['v'], rows[2]['gs']), (15, 8, 5, 22))

    def test_parse_one_cell_per_line(self):
        text = '1\nREAL BOVEZZO\n21\n8\n7\n0\n1\n40\n12\n2\nFLAMINGOS\n18\n8\n6\n0\n2\n33\n20'
        rows = parse_standings(text)
        self.assertEqual(rows[1]['team'], 'FLAMINGOS'); self.assertEqual(rows[1]['gf'], 33)

    def test_parse_plain_rows_detects_column_order_and_skips_form(self):
        text = ("1° Real Bovezzo 8 7 0 1 40 12 21 V V P V V\n2° Flamingos 8 6 0 2 33 20 18 V P V V P\n"
                "3° Atletico 8 5 0 3 25 22 15 P V V P V")
        rows = parse_standings(text)
        self.assertEqual((rows[0]['pt'], rows[0]['g'], rows[0]['v']), (21, 8, 7))

    def test_parse_html_table(self):
        page = ('<table><tr><th>#</th><th>Squadra</th><th>Pt</th><th>G</th><th>V</th><th>N</th><th>P</th>'
                '<th>Gf</th><th>Gs</th></tr><tr><td>1</td><td><a>Real</a></td><td>21</td><td>8</td><td>7</td>'
                '<td>0</td><td>1</td><td>40</td><td>12</td></tr><tr><td>2</td><td>Flamingos</td><td>18</td>'
                '<td>8</td><td>6</td><td>0</td><td>2</td><td>33</td><td>20</td></tr></table>')
        rows = _best_table(page)
        self.assertEqual(rows[1]['team'], 'FLAMINGOS'); self.assertEqual(rows[1]['pt'], 18)

    def test_bad_text_raises(self):
        for text in ('', 'ciao a tutti', 'SQUADRA PT\nFLAMINGOS'):
            with self.assertRaises(ValueError):
                parse_standings(text)

    def test_sort_by_points_then_difference(self):
        rows = sort_rows([dict(pos=1, team='A', pt=10, g=5, v=3, n=1, p=1, gf=8, gs=8),
                          dict(pos=2, team='B', pt=10, g=5, v=3, n=1, p=1, gf=9, gs=4)])
        self.assertEqual([r['team'] for r in rows], ['B', 'A']); self.assertEqual(rows[0]['pos'], 1)

    def test_every_preset_and_size_fits_the_post(self):
        for preset in PRESET_IDS:
            for count, detail in ((2, 'Completa'), (8, 'Compatta'), (MAX_TEAMS, 'Completa')):
                with self.subTest(preset=preset, count=count):
                    config = apply_preset(defaults('Classifica'), preset, True)
                    config.update(team_count=count, table_detail=detail)
                    for i in range(count):
                        config['standings'][i].update(team=config['standings'][i]['team'] or f'SQUADRA {i}')
                    scene = k.scene(config, LOGO, render_scale=1)
                    self.assertFalse(layout_warnings(scene, CROPS['Post 4:5']))
                    self.assertEqual(k.compose(scene, animated=False).size, (540, 960))

    def test_our_team_is_highlighted(self):
        config = defaults('Classifica')
        a = np.asarray(k.table_image(config))
        config['our_team'] = 'NESSUNO'
        b = np.asarray(k.table_image(config))
        self.assertGreater(np.abs(a.astype(int)-b.astype(int)).sum(), 10000)

    def test_png_and_project_roundtrip(self):
        for fmt, size in zip(FORMATS, ((1080, 1080), (1080, 1350), (1080, 1920))):
            data = k.png_bytes(defaults('Classifica'), LOGO, format=fmt)
            self.assertEqual(Image.open(io.BytesIO(data)).size, size)
        config = defaults('Classifica'); config['standings'][0]['pt'] = 5000
        clean = sanitize_config('Classifica', config)
        self.assertEqual(clean['standings'][0]['pt'], 999)
        self.assertEqual(len(clean['standings']), MAX_TEAMS)
        raw = dict(empty_library(), projects={'x': {'name': 'Girone', 'template': 'Classifica', 'config': config}})
        library, messages = validate_library(raw)
        self.assertFalse(messages); self.assertIn('x', library['projects'])


class SharedMatchTests(unittest.TestCase):
    MATCH = dict(our_name='FLAMINGOS', opponent='REAL BOVEZZO', our_side='Ospiti', date='25/10/2026',
                 kickoff='21:00', meeting_time='20:15', venue='CAMPO X', round=9, opponent_logo_id='none')

    def test_away_match_swaps_sides_everywhere(self):
        md = apply_match('Matchday Screen', defaults('Matchday Screen'), self.MATCH)
        self.assertEqual((md['home_name'], md['away_name'], md['home_logo_id']), ('REAL BOVEZZO', 'FLAMINGOS', 'none'))
        ft = apply_match('Full Time', defaults('Full Time'), self.MATCH)
        self.assertEqual(ft['our_side'], 'Ospiti')
        cv = apply_match('Convocati', defaults('Convocati'), self.MATCH)
        self.assertEqual((cv['opponent'], cv['meeting_time'], cv['venue']), ('REAL BOVEZZO', '20:15', 'CAMPO X'))
        self.assertEqual(apply_match('Classifica', defaults('Classifica'), self.MATCH)['round_label'], 'GIORNATA 9')

    def test_layout_and_colours_survive(self):
        config = defaults('Convocati'); config['positions']['title'] = [100, 400]; config['pink'] = '#123456'
        out = apply_match('Convocati', config, self.MATCH)
        self.assertEqual(out['positions']['title'], [100, 400]); self.assertEqual(out['pink'], '#123456')

    def test_round_rotation_follows_the_match(self):
        config = dict(defaults('Matchday Screen'), rotation_mode='Per giornata')
        out = apply_match('Matchday Screen', config, self.MATCH)
        self.assertEqual(out['preset_id'], PRESET_IDS[8 % len(PRESET_IDS)])

    def test_home_placeholder_logo_renders(self):
        md = apply_match('Matchday Screen', defaults('Matchday Screen'), self.MATCH)
        scene = m.scene(md, None, LOGO, None, 1)
        self.assertEqual(m.compose(scene, animated=False).size, (540, 960))


class TransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Image.new('RGB', (108, 192), (240, 40, 120))
        cls.b = Image.new('RGB', (108, 192), (30, 200, 240))

    def test_endpoints_and_sizes(self):
        for kind in TRANSITION_IDS:
            with self.subTest(kind=kind):
                first = transition_frame(kind, self.a, self.b, 0)
                last = transition_frame(kind, self.a, self.b, 1)
                self.assertEqual(first.size, self.a.size)
                self.assertLess(np.abs(np.asarray(last, int)-np.asarray(self.b, int)).mean(), 8)
                if kind != 'channel':  # channel 0 is already the first frame of noise-in
                    self.assertLess(np.abs(np.asarray(first, int)-np.asarray(self.a, int)).mean(), 8)

    def test_middle_frames_change_the_picture(self):
        for kind in TRANSITION_IDS:
            with self.subTest(kind=kind):
                middle = transition_frame(kind, self.a, self.b, .5)
                self.assertFalse(np.array_equal(np.asarray(middle), np.asarray(self.a)))

    def test_storyboard(self):
        sheet = preview_strip(self.a, self.b, 'glitch', 5, 50)
        self.assertEqual(sheet.size, (5*50+16, round(192*50/108)))

    def test_sequence_video_length_and_size(self):
        scenes = []
        for template in ('Matchday Screen', 'Convocati', 'Classifica'):
            module = MODULES[template]
            scenes.append((module.scene(defaults(template), LOGO, None, None, 1), module.compose))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'seq.mp4'
            render_sequence(scenes, ['channel', 'poweroff'], path, 12, 2.0, 1.0, 'Post 4:5', 1)
            reader = imageio.get_reader(path)
            frames = sum(1 for _ in reader)
            self.assertEqual(frames, 12*2*3+12*2)
            self.assertEqual(reader.get_meta_data()['size'], (540, 676))


if __name__ == '__main__':
    unittest.main()
