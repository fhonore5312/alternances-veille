#!/usr/bin/env python3
"""
dump_context.py — Génère un snapshot du projet pour contexte LLM

Usage:
    python dump_context.py                              → dump complet
    python dump_context.py --groups scripts config      → groupes prédéfinis
    python dump_context.py --files scripts/validator.py → fichiers spécifiques
    python dump_context.py --since HEAD~1               → fichiers modifiés depuis HEAD~1
    python dump_context.py --since 2026-03-06           → fichiers modifiés depuis une date
    python dump_context.py --groups scripts --output session_validator.txt
"""

import argparse
import subprocess
from datetime import datetime
from pathlib import Path

GROUPS = {
    "core": [
        "main_flow.py",
        "README.md",
        "CONTEXT.md",
        "requirements.txt",
    ],
    "scripts": [
        "scripts/scraper_lba.py",
        "scripts/test_search_agent.py",
        "scripts/merge_llm_tracks.py",
        "scripts/merge_offers.py",
        "scripts/validator.py",
        "scripts/generate_html_email.py",
        "scripts/scrape_hr_contacts_agent.py",
    ],
    "config": [
        "config/tracks.yml",
        "config/prompt_llm_search_digitalmarketing.md",
        "config/prompt_llm_search_finance.md",
        "config/agent_backstory_digitalmarketing.md",
        "config/agent_backstory_finance.md",
    ],
    "utils": [
        "utils/config_loader.py",
        "utils/deduplication.py",
    ],
    "ci": [
        ".env.example",
    ],
}

ALL_FILES = [f for group in GROUPS.values() for f in group]


def get_files_modified_since(since: str) -> list[str]:
    """Retourne les fichiers trackés par git modifiés depuis `since` (ref ou date ISO)."""
    try:
        # Tentative : since = git ref (HEAD~1, abc123, tag...)
        result = subprocess.run(
            ["git", "diff", "--name-only", since],
            capture_output=True, text=True, check=True
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        # Ajoute aussi les fichiers non commités (working tree)
        result2 = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, check=True
        )
        files += [f.strip() for f in result2.stdout.splitlines() if f.strip()]

    except subprocess.CalledProcessError:
        # Fallback : since = date ISO (ex: 2026-03-06)
        try:
            result = subprocess.run(
                ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
                capture_output=True, text=True, check=True
            )
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur git : {e}")
            return []

    # Filtre : seulement les fichiers connus du projet et existants
    known = set(ALL_FILES)
    return sorted(set(f for f in files if f in known and Path(f).exists()))


def dump_files(file_list: list[str], output_path: Path):
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
            lines.append(f"⚠️ FICHIER INTROUVABLE : {filepath}")
            missing += 1

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ {output_path} généré — {found} fichiers / {missing} manquants")
    if missing:
        print(f"⚠️  Manquants : {[f for f in file_list if not Path(f).exists()]}")


def main():
    parser = argparse.ArgumentParser(description="Dump contexte projet pour LLM")
    parser.add_argument(
        "--files", nargs="+", metavar="FILE",
        help="Fichiers spécifiques à dumper"
    )
    parser.add_argument(
        "--groups", nargs="+", choices=list(GROUPS.keys()), metavar="GROUP",
        help=f"Groupes disponibles : {', '.join(GROUPS.keys())}"
    )
    parser.add_argument(
        "--since", metavar="REF_OR_DATE",
        help="Fichiers modifiés depuis une ref git (HEAD~1) ou une date (2026-03-06)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Nom du fichier de sortie (défaut : CONTEXT_DUMP_<label>.txt)"
    )
    args = parser.parse_args()

    if args.since:
        file_list = get_files_modified_since(args.since)
        label = f"since_{args.since.replace('/', '-').replace(' ', '_')}"
        if not file_list:
            print(f"⚠️  Aucun fichier modifié détecté depuis '{args.since}'")
            return
        print(f"📋 Fichiers détectés ({len(file_list)}) : {file_list}")

    elif args.files:
        file_list = args.files
        label = "custom"

    elif args.groups:
        file_list = [f for g in args.groups for f in GROUPS[g]]
        label = "+".join(args.groups)

    else:
        file_list = ALL_FILES
        label = "full"

    output_name = args.output or f"CONTEXT_DUMP_{label}.txt"
    dump_files(file_list, Path(output_name))


if __name__ == "__main__":
    main()
