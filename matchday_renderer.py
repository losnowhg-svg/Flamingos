"""Native-resolution Matchday Screen CRT. Original supplied photographic shell retained."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

from render_utils import ScaledDraw, checked_scale, safe_positions
from scene_styles import atmosphere
from renderer import (W, H, Layer, DEFAULT_PINK, DEFAULT_WHITE, clean_logo,
                      composite_layer, text_image, text_runs, rgb, progress,
                      encode_png, video_writer, video_settings)

ROOT = Path(__file__).resolve().parent
DEFAULT_POSITIONS = {
    'title': (270, 348), 'date': (270, 376), 'home_logo': (166, 475),
    'away_logo': (374, 475), 'vs': (270, 481), 'home_name': (166, 579),
    'away_name': (374, 579), 'kickoff': (270, 629), 'venue': (270, 652),
}
LAYER_NAMES = {'title': 'Titolo', 'date': 'Data', 'home_logo': 'Stemma Flamingos',
               'away_logo': 'Stemma avversari', 'vs': 'VS', 'home_name': 'Nome Flamingos',
               'away_name': 'Nome avversari', 'kickoff': 'Orario inizio', 'venue': 'Campo'}
FEED_CROP = (0, 210, 540, 750)


def _pixel_box(draw, rect, border=(90, 223, 246), fill=(6, 12, 26), thickness=2, bevel=6):
    x1, y1, x2, y2 = rect
    b, n = bevel, thickness
    draw.polygon([(x1+b,y1),(x2-b,y1),(x2,y1+b),(x2,y2-b),
                  (x2-b,y2),(x1+b,y2),(x1,y2-b),(x1,y1+b)], fill=(*border,255))
    draw.polygon([(x1+b,y1+n),(x2-b,y1+n),(x2-n,y1+b),(x2-n,y2-b),
                  (x2-b,y2-n),(x1+b,y2-n),(x1+n,y2-b),(x1+n,y1+b)], fill=(*fill,255))


@lru_cache(maxsize=1)
def _shell():
    with Image.open(ROOT/'assets'/'matchday_crt.png') as im:
        return im.convert('RGB')


@lru_cache(maxsize=3)
def background(cyan_hex='#79DCF7', render_scale=2):
    s = checked_scale(render_scale)
    cyan, sh = rgb(cyan_hex, (121,220,247)), _shell()
    # Only the photographic background is resized; panels and typography are native.
    dark = sh.resize((W*s,H*s), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(50*s))
    im = ImageEnhance.Brightness(dark).enhance(.26).convert('RGBA')
    glow = Image.new('RGBA', im.size)
    gd = ScaledDraw(glow,s)
    gd.rectangle((85,183,455,187), fill=(*cyan,65))
    gd.rectangle((85,770,455,773), fill=(247,76,144,70))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18*s)))
    tv = sh.resize((520*s,520*s),Image.Resampling.LANCZOS).convert('RGBA')
    im.alpha_composite(tv,(10*s,220*s))
    dr = ScaledDraw(im,s)
    for rect in [(115,322,425,394),(91,559,242,600),(297,559,449,600),(93,608,448,672)]:
        _pixel_box(dr,rect,border=cyan,fill=(5,13,31),thickness=1.4,bevel=5)
    return im


def normalized_positions(config):
    return safe_positions(config,DEFAULT_POSITIONS)


def _decorate_text(asset, render_scale=1):
    if asset is None:
        return None
    s = render_scale
    # A small clean drop shadow, instead of repeatedly resampling outlined glyphs.
    image = Image.new('RGBA',(asset.width+4*s,asset.height+4*s))
    under = Image.new('RGBA',asset.size,(4,9,19,0))
    under.putalpha(asset.getchannel('A').point(lambda a: round(a*.80)))
    image.alpha_composite(under,(2*s,2*s))
    image.alpha_composite(asset,(s,s))
    return image


def _name_text(value,style,size,color,font_bytes,s=1):
    value = str(value).strip()[:42]
    if not value:
        return None
    words = value.split()
    if len(value)>13 and len(words)>1:
        # Balance word lengths, then fit each line using the original font outlines.
        split = min(range(1,len(words)), key=lambda i: abs(len(' '.join(words[:i]))-len(' '.join(words[i:]))))
        lines = [' '.join(words[:split]), ' '.join(words[split:])]
        rows = [text_image(line,style,max(9,size-2),color,139,font_bytes,s,14) for line in lines]
        width, height = max(row.width for row in rows), sum(row.height for row in rows)+2*s
        image = Image.new('RGBA',(width,height))
        y = 0
        for row in rows:
            image.alpha_composite(row,((width-row.width)//2,y)); y += row.height+2*s
        return _decorate_text(image,s)
    return _decorate_text(text_image(value,style,size,color,138,font_bytes,s,30),s)


def _vs_sprite(color,style,font_bytes,size=44,s=1):
    image = Image.new('RGBA',(94*s,115*s))
    d = ScaledDraw(image,s)
    for x,y in [(11,15),(17,24),(77,15),(71,24),(10,89),(19,80),(79,89),(71,80)]:
        d.rectangle((x,y,x+3,y+3),fill=(*color,255))
    inner = _decorate_text(text_image('VS',style,size,color,86,font_bytes,s,62),s)
    if inner:
        image.alpha_composite(inner,((image.width-inner.width)//2,(image.height-inner.height)//2))
    return image


def _unknown_shield(s=1):
    image = Image.new('RGBA',(106*s,147*s))
    d = ScaledDraw(image,s)
    d.polygon([(7,6),(99,6),(99,112),(53,141),(7,112)],fill=(8,11,23,255),outline=(111,224,255,255),width=2)
    d.polygon([(17,15),(89,15),(89,105),(53,127),(17,105)],outline=(255,216,104,255),width=1.5)
    question = text_image('?','Sans Bold',50,(255,211,101),60,None,s)
    image.alpha_composite(question,((image.width-question.width)//2,(image.height-question.height)//2))
    return image


def get_layers(config,home_logo,away_logo=None,font_bytes=None,render_scale=1):
    s = checked_scale(render_scale)
    style = config.get('text_style',config.get('font_choice','Sans Bold'))
    pink = rgb(config.get('pink','#F268A8'),DEFAULT_PINK)
    cyan = rgb(config.get('cyan','#79DCF7'),(121,220,247))
    white = rgb(config.get('white','#F6F4FC'),DEFAULT_WHITE)
    yellow = rgb(config.get('yellow','#FFC963'),(255,201,99))
    layers = []
    for id_, value, size, color, width, height in [
        ('title',config.get('title','MATCHDAY SCREEN'),config.get('title_size',27),white,294,29),
        ('date',config.get('date','GG/MM/AAAA'),config.get('title_size',27)-1,pink,260,23),
    ]:
        asset = _decorate_text(text_image(value,style,size,color,width,font_bytes,s,height),s)
        if asset: layers.append(Layer(id_,LAYER_NAMES[id_],asset))
    for side,data in [('home',home_logo),('away',away_logo)]:
        image = clean_logo(data,config.get(f'{side}_logo_size',103),config.get(f'{side}_clear_white',True),s) if data else _unknown_shield(s)
        layers.append(Layer(f'{side}_logo',LAYER_NAMES[f'{side}_logo'],image))
    layers.append(Layer('vs','VS',_vs_sprite(yellow,style,font_bytes,config.get('vs_size',43),s)))
    for side,color,default in [('home',pink,'FLAMINGOS'),('away',cyan,'AVVERSARI')]:
        image = _name_text(config.get(f'{side}_name',default),style,config.get('label_size',18),color,font_bytes,s)
        if image: layers.append(Layer(f'{side}_name',LAYER_NAMES[f'{side}_name'],image))
    for id_,parts in [
        ('kickoff',[(config.get('kickoff_label',"CALCIO D'INIZIO:")+' ',white),(config.get('kickoff','HH:MM'),yellow)]),
        ('venue',[(config.get('venue_label','LUOGO:')+' ',cyan),(config.get('venue','VIA FORNACI, 82'),yellow)]),
    ]:
        image = _decorate_text(text_runs(parts,style,config.get('info_size',16),328,font_bytes,s,19),s)
        if image: layers.append(Layer(id_,LAYER_NAMES[id_],image))
    return layers


def scene(config,home_logo,away_logo=None,font_bytes=None,render_scale=2):
    s = checked_scale(render_scale)
    if config.get('backdrop','CRT originale') == 'CRT originale':
        base = background(config.get('cyan','#79DCF7'),s).copy()
    else:
        cyan = rgb(config.get('cyan'),(121,220,247))
        pink = rgb(config.get('pink'),DEFAULT_PINK)
        panel = rgb(config.get('panel_color'),(32,26,46))
        base = atmosphere(W,H,rgb(config.get('background'),(16,14,26)),pink,cyan,
                          config.get('pattern','Pulito'),s,config.get('texture',25))
        draw = ScaledDraw(base,s)
        draw.rounded_rectangle((20,236,520,724),radius=24,fill=(*panel,245),outline=(*cyan,160),width=1.5)
        draw.line((44,268,146,268),fill=(*pink,255),width=4)
        draw.line((44,693,496,693),fill=(*cyan,110),width=1)
    return base,get_layers(config,home_logo,away_logo,font_bytes,s),normalized_positions(config)


def compose(prepared,t=999,animated=True):
    base,layers,positions = prepared
    canvas = base.copy()
    timeline = {'title':.2,'date':.6,'home_logo':1.25,'away_logo':1.55,'vs':2.05,
                'home_name':2.6,'away_name':2.9,'kickoff':3.4,'venue':3.75}
    for layer in layers:
        a = progress(t,timeline.get(layer.id,0),.46) if animated else 1
        drop = (1-a)*(24 if layer.id in ('home_logo','away_logo') else 11)
        composite_layer(canvas,layer,positions[layer.id],a,drop)
    if animated:
        s = canvas.width//W
        y = 310+((t*.9)%1)*350
        overlay = Image.new('RGBA',canvas.size)
        ScaledDraw(overlay,s).line((71,y,469,y),fill=(90,225,245,14),width=1)
        canvas.alpha_composite(overlay)
    return canvas.convert('RGB')


def output_image(image,format='Story 9:16',scale=2):
    scale = checked_scale(scale)
    source_scale = image.width/W
    if format.startswith('Post'):
        image = image.crop(tuple(round(v*source_scale) for v in FEED_CROP))
        target = (W*scale,W*scale)
    else:
        target = (W*scale,H*scale)
    if image.size != target:
        image = image.resize(target,Image.Resampling.LANCZOS)
    return image


def png_bytes(config,home_logo,away_logo=None,font_bytes=None,format='Story 9:16',scale=2,supersample=2):
    scale = checked_scale(scale)
    ss = checked_scale(supersample,2)
    prepared = scene(config,home_logo,away_logo,font_bytes,min(4,scale*ss))
    return encode_png(output_image(compose(prepared,animated=False),format,scale))


def render_video(config,home_logo,away_logo,path,font_bytes=None,fps=24,duration=8,format='Story 9:16',scale=2,progress_callback=None):
    fps,duration = video_settings(fps,duration,scale)
    prepared = scene(config,home_logo,away_logo,font_bytes,scale)
    writer = video_writer(path,fps)
    count = round(duration*fps)
    try:
        for i in range(count):
            writer.append_data(np.asarray(output_image(compose(prepared,i/fps,True),format,scale)))
            if progress_callback and (i%fps==0 or i==count-1):
                progress_callback((i+1)/count)
    finally:
        writer.close()
    return str(path)
