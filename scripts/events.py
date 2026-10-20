"""Mostre / eventi / conferenze: parser dedicati per ogni sito (nessun servizio esterno, nessuna chiave).

Fonti: arte.it (calendario mensile), CAMERA (mostre e agenda), Museo Nazionale del Cinema (calendario),
Turismo Torino (agenda). Ogni parser è tollerante; se un sito cambia, la fonte risulta "non aggiornata".
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .common import get, load, save, set_health, config, norm
from .massimo import MONTHS

D = r"(\d{1,2})\s+([A-Za-zàèéìòù]+)\s+(\d{4})"
DATE_RE = re.compile(D)
SLASH_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
PHOTO = ("fotograf", "photo", "camera -", "scatt", "obiettivo")
CINEMA = ("cinema", "film", "cinematograf", "regista", "pontecorvo", "set ", "schermo")


def _d(day, month, year):
    mo = MONTHS.get(month.lower())
    if not mo:
        return None
    try:
        return dt.date(int(year), mo, int(day)).isoformat()
    except ValueError:
        return None


def guess_tag(*texts):
    t = " ".join(x or "" for x in texts).lower()
    if any(k in t for k in PHOTO):
        return "fotografia"
    if any(k in t for k in CINEMA):
        return "cinema"
    return "arte"


def date_range(text):
    """Primo intervallo di date trovato: 'Dal 3 ottobre 2026 al 8 dicembre 2026', '17 ottobre 2026 – 7 febbraio 2027',
    '10/09/2026 to 31/01/2027', '12 – 20 settembre 2026'. -> (start, end) oppure (None, None)."""
    s = SLASH_RE.findall(text)
    if s:
        d1 = dt.date(int(s[0][2]), int(s[0][1]), int(s[0][0])).isoformat()
        d2 = dt.date(int(s[1][2]), int(s[1][1]), int(s[1][0])).isoformat() if len(s) > 1 else d1
        return d1, d2
    ms = [m for m in DATE_RE.finditer(text) if m.group(2).lower() in MONTHS]
    full = [(m.group(1), m.group(2), m.group(3)) for m in ms]
    if full:
        d1 = _d(*full[0])
        if len(full) > 1:
            return d1, _d(*full[1])
        open_ended = text[:ms[0].start()].rstrip().lower().endswith("dal")
        return d1, (None if open_ended else d1)
    return None, None


def _item(title, venue, start, end, kind, tag, url, source, desc=""):
    return {"title": re.sub(r"\s+", " ", title).strip(" ·-–"), "venue": venue, "start": start, "end": end,
            "kind": kind, "tag": tag, "desc": desc[:160], "url": url, "source": source}


# ---------- arte.it ----------
def parse_arte(html_text, source):
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    for a in soup.select('a[href*="/calendario-arte/"]'):
        href = a.get("href", "")
        if not re.search(r"/(mostra|evento)-", href):
            continue
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        m = re.search(r"^(.*?)\s*\bDal\s+(?:" + D + r")(?:\s+al\s+(?:" + D + r"))?(.*)$", text, re.I)
        if not m:
            continue
        title = m.group(1)
        start = _d(*m.group(2, 3, 4))
        end = _d(*m.group(5, 6, 7)) if m.group(5) else start
        rest = m.group(8).strip()
        venue = ""
        for line in a.get_text("\n", strip=True).split("\n"):
            if "|" in line and len(line) < 120:
                city, _, place = line.partition("|")
                venue = f"{city.strip()} – {place.strip()}"
                break
        if not venue:
            v = re.match(r"([^|]{2,40})\|\s*(.{3,70})", rest)
            if v:
                venue = f"{v.group(1).strip()} – {v.group(2).strip()}"
        if not start:
            continue
        url = href if href.startswith("http") else "https://www.arte.it" + href
        kind = "mostra" if "/mostra-" in href else "evento"
        out.append(_item(title, venue, start, end, kind, guess_tag(title, venue), url, source, rest[-150:]))
    return out


# ---------- CAMERA ----------
def parse_camera(html_text, source, kind):
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    pat = "/mostre/" if kind == "mostra" else "/"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(" ", strip=True)
        if not re.search(r"camera\.to/(mostre|agenda|incontri|eventi|contenuti-incontri)/[^/]+/?$", href) or len(title) < 4:
            continue
        head = a.find_parent(["h1", "h2", "h3", "h4", "h5"]) or a
        text = ""
        for sib in list(head.next_siblings)[:4]:
            if getattr(sib, "name", None) in ("h1", "h2", "h3", "h4", "h5"):
                break
            text += " " + (sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib))
        start, end = date_range(text)
        if not start and not end:
            continue
        venue = "CAMERA"
        vm = re.match(r"\s*-?\s*([^|\d]{3,60})\|", text)
        if vm:
            venue = vm.group(1).strip()
        out.append(_item(title, venue, start, end, "mostra" if "/mostre/" in href else "evento", "fotografia",
                         href, source))
    return out


# ---------- Museo del Cinema ----------
def parse_museo(html_text, source):
    soup = BeautifulSoup(html_text, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/it/(attivita|mostre)/", href):
            continue
        box = a
        for _ in range(5):
            box = box.parent
            if box is None or DATE_RE.search(box.get_text(" ", strip=True)):
                break
        if box is None:
            continue
        lines = [l.strip() for l in box.get_text("\n", strip=True).split("\n") if l.strip()]
        di = next((i for i, l in enumerate(lines) if any(m.group(2).lower() in MONTHS for m in DATE_RE.finditer(l))), None)
        if di is None or di + 1 >= len(lines):
            continue
        start, end = date_range(lines[di])
        title = lines[di + 1]
        venue = lines[di + 2] if di + 2 < len(lines) and lines[di + 2] != "Vai alla pagina" else "Museo Nazionale del Cinema"
        url = href if href.startswith("http") else "https://www.museocinema.it" + href
        if url in seen or not start:
            continue
        seen.add(url)
        out.append(_item(title, venue, start, end, "mostra" if "/it/mostre/" in href else "evento", "cinema", url, source))
    return out


# ---------- Turismo Torino ----------
def parse_turismo(html_text, source):
    soup = BeautifulSoup(html_text, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/it/visita/eventi/[^/]+$", href) or href.endswith("/agenda"):
            continue
        url = href if href.startswith("http") else "https://turismotorino.org" + href
        if url in seen:
            continue
        box = a
        for _ in range(4):
            box = box.parent
            if box is None or SLASH_RE.search(box.get_text(" ", strip=True)):
                break
        if box is None:
            continue
        text = box.get_text("\n", strip=True)
        start, end = date_range(text)
        lines = [l for l in text.split("\n") if l.strip()]
        title = a.get_text(" ", strip=True) or (lines[0] if lines else "")
        if not start or len(title) < 3:
            continue
        seen.add(url)
        multi = start != end and (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days > 20
        out.append(_item(title, "Torino", start, end, "mostra" if multi and "mostra" in text.lower() else "evento",
                         guess_tag(title, text), url, source))
    return out


PARSERS = {"arte": lambda h, n, u: parse_arte(h, n), "camera_mostre": lambda h, n, u: parse_camera(h, n, "mostra"),
           "camera_agenda": lambda h, n, u: parse_camera(h, n, "evento"), "museo": lambda h, n, u: parse_museo(h, n),
           "turismo": lambda h, n, u: parse_turismo(h, n)}


def _valid(i, today):
    return bool(i.get("title")) and not (i.get("end") and i["end"] < today)


def run():
    cfg = config()
    today = dt.date.today()
    urls = []
    for src in cfg["event_pages"]:
        if "{yyyy}" in src["url"]:
            for k in range(src.get("months_ahead", 0) + 1):
                m = today.month - 1 + k
                urls.append((src, src["url"].format(yyyy=today.year + m // 12, mm=f"{m % 12 + 1:02d}")))
        else:
            urls.append((src, src["url"]))
    allitems, failed_sources = {}, set()
    per_source = {}
    for src, url in urls:
        name = src["name"]
        try:
            items = PARSERS[src["parser"]](get(url, delay=2).text, name, url)
            items = [i for i in items if _valid(i, today.isoformat())]
            per_source[name] = per_source.get(name, 0) + len(items)
            for i in items:
                allitems[(norm(i["title"]), i["start"])] = i
        except Exception as e:
            per_source.setdefault(name, 0)
            set_health(f"eventi: {name}", False, 0, str(e)[:200])
            failed_sources.add(name)
    for name, n in per_source.items():
        if name not in failed_sources:
            set_health(f"eventi: {name}", n > 0, n, "" if n else "pagina letta ma nessun evento riconosciuto (formato cambiato?)")
    old = load("events.json", [])
    bad = failed_sources | {n for n, c in per_source.items() if c == 0}
    keep = [o for o in old if o.get("source") in bad and _valid(o, today.isoformat())]
    if allitems or keep:
        save("events.json", list(allitems.values()) + keep)
