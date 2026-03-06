#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper LBA Alternances — Multi-tracks
Pipeline :
- Lecture config/tracks.yml
- Appel API LBA par ville + codes ROME du track
- Filtrage écoles (nom + description) + mots-clés du track
- Filtrage offres vides/fantômes
- Filtrage dates passées
- Filtrage niveau BAC+5 (track finance)
- Détection de compétences
- Gestion historique
- Génération data/offres_lba.json

Note API LBA : l'endpoint /api/job/v1/search ne propose pas de filtre
niveauDiplome — tout le filtrage niveau se fait côté code.

Usage:
python -m scripts.scraper_lba                 # digital_marketing
python -m scripts.scraper_lba --track finance
python -m scripts.scraper_lba --all-tracks    # tous les tracks
"""

import argparse
import json
import os
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

from utils.config_loader import load_tracks, get_track

# ===== CONFIGURATION CHEMINS =====

SCRIPT_DIR   = Path(__file__).parent
BASE_DIR     = SCRIPT_DIR.parent
DATA_DIR     = BASE_DIR / "data"
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

# ===== EXTRACTION ENTREPRISE DEPUIS LE TITRE =====

# Mots génériques qui NE sont PAS des noms d'entreprise
_GENERIC_STARTS = {
    "comptable", "collaborateur", "aide", "auditeur", "auditeur.rice",
    "contrôleur", "controleur", "alternant", "apprenti", "gestionnaire",
    "assistant", "assistante", "assistante(e)", "assistant(e)", "chargé",
    "chargée", "responsable", "chef", "directeur", "analyste", "stagiaire",
    "alternance", "emploi", "offre", "poste", "recrutement",
}

def _try_extract_company_from_title(title: str) -> str:
    """
    Tente d'extraire un nom d'entreprise depuis le titre quand company_name est vide.
    Patterns gérés :
      - "COMPANY - Job title..."   → entreprise en début
      - "Job title ... - COMPANY"  → entreprise en fin
    Retourne "" si rien de probant n'est trouvé.
    """
    if not title:
        return ""

    _NOISE_SUFFIX = {"h/f", "f/h", "(h/f)", "(f/h)", "paris", "rennes",
                     "nantes", "lyon", "bordeaux", "france", "alternance"}

    # Pattern 1 — entreprise en DÉBUT : "COMPANY - ..."
    m = re.match(
        r"^([A-ZÀ-Ü][A-Za-zÀ-ÿ0-9 &.''\-]{2,40}?)\s*[-–—]\s*"
        r"(?:Comptable|Auditeur|Alternance|Assistant|Collaborateur|"
        r"Contrôleur|Gestionnaire|Analyste|Apprenti|Aide|Chargé)",
        title
    )
    if m:
        candidate = m.group(1).strip()
        if candidate.lower().split()[0] not in _GENERIC_STARTS and len(candidate) > 3:
            return candidate

    # Pattern 2 — entreprise en FIN : "... - COMPANY"
    m2 = re.search(
        r"[-–—]\s*([A-ZÀ-Ü][A-Za-zÀ-ÿ0-9 &.''\-]{2,40})\s*$", title
    )
    if m2:
        candidate = m2.group(1).strip()
        if (len(candidate) > 3
                and candidate.lower() not in _NOISE_SUFFIX
                and candidate.lower().split()[0] not in _GENERIC_STARTS):
            return candidate

    return ""

# ===== API LBA =====

def fetch_lba_offers(ville_name, config, romes_codes):
    url     = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
    headers = {"Authorization": f"Bearer {os.getenv('LBA_API_KEY', '')}"}
    params  = {
        "romes":     romes_codes,
        "latitude":  config["latitude"],
        "longitude": config["longitude"],
        "radius":    config["radius"],
        "caller":    "VeilleAlternance",
    }
    print(f"  📍 {ville_name}...", end=" ", flush=True)
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        print(f"[{response.status_code}]", end=" ")
        if response.status_code != 200:
            print(f"→ {response.text[:200]}")
            return []
        data    = response.json()
        results = (
            data.get("jobs")
            or data.get("results")
            or data.get("partnerJobs", {}).get("results", [])
        )
        print(f"✅ {len(results)} offres")
        return results
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return []

# ===== TRANSFORMATION =====

def transform_offers(raw_offers, ville_name, ville_config, track_key, track_cfg):
    offers = []
    for offer in raw_offers:
        title_raw   = offer.get("offer", {}).get("title", "")
        company_raw = offer.get("workplace", {}).get("name") or ""
        siret       = offer.get("workplace", {}).get("siret", "")
        address     = offer.get("workplace", {}).get("location", {}).get("address", "")

        zip_match  = re.search(r"\b(\d{5})\b", address)
        zipcode    = zip_match.group(1) if zip_match else ""
        city_match = re.search(r"\d{5}\s+(.+)$", address)
        city       = city_match.group(1).title() if city_match else ""

        # ── Extraction entreprise depuis le titre (France Travail ne la fournit pas) ──
        if not company_raw.strip():
            company_raw = _try_extract_company_from_title(title_raw)

        title_clean   = title_raw.lower().replace(" ", "").replace("/", "")
        company_clean = company_raw.lower().replace(" ", "")
        cle_composite = f"{title_clean}_{company_clean}_{zipcode}"

        description_raw   = offer.get("offer", {}).get("description", "")
        description_clean = clean_html(description_raw)
        description_short = truncate_text(description_clean, 200)

        detected_skills = detect_skills(
            title_raw, description_clean, track_cfg["skills_keywords"]
        )

        contract_types = offer.get("contract", {}).get("type", [])
        contract_text  = " + ".join(contract_types) if contract_types else "Alternance"

        offers.append({
            "cle_composite":     cle_composite,
            "title":             title_raw,
            "company_name":      company_raw,
            "company_siret":     siret,
            "city":              city,
            "zipcode":           zipcode,
            "full_address":      address,
            "description":       description_short,
            "description_full":  description_clean,
            "detected_skills":   detected_skills,
            "contact_url":       offer.get("apply", {}).get("url", "#"),
            "partner_label":     offer.get("identifier", {}).get("partner_label", "LBA"),
            "creation_date":     None,
            "expiration_date":   None,
            "start_date":        format_date(offer.get("contract", {}).get("start")),
            "contract_type":     contract_text,
            "contract_duration": offer.get("contract", {}).get("duration"),
            "ville_recherche":   ville_name,
            "ville_priority":    ville_config["priority"],
            "track":             track_key,
            "status":            "new",
        })
    return offers

# ===== FILTRAGE =====

# ── Exclusions écoles ────────────────────────────────────────────────────────

SCHOOL_EXCLUSIONS_NAME = [
    "enseigne inconnue", "école", "ecole",
    "université", "universite", "campus", "cfa",
    "centre de formation", "lycée",
    # Finance : organismes qui spamment des offres non étudiantes ─────────────
    "neogest",                          # NEOGEST EDUCATION GROUP
    "education group",                  # pattern générique xxx Education Group
    "institut superieur de techniques", # ISTECH Bretagne
    "groupe igf",                       # IGF : école compta, offres dates passées
    "igf formation",
]

SCHOOL_EXCLUSIONS_DESC = [
    "l'iscod", "alticome", "alticom,", "mydigitalschool", "studi ", "sup de pub",
    "groupe igs", "bringme", "optez pour l'alternance nouvelle génération",
    "préparez un bachelor", "préparez un master", "recrutement en 4 étapes",
    "formation prise en charge à 100% par l'entreprise",
    "recherche pour l'une de ses entreprises partenaires",
    "nos formations diplômantes reconnues par l'etat",
    "school 100 % en alternance", "notre école recrute pour",
    "notre cfa recrute pour",
    "postulez à cette offre si vous souhaitez intégrer",
]

# Titres purement génériques sans entreprise identifiable
_GENERIC_TITLE_PATTERNS = re.compile(
    r"^(comptable|aide[- ]comptable|collaborateur comptable|"
    r"comptable fournisseurs|comptable clients|comptable général|"
    r"aide comptable|assistant[e]? comptable|"
    r"responsable marketing|assistant[e]? marketing|"
    r"gestionnaire|analyste financier)[^a-zà-ÿ]",
    re.IGNORECASE
)

def filter_schools(offers: list) -> list:
    before   = len(offers)
    filtered = []
    for o in offers:
        name_lower = o["company_name"].lower()
        desc_lower = o["description_full"].lower()
        if any(excl in name_lower for excl in SCHOOL_EXCLUSIONS_NAME):
            continue
        if any(excl in desc_lower for excl in SCHOOL_EXCLUSIONS_DESC):
            continue
        filtered.append(o)
    print(f"  🔍 Filtrage écoles       : {before} → {len(filtered)} offres")
    return filtered

def filter_by_keywords(offers: list, keywords: list) -> list:
    keywords_lower = [k.lower() for k in keywords]
    filtered = [
        o for o in offers
        if any(k in o["title"].lower() for k in keywords_lower)
    ]
    print(f"  🎯 Filtrage track        : {len(offers)} → {len(filtered)} offres")
    return filtered

def filter_empty_offers(offers: list) -> list:
    """
    Exclut les offres fantômes/inutilisables :
    - Pas d'entreprise (même après extraction du titre) ET description < 80 chars
    - OU titre purement générique (ex: 'Comptable (H/F)') SANS entreprise identifiée
    """
    kept, excluded = [], 0
    for o in offers:
        has_company  = bool(o["company_name"].strip())
        desc_ok      = len(o["description_full"]) >= 80
        generic_title = bool(_GENERIC_TITLE_PATTERNS.match(o["title"].strip()))

        if not has_company and generic_title:
            excluded += 1
            continue  # titre générique + pas d'entreprise → inutile pour email et RH
        if not has_company and not desc_ok:
            excluded += 1
            continue  # fantôme : rien d'identifiable

        kept.append(o)
    if excluded:
        print(f"  🗑️ Filtrage vides/génériques: {len(offers)} → {len(kept)} offres ({excluded} exclues)")
    return kept

def filter_by_start_date(offers: list) -> list:
    """Exclut les offres dont la date_debut est strictement antérieure à aujourd'hui."""
    today    = datetime.now()
    kept     = []
    excluded = 0
    for o in offers:
        sd = o.get("start_date")
        if not sd:
            kept.append(o)
            continue
        parsed = False
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(str(sd), fmt)
                if dt < today:
                    excluded += 1
                else:
                    kept.append(o)
                parsed = True
                break
            except ValueError:
                continue
        if not parsed:
            kept.append(o)
    print(f"  📅 Filtrage dates passées : {len(offers)} → {len(kept)} offres ({excluded} exclues)")
    return kept

# ── Filtrage niveau BAC+5 (finance uniquement) ───────────────────────────────

_BAC5_KW = [
    "master", "bac+5", "bac +5", "m1", "m2", "dscg",
    "grande école", "grande ecole", "msc", "bac+4", "bac +4",
]
_LOW_LEVEL_KW = [
    "bts", "deust", "dut", "but gestion", "bac+2", "bac +2",
    "bac/but/bachelor", "bts ou dut", "intégrer un bts", "intégrez un bts",
    "formation bac+2", "niveau bac+2",
]

def filter_by_niveau_bac5(offers: list, track_key: str) -> list:
    """Finance uniquement : exclut offres ciblant BTS/DUT/BAC+2 sans mention Master."""
    if track_key != "finance":
        return offers
    kept     = []
    excluded = 0
    for o in offers:
        desc     = (o.get("description_full", "") + " " + o.get("title", "")).lower()
        has_bac5 = any(kw in desc for kw in _BAC5_KW)
        has_low  = any(kw in desc for kw in _LOW_LEVEL_KW)
        if has_low and not has_bac5:
            excluded += 1
        else:
            kept.append(o)
    print(f"  🎓 Filtrage niveau BAC+5 : {len(offers)} → {len(kept)} offres ({excluded} exclues)")
    return kept

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
    print(f"\n{'─'*60}")
    print(f"🎯 Track : {track_cfg['label']} ({track_key})")
    print(f"{'─'*60}")

    romes_codes = ",".join(track_cfg["rome_codes"])
    all_raw     = []

    for ville_name, config in VILLES.items():
        raw         = fetch_lba_offers(ville_name, config, romes_codes)
        transformed = transform_offers(raw, ville_name, config, track_key, track_cfg)
        all_raw.extend(transformed)

    print(f"  📦 {len(all_raw)} offres brutes récupérées")
    filtered = filter_schools(all_raw)
    filtered = filter_by_keywords(filtered, track_cfg["filter_keywords"])
    filtered = filter_empty_offers(filtered)           # ← titre générique + pas d'entreprise
    filtered = filter_by_start_date(filtered)          # ← dates passées
    filtered = filter_by_niveau_bac5(filtered, track_key)  # ← BAC+5 finance
    return filtered

# ===== SAUVEGARDER offres_lba.json =====

def build_output(all_offers, track_keys):
    history = load_history()
    new_offers, active_offers, updated_history = detect_new_offers(all_offers, history)
    save_history(updated_history)

    new_keys = {o["cle_composite"] for o in new_offers}

    print(f"\n📊 Analyse globale :")
    print(f"  🆕 Nouvelles : {len(new_offers)}")
    print(f"  ♻️  Actives   : {len(active_offers)}")

    offres_json = []
    for offer in all_offers:
        is_new     = offer["cle_composite"] in new_keys
        first_seen = updated_history["offers"].get(offer["cle_composite"], {}).get("first_seen")
        last_seen  = updated_history["offers"].get(offer["cle_composite"], {}).get("last_seen")

        offres_json.append({
            "id":                    offer["cle_composite"],
            "source":                "LBA",
            "status":                "new" if is_new else "active",
            "titre":                 offer["title"],
            "entreprise":            offer["company_name"],
            "ville":                 offer["city"],
            "code_postal":           offer["zipcode"],
            "adresse_complete":      offer["full_address"],
            "description":           offer["description"],
            "description_complete":  offer["description_full"],
            "competences_detectees": offer["detected_skills"],
            "url_candidature":       offer["contact_url"],
            "type_contrat":          offer["contract_type"],
            "duree_contrat":         offer["contract_duration"],
            "date_debut":            offer["start_date"],
            "date_creation":         offer["creation_date"],
            "date_expiration":       offer["expiration_date"],
            "plateforme_source":     offer["partner_label"],
            "ville_recherche":       offer["ville_recherche"],
            "priorite_ville":        offer["ville_priority"],
            "track":                 offer["track"],
            "first_seen":            first_seen,
            "last_seen":             last_seen,
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
