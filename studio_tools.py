"""Pure workflow helpers shared by the UI and regression tests."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import re
import unicodedata
import zipfile

import renderer as r
import matchday_renderer as m
import match_result_renderer as mr
from presets import apply_preset
from studio_state import defaults, sanitize_config
from render_utils import layout_warnings


def switch_result_format(config, new_format):
    if new_format not in mr.FORMATS:
        raise ValueError('Formato non supportato.')
    updated = copy.deepcopy(config)
    old_format = config.get('export_format','Story 9:16')
    if new_format == old_format:
        return updated
    layouts = updated.setdefault('layouts',{})
    layouts[old_format] = copy.deepcopy(updated['positions'])
    updated['positions'] = copy.deepcopy(layouts.get(new_format, {k:list(v) for k,v in mr.default_positions(new_format).items()}))
    updated['export_format'] = new_format
    return sanitize_config('Match Result',updated)


def matchday_to_result(config):
    source = sanitize_config('Matchday Screen',config)
    result = apply_preset('Match Result',defaults('Match Result'),source.get('preset_id','flamingos'))
    for key in ('date','home_name','away_name','home_logo_id','away_logo_id','home_clear_white','away_clear_white','font_choice','competition','round_label'):
        result[key] = source[key]
    result.update(accent=source['pink'],secondary=source['cyan'],text_color=source['white'],
                  background=source['background'],panel_color=source['panel_color'],pattern=source['pattern'],texture=source['texture'])
    return sanitize_config('Match Result',result)


def signature(config, home, away=None, font=None, video=False):
    values = copy.deepcopy(config)
    ignored = ['locked_layers','layouts','preset_id']
    if not video:
        ignored += ['fps','duration','video_scale','png_quality']
    for key in ignored:
        values.pop(key,None)
    if not video:
        # PNG quality changes rasterization, unlike video-only settings.
        values['png_quality'] = config.get('png_quality','Fine')
    payload = {'config':values,'assets':[hashlib.sha256(blob or b'').hexdigest() for blob in (home,away,font)]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def slug(value):
    normalized = unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','-',normalized).strip('-')[:64]


def export_basename(template,config):
    parts = [slug(template)]
    if template != 'Starting 7':
        parts += [slug(config.get('home_name','casa')),slug(config.get('away_name','ospiti')),slug(config.get('date',''))]
    else:
        parts += [slug(config.get('team_name','flamingos'))]
    parts += [slug(config.get('export_format','story'))]
    return '_'.join(p for p in parts if p)


def png_export(template,config,home,away=None,font=None):
    ss = 2 if config.get('png_quality') == 'Fine' else 1
    if template == 'Match Result':
        return mr.png_bytes(config,home,away,font,2,ss)
    if template == 'Matchday Screen':
        return m.png_bytes(config,home,away,font,config['export_format'],2,ss)
    return r.png_bytes(config,home,font,2,ss)


def export_pack(template,config,home,away=None,font=None):
    formats = list(mr.FORMATS) if template == 'Match Result' else ['Story 9:16','Post 1:1'] if template == 'Matchday Screen' else ['Story 9:16']
    buffer = io.BytesIO()
    notes = []
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for fmt in formats:
            conf = switch_result_format(config,fmt) if template == 'Match Result' else {**copy.deepcopy(config),'export_format':fmt}
            # Switching format sanitizes persisted values; restore the runtime font selection.
            if config.get('text_style'):
                conf['text_style'] = config['text_style']
            module = mr if template=='Match Result' else m if template=='Matchday Screen' else r
            prepared = module.scene(conf,home,font,1) if template=='Starting 7' else module.scene(conf,home,away,font,1)
            crop = m.FEED_CROP if template=='Matchday Screen' and fmt=='Post 1:1' else None
            warnings = preflight(template,conf,prepared,crop)
            notes.extend(f'{fmt}: {warning}' for warning in warnings)
            archive.writestr(export_basename(template,conf)+'.png',png_export(template,conf,home,away,font))
        archive.writestr('LEGGIMI.txt','Flamingos Studio 1.5\nControllare i file prima di pubblicare.\n\n'+'\n'.join(notes or ['Nessun avviso automatico. Verificare comunque i contenuti.']))
    return buffer.getvalue(),notes


def build_caption(template,config):
    if template == 'Starting 7':
        lines = [f"{config.get('team_name','FLAMINGOS')} | {config.get('headline','STARTING 7')}",config.get('formation_text',''),'']
        lines += [f"{p['number']}. {p['name']}" for p in config.get('players',[])]
    else:
        lines = []
        info = ' / '.join(config.get(k,'').strip() for k in ('competition','round_label') if config.get(k,'').strip())
        if info: lines.append(info)
        if template == 'Match Result':
            lines += [f"{config['home_name']} {config['home_score']} - {config['away_score']} {config['away_name']}",config.get('match_status','FINALE')]
            if config.get('match_status') == 'DOPO I RIGORI':
                lines.append(f"Rigori: {config.get('home_penalties',0)} - {config.get('away_penalties',0)}")
            for side in ('home','away'):
                scorers = mr.scorer_lines(config.get('scorers_'+side,''))
                if scorers: lines.append(f"Marcatori {config[side+'_name']}: "+'; '.join(scorers))
            if config.get('show_mvp',True) and config.get('mvp','').strip():
                lines.append('MVP: '+config['mvp'].strip())
            lines.append(config.get('date',''))
        else:
            lines += [config['home_name']+' vs '+config['away_name'],config.get('date','')+' | '+config.get('kickoff',''),config.get('venue','')]
    lines += ['','#ForzaFlamingos #Flamingos']
    return '\n'.join(lines)


def preflight(template,config,prepared=None,crop=None):
    warnings = layout_warnings(prepared,crop) if prepared else []
    if template != 'Starting 7':
        for field,label,placeholder in [('date','Data','GG/MM/AAAA'),('away_name','Avversario','AVVERSARI')]:
            if not str(config.get(field,'')).strip() or config.get(field)==placeholder:
                warnings.append(label+': dato mancante o ancora di esempio.')
        if not str(config.get('home_name','')).strip(): warnings.append('Nome squadra di casa mancante.')
    if template == 'Matchday Screen' and config.get('kickoff') in ('','HH:MM'):
        warnings.append('Orario ancora da compilare.')
    if template == 'Match Result':
        for side in ('home','away'):
            lines = mr.scorer_lines(config.get('scorers_'+side,''))
            if len(lines)>6: warnings.append(('Marcatori casa' if side=='home' else 'Marcatori ospiti')+': nella grafica entrano sei righe; raggruppa le marcature. La didascalia conserva tutte le righe.')
            if any(len(line)>80 for line in lines[:6]): warnings.append('Una riga marcatori supera 80 caratteri e viene abbreviata nella grafica.')
        if config.get('match_status')=='DOPO I RIGORI':
            if config.get('home_score') != config.get('away_score'):
                warnings.append('Dopo i rigori: il punteggio prima della serie dovrebbe essere in parita. Verifica i dati inseriti.')
            if config.get('home_penalties')==config.get('away_penalties'):
                warnings.append('La serie dei rigori risulta in parita: verifica il risultato finale.')
    else:
        if template=='Starting 7':
            numbers = [p['number'] for p in config.get('players',[])]
            if len(set(numbers)) != len(numbers): warnings.append('Numeri di maglia duplicati.')
    return warnings
