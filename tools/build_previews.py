"""Build the actual renderer's demo catalogue; no external images or font files."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import renderer as r
from studio_state import defaults,MODULES
from crt_presets import PRESET_IDS,PRESETS,apply_preset,output_image


def demo(template):
    cfg=defaults(template)
    if template=='Full Time':
        cfg.update(home_score=4,away_score=2,home_scorers="ROSSI 12', 38'\nBIANCHI 26'\nVERDI 51'",
                   away_scorers="NERI 18'\nCONTI 45'",date='18/10/2026',away_name='ATLETICO',competition='CSI / GIORNATA 04')
    else:
        cfg.update(date='18/10/2026',kickoff='21:00',meeting_time='20:15',opponent='VS ATLETICO',
                   venue='CAMPO FORNACI / BRESCIA',roster_count=14)
        names=['ROSSI','BIANCHI','VERDI','NERI','RIVA','CONTI','FERRARI','MORETTI','ROMANO','GALLO',
               'COSTA','FONTANA','GRECO','RICCI','LONGHI','VILLA','COLOMBO','MARTINELLI']
        roles=['P','D','D','C','C','C','A','P','D','C','A','D','C','A','P','D','C','A']
        for index,person in enumerate(cfg['roster']):person.update(name=names[index],role=roles[index])
        cfg['roster'][3]['captain']=True
    return cfg


def build(examples=None):
    logo=(ROOT/'assets/flamingos_logo.jpg').read_bytes()
    canvas=Image.new('RGB',(1680,1400),(9,11,20))
    draw=ImageDraw.Draw(canvas)
    draw.text((36,28),'FLAMINGOS / CRT SEASON PACK',font=r.standard_font(39),fill=(246,237,247))
    draw.text((38,83),'FULL TIME + CONVOCATI     /     6 PRESET     /     CRT TERMINAL + CRT SCOREBOARD',
              font=r.standard_font(18),fill=(172,180,201))
    for index,preset in enumerate(PRESET_IDS):
        template='Convocati' if preset=='tactics' else 'Full Time'
        cfg=apply_preset(demo(template),preset,typography=True)
        module=MODULES[template]
        im=output_image(module.compose(module.scene(cfg,logo,render_scale=2),animated=False),'Post 1:1',2)
        x=36+(index%3)*544;y=158+(index//3)*598
        draw.text((x,y),PRESETS[preset]['name'].upper(),font=r.standard_font(22),fill=(237,227,242))
        canvas.paste(im.resize((520,520),Image.Resampling.LANCZOS),(x,y+36))
        if examples:
            examples.mkdir(parents=True,exist_ok=True)
            im.save(examples/(template.lower().replace(' ','_')+'_'+preset+'.png'))
    draw.text((38,1364),'ESEMPI DI IMPAGINAZIONE / NOMI, DATE E RISULTATI DIMOSTRATIVI',font=r.standard_font(16),fill=(166,174,194))
    target=ROOT/'assets/preset_catalog.jpg';canvas.save(target,quality=93,subsampling=0)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--examples',type=Path)
    args=parser.parse_args();print(build(args.examples))
