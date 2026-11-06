"""
Unit and Integration Tests for Sprint 2 Deliverables:
  - 2.1 M1 Coverage for All 10 Grid Constructors & 12 Silly Season Verticals
  - 2.2 Submodule M1.5 Paddock Dilemma (Interactive Storytelling, Turn-Lock, Canon Ledger consequence)
  - 2.3 M6 with Relevant NPC Quotes and Audio Debriefing Ingestion
  - 2.4 M8 with Race Chronicle & Legends Panel (Prost, Mansell, Villeneuve)
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from src.ai_showrunner import (
    ALL_10_CONSTRUCTORS,
    generate_paddock_dilemma,
    resolve_paddock_dilemma,
)
from src.canon_ledger import SILLY_SEASON_THEMES, sample_weekly_themes, CanonLedgerManager
from src.discord_gateway import detect_stage_command


class TestSprint2StorytellingAndPrompts(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent

    # -------------------------------------------------------------
    # 2.1 M1: 10 Grid Constructors & 12 Verticals
    # -------------------------------------------------------------
    def test_all_10_constructors_registered(self):
        self.assertEqual(len(ALL_10_CONSTRUCTORS), 10)
        team_ids = {team_id for _, team_id, _, _ in ALL_10_CONSTRUCTORS}
        expected = {
            "mercedes", "sauber", "red_bull", "mclaren", "aston_martin",
            "ferrari", "williams", "alpine", "haas", "vcarb",
        }
        self.assertEqual(team_ids, expected)

    def test_silly_season_catalog_has_12_verticals(self):
        self.assertEqual(len(SILLY_SEASON_THEMES), 12)
        for i in range(1, 13):
            prefix = f"T{i:02d} —"
            self.assertTrue(
                any(t.startswith(prefix) for t in SILLY_SEASON_THEMES),
                f"Vertical {prefix} not found in SILLY_SEASON_THEMES",
            )

    def test_deterministic_sampling_for_all_10_teams(self):
        for _, team_id, _, _ in ALL_10_CONSTRUCTORS:
            sampled = sample_weekly_themes(11, team_id)
            self.assertEqual(len(sampled), 4)
            # No duplicates among the 4 days
            self.assertEqual(len(set(sampled.values())), 4)
            # Deterministic across multiple calls
            sampled2 = sample_weekly_themes(11, team_id)
            self.assertEqual(sampled, sampled2)

    def test_m1_prompt_template_integrity(self):
        prompt_path = self.root_dir / "prompts" / "01_semana_equipes.md"
        self.assertTrue(prompt_path.exists())
        content = prompt_path.read_text(encoding="utf-8")
        self.assertIn("TODAS AS 10 EQUIPES DO GRID", content)
        self.assertIn("12 VERTICAIS TEMÁTICAS", content)
        self.assertIn("T01 —", content)
        self.assertIn("T12 —", content)

    # -------------------------------------------------------------
    # 2.2 Submódulo M1.5: Dilema Interativo de Paddock
    # -------------------------------------------------------------
    def test_detect_stage_command_dilemma(self):
        cmd1 = detect_stage_command("dilema etapa 11")
        self.assertEqual(cmd1, ("START_DILEMMA", 11))

        cmd2 = detect_stage_command("dilemma etapa 12")
        self.assertEqual(cmd2, ("START_DILEMMA", 12))

        cmd3 = detect_stage_command("forcar avanco dilema")
        self.assertEqual(cmd3[0], "FORCE_DILEMMA_ADVANCE")

        cmd4 = detect_stage_command("timeout dilema")
        self.assertEqual(cmd4[0], "FORCE_DILEMMA_ADVANCE")

    def test_dilemma_prompt_template_exists(self):
        prompt_path = self.root_dir / "prompts" / "01b_dilema_paddock.md"
        self.assertTrue(prompt_path.exists())
        text = prompt_path.read_text(encoding="utf-8")
        self.assertIn("MÓDULO #1.5: DILEMA INTERATIVO DE PADDOCK", text)
        self.assertIn("OPÇÃO A", text)
        self.assertIn("OPÇÃO B", text)
        self.assertIn("TRAVA DE TURNO ATIVA", text)

    def test_generate_and_resolve_paddock_dilemma_lifecycle(self):
        round_num = 11
        round_folder = "et_11_austria"

        # 1. Generate Dilemma
        d_data = generate_paddock_dilemma(self.root_dir, round_num, round_folder, target_driver="felipe")
        self.assertEqual(d_data["status"], "AWAITING_DILEMMA_CHOICE")
        self.assertEqual(d_data["target_driver"], "felipe")
        self.assertEqual(d_data["driver_name"], "Felipe")

        state_file = self.root_dir / "data" / "state" / f"dilemma_et{round_num:02d}.json"
        self.assertTrue(state_file.exists())

        target_md = self.root_dir / "data" / "seasons" / "season_01" / round_folder / f"Etapa {round_num:02d} - Relatório de Bastidores - M1.5 Dilema de Paddock - GP da Áustria 2026.md"
        self.assertTrue(target_md.exists())

        # 2. Resolve Dilemma
        res = resolve_paddock_dilemma(
            self.root_dir,
            round_num,
            round_folder,
            raw_choice="Opção A: Aceito a oferta secreta da Audi com cláusula de liderança técnica imediata.",
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["driver_id"], "felipe")
        self.assertIn("DECISÃO DE FELIPE REGISTRADA NO CANON LEDGER", res["ack_message"])

        # Check state file updated
        updated_state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(updated_state["status"], "COMPLETED")
        self.assertTrue(updated_state["completed"])
        self.assertIn("Opção A", updated_state["chosen_option"])

        # Check Canon Ledger event
        ledger_mgr = CanonLedgerManager()
        ledger = ledger_mgr.load()
        dilemma_ev = next((ev for ev in ledger.get("events", []) if ev.get("event_id") == f"ET{round_num:02d}-M1.5-DILEMMA"), None)
        self.assertIsNotNone(dilemma_ev)
        self.assertIn("Felipe decidiu", dilemma_ev["summary"])

        # Clean up temporary test files
        if state_file.exists():
            state_file.unlink()
        if target_md.exists():
            target_md.unlink()

        # Purge test event from Canon Ledger
        from src.orchestrator_cli import execute_stage_rollback
        execute_stage_rollback(11, scope="semana")

    # -------------------------------------------------------------
    # 2.3 M6: NPCs & Áudios de Voz
    # -------------------------------------------------------------
    def test_m6_prompt_template_integrity(self):
        prompt_path = self.root_dir / "prompts" / "06_cerimonia_podio.md"
        self.assertTrue(prompt_path.exists())
        content = prompt_path.read_text(encoding="utf-8")
        self.assertIn("ATO 1: PARC FERMÉ", content)
        self.assertIn("ATO 2: COOLDOWN ROOM", content)
        self.assertIn("ATO 3: A CERIMÔNIA DO PÓDIO", content)
        self.assertIn("ATO 4: ZONA MISTA", content)
        self.assertIn("DECLARAÇÕES DE NPCS", content)
        self.assertIn("ÁUDIOS DE DEBRIEFING", content)

    # -------------------------------------------------------------
    # 2.4 M8: Crônica de Corrida & Bancada de Lendas
    # -------------------------------------------------------------
    def test_legends_personas_exist(self):
        prost_path = self.root_dir / "personas" / "alain_prost_ex_driver.md"
        mansell_path = self.root_dir / "personas" / "nigel_mansell.md"
        villeneuve_path = self.root_dir / "personas" / "jacques_villeneuve.md"

        self.assertTrue(prost_path.exists(), "Persona Alain Prost missing")
        self.assertTrue(mansell_path.exists(), "Persona Nigel Mansell missing")
        self.assertTrue(villeneuve_path.exists(), "Persona Jacques Villeneuve missing")

        p_txt = prost_path.read_text(encoding="utf-8")
        m_txt = mansell_path.read_text(encoding="utf-8")
        v_txt = villeneuve_path.read_text(encoding="utf-8")

        self.assertIn("Le Professeur", p_txt)
        self.assertIn("Il Leone", m_txt)
        self.assertIn("Notas de 0 a 10", m_txt)
        self.assertIn("Jacques Villeneuve", v_txt)
        self.assertIn("Notas de 0 a 10", v_txt)

    def test_m8_prompt_template_structure(self):
        prompt_path = self.root_dir / "prompts" / "08_repercussao_midia.md"
        self.assertTrue(prompt_path.exists())
        content = prompt_path.read_text(encoding="utf-8")
        self.assertIn("PARTE 1: A CRÔNICA GERAL DO GRANDE PRÊMIO (RACE CHRONICLE)", content)
        self.assertIn("PARTE 2: A BANCADA DE LENDAS DA FÓRMULA 1", content)
        self.assertIn("Alain Prost", content)
        self.assertIn("Nigel Mansell", content)
        self.assertIn("Jacques Villeneuve", content)
        self.assertIn("PARTE 3: REPERCUSSÃO NA IMPRENSA INTERNACIONAL E BRASILEIRA", content)
        self.assertIn("PARTE 4: PODCASTS, YOUTUBE & REDES SOCIAIS", content)


if __name__ == "__main__":
    unittest.main()
