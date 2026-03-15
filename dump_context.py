#!/usr/bin/env python3
"""
dump_context.py — Génère un snapshot du projet pour contexte LLM

Usage:
    python dump_context.py                                  → dump complet
    python dump_context.py --groups crewai config          → groupes prédéfinis
    python dump_context.py --files src/alternances_veille/tools/validator.py
    python dump_context.py --since HEAD~1
    python dump_context.py --since 2026-03-14
    python dump_context.py --groups tools html --output session_html.txt
"""

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

GROUPS = {
    "core": [
        "main.py",
        "CONTEXT.md",
        "src/alternances_veille/main.py",
        "src/alternances_veille/flow.py",
    ],
    "crewai": [
        "src/alternances_veille/tools/llm_search_agent.py",
        "config/agents.yaml",
        "config/tasks.yaml",
        # backstory et prompts supprimés (fichiers obsolètes)
    ],
    "config": [
        "config/tracks.yml",
        "config/agents.yaml",
        "config/tasks.yaml",
    ],
    "tools": [
        "src/alternances_veille/tools/lba_scraper.py",
        "src/alternances_veille/tools/merge_offers.py",
        "src/alternances_veille/tools/validator.py",
        "src/alternances_veille/tools/html_email.py",
    ],
    "html": [
        "src/alternances_veille/tools/html_email.py",
    ],
    "ci": [
        ".env.example",
        ".github/workflows/veille-alternance.yml",
    ],
}

ALL_FILES = list(dict.fromkeys(f for group in GROUPS.values() for f in group))


def get_files_modified_since(since: str) -> list[str]:
    """Retourne les fichiers trackés par git modifiés depuis `since` (ref ou date ISO)."""
    files = []
    try:
        r1 = subprocess.run(
            ["git", "diff", "--name-only", since],
            capture_output=True, text=True, check=True,
        )
        files += [f.strip() for f in r1.stdout.splitlines() if f.strip()]
        r2 = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, check=True,
        )
        files += [f.strip() for f in r2.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        try:
            r3 = subprocess.run(
                ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
                capture_output=True, text=True, check=True,
            )
            files = [f.strip() for f in r3.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError as e:
            print(f"Erreur git : {e}")
            return []

    known = set(ALL_FILES)
    return sorted(set(f for f in files if f in known and Path(f).exists()))


def dump_files(file_list: list[str], output_path: Path) -> None:
    lines = [f"# CONTEXT DUMP — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    found, missing = 0, 0

    for filepath in file_list:
        p = Path(filepath)
        lines.append(f"\n{'=' * 60}")
        lines.append(f"# FILE: {filepath}")
        lines.append(f"{'=' * 60}\n")
        if p.exists():
            lines.append(p.read_text(encoding="utf-8"))
            found += 1
        else:
            lines.append(f"FICHIER INTROUVABLE : {filepath}")
            missing += 1

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK {output_path} — {found} fichiers / {missing} manquants")
    if missing:
        print(f"Manquants : {[f for f in file_list if not Path(f).exists()]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump contexte projet V2 pour LLM")
    parser.add_argument("--files", nargs="+", metavar="FILE")
    parser.add_argument(
        "--groups", nargs="+", choices=list(GROUPS.keys()), metavar="GROUP",
        help=f"Groupes disponibles : {', '.join(GROUPS.keys())}",
    )
    parser.add_argument("--since", metavar="REF_OR_DATE",
                        help="ex: HEAD~1, 2026-03-14")
    parser.add_argument("--output", default=None,
                        help="Nom du fichier de sortie (défaut: CONTEXT_DUMP_<label>.txt)")
    args = parser.parse_args()

    if args.since:
        file_list = get_files_modified_since(args.since)
        label = f"since_{args.since.replace('/', '-').replace(' ', '_')}"
        if not file_list:
            print(f"Aucun fichier modifié détecté depuis '{args.since}'")
            return
        print(f"Fichiers détectés ({len(file_list)}) : {file_list}")
    elif args.files:
        file_list = args.files
        label = "custom"
    elif args.groups:
        file_list = list(dict.fromkeys(f for g in args.groups for f in GROUPS[g]))
        label = "+".join(args.groups)
    else:
        file_list = ALL_FILES
        label = "full"

    output_name = args.output or f"CONTEXT_DUMP_{label}.txt"
    dump_files(file_list, Path(output_name))


if __name__ == "__main__":
    main()
