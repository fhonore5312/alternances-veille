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
- **GitHub Pages V1** : https://fhonore5312.github.io/alternances-veille/
- **GitHub Pages V2** : https://fhonore5312.github.io/alternances-veille/v2/

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

```
Étape 1 — tools/lba_scraper.py      → Scrape l'API La Bonne Alternance (4 tracks)
Étape 2 — tools/llm_search_agent.py → Agent LLM CrewAI par track (digital_marketing + finance)
Étape 3 — tools/merge_offers.py     → Merge + déduplication + historique → offres_merged.json
Étape 4 — tools/validator.py        → Valide les offres → offres_*_validated.json
Étape 5 — tools/html_email.py       → HTML email + GitHub Pages docs/v2/ + envoi Gmail
```

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

```
alternances-veille-v2/
├── main.py                          ← point d'entrée racine
├── dump_context.py
├── list_structure.py
├── CONTEXT.md
├── config/                          ← config CrewAI (source de vérité)
│   ├── agents.yaml
│   ├── tasks.yaml
│   ├── tracks.yml
│   ├── agent_backstory_digitalmarketing.md
│   ├── agent_backstory_finance.md
│   ├── prompt_llm_search_digitalmarketing.md
│   └── prompt_llm_search_finance.md
├── data/
│   ├── offres_merged.json           ← input de html_email.py
│   ├── offres_historique.json       ← historique déduplication
│   └── hr_contacts.json             ← contacts RH (futur)
├── docs/
│   ├── index.html                   ← ⚠️ PAGE V1 — NE PAS MODIFIER dans V2
│   └── v2/
│       ├── index.html               ← page riche V2 (générée par html_email.py)
│       └── archives/                ← archives horodatées (30 jours)
└── src/
    └── alternances_veille/
        ├── __init__.py
        ├── main.py                  ← point d'entrée package
        ├── flow.py                  ← CrewAI Flow orchestration
        ├── crews/
        │   └── __init__.py
        └── tools/
            ├── __init__.py
            ├── llm_search_agent.py  ← VeilleSearchCrew (@CrewBase) + CLI --track --test
            ├── lba_scraper.py
            ├── merge_offers.py
            ├── validator.py
            └── html_email.py        ← CSS pixel-perfect V1, groupement par ville
```

> ⚠️ **RÈGLE GIT** : `docs/index.html` appartient à la V1 et ne doit JAMAIS être modifié
> par des commits V2. `html_email.py` n'écrit que dans `docs/v2/` et pousse uniquement
> `docs/v2/` vers `origin/main`.

---

## 🎨 Format HTML — RÈGLE ABSOLUE

⚠️ NE PAS MODIFIER le format de restitution HTML lors de corrections ou d'améliorations.
Le design de `tools/html_email.py` est validé et satisfaisant.
Toute modification doit être explicitement demandée par l'utilisateur.

### Caractéristiques du format actuel V2 (à préserver)
- CSS identique à la V1 (pixel-perfect) — `max-width: 940px`, gradient `#2c3e50 → #3498db`
- Offres groupées par **track** (avec couleur) puis par **ville** (`city-group`)
- Dans chaque ville, offres triées par **date décroissante**
- Offres affichées comme liste avec `border-bottom: 1px solid #f0f0f0` (pas de card)
- Badges : `badge-new` (vert), `badge-lba` (texte vert clair), `badge-llm` (texte violet clair)
- Contact RH : bloc `hr-contact` avec `border-left: 3px solid #3498db` — affiché **uniquement si contact trouvé**
- Stats globales : boxes individuelles (`flex:1`) — total, nouvelles, LBA, LLM, par ville
- Filtres JS : track / ville / statut avec `filter-chip` (border-radius: 14px)
- Bouton Postuler → couleur du track
- Publié sur **GitHub Pages** `docs/v2/` + archive horodatée + envoi Gmail

### Email minimal (compatible Gmail)
- Même stats/structure en CSS inline
- Tableau par track (total + nouvelles)
- CTA → lien GitHub Pages V2

---

## 🔧 Environnement technique

- **Python** 3.11+, Windows (PowerShell) + GitHub Actions (Ubuntu)
- **Package** : `src/alternances_veille/` — exécution via `python -m alternances_veille.tools.llm_search_agent`
- **Scheduling** : GitHub Actions (`.github/workflows/veille-alternance.yml` — actuellement `.disabled`)
- **Email** : Gmail SMTP (`GMAIL_USER`, `GMAIL_PASSWORD`, `RECIPIENT_EMAIL`)
- **Encoding** : UTF-8 forcé partout (`PYTHONUTF8=1`)
- **Variables** : `.env` (ne jamais committer — voir `.env.example`)
- **Git push docs/v2/** : toujours vers `origin/main` (GitHub Pages)

---

## 🚧 État au 14/03/2026

### ✅ Fonctionnel
- Pipeline complet V2 opérationnel — run du 14/03/2026 à 16:09 : **82 offres actives, 28 nouvelles**
- Scraper LBA : 73 offres / 4 tracks
- Agent LLM CrewAI : 9 offres / 2 tracks (digital_marketing + finance)
- merge_offers.py : déduplication + historique `offres_historique.json`
- validator.py : validation par track
- html_email.py V2 : page pixel-perfect V1 + groupement par ville + email Gmail envoyé ✅
- GitHub Pages V2 live : https://fhonore5312.github.io/alternances-veille/v2/
- Email reçu avec design mail V1 (stats + tableau tracks + CTA)

### 🐛 Bugs corrigés (14/03/2026)
- `docs/index.html` conflit Git récurrent entre V1 et V2 :
  **fix** : `html_email.py` ne git-add que `docs/v2/`, pousse vers `origin/main`
- V2 CSS divergeait de V1 (cards, badges blancs, container 1100px) :
  **fix** : réécriture complète avec CSS V1 pixel-perfect + groupement par ville

### 🔄 À faire (prochain thread)
- Réactiver GitHub Actions workflow (`.github/workflows/veille-alternance.yml`)
- Tester pipeline complet en GitHub Actions (Ubuntu)
- Développer scraper contacts RH (`data/hr_contacts.json`)
- Nettoyer les doublons dans `src/alternances_veille/config/`
- Configurer agent LLM pour tracks `supply_chain` et `business_dev` si besoin

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
9. **RÈGLE GIT** : ne jamais git-add `docs/index.html` dans les commits V2 — uniquement `docs/v2/`
