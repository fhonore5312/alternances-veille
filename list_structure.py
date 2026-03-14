#!/usr/bin/env python3
# list_structure.py
# Lancer depuis la racine du repo : python list_structure.py

from pathlib import Path

IGNORE = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}

def list_tree(root: Path, prefix: str = ""):
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    for i, entry in enumerate(entries):
        if entry.name in IGNORE:
            continue
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            list_tree(entry, prefix + extension)

root = Path(".")
print(f"\n📁 {root.resolve().name}/")
list_tree(root)
print()
