#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import argparse
from datetime import date
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

TRACK_LABELS = {
    "digitalmarketing": "Marketing Digital",
    "finance": "Finance, Audit et Contrôle de gestion",
    "supplychain": "Supply Chain et Achats",
    "businessdev": "Business Development et Vente",
}


def clean_llm_output_file(filepath: str):
    """
    Nettoie le fichier JSON si le LLM a ajouté du texte avant/après
    ou des balises ```json ... ```.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    # Déjà propre
    if raw.startswith("{"):
        return

    # Cas 1 : balises ```json ... ```
    match = re.search(r'```json\s*([\s\S]+?)\s*```', raw)
    if match:
        cleaned = match.group(1).strip()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"[clean] Balises ```json``` supprimées dans {filepath}")
        return

    # Cas 2 : texte avant le premier {
    match = re.search(r'(\{[\s\S]+\})', raw)
    if match:
        cleaned = match.group(1).strip()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"[clean] Texte parasite supprimé dans {filepath}")
        return

    print(f"[warn] Impossible de nettoyer {filepath} — vérifier manuellement")


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
        goal=f"Trouver 5-10 offres d'alternance {track_label} valides à Rennes, Nantes ou Paris et retourner un JSON strict.",
        backstory=backstory,
        tools=[search_tool, scrape_tool],
        llm=llm,
        max_iter=25,
        verbose=True
    )

    task = Task(
        description=task_desc,
        expected_output="Un JSON valide avec clés meta et offres.",
        agent=agent,
        output_file=output_file
    )

    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    print(f"\n> Track     : {track_label}")
    print(f"> LLM       : {llm_name}")
    print(f"> Backstory : {backstory_file}")
    print(f"> Prompt    : {prompt_file}")
    print(f"> Output    : {output_file}\n")

    result = crew.kickoff()

    # Nettoyage post-run : supprime texte parasite et balises ```json```
    if os.path.exists(output_file):
        clean_llm_output_file(output_file)
    else:
        print(f"[warn] Fichier de sortie non trouvé : {output_file}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test agent CrewAI par track")
    parser.add_argument(
        "--track",
        default="digitalmarketing",
        choices=list(TRACK_LABELS.keys()),
        help="Track d'alternance à rechercher"
    )
    parser.add_argument(
        "--llm",
        default="anthropic/claude-haiku-4-5-20251001",
        help="Modèle LLM à utiliser"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Mode test : écrit dans offres_agent_{track}_test.json"
    )
    args = parser.parse_args()
    test_llm_search(args.llm, args.track, args.test)
