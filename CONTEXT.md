# CONTEXT.md — alternances-veille

> Fichier de contexte pour LLM (Perplexity, Claude...).
> À attacher en début de nouveau thread pour mise à niveau immédiate.
> Maintenir à jour à chaque évolution majeure du projet.

---

## 👤 Profil candidat

- **Étudiante** : Bachelor 3 — Rennes School of Business (campus Rennes et Paris)
- **Recherche** : Alternance multi-domaines — début **Septembre 2026** (flexible dès Juin 2026)
- **Durée contrat** : 12-24 mois (critère secondaire à aborder en entretien)
- **Villes** : Rennes = Paris (même priorité), puis Nantes — Rennes affiché en premier dans les résultats
- **GitHub Pages** : https://fhonore5312.github.io/alternances-veille/

---

## 🎯 Tracks de recherche

Le système couvre plusieurs domaines (tracks), chacun configuré dans `config/tracks.yml`.

### Track : digital_marketing
- **Domaine** : Marketing Digital (SEO, SEA/Paid Media, Social Media, Content, Analytics, CRM/Automation, E-commerce, Growth/Acquisition, UX/Design)
- **Couleur** : `#4F81BD`
- **Sources** : LBA + Agent LLM
- **Config** : `config/agent_backstory_digitalmarketing.md` + `config/prompt_llm_search_digitalmarketing.md`

### Track : finance
- **Domaine** : Finance / Audit / Contrôle de gestion (Comptabilité, Audit, Analyse financière, Trésorerie, Reporting, Consolidation)
- **Couleur** : `#27AE60`
- **Sources** : LBA + Agent LLM
- **Note** : Master 2 sans dérogation Bac+3 → EXCLURE ; Master 1 requis → status "incertain"
- **Config** : `config/agent_backstory_finance.md` + `config/prompt_llm_search_finance.md`

### Track : supply_chain *(LBA uniquement, pas d'agent LLM)*
- **Domaine** : Supply Chain & Achats (Logistique, Achats, Transport, Planification, Amélioration continue)
- **Couleur** : `#E67E22`

### Track : business_dev *(LBA uniquement, pas d'agent LLM)*
- **Domaine** : Business Development & Vente (Négociation, Développement commercial, Account Management, Retail, CRM)
- **Couleur** : `#9B59B6`

---

## 🏗️ Architecture du pipeline

Orchestré par `main_flow.py`, exécutable via GitHub Actions.

```
Étape 1 — scraper_lba.py         → Scrape l'API La Bonne Alternance (4 tracks)
Étape 2 — test_search_agent.py   → LLM agent par track (2 tracks : digitalmarketing + finance)
Étape 3 — merge_llm_tracks.py    → Fusionne les JSON LLM → data/offres_llm.json
Étape 4 — validator.py           → Valide les offres LBA + LLM → offres_*_validated.json
Étape 5 — merge_offers.py        → Merge + déduplication + historique → offres_merged.json
Étape 6 — generate_html_email.py → HTML email + GitHub Pages + envoi Gmail
```

### Tracks configurés (config/tracks.yml)

| Track          | LBA | LLM agent | Couleur   |
|----------------|-----|-----------|-----------|
| digital_marketing | ✅ | ✅     | `#4F81BD` |
| finance           | ✅ | ✅     | `#27AE60` |
| supply_chain      | ✅ | ❌     | `#E67E22` |
| business_dev      | ✅ | ❌     | `#9B59B6` |

### LLM model actuellement utilisé
`anthropic/claude-haiku-4-5-20251001` (hardcodé dans `main_flow.py`)

### Règles communes à tous les tracks LLM
- Ne PAS scraper linkedin.com — utiliser uniquement le snippet SerperDev pour LinkedIn
- Scraper : welcometothejungle.com, cadremploi.fr, sites carrières directs
- EXCLURE : CDI, CDD, Stage, offres expirées, début < Juin 2026, publication > 8 mois, écoles de formation, CFA internes
- Génère UNIQUEMENT le JSON (aucun texte avant/après)

---

## 📁 Structure des fichiers clés

```
alternances-veille/
├── main_flow.py
├── dump_context.py
├── CONTEXT.md
├── DUMP_CONTEXT_README.md
├── requirements.txt
├── .env.example
├── config/
│   ├── tracks.yml                              ← 4 tracks : digital_marketing, finance, supply_chain, business_dev
│   ├── prompt_llm_search_digitalmarketing.md
│   ├── prompt_llm_search_finance.md
│   ├── agent_backstory_digitalmarketing.md
│   └── agent_backstory_finance.md
├── scripts/
│   ├── scraper_lba.py
│   ├── test_search_agent.py                    ← repair JSON tronqué + normalize_offer()
│   ├── merge_llm_tracks.py                     ← repair JSON tronqué + normalize_offer()
│   ├── validator.py                            ← date_creation nullable + fix --quick (en attente)
│   ├── merge_offers.py
│   ├── generate_html_email.py
│   └── scrape_hr_contacts_agent.py             ← agent scraping contacts RH
├── utils/
│   ├── config_loader.py                        ← load_tracks() / get_track() depuis tracks.yml
│   └── deduplication.py
└── data/                                       ← fichiers générés (non versionnés)
    ├── offres_lba.json
    ├── offres_lba_validated.json
    ├── offres_llm.json
    ├── offres_llm_validated.json
    ├── offres_merged.json
    ├── offres_historique.json                  ← persistant (peut être versionné)
    ├── offres_agent_digitalmarketing.json
    ├── offres_agent_finance.json
    ├── hr_contacts.json
    └── hr_contacts_history.json
```

---

## 🎨 Format HTML — RÈGLE ABSOLUE

⚠️ NE PAS MODIFIER le format de restitution HTML lors de corrections ou d'améliorations.
Le design de `generate_html_email.py` est validé et satisfaisant.
Toute modification doit être explicitement demandée par l'utilisateur.

### Caractéristiques du format actuel (à préserver)
- Offres groupées par **track** avec couleur propre à chaque track (depuis `tracks.yml`)
- Dans chaque track, offres triées par **date décroissante** (`date_creation` DD/MM/YYYY ou `first_seen` YYYY-MM-DD)
- Badge **NEW** sur les offres à status "new"
- Label **source** visible : LBA ou LLM
- Stats globales en header : total offres, nouvelles, répartition par ville
- Bouton **Postuler →** avec lien direct vers l'offre
- Compétences affichées en badges
- Rendu optimisé Gmail (CSS inline)
- Publié sur **GitHub Pages** + envoyé en pièce jointe `.html` par Gmail

---

## 🔧 Environnement technique

- **Python** 3.11+, Windows (PowerShell) + GitHub Actions (Ubuntu)
- **Scheduling** : GitHub Actions (`.github/workflows/veille-alternance.yml` — actuellement `.disabled`)
- **Email** : Gmail SMTP (`GMAIL_USER`, `GMAIL_PASSWORD`, `RECIPIENT_EMAIL`)
- **Encoding** : UTF-8 forcé partout (`PYTHONUTF8=1`)
- **Dépendances** : voir `requirements.txt`
- **Variables** : `.env` (ne jamais committer — voir `.env.example`)

---

## 🚧 État au 06/03/2026

### ✅ Fonctionnel
- Pipeline complet (étapes 1→6) opérationnel en local
- HTML email généré et archivé dans `docs/archives/`
- GitHub Pages à jour avec `docs/index.html`
- Tracks `digital_marketing` (LBA+LLM) et `finance` (LBA+LLM) opérationnels
- Tracks `supply_chain` et `business_dev` opérationnels (LBA)
- `config/tracks.yml` centralisé — source unique des 4 tracks + couleurs
- `utils/config_loader.py` — chargement YAML partagé entre scripts
- `scripts/scrape_hr_contacts_agent.py` — scraping contacts RH opérationnel

### 🐛 Bugs corrigés (06/03/2026)
- JSON tronqué (token limit LLM) : réparation automatique dans `merge_llm_tracks.py` et `test_search_agent.py`
- `date_creation: null` rejeté par validator : normalisé → `first_seen` en `DD/MM/YYYY`
- `status: incertain` rejeté par validator : normalisé → `new`
- `--quick` du validator sans effet : fix en attente dans `validator.py`

### 🔄 À faire
- `validator.py` : fix `--quick` (merger avec `offres_lba_validated.json` pour récupérer les statuts précédents)
- `validator.py` : rendre `date_creation` nullable dans `REQUIRED_LLM_FIELDS`
- GitHub Actions workflow : réactiver (`.yml.disabled` → `.yml`)
- Tracks `supply_chain` et `business_dev` : configurer agent LLM (backstory + prompt)

---

## 💡 Consignes pour le LLM assistant

1. **Ne pas toucher au format HTML** sauf demande explicite
2. Toujours vérifier la compatibilité UTF-8 dans les modifications de scripts
3. Les chemins sont relatifs à `BASE_DIR` (racine du projet), pas à `SCRIPT_DIR`
4. `offres_merged.json` est le seul input de `generate_html_email.py`
5. En cas de fix, **proposer le diff ou les lignes modifiées uniquement** — pas réécrire tout le fichier sauf demande explicite
6. `config/tracks.yml` est la source de vérité pour les tracks, couleurs et mots-clés
