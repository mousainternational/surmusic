"""Weather for the world's big cities, kept up to date by itself (Open-Meteo, free, no key).

One request every 30 minutes asks for all the cities at once. Visitors only ever read the saved copy (memory, then the
database copy): a page never waits for the weather service, and a restart does not empty it.
"""
import json
import logging
import re
import threading
import urllib.parse
import time
import urllib.request

from .util import slugify

# (city, country, key of the country's radio page, latitude, longitude)
CITIES = [
    ("Lahore", "Pakistan", "pakistan", 31.55, 74.34), ("Karachi", "Pakistan", "pakistan", 24.86, 67.01),
    ("Islamabad", "Pakistan", "pakistan", 33.68, 73.05), ("Rawalpindi", "Pakistan", "pakistan", 33.60, 73.04),
    ("Faisalabad", "Pakistan", "pakistan", 31.42, 73.08), ("Multan", "Pakistan", "pakistan", 30.20, 71.47),
    ("Peshawar", "Pakistan", "pakistan", 34.01, 71.58), ("Quetta", "Pakistan", "pakistan", 30.18, 67.00),
    ("Hyderabad Sindh", "Pakistan", "pakistan", 25.40, 68.37), ("Sialkot", "Pakistan", "pakistan", 32.49, 74.53),
    ("Gujranwala", "Pakistan", "pakistan", 32.16, 74.19), ("Mumbai", "India", "india", 19.08, 72.88),
    ("Delhi", "India", "india", 28.61, 77.21), ("Bengaluru", "India", "india", 12.97, 77.59),
    ("Kolkata", "India", "india", 22.57, 88.36), ("Chennai", "India", "india", 13.08, 80.27),
    ("Hyderabad India", "India", "india", 17.39, 78.49), ("Ahmedabad", "India", "india", 23.02, 72.57),
    ("Pune", "India", "india", 18.52, 73.86), ("Jaipur", "India", "india", 26.91, 75.79),
    ("Dhaka", "Bangladesh", "bangladesh", 23.81, 90.41), ("Chittagong", "Bangladesh", "bangladesh", 22.36, 91.78),
    ("Kabul", "Afghanistan", "afghanistan", 34.53, 69.17), ("Kathmandu", "Nepal", "nepal", 27.72, 85.32),
    ("Colombo", "Sri Lanka", "sri-lanka", 6.93, 79.86), ("Dubai", "UAE", "uae", 25.20, 55.27),
    ("Abu Dhabi", "UAE", "uae", 24.45, 54.38), ("Riyadh", "Saudi Arabia", "saudi-arabia", 24.71, 46.68),
    ("Jeddah", "Saudi Arabia", "saudi-arabia", 21.49, 39.19), ("Makkah", "Saudi Arabia", "saudi-arabia", 21.39, 39.86),
    ("Madinah", "Saudi Arabia", "saudi-arabia", 24.47, 39.61), ("Doha", "Qatar", "qatar", 25.29, 51.53),
    ("Kuwait City", "Kuwait", "kuwait", 29.38, 47.99), ("Muscat", "Oman", "oman", 23.59, 58.41),
    ("Manama", "Bahrain", "bahrain", 26.23, 50.59), ("Baghdad", "Iraq", "iraq", 33.31, 44.37),
    ("Tehran", "Iran", "iran", 35.69, 51.39), ("Amman", "Jordan", "jordan", 31.95, 35.93),
    ("Istanbul", "Turkey", "turkey", 41.01, 28.98), ("Ankara", "Turkey", "turkey", 39.93, 32.86),
    ("Cairo", "Egypt", "egypt", 30.04, 31.24), ("Casablanca", "Morocco", "morocco", 33.57, -7.59),
    ("Lagos", "Nigeria", "nigeria", 6.52, 3.38), ("Abuja", "Nigeria", "nigeria", 9.08, 7.40),
    ("Nairobi", "Kenya", "kenya", -1.29, 36.82), ("Johannesburg", "South Africa", "south-africa", -26.20, 28.05),
    ("Cape Town", "South Africa", "south-africa", -33.92, 18.42), ("London", "UK", "uk", 51.51, -0.13),
    ("Manchester", "UK", "uk", 53.48, -2.24), ("Birmingham", "UK", "uk", 52.49, -1.89),
    ("Paris", "France", "france", 48.86, 2.35), ("Berlin", "Germany", "germany", 52.52, 13.41),
    ("Madrid", "Spain", "spain", 40.42, -3.70), ("Rome", "Italy", "italy", 41.90, 12.50),
    ("Moscow", "Russia", "russia", 55.76, 37.62), ("New York", "USA", "usa", 40.71, -74.01),
    ("Los Angeles", "USA", "usa", 34.05, -118.24), ("Chicago", "USA", "usa", 41.88, -87.63),
    ("Houston", "USA", "usa", 29.76, -95.37), ("Toronto", "Canada", "canada", 43.65, -79.38),
    ("Mexico City", "Mexico", "mexico", 19.43, -99.13), ("Sao Paulo", "Brazil", "brazil", -23.55, -46.63),
    ("Buenos Aires", "Argentina", "argentina", -34.60, -58.38), ("Sydney", "Australia", "australia", -33.87, 151.21),
    ("Melbourne", "Australia", "australia", -37.81, 144.96), ("Tokyo", "Japan", "japan", 35.68, 139.69),
    ("Seoul", "South Korea", "south-korea", 37.57, 126.98), ("Beijing", "China", "china", 39.90, 116.41),
    ("Shanghai", "China", "china", 31.23, 121.47), ("Bangkok", "Thailand", "thailand", 13.76, 100.50),
    ("Jakarta", "Indonesia", "indonesia", -6.21, 106.85), ("Kuala Lumpur", "Malaysia", "malaysia", 3.14, 101.69),
    ("Singapore", "Singapore", "singapore", 1.35, 103.82), ("Manila", "Philippines", "philippines", 14.60, 120.98),
]
BY_SLUG = {slugify(c[0], 60): c for c in CITIES}

CODES = {0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle",
         55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
         67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers", 81: "Rain showers",
         82: "Violent rain showers", 85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}

TTL = 3 * 3600                    # MET Norway: the same place is not asked more often than every 3 hours
log = logging.getLogger(__name__)
_lock = threading.Lock()
_DATA = {}                       # slug -> {t (saved at), now: {...}, days: [...]}
_THREAD = {"pid": None}


def _num(v):
    return round(v) if isinstance(v, (int, float)) else None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SurMusicRadio/1.0 (+https://www.surmusicradio.com)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (fixed https host)
        raw = r.read(3 * 1024 * 1024 + 1)
    if len(raw) > 3 * 1024 * 1024:
        raise ValueError("answer too large")
    return json.loads(raw.decode("utf-8", "replace"))


def parse_place(block):
    """One Open-Meteo place -> what a page shows, or None if it is incomplete."""
    cur, daily = block.get("current") or {}, block.get("daily") or {}
    days = []
    for i, d in enumerate(daily.get("time") or []):
        try:
            days.append({"d": d, "hi": _num(daily["temperature_2m_max"][i]), "lo": _num(daily["temperature_2m_min"][i]),
                         "text": CODES.get(daily["weather_code"][i], "Changing"), "rain": _num((daily.get("precipitation_probability_max") or [None] * 9)[i])})
        except (KeyError, IndexError, TypeError):
            continue
    if cur.get("temperature_2m") is None or not days:
        return None
    return {"temp": _num(cur.get("temperature_2m")), "feels": _num(cur.get("apparent_temperature")), "hum": _num(cur.get("relative_humidity_2m")),
            "wind": _num(cur.get("wind_speed_10m")), "text": CODES.get(cur.get("weather_code"), "Changing"), "days": days[:7]}


_MET_TEXT = (("thunder", "Thunderstorm"), ("heavysnow", "Heavy snow"), ("lightsnow", "Light snow"), ("snow", "Snow"), ("sleet", "Rain and snow"),
             ("heavyrain", "Heavy rain"), ("lightrain", "Light rain"), ("showers", "Rain showers"), ("rain", "Rain"), ("fog", "Fog"),
             ("partlycloudy", "Partly cloudy"), ("cloudy", "Overcast"), ("fair", "Mainly clear"), ("clearsky", "Clear sky"))


def met_text(code):
    low = str(code or "").lower()
    return next((t for k, t in _MET_TEXT if k in low), "Changing")


def parse_met(block, lon=0.0):
    """One MET Norway (api.met.no) forecast -> what a page shows, or None if it is incomplete. Days follow the place's own clock (longitude / 15)."""
    from datetime import datetime, timedelta, timezone
    series = ((block or {}).get("properties") or {}).get("timeseries") or []
    shift = timedelta(hours=round(float(lon) / 15))
    days, order, now = {}, [], None
    for e in series:
        try:
            when = datetime.fromisoformat(e["time"].replace("Z", "+00:00")).astimezone(timezone.utc) + shift
            det = e["data"]["instant"]["details"]
            t = det["air_temperature"]
        except (KeyError, TypeError, ValueError):
            continue
        data = e["data"]
        sym = ((data.get("next_1_hours") or data.get("next_6_hours") or {}).get("summary") or {}).get("symbol_code")
        if now is None:
            now = {"temp": _num(t), "feels": _num(t), "hum": _num(det.get("relative_humidity")),
                   "wind": _num(det.get("wind_speed") * 3.6) if isinstance(det.get("wind_speed"), (int, float)) else None, "text": met_text(sym)}
        d = when.strftime("%Y-%m-%d")
        if d not in days:
            days[d] = {"d": d, "temps": [], "mid": None, "best": 99}
            order.append(d)
        days[d]["temps"].append(t)
        sym6 = ((data.get("next_6_hours") or {}).get("summary") or {}).get("symbol_code") or sym
        gap = abs(when.hour - 12)
        if sym6 and gap < days[d]["best"]:
            days[d]["best"], days[d]["mid"] = gap, sym6
    out = [{"d": d, "hi": _num(max(days[d]["temps"])), "lo": _num(min(days[d]["temps"])), "text": met_text(days[d]["mid"]), "rain": None} for d in order if days[d]["temps"]]
    if now is None or not out:
        return None
    now["days"] = out[:7]
    return now


def _met_url(lat, lon):
    return "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=%.4f&lon=%.4f" % (float(lat), float(lon))


def refresh_all(fetch=None):
    """One request per city to MET Norway (free, no key), about half a second apart; returns how many cities were updated.
    A failed request keeps the old copy."""
    live = fetch is None
    fetch = fetch or _get
    got = 0
    for i, c in enumerate(CITIES):
        if live and i:
            time.sleep(0.5)
        try:
            block = fetch(_met_url(c[3], c[4]))
        except Exception as exc:
            log.warning("Weather request failed (%s %s)", exc.__class__.__name__, getattr(exc, "code", "") or str(exc)[:80])
            continue
        info = parse_met(block, c[4])
        if info:
            with _lock:
                _DATA[slugify(c[0], 60)] = dict(info, t=time.time())
            got += 1
    return got


def get(slug):
    with _lock:
        return _DATA.get(slug)


def saved_copy():
    with _lock:
        return dict(_DATA)


def load_saved(data):
    """Put a database copy (after a restart) into memory, only for cities not yet known."""
    if not isinstance(data, dict):
        return
    with _lock:
        for k, v in data.items():
            if k in BY_SLUG and k not in _DATA and isinstance(v, dict) and v.get("days"):
                _DATA[k] = v


def start(app, keep, peek):
    """Background refresh in this process (once per process). keep(key, data) saves a copy, peek(key) reads it."""
    import os
    if app.config.get("TESTING") or app.config.get("RADIO_DEMO") or _THREAD["pid"] == os.getpid():
        return None
    _THREAD["pid"] = os.getpid()

    def run():
        time.sleep(15)
        while True:
            try:
                with app.app_context():
                    if not _DATA:
                        load_saved(peek("keep:weather"))
                    if refresh_all():
                        keep("keep:weather", saved_copy())
            except Exception:
                pass
            time.sleep(TTL if _DATA else 120)
    t = threading.Thread(target=run, daemon=True, name="weather")
    t.start()
    return t


def f_from_c(c):
    return round(c * 9 / 5 + 32) if c is not None else None


_SAFE = re.compile(r"[^a-z0-9-]")


def valid_slug(slug):
    return bool(slug) and not _SAFE.search(slug) and slug in BY_SLUG


# ---------------------------------------------------------------- any other place a visitor comes from (for the header gadget)
_PLACES = {}                 # "CC:city" -> {"t", "name", ...weather} or {"t", "none": True}
_BUSY = set()


def _place_key(cc, city):
    return f"{cc.upper()}:{' '.join(city.lower().split())[:60]}"


def fetch_place(cc, city, get=None):
    """Find the place (Open-Meteo's free name search) and read its weather. Stored in memory; an unknown place is remembered too."""
    get = get or _get
    key = _place_key(cc, city)
    try:
        found = (get("https://geocoding-api.open-meteo.com/v1/search?name=" + urllib.parse.quote(city[:60]) + "&count=1&language=en&format=json&countryCode=" + cc.upper()) or {}).get("results") or []
        if not found:
            info = {"none": True}
        else:
            p = found[0]
            data = get(_met_url(p["latitude"], p["longitude"]))
            info = parse_met(data, p["longitude"]) or {"none": True}
            info["name"] = str(p.get("name") or city)[:60]
    except Exception:
        return None
    info["t"] = time.time()
    with _lock:
        _PLACES[key] = info
        if len(_PLACES) > 300:
            for k in sorted(_PLACES, key=lambda k: _PLACES[k]["t"])[:60]:
                _PLACES.pop(k, None)
    return info


def place(cc, city):
    """The saved weather of a visitor's own place (None = not known yet: it is looked up in the background for the next look)."""
    import os
    if not re.fullmatch(r"[A-Za-z]{2}", cc or "") or not city or len(city) > 60 or not re.fullmatch(r"[^\W\d_][\w .'\-]*", city, re.U):
        return None
    key = _place_key(cc, city)
    with _lock:
        hit = _PLACES.get(key)
    if hit and time.time() - hit["t"] < (TTL if not hit.get("none") else 6 * 3600):
        return None if hit.get("none") else hit
    if os.environ.get("PYTEST_CURRENT_TEST") or key in _BUSY or len(_BUSY) >= 3:
        return None if not hit or hit.get("none") else hit
    _BUSY.add(key)

    def run():
        try:
            fetch_place(cc, city)
        finally:
            _BUSY.discard(key)
    threading.Thread(target=run, daemon=True, name="weather-place").start()
    return None if not hit or hit.get("none") else hit
