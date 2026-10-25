"""Caption studio: hundreds of Instagram captions from the week's data.

A caption is assembled from pools of sentences - hook, core, details,
closer - each written in one of six tones. The facts (opponent, time,
score, scorers, position, streak, event, theme...) come from the editors,
the shared match, the squad and the CSI calendar; a sentence that needs a
fact we do not have is simply skipped. Pure Python, no Streamlit.
"""
from __future__ import annotations

import random
import re

TONES = {
    'epico': '🔥 Epico',
    'ironico': '😏 Ironico',
    'retro': '🕹️ Retro gamer',
    'telecronaca': "🎙️ Telecronaca anni '90",
    'sobrio': '📋 Sobrio',
    'spogliatoio': '🍻 Da spogliatoio',
}
TONE_IDS = tuple(TONES)
LENGTHS = {'corta': 'Corta', 'media': 'Media', 'lunga': 'Lunga'}
HASHTAG_LEVELS = {'nessuno': 'Nessuno', 'pochi': 'Pochi', 'tanti': 'Tanti'}
CONTEXTS = {
    'Matchday Screen': 'Matchday',
    'Convocati': 'Convocati',
    'Reparti': 'Presentazione reparti',
    'Full Time': 'Full Time',
    'Classifica': 'Classifica',
    'Calendario': 'Calendario',
}
TONE_EMOJI = {'epico': '🔥', 'ironico': '😏', 'retro': '🕹️', 'telecronaca': '🎙️', 'sobrio': '🦩', 'spogliatoio': '🍻'}
DETAIL_EMOJI = {'date': '📅', 'time': '⏰', 'venue': '📍', 'meeting': '⏱️', 'score': '⚽', 'scorers': '⚽', 'table': '📊',
                'streak': '📈', 'event': '🚨', 'theme': '✨', 'captain': '⭐', 'list': '📋', 'next': '➡️', 'month': '🗓️'}
MAX_CHARS = 2200
DAYS = ('lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica')
PLACEHOLDERS = re.compile(r'^(GG/MM/AAAA|HH:MM|AVVERSARI.*|GIOCATORE \d+|CAMPO / INDIRIZZO)$', re.I)


# --- Facts ---------------------------------------------------------------

def _clean(value):
    value = re.sub(r'\s+', ' ', str(value or '')).strip()
    return '' if not value or PLACEHOLDERS.match(value) else value


def title(value):
    """'UNITED FLERO' -> 'United Flero', keeping acronyms and numbers."""
    words = []
    for word in str(value).split():
        bare = word.replace('.', '')
        keep = (len(bare) <= 3 and bare.isupper() and bare not in ('VIA', 'DEL', 'DI')) or any(ch.isdigit() for ch in word)
        words.append(word if keep else word.capitalize())
    return ' '.join(words)


def _date_text(value):
    m = re.search(r'(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?', str(value or ''))
    if not m:
        return ''
    day, month = int(m.group(1)), int(m.group(2))
    year = m.group(3)
    try:
        import datetime as dt
        y = int(year)+(2000 if year and len(year) == 2 else 0) if year else dt.date.today().year
        return f'{DAYS[dt.date(y, month, day).weekday()]} {day}/{month}'
    except ValueError:
        return f'{day}/{month}'


def parse_scorers(text):
    """[(name, goals)] from lines like "TEU 12', 38'" or "CAVA x2"."""
    out = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line or line == '-':
            continue
        name = re.split(r"\s+\d|\s+x\d|\(", line)[0].strip(" -'")
        minutes = re.findall(r"\d{1,3}'", line)
        times = re.search(r'x\s*(\d)|\((\d)\)', line)
        goals = len(minutes) or (int(times.group(1) or times.group(2)) if times else 1)
        if name:
            out.append((' '.join(w.capitalize() for w in name.split()), max(1, goals)))
    return out


def name(value):
    """Player names: 'TEU' -> 'Teu', 'DE LUCA' -> 'De Luca'."""
    return ' '.join(w.capitalize() for w in str(value).split())


def _handle(squad, name):
    for p in squad or []:
        if p.get('name', '').upper() == str(name).upper() and p.get('ig'):
            return '@'+p['ig']
    return ''


def _streak(matches, ours):
    """(kind, n): ('vittorie', 3) / ('risultati utili', 4) from the most recent played games."""
    if not matches:
        return '', 0
    from csi_page import is_ours
    played = [m for m in matches if m.get('score') and (is_ours(m['home'], ours) or is_ours(m['away'], ours))]
    played.sort(key=lambda m: m['date'], reverse=True)
    results = []
    for m in played:
        a, b = m['score']
        us, them = (a, b) if is_ours(m['home'], ours) else (b, a)
        results.append('V' if us > them else 'N' if us == them else 'P')
    wins = next((i for i, r in enumerate(results) if r != 'V'), len(results))
    if wins >= 2:
        return 'vittorie', wins
    unbeaten = next((i for i, r in enumerate(results) if r == 'P'), len(results))
    if unbeaten >= 3:
        return 'risultati utili', unbeaten
    return '', 0


def build_facts(template, config, match=None, squad=None, matches=None, standings=None):
    """Everything a caption may mention, as plain strings / numbers. Missing = absent."""
    import themes
    match = match or {}
    f = {'ours': 'Flamingos'}
    ours_name = _clean(match.get('our_name')) or 'FLAMINGOS'
    opp = ''
    home = None
    if template in ('Matchday Screen', 'Full Time'):
        home = config.get('our_side', 'Casa') == 'Casa'
        opp = _clean(config.get('away_name' if home else 'home_name'))
    elif template in ('Convocati', 'Reparti'):
        opp = _clean(config.get('opponent'))
    opp = opp or _clean(match.get('opponent'))
    if home is None and match.get('our_side'):
        home = match['our_side'] == 'Casa'
    if opp:
        f['opp'] = title(opp)
    if home is not None:
        f['where'] = 'in casa' if home else 'in trasferta'
        f['home'] = home
    date = _date_text(config.get('date')) or _date_text(match.get('date'))
    if date:
        f['date'] = date
    for key, source in (('time', 'kickoff'), ('meeting', 'meeting_time'), ('venue', 'venue')):
        value = _clean(config.get(source)) or _clean(match.get(source))
        if value:
            f[key] = title(value) if key == 'venue' else value
    if match.get('round'):
        f['round'] = str(match['round'])
    theme = themes.resolve(dict(config, theme=config.get('theme', 'auto')))
    if theme in themes.EVENTS:
        f['event'] = {'derby': 'derby', 'bigmatch': 'big match', 'ultima': 'ultima giornata'}[theme]
    elif theme:
        f['season'] = themes.THEMES[theme]['name']
    kind, n = _streak(matches, ours_name)
    if kind:
        f['streak'] = f'{n} {kind} di fila'

    if template == 'Full Time':
        a, b = int(config.get('home_score', 0)), int(config.get('away_score', 0))
        us, them = (a, b) if home else (b, a)
        f.update(us=us, them=them, score=f'{us}-{them}')
        if config.get('show_penalties') and a == b:
            pa, pb = int(config.get('home_penalties', 0)), int(config.get('away_penalties', 0))
            pu, pt = (pa, pb) if home else (pb, pa)
            f['pens'] = f'{pu}-{pt}'
            f['outcome'] = 'win' if pu > pt else 'loss' if pu < pt else 'draw'
        else:
            f['outcome'] = 'win' if us > them else 'loss' if us < them else 'draw'
        f['big'] = abs(us-them) >= 3
        if them == 0 and f['outcome'] == 'win':
            f['clean_sheet'] = 'Porta inviolata'
        scorers = parse_scorers(config.get('home_scorers' if home else 'away_scorers'))
        if scorers:
            parts = [(f'{n} ({g})' if g > 1 else n)+(' '+_handle(squad, n) if _handle(squad, n) else '') for n, g in scorers]
            f['scorers'] = ', '.join(parts)
            top = max(scorers, key=lambda s: s[1])
            f['top'] = top[0]
            if top[1] >= 2:
                f['top_goals'] = {2: 'doppietta', 3: 'tripletta', 4: 'poker'}.get(top[1], f'{top[1]} gol')

    if template in ('Convocati', 'Reparti'):
        count = int(config.get('roster_count', 0))
        roster = [r for r in config.get('roster', [])[:count] if _clean(r.get('name'))]
        if roster:
            f['count'] = str(len(roster))
            f['names'] = ', '.join(name(r['name'])+(' '+_handle(squad, r['name']) if _handle(squad, r['name']) else '')
                                   for r in roster)
            captain = next((r['name'] for r in roster if r.get('captain')), '')
            if captain:
                f['captain'] = name(captain)
            keepers = [name(r['name']) for r in roster if r.get('role') == 'P']
            if keepers:
                f['keepers'] = ' e '.join(keepers)
        staff = [name(p['name']) for p in squad or [] if p.get('role') == 'ALL']
        if staff:
            f['coach'] = staff[0]

    rows = standings if standings is not None else (config.get('standings', [])[:config.get('team_count', 0)]
                                                   if template == 'Classifica' else None)
    rows = [r for r in (rows or []) if _clean(r.get('team'))]
    if rows and not any(str(r['team']).startswith('SQUADRA ') for r in rows):
        mine = next((r for r in rows if ours_name.upper() in str(r['team']).upper()
                     or str(r['team']).upper() in ours_name.upper()), None)
        if mine:
            pos = int(mine.get('pos', 0) or rows.index(mine)+1)
            f.update(pos=pos, pos_ord=f'{pos}°', points=str(int(mine.get('pt', 0))), played=str(int(mine.get('g', 0))))
            leader = rows[0]
            if pos > 1:
                f['leader'] = title(leader['team'])
                f['gap'] = str(int(leader.get('pt', 0))-int(mine.get('pt', 0)))
            elif len(rows) > 1:
                f['lead'] = str(int(mine.get('pt', 0))-int(rows[1].get('pt', 0)))
            promo, playoff = int(config.get('promo_count', 3)), int(config.get('playoff_count', 2))
            f['zone'] = 'promozione' if pos <= promo else 'spareggio' if pos <= promo+playoff else ''
            prev = int(config.get('prev_pos', 0) or 0)
            if prev and prev != pos:
                if prev > pos:
                    f['up'] = str(prev-pos)
                else:
                    f['down'] = str(pos-prev)
            f['teams'] = str(len(rows))

    if template == 'Calendario':
        fixtures = [x for x in config.get('fixtures', [])[:config.get('fixture_count', 0)] if _clean(x.get('opponent'))]
        if fixtures:
            f['month'] = (_clean(config.get('month_label')) or 'questo mese').lower()
            f['n'] = str(len(fixtures))
            f['list'] = ' / '.join(f"{x.get('date', '')} {title(x['opponent'])}".strip() for x in fixtures)
            nxt = next((x for x in fixtures if not str(x.get('score', '')).strip()), None)
            if nxt:
                f['next_opp'] = title(nxt['opponent'])
                f['next_date'] = str(nxt.get('date', ''))
            done = [x for x in fixtures if str(x.get('score', '')).strip()]
            if done:
                f['played_n'] = str(len(done))
    return f


# --- Sentence pools ------------------------------------------------------
# (tone or '*', text). '{x}' needs fact x. Lines starting with 'type|' get
# that detail emoji when emoji are on.

HOOKS = {
    'Matchday Screen': [
        ('epico', 'È il giorno. È il nostro giorno.'), ('epico', 'Settimana lunga, ma ci siamo: si va in battaglia.'),
        ('epico', 'Luci accese, scarpini allacciati, cuore rosa.'), ('epico', 'Ci sono partite che si giocano. E partite che si vincono prima di entrare.'),
        ('ironico', 'Annullate gli impegni, inventate scuse, chiamate in ufficio: c\'è la partita.'),
        ('ironico', 'Il mister dice che è una partita come le altre. Il mister mente.'),
        ('ironico', 'Stretching fatto (quasi). Panino digerito (forse). Si gioca.'),
        ('ironico', 'Previsioni meteo: 100% di possibilità di Flamingos.'),
        ('retro', '▶ PRESS START'), ('retro', '👾 NEW CHALLENGER APPROACHING'), ('retro', '💾 LOADING MATCHDAY... ▓▓▓▓▓▓▓░░░'),
        ('retro', '📺 CH.07 / MATCHDAY / IN ONDA'), ('retro', 'INSERT COIN. PLAYER 1 READY.'),
        ('telecronaca', 'Buonasera e benvenuti, amici sportivi, collegati da casa e da bordo campo!'),
        ('telecronaca', 'Linea allo stadio: qui tutto è pronto per il fischio d\'inizio.'),
        ('telecronaca', 'Signore e signori, pronti per un altro capitolo di calcio a 7!'),
        ('sobrio', 'Matchday.'), ('sobrio', 'Prossima partita.'), ('sobrio', 'Si torna in campo.'),
        ('spogliatoio', 'Ragazzi, borsa pronta e niente ritardi stavolta 👀'),
        ('spogliatoio', 'Chi porta i palloni? Chi porta le casacche? Intanto: si gioca.'),
        ('spogliatoio', 'Gruppo WhatsApp in fiamme: è matchday.'),
        ('*', 'MATCHDAY 🦩'),
    ],
    'Convocati': [
        ('epico', 'La chiamata è arrivata. Questi i guerrieri.'), ('epico', 'Scelti, pronti, affamati.'),
        ('epico', 'Una maglia, un obiettivo, una squadra.'),
        ('ironico', 'Lista ufficiale. Reclami solo in forma scritta al mister (che non li leggerà).'),
        ('ironico', 'Se il tuo nome è qui sotto: niente aperitivo lungo la sera prima.'),
        ('ironico', 'Convocati veri, non quelli del fantacalcio.'),
        ('retro', '🎮 SELECT YOUR PLAYERS'), ('retro', '📋 PARTY COMPLETO'), ('retro', '💾 SAVE FILE: CONVOCATI'),
        ('retro', 'CHOOSE YOUR FIGHTERS ▮'),
        ('telecronaca', 'Ed ecco le scelte dell\'allenatore, appena giunte in redazione!'),
        ('telecronaca', 'Le formazioni sono ufficiali, amici: vediamo chi scende in campo.'),
        ('sobrio', 'I convocati.'), ('sobrio', 'Lista dei convocati.'),
        ('spogliatoio', 'Ecco chi si becca il turno lavatrice delle maglie 😂'),
        ('spogliatoio', 'Squadra fatta. Ora tocca solo non dimenticare i parastinchi.'),
        ('*', 'CONVOCATI 🦩'),
    ],
    'Reparti': [
        ('epico', 'Ogni reparto, una missione. Ogni volto, una storia.'), ('epico', 'Dietro ogni pixel, un guerriero.'),
        ('ironico', 'Li abbiamo fatti in pixel perché in HD non rendevano 😏'),
        ('ironico', 'Abbiamo ritoccato i giocatori. Pochi pixel, zero difetti.'),
        ('retro', '🕹️ CHARACTER SELECT'), ('retro', '👾 MEET THE SQUAD / 8-BIT EDITION'), ('retro', 'PLAYER SELECT ▶ ▶ ▶'),
        ('telecronaca', 'Conosciamo da vicino i protagonisti, reparto per reparto!'),
        ('sobrio', 'Reparto per reparto.'), ('sobrio', 'La squadra, reparto per reparto.'),
        ('spogliatoio', 'Sì, le facce sono quelle. No, non le abbiamo migliorate.'),
        ('*', 'MEET THE FLAMINGOS 🦩'),
    ],
    'Full Time': {
        'win': [
            ('epico', 'VITTORIA. Sudata, cercata, meritata.'), ('epico', 'Tre punti che pesano come oro.'),
            ('epico', 'Abbiamo lottato su ogni pallone. E abbiamo vinto.'),
            ('ironico', 'Tre punti e nessun infortunio grave. Il fisioterapista ringrazia.'),
            ('ironico', 'Vinto. Ora qualcuno spieghi al mister che non serve urlare così tanto 😂'),
            ('retro', '🏆 STAGE CLEAR!'), ('retro', '⭐ LEVEL UP'), ('retro', '🎮 YOU WIN / PERFECT? QUASI.'),
            ('retro', '+3 PUNTI. SALVATAGGIO IN CORSO... 💾'),
            ('telecronaca', 'Finisce qui! Triplice fischio e i Flamingos possono esultare!'),
            ('telecronaca', 'Che partita, amici! Vittoria rosa, roba da far tremare il televisore!'),
            ('sobrio', 'Vittoria.'), ('sobrio', 'Tre punti.'),
            ('spogliatoio', 'Stasera birra offerta da chi ha segnato. Le regole sono regole 🍻'),
            ('spogliatoio', 'Docce calde e sorrisi larghi: si vince!'),
        ],
        'draw': [
            ('epico', 'Un punto che costruisce. Non si molla mai.'), ('epico', 'Pari, ma a testa alta.'),
            ('ironico', 'Pareggio: nessuno felice, nessuno arrabbiato. Tutti affamati.'),
            ('ironico', 'Ci siamo divisi la torta. Ma volevamo tutta la torta.'),
            ('retro', '🤝 DRAW GAME'), ('retro', 'CONTINUE? ▮ SÌ, SEMPRE.'), ('retro', '1 PUNTO SALVATO IN MEMORIA 💾'),
            ('telecronaca', 'Finisce in parità, amici, al termine di una gara combattuta!'),
            ('sobrio', 'Pareggio.'), ('sobrio', 'Un punto.'),
            ('spogliatoio', 'Un punto e qualche rimpianto. Ne riparliamo al terzo tempo.'),
        ],
        'loss': [
            ('epico', 'Oggi è andata male. Domani si riparte più forti.'), ('epico', 'Si cade, ci si rialza. Sempre insieme.'),
            ('ironico', 'Non è andata. Diamo la colpa al campo, come da tradizione.'),
            ('ironico', 'Sconfitta. Il mister ha già prenotato l\'allenamento extra 😅'),
            ('retro', '💀 GAME OVER'), ('retro', 'CONTINUE? 9... 8... SÌ, CONTINUE.'), ('retro', 'LIFE -1. MA ABBIAMO ANCORA VITE.'),
            ('telecronaca', 'Non sorride oggi la dea bendata ai colori rosa, amici.'),
            ('sobrio', 'Sconfitta.'), ('sobrio', 'Non è la giornata giusta.'),
            ('spogliatoio', 'Si perde insieme, si riparte insieme. Allenamento, ragazzi.'),
        ],
    },
    'Classifica': [
        ('epico', 'La classifica parla. E noi vogliamo farla urlare.'), ('epico', 'Ogni punto è una conquista.'),
        ('ironico', 'Classifica aggiornata. Screenshot fatto, lo mandiamo alla nonna.'),
        ('ironico', 'Matematica applicata al calcio a 7: guardate dove siamo.'),
        ('retro', '📊 HIGH SCORE TABLE'), ('retro', '🕹️ RANKING / PLAYER 1'), ('retro', '💾 TABELLA SALVATA'),
        ('telecronaca', 'Ed ora, amici, uno sguardo alla classifica!'),
        ('sobrio', 'La classifica.'), ('sobrio', 'Classifica aggiornata.'),
        ('spogliatoio', 'Classifica alla mano, discussione aperta al terzo tempo.'),
        ('*', 'CLASSIFICA 🦩'),
    ],
    'Calendario': [
        ('epico', 'Un mese, tante battaglie.'), ('epico', 'Segnatevi le date: ci sarà da lottare.'),
        ('ironico', 'Fidanzate, mogli, capi: vi lasciamo il calendario così vi organizzate.'),
        ('ironico', 'Ecco perché quei giorni siamo "impegnati".'),
        ('retro', '🗓️ LEVEL SELECT'), ('retro', '📼 PROGRAMMAZIONE DEL MESE'), ('retro', '🕹️ STAGE MAP'),
        ('telecronaca', 'Il palinsesto del mese, amici telespettatori!'),
        ('sobrio', 'Il calendario del mese.'), ('sobrio', 'Le prossime partite.'),
        ('spogliatoio', 'Calendario in frigo, sul telefono e tatuato sul braccio.'),
        ('*', 'CALENDARIO 🦩'),
    ],
}

# 'main' states the fact (one per caption); 'flavor' adds colour when the data allows it.
CORES = {
    'Matchday Screen': {
        'main': [('*', '{ours} contro {opp}, {where}.'), ('*', 'Di fronte {opp}: si gioca {where}.'),
                 ('epico', 'Contro {opp} vogliamo una cosa sola.'), ('ironico', '{opp} è avvisato: abbiamo pure fatto stretching.'),
                 ('retro', '{opp.upper} entra nel livello. I Flamingos accettano la sfida.'),
                 ('telecronaca', 'Di fronte {ours} e {opp}: le squadre sono pronte!'),
                 ('sobrio', '{ours} - {opp}.'), ('spogliatoio', '{opp}? Rispetto massimo, paura zero.'),
                 ('*', 'Si gioca contro {opp}.')],
        'flavor': [('*', 'È il {event}: questa conta doppio.'), ('*', 'Arriviamo da {streak}: guai a fermarsi ora.'),
                   ('*', 'Giornata {round}: tocca a noi.'), ('retro', 'Livello {round}. Difficoltà: alta.'),
                   ('ironico', 'Giornata {round}, e le gambe dicono già "basta".'),
                   ('epico', 'Edizione {season}: niente paura, solo voglia.')],
    },
    'Convocati': {
        'main': [('*', 'Ecco i {count} convocati per {opp}.'), ('*', 'In {count} per la sfida contro {opp}.'),
                 ('*', 'Questi i {count} per la partita di {date}.'),
                 ('retro', '{count} giocatori selezionati. Avversario: {opp}.'),
                 ('telecronaca', 'Sono {count} gli uomini a disposizione per la sfida a {opp}!'),
                 ('ironico', '{count} nomi, zero scuse.'), ('sobrio', 'Convocati per {opp}.')],
        'flavor': [('*', 'Fascia al braccio per {captain}.'), ('epico', 'Guida il gruppo il capitano {captain}.'),
                   ('retro', 'Player leader: {captain} ⭐'), ('ironico', '{captain} capitano: e chi glielo dice che deve pure parlare all\'arbitro?'),
                   ('*', 'È il {event}: testa e cuore.')],
    },
    'Reparti': {
        'main': [('*', 'Questi i convocati per {opp}, reparto per reparto.'), ('*', 'Scorri per conoscerli tutti 👉'),
                 ('retro', 'Portieri, difensori, centrocampisti, attaccanti: ognuno con il suo sprite.'),
                 ('ironico', 'Scorrete: ogni slide un reparto, ogni reparto un mistero.'), ('sobrio', 'La rosa per {opp}.')],
        'flavor': [('*', 'Tra i pali: {keepers}.'), ('*', 'In panchina a guidarci: mister {coach}.'),
                   ('retro', 'Coach: {coach}. Difficoltà allenamenti: estrema.'), ('*', 'Capitano: {captain}.')],
    },
    'Full Time': {
        'main': [('*', '{ours} {score} {opp}.'), ('*', 'Finisce {score} contro {opp}.'), ('*', '{score} {where} contro {opp}.'),
                 ('telecronaca', 'Il tabellino recita {score}, amici!'), ('sobrio', 'Risultato finale: {score}.'),
                 ('retro', 'SCORE: {score}. Avversario: {opp}.')],
        'flavor': [('*', 'Decidono i rigori: {pens} per noi.'), ('epico', '{top_goals} di {top}: serata da ricordare.'),
                   ('retro', 'Combo di {top}: {top_goals}!'), ('ironico', '{top_goals} per {top}: stasera paga lui.'),
                   ('*', '{clean_sheet}: zero gol subiti. 🧤'), ('*', 'Sono {streak}: avanti così.'),
                   ('*', 'Era il {event}: missione compiuta.')],
    },
    'Classifica': {
        'main': [('*', 'Siamo {pos_ord} con {points} punti dopo {played} partite.'), ('*', '{pos_ord} posto, {points} punti.'),
                 ('retro', 'Posizione {pos_ord} su {teams}. Next level in arrivo.'),
                 ('telecronaca', 'I rosa occupano la {pos_ord} posizione con {points} punti!'),
                 ('ironico', '{pos_ord} posto: lo diciamo piano per non spaventarci.'), ('sobrio', '{pos_ord} posto.')],
        'flavor': [('*', 'In zona {zone}.'), ('*', 'A {gap} punti dalla vetta ({leader}).'), ('*', 'Primi, con {lead} punti di vantaggio.'),
                   ('*', 'Saliamo di {up} posizioni.'), ('*', 'Scendiamo di {down}, ma il campionato è lungo.'),
                   ('epico', 'Una scalata di {up} posizioni: e non è finita.'), ('retro', 'RANK UP +{up} ⬆️'),
                   ('*', 'Serie aperta: {streak}.')],
    },
    'Calendario': {
        'main': [('*', '{n} partite a {month}.'), ('retro', '{n} stage da superare a {month}.'),
                 ('telecronaca', 'Ben {n} appuntamenti a {month}, amici!'), ('sobrio', 'Calendario di {month}.')],
        'flavor': [('*', 'Prossima: {next_opp}, il {next_date}.'), ('ironico', 'Si comincia con {next_opp}: preparate i polpacci.'),
                   ('*', 'Già giocate: {played_n}.')],
    },
}

DETAILS = {
    'Matchday Screen': ['date|{date}', 'time|Calcio d\'inizio {time}', 'venue|{venue}', 'event|È {event}!',
                        'theme|Edizione speciale {season}', 'streak|Veniamo da {streak}'],
    'Convocati': ['date|{date}', 'meeting|Ritrovo {meeting}', 'time|Kick off {time}', 'venue|{venue}',
                  'captain|Capitano: {captain}', 'list|{names}'],
    'Reparti': ['date|{date}', 'time|Kick off {time}', 'venue|{venue}', 'captain|Capitano: {captain}', 'list|{names}'],
    'Full Time': ['scorers|Marcatori: {scorers}', 'streak|{streak}', 'event|Era {event}: missione compiuta.',
                  'table|Prossima tappa: aggiornare la classifica.'],
    'Classifica': ['table|{points} punti in {played} partite', 'streak|Serie aperta: {streak}', 'table|Davanti a tutti: {leader}'],
    'Calendario': ['month|{list}', 'next|Prossima: {next_opp} ({next_date})'],
}

CLOSERS = {
    'epico': ['Forza Flamingos. Sempre.', 'Uniti si vince. 💗', 'Tutti per uno, rosa per tutti.', 'Insieme. Fino all\'ultimo minuto.',
              'Il rosa non si arrende mai.', 'Cuore, gambe e testa: tutto rosa.', 'Nessun passo indietro.', 'Per la maglia, per il gruppo.'],
    'ironico': ['Portate i pop-corn. E magari un defibrillatore.', 'Venite a vederci: almeno ridete.',
                'Seguiteci, che tanto a casa non avete niente di meglio.', 'Like se anche tu hai mal di gambe solo a leggerlo.', 'Lo sappiamo: siamo più forti su Instagram che in campo. Per ora.', 'Commentate con un 🦩 se siete dei nostri.', 'Il fisioterapista è già in allerta.'],
    'retro': ['INSERT COIN TO CONTINUE ▮', 'GAME SAVED 💾', 'PRESS START TO PLAY TOGETHER', 'SEE YOU NEXT LEVEL 👾',
              'HIGH SCORE IN ARRIVO...', 'PLAYER 2 HAS JOINED THE GAME', 'NEXT STAGE ▶▶', 'CHEAT CODE: ALLENARSI.'],
    'telecronaca': ['A voi la linea, amici sportivi!', 'Restate sintonizzati!', 'Non cambiate canale!',
                    'Dal campo è tutto, a voi studio!', 'Per oggi è tutto, buona serata dal campo!', 'La linea passa a voi, amici del calcio a 7!'],
    'sobrio': ['Forza Flamingos.', 'Avanti così.', 'Ci vediamo in campo.', '🦩', 'Testa alla prossima.', 'Grazie a tutti.'],
    'spogliatoio': ['Ci vediamo al terzo tempo 🍻', 'Chi arriva tardi paga da bere.', 'Muoversi, ragazzi!',
                    'E ora tutti a casa a mettere il ghiaccio.', 'Il gruppo WhatsApp non dormirà stanotte.', 'Pizza dopo? Pizza dopo.', 'Qualcuno porti le arance a metà tempo 🍊'],
}
CTA = {
    'Matchday Screen': ['Venite a tifare! 📣', 'Passate parola e portate gli amici!', 'Diretta? No: venite dal vivo.'],
    'Convocati': ['Pronti? Noi sì.', 'Il resto lo diciamo in campo.'],
    'Reparti': ['Scorri e scegli il tuo preferito 👉', 'Chi è il vostro MVP? Ditelo nei commenti 👇'],
    'Full Time': ['Grazie a chi è venuto a tifare! 💗', 'Chi è il vostro migliore in campo? Ditelo nei commenti 👇'],
    'Classifica': ['Il campionato è lungo: testa alla prossima.', 'Ogni punto conta, continuiamo così.'],
    'Calendario': ['Salvate il post per non perdervi niente 📌', 'Ci vediamo a bordo campo!'],
}
HASHTAGS = {
    'base': ['#Flamingos', '#CalcioA7', '#CSIBrescia'],
    'extra': ['#SerieC', '#GironeD', '#Amatori', '#CalcioAmatoriale', '#Brescia', '#Football', '#7aside', '#TeamSpirit'],
    'retro': ['#RetroGaming', '#PixelArt', '#8bit', '#CRT', '#Arcade'],
    'Matchday Screen': ['#Matchday', '#GameDay'], 'Convocati': ['#Convocati', '#Squad'], 'Reparti': ['#MeetTheTeam', '#Squad'],
    'Full Time': ['#FullTime', '#Risultato'], 'Classifica': ['#Classifica'], 'Calendario': ['#Calendario', '#Fixtures'],
    'derby': ['#Derby'], 'big match': ['#BigMatch'], 'ultima giornata': ['#UltimaGiornata'],
    'Halloween': ['#Halloween'], 'Natale': ['#Natale'], 'Capodanno': ['#Capodanno'],
}


class _Missing(KeyError):
    pass


def fill(text, facts):
    """Fill {field} and {field.upper}; raise _Missing when a fact is absent."""
    def repl(m):
        key, _, mod = m.group(1).partition('.')
        value = facts.get(key)
        if value in (None, '', False):
            raise _Missing(key)
        value = str(value)
        return value.upper() if mod == 'upper' else value
    return re.sub(r'\{([a-z_]+(?:\.upper)?)\}', repl, text)


def _cap(text):
    """Capital letter at the start of a sentence."""
    return text[:1].upper()+text[1:] if text and text[0].islower() else text


def _pick(rng, pool, tone, facts):
    options = [text for t, text in pool if t in (tone, '*')]
    rng.shuffle(options)
    for text in options:
        try:
            return fill(text, facts)
        except _Missing:
            continue
    return None


def _hooks(context, facts):
    pool = HOOKS[context]
    if isinstance(pool, dict):
        pool = pool.get(facts.get('outcome', 'win'), [])
    return pool


def _hashtags(rng, context, facts, tone, level):
    if level == 'nessuno':
        return ''
    tags = list(HASHTAGS['base'])+HASHTAGS.get(context, [])[:1]
    for key in (facts.get('event'), facts.get('season') if level == 'tanti' else None):
        if key and key in HASHTAGS:
            tags += HASHTAGS[key]
    if level == 'tanti':
        tags += HASHTAGS.get(context, [])[1:]
        extra = list(HASHTAGS['extra'])
        rng.shuffle(extra)
        tags += extra[:5]
        if tone == 'retro':
            tags += HASHTAGS['retro']
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return ' '.join(out[:30])


def compose_caption(rng, context, facts, tone, length='media', emoji=True, hashtags='pochi'):
    hook = _pick(rng, _hooks(context, facts), tone, facts)
    pools = CORES.get(context, {})
    main = _pick(rng, pools.get('main', []), tone, facts)
    flavor = _pick(rng, pools.get('flavor', []), tone, facts) if length != 'corta' or rng.random() < .4 else None
    cores = [_cap(x) for x in (main, flavor) if x]
    if not hook or not main:
        return None
    details = []
    if length != 'corta':
        pool = list(DETAILS.get(context, []))
        if length == 'media':
            rng.shuffle(pool)
        body = ' '.join(cores)
        for item in pool:
            kind, _, text = item.partition('|')
            try:
                line = fill(text, facts)
            except _Missing:
                continue
            used = [str(facts[k.split('.')[0]]) for k in re.findall(r'\{([a-z_.]+)\}', text)]
            if used and all(u in body for u in used):
                continue  # already said in the sentence above
            details.append((DETAIL_EMOJI.get(kind, '•')+' ' if emoji else '')+line)
            if length == 'media' and len(details) >= 3:
                break
    closer = rng.choice(CLOSERS[tone]) if length != 'corta' or rng.random() < .5 else None
    cta = rng.choice(CTA.get(context, [''])) if length == 'lunga' else None
    head = (TONE_EMOJI[tone]+' ' if emoji and not re.match(r'^\W', hook) else '')+hook
    blocks = [head, ' '.join(cores)]
    if details:
        blocks.append('\n'.join(details))
    tail = '\n'.join(x for x in (closer, cta) if x)
    if tail:
        blocks.append(tail)
    text = '\n\n'.join(blocks)
    if not emoji:
        text = re.sub(r'[\U0001F300-\U0001FAFF☀-➿⭐⬆↔-⇿▶▮▓░]️?\s?', '', text)
        text = re.sub(r'[ \t]+\n', '\n', text).strip()
    tags = _hashtags(rng, context, facts, tone, hashtags)
    if tags:
        text += '\n\n'+tags
    return text[:MAX_CHARS]


def generate(context, facts, tones=TONE_IDS, count=30, seed=0, length='media', emoji=True, hashtags='pochi'):
    """Up to `count` different captions: [{'tone', 'text'}]."""
    tones = [t for t in tones if t in TONES] or list(TONE_IDS)
    rng = random.Random(f'{context}|{seed}')
    out, seen = [], set()
    attempts = 0
    while len(out) < count and attempts < count*25:
        attempts += 1
        tone = tones[attempts % len(tones)]
        text = compose_caption(rng, context, facts, tone, length, emoji, hashtags)
        if not text:
            continue
        key = re.sub(r'\W+', '', text.lower())[:160]
        if key in seen:
            continue
        seen.add(key)
        out.append({'tone': tone, 'text': text})
    return out


def variety(context, facts, tone):
    """A rough count of distinct captions available for a tone (for the page header)."""
    hooks = len([1 for t, _ in _hooks(context, facts) if t in (tone, '*')])
    pools = CORES.get(context, {})
    mains = len([1 for t, _ in pools.get('main', []) if t in (tone, '*')])
    flavors = len([1 for t, _ in pools.get('flavor', []) if t in (tone, '*')])+1
    return hooks*max(1, mains)*flavors*len(CLOSERS[tone])*len(CTA.get(context, [1]))
