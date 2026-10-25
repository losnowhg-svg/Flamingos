"""2.4: Flamingos Wrapped, sponsor, profile picture and highlight covers."""
import datetime as dt
import hashlib
import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mockup
import profile_pics as pp
import season_stats as ss
import sponsor
import wrapped_renderer as wr
from studio_state import MODULES, defaults, sanitize_config, sanitize_week

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
D = dt.date


def sponsor_logo():
    im = Image.new('RGB', (400, 160), 'white')
    ImageDraw.Draw(im).rounded_rectangle((10, 20, 390, 140), 30, fill=(30, 90, 200))
    out = io.BytesIO()
    im.save(out, 'PNG')
    data = out.getvalue()
    sid = 'logo:'+hashlib.sha256(data).hexdigest()
    sponsor.register({sid: {'kind': 'logo', 'bytes': data}})
    return sid


GAMES = [dict(date=D(2026, 9, 25), opp='REAL BOVEZZO', home=True, us=3, them=1, round=1),
         dict(date=D(2026, 10, 2), opp='LIONS 25', home=False, us=2, them=2, round=2),
         dict(date=D(2026, 10, 9), opp='ATLETICO 7', home=True, us=5, them=0, round=3),
         dict(date=D(2026, 10, 16), opp='UMC', home=False, us=1, them=0, round=4),
         dict(date=D(2026, 10, 30), opp='UNITED FLERO', home=False, us=0, them=2, round=5)]


class SeasonTests(unittest.TestCase):
    def test_numbers(self):
        n = ss.stats(GAMES)
        self.assertEqual((n['played'], n['w'], n['d'], n['l'], n['points']), (5, 3, 1, 1, 10))
        self.assertEqual((n['gf'], n['ga'], n['clean']), (11, 5, 2))
        self.assertEqual(n['best']['opp'], 'ATLETICO 7')
        self.assertEqual(n['unbeaten'], 4)
        self.assertEqual(n['win_streak'], 2)
        self.assertEqual(n['home']['w'], 2)
        self.assertEqual(ss.stats([]), {})

    def test_periods(self):
        self.assertEqual(len(ss.select(GAMES, 'mese', (2026, 10))), 4)
        self.assertEqual(ss.period_label('mese', (2026, 10)), 'OTTOBRE 2026')
        self.assertEqual(ss.period_label('stagione', games=GAMES), 'STAGIONE 2026/27')
        matches = [dict(home='FLAMINGOS', away='X', date=D(2026, 9, 1)+dt.timedelta(days=7*i), score=None, round=i+1)
                   for i in range(10)]
        self.assertEqual(len(ss.select(GAMES, 'andata', all_matches=matches)), 5)

    def test_csi_matches(self):
        matches = [dict(home='FLAMINGOS', away='LIONS', date=D(2026, 10, 2), score=(2, 1), round=1),
                   dict(home='UMC', away='FLAMINGOS', date=D(2026, 10, 9), score=(3, 0), round=2),
                   dict(home='UMC', away='LIONS', date=D(2026, 10, 9), score=(1, 1), round=2),
                   dict(home='FLAMINGOS', away='GALBA', date=D(2026, 10, 16), score=None, round=3)]
        games = ss.our_games(matches, 'FLAMINGOS')
        self.assertEqual([(g['opp'], g['us'], g['them'], g['home']) for g in games],
                         [('LIONS', 2, 1, True), ('UMC', 0, 3, False)])


class WrappedTests(unittest.TestCase):
    def test_slides_and_render(self):
        base = dict(defaults('Classifica'), theme='none')
        slides = wr.slides(ss.stats(GAMES), 'STAGIONE 2026/27', base, [('TEU', 5), ('CAVA', 0)], dict(pos=2, pt=17), [])
        self.assertEqual([k for k, _ in slides], list(wr.SLIDES))
        for key, config in slides:
            prepared = wr.scene(config, LOGO, None, None, 1)
            wr.compose(prepared, 2.0, True)
            self.assertEqual(wr.compose(prepared, 999, False).size, (540, 960))
        big = [l for l in wr.scene(dict(slides)['gol'], LOGO, None, None, 1)[1] if l.id == 'big'][0]
        self.assertEqual(big.anim, 'count')
        empty = wr.slides({}, 'STAGIONE', base)
        self.assertEqual([k for k, _ in empty], ['intro', 'outro'])

    def test_png(self):
        base = dict(defaults('Classifica'), theme='none')
        config = dict(wr.slides(ss.stats(GAMES), 'X', base))['partite']
        data = wr.png_bytes(config, LOGO, None, None, 'Post 4:5', 1, 1)
        self.assertEqual(Image.open(io.BytesIO(data)).size, (540, 675))


class SponsorTests(unittest.TestCase):
    def test_sticker_on_every_editor(self):
        sid = sponsor_logo()
        for template in ('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario'):
            config = dict(defaults(template), theme='none')
            plain = MODULES[template].scene(config, LOGO, None, None, 1)
            with_logo = MODULES[template].scene(dict(config, sponsor_on=True, sponsor_logo_id=sid, sponsor_name='BAR'), LOGO, None, None, 1)
            a, b = np.asarray(plain[0], int), np.asarray(with_logo[0], int)
            band = slice(675, 696)
            self.assertGreater(np.abs(a[band]-b[band]).sum(), 0, template)
            self.assertEqual(np.abs(a[:600]-b[:600]).sum(), 0, template)   # the graphic itself is untouched

    def test_off_or_missing_logo(self):
        config = dict(defaults('Convocati'), sponsor_on=True, sponsor_logo_id='logo:missing')
        self.assertFalse(sponsor.active(config))
        self.assertIsNone(sponsor.sticker(config))

    def test_slide_and_mockup(self):
        sid = sponsor_logo()
        config = dict(defaults('Classifica'), theme='none', sponsor_logo_id=sid, sponsor_name='PIZZERIA')
        prepared = sponsor.scene(config, None, None, None, 1)
        self.assertIn('logo', [l.id for l in prepared[1]])
        frame = sponsor.compose(prepared, 999, False)
        tv_plain = np.asarray(mockup.frame(frame, 'Post 1:1', 1, 0), int)
        tv = np.asarray(mockup.frame(frame, 'Post 1:1', 1, 0, sponsor.sticker(dict(config, sponsor_on=True), 1)), int)
        self.assertGreater(np.abs(tv-tv_plain).sum(), 0)

    def test_state(self):
        config = sanitize_config('Matchday Screen', dict(defaults('Matchday Screen'), sponsor_on=True, sponsor_name='x'*50))
        self.assertTrue(config['sponsor_on'])
        self.assertEqual(len(config['sponsor_name']), 24)
        week = sanitize_week(dict(sponsor=dict(on=True, logo_id='bad', name='BAR'),
                                  season=[dict(date='2026-10-02', opp='LIONS', home=True, us=2, them=1), dict(date='x', opp='Y')],
                                  scorers=[dict(name='teu', goals=4), dict(name='', goals=2)]))
        self.assertEqual(week['sponsor']['logo_id'], 'none')
        self.assertEqual(len(week['season']), 1)
        self.assertEqual(week['scorers'], [dict(name='TEU', goals=4)])


class InstagramTests(unittest.TestCase):
    def test_profile_pictures(self):
        for style in pp.STYLES:
            image = pp.profile_picture(LOGO, style, 540)
            self.assertEqual(image.size, (540, 540))
            arr = np.asarray(image, int)
            self.assertGreater(arr[200:340, 200:340].std(), 20)   # the crest is in the middle

    def test_covers(self):
        for name in pp.ICONS:
            rows = pp.ICONS[name][1]
            if rows:
                self.assertTrue(all(set(r) <= set('.')|set(pp.ICON_COLORS) for r in rows), name)
        cover = pp.highlight_cover('partite', 'neon', LOGO, True, (540, 960))
        self.assertEqual(cover.size, (540, 960))
        crest = pp.highlight_cover('stemma', 'rosa', LOGO, False, (540, 960))
        self.assertEqual(crest.size, (540, 960))
        self.assertEqual(pp.circle_preview(cover, 100).size, (100, 100))


if __name__ == '__main__':
    unittest.main()
