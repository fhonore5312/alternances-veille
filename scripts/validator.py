#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validator.py - Validation complète LBA + Perplexity

Ce script :
1. Charge et valide data/offres_lba.json (validation métier + HTTP)
2. Charge et valide data/offres_perplexity.json (validation structure JSON)
3. Génère data/offres_lba_validated.json
4. Génère data/offres_perplexity_validated.json

Usage:
  python -m scripts.validator
  python -m scripts.validator --quick
"""

import requests
import json
from datetime import datetime
import time
import re
import argparse
from pathlib import Path

# ===== CONFIGURATION CHEMINS =====

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"

LBA_INPUT_FILE = DATA_DIR / "offres_lba.json"
PERPLEXITY_INPUT_FILE = DATA_DIR / "offres_perplexity.json"
LBA_OUTPUT_FILE = DATA_DIR / "offres_lba_validated.json"
PERPLEXITY_OUTPUT_FILE = DATA_DIR / "offres_perplexity_validated.json"

# ===== CONFIGURATION VALIDATION =====

TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EXPIRED_KEYWORDS = [
    "offre n'est plus disponible",
    "candidatures fermées",
    "no longer accepting applications",
    "expired",
    "closed",
    "pourvue",
    "les candidatures ne sont plus acceptées",
    "cette offre a expiré",
    "offre expirée",
    "offre retirée",
    "plus d'offres disponibles",
    "offre pourvue",
    "poste pourvu",
    "recrutement terminé",
    "cette offre n'est plus disponible",
    "offre clôturée",
]

APPLY_BUTTON_KEYWORDS = [
    "postuler",
    "candidater",
    "apply now",
    "apply",
    "postuler maintenant",
    "je postule",
    "envoyer ma candidature",
    "postuler en ligne",
    "déposer votre candidature",
]

SENIOR_JOB_TITLES = [
    "manager",
    "responsable",
    "chef",
    "directeur",
    "head of",
    "lead",
]

# ===== SCHÉMA PERPLEXITY =====

REQUIRED_PERPLEXITY_FIELDS = {
    "id": str,
    "source": str,
    "status": str,
    "titre": str,
    "entreprise": str,
    "ville": str,
    "code_postal": str,
    "url_candidature": str,
    "date_creation": str,
    "priorite_ville": int,
}

OPTIONAL_PERPLEXITY_FIELDS = {
    "description": str,
    "description_complete": str,
    "competences_detectees": list,
    "type_contrat": str,
    "duree_contrat": str,
    "date_debut": str,
    "date_expiration": (str, type(None)),
    "plateforme_source": str,
    "ville_recherche": str,
    "adresse_complete": str,
    "first_seen": str,
    "last_seen": str,
    "track": str,
}

# ===== UTILITAIRES =====

def fetch_url_content(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return response.status_code, response.text, None
    except requests.exceptions.Timeout:
        return None, None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "connection_error"
    except Exception as e:
        return None, None, str(e)


def check_offer_status(html_content):
    if not html_content:
        return {
            "is_expired": True,
            "has_apply_button": False,
            "detected_date": None,
            "confidence": "low",
            "reason": "no_content",
        }

    html_lower = html_content.lower()
    is_expired = any(kw in html_lower for kw in EXPIRED_KEYWORDS)
    has_apply_button = any(kw in html_lower for kw in APPLY_BUTTON_KEYWORDS)

    detected_date = None
    date_patterns = [
        r"(?:publiée|postée|published).*?(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})",
        r"(?:il y a|posted)\s+(\d+)\s+(jour|jours|day|days|semaine|week|mois|month)",
        r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, html_lower)
        if match:
            detected_date = match.group(0)
            break

    if is_expired and not has_apply_button:
        confidence = "high"
    elif not is_expired and has_apply_button:
        confidence = "high"
    elif is_expired or not has_apply_button:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "is_expired": is_expired,
        "has_apply_button": has_apply_button,
        "detected_date": detected_date,
        "confidence": confidence,
        "reason": "content_analysis",
    }


def validate_offer_data(offer):
    titre = offer.get("titre", "").lower()
    duree_contrat = offer.get("duree_contrat")
    date_debut = offer.get("date_debut")

    if date_debut:
        try:
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                try:
                    debut_date = datetime.strptime(str(date_debut), fmt)
                    if debut_date.year < 2026:
                        return False, f"Date début obsolète ({debut_date.year})"
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    is_senior_title = any(kw in titre for kw in SENIOR_JOB_TITLES)
    has_no_duration = not duree_contrat or str(duree_contrat).lower() in ["null", "none", ""]
    if is_senior_title and has_no_duration:
        return False, "Poste confirmé sans durée (probable CDI)"

    return True, "OK"


def validate_lba_offer(offer, quick_mode=False):
    url = offer.get("url_candidature", "")

    if not url or url == "#" or url.startswith("#"):
        offer["validation_status"] = "invalid"
        offer["validation_details"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "no_url",
            "is_expired": True,
        }
        return offer

    if quick_mode and offer.get("validation_status") == "validated":
        validation_date = offer.get("validation_details", {}).get("checked_at")
        if validation_date:
            try:
                last_check = datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_check).days < 7:
                    print(f"  ⏭️ Skip (validé récemment)")
                    return offer
            except Exception:
                pass

    print(f"  🔍 {offer['titre'][:55]}...")
    status_code, html_content, error = fetch_url_content(url)

    if error:
        offer["validation_status"] = "error"
        offer["validation_details"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": error,
            "is_expired": None,
        }
        print(f"  ❌ Erreur réseau : {error}")

    elif status_code == 404:
        offer["validation_status"] = "expired"
        offer["validation_details"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status_code": 404,
            "is_expired": True,
            "confidence": "high",
            "reason": "page_not_found",
        }
        print(f"  💀 404 - Expirée (définitif)")

    elif status_code == 200:
        status = check_offer_status(html_content)
        if status["is_expired"]:
            offer["validation_status"] = "expired"
            print(f"  💀 Expirée ({status['confidence']})")
        elif status["has_apply_button"]:
            offer["validation_status"] = "validated"
            print(f"  ✅ Active ({status['confidence']})")
        else:
            offer["validation_status"] = "uncertain"
            print(f"  ⚠️ Incertain ({status['confidence']})")
        offer["validation_details"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status_code": status_code,
            "is_expired": status["is_expired"],
            "has_apply_button": status["has_apply_button"],
            "detected_date": status["detected_date"],
            "confidence": status["confidence"],
        }

    else:
        offer["validation_status"] = "uncertain"
        offer["validation_details"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status_code": status_code,
            "is_expired": None,
            "confidence": "low",
        }
        print(f"  ⚠️ Status HTTP : {status_code}")

    return offer


# ===== VALIDATION LBA =====

def validate_lba_offers(quick_mode=False):
    print("=" * 80)
    print("🔍 VALIDATION LBA")
    print("=" * 80)
    print(f"📂 Entrée : {LBA_INPUT_FILE}")
    print(f"💾 Sortie : {LBA_OUTPUT_FILE}")
    print(f"⚡ Mode   : {'Quick' if quick_mode else 'Complet'}")
    print()

    if not LBA_INPUT_FILE.exists():
        print(f"❌ Fichier introuvable : {LBA_INPUT_FILE}")
        return None

    with open(LBA_INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    offers = data.get("offres", [])
    print(f"📦 {len(offers)} offres chargées\n")

    if not offers:
        print("⚠️ Aucune offre à valider")
        return None

    validated_count = 0
    expired_count = 0
    error_count = 0
    uncertain_count = 0
    rejected_data_count = 0
    kept_despite_issues = 0
    validated_offers = []

    for i, offer in enumerate(offers, 1):
        print(f"[{i}/{len(offers)}] {offer.get('entreprise','?')} - {offer.get('ville','?')}")

        # Validation métier
        is_valid_data, reason = validate_offer_data(offer)
        if not is_valid_data:
            print(f"  🚫 Rejetée (métier) : {reason}")
            offer["validation_status"] = "rejected"
            offer["validation_details"] = {
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason,
                "rejection_type": "business_rule",
            }
            rejected_data_count += 1
            continue

        # Validation HTTP
        offer = validate_lba_offer(offer, quick_mode=quick_mode)
        status = offer.get("validation_status")
        confidence = offer.get("validation_details", {}).get("confidence", "low")

        if status == "validated":
            validated_count += 1
            validated_offers.append(offer)

        elif status == "uncertain":
            uncertain_count += 1
            validated_offers.append(offer)
            kept_despite_issues += 1
            print(f"  ℹ️ Gardée (incertitude)")

        elif status == "expired":
            expired_count += 1
            # ✅ CORRECTIF : on exclut si confidence medium ou high
            if confidence == "low":
                validated_offers.append(offer)
                kept_despite_issues += 1
                print(f"  ℹ️ Gardée (expiration incertaine, confidence: low)")
            else:
                print(f"  💀 Exclue définitivement (confidence: {confidence})")

        elif status == "invalid":
            expired_count += 1
            print(f"  🚫 Invalide (URL manquante)")

        elif status == "error":
            error_count += 1
            validated_offers.append(offer)
            kept_despite_issues += 1
            print(f"  ℹ️ Gardée (erreur réseau transitoire)")

        else:
            uncertain_count += 1

        if i < len(offers):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    data["offres"] = validated_offers
    data["meta"].update({
        "validation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_offres": len(validated_offers),
        "nouvelles": len([o for o in validated_offers if o.get("status") == "new"]),
        "actives": len([o for o in validated_offers if o.get("status") == "active"]),
        "validated": validated_count,
        "expired": expired_count,
        "errors": error_count,
        "uncertain": uncertain_count,
        "rejected_business": rejected_data_count,
        "kept_despite_issues": kept_despite_issues,
    })

    with open(LBA_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 80)
    print("✅ VALIDATION LBA TERMINÉE")
    print("=" * 80)
    print(f"🚫 Rejetées (métier)       : {rejected_data_count}")
    print(f"✅ Validées (actives)       : {validated_count}")
    print(f"⚠️  Incertaines (gardées)   : {uncertain_count}")
    print(f"ℹ️  Gardées malgré problème : {kept_despite_issues}")
    print(f"💀 Expirées exclues         : {expired_count - kept_despite_issues}")
    print(f"❌ Erreurs réseau           : {error_count}")
    print(f"\n💾 {len(validated_offers)} offres → {LBA_OUTPUT_FILE}")
    print("=" * 80)

    return data


# ===== VALIDATION PERPLEXITY =====

def validate_perplexity_offer(offer, index):
    errors = []
    warnings = []

    for field, expected_type in REQUIRED_PERPLEXITY_FIELDS.items():
        if field not in offer:
            errors.append(f"Champ obligatoire manquant : {field}")
        elif not isinstance(offer[field], expected_type):
            errors.append(f"Type incorrect pour {field} : attendu {expected_type.__name__}, reçu {type(offer[field]).__name__}")
        elif expected_type == str and not offer[field].strip():
            errors.append(f"Champ vide : {field}")

    if offer.get("source") != "Perplexity":
        warnings.append(f"Source devrait être 'Perplexity', trouvé : {offer.get('source')}")
    if offer.get("status") not in ["new", "active"]:
        warnings.append(f"Status inhabituel : {offer.get('status')}")
    if offer.get("priorite_ville") not in [1, 2, 3]:
        warnings.append(f"Priorité ville invalide : {offer.get('priorite_ville')}")

    url = offer.get("url_candidature", "")
    if url and not url.startswith("http"):
        errors.append(f"URL invalide : {url}")

    date_creation = offer.get("date_creation", "")
    if date_creation:
        try:
            datetime.strptime(date_creation, "%d/%m/%Y")
        except ValueError:
            warnings.append(f"Format date_creation incorrect (attendu DD/MM/YYYY) : {date_creation}")

    is_valid = len(errors) == 0
    offer["validation_status"] = "validated" if is_valid else "invalid"
    offer["validation_details"] = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "errors": errors if errors else None,
        "warnings": warnings if warnings else None,
        "source": "structure_validation",
    }

    if is_valid:
        suffix = " (avec avertissements)" if warnings else ""
        print(f"  ✅ {offer['titre']} - {offer['entreprise']}{suffix}")
        for w in warnings:
            print(f"     ⚠️ {w}")
    else:
        print(f"  ❌ {offer['titre']} - {offer['entreprise']}")
        for e in errors:
            print(f"     • {e}")

    return offer, is_valid


def validate_perplexity_offers():
    print("\n" + "=" * 80)
    print("🔍 VALIDATION PERPLEXITY")
    print("=" * 80)
    print(f"📂 Entrée : {PERPLEXITY_INPUT_FILE}")
    print(f"💾 Sortie : {PERPLEXITY_OUTPUT_FILE}")
    print()

    if not PERPLEXITY_INPUT_FILE.exists():
        print(f"ℹ️ Fichier introuvable → aucune offre Perplexity à valider")
        print("=" * 80)
        return None

    try:
        with open(PERPLEXITY_INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON : {e}")
        print("=" * 80)
        return None

    offers = data.get("offres", [])
    print(f"📦 {len(offers)} offres chargées\n")

    if not offers:
        print("⚠️ Aucune offre à valider")
        print("=" * 80)
        return None

    valid_count = 0
    invalid_count = 0
    warning_count = 0
    validated_offers = []

    for i, offer in enumerate(offers, 1):
        print(f"[{i}/{len(offers)}] {offer.get('entreprise', 'N/A')} - {offer.get('ville', 'N/A')}")
        validated_offer, is_valid = validate_perplexity_offer(offer, i)
        validated_offers.append(validated_offer)

        if is_valid:
            valid_count += 1
            if validated_offer["validation_details"].get("warnings"):
                warning_count += 1
        else:
            invalid_count += 1

    if "meta" not in data:
        data["meta"] = {}

    data["meta"].update({
        "validation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_offres": len(offers),
        "valid_offres": valid_count,
        "invalid_offres": invalid_count,
        "warnings": warning_count,
    })
    data["offres"] = validated_offers

    with open(PERPLEXITY_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 80)
    print("✅ VALIDATION PERPLEXITY TERMINÉE")
    print("=" * 80)
    print(f"✅ Valides             : {valid_count}")
    print(f"⚠️  Avec avertissements : {warning_count}")
    print(f"❌ Invalides           : {invalid_count}")
    print(f"\n💾 {len(validated_offers)} offres → {PERPLEXITY_OUTPUT_FILE}")
    print("=" * 80)

    return data


# ===== MAIN =====

def main():
    parser = argparse.ArgumentParser(description="Valide les offres LBA et Perplexity")
    parser.add_argument("--quick", action="store_true", help="Skip les offres déjà validées < 7 jours")
    args = parser.parse_args()

    print("=" * 80)
    print("🚀 VALIDATOR - LBA + PERPLEXITY")
    print("=" * 80)
    print()

    lba_result = validate_lba_offers(quick_mode=args.quick)
    perplexity_result = validate_perplexity_offers()

    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ GLOBAL")
    print("=" * 80)

    if lba_result:
        print(f"✅ LBA        : {lba_result['meta']['validated']} validées / {lba_result['meta']['total_offres']} retenues")
    else:
        print("⚠️ LBA        : Aucune offre")

    if perplexity_result:
        print(f"✅ Perplexity : {perplexity_result['meta']['valid_offres']} validées")
    else:
        print("ℹ️ Perplexity : Aucune offre")

    print()
    print("➡️ PROCHAINE ÉTAPE : python -m scripts.merge_offers")
    print("=" * 80)


if __name__ == "__main__":
    main()
