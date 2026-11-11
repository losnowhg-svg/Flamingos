"""3.19: intro della partita, the animated pixel intro that ends on the match poster."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intro

CREST = (ROOT/'assets'/'stemmi'/'caste_united.png').read_bytes()
MATCH = dict(our_name='FLAMINGOS', opponent='CASTE UNITED', our_side='Casa', date='12/11/2026', kickoff='21:00',
             venue='Via Fornaci, 82', round=7)


def texts(**changes):
    return intro.texts_for(dict(MATCH, **changes), 'CSI SERIE C / GIRONE D')


class Words(unittest.TestCase):
    def test_informative_words_from_the_match(self):
        t = texts()
        self.assertEqual(t['date'], 'GIOVEDI 12 NOVEMBRE')                 # no accents: the pixel font has none
        self.assertEqual((t['kickoff'], t['place'], t['home']), ('21:00', 'VIA FORNACI, 82', True))
        self.assertEqual(t['competition'], 'CSI SERIE C / GIRONE D / GIORNATA 7')
        self.assertEqual(texts(kickoff='HH:MM')['kickoff'], '')
        self.assertEqual(intro.date_line('GG/MM/AAAA'), 'GG/MM/AAAA')
        self.assertFalse(texts(our_side='Ospiti')['home'])


class Pictures(unittest.TestCase):
    def test_sizes_and_every_part_of_the_timeline(self):
        for fmt, size in (('Story 9:16', (540, 960)), ('Post 4:5', (540, 675))):
            show = intro.Intro(texts(), CREST, fmt, 1)
            for t in (.1, 1.0, 2.6, 3.3, 4.2, 5.0, intro.DROP, 6.8, 7.2, 8.0, 8.4, 11.4):
                self.assertEqual(show.frame(t).size, size, (fmt, t))
            self.assertEqual(Image.open(io.BytesIO(intro.poster_png(texts(), CREST, fmt, 2))).size, (size[0]*2, size[1]*2))

    def test_vs_lands_on_the_drop(self):
        show = intro.Intro(texts(), CREST, 'Story 9:16', 1)
        before = np.asarray(show.frame(intro.DROP-.3), np.int16)
        after = np.asarray(show.frame(intro.DROP+.2), np.int16)
        middle = (slice(400, 560), slice(180, 360))
        yellow = lambda a: ((a[..., 0] > 170) & (a[..., 1] > 140) & (a[..., 2] < 150)).sum()
        self.assertGreater(yellow(after[middle]), yellow(before[middle])+800)
        self.assertTrue(intro.T_FACE < intro.DROP < intro.T_BUILD < intro.T_CARD < intro.LENGTH)

    def test_colours_come_from_the_crest_and_the_home_team_is_on_the_left(self):
        home = intro.Intro(texts(), CREST, 'Story 9:16', 1)
        self.assertGreater(home.c1[0], home.c1[2]+80)                      # Caste United: red
        poster = np.asarray(home.poster(), np.int16)
        away = np.asarray(intro.Intro(texts(our_side='Ospiti'), CREST, 'Story 9:16', 1).poster(), np.int16)
        row = slice(300, 600)
        pink = lambda a: ((a[..., 0] > 180) & (a[..., 2] > 90) & (a[..., 1] < 90)).sum()
        self.assertGreater(pink(poster[row, :200]), pink(poster[row, 340:])*3)      # at home: pink on the left
        self.assertGreater(pink(away[row, 340:]), pink(away[row, :200])*3)          # away: pink on the right

    def test_without_a_crest_and_with_every_look(self):
        show = intro.Intro(texts(opponent='REAL BORGOSATOLLO'), None, 'Post 4:5', 1, look='bianco')
        self.assertEqual(show.frame(4.3).size, (540, 675))
        self.assertEqual(show.look, 'bianco')
        self.assertIn(intro.Intro(texts(), CREST, 'Story 9:16', 1).look, intro.LOOKS)   # auto picks one
        for look in intro.LOOKS:
            self.assertEqual(intro.Intro(texts(), CREST, 'Story 9:16', 1, look=look).frame(1.5).size, (540, 960))
        dark = (ROOT/'assets'/'stemmi'/'pirati.png').read_bytes()
        self.assertEqual(intro.Intro(texts(opponent='PIRATI'), dark, 'Story 9:16', 1).frame(4.0).size, (540, 960))

    def test_video_with_music_and_effects(self):
        show = intro.Intro(texts(), CREST, 'Story 9:16', 1)
        self.assertTrue(all(0 <= at < show.length for at, _ in show.events()))
        real = intro.LENGTH
        intro.LENGTH = 1.2                                                 # a short one is enough here
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'i.mp4'
                intro.render_video(texts(), CREST, path, 8, 'Post 4:5', .5, 'cc0_robots', True)
                self.assertGreater(path.stat().st_size, 20_000)
        finally:
            intro.LENGTH = real


if __name__ == '__main__':
    unittest.main()
