#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/llm_search_agent.py — Crew CrewAI @CrewBase — recherche LLM d'offres d'alternance

Usage:
    python -m alternances_veille.tools.llm_search_agent --track digitalmarketing --test
    python -m alternances_veille.tools.llm_search_agent --track finance
    python -m alternances_veille.tools.llm_search_agent --all
"""

import os, re, json, argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Task, Crew, LLM, Process
from crewai.project import CrewBase, agent, task, crew
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# ===== CHEMINS =====

BASE_DIR   = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR   = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRACKS_LLM = ["digitalmarketing", "finance"]

# ===== NETTOYAGE / RÉPARATION JSON =====

def _repair_truncated_json(raw: str):
    for closing in ["\n  ]\n}", "\n]}"]:
        try:
            return json.loads(raw.rstrip() + closing)
        except json.JSONDecodeError:
            continue
    return None


def _normalize_offer(offer: dict, today_str: str) -> None:
    if not offer.get("date_creation"):
        raw = offer.get("first_seen") or today_str
        try:
            offer["date_creation"] = datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            offer["date_creation"] = raw
    if offer.get("status") not in ("new", "active", "incertain"):
        offer["status"] = "new"


_SCHOOL_BLACKLIST_ENTREPRISE = {
    "alticome", "mydigitalschool", "studi", "iscod",
    "sup de pub", "openclassrooms", "bringme", "alticom",
    "groupe igs", "neogest", "igf formation", "campus channel",
    "école", "ecole", "cfa", "centre de formation",
    "rocket school",
    "association imc",
    "talents handicap",
}

_SCHOOL_BLACKLIST_URL = {
    "alticome.fr", "mydigitalschool.com", "studi.fr", "iscod.fr",
    "sup-de-pub.com", "openclassrooms.com", "bringme.fr",
    "alticom.com", "groupe-igs.fr", "neogest.com",
}

_SCHOOL_BLACKLIST_DESC = {
    "formaposte",
    "l'alternance à la poste est exclusivement accessible en suivant la formation",
    "centre de formation professionnelle recherche pour l'un de ses",
    "recherche pour l'une de ses entreprises partenaires",
    "notre école recrute pour",
    "notre cfa recrute pour",
    "irss,",
}


def _is_school_offer(offer: dict) -> bool:
    entreprise = offer.get("entreprise", "").lower()
    url        = offer.get("url_candidature", "").lower()
    desc       = offer.get("description_complete", offer.get("description", "")).lower()
    if any(s in entreprise for s in _SCHOOL_BLACKLIST_ENTREPRISE):
        return True
    if any(d in url for d in _SCHOOL_BLACKLIST_URL):
        return True
    if any(p in desc for p in _SCHOOL_BLACKLIST_DESC):
        return True
    return False


def clean_llm_output_file(filepath: str) -> int:
    """Nettoie le JSON LLM, répare les troncatures, normalise et filtre les offres. Retourne nb offres."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    today_str = str(date.today())
    cleaned = None

    if raw.startswith("{"):
        cleaned = raw
    else:
        for pat in [r"```json\s*([\s\S]+?)\s*```", r"(\{[\s\S]+\})"]:
            m = re.search(pat, raw)
            if m:
                cleaned = m.group(1).strip()
                break

    if not cleaned:
        print(f"[warn] Impossible de nettoyer {filepath}")
        return 0

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[warn] JSON invalide : {e} — tentative de réparation")
        data = _repair_truncated_json(cleaned)
        if data is None:
            print(f"[ERROR] Réparation impossible : {filepath}")
            return 0

    for offer in data.get("offres", []):
        _normalize_offer(offer, today_str)

    before = len(data.get("offres", []))
    data["offres"] = [o for o in data.get("offres", []) if not _is_school_offer(o)]
    removed = before - len(data["offres"])
    if removed:
        print(f"[filter-school] {removed} offre(s) école/CFA supprimée(s)")

    nb = len(data["offres"])
    data.setdefault("meta", {})["nb_offres"] = nb

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[ok] {filepath} → {nb} offres")
    return nb


# ===== CREW @CrewBase =====

@CrewBase
class VeilleSearchCrew:
    """
    Crew de recherche d'offres d'alternance.
    Architecture officielle CrewAI : agents.yaml + tasks.yaml + @CrewBase.
    Un seul track par instanciation (digitalmarketing ou finance).
    """

    agents_config = str(CONFIG_DIR / "agents.yaml")
    tasks_config  = str(CONFIG_DIR / "tasks.yaml")

    def __init__(self, track: str, test_mode: bool = False):
        if track not in TRACKS_LLM:
            raise ValueError(f"Track inconnu : {track}. Valeurs valides : {TRACKS_LLM}")
        self.track     = track
        self.test_mode = test_mode

        self._llm    = LLM(
            model=os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            max_tokens=4096,
            temperature=0.0,
        )
        self._search = SerperDevTool(
            n_results=5,
            country="fr",
            locale="fr",
        )
        self._scrape = ScrapeWebsiteTool(
            max_chars=4000,
        )

    # ── Agents ──────────────────────────────────────────────────────────────

    @agent
    def search_agent_digitalmarketing(self) -> Agent:
        return Agent(
            config=self.agents_config["search_agent_digitalmarketing"],
            tools=[self._search, self._scrape],
            llm=self._llm,
            verbose=True,
            allow_delegation=False,
            max_iter=15,
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
            max_iter=15,
            memory=False,
        )

    # ── Tasks ────────────────────────────────────────────────────────────────

    @task
    def search_task_digitalmarketing(self) -> Task:
        suffix = "_test" if self.test_mode else ""
        return Task(
            config=self.tasks_config["search_task_digitalmarketing"],
            output_file=str(DATA_DIR / f"offres_agent_digitalmarketing{suffix}.json"),
        )

    @task
    def search_task_finance(self) -> Task:
        suffix = "_test" if self.test_mode else ""
        return Task(
            config=self.tasks_config["search_task_finance"],
            output_file=str(DATA_DIR / f"offres_agent_finance{suffix}.json"),
        )

    # ── Crew ─────────────────────────────────────────────────────────────────

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


# ===== FONCTIONS D'EXÉCUTION =====

def run_llm_search_agent(track: str = "digitalmarketing", test_mode: bool = False) -> str:
    today = date.today().isoformat()
    print(f"\n{'='*60}")
    print(f"🤖 LLM SEARCH AGENT — {track.upper()}")
    print(f"{'='*60}\n")

    crew_inst = VeilleSearchCrew(track=track, test_mode=test_mode)

    try:
        crew_inst.crew().kickoff(inputs={"date_today": today})
    except ValueError as e:
        print(f"[warn] Crew échouée ({e}) — tentative de récupération du fichier partiel")
    except Exception as e:
        print(f"[error] Crew échouée de manière inattendue : {e}")

    suffix      = "_test" if test_mode else ""
    output_file = str(DATA_DIR / f"offres_agent_{track}{suffix}.json")

    if os.path.exists(output_file):
        nb = clean_llm_output_file(output_file)
        print(f"[ok] {nb} offres sauvegardées" if nb else "[warn] Fichier vide")
    else:
        print(f"[warn] Aucun fichier de sortie créé — run sans résultat")

    return output_file


def run_all_llm_agents(test_mode: bool = False) -> dict:
    """Lance les deux tracks séquentiellement."""
    results = {}
    for track in TRACKS_LLM:
        try:
            results[track] = run_llm_search_agent(track, test_mode)
            print(f"✅ {track} OK → {results[track]}")
        except Exception as e:
            print(f"❌ {track} ERREUR : {e}")
            results[track] = None
    return results


# ===== MAIN =====

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent LLM de recherche d'offres d'alternance")
    parser.add_argument("--track", default="digitalmarketing",
                        choices=TRACKS_LLM + ["all"],
                        help="Track à traiter (ou 'all' pour les deux)")
    parser.add_argument("--test", action="store_true",
                        help="Mode test : écrit dans offres_agent_*_test.json")
    args = parser.parse_args()

    if args.track == "all":
        run_all_llm_agents(test_mode=args.test)
    else:
        run_llm_search_agent(args.track, args.test)
