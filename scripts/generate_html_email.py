#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime, timedelta
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
ARCHIVES_DIR = DOCS_DIR / "archives"

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
RETENTION_DAYS = 30  # Conserver 30 jours d'archives


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
    <title>🎯 Veille Alternances Marketing Digital</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* Header */
        .header {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            color: #2c3e50;
            font-size: 32px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .header-subtitle {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        
        /* Stats */
        .stats {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            padding: 15px 25px;
            border-radius: 10px;
            flex: 1;
            min-width: 140px;
            text-align: center;
        }}
        
        .stat-card.highlight {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .stat-card.highlight .stat-number {{
            color: white;
        }}
        
        .stat-number {{
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
            display: block;
        }}
        
        .stat-label {{
            font-size: 13px;
            color: #7f8c8d;
            margin-top: 5px;
        }}
        
        .stat-card.highlight .stat-label {{
            color: white;
            opacity: 0.95;
        }}
        
        /* City sections */
        .city-section {{
            background: white;
            border-radius: 15px;
            margin-bottom: 25px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        
        .city-header {{
            padding: 20px 30px;
            color: white;
            font-size: 22px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .city-header.rennes {{
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        }}
        
        .city-header.nantes {{
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        }}
        
        .city-header.paris {{
            background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        }}
        
        /* Offer cards */
        .offer-card {{
            border-bottom: 1px solid #ecf0f1;
            padding: 25px 30px;
            transition: all 0.3s ease;
        }}
        
        .offer-card:last-child {{
            border-bottom: none;
        }}
        
        .offer-card:hover {{
            background: #f8f9fa;
            transform: translateX(5px);
        }}
        
        .offer-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        
        .offer-title {{
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }}
        
        .offer-company {{
            color: #7f8c8d;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .offer-badges {{
            display: flex;
            gap: 8px;
            flex-shrink: 0;
        }}
        
        .badge {{
            padding: 5px 12px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .badge.new {{
            background: #e74c3c;
            color: white;
        }}
        
        .badge.active {{
            background: #95a5a6;
            color: white;
        }}
        
        .badge.lba {{
            background: #3498db;
            color: white;
        }}
        
        .badge.perplexity {{
            background: #9b59b6;
            color: white;
        }}
        
        .offer-description {{
            color: #555;
            line-height: 1.6;
            margin-bottom: 15px;
            font-size: 14px;
        }}
        
        .offer-skills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 15px;
        }}
        
        .skill-tag {{
            background: #d4edda;
            color: #155724;
            padding: 5px 12px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .offer-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .detail-group {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
        }}
        
        .detail-title {{
            font-weight: bold;
            color: #667eea;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        
        .detail-content {{
            color: #2c3e50;
            font-size: 13px;
        }}
        
        .offer-actions {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .btn-apply {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 25px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            font-size: 14px;
            transition: all 0.3s ease;
            display: inline-block;
        }}
        
        .btn-apply:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            color: white;
            padding: 30px;
            font-size: 14px;
        }}
        
        .footer-timestamp {{
            font-size: 12px;
            opacity: 0.9;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <p class="header-subtitle">Bachelor 3 RSB · Début: Septembre 2026 · Durée: 12-24 mois</p>
            
            <div class="stats">
                <div class="stat-card highlight">
                    <span class="stat-number">🆕 {new_count}</span>
                    <div class="stat-label">nouvelles</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number">📊 {total_offers}</span>
                    <div class="stat-label">offres actives total</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number">LBA: {meta.get('source_lba', 0)}</span>
                    <div class="stat-label">La Bonne Alternance</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number">Perplexity: {meta.get('source_perplexity', 0)}</span>
                    <div class="stat-label">Recherche complémentaire</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number">📍 Rennes: {stats_by_city['Rennes']}</span>
                    <div class="stat-label">· Nantes: {stats_by_city['Nantes']} · Paris: {stats_by_city['Paris']}</div>
                </div>
            </div>
        </div>
"""
    
    # Ordre de priorité des villes
    city_priority = ['Rennes', 'Nantes', 'Paris']
    city_classes = {
        'Rennes': 'rennes',
        'Nantes': 'nantes',
        'Paris': 'paris'
    }
    
    # Générer les sections par ville
    for city in city_priority:
        if city not in offers_by_city:
            continue
        
        city_offers = offers_by_city[city]
        city_class = city_classes.get(city, '')
        
        html += f"""
        <!-- {city} Section -->
        <div class="city-section">
            <div class="city-header {city_class}">
                🎯 {city} Priorité #{city_priority.index(city) + 1} ({len(city_offers)} offres)
            </div>
"""
        
        for offer in city_offers:
            # Extraction des données
            status = offer.get('status', 'active')
            source = offer.get('source', 'LBA')
            titre = offer.get('titre', 'Sans titre')
            entreprise = offer.get('entreprise', 'Non précisé')
            ville = offer.get('ville', city)
            description = offer.get('description', 'Pas de description disponible')
            competences = offer.get('competences', [])
            contrat = offer.get('type_contrat', 'Apprentissage')
            duree = offer.get('duree_contrat', '12 mois')
            debut = offer.get('debut', 'Septembre 2026')
            date_creation = offer.get('date_creation', '—')
            date_expiration = offer.get('date_expiration', '—')
            via = offer.get('via', 'ISME')
            url_candidature = offer.get('url_candidature', '#')
            
            # Badges
            badge_status = f'<span class="badge new">🆕 NEW</span>' if status == 'new' else '<span class="badge active">Active</span>'
            badge_source = f'<span class="badge {"lba" if source == "LBA" else "perplexity"}">{source}</span>'
            
            # Compétences
            skills_html = ""
            if competences:
                skills_html = '<div class="offer-skills">'
                for skill in competences:
                    skills_html += f'<span class="skill-tag">{skill}</span>'
                skills_html += '</div>'
            
            html += f"""
            <div class="offer-card">
                <div class="offer-header">
                    <div>
                        <div class="offer-title">{titre}</div>
                        <div class="offer-company">🏢 {entreprise} · 📍 {ville}</div>
                    </div>
                    <div class="offer-badges">
                        {badge_status}
                        {badge_source}
                    </div>
                </div>
                
                <div class="offer-description">
                    {description}
                </div>
                
                {skills_html}
                
                <div class="offer-details">
                    <div class="detail-group">
                        <div class="detail-title">📋 ALTERNANCE</div>
                        <div class="detail-content">
                            Contrat: {contrat}<br>
                            Durée: {duree}<br>
                            Début: {debut}
                        </div>
                    </div>
                    <div class="detail-group">
                        <div class="detail-title">🔍 SOURCE</div>
                        <div class="detail-content">
                            Créée: {date_creation}<br>
                            Expire: {date_expiration}<br>
                            Via: {via}
                        </div>
                    </div>
                </div>
                
                <div class="offer-actions">
                    <a href="{url_candidature}" target="_blank" class="btn-apply">Postuler →</a>
                </div>
            </div>
"""
        
        html += """
        </div>
"""
    
    # Footer
    html += f"""
        <div class="footer">
            <div>📅 Mise à jour : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="footer-timestamp">🤖 Scraper automatique LBA + Recherche Perplexity</div>
        </div>
    </div>
</body>
</html>
"""
    
    return html


def cleanup_old_archives():
    """Supprime les archives de plus de RETENTION_DAYS jours"""
    if not ARCHIVES_DIR.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    
    for archive_file in ARCHIVES_DIR.glob("*.html"):
        try:
            # Format attendu : YYYY-MM-DD.html
            file_date_str = archive_file.stem
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d')
            
            if file_date < cutoff_date:
                archive_file.unlink()
                deleted_count += 1
                print(f"  🗑️  Archive supprimée : {archive_file.name}")
        except ValueError:
            continue
    
    if deleted_count > 0:
        print(f"✅ {deleted_count} archive(s) supprimée(s) (> {RETENTION_DAYS} jours)")


def generate_historique_page():
    """Génère la page historique.html listant toutes les archives"""
    archives = sorted(ARCHIVES_DIR.glob("*.html"), reverse=True)
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Historique - Veille Alternances</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 30px;
        }}
        .archive-list {{
            list-style: none;
            padding: 0;
        }}
        .archive-item {{
            padding: 15px;
            margin-bottom: 10px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            transition: all 0.3s ease;
        }}
        .archive-item:hover {{
            background: #f5f5f5;
            border-color: #667eea;
            transform: translateX(5px);
        }}
        .archive-item a {{
            text-decoration: none;
            color: #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .date {{
            font-weight: bold;
            color: #667eea;
        }}
        .badge {{
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 30px;
            color: #667eea;
            text-decoration: none;
            font-weight: bold;
        }}
        .back-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Historique des veilles</h1>
        <p class="subtitle">Consultez les veilles des {RETENTION_DAYS} derniers jours</p>
        
        <ul class="archive-list">
"""
    
    for i, archive in enumerate(archives):
        date_str = archive.stem  # YYYY-MM-DD
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_formatted = date_obj.strftime('%d/%m/%Y')
            
            badge = '<span class="badge">Aujourd\'hui</span>' if i == 0 else ''
            
            html += f"""
            <li class="archive-item">
                <a href="archives/{archive.name}">
                    <span class="date">{date_formatted}</span>
                    {badge}
                </a>
            </li>
"""
        except ValueError:
            continue
    
    html += """
        </ul>
        
        <a href="index.html" class="back-link">← Retour à la dernière veille</a>
    </div>
</body>
</html>
"""
    
    historique_path = DOCS_DIR / "historique.html"
    historique_path.write_text(html, encoding='utf-8')
    print(f"✅ Page historique générée : {historique_path}")


def save_html_with_archives(html_content):
    """Sauvegarde index.html + archive datée + génère historique"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Créer le dossier archives
    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Sauvegarder l'archive datée
    archive_path = ARCHIVES_DIR / f"{today}.html"
    archive_path.write_text(html_content, encoding='utf-8')
    print(f"✅ Archive sauvegardée : {archive_path}")
    
    # 2. Écraser index.html (dernière version)
    index_path = DOCS_DIR / "index.html"
    index_path.write_text(html_content, encoding='utf-8')
    print(f"✅ Index mis à jour : {index_path}")
    
    # 3. Nettoyer les vieilles archives
    cleanup_old_archives()
    
    # 4. Générer la page historique
    generate_historique_page()
    
    return index_path


def git_commit_and_push():
    """Commit et push HTML sur GitHub (non bloquant)"""
    if not shutil.which('git'):
        print("⚠️  Git non disponible - Skip publication")
        print("   (Normal en local Windows, OK dans GitHub Actions)")
        return
    
    try:
        subprocess.run(['git', 'add', 'docs/'], cwd=BASE_DIR, check=True, capture_output=True)
        subprocess.run([
            'git', 'commit', '-m', 
            f'Update veille {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        ], cwd=BASE_DIR, check=True, capture_output=True)
        subprocess.run(['git', 'push'], cwd=BASE_DIR, check=True, capture_output=True)
        print("✅ Publié sur GitHub Pages")
    except subprocess.CalledProcessError:
        print("⚠️  Erreur Git (non bloquant)")


def send_email(html_path, data):
    """Envoie l'email avec lien amélioré + pièce jointe HTML"""
    meta = data.get('meta', {})
    nb_total = meta.get('total_offres', 0)
    nb_new = meta.get('nouvelles', 0)
    
    # Configuration email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"🎯 Veille Alternances : {nb_new} nouvelles offres ({nb_total} total)"
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    
    # Corps HTML de l'email - AMÉLIORÉ avec lien plus visible
    email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 25px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        .header p {{
            margin: 0;
            opacity: 0.95;
            font-size: 14px;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin: 25px 0;
            text-align: center;
        }}
        .stat {{
            flex: 1;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            display: block;
        }}
        .stat-label {{
            font-size: 13px;
            color: #666;
            margin-top: 5px;
        }}
        
        /* LIENS AMÉLIORÉS - Plus visibles */
        .links-section {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
        }}
        .links-title {{
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 20px;
        }}
        .btn {{
            display: inline-block;
            padding: 16px 32px;
            margin: 8px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 15px;
            transition: all 0.3s ease;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
        }}
        .btn-secondary {{
            background: #95a5a6;
            color: white !important;
        }}
        .btn-secondary:hover {{
            background: #7f8c8d;
        }}
        
        .attachment-note {{
            font-size: 13px;
            color: #666;
            margin-top: 15px;
            padding: 12px;
            background: white;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .legend {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 13px;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        .legend ul {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        .legend li {{
            margin: 5px 0;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            color: white;
        }}
        .badge.new {{ background: #e74c3c; }}
        .badge.lba {{ background: #3498db; }}
        .badge.perplexity {{ background: #9b59b6; }}
        
        .footer {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <p>Bachelor 3 RSB · Début: Septembre 2026</p>
        </div>
        
        <!-- Stats -->
        <div class="stats">
            <div class="stat">
                <span class="stat-number">{nb_new}</span>
                <div class="stat-label">Nouvelles</div>
            </div>
            <div class="stat">
                <span class="stat-number">{nb_total}</span>
                <div class="stat-label">Total actives</div>
            </div>
        </div>
        
        <!-- Liens principaux - AMÉLIORÉS -->
        <div class="links-section">
            <div class="links-title">📋 Consulter les offres détaillées</div>
            
            <a href="{GITHUB_PAGES_URL}" class="btn btn-primary">
                🌐 Voir les dernières offres en ligne
            </a>
            <br>
            <a href="{GITHUB_PAGES_URL}historique.html" class="btn btn-secondary">
                📁 Consulter l'historique des 30 jours
            </a>
            
            <div class="attachment-note">
                💡 <strong>Conseil :</strong> Ou ouvre la <strong>pièce jointe HTML</strong> ci-dessous pour consulter hors ligne
            </div>
        </div>
        
        <!-- Légende -->
        <div class="legend">
            <div class="legend-title">Légende des badges :</div>
            <ul>
                <li><span class="badge new">NEW</span> : Nouvelle offre détectée aujourd'hui</li>
                <li><span class="badge">Active</span> : Offre toujours active (déjà connue)</li>
                <li><span class="badge lba">LBA</span> : Source API La Bonne Alternance</li>
                <li><span class="badge perplexity">Perplexity</span> : Recherche complémentaire</li>
            </ul>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            📅 Mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
            🤖 Scraper automatique quotidien LBA + Recherche Perplexity
        </div>
    </div>
</body>
</html>
"""
    
    msg.attach(MIMEText(email_html, 'html'))
    
    # Pièce jointe HTML
    with open(html_path, 'rb') as f:
        attachment = MIMEBase('text', 'html')
        attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename="veille_alternances_{datetime.now().strftime("%Y-%m-%d")}.html"'
        )
        msg.attach(attachment)
    
    # Envoi
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email envoyé à : {GMAIL_USER}")
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")


def main():
    """Fonction principale avec gestion des archives"""
    print("=" * 70)
    print("🚀 GÉNÉRATION HTML + ARCHIVES + ENVOI EMAIL")
    print("=" * 70)
    
    print("\n[1/5] Chargement des données...")
    data = load_offers()
    print(f"✅ {len(data['offres'])} offres chargées")
    
    print("\n[2/5] Génération du HTML...")
    html_content = generate_html(data)
    
    print("\n[3/5] Sauvegarde avec archives (30 jours)...")
    html_path = save_html_with_archives(html_content)
    
    print("\n[4/5] Publication GitHub...")
    git_commit_and_push()
    
    print("\n[5/5] Envoi de l'email...")
    send_email(html_path, data)
    
    print("\n" + "=" * 70)
    print("✅ PROCESSUS TERMINÉ")
    print(f"📄 Index : {html_path}")
    print(f"📧 Email envoyé à : {GMAIL_USER}")
    print(f"🌐 URL en ligne : {GITHUB_PAGES_URL}")
    print(f"📚 Historique : {GITHUB_PAGES_URL}historique.html")
    print("=" * 70)


if __name__ == "__main__":
    main()
