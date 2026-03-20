#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/hr_contacts_agent.py — Orchestration de la recherche contacts RH V2
Conforme architecture CrewAI Flow alternances-veille v2.

Interface publique :
    run_hr_contacts_agent(track=None, flush=False, flush_history=False) -> int

Usage standalone :
    python -m alternances_veille.tools.hr_contacts_agent
    python -m alternances_veille.tools.hr_contacts_agent --track finance
    python -m alternances_veille.tools.hr_contacts_agent --all-tracks
    python -m alternances_veille.tools.hr_contacts_agent --flush
    python -m alternances_veille.tools.hr_contacts_agent --flush --flush-history
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import ssl
import urllib3

if os.getenv("PYTHONHTTPSVERIFY", "1") == "0":
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from dotenv import load_dotenv
load_dotenv()

# ===== CHEMINS =====
# tools/ -> alternances_veille/ -> src/ -> repo_root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MERGED_FILE = DATA_DIR / "offres_merged.json"
OUTPUT_JSON = DATA_DIR / "hr_contacts.json"
HISTORY_FILE = DATA_DIR / "hr_contacts_history.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===== CONFIG =====
DELAY = 2.0  # secondes entre deux appels agent

SMALL_COMPANY_KEYWORDS = [
    "agence", "studio", "startup", "sas", "sarl", "eurl",
    "the source", "apogei", "adelia", "junto", "ccm",
]

# Tracks pour lesquels la recherche RH est activee (defaut V2)
TRACKS_WITH_HR_CONTACTS = ["digital_marketing", "finance"]

# ===== KNOWN CAREERS (0 appel agent — URL directe hardcodee) =====
KNOWN_CAREERS = {
    "kpmg": "https://kpmg.com/fr/fr/home/careers/students-graduates.html",
    "deloitte": "https://www2.deloitte.com/fr/fr/pages/careers/articles/join-deloitte.html",
    "ey": "https://www.ey.com/fr_fr/careers",
    "pwc": "https://www.pwc.fr/fr/carrieres.html",
    "mazars": "https://www.forvis-mazars.com/fr/fr/careers",
    "forvis": "https://www.forvis-mazars.com/fr/fr/careers",
    "bdo": "https://www.bdo.fr/fr-fr/carrieres",
    "grant": "https://www.grantthornton.fr/carrieres/",
    "in extenso": "https://www.inextenso.fr/nous-rejoindre",
    "cerfrance": "https://www.cerfrance.fr/rejoignez-nous",
    "fiducial": "https://www.fiducial.fr/recrutement",
    "capgemini": "https://www.capgemini.com/fr-fr/carrieres/",
    "accenture": "https://www.accenture.com/fr-fr/careers",
    "sopra": "https://careers.soprasteria.com/fr",
    "ntt data": "https://fr.nttdata.com/carrieres",
    "nttdata": "https://fr.nttdata.com/carrieres",
    "mc2i": "https://www.mc2i.fr/rejoindre-mc2i",
    "wavestone": "https://www.wavestone.com/fr/join-us/",
    "bnp paribas": "https://group.bnpparibas/rejoindre-le-groupe",
    "societe generale": "https://careers.societegenerale.com/fr",
    "natixis": "https://www.natixis.com/natixis/jcms/ala_5415/fr/carrieres",
    "axa": "https://careers.axa.com/fr",
    "totalenergies": "https://totalenergies.com/fr/carrieres",
    "danone": "https://www.danone.com/fr/carrieres.html",
    "loreal": "https://careers.loreal.com/fr_FR/home",
    "lvmh": "https://www.lvmh.fr/rejoignez-nous/",
    "sncf": "https://www.emploi.sncf.com/fr",
    "bouygues": "https://www.bouygues.com/emploi",
    "michelin": "https://careers.michelin.com/fr",
    "renault": "https://www.renaultgroup.com/carrieres/",
    "pernod ricard": "https://www.pernod-ricard.com/fr/carrieres/",
    "lactalis": "https://www.lactalis.com/fr/talent/",
    "covivio": "https://www.covivio.eu/fr/carrieres/",
    "doctolib": "https://careers.doctolib.fr/",
    "back market": "https://jobs.backmarket.com/",
    "qonto": "https://qonto.com/fr/careers",
    "alan": "https://alan.com/fr/careers",
    "swile": "https://www.swile.co/fr/careers",
    "payfit": "https://payfit.com/fr/careers/",
    "contentsquare": "https://contentsquare.com/fr-fr/careers/",
    "artefact": "https://www.artefact.com/join-us/",
    "eskimoz": "https://eskimoz.fr/agence/",
    "samsic": "https://www.samsic.fr/recrutement/",
    "bureau veritas": "https://careers.bureauveritas.com/fr",
    "airbus": "https://www.airbus.com/en/careers",
    "harmonie mutuelle": "https://www.harmonie-mutuelle.fr/nous-rejoindre",
    "vyv": "https://www.vyv.fr/nous-rejoindre/",
}

# ===== BLACKLIST EMAILS NON-RH =====
_EMAIL_BLACKLIST = [
    "data-privacy", "dataprivacy", "dpo@", "rgpd@", "gdpr@",
    "contact@", "info@", "noreply@", "no-reply@", "hello@",
    "support@", "admin@", "webmaster@", "postmaster@",
    "communication@", "presse@", "accueilsiege", "accueil@", "reception@",
    "global.careers", "careers@",
    "marketing@", "legal@", "juridique@",
]

# ===== UTILITAIRES =====

def normalize_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())[:30]

def is_small_company(company: str) -> bool:
    return any(kw in company.lower() for kw in SMALL_COMPANY_KEYWORDS)

def sanitize_contact(contact: dict) -> dict:
    """Blackliste les emails non-RH — les deplace dans la note."""
    email = contact.get("email_rh") or ""
    if email and any(p in email.lower() for p in _EMAIL_BLACKLIST):
        note_existing = contact.get("note") or ""
        contact["note"] = f"Email non-RH detecte ({email}). {note_existing}".strip()
        contact["email_rh"] = None
    return contact

def clean_json_output(raw: str) -> dict | None:
    """Parse le JSON retourne par result.raw (robuste aux delimiteurs markdown)."""
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except Exception:
            pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None

def build_search_queries(company: str, titre: str) -> tuple[str, str]:
    """Construit les 2 requetes Serper a passer en inputs au Crew."""
    domain = company.lower().replace(" ", "")
    contact_priority = (
        "manager directeur CEO"
        if is_small_company(company)
        else "Talent Acquisition Manager responsable recrutement RRH"
    )
    q1 = (
        f"{company} recrutement alternance email contact RH "
        f"site:{domain}.fr OR site:{domain}.com"
    )
    q2 = f"{company} {contact_priority.split()[0]} LinkedIn site officiel"
    return q1, q2

# ===== CHARGEMENT / SAUVEGARDE =====

def load_offers(tracks: list[str]) -> list:
    """Charge les offres validees filtrées sur la liste de tracks."""
    with open(MERGED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    offers = [
        o for o in data["offres"]
        if o.get("validation_status") in ("validated", "uncertain")
        and o.get("url_candidature", "#") != "#"
        and o.get("track") in tracks
    ]
    return offers

def load_existing_contacts() -> dict:
    if not OUTPUT_JSON.exists():
        return {}
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {c["offer_id"]: c for c in data.get("contacts", [])}

def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", {})

def save_history(history: dict):
    output = {
        "meta": {
            "date_mise_a_jour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_entreprises": len(history),
            "description": (
                "Base historique contacts RH par entreprise. "
                "1 entree par entreprise — reutilisee sur tous les runs. "
                "Ne pas supprimer sauf --flush-history."
            ),
        },
        "companies": history,
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def save_contacts(results: dict, tracks: list[str]):
    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tracks": tracks,
            "total": len(results),
        },
        "contacts": list(results.values()),
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def update_history(history: dict, contact: dict) -> bool:
    """Met a jour l'historique si le nouveau contact a une meilleure confiance."""
    company = contact.get("entreprise", "")
    norm_key = normalize_company(company)
    if not norm_key:
        return False
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    new_rank = conf_rank.get(contact.get("confidence", "low"), 0)
    old_rank = conf_rank.get(history.get(norm_key, {}).get("confidence", "low"), 0)
    if new_rank > old_rank:
        history[norm_key] = {
            **contact,
            "history_key": norm_key,
            "history_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return True
    return False

# ===== KNOWN CAREERS LOOKUP =====

def lookup_known_careers(
    company: str, offer_id: str, titre: str, ville: str
) -> dict | None:
    norm = normalize_company(company)
    for key, url in KNOWN_CAREERS.items():
        if normalize_company(key) in norm:
            return {
                "offer_id": offer_id,
                "entreprise": company,
                "titre": titre,
                "ville": ville,
                "corporate_site": None,
                "email_rh": None,
                "nom_contact": None,
                "role_contact": "Voir page carrieres",
                "url_careers": url,
                "url_contact": None,
                "youtube_url": None,
                "source_info": "KNOWN_CAREERS (hardcode)",
                "confidence": "medium",
                "note": f"URL carrieres connue pour {company}",
                "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    return None

# ===== APPEL CREW CREWAI =====

def run_hr_crew(
    company: str, titre: str, ville: str, offer_id: str
) -> dict | None:
    """
    Lance HRContactsCrew pour une offre.
    Conforme CrewAI V2 : resultat via result.raw, pas de fichier temporaire.
    """
    from alternances_veille.crews.hr_contacts_crew.hr_contacts_crew import HRContactsCrew

    search_q1, search_q2 = build_search_queries(company, titre)

    try:
        result = HRContactsCrew().crew().kickoff(inputs={
            "company": company,
            "titre": titre,
            "ville": ville,
            "search_query_1": search_q1,
            "search_query_2": search_q2,
        })
        raw = result.raw
    except Exception as e:
        print(f"\n  Erreur CrewAI : {e}")
        return None

    parsed = clean_json_output(raw)
    if parsed:
        parsed = sanitize_contact(parsed)
        parsed["offer_id"] = offer_id
        parsed["titre"] = titre
        parsed["ville"] = ville
        parsed["scrape_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return parsed

# ===== INTERFACE PRINCIPALE =====

def run_hr_contacts_agent(
    track: str | list[str] | None = None,
    flush: bool = False,
    flush_history: bool = False,
) -> int:
    """
    Point d'entree conforme architecture V2.
    Appele par flow.py -> find_hr_contacts().
    Retourne le nombre de contacts actionnables trouves.

    track peut etre :
      - None           -> defaut TRACKS_WITH_HR_CONTACTS (digital_marketing + finance)
      - str            -> un seul track (retro-compat)
      - list[str]      -> liste de tracks specifiques
    """
    # Normalisation -> toujours une liste
    if track is None:
        tracks = TRACKS_WITH_HR_CONTACTS
    elif isinstance(track, str):
        tracks = [track]
    else:
        tracks = track

    print("=" * 65)
    print(f"Agent RH CONTACTS v2 — Tracks : {', '.join(tracks)}")
    print(f"  LLM     : {os.getenv('LLM_MODEL', 'anthropic/claude-haiku-4-5-20251001')}")
    print(f"  Config  : max_iter=8 | n_results=3 | max_chars=2000")
    print(f"  History : {HISTORY_FILE.name}")
    print("=" * 65)

    offers = load_offers(tracks)
    history = {} if flush_history else load_history()

    # Flush selectif : purge uniquement les offres des tracks courants
    if flush and tracks:
        all_existing = load_existing_contacts()
        track_ids = {o["id"] for o in offers}
        existing = {k: v for k, v in all_existing.items() if k not in track_ids}
        print(f"Flush {tracks} : {len(all_existing) - len(existing)} purges, "
              f"{len(existing)} autres tracks conserves")
    elif flush:
        existing = {}
        print("Flush all : cache entierement purge")
    else:
        existing = load_existing_contacts()

    print(f"  {len(offers)} offres chargees")
    print(f"  {len(existing)} en cache")
    print(f"  {len(history)} entreprises en historique")
    print()

    results = dict(existing)

    # Pre-charger le cache entreprises depuis l'historique
    run_company_cache: dict[str, dict] = {
        k: sanitize_contact(dict(v)) for k, v in history.items()
    }

    n_agent = n_history = n_dedup = n_cache = n_skip = n_known = 0

    for i, offer in enumerate(offers, 1):
        offer_id = offer["id"]
        company = offer.get("entreprise", "").strip()
        titre = offer.get("titre", "")
        ville = offer.get("ville", "")
        norm_co = normalize_company(company)
        prefix = f"[{i:>2}/{len(offers)}]"

        # -- Cas 1 : offre deja en cache -----------------------------------
        if offer_id in results:
            cached = results[offer_id]
            has = bool(
                cached.get("email_rh") or
                cached.get("nom_contact") or
                cached.get("url_careers")
            )
            print(f"{prefix} Cache {'OK' if has else 'vide'} : {(company or titre)[:45]}")
            n_cache += 1
            continue

        # -- Cas 2 : company vide — skip agent -----------------------------
        if not company:
            contact = {
                "offer_id": offer_id, "entreprise": "", "titre": titre, "ville": ville,
                "corporate_site": None, "email_rh": None, "nom_contact": None,
                "role_contact": None, "url_careers": None, "url_contact": None,
                "youtube_url": None, "source_info": None, "confidence": "low",
                "note": "Entreprise non renseignee — skip agent",
                "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            results[offer_id] = contact
            print(f"{prefix} Skip (pas d'entreprise) : {titre[:50]}")
            n_skip += 1
            save_contacts(results, tracks)
            continue

        # -- Cas 3 : entreprise connue (historique ou dedup run) -----------
        if norm_co and norm_co in run_company_cache:
            source = run_company_cache[norm_co]
            cloned = {**source, "offer_id": offer_id, "titre": titre, "ville": ville}
            cloned = sanitize_contact(cloned)
            results[offer_id] = cloned
            has = bool(
                cloned.get("email_rh") or
                cloned.get("nom_contact") or
                cloned.get("url_careers")
            )
            origin = "Historique" if norm_co in history else "Dedup run "
            print(f"{prefix} {origin} {'OK' if has else 'vide'} : {company[:45]}")
            n_history += 1 if norm_co in history else 0
            n_dedup += 0 if norm_co in history else 1
            save_contacts(results, tracks)
            continue

        # -- Cas 4 : entreprise dans KNOWN_CAREERS -------------------------
        known = lookup_known_careers(company, offer_id, titre, ville)
        if known:
            results[offer_id] = known
            run_company_cache[norm_co] = known
            update_history(history, known)
            save_history(history)
            save_contacts(results, tracks)
            print(f"{prefix} Hardcode OK : {company[:40]} -> {known['url_careers'][:45]}")
            n_known += 1
            continue

        # -- Cas 5 : appel Crew CrewAI -------------------------------------
        print(f"{prefix} Crew en cours : {company[:45]}", end=" ... ", flush=True)

        contact = run_hr_crew(company, titre, ville, offer_id)
        time.sleep(DELAY)

        if not contact:
            print("ECHEC crew")
            contact = {
                "offer_id": offer_id, "entreprise": company, "titre": titre, "ville": ville,
                "corporate_site": None, "email_rh": None, "nom_contact": None,
                "role_contact": None, "url_careers": None, "url_contact": None,
                "youtube_url": None, "source_info": None, "confidence": "low",
                "note": None, "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            confidence = contact.get("confidence", "low")
            has = bool(
                contact.get("email_rh") or
                contact.get("nom_contact") or
                contact.get("url_careers")
            )
            parts = []
            if contact.get("email_rh"):    parts.append(f"email:{contact['email_rh']}")
            if contact.get("nom_contact"): parts.append(f"contact:{contact['nom_contact']}")
            if contact.get("url_careers"): parts.append("careers:OK")
            if contact.get("youtube_url"): parts.append("youtube:OK")
            result_str = " | ".join(parts) if parts else "rien trouve"
            print(f"{'OK' if has else 'vide'} [{confidence}] {result_str}")

        results[offer_id] = contact
        run_company_cache[norm_co] = contact
        n_agent += 1

        if update_history(history, contact):
            save_history(history)
        save_contacts(results, tracks)

    # -- Sauvegarde finale -------------------------------------------------
    save_contacts(results, tracks)
    save_history(history)

    contacts_list = list(results.values())
    found = sum(
        1 for r in contacts_list
        if r.get("email_rh") or r.get("nom_contact") or r.get("url_careers")
    )
    not_found = len(contacts_list) - found

    print(f"\n{'=' * 65}")
    print(f"Resume HR contacts :")
    print(f"  {n_agent} appels Crew reels")
    print(f"  {n_known} depuis KNOWN_CAREERS (0 cout)")
    print(f"  {n_history} depuis historique (0 cout)")
    print(f"  {n_dedup} dedupliques ce run (0 cout)")
    print(f"  {n_cache} depuis cache offre (0 cout)")
    print(f"  {n_skip} skippes (pas d'entreprise)")
    print(f"  {found} contacts actionnables / {len(contacts_list)} offres")
    print(f"  {not_found} sans contact")
    print(f"\nFichiers :")
    print(f"  {OUTPUT_JSON}")
    print(f"  {HISTORY_FILE} ({len(history)} entreprises)")
    print("=" * 65)

    return found

# ===== ENTRYPOINT STANDALONE =====

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent CrewAI contacts RH v2")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--track", default=None,
        help="Track cible (defaut: digital_marketing + finance)",
    )
    grp.add_argument(
        "--all-tracks", action="store_true",
        help="Traiter tous les tracks HR (digital_marketing + finance)",
    )
    parser.add_argument(
        "--flush", action="store_true",
        help="Re-recherche le(s) track(s) courant(s) (autres tracks conserves)",
    )
    parser.add_argument(
        "--flush-history", action="store_true",
        help="Efface hr_contacts_history.json",
    )
    args = parser.parse_args()
    track_arg = None if args.all_tracks else args.track
    run_hr_contacts_agent(
        track=track_arg, flush=args.flush, flush_history=args.flush_history
    )
