"""Ready-to-copy Instagram captions in a retro pixel / arcade voice.

Every editor gets several variants. Full Time picks its set from the result
(big win, win, draw, defeat, penalties); Classifica from our position.
Pure functions, no Streamlit: easy to test and to extend with new lines.
"""
from __future__ import annotations

import re

HASHTAGS = '#Flamingos #CalcioA7 #CSIBrescia #SerieC #Amatori #PixelFootball #RetroGaming'


def _clean(value, fallback=''):
    value = str(value or '').strip()
    if not value or re.fullmatch(r'[A-Z]{2}/[A-Z]{2}/[A-Z]{4}|HH:MM|AVVERSARI|GG/MM/AAAA', value):
        return fallback
    return value


def _title(value):
    """'REAL BOVEZZO' -> 'Real Bovezzo', keeping short acronyms like UMC or F.C."""
    words = []
    for word in str(value).split():
        bare = word.replace('.', '')
        words.append(word if (len(bare) <= 3 and bare.isupper()) or any(ch.isdigit() for ch in word) else word.capitalize())
    return ' '.join(words)


def _lines(*parts):
    return '\n'.join(p for p in parts if p is not None).strip()


def _ours_and_opponent(config):
    home, away = config.get('home_name', ''), config.get('away_name', '')
    if config.get('our_side', 'Casa') == 'Casa':
        return _title(home), _title(away), True
    return _title(away), _title(home), False


def matchday(config):
    ours, opp, home = _ours_and_opponent(config)
    opp = _clean(opp, 'il prossimo avversario')
    date = _clean(config.get('date'))
    time = _clean(config.get('kickoff'))
    venue = _title(_clean(config.get('venue')))
    when = ' / '.join(p for p in (date, time) if p)
    where = ('Si gioca in casa' if home else 'In trasferta') + (f': {venue}' if venue else '')
    return [
        _lines('▶ PRESS START', '', f'🕹️ {ours} vs {opp}', f'📅 {when}' if when else None, f'📍 {where}', '',
               'Player 1 pronto. Il controller è carico. Ci vediamo in campo 💗', '', HASHTAGS),
        _lines('📺 CH.07 / MATCHDAY', '', f'Sintonizzatevi: stasera va in onda {ours} - {opp}.' if not date else
               f'Sintonizzatevi: {date} va in onda {ours} - {opp}.',
               f'⏰ Calcio d\'inizio {time}' if time else None, f'📍 {venue}' if venue else None, '',
               'Niente telecomando: venite a vederla dal vivo 🦩', '', HASHTAGS),
        _lines('👾 NEW CHALLENGER APPROACHING', '', f'{opp.upper()} entra nel livello.', 'I Flamingos accettano la sfida.', '',
               f'{"🏠" if home else "🚌"} {where}', f'🕹️ {when}' if when else None, '', 'INSERT COIN TO CONTINUE ▮', '', HASHTAGS),
        _lines('💾 LOADING MATCHDAY...', '▓▓▓▓▓▓▓▓░░ 80%', '', f'{ours} 🆚 {opp}', f'{when}' if when else None, venue or None,
               '', 'Il resto lo carichiamo in campo. Forza Flamingos! 💗', '', HASHTAGS),
    ]


def convocati(config):
    opp = _title(_clean(config.get('opponent'), 'il prossimo avversario'))
    count = int(config.get('roster_count', 12))
    meeting = _clean(config.get('meeting_time'))
    kickoff = _clean(config.get('kickoff'))
    venue = _title(_clean(config.get('venue')))
    date = _clean(config.get('date'))
    roster = [r for r in config.get('roster', [])[:count] if str(r.get('name', '')).strip()]
    captain = next((r['name'] for r in roster if r.get('captain')), '')
    names = ' / '.join(_title(r['name']) for r in roster if not str(r['name']).startswith('GIOCATORE '))
    return [
        _lines('🎮 SELECT YOUR PLAYERS', '', f'Ecco i {count} convocati per la sfida contro {opp}.',
               f'📅 {date}' if date else None, f'⏱️ Ritrovo {meeting}' if meeting else None,
               f'⚽ Kick off {kickoff}' if kickoff else None, f'📍 {venue}' if venue else None, '',
               f'Capitano: {_title(captain)} ⭐' if captain else None, '', HASHTAGS),
        _lines('📋 PARTY COMPLETO', '', names or None, '', f'Missione: {opp}.', 'Equipaggiamento pronto, borraccia carica 💧',
               f'Appuntamento alle {meeting}.' if meeting else None, '', HASHTAGS),
        _lines('💾 SAVE FILE: CONVOCATI', '', f'{count} giocatori salvati in memoria per {opp}.',
               'Chi non c\'è ci tifa da casa: il multiplayer funziona anche a distanza 🦩', '', HASHTAGS),
    ]


def starting7(config):
    team = _title(_clean(config.get('team_name'), 'Flamingos'))
    names = [str(p.get('name', '')).strip() for p in config.get('players', [])]
    lineup = ' / '.join(_title(n) for n in names if n)
    formation = _clean(config.get('formation_text'))
    return [
        _lines('🕹️ STARTING 7 / PLAYER SELECT', '', lineup or None, formation or None, '',
               f'Questi i sette di {team} che premono START oggi. 💗', '', HASHTAGS),
        _lines('👾 LINE UP CARICATA', '', 'Portiere, difesa, centrocampo, attacco: tutti i pixel al loro posto.',
               lineup or None, '', 'GO GO FLAMINGOS ▶▶', '', HASHTAGS),
        _lines('📺 IN ONDA ADESSO', '', f'La formazione di {team} è sul tabellone.', formation or None, '', 'Stay tuned 📡', '', HASHTAGS),
    ]


def outcome(config):
    """big_win, win, draw, defeat, big_defeat, pen_win, pen_loss."""
    home, away = int(config.get('home_score', 0)), int(config.get('away_score', 0))
    ours_home = config.get('our_side', 'Casa') == 'Casa'
    us, them = (home, away) if ours_home else (away, home)
    if config.get('show_penalties') and home == away:
        ph, pa = int(config.get('home_penalties', 0)), int(config.get('away_penalties', 0))
        pu, pt = (ph, pa) if ours_home else (pa, ph)
        if pu != pt:
            return 'pen_win' if pu > pt else 'pen_loss'
    if us == them:
        return 'draw'
    if us > them:
        return 'big_win' if us-them >= 3 else 'win'
    return 'big_defeat' if them-us >= 3 else 'defeat'


def _scorers(config):
    field = 'home_scorers' if config.get('our_side', 'Casa') == 'Casa' else 'away_scorers'
    lines = [l.strip() for l in str(config.get(field, '')).splitlines() if l.strip()]
    return ', '.join(_title(l) for l in lines)


def fulltime(config):
    ours, opp, home = _ours_and_opponent(config)
    opp = _clean(opp, 'gli avversari')
    h, a = int(config.get('home_score', 0)), int(config.get('away_score', 0))
    score = f'{_title(config.get("home_name", ""))} {h}-{a} {_title(config.get("away_name", ""))}'
    scorers = _scorers(config)
    goals = f'⚽ {scorers}' if scorers else None
    pens = ''
    if config.get('show_penalties') and h == a:
        pens = f' (d.c.r. {config.get("home_penalties", 0)}-{config.get("away_penalties", 0)})'
    kind = outcome(config)
    sets = {
        'big_win': [
            _lines('🏆 HIGH SCORE!', '', score+pens, goals, '', 'Combo infinita, barra della vita piena. Partita da salvare nel floppy 💾', '', HASHTAGS),
            _lines('👾 FLAWLESS VICTORY', '', score, goals, '', f'{opp} non ha trovato il pulsante pausa. Che serata 💗🦩', '', HASHTAGS),
            _lines('⭐ LEVEL UP x3', '', score, goals, '', 'Tre punti, tanti gol e zero bug. Avanti così.', '', HASHTAGS),
        ],
        'win': [
            _lines('🏁 STAGE CLEAR', '', score, goals, '', 'Tre punti in tasca. Il livello successivo ci aspetta ▶', '', HASHTAGS),
            _lines('🎮 YOU WIN!', '', score, goals, '', 'Sudata, giocata, vinta. Flamingos 1UP 💗', '', HASHTAGS),
            _lines('💾 PARTITA SALVATA', '', score, goals, '', f'Vittoria contro {opp}: progressi registrati in classifica 📈', '', HASHTAGS),
        ],
        'draw': [
            _lines('⏸️ PAUSA / PAREGGIO', '', score, goals, '', 'Un punto che muove la classifica. Si riparte dal checkpoint.', '', HASHTAGS),
            _lines('🤝 TIE GAME', '', score, goals, '', 'Nessun vincitore in questo round. Il prossimo è nostro 🦩', '', HASHTAGS),
            _lines('📺 SEGNALE DIVISO', '', score, goals, '', f'Un punto a testa con {opp}. Ricarichiamo le batterie 🔋', '', HASHTAGS),
        ],
        'defeat': [
            _lines('💔 GAME OVER?', '', score, goals, '', 'No: CONTINUE? 9... 8... 7... Premiamo START e si riparte.', '', HASHTAGS),
            _lines('📼 REWIND', '', score, goals, '', 'Si riguarda il nastro, si impara, si torna in campo più forti 💗', '', HASHTAGS),
            _lines('🕹️ RETRY', '', score, goals, '', 'Oggi il livello ha vinto lui. La prossima partita è un nuovo tentativo.', '', HASHTAGS),
        ],
        'big_defeat': [
            _lines('⚠️ SYSTEM ERROR', '', score, goals, '', 'Serata storta, riavvio in corso... Si torna online più forti 🔄', '', HASHTAGS),
            _lines('📼 NASTRO DA RIAVVOLGERE', '', score, goals, '', 'Testa alta Flamingos: il prossimo round si gioca a modo nostro 💗', '', HASHTAGS),
        ],
        'pen_win': [
            _lines('🎯 SUDDEN DEATH: WIN', '', score+pens, goals, '', 'Nervi d\'acciaio dal dischetto. Partita chiusa ai rigori 💗', '', HASHTAGS),
            _lines('👾 BONUS STAGE SUPERATO', '', score+pens, '', 'Ai rigori il controller lo avevamo noi 🎮', '', HASHTAGS),
        ],
        'pen_loss': [
            _lines('🎯 SUDDEN DEATH', '', score+pens, goals, '', 'Decide il dischetto e stavolta dice no. Orgogliosi lo stesso 💗', '', HASHTAGS),
            _lines('💔 CONTINUE?', '', score+pens, '', 'Ai rigori è una lotteria: ci rifacciamo al prossimo round.', '', HASHTAGS),
        ],
    }
    return sets[kind]


def classifica(config, rows=None):
    from classifica_renderer import active_rows, is_ours, zone_of
    rows = rows if rows is not None else active_rows(config)
    ours = config.get('our_team', 'FLAMINGOS')
    me = next((r for r in rows if is_ours(r.get('team', ''), ours)), None)
    when = _clean(config.get('round_label'))
    head = f'📊 CLASSIFICA / {when.upper()}' if when else '📊 CLASSIFICA AGGIORNATA'
    if not me:
        return [_lines(head, '', 'Il girone dopo l\'ultima giornata. Dove ci vedete a fine stagione? 👇', '', HASHTAGS)]
    pos, pts = int(me['pos']), int(me['pt'])
    zone = zone_of(pos, config)
    leader = rows[0] if rows else None
    gap = int(leader['pt'])-pts if leader and leader is not me else 0
    stat = f'🦩 {pos}° posto / {pts} punti / {me["g"]} giocate'
    if pos == 1:
        texts = ['👑 PLAYER 1 IN TESTA', 'Primo posto in classifica: il cursore è su di noi. Restiamo li 💗',
                 '🏆 HIGH SCORE TABLE: NUMERO 1', 'Siamo in cima al tabellone. Ora difendere il record.']
    elif zone == 'promo':
        texts = ['🚀 ZONA PROMOZIONE', f'In zona salto diretto: {gap} punti dalla vetta. Teniamo premuto ▶',
                 '⬆️ LEVEL UP IN VISTA', 'Siamo tra chi sale direttamente. Nessun calo di frame adesso.']
    elif zone == 'playoff':
        texts = ['🎯 ZONA SPAREGGIO', f'Dentro gli spareggi, a {gap} punti dalla vetta. Il boss finale si avvicina 👾',
                 '🕹️ BONUS STAGE IN VISTA', 'Posto da spareggio per salire: ogni punto adesso vale doppio.']
    else:
        promo_line = int(config.get('promo_count', 3))+int(config.get('playoff_count', 2))
        target = next((r for r in rows if int(r['pos']) == promo_line), None)
        need = int(target['pt'])-pts if target else 0
        texts = ['📈 LA RIMONTA È IN CARICAMENTO', f'{need} punti dalla zona spareggio: la partita è ancora tutta da giocare 💗' if need > 0
                 else 'La zona spareggio è a un passo: serve la combo giusta.',
                 '🎮 CONTINUE? YES', 'Classifica corta, stagione lunga. Si sale un livello alla volta.']
    return [
        _lines(head, '', stat, '', f'{texts[0]}', texts[1], '', HASHTAGS),
        _lines(f'{texts[2]}', '', stat, '', texts[3], '', HASHTAGS),
        _lines('💾 SALVATAGGIO CLASSIFICA', when or None, '',
               *[f'{int(r["pos"]):>2}. {_title(r["team"])} {r["pt"]}' for r in rows[:5]], '...', stat, '', HASHTAGS),
    ]


def calendario(config):
    month = _clean(config.get('month_label'), 'questo mese')
    rows = [r for r in config.get('fixtures', [])[:int(config.get('fixture_count', 4))] if str(r.get('opponent', '')).strip()]
    lines = [f'{r.get("date", "")} {"🏠" if r.get("side", "C") == "C" else "🚌"} vs {_title(r["opponent"])}'
             + (f' / {r["time"]}' if r.get('time') else '') + (f' / {r["score"]}' if r.get('score') else '') for r in rows]
    return [
        _lines(f'🗓️ CALENDARIO / {month.upper()}', '', *lines, '', 'Segnatevi le date: il multiplayer è aperto a tutti i tifosi 💗', '', HASHTAGS),
        _lines('📺 PALINSESTO DEL MESE', '', *lines, '', 'Tutte le puntate in diretta dal campo. Non cambiate canale 📡', '', HASHTAGS),
        _lines('🕹️ NEXT LEVELS', '', *lines, '', 'Un livello alla volta, insieme. Forza Flamingos 🦩', '', HASHTAGS),
    ]


GENERATORS = {'Matchday Screen': matchday, 'Convocati': convocati, 'Starting 7': starting7,
              'Full Time': fulltime, 'Classifica': classifica, 'Calendario': calendario}


def captions(template, config):
    generator = GENERATORS.get(template)
    return [text for text in (generator(config) if generator else []) if text.strip()]
