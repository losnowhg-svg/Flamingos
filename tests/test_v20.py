"""2.0: pixel avatars, department slides, staff roles, pasted CSI page, no Starting 7."""
import base64
import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import avatars
import reparti_renderer as rr
from csi_page import read_page
from studio_state import defaults, sanitize_squad, STAFF_ROLES
from tests.fixtures.csi_samples import STANDINGS, LINES, CARDS

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def portrait(face_center=(300, 330), size=(600, 1000)):
    """A synthetic selfie: grey wall, dark hair, skin-coloured face, shirt."""
    im = Image.new('RGB', size, (120, 124, 130))
    d = ImageDraw.Draw(im)
    x, y = face_center
    d.ellipse((x-120, y-170, x+120, y+60), fill=(50, 34, 26))           # hair
    d.ellipse((x-95, y-120, x+95, y+130), fill=(214, 160, 128))         # face
    for ex in (x-40, x+40):
        d.ellipse((ex-14, y-20, ex+14, y-4), fill=(30, 22, 20))          # eyes
    d.rectangle((x-35, y+70, x+35, y+80), fill=(140, 60, 60))           # mouth
    d.rectangle((x-200, y+190, x+200, size[1]), fill=(40, 60, 140))     # shirt
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=92)
    return out.getvalue()


class AvatarTests(unittest.TestCase):
    def test_face_is_found(self):
        photo = avatars.load_photo(portrait((300, 330)))
        cx, cy, zoom = avatars.guess_face(photo)
        self.assertAlmostEqual(cx, .5, delta=.08)
        self.assertAlmostEqual(cy*photo.height, 330, delta=120)
        self.assertGreaterEqual(zoom, 1)

    def test_avatar_shape_and_background(self):
        photo = avatars.load_photo(portrait())
        avatar = avatars.make_avatar(photo, *avatars.guess_face(photo))
        self.assertEqual(avatar.size, (avatars.SIZE, avatars.SIZE))
        alpha = np.asarray(avatar)[..., 3]
        self.assertEqual(alpha[0, 0], 0)                     # corner is background
        self.assertEqual(alpha[avatars.SIZE//2, avatars.SIZE//2], 255)
        colors = {tuple(p) for p in np.asarray(avatar)[alpha > 0][:, :3]}
        self.assertLessEqual(len(colors), 8+6)               # palette + shirt + outline
        pink = np.asarray(avatar)[-1, avatars.SIZE//2+5, :3]
        self.assertGreater(int(pink[0]), int(pink[2]))       # Flamingos shirt at the bottom

    def test_encode_decode(self):
        photo = avatars.load_photo(portrait())
        value = avatars.encode(avatars.make_avatar(photo))
        self.assertLess(len(value), avatars.MAX_AVATAR)
        self.assertEqual(avatars.decode(value).size, (avatars.SIZE, avatars.SIZE))
        self.assertIsNone(avatars.decode('not base64!'))
        jpg = base64.b64encode(portrait()).decode()
        self.assertIsNone(avatars.decode(jpg))               # only small PNGs are accepted

    def test_bad_photo(self):
        with self.assertRaises(ValueError):
            avatars.load_photo(b'hello')

    def test_screenshot_bars_trimmed(self):
        im = Image.new('RGB', (400, 900), (0, 0, 0))
        im.paste(Image.open(io.BytesIO(portrait(size=(400, 700)))), (0, 100))
        out = io.BytesIO(); im.save(out, 'PNG')
        self.assertLess(avatars.load_photo(out.getvalue()).height, 800)


class SquadTests(unittest.TestCase):
    def test_staff_roles_and_avatars(self):
        good = avatars.encode(avatars.placeholder())
        squad = sanitize_squad([dict(name='nick', role='ALL', avatar=good), dict(name='ds', role='DIR'),
                                dict(name='teu', number=9, role='A', avatar='junk')])
        self.assertEqual([p['role'] for p in squad], ['ALL', 'DIR', 'A'])
        self.assertIn('avatar', squad[0])
        self.assertNotIn('avatar', squad[2])
        self.assertEqual(set(STAFF_ROLES), {'ALL', 'DIR'})


def convocati(squad, captain='CAVA'):
    config = defaults('Convocati')
    config['theme'] = 'none'
    players = [p for p in squad if p['role'] not in STAFF_ROLES]
    for i, p in enumerate(players):
        config['roster'][i] = dict(number=p['number'], name=p['name'], role=p.get('roster_role', p['role']),
                                   captain=p['name'] == captain)
    config['roster_count'] = max(7, len(players))
    config['opponent'] = 'LIONS'
    config['date'] = '30/10/2026'
    return config


SQUAD = [dict(number=0, name='NICK', role='ALL', avatar=avatars.encode(avatars.placeholder())),
         dict(number=1, name='BRAMBO', role='P'), dict(number=12, name='OLI', role='P'),
         dict(number=6, name='GIANLU', role='D'),
         *[dict(number=n, name=x, role='C') for n, x in ((4, 'BOBBI'), (14, 'DEMA'), (0, 'KEVIN'), (3, 'LUCA'),
                                                         (10, 'CAVA'), (11, 'SCATTO'), (8, 'ELVIN'), (15, 'STRINGA'))],
         dict(number=9, name='TEU', role='A')]


class DepartmentTests(unittest.TestCase):
    def test_groups(self):
        slides = rr.slides(convocati(SQUAD), SQUAD)
        self.assertEqual([g for g, _ in slides], ['P', 'D', 'C', 'A', 'STAFF'])
        mids = dict(slides)['C']['members']
        self.assertEqual(len(mids), 8)
        self.assertTrue(next(m for m in mids if m['name'] == 'CAVA')['captain'])
        staff = dict(slides)['STAFF']
        self.assertEqual(staff['members'][0]['name'], 'NICK')
        self.assertTrue(staff['members'][0]['avatar'])
        self.assertIn('LIONS', dict(slides)['P']['slide_subtitle'])

    def test_role_from_squad_and_unassigned(self):
        squad = [dict(SQUAD[1]), dict(number=7, name='NUOVO', role='-')]
        config = convocati([dict(squad[0], roster_role='-'), squad[1]])
        self.assertEqual([g for g, _ in rr.slides(config, squad)], ['P'])
        self.assertEqual(rr.unassigned(config, squad), ['NUOVO'])

    def test_cards_fit_the_screen(self):
        for count in range(1, rr.MAX_CARDS+1):
            boxes, w, h = rr.card_boxes(count)
            for x, y in boxes:
                self.assertGreaterEqual(x-w/2, rr.BODY[0]-.5)
                self.assertLessEqual(x+w/2, rr.BODY[2]+.5)
                self.assertGreaterEqual(y-h/2, rr.BODY[1]-.5)
                self.assertLessEqual(y+h/2, rr.BODY[3]+.5)

    def test_render_and_animate(self):
        for group, slide in rr.slides(convocati(SQUAD), SQUAD):
            prepared = rr.scene(slide, LOGO, None, None, 1)
            cards = [l for l in prepared[1] if l.id.startswith('card_')]
            self.assertEqual(len(cards), len(slide['members']))
            self.assertTrue(all(l.anim == 'glitch' for l in cards))
            still = rr.compose(prepared, 999, False)
            self.assertEqual(still.size, (540, 960))
            rr.compose(prepared, 2.0, True)
        data = rr.png_bytes(dict(rr.slides(convocati(SQUAD), SQUAD))['P'], LOGO, None, None, 'Post 4:5', 1, 1)
        self.assertEqual(Image.open(io.BytesIO(data)).size, (540, 675))


class CsiPasteTests(unittest.TestCase):
    def test_pasted_page_reads_like_the_bookmark(self):
        import datetime as dt
        page = read_page({'u': '', 't': '', 'x': STANDINGS+'\n'+LINES+'\n'+CARDS}, 'FLAMINGOS', dt.date(2026, 10, 23))
        self.assertTrue(page['standings'])
        self.assertTrue(page['fields'])


class PagesTests(unittest.TestCase):
    def test_no_starting7_page_or_server_import(self):
        app = (ROOT/'app.py').read_text()
        self.assertNotIn("'Starting 7':", app)
        ui = (ROOT/'studio_ui.py').read_text()
        self.assertNotIn('Dal server', ui)
        self.assertNotIn('fetch_standings', ui)
        week = (ROOT/'week_ui.py').read_text()
        self.assertIn('Incolla la pagina', week)


if __name__ == '__main__':
    unittest.main()


import pixel_character as pc


class CharacterTests(unittest.TestCase):
    def test_sanitize(self):
        look = pc.sanitize(dict(hair='ricci', beard='xx', skin='#123456', hair_color='red'))
        self.assertEqual((look['hair'], look['beard'], look['skin']), ('ricci', 'nessuna', '#123456'))
        self.assertEqual(look['hair_color'], pc.DEFAULT_LOOK['hair_color'])
        self.assertIsNone(pc.sanitize('nope'))

    def test_every_combination_draws(self):
        for hair in pc.HAIR_STYLES:
            for beard in pc.BEARDS:
                for glasses in pc.GLASSES:
                    img = pc.image(dict(hair=hair, beard=beard, glasses=glasses), 'arcade')
                    self.assertEqual(img.size, (pc.SIZE, pc.SIZE))
        a = np.asarray(pc.image(dict(beard='nessuna')))
        b = np.asarray(pc.image(dict(beard='piena')))
        self.assertGreater(np.abs(a.astype(int)-b.astype(int)).sum(), 0)

    def test_gameboy_has_four_greens(self):
        arr = np.asarray(pc.image(dict(hair='ciuffo', beard='corta', glasses='sole'), 'gameboy'))
        colours = {tuple(p) for p in arr[arr[..., 3] > 0][:, :3]}
        self.assertTrue(colours <= {tuple(c) for c in pc.GAMEBOY})
        self.assertGreaterEqual(len(colours), 3)

    def test_colours_from_photo(self):
        colours = pc.colors_from_photo(avatars.load_photo(portrait()))
        self.assertEqual(set(colours), {'skin', 'hair_color', 'beard_color'})
        skin = np.array(list(bytes.fromhex(colours['skin'][1:])))
        hair = np.array(list(bytes.fromhex(colours['hair_color'][1:])))
        self.assertGreater(skin.sum(), hair.sum()+150)

    def test_squad_and_slides_use_the_look(self):
        look = dict(hair='ciuffo', beard='corta')
        squad = sanitize_squad([dict(name='teu', number=9, role='A', look=look), dict(name='nick', role='ALL', look=look)])
        self.assertEqual(squad[0]['look']['hair'], 'ciuffo')
        config = convocati(squad)
        slides = dict(rr.slides(config, squad))
        self.assertEqual(slides['A']['members'][0]['look']['hair'], 'ciuffo')
        self.assertTrue(slides['STAFF']['members'][0]['look'])
        green = np.asarray(pc.picture(slides['A']['members'][0], 'gameboy'))
        self.assertTrue({tuple(p) for p in green[green[..., 3] > 0][:, :3]} <= {tuple(c) for c in pc.GAMEBOY})
        rr.png_bytes(slides['A'], LOGO, None, None, 'Post 1:1', 1, 1)


class OurColourTests(unittest.TestCase):
    def test_flamingos_pink_away_too(self):
        from studio_state import MODULES
        from renderer import rgb
        for template in ('Matchday Screen', 'Full Time'):
            for side, ours_id in (('Casa', 'home_name'), ('Ospiti', 'away_name')):
                config = defaults(template)
                config.update(theme='none', our_side=side)
                if side == 'Ospiti':
                    config.update(home_name='LIONS', away_name='FLAMINGOS')
                layers = {l.id: l for l in MODULES[template].scene(config, LOGO, None, None, 1)[1]}
                pink = np.array(rgb(config['pink']))
                arr = np.asarray(layers[ours_id].image).astype(int)
                opaque = arr[arr[..., 3] > 200][:, :3]
                closest = np.abs(opaque-pink).sum(axis=1).min()
                self.assertLess(closest, 30, (template, side))
