"""Run: python -m unittest discover -s tests -v"""
import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

import renderer as r
import matchday_renderer as m
from render_utils import layout_warnings
from studio_state import defaults, empty_library, sanitize_config, validate_library

ROOT = Path(__file__).resolve().parents[1]


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logo = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
        cls.s7 = defaults('Starting 7')
        cls.md = defaults('Matchday Screen')

    def test_png_dimensions_and_profile(self):
        cases = [r.png_bytes(self.s7,self.logo),
                 m.png_bytes(self.md,self.logo,format='Post 1:1'),
                 m.png_bytes(self.md,self.logo,format='Story 9:16')]
        for value,size in zip(cases,[(1080,1920),(1080,1080),(1080,1920)]):
            im = Image.open(io.BytesIO(value))
            self.assertEqual(im.size,size)
            self.assertEqual(im.mode,'RGB')
            self.assertIn('srgb',im.info)

    def test_scene_is_natively_high_resolution(self):
        prepared = r.scene(self.s7,self.logo,render_scale=4)
        self.assertEqual(prepared[0].size,(2160,3840))
        players = [layer for layer in prepared[1] if layer.id.startswith('player_')]
        self.assertEqual(players[0].image.size,(600,444))
        ed = r.editor_data(prepared)
        item = next(layer for layer in ed['layers'] if layer['id']=='player_0')
        self.assertEqual(item['width'],150)
        self.assertEqual(item['height'],111)
        self.assertEqual(ed['positions']['player_0'],[270,746])

    def test_antialias_and_no_nearest_upscale(self):
        text = r.text_image('Flamingos 123','Sans Bold',19,(255,255,255),360,render_scale=4)
        alpha = np.asarray(text.getchannel('A'))
        self.assertTrue(np.any((alpha>0)&(alpha<255)))
        low = r.text_image('Flamingos 123','Sans Bold',19,(255,255,255),360,render_scale=1)
        nearest = low.resize(text.size,Image.Resampling.NEAREST)
        self.assertFalse(np.array_equal(np.asarray(text),np.asarray(nearest)))

    def test_text_fit_and_multiline(self):
        for style in ['Sans Bold','Monospace Bold','Pixel Arcade']:
            asset = r.text_image('UN NOME MOLTO LUNGO 123',style,32,(255,255,255),136,render_scale=4,max_height=26)
            self.assertLessEqual(asset.width,544)
            self.assertLessEqual(asset.height,104)
        name = m._name_text('AVVERSARIO CON NOME LUNGO','Sans Bold',30,(255,255,255),None,4)
        self.assertLessEqual(name.height,34*4)
        self.assertIsNone(r.text_image('  ','Sans Bold',20,(255,255,255),100))

    def test_alpha_composition(self):
        canvas = Image.new('RGBA',(540,960),(0,0,0,255))
        layer = r.Layer('a','Test',Image.new('RGBA',(2,2),(255,255,255,128)))
        r.composite_layer(canvas,layer,(270,480))
        self.assertEqual(canvas.getpixel((270,480)),(128,128,128,255))
        r.composite_layer(canvas,layer,(-50,-50))  # clipped, not an exception

    def test_normalization_and_crop_warnings(self):
        for module in [r,m]:
            field = next(iter(module.DEFAULT_POSITIONS))
            for value in [[float('nan'),10],[float('inf'),10],'bad',12,None]:
                self.assertEqual(module.normalized_positions({'positions':{field:value}})[field],module.DEFAULT_POSITIONS[field])
            self.assertEqual(module.normalized_positions({'positions':{field:[-99,9999]}})[field],(0,960))
        config = copy.deepcopy(self.md)
        config['positions']['title'] = [270,100]
        self.assertTrue(layout_warnings(m.scene(config,self.logo),m.FEED_CROP))
        self.assertFalse(layout_warnings(m.scene(self.md,self.logo),m.FEED_CROP))

    def test_custom_font_loaded_when_available(self):
        path = next((Path(p) for p in r.FONT_FALLBACK if Path(p).is_file()),None)
        if not path:
            self.skipTest('No system font available for this test.')
        data = path.read_bytes()
        r.validate_font(data)
        for module,cfg in [(r,self.s7),(m,self.md)]:
            config = {**cfg,'text_style':'Font salvato'}
            result = module.png_bytes(config,self.logo,font_bytes=data,scale=2)
            self.assertGreater(len(result),10000)
        with self.assertRaises(ValueError):
            r.validate_font(b'not a font')

    def test_logo_validation_and_resize(self):
        self.assertEqual(r.validate_logo(self.logo),(1600,1067))
        im = r.clean_logo(self.logo,100,True,4)
        self.assertEqual(im.width,400)
        self.assertEqual(im.mode,'RGBA')
        with self.assertRaises(ValueError):
            r.validate_logo(b'not an image')

    def test_video_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            for template,scale,fmt,size in [('s7',1,None,(540,960)),('s7',2,None,(1080,1920)),
                                             ('md',1,'Post 1:1',(540,540)),('md',2,'Post 1:1',(1080,1080)),
                                             ('md',2,'Story 9:16',(1080,1920))]:
                path = Path(temp)/(template+str(scale)+(fmt or '')[:4]+'.mp4')
                if template=='s7':
                    r.render_video(self.s7,self.logo,path,fps=12,duration=.25,scale=scale)
                else:
                    m.render_video(self.md,self.logo,None,path,fps=12,duration=.25,format=fmt,scale=scale)
                reader = imageio.get_reader(path)
                try:
                    self.assertEqual(reader.get_meta_data()['size'],size)
                    self.assertEqual(reader.count_frames(),3)
                    self.assertEqual(reader.get_meta_data()['fps'],12)
                finally:
                    reader.close()


class LibraryTests(unittest.TestCase):
    def test_project_import_sanitizes_fields(self):
        raw = {'title_size':99999,'date':'x'*100,'pink':'not a color','positions':{'title':[99,8888]},
               'duration':-20,'fps':200,'surprise':'ignored'}
        c = sanitize_config('Matchday Screen',raw)
        self.assertEqual(c['title_size'],42)
        self.assertEqual(len(c['date']),24)
        self.assertEqual(c['positions']['title'],[99,960])
        self.assertEqual(c['duration'],5)
        self.assertEqual(c['fps'],24)
        self.assertNotIn('surprise',c)

    def test_browser_snapshot_is_validated(self):
        lib = empty_library()
        data = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()
        id_ = 'logo:'+hashlib.sha256(data).hexdigest()
        lib['assets'][id_] = {'kind':'logo','name':'Shield.jpg','data':base64.b64encode(data).decode()}
        lib['projects']['test'] = {'name':'Example','template':'Starting 7','config':defaults('Starting 7')}
        valid,messages = validate_library(lib)
        self.assertFalse(messages)
        self.assertEqual(valid['assets'][id_]['bytes'],data)
        self.assertEqual(len(valid['projects']),1)
        lib['assets'][id_]['data'] = '!!!'
        invalid,messages = validate_library(lib)
        self.assertTrue(messages)
        self.assertFalse(invalid['assets'])

    def test_malformed_archives_and_geometry(self):
        for raw in [None,[],{}, {'schema':999}]:
            with self.assertRaises(ValueError):
                validate_library(raw)
        raw = defaults('Starting 7')
        raw['players'] = [{'number':float('nan'),'name':'x'*100}]
        result = sanitize_config('Starting 7',raw)
        self.assertEqual(result['players'][0]['number'],1)
        self.assertEqual(len(result['players'][0]['name']),27)
        self.assertEqual(len(result['players']),7)


if __name__=='__main__':
    unittest.main()
