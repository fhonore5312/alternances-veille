## 🛠️ dump_context.py — Outil de snapshot LLM

Génère un fichier texte contenant le code source du projet,
destiné à être attaché à un thread LLM (Perplexity, Claude...).

### Usage

```bash
# Dump complet de tous les fichiers du projet
python dump_context.py

# Par groupe prédéfini
python dump_context.py --groups scripts
python dump_context.py --groups scripts config utils

# Fichiers spécifiques
python dump_context.py --files scripts/validator.py config/tracks.yml

# Fichiers modifiés depuis un commit
python dump_context.py --since HEAD~1
python dump_context.py --since main

# Fichiers modifiés depuis une date
python dump_context.py --since 2026-03-01

# Nom de sortie personnalisé
python dump_context.py --groups scripts --output session_validator.txt
