# CONTEXT.md — alternances-veille

> Fichier de contexte pour LLM (Perplexity, Claude...).
> À attacher en début de nouveau thread pour mise à niveau immédiate.
> Maintenir à jour à chaque évolution majeure du projet.

---

## 👤 Profil candidat

- **Étudiante** : Bachelor 3 — Rennes School of Business (campus Rennes et Paris)
- **Recherche** : Alternance multi-domaines — début **Septembre 2026** (flexible dès Juin 2026)
- **Durée contrat** : 12-24 mois (critère secondaire)
- **Villes** : Rennes ≥ Paris (même priorité), puis Nantes
- **GitHub Pages** : https://fhonore5312.github.io/alternances-veille/

---

## 🎯 Tracks de recherche

Configurés dans `config/tracks.yml` — source de vérité.

| Track | Sources | Couleur | Notes |
|---|---|---|---|
| `digital_marketing` | LBA + LLM | `#4F81BD` | SEO, SEA, Social, Content, Analytics, CRM, Growth |
| `finance` | LBA + LLM | `#27AE60` | Audit, Comptabilité, Contrôle gestion — BAC+5 uniquement |
| `supply_chain` | LBA seul | `#E67E22` | Logistique, Achats, Transport, Planification |
| `business_dev` | LBA seul | `#9B59B6` | Commerce, Négociation, Account Management |

**Règles LLM communes :**
- Ne PAS scraper linkedin.com — snippet SerperDev uniquement
- Scraper : welcometothejungle.com, cadremploi.fr, sites carrières directs
- EXCLURE : CDI, CDD, Stage, offres expirées, début < Juin 2026, publication > 8 mois, écoles/CFA
- Sortie JSON pur (aucun texte autour)

---

## Architecture V2 CrewAI Flow

### Pipeline flow.py
| Étape | Méthode flow | Tool appelé | Sortie |
|---|---|---|---|
| 1a | `scrape_lba` | `lba_scraper.run_lba_scraper` | `data/offres_lba.json` |
| 1b | `run_llm_agents` (parallèle) | `alternance_search_agent.run_llm_search_agent(track)` | `data/offres_agent_{track}.json` |
| 2 | `validate` | `validator.run_validator(quick_mode)` | `offres_lba_validated.json` / `offres_llm_validated.json` |
| 3 | `merge` | `merge_offers.run_merge_offers` | `data/offres_merged.json` |
| 4 | `generate_email` | `html_email.run_html_email` | `docs/v2/index.html` + email |
| 5 | `summary` | log console | — |

### Structure des crews
src/alternances_veille/
├── flow.py # Orchestrateur CrewAI Flow PRINCIPAL
├── main.py # Entry point (crewai flow run)
├── crews/
│ ├── search_crew/ # Crew recherche offres LLM
│ │ ├── search_crew.py # @CrewBase — 2 tracks : digitalmarketing, finance
│ │ └── config/
│ │ ├── agents.yaml
│ │ └── tasks.yaml
│ └── hr_contacts_crew/ # Crew recherche contacts RH
│ ├── hr_contacts_crew.py # @CrewBase — 1 agent / 1 offre
│ └── config/
│ ├── agents.yaml
│ └── tasks.yaml
└── tools/
├── alternance_search_agent.py # Interface run_llm_search_agent(track)
├── hr_contacts_agent.py # Interface run_hr_contacts_agent(track)
├── lba_scraper.py
├── validator.py
├── merge_offers.py
└── html_email.py


### Config racine
- `config/tracks.yml` — source de vérité tracks, couleurs, ROME, keywords

### Pipeline parallèle (flow.py)

```
scrape_lba()   ─@start()─┐
                          ├─ and_() → validate → merge → generate_email → summary
run_llm_agents()─@start()─┘
```

| Étape | Méthode flow | Tool appelé | Sortie |
|---|---|---|---|
| 1a | `scrape_lba` | `lba_scraper.run_lba_scraper()` | `data/offres_lba.json` |
| 1b | `run_llm_agents` | `llm_search_agent.run_llm_search_agent(track)` | `data/offres_agent_<track>.json` |
| 2 | `validate` | `validator.run_validator(quick_mode)` | `offres_lba_validated.json` + `offres_llm_validated.json` |
| 3 | `merge` | `merge_offers.run_merge_offers()` | `data/offres_merged.json` |
| 4 | `generate_email` | `html_email.run_html_email()` | `docs/v2/index.html` + email |
| 5 | `summary` | — | Log résumé console |

### Tracks LLM
`TRACKS_LLM = ["digital_marketing", "finance"]` (défini dans flow.py)

### LLM model
`anthropic/claude-haiku-4-5-20251001` — configuré dans `config/agents.yaml`

---

## 📁 Structure des fichiers (V2 — état 15/03/2026)

```
alternances-veille-v2/
├── main.py                         ← Entry point racine (appelle flow.kickoff())
├── list_project.py                 ← Listing fichiers + détection suspects
├── dump_context.py                 ← Générateur CONTEXT_DUMP_*.txt
├── CONTEXT.md                      ← Ce fichier
├── requirements.txt
├── .env / .env.example
│
├── config/
│   ├── tracks.yml                  ← 4 tracks + ROME + couleurs + keywords
│   ├── agents.yaml                 ← Config agents CrewAI (LLM model, backstory...)
│   ├── tasks.yaml                  ← Config tasks CrewAI (prompts, outputs...)
│   └── [prompt_*.md + backstory_*.md si externalisés]
│
├── src/
│   └── alternances_veille/
│       ├── __init__.py
│       ├── flow.py                 ← Orchestrateur CrewAI Flow (PRINCIPAL)
│       ├── main.py                 ← crewai flow run entry point
│       ├── crews/
│       │   └── __init__.py         ← [Crews CrewAI si nécessaire]
│       └── tools/
│           ├── __init__.py
│           ├── lba_scraper.py      ← Scraper LBA V2 (4 tracks, 3 villes)
│           ├── alternance_search_agent.py  ← Agent LLM search (Perplexity/Serper)
│           ├── validator.py        ← Validation HTTP LBA + structure LLM
│           ├── merge_offers.py     ← Merge + déduplication + historique
│           └── html_email.py       ← HTML email + GitHub Pages + Gmail
│
├── data/                           ← Générés (non versionnés sauf historiques)
│   ├── offres_lba.json             ← Sortie lba_scraper (étape 1a)
│   ├── lba_history.json            ← Historique léger LBA {id: {first_seen...}}
│   ├── offres_agent_digital_marketing.json  ← Sortie agent LLM (étape 1b)
│   ├── offres_agent_finance.json
│   ├── offres_lba_validated.json   ← Validation LBA (étape 2)
│   ├── offres_llm_validated.json   ← Validation LLM (étape 2)
│   ├── offres_merged.json          ← Merge final (étape 3) — input HTML
│   └── offres_historique.json      ← Historique complet V2 {meta, offres:[]}
│
└── docs/
    └── v2/
        ├── index.html              ← GitHub Pages (dernière veille) ← html_email écrit ici
        └── archives/
            └── veille_YYYY-MM-DD_HH-MM.html
```

---

## 🔑 Points clés architecture V2

### lba_scraper.py
- `lba_history.json` : historique léger LBA (dict `{id: {first_seen, last_seen}}`)
- `offres_historique.json` : géré par `merge_offers.py` uniquement (format liste V2)
- Exclusions : 14 noms + 18 descriptions (5 ajouts vs V1 : rocket school, assoc imc, bscc...)
- `fetch_lba_offers` : cumule 3 sources (`jobs` + `results` + `partnerJobs`)
- Filtre BAC+5 actif uniquement pour track `finance`
- ⚠️ Pas de `\n` dans f-string avec emoji (SyntaxError Windows)

### alternance_search_agent.py 
- Interface : `run_llm_search_agent(track: str) -> int` (retourne nb offres)
- Lit config depuis `config/agents.yaml` + `config/tasks.yaml`
- Écrit `data/offres_agent_<track>.json`

### validator.py
- Interface : `run_validator(quick_mode=False) -> (lba_count, llm_count)`
- `--quick` : skip offres validées dans les 7 derniers jours ✅

### merge_offers.py
- Interface : `run_merge_offers() -> (merged_count, nouvelles_count)`
- Sources : `offres_lba_validated.json` + `offres_llm_validated.json`
- Met à jour `offres_historique.json` (format V2)

### html_email.py
- Interface : `run_html_email()`
- Écrit dans `docs/v2/index.html` + `docs/v2/archives/`
- Envoie par Gmail SMTP

---

## 🎨 Format HTML — RÈGLE ABSOLUE

⚠️ Ne pas modifier `html_email.py` sauf demande explicite.

- Offres groupées par track avec couleur (`tracks.yml`)
- Tri par date décroissante (`date_creation` ou `first_seen`)
- Badge NEW, label source LBA/LLM, bouton Postuler
- Stats header, compétences en badges, CSS inline Gmail
- Publié GitHub Pages + envoyé en `.html` pièce jointe

---

## 🔧 Environnement technique

- **Python** 3.11+, Windows PowerShell + GitHub Actions (Ubuntu)
- **Package** : `src/alternances_veille/` (installable via `pip install -e .`)
- **Scheduling** : `.github/workflows/veille-alternance.yml` (`.disabled` — inactif)
- **Email** : Gmail SMTP (`GMAIL_USER`, `GMAIL_PASSWORD`, `RECIPIENT_EMAIL`)
- **Encoding** : UTF-8 forcé partout (`PYTHONUTF8=1`)
- **Run** : `crewai flow run` ou `python main.py`

---

## 🚧 État au 15/03/2026

### ✅ Fonctionnel
- `lba_scraper.py` V2 : exclusions complètes, lba_history.json, syntaxe corrigée
- `validator.py` V2 : --quick opérationnel, retourne (lba_count, llm_count)
- `merge_offers.py` V2 : format historique V2 listes
- `flow.py` : agents LLM intégrés (run_llm_agents en @start() parallèle)
- Historiques V1+V2 mergés → offres_historique.json (base nettoyée)

### 🐛 Bugs corrigés (15/03/2026)
- `lba_scraper.py` : SyntaxError \n dans f-string avec emoji → prints séparés
- `lba_scraper.py` : écrasement offres_historique.json V2 → lba_history.json séparé
- `lba_scraper.py` : 5 exclusions écoles manquantes vs V1
- `flow.py` : run_validator() doublon supprimé
- `flow.py` : agents LLM intégrés en parallèle via and_()

### 🔄 À faire (prochain sprint — contacts RH)
- Implémenter `tools/hr_contacts_agent.py`
- L'intégrer dans flow.py après l'étape merge (étape optionnelle)
- Réactiver GitHub Actions (workflow `.disabled` → `.yml`)
- Vérifier `llm_search_agent.run_llm_search_agent(track)` retourne bien un int
- Vérifier config GitHub Pages : doit servir `docs/v2/` ou `docs/`

---

## 💡 Consignes LLM assistant

1. **Architecture = CrewAI Flow** — pas de main_flow.py, le seul orchestrateur est `flow.py`
2. **Ne pas toucher à `html_email.py`** sauf demande explicite
3. UTF-8 : toujours vérifier la compatibilité (PYTHONUTF8=1)
4. Chemins relatifs à `BASE_DIR` (racine repo), pas à `SCRIPT_DIR`
5. `offres_merged.json` = seul input de `html_email.run_html_email()`
6. `lba_history.json` ≠ `offres_historique.json` — deux fichiers distincts
7. Proposer diff ou lignes modifiées — pas réécrire tout le fichier sauf demande
8. `config/tracks.yml` = source de vérité pour tracks, couleurs, ROME, keywords
9. Pas de `\n` à l'intérieur d'une f-string avec emoji (SyntaxError Windows)

---

## 🗺️ Roadmap — Évolutions prévues (mars 2026)

### Sprint 1 — WhatsApp notifier (CallMeBot)
- Nouveau fichier : `tools/notifier.py`
- Fonction : `notify_nouvelles_offres(nouvelles: int, top_offres: list)`
- Nouvelle étape dans flow.py : `@listen(generate_email) def notify(self)`
- Silencieux si `nouvelles_count == 0`
- Variables .env à ajouter : `CALLMEBOT_PHONE`, `CALLMEBOT_APIKEY`
- API : https://api.callmebot.com/whatsapp.php

### Sprint 2 — JobTeaser scraper
- Nouveau fichier : `tools/jobteaser_scraper.py`
- Interface : `run_jobteaser_scraper() -> int`
- Scraping HTML (pas d'API publique) — requests + BeautifulSoup
- Intégration : 2e `@start()` parallèle à `scrape_lba`
- `@listen(and_(scrape_lba, scrape_jobteaser))` sur `validate`
- Nouveau state : `jobteaser_count`, `jobteaser_ok`

### Sprint 3 — Scoring Crew
- Nouveau crew : `src/crews/scoring_crew/`
- Ne tourne que sur les nouvelles offres (`first_seen == today`)
- Score 0-10 + justification → enrichit `offres_merged.json`
- Critères : profil entreprise, compétences RSB DM/Finance, localisation, date début
- Intégration : entre `merge` et `find_hr_contacts` dans flow.py

