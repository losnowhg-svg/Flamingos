"""3.25: the real match weather and time on Matchday and Convocati.

The forecast for the pitch's town at kick-off comes from Open-Meteo (free, no account,
up to 16 days ahead); evening and night come from the kick-off time against the sunset in
Brescia, so they need no internet at all. The graphic then changes by itself: night or
sunset light, rain streaks, snow, fog or a storm around the screen (never over the texts).
'Meteo e ora della partita' in the editor switches it off.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import re
import urllib.parse
import urllib.request

FORECAST = 'https://api.open-meteo.com/v1/forecast'
GEOCODE = 'https://geocoding-api.open-meteo.com/v1/search'
TIMEOUT = 6
BRESCIA = ('Brescia', 45.539, 10.220)
MAX_DAYS = 15
# Towns of our girone and around it (no lookup needed); anything else is looked up once.
TOWNS = {
    'FORNACI': BRESCIA, 'BRESCIA': BRESCIA, 'FLERO': ('Flero', 45.483, 10.175), 'PONCARALE': ('Poncarale', 45.461, 10.177),
    'CASTEL MELLA': ('Castel Mella', 45.498, 10.146), 'CASTELMELLA': ('Castel Mella', 45.498, 10.146),
    'LENO': ('Leno', 45.369, 10.215), 'VEROLANUOVA': ('Verolanuova', 45.326, 10.076),
    'CASTEGNATO': ('Castegnato', 45.563, 10.112), 'CAPRIANO DEL COLLE': ('Capriano del Colle', 45.455, 10.130),
    'TORBOLE CASAGLIA': ('Torbole Casaglia', 45.513, 10.115), 'ROVATO': ('Rovato', 45.565, 10.001),
    'GHEDI': ('Ghedi', 45.402, 10.278), 'BAGNOLO MELLA': ('Bagnolo Mella', 45.428, 10.185),
    'MANERBIO': ('Manerbio', 45.354, 10.138), 'CASTENEDOLO': ('Castenedolo', 45.471, 10.296),
    'BORGOSATOLLO': ('Borgosatollo', 45.476, 10.239), 'RONCADELLE': ('Roncadelle', 45.527, 10.153),
    'GUSSAGO': ('Gussago', 45.592, 10.157), 'REZZATO': ('Rezzato', 45.513, 10.329), 'TRAVAGLIATO': ('Travagliato', 45.523, 10.080),
    'OSPITALETTO': ('Ospitaletto', 45.555, 10.075), 'MONTICHIARI': ('Montichiari', 45.415, 10.391),
    'AZZANO MELLA': ('Azzano Mella', 45.453, 10.117), 'DELLO': ('Dello', 45.415, 10.075),
}
CONDITIONS = {'sereno': 'Sereno', 'nuvoloso': 'Nuvoloso', 'nebbia': 'Nebbia', 'pioggia': 'Pioggia', 'neve': 'Neve',
              'temporale': 'Temporale'}
SKY = {'sereno': '☀️', 'nuvoloso': '☁️', 'nebbia': '🌫️', 'pioggia': '🌧️', 'neve': '❄️', 'temporale': '⛈️'}


# --- Where and when ----------------------------------------------------------------

def town(venue):
    """(name, lat, lon) for a pitch address; None when it has to be looked up ('…, 25020 PONCARALE (BS)')."""
    text = re.sub(r'\s+', ' ', str(venue or '').upper())
    tail = re.split(r'\s+-\s+', text)[-1] if ' - ' in text else text.split(',')[-1]
    tail = re.sub(r'\(?\bBS\b\)?|\b\d{5}\b', ' ', tail).strip(' ,.-')
    for key in sorted(TOWNS, key=len, reverse=True):
        if re.search(r'\b'+key+r'\b', tail):
            return TOWNS[key]
    for key in sorted(TOWNS, key=len, reverse=True):
        if re.search(r'\b'+key+r'\b', text):
            return TOWNS[key]
    return None


def town_name(venue):
    """The town written in the address, for the lookup ('' if none)."""
    text = re.sub(r'\s+', ' ', str(venue or '').upper())
    tail = re.split(r'\s+-\s+', text)[-1] if ' - ' in text else (text.split(',')[-1] if ',' in text else '')
    tail = re.sub(r'\(?\bBS\b\)?|\b\d{5}\b|\bVIA\b.*', ' ', tail).strip(' ,.-')
    return tail.title() if 2 < len(tail) < 40 else ''


def _get(url, params, opener, timeout):
    request = urllib.request.Request(url+'?'+urllib.parse.urlencode(params), headers={'User-Agent': 'FlamingosStudio/3.25'})
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def locate(venue, opener=urllib.request.urlopen, timeout=TIMEOUT):
    """(name, lat, lon): known towns first, then Open-Meteo's town lookup, then Brescia."""
    known = town(venue)
    if known:
        return known
    name = town_name(venue)
    if name:
        try:
            data = _get(GEOCODE, {'name': name, 'count': 1, 'language': 'it', 'countryCode': 'IT', 'format': 'json'},
                        opener, timeout)
            hit = (data.get('results') or [None])[0]
            if hit:
                return hit.get('name', name), float(hit['latitude']), float(hit['longitude'])
        except Exception:                          # offline or an odd answer: the city is close enough
            pass
    return BRESCIA


def kickoff_time(date_text, clock):
    """The kick-off as a datetime (dd/mm/yyyy, HH:MM); None if either is still a placeholder."""
    from integration import parse_date
    day = parse_date(date_text)
    found = re.search(r'(\d{1,2})[:.](\d{2})', str(clock or ''))
    if not day or not found:
        return None
    hour, minute = int(found.group(1)), int(found.group(2))
    if hour > 23 or minute > 59:
        return None
    return dt.datetime(day.year, day.month, day.day, hour, minute)


def sunset(day, lat=BRESCIA[1], lon=BRESCIA[2]):
    """Local sunset (Europe/Rome, summer time included) with the usual NOAA approximation."""
    n = day.timetuple().tm_yday
    g = 2*math.pi/365*(n-1)
    eq = 229.18*(.000075+.001868*math.cos(g)-.032077*math.sin(g)-.014615*math.cos(2*g)-.040849*math.sin(2*g))
    decl = (.006918-.399912*math.cos(g)+.070257*math.sin(g)-.006758*math.cos(2*g)+.000907*math.sin(2*g)
            - .002697*math.cos(3*g)+.00148*math.sin(3*g))
    lat_r = math.radians(lat)
    cos_h = (math.cos(math.radians(90.833))/(math.cos(lat_r)*math.cos(decl))-math.tan(lat_r)*math.tan(decl))
    hour_angle = math.degrees(math.acos(max(-1, min(1, cos_h))))
    utc_minutes = 720-4*(lon-hour_angle)-eq
    utc = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)+dt.timedelta(minutes=utc_minutes)
    try:
        from zoneinfo import ZoneInfo
        local = utc.astimezone(ZoneInfo('Europe/Rome'))
    except Exception:                              # no time zone data: CET, one hour more in summer
        local = utc+dt.timedelta(hours=2 if 3 < day.month < 11 else 1)
    return local.replace(tzinfo=None)


def light(date_text, clock):
    """'notte' after dusk, 'tramonto' around the sunset, None in daylight or when the time is unknown."""
    when = kickoff_time(date_text, clock)
    if not when:
        return None
    down = sunset(when.date())
    if when >= down+dt.timedelta(minutes=35):
        return 'notte'
    if when >= down-dt.timedelta(minutes=70):
        return 'tramonto'
    if when.hour < 7:
        return 'notte'
    return None


# --- The forecast ------------------------------------------------------------------

def condition(code, chance=None):
    """One of CONDITIONS from a WMO weather code (and the chance of rain, when known)."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return ''
    if code >= 95:
        return 'temporale'
    if code in (71, 73, 75, 77, 85, 86):
        return 'neve'
    if 51 <= code <= 67 or 80 <= code <= 82:
        return 'pioggia' if code >= 61 or chance is None or chance >= 40 else 'nuvoloso'
    if code in (45, 48):
        return 'nebbia'
    if code == 3:
        return 'nuvoloso'
    return 'sereno'


def forecast(lat, lon, when, opener=urllib.request.urlopen, timeout=TIMEOUT):
    """{'weather', 'code', 'chance', 'temp'} at the kick-off hour; ValueError if the hour is not in the answer."""
    day = when.date().isoformat()
    data = _get(FORECAST, {'latitude': f'{lat:.3f}', 'longitude': f'{lon:.3f}', 'timezone': 'Europe/Rome',
                           'hourly': 'weather_code,precipitation_probability,temperature_2m',
                           'start_date': day, 'end_date': day}, opener, timeout)
    hourly = data.get('hourly') or {}
    stamp = when.replace(minute=0).strftime('%Y-%m-%dT%H:%M')
    times = hourly.get('time') or []
    if stamp not in times:
        raise ValueError('ora non presente nelle previsioni')
    i = times.index(stamp)

    def value(name):
        values = hourly.get(name) or []
        return values[i] if i < len(values) else None
    code, chance, temp = value('weather_code'), value('precipitation_probability'), value('temperature_2m')
    return dict(weather=condition(code, chance), code=code, chance=chance,
                temp=None if temp is None else round(float(temp)))


def note(result, place, when):
    """'🌧️ Pioggia (80%) · 7° · Castel Mella, sab 18:30' for the editor."""
    days = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')
    kind = result.get('weather', '')
    bits = [f"{SKY.get(kind, '')} {CONDITIONS.get(kind, 'Previsione')}".strip()
            + (f" ({result['chance']}%)" if result.get('chance') and kind in ('pioggia', 'temporale', 'neve') else '')]
    if result.get('temp') is not None:
        bits.append(f"{result['temp']}°")
    bits.append(f"{place}, {days[when.weekday()]} {when:%H:%M}")
    return ' · '.join(bits)[:90]


def check(match, today, opener=urllib.request.urlopen):
    """What to write in the graphics for this match: {'weather', 'note'}; None if it is too far ahead or past."""
    when = kickoff_time(match.get('date'), match.get('kickoff'))
    if not when:
        return None
    days = (when.date()-today).days
    if days < 0:
        return None
    if days > MAX_DAYS:
        return dict(weather='', note=f'Previsioni disponibili da {when.date()-dt.timedelta(days=MAX_DAYS):%d/%m}.')
    place, lat, lon = locate(match.get('venue'), opener)
    result = forecast(lat, lon, when, opener)
    return dict(weather=result['weather'], note=note(result, place, when))


# --- On the graphic ----------------------------------------------------------------

KINDS = ('matchday', 'convocati')


def _active(config, layout):
    return bool(config.get('weather_auto', True)) and str(layout).split('@')[0] in KINDS


def atmosphere(config, layout):
    """The light of the match (overrides the chosen atmosphere), or None to keep it."""
    if not _active(config, layout):
        return None
    sky = config.get('weather', '')
    dark = light(config.get('date'), config.get('kickoff'))
    if sky in ('pioggia', 'temporale', 'neve'):
        return 'notte' if dark == 'notte' else ('pioggia' if sky != 'neve' else 'neve')
    if sky == 'nebbia':
        return 'nebbia'
    return dark


def particles(config, layout):
    if not _active(config, layout):
        return ''
    return {'pioggia': 'rain', 'temporale': 'storm', 'neve': 'snow', 'nebbia': 'fog'}.get(config.get('weather', ''), '')


SCREEN = (78, 316, 462, 674)


def _drops(kind):
    rnd = random.Random({'rain': 11, 'storm': 12, 'snow': 13}.get(kind, 1))
    count = {'rain': 150, 'storm': 190, 'snow': 120}.get(kind, 0)
    return [(rnd.uniform(-60, 600), rnd.uniform(0, 980), rnd.uniform(.7, 1.3), rnd.uniform(0, 6.28), rnd.random())
            for _ in range(count)]


_DROPS = {}


def draw(canvas, kind, t):
    """Rain, storm or snow around the screen at time t (fog is part of the background)."""
    if kind not in ('rain', 'storm', 'snow'):
        return
    from PIL import Image
    from render_utils import ScaledDraw
    s = canvas.width/540
    layer = canvas if canvas.mode == 'RGB' else Image.new('RGBA', canvas.size)
    d = ScaledDraw(layer, s, 'RGBA' if canvas.mode == 'RGB' else None)
    drops = _DROPS.setdefault(kind, _drops(kind))
    x1, y1, x2, y2 = SCREEN
    for x0, y0, speed, phase, r in drops:
        if kind == 'snow':
            y = (y0+t*34*speed) % 980-10
            x = x0+math.sin(t*1.2*speed+phase)*11
            inside = x1 < x < x2 and y1 < y < y2
            size = 2.4+r*3.6
            d.ellipse((x, y, x+size, y+size), fill=(248, 251, 255, 70 if inside else 225))
        else:
            fall = 640 if kind == 'storm' else 520
            y = (y0+t*fall*speed) % 980-20
            x = (x0-(y-y0)*.22) % 620-40
            if x1-4 < x < x2+4 and y1-12 < y < y2+4:
                continue                              # never over the screen
            length = 9+r*9
            d.line((x, y, x-length*.22, y+length), fill=(214, 230, 255, 130+round(r*100)), width=1.1)
    if kind == 'storm':
        flash = max(0.0, 1-abs((t % 3.7)-1.15)*9)
        if flash > 0:
            d.rectangle((0, 0, 540, 960), fill=(235, 240, 255, round(70*flash)))
    if layer is not canvas:
        canvas.alpha_composite(layer)


def haze(image, s):
    """Fog: a milky veil rising from the bottom around the screen (static, part of the background)."""
    import numpy as np
    from PIL import Image
    arr = np.asarray(image).astype(np.float32)
    h, w = arr.shape[:2]
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    amount = .18+.42*np.clip((y-.25)/.75, 0, 1)
    rng = np.random.default_rng(5)
    clouds = rng.random((max(2, h//(60*int(s) or 1)), max(2, w//(60*int(s) or 1)))).astype(np.float32)
    clouds = np.asarray(Image.fromarray((clouds*255).astype('uint8')).resize((w, h), Image.Resampling.BICUBIC),
                        np.float32)[..., None]/255
    amount = amount*(.7+.6*clouds)
    rgb = arr[..., :3]+(np.array((214, 220, 228), np.float32)-arr[..., :3])*np.clip(amount, 0, .78)
    x1, y1, x2, y2 = (round(v*s) for v in SCREEN)
    rgb[y1:y2, x1:x2] = arr[y1:y2, x1:x2, :3]
    out = np.concatenate([rgb.clip(0, 255), arr[..., 3:]], axis=2).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')
