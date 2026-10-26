"""2.5: the squad's own sprites, new editor traits, idle animations, pixel team photo."""
import io
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animations
import pixel_character as pc
import reparti_renderer as rr
import team_photo as tp
from studio_state import sanitize_squad
from team_looks import OFFICIAL_SQUAD

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


class OfficialSquad(unittest.TestCase):
    def test_everyone_has_a_valid_ready_sprite(self):
        names = [p['name'] for p in OFFICIAL_SQUAD]
        self.assertEqual(len(names), len(set(names)))
        for person in OFFICIAL_SQUAD:
            self.assertEqual(pc.sanitize(person['look']), person['look'], person['name'])
        for name in ('NICK', 'MANU', 'CHOPPA', 'BANA', 'TEU', 'ELVIN', 'TABE', 'KEVIN'):
            self.assertIn(name, names)

    def test_new_directors_and_coach(self):
        roles = {p['name']: p['role'] for p in OFFICIAL_SQUAD}
        self.assertEqual(roles['NICK'], 'ALL')
        for name in ('MANU', 'CHOPPA', 'BANA'):
            self.assertEqual(roles[name], 'DIR')

    def test_traits_from_the_brief(self):
        looks = {p['name']: p['look'] for p in OFFICIAL_SQUAD}
        self.assertIn(looks['TABE']['hair'], ('ricci', 'ricci_lunghi'))
        self.assertEqual(looks['ELVIN']['face'], 'magro')

    def test_survives_squad_sanitizing(self):
        clean = sanitize_squad([dict(p) for p in OFFICIAL_SQUAD])
        self.assertEqual(len(clean), len(OFFICIAL_SQUAD))
        self.assertTrue(all(p.get('look') for p in clean))


class Sprites(unittest.TestCase):
    def test_every_new_trait_renders(self):
        base = dict(pc.DEFAULT_LOOK)
        for key, options in (('hair', pc.HAIR_STYLES), ('face', pc.FACES), ('eyes', pc.EYES),
                             ('accessory', pc.ACCESSORIES), ('expression', pc.EXPRESSIONS)):
            for option in options:
                img = pc.image(dict(base, **{key: option}))
                self.assertEqual(img.size, (pc.SIZE, pc.SIZE))

    def test_idle_frames_change_the_face(self):
        look = dict(pc.DEFAULT_LOOK, glasses='spessi')
        frames = pc.frames_for(look)
        self.assertIn('glint', frames)
        rest = pc.image(look).tobytes()
        for frame in frames:
            self.assertNotEqual(pc.image(look, frame=frame).tobytes(), rest, frame)

    def test_sunglasses_do_not_blink(self):
        self.assertNotIn('blink', pc.frames_for(dict(pc.DEFAULT_LOOK, glasses='sole')))

    def test_idle_gif_is_animated(self):
        gif = Image.open(io.BytesIO(pc.idle_gif(OFFICIAL_SQUAD[0]['look'], 'arcade', 128)))
        self.assertGreater(gif.n_frames, 6)
        self.assertEqual(gif.size, (128, 128))


class CardAnimations(unittest.TestCase):
    def setUp(self):
        members = [dict(p, captain=False) for p in OFFICIAL_SQUAD if p['role'] == 'P']
        self.config = dict(members=members, group='P', slide_title='PORTIERI')
        self.layers = rr.get_layers(self.config, LOGO, None, None, 1)
        self.card = next(l for l in self.layers if l.id == 'card_0')

    def test_cards_carry_their_special_frames(self):
        self.assertIn('bob', self.card.alive)
        expected = set(pc.frames_for(self.config['members'][0]['look']))
        self.assertTrue(expected <= set(self.card.alive))

    def test_special_move_shows_up_in_the_loop(self):
        self.card.sequence = 0
        seen = {id(animations._idle_card(self.card, i/24, 0)) for i in range(24*12)}
        specials = {id(self.card.alive[k]) for k in ('wink', 'smile', 'brows', 'glint') if k in self.card.alive}
        self.assertTrue(seen & specials)

    def test_hop_after_landing(self):
        self.card.dur = .4
        self.assertLess(animations._card_hop(self.card, .4+animations.HOP/2, 1.0), -5)
        self.assertEqual(animations._card_hop(self.card, .4+animations.HOP+.2, 1.0), 0)

    def test_scene_renders_frames(self):
        prepared = rr.scene(self.config, LOGO, None, None, 1)
        for t in (0.5, 2.0, 4.0, 7.0):
            self.assertEqual(rr.compose(prepared, t, True).size[0], 540)


class TeamPhoto(unittest.TestCase):
    def test_groups_in_department_order(self):
        labels = [label for label, _ in tp.groups(OFFICIAL_SQUAD)]
        self.assertEqual(labels, ['PORTIERI', 'DIFENSORI', 'CENTROCAMPISTI', 'ATTACCANTI', 'STAFF'])
        staff = dict(tp.groups(OFFICIAL_SQUAD))['STAFF']
        self.assertEqual(staff[0]['name'], 'NICK')

    def test_pack_keeps_small_sections_together(self):
        rows = tp._pack([('A', [1, 2]), ('B', [3, 4]), ('C', list(range(8)))], 6)
        self.assertEqual(len(rows[0]), 4)
        self.assertEqual(sum(len(r) for r in rows), 12)
        self.assertTrue(all(len(r) <= 6 for r in rows))

    def test_every_size_and_style(self):
        for size, wh in tp.SIZES.items():
            for preset in ('crt', 'gameboy'):
                img = tp.team_photo(OFFICIAL_SQUAD, preset, LOGO, size=size)
                self.assertEqual(img.size, wh)

    def test_empty_squad(self):
        self.assertEqual(tp.team_photo([], 'crt').size, tp.SIZES['Post 4:5'])

    def test_season_label(self):
        import datetime as dt
        self.assertEqual(tp.season_label(dt.date(2026, 10, 25)), '2026/27')
        self.assertEqual(tp.season_label(dt.date(2027, 3, 1)), '2026/27')


def _audio_rms(path):
    import subprocess
    import imageio_ffmpeg
    import numpy as np
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(path), '-f', 's16le', '-ac', '1',
                          '-ar', '8000', '-'], capture_output=True).stdout
    samples = np.frombuffer(raw, np.int16).astype(float)
    return float(np.sqrt(np.mean(samples**2))) if len(samples) else 0.0


class MusicWithoutEffects(unittest.TestCase):
    """2.5.1: the chiptune plays even when Suoni CRT is off (department video, sequences)."""

    def _scenes(self, music):
        members = [dict(p, captain=False) for p in OFFICIAL_SQUAD if p['role'] == 'P']
        out = []
        for group in ('P', 'D'):
            prepared = rr.scene(dict(members=members, group=group, slide_title=group, music=music, theme='none'),
                                LOGO, None, None, 1)
            out.append((prepared, rr.compose))
        return out

    def test_music_only_sequence_has_audio(self):
        import tempfile
        from transitions import render_sequence
        with tempfile.TemporaryDirectory() as folder:
            loud = Path(folder)/'music.mp4'
            render_sequence(self._scenes(True), ['channel'], loud, 12, 1.5, .5, 'Story 9:16', 1, sound=False)
            mute = Path(folder)/'mute.mp4'
            render_sequence(self._scenes(False), ['channel'], mute, 12, 1.5, .5, 'Story 9:16', 1, sound=False)
            self.assertGreater(_audio_rms(loud), 500)
            self.assertEqual(_audio_rms(mute), 0.0)

    def test_music_only_events(self):
        import sounds
        prepared, compose = self._scenes(True)[0]
        self.assertEqual(len(sounds.scene_events(prepared, compose, until=4, effects=False)), 1)
        prepared, compose = self._scenes(False)[0]
        self.assertEqual(sounds.scene_events(prepared, compose, until=4, effects=False), [])


if __name__ == '__main__':
    unittest.main()
