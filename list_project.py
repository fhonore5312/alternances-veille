#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_project.py — Liste tous les fichiers du projet avec taille et date.
Signale les fichiers suspects (doublons, temporaires, residus V1).
Usage : python list_project.py
"""
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent

# Patterns a signaler comme suspects
SUSPECT_PATTERNS = [
    "scraper_lba.py",       # V1 (remplace par lba_scraper.py)
    "test_search_agent.py", # ancien nom
    "merge_llm_tracks.py",  # verifier si encore utilise
    "main_flow.py",         # architecture V1 subprocess (remplace par flow.py)
    ".disabled",
    "__pycache__",
    ".pyc",
    "offres_historique_v1", "offres_historique_v2",  # fichiers merge one-shot
]

IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache"}

def fmt_size(n):
    if n < 1024: return f"{n}B"
    if n < 1024**2: return f"{n//1024}KB"
    return f"{n//1024**2}MB"

def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

print("=" * 80)
print(f"LISTING PROJET : {BASE_DIR}")
print("=" * 80)

total_files = 0
total_size  = 0
suspects    = []

for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in sorted(dirs) if d not in IGNORE_DIRS]
    rel_root = Path(root).relative_to(BASE_DIR)
    depth    = len(rel_root.parts)
    indent   = "  " * depth
    if depth > 0:
        print(f"{indent[:-2]}📁 {Path(root).name}/")
    for fname in sorted(files):
        fpath = Path(root) / fname
        stat  = fpath.stat()
        size  = stat.st_size
        mdate = fmt_date(stat.st_mtime)
        flag  = ""
        for pat in SUSPECT_PATTERNS:
            if pat.lower() in fname.lower():
                flag = "  ⚠️  SUSPECT"
                suspects.append(str(fpath.relative_to(BASE_DIR)))
                break
        print(f"{"  " * depth}  📄 {fname:<45} {fmt_size(size):>7}  {mdate}{flag}")
        total_files += 1
        total_size  += size

print()
print("=" * 80)
print(f"Total : {total_files} fichiers — {fmt_size(total_size)}")
if suspects:
    print()
    print(f"⚠️  Fichiers suspects ({len(suspects)}) — a verifier/supprimer :")
    for s in suspects:
        print(f"   del {s}")
print("=" * 80)
