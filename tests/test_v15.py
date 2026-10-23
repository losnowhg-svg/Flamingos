"""Regression coverage for season presets, new editors, fonts and format export."""
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
import fulltime_renderer as f
import convocati_renderer as c
from crt_presets import PRESETS, PRESET_IDS, CROPS, FORMATS, apply_preset, preset_for_round, output_image, even_video_frame
from pixel_fonts import PIXEL_FONTS, TERMINAL, COMPACT
from studio_state import defaults, sanitize_config, empty_library, validate_library, MODULES, BUILTIN_FONTS
from render_utils import layout_warnings

ROOT=Path(__file__).resolve().parents[1]


class NewEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.logo=(ROOT/'assets/flamingos_logo.jpg').read_bytes()

    def test_all_crt_scenes_and_default_bounds(self):
        fingerprints={}
        for template in ('Matchday Screen','Full Time','Convocati'):
            module=MODULES[template]
            for preset in PRESET_IDS:
                with self.subTest(template=template,preset=preset):
                    config=apply_preset(defaults(template),preset)
                    scene=module.scene(config,self.logo,render_scale=1)
                    self.assertFalse(layout_warnings(scene,CROPS['Post 1:1']))
                    self.assertEqual(set(x.id for x in scene[1]),set(r.editor_data(scene)['layers'][i]['id'] for i in range(len(scene[1]))))
                    image=module.compose(scene,animated=False)
                    self.assertEqual(image.size,(540,960))
                    fingerprints[template,preset]=hashlib.sha256(image.tobytes()).digest()
        self.assertEqual(len(set(fingerprints.values())),3*len(PRESET_IDS))

    def test_png_formats_and_profile(self):
        for template in ('Full Time','Convocati'):
            for fmt,size in zip(FORMATS,((1080,1080),(1080,1350),(1080,1920))):
                with self.subTest(template=template,format=fmt):
                    data=MODULES[template].png_bytes(defaults(template),self.logo,format=fmt)
                    im=Image.open(io.BytesIO(data))
                    self.assertEqual(im.size,size)
                    self.assertEqual(im.mode,'RGB')
                    self.assertIn('srgb',im.info)
        im=Image.open(io.BytesIO(m.png_bytes(defaults('Matchday Screen'),self.logo,format='Post 4:5')))
        self.assertEqual(im.size,(1080,1350))

    def test_score_changes_real_pixels(self):
        cfg=defaults('Full Time')
        a=f.compose(f.scene(cfg,self.logo,render_scale=1),animated=False)
        cfg['home_score']=13;cfg['away_score']=11
        b=f.compose(f.scene(cfg,self.logo,render_scale=1),animated=False)
        self.assertNotEqual(a.tobytes(),b.tobytes())
        score=next(x for x in f.get_layers(cfg,self.logo) if x.id=='score')
        self.assertLessEqual(score.image.width,146)

    def test_results_relative_to_our_side_and_penalties(self):
        cfg=defaults('Full Time')
        for home,away,side,expected in ((4,2,'Casa','VITTORIA'),(4,2,'Ospiti','SCONFITTA'),
                                       (1,3,'Casa','SCONFITTA'),(1,3,'Ospiti','VITTORIA'),(2,2,'Casa','PAREGGIO')):
            cfg.update(home_score=home,away_score=away,our_side=side)
            self.assertEqual(f.result_text(cfg),expected)
        cfg.update(show_penalties=True,home_penalties=5,away_penalties=4)
        self.assertEqual(f.result_text(cfg),'VITTORIA AI RIGORI')
        cfg['away_penalties']=5
        self.assertEqual(f.result_text(cfg),'RIGORI IN PARITA')
        cfg.update(home_score=3,away_score=2)
        self.assertEqual(f.result_text(cfg),'VITTORIA')
        self.assertNotIn('penalties',[x.id for x in f.get_layers(cfg,self.logo)])
        cfg['show_result']=False
        self.assertEqual(f.result_text(cfg),'')

    def test_scorers_visibility_and_six_lines(self):
        cfg=defaults('Full Time')
        cfg.update(home_scorers='\n'.join([f'GIOCATORE {i} 12\'' for i in range(6)]),away_scorers='')
        self.assertEqual(len(f.scorer_lines(cfg['home_scorers'])),6)
        self.assertFalse(layout_warnings(f.scene(cfg,self.logo),CROPS['Post 1:1']))
        cfg['show_scorers']=False
        self.assertNotIn('home_scorers',[x.id for x in f.get_layers(cfg,self.logo)])

    def test_scorer_line_rows_have_clear_gaps(self):
        # Guard against the overlapping multiline text caught in visual review.
        for count in (3,6):
            im=f._scorers('\n'.join(['ROSSI 12\'']*count),'MARCATORI',(255,0,0),(255,255,255),'CRT Terminal',11,None,2)
            occupied=np.asarray(im.getchannel('A')).max(axis=1)>0
            groups=sum(bool(occupied[i]) and (i==0 or not occupied[i-1]) for i in range(len(occupied)))
            self.assertGreaterEqual(groups,count+1)

    def test_convocati_seven_to_eighteen_and_hidden_values(self):
        cfg=defaults('Convocati')
        cfg['roster'][17].update(name='ULTIMO',captain=True)
        for count in (7,12,18):
            cfg['roster_count']=count
            scene=c.scene(cfg,self.logo,render_scale=2)
            self.assertEqual(len([x for x in scene[1] if x.id.startswith('player_')]),count)
            self.assertFalse(layout_warnings(scene,CROPS['Post 1:1']))
        cfg['roster_count']=7
        validated=sanitize_config('Convocati',cfg)
        self.assertEqual(validated['roster'][17]['name'],'ULTIMO')
        self.assertTrue(validated['roster'][17]['captain'])

    def test_animations_reach_final_frame(self):
        for module,template in ((f,'Full Time'),(c,'Convocati')):
            scene=module.scene(defaults(template),self.logo,render_scale=1)
            first=module.compose(scene,t=0)
            last=module.compose(scene,t=4.9)
            self.assertNotEqual(first.tobytes(),last.tobytes())

    def test_mp4_new_formats_and_even_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            for template,module,scale,fmt,dimensions in (
                    ('Full Time',f,2,'Post 1:1',(1080,1080)),
                    ('Full Time',f,2,'Post 4:5',(1080,1350)),
                    ('Convocati',c,2,'Story 9:16',(1080,1920)),
                    ('Convocati',c,1,'Post 4:5',(540,676)),
                    ('Matchday Screen',m,1,'Post 4:5',(540,676))):
                file=Path(tmp)/(template+str(scale)+fmt[:6]+'.mp4')
                module.render_video(defaults(template),self.logo,None,file,fps=12,duration=.25,format=fmt,scale=scale)
                reader=imageio.get_reader(file)
                try:
                    self.assertEqual(reader.get_meta_data()['size'],dimensions)
                    self.assertEqual(reader.count_frames(),3)
                finally:reader.close()
        source=Image.new('RGB',(540,675),(10,20,30))
        padded=even_video_frame(source)
        self.assertEqual(padded.size,(540,676))
        self.assertEqual(padded.crop((0,0,540,675)).tobytes(),source.tobytes())


class SeasonSchemaTests(unittest.TestCase):
    def test_preset_cycles_and_preserves_content(self):
        original=defaults('Full Time');original.update(home_score=8,away_score=6,home_scorers='ROSSI 3',font_choice='Sans Bold')
        original['positions']['score']=[261,455]
        for round_no in range(1,81):
            self.assertEqual(preset_for_round(round_no),PRESET_IDS[(round_no-1)%len(PRESET_IDS)])
        result=apply_preset(original,'handheld')
        for key in ('home_score','away_score','home_scorers','home_logo_id','font_choice','positions'):
            self.assertEqual(result[key],original[key])
        result['positions']['score'][0]=99
        self.assertEqual(original['positions']['score'][0],261)
        self.assertNotEqual(result['cyan'],original['cyan'])
        self.assertEqual(apply_preset(original,'arcade',True)['font_choice'],'CRT Scoreboard')
        self.assertEqual(apply_preset(original,'invalid')['preset_id'],'crt')

    def test_defaults_roundtrip_and_old_archives(self):
        library=empty_library()
        for template in MODULES:
            cfg=defaults(template)
            self.assertEqual(sanitize_config(template,cfg),cfg)
            library['projects'][template]={'name':'Example','template':template,'config':cfg}
        old=copy.deepcopy(library['projects']['Matchday Screen']['config'])
        for key in ('preset_id','rotation_mode','season_round','scanlines','our_side'):old.pop(key)
        old['font_choice']='Sans Bold'
        library['projects']['v14']={'name':'Old','template':'Matchday Screen','config':old}
        clean,messages=validate_library(json.loads(json.dumps(library)))
        self.assertFalse(messages)
        self.assertEqual(len(clean['projects']),len(MODULES)+1)
        self.assertEqual(clean['projects']['v14']['config']['preset_id'],'crt')
        self.assertEqual(clean['projects']['v14']['config']['font_choice'],'Sans Bold')

    def test_new_import_limits_and_untrusted_values(self):
        cfg=sanitize_config('Full Time',{'home_score':-10,'away_score':9999,'preset_id':{'bad':1},
            'positions':{'score':[float('nan'),999]},'show_penalties':'true','season_round':float('inf'),
            'home_scorers':'x'*2000,'our_side':'Unknown','export_format':'Post 4:5'})
        self.assertEqual((cfg['home_score'],cfg['away_score']),(0,99))
        self.assertEqual(cfg['preset_id'],'crt')
        self.assertEqual(cfg['positions']['score'],list(f.DEFAULT_POSITIONS['score']))
        self.assertFalse(cfg['show_penalties'])
        self.assertEqual(len(cfg['home_scorers']),1200)
        self.assertEqual(cfg['export_format'],'Post 4:5')
        roster=sanitize_config('Convocati',{'roster_count':999,'roster':[{'number':-2,'name':'x'*90,'role':[], 'captain':'true'}]})
        self.assertEqual(roster['roster_count'],18)
        self.assertEqual(roster['roster'][0],dict(number=0,name='x'*27,role='-',captain=False))


class PixelFontTests(unittest.TestCase):
    def test_glyph_tables_and_distinct_alphabets(self):
        for key,encoded in TERMINAL.items():
            self.assertEqual(len(encoded),14,key)
            self.assertTrue(all(int(encoded[i:i+2],16)<32 for i in range(0,14,2)),key)
        for key,encoded in COMPACT.items():
            self.assertEqual(len(encoded),5,key)
            self.assertTrue(all(int(x,16)<8 for x in encoded),key)
        self.assertTrue(all(font in BUILTIN_FONTS for font in PIXEL_FONTS))
        a=r.text_image('FULL TIME 4-2',PIXEL_FONTS[0],30,(255,255,255),500)
        b=r.text_image('FULL TIME 4-2',PIXEL_FONTS[1],30,(255,255,255),500)
        self.assertNotEqual(a.tobytes(),b.tobytes())

    def test_pixel_fonts_fit_and_accents_in_all_output_scales(self):
        value='PERCH\u00c9 PI\u00d9 CITT\u00c0 123 / 38\u2019'
        for font in PIXEL_FONTS:
            for scale in (1,2,4):
                im=r.text_image(value,font,32,(255,255,255),160,render_scale=scale,max_height=19)
                self.assertLessEqual(im.width,160*scale)
                self.assertLessEqual(im.height,19*scale)
                self.assertEqual(set(np.unique(im.getchannel('A'))),{0,255})
        self.assertIsNone(r.text_image(' ',PIXEL_FONTS[0],20,(255,255,255),200))

    def test_shared_run_baseline_has_no_extra_spacing(self):
        white=(255,255,255)
        for font in PIXEL_FONTS:
            a=r.text_runs([('KICK ',white),('OFF',white)],font,20,200,render_scale=2)
            b=r.text_image('KICK OFF',font,20,white,200,render_scale=2)
            self.assertEqual(a.tobytes(),b.tobytes())


if __name__=='__main__':unittest.main()
