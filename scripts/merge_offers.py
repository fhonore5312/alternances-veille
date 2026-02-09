#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusion des offres LBA + Perplexity
Adapté pour la nouvelle structure de dossiers
"""

import json
from datetime import datetime
import os
from pathlib import Path

# Configuration des chemins
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

# Fichiers
LBA_FILE = DATA_DIR / "offres_lba.json"
PERPLEXITY_FILE = DATA_DIR / "offres_perplexity.json"
OUTPUT_FILE = DATA_DIR / "offres_merged.json"

def load_json(filepath):
    """Charge un fichier JSON"""
    if not filepath.exists():
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def merge_offers():
    """Fusionne les offres LBA + Perplexity"""
    print("=" * 60)
    print("🔄 FUSION DES OFFRES LBA + PERPLEXITY")
    print("=" * 60)

    # 1. Charger LBA (obligatoire)
    lba_data = load_json(LBA_FILE)
    if not lba_data:
        print(f"❌ Erreur : {LBA_FILE} introuvable")
        return
    print(f"📥 LBA : {lba_data['meta']['total_offres']} offres")

    # 2. Charger Perplexity (optionnel)
    perplexity_data = load_json(PERPLEXITY_FILE)
    if perplexity_data:
        print(f"📥 Perplexity : {len(perplexity_data.get('offres', []))} offres")
    else:
        print("ℹ️  Aucun fichier offres_perplexity.json (mode LBA seul)")
        perplexity_data = {"offres": []}

    # 3. Fusionner
    merged_offers = lba_data['offres'].copy()

    duplicates = 0
    added = 0

    for perplexity_offer in perplexity_data.get('offres', []):
        # Vérifier doublon (même entreprise + même titre + même ville)
        is_duplicate = False
        for existing in merged_offers:
            if (existing['entreprise'].lower() == perplexity_offer['entreprise'].lower() and
                existing['titre'].lower() == perplexity_offer['titre'].lower() and
                existing['ville'].lower() == perplexity_offer['ville'].lower()):
                is_duplicate = True
                duplicates += 1
                print(f"  ⚠️  Doublon ignoré : {perplexity_offer['titre']} - {perplexity_offer['entreprise']}")
                break

        if not is_duplicate:
            merged_offers.append(perplexity_offer)
            added += 1
            print(f"  ✅ Ajoutée : {perplexity_offer['titre']} - {perplexity_offer['entreprise']}")

    print(f"\n📊 Fusion :")
    print(f"  ✅ {added} offres Perplexity ajoutées")
    print(f"  ⚠️  {duplicates} doublons ignorés")

    # 4. Trier
    merged_offers.sort(key=lambda x: (
        x['priorite_ville'],
        0 if x['status'] == 'new' else 1
    ))

    # 5. JSON final
    output = {
        "meta": {
            "date_generation": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "sources": ["LBA"] if not perplexity_data.get('offres') else ["LBA", "Perplexity"],
            "total_offres": len(merged_offers),
            "nouvelles": len([o for o in merged_offers if o['status'] == 'new']),
            "actives": len([o for o in merged_offers if o['status'] == 'active']),
            "source_lba": lba_data['meta']['total_offres'],
            "source_perplexity": len(perplexity_data.get('offres', []))
        },
        "offres": merged_offers
    }

    # 6. Sauvegarder
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Fichier fusionné sauvegardé : {OUTPUT_FILE}")
    print(f"📊 Total : {output['meta']['total_offres']} offres")
    print(f"  🆕 {output['meta']['nouvelles']} nouvelles")
    print(f"  ♻️  {output['meta']['actives']} actives")
    print("\n➡️  PROCHAINE ÉTAPE : Génération HTML + Email")
    print("  Exécute : python generate_html_email.py")
    print("=" * 60)

if __name__ == '__main__':
    merge_offers()
