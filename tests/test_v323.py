"""3.23: the app as an app on the phone (bottom bar, Home with the next match)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_shell as sh

MATCH = dict(our_name='FLAMINGOS', opponent='FC MUSTANGS', our_side='Ospiti', date='04/12/2026', kickoff='20:30',
             meeting_time='19:30', venue='PARROCCHIA TORBOLE CASAGLIA', round=11)
TODAY = dt.date(2026, 11, 24)


class Card(unittest.TestCase):
    def test_when(self):
        self.assertEqual(sh.when_label(MATCH, TODAY), ('Ven 4 dicembre · 20:30', 'tra 10 giorni'))
        self.assertEqual(sh.when_label(MATCH, dt.date(2026, 12, 3))[1], 'domani')
        self.assertEqual(sh.when_label(MATCH, dt.date(2026, 12, 4))[1], 'oggi')
        self.assertEqual(sh.when_label(MATCH, dt.date(2026, 12, 6))[1], 'giocata 2 giorni fa')
        self.assertEqual(sh.when_label(dict(MATCH, date='GG/MM/AAAA'), TODAY), ('Data da decidere', ''))
        self.assertEqual(sh.when_label(dict(MATCH, kickoff='HH:MM'), TODAY)[0], 'Ven 4 dicembre')

    def test_card_away_side_and_form(self):
        card = sh.match_card(MATCH, TODAY, form=dict(last=['P', 'P', 'V', 'V', 'V'], pos=2, first_leg=''))
        self.assertIn('PROSSIMA PARTITA', card)
        self.assertIn('GIORNATA 11', card)
        self.assertIn('Fuori casa', card)
        self.assertLess(card.index('Fc Mustangs'), card.index('Flamingos'))      # they are at home: on the left
        self.assertIn('ritrovo 19:30', card)
        self.assertIn('2° posto', card)
        self.assertEqual(card.count('fs-sq'), 5)

    def test_names_are_escaped(self):
        card = sh.match_card(dict(MATCH, opponent='<script>x</script>', venue='A & B'), TODAY)
        self.assertNotIn('<script>', card)
        self.assertIn('&amp;', card)

    def test_played_match(self):
        self.assertIn('ULTIMA PARTITA', sh.match_card(MATCH, dt.date(2026, 12, 5)))

    def test_badges(self):
        self.assertEqual(sh.initials('FC MUSTANGS'), 'MUS')
        self.assertEqual(sh.initials('GSO PONCARALE'), 'PON')
        self.assertIn('data:image/png;base64,', sh.match_card(MATCH, TODAY, home_logo=b'\x89PNG'))


class Pieces(unittest.TestCase):
    def test_sparkline(self):
        history = [dict(round=r, pos=p) for r, p in enumerate((8, 10, 8, 9, 7, 6, 9, 9), 1)]
        svg = sh.sparkline(history)
        self.assertIn('<polyline', svg)
        self.assertIn('8, 10, 8, 9, 7, 6, 9, 9', svg)
        self.assertEqual(sh.sparkline(history[:1]), '')

    def test_tile_status(self):
        self.assertEqual(sh.tile_status('Full Time', [], MATCH, TODAY)[0], 'DOPO LA PARTITA')
        self.assertEqual(sh.tile_status('Full Time', [], MATCH, dt.date(2026, 12, 5))[0], 'PRONTA')
        self.assertEqual(sh.tile_status('Matchday Screen', ['orario'], MATCH, TODAY)[0], 'DA FARE')

    def test_bar(self):
        self.assertEqual([label for _, label, _ in sh.NAV], ['Home', 'Matchday', 'Full Time', 'Classifica'])

    def test_every_tile_is_a_page(self):
        text = (ROOT/'app.py').read_text()
        for target, _, _ in sh.MORE+sh.NAV+sh.TILES:
            self.assertIn(f"'{target}'", text)
        self.assertIn('@media (max-width:640px)', sh.CSS)
        self.assertIn('position:fixed', sh.CSS)


if __name__ == '__main__':
    unittest.main()
