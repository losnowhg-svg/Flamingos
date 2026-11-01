"""Figurine e pagelle (3.9): the data side, without Streamlit.

Who played (from the Convocati list), their goals (from the Full Time scorers),
the match line, the default stats and caption of each card edition, votes as
the pagelle write them (6½), and the season's MVP collection that feeds the
album's rarities.
"""
from __future__ import annotations

import datetime as dt
import re

import cards

VOTE_OPTIONS = ['']+[cards.vote_text(x/2) for x in range(8, 21)]      # '', '4', '4½', ... '10'
MAX_MVPS = 80


def parse_vote(value):
    """'6½', '6.5', '6,5', 6.5 -> 6.5; '' / 'SV' / None -> None. Clamped to 4-10 on half points."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().upper().replace(',', '.')
        if not text or text in ('SV', 'S.V.', '-'):
            return None
        half = text.endswith('½')
        text = text.rstrip('½').strip()
        try:
            number = float(text)+(.5 if half else 0)
        except ValueError:
            return None
    if number != number:
        return None
    return max(4.0, min(10.0, round(number*2)/2))


def season_label(date_text=None, today=None):
    """'GG/MM/AAAA' (or today) -> '2026/27': seasons start in August."""
    day = None
    try:
        day = dt.datetime.strptime(str(date_text).strip(), '%d/%m/%Y').date()
    except (TypeError, ValueError):
        day = today or dt.date.today()
    start = day.year if day.month >= 8 else day.year-1
    return f'{start}/{str(start+1)[-2:]}'


def _key(name):
    return ' '.join(str(name).upper().split())


def ours(fulltime):
    """('home'|'away') for our side in a Full Time config."""
    return 'away' if fulltime.get('our_side', 'Casa') == 'Ospiti' else 'home'


def goals_by_player(fulltime):
    """{NAME: goals} from our scorers in the Full Time editor."""
    from fulltime_renderer import scorer_goals
    out = {}
    for name in scorer_goals(fulltime.get(ours(fulltime)+'_scorers', '')):
        if name:
            out[_key(name)] = out.get(_key(name), 0)+1
    return out


def score_line(fulltime):
    """'FLAMINGOS 3-1 UNITED FLERO' (home first, as on the scoreboard)."""
    home, away = _key(fulltime.get('home_name', '')), _key(fulltime.get('away_name', ''))
    return f"{home} {int(fulltime.get('home_score', 0))}-{int(fulltime.get('away_score', 0))} {away}".strip()


def score_for_us(fulltime):
    """'3-1' with our goals first."""
    a, b = int(fulltime.get('home_score', 0)), int(fulltime.get('away_score', 0))
    return f'{a}-{b}' if ours(fulltime) == 'home' else f'{b}-{a}'


def opponent(fulltime):
    return _key(fulltime.get('away_name' if ours(fulltime) == 'home' else 'home_name', ''))


def conceded(fulltime):
    a, b = int(fulltime.get('home_score', 0)), int(fulltime.get('away_score', 0))
    return b if ours(fulltime) == 'home' else a


def played(convocati, squad):
    """The people who played: the active Convocati list (with look, role and number from the squad),
    or every player of the squad when the list still holds the example names."""
    by_name = {_key(p['name']): p for p in squad or []}
    active = [p for p in (convocati or {}).get('roster', [])[:(convocati or {}).get('roster_count', 0)]
              if str(p.get('name', '')).strip() and not str(p['name']).startswith('GIOCATORE ')]
    out = []
    for p in active:
        known = by_name.get(_key(p['name']), {})
        role = p.get('role') if p.get('role') in ('P', 'D', 'C', 'A') else known.get('role', 'C')
        out.append(dict(name=_key(p['name']), number=int(p.get('number') or known.get('number') or 0),
                        role=role if role in cards.ROLES else 'C', look=known.get('look'), avatar=known.get('avatar', ''),
                        captain=bool(p.get('captain'))))
    if not out:
        team = [p for p in squad or [] if p.get('role') in ('P', 'D', 'C', 'A')] or \
            [p for p in squad or [] if p.get('role') not in ('ALL', 'DIR')]        # roles not set yet: everybody
        out = [dict(name=_key(p['name']), number=int(p.get('number') or 0),
                    role=p.get('role') if p.get('role') in ('P', 'D', 'C', 'A') else 'C', look=p.get('look'),
                    avatar=p.get('avatar', ''), captain=False) for p in team]
    return out


def season_numbers(name, scorers, games):
    goals = next((int(s.get('goals') or 0) for s in scorers or [] if _key(s.get('name', '')) == _key(name)), 0)
    count = len(games or [])
    return goals, count


def stats_for(edition, member, ctx):
    """The three stats printed on a card, by edition. ctx: fulltime, round, scorers, games, mvps."""
    fulltime = ctx.get('fulltime') or {}
    name = _key(member.get('name', ''))
    number = int(member.get('number') or 0)
    role = cards.ROLES.get(member.get('role'), cards.ROLES['C'])[0]
    match_goals = goals_by_player(fulltime).get(name, 0)
    goals, games = season_numbers(name, ctx.get('scorers'), ctx.get('games'))
    round_ = int(ctx.get('round') or 0)
    mvps = sum(1 for m in ctx.get('mvps') or [] if _key(m.get('name', '')) == name)
    shirt = f'#{number}' if number else '-'
    if edition == 'mvp':
        return [('GOL', str(match_goals)), ('RISULTATO', score_for_us(fulltime)), ('GIORNATA', str(round_) if round_ else '-')]
    if edition == 'bomber':
        average = f'{goals/games:.1f}'.replace('.', ',') if games else '-'
        return [('GOL', str(goals)), ('PARTITE', str(games) if games else '-'), ('MEDIA', average)]
    if edition == 'muro':
        return [('GOL SUBITI', str(conceded(fulltime))), ('RISULTATO', score_for_us(fulltime)),
                ('GIORNATA', str(round_) if round_ else '-')]
    if edition == 'auguri':
        return [('MAGLIA', shirt), ('RUOLO', role), ('MVP', str(mvps))]
    if edition in ('capitano', 'benvenuto'):
        return [('RUOLO', role), ('MAGLIA', shirt), ('STAGIONE', ctx.get('season', '2026/27')[-5:])]
    return [('MVP', str(mvps)), ('GOL', str(goals)), ('MAGLIA', shirt)]


def caption_for(edition, member, ctx):
    """The line under the card in the video and the post."""
    fulltime = ctx.get('fulltime') or {}
    name = _key(member.get('name', ''))
    round_ = int(ctx.get('round') or 0)
    tail = f' · GIORNATA {round_}' if round_ else ''
    if edition == 'mvp':
        return score_line(fulltime)+tail
    if edition == 'muro':
        return 'PORTA INVIOLATA · '+score_line(fulltime)
    if edition == 'bomber':
        goals, games = season_numbers(name, ctx.get('scorers'), ctx.get('games'))
        return f'{goals} GOL IN {games} PARTITE' if games else f'{goals} GOL IN STAGIONE'
    if edition == 'auguri':
        return f'TANTI AUGURI {name}!'
    if edition == 'benvenuto':
        return f'BENVENUTO {name}!'
    if edition == 'capitano':
        return 'IL NOSTRO CAPITANO'
    return ''


def award_date(*candidates, today=None):
    """The first real date among the match's ('GG/MM/AAAA' placeholders skipped), else today."""
    for value in candidates:
        try:
            return dt.datetime.strptime(str(value).strip(), '%d/%m/%Y').strftime('%d/%m/%Y')
        except (TypeError, ValueError):
            continue
    return (today or dt.date.today()).strftime('%d/%m/%Y')


def add_mvp(mvps, entry):
    """The collection with this MVP added once (same date and name = the same award)."""
    entry = sanitize_mvp(entry)
    if entry is None:
        return list(mvps or [])
    kept = [m for m in mvps or [] if not (m.get('date') == entry['date'] and m.get('name') == entry['name'])]
    return (kept+[entry])[-MAX_MVPS:]


def sanitize_mvp(raw):
    if not isinstance(raw, dict):
        return None
    name = re.sub(r'\s+', ' ', str(raw.get('name', ''))).strip().upper()[:27]
    if not name:
        return None
    vote = parse_vote(raw.get('vote'))
    return dict(name=name, date=str(raw.get('date', ''))[:10], opp=re.sub(r'\s+', ' ', str(raw.get('opp', ''))).strip()[:40],
                score=str(raw.get('score', ''))[:7], vote=vote, round=max(0, min(99, int(raw.get('round') or 0)))
                if str(raw.get('round') or '0').isdigit() else 0)


def sanitize_mvps(raw):
    out = []
    for item in (raw if isinstance(raw, list) else [])[:MAX_MVPS]:
        clean = sanitize_mvp(item)
        if clean:
            out.append(clean)
    return out


# --- Captions for the posts ---------------------------------------------------------------------------

def _title(name):
    return ' '.join(w.capitalize() for w in str(name).split())


def _tag(member):
    handle = (member or {}).get('ig')
    return f' (@{handle})' if handle else ''


def pagelle_caption(rows, mvp, fulltime):
    """The caption of the ratings post: MVP, scorers, the best marks."""
    from captions import HASHTAGS
    by = {r['name']: r for r in rows}
    best = by.get(mvp)
    scorers = [f"{_title(r['name'])}{' x'+str(r['goals']) if int(r.get('goals') or 0) > 1 else ''}"
               for r in rows if int(r.get('goals') or 0) > 0]
    high = [f"{_title(r['name'])} {cards.vote_text(r['vote'])}" for r in sorted(rows, key=lambda r: -float(r['vote']))
            if float(r['vote']) >= 7 and r['name'] != mvp][:4]
    lines = [f'📝 LE PAGELLE / {score_line(fulltime)}', '']
    if best:
        lines.append(f"🃏 MVP: {_title(best['name'])} {cards.vote_text(best['vote'])}{_tag(best)}")
    if scorers:
        lines.append('⚽ Gol: '+', '.join(scorers))
    if high:
        lines.append('⭐ Bene anche: '+', '.join(high))
    lines += ['', 'D\'accordo con i voti? Ditecelo nei commenti 👇', '', HASHTAGS+' #Pagelle']
    return '\n'.join(lines)


def card_caption(edition, member, ctx, vote=None, rarity='base'):
    """The caption of a card post, in the studio's arcade voice."""
    from captions import HASHTAGS
    name = _title(member.get('name', ''))
    tag = _tag(member)
    fulltime = ctx.get('fulltime') or {}
    opp = _title(opponent(fulltime))
    rare = cards.RARITIES.get(rarity, cards.RARITIES['base'])['name']
    vote_txt = f' con voto {cards.vote_text(vote)}' if vote is not None else ''
    goals, games = season_numbers(member.get('name', ''), ctx.get('scorers'), ctx.get('games'))
    first = {
        'mvp': ('🃏 CARTA SPECIALE TROVATA!', f'Nella bustina c\'era {name}{tag}: MVP contro {opp}{vote_txt} ({score_for_us(fulltime)}).'),
        'bomber': ('💥 FIGURINA LEGGENDARIA', f'{name}{tag}, {goals} gol in stagione: è lui il bomber dei Flamingos.'),
        'muro': ('🧤 PORTA INVIOLATA', f'{name}{tag} ha abbassato la saracinesca contro {opp}{vote_txt}.'),
        'capitano': ('⭐ IL NOSTRO CAPITANO', f'{name}{tag}: fascia al braccio, figurina in collezione.'),
        'benvenuto': ('🆕 NUOVO ACQUISTO', f'Benvenuto {name}{tag}! La sua prima figurina è già nell\'album.'),
        'auguri': ('🎂 TANTI AUGURI', f'Oggi la figurina è tutta per {name}{tag}. Buon compleanno!'),
    }.get(edition, ('🃏 FIGURINE FLAMINGOS', f'La figurina di {name}{tag}, stagione {ctx.get("season", "")}.'))
    return '\n'.join([first[0], '', first[1], f'Rarità: {rare} ✨', '', 'Collezionatele tutte 🦩', '',
                      HASHTAGS+' #Figurine'])
