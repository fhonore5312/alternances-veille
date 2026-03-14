# CONTEXT.md — alternances-veille-v2

> Fichier de contexte pour LLM (Perplexity, Claude...).
> À attacher en début de nouveau thread pour mise à niveau immédiate.
> Maintenir à jour à chaque évolution majeure du projet.

---

## 👤 Profil candidat

- **Étudiante** : Bachelor 3 — Rennes School of Business (campus Rennes et Paris)
- **Recherche** : Alternance multi-domaines — début **Septembre 2026** (flexible dès Juin 2026)
- **Durée contrat** : 12-24 mois (critère secondaire à aborder en entretien)
- **Villes** : Rennes = Paris (même priorité), puis Nantes — Rennes affiché en premier
- **GitHub Pages** : https://fhonore5312.github.io/alternances-veille/

---

## 🎯 Tracks de recherche

Configurés dans `config/tracks.yml`, `config/agents.yaml`, `config/tasks.yaml`.

### Track : digital_marketing
- **Domaine** : Marketing Digital (SEO, SEA/Paid Media, Social Media, Content, Analytics, CRM, E-commerce, Growth, UX)
- **Couleur** : `#4F81BD`
- **Sources** : LBA + Agent LLM (CrewAI)

### Track : finance
- **Domaine** : Finance / Audit / Contrôle de gestion (Comptabilité, Audit, Analyse financière, Trésorerie, Reporting, Consolidation)
- **Couleur** : `#27AE60`
- **Sources** : LBA + Agent LLM (CrewAI)
- **Note** : Master 2 sans dérogation Bac+3 → EXCLURE ; Master 1 requis → status "incertain"

### Track : supply_chain *(LBA uniquement)*
- **Domaine** : Supply Chain & Achats (Logistique, Achats, Transport, Planification, Amélioration continue)
- **Couleur** : `#E67E22`

### Track : business_dev *(LBA uniquement)*
- **Domaine** : Business Development & Vente (Négociation, Développement commercial, Account Management, Retail, CRM)
- **Couleur** : `#9B59B6`

---

## 🏗️ Architecture du pipeline

Orchestré par `src/alternances_veille/flow.py` (CrewAI Flow), point d'entrée `main.py`.

Étape 1 — tools/lba_scraper.py → Scrape l'API La Bonne Alternance (4 tracks)
Étape 2 — tools/llm_search_agent.py → Agent LLM CrewAI par track (digitalmarketing + finance)
Étape 3 — tools/merge_offers.py → Merge + déduplication + historique → offres_merged.json
Étape 4 — tools/validator.py → Valide les offres → offres_*_validated.json
Étape 5 — tools/html_email.py → HTML email + GitHub Pages + envoi Gmail

text

### Tracks configurés

| Track             | LBA | LLM agent | Couleur   |
|-------------------|-----|-----------|-----------|
| digital_marketing | ✅  | ✅        | `#4F81BD` |
| finance           | ✅  | ✅        | `#27AE60` |
| supply_chain      | ✅  | ❌        | `#E67E22` |
| business_dev      | ✅  | ❌        | `#9B59B6` |

### LLM model utilisé
`anthropic/claude-haiku-4-5-20251001` — configuré dans `tools/llm_search_agent.py`

### Architecture CrewAI (@CrewBase)
- `config/agents.yaml` — définition des agents par track
- `config/tasks.yaml` — tâches avec description + expected_output
- `config/agent_backstory_*.md` — backstories des agents
- `config/prompt_llm_search_*.md` — prompts de recherche par track
- **RÈGLE ABSOLUE** : seul `{date_today}` est un placeholder valide dans `tasks.yaml`.
  Tous les autres `{...}` doivent être écrits en texte libre sans accolades —
  sinon CrewAI lève `Template variable not found in inputs dictionary`.
- `max_iter=15` dans l'instanciation de chaque agent
- Scraper uniquement les URLs d'offres individuelles (`/jobs/`, `/offre/`, slug entreprise)
- Ne JAMAIS scraper : `/pages/`, `liste_offres`, `/q-`, `/Emplois-`, `linkedin.com`, `indeed.fr`
- Maximum 4 scrapes par run (budget contexte LLM)

### Règles communes à tous les tracks LLM
- EXCLURE : CDI, CDD, Stage, offres expirées, début < Juin 2026, publication > 8 mois
- EXCLURE : toute école, CFA, organisme de formation (mydigitalschool, studi, iscod, alticome...)
- Génère UNIQUEMENT le JSON — aucun texte ni balise markdown avant/après

---

## 📁 Structure des fichiers clés

alternances-veille-v2/
├── main.py ← point d'entrée racine
├── dump_context.py
├── list_structure.py
├── CONTEXT.md
├── config/ ← config CrewAI (source de vérité)
│ ├── agents.yaml
│ ├── tasks.yaml
│ ├── tracks.yml
│ ├── agent_backstory_digitalmarketing.md
│ ├── agent_backstory_finance.md
│ ├── prompt_llm_search_digitalmarketing.md
│ └── prompt_llm_search_finance.md
└── src/
└── alternances_veille/
├── init.py
├── main.py ← point d'entrée package
├── flow.py ← CrewAI Flow orchestration
├── config/
│ └── init.py
├── crews/
│ └── init.py
└── tools/
├── init.py
├── llm_search_agent.py ← VeilleSearchCrew (@CrewBase) + CLI --track --test
├── lba_scraper.py
├── merge_offers.py
├── validator.py
└── html_email.py

text

> ⚠️ Les fichiers `src/alternances_veille/config/agent_backstory_digitalmarketing.md`
> et `prompt_llm_search_digitalmarketing.md` sont des doublons de `config/`.
> La source de vérité est `config/` (racine).

---

## 🎨 Format HTML — RÈGLE ABSOLUE

⚠️ NE PAS MODIFIER le format de restitution HTML lors de corrections ou d'améliorations.
Le design de `tools/html_email.py` est validé et satisfaisant.
Toute modification doit être explicitement demandée par l'utilisateur.

### Caractéristiques du format actuel (à préserver)
- Offres groupées par **track** avec couleur propre à chaque track
- Dans chaque track, offres triées par **date décroissante** (`date_creation` DD/MM/YYYY ou `first_seen` YYYY-MM-DD)
- Badge **NEW** sur les offres à status "new"
- Label **source** visible : LBA ou LLM
- Stats globales en header : total offres, nouvelles, répartition par ville
- Bouton **Postuler →** avec lien direct
- Compétences affichées en badges
- Rendu optimisé Gmail (CSS inline)
- Publié sur **GitHub Pages** + envoyé en pièce jointe `.html` par Gmail

---

## 🔧 Environnement technique

- **Python** 3.11+, Windows (PowerShell) + GitHub Actions (Ubuntu)
- **Package** : `src/alternances_veille/` — exécution via `python -m alternances_veille.tools.llm_search_agent`
- **Scheduling** : GitHub Actions (`.github/workflows/veille-alternance.yml` — actuellement `.disabled`)
- **Email** : Gmail SMTP (`GMAIL_USER`, `GMAIL_PASSWORD`, `RECIPIENT_EMAIL`)
- **Encoding** : UTF-8 forcé partout (`PYTHONUTF8=1`)
- **Variables** : `.env` (ne jamais committer — voir `.env.example`)

---

## 🚧 État au 13/03/2026

### ✅ Fonctionnel
- Agent LLM CrewAI (@CrewBase) opérationnel — track `digitalmarketing`
- 5 offres / run obtenues en mode test (`--test`)
- `data/offres_agent_digitalmarketing_test.json` généré correctement
- Crew Execution Completed sans échec après corrections `tasks.yaml`
- Scraper LBA opérationnel (`tools/lba_scraper.py`)

### 🐛 Bugs corrigés
- `{code_postal}` et autres variables dans `expected_output` → `Template variable not found` :
  **fix** : supprimer tous les `{...}` sauf `{date_today}` dans `tasks.yaml`
- Agent scrapait des pages catégorie WTTJ (`/pages/`) → overflow contexte → `Invalid response from LLM` :
  **fix** : règle explicite dans `tasks.yaml` — scraper uniquement les URLs `/jobs/` individuelles, max 4 scrapes
- `Invalid response from LLM call - None or empty` mid-run (Haiku sous charge) :
  comportement normal géré par CrewAI (retry interne), non bloquant

### 🔄 À faire
- Tester et valider le track `finance` (agent + output JSON)
- Implémenter `flow.py` (CrewAI Flow) pour orchestrer le pipeline complet
- Connecter tous les `tools/` dans le flow
- Réactiver GitHub Actions workflow
- Nettoyer les doublons dans `src/alternances_veille/config/`
- Configurer agent LLM pour tracks `supply_chain` et `business_dev`

---

## 💡 Consignes pour le LLM assistant

1. **Ne pas toucher au format HTML** sauf demande explicite
2. Toujours vérifier la compatibilité UTF-8 dans les modifications de scripts
3. Les chemins sont relatifs à la racine `alternances-veille-v2/`
4. `offres_merged.json` est le seul input de `tools/html_email.py`
5. En cas de fix, **proposer le diff ou les lignes modifiées uniquement** — pas réécrire tout le fichier sauf demande
6. Dans `tasks.yaml` : **seul `{date_today}` est un placeholder valide** — tout autre `{...}` cause une erreur CrewAI
7. Le module s'exécute via `python -m alternances_veille.tools.llm_search_agent` depuis `src/`
8. La config CrewAI est dans `config/` (racine), pas dans `src/alternances_veille/config/`