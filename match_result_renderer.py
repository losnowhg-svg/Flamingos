"""Editable Match Result: independent Story, portrait feed and square layouts."""
from __future__ import annotations
from PIL import Image
import numpy as np

import renderer as r
from matchday_renderer import _unknown_shield
from render_utils import ScaledDraw, checked_scale, safe_positions
from scene_styles import atmosphere, blend

FORMATS = {'Story 9:16': 960, 'Post 4:5': 675, 'Post 1:1': 540}
LAYER_NAMES = {
    'competition': 'Competizione e giornata', 'title': 'Titolo', 'date': 'Data',
    'home_logo': 'Stemma casa', 'away_logo': 'Stemma ospiti',
    'home_name': 'Nome casa', 'away_name': 'Nome ospiti', 'score': 'Punteggio',
    'outcome': 'Stato ed esito', 'scorers_home': 'Marcatori casa',
    'scorers_away': 'Marcatori ospiti', 'mvp': 'MVP', 'footer': 'Pi\u00e8 di pagina',
}


def canvas_height(config):
    return FORMATS.get(config.get('export_format'), 960)


def default_positions(format='Story 9:16'):
    if format == 'Post 1:1':
        ys = [28, 60, 91, 155, 218, 276, 332, 406, 483, 520]
    elif format == 'Post 4:5':
        ys = [38, 81, 119, 208, 281, 354, 426, 513, 604, 647]
    else:
        ys = [79, 134, 184, 310, 408, 501, 597, 705, 839, 907]
    competition, title, date, logos, names, score, outcome, scorers, mvp, footer = ys
    return {'competition':(270,competition), 'title':(270,title), 'date':(270,date),
            'home_logo':(142,logos), 'away_logo':(398,logos),
            'home_name':(142,names), 'away_name':(398,names), 'score':(270,score),
            'outcome':(270,outcome), 'scorers_home':(144,scorers), 'scorers_away':(396,scorers),
            'mvp':(270,mvp), 'footer':(270,footer)}


DEFAULT_POSITIONS = default_positions()


def normalized_positions(config):
    return safe_positions(config, default_positions(config.get('export_format')), height=canvas_height(config))


def outcome(config):
    status = config.get('match_status', 'FINALE')
    if status == 'INTERVALLO':
        return 'INTERVALLO'
    home, away = int(config.get('home_score', 0)), int(config.get('away_score', 0))
    if status == 'DOPO I RIGORI' and home == away:
        home, away = int(config.get('home_penalties', 0)), int(config.get('away_penalties', 0))
        if home == away:
            return 'RIGORI DA VERIFICARE'
    if config.get('team_side') == 'Ospiti':
        home, away = away, home
    return 'VITTORIA' if home > away else 'SCONFITTA' if home < away else 'PAREGGIO'


def scorer_lines(value):
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _block(value, style, color, accent, panel, font_bytes, scale, compact=False, heading='', rows=1):
    lines = scorer_lines(value)
    if not lines:
        return None
    width, row_height = 218, 15 if compact else 18
    lines = lines[:6]
    height = 26 + max(len(lines),min(6,rows))*row_height
    image = Image.new('RGBA', (width*scale, height*scale))
    draw = ScaledDraw(image, scale)
    draw.rounded_rectangle((0,0,width-1,height-1), radius=8, fill=(*panel,240))
    title = r.text_image(heading,style,10,accent,width-20,font_bytes,scale,12)
    if title:
        image.alpha_composite(title,(10*scale,5*scale))
    for i, line in enumerate(lines):
        text = r.text_image(line[:80], style, 13 if compact else 15, color, width-20, font_bytes, scale, row_height-1)
        if text:
            image.alpha_composite(text,(10*scale,(22+i*row_height)*scale))
    return image


def get_layers(config, home_logo, away_logo=None, font_bytes=None, render_scale=1):
    s = checked_scale(render_scale)
    height = canvas_height(config)
    compact = height == 540
    style = config.get('text_style', config.get('font_choice', 'Sans Bold'))
    accent = r.rgb(config.get('accent'), r.DEFAULT_PINK)
    secondary = r.rgb(config.get('secondary'), (124,218,239))
    white = r.rgb(config.get('text_color'), r.DEFAULT_WHITE)
    panel = r.rgb(config.get('panel_color'), (32,26,46))
    muted = blend(white,panel,.25)
    layers = []

    def text(id_, value, size, color, width=460, max_height=None):
        asset = r.text_image(value,style,size,color,width,font_bytes,s,max_height)
        if asset:
            layers.append(r.Layer(id_,LAYER_NAMES[id_],asset))

    info = ' / '.join(str(config.get(k, '')).strip() for k in ('competition','round_label') if str(config.get(k,'')).strip())
    text('competition', info, 12 if compact else 14, accent, 468, 18)
    text('title', config.get('title','MATCH RESULT'), config.get('title_size',42), white, 462, 38 if compact else 54)
    text('date',config.get('date','GG/MM/AAAA'),13 if compact else 16,muted,460,20)
    for side, data in [('home',home_logo),('away',away_logo)]:
        size = config.get(f'{side}_logo_size',90)
        asset = r.clean_logo(data,size,config.get(f'{side}_clear_white',True),s).copy() if data else _unknown_shield(s)
        limit = 90 if compact else 118 if height == 675 else 160
        asset.thumbnail((130*s,limit*s),Image.Resampling.LANCZOS)
        layers.append(r.Layer(f'{side}_logo',LAYER_NAMES[f'{side}_logo'],asset))
        text(f'{side}_name',config.get(f'{side}_name','SQUADRA'),config.get('label_size',22),accent if side=='home' else secondary,218,28)
    # The score plate travels with the score; there is no fixed backdrop left behind.
    plate_h = 76 if compact else 102 if height==675 else 126
    plate = Image.new('RGBA',(460*s,plate_h*s))
    draw = ScaledDraw(plate,s)
    draw.rounded_rectangle((0,0,459,plate_h-1),radius=14,fill=(*panel,250),outline=(*accent,150),width=1)
    score = r.text_image(f"{config.get('home_score',0)} - {config.get('away_score',0)}",style,config.get('score_size',98),white,416,font_bytes,s,plate_h-18)
    if score:
        plate.alpha_composite(score,((plate.width-score.width)//2,(plate.height-score.height)//2))
    layers.append(r.Layer('score',LAYER_NAMES['score'],plate))
    status = str(config.get('match_status','FINALE'))
    label = outcome(config) if config.get('show_outcome', True) else status
    if config.get('show_outcome',True) and label != status:
        label += '  /  ' + status
    if status == 'DOPO I RIGORI':
        label += f"  ({config.get('home_penalties',0)}-{config.get('away_penalties',0)} rig.)"
    text('outcome',label,config.get('info_size',16),accent,460,24)
    rows = min(6,max(len(scorer_lines(config.get('scorers_home',''))),len(scorer_lines(config.get('scorers_away',''))),1))
    for side in ('home','away'):
        block = _block(config.get(f'scorers_{side}',''),style,white,accent if side=='home' else secondary,panel,font_bytes,s,compact,'MARCATORI CASA' if side=='home' else 'MARCATORI OSPITI',rows)
        if block:
            layers.append(r.Layer(f'scorers_{side}',LAYER_NAMES[f'scorers_{side}'],block))
    if config.get('show_mvp',True) and str(config.get('mvp','')).strip():
        text('mvp','MVP  /  '+str(config['mvp']),config.get('info_size',16),secondary,458,22)
    text('footer',config.get('footer','#FORZAFLAMINGOS'),12 if compact else 15,muted,462,20)
    return layers


def scene(config,home_logo,away_logo=None,font_bytes=None,render_scale=2):
    s = checked_scale(render_scale)
    height = canvas_height(config)
    accent = r.rgb(config.get('accent'),r.DEFAULT_PINK)
    secondary = r.rgb(config.get('secondary'),(124,218,239))
    bg = r.rgb(config.get('background'),(16,14,26))
    base = atmosphere(540,height,bg,accent,secondary,config.get('pattern','Pulito'),s,config.get('texture',25))
    draw = ScaledDraw(base,s)
    draw.line((28,10,142,10),fill=(*accent,255),width=3)
    draw.line((148,10,188,10),fill=(*secondary,255),width=3)
    draw.line((28,height-9,512,height-9),fill=(*accent,100),width=1)
    return base,get_layers(config,home_logo,away_logo,font_bytes,s),normalized_positions(config)


def compose(prepared,t=999,animated=True):
    base,layers,positions = prepared
    image = base.copy()
    times = {'competition':.05,'title':.25,'date':.5,'home_logo':.8,'away_logo':1.0,
             'home_name':1.25,'away_name':1.4,'score':1.65,'outcome':2.2,
             'scorers_home':2.55,'scorers_away':2.7,'mvp':3.1,'footer':3.35}
    for layer in layers:
        alpha = r.progress(t,times.get(layer.id,0),.45) if animated else 1
        r.composite_layer(image,layer,positions[layer.id],alpha,(1-alpha)*18)
    return image.convert('RGB')


def png_bytes(config,home_logo,away_logo=None,font_bytes=None,scale=2,supersample=2):
    scale = checked_scale(scale)
    ss = checked_scale(supersample,2)
    image = compose(scene(config,home_logo,away_logo,font_bytes,min(4,scale*ss)),animated=False)
    target = (540*scale,canvas_height(config)*scale)
    if image.size != target:
        image = image.resize(target,Image.Resampling.LANCZOS)
    return r.encode_png(image)


def render_video(config,home_logo,away_logo,path,font_bytes=None,fps=24,duration=8,scale=2,progress_callback=None):
    fps,duration = r.video_settings(fps,duration,scale)
    prepared = scene(config,home_logo,away_logo,font_bytes,scale)
    writer = r.video_writer(path,fps)
    count = round(duration*fps)
    try:
        for i in range(count):
            image = compose(prepared,i/fps,True)
            # H.264 yuv420p requires even dimensions; 540px 4:5 uses 540x676.
            if image.height % 2:
                padded = Image.new('RGB',(image.width,image.height+1))
                padded.paste(image,(0,0));padded.paste(image.crop((0,image.height-1,image.width,image.height)),(0,image.height))
                image = padded
            writer.append_data(np.asarray(image))
            if progress_callback and (i%fps==0 or i==count-1):
                progress_callback((i+1)/count)
    finally:
        writer.close()
    return str(path)
