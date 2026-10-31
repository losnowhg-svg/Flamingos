"""2.1: strong moments, living avatars, intro / ending, VHS details, chiptune."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animations
import pixel_character as pc
import sounds
from classifica_data import with_rows
from crt_common import video_length
from studio_state import MODULES, defaults, sanitize_config

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def scene(template, **changes):
    config = defaults(template)
    config.update(theme='none')
    config.update(changes)
    return MODULES[template].scene(config, LOGO, LOGO, None, 1)


def kinds(prepared):
    return [k for _, k, _ in animations.moments(prepared)]


class MomentTests(unittest.TestCase):
    def test_matchday_crash(self):
        prepared = scene('Matchday Screen')
        self.assertIn('impact', kinds(prepared))
        compose = MODULES['Matchday Screen'].compose
        t = next(at for at, k, _ in animations.moments(prepared) if k == 'impact')
        before = np.asarray(compose(prepared, t-.01, True), float).mean()
        flash = np.asarray(compose(prepared, t+.03, True), float).mean()
        self.assertGreater(flash, before+10)

    def test_fulltime_outcomes(self):
        win = scene('Full Time', home_score=3, away_score=1, show_scorers=False)   # the counter: no scorers
        self.assertEqual(win[0].info['outcome'], 'win')
        self.assertIn('goal', kinds(win))
        banner = [d for _, k, d in animations.moments(win) if k == 'banner'][0]
        self.assertEqual(banner['outcome'], 'win')
        loss = scene('Full Time', home_score=0, away_score=2)
        self.assertEqual(loss[0].info['outcome'], 'loss')
        self.assertNotIn('goal', kinds(loss))
        away_win = scene('Full Time', home_score=1, away_score=2, our_side='Ospiti')
        self.assertEqual(away_win[0].info['outcome'], 'win')
        pens = scene('Full Time', home_score=1, away_score=1, show_penalties=True, home_penalties=5, away_penalties=4)
        self.assertEqual(pens[0].info['outcome'], 'win')
        sounds_ = [k for _, k, _ in animations.events(win)]
        self.assertIn('win', sounds_)
        self.assertIn('goal', sounds_)

    def test_classifica_climb_and_crown(self):
        rows = [dict(r) for r in defaults('Classifica')['standings']]
        rows[0], rows[1] = dict(rows[1], pos=1), dict(rows[0], pos=2)
        prepared = scene('Classifica', standings=rows, prev_pos=3)
        table = [l for l in prepared[1] if l.id == 'table'][0]
        self.assertEqual(table.image.info['ours'], 1)
        self.assertEqual(table.image.info['prev'], 3)
        self.assertTrue(table.image.info['first'])
        self.assertEqual(kinds(prepared).count('climb'), 1)
        self.assertEqual(kinds(prepared).count('crown'), 1)
        compose = MODULES['Classifica'].compose
        for t in (3.2, 3.6, 4.4):
            compose(prepared, t, True)

    def test_previous_position_from_import(self):
        config = defaults('Classifica')
        real = [dict(r, team=r['team'].replace('SQUADRA', 'TEAM')) for r in config['standings'][:8]]
        config = sanitize_config('Classifica', with_rows(config, real))   # FLAMINGOS 2nd
        moved = [dict(real[1], pos=1), dict(real[0], pos=2)]+real[2:]
        moved[0]['pt'] += 3
        updated = with_rows(config, moved)
        self.assertEqual(updated['prev_pos'], 2)
        again = with_rows(sanitize_config('Classifica', updated), moved)  # same table: keep it
        self.assertEqual(again['prev_pos'], 2)

    def test_calendar_next_and_dings(self):
        prepared = scene('Calendario')
        self.assertIn('next', kinds(prepared))
        self.assertIn('ding', [k for _, k, _ in animations.events(prepared)])

    def test_captain_shine(self):
        config = defaults('Convocati')
        config['roster'][2]['captain'] = True
        prepared = MODULES['Convocati'].scene(dict(config, theme='none'), LOGO, None, None, 1)
        self.assertIn('shine', kinds(prepared))


class LifeTests(unittest.TestCase):
    def test_blink(self):
        look = dict(hair='ciuffo')
        a = np.asarray(pc.image(look), int)
        b = np.asarray(pc.image(look, blink=True), int)
        self.assertGreater(np.abs(a-b).sum(), 0)
        sun = dict(look, glasses='sole')
        self.assertEqual(np.abs(np.asarray(pc.image(sun), int)-np.asarray(pc.image(sun, blink=True), int)).sum(), 0)


class FramingTests(unittest.TestCase):
    def test_intro_and_power(self):
        prepared = scene('Matchday Screen', intro=True)
        compose = MODULES['Matchday Screen'].compose
        intro = np.asarray(compose(prepared, .2, True), float)
        self.assertLess(intro.mean(), 20)
        self.assertGreater(intro.max(), 150)                 # PRESS START text
        self.assertLess(np.asarray(compose(prepared, animations.INTRO+.05, True), float).mean(), 15)
        self.assertEqual([k for _, k, _ in animations.events(prepared)][:4], ['start', 'start', 'start', 'ready'])

    def test_endings(self):
        prepared = scene('Convocati', ending='spegnimento')
        prepared[0].info['duration'] = 8
        compose = MODULES['Convocati'].compose
        self.assertLess(np.asarray(compose(prepared, 7.99, True), float).mean(), 3)
        loop = scene('Convocati', ending='loop')
        loop[0].info['duration'] = 8
        self.assertLess(np.asarray(compose(loop, 7.99, True), float).mean(), 3)

    def test_video_length_grows_when_needed(self):
        prepared = scene('Full Time', intro=True, ending='spegnimento', home_score=2)
        self.assertGreater(video_length(prepared, 5), 5)
        self.assertEqual(video_length(prepared, 1), 1)
        classic = scene('Full Time', animation='Classica')
        self.assertEqual(video_length(classic, 5), 5)

    def test_music_snaps_and_plays(self):
        prepared = scene('Classifica', music=True)
        anchor = animations._anchor(prepared)[0]   # 3.2: the strongest moment is placed exactly on the drop instead
        self.assertTrue(all(abs(l.start/animations.BEAT-round(l.start/animations.BEAT)) < 1e-9
                            for l in prepared[1] if l is not anchor))
        track = sounds.chiptune(4.0)
        self.assertEqual(len(track), int(4*sounds.SR)+1)
        self.assertGreater(np.abs(track).max(), .05)
        evs = sounds.scene_events(prepared, MODULES['Classifica'].compose, until=6)
        self.assertTrue(any(len(s) > sounds.SR*5 for _, s in evs))

    def test_state_keys(self):
        config = sanitize_config('Matchday Screen', dict(defaults('Matchday Screen'), ending='boh', intro='x'))
        self.assertEqual((config['ending'], config['intro'], config['details'], config['music']), ('nessuno', False, True, False))


if __name__ == '__main__':
    unittest.main()
