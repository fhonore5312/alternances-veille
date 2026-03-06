#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération HTML + envoi email — v2
Architecture :
  - render_email_html()  → email minimal (stats + CTA)  → MIME body
  - render_page_html()   → page riche (filtres + offres + contacts RH) → docs/index.html + archive
  - send_email()         → envoie l'email et push GitHub Pages

Usage:
    python -m scripts.generate_html_email
"""

import json
import os
import re
import smtplib
import subprocess
from datetime import datetime
from email import encoders as email_encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

from utils.config_loader import load_tracks

load_dotenv()

# ===== CHEMINS =====

SCRIPT_DIR   = Path(__file__).parent
BASE_DIR     = SCRIPT_DIR.parent
DATA_DIR     = BASE_DIR / "data"
DOCS_DIR     = BASE_DIR / "docs"
ARCHIVES_DIR = DOCS_DIR / "archives"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

OFFRES_MERGED    = DATA_DIR / "offres_merged.json"
HR_CONTACTS_FILE = DATA_DIR / "hr_contacts.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

# ===== PARAMÈTRES =====

GMAIL_USER      = os.getenv("GMAIL_USER")
GMAIL_PASSWORD  = os.getenv("GMAIL_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", GMAIL_USER)
GITHUB_PAGES_URL = "https://fhonore5312.github.io/alternances-veille/"
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "")  # ex: G-XXXXXXXXXX
RETENTION_DAYS   = 30

if not GMAIL_USER or not GMAIL_PASSWORD:
    raise ValueError("GMAIL_USER et GMAIL_PASSWORD doivent être définis dans .env")

# ===== CHARGEMENT DONNÉES =====

def load_offers() -> dict:
    with open(OFFRES_MERGED, "r", encoding="utf-8") as f:
        return json.load(f)

def load_hr_contacts() -> dict:
    """Retourne un dict {offer_id: contact} à partir de hr_contacts.json."""
    if not HR_CONTACTS_FILE.exists():
        return {}
    try:
        with open(HR_CONTACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {c["offer_id"]: c for c in data.get("contacts", [])}
    except Exception:
        return {}

# ===== UTILITAIRES =====

def parse_date_offre(offer: dict) -> datetime:
    for field, fmt in [("date_creation", "%d/%m/%Y"), ("first_seen", "%Y-%m-%d")]:
        val = offer.get(field)
        if val:
            try:
                return datetime.strptime(val, fmt)
            except Exception:
                pass
    return datetime.min

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
        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if not result.stdout.strip():
            print("GitHub Pages : rien à commiter")
            return True
        subprocess.run(["git", "add", "docs/"], check=True, cwd=BASE_DIR)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore: veille {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True, cwd=BASE_DIR
        )
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=BASE_DIR)
        print("✅ GitHub Pages mis à jour")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push échoué : {e}")
        return False

# ===== RENDU EMAIL (minimal) =====

def render_email_html(meta: dict, stats_by_city: dict, stats_by_track: dict,
                      tracks_cfg: dict, push_ok: bool) -> str:
    total    = meta.get("total_offres", 0)
    nouvelles = meta.get("nouvelles", 0)
    lba      = meta.get("source_lba", 0)
    llm      = meta.get("source_llm", 0)
    now_str  = datetime.now().strftime("%d/%m/%Y à %H:%M")
    page_status = "✅ Page en ligne mise à jour" if push_ok else "⚠️ Page non mise à jour (git push échoué)"

    # Lignes par track
    track_rows = ""
    for tk, stats in stats_by_track.items():
        cfg   = tracks_cfg.get(tk, {})
        label = cfg.get("label", tk)
        t     = stats.get("total", 0)
        n     = stats.get("nouvelles", 0)
        new_badge = f'&nbsp;<span style="background:#27ae60;color:white;font-size:10px;padding:2px 6px;border-radius:8px;">{n} new</span>' if n > 0 else ""
        track_rows += f"""
        <tr>
          <td style="padding:5px 0;font-size:13px;color:#555;">{label}</td>
          <td style="padding:5px 0;font-size:13px;color:#2c3e50;font-weight:bold;text-align:right;">{t} offres{new_badge}</td>
        </tr>"""

    # Ligne par ville
    ville_cells = ""
    for ville, emoji in [("Rennes","🏴"), ("Nantes","⚓"), ("Paris","🗼")]:
        c = stats_by_city.get(ville, 0)
        ville_cells += f"""
        <td style="text-align:center;padding:10px 6px;background:white;border-radius:8px;">
          <strong style="display:block;font-size:18px;color:#2c3e50;">{c}</strong>
          <span style="font-size:11px;color:#7f8c8d;">{emoji} {ville}</span>
        </td>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:560px;margin:20px auto;padding:16px;">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#2c3e50 0%,#3498db 100%);color:white;
              padding:26px 28px;border-radius:12px;text-align:center;margin-bottom:14px;">
    <h1 style="margin:0 0 6px;font-size:22px;font-weight:bold;">🎓 Veille Alternances</h1>
    <p style="margin:3px 0;font-size:13px;opacity:.9;">{now_str}</p>
    <p style="margin:3px 0;font-size:12px;opacity:.75;">Bachelor 3 RSB · Début : Septembre 2026 · Durée : 12–24 mois</p>
  </div>

  <!-- STATS PRINCIPALES -->
  <table style="width:100%;border-collapse:separate;border-spacing:6px;margin-bottom:14px;">
    <tr>
      <td style="background:white;border-radius:8px;padding:14px 10px;text-align:center;
                 box-shadow:0 2px 6px rgba(0,0,0,.07);">
        <strong style="display:block;font-size:26px;color:#2c3e50;">{total}</strong>
        <span style="font-size:11px;color:#7f8c8d;">offres actives</span>
      </td>
      <td style="background:#27ae60;border-radius:8px;padding:14px 10px;text-align:center;
                 box-shadow:0 2px 6px rgba(0,0,0,.07);">
        <strong style="display:block;font-size:26px;color:white;">{nouvelles}</strong>
        <span style="font-size:11px;color:rgba(255,255,255,.8);">nouvelles</span>
      </td>
      <td style="background:white;border-radius:8px;padding:14px 10px;text-align:center;
                 box-shadow:0 2px 6px rgba(0,0,0,.07);">
        <strong style="display:block;font-size:16px;color:#2c3e50;">{lba}<span style="font-size:11px;font-weight:normal;color:#7f8c8d;"> LBA</span></strong>
        <strong style="display:block;font-size:16px;color:#6d28d9;">{llm}<span style="font-size:11px;font-weight:normal;color:#7f8c8d;"> LLM</span></strong>
      </td>
    </tr>
  </table>

  <!-- STATS PAR VILLE -->
  <table style="width:100%;border-collapse:separate;border-spacing:6px;margin-bottom:14px;">
    <tr>{ville_cells}</tr>
  </table>

  <!-- STATS PAR TRACK -->
  <div style="background:white;border-radius:8px;padding:14px 16px;margin-bottom:20px;
              box-shadow:0 2px 6px rgba(0,0,0,.07);">
    <table style="width:100%;border-collapse:collapse;">{track_rows}
    </table>
  </div>

  <!-- CTA -->
  <div style="text-align:center;margin:22px 0 18px;">
    <a href="{GITHUB_PAGES_URL}"
       style="display:inline-block;padding:14px 36px;background:#3498db;color:white;
              text-decoration:none;border-radius:8px;font-weight:bold;font-size:16px;
              letter-spacing:.3px;box-shadow:0 3px 10px rgba(52,152,219,.4);">
      📋 Voir toutes les offres en ligne &nbsp;→
    </a>
  </div>

  <!-- FOOTER -->
  <p style="text-align:center;font-size:11px;color:#aaa;margin-top:8px;">{page_status}</p>
  <p style="text-align:center;font-size:11px;color:#ccc;">Automatisation · {GMAIL_USER}</p>

</div>
</body>
</html>"""

# ===== RENDU PAGE HTML (riche) =====

def render_page_html(data: dict, contacts: dict, tracks_cfg: dict) -> str:
    offers   = data["offres"]
    meta     = data["meta"]
    total    = meta.get("total_offres", 0)
    nouvelles = meta.get("nouvelles", 0)
    lba      = meta.get("source_lba", 0)
    llm      = meta.get("source_llm", 0)
    stats_by_track = meta.get("stats_by_track", {})

    stats_by_city = {
        v: len([o for o in offers if o.get("ville_recherche") == v])
        for v in ("Rennes", "Nantes", "Paris")
    }

    now_full  = datetime.now().strftime("%A %d %B %Y - %H:%M")
    now_short = datetime.now().strftime("%d/%m/%Y à %H:%M")
    tracks_in_data = [k for k in tracks_cfg if any(o.get("track") == k for o in offers)]

    # ── Google Analytics ───────────────────────────────────────────────────
    ga_tag = ""
    if GA_MEASUREMENT_ID:
        ga_tag = f"""  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA_MEASUREMENT_ID}');
  </script>"""

    # ── Filtres Track (chips) ──────────────────────────────────────────────
    track_chips = f'<div class="filter-chip active" data-filter="track" data-val="all" style="background:#3498db;border-color:#3498db;">Tous &nbsp;{total}</div>\n'
    for tk in tracks_in_data:
        cfg   = tracks_cfg.get(tk, {})
        color = cfg.get("color_hex", "#3498db")
        label = cfg.get("label", tk)
        count = stats_by_track.get(tk, {}).get("total", 0)
        track_chips += f'    <div class="filter-chip" data-filter="track" data-val="{tk}" data-color="{color}">{label} &nbsp;{count}</div>\n'

    # ── Filtres Ville ──────────────────────────────────────────────────────
    ville_chips = '<div class="filter-chip active" data-filter="ville" data-val="all" style="background:#3498db;border-color:#3498db;">Toutes villes</div>\n'
    for ville, emoji in [("Rennes", "🏴"), ("Nantes", "⚓"), ("Paris", "🗼")]:
        c = stats_by_city.get(ville, 0)
        if c > 0:
            ville_chips += f'    <div class="filter-chip" data-filter="ville" data-val="{ville}">{emoji} {ville} &nbsp;{c}</div>\n'

    # ── Filtres Source ─────────────────────────────────────────────────────
    source_chips = """
    <div class="filter-chip active" data-filter="source" data-val="all" style="background:#3498db;border-color:#3498db;">Toutes sources</div>
    <div class="filter-chip" data-filter="source" data-val="LBA">LBA</div>
    <div class="filter-chip" data-filter="source" data-val="LLM">LLM</div>"""

    # ── Toggle Nouvelles ───────────────────────────────────────────────────
    new_toggle = f'<div class="filter-chip" id="toggle-new" data-filter="new" data-val="false">✨ Nouvelles uniquement &nbsp;({nouvelles})</div>'

    # ── Sections offres par track ──────────────────────────────────────────
    sections_html = ""
    for tk in tracks_in_data:
        cfg   = tracks_cfg.get(tk, {})
        color = cfg.get("color_hex", "#3498db")
        label = cfg.get("label", tk)
        track_offers = [o for o in offers if o.get("track") == tk]
        if not track_offers:
            continue
        t_new  = sum(1 for o in track_offers if o.get("status") == "new")
        badge_new = f'<span style="font-size:12px;font-weight:normal">{t_new} nouvelles</span>' if t_new else ""

        sections_html += f'\n<div class="track-section" data-track="{tk}">\n'
        sections_html += f'  <div class="track-header" style="background:{color}">🎯 {label} &nbsp;· {len(track_offers)} offres &nbsp;{badge_new}</div>\n'
        sections_html += '  <div class="track-body">\n'

        for ville, emoji in [("Rennes", "🏴"), ("Nantes", "⚓"), ("Paris", "🗼")]:
            city_offers = [o for o in track_offers if o.get("ville_recherche") == ville]
            if not city_offers:
                continue
            priority = city_offers[0].get("priorite_ville", "?")
            city_offers_sorted = sorted(
                city_offers,
                key=lambda x: (0 if x.get("status") == "new" else 1, -parse_date_offre(x).timestamp())
            )

            sections_html += f'    <div class="city-group" data-ville="{ville}">\n'
            sections_html += f'      <div class="city-header">{emoji} {ville} · Priorité {priority} · {len(city_offers)} offres</div>\n'

            for offer in city_offers_sorted:
                offer_id  = offer.get("id", "")
                is_new    = offer.get("status") == "new"
                src       = offer.get("source", "LBA").upper()
                src_badge = (
                    '<span class="badge-llm">LLM</span>' if src == "LLM"
                    else '<span class="badge-lba">LBA</span>'
                )
                new_badge = '<span class="badge-new">✨ NOUVELLE</span>' if is_new else ""
                competences = offer.get("competences_detectees", [])
                skills_html = ""
                if competences:
                    skills_html = '<div class="skills">' + "".join(
                        f'<span class="skill-tag">{s}</span>' for s in competences
                    ) + "</div>"

                meta_parts = []
                if offer.get("entreprise"):
                    meta_parts.append(f'🏢 {offer["entreprise"]}')
                city_zip = f'{offer.get("ville","")} {offer.get("code_postal","")}'.strip()
                if city_zip:
                    meta_parts.append(f'📍 {city_zip}')
                if offer.get("date_creation"):
                    meta_parts.append(f'📅 {offer["date_creation"]}')
                if offer.get("date_debut"):
                    meta_parts.append(f'🗓 Début {offer["date_debut"]}')
                if offer.get("duree_contrat"):
                    meta_parts.append(f'⏱ {offer["duree_contrat"]}')
                if offer.get("plateforme_source"):
                    meta_parts.append(f'🔗 {offer["plateforme_source"]}')
                meta_html = " &nbsp;·&nbsp; ".join(meta_parts)

                url    = offer.get("url_candidature", "#")
                titre  = offer.get("titre", "NA")
                desc   = offer.get("description", "")

                # ── Contact RH ────────────────────────────────────────────
                contact      = contacts.get(offer_id, {})
                contact_html = ""
                if contact:
                    parts = []
                    nom    = contact.get("nom_contact")
                    role   = contact.get("role_contact")
                    email  = contact.get("email_rh")
                    careers = contact.get("url_careers")
                    note   = contact.get("note")
                    conf   = contact.get("confidence", "low")
                    conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")

                    if nom:
                        role_str = f' <em style="color:#888;font-size:11px;">({role})</em>' if role else ""
                        parts.append(f'👤 <strong>{nom}</strong>{role_str}')
                    if email:
                        parts.append(f'📧 <a href="mailto:{email}" style="color:#3498db;">{email}</a>')
                    if careers:
                        parts.append(f'💼 <a href="{careers}" target="_blank" style="color:#3498db;">Page carrières</a>')
                    if note and not nom and not email and not careers:
                        note_short = note[:100] + "…" if len(note) > 100 else note
                        parts.append(f'📝 {note_short}')

                    if parts:
                        contact_html = f"""
                <div class="hr-contact">
                  <span class="hr-conf">{conf_icon} Contact RH</span>
                  {"&nbsp;·&nbsp;".join(parts)}
                </div>"""

                sections_html += f"""    <div class="offer" data-track="{tk}" data-ville="{ville}" data-source="{src}" data-new="{'true' if is_new else 'false'}">
      <h3>{titre} {src_badge}{new_badge}</h3>
      <p class="description">{desc}</p>
      {skills_html}
      <div class="meta">{meta_html}</div>
      {contact_html}
      <a class="btn-apply" href="{url}" target="_blank" style="background:{color}">Postuler →</a>
    </div>\n"""

            sections_html += "    </div>\n"  # city-group
        sections_html += "  </div>\n</div>\n"  # track-body + track-section

    # ── JavaScript filtres ─────────────────────────────────────────────────
    js = """
    const state = { track: 'all', ville: 'all', source: 'all', newOnly: false };

    function applyFilters() {
      const offers = document.querySelectorAll('.offer');
      offers.forEach(o => {
        const mt = state.track  === 'all' || o.dataset.track  === state.track;
        const mv = state.ville  === 'all' || o.dataset.ville  === state.ville;
        const ms = state.source === 'all' || o.dataset.source === state.source;
        const mn = !state.newOnly || o.dataset.new === 'true';
        o.style.display = (mt && mv && ms && mn) ? '' : 'none';
      });
      document.querySelectorAll('.city-group').forEach(grp => {
        const visible = [...grp.querySelectorAll('.offer')].some(o => o.style.display !== 'none');
        grp.style.display = visible ? '' : 'none';
      });
      document.querySelectorAll('.track-section').forEach(sec => {
        const visible = [...sec.querySelectorAll('.offer')].some(o => o.style.display !== 'none');
        sec.style.display = visible ? '' : 'none';
      });
    }

    document.querySelectorAll('.filter-chip[data-filter="track"]').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.filter-chip[data-filter="track"]').forEach(c => {
          c.classList.remove('active'); c.style.background = ''; c.style.borderColor = ''; c.style.color = '';
        });
        chip.classList.add('active');
        const color = chip.dataset.color || '#3498db';
        chip.style.background = color; chip.style.borderColor = color; chip.style.color = 'white';
        state.track = chip.dataset.val;
        applyFilters();
      });
    });

    document.querySelectorAll('.filter-chip[data-filter="ville"]').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.filter-chip[data-filter="ville"]').forEach(c => {
          c.classList.remove('active'); c.style.background = ''; c.style.borderColor = ''; c.style.color = '';
        });
        chip.classList.add('active');
        chip.style.background = '#3498db'; chip.style.borderColor = '#3498db'; chip.style.color = 'white';
        state.ville = chip.dataset.val;
        applyFilters();
      });
    });

    document.querySelectorAll('.filter-chip[data-filter="source"]').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.filter-chip[data-filter="source"]').forEach(c => {
          c.classList.remove('active'); c.style.background = ''; c.style.borderColor = ''; c.style.color = '';
        });
        chip.classList.add('active');
        chip.style.background = '#3498db'; chip.style.borderColor = '#3498db'; chip.style.color = 'white';
        state.source = chip.dataset.val;
        applyFilters();
      });
    });

    const toggleNew = document.getElementById('toggle-new');
    if (toggleNew) {
      toggleNew.addEventListener('click', () => {
        state.newOnly = !state.newOnly;
        if (state.newOnly) {
          toggleNew.classList.add('active');
          toggleNew.style.background = '#27ae60'; toggleNew.style.borderColor = '#27ae60'; toggleNew.style.color = 'white';
        } else {
          toggleNew.classList.remove('active');
          toggleNew.style.background = ''; toggleNew.style.borderColor = ''; toggleNew.style.color = '';
        }
        applyFilters();
      });
    }"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Veille Alternances RSB — {now_short}</title>
{ga_tag}
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           margin: 0; padding: 20px; background: #f8f9fa; color: #2c3e50; line-height: 1.6; }}
    .container {{ max-width: 940px; margin: 0 auto; }}

    /* Header */
    .header {{ background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
               color: white; padding: 28px 30px; border-radius: 12px;
               margin-bottom: 18px; text-align: center; }}
    .header h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .header p  {{ margin: 3px 0; opacity: .9; font-size: 13px; }}

    /* Stats bar */
    .stats-bar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }}
    .stat {{ background: white; border-radius: 8px; padding: 10px 14px;
             box-shadow: 0 2px 6px rgba(0,0,0,.07); text-align: center; flex: 1; min-width: 70px; }}
    .stat strong {{ display: block; font-size: 20px; color: #2c3e50; }}
    .stat span   {{ font-size: 11px; color: #7f8c8d; }}

    /* Filter bars */
    .filter-section {{ background: white; border-radius: 8px; padding: 12px 14px;
                       box-shadow: 0 2px 6px rgba(0,0,0,.07); margin-bottom: 10px; }}
    .filter-section label {{ font-size: 11px; color: #999; display: block; margin-bottom: 6px; }}
    .filter-bar {{ display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }}
    .filter-chip {{ padding: 5px 13px; border-radius: 14px; border: 1.5px solid #ddd;
                    background: #fff; font-size: 12px; cursor: pointer;
                    transition: all .15s ease; user-select: none; }}
    .filter-chip:hover {{ border-color: #3498db; color: #3498db; }}
    .filter-chip.active {{ color: white; border-color: transparent; }}

    /* Track sections */
    .track-section {{ margin-bottom: 26px; background: white; border-radius: 10px;
                      box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }}
    .track-header {{ padding: 13px 20px; color: white; font-size: 16px; font-weight: bold; }}
    .track-body   {{ padding: 0 20px 14px; }}

    /* City groups */
    .city-group  {{ margin-bottom: 6px; }}
    .city-header {{ font-size: 13px; font-weight: bold; color: #555;
                    padding: 14px 0 7px; border-bottom: 2px solid #eee; margin-bottom: 8px; }}

    /* Offer cards */
    .offer {{ padding: 12px 0; border-bottom: 1px solid #f0f0f0; }}
    .offer:last-child {{ border-bottom: none; }}
    .offer h3 {{ margin: 0 0 4px; font-size: 14px; color: #2c3e50; }}
    .description {{ font-size: 13px; color: #555; margin: 4px 0 6px; }}
    .skills {{ margin-bottom: 6px; }}
    .skill-tag {{ display: inline-block; background: #eef2ff; color: #3498db;
                  font-size: 11px; padding: 2px 8px; border-radius: 10px; margin: 2px 3px 2px 0; }}
    .meta {{ font-size: 11px; color: #95a5a6; margin-bottom: 7px; }}

    /* Badges */
    .badge-new {{ background: #27ae60; color: white; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 6px;
                  font-weight: normal; vertical-align: middle; }}
    .badge-lba {{ background: #e8f8f0; color: #1a7a4a; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 5px;
                  font-weight: bold; vertical-align: middle; }}
    .badge-llm {{ background: #ede9fe; color: #6d28d9; font-size: 10px;
                  padding: 2px 7px; border-radius: 10px; margin-left: 5px;
                  font-weight: bold; vertical-align: middle; }}

    /* Contact RH */
    .hr-contact {{ font-size: 12px; color: #555; margin: 6px 0 8px;
                   padding: 6px 10px; background: #f9fafb;
                   border-left: 3px solid #3498db; border-radius: 0 6px 6px 0; }}
    .hr-conf {{ color: #888; font-size: 11px; margin-right: 6px; }}
    .hr-contact a {{ color: #3498db; text-decoration: none; }}
    .hr-contact a:hover {{ text-decoration: underline; }}

    /* Button */
    .btn-apply {{ display: inline-block; padding: 5px 14px; color: white;
                  text-decoration: none; border-radius: 5px; font-size: 12px;
                  font-weight: bold; margin-top: 4px; }}
    .btn-apply:hover {{ opacity: .88; }}

    /* Footer */
    .footer {{ text-align: center; padding: 18px; background: white; border-radius: 10px;
               margin-top: 18px; font-size: 12px; color: #7f8c8d;
               box-shadow: 0 2px 6px rgba(0,0,0,.06); }}
    .footer a {{ color: #3498db; text-decoration: none; }}
  </style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <h1>🎓 Veille Alternances &mdash; Rennes School of Business</h1>
    <p><strong>{now_full}</strong></p>
    <p>Bachelor 3 RSB &nbsp;·&nbsp; Début : Septembre 2026 &nbsp;·&nbsp; Durée : 12–24 mois</p>
  </div>

  <!-- STATS -->
  <div class="stats-bar">
    <div class="stat"><strong>{total}</strong><span>Total</span></div>
    <div class="stat"><strong>{nouvelles}</strong><span>✨ Nouvelles</span></div>
    <div class="stat"><strong>{stats_by_city.get('Rennes',0)}</strong><span>🏴 Rennes</span></div>
    <div class="stat"><strong>{stats_by_city.get('Nantes',0)}</strong><span>⚓ Nantes</span></div>
    <div class="stat"><strong>{stats_by_city.get('Paris',0)}</strong><span>🗼 Paris</span></div>
    <div class="stat"><strong>{lba}</strong><span>LBA</span></div>
    <div class="stat"><strong>{llm}</strong><span>LLM</span></div>
  </div>

  <!-- FILTRES -->
  <div class="filter-section">
    <label>🎯 Domaine</label>
    <div class="filter-bar">
      {track_chips}
    </div>
  </div>
  <div class="filter-section">
    <label>📍 Ville &nbsp;&nbsp;&nbsp; 📡 Source &nbsp;&nbsp;&nbsp; ✨ Nouveautés</label>
    <div class="filter-bar">
      {ville_chips}
      <span style="width:1px;background:#ddd;height:20px;margin:0 4px;align-self:center;"></span>
      {source_chips}
      <span style="width:1px;background:#ddd;height:20px;margin:0 4px;align-self:center;"></span>
      {new_toggle}
    </div>
  </div>

  <!-- OFFRES -->
  {sections_html}

  <!-- FOOTER -->
  <div class="footer">
    <p>Mise à jour le {now_short} &nbsp;·&nbsp; LBA {lba} &nbsp;·&nbsp; LLM {llm}</p>
    <p><a href="archives/">📂 Historique {RETENTION_DAYS} derniers jours</a></p>
  </div>

</div>
<script>
  document.addEventListener('DOMContentLoaded', function() {{
    {js}
  }});
</script>
</body>
</html>"""

# ===== ENVOI EMAIL =====

def send_email(email_html: str, page_html: str, meta: dict) -> None:
    cleanup_archives()

    # Sauvegarder page HTML
    with open(OUTPUT_HTML_DOCS, "w", encoding="utf-8") as f:
        f.write(page_html)

    # Archive horodatée
    archive_name = f"veille_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html"
    archive_path = ARCHIVES_DIR / archive_name
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(page_html)

    push_ok = git_push_html()

    total     = meta.get("total_offres", 0)
    nouvelles = meta.get("nouvelles", 0)
    subject   = (f"[Veille Alternances] {nouvelles} nouvelles offres · "
                 f"{total} actives — {datetime.now().strftime('%d/%m/%Y à %H:%M')}")

    msg          = MIMEMultipart("mixed")
    msg["From"]  = GMAIL_USER
    msg["To"]    = RECIPIENT_EMAIL
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Veille alternances — voir la version HTML en ligne.", "plain"))
    alt.attach(MIMEText(email_html, "html"))
    msg.attach(alt)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print(f"✅ Email envoyé à {RECIPIENT_EMAIL}")
        print(f"   Page  : {OUTPUT_HTML_DOCS}")
        print(f"   Archive : {archive_path}")
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")

# ===== MAIN =====

def main():
    print("=" * 60)
    print("📧 GÉNÉRATION EMAIL + PAGE HTML")
    print("=" * 60)

    data       = load_offers()
    contacts   = load_hr_contacts()
    tracks_cfg = load_tracks()
    meta       = data["meta"]
    offers     = data["offres"]

    stats_by_city  = {
        v: len([o for o in offers if o.get("ville_recherche") == v])
        for v in ("Rennes", "Nantes", "Paris")
    }
    stats_by_track = meta.get("stats_by_track", {})

    print(f"  📦 {meta.get('total_offres', 0)} offres — {meta.get('nouvelles', 0)} nouvelles")
    print(f"  📬 {len(contacts)} contacts RH chargés")

    # Écriture page (besoin de push_ok pour l'email)
    with open(OUTPUT_HTML_DOCS, "w", encoding="utf-8") as f:
        f.write("")  # placeholder
    push_ok = git_push_html()

    page_html  = render_page_html(data, contacts, tracks_cfg)
    email_html = render_email_html(meta, stats_by_city, stats_by_track, tracks_cfg, push_ok)

    send_email(email_html, page_html, meta)

    print("=" * 60)
    print("➡️  Pipeline terminé !")
    print("=" * 60)

if __name__ == "__main__":
    main()
