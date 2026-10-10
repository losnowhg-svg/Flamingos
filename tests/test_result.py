"""Regression tests for 1.5: results, presets, responsive layouts and exports."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import imageio.v2 as imageio
from PIL import Image, ImageChops
import renderer as r
import matchday_renderer as m
import match_result_renderer as mr
from presets import PRESETS, apply_preset
from studio_state import defaults, sanitize_config, empty_library, validate_library
from studio_tools import (switch_result_format, matchday_to_result, signature,
                          png_export, export_pack, export_basename, build_caption, preflight)
from render_utils import layout_warnings

LOGO = (ROOT/'assets'/'flamingos_logo.jpg').read_bytes()


def sample():
    value = defaults('Match Result')
    value.update(home_score=3,away_score=1,away_name='SPORTING CLUB',date='18/10/2026',
                 round_label='GIORNATA 06',scorers_home="Rossi 12', 47'\nBianchi 68'",scorers_away="Verdi 35'",mvp='MARCO ROSSI')
    return value


class ResultTests(unittest.TestCase):
    def test_all_formats_png_dimensions_and_editor_geometry(self):
        for fmt,height in mr.FORMATS.items():
            with self.subTest(format=fmt):
                config = switch_result_format(sample(),fmt)
                png = mr.png_bytes(config,LOGO,supersample=1)
                with Image.open(io.BytesIO(png)) as image:
                    self.assertEqual(image.size,(1080,height*2))
                    self.assertIn('srgb',image.info)
                scene = mr.scene(config,LOGO,render_scale=1)
                data = r.editor_data(scene)
                self.assertEqual(data['canvas_height'],height)
                self.assertEqual(data['canvas_width'],540)
                self.assertFalse(layout_warnings(scene))

    def test_fine_png_supersampling(self):
        c = switch_result_format(sample(),'Post 1:1')
        fine = mr.png_bytes(c,LOGO,supersample=2)
        standard = mr.png_bytes(c,LOGO,supersample=1)
        self.assertNotEqual(fine,standard)
        self.assertEqual(Image.open(io.BytesIO(fine)).size,(1080,1080))

    def test_score_changes_graphic(self):
        a = sample();b = {**a,'home_score':0}
        self.assertNotEqual(mr.png_bytes(a,LOGO,scale=1,supersample=1),mr.png_bytes(b,LOGO,scale=1,supersample=1))

    def test_large_scores_long_names_and_six_scorers(self):
        c = sample()
        c.update(home_score=99,away_score=99,home_name='ASSOCIAZIONE SPORTIVA NOME MOLTO LUNGO',
                 away_name='UNIONE SPORTIVA AVVERSARIA NOME LUNGO',scorers_home='\n'.join(['Nome molto lungo 12\', 43\'']*6),scorers_away='\n'.join(['Verdi 12\'']*6))
        for fmt in mr.FORMATS:
            config = switch_result_format(c,fmt)
            prepared = mr.scene(config,LOGO,render_scale=1)
            self.assertFalse(layout_warnings(prepared))
            blocks = {l.id:l.image for l in prepared[1] if l.id.startswith('scorers_')}
            self.assertEqual(blocks['scorers_home'].height,blocks['scorers_away'].height)

    def test_empty_optional_layers(self):
        c = defaults('Match Result')
        ids = [l.id for l in mr.scene(c,LOGO,render_scale=1)[1]]
        self.assertNotIn('mvp',ids)
        self.assertNotIn('scorers_home',ids)
        self.assertIn('score',ids)

    def test_outcome_home_away_half_time_and_penalties(self):
        c = sample()
        self.assertEqual(mr.outcome(c),'VITTORIA')
        self.assertEqual(mr.outcome({**c,'team_side':'Ospiti'}),'SCONFITTA')
        self.assertEqual(mr.outcome({**c,'home_score':1}),'PAREGGIO')
        self.assertEqual(mr.outcome({**c,'match_status':'INTERVALLO'}),'INTERVALLO')
        c.update(home_score=2,away_score=2,match_status='DOPO I RIGORI',home_penalties=4,away_penalties=5)
        self.assertEqual(mr.outcome(c),'SCONFITTA')
        self.assertEqual(mr.outcome({**c,'team_side':'Ospiti'}),'VITTORIA')
        self.assertEqual(mr.outcome({**c,'home_penalties':5}),'RIGORI DA VERIFICARE')

    def test_animation_finishes_with_all_layers(self):
        prepared = mr.scene(sample(),LOGO,render_scale=1)
        final = mr.compose(prepared,animated=False)
        self.assertIsNone(ImageChops.difference(mr.compose(prepared,t=4),final).getbbox())
        self.assertIsNotNone(ImageChops.difference(mr.compose(prepared,t=0),final).getbbox())

    def test_video_formats_and_odd_dimension_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            for fmt,height in mr.FORMATS.items():
                c = switch_result_format(sample(),fmt)
                path = Path(directory)/'result.mp4'
                calls = []
                mr.render_video(c,LOGO,None,path,fps=12,duration=.3,scale=1,progress_callback=calls.append)
                reader = imageio.get_reader(path)
                try:
                    frame = reader.get_data(0)
                    self.assertEqual(frame.shape[:2],(height+(height%2),540))
                finally:
                    reader.close()
                self.assertEqual(calls[-1],1)
            c = switch_result_format(sample(),'Post 4:5')
            mr.render_video(c,LOGO,None,path,fps=12,duration=.3,scale=2)
            reader=imageio.get_reader(path)
            try:self.assertEqual(reader.get_data(0).shape[:2],(1350,1080))
            finally:reader.close()


class WorkflowTests(unittest.TestCase):
    def test_eight_presets_preserve_data_and_are_non_mutating(self):
        self.assertEqual(len(PRESETS),8)
        for template in ('Starting 7','Matchday Screen','Match Result'):
            c = defaults(template)
            c['font_choice']='font:example';c['locked_layers']=['title']
            original = copy.deepcopy(c)
            for preset in PRESETS:
                styled=apply_preset(template,c,preset)
                for field in ('positions','players','home_score','away_score','home_name','away_name','logo_id','home_logo_id','date','title','font_choice','locked_layers','export_format'):
                    if field in c:self.assertEqual(styled[field],c[field],(template,preset,field))
            self.assertEqual(c,original)

    def test_presets_have_distinct_rendered_results_for_all_templates(self):
        for template,module in [('Starting 7',r),('Matchday Screen',m),('Match Result',mr)]:
            hashes = set()
            for preset in PRESETS:
                c=apply_preset(template,defaults(template),preset)
                scene=module.scene(c,LOGO,render_scale=1)
                hashes.add(hashlib.sha256(module.compose(scene,animated=False).tobytes()).hexdigest())
            self.assertEqual(len(hashes),8,template)

    def test_format_switch_remembers_each_layout(self):
        c=sample();c['positions']['score']=[210,470]
        c=switch_result_format(c,'Post 1:1')
        self.assertEqual(c['positions']['score'],[270,276])
        c['positions']['score']=[240,270]
        c=switch_result_format(c,'Story 9:16')
        self.assertEqual(c['positions']['score'],[210,470])
        c=sanitize_config('Match Result',json.loads(json.dumps(c)))
        c=switch_result_format(c,'Post 1:1')
        self.assertEqual(c['positions']['score'],[240,270])

    def test_schema_bounds_and_bare_square_import(self):
        c=sanitize_config('Match Result',{'home_score':-8,'away_score':900,'home_penalties':float('inf'),
            'locked_layers':['score','score','unknown',{}],'export_format':'Post 1:1','footer':'#NUOVOHASHTAG',
            'layouts':{'Post 4:5':{'score':[900,-4]},'invalid':{}}})
        self.assertEqual(c['home_score'],0);self.assertEqual(c['away_score'],99)
        self.assertEqual(c['home_penalties'],0);self.assertEqual(c['locked_layers'],['score'])
        self.assertEqual(c['positions']['score'],[270,276])
        self.assertEqual(c['layouts']['Post 4:5']['score'],[540,0])
        self.assertEqual(c['footer'],'#NUOVOHASHTAG')
        self.assertNotIn('invalid',c['layouts'])

    def test_backward_compatible_library_and_new_project(self):
        library=empty_library()
        for template in ('Starting 7','Matchday Screen','Match Result'):
            c=defaults(template)
            for key in ('locked_layers','preset_id','pattern'):c.pop(key,None)
            library['projects'][template]={'name':'Test','template':template,'config':c}
        result,messages=validate_library(library)
        self.assertFalse(messages)
        self.assertEqual(len(result['projects']),3)
        self.assertEqual(result['projects']['Match Result']['config']['locked_layers'],[])

    def test_matchday_transfer_resets_result_and_preserves_assets(self):
        md=apply_preset('Matchday Screen',defaults('Matchday Screen'),'night')
        md.update(home_name='CASA',away_name='OSPITI',date='18/10/2026',font_choice='font:custom',away_logo_id='logo:custom',competition='COPPA',round_label='SEMIFINALE')
        result=matchday_to_result(md)
        for key in ('home_name','away_name','date','font_choice','away_logo_id','competition','round_label'):
            self.assertEqual(result[key],md[key])
        self.assertEqual(result['accent'],md['pink'])
        self.assertEqual(result['home_score'],0)
        self.assertEqual(result['scorers_home'],'')

    def test_preflight_clipping_and_incomplete_data(self):
        c=switch_result_format(sample(),'Post 1:1')
        c['positions']['footer']=[270,539]
        c['scorers_home']='\n'.join(['Rossi']*7)
        warnings=preflight('Match Result',c,mr.scene(c,LOGO,render_scale=1))
        self.assertTrue(any('fuori' in w for w in warnings))
        self.assertTrue(any('sei righe' in w for w in warnings))
        self.assertTrue(preflight('Match Result',defaults('Match Result')))
        c.update(match_status='DOPO I RIGORI')
        self.assertTrue(any('rigori' in w for w in preflight('Match Result',c)))

    def test_caption_uses_actual_data_and_preserves_all_scorers(self):
        c=sample();c['scorers_home']='\n'.join('Marcatore '+str(i) for i in range(8))
        caption=build_caption('Match Result',c)
        self.assertIn('FLAMINGOS 3 - 1 SPORTING CLUB',caption)
        self.assertIn('Marcatore 7',caption)
        self.assertIn('MVP: MARCO ROSSI',caption)
        self.assertNotIn('MVP:',build_caption('Match Result',{**c,'show_mvp':False}))
        c.update(match_status='DOPO I RIGORI',home_penalties=5,away_penalties=4)
        self.assertIn('Rigori: 5 - 4',build_caption('Match Result',c))
        self.assertIn('vs',build_caption('Matchday Screen',defaults('Matchday Screen')))
        self.assertIn('1. PORTIERE',build_caption('Starting 7',defaults('Starting 7')))

    def test_signatures_do_not_make_old_downloads_look_current(self):
        c=sample();sig=signature(c,LOGO)
        self.assertNotEqual(sig,signature({**c,'home_score':7},LOGO))
        self.assertNotEqual(sig,signature({**c,'png_quality':'Standard'},LOGO))
        self.assertEqual(sig,signature({**c,'duration':15,'locked_layers':['score']},LOGO))
        self.assertNotEqual(signature(c,LOGO,video=True),signature({**c,'fps':12},LOGO,video=True))

    def test_pack_contains_three_correct_pngs_and_notes(self):
        c=sample();c['png_quality']='Standard'
        before=copy.deepcopy(c)
        data,notes=export_pack('Match Result',c,LOGO)
        self.assertEqual(before,c)
        self.assertFalse(notes)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            pngs=[name for name in archive.namelist() if name.endswith('.png')]
            self.assertEqual(len(pngs),3)
            dimensions={Image.open(io.BytesIO(archive.read(name))).size for name in pngs}
            self.assertEqual(dimensions,{(1080,1920),(1080,1350),(1080,1080)})
            self.assertIn('LEGGIMI.txt',archive.namelist())

    def test_filename_is_safe_and_descriptive(self):
        c=sample();c['away_name']='../Sporting / Club?'
        name=export_basename('Match Result',c)
        self.assertNotIn('/',name);self.assertNotIn('..',name)
        self.assertIn('sporting-club',name)
        self.assertIn('18-10-2026',name)

    def test_invalid_preset_and_format_rejected(self):
        with self.assertRaises(ValueError):apply_preset('Match Result',sample(),'missing')
        with self.assertRaises(ValueError):switch_result_format(sample(),'cinema')


if __name__=='__main__':unittest.main()
