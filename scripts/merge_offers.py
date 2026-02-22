#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusion des offres LBA + Perplexity + Gestion historique
IMPORTANT: Ce script utilise les fichiers _validated.json
générés par validator.py

Usage:
  python -m scripts.merge_offers
"""

import json
from datetime import datetime
from pathlib import Path
from utils.deduplication import generate_offer_id, get_url_key, deduplicate_offers

# ===== CONFIGURATION CHEMINS =====

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

LBA_FILE        = DATA_DIR / "offres_lba_validated.json"
PERPLEXITY_FILE = DATA_DIR / "offres_perplexity_validated.json"
HISTORIQUE_FILE = DATA_DIR / "offres_historique.json"
OUTPUT_FILE     = DATA_DIR / "offres_merged.json"


# ===== UTILITAIRES =====

def load_json(filepath):
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===== MERGE PRINCIPAL =====

def merge_offers():
    print("=" * 70)
    print("🔄 FUSION DES OFFRES LBA + PERPLEXITY + HISTORIQUE")
    print("=" * 70)

    # 1. Charger LBA (obligatoire)
    lba_data = load_json(LBA_FILE)
    if not lba_data:
        print(f"❌ Erreur : {LBA_FILE} introuvable")
        print("  → Exécutez d'abord : python -m scripts.validator")
        return

    lba_offers = [
        o for o in lba_data.get("offres", [])
        if o.get("validation_status") in ["validated", "uncertain", "error"]
    ]
    print(f"📥 LBA         : {lba_data['meta']['total_offres']} offres chargées")
    print(f"   → {len(lba_offers)} retenues (validées/incertaines)")

    # 2. Charger Perplexity (optionnel)
    perplexity_data = load_json(PERPLEXITY_FILE)
    perplexity_offers = []
    if perplexity_data and perplexity_data.get("offres"):
        perplexity_offers = [
            o for o in perplexity_data.get("offres", [])
            if o.get("validation_status") == "validated"
        ]
        print(f"📥 Perplexity  : {len(perplexity_data.get('offres', []))} offres chargées")
        print(f"   → {len(perplexity_offers)} retenues (validées)")
    else:
        print("ℹ️  Perplexity  : Aucun fichier (recherche manuelle non faite)")

    # 3. Charger l'historique
    historique_data = load_json(HISTORIQUE_FILE)
    if historique_data:
        print(f"📚 Historique  : {len(historique_data.get('offres', []))} offres connues")
        historique_ids  = {generate_offer_id(o): o for o in historique_data.get("offres", [])}
        historique_urls = {get_url_key(o) for o in historique_data.get("offres", []) if get_url_key(o)}
    else:
        print("ℹ️  Historique  : Aucun (première exécution)")
        historique_ids  = {}
        historique_urls = set()

    # 4. Patch rétrocompatibilité : garantir le champ track
    for offer in lba_offers + perplexity_offers:
        if not offer.get("track"):
            offer["track"] = "digital_marketing"

    # 5. Déduplication interne LBA (au cas où)
    lba_offers, lba_dups = deduplicate_offers(lba_offers)
    if lba_dups:
        print(f"   🔁 {lba_dups} doublons internes LBA supprimés")

    # 6. Fusion LBA + Perplexity sans doublons cross-source
    seen_ids  = {generate_offer_id(o) for o in lba_offers}
    seen_urls = {get_url_key(o) for o in lba_offers if get_url_key(o)}

    all_offers = list(lba_offers)
    duplicates_perplexity = 0

    for offer in perplexity_offers:
        url_key  = get_url_key(offer)
        offer_id = generate_offer_id(offer)

        if (url_key and url_key in seen_urls) or offer_id in seen_ids:
            duplicates_perplexity += 1
            print(f"  ⚠️ Doublon Perplexity ignoré : {offer['titre'][:45]} - {offer['entreprise']}")
        else:
            all_offers.append(offer)
            seen_ids.add(offer_id)
            if url_key:
                seen_urls.add(url_key)
            print(f"  ✅ Perplexity ajoutée : {offer['titre'][:45]} - {offer['entreprise']}")

    # 7. Marquer new / active vs historique
    nouvelles = 0
    actives   = 0

    for offer in all_offers:
        offer_id = generate_offer_id(offer)
        url_key  = get_url_key(offer)

        is_known = (
            offer_id in historique_ids
            or (url_key and url_key in historique_urls)
        )

        if is_known:
            offer["status"] = "active"
            actives += 1
        else:
            offer["status"] = "new"
            nouvelles += 1
            print(f"  🆕 NOUVELLE : {offer['titre'][:45]} - {offer['entreprise']}")

    print(f"\n📊 Résultat fusion :")
    print(f"   ✅ {len(perplexity_offers) - duplicates_perplexity} offres Perplexity ajoutées")
    print(f"   ⚠️ {duplicates_perplexity} doublons Perplexity ignorés")
    print(f"   🆕 {nouvelles} nouvelles offres")
    print(f"   ♻️  {actives} offres déjà connues")

    # 8. Trier : par track, puis priorité ville, puis new en premier
    all_offers.sort(key=lambda x: (
        x.get("track", "zzz"),
        x.get("priorite_ville", 99),
        0 if x.get("status") == "new" else 1,
    ))

    # 9. Mettre à jour l'historique
    updated_historique = list(historique_ids.values())
    for offer in all_offers:
        offer_id = generate_offer_id(offer)
        url_key  = get_url_key(offer)
        is_known = (
            offer_id in historique_ids
            or (url_key and url_key in historique_urls)
        )
        if not is_known:
            updated_historique.append(offer.copy())

    save_json(HISTORIQUE_FILE, {
        "meta": {
            "date_mise_a_jour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_offres": len(updated_historique),
        },
        "offres": updated_historique,
    })
    print(f"\n📚 Historique mis à jour : {len(updated_historique)} offres totales")

    # 10. Stats par track pour le HTML
    tracks_present = sorted(set(o.get("track", "digital_marketing") for o in all_offers))
    stats_by_track = {
        track: {
            "total": len([o for o in all_offers if o.get("track") == track]),
            "nouvelles": len([o for o in all_offers if o.get("track") == track and o.get("status") == "new"]),
        }
        for track in tracks_present
    }

    # 11. Sauvegarder offres_merged.json
    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": ["LBA"] if not perplexity_offers else ["LBA", "Perplexity"],
            "total_offres": len(all_offers),
            "nouvelles": nouvelles,
            "actives": actives,
            "source_lba": len(lba_offers),
            "source_perplexity": len(perplexity_offers) - duplicates_perplexity,
            "stats_by_track": stats_by_track,
        },
        "offres": all_offers,
    }

    save_json(OUTPUT_FILE, output)

    print(f"\n💾 Fichier fusionné : {OUTPUT_FILE}")
    print(f"📊 Total : {len(all_offers)} offres")
    print(f"   🆕 {nouvelles} nouvelles  |  ♻️  {actives} déjà connues")
    print()
    for track, stats in stats_by_track.items():
        print(f"   🎯 {track:<25} : {stats['total']} offres ({stats['nouvelles']} nouvelles)")

    print("\n➡️ PROCHAINE ÉTAPE : python -m scripts.generate_html_email")
    print("=" * 70)


if __name__ == "__main__":
    merge_offers()
