"""3.17: integrazione tra schermate (Full Time -> stagione, Full Time -> Risultati della giornata e Classifica)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import integration as ig
from studio_state import defaults

TODAY = dt.date(2026, 11, 4)


def fulltime(home=3, away=1, scorers="TEU 12', 38'\nCAVA", date='01/11/2026', opp='UNITED FLERO', side='Casa'):
    config = defaults('Full Time')
    config.update(home_name='FLAMINGOS' if side == 'Casa' else opp, away_name=opp if side == 'Casa' else 'FLAMINGOS',
                  our_side=side, date=date, home_score=home, away_score=away,
                  home_scorers=scorers if side == 'Casa' else '', away_scorers='' if side == 'Casa' else scorers)
    return config


class Names(unittest.TestCase):
    def test_same_team_spelled_differently(self):
        self.assertTrue(ig.same_team('A.S.D. United Flero', 'UNITED FLERO'))
        self.assertTrue(ig.same_team('GSO Poncarale', 'G.S.O. PONCARALE'))
        self.assertFalse(ig.same_team('UMC', 'PIRATI'))
        self.assertEqual(ig.parse_date('01/11/2026'), dt.date(2026, 11, 1))
        self.assertIsNone(ig.parse_date('GG/MM/AAAA'))


class Season(unittest.TestCase):
    def test_when_a_result_counts(self):
        result, _ = ig.fulltime_result(fulltime(), today=TODAY)
        self.assertEqual((result['us'], result['them'], result['opp']), (3, 1, 'UNITED FLERO'))
        self.assertEqual(result['goals'], {'TEU': 2, 'CAVA': 1})
        self.assertIsNone(ig.fulltime_result(fulltime(date='06/11/2026'), today=TODAY)[0])      # not played yet
        self.assertIsNone(ig.fulltime_result(fulltime(date='GG/MM/AAAA'), today=TODAY)[0])
        self.assertIsNone(ig.fulltime_result(fulltime(opp='AVVERSARI'), today=TODAY)[0])
        away, _ = ig.fulltime_result(fulltime(home=1, away=2, side='Ospiti'), today=TODAY)
        self.assertEqual((away['us'], away['them'], away['home']), (2, 1, False))
        self.assertFalse(ig.worth_recording(ig.fulltime_result(fulltime(0, 0, ''), today=TODAY)[0]))

    def test_record_correct_and_undo_without_counting_twice(self):
        state = {'season_scorers': [dict(name='TEU', goals=5), dict(name='BOBBI', goals=1)]}
        result, _ = ig.fulltime_result(fulltime(), today=TODAY)
        self.assertTrue(ig.record(state, result))
        self.assertFalse(ig.record(state, result))                       # the same again: nothing changes
        goals = {s['name']: s['goals'] for s in state['season_scorers']}
        self.assertEqual(goals, {'TEU': 7, 'BOBBI': 1, 'CAVA': 1})
        self.assertEqual(len(state['season_games']), 1)
        fixed, _ = ig.fulltime_result(fulltime(4, 1, "TEU 12', 38', 50'\nDEMA"), today=TODAY)    # a correction
        ig.record(state, fixed)
        goals = {s['name']: s['goals'] for s in state['season_scorers']}
        self.assertEqual(goals, {'TEU': 8, 'BOBBI': 1, 'DEMA': 1})                              # CAVA's goal gone
        self.assertEqual((state['season_games'][0]['us'], len(state['season_games'])), (4, 1))
        self.assertTrue(ig.unrecord(state, fixed['key']))
        goals = {s['name']: s['goals'] for s in state['season_scorers']}
        self.assertEqual(goals, {'TEU': 5, 'BOBBI': 1})
        self.assertEqual(state['season_games'], [])

    def test_the_csi_calendar_wins_for_the_game(self):
        csi = [dict(home='A.S.D. UNITED FLERO', away='FLAMINGOS', date=dt.date(2026, 11, 1), time='20:45', score=(1, 3),
                    venue='', round=6)]
        state = {'csi_matches': csi}
        result, _ = ig.fulltime_result(fulltime(side='Ospiti', home=1, away=3), today=TODAY)
        ig.record(state, result)
        self.assertEqual(state['season_games'], [])                      # the CSI already has the game...
        self.assertEqual({s['name']: s['goals'] for s in state['season_scorers']}, {'TEU': 2, 'CAVA': 1})   # ...not the goals
        from season_stats import our_games
        games = ig.merge_games(our_games(csi, 'FLAMINGOS'), [dict(date=dt.date(2026, 11, 1), opp='UNITED FLERO', home=False,
                                                                     us=3, them=1, round=None)])
        self.assertEqual(len(games), 1)                                  # spelled differently, still one game


class ResultsAndTable(unittest.TestCase):
    def setUp(self):
        self.result, _ = ig.fulltime_result(fulltime(side='Ospiti', home=1, away=3), today=TODAY)
        self.csi = [dict(home='A.S.D. UNITED FLERO', away='FLAMINGOS', date=dt.date(2026, 11, 1), time='20:45', score=None,
                         venue='', round=6),
                    dict(home='UMC', away='PIRATI', date=dt.date(2026, 11, 1), time='21:00', score=None, venue='', round=6)]

    def test_our_score_in_the_round_results(self):
        matches, filled = ig.with_fulltime(self.csi, self.result)
        self.assertTrue(filled)
        self.assertEqual(matches[0]['score'], (1, 3))                   # home first, as on the CSI site
        self.assertIsNone(matches[1]['score'])
        self.assertIsNone(self.csi[0]['score'])                          # the CSI list itself is untouched
        import results_round as rr
        group = rr.rounds(matches)[0]
        self.assertEqual(group['played'], 1)

    def test_provisional_table(self):
        config = defaults('Classifica')
        config['standings'][1]['team'] = 'FLAMINGOS'
        config['standings'][2]['team'] = 'U.S. UNITED FLERO'
        config['round_label'] = 'GIORNATA 6'
        before = {r['team']: dict(r) for r in config['standings'][:config['team_count']]}
        updated = ig.apply_provisional(config, self.result)
        after = {r['team']: r for r in updated['standings'][:updated['team_count']]}
        self.assertEqual(after['FLAMINGOS']['pt'], before['FLAMINGOS']['pt']+3)
        self.assertEqual(after['FLAMINGOS']['g'], before['FLAMINGOS']['g']+1)
        self.assertEqual(after['U.S. UNITED FLERO']['p'], before['U.S. UNITED FLERO']['p']+1)
        self.assertEqual(after['FLAMINGOS']['gf'], before['FLAMINGOS']['gf']+3)
        self.assertEqual(after['FLAMINGOS']['pos'], 1)                   # 17+3 = 20 > 19: first
        self.assertEqual(updated['round_label'], 'GIORNATA 6 · PROVVISORIA')
        self.assertEqual(ig.plain_label(updated['round_label']), 'GIORNATA 6')
        self.assertEqual(ig.provisional_label(updated['round_label']), 'GIORNATA 6 · PROVVISORIA')   # never twice
        self.assertIsNone(ig.apply_provisional(defaults('Classifica'), self.result))   # opponent not in the table
        played = [dict(self.csi[0], score=(1, 3))]
        self.assertFalse(ig.standings_have(updated['standings'], self.result, 'FLAMINGOS', self.csi))
        self.assertTrue(ig.standings_have(config['standings'], self.result, 'FLAMINGOS', played))


if __name__ == '__main__':
    unittest.main()
