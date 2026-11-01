"""The look of the figurine screens (3.10): the synthwave night, or a studio preset.

With a preset the cards, the ratings and the album sit on that preset's own
background (TV, cassette, Game Boy, stadium board...) with its atmosphere and
seasonal theme, and the glow and the dust take its colours. The card itself
keeps its design, so the collection stays recognisable.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

SYNTHWAVE = 'synthwave'
FOLLOW = 'fulltime'
# Settings of the Full Time editor that shape a preset background.
KEYS = ('atmosphere', 'decor', 'panel_style', 'brightness', 'scanlines', 'theme', 'date', 'season_round',
        'texture_fx', 'frame_style')


def _rgb(value):
    return tuple(bytes.fromhex(str(value).lstrip('#')))


def key_for(choice, fulltime):
    """A small JSON key (hashable, cacheable) for a style choice: 'synthwave', 'fulltime' or a preset id."""
    from crt_presets import PRESETS
    if choice == SYNTHWAVE:
        return json.dumps({'preset': SYNTHWAVE})
    preset = fulltime.get('preset_id', 'crt') if choice == FOLLOW else choice
    if preset not in PRESETS:
        return json.dumps({'preset': SYNTHWAVE})
    return json.dumps({'preset': preset, 'config': {k: fulltime.get(k) for k in KEYS if k in fulltime}},
                      sort_keys=True, default=str)


def label(choice, fulltime):
    from crt_presets import PRESETS
    if choice == SYNTHWAVE:
        return 'Figurine: notte synthwave'
    if choice == FOLLOW:
        preset = fulltime.get('preset_id', 'crt')
        return f"Come il Full Time ({PRESETS.get(preset, PRESETS['crt'])['name'].split('/ ')[-1]})"
    return 'Preset '+PRESETS[choice]['name']


@lru_cache(maxsize=12)
def build(key, format='Story 9:16', width=1080):
    """{'image', 'glow', 'palette'} for a style key at a canvas width (pixels), or None for synthwave."""
    data = json.loads(key) if key else {}
    preset = data.get('preset')
    from crt_presets import CROPS, PRESETS, apply_preset, background
    if preset not in PRESETS:
        return None
    from studio_state import defaults
    config = apply_preset(dict(defaults('Classifica'), **(data.get('config') or {})), preset)
    scale = max(1, min(2, math.ceil(width/540)))
    image = background(config, 'classifica', scale).convert('RGB')
    crop = CROPS.get(format)
    if crop:
        k = image.width/540
        image = image.crop(tuple(round(v*k) for v in crop))
    colors = [_rgb(PRESETS[preset][c]) for c in ('pink', 'cyan', 'yellow', 'white')]
    return {'image': image, 'glow': colors[0], 'palette': tuple(colors), 'preset': preset}
