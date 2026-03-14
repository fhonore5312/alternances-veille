#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Point d'entrée du robot alternances-veille v2

Usage:
    python -m alternances_veille.main              # flow complet
    python -m alternances_veille.main --quick      # skip validation < 7 jours
    python -m alternances_veille.main --debug      # skip étapes si JSON existants
    python -m alternances_veille.main --quick --debug
"""
import argparse
import os
import sys

os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from alternances_veille.flow import VeilleFlow, VeilleState


def main():
    parser = argparse.ArgumentParser(description="Robot de veille alternances v2 — CrewAI Flow")
    parser.add_argument("--quick", action="store_true",
                        help="Skip validation HTTP des offres déjà validées < 7 jours")
    parser.add_argument("--debug", action="store_true",
                        help="Skip les étapes dont les fichiers JSON existent déjà")
    args = parser.parse_args()

    print("=" * 70)
    print("🤖 ALTERNANCES-VEILLE v2 — CrewAI Flow")
    print("=" * 70)
    mode = " + ".join(filter(None, [
        "quick" if args.quick else "",
        "debug" if args.debug else "",
    ])) or "complet"
    print(f"  Mode : {mode}")
    print()

    flow = VeilleFlow()
    flow.kickoff(inputs={
        "quick_mode": args.quick,
        "debug_mode": args.debug,
    })


if __name__ == "__main__":
    main()
