#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/html_email.py - Génération HTML (pixel-perfect V1) + envoi Gmail
Architecture :
  - render_email_html()  → email minimal (stats + CTA) → corps MIME
  - render_page_html()   → page riche (filtres + contacts RH + GA) → docs/v2/index.html
  - run_html_email()     → orchestre le tout + git push + envoi Gmail
"""

import json
import os
import re
import smtplib
import subprocess
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ===== CHEMINS =====
BASE_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR      = BASE_DIR / "data"
DOCS_DIR      = BASE_DIR / "docs" / "v2"
ARCHIVES_DIR  = DOCS_DIR / "archives"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

OFFRES_MERGED    = DATA_DIR / "offres_merged.json"
HR_CONTACTS_FILE = DATA_DIR / "hr_contacts.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

# ===== PARAMETRES =====
GMAIL_USER        = os.getenv("GMAIL_USER")
GMAIL_PASSWORD    = os.getenv("GMAIL_PASSWORD")
RECIPIENT_EMAIL   = os.getenv("RECIPIENT_EMAIL", GMAIL_USER)
GITHUB_PAGES_URL  = "https://fhonore5312.github.io/alternances-veille/v2/"
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "")
RETENTION_DAYS    = 30

# ===== CSS V1 pixel-perfect =====
_CSS = """
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           margin: 0; padding: 20px; background: #f8f9fa; color: #2c3e50; line-height: 1.6; }
    .container { max-width: 940px; margin: 0 auto; }

    .header { background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
               color: white; padding: 28px 30px; border-radius: 12px;
               margin-bottom: 18px; text-align: center; }
    .header h1 { margin: 0 0 6px; font-size: 24px; }
    .header p  { margin: 3px 0; opacity: .9; font-size: 13px; }

    .stats-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
    .stat { background: white; border-radius: 8px; padding: 10px 14px;
             box-shadow: 0 2px 6px rgba(0,0,0,.07); text-align: center; flex: 1; min-width: 70px; }
    .stat strong { display: block; font-size: 20px; color: #2c3e50; }
    .stat span   { font-size: 11px; color: #7f8c8d; }

    .filter-section { background: white; border-radius: 8px; padding: 12px 14px;
                       box-shadow: 0 2px 6px rgba(0,0,0,.07); margin-bottom: 10px; }
    .filter-section label { font-size: 11px; color: #999; display: block; margin-bottom: 6px; }
    .filter-bar { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
    .filter-chip { padding: 5px 13px; border-radius: 14px; border: 1.5px solid #ddd;
                    background: #fff; font-size: 12px; cursor: pointer;
                    transition: all .15s ease; user-select: none; }
    .filter-chip:hover { border-color: #3498db; color: #3498db; }
    .filter-chip.active { color: white; border-color: transparent; }

    .track-section { margin-bottom: 26px; background: white; border-radius: 10px;
                      box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }
    .track-header { padding: 13px 20px; color: white; font-size: 16px; font-weight: bold; }
    .track-body   { padding: 0 20px 14px; }

    .city-group  { margin-bottom: 6px; }
    .city-header { font-size: 13px; font-weight: bold; color: #555;
                    padding: 14px 0 7px; border-bottom: 2px solid #eee; margin-bottom: 8px; }

    .offer { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
    .offer:last-child { border-bottom: none; }
    .offer h3 { margin: 0 0 4px; font-size: 14px; color: #2c3e50; }
    .description { font-size: 13px; color: #555; margin: 4px 0 6px; }
    .skills { margin-bottom: 6px; }
    .skill-tag { display: inline-block; background: #eef2ff; color: #3498db;
                  font-size: 11px; padding: 2px 8px; border-radius: 10px; margin: 2px 3px 2px 0; }
    .meta { font-size: 11px; color: #95a5a6; margin-bottom: 7px; }

    .badge-new { background: #27ae60; color: white; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 6px;
                  font-weight: normal; vertical-align: middle; }
    .badge-incertain { background: #f39c12; color: white; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 6px;
                  font-weight: normal; vertical-align: middle; }
    .badge-lba { background: #e8f8f0; color: #1a7a4a; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 5px;
                  font-weight: bold; vertical-align: middle; }
    .badge-llm { background: #ede9fe; color: #6d28d9; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 5px;
                  font-weight: bold; vertical-align: middle; }

    .hr-contact { font-size: 12px; color: #555; margin: 6px 0 8px;
                   padding: 6px 10px; background: #f9fafb;
                   border-left: 3px solid #3498db; border-radius: 0 6px 6px 0; }
    .hr-conf { color: #888; font-size: 11px; margin-right: 6px; }
    .hr-contact a { color: #3498db; text-decoration: none; }
    .hr-contact a:hover { text-decoration: underline; }

    .btn-apply { display: inline-block; padding: 5px 14px; color: white;
                  text-decoration: none; border-radius: 5px; font-size: 12px;
                  font-weight: bold; margin-top: 4px; }
    .btn-apply:hover { opacity: .88; }

    .footer { text-align: center; padding: 18px; background: white; border-radius: 10px;
               margin-top: 18px; font-size: 12px; color: #7f8c8d;
               box-shadow: 0 2px 6px rgba(0,0,0,.06); }
    .footer a { color: #3498db; text-decoration: none; }

    @media (max-width: 600px) {
        body { padding: 10px; }
        .header { padding: 18px 16px; }
        .header h1 { font-size: 18px; }
        .stats-bar { gap: 6px; }
    }
"""

_TRACK_LABELS = {
    "digital_marketing": "📱 Digital Marketing",
    "finance":           "💰 Finance, Audit & Contrôle",
    "supply_chain":      "📦 Supply Chain & Achats",
    "business_dev":      "🤝 Business Development & Vente",
}
_TRACK_ORDER = ["digital_marketing", "finance", "supply_chain", "business_dev"]
_CITY_ORDER  = ["Rennes", "Nantes", "Paris"]


# ===== CHARGEMENT =====

def load_offers() -> dict:
    with open(OFFRES_MERGED, encoding="utf-8") as f:
        return json.load(f)


def load_hr_contacts() -> dict:
    if not HR_CONTACTS_FILE.exists():
        return {}
    try:
        with open(HR_CONTACTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {c["offer_id"]: c for c in data.get("contacts", [])}
    except Exception:
        return {}


def load_tracks_config() -> dict:
    try:
        import yaml
        cfg_path = BASE_DIR / "config" / "tracks.yml"
        if not cfg_path.exists():
            return {}
        with open(cfg_path, encoding="utf-8") as f:
            tracks = yaml.safe_load(f)
        return tracks.get("tracks", tracks)
    except Exception:
        return {}


def load_track_colors() -> dict:
    tc = load_tracks_config()
    return {k: v.get("color_hex", "#34495e") for k, v in tc.items()} if tc else {}


# ===== UTILITAIRES =====

def _e(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_date_offre(offer: dict) -> datetime:
    for field, fmt in [("date_creation", "%d/%m/%Y"), ("first_seen", "%Y-%m-%d")]:
        val = offer.get(field)
        if val:
            try:
                return datetime.strptime(val, fmt)
            except Exception:
                pass
    return datetime.min


def _format_now_long() -> str:
    now = datetime.now()
    days   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    return f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year} - {now.strftime('%H:%M')}"


def cleanup_archives():
    now = datetime.now()
    for archive in ARCHIVES_DIR.glob("*.html"):
        try:
            if (now - datetime.fromtimestamp(archive.stat().st_mtime)).days > RETENTION_DAYS:
                archive.unlink()
        except Exception:
            pass


def git_push_html() -> bool:
    try:
        # Vérifier uniquement docs/v2/ (jamais docs/index.html)
        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/v2/"],
            capture_output=True, text=True, cwd=BASE_DIR,
        )
        if not result.stdout.strip():
            print("  info GitHub Pages : rien a commiter")
            return True

        subprocess.run(["git", "add", "docs/v2/"], check=True, cwd=BASE_DIR)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore: veille {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True, cwd=BASE_DIR,
        )
        # Push docs/v2/ directement sur main (GitHub Pages)
        subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            check=True, cwd=BASE_DIR,
        )
        print("  OK GitHub Pages mis a jour (-> main)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERREUR Git push echoue : {e}")
        return False


# ===== RENDER EMAIL MINIMAL (compatible Gmail) =====

def render_email_html(meta: dict, stats_by_city: dict, stats_by_track: dict,
                      tracks_cfg: dict, push_ok: bool) -> str:
    total     = meta.get("total_offres", 0)
    nouvelles = meta.get("nouvelles", 0)
    lba       = meta.get("source_lba", 0)
    llm       = meta.get("source_llm", 0)
    now_str   = datetime.now().strftime("%d/%m/%Y a %H:%M")
    status_line = ("OK Page en ligne mise a jour" if push_ok
                   else "WARN Page non mise a jour (git push echoue)")

    track_rows = ""
    for tk, stats in stats_by_track.items():
        cfg   = tracks_cfg.get(tk, {})
        label = cfg.get("label", _TRACK_LABELS.get(tk, tk))
        color = cfg.get("color_hex", "#34495e")
        t     = stats.get("total", 0)
        n     = stats.get("nouvelles", 0)
        new_badge = (
            f'<span style="background:#27ae60;color:white;padding:1px 6px;'
            f'border-radius:10px;font-size:10px;margin-left:6px;">{n} new</span>'
            if n > 0 else ""
        )
        track_rows += (
            f'<tr>'
            f'<td style="padding:7px 14px;border-bottom:1px solid #f0f0f0;">'
            f'<span style="color:{color};font-weight:600;">{_e(label)}</span>{new_badge}</td>'
            f'<td style="padding:7px 14px;border-bottom:1px solid #f0f0f0;'
            f'text-align:center;font-weight:600;">{t}</td>'
            f'<td style="padding:7px 14px;border-bottom:1px solid #f0f0f0;'
            f'text-align:center;color:#27ae60;font-weight:600;">{n}</td>'
            f'</tr>'
        )

    city_stats = "".join(
        f'<div style="background:white;border-radius:8px;padding:10px 14px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);text-align:center;flex:1;min-width:70px;">'
        f'<strong style="display:block;font-size:18px;color:#2c3e50;">{n}</strong>'
        f'<span style="font-size:11px;color:#7f8c8d;">{_e(v)}</span></div>'
        for v, n in stats_by_city.items()
    )

    return (
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Veille Alternances</title></head>'
        f'<body style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        f'background:#f8f9fa;color:#2c3e50;padding:20px;margin:0;">'
        f'<div style="max-width:600px;margin:0 auto;">'
        f'<div style="background:linear-gradient(135deg,#2c3e50 0%,#3498db 100%);color:white;'
        f'padding:28px 30px;border-radius:12px;margin-bottom:18px;text-align:center;">'
        f'<h1 style="margin:0 0 6px;font-size:22px;">&#129302; Veille Automatique des Alternances</h1>'
        f'<p style="margin:3px 0;opacity:.9;font-size:13px;">Bachelor 3 RSB &middot; Debut : Septembre 2026 &middot; Duree : 12-24 mois</p>'
        f'<p style="margin:3px 0;opacity:.9;font-size:13px;">&#128197; {now_str}</p></div>'
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">'
        f'<div style="background:white;border-radius:8px;padding:10px 14px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);text-align:center;flex:1;min-width:70px;">'
        f'<strong style="display:block;font-size:20px;color:#2c3e50;">{total}</strong>'
        f'<span style="font-size:11px;color:#7f8c8d;">offres actives</span></div>'
        f'<div style="background:white;border-radius:8px;padding:10px 14px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);text-align:center;flex:1;min-width:70px;">'
        f'<strong style="display:block;font-size:20px;color:#27ae60;">{nouvelles}</strong>'
        f'<span style="font-size:11px;color:#7f8c8d;">nouvelles</span></div>'
        f'<div style="background:white;border-radius:8px;padding:10px 14px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);text-align:center;flex:1;min-width:70px;">'
        f'<strong style="display:block;font-size:20px;color:#1a7a4a;">{lba}</strong>'
        f'<span style="font-size:11px;color:#7f8c8d;">LBA</span></div>'
        f'<div style="background:white;border-radius:8px;padding:10px 14px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);text-align:center;flex:1;min-width:70px;">'
        f'<strong style="display:block;font-size:20px;color:#6d28d9;">{llm}</strong>'
        f'<span style="font-size:11px;color:#7f8c8d;">LLM</span></div>'
        f'{city_stats}</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:white;border-radius:8px;margin-bottom:18px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,.07);">'
        f'<tr style="background:#f8f9fa;">'
        f'<th style="padding:8px 14px;text-align:left;font-size:11px;color:#999;border-bottom:2px solid #eee;">TRACK</th>'
        f'<th style="padding:8px 14px;text-align:center;font-size:11px;color:#999;border-bottom:2px solid #eee;">TOTAL</th>'
        f'<th style="padding:8px 14px;text-align:center;font-size:11px;color:#999;border-bottom:2px solid #eee;">NOUVELLES</th>'
        f'</tr>{track_rows}</table>'
        f'<div style="text-align:center;margin-bottom:18px;">'
        f'<a href="{GITHUB_PAGES_URL}" style="display:inline-block;background:#2c3e50;color:white;'
        f'padding:10px 28px;border-radius:6px;font-weight:bold;font-size:14px;text-decoration:none;">'
        f'&#128203; Voir toutes les offres &#8594;</a>'
        f'<p style="margin-top:8px;font-size:12px;color:#7f8c8d;">{status_line}</p></div>'
        f'<div style="text-align:center;font-size:11px;color:#95a5a6;">'
        f'Automatisation &middot; {GMAIL_USER or "veille-alternances"}<br>'
        f'<a href="{GITHUB_PAGES_URL}" style="color:#3498db;">{GITHUB_PAGES_URL}</a>'
        f'</div></div></body></html>'
    )


# ===== RENDER PAGE RICHE (pixel-perfect V1) =====

def render_page_html(offers: list, meta: dict, track_colors: dict,
                     tracks_cfg: dict, hr_contacts: dict) -> str:
    now_str   = _format_now_long()
    total     = meta.get("total_offres", len(offers))
    nouvelles = meta.get("nouvelles", 0)
    lba       = meta.get("source_lba", 0)
    llm       = meta.get("source_llm", 0)

    stats_by_city: dict = meta.get("stats_by_city", {})
    if not stats_by_city:
        for o in offers:
            v = o.get("ville_recherche") or o.get("ville", "?")
            stats_by_city[v] = stats_by_city.get(v, 0) + 1

    tracks_map: dict = {}
    for o in offers:
        t = o.get("track", "digital_marketing")
        tracks_map.setdefault(t, []).append(o)

    sorted_tracks = sorted(
        tracks_map.keys(),
        key=lambda t: _TRACK_ORDER.index(t) if t in _TRACK_ORDER else 99,
    )

    ga_snippet = ""
    if GA_MEASUREMENT_ID:
        ga_snippet = (
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>\n'
            f'<script>window.dataLayer=window.dataLayer||[];'
            f'function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());'
            f'gtag("config","{GA_MEASUREMENT_ID}");</script>'
        )

    # Stats bar villes
    city_stats_html = ""
    for v in _CITY_ORDER:
        if v in stats_by_city:
            city_stats_html += (
                f'<div class="stat"><strong>{stats_by_city[v]}</strong>'
                f'<span>{_e(v)}</span></div>'
            )
    for v, n in stats_by_city.items():
        if v not in _CITY_ORDER:
            city_stats_html += (
                f'<div class="stat"><strong>{n}</strong><span>{_e(v)}</span></div>'
            )

    # Filtre track
    track_chips = (
        '<span class="filter-chip active" onclick="filterTrack(\'all\',this)"'
        ' style="background:#2c3e50;">Tous</span>'
    )
    for t in sorted_tracks:
        color = track_colors.get(t, "#34495e")
        label = _TRACK_LABELS.get(t, t)
        track_chips += (
            f'<span class="filter-chip" onclick="filterTrack(\'{t}\',this)"'
            f' data-color="{color}">{label}</span>'
        )

    # Filtre ville
    city_chips = (
        '<span class="filter-chip active" onclick="filterCity(\'all\',this)"'
        ' style="background:#2c3e50;">Toutes</span>'
    )
    for v in _CITY_ORDER:
        if v in stats_by_city:
            city_chips += (
                f'<span class="filter-chip" onclick="filterCity(\'{_e(v)}\',this)">'
                f'&#128205; {_e(v)}</span>'
            )

    # Sections par track
    sections_html = ""
    for track in sorted_tracks:
        t_offers = tracks_map[track]
        color    = track_colors.get(track, "#34495e")
        label    = _TRACK_LABELS.get(track, track.replace("_", " ").title())
        t_new    = sum(1 for o in t_offers if o.get("status") == "new")
        new_badge = f'<span class="badge-new">{t_new} new</span>' if t_new else ""

        city_map: dict = {}
        for o in t_offers:
            v = o.get("ville_recherche") or o.get("ville", "Autre")
            city_map.setdefault(v, []).append(o)

        sorted_cities = sorted(
            city_map.keys(),
            key=lambda v: _CITY_ORDER.index(v) if v in _CITY_ORDER else 99,
        )

        city_groups_html = ""
        for city in sorted_cities:
            city_offers = sorted(city_map[city], key=parse_date_offre, reverse=True)
            offers_html = ""
            for o in city_offers:
                is_new    = o.get("status") == "new"
                is_incert = o.get("status") == "incertain"
                src       = o.get("source", "LBA")

                status_badge = ""
                if is_new:
                    status_badge = '<span class="badge-new">NEW</span>'
                elif is_incert:
                    status_badge = '<span class="badge-incertain">&#9888;&#65039;</span>'

                src_badge = (
                    '<span class="badge-llm">LLM</span>'
                    if src == "LLM" else
                    '<span class="badge-lba">LBA</span>'
                )

                meta_parts = []
                if o.get("entreprise"):
                    meta_parts.append(f'&#127970; {_e(o["entreprise"])}')
                if o.get("date_debut"):
                    meta_parts.append(f'&#128197; Debut : {_e(o["date_debut"])}')
                if o.get("type_contrat"):
                    dur = f' &middot; {_e(o["duree_contrat"])}' if o.get("duree_contrat") else ""
                    meta_parts.append(f'&#128221; {_e(o["type_contrat"])}{dur}')
                if o.get("date_creation"):
                    meta_parts.append(f'&#128467;&#65039; Publie le {_e(o["date_creation"])}')
                meta_html = (
                    f'<div class="meta">{" &nbsp;&middot;&nbsp; ".join(meta_parts)}</div>'
                    if meta_parts else ""
                )

                desc = _e(o.get("description", ""))
                desc_html = f'<div class="description">{desc}</div>' if desc else ""

                skills_html = ""
                if o.get("competences_detectees"):
                    tags = "".join(
                        f'<span class="skill-tag">{_e(s)}</span>'
                        for s in o["competences_detectees"]
                    )
                    skills_html = f'<div class="skills">{tags}</div>'

                # Contact RH - affiche uniquement si contact trouve
                contact_html = ""
                contact = hr_contacts.get(o.get("id", ""))
                if contact:
                    name      = _e(contact.get("name", ""))
                    role      = _e(contact.get("role", ""))
                    email_val = contact.get("email", "")
                    li        = contact.get("linkedin", "")
                    conf      = contact.get("confidence", "")
                    conf_html = f'<span class="hr-conf">[{_e(conf)}]</span>' if conf else ""
                    email_link = (
                        f' &middot; <a href="mailto:{_e(email_val)}">{_e(email_val)}</a>'
                        if email_val else ""
                    )
                    li_link = (
                        f' &middot; <a href="{_e(li)}" target="_blank" rel="noopener">LinkedIn &#8599;</a>'
                        if li else ""
                    )
                    contact_html = (
                        f'<div class="hr-contact">{conf_html}'
                        f'&#128100; <strong>{name}</strong>'
                        f'{(" &mdash; " + role) if role else ""}'
                        f'{email_link}{li_link}</div>'
                    )

                data_city   = _e(o.get("ville_recherche") or o.get("ville", ""))
                data_status = _e(o.get("status", ""))

                offers_html += (
                    f'<div class="offer" data-track="{track}"'
                    f' data-city="{data_city}" data-status="{data_status}">'
                    f'<h3>{_e(o.get("titre", "Titre inconnu"))}{status_badge}{src_badge}</h3>'
                    f'{meta_html}{desc_html}{skills_html}{contact_html}'
                    f'<a class="btn-apply" href="{_e(o.get("url_candidature", "#"))}"'
                    f' style="background:{color};" target="_blank" rel="noopener noreferrer">'
                    f'Postuler &#8594;</a></div>'
                )

            city_groups_html += (
                f'<div class="city-group">'
                f'<div class="city-header">&#128205; {_e(city)}</div>'
                f'{offers_html}</div>'
            )

        sections_html += (
            f'<div class="track-section" data-track="{track}">'
            f'<div class="track-header" style="background:{color};">'
            f'{label} {new_badge}</div>'
            f'<div class="track-body">{city_groups_html}</div></div>'
        )

    js = """
    function filterTrack(track, btn) {
        document.querySelectorAll('.filter-section').forEach(function(sec, i) {
            if (i === 0) sec.querySelectorAll('.filter-chip').forEach(function(b) {
                b.classList.remove('active');
                b.style.background = '';
            });
        });
        btn.classList.add('active');
        btn.style.background = btn.dataset.color || '#2c3e50';
        document.querySelectorAll('.track-section').forEach(function(s) {
            s.style.display = (track === 'all' || s.dataset.track === track) ? '' : 'none';
        });
    }
    function filterCity(city, btn) {
        document.querySelectorAll('.filter-section').forEach(function(sec, i) {
            if (i === 1) sec.querySelectorAll('.filter-chip').forEach(function(b) {
                b.classList.remove('active');
                b.style.background = '';
            });
        });
        btn.classList.add('active');
        btn.style.background = '#2c3e50';
        document.querySelectorAll('.offer').forEach(function(o) {
            o.style.display = (city === 'all' || o.dataset.city === city) ? '' : 'none';
        });
    }
    function filterStatus(status, btn) {
        document.querySelectorAll('.filter-section').forEach(function(sec, i) {
            if (i === 2) sec.querySelectorAll('.filter-chip').forEach(function(b) {
                b.classList.remove('active');
                b.style.background = '';
            });
        });
        btn.classList.add('active');
        btn.style.background = '#2c3e50';
        document.querySelectorAll('.offer').forEach(function(o) {
            o.style.display = (status === 'all' || o.dataset.status === status) ? '' : 'none';
        });
    }
    """

    return (
        f'<!DOCTYPE html><html lang="fr"><head>'
        f'<meta charset="UTF-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>Veille Alternances &mdash; {_e(now_str)}</title>'
        f'{ga_snippet}'
        f'<style>{_CSS}</style></head><body>'
        f'<div class="container">'
        f'<div class="header">'
        f'<h1>&#129302; Veille Automatique des Alternances</h1>'
        f'<p>Bachelor 3 RSB &middot; Debut : Septembre 2026 &middot; Duree : 12&ndash;24 mois</p>'
        f'<p>{_e(now_str)}</p></div>'
        f'<div class="stats-bar">'
        f'<div class="stat"><strong>{total}</strong><span>offres actives</span></div>'
        f'<div class="stat"><strong style="color:#27ae60;">{nouvelles}</strong><span>nouvelles</span></div>'
        f'<div class="stat"><strong style="color:#1a7a4a;">{lba}</strong><span>LBA</span></div>'
        f'<div class="stat"><strong style="color:#6d28d9;">{llm}</strong><span>LLM</span></div>'
        f'{city_stats_html}</div>'
        f'<div class="filter-section"><label>FILTRE PAR TRACK</label>'
        f'<div class="filter-bar">{track_chips}</div></div>'
        f'<div class="filter-section"><label>FILTRE PAR VILLE</label>'
        f'<div class="filter-bar">{city_chips}</div></div>'
        f'<div class="filter-section"><label>FILTRE PAR STATUT</label>'
        f'<div class="filter-bar">'
        f'<span class="filter-chip active" onclick="filterStatus(\'all\',this)"'
        f' style="background:#2c3e50;">Tous</span>'
        f'<span class="filter-chip" onclick="filterStatus(\'new\',this)"'
        f' data-color="#27ae60;">&#128994; Nouvelles</span>'
        f'<span class="filter-chip" onclick="filterStatus(\'active\',this)"'
        f' data-color="#7f8c8d;">&#9851;&#65039; Actives</span>'
        f'</div></div>'
        f'{sections_html}'
        f'<div class="footer">'
        f'<p>Genere automatiquement par le robot de veille alternances v2 (CrewAI Flow)<br>'
        f'Mis a jour : {_e(now_str)}<br>'
        f'<a href="{GITHUB_PAGES_URL}" target="_blank">{GITHUB_PAGES_URL}</a></p>'
        f'</div></div>'
        f'<script>{js}</script>'
        f'</body></html>'
    )


# ===== ENVOI EMAIL =====

def send_email(email_html: str) -> None:
    if not GMAIL_USER or not GMAIL_PASSWORD:
        print("  WARN Credentials Gmail absents - envoi ignore")
        return
    msg            = MIMEMultipart("alternative")
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg["Subject"] = f"Veille Alternances - {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText(
        f"Veille du {datetime.now().strftime('%d/%m/%Y')}.\n"
        f"Voir en ligne : {GITHUB_PAGES_URL}", "plain", "utf-8"
    ))
    msg.attach(MIMEText(email_html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        print(f"  OK Email envoye a {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"  ERREUR envoi email : {e}")


# ===== POINT D'ENTREE =====

def run_html_email() -> None:
    if not OFFRES_MERGED.exists():
        print(f"[warn] {OFFRES_MERGED} introuvable - HTML ignore")
        return

    with open(OFFRES_MERGED, encoding="utf-8") as f:
        data = json.load(f)

    offers         = data.get("offres", [])
    meta           = data.get("meta", {})
    track_colors   = load_track_colors()
    tracks_cfg     = load_tracks_config()
    hr_contacts    = load_hr_contacts()
    stats_by_city  = meta.get("stats_by_city", {})
    stats_by_track = meta.get("stats_by_track", {})

    print(f"\n{'='*60}")
    print(f"HTML EMAIL - {len(offers)} offres")
    print(f"{'='*60}\n")

    page_html = render_page_html(offers, meta, track_colors, tracks_cfg, hr_contacts)
    with open(OUTPUT_HTML_DOCS, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"  SAVE {OUTPUT_HTML_DOCS}")

    archive_path = ARCHIVES_DIR / f"veille_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html"
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"  SAVE archive/{archive_path.name}")

    cleanup_archives()

    push_ok = git_push_html()

    email_html = render_email_html(meta, stats_by_city, stats_by_track, tracks_cfg, push_ok)
    send_email(email_html)


if __name__ == "__main__":
    run_html_email()
