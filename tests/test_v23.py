"""2.3: the caption studio."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import caption_studio as cs
from studio_state import defaults, sanitize_squad

SQUAD = [dict(name='TEU', number=9, role='A', ig='teu.9'), dict(name='NICK', role='ALL'), dict(name='CAVA', number=10, role='C')]


def fulltime(**changes):
    config = defaults('Full Time')
    config.update(theme='none', our_side='Ospiti', home_name='UNITED FLERO', away_name='FLAMINGOS', home_score=1,
                  away_score=4, away_scorers="TEU 12', 38'\nCAVA 30'", date='29/10/2026')
    config.update(changes)
    return config


def convocati():
    config = defaults('Convocati')
    config.update(theme='none', opponent='UNITED FLERO', date='29/10/2026', meeting_time='20:15', kickoff='21:15')
    for i, n in enumerate(['BRAMBO', 'TEU', 'CAVA', 'OLI', 'DEMA', 'LUCA', 'TABE']):
        config['roster'][i] = dict(number=i+1, name=n, role='P' if n in ('BRAMBO', 'OLI') else 'C', captain=n == 'CAVA')
    config['roster_count'] = 7
    return config


class FactTests(unittest.TestCase):
    def test_fulltime_facts(self):
        f = cs.build_facts('Full Time', fulltime(), {'round': 7}, SQUAD)
        self.assertEqual((f['score'], f['outcome'], f['opp'], f['where']), ('4-1', 'win', 'United Flero', 'in trasferta'))
        self.assertEqual(f['top'], 'Teu')
        self.assertEqual(f['top_goals'], 'doppietta')
        self.assertIn('@teu.9', f['scorers'])
        loss = cs.build_facts('Full Time', fulltime(home_score=3, away_score=1))
        self.assertEqual(loss['outcome'], 'loss')

    def test_scorer_lines(self):
        self.assertEqual(cs.parse_scorers("TEU 12', 38'\nDE LUCA x3\nCAVA (2)\n-"), [('Teu', 2), ('De Luca', 3), ('Cava', 2)])

    def test_placeholders_are_not_facts(self):
        f = cs.build_facts('Matchday Screen', defaults('Matchday Screen'))
        self.assertNotIn('opp', f)
        self.assertNotIn('date', f)
        self.assertEqual(cs.generate('Calendario', cs.build_facts('Calendario', defaults('Calendario'))), [])

    def test_standings_facts(self):
        config = defaults('Classifica')
        config['standings'] = [dict(r, team=r['team'].replace('SQUADRA', 'TEAM')) for r in config['standings']]
        config['prev_pos'] = 4
        f = cs.build_facts('Classifica', config)
        self.assertEqual((f['pos_ord'], f['zone'], f['up'], f['leader']), ('2°', 'promozione', '2', 'Team A'))


class GenerationTests(unittest.TestCase):
    def test_many_different_captions(self):
        f = cs.build_facts('Full Time', fulltime(), {'round': 7}, SQUAD)
        captions = cs.generate('Full Time', f, count=200, seed=1)
        self.assertEqual(len(captions), 200)
        self.assertEqual(len({c['text'] for c in captions}), 200)
        self.assertEqual({c['tone'] for c in captions}, set(cs.TONES))
        for c in captions:
            self.assertNotIn('{', c['text'])
            self.assertLessEqual(len(c['text']), cs.MAX_CHARS)
            self.assertLessEqual(len(re.findall(r'#\w+', c['text'])), 30)

    def test_every_context(self):
        sources = {'Matchday Screen': defaults('Matchday Screen'), 'Convocati': convocati(), 'Reparti': convocati(),
                   'Full Time': fulltime()}
        sources['Matchday Screen'].update(theme='none', our_side='Ospiti', home_name='UNITED FLERO', date='29/10/2026',
                                          kickoff='21:15', venue='ORATORIO FLERO')
        for context, config in sources.items():
            f = cs.build_facts(context, config, {'round': 7}, SQUAD)
            captions = cs.generate(context, f, count=40, seed=3)
            self.assertGreaterEqual(len(captions), 40, context)

    def test_options(self):
        f = cs.build_facts('Convocati', convocati(), {}, SQUAD)
        plain = cs.generate('Convocati', f, count=20, emoji=False, hashtags='nessuno', length='corta')
        for c in plain:
            self.assertIsNone(re.search(r'[\U0001F300-\U0001FAFF]', c['text']), c['text'])
            self.assertNotIn('#', c['text'])
        long_ = cs.generate('Convocati', f, count=10, length='lunga', hashtags='tanti')
        short = cs.generate('Convocati', f, count=10, length='corta')
        self.assertGreater(sum(len(c['text']) for c in long_), sum(len(c['text']) for c in short))
        only = cs.generate('Convocati', f, tones=['retro'], count=10)
        self.assertEqual({c['tone'] for c in only}, {'retro'})

    def test_seeds(self):
        f = cs.build_facts('Full Time', fulltime())
        a = [c['text'] for c in cs.generate('Full Time', f, count=10, seed=1)]
        self.assertEqual(a, [c['text'] for c in cs.generate('Full Time', f, count=10, seed=1)])
        self.assertNotEqual(a, [c['text'] for c in cs.generate('Full Time', f, count=10, seed=2)])

    def test_captain_not_repeated(self):
        f = cs.build_facts('Convocati', convocati())
        for c in cs.generate('Convocati', f, count=60, seed=4):
            self.assertLessEqual(c['text'].count('Capitano: Cava'), 1)

    def test_instagram_handles_in_squad(self):
        squad = sanitize_squad([dict(name='teu', ig='@teu.9!'), dict(name='oli')])
        self.assertEqual(squad[0]['ig'], 'teu.9')
        self.assertNotIn('ig', squad[1])


if __name__ == '__main__':
    unittest.main()
