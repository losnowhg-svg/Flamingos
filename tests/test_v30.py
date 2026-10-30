"""3.0 "varietà pro": 8 new presets, atmospheres, details, panel styles, title effects,
frames and textures, entrance families, camera moves, continuous effects, new endings,
the logo intro and the Reel mode."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animations
import atmospheres
import crt_common
import frames
import intros
import motion
import preset_worlds2 as pw2
import title_fx
from crt_presets import BUILDERS, PANEL_STYLES, PRESETS, PRESET_IDS, STYLE, apply_preset, background
from renderer import text_image
from studio_state import CRT_DEFAULT, MODULES, defaults, sanitize_config

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
TEMPLATES = ('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario')


def scene(template='Matchday Screen', s=1, **extra):
    config = dict(apply_preset(defaults(template), extra.pop('preset', 'crt'), typography=True), theme='none')
    config.update(extra)
    return MODULES[template].scene(config, LOGO, None, None, s), config


def arr(image):
    return np.asarray(image.convert('RGB'), np.int16)


class NewPresets(unittest.TestCase):
    def test_registered_after_the_2_7_worlds(self):
        new = tuple(pw2.PRESETS)
        self.assertEqual(len(new), 8)
        self.assertEqual(PRESET_IDS[23:], new)
        for i, preset in enumerate(new):
            self.assertTrue(PRESETS[preset]['name'].startswith(f'{24+i} /'), preset)
            self.assertIn(preset, BUILDERS)
            self.assertIn(preset, STYLE)
            for key in ('pink', 'cyan', 'yellow', 'white'):
                self.assertRegex(PRESETS[preset][key], r'^#[0-9A-F]{6}$')

    def test_every_template_renders_on_every_new_preset(self):
        for preset in pw2.PRESETS:
            for template in TEMPLATES:
                with self.subTest(preset=preset, template=template):
                    prepared, _ = scene(template, preset=preset)
                    image = MODULES[template].compose(prepared, 999, False)
                    self.assertEqual(image.size, (540, 960))


class Atmospheres(unittest.TestCase):
    def test_the_screen_never_changes_the_world_does(self):
        base = arr(background(dict(apply_preset(defaults('Convocati'), 'tavolo'), theme='none'), 'convocati', 1))
        for mode in ('giorno', 'tramonto', 'notte', 'neon'):
            with self.subTest(mode):
                other = arr(background(dict(apply_preset(defaults('Convocati'), 'tavolo'), theme='none', atmosphere=mode),
                                       'convocati', 1))
                self.assertEqual(np.abs(other[316:674, 78:462]-base[316:674, 78:462]).max(), 0)
                self.assertGreater(np.abs(other-base).mean(), 6)

    def test_rotation_by_round(self):
        seen = {atmospheres.resolve_atmosphere({'atmosphere': 'rotazione', 'season_round': n}) for n in range(1, 6)}
        self.assertEqual(seen, {'standard', 'giorno', 'tramonto', 'notte', 'neon'})
        self.assertEqual(atmospheres.resolve_atmosphere({'atmosphere': 'boh'}), 'standard')

    def test_details_stay_off_the_screen_and_change_with_the_round(self):
        config = dict(apply_preset(defaults('Matchday Screen'), 'crt'), theme='none')
        plain = arr(background(config, 'matchday', 1))
        x1, y1, x2, y2 = atmospheres.KEEP_OUT
        for mode in ('stelle', 'coriandoli', 'griglia', 'adesivi', 'scritte'):
            with self.subTest(mode):
                week1 = arr(background(dict(config, decor=mode, season_round=1), 'matchday', 1))
                self.assertEqual(np.abs(week1[y1:y2, x1:x2]-plain[y1:y2, x1:x2]).max(), 0)
                self.assertGreater(np.abs(week1-plain).mean(), .3)
                if mode != 'griglia':   # the grid is the same every week, the rest moves
                    week2 = arr(background(dict(config, decor=mode, season_round=2), 'matchday', 1))
                    self.assertGreater(np.abs(week2-week1).mean(), .1)


class PanelsAndTitles(unittest.TestCase):
    def test_every_panel_style_keeps_the_panel_colour(self):
        panel = np.array(STYLE['crt']['panel'])
        borders = {}
        for style in PANEL_STYLES:
            if style == 'rotazione':
                continue
            image = arr(background(dict(apply_preset(defaults('Convocati'), 'crt'), theme='none', panel_style=style),
                                   'convocati', 1))
            inside = image[335:375, 110:430].reshape(-1, 3)
            self.assertGreater((np.abs(inside-panel).sum(axis=1) < 60).mean(), .8, style)
            borders[style] = image[312:330, 76:200]
        for a in borders:
            for b in borders:
                if a < b:
                    self.assertGreater(np.abs(borders[a]-borders[b]).mean(), .5, (a, b))

    def test_title_effects_keep_the_text_centred(self):
        asset = text_image('CLASSIFICA', 'CRT Terminal', 24, (246, 244, 252), 280, None, 2, 24)
        centre = np.array(asset.size)/2
        outputs = {}
        for effect in title_fx.EFFECTS:
            if effect == 'rotazione':
                continue
            image = title_fx.decorate(asset, 2, effect)
            alpha = np.asarray(image.getchannel('A'), np.float32)
            ys, xs = np.nonzero(alpha > 200)
            middle = np.array(((xs.min()+xs.max())/2, (ys.min()+ys.max())/2))
            shift = middle-np.array(image.size)/2
            self.assertLess(np.abs(shift).max(), 9, effect)    # long shadows lean a little, never more
            outputs[effect] = image
        self.assertGreaterEqual(len({o.tobytes() for o in outputs.values()}), 8)
        self.assertEqual(title_fx.resolve({'title_fx': 'rotazione', 'season_round': 3}), title_fx.CYCLE[2])

    def test_the_title_changes_in_every_template(self):
        for template in TEMPLATES:
            with self.subTest(template):
                a, _ = scene(template)
                b, _ = scene(template, title_fx='neon')
                ta = next(l for l in a[1] if l.id == 'title').image
                tb = next(l for l in b[1] if l.id == 'title').image
                self.assertNotEqual(ta.tobytes(), tb.tobytes())
                others_a = [l.image.tobytes() for l in a[1] if l.id != 'title']
                others_b = [l.image.tobytes() for l in b[1] if l.id != 'title']
                self.assertEqual(others_a, others_b)


class FramesAndTextures(unittest.TestCase):
    def png(self, fmt, **extra):
        config = dict(apply_preset(defaults('Matchday Screen'), 'crt'), theme='none', export_format=fmt, **extra)
        return arr(Image.open(io.BytesIO(MODULES['Matchday Screen'].png_bytes(config, LOGO, None, None, fmt, 1, 1))))

    def test_the_polaroid_border_sits_on_the_edges_of_every_format(self):
        for fmt in ('Story 9:16', 'Post 4:5', 'Post 1:1'):
            with self.subTest(fmt):
                image = self.png(fmt, frame_style='polaroid')
                bottom = image[-40:-10, 120:420].reshape(-1, 3).mean(axis=0)
                side = image[100:-100, 2:12].reshape(-1, 3).mean(axis=0)
                self.assertGreater(bottom.min(), 200)
                self.assertGreater(side.min(), 220)

    def test_every_frame_and_texture_changes_the_picture(self):
        plain = self.png('Post 4:5')
        for name in frames.FRAMES:
            if name not in ('nessuna', 'rotazione'):
                self.assertGreater(np.abs(self.png('Post 4:5', frame_style=name)-plain).mean(), 1, name)
        for name in frames.TEXTURES:
            if name not in ('nessuna', 'rotazione'):
                textured = self.png('Post 4:5', texture_fx=name)
                self.assertGreater(np.abs(textured-plain).mean(), .05, name)   # dust is sparse
                self.assertLess(abs(textured.mean()-plain.mean()), 12, name)

    def test_the_tv_mockup_is_the_frame(self):
        a = self.png('Post 1:1', mockup=True)
        b = self.png('Post 1:1', mockup=True, frame_style='neon', texture_fx='vhs')
        self.assertEqual(np.abs(a-b).max(), 0)

    def test_still_images_are_deterministic(self):
        a = self.png('Story 9:16', texture_fx='grana', frame_style='pellicola')
        b = self.png('Story 9:16', texture_fx='grana', frame_style='pellicola')
        self.assertEqual(np.abs(a-b).max(), 0)


class Motion(unittest.TestCase):
    def test_entrance_families_keep_the_signature_moves(self):
        prepared, _ = scene('Full Time', entrance='pixel')
        kinds = {l.id: l.anim for l in prepared[1]}
        self.assertEqual(kinds['score'], 'count')
        self.assertEqual(kinds['title'], 'pixelate')
        self.assertEqual(kinds['home_logo'], 'pixelate')
        mixed, _ = scene('Full Time')
        self.assertEqual({l.id: l.anim for l in mixed[1]}['title'], 'type')
        matchday, _ = scene('Matchday Screen', entrance='rimbalzo')
        kinds = {l.id: l.anim for l in matchday[1]}
        self.assertEqual(kinds['home_logo'], 'slide_left')
        self.assertEqual(kinds['vs'], 'bounce')
        sounds = {kind for _, kind, _ in animations.events(scene('Classifica', entrance='pixel')[0])}
        self.assertIn('glitch', sounds)

    def test_every_entrance_draws_in_between(self):
        for family in ('glitch', 'pixel', 'scrivere', 'rimbalzo', 'tendina', 'zoom'):
            with self.subTest(family):
                prepared, _ = scene('Convocati', entrance=family, power_on=False)
                title = next(l for l in prepared[1] if l.id == 'title')
                middle = animations.compose(prepared, title.start+title.dur*.4, True)
                end = animations.compose(prepared, 30, True)
                self.assertGreater(np.abs(arr(middle)-arr(end)).mean(), .5)

    def test_cameras_and_effects_move_videos_only(self):
        still, _ = scene('Matchday Screen')
        reference = arr(animations.compose(still, 6.2, True))
        for extra in ({'camera': 'zoom'}, {'camera': 'oscillazione'}, {'camera': 'carrellata'}, {'camera': 'parallasse'},
                      {'camera': 'ritmo'}, {'fx_pulse': True}, {'fx_particles': True}, {'fx_flicker': True}):
            with self.subTest(extra):
                prepared, config = scene('Matchday Screen', **extra)
                prepared[0].info['duration'] = 8
                moving = arr(animations.compose(prepared, 6.2, True))
                self.assertGreater(np.abs(moving-reference).mean(), .05)   # particles are small
                png = MODULES['Matchday Screen'].png_bytes(config, LOGO, None, None, 'Story 9:16', 1, 1)
                plain = MODULES['Matchday Screen'].png_bytes(dict(config, **{k: CRT_DEFAULT[k] for k in extra}),
                                                             LOGO, None, None, 'Story 9:16', 1, 1)
                self.assertEqual(png, plain)
        sweep, _ = scene('Matchday Screen', fx_sweep=True)
        frames_ = [arr(animations.compose(sweep, t, True)) for t in (7.4, 7.6)]
        plain_ = [arr(animations.compose(still, t, True)) for t in (7.4, 7.6)]
        self.assertGreater(max(np.abs(a-b).mean() for a, b in zip(frames_, plain_)), .3)

    def test_new_endings(self):
        for ending in motion.NEW_ENDINGS:
            with self.subTest(ending):
                config = sanitize_config('Matchday Screen', dict(defaults('Matchday Screen'), ending=ending))
                self.assertEqual(config['ending'], ending)
                prepared, _ = scene('Matchday Screen', ending=ending)
                length = crt_common.video_length(prepared, 5)
                plain, _ = scene('Matchday Screen')
                self.assertAlmostEqual(length-crt_common.video_length(plain, 5), .8, places=1)
                prepared[0].info['duration'] = length
                last = arr(animations.compose(prepared, length-.05, True)).mean()
                before = arr(animations.compose(prepared, length-1.0, True)).mean()
                self.assertLess(last, before*.6)
                self.assertTrue(any(abs(t-(length-.8)) < .01 for t, _, _ in animations.events(prepared)))

    def test_logo_intro(self):
        prepared, _ = scene('Classifica', intro=True, intro_style='logo')
        info = prepared[0].info
        self.assertIsNotNone(info['crest'])
        early = arr(animations.compose(prepared, .5, True))
        late = arr(animations.compose(prepared, 1.5, True))
        self.assertGreater(early.mean(), 2)
        self.assertGreater(late.mean(), early.mean())
        bare = Image.new('RGB', (540, 960))
        self.assertEqual(intros.frame(bare, 1.5, {'intro_style': 'logo'}).size, (540, 960))   # no crest: our logo
        self.assertIn('impact', [k for _, k, _ in intros.sound_events('logo')])

    def test_reel_mode_is_valid_everywhere(self):
        for template in TEMPLATES:
            config = sanitize_config(template, dict(defaults(template), **motion.REEL))
            for key, value in motion.REEL.items():
                self.assertEqual(config[key], value, (template, key))

    def test_a_reel_renders(self):
        prepared_config = dict(apply_preset(defaults('Convocati'), 'curva'), theme='none', **motion.REEL)
        prepared_config.update(frame_style='neon', texture_fx='vhs', entrance='rotazione', decor='adesivi',
                               atmosphere='notte', panel_style='neon', title_fx='glitch', duration=5)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'reel.mp4'
            MODULES['Convocati'].render_video(prepared_config, LOGO, None, path, None, 6, 5, 'Story 9:16', 1)
            self.assertGreater(path.stat().st_size, 20_000)


class State(unittest.TestCase):
    def test_old_projects_get_the_classic_look(self):
        old = defaults('Full Time')
        for key in ('atmosphere', 'decor', 'panel_style', 'title_fx', 'frame_style', 'texture_fx', 'entrance', 'camera',
                    'fx_pulse', 'fx_flicker', 'fx_particles', 'fx_sweep'):
            old.pop(key)
        config = sanitize_config('Full Time', old)
        self.assertEqual((config['atmosphere'], config['panel_style'], config['title_fx'], config['frame_style'],
                          config['camera'], config['fx_pulse']), ('standard', 'smussato', 'ombra', 'nessuna', 'fermo', False))

    def test_bad_values_fall_back(self):
        config = sanitize_config('Classifica', dict(defaults('Classifica'), camera='drone', title_fx=3, ending='boom'))
        self.assertEqual((config['camera'], config['title_fx'], config['ending']), ('fermo', 'ombra', 'nessuno'))

    def test_starting_seven_texture_slider_untouched(self):
        self.assertEqual(sanitize_config('Starting 7', dict(defaults('Starting 7'), texture=60))['texture'], 60)


if __name__ == '__main__':
    unittest.main()
