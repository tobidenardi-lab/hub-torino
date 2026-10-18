"""Email settimanale: film in sala dalla watchlist, consigliati dai seguiti, mostre in scadenza, avvisi fonti."""
import datetime as dt
import html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .common import load


def stars(r):
    if not r:
        return ""
    return "★" * int(r) + ("½" if r % 1 else "")


def compose(hub):
    today = hub["today"]
    h = [f"<h2>{html.escape(hub['title'])} – settimana del {dt.date.fromisoformat(today).strftime('%d/%m')}</h2>"]
    wl = [f for f in hub["films"] if f["watchlist"] and not f["i_seen"]]
    h.append("<h3>Dalla tua watchlist, in sala adesso</h3>")
    h.append("<ul>" + "".join(
        f"<li><b>{html.escape(f['title'])}</b> – {html.escape(', '.join(sorted({s['cinema'] for s in f['showings']})))}</li>"
        for f in wl) + "</ul>" if wl else "<p>Nessuno questa settimana.</p>")
    rec = [f for f in hub["films"] if f["seen_by"] and not f["i_seen"]]
    rec.sort(key=lambda f: -max((s["rating"] or 0) for s in f["seen_by"]))
    h.append("<h3>Visti dai tuoi seguiti</h3><ul>")
    for f in rec[:10]:
        who = ", ".join(f"{s['user']} {stars(s['rating'])}" for s in f["seen_by"][:4])
        h.append(f"<li><b>{html.escape(f['title'])}</b> – {html.escape(who)}</li>")
    h.append("</ul>")
    soon = [e for e in hub["events"] if e.get("end") and today <= e["end"] <= (dt.date.fromisoformat(today) + dt.timedelta(days=14)).isoformat()]
    h.append("<h3>Mostre ed eventi che finiscono presto</h3><ul>" + "".join(
        f"<li>{html.escape(e['title'])} ({html.escape(e.get('venue') or '')}) – fino al {e['end']}</li>"
        for e in sorted(soon, key=lambda e: e["end"])) + "</ul>")
    bad = {k: v for k, v in hub["health"].items() if not v["ok"]}
    if bad:
        h.append("<h3 style='color:#b00'>⚠ Fonti da controllare</h3><ul>" + "".join(
            f"<li>{html.escape(k)}: {html.escape(v['note'] or 'nessun dato')} (ultimo ok: {v['last_ok'] or 'mai'})</li>"
            for k, v in bad.items()) + "</ul>")
    return "".join(h)


def send(hub):
    user, pw, to = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS"), os.environ.get("MAIL_TO")
    if not (user and pw and to):
        print("Email non configurata (SMTP_USER/SMTP_PASS/MAIL_TO): salto.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{hub['title']} – riepilogo settimanale"
    msg["From"], msg["To"] = user, to
    msg.attach(MIMEText(compose(hub), "html", "utf-8"))
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    return True
