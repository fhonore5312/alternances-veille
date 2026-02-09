#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        ville = offer.get('ville_recherche', offer.get('ville', 'Autre'))
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
    
    # Stats - CORRECTION ICI avec underscores
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
    <title>Alternances Marketing Digital - {datetime.now().strftime('%d/%m/%Y')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        .header .date {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 40px;
            background: #f8f9fa;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .stat-card .label {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .city-section {{
            padding: 30px 40px;
        }}
        .city-title {{
            font-size: 1.8em;
            color: #2d3748;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        .offer-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .offer-card:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .offer-card.new {{
            border-left-color: #48bb78;
            background: linear-gradient(to right, #f0fff4 0%, #f8f9fa 100%);
        }}
        .offer-card.new::before {{
            content: "🆕 NOUVEAU";
            background: #48bb78;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 10px;
        }}
        .offer-title {{
            font-size: 1.3em;
            color: #2d3748;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .offer-company {{
            font-size: 1.1em;
            color: #667eea;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        .offer-details {{
            color: #4a5568;
            margin: 5px 0;
        }}
        .offer-details strong {{
            color: #2d3748;
        }}
        .apply-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 8px;
            margin-top: 15px;
            font-weight: 600;
            transition: transform 0.2s;
        }}
        .apply-btn:hover {{
            transform: scale(1.05);
        }}
        .footer {{
            background: #2d3748;
            color: white;
            text-align: center;
            padding: 30px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Alternances Marketing Digital</h1>
            <div class="date">Mise à jour : {datetime.now().strftime('%d/%m/%Y à %H:%M')}</div>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="number">{total_offers}</div>
                <div class="label">Offres totales</div>
            </div>
            <div class="stat-card">
                <div class="number">{new_count}</div>
                <div class="label">Nouvelles offres</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats_by_city['Rennes']}</div>
                <div class="label">Rennes</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats_by_city['Nantes']}</div>
                <div class="label">Nantes</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats_by_city['Paris']}</div>
                <div class="label">Paris</div>
            </div>
        </div>
"""
    
    # Sections par ville
    for city in ['Rennes', 'Nantes', 'Paris']:
        if city in offers_by_city:
            html += f"""
        <div class="city-section">
            <h2 class="city-title">📍 {city}</h2>
"""
            for offer in offers_by_city[city]:
                new_class = "new" if offer.get('status') == 'new' else ""
                titre = offer.get('titre', 'Titre non spécifié')
                entreprise = offer.get('entreprise', 'Entreprise non spécifiée')
                ville_offre = offer.get('ville', offer.get('adresse_complete', 'Lieu non spécifié'))
                contrat = offer.get('type_contrat', 'Alternance')
                duree = offer.get('duree_contrat', 'Non spécifiée')
                source = offer.get('source', 'La Bonne Alternance')
                url = offer.get('url_candidature', '#')
                
                html += f"""
            <div class="offer-card {new_class}">
                <div class="offer-title">{titre}</div>
                <div class="offer-company">🏢 {entreprise}</div>
                <div class="offer-details"><strong>📍 Lieu:</strong> {ville_offre}</div>
                <div class="offer-details"><strong>💼 Contrat:</strong> {contrat}</div>
                <div class="offer-details"><strong>📅 Durée:</strong> {duree}</div>
                <div class="offer-details"><strong>🔗 Source:</strong> {source}</div>
                <a href="{url}" class="apply-btn" target="_blank">Postuler maintenant →</a>
            </div>
"""
            html += """
        </div>
"""
    
    # Footer
    html += f"""
        <div class="footer">
            <p>🤖 Généré automatiquement par le robot de veille • {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
            <p>Sources: La Bonne Alternance ({source_lba}) • Perplexity ({source_perplexity})</p>
        </div>
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
    
    # Vérifie si Git est disponible
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
    nb_total = meta['total_offres']  # CORRECTION ICI aussi
    
    # Subject
    if nb_new > 0:
        subject = f"🆕 {nb_new} nouvelles alternances Marketing Digital ({nb_total} au total)"
    else:
        subject = f"📊 Veille Alternances Marketing Digital - {nb_total} offres"
    
    # Corps de l'email (texte simple + lien vers GitHub Pages)
    body = f"""Bonjour,

Voici votre veille quotidienne d'alternances en Marketing Digital.

📊 Statistiques du jour :
• {nb_total} offres au total
• {nb_new} nouvelles offres aujourd'hui

🔗 Consulter les offres :
{GITHUB_PAGES_URL}

Le fichier HTML complet est également disponible en pièce jointe.

---
🤖 Email généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
"""
    
    # Créer le message
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    msg['Subject'] = subject
    
    # Corps texte
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Pièce jointe HTML
    with open(html_filename, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    html_attachment = MIMEText(html_content, 'html', 'utf-8')
    html_attachment.add_header('Content-Disposition', 'attachment', filename=f'alternances_{datetime.now().strftime("%Y%m%d")}.html')
    msg.attach(html_attachment)
    
    # Envoi
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Email envoyé avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email : {e}")
        return False


def main():
    print("=" * 70)
    print("🚀 GÉNÉRATION HTML + ENVOI EMAIL")
    print("=" * 70)
    
    print("\n[1/4] Chargement des données...")
    data = load_offers()
    print(f"✅ {len(data['offres'])} offres chargées")
    
    print("\n[2/4] Génération du HTML...")
    html_path = generate_html(data)
    print(f"✅ HTML sauvegardé : {html_path}")
    
    git_commit_and_push()
    
    print("\n[4/4] Envoi de l'email...")
    send_email(html_path, data)
    
    print("\n✅ TERMINÉ !")


if __name__ == "__main__":
    main()
