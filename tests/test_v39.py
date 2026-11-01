"""3.9: figurine (holographic cards, the pack-opening video), pagelle and the season album."""
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import album
import card_video
import cards
import figurine_data as fd
import pagelle
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
SQUAD = {p['name']: p for p in OFFICIAL_SQUAD}
TEU = dict(SQUAD['TEU'], edition='mvp', vote=8.5, stats=[('GOL', '2'), ('RISULTATO', '3-1'), ('GIORNATA', '7')],
           serial=(9, 15))


class Type(unittest.TestCase):
    def test_bundled_font_and_licence(self):
        for name in ('InterDisplay-BlackItalic.otf', 'InterDisplay-Bold.otf', 'InterDisplay-ExtraBold.otf'):
            self.assertLess((ROOT/'assets'/'fonts'/name).stat().st_size, 120_000)
        self.assertIn('Open Font License', (ROOT/'assets'/'fonts'/'OFL.txt').read_text().replace('OPEN FONT LICENSE', 'Open Font License'))
        self.assertIn('Inter Display', ' '.join(cards.font('black', 30).getname()))

    def test_vote_text(self):
        self.assertEqual(cards.vote_text(8.5), '8½')
        self.assertEqual(cards.vote_text(7), '7')
        self.assertEqual(cards.vote_text(None), '')


class Card(unittest.TestCase):
    def test_spec_defaults(self):
        spec = cards.spec_for(dict(name='brambo', role='P', edition='bomber'))
        self.assertEqual((spec['name'], spec['rarity'], spec['pose']), ('BRAMBO', 'leggenda', 'guanti'))  # keepers keep gloves
        self.assertEqual(cards.spec_for({'edition': 'nope'})['edition'], 'base')
        self.assertEqual(cards.spec_for(dict(edition='mvp', rarity='rara'))['rarity'], 'rara')

    def test_render_size_corners_and_foil(self):
        card = cards.Card(TEU, 1.0, LOGO)
        img = card.render(0, 0)
        self.assertEqual(img.size, (cards.W, cards.H))
        self.assertEqual(img.getpixel((0, 0))[3], 0)                       # rounded corners
        self.assertEqual(img.getpixel((cards.W//2, cards.H//2))[3], 255)
        a = np.asarray(card.render(-25, 0), np.int16)
        b = np.asarray(card.render(25, 0), np.int16)
        self.assertGreater(np.abs(a-b)[..., :3].mean(), 4)                 # the foil and the light move with the tilt

    def test_count_up_and_blink_change_the_ink(self):
        card = cards.Card(TEU, .8, LOGO)
        plain = card.ink_for()
        low = card.ink_for(vote=5.0, stats=(('GOL', '0'), ('RISULTATO', '3-1'), ('GIORNATA', '7')))
        self.assertGreater(np.abs(plain-low).mean(), .001)
        self.assertGreater(np.abs(plain-card.ink_for('blink')).sum(), 0)

    def test_back_pack_and_transparent_png(self):
        back = cards.back(1.0, LOGO)
        self.assertEqual(back.size, (cards.W, cards.H))
        pack, tear = cards.pack(1.0, LOGO)
        self.assertGreater(pack.height, cards.H)
        self.assertTrue(0 < tear < pack.height//4)
        png = Image.open(io.BytesIO(cards.card_png(TEU, LOGO, 700)))
        self.assertEqual(png.mode, 'RGBA')
        self.assertEqual(png.height, 700)

    def test_turned_past_ninety_degrees_shows_the_back(self):
        front = Image.new('RGBA', (100, 140), (255, 0, 0, 255))
        back = Image.new('RGBA', (100, 140), (0, 0, 255, 255))
        img, _, _ = cards.warp(front, (200, 200), 160, 0, back_img=back)
        r, g, b, a = img.getpixel((img.width//2, img.height//2))
        self.assertGreater(b, r)
        img, _, _ = cards.warp(front, (200, 200), 20, 0, back_img=back)
        r, g, b, a = img.getpixel((img.width//2, img.height//2))
        self.assertGreater(r, b)


class Video(unittest.TestCase):
    def test_hints_fall_on_the_beat_of_the_track(self):
        show = card_video.Show(TEU, LOGO, 'Post 1:1', .5, 'cc0_robots')
        beat = 60/90.0
        for at in show.hints:
            steps = (card_video.DROP-at)/beat
            self.assertAlmostEqual(steps, round(steps), places=6)
        self.assertTrue(.5 < show.hints[0] < show.hints[1] < show.hints[2] < card_video.DROP)

    def test_card_flips_to_its_front_and_frames_are_even(self):
        show = card_video.Show(TEU, LOGO, 'Story 9:16', .5, None, 'prova')
        self.assertGreater(show.card_pose(card_video.DROP+.05)[2], 120)    # still showing the back
        self.assertLess(abs(show.card_pose(card_video.DROP+1.2)[2]), 25)   # front, breathing
        frame = show.frame_array(card_video.DROP+2)
        self.assertEqual(frame.shape, (480, 270, 3))
        before = show.frame_array(2.5).astype(np.int16)
        self.assertGreater(np.abs(frame.astype(np.int16)-before).mean(), 5)

    def test_poster_in_every_format(self):
        for fmt, h in (('Story 9:16', 960), ('Post 4:5', 675), ('Post 1:1', 540)):
            img = card_video.poster(TEU, LOGO, fmt, .5, 'FLAMINGOS 3-1 UNITED FLERO')
            self.assertEqual(img.size, (270, h//2))

    def test_video_with_music_and_effects(self):
        import tracks
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'f.mp4'
            card_video.render_video(TEU, LOGO, path, 8, 'Post 1:1', .5, 'cc0_battle', 'prova', True, .8, 5.0)
            self.assertGreater(path.stat().st_size, 20_000)
            audio = tracks.decode(path)
            sr = tracks.SR
            drop = np.abs(audio[int(3.95*sr):int(4.3*sr)]).max()
            calm = np.abs(audio[int(2.0*sr):int(2.3*sr)]).max()
            self.assertGreater(drop, calm)                                  # the reveal hits on the drop


class Pagelle(unittest.TestCase):
    ROWS = [dict(SQUAD['TEU'], vote=8.5, goals=2, note='Doppietta'), dict(SQUAD['BRAMBO'], vote=6.5),
            dict(SQUAD['CAVA'], vote=8.5, goals=1), dict(SQUAD['KEVIN'], vote=5.5), dict(SQUAD['COCCO'], vote=None)]

    def test_order_best_and_colours(self):
        names = [r['name'] for r in pagelle.order(self.ROWS)]
        self.assertEqual(names[0], 'BRAMBO')                                # goalkeeper first
        self.assertEqual(pagelle.best(self.ROWS), 'TEU')                    # same vote, more goals
        self.assertEqual(pagelle.vote_color(8), cards.CYAN)
        self.assertEqual(pagelle.vote_color(5.5), cards.PINK)

    def test_mvp_waits_for_the_drop(self):
        show = pagelle.Pagelle(self.ROWS, {'line': 'FLAMINGOS 3-1 UNITED FLERO'}, LOGO, 'Story 9:16', .5)
        self.assertEqual(len(show.rows), 4)                                 # no vote, no row
        mvp = next(i for i, r in enumerate(show.rows) if r['name'] == 'TEU')
        self.assertEqual(show.times[mvp], card_video.DROP)
        self.assertTrue(all(at < card_video.DROP for i, at in show.times.items() if i != mvp))
        self.assertEqual(show.still_frame().size, (270, 480))
        self.assertTrue(any(at == card_video.DROP for at, _ in show.events()))

    def test_png(self):
        png = Image.open(io.BytesIO(pagelle.png_bytes(self.ROWS, {'line': 'A 1-0 B'}, LOGO, 'Post 4:5', .5)))
        self.assertEqual(png.size, (270, 337))


class Album(unittest.TestCase):
    def test_rarity_grows_with_mvps(self):
        self.assertEqual([album.rarity_for(n) for n in (0, 1, 2, 3, 7)], ['base', 'rara', 'epica', 'leggenda', 'leggenda'])
        mvps = [dict(name='TEU')]*3+[dict(name='CAVA')]
        members = album.members_for(OFFICIAL_SQUAD, mvps, [dict(name='TEU', goals=9)])
        by = {m['name']: m for m in members}
        self.assertEqual((by['TEU']['rarity'], by['CAVA']['rarity'], by['BRAMBO']['rarity']), ('leggenda', 'rara', 'base'))
        self.assertIn(('GOL', '9'), by['TEU']['stats'])
        self.assertEqual(members[0]['role'], 'P')
        self.assertEqual(members[-1]['serial'], (len(members), len(members)))
        self.assertNotIn('MANU', by)                                        # managers stay out, the coach is in
        self.assertIn('NICK', by)

    def test_grid_fits_and_files(self):
        for n in (4, 9, 15, 20):
            cols, w = album.grid(n, 500, 640)
            rows = -(-n//cols)
            self.assertLessEqual(rows*w*cards.H/cards.W+(rows-1)*10, 640+1e-6)
            self.assertLessEqual(cols*w+(cols-1)*10, 500+1e-6)
        members = album.members_for(OFFICIAL_SQUAD)[:3]
        img = album.poster(members, LOGO, 'Post 4:5', .5)
        self.assertEqual(img.size, (270, 337))
        with zipfile.ZipFile(io.BytesIO(album.zip_bytes(members, LOGO, 300))) as z:
            self.assertEqual(len(z.namelist()), 3)
            self.assertTrue(z.namelist()[0].startswith('01_'))


class Data(unittest.TestCase):
    FT = dict(home_name='UNITED FLERO', away_name='FLAMINGOS', home_score=1, away_score=3, our_side='Ospiti',
              home_scorers='ROSSI', away_scorers="TEU 12', 41'\nCAVA", date='26/10/2026')

    def test_votes(self):
        self.assertEqual([fd.parse_vote(v) for v in ('6½', '6.5', '6,5', 7, '', 'SV', None, '12', 'x')],
                         [6.5, 6.5, 6.5, 7.0, None, None, None, 10.0, None])
        self.assertEqual(fd.VOTE_OPTIONS[1], '4')
        self.assertIn('8½', fd.VOTE_OPTIONS)

    def test_match_numbers_from_our_side(self):
        self.assertEqual(fd.goals_by_player(self.FT), {'TEU': 2, 'CAVA': 1})
        self.assertEqual(fd.score_line(self.FT), 'UNITED FLERO 1-3 FLAMINGOS')
        self.assertEqual(fd.score_for_us(self.FT), '3-1')
        self.assertEqual((fd.opponent(self.FT), fd.conceded(self.FT)), ('UNITED FLERO', 1))
        self.assertEqual(fd.season_label('26/10/2026'), '2026/27')
        self.assertEqual(fd.season_label('15/03/2027'), '2026/27')

    def test_played_from_convocati_or_squad(self):
        convocati = dict(roster=[dict(name='Teu', number=9, role='-'), dict(name='GIOCATORE 02', number=2, role='-')],
                         roster_count=2)
        people = fd.played(convocati, OFFICIAL_SQUAD)
        self.assertEqual([(p['name'], p['role']) for p in people], [('TEU', 'A')])
        self.assertTrue(people[0]['look'])
        fallback = fd.played(dict(roster=[], roster_count=0), OFFICIAL_SQUAD)
        self.assertTrue(all(p['role'] in ('P', 'D', 'C', 'A') for p in fallback))

    def test_stats_and_captions_by_edition(self):
        ctx = dict(fulltime=self.FT, round=7, scorers=[dict(name='TEU', goals=9)], games=[1]*6, mvps=[dict(name='TEU')])
        teu = SQUAD['TEU']
        self.assertEqual(fd.stats_for('mvp', teu, ctx), [('GOL', '2'), ('RISULTATO', '3-1'), ('GIORNATA', '7')])
        self.assertEqual(fd.stats_for('bomber', teu, ctx), [('GOL', '9'), ('PARTITE', '6'), ('MEDIA', '1,5')])
        self.assertEqual(fd.stats_for('base', teu, ctx)[0], ('MVP', '1'))
        self.assertEqual(fd.caption_for('mvp', teu, ctx), 'UNITED FLERO 1-3 FLAMINGOS · GIORNATA 7')
        for edition in cards.EDITIONS:
            self.assertEqual(len(fd.stats_for(edition, teu, ctx)), 3)
            self.assertIsInstance(fd.caption_for(edition, teu, ctx), str)

    def test_captions(self):
        rows = [dict(SQUAD['TEU'], vote=8.5, goals=2, ig='teu9'), dict(SQUAD['CAVA'], vote=7.5, goals=1)]
        text = fd.pagelle_caption(rows, 'TEU', self.FT)
        self.assertIn('MVP: Teu 8½ (@teu9)', text)
        self.assertIn('Gol: Teu x2, Cava', text)
        self.assertIn('#Pagelle', text)
        ctx = dict(fulltime=self.FT, scorers=[dict(name='TEU', goals=9)], games=[1]*6, season='2026/27')
        for edition in cards.EDITIONS:
            self.assertIn('#Figurine', fd.card_caption(edition, SQUAD['TEU'], ctx, 8.5, 'epica'))
        self.assertIn('MVP contro United Flero con voto 8½ (3-1)', fd.card_caption('mvp', SQUAD['TEU'], ctx, 8.5))

    def test_squads_without_roles_and_award_dates(self):
        squad = [dict(name='ANNA', number=3, role='-'), dict(name='MISTER', number=0, role='ALL')]
        self.assertEqual([p['name'] for p in fd.played({}, squad)], ['ANNA'])
        self.assertEqual([m['name'] for m in album.members_for(squad)], ['ANNA', 'MISTER'])
        import datetime as dt
        self.assertEqual(fd.award_date('GG/MM/AAAA', '26/10/2026'), '26/10/2026')
        self.assertEqual(fd.award_date('GG/MM/AAAA', None, today=dt.date(2026, 11, 1)), '01/11/2026')
        self.assertEqual(cards.printable('TEU ⚽🔥 8½'), 'TEU  8½')

    def test_collection_dedupes_and_is_saved_with_the_week(self):
        mvps = fd.add_mvp([], dict(name='teu', date='26/10/2026', vote='8½', opp='UNITED FLERO', score='3-1', round=7))
        mvps = fd.add_mvp(mvps, dict(name='TEU', date='26/10/2026', vote=9))
        self.assertEqual(len(mvps), 1)
        self.assertEqual(mvps[0]['vote'], 9.0)
        self.assertEqual(fd.add_mvp(mvps, {'name': ''}), mvps)
        from studio_state import sanitize_week
        week = sanitize_week({'match': {}, 'mvps': mvps+['junk', {'name': 'CAVA', 'vote': 'x'}]})
        self.assertEqual([m['name'] for m in week['mvps']], ['TEU', 'CAVA'])


if __name__ == '__main__':
    unittest.main()
