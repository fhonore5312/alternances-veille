#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent CrewAI — Recherche contacts RH par offre — v4.1
Corrections vs v4 :
  - Bug fix : --flush préserve les contacts des autres tracks
  - Bug fix : sanitize_contact() appliqué aussi sur données historique/dédup
  - Bug fix : skip systématique si company vide (indépendant du titre)
  - Bug fix : blacklist emails élargie (dataprivacy, global.careers, accueilsiege...)
  - KNOWN_CAREERS : Big4/ESN/grandes entreprises → URL careers hardcodée

Usage:
    python -m scripts.scrape_hr_contacts_agent
    python -m scripts.scrape_hr_contacts_agent --track finance
    python -m scripts.scrape_hr_contacts_agent --all-tracks
    python -m scripts.scrape_hr_contacts_agent --flush             # re-cherche le track courant
    python -m scripts.scrape_hr_contacts_agent --flush --flush-history
"""

import argparse
import json
import os
if os.getenv("PYTHONHTTPSVERIFY", "1") == "0":
    import ssl
    import urllib3
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import re
import time
from datetime import datetime
from pathlib import Path

from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from dotenv import load_dotenv

load_dotenv()

# ===== CHEMINS =====

SCRIPT_DIR   = Path(__file__).parent
BASE_DIR     = SCRIPT_DIR.parent
DATA_DIR     = BASE_DIR / "data"
MERGED_FILE  = DATA_DIR / "offres_merged.json"
OUTPUT_JSON  = DATA_DIR / "hr_contacts.json"
HISTORY_FILE = DATA_DIR / "hr_contacts_history.json"

# ===== CONFIG =====

LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")
DELAY     = 2.0

SMALL_COMPANY_KEYWORDS = [
    "agence", "studio", "startup", "sas", "sarl", "eurl",
    "the source", "apogei", "adelia", "junto", "ccm",
]

# ===== KNOWN CAREERS (0 appel agent — URL directe) =====

KNOWN_CAREERS = {
    # Big4 / Audit
    "kpmg":         "https://kpmg.com/fr/fr/home/careers/students-graduates.html",
    "deloitte":     "https://www2.deloitte.com/fr/fr/pages/careers/articles/join-deloitte.html",
    "ey":           "https://www.ey.com/fr_fr/careers",
    "pwc":          "https://www.pwc.fr/fr/carrieres.html",
    "mazars":       "https://www.forvis-mazars.com/fr/fr/careers",
    "forvis":       "https://www.forvis-mazars.com/fr/fr/careers",
    "bdo":          "https://www.bdo.fr/fr-fr/carrieres",
    "grant":        "https://www.grantthornton.fr/carrieres/",
    "in extenso":   "https://www.inextenso.fr/nous-rejoindre",
    "cerfrance":    "https://www.cerfrance.fr/rejoignez-nous",
    "fiducial":     "https://www.fiducial.fr/recrutement",
    # ESN / Conseil
    "capgemini":    "https://www.capgemini.com/fr-fr/carrieres/",
    "accenture":    "https://www.accenture.com/fr-fr/careers",
    "sopra":        "https://careers.soprasteria.com/fr",
    "ntt data":     "https://fr.nttdata.com/carrieres",
    "nttdata":      "https://fr.nttdata.com/carrieres",
    "mc2i":         "https://www.mc2i.fr/rejoindre-mc2i",
    "wavestone":    "https://www.wavestone.com/fr/join-us/",
    # Grands groupes finance/industrie
    "bnp paribas":     "https://group.bnpparibas/rejoindre-le-groupe",
    "societe generale":"https://careers.societegenerale.com/fr",
    "natixis":         "https://www.natixis.com/natixis/jcms/ala_5415/fr/carrieres",
    "axa":             "https://careers.axa.com/fr",
    "totalenergies":   "https://totalenergies.com/fr/carrieres",
    "danone":          "https://www.danone.com/fr/carrieres.html",
    "loreal":          "https://careers.loreal.com/fr_FR/home",
    "lvmh":            "https://www.lvmh.fr/rejoignez-nous/",
    "sncf":            "https://www.emploi.sncf.com/fr",
    "bouygues":        "https://www.bouygues.com/emploi",
    "michelin":        "https://careers.michelin.com/fr",
    "renault":         "https://www.renaultgroup.com/carrieres/",
    "pernod ricard":   "https://www.pernod-ricard.com/fr/carrieres/",
    "lactalis":        "https://www.lactalis.com/fr/talent/",
    "covivio":         "https://www.covivio.eu/fr/carrieres/",
    "doctolib":        "https://careers.doctolib.fr/",
    "back market":     "https://jobs.backmarket.com/",
    "qonto":           "https://qonto.com/fr/careers",
    "alan":            "https://alan.com/fr/careers",
    "swile":           "https://www.swile.co/fr/careers",
    "payfit":          "https://payfit.com/fr/careers/",
    "contentsquare":   "https://contentsquare.com/fr-fr/careers/",
    "artefact":        "https://www.artefact.com/join-us/",
    "eskimoz":         "https://eskimoz.fr/agence/",
    "samsic":          "https://www.samsic.fr/recrutement/",
    "bureau veritas":  "https://careers.bureauveritas.com/fr",
    "airbus":          "https://www.airbus.com/en/careers",
    "harmonie mutuelle":"https://www.harmonie-mutuelle.fr/nous-rejoindre",
    "vyv":             "https://www.vyv.fr/nous-rejoindre/",
}

# ===== BLACKLIST EMAILS NON-RH =====

_EMAIL_BLACKLIST = [
    # RGPD / DPO
    "data-privacy", "dataprivacy", "dpo@", "rgpd@", "gdpr@",
    # Génériques entreprise
    "contact@", "info@", "noreply@", "no-reply@", "hello@",
    "support@", "admin@", "webmaster@", "postmaster@",
    # Communication / accueil
    "communication@", "presse@", "accueilsiege", "accueil@", "reception@",
    # RH génériques non-nominatifs non fiables
    "global.careers",   # ex: NTT global.careers@nttdata.com
    "careers@",         # boîte générique carrières
    "marketing@",
    "legal@", "juridique@",
]

# ===== UTILITAIRES =====

def normalize_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())[:30]

def is_small_company(company: str) -> bool:
    return any(kw in company.lower() for kw in SMALL_COMPANY_KEYWORDS)

def sanitize_contact(contact: dict) -> dict:
    """
    Blackliste les emails non-RH et les déplace dans la note.
    Appliqué systématiquement : agent, historique, dédup.
    """
    email = contact.get("email_rh") or ""
    if email and any(p in email.lower() for p in _EMAIL_BLACKLIST):
        note_existing = contact.get("note") or ""
        contact["note"]     = f"Email non-RH détecté ({email}). {note_existing}".strip()
        contact["email_rh"] = None
    return contact

def clean_json_output(raw: str) -> dict | None:
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

# ===== CHARGEMENT / SAUVEGARDE =====

def load_offers(track: str | None = "digital_marketing") -> list:
    with open(MERGED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    offers = [
        o for o in data["offres"]
        if o.get("validation_status") in ("validated", "uncertain")
        and o.get("url_candidature", "#") != "#"
    ]
    if track:
        offers = [o for o in offers if o.get("track") == track]
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
            "date_mise_a_jour":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_entreprises": len(history),
            "description": (
                "Base historique des contacts RH par entreprise. "
                "1 entrée par entreprise unique — réutilisée sur tous les runs. "
                "Ne pas supprimer sauf --flush-history."
            ),
        },
        "companies": history,
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def save_contacts(results: dict, track: str | None):
    output = {
        "meta": {
            "date_generation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "track":           track or "all",
            "total":           len(results),
        },
        "contacts": list(results.values()),
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def update_history(history: dict, contact: dict) -> bool:
    company  = contact.get("entreprise", "")
    norm_key = normalize_company(company)
    if not norm_key:
        return False
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    new_rank  = conf_rank.get(contact.get("confidence", "low"), 0)
    old_rank  = conf_rank.get(history.get(norm_key, {}).get("confidence", "low"), 0)
    if new_rank > old_rank:
        history[norm_key] = {
            **contact,
            "history_key":     norm_key,
            "history_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return True
    return False

# ===== LOOKUP KNOWN CAREERS =====

def lookup_known_careers(
    company: str, offer_id: str, titre: str, ville: str
) -> dict | None:
    """Retourne un contact préconstruit si l'entreprise est dans KNOWN_CAREERS."""
    norm = normalize_company(company)
    for key, url in KNOWN_CAREERS.items():
        if normalize_company(key) in norm:
            return {
                "offer_id":      offer_id,
                "entreprise":    company,
                "titre":         titre,
                "ville":         ville,
                "corporate_site": None,
                "email_rh":      None,
                "nom_contact":   None,
                "role_contact":  "Voir page carrières",
                "url_careers":   url,
                "url_contact":   None,
                "youtube_url":   None,
                "source_info":   "KNOWN_CAREERS (hardcodé)",
                "confidence":    "medium",
                "note":          f"URL carrières connue pour {company}",
                "scrape_date":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    return None

# ===== PROMPT =====

def build_task_description(company: str, titre: str, ville: str) -> str:
    small = is_small_company(company)
    contact_priority = (
        "manager marketing, directeur ou CEO"
        if small else
        "Talent Acquisition Manager, responsable recrutement, RRH"
    )
    return f"""Trouve les coordonnées du contact recrutement pour :
- Entreprise : {company}
- Poste : {titre}
- Ville : {ville}

Fais AU MAXIMUM 2 recherches Serper puis scrape si pertinent :
1. `{company} recrutement alternance email contact RH site:{company.lower().replace(' ', '')}.fr OR site:{company.lower().replace(' ', '')}.com`
2. `{company} {contact_priority.split(',')[0].strip()} LinkedIn site officiel`

Si une URL /careers, /recrutement ou /contact RH apparaît dans les résultats Serper, scrape-la.

Règles importantes :
- Ne jamais inventer un email ou un nom
- Les emails génériques (contact@, info@, dpo@, dataprivacy@, global.careers@, accueil@) ne sont PAS des contacts RH — mets null pour email_rh
- Un email RH valide est nominatif (prenom.nom@) ou explicitement recrutement@ / rh@ / talent@
- Si tu ne trouves rien de certain, mets null et confidence=low
- Retourne UNIQUEMENT ce JSON, sans texte avant ni après :

{{
  "entreprise": "{company}",
  "corporate_site": "URL site officiel ou null",
  "email_rh": "email DIRECT RH nominatif ou recrutement@/rh@/talent@ uniquement — sinon null",
  "nom_contact": "Prénom Nom ou null",
  "role_contact": "rôle exact ou null",
  "url_careers": "URL page carrières/offres ou null",
  "url_contact": "URL formulaire contact ou null",
  "youtube_url": "URL vidéo YouTube recrutement ou null",
  "source_info": "URL ou texte source",
  "confidence": "high | medium | low",
  "note": "infos utiles : téléphone, adresse, nom manager, URL candidature directe, etc. ou null"
}}"""

# ===== AGENT =====

def run_hr_agent(company: str, titre: str, ville: str, offer_id: str) -> dict | None:
    safe_id     = re.sub(r"[^a-zA-Z0-9_-]", "_", offer_id[:20])
    output_file = str(DATA_DIR / f"hr_tmp_{safe_id}.json")

    serper  = SerperDevTool(n_results=3)
    scraper = ScrapeWebsiteTool(max_chars=2000)
    llm     = LLM(model=LLM_MODEL, max_tokens=512, temperature=0.0)

    agent = Agent(
        role="Chasseur de contacts recruteurs",
        goal=f"Trouver le contact RH ou manager recruteur de {company} pour : {titre}",
        backstory=(
            "Expert en recherche de contacts RH B2B. "
            "Tu cherches efficacement avec Serper puis scrapes si nécessaire. "
            "Tu retournes toujours un JSON strict sans inventer de données. "
            "Les emails génériques (contact@, info@, dpo@, global.careers@) ne comptent pas. "
            "Si tu ne trouves pas d'email nominatif ou recrutement@, tu mets null — jamais de données fictives."
        ),
        tools=[serper, scraper],
        llm=llm,
        max_iter=5,
        verbose=False,
    )

    task = Task(
        description=build_task_description(company, titre, ville),
        expected_output="JSON strict avec les clés définies, sans texte autour",
        agent=agent,
        output_file=output_file,
    )

    try:
        Crew(agents=[agent], tasks=[task], verbose=False).kickoff()
    except Exception as e:
        print(f"\n    ❌ CrewAI: {e}")
        return None

    result_path = Path(output_file)
    if not result_path.exists():
        return None

    try:
        with open(result_path, "r", encoding="utf-8") as f:
            raw = f.read()
        result_path.unlink(missing_ok=True)
        parsed = clean_json_output(raw)
        if parsed:
            parsed = sanitize_contact(parsed)   # ← nettoyage emails non-RH
            parsed["offer_id"]    = offer_id
            parsed["titre"]       = titre
            parsed["ville"]       = ville
            parsed["scrape_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return parsed
    except Exception as e:
        print(f"\n    ❌ Lecture résultat: {e}")
    return None

# ===== MAIN =====

def run_contacts(
    track: str | None = "digital_marketing",
    flush: bool = False,
    flush_history: bool = False,
):
    print("=" * 65)
    print(f"🤖 AGENT RH CONTACTS v4.1 — Track : {track or 'ALL'}")
    print(f"   LLM     : {LLM_MODEL}")
    print(f"   Config  : max_iter=5 | n_results=3 | max_chars=2000")
    print(f"   Historique entreprises : {HISTORY_FILE.name}")
    print("=" * 65)

    offers  = load_offers(track)
    history = {} if flush_history else load_history()

    # ── Chargement cache : --flush ne purge QUE les offres du track courant ──
    if flush and track:
        all_existing     = load_existing_contacts()
        track_offer_ids  = {o["id"] for o in offers}
        existing = {
            k: v for k, v in all_existing.items()
            if k not in track_offer_ids
        }
        print(f"♻️  Flush track '{track}' : {len(all_existing) - len(existing)} contacts purgés, "
              f"{len(existing)} autres tracks conservés")
    elif flush:
        existing = {}
        print(f"♻️  Flush all : cache entièrement purgé")
    else:
        existing = load_existing_contacts()

    print(f"📥 {len(offers)} offres")
    print(f"⏭️  {len(existing)} en cache (hr_contacts.json)")
    print(f"📚 {len(history)} entreprises en historique\n")

    results = dict(existing)

    # Pré-charger le run_company_cache depuis l'historique (avec sanitize appliqué)
    run_company_cache: dict[str, dict] = {}
    for norm_key, contact in history.items():
        run_company_cache[norm_key] = sanitize_contact(dict(contact))

    n_agent   = 0
    n_history = 0
    n_dedup   = 0
    n_cache   = 0
    n_skip    = 0
    n_known   = 0

    for i, offer in enumerate(offers, 1):
        offer_id = offer["id"]
        company  = offer.get("entreprise", "").strip()
        titre    = offer.get("titre", "")
        ville    = offer.get("ville", "")
        norm_co  = normalize_company(company)
        prefix   = f"[{i:>2}/{len(offers)}]"

        # ── Cas 1 : offer_id déjà en cache ──────────────────────────────
        if offer_id in results:
            cached = results[offer_id]
            has    = bool(cached.get("email_rh") or cached.get("nom_contact") or cached.get("url_careers"))
            print(f"{prefix} ⏭️  Cache       {'✅' if has else '⚠️ '} : {(company or titre)[:45]}")
            n_cache += 1
            continue

        # ── Cas 2 : skip — company vide (aucun appel agent possible) ────
        if not company:
            contact = {
                "offer_id":      offer_id,
                "entreprise":    "",
                "titre":         titre,
                "ville":         ville,
                "corporate_site": None,
                "email_rh":      None,
                "nom_contact":   None,
                "role_contact":  None,
                "url_careers":   None,
                "url_contact":   None,
                "youtube_url":   None,
                "source_info":   None,
                "confidence":    "low",
                "note":          "Entreprise non renseignée dans l'offre — skip agent",
                "scrape_date":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            results[offer_id] = contact
            print(f"{prefix} ⏩ Skip        ⚠️  : {titre[:50]} (pas d'entreprise)")
            n_skip += 1
            save_contacts(results, track)
            continue

        # ── Cas 3 : entreprise connue (historique ou dédup run) ─────────
        if norm_co and norm_co in run_company_cache:
            source = run_company_cache[norm_co]
            cloned = {**source, "offer_id": offer_id, "titre": titre, "ville": ville}
            cloned = sanitize_contact(cloned)   # ← nettoyage systématique
            results[offer_id] = cloned
            has    = bool(cloned.get("email_rh") or cloned.get("nom_contact") or cloned.get("url_careers"))
            origin = "Historique" if norm_co in history else "Dédup run "
            icon   = "📚" if norm_co in history else "🔁"
            print(f"{prefix} {icon} {origin:<10} {'✅' if has else '⚠️ '} : {company[:45]}")
            if norm_co in history:
                n_history += 1
            else:
                n_dedup += 1
            save_contacts(results, track)
            continue

        # ── Cas 4 : entreprise connue dans KNOWN_CAREERS ────────────────
        known = lookup_known_careers(company, offer_id, titre, ville)
        if known:
            results[offer_id]          = known
            run_company_cache[norm_co] = known
            update_history(history, known)
            save_history(history)
            save_contacts(results, track)
            print(f"{prefix} 📖 Hardcodé    ✅ : {company[:40]} → {known['url_careers'][:45]}")
            n_known += 1
            continue

        # ── Cas 5 : appel agent ──────────────────────────────────────────
        print(f"{prefix} 🔍 Agent       ⏳ : {company[:45]}", end=" ... ", flush=True)

        contact = run_hr_agent(company, titre, ville, offer_id)
        time.sleep(DELAY)

        if not contact:
            print("❌ Agent failed")
            contact = {
                "offer_id":      offer_id,
                "entreprise":    company,
                "titre":         titre,
                "ville":         ville,
                "corporate_site": None,
                "email_rh":      None,
                "nom_contact":   None,
                "role_contact":  None,
                "url_careers":   None,
                "url_contact":   None,
                "youtube_url":   None,
                "source_info":   None,
                "confidence":    "low",
                "note":          None,
                "scrape_date":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            confidence = contact.get("confidence", "low")
            has = bool(contact.get("email_rh") or contact.get("nom_contact") or contact.get("url_careers"))
            icon = "✅" if has else "⚠️ "
            summary = []
            if contact.get("email_rh"):    summary.append(f"📧 {contact['email_rh']}")
            if contact.get("nom_contact"): summary.append(f"👤 {contact['nom_contact']}")
            if contact.get("url_careers"): summary.append("💼 careers")
            if contact.get("youtube_url"): summary.append("🎥 YT")
            print(f"{icon} [{confidence}] {' | '.join(summary) if summary else 'rien trouvé'}")

        results[offer_id]          = contact
        run_company_cache[norm_co] = contact
        n_agent += 1

        updated = update_history(history, contact)
        if updated:
            save_history(history)

        save_contacts(results, track)

    # ── Sauvegarde finale ───────────────────────────────────────────────
    save_contacts(results, track)
    save_history(history)

    contacts_list = list(results.values())
    found     = sum(1 for r in contacts_list
                    if r.get("email_rh") or r.get("nom_contact") or r.get("url_careers"))
    not_found = len(contacts_list) - found

    print(f"\n{'='*65}")
    print(f"📊 Résultat run :")
    print(f"   🤖 {n_agent}  appels agent réels")
    print(f"   📖 {n_known}  depuis KNOWN_CAREERS (0 coût)")
    print(f"   📚 {n_history} depuis historique (0 coût)")
    print(f"   🔁 {n_dedup}  dédupliqués dans ce run (0 coût)")
    print(f"   ⏭️  {n_cache}  depuis cache offre (0 coût)")
    print(f"   ⏩ {n_skip}  skippés (pas d'entreprise)")
    print(f"   ✅ {found} contacts actionnables / {len(contacts_list)} offres")
    print(f"   ⚠️  {not_found} sans contact")
    print(f"\n📁 Fichiers :")
    print(f"   {OUTPUT_JSON}")
    print(f"   {HISTORY_FILE}  ({len(history)} entreprises)")
    print("=" * 65)
    print("➡️  Prochaine étape : python -m scripts.generate_html_email")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent CrewAI contacts RH v4.1")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--track", default="digital_marketing",
        help="Track cible (défaut: digital_marketing)",
    )
    grp.add_argument(
        "--all-tracks", action="store_true",
        help="Traiter tous les tracks",
    )
    parser.add_argument(
        "--flush", action="store_true",
        help="Re-cherche uniquement le track courant (autres tracks conservés)",
    )
    parser.add_argument(
        "--flush-history", action="store_true",
        help="⚠️  Efface hr_contacts_history.json — re-cherche toutes les entreprises",
    )
    args  = parser.parse_args()
    track = None if args.all_tracks else args.track
    run_contacts(track=track, flush=args.flush, flush_history=args.flush_history)
