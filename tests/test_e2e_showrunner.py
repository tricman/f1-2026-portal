"""
End-to-End Automated Homologation Suite for F1 2026 Showrunner Engine (Sprint 4).
Validates the complete lifecycle for Round 11 (GP da Áustria):
  1. M1 Pre-Race Weekly Chronicle Generation (All 10 Teams).
  2. M1.5 Paddock Dilemma (Generation, Lock, and Resolution).
  3. M2 FIA Press Conference (Dynamic Questions, Pilot Reply / Timeout Contingency).
  4. Telemetry Ingestion & PaceDex Merging.
  5. FIA Championship Calculation & Position Delta Tracking.
  6. Post-Race Editorial Modules M3..M8 Generation.
  7. Round Finalization & Canon Digest Ledger Recording.
  8. Editorial Portal Build (Paddock Dark Mode & Weekend Sequence Tabs).
  9. Granular Rollback Execution & Safety Guard Verification.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ai_showrunner import (
    GeminiFreeTierClient,
    generate_m1_daily_episode,
    generate_paddock_dilemma,
    resolve_paddock_dilemma,
    generate_post_race_modules,
    finalize_round_transition,
)
from src.press_conference import PressConferenceSession
from src.telemetry_merger import parse_free_practice_summary, merge_race_telemetry
from src.fia_calculator import update_championship_standings
from src.portal_builder import build_editorial_portal
from src.orchestrator_cli import execute_stage_rollback, process_round_telemetry
from src.canon_ledger import CanonLedgerManager


ROOT_PROJECT_DIR = Path(__file__).resolve().parent.parent


class TestE2EShowrunnerRound11(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="f1_e2e_round11_"))
        self.seasons_dir = self.temp_dir / "data" / "seasons" / "season_01"
        self.r11_dir = self.seasons_dir / "et_11_austria"
        self.r11_tel = self.r11_dir / "telemetry"
        self.r11_tel.mkdir(parents=True, exist_ok=True)
        self.state_dir = self.temp_dir / "data" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Copy prompts and personas for storytelling context
        shutil.copytree(ROOT_PROJECT_DIR / "prompts", self.temp_dir / "prompts")
        shutil.copytree(ROOT_PROJECT_DIR / "personas", self.temp_dir / "personas")
        shutil.copytree(ROOT_PROJECT_DIR / "data" / "setup", self.temp_dir / "data" / "setup")

        # Copy initial Round 10 state
        real_standings = ROOT_PROJECT_DIR / "data" / "state" / "standings.json"
        if real_standings.exists():
            shutil.copy(real_standings, self.state_dir / "standings.json")

        for snap in (ROOT_PROJECT_DIR / "data" / "state").glob("standings_et*.json"):
            shutil.copy(snap, self.state_dir / snap.name)

        real_ledger = ROOT_PROJECT_DIR / "data" / "state" / "canon_ledger.json"
        if real_ledger.exists():
            shutil.copy(real_ledger, self.state_dir / "canon_ledger.json")

        # Copy sample telemetry from Round 10 to serve as Round 11 raw PaceDex data
        r10_tel = ROOT_PROJECT_DIR / "data" / "seasons" / "season_01" / "et_10_espanha" / "telemetry"
        for f in r10_tel.glob("*.csv"):
            shutil.copy(f, self.r11_tel / f.name.replace("catalunya-espanha", "redbullring-austria"))

        # Setup tv overlay for Austria
        r10_tv = r10_tel / "tv_overlay_et10.json"
        if r10_tv.exists():
            tv_data = json.loads(r10_tv.read_text(encoding="utf-8"))
            (self.r11_tel / "tv_overlay_et11.json").write_text(
                json.dumps(tv_data, indent=2), encoding="utf-8"
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_ai(self) -> MagicMock:
        mock = MagicMock(spec=GeminiFreeTierClient)
        mock.api_key = "fake_test_key"
        mock.flash_model = "gemini-flash-test"
        mock.pro_model = "gemini-pro-test"
        mock._call_generate_content.return_value = (
            "## CONTEÚDO NARRATIVO HOMOLOGADO E2E\n"
            "Análise detalhada do Paddock de Spielberg. Sarah, Davi e Felipe travaram duelo tenso nas montanhas austríacas."
        )
        return mock

    @patch("src.press_conference.deploy_portal_to_github_pages")
    def test_e2e_complete_austria_round_lifecycle(self, mock_deploy):
        mock_ai = self._create_mock_ai()

        # -------------------------------------------------------------
        # STEP 1: M1 PRE-RACE DAILY EPISODE (QUARTA-FEIRA)
        # -------------------------------------------------------------
        m1_path, teaser = generate_m1_daily_episode(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            day_num=3,
            ai_client=mock_ai,
        )
        self.assertTrue(m1_path.exists())
        self.assertIn("ET11_PRE_A_Semana_da_F1_Dia_3.md", m1_path.name)
        m1_text = m1_path.read_text(encoding="utf-8")
        self.assertIn("QUARTA-FEIRA", m1_text)

        # -------------------------------------------------------------
        # STEP 2: M1.5 PADDOCK DILEMMA (LOCK & RESOLVE)
        # -------------------------------------------------------------
        dilemma = generate_paddock_dilemma(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            target_driver="felipe",
            ai_client=mock_ai,
        )
        self.assertEqual(dilemma["status"], "AWAITING_DILEMMA_CHOICE")
        self.assertTrue((self.state_dir / "dilemma_et11.json").exists())

        resolution = resolve_paddock_dilemma(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            raw_choice="Opção A (Focar na telemetria de longo curso)",
            ai_client=mock_ai,
        )
        self.assertEqual(resolution["status"], "COMPLETED")
        dilemma_saved = json.loads((self.state_dir / "dilemma_et11.json").read_text(encoding="utf-8"))
        self.assertEqual(dilemma_saved["status"], "COMPLETED")

        # -------------------------------------------------------------
        # STEP 3: M2 INTERACTIVE PRESS CONFERENCE
        # -------------------------------------------------------------
        sess = PressConferenceSession(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            ai_client=mock_ai,
        )
        opening = sess.start_session()
        self.assertIn("COLETIVA", opening)
        # Advance through conference questions
        while not sess.state.get("completed"):
            if sess.state.get("status") == "AWAITING_PILOT_REPLY":
                sess.force_timeout_answer(reason="Resposta padrão da assessoria")
            sess.advance_to_next_question()

        self.assertTrue(sess.state.get("completed"))
        m2_files = list(self.r11_dir.glob("*Coletiva*.md"))
        self.assertGreaterEqual(len(m2_files), 1)

        # -------------------------------------------------------------
        # STEP 4: TELEMETRY MERGE & STANDINGS COMPUTATION
        # -------------------------------------------------------------
        with patch("src.orchestrator_cli.ROOT_DIR", self.temp_dir):
            process_round_telemetry(11, "et_11_austria")

        self.assertTrue((self.r11_tel / "race_telemetry_merged.json").exists())
        self.assertTrue((self.state_dir / "standings_et11.json").exists())

        standings_et11 = json.loads((self.state_dir / "standings_et11.json").read_text(encoding="utf-8"))
        self.assertEqual(standings_et11["last_completed_round"], 11)
        drivers = standings_et11.get("drivers_standings", [])
        self.assertGreaterEqual(len(drivers), 20)

        # Sarah, Davi or Felipe should have updated points and valid pos_delta
        sarah = next(d for d in drivers if d["id"] == "sarah")
        self.assertGreater(sarah["points"], 0)
        self.assertIn("pos_delta", sarah)

        # -------------------------------------------------------------
        # STEP 5: POST-RACE MODULES GENERATION (M3..M8)
        # -------------------------------------------------------------
        generated_modules = generate_post_race_modules(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            ai_client=mock_ai,
        )
        self.assertGreaterEqual(len(generated_modules), 5)
        for mod_path in generated_modules:
            self.assertTrue(mod_path.exists())

        # -------------------------------------------------------------
        # STEP 6: ROUND TRANSITION FINALIZATION & CANON LEDGER
        # -------------------------------------------------------------
        trans_res = finalize_round_transition(
            root_dir=self.temp_dir,
            round_num=11,
            round_folder="et_11_austria",
            ai_client=mock_ai,
        )
        self.assertEqual(trans_res["round_finalized"], 11)
        self.assertEqual(trans_res["next_round"], 12)

        # Standings.json must be promoted to Round 11
        main_st = json.loads((self.state_dir / "standings.json").read_text(encoding="utf-8"))
        self.assertEqual(main_st["last_completed_round"], 11)

        # Canon ledger has the Round 11 closing event
        ledger_mgr = CanonLedgerManager(self.state_dir / "canon_ledger.json")
        ledger_data = ledger_mgr.load()
        event_ids = [e.get("event_id") for e in ledger_data.get("events", [])]
        self.assertIn("ET11-AUTO-M5", event_ids)

        # -------------------------------------------------------------
        # STEP 7: PORTAL BUILD & PADDOCK DARK MODE VALIDATION
        # -------------------------------------------------------------
        portal_path = build_editorial_portal(self.temp_dir)
        self.assertTrue(portal_path.exists())
        html = portal_path.read_text(encoding="utf-8")

        # Assert Paddock Dark Mode colors and components
        self.assertIn("--bg-paddock: #0b131e;", html)
        self.assertIn("--fia-navy: #1b365d;", html)
        self.assertIn("--f1-red: #e10600;", html)
        self.assertIn("id=\"weekendModuleTabs\"", html)
        self.assertIn("renderDeltaBadge", html)
        self.assertIn("Pilotos (WDC)", html)
        self.assertIn("Construtores (WCC)", html)

        # Assert Round 11 articles are indexed in portal_data.json
        portal_json = json.loads((self.temp_dir / "portal" / "portal_data.json").read_text(encoding="utf-8"))
        r11_entry = next((r for r in portal_json["rounds"] if r["num"] == 11), None)
        self.assertIsNotNone(r11_entry)
        self.assertGreaterEqual(len(r11_entry["articles"]), 6)

        # -------------------------------------------------------------
        # STEP 8: GRANULAR ROLLBACK (SESSAO) & SAFETY GUARDS
        # -------------------------------------------------------------
        with patch("src.orchestrator_cli.ROOT_DIR", self.temp_dir):
            # Attempting rollback on Round 10 must fail by safety guard
            with self.assertRaises(ValueError):
                execute_stage_rollback(round_num=10, scope="sessao")

            # Rollback Round 11 session
            rollback_res = execute_stage_rollback(round_num=11, scope="sessao")
            self.assertGreater(rollback_res["deleted_files_count"], 0)
            self.assertTrue(rollback_res["reverted_standings"])

            # Verify M3..M8 files were purged while M1 / M2 remain
            r11_mds = [f.name for f in self.r11_dir.glob("*.md")]
            self.assertTrue(any("Semana_da_F1" in f for f in r11_mds))
            self.assertTrue(any("Coletiva" in f for f in r11_mds))
            self.assertFalse(any("Resultado Final" in f for f in r11_mds))


if __name__ == "__main__":
    unittest.main()
