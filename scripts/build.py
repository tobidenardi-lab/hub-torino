"""Unisce programmazione, Letterboxd ed eventi in docs/data.js (letto da docs/index.html)."""
import datetime as dt
import json
import re

from .common import DOCS, load, save, norm, config, ROOT
from . import tmdb
from .letterboxd import load_export_watched


def _year_ok(a, b):
    return not a or not b or abs(a - b) <= 1


def _match_entry(entry, res, title_norm, year):
    if res and res.get("id") and entry.get("tmdb") == res["id"]:
        return True
    names = set(res["titles"]) if res else {title_norm}
    return norm(entry["title"]) in names and _year_ok(entry.get("year"), year)


def build(today=None):
    cfg = config()
    me = cfg["letterboxd_user"]
    today = today or dt.date.today()
    films = {}

    def add(title, year, slug, cinema, date, times, note="", director="", room=None):
        k = norm(title)
        f = films.setdefault(k, {"title": title, "year": year, "slug": slug, "director": director,
                                 "showings": [], "notes": []})
        f["year"] = f["year"] or year
        f["slug"] = f["slug"] or slug
        f["director"] = f["director"] or director
        f["showings"].append({"cinema": cinema, "date": date, "times": times, "room": room})
        if note and note not in f["notes"]:
            f["notes"].append(note)

    mass = load("massimo.json", {"shows": [], "festivals": []})
    for s in mass["shows"]:
        add(s["title"], s["year"], None, "Massimo (MNC)", s["date"],
            [{"t": t, "vo": False} for t in s["times"]], s["note"], s["director"], s["room"])
    for s in load("mymovies.json", {"showings": []})["showings"]:
        if mass["shows"] and s["cinema"].startswith("Massimo"):
            continue  # per il Massimo vale il calendario ufficiale
        add(s["title"], s["year"], s["slug"], s["cinema"], s["date"], s["times"])

    friends = load("friends.json", [])
    diaries = {p["user"]: load(f"diary_{p['user']}.json", {}) for p in friends}
    mine = list(load(f"diary_{me}.json", {}).values()) + load_export_watched()
    watchlist = load("watchlist.json", [])
    revs = load("reviews.json", {})
    key = None
    out_films = []
    for k, f in sorted(films.items()):
        res = tmdb.lookup(f["title"], f["year"], key)
        f["tmdb"] = res["id"] if res else None
        seen_by = []
        for p in friends:
            cands = [e for e in diaries[p["user"]].values() if _match_entry(e, res, k, f["year"])]
            if cands:
                e = max(cands, key=lambda e: (bool(e["review"]), e["watched"] or ""))
                slug = e.get("slug") or (re.search(r"/film/([^/]+)/", e["url"] or "") or [None, None])[1]
                review = e["review"] or revs.get(f"{p['user']}/{slug}", {}).get("text", "")
                seen_by.append({"user": p["user"], "rating": e["rating"], "review": review, "slug": slug,
                                "like": e["like"], "url": e["url"], "watched": e["watched"]})
        f["seen_by"] = sorted(seen_by, key=lambda x: -(x["rating"] or 0))
        f["watchlist"] = any(_match_entry({"title": w["title"], "year": w["year"], "tmdb": None}, res, k, f["year"])
                             for w in watchlist)
        f["i_seen"] = any(_match_entry(e, res, k, f["year"]) for e in mine)
        f["lb_url"] = f"https://letterboxd.com/tmdb/{f['tmdb']}/" if f["tmdb"] else None
        merged = {}
        for s in f["showings"]:  # unisce righe doppie (stesso cinema, giorno, sala) e toglie orari ripetuti
            m = merged.setdefault((s["date"], s["cinema"], s.get("room")), {**s, "times": []})
            have = {t["t"] for t in m["times"]}
            m["times"] += [t for t in s["times"] if t["t"] not in have and not have.add(t["t"])]
        f["showings"] = sorted(merged.values(), key=lambda s: (s["date"], s["cinema"], s.get("room") or ""))
        for s in f["showings"]:
            s["times"].sort(key=lambda t: t["t"])
        out_films.append(f)

    events = load("events.json", [])
    for fest in mass.get("festivals", []):
        events.append({"title": fest["title"], "venue": "Cinema Massimo", "start": fest["start"], "end": fest["end"],
                       "kind": "festival", "tag": "cinema", "desc": "", "url": "https://www.cinemamassimotorino.it/",
                       "source": "Cinema Massimo"})
    hub = {
        "generated": dt.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"),
        "today": today.isoformat(),
        "title": cfg["site_title"],
        "me": me,
        "friends": friends,
        "films": out_films,
        "events": events,
        "health": load("health.json", {}),
    }
    save("hub.json", hub)
    (DOCS / "data.js").write_text("window.HUB = " + json.dumps(hub, ensure_ascii=False) + ";", encoding="utf-8")
    return hub
