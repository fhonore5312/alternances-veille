#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow.py - Orchestrateur principal CrewAI Flow

Pipeline actuel (séquentiel) :
    scrape_lba → validate → merge → generate_email → summary

Pipeline futur (avec agents LLM en parallèle) :
    scrape_lba ─┐
                ├─ and_() → validate → merge → generate_email
    llm_agents ─┘
"""

from datetime import datetime
from pathlib import Path

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent.parent.parent  # src/alternances_veille/ → repo root
DATA_DIR = BASE_DIR / "data"


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

    # --- Flags de succès par étape ---
    lba_ok: bool = False
    llm_ok: bool = False       # placeholder — agents LLM (étape future)
    validated_ok: bool = False
    merged_ok: bool = False
    email_ok: bool = False

    # --- Erreurs accumulées ---
    errors: list[str] = []


# ===== FLOW PRINCIPAL =====

class VeilleFlow(Flow[VeilleState]):

    # ── Étape 1 : Scraper LBA ──────────────────────────────────────────────

    @start()
    def scrape_lba(self):
        """Scrape l'API La Bonne Alternance — 4 tracks, géolocalisation serveur."""
        if self.state.debug_mode and (DATA_DIR / "offres_lba.json").exists():
            print("⏭️  [DEBUG] Skip scraping LBA (fichier existant)")
            self.state.lba_ok = True
            return

        from alternances_veille.tools.lba_scraper import run_lba_scraper
        try:
            count = run_lba_scraper()
            self.state.lba_count = count
            self.state.lba_ok = True
            print(f"✅ LBA scraping : {count} offres")
        except Exception as e:
            self.state.errors.append(f"scrape_lba: {e}")
            print(f"❌ Erreur scrape_lba : {e}")

    # ── [FUTUR] Étape 1b : Agents LLM search (parallèle avec LBA) ───────────
    #
    # @start()
    # def run_llm_agents(self):
    #     from alternances_veille.crews.search_crew import SearchCrew
    #     ...
    #     self.state.llm_ok = True
    #
    # Quand activé, remplacer @listen(scrape_lba) par @listen(and_(scrape_lba, run_llm_agents))
    # ────────────────────────────────────────────────────────────────────────

    # ── Étape 2 : Validation ───────────────────────────────────────────────

    @listen(scrape_lba)
    def validate(self):
        """Validation HTTP (LBA) + structure JSON (LLM)."""
        if not self.state.lba_ok:
            print("⚠️ Validation skippée — scraping LBA en erreur")
            return

        if self.state.debug_mode and (DATA_DIR / "offres_lba_validated.json").exists():
            print("⏭️ [DEBUG] Skip validation (fichiers existants)")
            self.state.validated_ok = True
            return

        from alternances_veille.tools.validator import run_validator
        # ← ligne run_validator(quick_mode=getattr(...)) SUPPRIMÉE
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
    def merge(self):
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

    # ── Étape 4 : Génération HTML + email ──────────────────────────────────

    @listen(merge)
    def generate_email(self):
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
    def summary(self):
        print("\n" + "=" * 70)
        print(f"📊 RÉSUMÉ — Run {self.state.run_id}")
        print("=" * 70)
        print(f"  📥 LBA scrapées          : {self.state.lba_count}")
        print(f"  ✅ Validées LBA          : {self.state.validated_lba_count}")
        print(f"  ✅ Validées LLM          : {self.state.validated_llm_count}")
        print(f"  📦 Total mergées         : {self.state.merged_count}")
        print(f"  🆕 Nouvelles             : {self.state.nouvelles_count}")
        print(f"  📧 Email                 : {'✅' if self.state.email_ok else '❌'}")
        if self.state.errors:
            print(f"\n  ⚠️  Erreurs ({len(self.state.errors)}) :")
            for err in self.state.errors:
                print(f"     • {err}")
        print("=" * 70)
