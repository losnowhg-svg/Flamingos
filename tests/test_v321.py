"""3.21: what the CSI results give the graphics by themselves (climb, trend, opponent, moved match)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import csi_brescia as cb
import csi_sync as cs
import opponent_form as of
import standings_history as sh

FIXTURES = ROOT/'tests'/'fixtures'/'csi_brescia'
PAGES = {kind: (FIXTURES/f'{kind}.html').read_text(encoding='utf-8') for kind in cb.KINDS}
TABLE = cb.read(PAGES, 'FLAMINGOS', dt.date(2026, 11, 17))['standings']      # = CSI LIVE, 17/11/2026


def season():
    """Every result of the girone up to round 8 (17/11/2026), one week a round."""
    out = []
    for line in (FIXTURES/'risultati_17nov.txt').read_text(encoding='utf-8').splitlines():
        code, home, away, a, b = line.split('|')
        rnd = int(code[-4:-2])
        out.append(dict(home=home, away=away, score=(int(a), int(b)), round=rnd, time='20:30',
                        date=dt.date(2026, 9, 20)+dt.timedelta(days=7*rnd), code=code))
    return out


class History(unittest.TestCase):
    def test_the_last_round_is_the_real_table(self):
        teams = [r['team'] for r in TABLE]
        stats = sh.table(season(), teams)
        self.assertEqual(sh.order(stats, teams), teams)
        self.assertEqual(stats['FLAMINGOS'], dict(pt=10, g=8, v=3, n=1, p=4, gf=25, gs=32))

    def test_our_place_round_by_round(self):
        history = sh.positions(season(), TABLE)
        self.assertEqual([(h['round'], h['pos'], h['pt']) for h in history],
                         [(1, 8, 1), (2, 10, 1), (3, 8, 4), (4, 9, 4), (5, 7, 7), (6, 6, 10), (7, 9, 10), (8, 9, 10)])
        self.assertEqual(sh.previous(history), 9)

    def test_a_climb_shows_by_itself(self):
        matches = season()+[dict(home='FLAMINGOS', away='AS ARDENS 2002', score=(4, 1), round=9, date=dt.date(2026, 11, 19))]
        table = [dict(r) for r in TABLE]
        for r in table:                                              # the real table after the win
            if r['team'] == 'FLAMINGOS':
                r.update(pt=13, g=9, v=4, gf=29, gs=33)
            if r['team'] == 'AS ARDENS 2002':
                r.update(g=8, p=4, gf=35, gs=30)
        history = sh.positions(matches, table)
        self.assertEqual((sh.previous(history), history[-1]['pos']), (9, 6))   # from 9th to 6th, nobody types it

    def test_penalties_count_from_the_start(self):
        table = [dict(r, pt=r['pt']-3) if r['team'] == 'UMC' else dict(r) for r in TABLE]
        history = sh.positions(season(), table, 'UMC')
        self.assertEqual(history[-1]['pt'], 15)

    def test_missing_results_give_no_history(self):
        self.assertEqual(sh.positions(season()[:-3], TABLE), [])          # better nothing than a wrong climb


class Opponent(unittest.TestCase):
    def test_last_five_place_and_first_leg(self):
        ardens = of.form(season(), TABLE, 'AS ARDENS 2002', 'FLAMINGOS', '19/11/2026')
        self.assertEqual(ardens, dict(last=['P', 'V', 'P', 'N', 'V'], pos=8, first_leg='', first_leg_outcome=''))
        poncarale = of.form(season(), TABLE, 'GSO PONCARALE', 'FLAMINGOS', '16/01/2027')
        self.assertEqual((poncarale['pos'], poncarale['first_leg'], poncarale['first_leg_outcome']), (4, '3-3', 'N'))
        lions = of.form(season(), TABLE, 'LIONS 25', 'FLAMINGOS', '04/03/2027')
        self.assertEqual(lions['first_leg'], '5-8')                    # our goals first

    def test_only_matches_before_ours(self):
        early = of.form(season(), TABLE, 'AS ARDENS 2002', 'FLAMINGOS', '10/10/2026')
        self.assertEqual(len(early['last']), 2)

    def test_text_round_trip(self):
        data = dict(last=['V', 'N', 'P'], pos=3, first_leg='2-1', first_leg_outcome='V')
        self.assertEqual(of.decode(of.encode(data)), data)
        self.assertIsNone(of.decode(''))
        self.assertIsNone(of.decode('rotto'))
        self.assertEqual(of.encode(dict(last=[], pos=0)), '')

    def test_the_strip_on_the_matchday(self):
        try:
            import matchday_renderer as mr
            import studio_state as ss
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        config = ss.sanitize_config('Matchday Screen', dict(ss.defaults('Matchday Screen'), opponent_form='PVPNV|8||'))
        ids = [layer.id for layer in mr.get_layers(config, None)]
        self.assertIn('form', ids)
        self.assertNotIn('form', [layer.id for layer in mr.get_layers(dict(config, show_form=False), None)])
        self.assertNotIn('form', [layer.id for layer in mr.get_layers(dict(config, opponent_form=''), None)])
        moved = mr._room_for_form(config, mr.normalized_positions(config))
        self.assertEqual(moved['form'], (270, 622))                     # inside the bottom box
        custom = dict(config, positions=dict(config['positions'], kickoff=[270, 600]))
        self.assertEqual(mr._room_for_form(custom, mr.normalized_positions(custom))['kickoff'], (270, 600))


ARDENS = dict(opponent='AS ARDENS 2002', our_side='Casa', date='19/11/2026', kickoff='20:45', meeting_time='19:45',
              venue='ORATORIO FORNACI BRESCIA', round=9)
TODAY = dt.date(2026, 11, 17)


class Moved(unittest.TestCase):
    def test_new_time(self):
        site = dict(ARDENS, kickoff='21:15', meeting_time='20:15')
        step, fields = cs.match_step(ARDENS, site, ARDENS, TODAY)
        self.assertEqual(step, 'update')
        self.assertEqual(cs.moved(ARDENS, fields, ARDENS), {'kickoff': ('20:45', '21:15')})

    def test_new_day_is_the_same_match(self):
        site = dict(ARDENS, date='20/11/2026')
        step, fields = cs.match_step(ARDENS, site, ARDENS, TODAY)
        self.assertEqual((step, fields), ('update', {'date': '20/11/2026'}))
        self.assertEqual(cs.moved(ARDENS, fields, ARDENS), {'date': ('19/11/2026', '20/11/2026')})

    def test_new_pitch(self):
        site = dict(ARDENS, venue='ORATORIO PONCARALE')
        _, fields = cs.match_step(ARDENS, site, ARDENS, TODAY)
        self.assertEqual(cs.moved(ARDENS, fields, ARDENS), {'venue': ('ORATORIO FORNACI BRESCIA', 'ORATORIO PONCARALE')})

    def test_no_alarm_the_first_time_or_for_the_next_match(self):
        self.assertEqual(cs.moved(ARDENS, {'kickoff': '21:00'}, None), {})
        mustangs = dict(ARDENS, opponent='FC MUSTANGS', date='04/12/2026')
        self.assertEqual(cs.match_step(ARDENS, mustangs, ARDENS, dt.date(2026, 11, 25))[0], 'apply')
        self.assertFalse(cs.rescheduled(ARDENS, dict(ARDENS, date='12/03/2027'), ARDENS, dt.date(2026, 11, 25)))


class Bomber(unittest.TestCase):
    def test_own_goals_are_not_a_player(self):
        try:
            import wrapped_renderer as wr
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        for name in ('AUTOGOL', 'autorete', 'AUTO GOL', 'Autogoal'):
            self.assertTrue(wr.is_own_goal(name), name)
        self.assertFalse(wr.is_own_goal('AUTORI'))
        numbers = dict(played=8, w=3, d=1, l=4, points=10, gf=25, ga=32, avg=3.1, clean=0, gd=-7, best=None,
                       win_streak=1, unbeaten=1, home=dict(played=0), away=dict(played=0))
        slides = dict(wr.slides(numbers, 'STAGIONE', {}, [('TEU', 4), ('AUTOGOL', 3), ('CALLA', 3)]))
        self.assertEqual([n for n, _ in slides['bomber']['slide']['scorers']], ['TEU', 'CALLA'])

    def test_trend_slide(self):
        try:
            import wrapped_renderer as wr
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        numbers = dict(played=8, w=3, d=1, l=4, points=10, gf=25, ga=32, avg=3.1, clean=0, gd=-7, best=None,
                       win_streak=1, unbeaten=1, home=dict(played=0), away=dict(played=0))
        history = sh.positions(season(), TABLE)
        slides = dict(wr.slides(numbers, 'STAGIONE', {'team_count': 13}, positions=history))
        self.assertEqual(slides['andamento']['slide']['line1'], 'DAL POSTO 8 AL POSTO 9')
        self.assertEqual(slides['andamento']['slide']['line2'], 'MIGLIOR POSIZIONE: 6')
        self.assertNotIn('andamento', dict(wr.slides(numbers, 'STAGIONE', {}, positions=history[:1])))


if __name__ == '__main__':
    unittest.main()
