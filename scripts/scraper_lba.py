#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper LBA Alternances — Multi-tracks
Pipeline :
  - Lecture config/tracks.yml
  - Appel API LBA par ville + codes ROME du track
  - Filtrage écoles + mots-clés du track
  - Détection de compétences
  - Gestion historique
  - Génération data/offres_lba.json

Usage:
  python -m scripts.scraper_lba                          # digital_marketing
  python -m scripts.scraper_lba --track finance
  python -m scripts.scraper_lba --all-tracks             # tous les tracks
"""

import argparse
import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests
from utils.config_loader import load_tracks, get_track

# ===== CONFIGURATION CHEMINS =====

SCRIPT_DIR  = Path(__file__).parent
BASE_DIR    = SCRIPT_DIR.parent
DATA_DIR    = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE  = DATA_DIR / "offres_lba.json"
HISTORY_FILE = DATA_DIR / "offres_historique.json"

# ===== VILLES =====

VILLES = {
    "Rennes": {
        "latitude":  48.1173,
        "longitude": -1.6778,
        "insee":     "35238",
        "radius":    30,
        "priority":  1,
    },
    "Nantes": {
        "latitude":  47.2184,
        "longitude": -1.5536,
        "insee":     "44109",
        "radius":    30,
        "priority":  2,
    },
    "Paris": {
        "latitude":  48.8566,
        "longitude": 2.3522,
        "insee":     "75056",
        "radius":    30,
        "priority":  3,
    },
}

# ===== UTILITAIRES TEXTE =====

def clean_html(html_text):
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate_text(text, max_length=200):
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


def format_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def detect_skills(title, description, skills_keywords):
    text = (title + " " + description).lower()
    detected = []
    for skill_name, keywords in skills_keywords.items():
        if any(kw.lower() in text for kw in keywords):
            detected.append(skill_name)
    return detected


# ===== API LBA =====

def fetch_lba_offers(ville_name, config, romes_codes):
    url = "https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/jobs"
    params = {
        "romes":     romes_codes,
        "latitude":  config["latitude"],
        "longitude": config["longitude"],
        "insee":     config["insee"],
        "radius":    config["radius"],
        "sources":   "partnerJob",
        "caller":    "VeilleAlternance",
    }
    print(f"  📍 {ville_name}...", end=" ", flush=True)
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data    = response.json()
        results = data.get("partnerJobs", {}).get("results", [])
        print(f"✅ {len(results)} offres")
        return results
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return []


# ===== TRANSFORMATION =====

def transform_offers(raw_offers, ville_name, ville_config, track_key, track_cfg):
    offers = []
    for offer in raw_offers:
        title_raw   = offer.get("title", "")
        company_raw = offer.get("company", {}).get("name", "")
        zipcode     = offer.get("place", {}).get("zipCode", "")

        title_clean   = title_raw.lower().replace(" ", "").replace("/", "")
        company_clean = company_raw.lower().replace(" ", "")
        cle_composite = f"{title_clean}_{company_clean}_{zipcode}"

        description_raw   = offer.get("job", {}).get("description", "")
        description_clean = clean_html(description_raw)
        description_short = truncate_text(description_clean, 200)

        detected_skills = detect_skills(
            title_raw, description_clean, track_cfg["skills_keywords"]
        )

        contract_types = offer.get("job", {}).get("type", [])
        contract_text  = " + ".join(contract_types) if contract_types else "Alternance"

        offers.append({
            "cle_composite":    cle_composite,
            "title":            title_raw,
            "company_name":     company_raw,
            "company_siret":    offer.get("company", {}).get("siret", ""),
            "city":             offer.get("place", {}).get("city", ""),
            "zipcode":          zipcode,
            "full_address":     offer.get("place", {}).get("fullAddress", ""),
            "description":      description_short,
            "description_full": description_clean,
            "detected_skills":  detected_skills,
            "contact_url":      offer.get("contact", {}).get("url", "#"),
            "partner_label":    offer.get("job", {}).get("partner_label", "LBA"),
            "creation_date":    format_date(offer.get("job", {}).get("creationDate")),
            "expiration_date":  format_date(offer.get("job", {}).get("jobExpirationDate")),
            "start_date":       format_date(offer.get("job", {}).get("jobStartDate")),
            "contract_type":    contract_text,
            "contract_duration": offer.get("job", {}).get("dureeContrat", None),
            "ville_recherche":  ville_name,
            "ville_priority":   ville_config["priority"],
            "track":            track_key,
            "status":           "new",
        })
    return offers


# ===== FILTRAGE =====

SCHOOL_EXCLUSIONS = [
    "enseigne inconnue",
    "école",
    "ecole",
    "formation",
    "université",
    "universite",
    "campus",
    "cfa",
    "centre de formation",
    "lycée",
]


def filter_schools(offers):
    filtered = [
        o for o in offers
        if not any(excl in o["company_name"].lower() for excl in SCHOOL_EXCLUSIONS)
        and o["company_siret"] != ""
    ]
    print(f"  🔍 Filtrage écoles : {len(offers)} → {len(filtered)} offres")
    return filtered


def filter_by_keywords(offers, keywords):
    keywords_lower = [k.lower() for k in keywords]
    filtered = [
        o for o in offers
        if any(k in (o["title"] + " " + o["description_full"]).lower() for k in keywords_lower)
    ]
    print(f"  🎯 Filtrage track  : {len(offers)} → {len(filtered)} offres")
    return filtered


# ===== HISTORIQUE =====

def load_history():
    if not HISTORY_FILE.exists():
        return {"last_update": None, "offers": {}}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "offers" not in data:
            data["offers"] = {}
        return data
    except Exception as e:
        print(f"⚠️ Historique corrompu, recréation : {e}")
        return {"last_update": None, "offers": {}}


def save_history(history):
    history["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def detect_new_offers(current_offers, history):
    today        = datetime.now().strftime("%Y-%m-%d")
    current_keys = {o["cle_composite"] for o in current_offers}
    history_keys = set(history["offers"].keys())
    new_keys     = current_keys - history_keys

    new_offers    = [o for o in current_offers if o["cle_composite"] in new_keys]
    active_offers = [o for o in current_offers if o["cle_composite"] in history_keys]

    for offer in current_offers:
        key = offer["cle_composite"]
        if key in new_keys:
            history["offers"][key] = {
                "first_seen":   today,
                "last_seen":    today,
                "status":       "new",
                "title":        offer["title"],
                "company_name": offer["company_name"],
                "track":        offer["track"],
            }
        else:
            history["offers"][key]["last_seen"] = today
            history["offers"][key]["status"]    = "active"

    return new_offers, active_offers, history


# ===== SCRAPE UN TRACK =====

def scrape_track(track_key, track_cfg):
    """Scrape toutes les villes pour un track. Retourne la liste d'offres formatées."""
    print(f"\n{'─'*60}")
    print(f"🎯 Track : {track_cfg['label']} ({track_key})")
    print(f"{'─'*60}")

    romes_codes = ",".join(track_cfg["rome_codes"])
    all_raw     = []

    for ville_name, config in VILLES.items():
        raw = fetch_lba_offers(ville_name, config, romes_codes)
        transformed = transform_offers(raw, ville_name, config, track_key, track_cfg)
        all_raw.extend(transformed)

    print(f"  📦 {len(all_raw)} offres brutes récupérées")

    filtered = filter_schools(all_raw)
    filtered = filter_by_keywords(filtered, track_cfg["filter_keywords"])

    return filtered


# ===== SAUVEGARDER offres_lba.json =====

def build_output(all_offers, track_keys):
    """Construit le JSON final à partir de toutes les offres (multi-tracks)."""
    history = load_history()
    new_offers, active_offers, updated_history = detect_new_offers(all_offers, history)
    save_history(updated_history)

    new_keys = {o["cle_composite"] for o in new_offers}

    print(f"\n📊 Analyse globale :")
    print(f"  🆕 Nouvelles : {len(new_offers)}")
    print(f"  ♻️  Actives   : {len(active_offers)}")

    offres_json = []
    for offer in all_offers:
        is_new = offer["cle_composite"] in new_keys
        first_seen = updated_history["offers"].get(offer["cle_composite"], {}).get("first_seen")
        last_seen  = updated_history["offers"].get(offer["cle_composite"], {}).get("last_seen")

        offres_json.append({
            "id":                   offer["cle_composite"],
            "source":               "LBA",
            "status":               "new" if is_new else "active",
            "titre":                offer["title"],
            "entreprise":           offer["company_name"],
            "ville":                offer["city"],
            "code_postal":          offer["zipcode"],
            "adresse_complete":     offer["full_address"],
            "description":          offer["description"],
            "description_complete": offer["description_full"],
            "competences_detectees": offer["detected_skills"],
            "url_candidature":      offer["contact_url"],
            "type_contrat":         offer["contract_type"],
            "duree_contrat":        offer["contract_duration"],
            "date_debut":           offer["start_date"],
            "date_creation":        offer["creation_date"],
            "date_expiration":      offer["expiration_date"],
            "plateforme_source":    offer["partner_label"],
            "ville_recherche":      offer["ville_recherche"],
            "priorite_ville":       offer["ville_priority"],
            "track":                offer["track"],
            "first_seen":           first_seen,
            "last_seen":            last_seen,
        })

    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tracks":          track_keys,
            "total_offres":    len(offres_json),
            "nouvelles":       len(new_offers),
            "actives":         len(active_offers),
        },
        "offres": offres_json,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Sauvegardé : {OUTPUT_FILE}")
    print(f"   {len(offres_json)} offres — {len(new_offers)} nouvelles")
    print("=" * 60)
    print("➡️ PROCHAINE ÉTAPE : python -m scripts.validator")
    print("=" * 60)


# ===== MAIN =====

def main():
    parser = argparse.ArgumentParser(description="Scraper LBA multi-tracks")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--track",
        default="digital_marketing",
        help="Track à scraper (ex: digital_marketing, finance...)",
    )
    group.add_argument(
        "--all-tracks",
        action="store_true",
        help="Scrape tous les tracks définis dans tracks.yml",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 SCRAPER LBA")
    print("=" * 60)

    tracks = load_tracks()

    if args.all_tracks:
        track_keys = list(tracks.keys())
        print(f"📋 Mode : TOUS LES TRACKS ({', '.join(track_keys)})")
    else:
        if args.track not in tracks:
            available = ", ".join(tracks.keys())
            raise ValueError(f"Track '{args.track}' inconnu. Disponibles : {available}")
        track_keys = [args.track]
        print(f"📋 Mode : track unique ({args.track})")

    # Scraper chaque track et accumuler
    all_offers = []
    for tk in track_keys:
        offers = scrape_track(tk, tracks[tk])
        all_offers.extend(offers)

    if not all_offers:
        print("⚠️ Aucune offre trouvée tous tracks confondus.")
        return

    build_output(all_offers, track_keys)


if __name__ == "__main__":
    main()
