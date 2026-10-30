"""Animation and export shared by the Full Time and Convocati editors."""
from __future__ import annotations
import numpy as np
from PIL import Image
from render_utils import ScaledDraw, checked_scale
from renderer import composite_layer, progress, encode_png, video_settings, video_writer
from crt_presets import output_image, even_video_frame


def compose(prepared, t=999, animated=True):
    import animations
    if animated and animations.rich(prepared):
        return animations.compose(prepared,t)
    base,layers,positions=prepared
    image=base.copy()
    animations.particles(image,prepared,t,animated)
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
    import frames
    return frames.apply(image.convert('RGB'),base.info,t,animated)


def video_length(prepared, duration):
    """The requested length, stretched when intro, animations and ending need more."""
    import animations
    if not animations.rich(prepared) or duration < 3:  # very short test clips stay as asked
        return duration
    needed=(animations.intro_length(prepared) or 0)+1.6
    import motion
    needed+=motion.ENDING_LENGTH.get(prepared[0].info.get('ending'),0)
    return round(min(30,max(duration,needed)),2)


def finish(prepared, config, kind):
    import animations
    import sponsor
    if kind != 'sponsor':
        sponsor.decorate(prepared[0], config)
    if sponsor.active(config) and kind != 'sponsor':
        prepared[0].info['sponsor_cfg'] = {k: config.get(k) for k in ('sponsor_on', 'sponsor_logo_id', 'sponsor_name', 'cyan')}
    return animations.prepare(prepared, config, kind)


def sponsor_sticker(prepared, scale):
    """The sponsor pill for the TV mockup, from what the scene recorded."""
    import sponsor
    cfg = prepared[0].info.get('sponsor_cfg')
    return sponsor.sticker(cfg, scale) if cfg else None


def _frame(compose_fn, prepared, t, animated, format, scale, mockup, knob=0.0):
    if mockup:
        import mockup as tv
        return tv.frame(compose_fn(prepared, t, animated), format, scale, knob, sponsor_sticker(prepared, scale))
    return output_image(compose_fn(prepared, t, animated), format, scale)


def export_png(scene_function, config, home_logo, away_logo=None, font_bytes=None,
               format='Story 9:16', scale=2, supersample=2, compose_fn=None):
    compose_fn=compose_fn or compose
    scale=checked_scale(scale)
    ss=checked_scale(supersample,2)
    prepared=scene_function(config,home_logo,away_logo,font_bytes,min(4,scale*ss))
    prepared[0].info['format']=format
    return encode_png(_frame(compose_fn,prepared,999,False,format,scale,config.get('mockup',False)))


def export_video(scene_function, config, home_logo, away_logo, path, font_bytes=None,
                 fps=24, duration=8, format='Story 9:16', scale=2, progress_callback=None, compose_fn=None):
    compose_fn=compose_fn or compose
    fps,duration=video_settings(fps,duration,scale)
    prepared=scene_function(config,home_logo,away_logo,font_bytes,scale)
    prepared[0].info['format']=format
    duration=video_length(prepared,duration)
    prepared[0].info['duration']=duration
    writer=video_writer(path,fps)
    count=round(duration*fps)
    mockup=config.get('mockup',False)
    try:
        for i in range(count):
            frame=_frame(compose_fn,prepared,i/fps,True,format,scale,mockup)
            writer.append_data(np.asarray(even_video_frame(frame)))
            if progress_callback and (i % fps==0 or i==count-1):
                progress_callback((i+1)/count)
    finally:
        writer.close()
    return str(path)
