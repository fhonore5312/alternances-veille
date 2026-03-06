# alternances-veille 🤖

Robot de veille automatique des offres d'alternance pour Rennes School of Business.
Agrège les offres LBA (La Bonne Alternance) et les résultats d'agents LLM, valide les URLs,
génère un email HTML et publie sur GitHub Pages.

---

## 📋 Prérequis

- Python 3.11+
- Clés API dans `.env` (copier `.env.example`)

```env
LBA_API_KEY=...
ANTHROPIC_API_KEY=...
SERPER_API_KEY=...
GMAIL_USER=...
GMAIL_PASSWORD=...
RECIPIENT_EMAIL=...
```

Installer les dépendances :
```powershell
pip install -r requirements.txt
```

---

## 🚀 Exécution complète (flow automatique)

```powershell
# Flow complet (validator standard)
python main_flow.py

# Flow complet avec validator rapide (skip offres déjà validées < 7 jours)
python main_flow.py --quick
```

---

## 🔧 Exécution manuelle étape par étape

### Étape 1 — Scraper La Bonne Alternance
Récupère les offres depuis l'API LBA pour les 4 tracks et 3 villes.
```powershell
python -m scripts.scraper_lba --all-tracks
# → data/offres_lba.json
```
Options disponibles :
```powershell
python -m scripts.scraper_lba --track finance   # un seul track
python -m scripts.scraper_lba --track digital_marketing
python -m scripts.scraper_lba --track supply_chain
python -m scripts.scraper_lba --track business_dev
```

---

### Étape 2 — Agents LLM (recherche web + scraping)
Lance l'agent CrewAI par track pour trouver des offres supplémentaires.
```powershell
python -m scripts.test_search_agent --track digitalmarketing --llm anthropic/claude-haiku-4-5-20251001
python -m scripts.test_search_agent --track finance           --llm anthropic/claude-haiku-4-5-20251001
# → data/offres_agent_digitalmarketing.json
# → data/offres_agent_finance.json
```
Option test (fichier séparé, sans écraser la prod) :
```powershell
python -m scripts.test_search_agent --track finance --test
# → data/offres_agent_finance_test.json
```

---

### Étape 3 — Fusion des fichiers LLM
Fusionne tous les `offres_agent_*.json` en un seul fichier.
Normalise `date_creation` et `status` pour le validator.
```powershell
python -m scripts.merge_llm_tracks
# → data/offres_llm.json
```

---

### Étape 4 — Validation
Vérifie chaque URL LBA (HTTP) et valide la structure JSON des offres LLM.
```powershell
python -m scripts.validator          # validation complète (~2-3min selon nombre d'offres)
python -m scripts.validator --quick  # skip les offres validées il y a < 7 jours
# → data/offres_lba_validated.json
# → data/offres_llm_validated.json
```

---

### Étape 5 — Merge & déduplication
Fusionne LBA + LLM, déduplique, gère l'historique (new / active).
```powershell
python -m scripts.merge_offers
# → data/offres_merged.json
# → data/offres_historique.json (mis à jour)
```

---

### Étape 6 — Génération HTML + envoi email
Génère la page HTML, publie sur GitHub Pages, envoie l'email Gmail.
```powershell
python -m scripts.generate_html_email
# → docs/index.html
# → docs/archives/veille_YYYY-MM-DD_HH-MM.html
```

---

### Optionnel — Scraping contacts RH
Lance l'agent de recherche de contacts RH sur les entreprises cibles.
```powershell
python -m scripts.scrape_hr_contacts_agent
# → data/hr_contacts.json
# → data/hr_contacts_history.json
```

---

## 📊 Générer un dump de contexte LLM

```powershell
# Dump complet
python dump_context.py

# Scripts modifiés depuis hier
python dump_context.py --since 2026-03-06 --output CONTEXT_DUMP_20260306.txt

# Par groupe
python dump_context.py --groups scripts config utils
```

---

## 📁 Structure du projet

```
alternances-veille/
├── main_flow.py                    ← orchestrateur (étapes 1→6)
├── dump_context.py                 ← snapshot LLM
├── CONTEXT.md                      ← contexte projet pour LLM
├── requirements.txt
├── .env.example
├── config/
│   ├── tracks.yml                  ← 4 tracks : digital_marketing, finance, supply_chain, business_dev
│   ├── agent_backstory_*.md
│   └── prompt_llm_search_*.md
├── scripts/
│   ├── scraper_lba.py              ← étape 1
│   ├── test_search_agent.py        ← étape 2
│   ├── merge_llm_tracks.py         ← étape 3
│   ├── validator.py                ← étape 4
│   ├── merge_offers.py             ← étape 5
│   ├── generate_html_email.py      ← étape 6
│   └── scrape_hr_contacts_agent.py ← optionnel
├── utils/
│   ├── config_loader.py
│   └── deduplication.py
└── data/
    └── offres_historique.json      ← persistant (mémoire du pipeline)
```

---

## ⚙️ GitHub Actions

Le workflow `.github/workflows/veille-alternance.yml` est actuellement désactivé (`.disabled`).
Pour réactiver l'exécution automatique quotidienne :
```powershell
Rename-Item .github\workflows\veille-alternance.yml.disabled .github\workflows\veille-alternance.yml
git add .github/workflows/veille-alternance.yml
git commit -m "ci: réactivation workflow GitHub Actions"
git push
```
