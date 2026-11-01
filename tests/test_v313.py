"""3.13: the words and panels around the figurines follow the preset (the cards stay the same)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import album
import card_video
import cards
import figurine_style as fs
import pagelle
from preset_look import Look
from studio_state import defaults
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
FT = dict(defaults('Full Time'), theme='none')
GAMEBOY = fs.build(fs.key_for('gameboy', FT), 'Story 9:16', 540)
ROWS = [dict(p, vote=v, goals=g) for p, v, g in zip(OFFICIAL_SQUAD[:5], (6.5, 7, 8.5, 6, 5.5), (0, 1, 2, 0, 0))]


class LookTests(unittest.TestCase):
    def test_synthwave_and_preset(self):
        night, preset = Look(None, 1), Look(GAMEBOY, 1)
        self.assertFalse(night.preset)
        self.assertEqual(preset.font, 'CRT Scoreboard')
        self.assertEqual(preset.panel, tuple(GAMEBOY['panel']))
        self.assertEqual(night.pink, cards.PINK)
        self.assertIsNotNone(preset.text('8½ ★ MVP', 'black', 20, preset.white))   # glyphs the pixel font lacks
        self.assertIsNone(preset.text('', 'black', 20, preset.white))
        half = Look(GAMEBOY, .5).text('LE PAGELLE', 'black', 40, (255, 255, 255))
        full = Look(GAMEBOY, 1).text('LE PAGELLE', 'black', 40, (255, 255, 255))
        self.assertAlmostEqual(half.width*2, full.width, delta=2)

    def test_light_panel_keeps_a_light_box(self):
        lcd = Look(fs.build(fs.key_for('lcd', FT), 'Story 9:16', 540), 1)
        self.assertGreater(sum(lcd.box_fill()[:3]), 400)


class Screens(unittest.TestCase):
    def test_pagelle_mvp_row_takes_the_preset_yellow(self):
        show = pagelle.Pagelle(ROWS, {'line': 'A 1-0 B'}, LOGO, 'Story 9:16', 1, still=True, style=GAMEBOY)
        i = next(k for k, r in enumerate(show.rows) if r['name'] == show.mvp)
        pixels = np.asarray(show.panels[i])
        typical = np.median(pixels[pixels[..., 3] > 240][:, :3], axis=0)
        self.assertLess(np.abs(typical-np.array(GAMEBOY['palette'][2])).max(), 40)
        night = pagelle.Pagelle(ROWS, {'line': 'A 1-0 B'}, LOGO, 'Story 9:16', 1, still=True)
        self.assertFalse(night.look.preset)
        self.assertEqual(pagelle.vote_color(8), cards.CYAN)

    def test_pack_show_and_album_on_a_preset(self):
        show = card_video.Show(dict(OFFICIAL_SQUAD[2], edition='mvp', vote=8), LOGO, 'Post 4:5', 1, None, 'prova',
                               style=GAMEBOY)
        self.assertTrue(show.look.preset)
        self.assertEqual(show.frame(card_video.DROP+1.6).size, (540, 675))
        page = album.poster(album.members_for(OFFICIAL_SQUAD)[:4], LOGO, 'Post 1:1', 1, style=GAMEBOY)
        self.assertEqual(page.size, (540, 540))


if __name__ == '__main__':
    unittest.main()
