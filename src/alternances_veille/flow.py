#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow.py - Orchestrateur principal CrewAI Flow

Pipeline V2 (parallèle) :
    scrape_lba()    ─@start()─┐
                               ├─ and_() → validate → merge → find_hr_contacts → generate_email → summary
    run_llm_agents()─@start()─┘
"""

import os
import sys
os.environ["PYTHONUTF8"] = "1"

from datetime import datetime
from pathlib import Path

from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent.parent.parent  # src/alternances_veille/ → repo root
DATA_DIR = BASE_DIR / "data"

# Garantit que src/ est dans sys.path (standalone + flow run)
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ===== ÉTAT DU FLOW =====

class VeilleState(BaseModel):

    # --- Configuration du run ---
    quick_mode: bool = False
    debug_mode: bool = False
    run_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    # --- Compteurs par étape ---
    lba_count: int = 0
    llm_count: int = 0
    validated_lba_count: int = 0
    validated_llm_count: int = 0
    merged_count: int = 0
    nouvelles_count: int = 0
    hr_contacts_count: int = 0

    # --- Flags de succès par étape ---
    lba_ok: bool = False
    llm_ok: bool = False
    validated_ok: bool = False
    merged_ok: bool = False
    hr_contacts_ok: bool = False
    email_ok: bool = False

    # --- Erreurs accumulées ---
    errors: list[str] = []


# ===== FLOW PRINCIPAL =====

TRACKS_LLM = ["digitalmarketing", "finance"]


class VeilleFlow(Flow[VeilleState]):

    # ── Étape 1a : Scraper LBA ────────────────────────────────────────────

    @start()
    async def scrape_lba(self):
        """Scrape l'API La Bonne Alternance — 4 tracks, géolocalisation serveur."""
        print(f"🚀 [scrape_lba] Démarrage — {datetime.now().strftime('%H:%M:%S')}")

        if self.state.debug_mode and (DATA_DIR / "offres_lba.json").exists():
            print("⏭️  [DEBUG] Skip scraping LBA (fichier existant)")
            self.state.lba_ok = True
            return

        from alternances_veille.tools.lba_scraper import run_lba_scraper
        try:
            count = run_lba_scraper()
            self.state.lba_count = count
            self.state.lba_ok = True
            print(f"✅ LBA scraping : {count} offres — {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            self.state.errors.append(f"scrape_lba: {e}")
            print(f"❌ Erreur scrape_lba : {e}")

    # ── Étape 1b : Agents LLM search (parallèle avec LBA) ────────────────

    @start()
    async def run_llm_agents(self):
        """Recherche offres via SearchCrew (digital_marketing + finance) — parallèle avec LBA."""
        print(f"🚀 [run_llm_agents] Démarrage — {datetime.now().strftime('%H:%M:%S')}")

        # Debug : skip si tous les fichiers agents existent déjà
        all_exist = all(
            (DATA_DIR / f"offres_agent_{track}.json").exists()
            for track in TRACKS_LLM
        )
        if self.state.debug_mode and all_exist:
            print("⏭️  [DEBUG] Skip agents LLM (fichiers existants)")
            self.state.llm_ok = True
            return

        from alternances_veille.tools.alternance_search_agent import run_alternance_search_agent
        total = 0
        for track in TRACKS_LLM:
            try:
                print(f"  🤖 [run_llm_agents] Lancement track '{track}'...")
                output_file = run_alternance_search_agent(track=track)
                print(f"  ✅ [run_llm_agents] Track '{track}' terminé → {output_file}")
                total += 1
            except Exception as e:
                self.state.errors.append(f"run_llm_agents[{track}]: {e}")
                print(f"  ❌ [run_llm_agents] Erreur track '{track}' : {e}")

        self.state.llm_count = total
        self.state.llm_ok = True  # non bloquant — validate gère les fichiers manquants
        print(f"✅ LLM agents terminés ({total}/{len(TRACKS_LLM)}) — {datetime.now().strftime('%H:%M:%S')}")

    # ── Étape 2 : Validation ──────────────────────────────────────────────

    @listen(and_(scrape_lba, run_llm_agents))
    async def validate(self):
        """Validation HTTP (LBA) + structure JSON (LLM)."""
        print(f"🚀 [validate] Démarrage — {datetime.now().strftime('%H:%M:%S')}")

        # ── Double garde : les deux branches DOIVENT être terminées ──────
        if not self.state.lba_ok:
            print("⚠️  Validation skippée — scraping LBA en erreur")
            return

        if not self.state.llm_ok:
            # Ne devrait jamais arriver si and_() fonctionne, mais sécurité supplémentaire
            print("⚠️  Validation skippée — agents LLM non terminés")
            self.state.errors.append("validate: llm_ok=False au déclenchement (and_ bypass ?)")
            return

        if self.state.debug_mode and (DATA_DIR / "offres_lba_validated.json").exists():
            print("⏭️  [DEBUG] Skip validation (fichiers existants)")
            self.state.validated_ok = True
            return

        from alternances_veille.tools.validator import run_validator
        try:
            lba_count, llm_count = run_validator(quick_mode=self.state.quick_mode)
            self.state.validated_lba_count = lba_count
            self.state.validated_llm_count = llm_count
            self.state.validated_ok = True
            print(f"✅ Validation : {lba_count} LBA + {llm_count} LLM")
        except Exception as e:
            self.state.errors.append(f"validate: {e}")
            print(f"❌ Erreur validation : {e}")

    # ── Étape 3 : Merge & déduplication ───────────────────────────────────

    @listen(validate)
    async def merge(self):
        """Merge LBA + LLM, déduplication, gestion historique."""
        if not self.state.validated_ok:
            print("⚠️  Merge skippé — validation en erreur")
            return

        if self.state.debug_mode and (DATA_DIR / "offres_merged.json").exists():
            print("⏭️  [DEBUG] Skip merge (fichier existant)")
            self.state.merged_ok = True
            return

        from alternances_veille.tools.merge_offers import run_merge_offers
        try:
            merged_count, nouvelles = run_merge_offers()
            self.state.merged_count = merged_count
            self.state.nouvelles_count = nouvelles
            self.state.merged_ok = True
            print(f"✅ Merge : {merged_count} offres ({nouvelles} nouvelles)")
        except Exception as e:
            self.state.errors.append(f"merge: {e}")
            print(f"❌ Erreur merge : {e}")

    # ── Étape 3b : Recherche contacts RH ──────────────────────────────────

    @listen(merge)
    async def find_hr_contacts(self):
        """Recherche les contacts RH via HRContactsCrew (étape optionnelle, non bloquante)."""
        if not self.state.merged_ok:
            print("⚠️  Contacts RH skippés — merge en erreur")
            return

        if self.state.debug_mode and (DATA_DIR / "hr_contacts.json").exists():
            print("⏭️  [DEBUG] Skip HR contacts (fichier existant)")
            self.state.hr_contacts_ok = True
            return

        from alternances_veille.tools.hr_contacts_agent import run_hr_contacts_agent
        try:
            count = run_hr_contacts_agent(track=None)
            self.state.hr_contacts_count = count
            self.state.hr_contacts_ok = True
            print(f"✅ Contacts RH : {count} contacts actionnables")
        except Exception as e:
            self.state.errors.append(f"find_hr_contacts: {e}")
            print(f"❌ Erreur find_hr_contacts : {e}")
            # Non bloquant — generate_email se lance quand même

    # ── Étape 4 : Génération HTML + email ─────────────────────────────────

    @listen(find_hr_contacts)
    async def generate_email(self):
        """Génère la page HTML, publie sur GitHub Pages, envoie via Gmail."""
        if not self.state.merged_ok:
            print("⚠️  Email skippé — merge en erreur")
            return

        from alternances_veille.tools.html_email import run_html_email
        try:
            run_html_email()
            self.state.email_ok = True
            print("✅ Email HTML généré et envoyé")
        except Exception as e:
            self.state.errors.append(f"generate_email: {e}")
            print(f"❌ Erreur generate_email : {e}")

    # ── Résumé final ───────────────────────────────────────────────────────

    @listen(generate_email)
    async def summary(self):
        print("\n" + "=" * 70)
        print(f"📊 RÉSUMÉ — Run {self.state.run_id}")
        print("=" * 70)
        print(f"  📥 LBA scrapées          : {self.state.lba_count}")
        print(f"  🤖 Tracks LLM lancés     : {self.state.llm_count}/{len(TRACKS_LLM)}")
        print(f"  ✅ Validées LBA          : {self.state.validated_lba_count}")
        print(f"  ✅ Validées LLM          : {self.state.validated_llm_count}")
        print(f"  📦 Total mergées         : {self.state.merged_count}")
        print(f"  🆕 Nouvelles             : {self.state.nouvelles_count}")
        print(f"  👥 Contacts RH           : {self.state.hr_contacts_count}")
        print(f"  📧 Email                 : {'✅' if self.state.email_ok else '❌'}")
        if self.state.errors:
            print(f"\n  ⚠️  Erreurs ({len(self.state.errors)}) :")
            for err in self.state.errors:
                print(f"     • {err}")
        print("=" * 70)
