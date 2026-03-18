#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crews/hr_contacts_crew.py — Crew CrewAI @CrewBase — Recherche contact RH
Conforme architecture officielle CrewAI V2.

Utilisé par : tools/hr_contacts_agent.py
Appelé via  : HRContactsCrew().crew().kickoff(inputs={...})
"""

import os
from pathlib import Path
from typing import List

from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

# Résolution chemin absolu vers config/ partagé (repo root)
# crews/ → alternances_veille/ → src/ → repo_root
BASE_DIR   = Path(__file__).resolve().parent.parent.parent.parent


@CrewBase
class HRContactsCrew:
    """Crew de recherche de contact RH pour une offre donnée."""

    agents: List[BaseAgent]
    tasks:  List[Task]

    # ⚠️ Config ISOLÉE dans le sous-dossier dédié — PAS le config/ partagé racine
    _CREW_DIR    = Path(__file__).resolve().parent
    agents_config = str(_CREW_DIR / "config" / "agents.yaml")
    tasks_config  = str(_CREW_DIR / "config" / "tasks.yaml")

    @agent
    def hr_contact_agent(self) -> Agent:
        llm = LLM(
            model=os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            max_tokens=1024,
            temperature=0.1,
        )
        return Agent(
            config=self.agents_config["hr_contact_agent"],  # type: ignore[index]
            tools=[
                SerperDevTool(n_results=3),
                ScrapeWebsiteTool(max_chars=2000),
            ],
            llm=llm,
            max_iter=8,
            verbose=False,
        )

    @task
    def hr_contact_task(self) -> Task:
        return Task(
            config=self.tasks_config["hr_contact_task"],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Crew séquentiel : 1 agent / 1 task / 1 offre."""
        return Crew(
            agents=self.agents,   # collecté automatiquement par @agent
            tasks=self.tasks,     # collecté automatiquement par @task
            process=Process.sequential,
            verbose=False,
        )
