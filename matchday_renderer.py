"""Retro CRT matchday artwork for Flamingos Studio.

Renders reusable 9:16 stories and 1:1 feed posts using a cleaned CRT photo
supplied by the Flamingos team. No external image APIs are required.
"""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from renderer import (
    W, H, Layer, DEFAULT_PINK, DEFAULT_WHITE, clean_logo, composite_layer,
    text_image, rgb, progress,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_POSITIONS = {
    'title': (270, 348),
    'date': (270, 376),
    'home_logo': (166, 475),
    'away_logo': (374, 475),
    'vs': (270, 481),
    'home_name': (166, 579),
    'away_name': (374, 579),
    'kickoff': (270, 629),
    'venue': (270, 652),
}
LAYER_NAMES = {
    'title': 'Titolo', 'date': 'Data', 'home_logo': 'Stemma Flamingos',
    'away_logo': 'Stemma avversari', 'vs': 'VS', 'home_name': 'Nome Flamingos',
    'away_name': 'Nome avversari', 'kickoff': 'Orario inizio', 'venue': 'Campo',
}
FEED_CROP = (0, 210, 540, 750)


def _pixel_box(draw, rect, border=(90, 223, 246), fill=(6, 12, 26), thickness=2, bevel=6):
    x1, y1, x2, y2 = rect
    b = bevel
    poly = [(x1+b, y1), (x2-b, y1), (x2, y1+b), (x2, y2-b),
            (x2-b, y2), (x1+b, y2), (x1, y2-b), (x1, y1+b)]
    draw.polygon(poly, fill=(*border, 255))
    n = thickness
    inner = [(x1+b, y1+n), (x2-b, y1+n), (x2-n, y1+b), (x2-n, y2-b),
             (x2-b, y2-n), (x1+b, y2-n), (x1+n, y2-b), (x1+n, y1+b)]
    draw.polygon(inner, fill=(*fill, 255))
    # Simple low-resolution specular highlight.
    draw.line((x1+b+4, y1+n+1, x2-b-5, y1+n+1), fill=(*border, 82), width=1)


@lru_cache(maxsize=2)
def _shell():
    return Image.open(ROOT/'assets'/'matchday_crt.png').convert('RGB')


@lru_cache(maxsize=6)
def background(cyan_hex='#5FCFF4'):
    """Composited empty monitor, photo bezel, blue grid and edit-safe panels."""
    cyan = rgb(cyan_hex, (95, 207, 244))
    sh = _shell()
    dark = sh.resize((540, 960), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(50))
    dark = ImageEnhance.Brightness(dark).enhance(.26)
    im = Image.new('RGBA', (W, H), (6, 8, 16, 255))
    im.alpha_composite(dark.convert('RGBA'))
    # A subdued analog scan glow above/below TV for stories.
    glow = Image.new('RGBA', (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.rectangle((85,183,455,187), fill=(*cyan, 65))
    gd.rectangle((85,770,455,773), fill=(247,76,144,70))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    tv = sh.resize((520,520), Image.Resampling.LANCZOS).convert('RGBA')
    im.alpha_composite(tv, (10, 220))
    dr = ImageDraw.Draw(im)
    _pixel_box(dr,(125,322,435,394),border=cyan, fill=(5,13,31),thickness=2,bevel=5)
    _pixel_box(dr,(91,559,242,600),border=cyan, fill=(5,13,31),thickness=2,bevel=5)
    _pixel_box(dr,(297,559,449,600),border=cyan, fill=(5,13,31),thickness=2,bevel=5)
    _pixel_box(dr,(93,608,448,672),border=cyan, fill=(5,13,31),thickness=2,bevel=5)
    # Outer image is designed so center-crop exactly frames the monitor as a square post.
    return im


def normalized_positions(config):
    incoming = config.get('positions', {})
    results = {}
    for k,(dx,dy) in DEFAULT_POSITIONS.items():
        value = incoming.get(k) if isinstance(incoming,dict) else None
        try:
            if isinstance(value,(tuple,list)) and len(value)==2:
                dx = float(value[0]); dy=float(value[1])
        except (ValueError,TypeError,OverflowError):
            dx,dy=DEFAULT_POSITIONS[k]
        results[k]=(min(W,max(0,round(dx))), min(H,max(0,round(dy))))
    return results


def _decorate_text(asset):
    if asset is None:
        return None
    # Crisp black outline helps imitate arcade typography against the blue screen.
    shadow = Image.new('RGBA', (asset.width+6,asset.height+6),(0,0,0,0))
    mask=asset.getchannel('A')
    for ox,oy in [(1,2),(3,2),(2,1),(2,3),(2,4)]:
        under=Image.new('RGBA',asset.size,(4,9,19,255))
        shadow.paste(under,(ox,oy),mask)
    shadow.alpha_composite(asset,(2,1))
    return shadow


def _title_layer(id_, label, value, size, color, max_width, style, font_bytes):
    img=text_image(value,style,size,color,max_width,font_bytes)
    if img is None:
        return None
    return Layer(id_,label,_decorate_text(img))


def _mixed_text(parts,style,size,max_width,font_bytes):
    chunks=[]
    for txt,clr in parts:
        a=text_image(txt,style,size,clr,0,font_bytes)
        if a is not None:
            chunks.append(a)
    if not chunks:
        return None
    gap=4
    total_w=sum(p.width for p in chunks)+(len(chunks)-1)*gap
    max_h=max(p.height for p in chunks)
    out=Image.new('RGBA',(total_w,max_h+2),(0,0,0,0))
    px=0
    for p in chunks:
        out.alpha_composite(p,(px,(max_h-p.height)//2))
        px+=p.width+gap
    if out.width>max_width:
        factor=max_width/out.width
        out=out.resize((max(1,round(out.width*factor)),max(1,round(out.height*factor))),Image.Resampling.NEAREST)
    return _decorate_text(out)


def _name_text(value,style,size,color,font_bytes):
    value=str(value).strip().upper()[:42]
    if not value:
        return None
    words=value.split()
    if len(value)>13 and len(words)>1:
        lines=['','']
        for word in words:
            if not lines[0] or len(lines[0])+len(word)+1<=10:
                lines[0]=(lines[0]+' '+word).strip()
            else:
                lines[1]=(lines[1]+' '+word).strip()
        if lines[1]:
            rows=[text_image(x,style,max(9,size-2),color,139,font_bytes) for x in lines]
            rows=[x for x in rows if x]
            w=max(r.width for r in rows); h=sum(r.height for r in rows)+2*(len(rows)-1)
            image=Image.new('RGBA',(w,h),(0,0,0,0))
            y=0
            for r in rows:
                image.alpha_composite(r,((w-r.width)//2,y)); y+=r.height+2
            return _decorate_text(image)
    return _decorate_text(text_image(value,style,size,color,138,font_bytes))


def _vs_sprite(color, style, font_bytes, size=44):
    """Gold pixel sparks and arcade letters, outlined in near-black."""
    gold=color
    img=Image.new('RGBA',(94,115),(0,0,0,0))
    d=ImageDraw.Draw(img)
    for x,y in [(11,15),(17,24),(77,15),(71,24),(10,89),(19,80),(79,89),(71,80)]:
        d.rectangle((x,y,x+4,y+4),fill=(*gold,255))
    inner=_decorate_text(text_image('VS',style,size,gold,88,font_bytes))
    if inner:
        img.alpha_composite(inner,((94-inner.width)//2,(115-inner.height)//2))
    return img


def _unknown_shield():
    out=Image.new('RGBA',(106,147),(0,0,0,0))
    d=ImageDraw.Draw(out)
    vertices=[(7,6),(99,6),(99,112),(53,141),(7,112)]
    d.polygon(vertices,fill=(8,11,23,255),outline=(111,224,255,255),width=3)
    d.polygon([(17,15),(89,15),(89,105),(53,127),(17,105)],outline=(255,216,104,255),width=2)
    question=text_image('?', 'Pixel Arcade',50,(255,211,101),60,None)
    if question:
        out.alpha_composite(question,((106-question.width)//2,(147-question.height)//2))
    return out


def get_layers(config, home_logo, away_logo=None, font_bytes=None):
    style=config.get('text_style','Pixel Arcade')
    pink=rgb(config.get('pink','#F268A8'),DEFAULT_PINK)
    cyan=rgb(config.get('cyan','#79DCF7'),(121,220,247))
    white=rgb(config.get('white','#F6F4FC'),DEFAULT_WHITE)
    yellow=rgb(config.get('yellow','#FFC963'),(255,201,99))
    title_size=int(config.get('title_size',27))
    label_size=int(config.get('label_size',18))
    info_size=int(config.get('info_size',16))
    layers=[]
    def append(*args):
        v=_title_layer(*args,style,font_bytes)
        if v: layers.append(v)
    append('title','Titolo',config.get('title','MATCHDAY SCREEN'),title_size,white,298)
    append('date','Data',config.get('date','GG/MM/AAAA'),title_size-1,pink,260)
    if home_logo:
        layers.append(Layer('home_logo','Stemma Flamingos',clean_logo(home_logo,int(config.get('home_logo_size',103)),bool(config.get('home_clear_white',True)))))
    else:
        layers.append(Layer('home_logo','Stemma Flamingos',_unknown_shield()))
    if away_logo:
        layers.append(Layer('away_logo','Stemma avversari',clean_logo(away_logo,int(config.get('away_logo_size',103)),bool(config.get('away_clear_white',True)))))
    else:
        layers.append(Layer('away_logo','Stemma avversari',_unknown_shield()))
    layers.append(Layer('vs','VS',_vs_sprite(yellow,style,font_bytes,int(config.get('vs_size',43)))))
    hname=_name_text(config.get('home_name','FLAMINGOS'),style,label_size,pink,font_bytes)
    aname=_name_text(config.get('away_name','AVVERSARI'),style,label_size,cyan,font_bytes)
    if hname:layers.append(Layer('home_name','Nome Flamingos',hname))
    if aname:layers.append(Layer('away_name','Nome avversari',aname))
    kickoff=_mixed_text([(config.get('kickoff_label',"CALCIO D'INIZIO:").upper(),white),
                         (config.get('kickoff','HH:MM').upper(),yellow)],style,info_size,330,font_bytes)
    venue=_mixed_text([(config.get('venue_label','LUOGO:').upper(),cyan),
                       (config.get('venue','VIA FORNACI, 82'),yellow)],style,info_size,330,font_bytes)
    if kickoff:layers.append(Layer('kickoff','Orario inizio',kickoff))
    if venue:layers.append(Layer('venue','Campo',venue))
    return layers


def scene(config,home_logo,away_logo=None,font_bytes=None):
    return background(config.get('cyan','#79DCF7')).copy(),get_layers(config,home_logo,away_logo,font_bytes),normalized_positions(config)


def compose(prepared,t=999,animated=True):
    base,layers,positions=prepared
    canvas=base.copy()
    timeline={'title':.2,'date':.6,'home_logo':1.25,'away_logo':1.55,'vs':2.05,
              'home_name':2.6,'away_name':2.9,'kickoff':3.4,'venue':3.75}
    for item in layers:
        if animated:
            a=progress(t,timeline.get(item.id,0),.46)
            drop=int((1-a)*(11 if item.id not in ('home_logo','away_logo') else 24))
        else:
            a=1.0;drop=0
        composite_layer(canvas,item,positions[item.id],a,drop)
    if animated:
        # Bright horizontal scan bar, confined to TV screen.
        scan=(t*.9)%1
        y=int(310+scan*350)
        overlay=Image.new('RGBA',(W,H),(0,0,0,0))
        d=ImageDraw.Draw(overlay)
        d.line((71,y,469,y),fill=(90,225,245,18),width=2)
        canvas.alpha_composite(overlay)
        # Tiny screen flicker in the first half-second.
        if t<.36:
            flick=Image.new('RGBA',(W,H),(0,0,0,0))
            ImageDraw.Draw(flick).rectangle((73,477,468,479),fill=(172,235,255,round((.36-t)*420)))
            canvas.alpha_composite(flick)
    return canvas.convert('RGB')


def output_image(image,format='Story 9:16',scale=2):
    if format.startswith('Post'):
        image=image.crop(FEED_CROP)
    if scale!=1:
        image=image.resize((image.width*scale,image.height*scale),Image.Resampling.LANCZOS)
    return image


def png_bytes(config,home_logo,away_logo=None,font_bytes=None,format='Story 9:16',scale=2):
    p=scene(config,home_logo,away_logo,font_bytes)
    image=output_image(compose(p,animated=False),format,scale)
    data=io.BytesIO();image.save(data,format='PNG',optimize=True)
    return data.getvalue()


def render_video(config,home_logo,away_logo,path,font_bytes=None,fps=15,duration=8,format='Story 9:16',scale=1):
    prepared=scene(config,home_logo,away_logo,font_bytes)
    writer=imageio.get_writer(str(path),fps=int(fps),codec='libx264',quality=7,
                              ffmpeg_log_level='error',macro_block_size=4,
                              output_params=['-pix_fmt','yuv420p','-movflags','+faststart'])
    try:
        for i in range(round(float(duration)*fps)):
            frame=output_image(compose(prepared,i/fps,True),format,scale)
            writer.append_data(np.asarray(frame))
    finally:
        writer.close()
    return str(path)
