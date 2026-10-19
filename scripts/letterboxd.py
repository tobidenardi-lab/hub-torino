"""Letterboxd: RSS dei diari, elenco seguiti, avatar, watchlist.

Poche richieste al giorno: 1 RSS per persona (25 totali), 1 pagina seguiti,
alcune pagine watchlist, avatar scaricati solo se mancanti (refresh settimanale).
"""
import csv
import html
import pathlib
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from .common import DATA, DOCS, get, load, save, set_health, config

NS = {"lb": "https://letterboxd.com", "tmdb": "https://themoviedb.org"}
BASE = "https://letterboxd.com"


def _txt(item, tag):
    el = item.find(tag, NS)
    return el.text.strip() if el is not None and el.text else None


def _review_text(desc_html):
    """Estrae il testo della recensione dalla <description> (scarta locandina e riga 'Watched on')."""
    soup = BeautifulSoup(desc_html or "", "html.parser")
    paras = []
    for p in soup.find_all("p"):
        if p.find("img") and not p.get_text(strip=True):
            continue
        t = p.get_text("\n", strip=True)
        if not t or t.lower().startswith("watched on"):
            continue
        paras.append(t)
    return "\n\n".join(paras)


def parse_rss(xml_text):
    """Restituisce la lista di voci del diario di una persona."""
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        guid = (item.findtext("guid") or "").strip()
        title = _txt(item, "lb:filmTitle")
        if not title:  # liste o altro: ignora
            continue
        rating = _txt(item, "lb:memberRating")
        out.append({
            "guid": guid,
            "title": title,
            "year": int(_txt(item, "lb:filmYear") or 0) or None,
            "rating": float(rating) if rating else None,
            "like": (_txt(item, "lb:memberLike") or "").lower() == "yes",
            "rewatch": (_txt(item, "lb:rewatch") or "").lower() == "yes",
            "watched": _txt(item, "lb:watchedDate"),
            "tmdb": int(_txt(item, "tmdb:movieId")) if _txt(item, "tmdb:movieId") else None,
            "url": (item.findtext("link") or "").strip(),
            "review": _review_text(item.findtext("description")),
        })
    return out


def parse_following(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    people, seen = [], set()
    for a in soup.select("a.name, td.table-person a[href], div.person-summary a[href]"):
        m = re.match(r"^/([A-Za-z0-9_]+)/?$", a.get("href", ""))
        if not m or m.group(1) in seen:
            continue
        user = m.group(1)
        name = a.get_text(strip=True) or user
        row = a.find_parent(["tr", "div", "td"])
        img = row.find("img") if row else None
        avatar = (img.get("src") if img else "") or ""
        if "avatar" not in avatar and img is not None:
            avatar = img.get("data-src", avatar)
        seen.add(user)
        people.append({"user": user, "name": name, "avatar_url": avatar})
    return people


def fetch_following(user):
    people, page = {}, 1
    while page <= 6:
        url = f"{BASE}/{user}/following/" + (f"page/{page}/" if page > 1 else "")
        r = get(url)
        found = parse_following(r.text)
        new = [p for p in found if p["user"] not in people and p["user"] != user]
        if not new:
            break
        for p in new:
            people[p["user"]] = p
        page += 1
    return list(people.values())


def parse_watchlist(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    films = []
    for d in soup.select("[data-film-slug], [data-item-slug]"):
        slug = d.get("data-film-slug") or d.get("data-item-slug")
        name = d.get("data-film-name") or d.get("data-item-name") or ""
        year = d.get("data-film-release-year")
        m = re.match(r"^(.*)\s\((\d{4})\)$", name)
        if m:
            name, year = m.group(1), m.group(2)
        if not name:
            img = d.find("img")
            name = (img.get("alt") if img else "") or slug.replace("-", " ")
        films.append({"slug": slug, "title": name.strip(), "year": int(year) if year else None})
    return films


def fetch_watchlist(user):
    films, page = {}, 1
    while page <= 30:
        url = f"{BASE}/{user}/watchlist/" + (f"page/{page}/" if page > 1 else "")
        try:
            r = get(url)
        except Exception:
            break
        found = parse_watchlist(r.text)
        new = [f for f in found if f["slug"] not in films]
        if not new:
            break
        for f in new:
            films[f["slug"]] = f
        page += 1
    return list(films.values())


def load_export_watched():
    """Facoltativo: data/import/watched.csv dall'esportazione Letterboxd (Name,Year,...)."""
    p = DATA / "import" / "watched.csv"
    out = []
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    out.append({"title": row["Name"], "year": int(row["Year"])})
                except Exception:
                    pass
    return out


def update_diary(user, entries):
    """Accumula le voci nel tempo (l'RSS ne dà solo ~50): chiave = guid."""
    store = load(f"diary_{user}.json", {})
    for e in entries:
        store[e["guid"]] = e
    save(f"diary_{user}.json", store)
    return store


def download_avatars(people):
    av = DOCS / "avatars"
    av.mkdir(exist_ok=True)
    for p in people:
        dest = av / f"{p['user']}.jpg"
        url = p.get("avatar_url") or ""
        p["avatar"] = ""
        if dest.exists() and dest.stat().st_size > 0:
            p["avatar"] = f"avatars/{p['user']}.jpg"
            continue
        if not url or "static/img/avatar" in url:
            continue  # niente foto: la pagina mostra le iniziali
        if url.startswith("//"):
            url = "https:" + url
        try:
            dest.write_bytes(get(url, delay=0.5).content)
            p["avatar"] = f"avatars/{p['user']}.jpg"
        except Exception:
            pass


def run():
    cfg = config()
    me = cfg["letterboxd_user"]
    # 1) seguiti
    try:
        people = fetch_following(me)
        if not people:
            raise RuntimeError("elenco seguiti vuoto")
        old = {p["user"]: p for p in load("friends.json", [])}
        for p in people:
            if p["user"] in old and old[p["user"]].get("avatar"):
                p["avatar"] = old[p["user"]]["avatar"]
        download_avatars(people)
        save("friends.json", people)
        set_health("letterboxd_seguiti", True, len(people))
    except Exception as e:
        people = load("friends.json", [])
        set_health("letterboxd_seguiti", False, len(people), str(e)[:200])
    # 2) diari (io + seguiti)
    ok = fail = 0
    for user in [me] + [p["user"] for p in people]:
        try:
            r = get(f"{BASE}/{user}/rss/", delay=1.0)
            update_diary(user, parse_rss(r.text))
            ok += 1
        except Exception:
            fail += 1
    set_health("letterboxd_diari", ok > 0 and fail <= max(2, len(people) // 4), ok,
               f"{fail} falliti" if fail else "")
    # 3) watchlist
    wl = fetch_watchlist(me)
    if wl:
        save("watchlist.json", wl)
        set_health("letterboxd_watchlist", True, len(wl))
    else:
        set_health("letterboxd_watchlist", False, len(load("watchlist.json", [])), "nessun film letto")
