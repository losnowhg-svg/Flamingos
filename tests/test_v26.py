"""2.6 Varietà: layouts, rotating titles, intros, chiptune tracks, transitions, sprite poses and scenes."""
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animations
import intros
import layouts
import pixel_character as pc
import reparti_renderer as rr
import sounds
import team_photo as tp
import transitions
import variety
from studio_state import MODULES, apply_match, defaults, sanitize_config
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def still(template, config):
    module = MODULES[template]
    return module.compose(module.scene(config, LOGO, None, None, 1), 999, False).convert('RGB')


class Layouts(unittest.TestCase):
    def test_every_layout_renders_and_differs(self):
        for template in layouts.LAYOUTS:
            images = []
            for layout_id in layouts.options(template):
                config = layouts.apply(template, dict(defaults(template), theme='none'), layout_id)
                images.append(np.asarray(still(template, config), np.int16))
            self.assertGreaterEqual(len(images), 2, template)
            for other in images[1:]:
                self.assertGreater(np.abs(images[0]-other).mean(), 1.0, template)

    def test_apply_resets_positions_and_sizes(self):
        config = defaults('Matchday Screen')
        duel = layouts.apply('Matchday Screen', config, 'duello')
        self.assertEqual(duel['positions']['vs'], list(layouts.LAYOUTS['Matchday Screen']['duello']['positions']['vs']))
        self.assertEqual(duel['home_logo_size'], 76)
        back = layouts.apply('Matchday Screen', duel, 'classica')
        self.assertEqual(back['home_logo_size'], config['home_logo_size'])
        self.assertEqual(back['positions'], config['positions'])

    def test_layout_survives_sanitize_and_bad_values_fall_back(self):
        config = layouts.apply('Full Time', defaults('Full Time'), 'tabellone')
        self.assertEqual(sanitize_config('Full Time', config)['layout'], 'tabellone')
        self.assertEqual(sanitize_config('Full Time', dict(config, layout='boh'))['layout'], 'classica')
        self.assertEqual(sanitize_config('Calendario', dict(defaults('Calendario'), layout='duello'))['layout'], 'classica')

    def test_panels_are_registered(self):
        from crt_presets import PANEL_LAYOUTS
        self.assertIn('matchday@duello', PANEL_LAYOUTS)
        self.assertIn('fulltime_clean@tabellone', PANEL_LAYOUTS)
        clean = PANEL_LAYOUTS['fulltime_clean@tabellone']
        self.assertFalse(any('scorers' in p[4] for p in clean))

    def test_rotation_by_round(self):
        config = dict(defaults('Matchday Screen'), layout_rotation=True)
        seen = {apply_match('Matchday Screen', config, {'round': r})['layout'] for r in (1, 2, 3)}
        self.assertEqual(seen, set(layouts.options('Matchday Screen')))

    def test_shared_classifica_background_stays_classic(self):
        # Wrapped and the sponsor slide use the Classifica editor's config: never its layout panels.
        from crt_presets import background
        config = dict(layouts.apply('Classifica', defaults('Classifica'), 'piede'), theme='none')
        plain = np.asarray(background(dict(defaults('Classifica'), theme='none'), 'classifica', 1).convert('RGB'), np.int16)
        self.assertEqual(np.abs(np.asarray(background(config, 'classifica', 1).convert('RGB'), np.int16)-plain).max(), 0)


class Titles(unittest.TestCase):
    def test_rotation_fills_the_round(self):
        self.assertEqual(variety.title_for_round('Matchday Screen', 1), 'MATCHDAY SCREEN')
        titles = {variety.title_for_round('Matchday Screen', r) for r in range(1, 11)}
        self.assertEqual(len(titles), 10)
        self.assertIn('LEVEL 8', titles)

    def test_random_title_changes(self):
        for seed in range(5):
            self.assertNotEqual(variety.random_title('Convocati', 'CONVOCATI', 3, seed), 'CONVOCATI')

    def test_apply_match_rotates_titles(self):
        config = dict(defaults('Classifica'), title_rotation=True)
        self.assertEqual(apply_match('Classifica', config, {'round': 2})['title'], 'HIGH SCORES')
        self.assertEqual(apply_match('Classifica', defaults('Classifica'), {'round': 2})['title'], 'CLASSIFICA')

    def test_titles_fit(self):
        for pool in variety.TITLES.values():
            for title in pool:
                self.assertLessEqual(len(variety.fill(title, 80)), 36)


class Intros(unittest.TestCase):
    def test_every_intro_draws_something_and_differs(self):
        base = Image.new('RGBA', (540, 960))
        frames = {}
        for style in intros.DRAW:
            info = dict(intro_style=style, level=5, intro_names=('FLAMINGOS', 'REAL BOVEZZO'))
            frame = np.asarray(intros.frame(base, .9, info), np.int16)
            self.assertGreater(frame.std(), 5, style)
            frames[style] = frame
        styles = list(frames)
        for a in styles:
            for b in styles:
                if a < b:
                    self.assertGreater(np.abs(frames[a]-frames[b]).mean(), 1, (a, b))

    def test_versus_only_with_two_teams(self):
        self.assertEqual(variety.intro_style({'intro_style': 'versus'}, 'classifica'), 'press_start')
        self.assertEqual(variety.intro_style({'intro_style': 'versus'}, 'matchday'), 'versus')
        rotation = {variety.intro_style({'intro_style': 'rotazione', 'season_round': r}, 'matchday') for r in range(1, 6)}
        self.assertEqual(len(rotation), 5)

    def test_intro_in_a_scene_and_its_sounds(self):
        config = dict(defaults('Matchday Screen'), intro=True, intro_style='cartuccia', theme='none')
        prepared = MODULES['Matchday Screen'].scene(config, LOGO, None, None, 1)
        self.assertEqual(prepared[0].info['intro_style'], 'cartuccia')
        kinds = [k for t, k, _ in animations.events(prepared) if t < animations.INTRO]
        self.assertIn('impact', kinds)
        frame = animations.compose(prepared, .5)
        self.assertEqual(frame.size, (540, 960))


class Music(unittest.TestCase):
    def test_tracks_are_different_and_quiet(self):
        clips = {name: sounds.chiptune(4, track=name) for name in ('arcade', 'epica', 'tensione', 'festa')}
        for name, clip in clips.items():
            self.assertLess(np.abs(clip).max(), 1.0, name)
            self.assertGreater(np.sqrt((clip**2).mean()), .03, name)
        self.assertGreater(np.abs(clips['epica']-clips['festa']).mean(), .01)

    def test_automatic_choice(self):
        self.assertEqual(variety.music_track({}, 'fulltime', 'win'), 'cc0_funk')
        self.assertEqual(variety.music_track({}, 'fulltime', 'loss'), 'cc0_city')
        self.assertEqual(variety.music_track({}, 'matchday', theme='derby'), 'cc0_battle')
        self.assertEqual(variety.music_track({'music_track': 'epica'}, 'fulltime', 'win'), 'epica')

    def test_scene_carries_the_track(self):
        config = dict(defaults('Full Time'), home_score=3, away_score=0, music=True, theme='none')
        prepared = MODULES['Full Time'].scene(config, LOGO, None, None, 1)
        self.assertEqual(prepared[0].info['music_track'], 'cc0_funk')


class Transitions(unittest.TestCase):
    def test_new_transitions(self):
        a = Image.new('RGB', (270, 480), (255, 0, 0))
        b = Image.new('RGB', (270, 480), (0, 0, 255))
        for kind in ('pixel', 'iris', 'blocks', 'wipe'):
            start = np.asarray(transitions.transition_frame(kind, a, b, 0.0))
            end = np.asarray(transitions.transition_frame(kind, a, b, 1.0))
            self.assertGreater(start[..., 0].mean(), 200, kind)
            self.assertGreater(end[..., 2].mean(), 200, kind)
            self.assertIn(kind, sounds.TRANSITION_SOUNDS)
            self.assertGreater(len(sounds.TRANSITION_SOUNDS[kind](.8)), 0)

    def test_varied_never_repeats_in_a_row(self):
        chain = transitions.varied(9)
        self.assertTrue(all(x != y for x, y in zip(chain, chain[1:])))


class PosesAndScenes(unittest.TestCase):
    def test_every_pose_and_beat(self):
        look = OFFICIAL_SQUAD[0]['look']
        rest = pc.image(look).tobytes()
        for pose in pc.POSES[1:]:
            first = pc.image(look, pose=pose)
            self.assertNotEqual(first.tobytes(), rest, pose)
            if pose in pc.MOVING_POSES:
                self.assertNotEqual(pc.image(look, pose=pose, beat=1).tobytes(), first.tobytes(), pose)
            self.assertEqual(pc.image(look, 'gameboy', pose=pose).size, (32, 32))

    def test_scenes(self):
        for name in pc.SCENES:
            for style in ('arcade', 'gameboy'):
                self.assertEqual(pc.scene(name, style).size, (32, 32))
        gb = np.asarray(pc.scene('stadio', 'gameboy')).reshape(-1, 3)
        self.assertLessEqual(len({tuple(c) for c in gb}), 4)

    def test_variate_by_role(self):
        self.assertEqual(variety.pose_for({'role': 'P'}, 0), 'guanti')
        self.assertEqual(variety.pose_for({'role': 'A'}, 0), 'esultanza')
        self.assertEqual(variety.pose_for({'role': 'C'}, 5, 'pollice'), 'pollice')
        self.assertEqual(variety.scene_for('C', 'variate'), 'notte')

    def test_department_cards_get_pose_frames(self):
        members = [dict(p, captain=False) for p in OFFICIAL_SQUAD if p['role'] == 'A']
        config = dict(members=members, group='A', slide_title='ATTACCANTI', sprite_pose='variate', sprite_scene='stadio')
        layers = rr.get_layers(config, LOGO, None, None, 1)
        card = next(l for l in layers if l.id == 'card_0')
        self.assertIn('pose', card.alive)
        seen = {id(animations._idle_card(card, i/24, 0)) for i in range(48)}
        self.assertIn(id(card.alive['pose']), seen)

    def test_team_photo_with_poses_and_scenes(self):
        img = tp.team_photo(OFFICIAL_SQUAD, 'crt', LOGO, pose_mode='variate', scene_mode='variate')
        plain = tp.team_photo(OFFICIAL_SQUAD, 'crt', LOGO)
        self.assertGreater(np.abs(np.asarray(img, np.int16)-np.asarray(plain, np.int16)).mean(), 1)

    def test_config_fields(self):
        config = sanitize_config('Convocati', dict(defaults('Convocati'), sprite_pose='esultanza', sprite_scene='neve'))
        self.assertEqual((config['sprite_pose'], config['sprite_scene']), ('esultanza', 'neve'))
        config = sanitize_config('Convocati', dict(defaults('Convocati'), sprite_pose='x', sprite_scene=3))
        self.assertEqual((config['sprite_pose'], config['sprite_scene']), ('variate', 'sfumato'))


if __name__ == '__main__':
    unittest.main()
