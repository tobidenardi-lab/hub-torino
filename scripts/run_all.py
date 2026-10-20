"""Esegue tutto: python -m scripts.run_all [--digest]"""
import sys
import traceback

from . import letterboxd, massimo, mymovies, events, build, digest
from .common import set_health


def main():
    for name, fn in [("mymovies", mymovies.run), ("massimo", massimo.run),
                     ("letterboxd", letterboxd.run), ("eventi", events.run)]:
        try:
            fn()
        except Exception:
            traceback.print_exc()
            set_health(f"errore:{name}", False, 0, "eccezione non gestita, vedi log")
    hub = build.build()
    try:
        if letterboxd.enrich_reviews(hub):
            hub = build.build()
    except Exception:
        traceback.print_exc()
    if "--digest" in sys.argv:
        digest.send(hub)
    bad = [k for k, v in hub["health"].items() if not v["ok"]]
    print("Fonti con problemi:", bad or "nessuna")


if __name__ == "__main__":
    main()
