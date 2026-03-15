#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/lba_scraper.py - Scraper La Bonne Alternance V2
"""

import json
import os
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

# ===== CHEMINS =====

BASE_DIR     = Path(__file__).parent.parent.parent.parent
DATA_DIR     = BASE_DIR / "data"
CONFIG_FILE  = BASE_DIR / "config" / "tracks.yml"
OUTPUT_FILE  = DATA_DIR / "offres_lba.json"
# Historique léger LBA (dict-keyed) — séparé de offres_historique.json V2 (merge_offers)
HISTORY_FILE = DATA_DIR / "lba_history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===== VILLES =====

VILLES = {
    "Rennes": {"latitude": 48.1173, "longitude": -1.6778, "radius": 30, "priority": 1},
    "Nantes": {"latitude": 47.2184, "longitude": -1.5536, "radius": 30, "priority": 2},
    "Paris":  {"latitude": 48.8566, "longitude":  2.3522, "radius": 30, "priority": 3},
}

# ===== EXCLUSIONS ÉCOLES (nom entreprise) =====

SCHOOL_EXCLUSIONS_NAME = [
    "enseigne inconnue", "ecole", "universite",
    "campus", "cfa", "centre de formation",
    # Organismes de formation / écoles spammant LBA
    "neogest",
    "education group",
    "institut superieur de techniques",
    "groupe igf",
    "igf formation",
    "rocket school",
    "association imc",
    # La Poste via aplitrak (faux recruteur direct)
    "filiales service courrier colis",
    "bscc",
    # Forum emploi (pas un recruteur direct)
    "talents handicap",
]

# ===== EXCLUSIONS ÉCOLES (description) =====

SCHOOL_EXCLUSIONS_DESC = [
    "l'iscod", "alticome", "alticom,", "mydigitalschool", "studi ", "sup de pub",
    "groupe igs", "bringme", "optez pour l'alternance nouvelle generation",
    "preparez un bachelor", "preparez un master", "recrutement en 4 etapes",
    "formation prise en charge a 100% par l'entreprise",
    "recherche pour l'une de ses entreprises partenaires",
    "nos formations diplomantes reconnues par l'etat",
    "school 100 % en alternance", "notre ecole recrute pour",
    "notre cfa recrute pour",
    "postulez a cette offre si vous souhaitez integrer",
]

# ===== FILTRAGE NIVEAU =====

_BAC5_KW = [
    "master", "bac+5", "bac +5", "m1", "m2", "dscg",
    "grande ecole", "msc", "bac+4", "bac +4",
]
_LOW_KW = [
    "bts", "deust", "dut", "but gestion", "bac+2", "bac +2",
    "bac/but/bachelor", "bts ou dut", "integrer un bts",
    "integrez un bts", "formation bac+2", "niveau bac+2",
]

# ===== TITRES GÉNÉRIQUES =====

_GENERIC_TITLE_PATTERNS = re.compile(
    r"^(comptable|aide[- ]comptable|collaborateur comptable|"
    r"comptable fournisseurs|comptable clients|comptable general|"
    r"aide comptable|assistant[e]? comptable|"
    r"responsable marketing|assistant[e]? marketing|"
    r"gestionnaire|analyste financier)[^a-z]",
    re.IGNORECASE
)

# ===== UTILITAIRES =====

def load_tracks() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("tracks", data)

def clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\s+", " ", unescape(text)).strip()

def truncate_text(text: str, max_length: int = 200) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."

def format_date(date_str: str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None

def _try_extract_company(title: str) -> str:
    if not title:
        return ""
    _GENERIC = {
        "comptable", "collaborateur", "aide", "assistant", "assistante",
        "assistant(e)", "assistante(e)", "alternant", "apprenti",
        "charge", "chargee", "responsable", "analyste", "gestionnaire",
        "chef", "directeur", "auditeur", "controleur",
        "stagiaire", "alternance", "emploi", "offre", "poste", "recrutement",
    }
    _NOISE = {
        "h/f", "f/h", "(h/f)", "(f/h)", "paris", "rennes",
        "nantes", "lyon", "bordeaux", "france", "alternance",
    }
    m = re.match(
        r"^([A-Z\xc0-\xdc][A-Za-z\xc0-\xff0-9 &.'\-]{2,40}?)\s*[-\u2013\u2014]\s*"
        r"(?:Comptable|Auditeur|Alternance|Assistant|Collaborateur|"
        r"Contr\xf4leur|Gestionnaire|Analyste|Apprenti|Aide|Charg\xe9)",
        title
    )
    if m:
        c = m.group(1).strip()
        if len(c) > 3 and c.lower().split()[0] not in _GENERIC:
            return c
    m2 = re.search(
        r"[-\u2013\u2014]\s*([A-Z\xc0-\xdc][A-Za-z\xc0-\xff0-9 &.'\-]{2,40})\s*$",
        title
    )
    if m2:
        c = m2.group(1).strip()
        if len(c) > 3 and c.lower() not in _NOISE and c.lower().split()[0] not in _GENERIC:
            return c
    return ""

def detect_skills(title: str, description: str, skills_keywords: dict) -> list:
    text = (title + " " + description).lower()
    return [name for name, kws in skills_keywords.items()
            if any(k.lower() in text for k in kws)]

def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"last_update": None, "offers": {}}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "offers" not in data:
            data["offers"] = {}
        return data
    except Exception as e:
        print(f"⚠️  Historique corrompu, recréation : {e}")
        return {"last_update": None, "offers": {}}

def save_history(history: dict):
    history["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ===== API LBA =====

def fetch_lba_offers(ville_name: str, config: dict, romes_codes: str) -> list:
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
            print(f"❌ {response.text[:100]}")
            return []
        data    = response.json()
        results = []
        results.extend(data.get("jobs", []) or [])
        results.extend(data.get("results", []) or [])
        results.extend(data.get("partnerJobs", {}).get("results", []))
        print(f"✅ {len(results)} offres")
        return results
    except Exception as e:
        print(f"❌ {e}")
        return []

# ===== TRANSFORMATION =====

def transform_offer(raw: dict, ville_name: str, ville_cfg: dict,
                    track_key: str, track_cfg: dict) -> dict:
    title   = raw.get("offer", {}).get("title", "")
    company = raw.get("workplace", {}).get("name") or _try_extract_company(title)
    siret   = raw.get("workplace", {}).get("siret", "")
    addr    = raw.get("workplace", {}).get("location", {}).get("address", "")

    # Ville réelle de l'entreprise (pas la ville de recherche)
    zip_m   = re.search(r"\b(\d{5})\b", addr)
    zipcode = zip_m.group(1) if zip_m else ""
    city_m  = re.search(r"\d{5}\s+(.+)$", addr)
    city    = city_m.group(1).title() if city_m else ""
    if not city:
        city = raw.get("workplace", {}).get("location", {}).get("city", "") or ville_name

    desc_raw   = raw.get("offer", {}).get("description", "")
    desc_clean = clean_html(desc_raw)
    desc_short = truncate_text(desc_clean, 200)

    contracts = raw.get("contract", {}).get("type", [])
    contract  = " + ".join(contracts) if contracts else "Alternance"

    title_l   = title.lower()
    company_l = company.lower()
    cle       = (title_l.replace(" ", "").replace("/", "") + "_"
                 + company_l.replace(" ", "") + "_"
                 + zipcode)

    skills    = detect_skills(title, desc_clean, track_cfg.get("skills_keywords", {}))
    today_str = datetime.now().strftime("%Y-%m-%d")

    return {
        "id":                    cle,
        "source":                "LBA",
        "status":                "new",
        "titre":                 title,
        "entreprise":            company,
        "ville":                 city,
        "code_postal":           zipcode,
        "adresse_complete":      addr,
        "description":           desc_short,
        "description_complete":  desc_clean,
        "competences_detectees": skills,
        "url_candidature":       raw.get("apply", {}).get("url", "#"),
        "type_contrat":          contract,
        "duree_contrat":         raw.get("contract", {}).get("duration"),
        "date_creation":         None,
        "date_debut":            format_date(raw.get("contract", {}).get("start")),
        "date_expiration":       format_date(raw.get("offer", {}).get("expiration")),
        "first_seen":            today_str,
        "last_seen":             today_str,
        "plateforme_source":     raw.get("identifier", {}).get("partner_label", "LBA"),
        "siret":                 siret,
        "ville_recherche":       ville_name,
        "priorite_ville":        ville_cfg["priority"],
        "track":                 track_key,
        # Champs temporaires pour filtrage (supprimés avant sortie JSON)
        "_title_lower":          title_l,
        "_company_lower":        company_l,
        "_desc_lower":           desc_clean.lower(),
    }

def strip_temp_fields(offers: list) -> list:
    return [{k: v for k, v in o.items() if not k.startswith("_")} for o in offers]

# ===== FILTRAGE =====

def filter_schools(offers: list) -> list:
    """Exclut les écoles et organismes de formation (nom + description)."""
    before   = len(offers)
    filtered = [
        o for o in offers
        if not any(e in o.get("_company_lower", "") for e in SCHOOL_EXCLUSIONS_NAME)
        and not any(e in o.get("_desc_lower", "") for e in SCHOOL_EXCLUSIONS_DESC)
    ]
    print(f"  🔍 Filtrage écoles       : {before} → {len(filtered)} offres"
          f" ({before - len(filtered)} exclues)")
    return filtered

def filter_by_keywords(offers: list, keywords: list) -> list:
    """Garde uniquement les offres dont le titre contient un mot-clé du track."""
    before    = len(offers)
    kws_lower = [k.lower() for k in keywords]
    filtered  = [o for o in offers if any(k in o.get("_title_lower", "") for k in kws_lower)]
    print(f"  🎯 Filtrage track        : {before} → {len(filtered)} offres"
          f" ({before - len(filtered)} exclues)")
    return filtered

def filter_empty(offers: list) -> list:
    """Exclut les offres fantômes : pas d'entreprise ET titre générique ou description vide."""
    before         = len(offers)
    kept, excluded = [], 0
    for o in offers:
        has_company   = bool(o.get("_company_lower", "").strip())
        desc_ok       = len(o.get("_desc_lower", "")) >= 80
        generic_title = bool(_GENERIC_TITLE_PATTERNS.match(o.get("titre", "").strip()))
        if not has_company and generic_title:
            excluded += 1
            continue
        if not has_company and not desc_ok:
            excluded += 1
            continue
        kept.append(o)
    if excluded:
        print(f"  🗑️  Filtrage vides/génériques : {before} → {len(kept)} offres"
              f" ({excluded} exclues)")
    return kept

def filter_start_date(offers: list) -> list:
    """Exclut les offres dont la date de début est strictement dans le passé."""
    today          = datetime.now()
    kept, excluded = [], 0
    for o in offers:
        sd = o.get("date_debut")
        if not sd:
            kept.append(o)
            continue
        date_ok = True  # conserve si la date ne peut pas être parsée
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                if datetime.strptime(str(sd), fmt) < today:
                    date_ok = False
                    excluded += 1
                break
            except ValueError:
                continue
        if date_ok:
            kept.append(o)
    print(f"  📅 Filtrage dates passées : {len(offers)} → {len(kept)} offres"
          f" ({excluded} exclues)")
    return kept

def filter_niveau_finance(offers: list, track_key: str) -> list:
    """Finance uniquement : exclut les offres ciblant BTS/BAC+2 sans mention Master."""
    if track_key != "finance":
        return offers
    before         = len(offers)
    kept, excluded = [], 0
    for o in offers:
        text     = o.get("_desc_lower", "") + " " + o.get("_title_lower", "")
        has_bac5 = any(kw in text for kw in _BAC5_KW)
        has_low  = any(kw in text for kw in _LOW_KW)
        if has_low and not has_bac5:
            excluded += 1
        else:
            kept.append(o)
    print(f"  🎓 Filtrage niveau BAC+5 : {before} → {len(kept)} offres"
          f" ({excluded} exclues)")
    return kept

# ===== SCRAPE UN TRACK =====

def scrape_track(track_key: str, track_cfg: dict) -> list:
    label = track_cfg.get("label", track_key)
    print("")
    print("─" * 60)
    print(f"🎯 Track : {label} ({track_key})")
    print("─" * 60)

    romes = ",".join(track_cfg.get("rome_codes", []))
    if not romes:
        print(f"  ⚠️  Pas de codes ROME configurés pour {track_key}")
        return []

    raw_all = []
    for ville_name, ville_cfg in VILLES.items():
        raw   = fetch_lba_offers(ville_name, ville_cfg, romes)
        trans = [transform_offer(r, ville_name, ville_cfg, track_key, track_cfg) for r in raw]
        raw_all.extend(trans)

    print(f"  📦 {len(raw_all)} offres brutes récupérées")

    filtered = filter_schools(raw_all)
    filtered = filter_by_keywords(filtered, track_cfg.get("filter_keywords", []))
    filtered = filter_empty(filtered)
    filtered = filter_start_date(filtered)
    filtered = filter_niveau_finance(filtered, track_key)

    print(f"  ✅ {len(filtered)} offres retenues pour {track_key}")
    return filtered

# ===== HISTORIQUE =====

def apply_history(offers: list, history: dict) -> tuple:
    """Met à jour status, first_seen, last_seen via l'historique léger LBA."""
    today_str    = datetime.now().strftime("%Y-%m-%d")
    history_data = history.get("offers", {})
    new_count    = 0
    active_count = 0

    for o in offers:
        offer_id = o["id"]
        if offer_id in history_data:
            o["status"]     = "active"
            o["first_seen"] = history_data[offer_id].get("first_seen", today_str)
            o["last_seen"]  = today_str
            active_count   += 1
        else:
            o["status"]     = "new"
            o["first_seen"] = today_str
            o["last_seen"]  = today_str
            new_count      += 1

    return offers, new_count, active_count

def update_history(offers: list, history: dict) -> dict:
    today_str = datetime.now().strftime("%Y-%m-%d")
    for o in offers:
        offer_id = o["id"]
        if offer_id not in history["offers"]:
            history["offers"][offer_id] = {
                "first_seen": today_str,
                "last_seen":  today_str,
                "titre":      o.get("titre", ""),
                "entreprise": o.get("entreprise", ""),
            }
        else:
            history["offers"][offer_id]["last_seen"] = today_str
    return history

# ===== POINT D'ENTRÉE TOOL =====

def run_lba_scraper() -> int:
    tracks  = load_tracks()
    history = load_history()

    print("")
    print("=" * 60)
    print("🎯 LBA SCRAPER — 4 tracks")
    print("=" * 60)

    all_offers = []
    for tk, tcfg in tracks.items():
        offers = scrape_track(tk, tcfg)
        all_offers.extend(offers)

    print("")
    print("=" * 60)
    print(f"📦 Total toutes tracks : {len(all_offers)} offres")

    all_offers, new_count, active_count = apply_history(all_offers, history)
    all_offers = strip_temp_fields(all_offers)

    history = update_history(all_offers, history)
    save_history(history)

    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_offres":    len(all_offers),
            "nouvelles":       new_count,
            "actives":         active_count,
            "tracks":          list(tracks.keys()),
        },
        "offres": all_offers,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  🆕 Nouvelles : {new_count}")
    print(f"  ♻️  Actives   : {active_count}")
    print(f"💾 Sauvegardé : {OUTPUT_FILE}")
    print(f"   {len(all_offers)} offres — {new_count} nouvelles")
    print("=" * 60)
    print("➡️  PROCHAINE ÉTAPE : validator")
    print("=" * 60)

    return len(all_offers)


if __name__ == "__main__":
    run_lba_scraper()
