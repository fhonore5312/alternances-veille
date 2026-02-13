#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fusion des offres LBA + Perplexity + Gestion historique

IMPORTANT: Ce script utilise les fichiers _validated.json
générés par validator.py
"""

import json
from datetime import datetime
from pathlib import Path

# Configuration des chemins
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Fichiers (MODIFIÉ: utilise _validated.json)
LBA_FILE = DATA_DIR / "offres_lba_validated.json"
PERPLEXITY_FILE = DATA_DIR / "offres_perplexity_validated.json"
HISTORIQUE_FILE = DATA_DIR / "offres_historique.json"
OUTPUT_FILE = DATA_DIR / "offres_merged.json"

def load_json(filepath):
    """Charge un fichier JSON"""
    if not filepath.exists():
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    """Sauvegarde un fichier JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_offer_id(offer):
    """Génère un ID unique pour une offre"""
    titre = offer.get('titre', '').lower().strip()
    entreprise = offer.get('entreprise', '').lower().strip()
    ville = offer.get('ville', '').lower().strip()
    return f"{titre}|{entreprise}|{ville}"

def merge_offers():
    """Fusionne les offres LBA + Perplexity + Gère l'historique"""
    print("=" * 70)
    print("🔄 FUSION DES OFFRES LBA + PERPLEXITY + HISTORIQUE")
    print("=" * 70)
    
    # 1. Charger LBA (obligatoire)
    lba_data = load_json(LBA_FILE)
    if not lba_data:
        print(f"❌ Erreur : {LBA_FILE} introuvable")
        print("   → Exécutez d'abord: python validator.py")
        return
    
    print(f"📥 LBA : {lba_data['meta']['total_offres']} offres")
    
    # Filtrer uniquement les offres validées/uncertain (exclure rejected/expired définitives)
    lba_offers = [
        o for o in lba_data.get('offres', [])
        if o.get('validation_status') in ['validated', 'uncertain', 'error']
    ]
    print(f"   → {len(lba_offers)} offres retenues (validées/incertaines)")
    
    # 2. Charger Perplexity (optionnel)
    perplexity_data = load_json(PERPLEXITY_FILE)
    perplexity_offers = []
    
    if perplexity_data and perplexity_data.get('offres'):
        # Filtrer uniquement les offres validées
        perplexity_offers = [
            o for o in perplexity_data.get('offres', [])
            if o.get('validation_status') == 'validated'
        ]
        print(f"📥 Perplexity : {len(perplexity_data.get('offres', []))} offres")
        print(f"   → {len(perplexity_offers)} offres retenues (validées)")
    else:
        print("ℹ️  Aucune offre Perplexity (recherche manuelle pas encore faite)")
    
    # 3. Charger l'historique (optionnel)
    historique_data = load_json(HISTORIQUE_FILE)
    if historique_data:
        print(f"📚 Historique : {len(historique_data.get('offres', []))} offres")
        historique_ids = {generate_offer_id(o): o for o in historique_data.get('offres', [])}
    else:
        print("ℹ️  Aucun historique (première exécution)")
        historique_ids = {}
    
    # 4. Fusionner LBA + Perplexity
    all_offers = []
    seen_ids = set()
    duplicates_perplexity = 0
    
    # Ajouter offres LBA
    for offer in lba_offers:
        offer_id = generate_offer_id(offer)
        if offer_id not in seen_ids:
            all_offers.append(offer)
            seen_ids.add(offer_id)
    
    # Ajouter offres Perplexity (sans doublons)
    for offer in perplexity_offers:
        offer_id = generate_offer_id(offer)
        if offer_id in seen_ids:
            duplicates_perplexity += 1
            print(f"  ⚠️  Doublon Perplexity ignoré : {offer['titre']} - {offer['entreprise']}")
        else:
            all_offers.append(offer)
            seen_ids.add(offer_id)
            print(f"  ✅ Perplexity ajoutée : {offer['titre']} - {offer['entreprise']}")
    
    # 5. Comparer avec l'historique et marquer status
    nouvelles = 0
    actives = 0
    
    for offer in all_offers:
        offer_id = generate_offer_id(offer)
        
        if offer_id in historique_ids:
            # Offre existante dans l'historique
            offer['status'] = 'active'
            actives += 1
        else:
            # Nouvelle offre jamais vue
            offer['status'] = 'new'
            nouvelles += 1
            print(f"  🆕 NOUVELLE : {offer['titre']} - {offer['entreprise']}")
    
    print(f"\n📊 Résultat fusion :")
    print(f"  ✅ {len(perplexity_offers) - duplicates_perplexity} offres Perplexity ajoutées")
    print(f"  ⚠️  {duplicates_perplexity} doublons Perplexity ignorés")
    print(f"  🆕 {nouvelles} nouvelles offres")
    print(f"  ♻️  {actives} offres déjà connues")
    
    # 6. Trier par priorité
    all_offers.sort(key=lambda x: (
        x.get('priorite_ville', 99),
        0 if x['status'] == 'new' else 1
    ))
    
    # 7. Mettre à jour l'historique (ajouter les nouvelles offres)
    updated_historique = list(historique_ids.values())  # Anciennes offres
    
    for offer in all_offers:
        offer_id = generate_offer_id(offer)
        if offer_id not in historique_ids:
            # Ajouter uniquement les nouvelles offres à l'historique
            updated_historique.append(offer.copy())
    
    # Sauvegarder l'historique mis à jour
    historique_output = {
        "meta": {
            "date_mise_a_jour": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_offres": len(updated_historique)
        },
        "offres": updated_historique
    }
    
    save_json(HISTORIQUE_FILE, historique_output)
    print(f"\n📚 Historique mis à jour : {len(updated_historique)} offres totales")
    
    # 8. Sauvegarder offres_merged.json (pour affichage)
    output = {
        "meta": {
            "date_generation": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "sources": ["LBA"] if not perplexity_offers else ["LBA", "Perplexity"],
            "total_offres": len(all_offers),
            "nouvelles": nouvelles,
            "actives": actives,
            "source_lba": len(lba_offers),
            "source_perplexity": len(perplexity_offers)
        },
        "offres": all_offers
    }
    
    save_json(OUTPUT_FILE, output)
    
    print(f"\n💾 Fichier fusionné : {OUTPUT_FILE}")
    print(f"📊 Total : {output['meta']['total_offres']} offres actives")
    print(f"  🆕 {output['meta']['nouvelles']} nouvelles")
    print(f"  ♻️  {output['meta']['actives']} déjà connues")
    print("\n➡️  PROCHAINE ÉTAPE : python generate_html_email.py")
    print("=" * 70)

if __name__ == '__main__':
    merge_offers()
