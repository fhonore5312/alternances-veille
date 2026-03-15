#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/validator.py - Validation LBA (HTTP) + LLM (structure JSON)
Usage:
    python -m alternances_veille.tools.validator
    python -m alternances_veille.tools.validator --quick
"""

import argparse
import json
import re
import time
import requests
from datetime import datetime
from pathlib import Path

BASE_DIR        = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR        = BASE_DIR / "data"

LBA_INPUT_FILE  = DATA_DIR / "offres_lba.json"
LBA_OUTPUT_FILE = DATA_DIR / "offres_lba_validated.json"
LLM_OUTPUT_FILE = DATA_DIR / "offres_llm_validated.json"

# Fichiers LLM agents (un par track)
LLM_AGENT_FILES = [
    DATA_DIR / "offres_agent_digitalmarketing.json",
    DATA_DIR / "offres_agent_finance.json",
]

# ===== CONFIGURATION =====

TIMEOUT                = 15
DELAY_BETWEEN_REQUESTS = 2
USER_AGENT             = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EXPIRED_KEYWORDS = [
    "offre n'est plus disponible", "candidatures fermées",
    "no longer accepting applications", "expired", "closed",
    "pourvue", "les candidatures ne sont plus acceptées",
    "cette offre a expiré", "offre expirée", "offre retirée",
    "plus d'offres disponibles", "offre pourvue", "poste pourvu",
    "recrutement terminé", "cette offre n'est plus disponible", "offre clôturée",
]

APPLY_BUTTON_KEYWORDS = [
    "postuler", "candidater", "apply now", "apply",
    "postuler maintenant", "je postule", "envoyer ma candidature",
    "postuler en ligne", "déposer votre candidature",
]

SENIOR_JOB_TITLES = ["manager", "responsable", "chef", "directeur", "head of", "lead"]

REQUIRED_LLM_FIELDS = {
    "id":              str,
    "source":          str,
    "status":          str,
    "titre":           str,
    "entreprise":      str,
    "ville":           str,
    "code_postal":     str,
    "url_candidature": str,
    "date_creation":   (str, type(None)),
    "priorite_ville":  int,
}

OPTIONAL_LLM_FIELDS = {
    "description": str, "description_complete": str,
    "competences_detectees": list, "type_contrat": str,
    "duree_contrat": str, "date_debut": str,
    "date_expiration": (str, type(None)), "plateforme_source": str,
    "ville_recherche": str, "adresse_complete": str,
    "first_seen": str, "last_seen": str, "track": str,
}

# ===== UTILITAIRES HTTP =====

def fetch_url_content(url: str):
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, r.text, None
    except requests.exceptions.Timeout:
        return None, None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "connection_error"
    except Exception as e:
        return None, None, str(e)

def check_offer_status(html: str) -> dict:
    if not html:
        return {"is_expired": True, "has_apply_button": False,
                "detected_date": None, "confidence": "low", "reason": "no_content"}

    low                = html.lower()
    is_expired         = any(kw in low for kw in EXPIRED_KEYWORDS)
    has_apply_button   = any(kw in low for kw in APPLY_BUTTON_KEYWORDS)

    detected_date = None
    for pat in [
        r"(?:publiée|postée|published).*?(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})",
        r"(?:il y a|posted)\s+(\d+)\s+(jour|jours|day|days|semaine|week|mois|month)",
        r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+\d{4})",
    ]:
        m = re.search(pat, low)
        if m:
            detected_date = m.group(0)
            break

    if is_expired and not has_apply_button:
        confidence = "high"
    elif not is_expired and has_apply_button:
        confidence = "high"
    elif is_expired or not has_apply_button:
        confidence = "medium"
    else:
        confidence = "low"

    return {"is_expired": is_expired, "has_apply_button": has_apply_button,
            "detected_date": detected_date, "confidence": confidence,
            "reason": "content_analysis"}

def validate_offer_data(offer: dict) -> tuple:
    titre         = offer.get("titre", "").lower()
    date_debut    = offer.get("date_debut")
    duree_contrat = offer.get("duree_contrat")

    if date_debut:
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                d = datetime.strptime(str(date_debut), fmt)
                if d.year < 2026:
                    return False, f"Date début obsolète ({d.year})"
                break
            except ValueError:
                continue

    if any(kw in titre for kw in SENIOR_JOB_TITLES):
        if not duree_contrat or str(duree_contrat).lower() in ("null", "none", ""):
            return False, "Poste confirmé sans durée (probable CDI)"

    return True, "OK"

def validate_lba_offer(offer: dict, quick_mode: bool = False) -> dict:
    url = offer.get("url_candidature", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not url or url in ("#", ""):
        offer["validation_status"]  = "invalid"
        offer["validation_details"] = {"checked_at": now, "reason": "no_url", "is_expired": True}
        return offer

    if quick_mode and offer.get("validation_status") == "validated":
        val_date = offer.get("validation_details", {}).get("checked_at")
        if val_date:
            try:
                if (datetime.now() - datetime.strptime(val_date, "%Y-%m-%d %H:%M:%S")).days < 7:
                    print(f"  ⏭️  Skip (validé le {val_date[:10]})")
                    return offer
            except Exception:
                pass

    print(f"  🔍 {offer['titre'][:55]}...")
    status_code, html, error = fetch_url_content(url)

    if error:
        offer["validation_status"]  = "error"
        offer["validation_details"] = {"checked_at": now, "error": error, "is_expired": None}
        print(f"  ❌ Erreur réseau : {error}")
    elif status_code == 404:
        offer["validation_status"]  = "expired"
        offer["validation_details"] = {"checked_at": now, "status_code": 404,
                                        "is_expired": True, "confidence": "high",
                                        "reason": "page_not_found"}
        print("  💀 404 — Expirée")
    elif status_code == 200:
        s = check_offer_status(html)
        offer["validation_status"] = (
            "expired"    if s["is_expired"]       else
            "validated"  if s["has_apply_button"] else
            "uncertain"
        )
        offer["validation_details"] = {"checked_at": now, "status_code": 200, **s}
        icons = {"expired": "💀", "validated": "✅", "uncertain": "⚠️"}
        print(f"  {icons.get(offer['validation_status'], '?')} {offer['validation_status']} ({s['confidence']})")
    else:
        offer["validation_status"]  = "uncertain"
        offer["validation_details"] = {"checked_at": now, "status_code": status_code,
                                        "is_expired": None, "confidence": "low"}
        print(f"  ⚠️  HTTP {status_code}")

    return offer

# ===== VALIDATION LBA =====

def validate_lba_offers(quick_mode: bool = False) -> dict:
    print("=" * 80)
    print("🔍 VALIDATION LBA")
    print("=" * 80)

    if not LBA_INPUT_FILE.exists():
        print(f"❌ {LBA_INPUT_FILE} introuvable")
        return None

    with open(LBA_INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    offers = data.get("offres", [])
    print(f"📦 {len(offers)} offres chargées")

    # Quick mode : charger statuts précédents depuis offres_lba_validated.json
    previous = {}
    if quick_mode and LBA_OUTPUT_FILE.exists():
        try:
            with open(LBA_OUTPUT_FILE, encoding="utf-8") as f:
                prev_data = json.load(f)
            previous = {o["id"]: o for o in prev_data.get("offres", []) if o.get("id")}
            print(f"⚡ Quick mode : {len(previous)} statuts précédents chargés")
        except Exception as e:
            print(f"⚠️  Impossible de charger les statuts précédents : {e}")
    print()

    validated, expired_excl, errors, uncertain, rejected, kept = 0, 0, 0, 0, 0, 0
    validated_offers = []

    for i, offer in enumerate(offers, 1):
        print(f"[{i}/{len(offers)}] {offer.get('entreprise','?')} — {offer.get('ville','?')}")

        is_valid, reason = validate_offer_data(offer)
        if not is_valid:
            print(f"  🚫 Rejetée (métier) : {reason}")
            offer["validation_status"]  = "rejected"
            offer["validation_details"] = {
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason, "rejection_type": "business_rule",
            }
            rejected += 1
            continue

        if quick_mode and offer.get("id") in previous:
            prev = previous[offer["id"]]
            offer["validation_status"]  = prev.get("validation_status")
            offer["validation_details"] = prev.get("validation_details")

        offer  = validate_lba_offer(offer, quick_mode=quick_mode)
        status = offer.get("validation_status")
        conf   = offer.get("validation_details", {}).get("confidence", "low")

        if status == "validated":
            validated += 1
            validated_offers.append(offer)
        elif status == "uncertain":
            uncertain += 1
            validated_offers.append(offer)
            kept += 1
            print("  ℹ️  Gardée (incertitude)")
        elif status == "expired":
            if conf == "low":
                validated_offers.append(offer)
                kept += 1
                print("  ℹ️  Gardée (expiration incertaine, confidence: low)")
            else:
                expired_excl += 1
                print(f"  💀 Exclue (confidence: {conf})")
        elif status == "error":
            errors += 1
            validated_offers.append(offer)
            kept += 1
            print("  ℹ️  Gardée (erreur réseau transitoire)")
        elif status == "invalid":
            expired_excl += 1

        if i < len(offers):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    data["offres"] = validated_offers
    data["meta"].update({
        "validation_date":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_offres":        len(validated_offers),
        "validated":           validated,
        "expired":             expired_excl,
        "errors":              errors,
        "uncertain":           uncertain,
        "rejected_business":   rejected,
        "kept_despite_issues": kept,
    })

    with open(LBA_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {validated} validées | ⚠️ {uncertain} incertaines | 💀 {expired_excl} exclues")
    print(f"💾 {len(validated_offers)} offres → {LBA_OUTPUT_FILE}")
    print("=" * 80)
    return data

# ===== VALIDATION LLM =====

def validate_llm_offer(offer: dict) -> tuple:
    errors, warnings = [], []

    for field, expected_type in REQUIRED_LLM_FIELDS.items():
        if field not in offer:
            errors.append(f"Champ obligatoire manquant : {field}")
        elif not isinstance(offer[field], expected_type):
            type_name = (expected_type.__name__ if isinstance(expected_type, type)
                         else " | ".join(t.__name__ for t in expected_type))
            errors.append(f"Type incorrect pour {field} : attendu {type_name}, "
                          f"reçu {type(offer[field]).__name__}")
        elif isinstance(offer[field], str) and not offer[field].strip():
            errors.append(f"Champ vide : {field}")

    if offer.get("source") != "LLM":
        warnings.append(f"Source devrait être 'LLM', trouvé : {offer.get('source')}")
    if offer.get("status") not in ("new", "active", "incertain"):
        warnings.append(f"Status inhabituel : {offer.get('status')}")
    if offer.get("priorite_ville") not in (1, 2, 3):
        warnings.append(f"Priorité ville invalide : {offer.get('priorite_ville')}")

    url = offer.get("url_candidature", "")
    if url and not url.startswith("http"):
        errors.append(f"URL invalide : {url}")

    dc = offer.get("date_creation")
    if dc:
        try:
            datetime.strptime(dc, "%d/%m/%Y")
        except ValueError:
            warnings.append(f"Format date_creation incorrect : {dc}")

    is_valid = len(errors) == 0
    offer["validation_status"]  = "validated" if is_valid else "invalid"
    offer["validation_details"] = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "errors":     errors   or None,
        "warnings":   warnings or None,
        "source":     "structure_validation",
    }

    label  = "✅" if is_valid else "❌"
    suffix = " (avec avertissements)" if (is_valid and warnings) else ""
    print(f"  {label} {offer['titre']} — {offer['entreprise']}{suffix}")
    for e in errors:
        print(f"     • {e}")
    return offer, is_valid

def validate_llm_offers() -> dict:
    print("\n" + "=" * 80)
    print("🔍 VALIDATION LLM")
    print("=" * 80)

    # Consolide tous les fichiers agents en un seul jeu d'offres
    all_offers = []
    for agent_file in LLM_AGENT_FILES:
        if not agent_file.exists():
            print(f"ℹ️  {agent_file.name} absent — ignoré")
            continue
        try:
            with open(agent_file, encoding="utf-8") as f:
                data = json.load(f)
            track_offers = data.get("offres", [])
            print(f"📂 {agent_file.name} : {len(track_offers)} offres")
            all_offers.extend(track_offers)
        except json.JSONDecodeError as e:
            print(f"❌ JSON invalide dans {agent_file.name} : {e}")

    if not all_offers:
        print("ℹ️  Aucune offre LLM à valider")
        print("=" * 80)
        return None

    print(f"\n📦 {len(all_offers)} offres LLM au total\n")

    valid, invalid, warn_count = 0, 0, 0
    validated_offers = []

    for i, offer in enumerate(all_offers, 1):
        print(f"[{i}/{len(all_offers)}] {offer.get('entreprise','N/A')} — {offer.get('ville','N/A')}")
        v_offer, is_valid = validate_llm_offer(offer)
        validated_offers.append(v_offer)
        if is_valid:
            valid += 1
            if v_offer["validation_details"].get("warnings"):
                warn_count += 1
        else:
            invalid += 1

    output = {
        "meta": {
            "validation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_offres":    len(all_offers),
            "valid_offres":    valid,
            "invalid_offres":  invalid,
            "warnings":        warn_count,
        },
        "offres": validated_offers,
    }

    with open(LLM_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {valid} valides | ⚠️ {warn_count} avertissements | ❌ {invalid} invalides")
    print(f"💾 {len(validated_offers)} offres → {LLM_OUTPUT_FILE}")
    print("=" * 80)
    return output

# ===== POINT D'ENTRÉE =====

def run_validator(quick_mode: bool = False) -> tuple:
    """Lance validation LBA + LLM. Retourne (lba_count, llm_count)."""
    print("=" * 80)
    print("🚀 VALIDATOR — LBA + LLM")
    print("=" * 80)

    lba_result = validate_lba_offers(quick_mode=quick_mode)
    llm_result = validate_llm_offers()

    lba_count = lba_result["meta"]["total_offres"] if lba_result else 0
    llm_count = llm_result["meta"]["valid_offres"]  if llm_result else 0

    print(f"\n📊 RÉSUMÉ : {lba_count} LBA retenues | {llm_count} LLM valides")
    print("=" * 80)
    return lba_count, llm_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Skip les offres validées < 7 jours")
    args = parser.parse_args()
    run_validator(quick_mode=args.quick)
