"""Version 1.7: zones, captions, CRT sounds, next match from CSI LIVE, month calendar."""
import base64
import datetime as dt
import gzip
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import imageio_ffmpeg
import numpy as np

import calendario_renderer as cal
import captions as cap
import classifica_renderer as k
import sounds
from classifica_data import bookmarklet, parse_standings, with_rows
from crt_presets import CROPS, PRESET_IDS, apply_preset
from csi_page import decode_payload, fixtures_for_month, read_page
from render_utils import layout_warnings
from studio_state import DEFAULTS, MODULES, defaults, sanitize_config
from tests.fixtures.csi_samples import BLOCKS, CARDS, LINES, STANDINGS
from transitions import render_sequence

ROOT = Path(__file__).resolve().parents[1]
LOGO = (ROOT/'assets/flamingos_logo.jpg').read_bytes()
TODAY = dt.date(2026, 10, 23)


def girone_rows():
    return parse_standings(STANDINGS)


class ZoneTests(unittest.TestCase):
    def test_zone_boundaries(self):
        config = defaults('Classifica')
        self.assertEqual([k.zone_of(p, config) for p in range(1, 8)],
                         ['promo']*3+['playoff']*2+[None]*2)
        self.assertIsNone(k.zone_of(1, dict(config, show_zones=False)))
        self.assertEqual(k.zone_of(2, dict(config, promo_count=1, playoff_count=3)), 'playoff')

    def test_zone_colours_reach_the_pixels(self):
        config = with_rows(defaults('Classifica'), girone_rows())
        with_zones = np.asarray(k.table_image(config), int)
        without = np.asarray(k.table_image(dict(config, show_zones=False)), int)
        self.assertGreater(np.abs(with_zones-without).sum(), 50000)

    def test_full_girone_fits_every_preset(self):
        for preset in PRESET_IDS:
            with self.subTest(preset=preset):
                config = with_rows(apply_preset(defaults('Classifica'), preset, True), girone_rows())
                self.assertFalse(layout_warnings(k.scene(config, LOGO, render_scale=1), CROPS['Post 4:5']))


class CaptionTests(unittest.TestCase):
    def fulltime(self, home, away, side='Casa', pens=None):
        config = defaults('Full Time')
        config.update(home_name='FLAMINGOS', away_name='REAL BOVEZZO', home_score=home, away_score=away, our_side=side)
        if pens:
            config.update(show_penalties=True, home_penalties=pens[0], away_penalties=pens[1])
        return config

    def test_outcome_from_our_side(self):
        self.assertEqual(cap.outcome(self.fulltime(5, 1)), 'big_win')
        self.assertEqual(cap.outcome(self.fulltime(2, 1)), 'win')
        self.assertEqual(cap.outcome(self.fulltime(2, 2)), 'draw')
        self.assertEqual(cap.outcome(self.fulltime(2, 1, 'Ospiti')), 'defeat')
        self.assertEqual(cap.outcome(self.fulltime(1, 5, 'Ospiti')), 'big_win')
        self.assertEqual(cap.outcome(self.fulltime(2, 2, pens=(5, 4))), 'pen_win')
        self.assertEqual(cap.outcome(self.fulltime(2, 2, 'Ospiti', pens=(5, 4))), 'pen_loss')

    def test_every_editor_has_several_retro_captions(self):
        for template in DEFAULTS:
            with self.subTest(template=template):
                texts = cap.captions(template, defaults(template))
                self.assertGreaterEqual(len(texts), 2)
                for text in texts:
                    self.assertIn('#Flamingos', text)
                    self.assertNotIn('GG/MM/AAAA', text)
                    self.assertNotIn('HH:MM', text)

    def test_fulltime_texts_change_with_result_and_name_scorers(self):
        win = self.fulltime(3, 1); win['home_scorers'] = "ROSSI 12'\nBIANCHI 30'"
        loss = self.fulltime(0, 1)
        self.assertNotEqual(cap.captions('Full Time', win), cap.captions('Full Time', loss))
        self.assertIn("Rossi 12'", cap.captions('Full Time', win)[0])

    def test_classifica_texts_follow_position(self):
        rows = girone_rows()
        config = with_rows(defaults('Classifica'), rows)
        sixth = cap.captions('Classifica', config)[0]
        self.assertIn('6° posto', sixth)
        config['our_team'] = 'UMC'
        self.assertIn('PLAYER 1', cap.captions('Classifica', config)[0])
        config['our_team'] = 'GSO PONCARALE'
        self.assertIn('SPAREGGIO', cap.captions('Classifica', config)[0])


class SoundTests(unittest.TestCase):
    def test_every_transition_sound_is_bounded(self):
        for name, factory in sounds.TRANSITION_SOUNDS.items():
            with self.subTest(name=name):
                data = factory(1.0)
                self.assertGreater(len(data), sounds.SR*.9)
                self.assertTrue(np.isfinite(data).all())
                self.assertLess(np.abs(sounds.mix([(0, data)], 1.2)).max(), 1.0)

    def test_blips_follow_entrances(self):
        scene = MODULES['Matchday Screen'].scene(defaults('Matchday Screen'), LOGO, None, None, 1)
        times = sounds.entrance_times(scene, MODULES['Matchday Screen'].compose)
        self.assertEqual(len(times), len(scene[1])); self.assertEqual(times, sorted(times))

    def test_sequence_mp4_carries_audio(self):
        scenes = [(MODULES[t].scene(defaults(t), LOGO, None, None, 1), MODULES[t].compose)
                  for t in ('Matchday Screen', 'Calendario')]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'seq.mp4'
            render_sequence(scenes, ['rewind'], path, 12, 2.0, 1.0, 'Post 1:1', 1, sound=True)
            info = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-i', str(path)], capture_output=True, text=True).stderr
            self.assertIn('Audio: aac', info)
            self.assertIn('Video: h264', info)


class CsiPageTests(unittest.TestCase):
    def page(self, body):
        return {'t': '', 'x': STANDINGS+'\n'+body+'\n'+CARDS, 'u': ''}

    def test_line_layout(self):
        result = read_page(self.page(LINES), 'FLAMINGOS', TODAY)
        self.assertEqual(len(result['standings']), 13)
        self.assertEqual(len(result['matches']), 5)
        played = result['matches'][0]
        self.assertEqual((played['home'], played['away'], played['score']), ('GALBA F.C.', 'FLAMINGOS', (2, 4)))
        self.assertEqual(result['fields'], dict(opponent='LIONS 25', our_side='Casa', date='30/10/2026', kickoff='20:45',
                                                meeting_time='19:45', venue='ORATORIO FORNACI BRESCIA', round=6))

    def test_block_layout_without_years_and_away_venue_from_card(self):
        result = read_page(self.page(BLOCKS), 'FLAMINGOS', dt.date(2026, 10, 31))
        self.assertEqual(result['fields']['opponent'], 'LIONS 25')
        self.assertEqual(result['fields']['our_side'], 'Ospiti')
        self.assertEqual(result['fields']['date'], '08/11/2026')
        self.assertEqual(result['fields']['kickoff'], '18:00')  # from the Lions 25 card
        self.assertEqual(result['fields']['venue'], 'CAMPO LIONS VIA MILANO 1 BRESCIA')

    def test_venue_from_card_drops_the_postcode(self):
        from csi_page import match_fields
        match = dict(home='UNITED FLERO', away='FLAMINGOS', date=dt.date(2026, 10, 30), time='', score=None, venue='', round=6)
        cards = {'UNITED FLERO': dict(time='21:15', venue='Oratorio Flero Via Giuseppe Mazzini 25020 Flero')}
        fields = match_fields(match, 'FLAMINGOS', cards)
        self.assertEqual((fields['venue'], fields['kickoff'], fields['meeting_time'], fields['our_side']),
                         ('ORATORIO FLERO VIA GIUSEPPE MAZZINI FLERO', '21:15', '20:15', 'Ospiti'))

    def test_team_cards_do_not_bleed(self):
        cards = read_page(self.page(LINES), 'FLAMINGOS', TODAY)['cards']
        self.assertEqual((cards['FLAMINGOS']['colors'], cards['FLAMINGOS']['time']), ('Rosa', '20:45'))
        self.assertEqual(cards['GALBA F.C.']['time'], '20:15')

    def test_no_false_matches_from_standings_or_cards(self):
        result = read_page({'t': '', 'x': STANDINGS+'\n'+CARDS, 'u': ''}, 'FLAMINGOS', TODAY)
        self.assertEqual(result['matches'], [])
        self.assertIsNone(result['fields'])

    def test_payload_roundtrip_and_v1(self):
        data = json.dumps({'v': 2, 'u': 'x', 't': STANDINGS, 'x': LINES})
        value = 'z'+base64.urlsafe_b64encode(gzip.compress(data.encode())).decode().rstrip('=')
        self.assertEqual(decode_payload(value)['t'], STANDINGS)
        self.assertEqual(decode_payload('1\tUMC')['t'], '1\tUMC')
        with self.assertRaises(ValueError):
            decode_payload('znot-base64!!')

    def test_month_fixtures_from_our_side(self):
        result = read_page(self.page(LINES), 'FLAMINGOS', TODAY)
        rows = fixtures_for_month(result['matches'], 'FLAMINGOS', 2026, 10)
        self.assertEqual([(r['date'], r['opponent'], r['side'], r['score']) for r in rows],
                         [('23/10', 'GALBA F.C.', 'T', '2-4'), ('30/10', 'LIONS 25', 'C', '')])
        self.assertEqual(cal.result_of(rows[0]), 'V')

    def test_bookmarklet_v2(self):
        code = bookmarklet()
        self.assertTrue(all(ord(ch) < 128 for ch in code))
        self.assertIn('CompressionStream', code)
        self.assertNotIn('__', code)


class CalendarTests(unittest.TestCase):
    def test_results_from_our_side(self):
        self.assertEqual(cal.result_of(dict(score='3-1', side='C')), 'V')
        self.assertEqual(cal.result_of(dict(score='3-1', side='T')), 'P')
        self.assertEqual(cal.result_of(dict(score='2-2', side='T')), 'N')
        self.assertIsNone(cal.result_of(dict(score='', side='C')))

    def test_every_preset_and_count_fits(self):
        for preset in PRESET_IDS:
            for count in (1, 4, cal.MAX_FIXTURES):
                with self.subTest(preset=preset, count=count):
                    config = apply_preset(defaults('Calendario'), preset, True)
                    for i in range(count):
                        config['fixtures'][i].update(opponent=config['fixtures'][i]['opponent'] or f'SQUADRA {i}', date='01/11')
                    config['fixture_count'] = count
                    self.assertFalse(layout_warnings(cal.scene(config, LOGO, render_scale=1), CROPS['Post 4:5']))

    def test_sanitize_fixtures(self):
        config = defaults('Calendario')
        config['fixtures'][0].update(side='X', opponent='A'*80, score='12345678')
        clean = sanitize_config('Calendario', config)
        self.assertEqual(clean['fixtures'][0]['side'], 'C')
        self.assertEqual(len(clean['fixtures'][0]['opponent']), 30)
        self.assertEqual(len(clean['fixtures']), cal.MAX_FIXTURES)


if __name__ == '__main__':
    unittest.main()
