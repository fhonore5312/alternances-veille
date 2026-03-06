#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_flow.py - Orchestrateur principal du robot alternances

Usage:
    python main_flow.py              # flow complet, validator standard
    python main_flow.py --quick      # validator skip les offres validées < 7 jours
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Tracks LLM : clés au format test_search_agent (sans underscore)
TRACKS_LLM = ["digitalmarketing", "finance"]

# Tracks LBA : tous les tracks (--all-tracks lit tracks.yml directement)
# Listés ici pour le résumé de fin de flow uniquement
TRACKS_LBA = ["digital_marketing", "finance", "supply_chain", "business_dev"]

DATA_DIR   = Path("data")
CONFIG_DIR = Path("config")
LOG_DIR    = Path("logs")

LLM_MODEL = "anthropic/claude-haiku-4-5-20251001"

LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

file_handler    = logging.FileHandler(
    LOG_DIR / ("flow_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"),
    encoding="utf-8"
)
console_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[file_handler, console_handler]
)
log = logging.getLogger(__name__)


def _env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return env


# ===== ÉTAPE 1 : Scraper LBA =====

def run_lba_scraper():
    log.info("=== ETAPE 1 : Scraper La Bonne Alternance ===")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.scraper_lba", "--all-tracks"],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=_env()
        )
        if result.returncode == 0:
            log.info("LBA scraper OK")
        else:
            log.warning("LBA scraper erreur (code %d):\n%s", result.returncode, result.stderr[:500])
    except subprocess.TimeoutExpired:
        log.error("LBA scraper timeout (>5min)")
    except Exception as e:
        log.error("LBA scraper exception : %s", e)


# ===== ÉTAPE 2 : LLM Search Agents =====

def run_llm_agent(track):
    log.info("--- LLM agent : %s ---", track)
    backstory = CONFIG_DIR / ("agent_backstory_" + track + ".md")
    prompt    = CONFIG_DIR / ("prompt_llm_search_" + track + ".md")
    if not backstory.exists():
        log.error("Backstory manquante : %s", backstory)
        return False
    if not prompt.exists():
        log.error("Prompt manquant : %s", prompt)
        return False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.test_search_agent",
             "--track", track, "--llm", LLM_MODEL],
            capture_output=True, text=True, encoding="utf-8", timeout=600, env=_env()
        )
        if result.returncode == 0:
            log.info("LLM agent %s OK", track)
            return True
        else:
            log.warning("LLM agent %s erreur :\n%s", track, result.stderr[:500])
            return False
    except subprocess.TimeoutExpired:
        log.error("LLM agent %s timeout (>10min)", track)
        return False
    except Exception as e:
        log.error("LLM agent %s exception : %s", track, e)
        return False


def run_all_llm_agents():
    log.info("=== ETAPE 2 : LLM Search Agents ===")
    results = {}
    for track in TRACKS_LLM:
        results[track] = run_llm_agent(track)
    ok = sum(results.values())
    log.info("LLM agents : %d/%d reussis", ok, len(TRACKS_LLM))
    return results


# ===== ÉTAPE 3 : Fusion fichiers LLM =====

def run_merge_llm_tracks():
    log.info("=== ETAPE 3 : Fusion fichiers LLM par track ===")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.merge_llm_tracks"],
            capture_output=True, text=True, encoding="utf-8", timeout=60, env=_env()
        )
        if result.returncode == 0:
            log.info("Fusion LLM tracks OK")
            return True
        else:
            log.warning("Fusion LLM tracks erreur :\n%s", result.stderr[:500])
            return False
    except Exception as e:
        log.error("Fusion LLM tracks exception : %s", e)
        return False


# ===== ÉTAPE 4 : Validation =====

def run_validator(quick_mode=False):
    log.info("=== ETAPE 4 : Validation des offres%s ===", " (quick)" if quick_mode else "")
    cmd = [sys.executable, "-m", "scripts.validator"]
    if quick_mode:
        cmd.append("--quick")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=4800, env=_env()
        )
        if result.returncode == 0:
            log.info("Validation OK")
            return True
        else:
            log.warning("Validation erreur :\n%s", result.stderr[:500])
            return False
    except subprocess.TimeoutExpired:
        log.error("Validation timeout (>80min)")
        return False
    except Exception as e:
        log.error("Validation exception : %s", e)
        return False


# ===== ÉTAPE 5 : Merge & déduplication =====

def run_merge():
    log.info("=== ETAPE 5 : Merge & deduplication ===")
    lba_validated = DATA_DIR / "offres_lba_validated.json"
    if not lba_validated.exists():
        log.error("%s introuvable - validation LBA a echoue", lba_validated)
        return False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.merge_offers"],
            capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env()
        )
        if result.returncode == 0:
            log.info("Merge OK")
            return True
        else:
            log.warning("Merge erreur :\n%s", result.stderr[:500])
            return False
    except Exception as e:
        log.error("Merge exception : %s", e)
        return False


# ===== ÉTAPE 6 : Génération HTML + email =====

def run_html_email():
    log.info("=== ETAPE 6 : Generation email HTML ===")
    merged_file = DATA_DIR / "offres_merged.json"
    if not merged_file.exists():
        log.error("%s introuvable - merge a echoue", merged_file)
        return False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.generate_html_email"],
            capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env()
        )
        if result.returncode == 0:
            log.info("Email HTML genere OK")
            return True
        else:
            log.warning("Email HTML erreur :\n%s", result.stderr[:500])
            return False
    except Exception as e:
        log.error("Email HTML exception : %s", e)
        return False


# ===== RÉSUMÉ =====

def print_summary(agent_results, start):
    log.info("=== RESUME DU FLOW ===")
    merged_file = DATA_DIR / "offres_merged.json"
    if merged_file.exists():
        with open(merged_file, encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("meta", {})
        log.info("Total offres mergees : %s", meta.get("total_offres", "?"))
        log.info("  nouvelles : %s", meta.get("nouvelles", "?"))
        log.info("  actives   : %s", meta.get("actives",   "?"))
        for track, stats in meta.get("stats_by_track", {}).items():
            log.info("  %-25s : %d offres (%d nouvelles)", track, stats["total"], stats["nouvelles"])
    else:
        log.warning("offres_merged.json introuvable")
    for track, ok in agent_results.items():
        log.info("  %s LLM agent %s", "OK" if ok else "ECHEC", track)
    elapsed = int((datetime.now() - start).total_seconds())
    log.info("Duree totale : %ds (%dmin %ds)", elapsed, elapsed // 60, elapsed % 60)


# ===== MAIN =====

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrateur principal du robot alternances")
    parser.add_argument(
        "--quick", action="store_true",
        help="Mode rapide : validator skip les offres deja validees < 7 jours"
    )
    args = parser.parse_args()

    start = datetime.now()
    log.info("Flow demarre -- %s", start.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Mode : %s", "quick" if args.quick else "complet")

    run_lba_scraper()                            # Etape 1 : LBA → offres_lba.json
    agent_results = run_all_llm_agents()         # Etape 2 : LLM → offres_agent_*.json
    run_merge_llm_tracks()                       # Etape 3 : fusion → offres_llm.json
    run_validator(quick_mode=args.quick)         # Etape 4 : validation → *_validated.json
    run_merge()                                  # Etape 5 : merge → offres_merged.json
    run_html_email()                             # Etape 6 : HTML + email
    print_summary(agent_results, start)
