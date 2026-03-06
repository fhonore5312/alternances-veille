#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import argparse
from datetime import date, datetime
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

TRACK_LABELS = {
    "digitalmarketing": "Marketing Digital",
    "finance":          "Finance, Audit et Contrôle de gestion",
    "supplychain":      "Supply Chain et Achats",
    "businessdev":      "Business Development et Vente",
}


def repair_truncated_json(raw: str):
    """Tente de réparer un JSON tronqué (coupure sur token limit LLM)."""
    for closing in ["
  ]
}", "
]}"]:
        try:
            data = json.loads(raw.rstrip() + closing)
            print("[repair] JSON tronqué réparé automatiquement")
            return data
        except json.JSONDecodeError:
            continue
    return None


def normalize_offer(offer: dict, today_str: str) -> dict:
    """Normalise les champs pour passer le validator sans avertissements."""
    # date_creation null -> first_seen en DD/MM/YYYY
    if offer.get("date_creation") is None:
        raw_date = offer.get("first_seen") or today_str
        try:
            offer["date_creation"] = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            offer["date_creation"] = raw_date

    # status : incertain/None -> new
    if offer.get("status") not in ("new", "active"):
        offer["status"] = "new"

    return offer


def clean_llm_output_file(filepath: str):
    """
    Nettoie et répare le fichier JSON généré par le LLM :
    - Supprime le texte parasite avant/après le JSON
    - Supprime les balises ```json ... ```
    - Répare les JSON tronqués (token limit)
    - Normalise date_creation null -> first_seen (DD/MM/YYYY)
    - Normalise status incertain -> new
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    today_str = str(date.today())

    # Etape 1 : extraire le JSON brut
    cleaned = None
    if raw.startswith("{"):
        cleaned = raw
    else:
        m = re.search(r"```json\s*([\s\S]+?)\s*```", raw)
        if m:
            cleaned = m.group(1).strip()
            print(f"[clean] Balises ```json``` supprimées dans {filepath}")
        else:
            m = re.search(r"(\{[\s\S]+\})", raw)
            if m:
                cleaned = m.group(1).strip()
                print(f"[clean] Texte parasite supprimé dans {filepath}")

    if cleaned is None:
        print(f"[warn] Impossible de nettoyer {filepath} — vérifier manuellement")
        return

    # Etape 2 : parser (avec réparation si tronqué)
    data = None
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[warn] JSON invalide dans {filepath} : {e}")
        data = repair_truncated_json(cleaned)
        if data is None:
            print(f"[ERROR] Impossible de réparer {filepath} — fichier non sauvegardé")
            return

    # Etape 3 : normaliser les offres
    fixed = 0
    for offer in data.get("offres", []):
        before = (offer.get("date_creation"), offer.get("status"))
        normalize_offer(offer, today_str)
        if (offer.get("date_creation"), offer.get("status")) != before:
            fixed += 1
    if fixed:
        print(f"[normalize] {fixed} offre(s) normalisée(s) (date_creation / status)")

    # Etape 4 : réécrire le fichier proprement
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[ok] {filepath} sauvegardé ({len(data.get('offres', []))} offres)")


def test_llm_search(llm_name: str, track: str = "digitalmarketing", test_mode: bool = False):

    search_tool = SerperDevTool(n_results=3)
    scrape_tool = ScrapeWebsiteTool(max_chars=3000)

    backstory_file = f"config/agent_backstory_{track}.md"
    prompt_file    = f"config/prompt_llm_search_{track}.md"

    suffix      = "_test" if test_mode else ""
    output_file = f"data/offres_agent_{track}{suffix}.json"

    if not os.path.exists(backstory_file):
        raise FileNotFoundError(f"Backstory introuvable : {backstory_file}")
    if not os.path.exists(prompt_file):
        raise FileNotFoundError(f"Prompt introuvable : {prompt_file}")

    with open(backstory_file, "r", encoding="utf-8") as f:
        backstory = f.read()

    with open(prompt_file, "r", encoding="utf-8") as f:
        task_desc = f.read()

    task_desc = task_desc.replace("{{DATE_AUJOURD_HUI}}", date.today().isoformat())

    track_label = TRACK_LABELS.get(track, track)

    llm = LLM(
        model=llm_name,
        max_tokens=4096,
        temperature=0.1
    )

    agent = Agent(
        role=f"Chasseur d'alternances {track_label}",
        goal=f"Trouver 5-10 offres d'alternance {track_label} valides à Rennes, Nantes ou Paris et retourner un JSON strict.",
        backstory=backstory,
        tools=[search_tool, scrape_tool],
        llm=llm,
        max_iter=25,
        verbose=True
    )

    task = Task(
        description=task_desc,
        expected_output="Un JSON valide avec clés meta et offres.",
        agent=agent,
        output_file=output_file
    )

    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    print(f"\n> Track    : {track_label}")
    print(f"> LLM      : {llm_name}")
    print(f"> Backstory: {backstory_file}")
    print(f"> Prompt   : {prompt_file}")
    print(f"> Output   : {output_file}\n")

    result = crew.kickoff()

    # Nettoyage + réparation + normalisation post-run
    if os.path.exists(output_file):
        clean_llm_output_file(output_file)
    else:
        print(f"[warn] Fichier de sortie non trouvé : {output_file}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test agent CrewAI par track")
    parser.add_argument(
        "--track",
        default="digitalmarketing",
        choices=list(TRACK_LABELS.keys()),
        help="Track d'alternance à rechercher"
    )
    parser.add_argument(
        "--llm",
        default="anthropic/claude-haiku-4-5-20251001",
        help="Modèle LLM à utiliser"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Mode test : écrit dans offres_agent_{track}_test.json"
    )
    args = parser.parse_args()
    test_llm_search(args.llm, args.track, args.test)
