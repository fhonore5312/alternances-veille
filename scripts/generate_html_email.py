#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Génération HTML et envoi d'email
IMPORTANT: Workflow refactorisé - Ce script utilise data/offres_merged.json
généré par: scraper_lba.py → validator.py → merge_offers.py → generate_html_email.py
"""

import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase  # ← AJOUTÉ
from email import encoders  # ← AJOUTÉ
from pathlib import Path
import subprocess
import shutil


# ===== CONFIGURATION =====
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
ARCHIVES_DIR = DOCS_DIR / "archives"

# Créer les dossiers s'ils n'existent pas
DOCS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

# Fichiers
OFFRES_MERGED = DATA_DIR / "offres_merged.json"
OUTPUT_HTML_DOCS = DOCS_DIR / "index.html"

# Charge les variables d'environnement
load_dotenv()

# Configuration Gmail
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', GMAIL_USER)  # Destinataire (par défaut: soi-même)

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
    """Génère le HTML complet pour GitHub Pages"""
    offers = data['offres']
    meta = data['meta']
    
    # Regrouper par ville
    offers_by_city = group_by_city(offers)
    
    # Stats
    total_offers = meta['total_offres']
    new_count = meta['nouvelles']
    
    # Stats par ville
    stats_by_city = {
        'Rennes': len(offers_by_city.get('Rennes', [])),
        'Nantes': len(offers_by_city.get('Nantes', [])),
        'Paris': len(offers_by_city.get('Paris', []))
    }
    
    # Stats par source
    lba_count = meta.get('source_lba', 0)
    perplexity_count = meta.get('source_perplexity', 0)
    
    # Header HTML avec CSS complet
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 42px;
            margin-bottom: 15px;
            font-weight: 700;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        
        .header p {{
            font-size: 18px;
            opacity: 0.95;
            margin-bottom: 5px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            padding: 40px;
            background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
        }}
        
        .stat-card {{
            background: white;
            padding: 25px 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 2px solid transparent;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.2);
            border-color: #667eea;
        }}
        
        .stat-card.highlight {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .stat-card h3 {{
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .stat-card.highlight h3 {{
            color: rgba(255,255,255,0.9);
        }}
        
        .stat-card:not(.highlight) h3 {{
            color: #6c757d;
        }}
        
        .stat-card .number {{
            font-size: 40px;
            font-weight: 800;
            line-height: 1;
        }}
        
        .stat-card:not(.highlight) .number {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .archives-banner {{
            background: white;
            padding: 25px 40px;
            margin: 0 40px 20px 40px;
            border-radius: 12px;
            text-align: center;
            border: 2px dashed #667eea;
            transition: all 0.3s ease;
        }}
        
        .archives-banner:hover {{
            background: #f8f9ff;
            border-color: #764ba2;
        }}
        
        .archives-banner h3 {{
            color: #2c3e50;
            margin-bottom: 8px;
            font-size: 18px;
        }}
        
        .archives-banner p {{
            color: #6c757d;
            margin-bottom: 12px;
            font-size: 14px;
        }}
        
        .archives-banner a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
            transition: color 0.3s ease;
        }}
        
        .archives-banner a:hover {{
            color: #764ba2;
        }}
        
        .content {{
            padding: 30px 40px 50px 40px;
        }}
        
        .city-section {{
            margin-bottom: 50px;
        }}
        
        .city-header {{
            display: flex;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            color: white;
        }}
        
        .city-icon {{
            width: 50px;
            height: 50px;
            background: rgba(255,255,255,0.2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            font-size: 26px;
            backdrop-filter: blur(10px);
        }}
        
        .city-header h2 {{
            font-size: 28px;
            font-weight: 700;
            flex: 1;
        }}
        
        .city-header .count {{
            background: rgba(255,255,255,0.25);
            color: white;
            padding: 8px 20px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: 700;
            backdrop-filter: blur(10px);
        }}
        
        .offers-grid {{
            display: grid;
            gap: 25px;
        }}
        
        .offer-card {{
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 16px;
            padding: 30px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .offer-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 5px;
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .offer-card:hover {{
            border-color: #667eea;
            box-shadow: 0 8px 30px rgba(102, 126, 234, 0.15);
            transform: translateY(-3px);
        }}
        
        .offer-card:hover::before {{
            opacity: 1;
        }}
        
        .offer-card.new {{
            border-left: 5px solid #28a745;
            background: linear-gradient(90deg, rgba(40, 167, 69, 0.03) 0%, white 100px);
        }}
        
        .offer-card.new::before {{
            background: #28a745;
            opacity: 1;
        }}
        
        .offer-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 18px;
            gap: 15px;
        }}
        
        .offer-title {{
            flex: 1;
        }}
        
        .offer-title h3 {{
            font-size: 22px;
            color: #2c3e50;
            margin-bottom: 10px;
            font-weight: 700;
            line-height: 1.3;
        }}
        
        .offer-company {{
            font-size: 17px;
            color: #667eea;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .offer-location {{
            font-size: 15px;
            color: #6c757d;
            display: flex;
            align-items: center;
            font-weight: 500;
        }}
        
        .offer-location::before {{
            content: "📍";
            margin-right: 6px;
            font-size: 16px;
        }}
        
        .new-badge {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }}
        
        .offer-description {{
            color: #495057;
            line-height: 1.7;
            margin-bottom: 18px;
            font-size: 15px;
        }}
        
        .skills-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 18px;
        }}
        
        .skill-badge {{
            background: linear-gradient(135deg, #e7f0ff 0%, #f0e7ff 100%);
            color: #667eea;
            padding: 7px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid rgba(102, 126, 234, 0.2);
            transition: all 0.3s ease;
        }}
        
        .skill-badge:hover {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }}
        
        .offer-metadata {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }}
        
        .meta-item {{
            display: flex;
            align-items: center;
            font-size: 14px;
            color: #495057;
            font-weight: 500;
        }}
        
        .meta-item strong {{
            color: #2c3e50;
            margin-left: 5px;
        }}
        
        .offer-actions {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        
        .btn {{
            padding: 14px 28px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 700;
            font-size: 15px;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}
        
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }}
        
        .source-badge {{
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .source-lba {{
            background: #e3f2fd;
            color: #1976d2;
        }}
        
        .source-perplexity {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}
        
        .footer {{
            background: linear-gradient(to bottom, #f8f9fa 0%, #e9ecef 100%);
            padding: 40px;
            text-align: center;
            border-top: 3px solid #667eea;
        }}
        
        .footer p {{
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        
        .footer a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 700;
            transition: color 0.3s ease;
        }}
        
        .footer a:hover {{
            color: #764ba2;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 28px;
            }}
            
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
                padding: 20px;
            }}
            
            .content {{
                padding: 20px;
            }}
            
            .offer-header {{
                flex-direction: column;
            }}
            
            .new-badge {{
                align-self: flex-start;
            }}
            
            .offer-metadata {{
                flex-direction: column;
                gap: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <p>Bachelor 3 RSB · Début: Septembre 2026 · Durée: 12-24 mois</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card highlight">
                <h3>🆕 Nouvelles</h3>
                <div class="number">{new_count}</div>
            </div>
            <div class="stat-card">
                <h3>📊 Total actives</h3>
                <div class="number">{total_offers}</div>
            </div>
            <div class="stat-card">
                <h3>📍 LBA: {lba_count}</h3>
                <div class="number">{lba_count}</div>
            </div>
            <div class="stat-card">
                <h3>🔍 Perplexity: {perplexity_count}</h3>
                <div class="number">{perplexity_count}</div>
            </div>
            <div class="stat-card">
                <h3>🏰 Rennes</h3>
                <div class="number">{stats_by_city['Rennes']}</div>
            </div>
            <div class="stat-card">
                <h3>⚓ Nantes</h3>
                <div class="number">{stats_by_city['Nantes']}</div>
            </div>
            <div class="stat-card">
                <h3>🗼 Paris</h3>
                <div class="number">{stats_by_city['Paris']}</div>
            </div>
        </div>
        
        <div class="archives-banner">
            <h3>📚 Consulter l'historique des veilles</h3>
            <p>Accédez aux veilles des {RETENTION_DAYS} derniers jours</p>
            <a href="archives/" target="_blank">→ Voir les archives</a>
        </div>
        
        <div class="content">
"""
    
    # Générer les sections par ville
    city_order = ['Rennes', 'Nantes', 'Paris']
    city_icons = {'Rennes': '🏰', 'Nantes': '⚓', 'Paris': '🗼'}
    
    for city in city_order:
        if city in offers_by_city and len(offers_by_city[city]) > 0:
            city_offers = offers_by_city[city]
            html += f"""
            <div class="city-section">
                <div class="city-header">
                    <div class="city-icon">{city_icons[city]}</div>
                    <h2>{city} Priorité #{offers_by_city[city][0].get('priorite_ville', '?')}</h2>
                    <span class="count">{len(city_offers)} offres</span>
                </div>
                
                <div class="offers-grid">
"""
            
            for offer in city_offers:
                is_new = offer.get('status') == 'new'
                new_class = 'new' if is_new else ''
                new_badge = '<span class="new-badge">🆕 Nouvelle</span>' if is_new else ''
                
                source = offer.get('source', 'LBA')
                source_class = 'source-lba' if source == 'LBA' else 'source-perplexity'
                
                # Skills
                skills_html = ''
                if offer.get('competences_detectees'):
                    skills_html = '<div class="skills-container">'
                    for skill in offer['competences_detectees']:
                        skills_html += f'<span class="skill-badge">{skill}</span>'
                    skills_html += '</div>'
                
                # Metadata
                meta_items = []
                if offer.get('type_contrat'):
                    meta_items.append(f'<div class="meta-item">📋 <strong>{offer["type_contrat"]}</strong></div>')
                if offer.get('duree_contrat'):
                    meta_items.append(f'<div class="meta-item">⏱️ <strong>{offer["duree_contrat"]}</strong></div>')
                if offer.get('date_debut'):
                    meta_items.append(f'<div class="meta-item">📅 Début: <strong>{offer["date_debut"]}</strong></div>')
                if offer.get('plateforme_source'):
                    meta_items.append(f'<div class="meta-item">🔗 <strong>{offer["plateforme_source"]}</strong></div>')
                
                meta_html = '<div class="offer-metadata">' + ''.join(meta_items) + '</div>' if meta_items else ''
                
                html += f"""
                    <div class="offer-card {new_class}">
                        <div class="offer-header">
                            <div class="offer-title">
                                <h3>{offer['titre']}</h3>
                                <div class="offer-company">{offer['entreprise']}</div>
                                <div class="offer-location">{offer['ville']} ({offer['code_postal']})</div>
                            </div>
                            {new_badge}
                        </div>
                        <p class="offer-description">{offer.get('description', '')}</p>
                        {skills_html}
                        {meta_html}
                        <div class="offer-actions">
                            <a href="{offer.get('url_candidature', '#')}" class="btn btn-primary" target="_blank">
                                👉 Postuler
                            </a>
                            <span class="source-badge {source_class}">{source}</span>
                        </div>
                    </div>
"""
            
            html += """
                </div>
            </div>
"""
    
    # Footer
    html += f"""
        </div>
        
        <div class="footer">
            <p><strong>Généré automatiquement le {meta['date_generation']}</strong></p>
            <p>Sources: {' + '.join(meta.get('sources', ['LBA']))}</p>
            <p><a href="{GITHUB_PAGES_URL}" target="_blank">🔗 Lien permanent vers cette veille</a></p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def generate_email_html(data):
    """Génère un email HTML simple avec lien vers GitHub Pages"""
    meta = data['meta']
    new_count = meta['nouvelles']
    total_count = meta['total_offres']
    
    offers_by_city = group_by_city(data['offres'])
    stats_by_city = {
        'Rennes': len(offers_by_city.get('Rennes', [])),
        'Nantes': len(offers_by_city.get('Nantes', [])),
        'Paris': len(offers_by_city.get('Paris', []))
    }
    
    lba_count = meta.get('source_lba', 0)
    perplexity_count = meta.get('source_perplexity', 0)
    
    email_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 0;
            opacity: 0.95;
            font-size: 15px;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            padding: 30px 20px;
            background: #f8f9fa;
            text-align: center;
        }}
        .stat {{
            flex: 1;
        }}
        .stat-number {{
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 13px;
            color: #6c757d;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
        }}
        .cta-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            text-align: center;
            margin: 20px 0;
            border-radius: 10px;
        }}
        .cta-box p {{
            color: white;
            font-size: 16px;
            margin: 0 0 20px 0;
        }}
        .cta-button {{
            display: inline-block;
            background: white;
            color: #667eea;
            padding: 15px 40px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
        }}
        .info-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }}
        .info-box p {{
            margin: 5px 0;
            color: #495057;
            font-size: 14px;
        }}
        .footer {{
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 12px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>🎯 Veille Alternances Marketing Digital</h1>
            <p>Bachelor 3 RSB · Début: Septembre 2026</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{new_count}</div>
                <div class="stat-label">Nouvelles</div>
            </div>
            <div class="stat">
                <div class="stat-number">{total_count}</div>
                <div class="stat-label">Total actives</div>
            </div>
        </div>
        
        <div class="content">
            <div class="cta-box">
                <p>📋 Consulter les offres détaillées</p>
                <a href="{GITHUB_PAGES_URL}" class="cta-button">
                    👉 Voir les dernières offres en ligne
                </a>
            </div>
            
            <div class="info-box">
                <p><strong>💡 Conseil :</strong> Ou ouvre la <strong>pièce jointe HTML</strong> ci-dessous pour consulter hors ligne</p>
            </div>
            
            <div class="info-box">
                <p><strong>📊 Répartition par ville :</strong></p>
                <p>🏰 Rennes: {stats_by_city['Rennes']} · ⚓ Nantes: {stats_by_city['Nantes']} · 🗼 Paris: {stats_by_city['Paris']}</p>
            </div>
            
            <div class="info-box">
                <p><strong>🔗 Sources :</strong></p>
                <p>LBA: {lba_count} offres · Perplexity: {perplexity_count} offres</p>
            </div>
            
            <div class="info-box">
                <p><strong>📚 Consulter l'historique :</strong></p>
                <p><a href="{GITHUB_PAGES_URL}archives/" style="color: #667eea; font-weight: bold;">→ Archives des {RETENTION_DAYS} derniers jours</a></p>
            </div>
        </div>
        
        <div class="footer">
            <p>Généré automatiquement le {meta['date_generation']}</p>
            <p><a href="{GITHUB_PAGES_URL}">🔗 Lien permanent</a></p>
        </div>
    </div>
</body>
</html>
"""
    
    return email_html

def archive_old_html():
    """Archive l'ancien index.html si existant"""
    if OUTPUT_HTML_DOCS.exists():
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        archive_name = f"veille_{timestamp}.html"
        archive_path = ARCHIVES_DIR / archive_name
        
        shutil.copy(OUTPUT_HTML_DOCS, archive_path)
        print(f"📚 Archive créée: {archive_name}")
    
    # Nettoyer les archives > RETENTION_DAYS
    cleanup_old_archives()

def cleanup_old_archives():
    """Supprime les archives de plus de RETENTION_DAYS jours"""
    if not ARCHIVES_DIR.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    
    for archive_file in ARCHIVES_DIR.glob("veille_*.html"):
        try:
            date_str = archive_file.stem.split('_')[1]
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            if file_date < cutoff_date:
                archive_file.unlink()
                deleted_count += 1
                print(f"🗑️  Supprimé: {archive_file.name}")
        except (IndexError, ValueError):
            continue
    
    if deleted_count > 0:
        print(f"✅ {deleted_count} anciennes archives supprimées")

def generate_archives_index():
    """Génère un index.html pour le dossier archives"""
    if not ARCHIVES_DIR.exists():
        return
    
    archives = sorted(ARCHIVES_DIR.glob("veille_*.html"), reverse=True)
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📚 Archives - Veille Alternances</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 32px;
        }}
        .subtitle {{
            color: #6c757d;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 30px;
            color: #667eea;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
        }}
        .back-link:hover {{
            color: #764ba2;
        }}
        .archive-list {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
        }}
        .archive-item {{
            padding: 20px;
            background: white;
            margin-bottom: 15px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }}
        .archive-item:hover {{
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.2);
        }}
        .archive-item a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
        }}
        .archive-item a:hover {{
            color: #764ba2;
        }}
        .archive-date {{
            color: #6c757d;
            font-size: 14px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="../" class="back-link">← Retour à la veille actuelle</a>
        <h1>📚 Archives des veilles</h1>
        <p class="subtitle">Historique des {RETENTION_DAYS} derniers jours</p>
        
        <div class="archive-list">
"""
    
    for archive in archives:
        try:
            parts = archive.stem.split('_')
            date_str = parts[1]
            time_str = parts[2].replace('-', ':')
            
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
            
            html += f"""
            <div class="archive-item">
                <a href="{archive.name}">📄 Veille du {formatted_date} à {time_str}</a>
                <span class="archive-date">{date_str}</span>
            </div>
"""
        except (IndexError, ValueError):
            continue
    
    html += """
        </div>
    </div>
</body>
</html>
"""
    
    archives_index_path = ARCHIVES_DIR / "index.html"
    with open(archives_index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"📚 Index archives généré: {archives_index_path}")

def send_email(email_html_content, full_html_path, data):
    """Envoie l'email avec lien GitHub Pages + HTML en pièce jointe"""
    meta = data['meta']
    new_count = meta['nouvelles']
    total_count = meta['total_offres']
    
    # Créer le message
    msg = MIMEMultipart('mixed')
    msg['Subject'] = f"🎯 Veille Alternances : {new_count} nouvelles offres ({total_count} total)"
    msg['From'] = GMAIL_USER
    msg['To'] = RECIPIENT_EMAIL
    
    # Version alternative (texte + HTML)
    msg_alternative = MIMEMultipart('alternative')
    
    # Version texte (fallback)
    text_content = f"""
Veille Alternances Marketing Digital

{new_count} nouvelles offres · {total_count} total

Consultez les offres sur: {GITHUB_PAGES_URL}
"""
    
    part_text = MIMEText(text_content, 'plain', 'utf-8')
    part_html = MIMEText(email_html_content, 'html', 'utf-8')
    
    msg_alternative.attach(part_text)
    msg_alternative.attach(part_html)
    msg.attach(msg_alternative)
    
    # Attacher le fichier HTML complet
    with open(full_html_path, 'rb') as f:
        part = MIMEBase('text', 'html')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="veille_alternances_{datetime.now().strftime("%Y-%m-%d")}.html"')
        msg.attach(part)
    
    # Envoyer
    try:
        print("\n📧 Envoi de l'email...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email envoyé à {RECIPIENT_EMAIL} avec succès!")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email: {e}")

def commit_and_push():
    """Commit et push sur GitHub"""
    try:
        print("\n🔄 Mise à jour GitHub Pages...")
        subprocess.run(['git', 'add', 'docs/'], check=True, cwd=BASE_DIR)
        subprocess.run(['git', 'commit', '-m', f'Update veille {datetime.now().strftime("%Y-%m-%d %H:%M")}'], check=True, cwd=BASE_DIR)
        subprocess.run(['git', 'push'], check=True, cwd=BASE_DIR)
        print("✅ GitHub Pages mis à jour!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Erreur Git: {e}")
        print("   → Commit/push manuel nécessaire")

def main():
    print("=" * 70)
    print("📧 GÉNÉRATION HTML + EMAIL")
    print("=" * 70)
    
    # Charger les offres
    data = load_offers()
    print(f"📥 {data['meta']['total_offres']} offres chargées")
    print(f"   🆕 {data['meta']['nouvelles']} nouvelles")
    print(f"   ♻️  {data['meta']['actives']} actives")
    
    # Archiver l'ancien HTML
    archive_old_html()
    
    # Générer le HTML complet (pour GitHub Pages)
    print("\n🎨 Génération du HTML complet...")
    full_html = generate_html(data)
    
    # Sauvegarder dans docs/
    with open(OUTPUT_HTML_DOCS, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"✅ HTML complet généré: {OUTPUT_HTML_DOCS}")
    
    # Générer l'index des archives
    generate_archives_index()
    
    # Générer l'email HTML (simple avec lien)
    print("\n📧 Génération de l'email...")
    email_html = generate_email_html(data)
    
    # Envoyer l'email (avec HTML complet en PJ)
    if data['meta']['nouvelles'] > 0:
        send_email(email_html, OUTPUT_HTML_DOCS, data)
    else:
        print("\nℹ️  Aucune nouvelle offre → Email non envoyé")
    
    # Git commit + push
    commit_and_push()
    
    print("\n" + "=" * 70)
    print(f"✅ TERMINÉ")
    print(f"🌐 GitHub Pages: {GITHUB_PAGES_URL}")
    print(f"📧 Email: {'Envoyé' if data['meta']['nouvelles'] > 0 else 'Non envoyé (pas de nouvelles offres)'}")
    print("=" * 70)

if __name__ == '__main__':
    main()
