"""Cloud check: does the app work with only what Streamlit Cloud installs?

Streamlit Cloud installs requirements.txt and nothing else, while a developer
machine often has SciPy, OpenCV and friends. 3.1 broke exactly like that.

    python tools/cloud_check.py

1. Static: every third-party import must be in requirements.txt, unless it is
   optional (inside a try block, with a fallback).
2. Real run, in a separate Python where every other installed package is
   blocked: every template as PNG with all the 3.x options, a short video with
   intro, camera, music and audio, a transition sequence, department slides,
   Wrapped, sponsor and the team photo.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# requirement name -> import names
REQUIRED = {'streamlit': ('streamlit',), 'pillow': ('PIL',), 'numpy': ('numpy',), 'imageio': ('imageio',),
            'imageio-ffmpeg': ('imageio_ffmpeg',)}


def requirement_names():
    names = set()
    for line in (ROOT/'requirements.txt').read_text().splitlines():
        line = line.split('#')[0].strip()
        if line:
            for sep in '<>=!~;[ ':
                line = line.split(sep)[0]
            names.add(line.lower())
    return names


def allowed_imports():
    out = set()
    for requirement in requirement_names():
        out.update(REQUIRED.get(requirement, (requirement.replace('-', '_'),)))
    return out


def _in_try(node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.Try):
            return True
    return False


def static_problems():
    local = {p.stem for p in ROOT.glob('*.py')}
    std = set(sys.stdlib_module_names)
    allowed = allowed_imports()
    problems = []
    for path in sorted(ROOT.glob('*.py')):
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split('.')[0]
                if top in std or top in local or top in allowed or _in_try(node, parents):
                    continue
                problems.append(f'{path.name}:{node.lineno} importa {top}, che non e in requirements.txt '
                                f'(aggiungilo o mettilo in un try con alternativa)')
    return problems


BLOCKER = r'''
import sys, importlib.abc
ALLOWED = set(%(allowed)r) | set(sys.stdlib_module_names) | set(%(local)r) | {'_distutils_hack'}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        top = name.split('.')[0]
        if top not in ALLOWED and not top.startswith('_'):
            raise ImportError(f'{top} non e installato su Streamlit Cloud')
        return None
sys.meta_path.insert(0, Block())
sys.path.insert(0, %(root)r)
'''

RUN = r'''
import io, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import crests, motion, music, sounds, transitions
from studio_state import MODULES, defaults
from crt_presets import apply_preset
from crt_common import video_length
import renderer
LOGO = Path(__ROOT__, 'assets', 'flamingos_logo.jpg').read_bytes()
CREST = crests.builtin_assets()['stemma:united_flero']['bytes']
FANCY = dict(theme='none', atmosphere='tramonto', decor='adesivi', panel_style='neon', title_fx='glitch',
             frame_style='polaroid', texture_fx='grana')
done = []
for template in ('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario'):
    module = MODULES[template]
    config = dict(apply_preset(defaults(template), 'curva'), **FANCY)
    image = Image.open(io.BytesIO(module.png_bytes(config, LOGO, CREST, None, 'Post 4:5', 1, 1)))
    assert image.size == (540, 675), image.size
    done.append(template+' PNG')
renderer.png_bytes(defaults('Starting 7'), LOGO, None, 1, 1)
done.append('Starting 7 PNG')
import tracks as real
real_key, _ = real.register(Path(__ROOT__, 'assets', 'music', 'city_lights.m4a').read_bytes(), 'upload')
tracks = [t for t in music.TRACKS]+list(real.LIBRARY)+[real_key, 'arcade', 'epica', 'tensione', 'festa']
with tempfile.TemporaryDirectory() as folder:
    for i, template in enumerate(('Matchday Screen', 'Full Time', 'Convocati', 'Classifica', 'Calendario')):
        module = MODULES[template]
        config = dict(apply_preset(defaults(template), 'acquario'), **FANCY)
        config.update(motion.REEL, music_track=('cc0_robots', 'synthwave', 'cc0_funk', 'arcade', 'cc0_rush')[i], camera=('parallasse', 'ritmo', 'zoom')[i % 3],
                      ending=('pixel', 'glitch', 'zoom', 'tendina', 'loop')[i], duration=3)
        path = Path(folder, f'{i}.mp4')
        module.render_video(config, LOGO, CREST, path, None, 6, 3, 'Story 9:16', 1)
        prepared = module.scene(config, LOGO, CREST, None, 1)
        seconds = video_length(prepared, 3)
        prepared[0].info['duration'] = seconds
        sounds.add_scene_audio(path, prepared, module.compose, seconds, .8, effects=True)
        assert path.stat().st_size > 10_000
        done.append(template+' video + audio')
    for track in tracks:
        assert len(sounds.chiptune(2, 0, track=track)) > 0
        music.preview_wav(track) if track in music.TRACKS or real.is_real(track) else None
    done.append('tutte le musiche')
    scenes = [(MODULES[t].scene(dict(apply_preset(defaults(t), 'crt'), theme='none', music=True), LOGO, None, None, 1),
               MODULES[t].compose) for t in ('Matchday Screen', 'Classifica')]
    transitions.render_sequence(scenes, ['pixel'], Path(folder, 'seq.mp4'), 6, 1.0, .5, 'Post 1:1', 1, sound=True)
    done.append('sequenza video')
import reparti_renderer, wrapped_renderer, sponsor, team_photo, team_looks
convocati = dict(defaults('Convocati'))
squad = team_looks.OFFICIAL_SQUAD
for i, person in enumerate(squad[:12]):
    convocati['roster'][i] = dict(number=person.get('number', i+1), name=person['name'], role=person.get('role', 'C'), captain=False)
convocati['roster_count'] = 12
for _, slide in reparti_renderer.slides(convocati, squad)[:2]:
    reparti_renderer.png_bytes(slide, LOGO, None, None, 'Story 9:16', 1, 1)
done.append('reparti')
wrapped_renderer.png_bytes(dict(defaults('Classifica'), theme='none'), LOGO, None, None, 'Story 9:16', 1, 1)
done.append('wrapped')
sponsor.scene(dict(defaults('Classifica'), theme='none'), None, None, None, 1)
done.append('sponsor')
team_photo.png_bytes(squad, 'crt', LOGO)
done.append('foto di squadra')
import cards, card_video, pagelle, album
teu = dict(next(p for p in squad if p['name'] == 'TEU'), edition='mvp', vote=8.5,
           stats=[('GOL', '2'), ('RISULTATO', '3-1'), ('GIORNATA', '7')], serial=(9, 15))
cards.card_png(teu, LOGO, 600)
card_video.poster(teu, LOGO, 'Post 4:5', 1, 'FLAMINGOS 3-1 UNITED FLERO')
rows = [dict(p, vote=v, goals=g) for p, v, g in zip(squad[1:6], (6.5, 7, 8.5, 6, 5.5), (0, 1, 2, 0, 0))]
with tempfile.TemporaryDirectory() as folder:
    card_video.render_video(teu, LOGO, Path(folder, 'f.mp4'), 8, 'Post 1:1', .5, 'cc0_battle', 'prova', True, .8, 5.0)
    pagelle.render_video(rows, {'line': 'A 1-0 B'}, LOGO, Path(folder, 'p.mp4'), 8, 'Post 1:1', .5, 'cc0_funk', True, .8, 5.0)
pagelle.png_bytes(rows, {'line': 'A 1-0 B'}, LOGO, 'Post 4:5', 1)
album.png_bytes(album.members_for(squad), LOGO, 'Post 4:5', 1)
album.zip_bytes(album.members_for(squad)[:2], LOGO, 300)
done.append('figurine, bustina, pagelle, album')
import figurine_style, figurine_scenes
style = figurine_style.key_for('stadium', defaults('Full Time'))
card_video.poster(teu, LOGO, 'Story 9:16', 1, 'prova', figurine_style.build(style, 'Story 9:16', 540))
seq = [figurine_scenes.scene('Figurina MVP', {'spec': teu}, LOGO, 1, style),
       figurine_scenes.scene('Pagelle', {'rows': rows, 'info': {'line': 'A 1-0 B'}}, LOGO, 1, style),
       figurine_scenes.scene('Album', {'members': album.members_for(squad)[:4]}, LOGO, 1, None)]
with tempfile.TemporaryDirectory() as folder:
    transitions.render_sequence(seq, ['olografica', 'pagina'], Path(folder, 's.mp4'), 8, 2.0, .5, 'Post 4:5', 1, sound=True)
for kind in transitions.SPECIAL:
    transitions.transition_frame(kind, Image.new('RGB', (54, 96)), Image.new('RGB', (54, 96), (255, 0, 0)), .5)
done.append('stili dei preset, sequenza con figurine e transizioni da collezione')
import results_round
games = [dict(home='GALBA F.C.', away='FLAMINGOS', date='2026-10-24', time='20:45', score=[2, 4], venue='', round=5),
         dict(home='REAL BRESCIA', away='CHIARI', date='2026-10-26', time='21:00', score=None, venue='', round=5)]
group = results_round.rounds(games)[0]
lines = results_round.rows_for(group)
results_round.png_bytes(lines, LOGO, 'Post 4:5', 1, figurine_style.build(style, 'Post 4:5', 540), subtitle='GIORNATA 5')
with tempfile.TemporaryDirectory() as folder:
    results_round.render_video(lines, LOGO, Path(folder, 'r.mp4'), 8, 'Post 1:1', .5, 'cc0_ritmo', True)
    transitions.render_sequence([figurine_scenes.scene('Risultati', {'rows': lines}, LOGO, 1, None)], [],
                                Path(folder, 'rs.mp4'), 8, 2.0, .5, 'Story 9:16', 1)
done.append('risultati della giornata')
print('OK: '+', '.join(done))
'''


def runtime_problems():
    local = sorted(p.stem for p in ROOT.glob('*.py'))
    script = BLOCKER % {'allowed': sorted(allowed_imports()), 'local': local, 'root': str(ROOT)}+RUN.replace('__ROOT__', repr(str(ROOT)))
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    if result.returncode != 0:
        return [result.stderr.strip()[-1500:]], ''
    return [], result.stdout.strip()


def main():
    problems = static_problems()
    runtime, report = runtime_problems()
    problems += runtime
    if problems:
        print('PROBLEMI per Streamlit Cloud:')
        for line in problems:
            print(' -', line)
        return 1
    print(report)
    print('Pronto per Streamlit Cloud.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
