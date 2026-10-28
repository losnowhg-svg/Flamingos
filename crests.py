"""Crests of the other teams in the girone, built into the app.

The PNGs in assets/stemmi/ were cut out of screenshots and cleaned (background
removed, colours flattened, upscaled). They are offered next to the logos of
the browser archive with ids 'stemma:<slug>', and the opponent's crest is set
automatically when the match of the week names a team we know.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).resolve().parent/'assets'/'stemmi'
PREFIX = 'stemma:'
# slug: (display name, other names the CSI site or a person may use)
TEAMS = {
    'umc': ('UMC', ()),
    'sporting_leno': ('Sporting Leno', ('ASD SPORTING LENO', 'LENO')),
    'united_flero': ('United Flero', ('FLERO',)),
    'pirati': ('Pirati', ('ASD PIRATI', 'PIRATI CCS', 'PIRATI C.C.S. FOOTBALL CLUB')),
    'caste_united': ('Caste United', ('CASTE',)),
    'gso_poncarale': ('GSO Poncarale', ('G.S.O. PONCARALE', 'PONCARALE')),
    'fc_mustangs': ('FC Mustangs', ('MUSTANGS',)),
    'as_ardens': ('AS Ardens 2002', ('A.S. ARDENS', 'ARDENS')),
    'castel_mella': ('Castel Mella', ('CASTELMELLA', 'ORATORIO CASTELMELLA CALCIO', 'CASTEL MELLA CALCIO')),
    'gso_verolan': ('GSO Verolan', ('VEROLAN', 'VEROLANUOVA', 'GSO VEROLANUOVA', 'G. GAGGIA VEROLANUOVA')),
    'lions_25': ('Lions 25', ('LIONS25', 'LIONS')),
    'galba_fc': ('Galba FC', ('GALBA', 'GALBA F.C.')),
}
NOISE = {'ASD', 'AS', 'A', 'S', 'D', 'GSO', 'G', 'O', 'FC', 'F', 'C', 'SSD', 'US', 'AC', 'POL', 'CALCIO', 'ORATORIO',
         'GS', 'ASS', 'SPORTIVA', 'SQUADRA', 'TEAM'}


def key(name):
    words = [w for w in re.sub(r'[^A-Z0-9]+', ' ', str(name).upper()).split() if w not in NOISE]
    return ''.join(words)


def match(team_name):
    """The slug of a known team for a name as written anywhere (CSI, a person), or None."""
    target = key(team_name)
    if len(target) < 3:
        return None
    best, best_len = None, 0
    for slug, (name, aliases) in TEAMS.items():
        for alias in (name,)+aliases:
            k = key(alias)
            # the alias inside the name, or the name covering most of the alias (UNITED alone is ambiguous)
            if len(k) >= 3 and (k in target or (target in k and len(target) >= .6*len(k))) and len(k) > best_len:
                best, best_len = slug, len(k)
    return best


def logo_id_for(team_name):
    slug = match(team_name)
    return PREFIX+slug if slug and (FOLDER/f'{slug}.png').exists() else None


@lru_cache(maxsize=1)
def builtin_assets():
    """{'stemma:<slug>': asset} in the same shape as the browser archive's logos."""
    out = {}
    for slug, (name, _) in TEAMS.items():
        path = FOLDER/f'{slug}.png'
        if path.exists():
            out[PREFIX+slug] = {'kind': 'logo', 'name': f'{name} (girone)', 'bytes': path.read_bytes(), 'builtin': True}
    return out


def register(library):
    """Make the girone crests available next to the archive's own logos (never saved to the browser)."""
    library['assets'].update(builtin_assets())
    return library


def auto_opponent_logo(match_fields):
    """Fill the opponent crest when it is unset or one of ours and the opponent is a known team."""
    current = match_fields.get('opponent_logo_id', 'none')
    if current in ('none', '') or str(current).startswith(PREFIX):
        found = logo_id_for(match_fields.get('opponent', ''))
        if found:
            match_fields['opponent_logo_id'] = found
        elif str(current).startswith(PREFIX):
            match_fields['opponent_logo_id'] = 'none'
    return match_fields
