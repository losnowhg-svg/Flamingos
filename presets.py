"""Eight seasonal style presets. Applying a style never changes match content."""
from __future__ import annotations
import copy

PRESETS = {
    'flamingos': dict(name='Flamingos Original', when='Identità di squadra, tutta la stagione',
        accent='#F660A0', secondary='#7CDAEF', background='#100E1A', panel='#201A2E', text='#FFF6FB', pitch='#172C2C', pattern='Pulito', texture=25),
    'kickoff': dict(name='Kickoff Bold', when='Avvio stagione e presentazioni',
        accent='#FF7CAC', secondary='#FCE289', background='#191126', panel='#2C1B3B', text='#FFF7FC', pitch='#292038', pattern='Diagonali', texture=45),
    'night': dict(name='Neon Night', when='Partite serali e infrasettimanali',
        accent='#DA90FF', secondary='#7BEDE4', background='#101028', panel='#20213D', text='#F5FAFF', pitch='#182A38', pattern='Griglia', texture=38),
    'autumn': dict(name='Autumn Copper', when='Giornate autunnali',
        accent='#FFBC83', secondary='#F594BA', background='#231716', panel='#382622', text='#FFF4EA', pitch='#302A21', pattern='Fasce', texture=32),
    'winter': dict(name='Winter Ice', when='Periodo invernale e ripresa',
        accent='#A9DEFF', secondary='#D7C9FF', background='#0F2030', panel='#1B354A', text='#F7FCFF', pitch='#183749', pattern='Orbita', texture=35),
    'spring': dict(name='Spring Mint', when='Primavera e girone di ritorno',
        accent='#A0F0C9', secondary='#FFA4C4', background='#102521', panel='#1E3A31', text='#F4FFF8', pitch='#214234', pattern='Diagonali', texture=25),
    'derby': dict(name='Derby Contrast', when='Derby e sfide speciali',
        accent='#FF759D', secondary='#FFFFFF', background='#101014', panel='#24242C', text='#FFFFFF', pitch='#202029', pattern='Fasce', texture=45),
    'finals': dict(name='Final Gold', when='Ultime giornate, playoff e finali',
        accent='#FFDA8A', secondary='#FFA4CC', background='#201B16', panel='#352C23', text='#FFF9EA', pitch='#302D22', pattern='Coriandoli', texture=40),
}


def apply_preset(template: str, config: dict, preset_id: str) -> dict:
    if preset_id not in PRESETS:
        raise ValueError('Preset sconosciuto.')
    if template not in ('Starting 7', 'Matchday Screen', 'Match Result'):
        raise ValueError('Modello sconosciuto.')
    result, style = copy.deepcopy(config), PRESETS[preset_id]
    result.update(preset_id=preset_id, pattern=style['pattern'], texture=style['texture'],
                  panel_color=style['panel'], background=style['background'])
    if template == 'Matchday Screen':
        result.update(pink=style['accent'], cyan=style['secondary'], white=style['text'], yellow=style['accent'],
                      backdrop='CRT originale' if preset_id == 'flamingos' else 'Studio grafico')
    else:
        result.update(accent=style['accent'], text_color=style['text'])
        if template == 'Starting 7':
            result['pitch_color'] = style['pitch']
        else:
            result['secondary'] = style['secondary']
    return result
