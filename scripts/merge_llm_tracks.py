#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_llm_tracks.py - Fusionne les fichiers LLM par track en un seul offres_llm.json
A lancer AVANT validator.py
Usage: python -m scripts.merge_llm_tracks
"""

import json
import re
from pathlib import Path
from datetime import datetime, date

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

TRACK_FILES = [
    "offres_agent_digitalmarketing.json",
    "offres_agent_finance.json",
    "offres_agent_supplychain.json",
    "offres_agent_businessdev.json",
    "offres_agent_rh.json",
    "offres_agent_communication.json",
]

TRACK_NORMALIZE = {
    "digitalmarketing": "digital_marketing",
    "businessdev":      "business_dev",
}

OUTPUT_FILE = DATA_DIR / "offres_llm.json"


def clean_raw(raw):
    raw = raw.strip()
    if raw.startswith("{"):
        return raw
    m = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\{[\s\S]+\})", raw)
    if m:
        return m.group(1).strip()
    return raw


def repair_truncated_json(raw):
    """Tente de réparer un JSON tronqué (token limit LLM) en fermant les crochets manquants."""
    for closing in ["\n  ]\n}", "\n]}"]:
        try:
            data = json.loads(raw.rstrip() + closing)
            print("  [repair] JSON tronqué réparé automatiquement")
            return data
        except json.JSONDecodeError:
            continue
    return None


def normalize_offer(offer, today_str):
    """Normalise les champs problématiques pour le validator."""
    # date_creation null → first_seen converti en DD/MM/YYYY
    if offer.get("date_creation") is None:
        raw_date = offer.get("first_seen") or today_str
        try:
            offer["date_creation"] = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            offer["date_creation"] = raw_date

    # status : incertain/None → new
    if offer.get("status") not in ("new", "active"):
        offer["status"] = "new"

    return offer


def main():
    print("=" * 60)
    print("Fusion des fichiers LLM par track -> offres_llm.json")
    print("=" * 60)

    all_offres = []
    sources = []
    today_str = str(date.today())

    for filename in TRACK_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print("  [skip] " + filename + " non trouve")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        raw = clean_raw(raw)

        data = None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print("  [ERREUR JSON] " + filename + " : " + str(e))
            data = repair_truncated_json(raw)
            if data is None:
                print("  [SKIP] " + filename + " — réparation impossible")
                continue

        offres = data.get("offres", [])

        track_raw  = filename.replace("offres_agent_", "").replace(".json", "")
        track_norm = TRACK_NORMALIZE.get(track_raw, track_raw)

        for o in offres:
            o["track"] = track_norm
            normalize_offer(o, today_str)

        all_offres.extend(offres)
        sources.append(track_norm)
        print("  [OK] " + filename + " : " + str(len(offres)) + " offres (track=" + track_norm + ")")

    if not all_offres:
        print("Aucune offre LLM trouvee. Verifiez les fichiers data/offres_agent_*.json")
        return

    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": sources,
            "total_offres": len(all_offres),
        },
        "offres": all_offres,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("")
    print("OK : " + str(OUTPUT_FILE))
    print("  " + str(len(all_offres)) + " offres depuis " + str(len(sources)) + " track(s) : " + str(sources))
    print("")
    print("Prochaine etape : python -m scripts.validator")
    print("=" * 60)


if __name__ == "__main__":
    main()
