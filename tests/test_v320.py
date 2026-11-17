"""3.20: the girone straight from the CSI Brescia results site (no bookmark, no copy-paste)."""
import datetime as dt
import io
import sys
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import csi_brescia as cb
import csi_sync as cs

FIXTURES = ROOT/'tests'/'fixtures'/'csi_brescia'
PAGES = {kind: (FIXTURES/f'{kind}.html').read_text(encoding='utf-8') for kind in cb.KINDS}
TODAY = dt.date(2026, 11, 17)


class Reading(unittest.TestCase):
    def test_standings_in_the_site_order(self):
        rows = cb.parse_standings(PAGES['classifiche'])
        self.assertEqual(len(rows), 13)
        self.assertEqual(rows[0], dict(pos=1, team='UMC', pt=18, g=8, v=5, n=3, p=0, gf=31, gs=17))
        ours = next(r for r in rows if r['team'] == 'FLAMINGOS')
        self.assertEqual((ours['pos'], ours['pt'], ours['g'], ours['v'], ours['n'], ours['p'], ours['gf'], ours['gs']),
                         (8, 10, 7, 3, 1, 3, 20, 24))
        self.assertEqual([r['pos'] for r in rows], list(range(1, 14)))

    def test_no_table_is_a_clear_error(self):
        with self.assertRaises(cb.CSIError):
            cb.parse_standings('<html>Manutenzione</html>')

    def test_results_and_fixtures(self):
        matches = cb.parse_results(PAGES['risultati'])
        first = next(m for m in matches if m['code'] == '2026102DA0105')
        self.assertEqual((first['home'], first['away'], first['date'], first['time'], first['score'], first['round']),
                         ('FLAMINGOS', 'GSO PONCARALE', dt.date(2026, 9, 24), '20:45', (3, 3), 1))
        self.assertTrue(first['official'])
        red = next(m for m in matches if m['code'] == '2026102DA0703')
        self.assertEqual(red['score'], (9, 2))                      # "ufficioso": shown, and counted by the site
        self.assertFalse(red['official'])
        hidden = next(m for m in matches if m['code'] == '2026102DA0806')
        self.assertIsNone(hidden['score'])                           # typed by a team, not shown yet: left out
        nxt = next(m for m in matches if m['code'] == '2026102DA0901')
        self.assertEqual(nxt['venue'], 'ORATORIO FORNACI BRESCIA FORNACI 82 - BRESCIA BS')
        self.assertEqual([m['date'] for m in matches], sorted(m['date'] for m in matches))

    def test_return_leg_rounds_follow_the_first_leg(self):
        matches = cb.parse_results(PAGES['risultati'])
        back = next(m for m in matches if m['code'] == '2026102DR0105')
        self.assertEqual((back['home'], back['away'], back['round']), ('GSO PONCARALE', 'FLAMINGOS', 14))

    def test_team_cards(self):
        cards = cb.parse_teams(PAGES['squadre'])
        self.assertEqual(cards['FLAMINGOS'], dict(venue='ORATORIO FORNACI BRESCIA, FORNACI 82 - 25131 BRESCIA (BS)',
                                                  day='Giovedì', time='20:45', colors='ROSA'))
        self.assertEqual(cards['UMC']['day'], 'Lunedì')

    def test_everything_in_the_read_page_shape(self):
        page = cb.read(PAGES, 'FLAMINGOS', TODAY)
        self.assertEqual(set(page), {'standings', 'matches', 'cards', 'next', 'fields', 'url'})
        self.assertEqual(page['fields'], dict(opponent='AS ARDENS 2002', our_side='Casa', date='19/11/2026',
                                              kickoff='20:45', meeting_time='19:45',
                                              venue='ORATORIO FORNACI BRESCIA FORNACI 82 - BRESCIA BS', round=9))
        from csi_page import fixtures_for_month
        november = fixtures_for_month(page['matches'], 'FLAMINGOS', 2026, 11, 8)
        self.assertEqual([(f['date'], f['opponent'], f['side'], f['score']) for f in november],
                         [('05/11', 'CASTE UNITED', 'C', '2-5'), ('14/11', 'LIONS 25', 'T', ''),
                          ('19/11', 'AS ARDENS 2002', 'C', '')])


class Response:
    def __init__(self, body, charset='utf-8'):
        self.body, self.headers = body.encode(charset), self
        self.charset = charset

    def get_content_charset(self):
        return self.charset

    def read(self, limit=None):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Download(unittest.TestCase):
    def test_three_posts_like_the_site(self):
        seen = []

        def opener(request, timeout):
            form = dict(urllib.parse.parse_qsl(request.data.decode()))
            seen.append(form)
            self.assertEqual(request.full_url, cb.ENDPOINT)
            self.assertLessEqual(timeout, 10)
            kind = next(k for k in cb.KINDS if form.get(k) == 'ok')
            return Response(PAGES[kind], 'cp1252' if kind == 'squadre' else 'utf-8')

        page = cb.download('FLAMINGOS', TODAY, opener=opener)
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(f['campionato'] == '102' and f['girone'] == 'D' and f['albo'] == 'ok' for f in seen))
        self.assertEqual(page['cards']['FLAMINGOS']['day'], 'Giovedì')     # accented letters survive any charset

    def test_unreachable_site_is_one_short_reason(self):
        def opener(request, timeout):
            raise urllib.error.URLError('timed out')

        with self.assertRaises(cb.CSIError) as caught:
            cb.download(opener=opener)
        self.assertIn('non risponde', str(caught.exception))

        def forbidden(request, timeout):
            raise urllib.error.HTTPError(cb.ENDPOINT, 403, 'Forbidden', {}, io.BytesIO())

        with self.assertRaises(cb.CSIError) as caught:
            cb.download(opener=forbidden)
        self.assertIn('403', str(caught.exception))


ARDENS = dict(opponent='AS ARDENS 2002', our_side='Casa', date='19/11/2026', kickoff='20:45', meeting_time='19:45',
              venue='ORATORIO FORNACI BRESCIA FORNACI 82 - BRESCIA BS', round=9)
LIONS = dict(opponent='LIONS 25', our_side='Ospiti', date='14/11/2026', kickoff='18:00', meeting_time='17:00',
             venue='CAMPO OR. SAN DOMENICO SAVIO', round=8)


class When(unittest.TestCase):
    def test_once_an_hour(self):
        now = dt.datetime(2026, 11, 17, 22, 0)
        self.assertTrue(cs.due({}, now))
        self.assertTrue(cs.due({'tried_at': 'rotto'}, now))
        self.assertFalse(cs.due({'tried_at': '2026-11-17T21:30:00'}, now))
        self.assertTrue(cs.due({'tried_at': '2026-11-17T20:59:00'}, now))
        rome = dt.timezone(dt.timedelta(hours=1))
        self.assertFalse(cs.due({'tried_at': '2026-11-17T21:30:00+01:00'}, now.replace(tzinfo=rome)))


class NextMatch(unittest.TestCase):
    def test_a_match_long_gone_moves_on(self):
        step, fields = cs.match_step(dict(LIONS, date='01/11/2026'), ARDENS, None, TODAY)
        self.assertEqual((step, fields['opponent']), ('apply', 'AS ARDENS 2002'))

    def test_two_days_for_the_full_time_then_on(self):
        # Lions 14/11: on the 15th and 16th the graphics stay on it, on the 17th they move to Ardens
        for day, expected in ((14, 'hold'), (15, 'hold'), (16, 'hold'), (17, 'apply')):
            step, _ = cs.match_step(LIONS, ARDENS, None, dt.date(2026, 11, day))
            self.assertEqual(step, expected, day)
        self.assertEqual(cs.held_until(LIONS), dt.date(2026, 11, 16))

    def test_the_example_match_is_replaced_at_once(self):
        step, _ = cs.match_step(dict(LIONS, opponent='AVVERSARI', date=TODAY.strftime('%d/%m/%Y')), ARDENS, None, TODAY)
        self.assertEqual(step, 'apply')

    def test_same_match_only_what_the_site_changed(self):
        mine = dict(ARDENS, meeting_time='19:30', venue='FORNACI')         # a friend corrected these
        self.assertEqual(cs.match_step(mine, ARDENS, ARDENS, TODAY), ('keep', {}))
        moved = dict(ARDENS, kickoff='21:00', meeting_time='20:00')        # the site moves the kick-off
        step, fields = cs.match_step(mine, moved, ARDENS, TODAY)
        self.assertEqual((step, fields), ('update', {'kickoff': '21:00', 'meeting_time': '20:00'}))

    def test_first_time_from_the_site_keeps_a_friends_venue(self):
        mine = dict(ARDENS, kickoff='20:30', venue='FORNACI')
        self.assertEqual(cs.match_step(mine, ARDENS, None, TODAY), ('update', {'kickoff': '20:45'}))

    def test_a_match_chosen_by_hand_stays_until_the_site_moves_on(self):
        friendly = dict(ARDENS, opponent='AMICHEVOLE', date='18/11/2026')
        self.assertEqual(cs.match_step(friendly, ARDENS, ARDENS, TODAY), ('keep', {}))
        mustangs = dict(ARDENS, opponent='FC MUSTANGS', date='04/12/2026')
        self.assertEqual(cs.match_step(friendly, mustangs, ARDENS, dt.date(2026, 11, 25))[0], 'apply')

    def test_nothing_on_the_site(self):
        self.assertEqual(cs.match_step(LIONS, None, None, TODAY), ('keep', {}))


class FullTime(unittest.TestCase):
    MATCHES = [dict(home='LIONS 25', away='FLAMINGOS', date=dt.date(2026, 11, 14), time='18:00', score=(8, 5),
                    venue='', round=8),
               dict(home='FLAMINGOS', away='AS ARDENS 2002', date=dt.date(2026, 11, 19), time='20:45', score=None,
                    venue='', round=9)]
    EDITOR = dict(home_name='LIONS 25', away_name='FLAMINGOS', our_side='Ospiti', date='14/11/2026',
                  home_score=0, away_score=0)

    def test_the_result_fills_an_untouched_editor(self):
        self.assertEqual(cs.fulltime_score(self.EDITOR, self.MATCHES), (8, 5))

    def test_home_side_too(self):
        matches = [dict(self.MATCHES[1], score=(4, 2))]
        editor = dict(home_name='FLAMINGOS', away_name='AS ARDENS 2002', our_side='Casa', date='19/11/2026',
                      home_score=0, away_score=0)
        self.assertEqual(cs.fulltime_score(editor, matches), (4, 2))

    def test_a_score_typed_by_hand_is_never_covered(self):
        self.assertIsNone(cs.fulltime_score(dict(self.EDITOR, home_score=7, away_score=5), self.MATCHES))
        self.assertIsNone(cs.fulltime_score(dict(self.EDITOR, home_score=8, away_score=5), self.MATCHES))
        # but the site's own earlier score is corrected when the site corrects it
        self.assertEqual(cs.fulltime_score(dict(self.EDITOR, home_score=8, away_score=4), self.MATCHES, last=[8, 4]),
                         (8, 5))

    def test_other_matches_or_no_score(self):
        self.assertIsNone(cs.fulltime_score(dict(self.EDITOR, date='19/11/2026', home_name='FLAMINGOS',
                                                 away_name='AS ARDENS 2002', our_side='Casa'), self.MATCHES))
        self.assertIsNone(cs.fulltime_score(dict(self.EDITOR, home_name='UMC'), self.MATCHES))



class Banner(unittest.TestCase):
    def test_the_result_already_in_the_full_time(self):
        import ui_utils
        match = dict(opponent='LIONS 25', date='14/11/2026', kickoff='18:00')
        self.assertIn('8-5 è già nel Full Time', ui_utils.countdown(match, dt.date(2026, 11, 15), (8, 5)))
        self.assertIn('inserisci il risultato', ui_utils.countdown(match, dt.date(2026, 11, 15), (0, 0)))


if __name__ == '__main__':
    unittest.main()
