"""3.25: the opponent's colours on their half, and the real match weather and time."""
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Colours(unittest.TestCase):
    def test_csi_words(self):
        import team_colors as tc
        self.assertEqual(tc.parse('GIALLO ROSSO'), [(255, 208, 0), (222, 32, 44)])
        self.assertEqual(tc.parse('BIANCA/ROSSA'), [(245, 245, 242), (222, 32, 44)])
        self.assertEqual(tc.parse('FUCSIA E NERA'), [(232, 36, 146), (18, 18, 22)])
        self.assertEqual(tc.parse("BLU'/AZZURRO"), [(28, 72, 196), (64, 168, 240)])
        self.assertEqual(tc.parse('NERA O BIANCA'), [(18, 18, 22), (245, 245, 242)])
        self.assertEqual(tc.parse('ROSSO-BLU'), [(222, 32, 44), (28, 72, 196)])
        self.assertEqual(tc.parse('ROSA'), [(246, 120, 178)])
        self.assertEqual(tc.parse(''), [])
        self.assertEqual(tc.from_hex(tc.to_hex([(1, 2, 3), (250, 0, 16)])), [(1, 2, 3), (250, 0, 16)])

    def test_readable_name_on_a_dark_box(self):
        import team_colors as tc
        for words in ('BLU', 'NERO', 'GIALLO ROSSO', 'FUCSIA E NERA', 'BIANCO BLU', 'GRANATA'):
            main, second, text = tc.pair(tc.parse(words))
            self.assertGreaterEqual(tc._lum(text), .45, words)
            self.assertNotEqual(main, second)
        self.assertEqual(tc.pair(tc.parse('NERO'))[2], (246, 244, 240))      # black team: white name
        self.assertIsNone(tc.pair([]))

    def test_whole_girone_known_and_site_first(self):
        import team_colors as tc
        for name in ('AS ARDENS 2002', 'CASTE UNITED', 'CASTEL MELLA', 'GALBA F.C.', 'SPORTING LENO', 'FC MUSTANGS',
                     'GSO PONCARALE', 'GSO VEROLAN', 'LIONS 25', 'PIRATI', 'UMC', 'UNITED FLERO'):
            self.assertTrue(tc.lookup(name), name)
        self.assertEqual(tc.lookup('UMC', {'UMC': 'VERDE'}), '#189C4C')
        self.assertEqual(tc.lookup('SQUADRA NUOVA'), '')

    def test_only_the_opponent_half(self):
        import studio_state as ss, team_colors as tc
        c = ss.defaults('Matchday Screen')
        c.update(home_name='FLAMINGOS', away_name='AS ARDENS 2002', our_side='Casa')
        self.assertEqual(tc.opponent_side(c), 'away')
        self.assertEqual(tc.for_config(c)[0], (255, 208, 0))
        c.update(opp_colors_on=False)
        self.assertIsNone(tc.for_config(c))
        c.update(opp_colors_on=True, home_name='FC MUSTANGS', away_name='FLAMINGOS', our_side='Ospiti')
        self.assertEqual(tc.opponent_side(c), 'home')
        self.assertEqual(tc.for_config(c)[0], (232, 36, 146))
        c.update(opponent_colors='#112233,#445566', opponent_colors_for='FC MUSTANGS')     # picked by hand
        self.assertEqual(tc.for_config(c)[:2], ((17, 34, 51), (68, 85, 102)))
        c.update(home_name='UMC')                                                      # another opponent: not theirs
        self.assertEqual(tc.for_config(c)[0], (222, 32, 44))

    def test_their_box_in_every_layout(self):
        import layouts, studio_state as ss, team_colors as tc
        for template, base in (('Matchday Screen', 'matchday'), ('Full Time', 'fulltime')):
            for layout in layouts.options(template):
                for side in ('Casa', 'Ospiti'):
                    c = layouts.apply(template, ss.defaults(template), layout)
                    c['our_side'] = side
                    rect = tc.panel_for(c, template, layouts.panel_key(base, template, c))
                    self.assertIsNotNone(rect, (template, layout, side))
                    x = layouts.default_positions(template, layout)[tc.opponent_side(c)+'_name'][0]
                    self.assertTrue(rect[0] < x < rect[2])

    def test_renders_with_and_without(self):
        import numpy as np
        from PIL import Image
        import matchday_renderer as m, fulltime_renderer as f, studio_state as ss
        crest = (ROOT/'assets'/'stemmi'/'as_ardens.png').read_bytes()
        ours = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
        for mod, template in ((m, 'Matchday Screen'), (f, 'Full Time')):
            c = ss.defaults(template)
            c.update(home_name='FLAMINGOS', away_name='AS ARDENS 2002')
            on = np.asarray(Image.open(io.BytesIO(mod.png_bytes(c, ours, crest, None, 'Post 1:1', 1, 1))).convert('RGB'))
            c['opp_colors_on'] = False
            off = np.asarray(Image.open(io.BytesIO(mod.png_bytes(c, ours, crest, None, 'Post 1:1', 1, 1))).convert('RGB'))
            diff = np.abs(on.astype(int)-off).sum(axis=2) > 30
            cols = np.nonzero(diff.any(axis=0))[0]
            self.assertTrue(diff.any())
            self.assertGreater(cols.min(), 540*0.45, template)                   # only their (right) half changes


class Weather(unittest.TestCase):
    def test_codes(self):
        import weather as w
        self.assertEqual(w.condition(0), 'sereno')
        self.assertEqual(w.condition(3), 'nuvoloso')
        self.assertEqual(w.condition(45), 'nebbia')
        self.assertEqual(w.condition(63), 'pioggia')
        self.assertEqual(w.condition(51, 20), 'nuvoloso')                     # a drizzle unlikely to come
        self.assertEqual(w.condition(80, 70), 'pioggia')
        self.assertEqual(w.condition(73), 'neve')
        self.assertEqual(w.condition(95), 'temporale')
        self.assertEqual(w.condition(None), '')

    def test_towns_from_the_csi_addresses(self):
        import weather as w
        self.assertEqual(w.town('ORATORIO CASTEL MELLA VIA MARCONI - CASTEL MELLA BS')[0], 'Castel Mella')
        self.assertEqual(w.town('ORATORIO PONCARALE, VIA ROMA - PONCARALE (BS)')[0], 'Poncarale')
        self.assertEqual(w.town('VIA FORNACI, 82')[0], 'Brescia')
        self.assertEqual(w.town('CAMPO OR. SAN DOMENICO SAVIO, VIA DELLO STADIO 1 - CAPRIANO DEL COLLE (BS)')[0],
                         'Capriano del Colle')
        self.assertIsNone(w.town('CENTRO SPORTIVO, VIA LUNGA 3 - ISEO (BS)'))
        self.assertEqual(w.town_name('CENTRO SPORTIVO, VIA LUNGA 3 - ISEO (BS)'), 'Iseo')

    def test_lookup_and_offline(self):
        import weather as w

        def opener(request, timeout):
            self.assertIn('name=Iseo', request.full_url)
            return io.BytesIO(json.dumps({'results': [{'name': 'Iseo', 'latitude': 45.66, 'longitude': 10.05}]}).encode())
        self.assertEqual(w.locate('CAMPO - ISEO (BS)', opener), ('Iseo', 45.66, 10.05))

        def down(request, timeout):
            raise OSError('offline')
        self.assertEqual(w.locate('CAMPO - ISEO (BS)', down), w.BRESCIA)

    def test_sunset_and_light(self):
        import weather as w
        winter = w.sunset(dt.date(2026, 11, 28))
        summer = w.sunset(dt.date(2026, 6, 21))
        self.assertTrue(dt.time(16, 25) < winter.time() < dt.time(16, 55), winter)
        self.assertTrue(dt.time(20, 55) < summer.time() < dt.time(21, 25), summer)
        self.assertEqual(w.light('28/11/2026', '20:45'), 'notte')
        self.assertEqual(w.light('28/11/2026', '16:15'), 'tramonto')
        self.assertIsNone(w.light('28/11/2026', '14:30'))
        self.assertIsNone(w.light('21/06/2026', '19:00'))
        self.assertIsNone(w.light('GG/MM/AAAA', 'HH:MM'))

    def test_forecast_at_kickoff(self):
        import weather as w
        hours = [f'2026-11-28T{h:02d}:00' for h in range(24)]
        answer = {'hourly': {'time': hours, 'weather_code': [0]*20+[63]*4,
                             'precipitation_probability': [0]*20+[85]*4, 'temperature_2m': [5.4]*24}}

        def opener(request, timeout):
            self.assertIn('start_date=2026-11-28', request.full_url)
            return io.BytesIO(json.dumps(answer).encode())
        match = dict(date='28/11/2026', kickoff='20:45', venue='ORATORIO CASTEL MELLA VIA MARCONI - CASTEL MELLA BS')
        out = w.check(match, dt.date(2026, 11, 25), opener)
        self.assertEqual(out['weather'], 'pioggia')
        self.assertIn('Pioggia (85%)', out['note'])
        self.assertIn('5°', out['note'])
        self.assertIn('Castel Mella, sab 20:45', out['note'])
        far = w.check(match, dt.date(2026, 11, 1), opener)
        self.assertEqual(far['weather'], '')
        self.assertIn('Previsioni disponibili da 13/11', far['note'])
        self.assertIsNone(w.check(match, dt.date(2026, 12, 1), opener))         # already played

    def test_what_the_graphic_does(self):
        import weather as w
        c = dict(weather_auto=True, weather='pioggia', date='28/11/2026', kickoff='14:30')
        self.assertEqual(w.atmosphere(c, 'matchday'), 'pioggia')
        self.assertEqual(w.particles(c, 'matchday@duello'), 'rain')
        self.assertEqual(w.atmosphere(dict(c, kickoff='20:45'), 'convocati'), 'notte')
        self.assertEqual(w.atmosphere(dict(c, weather=''), 'convocati'), None)
        self.assertEqual(w.atmosphere(dict(c, weather='', kickoff='20:45'), 'matchday'), 'notte')
        self.assertIsNone(w.atmosphere(c, 'fulltime'))                          # Full Time stays as it is
        self.assertIsNone(w.atmosphere(dict(c, weather_auto=False), 'matchday'))
        self.assertEqual(w.particles(dict(c, weather='nebbia'), 'matchday'), 'fog')

    def test_backgrounds(self):
        import numpy as np
        import crt_presets, studio_state as ss
        base = ss.defaults('Matchday Screen')
        base.update(date='28/11/2026', kickoff='14:30')
        plain = crt_presets.background(dict(base, weather_auto=False), 'matchday', 1)
        self.assertEqual(plain.info['weather'], '')
        for sky, kind in (('pioggia', 'rain'), ('neve', 'snow'), ('nebbia', 'fog'), ('temporale', 'storm')):
            image = crt_presets.background(dict(base, weather=sky), 'matchday', 1)
            self.assertEqual(image.info['weather'], kind)
            a, b = np.asarray(plain).astype(int), np.asarray(image).astype(int)
            self.assertGreater(np.abs(a-b)[:200].mean(), 3, sky)                   # the world around changes
            self.assertEqual(np.abs(a-b)[420:560, 140:400].max(), 0, sky)          # the screen does not
        import animations, weather
        from PIL import Image
        for kind in ('rain', 'storm', 'snow'):
            for mode in ('RGB', 'RGBA'):
                canvas = Image.new(mode, (540, 960))
                weather.draw(canvas, kind, 1.0)
                self.assertGreater(np.asarray(canvas).max(), 0)


class Wired(unittest.TestCase):
    def test_app_pieces(self):
        week = (ROOT/'week_ui.py').read_text()
        self.assertIn('def update_weather(force=False):', week)
        self.assertLess(week.index('line = update_weather()'), week.index("if st.session_state.get('csi_auto_done'):\n        return"))
        self.assertIn("st.session_state['csi_team_colors'] = colors", week)
        seq = (ROOT/'sequence_ui.py').read_text()
        self.assertIn('refresh_opponent_colors()', seq)
        studio = (ROOT/'studio_ui.py').read_text()
        self.assertEqual(studio.count('opponent_colors_box(config, key)'), 3)   # the helper and two editors
        self.assertEqual(studio.count('weather_box(config, key)'), 3)
        import studio_state as ss
        for template in ('Matchday Screen', 'Full Time'):
            self.assertTrue(ss.defaults(template)['opp_colors_on'])
        for template in ('Matchday Screen', 'Convocati'):
            self.assertTrue(ss.defaults(template)['weather_auto'])
        c = ss.sanitize_config('Matchday Screen', dict(ss.defaults('Matchday Screen'), weather='pioggia',
                                                       opponent_colors='#FFD000,#DE202C'))
        self.assertEqual((c['weather'], c['opponent_colors']), ('pioggia', '#FFD000,#DE202C'))


if __name__ == '__main__':
    unittest.main()
