"""Seasonal CRT art direction and original, code-drawn pixel hardware shells."""
from __future__ import annotations

import copy
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from render_utils import ScaledDraw, checked_scale

PRESETS = {
    'crt': dict(name='01 / TV CRT originale', object='Televisore Matchday',
                description='La stessa tele del Matchday, neon rosa e ghiaccio.',
                pink='#F268A8', cyan='#79DCF7', yellow='#FFC963', white='#F6F4FC', font='CRT Terminal'),
    'handheld': dict(name='02 / Console portatile', object='Console 8-bit',
                description='Scocca lilla, croce direzionale e pulsanti pixel.',
                pink='#F6A6D6', cyan='#BEACFF', yellow='#D6FF91', white='#FAF4FF', font='CRT Scoreboard'),
    'cassette': dict(name='03 / Mixtape', object='Musicassetta',
                description='Nastro, bobine e dettagli corallo da spogliatoio.',
                pink='#FF8EAF', cyan='#FFBC98', yellow='#FFE08A', white='#FFF5EC', font='CRT Terminal'),
    'arcade': dict(name='04 / Arcade club', object='Cabinato arcade',
                description='Marquee, joystick e pulsanti da sala giochi.',
                pink='#FF89CC', cyan='#83E8FF', yellow='#FFF083', white='#FBF8E9', font='CRT Scoreboard'),
    'floppy': dict(name='05 / Save the game', object='Floppy disk',
                description='Scocca turchese, etichetta e otturatore pixel.',
                pink='#FFAECF', cyan='#83E6CD', yellow='#C7FF9A', white='#EEFFF9', font='CRT Terminal'),
    'tactics': dict(name='06 / Tactics board', object='Lavagna tattica',
                description='Lavagna magnetica, clip e richiami al calcio a 7.',
                pink='#FFB1CE', cyan='#A6EAA3', yellow='#FFE58C', white='#F6FFF1', font='CRT Scoreboard'),
}
PRESET_IDS = tuple(PRESETS)
FORMATS = ('Post 1:1', 'Post 4:5', 'Story 9:16')
CROPS = {'Post 1:1': (0, 210, 540, 750), 'Post 4:5': (0, 142.5, 540, 817.5), 'Story 9:16': None}


def preset_for_round(round_number):
    try:
        value = max(1, int(round_number))
    except (TypeError, ValueError, OverflowError):
        value = 1
    return PRESET_IDS[(value-1) % len(PRESET_IDS)]


def apply_preset(config, preset_id, typography=False):
    """Only art direction changes: never overwrite match data, assets or positions."""
    selected = preset_id if preset_id in PRESETS else 'crt'
    output = copy.deepcopy(config)
    output['preset_id'] = selected
    output.update({key: PRESETS[selected][key] for key in ('pink', 'cyan', 'yellow', 'white')})
    if typography:
        output['font_choice'] = PRESETS[selected]['font']
        output['text_style'] = output['font_choice']
    return output


def _rgb(value):
    return tuple(bytes.fromhex(value.lstrip('#')))


def _mix(a, b, amount):
    return tuple(round(x+(y-x)*amount) for x, y in zip(a, b))


def _box(d, xy, fill, border, thickness=2, bevel=5):
    x1,y1,x2,y2 = xy
    points = [(x1+bevel,y1),(x2-bevel,y1),(x2,y1+bevel),(x2,y2-bevel),
              (x2-bevel,y2),(x1+bevel,y2),(x1,y2-bevel),(x1,y1+bevel)]
    d.polygon(points, fill=border)
    n=thickness
    inner=[(x1+bevel,y1+n),(x2-bevel,y1+n),(x2-n,y1+bevel),(x2-n,y2-bevel),
           (x2-bevel,y2-n),(x1+bevel,y2-n),(x1+n,y2-bevel),(x1+n,y1+bevel)]
    d.polygon(inner, fill=fill)


def _label(im, value, x, y, width, color, size=11, scale=1):
    from pixel_fonts import pixel_text_runs
    label = pixel_text_runs([(value,color)], 'CRT Terminal', size, width, scale)
    if label:
        im.alpha_composite(label,(round(x*scale-label.width/2),round(y*scale-label.height/2)))


def _pixel_hardware(preset_id, pink, cyan, yellow, s):
    # Design on a real coarse grid; only the original hardware art is enlarged.
    art = Image.new('RGBA',(180,320))
    d=ScaledDraw(art,1/3)
    edge=(*cyan,255); dark=(13,16,28,255); ink=(4,10,22,255)
    body=(*_mix(cyan,(16,16,29),.70),255)
    muted=(*_mix(cyan,(16,16,29),.45),255)
    bright=(*pink,255)
    if preset_id=='handheld':
        _box(d,(31,230,509,738),body,edge,5,18)
        d.rectangle((46,243,493,296),fill=muted)
        d.rectangle((61,251,479,286),fill=ink)
        d.rectangle((78,699,129,716),fill=ink); d.rectangle((96,682,112,731),fill=ink)
        d.rectangle((383,692,404,713),fill=bright);d.rectangle((431,679,452,700),fill=(*yellow,255))
        d.rectangle((242,706,266,712),fill=edge); d.rectangle((284,706,308,712),fill=edge)
        for x in (362,374,386):d.rectangle((x,719,x+5,729),fill=muted)
    elif preset_id=='cassette':
        _box(d,(28,233,512,737),body,edge,5,15)
        for x in (43,490):
            for y in (248,714):d.rectangle((x,y,x+6,y+6),fill=edge)
        d.rectangle((67,251,471,291),fill=bright)
        d.rectangle((73,257,465,285),fill=ink)
        d.rectangle((67,686,471,727),fill=ink)
        for x in (167,373):
            d.ellipse((x-29,681,x+29,730),fill=muted,outline=edge,width=4)
            d.rectangle((x-8,694,x+8,713),fill=ink)
        d.rectangle((204,698,336,713),fill=muted)
        d.rectangle((227,704,313,708),fill=(*pink,255))
    elif preset_id=='arcade':
        d.polygon([(74,233),(466,233),(505,287),(501,678),(521,717),(494,739),
                   (46,739),(19,717),(39,678),(35,287)], fill=body)
        d.line((74,235,466,235,504,287,500,678,520,717,494,737,46,737,20,717,40,678,36,287,74,235),fill=edge,width=5)
        _box(d,(71,247,469,289),ink,(*yellow,255),3,6)
        for x in range(46,64,6):d.rectangle((x,325,x+2,654),fill=bright)
        for x in range(478,496,6):d.rectangle((x,325,x+2,654),fill=bright)
        d.polygon([(44,681),(496,681),(510,718),(30,718)],fill=muted)
        d.rectangle((132,695,175,704),fill=ink);d.rectangle((151,681,157,698),fill=edge)
        d.rectangle((142,678,166,688),fill=(*yellow,255))
        for x,y,col in ((348,696,bright),(392,690,edge),(434,699,(*yellow,255))):
            d.rectangle((x,y,x+16,y+9),fill=col)
    elif preset_id=='floppy':
        d.polygon([(35,234),(475,234),(508,267),(508,737),(32,737),(32,234)],fill=body)
        d.line((36,235,475,235,507,267,507,735,33,735,33,235),fill=edge,width=5)
        d.rectangle((91,239,415,298),fill=muted)
        d.rectangle((292,246,371,287),fill=ink)
        d.rectangle((106,251,251,257),fill=edge)
        d.rectangle((111,694,429,737),fill=muted)
        d.rectangle((131,705,310,720),fill=ink)
        d.rectangle((47,702,67,722),fill=ink);d.rectangle((473,702,493,722),fill=ink)
    else:  # magnetic tactics board
        _box(d,(33,257,507,737),(16,39,31,255),edge,6,12)
        _box(d,(190,230,350,292),body,(*yellow,255),4,9)
        d.rectangle((210,246,330,257),fill=ink)
        d.rectangle((218,235,322,242),fill=(*yellow,255))
        d.line((73,710,464,710),fill=(*cyan,160),width=2)
        for x,y,col in ((98,710,bright),(161,699,edge),(217,716,bright),(283,700,edge),(343,715,bright),(404,699,edge),(456,716,bright)):
            d.rectangle((x-5,y-5,x+5,y+5),fill=col)
    _box(d,(68,306,472,682),ink,edge,4,12)
    d.rectangle((77,315,463,673),fill=(5,14,27,255))
    return art.resize((540*s,960*s),Image.Resampling.NEAREST)


@lru_cache(maxsize=5)
def _background(preset_id, pink_hex, cyan_hex, yellow_hex, layout, intensity, s):
    pink,cyan,yellow = _rgb(pink_hex),_rgb(cyan_hex),_rgb(yellow_hex)
    if preset_id=='crt':
        from matchday_renderer import _shell
        sh=_shell()
        dark=sh.resize((540*s,960*s),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(50*s))
        im=ImageEnhance.Brightness(dark).enhance(.26).convert('RGBA')
        tv=sh.resize((520*s,520*s),Image.Resampling.LANCZOS).convert('RGBA')
    else:
        im=Image.new('RGBA',(540*s,960*s),(7,9,18,255));tv=None
    glow=Image.new('RGBA',im.size)
    gd=ScaledDraw(glow,s)
    gd.ellipse((60,250,480,709),fill=(*cyan,38))
    gd.line((90,187,450,187),fill=(*cyan,115),width=3)
    gd.line((90,774,450,774),fill=(*pink,105),width=3)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(25*s)))
    if tv:
        im.alpha_composite(tv,(10*s,220*s))
    else:
        bg=ScaledDraw(im,s)
        for y in range(165,820,27):
            for x in range(27,535,27):
                bg.rectangle((x,y,x+1,y+1),fill=(*cyan,60))
        im.alpha_composite(_pixel_hardware(preset_id,pink,cyan,yellow,s))
        labels={'arcade':('FLAMINGOS / ARCADE',270,271,320,10),
                'handheld':('7-A-SIDE / PLAYER ONE',270,269,380,10),
                'cassette':('SIDE A / MATCH TAPE',270,271,340,10),
                'floppy':('SAVE GAME',183,275,174,9),
                'tactics':('TACTICS',270,277,140,10)}
        label,x,y,width,size=labels[preset_id]
        _label(im,label,x,y,width,yellow,size,s)
        _label(im,'CALCIO A 7',270,185,390,cyan,11,s)
        _label(im,'PRESS START / PLAY TOGETHER',270,777,420,pink,10,s)
    # A translucent screen veil keeps the photo's grid but improves long-list contrast.
    if layout!='matchday' or preset_id!='crt':
        veil=Image.new('RGBA',im.size)
        vd=ScaledDraw(veil,s)
        vd.rectangle((78,316,462,674),fill=(3,10,23,165 if preset_id=='crt' else 30))
        im.alpha_composite(veil)
    scan=Image.new('RGBA',im.size)
    sd=ScaledDraw(scan,s)
    for y in range(318,674,4):
        sd.line((80,y,460,y),fill=(*cyan,intensity),width=.5)
    im.alpha_composite(scan)
    d=ScaledDraw(im,s)
    if layout=='matchday':
        for rect in ((115,322,425,394),(91,559,242,600),(297,559,449,600),(93,608,448,672)):
            _box(d,rect,(5,13,31,255),(*cyan,255),1.4,5)
    elif layout in ('fulltime','fulltime_clean'):
        for rect in ((107,324,433,390),(91,503,237,539),(303,503,449,539)):
            _box(d,rect,(5,13,31,255),(*cyan,255),1.2,5)
        if layout=='fulltime':
            _box(d,(87,577,453,673),(5,13,31,255),(*cyan,190),1.2,5)
            d.line((270,590,270,660),fill=(*cyan,90),width=.5)
    else:
        _box(d,(84,321,456,388),(5,13,31,255),(*cyan,255),1.2,5)
        _box(d,(84,621,456,673),(5,13,31,255),(*cyan,190),1.2,5)
    return im


def background(config, layout='matchday', render_scale=2):
    s=checked_scale(render_scale)
    preset=config.get('preset_id','crt')
    if preset not in PRESETS:preset='crt'
    palette=PRESETS[preset]
    colors=[]
    for key in ('pink','cyan','yellow'):
        value=config.get(key,palette[key])
        try:
            if len(_rgb(value)) != 3:raise ValueError()
        except (ValueError,TypeError,AttributeError):
            value=palette[key]
        colors.append(value)
    return _background(preset,*colors,layout,max(0,min(60,int(config.get('scanlines',16)))),s).copy()


def output_image(image, format='Story 9:16', scale=2):
    scale=checked_scale(scale)
    format=format if format in FORMATS else 'Story 9:16'
    crop=CROPS[format]
    source_scale=image.width/540
    if crop:
        top=math.floor(crop[1]*source_scale)
        box=(round(crop[0]*source_scale),top,round(crop[2]*source_scale),
             top+round((crop[3]-crop[1])*source_scale))
        image=image.crop(box)
    height=540 if format=='Post 1:1' else 675 if format=='Post 4:5' else 960
    target=(540*scale,height*scale)
    return image.resize(target,Image.Resampling.LANCZOS) if image.size!=target else image


def even_video_frame(image):
    """H.264/yuv420p needs even dimensions: pad, never stretch an odd crop."""
    width,height=image.size
    if width%2 or height%2:
        result=Image.new('RGB',(width+width%2,height+height%2))
        result.paste(image,(0,0))
        if height%2:result.paste(image.crop((0,height-1,width,height)),(0,height))
        if width%2:result.paste(result.crop((width-1,0,width,result.height)),(width,0))
        return result
    return image
