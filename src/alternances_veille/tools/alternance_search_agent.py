#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/llm_search_agent.py — Interface publique recherche LLM offres alternance
Délègue à crews/search_crew/search_crew.py (SearchCrew @CrewBase).

Interface :
    run_alternance_search_agent(track, test_mode=False) -> str  (chemin fichier)
    run_all_llm_agents(test_mode=False) -> dict

Usage standalone :
    python -m alternances_veille.tools.llm_search_agent --track digitalmarketing
    python -m alternances_veille.tools.llm_search_agent --track finance --test
    python -m alternances_veille.tools.llm_search_agent --all
"""

import argparse
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ===== CHEMINS =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRACKS_LLM = ["digitalmarketing", "finance"]

# ===== BLACKLISTS ÉCOLE =====

_SCHOOL_BLACKLIST_ENTREPRISE = {
    "alticome", "mydigitalschool", "studi", "iscod",
    "sup de pub", "openclassrooms", "bringme", "alticom",
    "groupe igs", "neogest", "igf formation", "campus channel",
    "école", "ecole", "cfa", "centre de formation",
    "rocket school", "association imc", "talents handicap",
}

_SCHOOL_BLACKLIST_URL = {
    "alticome.fr", "mydigitalschool.com", "studi.fr", "iscod.fr",
    "sup-de-pub.com", "openclassrooms.com", "bringme.fr",
    "alticom.com", "groupe-igs.fr", "neogest.com",
}

_SCHOOL_BLACKLIST_DESC = {
    "formaposte",
    "l'alternance à la poste est exclusivement accessible en suivant la formation",
    "centre de formation professionnelle recherche pour l'un de ses",
    "recherche pour l'une de ses entreprises partenaires",
    "notre école recrute pour",
    "notre cfa recrute pour",
    "irss,",
}


# ===== UTILITAIRES JSON =====

def _repair_truncated_json(raw: str):
    for closing in ["\n  ]\n}", "\n]}"]:
        try:
            return json.loads(raw.rstrip() + closing)
        except json.JSONDecodeError:
            continue
    return None


def _normalize_offer(offer: dict, today_str: str) -> None:
    if not offer.get("date_creation"):
        raw = offer.get("first_seen") or today_str
        try:
            offer["date_creation"] = datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            offer["date_creation"] = raw
    if offer.get("status") not in ("new", "active", "incertain"):
        offer["status"] = "new"


def _is_school_offer(offer: dict) -> bool:
    entreprise = offer.get("entreprise", "").lower()
    url        = offer.get("url_candidature", "").lower()
    desc       = offer.get("description_complete", offer.get("description", "")).lower()
    if any(s in entreprise for s in _SCHOOL_BLACKLIST_ENTREPRISE):
        return True
    if any(d in url for d in _SCHOOL_BLACKLIST_URL):
        return True
    if any(p in desc for p in _SCHOOL_BLACKLIST_DESC):
        return True
    return False


def clean_llm_output_file(filepath: str) -> int:
    """Nettoie le JSON LLM, répare les troncatures, normalise et filtre les offres."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    today_str = str(date.today())
    cleaned   = None

    if raw.startswith("{"):
        cleaned = raw
    else:
        for pat in [r"```json\s*([\s\S]+?)\s*```", r"(\{[\s\S]+\})"]:
            m = re.search(pat, raw)
            if m:
                cleaned = m.group(1).strip()
                break

    if not cleaned:
        print(f"[warn] Impossible de nettoyer {filepath}")
        return 0

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[warn] JSON invalide : {e} — tentative de réparation")
        data = _repair_truncated_json(cleaned)
        if data is None:
            print(f"[ERROR] Réparation impossible : {filepath}")
            return 0

    for offer in data.get("offres", []):
        _normalize_offer(offer, today_str)

    before = len(data.get("offres", []))
    data["offres"] = [o for o in data.get("offres", []) if not _is_school_offer(o)]
    removed = before - len(data["offres"])
    if removed:
        print(f"[filter-school] {removed} offre(s) école/CFA supprimée(s)")

    nb = len(data["offres"])
    data.setdefault("meta", {})["nb_offres"] = nb

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[ok] {filepath} → {nb} offres")
    return nb


# ===== INTERFACE PUBLIQUE =====

def run_alternance_search_agent(track: str = "digitalmarketing", test_mode: bool = False) -> str:
    """
    Lance SearchCrew pour un track donné.
    Retourne le chemin du fichier JSON produit.
    """
    from alternances_veille.crews.search_crew.search_crew import SearchCrew

    today = date.today().isoformat()
    print(f"\n{'=' * 60}")
    print(f"LLM SEARCH AGENT — {track.upper()}")
    print(f"{'=' * 60}\n")

    crew_inst = SearchCrew(track=track, test_mode=test_mode)

    try:
        crew_inst.crew().kickoff(inputs={"date_today": today})
    except ValueError as e:
        print(f"[warn] Crew échouée ({e}) — tentative récupération fichier partiel")
    except Exception as e:
        print(f"[error] Crew échouée : {e}")

    suffix      = "_test" if test_mode else ""
    output_file = str(DATA_DIR / f"offres_agent_{track}{suffix}.json")

    if os.path.exists(output_file):
        nb = clean_llm_output_file(output_file)
        print(f"[ok] {nb} offres sauvegardées" if nb else "[warn] Fichier vide")
    else:
        print("[warn] Aucun fichier de sortie — run sans résultat")

    return output_file


def run_all_alternance_search_agents(test_mode: bool = False) -> dict:
    """Lance les deux tracks séquentiellement."""
    results = {}
    for track in TRACKS_LLM:
        try:
            results[track] = run_alternance_search_agent(track, test_mode)
            print(f"OK {track} → {results[track]}")
        except Exception as e:
            print(f"ERREUR {track} : {e}")
            results[track] = None
    return results


# ===== ENTRYPOINT STANDALONE =====

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent LLM recherche offres alternance")
    parser.add_argument(
        "--track", default="digitalmarketing",
        choices=TRACKS_LLM + ["all"],
        help="Track à traiter (ou 'all' pour les deux)",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Mode test : écrit dans offres_agent_*_test.json",
    )
    args = parser.parse_args()

    if args.track == "all":
        run_all_llm_agents(test_mode=args.test)
    else:
        run_alternance_search_agent(args.track, args.test)
