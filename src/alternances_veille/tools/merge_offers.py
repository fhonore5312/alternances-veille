#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/merge_offers.py - Merge LBA + LLM, déduplication, historique
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR         = Path(__file__).parent.parent.parent.parent
DATA_DIR         = BASE_DIR / "data"

LBA_FILE         = DATA_DIR / "offres_lba_validated.json"
LLM_FILE         = DATA_DIR / "offres_llm_validated.json"
HISTORIQUE_FILE  = DATA_DIR / "offres_historique.json"
OUTPUT_FILE      = DATA_DIR / "offres_merged.json"

# ===== DOMAINES NON VÉRIFIABLES (HTTP 403 systématique) =====
# Ces plateformes bloquent le crawling — les offres uncertain qu'elles génèrent
# sont exclues du merge pour éviter les liens morts.
BLOCKED_DOMAINS_UNCERTAIN = [
    "directemploi.com",
]

# ===== UTILITAIRES =====

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_offer_id(offer: dict) -> str:
    return offer.get("id", "")

def get_url_key(offer: dict):
    url = offer.get("url_candidature", "")
    if not url or url == "#":
        return None
    return url.split("?")[0].rstrip("/").lower()

def is_blocked_uncertain(offer: dict) -> bool:
    """True si l'offre est uncertain ET provient d'un domaine non vérifiable (403 systématique)."""
    if offer.get("validation_status") != "uncertain":
        return False
    url  = offer.get("url_candidature", "")
    code = offer.get("validation_details", {}).get("status_code")
    return code == 403 and any(d in url for d in BLOCKED_DOMAINS_UNCERTAIN)

# ===== POINT D'ENTRÉE TOOL =====

def run_merge_offers() -> tuple:
    """
    Fusionne LBA + LLM, gère l'historique new/active.
    Retourne (total_offres, nouvelles_offres).
    """
    print(f"\n{'='*60}")
    print("📦 MERGE OFFERS")
    print(f"{'='*60}")

    # 1. Charger LBA (obligatoire)
    lba_data = load_json(LBA_FILE)
    if not lba_data:
        print(f"❌ {LBA_FILE.name} introuvable")
        return 0, 0

    lba_offers_raw = [
        o for o in lba_data.get("offres", [])
        if o.get("validation_status") in ("validated", "uncertain", "error")
    ]
    # Exclure les uncertain de domaines non vérifiables (403 systématique)
    lba_offers    = [o for o in lba_offers_raw if not is_blocked_uncertain(o)]
    blocked_count = len(lba_offers_raw) - len(lba_offers)

    print(f"  📥 LBA : {len(lba_offers_raw)} retenues (validées/incertaines/erreurs)")
    if blocked_count:
        print(f"  🚫 {blocked_count} uncertain 403 exclues ({', '.join(BLOCKED_DOMAINS_UNCERTAIN)})")
    print(f"  📥 LBA conservées : {len(lba_offers)}")

    # 2. Charger LLM (optionnel)
    llm_offers = []
    llm_data   = load_json(LLM_FILE)
    if llm_data:
        llm_offers = [
            o for o in llm_data.get("offres", [])
            if o.get("validation_status") == "validated"
        ]
        print(f"  📥 LLM : {len(llm_offers)} offres retenues")
    else:
        print("  ℹ️  LLM : aucun fichier (agents non exécutés)")

    # 3. Charger historique
    historique_data = load_json(HISTORIQUE_FILE)
    if historique_data:
        historique_ids  = {get_offer_id(o) for o in historique_data.get("offres", [])}
        historique_urls = {get_url_key(o) for o in historique_data.get("offres", []) if get_url_key(o)}
        print(f"  📚 Historique : {len(historique_ids)} offres connues")
    else:
        historique_ids  = set()
        historique_urls = set()
        print("  ℹ️  Historique : première exécution")

    # 4. Patch rétrocompatibilité track manquant
    for o in lba_offers + llm_offers:
        if not o.get("track"):
            o["track"] = "digital_marketing"

    # 5. Dédup interne LBA
    seen_ids  = set()
    seen_urls = set()
    dedup_lba = []
    for o in lba_offers:
        oid  = get_offer_id(o)
        ukey = get_url_key(o)
        if oid in seen_ids or (ukey and ukey in seen_urls):
            continue
        dedup_lba.append(o)
        seen_ids.add(oid)
        if ukey:
            seen_urls.add(ukey)
    if len(dedup_lba) < len(lba_offers):
        print(f"  🧹 {len(lba_offers) - len(dedup_lba)} doublons LBA supprimés")

    # 6. Fusion LBA + LLM (sans doublons cross-source)
    all_offers = list(dedup_lba)
    dupes_llm  = 0
    for o in llm_offers:
        oid  = get_offer_id(o)
        ukey = get_url_key(o)
        if oid in seen_ids or (ukey and ukey in seen_urls):
            dupes_llm += 1
            continue
        all_offers.append(o)
        seen_ids.add(oid)
        if ukey:
            seen_urls.add(ukey)
    if dupes_llm:
        print(f"  🧹 {dupes_llm} doublons LLM ignorés")

    # 7. Marquer new / active
    nouvelles = 0
    actives   = 0
    for o in all_offers:
        oid      = get_offer_id(o)
        ukey     = get_url_key(o)
        is_known = oid in historique_ids or (ukey and ukey in historique_urls)
        if is_known:
            o["status"] = "active"
            actives += 1
        else:
            o["status"] = "new"
            nouvelles += 1
            print(f"  🆕 {o.get('titre','?')[:45]} — {o.get('entreprise','?')}")

    # 8. Trier : track → priorité ville → new en premier
    all_offers.sort(key=lambda x: (
        x.get("track", "zzz"),
        x.get("priorite_ville", 99),
        0 if x.get("status") == "new" else 1,
    ))

    # 9. Stats par track
    stats_by_track = {}
    for o in all_offers:
        t = o.get("track", "unknown")
        if t not in stats_by_track:
            stats_by_track[t] = {"total": 0, "nouvelles": 0}
        stats_by_track[t]["total"] += 1
        if o.get("status") == "new":
            stats_by_track[t]["nouvelles"] += 1

    # 10. Mettre à jour l'historique
    existing_hist  = historique_data.get("offres", []) if historique_data else []
    existing_by_id = {get_offer_id(o): o for o in existing_hist}
    for o in all_offers:
        existing_by_id[get_offer_id(o)] = o
    updated_historique = list(existing_by_id.values())

    save_json(HISTORIQUE_FILE, {
        "meta": {
            "date_mise_a_jour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_offres":     len(updated_historique),
        },
        "offres": updated_historique,
    })

    # 11. Sauvegarder offres_merged.json
    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_offres":    len(all_offers),
            "nouvelles":       nouvelles,
            "actives":         actives,
            "source_lba":      len(dedup_lba),
            "source_llm":      len(llm_offers) - dupes_llm,
            "stats_by_track":  stats_by_track,
        },
        "offres": all_offers,
    }
    save_json(OUTPUT_FILE, output)

    print(f"\n  ✅ {len(all_offers)} offres fusionnées ({nouvelles} nouvelles, {actives} actives)")
    print(f"  💾 → {OUTPUT_FILE.name}")

    return len(all_offers), nouvelles


if __name__ == "__main__":
    run_merge_offers()
