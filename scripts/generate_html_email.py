#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import subprocess
import shutil

# ===== CONFIGURATION =====
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

# Fichiers
OFFRES_MERGED = DATA_DIR / "offres_merged.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

# Charge les variables d'environnement
load_dotenv()

# Configuration Gmail
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')

# Vérifie que les variables sont chargées
if not GMAIL_USER or not GMAIL_PASSWORD:
    raise ValueError("❌ Erreur : GMAIL_USER et GMAIL_PASSWORD doivent être définis dans le fichier .env")

GITHUB_PAGES_URL = "https://fhonore5312.github.io/alternances-veille/"


def load_offers():
    """Charge les offres depuis offres_merged.json"""
    with open(OFFRES_MERGED, 'r', encoding='utf-8') as f:
        return json.load(f)


def group_by_city(offers):
    """Regroupe les offres par ville_recherche"""
    grouped = {}
    for offer in offers:
        ville = offer.get('ville_recherche', 'Autre')
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
    <title>Veille Alternances - Marketing Digital</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 25px 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 28px;
        }}
        .header-stats {{
            display: flex;
            gap: 25px;
            margin-top: 15px;
            font-size: 14px;
            color: #666;
            flex-wrap: wrap;
        }}
        .stat-badge {{
            background: #f0f4ff;
            padding: 6px 14px;
            border-radius: 20px;
            color: #667eea;
            font-weight: 600;
        }}
        .stat-new {{
            background: #e74c3c;
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 700;
        }}
        .stat-source {{
            background: #3498db;
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 11px;
        }}
        .city-section {{
            margin-bottom: 35px;
        }}
        .city-header {{
            background: white;
            padding: 18px 30px;
            border-radius: 10px;
            font-size: 20px;
            font-weight: 700;
            color: #2c3e50;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            margin-bottom: 15px;
        }}
        .city-icon {{
            font-size: 24px;
        }}
        .city-rennes {{
            border-left: 5px solid #e74c3c;
        }}
        .city-nantes {{
            border-left: 5px solid #f39c12;
        }}
        .city-paris {{
            border-left: 5px solid #3498db;
        }}
        .offers-container {{
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        }}
        .offer-row {{
            display: grid;
            grid-template-columns: 60px 1fr 160px 160px 110px;
            gap: 25px;
            padding: 22px 30px;
            border-bottom: 1px solid #f0f0f0;
            transition: background 0.2s;
            align-items: start;
        }}
        .offer-row:hover {{
            background: #f8f9ff;
        }}
        .offer-row:last-child {{
            border-bottom: none;
        }}
        .new-badge {{
            background: #e74c3c;
            color: white;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            text-align: center;
            margin-top: 5px;
        }}
        .active-badge {{
            background: #95a5a6;
            color: white;
            padding: 8px 10px;
            border-radius: 50%;
            font-size: 14px;
            text-align: center;
            margin-top: 5px;
            width: 35px;
            height: 35px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .source-tag {{
            display: inline-block;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9px;
            font-weight: 700;
            margin-left: 5px;
        }}
        .source-tag.lba {{
            background: #27ae60;
        }}
        .source-tag.perplexity {{
            background: #9b59b6;
        }}
        .offer-main {{
            min-width: 0;
        }}
        .offer-title {{
            font-size: 16px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 6px;
            line-height: 1.3;
        }}
        .offer-company {{
            font-size: 14px;
            color: #667eea;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .offer-location {{
            font-size: 12px;
            color: #95a5a6;
            margin-bottom: 10px;
        }}
        .offer-description {{
            font-size: 13px;
            color: #555;
            line-height: 1.5;
            margin-bottom: 10px;
        }}
        .offer-skills {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 8px;
        }}
        .skill-badge {{
            background: #e8f5e9;
            color: #27ae60;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 600;
        }}
        .offer-info-box {{
            background: #f8f9fa;
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 12px;
            border: 1px solid #e9ecef;
        }}
        .info-title {{
            font-size: 11px;
            font-weight: 700;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .info-line {{
            margin-bottom: 5px;
            display: flex;
            color: #555;
        }}
        .info-line:last-child {{
            margin-bottom: 0;
        }}
        .info-label {{
            font-weight: 600;
            color: #666;
            min-width: 60px;
        }}
        .offer-action {{
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .btn-postuler {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: background 0.2s;
            white-space: nowrap;
        }}
        .btn-postuler:hover {{
            background: #5568d3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <p style="margin: 5px 0; color: #666;">Bachelor 3 RSB · Début: Septembre 2026 · Durée: 12-24 mois</p>
            <div class="header-stats">
                <span class="stat-new">🆕 {new_count} nouvelles</span>
                <span class="stat-badge">📊 {total_offers} offres actives total</span>
                <span class="stat-source" style="background: #27ae60;">LBA: {meta.get('source_lba', 0)}</span>
                <span class="stat-source" style="background: #9b59b6;">Perplexity: {meta.get('source_perplexity', 0)}</span>
                <span class="stat-badge">📍 Rennes: {stats_by_city['Rennes']} · Nantes: {stats_by_city['Nantes']} · Paris: {stats_by_city['Paris']}</span>
                <span class="stat-badge">🗓️ {meta['date_generation']}</span>
            </div>
        </div>
"""
    
    # Icônes et configurations par ville
    city_icons = {
        'Rennes': ('🎯', 'Priorité #1', 'city-rennes'),
        'Nantes': ('🔶', '', 'city-nantes'),
        'Paris': ('🗼', 'ÎLE-DE-FRANCE', 'city-paris')
    }
    
    # Générer les sections par ville
    for ville_name in ['Rennes', 'Nantes', 'Paris']:
        ville_offers = offers_by_city.get(ville_name, [])
        if not ville_offers:
            continue
        
        icon, subtitle, css_class = city_icons[ville_name]
        
        html += f"""
        <div class="city-section">
            <div class="city-header {css_class}">
                <span class="city-icon">{icon}</span>
                <span>{ville_name.upper()} {subtitle}</span>
                <span style="margin-left: auto; font-size: 15px; font-weight: normal; color: #666;">({len(ville_offers)} offres)</span>
            </div>
            <div class="offers-container">
"""
        
        # Générer les lignes d'offres
        for offer in ville_offers:
            # Badge source
            source_class = "lba" if offer['source'] == "LBA" else "perplexity"
            source_badge = f'<span class="source-tag {source_class}">{offer["source"]}</span>'
            
            # Compétences
            skills_html = ""
            if offer.get('competences_detectees'):
                skills_badges = ''.join([f'<span class="skill-badge">{skill}</span>' for skill in offer['competences_detectees'][:5]])
                skills_html = f'<div class="offer-skills">{skills_badges}</div>'
            
            # Badge statut
            if offer.get('status') == 'new':
                badge_html = '<div class="new-badge">🆕 NEW</div>'
            else:
                badge_html = '<div class="active-badge">✓</div>'
            
            # Dates
            creation_display = offer.get('date_creation') or '—'
            expiration_display = offer.get('date_expiration') or '—'
            start_display = offer.get('date_debut') or '—'
            duration_display = offer.get('duree_contrat') or '—'
            
            html += f"""
                <div class="offer-row">
                    <div style="text-align: center;">
                        {badge_html}
                    </div>
                    <div class="offer-main">
                        <div class="offer-title">{offer['titre']} {source_badge}</div>
                        <div class="offer-company">🏢 {offer['entreprise']}</div>
                        <div class="offer-location">📍 {offer['ville']} ({offer['code_postal']})</div>
                        <div class="offer-description">{offer['description']}</div>
                        {skills_html}
                    </div>
                    <div class="offer-info-box">
                        <div class="info-title">💼 Alternance</div>
                        <div class="info-line">
                            <span class="info-label">Contrat:</span>
                            <span>{offer['type_contrat']}</span>
                        </div>
                        <div class="info-line">
                            <span class="info-label">Durée:</span>
                            <span>{duration_display}</span>
                        </div>
                        <div class="info-line">
                            <span class="info-label">Début:</span>
                            <span>{start_display}</span>
                        </div>
                    </div>
                    <div class="offer-info-box">
                        <div class="info-title">📅 Dates</div>
                        <div class="info-line">
                            <span class="info-label">Créé:</span>
                            <span>{creation_display}</span>
                        </div>
                        <div class="info-line">
                            <span class="info-label">Expire:</span>
                            <span>{expiration_display}</span>
                        </div>
                        <div class="info-line">
                            <span class="info-label">Via:</span>
                            <span>{offer.get('plateforme_source', '—')}</span>
                        </div>
                    </div>
                    <div class="offer-action">
                        <a href="{offer['url_candidature']}" class="btn-postuler" target="_blank">Postuler →</a>
                    </div>
                </div>
"""
        
        html += """
            </div>
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    # Créer le dossier docs s'il n'existe pas
    DOCS_DIR.mkdir(exist_ok=True)
    
    # Sauvegarder
    with open(OUTPUT_HTML_DOCS, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return OUTPUT_HTML_DOCS


def git_commit_and_push():
    """Commit et push sur GitHub (si Git disponible)"""
    git_cmd = shutil.which('git')
    
    if not git_cmd:
        print("\n[3/4] Publication sur GitHub...")
        print("⚠️  Git non disponible - Skip de la publication GitHub")
        print("   (Normal en local Windows, OK dans GitHub Actions)")
        return False
    
    try:
        print("\n[3/4] Publication sur GitHub...")
        subprocess.run([git_cmd, 'add', 'docs/index.html', 'data/'], check=True, cwd=BASE_DIR)
        subprocess.run([git_cmd, 'commit', '-m', f'🤖 Update: {datetime.now().strftime("%Y-%m-%d %H:%M")}'], check=True, cwd=BASE_DIR)
        subprocess.run([git_cmd, 'push'], check=True, cwd=BASE_DIR)
        print("✅ Publié sur GitHub Pages")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Erreur Git (non bloquant) : {e}")
        return False


def send_email(html_filename, data):
    """Envoie l'email avec le HTML en pièce jointe"""
    meta = data['meta']
    nb_new = meta['nouvelles']
    nb_total = meta['total_offres']
    
    # Subject
    if nb_new > 0:
        subject = f"🆕 {nb_new} nouvelles alternances ({nb_total} total) - {datetime.now().strftime('%d/%m/%Y')}"
    else:
        subject = f"📊 Veille alternances ({nb_total} actives) - {datetime.now().strftime('%d/%m/%Y')}"
    
    # Corps email HTML
    body_html = f"""<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            color: #333;
            line-height: 1.6;
        }}
        .summary-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin: 20px 0;
        }}
        .summary-box h2 {{
            margin: 0 0 15px 0;
            font-size: 24px;
        }}
        .stats {{
            display: flex;
            gap: 30px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        .stat-item {{
            background: rgba(255,255,255,0.2);
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
        }}
        .stat-new {{
            background: #e74c3c;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
        }}
        .info-box {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .link-button {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="summary-box">
        <h2>🎯 Veille Alternances Marketing Digital</h2>
        <p style="margin: 5px 0; opacity: 0.9;">Bachelor 3 RSB · Début: Septembre 2026</p>
        <div class="stats">
            <div class="stat-new">{nb_new} NOUVELLES</div>
            <div class="stat-item">{nb_total} offres actives total</div>
            <div class="stat-item">LBA: {meta.get('source_lba', 0)}</div>
            <div class="stat-item">Perplexity: {meta.get('source_perplexity', 0)}</div>
        </div>
    </div>
    
    <div class="info-box">
        <p><strong>📎 Consulter les offres :</strong></p>
        <p style="margin: 15px 0;">
            <a href="{GITHUB_PAGES_URL}" class="link-button">🌐 Voir en ligne sur GitHub Pages →</a>
        </p>
        <p>ou ouvre la <strong>pièce jointe HTML</strong> pour consulter hors ligne.</p>
        <ul>
            <li>Badge <strong style="background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px;">NEW</strong> : Nouvelle offre détectée aujourd'hui</li>
            <li>Badge gris : Offre toujours active (déjà connue)</li>
            <li><span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">LBA</span> : Source API La Bonne Alternance</li>
            <li><span style="background: #9b59b6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">Perplexity</span> : Recherche complémentaire</li>
        </ul>
    </div>
    
    <p style="margin-top: 30px; color: #666; font-size: 13px;">
        📅 Mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
        🤖 Scraper automatique LBA + Recherche Perplexity
    </p>
</body>
</html>
"""
    
    # Construction du message
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    
    # Attacher le corps du mail
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
    
    # Attacher le fichier HTML
    try:
        with open(html_filename, 'rb') as f:
            attachment = MIMEBase('text', 'html')
            attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            
            filename = f'Alternances_Marketing_Digital_{datetime.now().strftime("%Y%m%d")}.html'
            attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(attachment)
    except Exception as e:
        print(f"⚠️ Erreur attachement : {e}")
    
    # Envoi
    try:
        print("Envoi de l'email...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email envoyé : {nb_new} nouvelles, {nb_total} total")
        return True
    except Exception as e:
        print(f"❌ Erreur email : {e}")
        return False


def main():
    print("=" * 60)
    print("🚀 GÉNÉRATION HTML + ENVOI EMAIL")
    print("=" * 60)
    
    # 1. Charger les offres fusionnées
    data = load_offers()
    print(f"\n✅ {data['meta']['total_offres']} offres chargées")
    print(f"🆕 {data['meta']['nouvelles']} nouvelles")
    print(f"📊 Sources : {', '.join(data['meta']['sources'])}")
    
    # 2. Générer HTML
    print("\nGénération du HTML...")
    html_path = generate_html(data)
    print(f"✅ HTML sauvegardé : {html_path}")
    
    # 3. Git commit (si disponible)
    git_commit_and_push()
    
    # 4. Envoyer email
    print("\n[4/4] Envoi de l'email...")
    send_email(html_path, data)
    
    print("\n" + "=" * 60)
    print("✅ PROCESSUS TERMINÉ")
    print(f"📄 Fichier HTML : {html_path}")
    print(f"📧 Email envoyé à : {GMAIL_USER}")
    print("=" * 60)


if __name__ == "__main__":
    main()
