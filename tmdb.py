"""Abbina i titoli italiani delle sale ai film Letterboxd tramite TMDB (con cache e correzioni manuali)."""
import json
import os

from .common import ROOT, get, load, save, norm

API = "https://api.themoviedb.org/3"


def _overrides():
    p = ROOT / "overrides.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def lookup(title, year, key=None):
    """-> {id, titles:[...normalizzati]} oppure None. Cache in data/tmdb_cache.json."""
    cache = load("tmdb_cache.json", {})
    ck = f"{norm(title)}|{year or ''}"
    if ck in cache and (cache[ck] or not key):
        return cache[ck]
    ov = _overrides().get("tmdb_by_title", {}).get(norm(title))
    key = key or os.environ.get("TMDB_API_KEY")
    res = None
    if key:
        try:
            tid = ov or None
            if not tid:
                r = get(f"{API}/search/movie?api_key={key}&language=it-IT&query={title}&year={year or ''}", delay=0.3).json()
                if not r.get("results") and year:  # anno a volte diverso di 1
                    r = get(f"{API}/search/movie?api_key={key}&language=it-IT&query={title}", delay=0.3).json()
                    r["results"] = [x for x in r.get("results", [])
                                    if abs(int((x.get("release_date") or "0")[:4] or 0) - year) <= 1]
                tid = r["results"][0]["id"] if r.get("results") else None
            if tid:
                it = get(f"{API}/movie/{tid}?api_key={key}&language=it-IT", delay=0.3).json()
                en = get(f"{API}/movie/{tid}?api_key={key}&language=en-US", delay=0.3).json()
                titles = {norm(x) for x in (it.get("title"), it.get("original_title"), en.get("title"), title) if x}
                res = {"id": tid, "titles": sorted(titles)}
        except Exception:
            res = None
    if res is None and not key:
        res = {"id": ov or None, "titles": [norm(title)]}
    cache[ck] = res
    save("tmdb_cache.json", cache)
    return res
