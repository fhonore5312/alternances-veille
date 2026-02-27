#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generation HTML et envoi email
Pipeline : scraper_lba.py -> validator.py -> merge_offers.py -> generate_html_email.py
"""

import json
from datetime import datetime
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import subprocess
from utils.config_loader import load_tracks

load_dotenv()

SCRIPT_DIR    = Path(__file__).parent
BASE_DIR      = SCRIPT_DIR.parent
DATA_DIR      = BASE_DIR / "data"
DOCS_DIR      = BASE_DIR / "docs"
ARCHIVES_DIR  = DOCS_DIR / "archives"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

OFFRES_MERGED    = DATA_DIR / "offres_merged.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

GMAIL_USER      = os.getenv("GMAIL_USER")
GMAIL_PASSWORD  = os.getenv("GMAIL_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", GMAIL_USER)

if not GMAIL_USER or not GMAIL_PASSWORD:
    raise ValueError("GMAIL_USER et GMAIL_PASSWORD doivent etre definis dans .env")

GITHUB_PAGES_URL = "https://fhonore5312.github.io/alternances-veille/"
RETENTION_DAYS   = 30


def load_offers():
    with open(OFFRES_MERGED, "r", encoding="utf-8") as f:
        return json.load(f)


def git_push_html():
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if not result.stdout.strip():
            print("GitHub Pages : rien a commiter")
            return True
        subprocess.run(["git", "add", "docs/"], check=True, cwd=BASE_DIR)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore: mise a jour veille {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True, cwd=BASE_DIR
        )
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=BASE_DIR)
        print("GitHub Pages mis a jour (main)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git push ECHOUE : {e}")
        return False


def cleanup_archives():
    now = datetime.now()
    for archive in ARCHIVES_DIR.glob("*.html"):
        try:
            mtime = datetime.fromtimestamp(archive.stat().st_mtime)
            if (now - mtime).days > RETENTION_DAYS:
                archive.unlink()
        except Exception:
            pass


# =============================================================
# MODIF 1 : helper tri par date
# =============================================================
def parse_date_offre(offer: dict) -> datetime:
    """Parse date_creation DD/MM/YYYY ou first_seen YYYY-MM-DD."""
    dc = offer.get("date_creation")
    if dc:
        try:
            return datetime.strptime(dc, "%d/%m/%Y")
        except Exception:
            pass
    fs = offer.get("first_seen")
    if fs:
        try:
            return datetime.strptime(fs, "%Y-%m-%d")
        except Exception:
            pass
    return datetime.min


def generate_html(data):
    offers     = data["offres"]
    meta       = data["meta"]
    tracks_cfg = load_tracks()

    total_offers   = meta["total_offres"]
    new_count      = meta.get("nouvelles", 0)
    lba_count      = meta.get("source_lba", 0)
    llm_count      = meta.get("source_llm", 0)
    stats_by_track = meta.get("stats_by_track", {})

    stats_by_city = {
        "Rennes": len([o for o in offers if o.get("ville_recherche") == "Rennes"]),
        "Nantes": len([o for o in offers if o.get("ville_recherche") == "Nantes"]),
        "Paris":  len([o for o in offers if o.get("ville_recherche") == "Paris"]),
    }

    tracks_in_data = [k for k in tracks_cfg if any(
        o.get("track", "digital_marketing") == k for o in offers
    )]

    now_str   = datetime.now().strftime("%d/%m/%Y")
    now_full  = datetime.now().strftime("%A %d %B %Y - %H:%M")
    now_short = datetime.now().strftime("%d/%m/%Y a %H:%M")

    html  = "<!DOCTYPE html>\n"
    html += '<html lang="fr">\n'
    html += "<head>\n"
    html += '    <meta charset="UTF-8">\n'
    html += '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html += f'    <title>Veille Alternances RSB - {now_str}</title>\n'
    html += "    <style>\n"
    html += "        * { box-sizing: border-box; }\n"
    html += "        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; color: #2c3e50; line-height: 1.6; }\n"
    html += "        .container { max-width: 920px; margin: 0 auto; }\n"
    html += "        .header { background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; padding: 28px 30px; border-radius: 10px; margin-bottom: 20px; text-align: center; }\n"
    html += "        .header h1 { margin: 0 0 6px 0; font-size: 24px; }\n"
    html += "        .header p { margin: 3px 0; opacity: 0.9; font-size: 13px; }\n"
    html += "        .stats-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }\n"
    html += "        .stat { background: white; border-radius: 8px; padding: 10px 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.07); text-align: center; flex: 1; min-width: 75px; }\n"
    html += "        .stat strong { display: block; font-size: 20px; color: #2c3e50; }\n"
    html += "        .stat span { font-size: 11px; color: #7f8c8d; }\n"
    html += "        .filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 22px; align-items: center; }\n"
    html += "        .filter-bar label { font-size: 12px; color: #7f8c8d; margin-right: 4px; }\n"
    html += "        .filter-chip { padding: 5px 13px; border-radius: 14px; border: 1.5px solid #ddd; background: #fff; font-size: 12px; cursor: pointer; transition: all 0.15s ease; user-select: none; }\n"
    html += "        .filter-chip:hover { border-color: #3498db; color: #3498db; }\n"
    html += "        .filter-chip.active { color: white; border-color: transparent; }\n"
    html += "        .track-section { margin-bottom: 28px; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); overflow: hidden; }\n"
    html += "        .track-header { padding: 13px 20px; color: white; font-size: 17px; font-weight: bold; }\n"
    html += "        .track-body { padding: 0 20px 15px 20px; }\n"
    html += "        .city-header { font-size: 14px; font-weight: bold; color: #555; padding: 14px 0 7px 0; border-bottom: 2px solid #eee; margin-bottom: 10px; }\n"
    html += "        .offer { padding: 13px 0; border-bottom: 1px solid #f0f0f0; }\n"
    html += "        .offer:last-child { border-bottom: none; }\n"
    html += "        .offer h3 { margin: 0 0 4px 0; font-size: 14px; color: #2c3e50; }\n"
    html += "        .badge-new { background: #27ae60; color: white; font-size: 10px; padding: 2px 7px; border-radius: 10px; margin-left: 7px; font-weight: normal; vertical-align: middle; }\n"
    html += "        .badge-lba { background: #e8f8f0; color: #1a7a4a; font-size: 10px; padding: 2px 7px; border-radius: 10px; margin-left: 7px; font-weight: bold; vertical-align: middle; }\n"
    html += "        .badge-llm { background: #ede9fe; color: #6d28d9; font-size: 10px; padding: 2px 7px; border-radius: 10px; margin-left: 7px; font-weight: bold; vertical-align: middle; }\n"
    html += "        .description { font-size: 13px; color: #555; margin: 4px 0 7px 0; }\n"
    html += "        .skills { margin-bottom: 7px; }\n"
    html += "        .skill-tag { display: inline-block; background: #eef2ff; color: #3498db; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin: 2px 3px 2px 0; }\n"
    html += "        .meta { font-size: 11px; color: #95a5a6; margin-bottom: 7px; }\n"
    html += "        .btn-apply { display: inline-block; padding: 5px 13px; color: white; text-decoration: none; border-radius: 5px; font-size: 12px; font-weight: bold; }\n"
    html += "        .footer { text-align: center; padding: 18px; background: white; border-radius: 10px; margin-top: 18px; font-size: 12px; color: #7f8c8d; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }\n"
    html += "        .footer a { color: #3498db; text-decoration: none; }\n"
    html += "    </style>\n</head>\n<body>\n<div class=\"container\">\n"

    html += f'    <div class="header">\n'
    html += f'        <h1>&#127891; Veille Alternances &middot; Rennes School of Business PGE</h1>\n'
    html += f'        <p><strong>{now_full}</strong></p>\n'
    html += f'        <p>Bachelor 3 RSB &middot; D&eacute;but : Septembre 2026 &middot; Dur&eacute;e : 12-24 mois</p>\n'
    html += f'    </div>\n'

    html += f'    <div class="stats-bar">\n'
    html += f'        <div class="stat"><strong>{total_offers}</strong><span>Total</span></div>\n'
    html += f'        <div class="stat"><strong>{new_count}</strong><span>&#128994; Nouvelles</span></div>\n'
    html += f'        <div class="stat"><strong>{stats_by_city["Rennes"]}</strong><span>&#127984; Rennes</span></div>\n'
    html += f'        <div class="stat"><strong>{stats_by_city["Nantes"]}</strong><span>&#9875; Nantes</span></div>\n'
    html += f'        <div class="stat"><strong>{stats_by_city["Paris"]}</strong><span>&#128508; Paris</span></div>\n'
    html += f'        <div class="stat"><strong>{lba_count}</strong><span>LBA</span></div>\n'
    html += f'        <div class="stat"><strong>{llm_count}</strong><span>Perplexity</span></div>\n'
    html += f'    </div>\n'

    html += '    <div class="filter-bar" id="track-filters">\n'
    html += '        <label>Filtrer :</label>\n'
    html += f'        <div class="filter-chip active" data-track="all" style="background:#3498db;border-color:#3498db;">Tous ({total_offers})</div>\n'

    for track_key in tracks_in_data:
        cfg   = tracks_cfg[track_key]
        color = cfg.get("color_hex", "#3498db")
        count = stats_by_track.get(track_key, {}).get("total",
                len([o for o in offers if o.get("track") == track_key]))
        html += f'        <div class="filter-chip" data-track="{track_key}" data-color="{color}">{cfg["label"]} ({count})</div>\n'

    html += "    </div>\n\n"

    for track_key in tracks_in_data:
        cfg          = tracks_cfg[track_key]
        color        = cfg.get("color_hex", "#3498db")
        track_offers = [o for o in offers if o.get("track", "digital_marketing") == track_key]
        if not track_offers:
            continue

        t_new = len([o for o in track_offers if o.get("status") == "new"])
        badge_new_track = f' <span style="font-size:12px;font-weight:normal;">({t_new} nouvelles)</span>' if t_new else ""

        html += f'    <div class="track-section" data-track="{track_key}">\n'
        html += f'        <div class="track-header" style="background:{color};">&#127919; {cfg["label"]} &nbsp;&middot;&nbsp; {len(track_offers)} offres{badge_new_track}</div>\n'
        html += '        <div class="track-body">\n'

        for ville, emoji_code in [("Rennes", "&#127984;"), ("Nantes", "&#9875;"), ("Paris", "&#128508;")]:
            city_offers = [o for o in track_offers if o.get("ville_recherche") == ville]
            if not city_offers:
                continue
            priority = city_offers[0].get("priorite_ville", "?")

            # MODIF 1 : new en premier, puis tri date décroissante
            city_offers_sorted = sorted(
                city_offers,
                key=lambda x: (0 if x.get("status") == "new" else 1,
                               -(parse_date_offre(x).timestamp()))
            )

            html += f'            <div class="city-header">{emoji_code} {ville} &middot; Priorit&eacute; #{priority} &middot; {len(city_offers)} offre(s)</div>\n'

            for offer in city_offers_sorted:
                is_new   = offer.get("status") == "new"
                b_new    = '<span class="badge-new">&#128994; NOUVELLE</span>' if is_new else ""

                # MODIF 2 : badge source
                src = offer.get("source", "").upper()
                b_src = '<span class="badge-llm">LLM</span>' if src == "LLM" else '<span class="badge-lba">LBA</span>'

                competences = offer.get("competences_detectees", [])
                skills_html = ""
                if competences:
                    skills_html = '<div class="skills">' + "".join(
                        f'<span class="skill-tag">{s}</span>' for s in competences
                    ) + "</div>"

                meta_parts = [
                    f"&#127970; {offer.get('entreprise', 'N/A')}",
                    f"&#128205; {offer.get('ville', ville)} {offer.get('code_postal', '')}".strip(),
                    f"&#128197; {offer.get('date_creation', 'N/A')}",
                ]
                if offer.get("date_debut"):
                    meta_parts.append(f"&#128197; D&eacute;but : {offer['date_debut']}")
                if offer.get("duree_contrat"):
                    meta_parts.append(f"&#9201; {offer['duree_contrat']}")
                src_platform = offer.get("plateforme_source", offer.get("source", ""))
                if src_platform:
                    meta_parts.append(f"&#128279; {src_platform}")
                meta_html = " &nbsp;&middot;&nbsp; ".join(meta_parts)
                url = offer.get("url_candidature", "#")

                html += f'            <div class="offer">\n'
                html += f'                <h3>{offer.get("titre", "N/A")}{b_src}{b_new}</h3>\n'
                html += f'                <p class="description">{offer.get("description", "")}</p>\n'
                html += f'                {skills_html}\n'
                html += f'                <div class="meta">{meta_html}</div>\n'
                html += f'                <a class="btn-apply" href="{url}" target="_blank" style="background:{color};">Postuler &#8594;</a>\n'
                html += '            </div>\n'

        html += "        </div>\n    </div>\n\n"

    html += f'    <div class="footer">\n'
    html += f'        <p><a href="{GITHUB_PAGES_URL}" target="_blank">&#128073; Voir les derni&egrave;res offres en ligne</a></p>\n'
    html += f'        <p>Mise &agrave; jour le {now_short} &nbsp;&middot;&nbsp; LBA : {lba_count} &nbsp;&middot;&nbsp; Perplexity : {llm_count}</p>\n'
    html += f'        <p><a href="archives/">&#128218; Historique {RETENTION_DAYS} derniers jours</a></p>\n'
    html += "    </div>\n\n</div>\n\n"

    html += """<script>
document.addEventListener('DOMContentLoaded', function () {
    const chips    = document.querySelectorAll('#track-filters .filter-chip');
    const sections = document.querySelectorAll('.track-section');
    chips.forEach(function (chip) {
        chip.addEventListener('click', function () {
            chips.forEach(function (c) {
                c.classList.remove('active');
                c.style.background  = '';
                c.style.borderColor = '';
                c.style.color       = '';
            });
            chip.classList.add('active');
            var color = chip.getAttribute('data-color') || '#3498db';
            chip.style.background  = color;
            chip.style.borderColor = color;
            chip.style.color       = 'white';
            var key = chip.getAttribute('data-track');
            sections.forEach(function (sec) {
                if (key === 'all' || sec.getAttribute('data-track') === key) {
                    sec.style.display = '';
                } else {
                    sec.style.display = 'none';
                }
            });
        });
    });
});
</script>
</body>
</html>"""

    return html


def send_email(html_content, meta, stats_by_city):
    cleanup_archives()
    with open(OUTPUT_HTML_DOCS, "w", encoding="utf-8") as f:
        f.write(html_content)
    archive_name = f"veille_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html"
    archive_path = ARCHIVES_DIR / archive_name
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    push_ok = git_push_html()
    subject = (
        f"Veille Alternances RSB - {meta.get('nouvelles', 0)} nouvelles offres"
        f" - {datetime.now().strftime('%d/%m/%Y')}"
    )
    msg            = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg["Subject"] = subject
    text = (
        f"Veille Alternances mise a jour !\n\n"
        f"{meta['total_offres']} offres au total ({meta.get('nouvelles', 0)} nouvelles)\n\n"
        f"Repartition :\nRennes : {stats_by_city['Rennes']}\nNantes : {stats_by_city['Nantes']}\nParis  : {stats_by_city['Paris']}\n\n"
        f"Voir les offres : {GITHUB_PAGES_URL}"
    )
    pages_status = "Page en ligne mise a jour" if push_ok else "Page en ligne NON mise a jour (git push echoue)"
    html_body = (
        f'<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">'
        f'<h2 style="color:#2c3e50;">Veille Alternances RSB - Mise a jour</h2>'
        f'<p><strong>{datetime.now().strftime("%d/%m/%Y %H:%M")}</strong></p>'
        f'<ul>'
        f'<li><strong>{meta["total_offres"]} offres</strong> au total</li>'
        f'<li><strong>{meta.get("nouvelles", 0)} nouvelles</strong> offres</li>'
        f'<li>Rennes : {stats_by_city["Rennes"]} | Nantes : {stats_by_city["Nantes"]} | Paris : {stats_by_city["Paris"]}</li>'
        f'</ul>'
        f'<p style="font-size:13px;color:#7f8c8d;">{pages_status}</p>'
        f'<p><a href="{GITHUB_PAGES_URL}" style="display:inline-block;padding:12px 25px;background:#3498db;color:white;text-decoration:none;border-radius:6px;font-weight:bold;font-size:15px;">Voir toutes les offres en ligne</a></p>'
        f'<p style="color:#555;font-size:13px;">Piece jointe : le fichier HTML est joint a cet email.</p>'
        f'<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">'
        f'<p style="color:#aaa;font-size:12px;">Automatisation - {GMAIL_USER}</p>'
        f'</div>'
    )
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text, "plain"))
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)
    from email.mime.base import MIMEBase
    from email import encoders as email_encoders
    pj = MIMEBase("text", "html")
    pj.set_payload(html_content.encode("utf-8"))
    email_encoders.encode_base64(pj)
    pj.add_header("Content-Disposition", "attachment",
                  filename=f"veille_{datetime.now().strftime('%Y-%m-%d')}.html")
    msg.attach(pj)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print(f"Email envoye a {RECIPIENT_EMAIL} (avec piece jointe)")
        print(f"HTML publie : {OUTPUT_HTML_DOCS}")
        print(f"Archive     : {archive_path}")
    except Exception as e:
        print(f"Erreur envoi email : {e}")


if __name__ == "__main__":
    data   = load_offers()
    meta   = data["meta"]
    offers = data["offres"]
    stats_by_city = {
        "Rennes": len([o for o in offers if o.get("ville_recherche") == "Rennes"]),
        "Nantes": len([o for o in offers if o.get("ville_recherche") == "Nantes"]),
        "Paris":  len([o for o in offers if o.get("ville_recherche") == "Paris"]),
    }
    html_content = generate_html(data)
    send_email(html_content, meta, stats_by_city)
    print("Pipeline termine !")
