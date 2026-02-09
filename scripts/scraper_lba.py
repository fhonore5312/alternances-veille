#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper LBA Alternances - Marketing Digital
Adapté pour la nouvelle structure de dossiers
"""

import requests
import json
from datetime import datetime
import re
from html import unescape
import os
from pathlib import Path

# ===== CONFIGURATION CHEMINS =====
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Créer le dossier data s'il n'existe pas
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Fichiers de sortie
OUTPUT_FILE = DATA_DIR / "offres_lba.json"
HISTORY_FILE = DATA_DIR / "offres_historique.json"

# ===== CONFIGURATION RECHERCHE =====
VILLES = {
    'Rennes': {
        'latitude': 48.1173,
        'longitude': -1.6778,
        'insee': '35238',
        'radius': 30,
        'priority': 1
    },
    'Nantes': {
        'latitude': 47.2184,
        'longitude': -1.5536,
        'insee': '44109',
        'radius': 30,
        'priority': 2
    },
    'Paris': {
        'latitude': 48.8566,
        'longitude': 2.3522,
        'insee': '75056',
        'radius': 30,
        'priority': 3
    }
}

# Codes ROME : Marketing + Communication + Contenus multimédias
ROMES_CODES = 'M1705,E1103,E1104'

# Compétences clés Digital Marketing
DIGITAL_SKILLS_KEYWORDS = {
    'SEO': ['seo', 'référencement naturel', 'référencement organique'],
    'SEA/Paid Media': ['sea', 'google ads', 'facebook ads', 'meta ads', 'paid media'],
    'Social Media': ['social media', 'réseaux sociaux', 'community management'],
    'Content Marketing': ['content', 'contenu', 'rédaction web', 'copywriting'],
    'Analytics': ['analytics', 'google analytics', 'data', 'tracking'],
    'Email Marketing': ['email marketing', 'emailing', 'newsletter'],
    'CRM/Automation': ['crm', 'marketing automation', 'hubspot', 'salesforce'],
    'E-commerce': ['e-commerce', 'ecommerce', 'marketplace', 'conversion'],
    'Growth/Acquisition': ['growth', 'acquisition', 'lead generation'],
    'UX/Design': ['ux', 'ui', 'expérience utilisateur', 'design']
}

# ===== UTILITAIRES =====
def clean_html(html_text):
    if not html_text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def truncate_text(text, max_length=200):
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + '...'

def format_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y')
    except:
        return None

def detect_skills(title, description):
    text = (title + " " + description).lower()
    detected = []
    for skill_name, keywords in DIGITAL_SKILLS_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            detected.append(skill_name)
    return detected

# ===== API LBA =====
def fetch_lba_offers(ville_name, config):
    url = "https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/jobs"
    params = {
        'romes': ROMES_CODES,
        'latitude': config['latitude'],
        'longitude': config['longitude'],
        'insee': config['insee'],
        'radius': config['radius'],
        'sources': 'partnerJob',
        'caller': 'VeilleAlternance'
    }

    print(f"📍 {ville_name}...")
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get('partnerJobs', {}).get('results', [])
        print(f"  ✅ {len(results)} offres")
        return results
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return []

# ===== TRANSFORMATION =====
def transform_offers(raw_offers, ville_name, ville_config):
    offers = []
    for offer in raw_offers:
        title_clean = offer.get('title', '').lower().replace(' ', '').replace('/', '')
        company_clean = offer.get('company', {}).get('name', '').lower().replace(' ', '')
        zipcode = offer.get('place', {}).get('zipCode', '')
        cle_composite = f"{title_clean}_{company_clean}_{zipcode}"

        description_raw = offer.get('job', {}).get('description', '')
        description_clean = clean_html(description_raw)
        description_short = truncate_text(description_clean, 200)

        detected_skills = detect_skills(offer.get('title', ''), description_clean)

        contract_types = offer.get('job', {}).get('type', [])
        contract_text = ' + '.join(contract_types) if contract_types else 'Alternance'

        offers.append({
            'cle_composite': cle_composite,
            'title': offer.get('title', ''),
            'company_name': offer.get('company', {}).get('name', ''),
            'company_siret': offer.get('company', {}).get('siret', ''),
            'city': offer.get('place', {}).get('city', ''),
            'zipcode': zipcode,
            'full_address': offer.get('place', {}).get('fullAddress', ''),
            'description': description_short,
            'description_full': description_clean,
            'detected_skills': detected_skills,
            'contact_url': offer.get('contact', {}).get('url', '#'),
            'partner_label': offer.get('job', {}).get('partner_label', 'LBA'),
            'creation_date': format_date(offer.get('job', {}).get('creationDate')),
            'expiration_date': format_date(offer.get('job', {}).get('jobExpirationDate')),
            'start_date': format_date(offer.get('job', {}).get('jobStartDate')),
            'contract_type': contract_text,
            'contract_duration': offer.get('job', {}).get('dureeContrat', None),
            'ville_recherche': ville_name,
            'ville_priority': ville_config['priority'],
            'status': 'new'
        })
    return offers

# ===== FILTRAGE =====
def filter_schools(offers):
    exclusions = ['enseigne inconnue', 'école', 'ecole', 'formation', 'université', 'campus']
    filtered = []
    for offer in offers:
        company_lower = offer['company_name'].lower()
        is_school = any(excl in company_lower for excl in exclusions)
        has_siret = offer['company_siret'] != ''
        if not is_school and has_siret:
            filtered.append(offer)
    print(f"🔍 Filtrage: {len(filtered)} offres valides")
    return filtered

def filter_digital_only(offers):
    keywords = ['digital', 'web', 'seo', 'sea', 'social', 'content', 'email', 
                'analytics', 'crm', 'ecommerce', 'growth', 'ads', 'online']
    filtered = []
    for offer in offers:
        text = (offer['title'] + ' ' + offer['description_full']).lower()
        if any(k in text for k in keywords):
            filtered.append(offer)
    print(f"🎯 Digital: {len(filtered)} offres")
    return filtered

# ===== HISTORIQUE =====
def load_history():
    if not HISTORY_FILE.exists():
        return {'last_update': None, 'offers': {}}
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_history(history):
    history['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def detect_new_offers(current_offers, history):
    today = datetime.now().strftime('%Y-%m-%d')
    current_keys = {o['cle_composite'] for o in current_offers}
    history_keys = set(history['offers'].keys())

    new_keys = current_keys - history_keys
    new_offers = [o for o in current_offers if o['cle_composite'] in new_keys]
    active_offers = [o for o in current_offers if o['cle_composite'] in history_keys]

    print(f"\n📊 Analyse:")
    print(f"  🆕 Nouvelles: {len(new_offers)}")
    print(f"  ♻️  Actives: {len(active_offers)}")

    for offer in current_offers:
        key = offer['cle_composite']
        if key in new_keys:
            history['offers'][key] = {
                'first_seen': today,
                'last_seen': today,
                'status': 'new',
                'title': offer['title'],
                'company_name': offer['company_name']
            }
        else:
            history['offers'][key]['last_seen'] = today
            history['offers'][key]['status'] = 'active'

    return new_offers, active_offers, history

# ===== MAIN =====
def main():
    print("=" * 60)
    print("🚀 SCRAPER LBA - MARKETING DIGITAL")
    print("=" * 60)

    all_offers = []
    for ville_name, config in VILLES.items():
        raw_offers = fetch_lba_offers(ville_name, config)
        transformed = transform_offers(raw_offers, ville_name, config)
        all_offers.extend(transformed)

    print(f"\n📦 Total: {len(all_offers)} offres")

    filtered_offers = filter_schools(all_offers)
    filtered_offers = filter_digital_only(filtered_offers)

    if not filtered_offers:
        print("⚠️  Aucune offre trouvée")
        return

    history = load_history()
    new_offers, active_offers, updated_history = detect_new_offers(filtered_offers, history)
    save_history(updated_history)

    # JSON final
    output_json = {
        "meta": {
            "date_generation": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "sources": ["LBA"],
            "total_offres": len(filtered_offers),
            "nouvelles": len(new_offers),
            "actives": len(active_offers)
        },
        "offres": []
    }

    for offer in filtered_offers:
        is_new = offer['cle_composite'] in {o['cle_composite'] for o in new_offers}
        output_json['offres'].append({
            "id": offer['cle_composite'],
            "source": "LBA",
            "status": "new" if is_new else "active",
            "titre": offer['title'],
            "entreprise": offer['company_name'],
            "ville": offer['city'],
            "code_postal": offer['zipcode'],
            "adresse_complete": offer['full_address'],
            "description": offer['description'],
            "description_complete": offer['description_full'],
            "competences_detectees": offer['detected_skills'],
            "url_candidature": offer['contact_url'],
            "type_contrat": offer['contract_type'],
            "duree_contrat": offer['contract_duration'],
            "date_debut": offer['start_date'],
            "date_creation": offer['creation_date'],
            "date_expiration": offer['expiration_date'],
            "plateforme_source": offer['partner_label'],
            "ville_recherche": offer['ville_recherche'],
            "priorite_ville": offer['ville_priority']
        })

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Sauvegardé: {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == '__main__':
    main()
