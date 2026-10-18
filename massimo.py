"""Calendario ufficiale del Cinema Massimo (testo per giorno/sala, con ospiti e festival)."""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .common import get, load, save, set_health, config

MONTHS = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
DAY_RE = re.compile(r"^(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(\d{1,2})\s+([a-zà]+)", re.I)
TIME_LINE = re.compile(
    r"^((?:\d{1,2}[.:]\d{2}\s*(?:/|,|e|-)?\s*)+)\s*(?:[–-]\s*Sala\s*(\d|Uno|Due|Tre)\s*[–-]\s*)?(.+)$", re.I)
ROOM_RE = re.compile(r"^Sala\s+(Uno|Due|Tre|1|2|3)\b", re.I)
FEST_RE = re.compile(r"^DA\s+\w+\s+(\d{1,2})\s+A\s+\w+\s+(\d{1,2})\s+([A-Za-zà]+)\s+(.+)$", re.I)
NOTE_START = ("il film è introdotto", "al termine", "ingresso", "in presenza", "incontro", "a seguire", "con la presenza")
ROOMS = {"1": "Sala 1", "uno": "Sala 1", "2": "Sala 2", "due": "Sala 2", "3": "Sala 3", "tre": "Sala 3"}


def _year_for(month, today):
    return today.year + 1 if month < today.month - 6 else today.year


def split_title(rest):
    """'Balcanica di N. Sorcinelli (I/Serbia 2026, 86’)' -> (titolo, regia, anno)."""
    rest = rest.replace("**", "").strip()
    year = None
    paren = rest.rfind("(")
    head, tail = (rest[:paren], rest[paren:]) if paren > 0 else (rest, "")
    ym = re.search(r"(19|20)\d{2}", tail)
    if ym:
        year = int(ym.group(0))
    head = head.strip(" –-")
    idx = head.rfind(" di ")
    if idx > 0 and tail:
        return head[:idx].strip(), head[idx + 4:].strip(), year
    return head, "", year


def parse_calendar(html_text, today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "section"]):
        tag.insert_before("\n")  # a capo solo sui blocchi: i tag inline (<strong>) restano sulla stessa riga
    lines = [re.sub(r"\s+", " ", l).strip() for l in soup.get_text("").split("\n")]
    lines = [l for l in lines if l]
    shows, festivals = [], []
    date = room = last = None
    for line in lines:
        clean = line.replace("*", "").strip()
        m = DAY_RE.match(clean)
        if m and m.group(2).lower() in MONTHS:
            mo = MONTHS[m.group(2).lower()]
            try:
                date = dt.date(_year_for(mo, today), mo, int(m.group(1)))
            except ValueError:
                date = None
            room = last = None
            continue
        f = FEST_RE.match(clean)
        if f and f.group(3).lower() in MONTHS:
            mo = MONTHS[f.group(3).lower()]
            y = _year_for(mo, today)
            try:
                festivals.append({"title": f.group(4).strip(), "start": dt.date(y, mo, int(f.group(1))).isoformat(),
                                  "end": dt.date(y, mo, int(f.group(2))).isoformat()})
            except ValueError:
                pass
            continue
        r = ROOM_RE.match(clean)
        if r and len(clean) < 30:
            room = ROOMS[r.group(1).lower()]
            continue
        if date is None:
            continue
        t = TIME_LINE.match(clean)
        if t:
            times = re.findall(r"\d{1,2}[.:]\d{2}", t.group(1))
            times = [x.replace(".", ":").zfill(5) for x in times]
            title, director, year = split_title(t.group(3))
            if not title:
                continue
            last = {"date": date.isoformat(), "times": times, "title": title, "director": director,
                    "year": year, "room": ROOMS.get((t.group(2) or "").lower(), room), "note": []}
            shows.append(last)
            continue
        if last and clean.lower().startswith(NOTE_START):
            last["note"].append(clean)
    for s in shows:
        s["note"] = " · ".join(s["note"])
    return shows, festivals


def run():
    cfg = config()
    try:
        shows, fests = parse_calendar(get(cfg["massimo_calendar"]).text)
        if not shows:
            raise RuntimeError("calendario letto ma nessuna proiezione trovata (formato cambiato?)")
        save("massimo.json", {"shows": shows, "festivals": fests})
        set_health("massimo_calendario", True, len(shows))
    except Exception as e:
        old = load("massimo.json", {"shows": []})
        set_health("massimo_calendario", False, len(old["shows"]), str(e)[:200])
