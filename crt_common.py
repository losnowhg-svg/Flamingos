"""Animation and export shared by the Full Time and Convocati editors."""
from __future__ import annotations
import numpy as np
from PIL import Image
from render_utils import ScaledDraw, checked_scale
from renderer import composite_layer, progress, encode_png, video_settings, video_writer
from crt_presets import output_image, even_video_frame


def compose(prepared, t=999, animated=True):
    base,layers,positions=prepared
    image=base.copy()
    for index,layer in enumerate(layers):
        start=.18+index*.12
        if layer.id=='score':start=1.0
        alpha=progress(t,start,.42) if animated else 1
        composite_layer(image,layer,positions[layer.id],alpha,(1-alpha)*12)
    if animated:
        s=image.width//540
        effect=Image.new('RGBA',image.size)
        y=317+(t*.35 % 1)*353
        ScaledDraw(effect,s).line((80,y,460,y),fill=(160,229,255,16),width=1)
        image.alpha_composite(effect)
    return image.convert('RGB')


def export_png(scene_function, config, home_logo, away_logo=None, font_bytes=None,
               format='Story 9:16', scale=2, supersample=2):
    scale=checked_scale(scale)
    ss=checked_scale(supersample,2)
    prepared=scene_function(config,home_logo,away_logo,font_bytes,min(4,scale*ss))
    return encode_png(output_image(compose(prepared,animated=False),format,scale))


def export_video(scene_function, config, home_logo, away_logo, path, font_bytes=None,
                 fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None):
    fps,duration=video_settings(fps,duration,scale)
    prepared=scene_function(config,home_logo,away_logo,font_bytes,scale)
    writer=video_writer(path,fps)
    count=round(duration*fps)
    try:
        for i in range(count):
            frame=output_image(compose(prepared,i/fps,True),format,scale)
            writer.append_data(np.asarray(even_video_frame(frame)))
            if progress_callback and (i % fps==0 or i==count-1):
                progress_callback((i+1)/count)
    finally:
        writer.close()
    return str(path)
