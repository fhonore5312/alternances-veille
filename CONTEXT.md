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

## 🏗️ Architecture V2 — CrewAI Flow

### Pipeline parallèle (flow.py)

```
scrape_lba()     ─@start()─┐
                            ├─ and_() → validate → merge → find_hr_contacts → generate_email → summary
run_llm_agents() ─@start()─┘
```

| Étape | Méthode flow | Tool appelé | Sortie |
|---|---|---|---|
| 1a | `scrape_lba` | `lba_scraper.run_lba_scraper()` | `data/offres_lba.json` |
| 1b | `run_llm_agents` | `alternance_search_agent.run_alternance_search_agent(track)` | `data/offres_agent_<track>.json` |
| 2 | `validate` | `validator.run_validator(quick_mode)` | `offres_lba_validated.json` + `offres_llm_validated.json` |
| 3 | `merge` | `merge_offers.run_merge_offers()` | `data/offres_merged.json` |
| 3b | `find_hr_contacts` | `hr_contacts_agent.run_hr_contacts_agent(track)` | `data/hr_contacts.json` |
| 4 | `generate_email` | `html_email.run_html_email()` | `docs/v2/index.html` + email |
| 5 | `summary` | — | Log résumé console |

**Tracks LLM** : `TRACKS_LLM = ["digital_marketing", "finance"]` (défini dans flow.py)
**Tracks RH** : `HR_TRACKS = ["digital_marketing", "finance"]` (défini dans find_hr_contacts)
**LLM model** : `anthropic/claude-haiku-4-5-20251001`

---

## 📁 Structure des fichiers (V2 — état 20/03/2026)

```
alternances-veille-v2/
├── list_project.py                 ← Listing fichiers + détection suspects
├── dump_context.py                 ← Générateur CONTEXT_DUMP_*.txt
├── CONTEXT.md                      ← Ce fichier
├── pyproject.toml                  ← pip install -e . (src layout)
├── requirements.txt
├── .env / .env.example
│
├── config/
│   └── tracks.yml                  ← 4 tracks + ROME + couleurs + keywords
│
├── src/
│   └── alternances_veille/
│       ├── __init__.py
│       ├── flow.py                 ← Orchestrateur CrewAI Flow (PRINCIPAL)
│       ├── main.py                 ← crewai flow run entry point
│       ├── crews/
│       │   ├── __init__.py
│       │   ├── search_crew/        ← Crew recherche offres LLM (DM + Finance)
│       │   │   ├── __init__.py
│       │   │   ├── search_crew.py
│       │   │   └── config/
│       │   │       ├── agents.yaml
│       │   │       └── tasks.yaml
│       │   └── hr_contacts_crew/   ← Crew recherche contacts RH
│       │       ├── __init__.py
│       │       ├── hr_contacts_crew.py
│       │       └── config/
│       │           ├── agents.yaml
│       │           └── tasks.yaml
│       └── tools/
│           ├── __init__.py
│           ├── lba_scraper.py
│           ├── alternance_search_agent.py
│           ├── hr_contacts_agent.py
│           ├── validator.py
│           ├── merge_offers.py
│           └── html_email.py
│
├── data/                           ← Générés (non versionnés sauf historiques)
│   ├── offres_lba.json
│   ├── lba_history.json            ← Historique léger LBA
│   ├── offres_agent_digital_marketing.json
│   ├── offres_agent_finance.json
│   ├── offres_lba_validated.json
│   ├── offres_llm_validated.json
│   ├── offres_merged.json
│   ├── offres_historique.json      ← Historique complet V2 — NE PAS SUPPRIMER
│   ├── hr_contacts.json            ← Contacts RH (non versionné — données sensibles)
│   └── hr_contacts_history.json    ← Historique contacts RH (non versionné)
│
└── docs/
    └── v2/
        ├── index.html              ← GitHub Pages (dernière veille)
        └── archives/               ← Ignoré par .gitignore
            └── veille_YYYY-MM-DD_HH-MM.html
```

---

## 🔑 Points clés architecture V2

### lba_scraper.py
- `lba_history.json` : historique léger LBA (dict `{id: {first_seen, last_seen}}`)
- `offres_historique.json` : géré par `merge_offers.py` uniquement (format liste V2)
- Exclusions : 14 noms + 18 descriptions (rocket school, assoc imc, bscc, ifcv...)
- `fetch_lba_offers` : cumule 3 sources (`jobs` + `results` + `partnerJobs`)
- Filtre BAC+5 actif uniquement pour track `finance`
- ⚠️ Pas de `\n` dans f-string avec emoji (SyntaxError Windows)

### alternance_search_agent.py
- Interface : `run_alternance_search_agent(track: str) -> str` (retourne chemin fichier)
- Écrit `data/offres_agent_<track>.json`

### validator.py
- Interface : `run_validator(quick_mode=False) -> (lba_count, llm_count)`
- `--quick` : skip offres validées dans les 7 derniers jours

### merge_offers.py
- Interface : `run_merge_offers() -> (merged_count, nouvelles_count)`
- Sources : `offres_lba_validated.json` + `offres_llm_validated.json`
- Étape 6b : **dédup sémantique** par `(entreprise + titre + track)` — conserve ville prioritaire (Rennes > Nantes > Paris)
- Met à jour `offres_historique.json` (format V2)

### hr_contacts_agent.py
- Interface : `run_hr_contacts_agent(track: str | list[str] | None = None, flush=False, flush_history=False) -> int`
- `track=None` → défaut `["digital_marketing", "finance"]`
- `track="finance"` → rétrocompat str
- `track=["digital_marketing", "finance"]` → liste directe
- Historique par entreprise dans `hr_contacts_history.json` (évite les re-requêtes)
- KNOWN_CAREERS : ~45 entreprises hardcodées (0 appel LLM)

### html_email.py
- Interface : `run_html_email()`
- Écrit dans `docs/v2/index.html` + `docs/v2/archives/`
- Envoie par Gmail SMTP
- ⚠️ Ne pas modifier sauf demande explicite

---

## 🎨 Format HTML — RÈGLE ABSOLUE

⚠️ Ne pas modifier `html_email.py` sauf demande explicite.

- Offres groupées par track avec couleur (`tracks.yml`)
- Tri par date décroissante (`date_creation` ou `first_seen`)
- Badge NEW, label source LBA/LLM, bouton Postuler, contacts RH inline
- Stats header, compétences en badges, CSS inline Gmail
- Publié GitHub Pages + envoyé en `.html` pièce jointe

---

## 🔧 Environnement technique

- **Python** 3.12, Windows PowerShell + GitHub Actions (Ubuntu)
- **Package** : `src/alternances_veille/` — installé via `pip install -e .` (pyproject.toml)
- **Scheduling** : `.github/workflows/veille-alternance.yml.disabled` — inactif
- **Email** : Gmail SMTP (`GMAIL_USER`, `GMAIL_PASSWORD`, `RECIPIENT_EMAIL`)
- **Encoding** : UTF-8 forcé partout (`PYTHONUTF8=1`)
- **Run** : `crewai flow run` ou `python -m alternances_veille.main`

---

## 🚧 État au 20/03/2026

### ✅ Fonctionnel
- `lba_scraper.py` V2 : exclusions complètes, lba_history.json, syntaxe corrigée
- `alternance_search_agent.py` : search_crew opérationnel (DM + Finance)
- `validator.py` V2 : --quick opérationnel, retourne (lba_count, llm_count)
- `merge_offers.py` V2 : dédup sémantique entreprise+titre+track ajoutée
- `hr_contacts_agent.py` V2 : opérationnel, tracks DM+Finance, historique, KNOWN_CAREERS
- `flow.py` : pipeline complet parallèle, find_hr_contacts intégré (non bloquant)
- `pip install -e .` : pyproject.toml créé, package installable
- Pipeline testé et validé — 91 offres, 23 nouvelles (run 20/03/2026)

### 🐛 Bugs corrigés (20/03/2026)
- `hr_contacts_agent.py` : signature track str|list|None, normalisation interne
- `merge_offers.py` : doublons sémantiques La Poste × 10 villes → 1 offre conservée
- `flow.py` : paramètre `track=` corrigé en `track=HR_TRACKS` (list)
- `pyproject.toml` : encodage UTF-8 sans BOM, backend setuptools.build_meta

### 🔄 À faire
- Réactiver GitHub Actions (`.disabled` → `.yml`)
- Sprint 1 : notifier WhatsApp (CallMeBot) — `tools/notifier.py`
- Sprint 2 : JobTeaser scraper — `tools/jobteaser_scraper.py`
- Sprint 3 : Scoring Crew — `src/crews/scoring_crew/`

---

## 💡 Consignes LLM assistant

1. **Architecture = CrewAI Flow** — seul orchestrateur : `flow.py`
2. **Ne pas toucher à `html_email.py`** sauf demande explicite
3. UTF-8 : toujours vérifier la compatibilité (`PYTHONUTF8=1`)
4. Chemins relatifs à `BASE_DIR` (racine repo), pas à `SCRIPT_DIR`
5. `offres_merged.json` = seul input de `html_email.run_html_email()`
6. `lba_history.json` ≠ `offres_historique.json` — deux fichiers distincts
7. Proposer diff ou lignes modifiées — pas réécrire tout le fichier sauf demande
8. `config/tracks.yml` = source de vérité pour tracks, couleurs, ROME, keywords
9. Pas de `\n` à l'intérieur d'une f-string avec emoji (SyntaxError Windows)
10. `run_hr_contacts_agent(track=...)` — paramètre `track`, pas `tracks`

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
- Intégration : 3e `@start()` parallèle à `scrape_lba` et `run_llm_agents`
- `@listen(and_(scrape_lba, run_llm_agents, scrape_jobteaser))` sur `validate`
- Nouveau state : `jobteaser_count`, `jobteaser_ok`

### Sprint 3 — Scoring Crew
- Nouveau crew : `src/crews/scoring_crew/`
- Ne tourne que sur les nouvelles offres (`first_seen == today`)
- Score 0-10 + justification → enrichit `offres_merged.json`
- Critères : profil entreprise, compétences RSB DM/Finance, localisation, date début
- Intégration : entre `merge` et `find_hr_contacts` dans flow.py
