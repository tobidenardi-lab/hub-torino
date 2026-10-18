"""Collaudo su dati di prova (struttura osservata dei siti). Esegui: python -m tests.test_all"""
import datetime as dt
import json

from scripts import common, massimo, mymovies, letterboxd, build, digest

TODAY = dt.date(2026, 10, 14)

MASSIMO = """<div><h2>Sala Uno</h2>
<p><strong>Martedì 13 ottobre</strong></p>
<p><strong>16.00/18.00/20.30 Balcanica</strong> di N. Sorcinelli (I/Serbia/Croazia 2026, 86’)</p>
<p><em>Il film è introdotto da Ugo Rossi</em></p>
<p>Ingresso euro 4,00</p>
<h2>Sala Due</h2>
<p><strong>Mercoledì 14 ottobre</strong></p>
<p>21.00 Il diavolo di Tasmania di E. Flynn (USA 1946, 90’)</p>
<p>20.30 – Sala 1 – Il dottor Stranamore di S. Kubrick (UK 1964, 95’)</p>
<p>DA MERCOLEDÌ 21 A DOMENICA 25 OTTOBRE ToHorror Fantastic Film Festival</p></div>"""

MYMOVIES = """<html><body><nav><a href="/film/2000/x/">menu</a> 10:00</nav>
<div class="film"><a href="/film/2026/palestine-36/">Palestina 36 - Quando tutto ebbe inizio</a>
<p>OGGI AL CINEMA</p><a href="/cinema/torino/5132/">CINEMA Centrale</a><p>16:00 18:30</p>
<p>Versione originale con sottotitoli:</p><p>21:00</p></div>
<div class="film"><a href="/film/2026/la-citta-dei-vivi/">La città dei vivi</a><p>20:15</p></div>
<div class="film"><a href="/film/2025/senza-orari/">Senza orari</a></div></body></html>"""


def item(guid, title, year, rating, tmdb, desc, like="No"):
    return f"""<item><title>{title}, {year}</title><link>https://letterboxd.com/u/film/x/</link><guid>{guid}</guid>
<letterboxd:watchedDate>2026-10-10</letterboxd:watchedDate><letterboxd:rewatch>No</letterboxd:rewatch>
<letterboxd:filmTitle>{title}</letterboxd:filmTitle><letterboxd:filmYear>{year}</letterboxd:filmYear>
<letterboxd:memberRating>{rating}</letterboxd:memberRating><letterboxd:memberLike>{like}</letterboxd:memberLike>
<tmdb:movieId>{tmdb}</tmdb:movieId><description><![CDATA[{desc}]]></description></item>"""


RSS = ('<?xml version="1.0"?><rss version="2.0" xmlns:letterboxd="https://letterboxd.com" xmlns:tmdb="https://themoviedb.org"><channel>'
       + item("letterboxd-review-1", "Palestine 36", 2025, "4.5", 111, '<p><img src="x"/></p><p>Bellissimo, potente.</p><p>Da vedere.</p>', "Yes")
       + item("letterboxd-watch-2", "Balcanica", 2026, "3.0", 222, "<p>Watched on Saturday October 10, 2026.</p>")
       + "</channel></rss>")

FOLLOWING = """<table><tr><td class="table-person"><a class="avatar" href="/marco/"><img src="https://a.ltrbxd.com/resized/avatar/marco.jpg"></a>
<a class="name" href="/marco/">Marco R</a></td></tr>
<tr><td class="table-person"><a class="name" href="/lucia/">Lucia</a><img src="https://s.ltrbxd.com/static/img/avatar80-1.png"></td></tr></table>"""

WATCHLIST = """<ul><li><div class="film-poster" data-film-slug="la-citta-dei-vivi" data-film-name="The City of the Living" data-film-release-year="2026"></div></li>
<li><div data-item-slug="balcanica" data-item-name="Balcanica (2026)"></div></li></ul>"""


def check(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    assert cond, msg


def main():
    shows, fests = massimo.parse_calendar(MASSIMO, TODAY)
    check(len(shows) == 3, f"Massimo: 3 proiezioni ({len(shows)})")
    check(shows[0]["title"] == "Balcanica" and shows[0]["times"] == ["16:00", "18:00", "20:30"], "Massimo: titolo e orari")
    check(shows[0]["director"] == "N. Sorcinelli" and shows[0]["year"] == 2026, "Massimo: regia e anno")
    check("introdotto da Ugo Rossi" in shows[0]["note"] and "4,00" in shows[0]["note"], "Massimo: ospiti e prezzo")
    check(shows[1]["title"] == "Il diavolo di Tasmania", "Massimo: ' di ' nel titolo")
    check(shows[2]["room"] == "Sala 1", "Massimo: sala indicata nella riga")
    check(fests and fests[0]["start"] == "2026-10-21" and fests[0]["end"] == "2026-10-25", "Massimo: festival multi-giorno")

    films = mymovies.parse_cinema_page(MYMOVIES)
    check(len(films) == 2, f"MYmovies: 2 film con orari, menu e film senza orari ignorati ({len(films)})")
    check([x["t"] for x in films[0]["times"]] == ["16:00", "18:30", "21:00"], "MYmovies: orari")
    check([x["vo"] for x in films[0]["times"]] == [False, False, True], "MYmovies: versione originale")

    e = letterboxd.parse_rss(RSS)
    check(len(e) == 2 and e[0]["tmdb"] == 111 and e[0]["rating"] == 4.5 and e[0]["like"], "RSS: voci, rating, tmdb, like")
    check(e[0]["review"] == "Bellissimo, potente.\n\nDa vedere." and e[1]["review"] == "", "RSS: recensione estratta, 'Watched on' scartato")
    fol = letterboxd.parse_following(FOLLOWING)
    check([p["user"] for p in fol] == ["marco", "lucia"] and "marco.jpg" in fol[0]["avatar_url"], "Seguiti + avatar")
    wl = letterboxd.parse_watchlist(WATCHLIST)
    check(len(wl) == 2 and wl[0]["year"] == 2026 and wl[1]["title"] == "Balcanica", "Watchlist: due formati attributi")

    # integrazione: dati in una cartella temporanea
    import tempfile, pathlib
    common.DATA = pathlib.Path(tempfile.mkdtemp())
    common.DOCS = pathlib.Path(tempfile.mkdtemp())
    for m in (build, letterboxd):
        m.DATA = common.DATA
        m.DOCS = common.DOCS
    import scripts.tmdb as tm
    for mod in (build, tm):
        mod.load, mod.save = common.load, common.save
    common.save("massimo.json", {"shows": shows, "festivals": fests})
    common.save("mymovies.json", {"showings": [{**f, "cinema": "Centrale", "date": "2026-10-14"} for f in films]
                                  + [{"title": "Balcanica", "year": 2026, "slug": "balcanica", "times": [{"t": "20:30", "vo": False}],
                                      "cinema": "Massimo (MNC)", "date": "2026-10-14"}]})
    common.save("friends.json", [{"user": "marco", "name": "Marco R", "avatar": ""}, {"user": "lucia", "name": "Lucia", "avatar": ""}])
    common.save("diary_marco.json", {x["guid"]: x for x in e})
    common.save("diary_lucia.json", {})
    common.save("diary_tobi_2117.json", {x["guid"]: x for x in e[1:]})
    common.save("watchlist.json", wl)
    common.save("health.json", {"x": {"ok": False, "note": "prova", "last_ok": "2026-10-01", "count": 0}})
    import os
    os.environ.pop("TMDB_API_KEY", None)
    hub = build.build(TODAY)
    by = {f["title"]: f for f in hub["films"]}
    b = by["Balcanica"]
    check(sum(1 for s in b["showings"] if s["cinema"].startswith("Massimo")) == 1, "Dedup Massimo: vale il calendario ufficiale")
    check(b["watchlist"] and b["i_seen"] and b["seen_by"][0]["user"] == "marco", "Balcanica: watchlist, visto da me, visto da Marco")
    # Titolo italiano senza TMDB key: riconoscibile solo via override/tmdb id => senza chiave non c'è match
    p36 = by["Palestina 36 - Quando tutto ebbe inizio"]
    print("INFO senza chiave TMDB 'Palestina 36' seen_by =", len(p36["seen_by"]), "(atteso 0: serve la chiave TMDB)")
    check(len(hub["events"]) == 1, "Eventi: festival Massimo incluso")
    html = digest.compose(hub)
    check("Fonti da controllare" in html and "watchlist" in html, "Email: avvisi e watchlist")
    json.loads(common.DOCS.joinpath("data.js").read_text()[len("window.HUB = "):-1])
    check(True, "data.js valido")
    print("\nTutti i test passati.")


if __name__ == "__main__":
    main()
