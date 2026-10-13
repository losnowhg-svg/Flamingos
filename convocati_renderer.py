"""Match call-up list for seven-a-side: starters + bench, roles and logistics."""
from __future__ import annotations
from PIL import Image
from render_utils import ScaledDraw, checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, text_runs, rgb
from matchday_renderer import _decorate_text
from crt_presets import background, output_image
from crt_common import compose, export_png, export_video

MAX_PLAYERS=18
ROLES=('P','D','C','A','-')
DEFAULT_POSITIONS={
    'logo':(112,351), 'title':(299,341), 'team':(299,366), 'match':(270,405),
    'meeting':(270,638), 'venue':(270,659), 'legend':(270,615),
    **{f'player_{i}':(174 if i%2==0 else 366,433+(i//2)*21) for i in range(MAX_PLAYERS)}
}
LAYER_NAMES={'logo':'Stemma','title':'Titolo convocati','team':'Nome squadra','match':'Partita e data',
             'meeting':'Ritrovo e calcio di inizio','venue':'Campo / indirizzo','legend':'Legenda ruoli e capitano',
             **{f'player_{i}':f'Convocato {i+1}' for i in range(MAX_PLAYERS)}}


def normalized_positions(config):
    return safe_positions(config,DEFAULT_POSITIONS)


def make_player(entry,index,config,font_bytes,s):
    style=config.get('text_style',config.get('font_choice','CRT Terminal'))
    pink=rgb(config.get('pink','#F268A8'));cyan=rgb(config.get('cyan','#79DCF7'))
    white=rgb(config.get('white','#F6F4FC'));yellow=rgb(config.get('yellow','#FFC963'))
    im=Image.new('RGBA',(178*s,19*s));d=ScaledDraw(im,s)
    d.rectangle((0,0,178,18),fill=(6,14,27,245))
    d.rectangle((0,0,21,18),fill=(*pink,255))
    number=text_image(str(entry.get('number',index+1)),style,11,(9,11,22),18,font_bytes,s,12)
    if number:im.alpha_composite(number,(round(10.5*s-number.width/2),round(9*s-number.height/2)))
    captain=bool(entry.get('captain',False))
    name=str(entry.get('name','GIOCATORE'))
    row=text_image(name,style,config.get('name_size',11),white,128,font_bytes,s,12)
    if row:im.alpha_composite(row,(27*s,round(9*s-row.height/2)))
    # Captain is shown as an asterisk, avoiding ambiguity with the C midfield role.
    tag='*' if captain else str(entry.get('role','-'))
    role=text_image(tag,style,9,yellow if captain else cyan,12,font_bytes,s,10)
    if role:im.alpha_composite(role,(round(169*s-role.width/2),round(9*s-role.height/2)))
    return Layer(f'player_{index}',f"{index+1}. {name}",im,sequence=index)


def get_layers(config,home_logo,away_logo=None,font_bytes=None,render_scale=1):
    s=checked_scale(render_scale)
    style=config.get('text_style',config.get('font_choice','CRT Terminal'))
    pink=rgb(config.get('pink','#F268A8'));cyan=rgb(config.get('cyan','#79DCF7'))
    white=rgb(config.get('white','#F6F4FC'));yellow=rgb(config.get('yellow','#FFC963'))
    layers=[Layer('logo','Stemma',clean_logo(home_logo,config.get('logo_size',45),config.get('remove_white',True),s))]
    items=[
        ('legend','P PORTIERE / D DIF. / C CENTRO / A ATT. / * CAP.',6,cyan,356,7),
        ('title',config.get('title','CONVOCATI'),config.get('title_size',25),white,268,26),
        ('team',config.get('team_name','FLAMINGOS'),config.get('team_size',12),pink,272,15),
        ('match',' / '.join(v for v in [str(config.get('opponent','AVVERSARI')),str(config.get('date','GG/MM/AAAA'))] if v.strip()),config.get('info_size',11),cyan,356,16),
        ('venue',config.get('venue','CAMPO / INDIRIZZO'),config.get('info_size',11),yellow,354,13),
    ]
    for id_,value,size,col,width,height in items:
        im=_decorate_text(text_image(value,style,size,col,width,font_bytes,s,height),s)
        if im:layers.append(Layer(id_,LAYER_NAMES[id_],im))
    parts=[('RITROVO ',white),(str(config.get('meeting_time','HH:MM')),yellow),(' / KICK OFF ',white),(str(config.get('kickoff','HH:MM')),yellow)]
    im=_decorate_text(text_runs(parts,style,config.get('info_size',11),354,font_bytes,s,13),s)
    if im:layers.append(Layer('meeting',LAYER_NAMES['meeting'],im))
    count=max(1,min(MAX_PLAYERS,int(config.get('roster_count',12))))
    for i,entry in enumerate(config.get('roster',[])[:count]):
        layers.append(make_player(entry,i,config,font_bytes,s))
    return layers


def scene(config,home_logo,away_logo=None,font_bytes=None,render_scale=2):
    s=checked_scale(render_scale)
    return background(config,'convocati',s),get_layers(config,home_logo,away_logo,font_bytes,s),normalized_positions(config)


def png_bytes(config,home_logo,away_logo=None,font_bytes=None,format='Story 9:16',scale=2,supersample=2):
    return export_png(scene,config,home_logo,away_logo,font_bytes,format,scale,supersample)


def render_video(config,home_logo,away_logo,path,font_bytes=None,fps=24,duration=8,format='Story 9:16',scale=2,progress_callback=None):
    return export_video(scene,config,home_logo,away_logo,path,font_bytes,fps,duration,format,scale,progress_callback)
