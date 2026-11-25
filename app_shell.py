"""3.23: the app as an app on the phone (style "sportiva + neon" from the mockup).

- style():       fonts, cards, big buttons; on a phone the bottom bar and room for it.
- bottom_nav():  Home, Matchday, Full Time, Classifica, Altro, always at the bottom of a phone screen.
- show_more():   the "Altro" screen: every other section as a tile.
- home_hero():   on top of "La tua settimana": the next match card, this week's four graphics, our place.

The pure pieces (match card, countdown, sparkline) are plain functions on dicts, tested without Streamlit.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import io

ACCENT = '#F268A8'
CYAN, YELLOW, GREEN, RED = '#79DCF7', '#FFC963', '#5BE6A4', '#FF6B78'
NAV = (('Settimana', 'Home', ':material/home:'), ('Matchday Screen', 'Matchday', ':material/campaign:'),
       ('Full Time', 'Full Time', ':material/timer:'), ('Classifica', 'Classifica', ':material/trophy:'))
TILES = (('Matchday Screen', 'Matchday', ':material/campaign:'), ('Convocati', 'Convocati', ':material/groups:'),
         ('Full Time', 'Full Time', ':material/timer:'), ('Classifica', 'Classifica', ':material/trophy:'))
MORE = (('Convocati', 'Convocati', ':material/groups:'), ('Calendario', 'Calendario', ':material/calendar_month:'),
        ('Figurine', 'Figurine', ':material/style:'), ('Risultati', 'Risultati', ':material/scoreboard:'),
        ('Sequenza video', 'Video', ':material/movie:'), ('Didascalie', 'Didascalie', ':material/edit_note:'),
        ('Wrapped', 'Wrapped', ':material/redeem:'), ('Instagram', 'Squadra', ':material/photo_camera:'),
        ('Settimana', 'Settimana', ':material/home:'))
WEEKDAYS = ('Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom')
MONTHS = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre',
          'ottobre', 'novembre', 'dicembre')


# --- Pure pieces ---------------------------------------------------------------------------------------

def parse_date(text):
    try:
        return dt.datetime.strptime(str(text or '').strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def when_label(match, today):
    """'Ven 4 dicembre · 20:30' and 'tra 10 giorni' / 'domani' / 'oggi' / 'giocata 2 giorni fa'."""
    date = parse_date(match.get('date'))
    if not date:
        return 'Data da decidere', ''
    clock = match.get('kickoff') if ':' in str(match.get('kickoff', '')) and match.get('kickoff') != 'HH:MM' else ''
    day = f'{WEEKDAYS[date.weekday()]} {date.day} {MONTHS[date.month-1]}' + (f' · {clock}' if clock else '')
    days = (date-today).days
    if days > 1:
        left = f'tra {days} giorni'
    elif days == 1:
        left = 'domani'
    elif days == 0:
        left = 'oggi'
    elif days == -1:
        left = 'giocata ieri'
    else:
        left = f'giocata {-days} giorni fa'
    return day, left


def initials(name):
    words = [w for w in str(name or '').upper().replace('.', ' ').split() if w not in ('AS', 'FC', 'GSO', 'ASD', 'US')]
    word = (words or [str(name or '?').upper()])[0]
    return word[:3]


def sparkline(history, width=150, height=44, accent=ACCENT):
    """Inline SVG of our place round by round (1st at the top), '' with fewer than two rounds."""
    if not history or len(history) < 2:
        return ''
    teams = max(13, max(int(h['pos']) for h in history))
    n = len(history)
    xs = [6+(width-12)*i/(n-1) for i in range(n)]
    ys = [6+(height-12)*(int(h['pos'])-1)/(teams-1) for h in history]
    points = ' '.join(f'{x:.0f},{y:.0f}' for x, y in zip(xs, ys))
    best = min(range(n), key=lambda i: history[i]['pos'])
    places = ', '.join(str(h['pos']) for h in history)
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="Andamento in classifica: {places}"><polyline points="{points}" fill="none" stroke="{accent}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{xs[best]:.0f}" cy="{ys[best]:.0f}" r="3" fill="{CYAN}"/>'
            f'<circle cx="{xs[-1]:.0f}" cy="{ys[-1]:.0f}" r="4" fill="{YELLOW}"/></svg>')


def _badge(name, logo, ours):
    if logo:
        src = 'data:image/png;base64,'+base64.b64encode(logo).decode()
        inner = f'<img src="{src}" alt="" style="width:46px;height:46px;object-fit:contain">'
    else:
        inner = html.escape(initials(name))
    border = ACCENT if ours else '#6b3a5c'
    glow = 'box-shadow:0 0 16px rgba(242,104,168,.35);' if ours else ''
    return (f'<div class="fs-badge" style="border-color:{border};{glow}">{inner}</div>'
            f'<span class="fs-team">{html.escape(str(name).title())}</span>')


def form_html(form, opponent):
    if not form:
        return ''
    colors = {'V': (GREEN, '#10261b'), 'N': (YELLOW, '#2a1d05'), 'P': (RED, '#2a0c10')}
    squares = ''.join(f'<span class="fs-sq" style="background:{colors[r][0]};color:{colors[r][1]}">{r}</span>'
                      for r in form.get('last') or [])
    place = f'<span class="fs-pos">{form["pos"]}° posto</span>' if form.get('pos') else ''
    first = f'<span class="fs-muted">andata {html.escape(form["first_leg"])}</span>' if form.get('first_leg') else ''
    return (f'<div class="fs-form"><span class="fs-muted">{html.escape(str(opponent).title())}</span>{squares}'
            f'{first}{place}</div>')


def match_card(match, today, home_logo=None, away_logo=None, form=None, sky=''):
    """The 'prossima partita' card as HTML (names escaped). home/away follow our side."""
    ours, theirs = match.get('our_name', 'FLAMINGOS'), match.get('opponent', 'AVVERSARI')
    home_side = match.get('our_side', 'Casa') == 'Casa'
    left = _badge(ours if home_side else theirs, home_logo, home_side)
    right = _badge(theirs if home_side else ours, away_logo, not home_side)
    day, left_days = when_label(match, today)
    meeting = match.get('meeting_time')
    meeting = f' <span class="fs-muted">(ritrovo {html.escape(meeting)})</span>' if meeting and meeting != 'HH:MM' else ''
    played = left_days.startswith('giocata')
    title = 'ULTIMA PARTITA' if played else 'PROSSIMA PARTITA'
    venue = html.escape(str(match.get('venue') or '').title())
    return f'''<section class="fs-card">
<div class="fs-row"><span class="fs-kicker">{title}</span><span class="fs-chip">GIORNATA {int(match.get('round') or 0)}</span></div>
<div class="fs-teams"><div class="fs-side">{left}</div>
<div class="fs-vs"><span>VS</span><small>{'In casa' if home_side else 'Fuori casa'}</small></div>
<div class="fs-side">{right}</div></div>
<div class="fs-info"><div>📅 {html.escape(day)}{meeting}</div><div class="fs-muted">📍 {venue}</div>{f'<div class="fs-muted">{html.escape(sky)}</div>' if sky and not played else ''}
{f'<div class="fs-left">⏳ {html.escape(left_days)}</div>' if left_days else ''}</div>
{form_html(form, theirs)}
</section>'''


def tile_status(template, todo, match, today):
    """('PRONTA' | 'DA FARE' | 'DOPO LA PARTITA', color) for a tile of this week's graphics."""
    date = parse_date(match.get('date'))
    if template == 'Full Time' and (not date or date > today):
        return 'DOPO LA PARTITA', '#9c8aa6'
    return ('DA FARE', YELLOW) if todo else ('PRONTA', GREEN)


CSS = '''<style class="fs-css">
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Silkscreen:wght@400;700&display=swap");
.stApp,.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,.stApp button{font-family:Inter,system-ui,sans-serif}
.stApp h1,.stApp h2,.stApp h3{font-family:Silkscreen,monospace!important;letter-spacing:.03em;font-weight:700!important}
.stButton button,.stDownloadButton button,.stLinkButton a{border-radius:14px!important;min-height:44px;font-weight:650}
[data-testid="stVerticalBlockBorderWrapper"]{background:#19131f}
.fs-card{border-radius:22px;padding:18px;background:#1a1220;border:1px solid #4a2c46;box-shadow:0 0 0 1px rgba(242,104,168,.12),0 12px 32px rgba(0,0,0,.35);display:flex;flex-direction:column;gap:14px;margin-bottom:6px}
.fs-row{display:flex;justify-content:space-between;align-items:center}
.fs-kicker{font:700 11px Inter,sans-serif;letter-spacing:.12em;color:#79DCF7}
.fs-chip{font:700 11px Inter,sans-serif;color:#bca9c5;padding:4px 8px;border-radius:8px;background:#241a2c}
.fs-teams{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:center;gap:6px}
.fs-side{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:0}
.fs-badge{width:60px;height:60px;border-radius:18px;background:#241a2c;border:1.5px solid;display:flex;align-items:center;justify-content:center;font:800 15px Inter,sans-serif;color:#F268A8}
.fs-team{font:700 13px Inter,sans-serif;text-align:center;line-height:1.2}
.fs-vs{display:flex;flex-direction:column;align-items:center;gap:2px}
.fs-vs span{font-family:Silkscreen,monospace;font-size:22px;color:#FFC963}
.fs-vs small{font:600 12px Inter,sans-serif;color:#bca9c5}
.fs-info{display:flex;flex-direction:column;gap:6px;padding-top:12px;border-top:1px solid #33243a;font:600 14px Inter,sans-serif}
.fs-muted{color:#bca9c5;font-weight:500;font-size:13px}
.fs-left{color:#FFC963;font-size:13px}
.fs-form{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.fs-sq{width:20px;height:20px;border-radius:5px;font:800 11px Inter,sans-serif;display:inline-flex;align-items:center;justify-content:center}
.fs-pos{margin-left:auto;font:700 12px Inter,sans-serif;color:#FFC963}
.fs-place{border-radius:18px;padding:14px 16px;background:#19131f;border:1px solid #3c2d44;display:flex;align-items:center;gap:14px;margin:4px 0}
.fs-place b{font-family:Silkscreen,monospace;font-size:26px;color:#FFC963;font-weight:400}
.fs-place svg{margin-left:auto}
.fs-dot{display:inline-block;width:8px;height:8px;border-radius:4px;margin-right:8px}
.st-key-home_tiles .stButton button{min-height:78px;justify-content:flex-start;text-align:left;background:#19131f;border:1px solid #3c2d44}
.st-key-home_tiles .stButton button p{font-size:14px}
.st-key-more_tiles .stButton button{min-height:88px;background:#19131f;border:1px solid #3c2d44}
.st-key-bottom_nav{display:none}
[data-testid="stElementContainer"]:has(style.fs-css){display:none}
@media (max-width:640px){
 .st-key-mobile_nav{display:none!important}
 .block-container{padding-bottom:110px!important}
 .st-key-bottom_nav{display:block;position:fixed;left:0;right:0;bottom:0;z-index:1000;background:#160f1c;border-top:1px solid #2e2236;padding:6px 6px calc(10px + env(safe-area-inset-bottom))}
 .st-key-bottom_nav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:2px!important}
 .st-key-bottom_nav [data-testid="stColumn"]{min-width:0!important;width:20%!important;flex:1 1 0!important}
 .st-key-bottom_nav .stButton button{min-height:56px!important;width:100%;padding:4px 0!important;border:0!important;background:transparent!important;color:#9c8aa6!important;box-shadow:none!important}
 .st-key-bottom_nav .stButton button,.st-key-bottom_nav .stButton button *:has(> [data-testid="stIconMaterial"]),
 .st-key-more_tiles .stButton button,.st-key-more_tiles .stButton button *:has(> [data-testid="stIconMaterial"]){display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:3px!important}
 .st-key-bottom_nav .stButton button p{font-size:11px!important;font-weight:650;white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;line-height:1.25!important;text-align:center;margin:0!important}
 .st-key-bottom_nav .stButton button p span,.st-key-more_tiles .stButton button p span{font-size:24px!important;line-height:1!important}
 .st-key-bottom_nav .stButton button [data-testid="stMarkdownContainer"],
 .st-key-more_tiles .stButton button [data-testid="stMarkdownContainer"]{overflow:visible!important;width:auto!important;max-width:none!important}
 .st-key-bottom_nav .stButton button span[data-testid="stIconMaterial"]{font-size:24px!important;margin:0!important}
 .st-key-more_tiles .stButton button p{font-size:12px!important;white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;text-align:center;line-height:1.4!important}
 .st-key-more_tiles .stButton button span[data-testid="stIconMaterial"]{font-size:26px!important;color:#F268A8;margin:0!important}
 .st-key-app_head{display:none!important}
 .stApp h3{font-size:1.15rem!important;line-height:1.6!important}
 .st-key-home_tiles [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important}
 .st-key-home_tiles [data-testid="stColumn"]{min-width:0!important;width:50%!important;flex:1 1 0!important}
 .st-key-more_tiles [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important}
 .st-key-more_tiles [data-testid="stColumn"]{min-width:0!important;width:33%!important;flex:1 1 0!important}
}
</style>'''


# --- Streamlit -----------------------------------------------------------------------------------------

def _jpeg_preview(data, width):
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        flat = Image.new('RGB', image.size, (16, 13, 22))
        flat.paste(image, mask=image.split()[-1])
        image = flat
    else:
        image = image.convert('RGB')
    if image.width > width:
        image = image.resize((width, round(image.height*width/image.width)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=84, optimize=True)
    return out.getvalue()


_PREVIEWS = {}


def preview(data, width=720):
    """3.24: what the page shows of a finished PNG: a light JPEG (the full file stays for download and share).
    The browser downloads shown images again at every run, so 1-2 MB PNGs made every tap slow."""
    if not data:
        return data
    import hashlib
    key = (hashlib.sha1(data).hexdigest(), width)
    if key not in _PREVIEWS:
        if len(_PREVIEWS) > 48:
            _PREVIEWS.clear()
        try:
            _PREVIEWS[key] = _jpeg_preview(data, width)
        except Exception:
            return data
    return _PREVIEWS[key]


def is_phone():
    """3.24: the browser says it is a phone (then the heavy drag editor is left out, the small preview stays)."""
    import streamlit as st
    try:
        agent = str(st.context.headers.get('User-Agent') or '')
    except Exception:
        return False
    return any(word in agent for word in ('iPhone', 'iPod', 'Android', 'Mobile'))


def style():
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def _goto(template):
    import streamlit as st
    st.session_state['studio_template'] = template
    st.session_state['phone_more'] = False


def _more():
    import streamlit as st
    st.session_state['phone_more'] = True


def bottom_nav(template):
    """The phone's bottom bar (hidden on a computer by the CSS)."""
    import streamlit as st
    current = 'Altro' if st.session_state.get('phone_more') else template
    with st.container(key='bottom_nav'):
        columns = st.columns(5, gap='small')
        for column, (target, label, icon) in zip(columns, NAV):
            column.button(f'{icon}  \n{label}', key=f'nav_{label}', on_click=_goto, args=(target,), width='stretch')
        columns[4].button(':material/more_horiz:  \nAltro', key='nav_Altro', on_click=_more, width='stretch')
    label = 'Altro' if current == 'Altro' else next((l for t, l, _ in NAV if t == current), '')
    if label:
        key = 'nav_'+label.replace(' ', '_')
        st.markdown(f'<style class="fs-css">@media (max-width:640px){{.st-key-bottom_nav .st-key-{key} .stButton button,'
                    f'.st-key-bottom_nav .st-key-{key} button{{color:{ACCENT}!important}}}}</style>',
                    unsafe_allow_html=True)


def show_more():
    """The 'Altro' screen of the phone: every other section, then the shared work box."""
    import streamlit as st
    st.subheader('ALTRO')
    st.caption('Tutto il resto dello studio.')
    with st.container(key='more_tiles'):
        for start in range(0, len(MORE), 3):
            columns = st.columns(3)
            for column, (target, label, icon) in zip(columns, MORE[start:start+3]):
                column.button(f'{icon}  \n{label}', key=f'more_{target}', on_click=_goto, args=(target,), width='stretch')
    import shared_ui                     # the full box (name, note, versions) stays in the side menu
    meta = shared_ui._meta()
    with st.container(border=True):
        st.markdown('**☁️ Lavoro condiviso**')
        if meta.get('status') == 'on':
            saved = meta.get('saved_at') or (meta.get('loaded') or {}).get('saved_at')
            st.caption((f'Salvato per tutti ({shared_ui.when(saved)}). ' if saved else '')
                       + 'Nome, nota per gli amici e versioni sono nel menu laterale (☰ in alto a sinistra).')
            st.button("↻ Prendi l'ultimo lavoro degli amici", key='more_reload', on_click=shared_ui.reload,
                      width='stretch')
        else:
            st.caption('Non attivo: si salva solo in questo browser.')


def _logos(root, library):
    """Small PNG logos for the match card: (home, away) as on the Matchday."""
    from PIL import Image
    from sequence_ui import current_config, resolve_assets
    try:
        _, home, away, _ = resolve_assets(root, 'Matchday Screen', current_config('Matchday Screen'), library['assets'])
    except Exception:
        return None, None
    out = []
    for data in (home, away):
        if not data:
            out.append(None)
            continue
        try:
            image = Image.open(io.BytesIO(data)).convert('RGBA')
            image.thumbnail((96, 96))
            if min(image.getpixel((0, 0))[:3]) > 235:        # a JPG crest on white: the white goes
                import numpy as np
                pixels = np.array(image)
                pixels[pixels[..., :3].min(axis=2) > 235, 3] = 0
                image = Image.fromarray(pixels, 'RGBA')
            buffer = io.BytesIO()
            image.save(buffer, 'PNG')
            out.append(buffer.getvalue())
        except Exception:
            out.append(None)
    return out[0], out[1]


def home_hero(root, library):
    """Top of 'La tua settimana': next match, this week's graphics, our place in the table."""
    import streamlit as st
    import opponent_form
    from sequence_ui import current_config
    from studio_state import sanitize_match
    from week_ui import _now, _when, data_status
    today = _now().date()
    match = sanitize_match(st.session_state.get('shared_match'))
    logos = st.session_state.get('_home_logos')
    sig = (match.get('our_logo_id'), match.get('opponent_logo_id'), match.get('our_side'))
    if not logos or logos[0] != sig:
        logos = (sig, *_logos(root, library))
        st.session_state['_home_logos'] = logos
    matchday = current_config('Matchday Screen')
    form = opponent_form.decode(matchday.get('opponent_form'))
    sky = matchday.get('weather_note', '') if matchday.get('weather') else ''      # 3.25: the forecast, when there is one
    st.markdown(match_card(match, today, logos[1], logos[2], form, sky), unsafe_allow_html=True)

    statuses = [(t, l, i, tile_status(t, data_status(t, current_config(t)), match, today)) for t, l, i in TILES]
    done = sum(1 for *_, (s, _) in statuses if s == 'PRONTA')
    st.markdown(f'**Da fare questa settimana** <span class="fs-muted" style="float:right">{done} di 4 pronte</span>',
                unsafe_allow_html=True)
    with st.container(key='home_tiles'):
        for start in (0, 2):
            columns = st.columns(2)
            for column, (target, label, icon, (status, color)) in zip(columns, statuses[start:start+2]):
                column.button(f'**{label}**  \n:{_tone(color)}[{status}]', icon=icon, key=f'tile_{target}',
                              on_click=_goto, args=(target,), width='stretch')

    history = st.session_state.get('season_positions') or []
    if history:
        last = history[-1]
        st.markdown(f'<div class="fs-place"><div><b>{int(last["pos"])}°</b><br><span class="fs-muted">'
                    f'{int(last.get("pt") or 0)} punti · giornata {int(last["round"])}</span></div>'
                    f'{sparkline(history)}</div>', unsafe_allow_html=True)
    sync = st.session_state.get('csi_sync') or {}
    if sync.get('ok_at'):
        dot, text = GREEN, f"Dati CSI aggiornati {_when(sync['ok_at'])}"
    elif sync.get('error'):
        dot, text = RED, 'Sito CSI non raggiunto: riprova da ① qui sotto'
    else:
        dot, text = '#9c8aa6', 'I dati del CSI arrivano da soli quando apri l\'app'
    st.markdown(f'<div class="fs-muted"><span class="fs-dot" style="background:{dot}"></span>{html.escape(text)}</div>',
                unsafe_allow_html=True)


def _tone(color):
    return {GREEN: 'green', YELLOW: 'orange'}.get(color, 'gray')
