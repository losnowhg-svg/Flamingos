"""3.16: the department slides inside the Video con transizioni."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import reparti_renderer as rr
import transitions as tr
from crt_presets import output_image
from studio_state import defaults
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def convocati(names):
    config = defaults('Convocati')
    people = [p for p in OFFICIAL_SQUAD if p['name'] in names]
    for i, person in enumerate(people):
        config['roster'][i] = dict(number=person.get('number', i+1), name=person['name'], role=person.get('role', 'C'),
                                   captain=False)
    config['roster_count'] = len(people)
    return config


class Reparti(unittest.TestCase):
    def test_one_scene_per_department(self):
        config = convocati({'BRAMBO', 'GIANLU', 'COCCO', 'BOBBI', 'TEU'})
        scenes = rr.sequence_scenes(config, OFFICIAL_SQUAD, LOGO, None, 1)
        groups = [g for g, _ in rr.slides(config, OFFICIAL_SQUAD)]
        self.assertEqual(len(scenes), len(groups))
        self.assertEqual(groups[:4], ['P', 'D', 'C', 'A'])
        prepared, compose = scenes[0]
        self.assertEqual(output_image(compose(prepared, 999, False), 'Post 4:5', 1).size, (540, 675))
        self.assertEqual(rr.sequence_scenes(defaults('Convocati'), [], LOGO, None, 1), [])   # nobody chosen yet

    def test_expand_puts_the_departments_in_line(self):
        groups = [['matchday'], ['portieri', 'difensori', 'attaccanti'], ['fulltime']]
        scenes, steps = tr.expand(groups, ['spogliatoio', 'cronometro'])
        self.assertEqual(scenes, ['matchday', 'portieri', 'difensori', 'attaccanti', 'fulltime'])
        self.assertEqual(len(steps), len(scenes)-1)
        self.assertEqual((steps[0], steps[-1]), ('spogliatoio', 'cronometro'))
        self.assertEqual(len(set(steps[1:3])), 2)                       # inside: two different transitions
        self.assertEqual(tr.expand([['a'], ['b']], ['wipe']), (['a', 'b'], ['wipe']))

    def test_themed_way_in(self):
        self.assertEqual(tr.special_for('Convocati', 'Reparti'), 'spogliatoio')
        self.assertEqual(tr.special_for('Matchday Screen', 'Reparti'), 'spogliatoio')
        self.assertEqual(tr.special_for('Reparti', 'Full Time'), 'cronometro')
        self.assertEqual(tr.special_for('Reparti', 'Figurina MVP'), 'strappo')

    def test_never_the_same_themed_transition_twice_in_a_row(self):
        self.assertEqual(tr.themed(['Matchday Screen', 'Convocati', 'Reparti']), ['spogliatoio', 'righe'])
        self.assertEqual(tr.themed(['Full Time', 'Classifica', 'Calendario']), ['righe', 'calendario'])
        for chain in (['Classifica', 'Risultati', 'Classifica'], ['Pagelle', 'Pagelle', 'Pagelle']):
            steps = tr.themed(chain)
            self.assertTrue(all(a != b for a, b in zip(steps, steps[1:])), steps)
            self.assertTrue(all(step in tr.TRANSITIONS for step in steps))

    def test_render_a_sequence_with_the_departments(self):
        config = convocati({'BRAMBO', 'GIANLU', 'TEU'})
        import convocati_renderer as c
        groups = [[(c.scene(config, LOGO, None, None, 1), c.compose)], rr.sequence_scenes(config, OFFICIAL_SQUAD, LOGO, None, 1)]
        scenes, steps = tr.expand(groups, ['spogliatoio'])
        self.assertEqual(len(scenes), 1+len(rr.slides(config, OFFICIAL_SQUAD)))      # portieri, difensori, attaccanti, staff
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'s.mp4'
            tr.render_sequence(scenes, steps, path, 8, 1.0, .4, 'Post 1:1', 1, sound=True)
            self.assertGreater(path.stat().st_size, 20_000)


if __name__ == '__main__':
    unittest.main()
