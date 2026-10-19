"""Mostre / eventi / conferenze: pagine web -> testo -> estrazione strutturata.

Estrazione con GitHub Models (gratuito nelle Actions, con limiti) perché ogni sito ha
un formato diverso e cambia nel tempo. Se il token manca, la fonte è segnalata come non aggiornata.
"""
import datetime as dt
import json
import os
import re

import requests
from bs4 import BeautifulSoup

from .common import UA, get, load, save, set_health, config, norm

PROMPT = """Sei un estrattore di dati. Dal testo di una pagina web sulla cultura a Torino estrai mostre, eventi,
conferenze, festival e rassegne. Oggi è {today}. Rispondi SOLO con JSON: {{"items":[{{"title":str,"venue":str,
"start":"YYYY-MM-DD o null","end":"YYYY-MM-DD o null","kind":"mostra|evento|conferenza|festival|rassegna",
"tag":"cinema|fotografia|arte|altro","desc":str (max 160 caratteri),"url":str o null}}]}}.
Usa tag "fotografia" per mostre di fotografia, "cinema" per tutto ciò che riguarda cinema/audiovisivo.
Escludi eventi già finiti. Non inventare date: se non sono nel testo usa null."""


def page_text(html_text, limit=30000):
    soup = BeautifulSoup(html_text, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        t.decompose()
    links = {}
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        if len(txt) > 8:
            links[txt] = a["href"]
            a.append(f" [{a['href']}]")
    text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
    return text[:limit]


def _chunks(text, size=15000):
    for i in range(0, len(text), size):
        yield text[i:i + size]


def _parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise ValueError("risposta non JSON: " + text[:120].replace("\n", " "))


def llm_extract(text, cfg, token):
    items = []
    for chunk in _chunks(text):
        body = {
            "model": cfg["llm"]["model"],
            "messages": [{"role": "system", "content": PROMPT.format(today=dt.date.today().isoformat())},
                         {"role": "user", "content": chunk}],
            "temperature": 0,
        }
        r = requests.post(cfg["llm"]["endpoint"], json=body, timeout=120,
                          headers={"Authorization": f"Bearer {token}", "User-Agent": UA,
                                   "Accept": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
        if r.status_code != 200:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:150]}")
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError("LLM risposta anomala: " + r.text[:150].replace("\n", " "))
        data = _parse_json(content)
        items += data.get("items", []) if isinstance(data, dict) else []
    return items


def _valid(i, today):
    if not isinstance(i, dict) or not i.get("title"):
        return False
    end = i.get("end")
    return not (end and re.match(r"\d{4}-\d{2}-\d{2}$", end) and end < today)


def run():
    cfg = config()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("MODELS_TOKEN")
    today = dt.date.today()
    urls = []
    for src in cfg["event_pages"]:
        if "{yyyy}" in src["url"]:
            for k in range(src.get("months_ahead", 0) + 1):
                m = today.month - 1 + k
                urls.append((src["name"], src["url"].format(yyyy=today.year + m // 12, mm=f"{m % 12 + 1:02d}")))
        else:
            urls.append((src["name"], src["url"]))
    allitems = {}
    for name, url in urls:
        try:
            if not token:
                raise RuntimeError("token GitHub Models assente")
            html_text = get(url, delay=2).text
            items = llm_extract(page_text(html_text), cfg, token)
            items = [i for i in items if _valid(i, today.isoformat())]
            for i in items:
                i["source"] = name
                if i.get("url") and i["url"].startswith("/"):
                    i["url"] = "/".join(url.split("/")[:3]) + i["url"]
                allitems[(norm(i["title"]), i.get("start"))] = i
            set_health(f"eventi: {name}", bool(items), len(items), "" if items else "nessun risultato")
        except Exception as e:
            set_health(f"eventi: {name}", False, 0, str(e)[:200])
    old = load("events.json", [])
    if allitems:
        # conserva voci vecchie di fonti fallite finché non scadono
        failed = {k for k, v in load("health.json", {}).items() if k.startswith("eventi:") and not v["ok"]}
        keep = [o for o in old if f"eventi: {o.get('source')}" in failed and _valid(o, today.isoformat())]
        merged = list(allitems.values()) + keep
        save("events.json", merged)
