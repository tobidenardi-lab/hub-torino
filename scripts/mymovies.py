"""MYmovies: programmazione di oggi per ogni cinema di Torino (una pagina per cinema)."""
import datetime as dt
import re

from bs4 import BeautifulSoup, NavigableString

from .common import get, load, save, set_health, config

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
FILM_HREF = re.compile(r"/film/(\d{4})/([^/?#]+)/?")


def parse_cinema_page(html_text):
    """Ritorna [{title, year, slug, times:[{t,vo}]}] nell'ordine della pagina."""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    films, cur, vo = [], None, False
    for el in soup.descendants:
        if getattr(el, "name", None) == "a":
            m = FILM_HREF.search(el.get("href", ""))
            title = el.get_text(" ", strip=True)
            if m and len(title) > 1 and title.lower() not in ("scheda", "scheda film", "trailer", "leggi tutto"):
                if cur and cur["slug"] == m.group(2):
                    continue
                if title.isupper() and len(title) > 3:
                    title = re.sub(r"(?<=\w)'(S)\b", "'s", title.title())
                cur = {"title": title, "year": int(m.group(1)), "slug": m.group(2), "times": []}
                films.append(cur)
                vo = False
        elif isinstance(el, NavigableString) and cur is not None:
            t = str(el)
            low = t.lower()
            if "versione originale" in low or "sottotitol" in low:
                vo = True
            for h, mi in TIME_RE.findall(t):
                cur["times"].append({"t": f"{int(h):02d}:{mi}", "vo": vo})
    out = []
    for f in films:
        seen, uniq = set(), []
        for x in f["times"]:
            if x["t"] not in seen:
                seen.add(x["t"])
                uniq.append(x)
        f["times"] = sorted(uniq, key=lambda x: x["t"])
        if f["times"]:
            out.append(f)
    return out


def run():
    cfg = config()["mymovies"]
    today = dt.date.today().isoformat()
    showings, failed = [], []
    for name, cid in cfg["cinemas"].items():
        try:
            r = get(f"{cfg['base']}/cinema/torino/{cid}/")
            for f in parse_cinema_page(r.text):
                showings.append({**f, "cinema": name, "date": today})
        except Exception as e:
            failed.append(f"{name}: {str(e)[:60]}")
    ok = len(showings) > 0 and len(failed) <= len(cfg["cinemas"]) // 3
    if ok:
        save("mymovies.json", {"date": today, "showings": showings})
    else:
        showings = load("mymovies.json", {"showings": []})["showings"]
    set_health("mymovies_cinema", ok, len(showings), "; ".join(failed)[:300])
