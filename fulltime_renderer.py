"""Full Time: same CRT as Matchday, editable score, penalties and scorers."""
from __future__ import annotations
from PIL import Image
from render_utils import checked_scale, safe_positions
from renderer import Layer, clean_logo, text_image, rgb
from matchday_renderer import _decorate_text, _name_text, _unknown_shield
import title_fx
from crt_presets import background, output_image
from crt_common import compose, export_png, export_video

DEFAULT_POSITIONS = {
    'title':(270,346), 'details':(270,375), 'home_logo':(164,448),
    'away_logo':(376,448), 'score':(270,450), 'penalties':(270,491),
    'home_name':(164,521), 'away_name':(376,521), 'result':(270,557),
    'home_scorers':(174,625), 'away_scorers':(366,625),
}
LAYER_NAMES = {'title':'Titolo Full Time','details':'Competizione e data','home_logo':'Stemma casa',
               'away_logo':'Stemma avversari','score':'Risultato','penalties':'Risultato rigori',
               'home_name':'Squadra casa','away_name':'Squadra ospite','result':'Esito partita',
               'home_scorers':'Marcatori casa','away_scorers':'Marcatori ospiti'}


def normalized_positions(config):
    return safe_positions(config,DEFAULT_POSITIONS)


def result_text(config):
    if not config.get('show_result',True):return ''
    a,b=int(config.get('home_score',0)),int(config.get('away_score',0))
    penalties=config.get('show_penalties',False) and a==b
    if penalties:
        a,b=int(config.get('home_penalties',0)),int(config.get('away_penalties',0))
    if a==b:
        return 'RIGORI IN PARITA' if penalties else 'PAREGGIO'
    won=(a>b) if config.get('our_side','Casa')=='Casa' else (b>a)
    return ('VITTORIA' if won else 'SCONFITTA')+(' AI RIGORI' if penalties else '')


def scorer_lines(value):
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _scorers(value,label,color,white,style,size,font_bytes,s):
    im=Image.new('RGBA',(174*s,86*s))
    head=text_image(label,style,9,color,160,font_bytes,s,10)
    if head:im.alpha_composite(head,((im.width-head.width)//2,1*s))
    lines=scorer_lines(value)[:6]
    count=max(1,len(lines))
    line_height=min(size,12 if count<=4 else 9)
    step=min(18,(64-line_height)/max(1,count-1))
    for i,line in enumerate(lines or ['-']):
        row=text_image(line,style,size,white,164,font_bytes,s,line_height)
        if row:im.alpha_composite(row,((im.width-row.width)//2,round((20+i*step)*s)))
    return im


def get_layers(config,home_logo,away_logo=None,font_bytes=None,render_scale=1):
    s=checked_scale(render_scale)
    style=config.get('text_style',config.get('font_choice','CRT Terminal'))
    pink=rgb(config.get('pink','#F268A8'));cyan=rgb(config.get('cyan','#79DCF7'))
    yellow=rgb(config.get('yellow','#FFC963'));white=rgb(config.get('white','#F6F4FC'))
    layers=[]
    def text(id_,value,size,color,width,height):
        raw=text_image(value,style,size,color,width,font_bytes,s,height)
        im=title_fx.title(raw,config,s) if id_=='title' else _decorate_text(raw,s)
        if im:layers.append(Layer(id_,LAYER_NAMES[id_],im))
    text('title',config.get('title','FULL TIME'),config.get('title_size',30),white,306,30)
    details=' / '.join(str(config.get(key,'')) for key in ('competition','date') if str(config.get(key,'')).strip())
    text('details',details,config.get('info_size',12),pink,302,15)
    for side,data in (('home',home_logo),('away',away_logo)):
        size=config.get(side+'_logo_size',66)
        im=clean_logo(data,size,config.get(side+'_clear_white',True),s) if data else _unknown_shield(s)
        if not data:
            im.thumbnail((size*s,round(size*1.42)*s),Image.Resampling.LANCZOS)
        layers.append(Layer(side+'_logo',LAYER_NAMES[side+'_logo'],im))
    text('score',f"{config.get('home_score',0)}-{config.get('away_score',0)}",config.get('score_size',54),yellow,142,63)
    if layers and layers[-1].id=='score' and config.get('animation','Retro')=='Retro':
        # Frames for the score counting up in videos.
        a,b=int(config.get('home_score',0)),int(config.get('away_score',0))
        steps=max(a,b); n=min(steps,10)
        variants=[]
        for i in sorted({round(k*steps/n) for k in range(n+1)} if n else {0}):
            im=_decorate_text(text_image(f'{min(i,a)}-{min(i,b)}',style,config.get('score_size',54),yellow,142,font_bytes,s,63),s)
            if im:variants.append(im)
        layers[-1].variants=variants or [layers[-1].image]
    if config.get('show_penalties',False) and config.get('home_score',0)==config.get('away_score',0):
        text('penalties',f"{config.get('home_penalties',0)}-{config.get('away_penalties',0)} D.C.R.",10,white,142,12)
    ours='away' if config.get('our_side','Casa')=='Ospiti' else 'home'
    side_color={'home':pink if ours=='home' else cyan,'away':pink if ours=='away' else cyan}
    for side,col in (('home',side_color['home']),('away',side_color['away'])):
        im=_name_text(config.get(side+'_name',''),style,config.get('label_size',15),col,font_bytes,s)
        if im:layers.append(Layer(side+'_name',LAYER_NAMES[side+'_name'],im))
    text('result',result_text(config),config.get('result_size',16),yellow,330,22)
    for side,col,label in (('home',side_color['home'],'MARCATORI CASA'),('away',side_color['away'],'MARCATORI OSPITI')):
        if config.get('show_scorers',True):
            im=_scorers(config.get(side+'_scorers',''),label,col,white,style,config.get('scorer_size',11),font_bytes,s)
            layers.append(Layer(side+'_scorers',LAYER_NAMES[side+'_scorers'],im))
    return layers


def outcome(config):
    """('win'|'draw'|'loss', our goals) from our side, penalties included."""
    a,b=int(config.get('home_score',0)),int(config.get('away_score',0))
    ours_home=config.get('our_side','Casa')=='Casa'
    goals=a if ours_home else b
    if a==b and config.get('show_penalties',False):
        a,b=int(config.get('home_penalties',0)),int(config.get('away_penalties',0))
    if a==b:
        return 'draw',goals
    return ('win' if (a>b)==ours_home else 'loss'),goals


def scene(config,home_logo,away_logo=None,font_bytes=None,render_scale=2):
    import themes
    from crt_common import finish
    s=checked_scale(render_scale)
    config=themes.effective(config)
    import layouts
    prepared=(background(config,layouts.panel_key('fulltime' if config.get('show_scorers',True) else 'fulltime_clean','Full Time',config),s),get_layers(config,home_logo,away_logo,font_bytes,s),normalized_positions(config))
    prepared[0].info['outcome'],prepared[0].info['our_goals']=outcome(config)
    return finish(prepared,config,'fulltime')


def png_bytes(config,home_logo,away_logo=None,font_bytes=None,format='Story 9:16',scale=2,supersample=2):
    return export_png(scene,config,home_logo,away_logo,font_bytes,format,scale,supersample)


def render_video(config,home_logo,away_logo,path,font_bytes=None,fps=24,duration=8,format='Story 9:16',scale=2,progress_callback=None):
    return export_video(scene,config,home_logo,away_logo,path,font_bytes,fps,duration,format,scale,progress_callback)
