#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération HTML et envoi d'email
Pipeline : scraper_lba.py → validator.py → merge_offers.py → generate_html_email.py
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

# ===== CONFIGURATION =====

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
    raise ValueError("❌ GMAIL_USER et GMAIL_PASSWORD doivent être définis dans .env")

GITHUB_PAGES_URL = "https://fhonore5312.github.io/alternances-veille/"
RETENTION_DAYS   = 30


# ===== CHARGEMENT =====

def load_offers():
    with open(OFFRES_MERGED, "r", encoding="utf-8") as f:
        return json.load(f)


# ===== GIT PUSH =====

def git_push_html():
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if not result.stdout.strip():
            print("ℹ️ GitHub Pages : rien à commiter")
            return True

        subprocess.run(["git", "add", "docs/"], check=True, cwd=BASE_DIR)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore: mise à jour veille {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True, cwd=BASE_DIR
        )
        # ✅ Push explicite sur main
        subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            check=True, cwd=BASE_DIR
        )
        print("🚀 GitHub Pages mis à jour avec succès (main)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Git push ÉCHOUÉ : {e}")
        return False


# ===== ARCHIVAGE =====

def cleanup_archives():
    now = datetime.now()
    for archive in ARCHIVES_DIR.glob("*.html"):
        try:
            mtime = datetime.fromtimestamp(archive.stat().st_mtime)
            if (now - mtime).days > RETENTION_DAYS:
                archive.unlink()
                print(f"🗑️ Archive supprimée : {archive.name}")
        except Exception:
            pass


# ===== GÉNÉRATION HTML =====

def generate_html(data):
    offers     = data["offres"]
    meta       = data["meta"]
    tracks_cfg = load_tracks()

    total_offers      = meta["total_offres"]
    new_count         = meta.get("nouvelles", 0)
    lba_count         = meta.get("source_lba", 0)
    perplexity_count  = meta.get("source_perplexity", 0)
    stats_by_track    = meta.get("stats_by_track", {})

    stats_by_city = {
        "Rennes": len([o for o in offers if o.get("ville_recherche") == "Rennes"]),
        "Nantes": len([o for o in offers if o.get("ville_recherche") == "Nantes"]),
        "Paris":  len([o for o in offers if o.get("ville_recherche") == "Paris"]),
    }

    # Tracks présents dans les données (dans l'ordre du yml)
    tracks_in_data = [k for k in tracks_cfg if any(
        o.get("track", "digital_marketing") == k for o in offers
    )]

    # ===== HTML / CSS =====
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Veille Alternances RSB — {datetime.now().strftime('%d/%m/%Y')}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px;
            background: #f8f9fa; color: #2c3e50; line-height: 1.6;
        }}
        .container {{ max-width: 920px; margin: 0 auto; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white; padding: 28px 30px; border-radius: 10px;
            margin-bottom: 20px; text-align: center;
        }}
        .header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
        .header p  {{ margin: 3px 0; opacity: 0.9; font-size: 13px; }}

        /* Stats */
        .stats-bar {{
            display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px;
        }}
        .stat {{
            background: white; border-radius: 8px; padding: 10px 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.07);
            text-align: center; flex: 1; min-width: 75px;
        }}
        .stat strong {{ display: block; font-size: 20px; color: #2c3e50; }}
        .stat span   {{ font-size: 11px; color: #7f8c8d; }}

        /* Filtre par track */
        .filter-bar {{
            display: flex; flex-wrap: wrap; gap: 8px;
            margin-bottom: 22px; align-items: center;
        }}
        .filter-bar label {{
            font-size: 12px; color: #7f8c8d; margin-right: 4px;
        }}
        .filter-chip {{
            padding: 5px 13px; border-radius: 14px;
            border: 1.5px solid #ddd; background: #fff;
            font-size: 12px; cursor: pointer;
            transition: all 0.15s ease;
            user-select: none;
        }}
        .filter-chip:hover  {{ border-color: #3498db; color: #3498db; }}
        .filter-chip.active {{
            color: white; border-color: transparent;
        }}

        /* Sections Track */
        .track-section {{
            margin-bottom: 28px; background: white;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            overflow: hidden;
        }}
        .track-header {{
            padding: 13px 20px; color: white;
            font-size: 17px; font-weight: bold;
        }}
        .track-body {{ padding: 0 20px 15px 20px; }}

        /* Sections Ville */
        .city-header {{
            font-size: 14px; font-weight: bold; color: #555;
            padding: 14px 0 7px 0;
            border-bottom: 2px solid #eee; margin-bottom: 10px;
        }}

        /* Offres */
        .offer {{
            padding: 13px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .offer:last-child {{ border-bottom: none; }}
        .offer h3 {{
            margin: 0 0 4px 0; font-size: 14px; color: #2c3e50;
        }}
        .badge-new {{
            background: #27ae60; color: white;
            font-size: 10px; padding: 2px 7px;
            border-radius: 10px; margin-left: 7px;
            font-weight: normal; vertical-align: middle;
        }}
        .description {{
            font-size: 13px; color: #555; margin: 4px 0 7px 0;
        }}
        .skills {{ margin-bottom: 7px; }}
        .skill-tag {{
            display: inline-block;
            background: #eef2ff; color: #3498db;
            font-size: 11px; padding: 2px 8px;
            border-radius: 10px; margin: 2px 3px 2px 0;
        }}
        .meta {{
            font-size: 11px; color: #95a5a6; margin-bottom: 7px;
        }}
        .btn-apply {{
            display: inline-block; padding: 5px 13px;
            color: white; text-decoration: none;
            border-radius: 5px; font-size: 12px; font-weight: bold;
        }}

        /* Footer */
        .footer {{
            text-align: center; padding: 18px;
            background: white; border-radius: 10px;
            margin-top: 18px; font-size: 12px; color: #7f8c8d;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        }}
        .footer a {{ color: #3498db; text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>🎓 Veille Alternances · Rennes School of Business PGE</h1>
        <p><strong>{datetime.now().strftime('%A %d %B %Y — %H:%M')}</strong></p>
        <p>Bachelor 3 RSB · Début : Septembre 2026 · Durée : 12-24 mois</p>
    </div>

    <div class="stats-bar">
        <div class="stat"><strong>{total_offers}</strong><span>Total</span></div>
        <div class="stat"><strong>{new_count}</strong><span>🆕 Nouvelles</span></div>
        <div class="stat"><strong>{stats_by_city['Rennes']}</strong><span>🏰 Rennes</span></div>
        <div class="stat"><strong>{stats_by_city['Nantes']}</strong><span>⚓ Nantes</span></div>
        <div class="stat"><strong>{stats_by_city['Paris']}</strong><span>🗼 Paris</span></div>
        <div class="stat"><strong>{lba_count}</strong><span>LBA</span></div>
        <div class="stat"><strong>{perplexity_count}</strong><span>Perplexity</span></div>
    </div>

    <div class="filter-bar" id="track-filters">
        <label>Filtrer :</label>
        <div class="filter-chip active" data-track="all"
             style="background:#3498db;border-color:#3498db;">
            Tous ({total_offers})
        </div>
"""

    # Chips de filtre dynamiques selon les tracks présents
    for track_key in tracks_in_data:
        cfg   = tracks_cfg[track_key]
        color = cfg.get("color_hex", "#3498db")
        count = stats_by_track.get(track_key, {}).get("total",
                len([o for o in offers if o.get("track") == track_key]))
        html += f"""        <div class="filter-chip" data-track="{track_key}"
             data-color="{color}">
            {cfg['label']} ({count})
        </div>
"""

    html += "    </div>\n\n"

    # ===== SECTIONS PAR TRACK =====
    for track_key in tracks_in_data:
        cfg          = tracks_cfg[track_key]
        color        = cfg.get("color_hex", "#3498db")
        track_offers = [o for o in offers if o.get("track", "digital_marketing") == track_key]

        if not track_offers:
            continue

        t_new = len([o for o in track_offers if o.get("status") == "new"])
        badge_new = f' <span style="font-size:12px;font-weight:normal;">({t_new} nouvelles)</span>' if t_new else ""

        html += f"""    <div class="track-section" data-track="{track_key}">
        <div class="track-header" style="background:{color};">
            🎯 {cfg['label']} &nbsp;·&nbsp; {len(track_offers)} offres{badge_new}
        </div>
        <div class="track-body">
"""

        for ville, emoji in [("Rennes", "🏰"), ("Nantes", "⚓"), ("Paris", "🗼")]:
            city_offers = [o for o in track_offers if o.get("ville_recherche") == ville]
            if not city_offers:
                continue

            priority = city_offers[0].get("priorite_ville", "?")
            html += f"""            <div class="city-header">{emoji} {ville} · Priorité #{priority} · {len(city_offers)} offre(s)</div>
"""
            for offer in sorted(city_offers, key=lambda x: (0 if x.get("status") == "new" else 1)):
                is_new    = offer.get("status") == "new"
                badge     = '<span class="badge-new">🆕 NOUVELLE</span>' if is_new else ""
                competences = offer.get("competences_detectees", [])
                skills_html = ""
                if competences:
                    skills_html = '<div class="skills">' + "".join(
                        f'<span class="skill-tag">{s}</span>' for s in competences
                    ) + "</div>"

                meta_parts = [
                    f"🏢 {offer.get('entreprise', 'N/A')}",
                    f"📍 {offer.get('ville', ville)} {offer.get('code_postal', '')}".strip(),
                    f"📅 {offer.get('date_creation', 'N/A')}",
                ]
                if offer.get("date_debut"):
                    meta_parts.append(f"🗓️ Début : {offer['date_debut']}")
                if offer.get("duree_contrat"):
                    meta_parts.append(f"⏱️ {offer['duree_contrat']}")
                source = offer.get("plateforme_source", offer.get("source", ""))
                if source:
                    meta_parts.append(f"🔗 {source}")

                meta_html = " &nbsp;·&nbsp; ".join(meta_parts)
                url = offer.get("url_candidature", "#")

                html += f"""            <div class="offer">
                <h3>{offer.get('titre', 'N/A')} {badge}</h3>
                <p class="description">{offer.get('description', '')}</p>
                {skills_html}
                <div class="meta">{meta_html}</div>
                <a class="btn-apply" href="{url}" target="_blank"
                   style="background:{color};">Postuler →</a>
            </div>
"""

        html += "        </div>\n    </div>\n\n"

    # ===== FOOTER =====
    html += f"""    <div class="footer">
        <p>
            <a href="{GITHUB_PAGES_URL}" target="_blank">
                👉 Voir les dernières offres en ligne
            </a>
        </p>
        <p>
            Mise à jour le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
            &nbsp;·&nbsp; LBA : {lba_count}
            &nbsp;·&nbsp; Perplexity : {perplexity_count}
        </p>
        <p><a href="archives/">📚 Historique {RETENTION_DAYS} derniers jours</a></p>
    </div>

</div>

<script>
document.addEventListener('DOMContentLoaded', function () {{
    const chips    = document.querySelectorAll('#track-filters .filter-chip');
    const sections = document.querySelectorAll('.track-section');

    chips.forEach(function (chip) {{
        chip.addEventListener('click', function () {{
            // Mettre à jour les chips
            chips.forEach(function (c) {{
                c.classList.remove('active');
                c.style.background  = '';
                c.style.borderColor = '';
                c.style.color       = '';
            }});
            chip.classList.add('active');
            var color = chip.getAttribute('data-color') || '#3498db';
            chip.style.background  = color;
            chip.style.borderColor = color;
            chip.style.color       = 'white';

            // Afficher/masquer les sections
            var key = chip.getAttribute('data-track');
            sections.forEach(function (sec) {{
                if (key === 'all' || sec.getAttribute('data-track') === key) {{
                    sec.style.display = '';
                }} else {{
                    sec.style.display = 'none';
                }}
            }});
        }});
    }});
}});
</script>

</body>
</html>"""

    return html


# ===== ENVOI EMAIL =====

def send_email(html_content, meta, stats_by_city):
    cleanup_archives()

    # Sauvegarder HTML principal
    with open(OUTPUT_HTML_DOCS, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Archive datée
    archive_name = f"veille_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.html"
    archive_path = ARCHIVES_DIR / archive_name
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Git push
    push_ok = git_push_html()

    subject = (
        f"🔍 Veille Alternances RSB — {meta.get('nouvelles', 0)} nouvelles offres"
        f" — {datetime.now().strftime('%d/%m/%Y')}"
    )

    msg            = MIMEMultipart("mixed")   # ← "mixed" pour supporter les PJ
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg["Subject"] = subject

    # Corps texte
    text = f"""Veille Alternances mise à jour !

{meta['total_offres']} offres au total ({meta.get('nouvelles', 0)} nouvelles)

Répartition :
🏰 Rennes : {stats_by_city['Rennes']}
⚓ Nantes  : {stats_by_city['Nantes']}
🗼 Paris   : {stats_by_city['Paris']}

Voir les offres en ligne : {GITHUB_PAGES_URL}
(Ou ouvrir la pièce jointe HTML ci-dessous)
"""

    pages_status = (
        "✅ Page en ligne mise à jour" if push_ok
        else "⚠️ Page en ligne NON mise à jour (git push échoué)"
    )

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
    <h2 style="color:#2c3e50;">🎓 Veille Alternances RSB — Mise à jour</h2>
    <p><strong>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong></p>
    <ul>
        <li><strong>{meta['total_offres']} offres</strong> au total</li>
        <li><strong>{meta.get('nouvelles', 0)} nouvelles</strong> offres</li>
        <li>
            🏰 Rennes : {stats_by_city['Rennes']} &nbsp;|&nbsp;
            ⚓ Nantes : {stats_by_city['Nantes']} &nbsp;|&nbsp;
            🗼 Paris : {stats_by_city['Paris']}
        </li>
    </ul>
    <p style="font-size:13px;color:#7f8c8d;">{pages_status}</p>
    <p>
        <a href="{GITHUB_PAGES_URL}"
           style="display:inline-block;padding:12px 25px;background:#3498db;
                  color:white;text-decoration:none;border-radius:6px;
                  font-weight:bold;font-size:15px;">
            👉 Voir toutes les offres en ligne
        </a>
    </p>
    <p style="color:#555;font-size:13px;">
        💡 <strong>Pièce jointe</strong> : le fichier HTML est joint à cet email
        pour consultation hors ligne ou si la page n'est pas à jour.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="color:#aaa;font-size:12px;">Automatisation — {GMAIL_USER}</p>
</div>
"""

    # Partie alternative (texte + HTML)
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text, "plain"))
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)

    # ✅ Pièce jointe HTML
    from email.mime.base import MIMEBase
    from email import encoders as email_encoders
    pj = MIMEBase("text", "html")
    pj.set_payload(html_content.encode("utf-8"))
    email_encoders.encode_base64(pj)
    pj.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"veille_{datetime.now().strftime('%Y-%m-%d')}.html"
    )
    msg.attach(pj)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print(f"✅ Email envoyé à {RECIPIENT_EMAIL} (avec pièce jointe)")
        print(f"📄 HTML publié  : {OUTPUT_HTML_DOCS}")
        print(f"📚 Archive      : {archive_path}")
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")



# ===== MAIN =====

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
    print("🎉 Pipeline terminé !")
