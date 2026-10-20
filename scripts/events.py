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


RANGE_RE = re.compile(r"(\d{1,2})(?:\s+([A-Za-zàèéìòù]+))?(?:\s+(\d{4}))?\s*[–—-]\s*(\d{1,2})\s+([A-Za-zàèéìòù]+)\s+(\d{4})")


def date_range(text):
    """Primo intervallo di date trovato: 'Dal 3 ottobre 2026 al 8 dicembre 2026', '17 ottobre 2026 – 7 febbraio 2027',
    '10/09/2026 to 31/01/2027', '12 – 20 settembre 2026'. -> (start, end) oppure (None, None)."""
    s = SLASH_RE.findall(text)
    if s:
        d1 = dt.date(int(s[0][2]), int(s[0][1]), int(s[0][0])).isoformat()
        d2 = dt.date(int(s[1][2]), int(s[1][1]), int(s[1][0])).isoformat() if len(s) > 1 else d1
        return d1, d2
    for m in RANGE_RE.finditer(text):
        m2 = m.group(5).lower()
        m1 = (m.group(2) or m2).lower()
        if m2 in MONTHS and m1 in MONTHS:
            y2 = int(m.group(6))
            y1 = int(m.group(3)) if m.group(3) else (y2 if MONTHS[m1] <= MONTHS[m2] else y2 - 1)
            return _d(m.group(1), m1, y1), _d(m.group(4), m2, y2)
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
    out, seen = [], set()
    for a in soup.select('a[href*="/calendario-arte/"]'):
        href = a.get("href", "")
        if not re.search(r"/(mostra|evento)-", href) or href in seen:
            continue
        if len(a.get_text(" ", strip=True)) < 4:  # link della sola immagine: il titolo è in un altro link uguale
            continue
        box = a
        while box is not None and not re.search(r"\bDal\s+" + D, box.get_text(" ", strip=True), re.I):
            box = box.parent if box.parent is not None and box.parent.name not in ("body", "html") else None
        if box is None or len(box.get_text(" ", strip=True)) > 700:  # contenitore troppo grande: più voci mischiate
            continue
        text = re.sub(r"\s+", " ", box.get_text(" ", strip=True))
        dm = re.search(r"\bDal\s+" + D + r"(?:\s+al\s+" + D + r")?", text, re.I)
        start = _d(*dm.group(1, 2, 3))
        end = _d(*dm.group(4, 5, 6)) if dm.group(4) else None
        if dm.group(4) is None:
            end = None
        title = a.get_text(" ", strip=True)
        title = re.split(r"\s*\bDal\s+\d", title, 1, flags=re.I)[0].strip()
        if len(title) < 4:
            title = text[:dm.start()].strip()
        venue = ""
        for line in box.get_text("\n", strip=True).split("\n"):
            if "|" in line and len(line) < 120 and not re.search(r"\bDal\s+\d", line, re.I):
                city, _, place = line.partition("|")
                venue = f"{city.strip()} – {place.strip()}"
                break
        if not venue:
            v = re.search(r"([^|]{2,40})\|\s*(.{3,70})", text[dm.end():])
            if v:
                venue = f"{v.group(1).strip()} – {v.group(2).strip()}"
        if not start or len(title) < 4:
            continue
        seen.add(href)
        url = href if href.startswith("http") else "https://www.arte.it" + href
        out.append(_item(title, venue, start, end, "mostra" if "/mostra-" in href else "evento",
                         guess_tag(title, venue), url, source, text[dm.end():dm.end() + 150]))
    return out


# ---------- CAMERA ----------
def parse_camera(html_text, source, kind):
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(" ", strip=True)
        if not re.search(r"camera\.to/(mostre|incontri)/[^/]+/?$", href) or len(title) < 4:
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
        pre = re.split(r"\d", text.strip(), 1)[0]
        if "/mostre/" in href:  # CAMERA elenca anche mostre in altre città: teniamo solo Torino
            if pre.strip(" |-,") and not re.search(r"camera|torino|project room|bagni|aurora|barriera|dorado", pre, re.I):
                continue
        venue = "CAMERA"
        vm = re.match(r"\s*-?\s*([^|\d]{3,60})\|", text)
        if vm and "/mostre/" in href and not re.match(r"\s*(incontro|letti)", vm.group(1), re.I):
            venue = vm.group(1).strip()
        out.append(_item(title, venue, start, end, "mostra" if "/mostre/" in href else "conferenza", "fotografia",
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
        j = di + 1
        while j < len(lines) - 1 and re.match(r"^(ore\s*)?\d{1,2}[:.]\d{2}", lines[j], re.I):
            j += 1
        title = lines[j]
        venue = lines[j + 1] if j + 1 < len(lines) and lines[j + 1] != "Vai alla pagina" else "Museo Nazionale del Cinema"
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
           "camera_incontri": lambda h, n, u: parse_camera(h, n, "incontro"), "museo": lambda h, n, u: parse_museo(h, n),
           "turismo": lambda h, n, u: parse_turismo(h, n)}


def _valid(i, today):
    return bool(i.get("title")) and not (i.get("end") and i["end"] < today)


def run():
    cfg = config()
    today = dt.date.today()
    names = {x["name"] for x in cfg["event_pages"]}
    h = load("health.json", {})
    save("health.json", {k: v for k, v in h.items() if not k.startswith("eventi:") or k[len("eventi: "):] in names})
    urls = []
    for src in cfg["event_pages"]:
        if "{yyyy}" in src["url"]:
            for k in range(src.get("months_ahead", 0) + 1):
                m = today.month - 1 + k
                urls.append((src, src["url"].format(yyyy=today.year + m // 12, mm=f"{m % 12 + 1:02d}")))
        else:
            urls.append((src, src["url"]))
    allitems, failed_sources = {}, set()
    per_source, diag = {}, {}
    for src, url in urls:
        name = src["name"]
        try:
            html_text = get(url, delay=2).text
            items = PARSERS[src["parser"]](html_text, name, url)
            if not items:
                sp = BeautifulSoup(html_text, "html.parser")
                diag[name] = (f"{len(html_text)} byte; titolo: {(sp.title.string or '')[:50] if sp.title else '-'}; "
                              f"link totali: {len(sp.find_all('a'))}; link mostra/evento: "
                              f"{len(sp.select('a[href*=\"/mostra-\"], a[href*=\"/evento-\"], a[href*=\"/attivita/\"], a[href*=\"/eventi/\"]'))}")
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
            set_health(f"eventi: {name}", n > 0, n, "" if n else "nessun evento riconosciuto. " + diag.get(name, ""))
    old = load("events.json", [])
    bad = failed_sources | {n for n, c in per_source.items() if c == 0}
    keep = [o for o in old if o.get("source") in bad and _valid(o, today.isoformat())]
    if allitems or keep:
        save("events.json", list(allitems.values()) + keep)
