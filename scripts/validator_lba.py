#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validator_lba.py - Validation approfondie des offres LBA
Adapté pour la nouvelle structure (data/, docs/)

Ce script :
1. Charge data/offres_lba.json
2. Valide les données métier (date, durée, type de poste)
3. Fetch chaque URL d'offre (tolérant avec 403/timeouts)
4. Vérifie le contenu de la page (offre expirée, date, bouton postuler)
5. Met à jour le champ validation_status
6. Génère data/offres_lba_validated.json

Usage:
python validator_lba.py
python validator_lba.py --quick # Valide seulement les nouvelles offres
"""

import requests
import json
from datetime import datetime
import time
import re
import argparse
from pathlib import Path

# ===== CONFIGURATION CHEMINS =====
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Fichiers
INPUT_FILE = DATA_DIR / "offres_lba.json"
OUTPUT_FILE = DATA_DIR / "offres_lba_validated.json"

# ===== CONFIGURATION VALIDATION =====
TIMEOUT = 15  # Secondes pour chaque requête
DELAY_BETWEEN_REQUESTS = 2  # Délai entre chaque fetch (anti-ban)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Mots-clés indiquant offre expirée
EXPIRED_KEYWORDS = [
    "offre n'est plus disponible",
    "candidatures fermées",
    "no longer accepting applications",
    "expired",
    "closed",
    "pourvue",
    "Les candidatures ne sont plus acceptées",
    "Cette offre a expiré",
    "offre expirée",
    "offre retirée",
    "plus d'offres disponibles",
    "offre pourvue",
    "poste pourvu",
    "recrutement terminé"
]

# Mots-clés indiquant bouton postuler actif
APPLY_BUTTON_KEYWORDS = [
    "postuler",
    "candidater",
    "apply now",
    "apply",
    "postuler maintenant",
    "je postule",
    "envoyer ma candidature",
    "postuler en ligne",
    "déposer votre candidature"
]

# ===== NOUVEAUX FILTRES MÉTIER =====
# Titres de poste suspects (niveau confirmé, pas alternance)
SENIOR_JOB_TITLES = [
    "manager",
    "responsable",
    "chef",
    "directeur",
    "head of",
    "lead"
]

# ===== UTILITAIRES =====
def fetch_url_content(url):
    """
    Fetch le contenu HTML d'une URL
    Retourne: (status_code, html_content, error_message)
    """
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return response.status_code, response.text, None
    except requests.exceptions.Timeout:
        return None, None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "connection_error"
    except Exception as e:
        return None, None, str(e)

def check_offer_status(html_content):
    """
    Analyse le contenu HTML pour déterminer le statut de l'offre
    Retourne: {
        'is_expired': bool,
        'has_apply_button': bool,
        'detected_date': str ou None,
        'confidence': 'high' | 'medium' | 'low'
    }
    """
    if not html_content:
        return {
            'is_expired': True,
            'has_apply_button': False,
            'detected_date': None,
            'confidence': 'low',
            'reason': 'no_content'
        }
    
    html_lower = html_content.lower()
    
    # 1. Vérifier si offre expirée
    is_expired = any(keyword in html_lower for keyword in EXPIRED_KEYWORDS)
    
    # 2. Vérifier présence bouton postuler
    has_apply_button = any(keyword in html_lower for keyword in APPLY_BUTTON_KEYWORDS)
    
    # 3. Essayer d'extraire une date de publication
    detected_date = None
    date_patterns = [
        r'(?:publiée|postée|published).*?(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
        r'(?:il y a|posted)\s+(\d+)\s+(jour|jours|day|days|semaine|week|mois|month)',
        r'(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, html_lower)
        if match:
            detected_date = match.group(0)
            break
    
    # 4. Déterminer la confiance
    confidence = 'low'
    if is_expired and not has_apply_button:
        confidence = 'high'  # Très probablement expirée
    elif not is_expired and has_apply_button:
        confidence = 'high'  # Très probablement active
    elif is_expired or not has_apply_button:
        confidence = 'medium'  # Incertain
    
    return {
        'is_expired': is_expired,
        'has_apply_button': has_apply_button,
        'detected_date': detected_date,
        'confidence': confidence,
        'reason': 'content_analysis'
    }

# ===== NOUVELLE FONCTION : VALIDATION MÉTIER =====
def validate_offer_data(offer):
    """
    Valide les données métier de l'offre AVANT la validation HTTP
    Retourne: (is_valid, reason)
    """
    titre = offer.get('titre', '').lower()
    duree_contrat = offer.get('duree_contrat')
    date_debut = offer.get('date_debut')
    
    # Filtre 1: Date de début trop ancienne
    if date_debut:
        try:
            # Parser les formats possibles
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                try:
                    debut_date = datetime.strptime(str(date_debut), fmt)
                    if debut_date.year < 2026:
                        return False, f"Date début obsolète ({debut_date.year})"
                    break
                except ValueError:
                    continue
        except Exception as e:
            pass  # Si parsing échoue, on continue
    
    # Filtre 2: Offres "Manager/Responsable" sans durée de contrat = probablement CDI
    is_senior_title = any(keyword in titre for keyword in SENIOR_JOB_TITLES)
    has_no_duration = not duree_contrat or str(duree_contrat).lower() in ['null', 'none', '']
    
    if is_senior_title and has_no_duration:
        return False, "Poste confirmé sans durée (probable CDI)"
    
    # Filtre 3 supprimé (trop strict)
    
    return True, "OK"

def validate_offer(offer, quick_mode=False):
    """
    Valide une offre en fetchant son URL
    Retourne l'offre mise à jour avec validation_status
    """
    url = offer.get('url_candidature', '')
    
    # Skip validation si URL vide ou # (pas de lien)
    if not url or url == '#' or url.startswith('#'):
        offer['validation_status'] = 'invalid'
        offer['validation_details'] = {
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': 'no_url',
            'is_expired': True
        }
        return offer
    
    # En mode quick, skip si déjà validé récemment
    if quick_mode and offer.get('validation_status') == 'validated':
        validation_date = offer.get('validation_details', {}).get('checked_at')
        if validation_date:
            try:
                last_check = datetime.strptime(validation_date, '%Y-%m-%d %H:%M:%S')
                days_ago = (datetime.now() - last_check).days
                if days_ago < 7:  # Validé il y a moins de 7 jours
                    print(f"   ⏭️  Skip (validé il y a {days_ago}j)")
                    return offer
            except:
                pass
    
    print(f"   🔍 {offer['titre'][:50]}...")
    
    # Fetch l'URL
    status_code, html_content, error = fetch_url_content(url)
    
    # Analyser le résultat
    if error:
        offer['validation_status'] = 'error'
        offer['validation_details'] = {
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': error,
            'is_expired': None
        }
        print(f"   ❌ Erreur: {error}")
    
    elif status_code == 404:
        offer['validation_status'] = 'expired'
        offer['validation_details'] = {
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status_code': 404,
            'is_expired': True,
            'confidence': 'high',
            'reason': 'page_not_found'
        }
        print(f"   💀 404 - Expirée")
    
    elif status_code == 200:
        # Analyser le contenu
        status = check_offer_status(html_content)
        
        if status['is_expired']:
            offer['validation_status'] = 'expired'
            print(f"   💀 Expirée ({status['confidence']})")
        elif status['has_apply_button']:
            offer['validation_status'] = 'validated'
            print(f"   ✅ Active ({status['confidence']})")
        else:
            offer['validation_status'] = 'uncertain'
            print(f"   ⚠️  Incertain ({status['confidence']})")
        
        offer['validation_details'] = {
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status_code': status_code,
            'is_expired': status['is_expired'],
            'has_apply_button': status['has_apply_button'],
            'detected_date': status['detected_date'],
            'confidence': status['confidence']
        }
    
    else:
        # Status 403, 500, etc.
        offer['validation_status'] = 'uncertain'
        offer['validation_details'] = {
            'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status_code': status_code,
            'is_expired': None,
            'confidence': 'low'
        }
        print(f"   ⚠️  Status: {status_code}")
    
    return offer

# ===== MAIN =====
def main():
    parser = argparse.ArgumentParser(description='Valide les offres LBA en profondeur')
    parser.add_argument('--quick', action='store_true', help='Valide seulement les nouvelles offres')
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔍 VALIDATOR LBA - Validation approfondie des offres")
    print("=" * 80)
    print(f"📂 Entrée: {INPUT_FILE}")
    print(f"💾 Sortie: {OUTPUT_FILE}")
    print(f"⚡ Mode: {'Quick (nouvelles uniquement)' if args.quick else 'Complet'}")
    print()
    
    # 1. Charger le fichier JSON
    if not INPUT_FILE.exists():
        print(f"❌ Fichier {INPUT_FILE} introuvable")
        print("   Exécute d'abord: python scraper_lba.py")
        return
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    offers = data.get('offres', [])
    print(f"📦 {len(offers)} offres chargées\n")
    
    if not offers:
        print("⚠️  Aucune offre à valider")
        return
    
    # 2. Valider chaque offre
    validated_count = 0
    expired_count = 0
    error_count = 0
    uncertain_count = 0
    rejected_data_count = 0
    kept_despite_issues = 0  # Nouveau compteur
    
    validated_offers = []
    
    for i, offer in enumerate(offers, 1):
        print(f"[{i}/{len(offers)}] {offer['entreprise']} - {offer['ville']}")
        
        # ===== VALIDATION MÉTIER =====
        is_valid_data, reason = validate_offer_data(offer)
        if not is_valid_data:
            print(f"   🚫 Rejetée (métier): {reason}")
            offer['validation_status'] = 'rejected'
            offer['validation_details'] = {
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reason': reason,
                'rejection_type': 'business_rule'
            }
            rejected_data_count += 1
            continue  # Skip la validation HTTP
        
        # Valider (validation HTTP)
        offer = validate_offer(offer, quick_mode=args.quick)
        
        # ===== COMPTAGE ET FILTRAGE ASSOUPLI ===== ← MODIFIÉ
        status = offer.get('validation_status')
        confidence = offer.get('validation_details', {}).get('confidence', 'low')
        
        if status == 'validated':
            # Offre clairement active
            validated_count += 1
            validated_offers.append(offer)
        
        elif status == 'uncertain':
            # Offre incertaine (403, pas de bouton postuler visible, etc.)
            # On garde quand même (probable blocage anti-scraping)
            uncertain_count += 1
            validated_offers.append(offer)
            kept_despite_issues += 1
            print(f"   ℹ️  Gardée malgré incertitude")
        
        elif status == 'expired':
            # Offre détectée comme expirée
            if confidence in ['medium', 'low']:
                # Si confidence faible/moyenne, c'est probablement un faux positif
                expired_count += 1
                validated_offers.append(offer)
                kept_despite_issues += 1
                print(f"   ℹ️  Gardée malgré suspicion expiration ({confidence})")
            else:
                # Si confidence "high", vraiment expirée (ex: 404)
                expired_count += 1
        
        elif status == 'invalid':
            # Pas d'URL valide
            expired_count += 1
        
        elif status == 'error':
            # Erreur technique (timeout, connection error)
            # On garde quand même (problème temporaire)
            error_count += 1
            validated_offers.append(offer)
            kept_despite_issues += 1
            print(f"   ℹ️  Gardée malgré erreur technique")
        
        else:
            uncertain_count += 1
        
        # Délai anti-ban
        if i < len(offers):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # 3. Mettre à jour les meta
    data['offres'] = validated_offers
    data['meta']['validation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['meta']['total_offres'] = len(validated_offers)
    data['meta']['nouvelles'] = len([o for o in validated_offers if o['status'] == 'new'])
    data['meta']['actives'] = len([o for o in validated_offers if o['status'] == 'active'])
    data['meta']['validated'] = validated_count
    data['meta']['expired'] = expired_count
    data['meta']['errors'] = error_count
    data['meta']['uncertain'] = uncertain_count
    data['meta']['rejected_business'] = rejected_data_count
    data['meta']['kept_despite_issues'] = kept_despite_issues  # Nouveau
    
    # 4. Sauvegarder le JSON validé
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 80)
    print("✅ VALIDATION TERMINÉE")
    print("=" * 80)
    print(f"🚫 Rejetées (métier): {rejected_data_count}")
    print(f"✅ Validées (actives): {validated_count}")
    print(f"ℹ️  Gardées malgré incertitude: {kept_despite_issues}")  # Nouveau
    print(f"💀 Expirées définitives: {expired_count - kept_despite_issues}")
    print(f"❌ Erreurs: {error_count}")
    print(f"⚠️  Incertaines: {uncertain_count}")
    print()
    print(f"💾 {len(validated_offers)} offres validées sauvegardées: {OUTPUT_FILE}")
    print(f"   (dont {kept_despite_issues} avec incertitudes tolérées)")
    print("=" * 80)

if __name__ == '__main__':
    main()
