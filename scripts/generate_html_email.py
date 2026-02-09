#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import subprocess

# ===== CONFIGURATION =====
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

# Fichiers
OFFRES_MERGED = DATA_DIR / "offres_merged.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

# Email
GMAIL_USER = os.getenv('GMAIL_USER', 'fhonore5312@gmail.com')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD') 
GITHUB_PAGES_URL = "https://fhonore5312.github.io/alternances-veille/"

def load_offers():
    """Charge les offres depuis offres_merged.json"""
    with open(OFFRES_MERGED, 'r', encoding='utf-8') as f:
        return json.load(f)

def group_by_city(offers):
    """Regroupe les offres par ville"""
    grouped = {}
    for offer in offers:
        ville = offer['ville_recherche']
        if ville not in grouped:
            grouped[ville] = []
        grouped[ville].append(offer)
    return grouped

def generate_html(data):
    """Génère le HTML à partir du JSON fusionné"""
    offers = data['offres']
    meta = data['meta']

    # Regrouper par ville
    offers_by_city = group_by_city(offers)

    # Stats
    total_offers = meta['total_offres']
    new_count = meta['nouvelles']
    source_lba = meta.get('source_lba', 0)
    source_perplexity = meta.get('source_perplexity', 0)

    stats_by_city = {
        'Rennes': len(offers_by_city.get('Rennes', [])),
        'Nantes': len(offers_by_city.get('Nantes', [])),
        'Paris': len(offers_by_city.get('Paris', []))
    }

    # Header HTML
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Veille Alternances Marketing Digital</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: white;
            padding: 30px 40px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .header h1 {{ font-size: 32px; color: #2c3e50; margin-bottom: 8px; }}
        .header-subtitle {{ color: #7f8c8d; font-size: 15px; margin-bottom: 20px; }}
        .header-stats {{ display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }}
        .stat-badge {{
            background: #ecf0f1;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            color: #2c3e50;
            font-weight: 600;
        }}
        .stat-new {{ background: #e74c3c; color: white; }}
        .stat-source {{ background: #3498db; color: white; }}
        .stat-city {{ background: #95a5a6; color: white; }}
        .city-section {{ margin-bottom: 30px; }}
        .city-header {{
            background: white;
            padding: 18px 30px;
            border-radius: 10px 10px 0 0;
            font-size: 18px;
            font-weight: 700;
            color: #2c3e50;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .city-rennes {{ border-left: 6px solid #e74c3c; }}
        .city-nantes {{ border-left: 6px solid #f39c12; }}
        .city-paris {{ border-left: 6px solid #3498db; }}
        .city-count {{ margin-left: auto; font-weight: normal; color: #7f8c8d; font-size: 15px; }}
        .offers-container {{
            background: white;
            border-radius: 0 0 10px 10px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .offer-row {{
            display: grid;
            grid-template-columns: 70px 1fr 180px 180px 120px;
            gap: 25px;
            padding: 25px 30px;
            border-bottom: 1px solid #ecf0f1;
            transition: background 0.2s;
            align-items: start;
        }}
        .offer-row:hover {{ background: #f8f9fa; }}
        .offer-row:last-child {{ border-bottom: none; }}
        .status-col {{ text-align: center; }}
        .new-badge {{
            background: #e74c3c;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
            margin-top: 5px;
        }}
        .active-badge {{
            background: #95a5a6;
            color: white;
            padding: 8px;
            border-radius: 50%;
            font-size: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            margin-top: 5px;
        }}
        .offer-main {{ min-width: 0; }}
        .offer-title {{ font-size: 17px; font-weight: 700; color: #2c3e50; margin-bottom: 8px; line-height: 1.4; }}
        .offer-source {{ font-size: 11px; color: #95a5a6; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; letter-spacing: 0.5px; }}
        .offer-company {{ font-size: 15px; color: #667eea; font-weight: 600; margin-bottom: 5px; }}
        .offer-location {{ font-size: 13px; color: #95a5a6; margin-bottom: 12px; }}
        .offer-description {{ font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 12px; }}
        .offer-skills {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
        .skill-badge {{ background: #e8f5e9; color: #27ae60; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
        .offer-info-box {{ background: #f8f9fa; padding: 14px 16px; border-radius: 8px; font-size: 13px; border: 1px solid #e9ecef; }}
        .info-title {{ font-size: 11px; font-weight: 700; color: #95a5a6; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px; }}
        .info-line {{ margin-bottom: 6px; color: #555; line-height: 1.5; }}
        .info-line:last-child {{ margin-bottom: 0; }}
        .info-label {{ font-weight: 600; color: #666; display: inline-block; min-width: 65px; }}
        .offer-action {{ text-align: center; display: flex; align-items: center; justify-content: center; }}
        .btn-postuler {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .btn-postuler:hover {{ background: #5568d3; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(102,126,234,0.3); }}
        @media (max-width: 1200px) {{
            .offer-row {{ grid-template-columns: 60px 1fr 150px 150px 100px; gap: 15px; padding: 20px; }}
        }}
        @media (max-width: 768px) {{
            .offer-row {{ grid-template-columns: 1fr; gap: 15px; }}
            .status-col, .offer-action {{ text-align: left; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <div class="header-subtitle">Bachelor 3 RSB · Début: Septembre 2026 · Durée: 12-24 mois</div>
            <div class="header-stats">
                <span class="stat-badge stat-new">🆕 {new_count} nouvelles</span>
                <span class="stat-badge">📊 {total_offers} offres actives total</span>
                <span class="stat-badge stat-source">LBA: {source_lba}</span>
                <span class="stat-badge stat-source">Perplexity: {source_perplexity}</span>
                <span class="stat-badge stat-city">📍 Rennes: {stats_by_city['Rennes']} · Nantes: {stats_by_city['Nantes']} · Paris: {stats_by_city['Paris']}</span>
                <span class="stat-badge">📅 {meta['date_generation']}</span>
            </div>
        </div>
"""

    # Ordre des villes
    city_order = [
        ('Rennes', 'city-rennes', 'Priorité #1'),
        ('Nantes', 'city-nantes', ''),
        ('Paris', 'city-paris', '🏙️')
    ]

    for city_name, city_class, city_subtitle in city_order:
        city_offers = offers_by_city.get(city_name, [])
        if not city_offers:
            continue

        subtitle_text = f" {city_subtitle}" if city_subtitle else ""

        html += f"""
        <div class="city-section">
            <div class="city-header {city_class}">
                <span>{city_name.upper()}{subtitle_text}</span>
                <span class="city-count">({len(city_offers)} offres)</span>
            </div>
            <div class="offers-container">
"""

        for offer in city_offers:
            source = offer.get('source', 'LBA')
            status = offer.get('status', 'active')
            titre = offer.get('titre', 'Sans titre')
            entreprise = offer.get('entreprise', 'N/A')
            ville = offer.get('ville', '')
            code_postal = offer.get('code_postal', '')
            adresse = offer.get('adresse_complete', f"{ville} ({code_postal})")
            description = offer.get('description', '')
            if len(description) > 200:
                description = description[:200] + '...'
            competences = offer.get('competences_detectees', [])
            url = offer.get('url_candidature', '#')
            type_contrat = offer.get('type_contrat', 'Alternance')
            duree = offer.get('duree_contrat', '')
            date_debut = offer.get('date_debut', '')
            date_creation = offer.get('date_creation', '')
            date_expiration = offer.get('date_expiration', '')
            plateforme = offer.get('plateforme_source', 'LBA')

            # Badge status
            if status == 'new':
                status_html = '<div class="new-badge">🆕 NEW</div>'
            else:
                status_html = '<div class="active-badge">✓</div>'

            # Compétences (max 5)
            skills_html = ''.join([f'<span class="skill-badge">{c}</span>' for c in competences[:5]])

            html += f"""
                <div class="offer-row">
                    <div class="status-col">{status_html}</div>
                    <div class="offer-main">
                        <div class="offer-title">{titre}</div>
                        <div class="offer-source">{source}</div>
                        <div class="offer-company">🏢 {entreprise}</div>
                        <div class="offer-location">📍 {adresse}</div>
                        <div class="offer-description">{description}</div>
                        <div class="offer-skills">{skills_html}</div>
                    </div>
                    <div class="offer-info-box">
                        <div class="info-title">📋 Alternance</div>
                        <div class="info-line"><span class="info-label">Contrat:</span> {type_contrat[:30]}</div>
                        <div class="info-line"><span class="info-label">Durée:</span> {duree if duree else '-'}</div>
                        <div class="info-line"><span class="info-label">Début:</span> {date_debut if date_debut else '-'}</div>
                    </div>
                    <div class="offer-info-box">
                        <div class="info-title">📅 Source</div>
                        <div class="info-line"><span class="info-label">Créée:</span> {date_creation if date_creation else '-'}</div>
                        <div class="info-line"><span class="info-label">Expire:</span> {date_expiration if date_expiration else '-'}</div>
                        <div class="info-line"><span class="info-label">Via:</span> {plateforme[:20]}</div>
                    </div>
                    <div class="offer-action">
                        <a href="{url}" class="btn-postuler" target="_blank">Postuler →</a>
                    </div>
                </div>
"""

        html += """            </div>
        </div>
"""

    html += """    </div>
</body>
</html>"""

    return html

def save_html_to_docs(html_content):
    """Sauvegarde le HTML dans docs/index.html"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML_DOCS, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ HTML sauvegardé : {OUTPUT_HTML_DOCS}")

def git_commit_and_push():
    """Commit et push automatique vers GitHub"""
    try:
        os.chdir(BASE_DIR)

        # Git add
        subprocess.run(['git', 'add', 'docs/index.html', 'data/'], check=True)

        # Git commit
        commit_message = f"Update veille alternances - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = subprocess.run(['git', 'commit', '-m', commit_message], 
                              capture_output=True, text=True)

        if "nothing to commit" in result.stdout:
            print("ℹ️  Aucun changement à commiter")
            return False

        # Git push
        subprocess.run(['git', 'push'], check=True)
        print("✅ Push sur GitHub réussi")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur Git: {e}")
        return False

def send_email(data):
    """Envoie l'email avec le lien GitHub Pages"""

    meta = data.get('meta', {})
    nouvelles = meta.get('nouvelles', 0)
    total = meta.get('total_offres', 0)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"🔍 Veille Alternances - {nouvelles} nouvelles offres - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER

    text_body = f"""
Veille Alternances Marketing Digital
=====================================

📊 Statistiques :
• {nouvelles} nouvelles offres
• {total} offres actives total

🔗 Voir toutes les offres :
{GITHUB_PAGES_URL}

Généré le {meta.get('date_generation', 'N/A')}
"""

    html_body = f"""<html>
<body style="font-family: Arial; background: #f4f4f4; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center;">
            <h1 style="margin: 0;">🔍 Veille Alternances</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Marketing Digital • Bachelor 3 RSB</p>
        </div>
        <div style="padding: 30px;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                <div style="margin-bottom: 12px;">
                    <strong style="color: #e74c3c; font-size: 24px;">{nouvelles}</strong> 
                    <span style="color: #555;">nouvelles offres</span>
                </div>
                <div style="color: #555;"><strong>{total}</strong> offres actives au total</div>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{GITHUB_PAGES_URL}" 
                   style="display: inline-block; background: #667eea; color: white; padding: 15px 40px; 
                          border-radius: 6px; text-decoration: none; font-weight: 600;">
                    📊 Voir toutes les offres
                </a>
            </div>
            <div style="color: #95a5a6; font-size: 13px; text-align: center; margin-top: 25px; 
                        padding-top: 20px; border-top: 1px solid #ecf0f1;">
                Généré le {meta.get('date_generation', 'N/A')}<br>
                Mise à jour quotidienne automatique
            </div>
        </div>
    </div>
</body>
</html>"""

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email envoyé")
    except Exception as e:
        print(f"❌ Erreur email: {e}")

def main():
    """Fonction principale"""
    print("=" * 70)
    print("🚀 GÉNÉRATION HTML + PUBLICATION GITHUB PAGES")
    print("=" * 70)

    print("\n[1/4] Chargement des données...")
    data = load_offers()
    print(f"✅ {len(data.get('offres', []))} offres chargées")

    print("\n[2/4] Génération du HTML...")
    html_content = generate_html(data)
    save_html_to_docs(html_content)

    print("\n[3/4] Publication sur GitHub...")
    pushed = git_commit_and_push()
    if pushed:
        print(f"✅ Site accessible : {GITHUB_PAGES_URL}")

    print("\n[4/4] Envoi de l'email...")
    send_email(data)

    print("\n" + "=" * 70)
    print("✅ PROCESSUS TERMINÉ !")
    print("=" * 70)

if __name__ == "__main__":
    main()
