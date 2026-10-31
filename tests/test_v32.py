"""3.2: Instagram safe zone, animations on the music, 60 fps."""
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
import motion
import safezone
from crt_presets import apply_preset
from studio_state import MODULES, defaults, sanitize_config

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
TEMPLATES = ('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario')


def scene(template, **extra):
    config = dict(apply_preset(defaults(template), 'crt'), theme='none', **extra)
    return MODULES[template].scene(config, LOGO, None, None, 1), config


class SafeZone(unittest.TestCase):
    def test_the_default_layouts_are_already_safe(self):
        for template in TEMPLATES:
            prepared, _ = scene(template)
            self.assertEqual(safezone.covered(prepared, 'Story 9:16'), [], template)

    def test_a_dragged_element_is_flagged_and_brought_back(self):
        prepared, config = scene('Matchday Screen')
        config['positions']['title'] = [270, 80]
        config['positions']['venue'] = [500, 900]
        moved, _ = scene('Matchday Screen', positions=config['positions'])
        self.assertEqual(set(safezone.covered(moved, 'Story 9:16')), {'Titolo', 'Campo'})
        self.assertEqual(safezone.covered(moved, 'Post 1:1'), [])      # only Reels and Stories
        fixed = safezone.fit(moved, config['positions'])
        again, _ = scene('Matchday Screen', positions=fixed)
        self.assertEqual(safezone.covered(again, 'Story 9:16'), [])
        self.assertEqual(fixed['home_logo'], config['positions']['home_logo'])   # the rest stays

    def test_editor_zones_and_mock(self):
        self.assertEqual(len(safezone.editor_zones('Story 9:16')), 4)
        self.assertIsNone(safezone.editor_zones('Post 4:5'))
        image = Image.new('RGB', (1080, 1920), (40, 40, 60))
        mocked = np.asarray(safezone.mock(image), np.int16)
        self.assertEqual(mocked.shape, (1920, 1080, 3))
        self.assertEqual(np.abs(mocked[700:1200, 200:800]-40).max() <= 20, True)    # the middle stays free
        self.assertGreater(np.abs(mocked[1600:1900]-np.asarray(image, np.int16)[1600:1900]).mean(), 5)


class OnTheMusic(unittest.TestCase):
    def moment(self, prepared):
        layer, extra = animations._anchor(prepared)
        return animations._offset(prepared)+layer.start+extra

    def test_the_big_moment_lands_on_the_drop_or_a_downbeat(self):
        for template in TEMPLATES:
            for extra in ({}, {'intro': True}, {'intro': True, 'intro_style': 'logo'}):
                with self.subTest(template=template, **extra):
                    config_extra = dict(extra, music=True)
                    if template == 'Full Time':
                        config_extra.update(home_score=2, away_score=1)
                    prepared, _ = scene(template, **config_extra)
                    at = self.moment(prepared)
                    self.assertAlmostEqual(at/2, round(at/2), places=2)      # on a bar line (every 2 s)
                    self.assertEqual(prepared[0].info['drop_at'], round(at, 2))

    def test_matchday_crests_crash_on_the_drop(self):
        prepared, _ = scene('Matchday Screen', music=True)
        self.assertAlmostEqual(self.moment(prepared), 4.0, places=2)
        by_id = {l.id: l for l in prepared[1]}
        self.assertEqual(by_id['home_logo'].start, by_id['away_logo'].start)
        order = [l.id for l in sorted(prepared[1], key=lambda l: l.start)]
        self.assertLess(order.index('title'), order.index('home_logo'))

    def test_without_music_nothing_moves(self):
        a, _ = scene('Full Time')
        self.assertNotIn('drop_at', a[0].info)
        b, _ = scene('Full Time')
        self.assertEqual([l.start for l in a[1]], [l.start for l in b[1]])

    def test_the_drop_is_felt_on_screen(self):
        prepared, _ = scene('Convocati', music=True, camera='ritmo')
        drop = prepared[0].info['drop_at']
        prepared[0].info['duration'] = 8
        on = np.asarray(animations.compose(prepared, drop+.03, True), np.int16)
        plain, _ = scene('Convocati', music=True)
        plain[0].info['duration'] = 8
        off = np.asarray(animations.compose(plain, drop+.03, True), np.int16)
        self.assertGreater(np.abs(on-off).mean(), 2)


class Fps(unittest.TestCase):
    def test_60_fps_is_accepted_and_renders(self):
        config = sanitize_config('Classifica', dict(defaults('Classifica'), fps=60))
        self.assertEqual(config['fps'], 60)
        self.assertEqual(motion.REEL['fps'], 30)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'v.mp4'
            MODULES['Classifica'].render_video(dict(config, theme='none'), LOGO, None, path, None, 60, 1, 'Post 1:1', 1)
            import imageio.v2 as iio
            reader = iio.get_reader(str(path))
            self.assertEqual(round(reader.get_meta_data()['fps']), 60)


if __name__ == '__main__':
    unittest.main()


class ClassificaFocus(unittest.TestCase):
    """3.3: zoom on our row, the climb past the others, the badge on the right."""

    def prepared(self, prev, **extra):
        prepared, _ = scene('Classifica', prev_pos=prev, power_on=False, **extra)
        climb = next(m for m in animations.moments(prepared) if m[1] == 'climb')
        return prepared, climb[0], climb[2]

    def test_modes_and_last_week_order(self):
        import classifica_renderer as cr
        for prev, mode in ((5, 'up'), (2, 'same'), (1, 'down')):
            prepared, at, data = self.prepared(prev)
            self.assertEqual(data['mode'], mode)
            table = next(l for l in prepared[1] if l.id == 'table')
            self.assertEqual(hasattr(table, 'before'), mode != 'same')
        config = dict(defaults('Classifica'), prev_pos=5)
        old, mapping = cr.last_week(config)
        rows = cr.active_rows(old)
        self.assertTrue(cr.is_ours(rows[4]['team'], 'FLAMINGOS'))
        self.assertEqual(sorted(mapping), list(range(len(rows))))

    def test_the_row_climbs_and_the_badge_stays(self):
        prepared, at, data = self.prepared(5)
        start = at-data['lead']
        frames = {t: np.asarray(animations.compose(prepared, t, True), np.int16) for t in (start-.2, start+1.2, at+.6, at+3)}
        self.assertGreater(np.abs(frames[start+1.2]-frames[start-.2]).mean(), 3)      # zoomed in and moving
        green = np.array((91, 230, 164))
        late = frames[at+3]
        right = late[380:680, 450:500].reshape(-1, 3)
        self.assertGreater((np.abs(right-green).sum(axis=1) < 60).sum(), 20)          # the badge, after zoom-out
        same, at2, data2 = self.prepared(2)
        yellow = np.array((255, 201, 99))
        right = np.asarray(animations.compose(same, at2+3, True), np.int16)[380:680, 450:500].reshape(-1, 3)
        self.assertGreater((np.abs(right-yellow).sum(axis=1) < 60).sum(), 20)

    def test_landing_on_the_drop_with_music(self):
        prepared, at, data = self.prepared(5, music=True)
        self.assertAlmostEqual(at/2, round(at/2), places=2)
        self.assertEqual(prepared[0].info['drop_at'], round(at, 2))

    def test_still_image_keeps_the_small_arrow(self):
        import classifica_renderer as cr
        same = np.asarray(cr.table_image(dict(defaults('Classifica'), prev_pos=2)).convert('RGB'), np.int16)
        plain = np.asarray(cr.table_image(dict(defaults('Classifica'), prev_pos=0)).convert('RGB'), np.int16)
        changed = np.abs(same-plain).sum(axis=2) > 30
        ys, xs = np.nonzero(changed)
        self.assertGreater(len(xs), 20)                       # the small = next to our name
        self.assertLess(xs.max(), 364-150)                    # inside the row, before the numbers


class DetailsEverywhere(unittest.TestCase):
    """3.4: score close-up and points chip, calendar stamp and glide to NEXT, captain armband."""

    def moments(self, template, **extra):
        prepared, _ = scene(template, power_on=False, **extra)
        return prepared, animations.moments(prepared)

    def test_full_time_points_chip_by_result(self):
        for home, away, side, colour in ((3, 1, 'Casa', (91, 230, 164)), (1, 1, 'Casa', (255, 201, 99)),
                                         (3, 1, 'Ospiti', (255, 107, 120))):
            prepared, moments = self.moments('Full Time', home_score=home, away_score=away, our_side=side)
            at = next(m[0] for m in moments if m[1] == 'points')
            self.assertTrue(any(m[1] == 'focus_score' for m in moments))
            frame = np.asarray(animations.compose(prepared, at+2, True), np.int16)
            area = frame[530:590, 300:460].reshape(-1, 3)
            self.assertGreater((np.abs(area-np.array(colour)).sum(axis=1) < 50).sum(), 30, (home, away, side))

    def test_score_close_up_zooms_and_comes_back(self):
        prepared, moments = self.moments('Full Time', home_score=2, away_score=0)
        at = next(m[0] for m in moments if m[1] == 'focus_score')
        import focus
        self.assertGreater(focus.camera_at(prepared, moments, at+.4)[0], 1.1)
        self.assertEqual(focus.camera_at(prepared, moments, at+2.5)[0], 1.0)

    def test_calendar_stamp_then_next(self):
        prepared, moments = self.moments('Calendario')
        stamp = next(m for m in moments if m[1] == 'stamp')
        nxt = next(m for m in moments if m[1] == 'next')
        meta = next(l for l in prepared[1] if l.id == 'table').image.info
        self.assertEqual(stamp[2]['row'], max(i for i, r in enumerate(meta['row_results']) if r and i < meta['next_row']))
        self.assertGreater(nxt[0], stamp[0])
        import focus
        z1, _, y1 = focus.camera_at(prepared, moments, stamp[0]+.5)
        z2, _, y2 = focus.camera_at(prepared, moments, stamp[0]+1.7)
        self.assertGreater(z1, 1.1)
        self.assertGreater(y2, y1)                    # the camera glides down to the next match

    def test_captain_armband(self):
        roster = defaults('Convocati')['roster']
        roster[2]['captain'] = True
        prepared, moments = self.moments('Convocati', roster=roster)
        captain = next(m for m in moments if m[1] == 'captain')
        self.assertEqual(captain[2]['layer'], 'player_2')
        before = np.asarray(animations.compose(prepared, captain[0]-.05, True), np.int16)
        after = np.asarray(animations.compose(prepared, captain[0]+2.5, True), np.int16)
        yellow = np.array((255, 201, 99))
        count = lambda f: (np.abs(f.reshape(-1, 3)-yellow).sum(axis=1) < 40).sum()
        self.assertGreater(count(after), count(before)+10)
