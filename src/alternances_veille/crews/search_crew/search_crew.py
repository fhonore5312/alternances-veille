#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crews/search_crew/search_crew.py — @CrewBase — Recherche offres alternance
Conforme architecture CrewAI V2. Config isolée dans crews/search_crew/config/.

Utilisé par : tools/llm_search_agent.py
Appelé via  : SearchCrew(track).crew().kickoff(inputs={"date_today": ...})
"""

import os
from pathlib import Path
from typing import List

from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent  # → repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_CREW_DIR = Path(__file__).resolve().parent  # crews/search_crew/

TRACKS_VALID = ["digitalmarketing", "finance"]


@CrewBase
class SearchCrew:
    """
    Crew de recherche d'offres d'alternance.
    Un seul track par instanciation (digitalmarketing ou finance).
    Sélection de l'agent/task actif via self.track dans crew().
    """

    agents: List[BaseAgent]
    tasks:  List[Task]

    # Config ISOLÉE — ne pointe plus sur config/ partagé racine
    agents_config = str(_CREW_DIR / "config" / "agents.yaml")
    tasks_config  = str(_CREW_DIR / "config" / "tasks.yaml")

    def __init__(self, track: str, test_mode: bool = False):
        if track not in TRACKS_VALID:
            raise ValueError(f"Track inconnu : {track}. Valides : {TRACKS_VALID}")
        self.track     = track
        self.test_mode = test_mode

        self._llm = LLM(
            model=os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            max_tokens=8192,          # ← était 4096 — JSON 10 offres × 30 champs = ~5000 tokens
            temperature=0.0,
        )
        self._search = SerperDevTool(n_results=5, country="fr", locale="fr")
        self._scrape = ScrapeWebsiteTool(max_chars=1500)  # ← était 4000 — réduit le contexte de 62%

    # ── Agents ──────────────────────────────────────────────────────────────

    @agent
    def search_agent_digitalmarketing(self) -> Agent:
        return Agent(
            config=self.agents_config["search_agent_digitalmarketing"],
            tools=[self._search, self._scrape],
            llm=self._llm,
            verbose=True,
            allow_delegation=False,
            max_iter=12,             # ← était 15 — 4 searches + 3-4 scrapes max
            memory=False,
        )

    @agent
    def search_agent_finance(self) -> Agent:
        return Agent(
            config=self.agents_config["search_agent_finance"],
            tools=[self._search, self._scrape],
            llm=self._llm,
            verbose=True,
            allow_delegation=False,
            max_iter=12,             # ← était 15
            memory=False,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def search_task_digitalmarketing(self) -> Task:
        suffix = "_test" if self.test_mode else ""
        return Task(
            config=self.tasks_config["search_task_digitalmarketing"],  # type: ignore[index]
            output_file=str(DATA_DIR / f"offres_agent_digitalmarketing{suffix}.json"),
        )

    @task
    def search_task_finance(self) -> Task:
        suffix = "_test" if self.test_mode else ""
        return Task(
            config=self.tasks_config["search_task_finance"],  # type: ignore[index]
            output_file=str(DATA_DIR / f"offres_agent_finance{suffix}.json"),
        )

    # ── Crew : sélection dynamique selon track ───────────────────────────────

    @crew
    def crew(self) -> Crew:
        if self.track == "digitalmarketing":
            agents_list = [self.search_agent_digitalmarketing()]
            tasks_list  = [self.search_task_digitalmarketing()]
        else:
            agents_list = [self.search_agent_finance()]
            tasks_list  = [self.search_task_finance()]

        return Crew(
            agents=agents_list,
            tasks=tasks_list,
            process=Process.sequential,
            verbose=True,
        )
