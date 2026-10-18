"""Utilità condivise: HTTP gentile, JSON, normalizzazione titoli."""
import json
import pathlib
import re
import time
import unicodedata

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
DATA.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)

# User-Agent che identifica il progetto (nessun dato personale).
UA = "hub-torino/1.0 (calendario culturale personale; poche richieste al giorno)"
_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "it,en;q=0.8"})
_last = {"t": 0.0}


def get(url, delay=1.5, timeout=30, **kw):
    """GET con pausa tra le richieste e 2 tentativi. Solleva eccezione se fallisce."""
    err = None
    for attempt in range(2):
        wait = delay - (time.time() - _last["t"])
        if wait > 0:
            time.sleep(wait)
        _last["t"] = time.time()
        try:
            r = _session.get(url, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            err = RuntimeError(f"HTTP {r.status_code} su {url}")
        except requests.RequestException as e:
            err = e
        time.sleep(3)
    raise err


def load(name, default=None):
    p = DATA / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def norm(s):
    """Titolo normalizzato per confronti: minuscolo, senza accenti/punteggiatura/articoli iniziali."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"^(the|a|an|il|lo|la|le|i|gli|l|un|una) ", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def set_health(source, ok, count, note=""):
    h = load("health.json", {})
    prev = h.get(source, {})
    h[source] = {
        "ok": bool(ok),
        "count": count,
        "note": note,
        "checked": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "last_ok": time.strftime("%Y-%m-%d", time.gmtime()) if ok else prev.get("last_ok", ""),
    }
    save("health.json", h)
