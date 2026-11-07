"""
Unit and Integration Tests for Sprint 1 Deliverables:
  - 1.1 ChatOps Telemetry Listener ('iniciar escuta f1', 'status telemetria', 'parar escuta f1')
  - 1.2 Granular Stage Rollback ('execute_stage_rollback', confirmation flow, safety guard)
  - 1.3 Press Conference Turn-Lock Timeout Contingency ('force_timeout_answer', 'forcar avanco coletiva')
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.discord_gateway import detect_stage_command
from src.orchestrator_cli import (
    execute_stage_rollback,
    get_udp_listener_status,
    is_pid_running,
    start_udp_listener,
    stop_udp_listener,
)
from src.press_conference import PressConferenceSession


class TestSprint1ChatOpsAndAutomation(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent

    # -------------------------------------------------------------
    # 1.1 ChatOps Command Detection Tests
    # -------------------------------------------------------------
    def test_detect_stage_command_udp_listener(self):
        cmd1 = detect_stage_command("iniciar escuta f1")
        self.assertEqual(cmd1[0], "START_UDP_LISTENER")

        cmd2 = detect_stage_command("escutar corrida")
        self.assertEqual(cmd2[0], "START_UDP_LISTENER")

        cmd3 = detect_stage_command("status telemetria")
        self.assertEqual(cmd3[0], "STATUS_UDP_LISTENER")

        cmd4 = detect_stage_command("status escuta")
        self.assertEqual(cmd4[0], "STATUS_UDP_LISTENER")

        cmd5 = detect_stage_command("parar escuta f1")
        self.assertEqual(cmd5[0], "STOP_UDP_LISTENER")

        cmd6 = detect_stage_command("encerrar escuta")
        self.assertEqual(cmd6[0], "STOP_UDP_LISTENER")

    def test_detect_stage_command_rollback(self):
        cmd1 = detect_stage_command("rollback etapa 11 sessao")
        self.assertEqual(cmd1, ("STAGE_ROLLBACK", 11, "sessao"))

        cmd2 = detect_stage_command("rollback etapa 12 tudo")
        self.assertEqual(cmd2, ("STAGE_ROLLBACK", 12, "tudo"))

        cmd3 = detect_stage_command("reverter etapa 11 coletiva")
        self.assertEqual(cmd3, ("STAGE_ROLLBACK", 11, "coletiva"))

        cmd4 = detect_stage_command("rollback etapa 11")
        self.assertEqual(cmd4, ("STAGE_ROLLBACK", 11, "sessao"))

        cmd5 = detect_stage_command("confirmar rollback")
        self.assertEqual(cmd5[0], "CONFIRM_ROLLBACK")

        cmd6 = detect_stage_command("cancelar rollback")
        self.assertEqual(cmd6[0], "CANCEL_ROLLBACK")

    def test_detect_stage_command_press_conference_timeout(self):
        cmd1 = detect_stage_command("forcar avanco coletiva")
        self.assertEqual(cmd1[0], "FORCE_PRESS_CONF_ADVANCE")

        cmd2 = detect_stage_command("forçar avanço coletiva")
        self.assertEqual(cmd2[0], "FORCE_PRESS_CONF_ADVANCE")

        cmd3 = detect_stage_command("timeout coletiva")
        self.assertEqual(cmd3[0], "FORCE_PRESS_CONF_ADVANCE")

    def test_legacy_commands_unaffected(self):
        self.assertEqual(detect_stage_command("inicio da etapa 10"), ("START", 10))
        self.assertEqual(detect_stage_command("final da etapa 10"), ("END", 10))
        self.assertEqual(detect_stage_command("inicio semana etapa 11"), ("START_SEMANA", 11))
        self.assertEqual(detect_stage_command("avancar dia"), ("TICK_SEMANA", None))
        self.assertIsNone(detect_stage_command("Belo papo no paddock hoje!"))

    # -------------------------------------------------------------
    # 1.2 Granular Stage Rollback Tests
    # -------------------------------------------------------------
    def test_rollback_safety_guard_prevents_legacy_corruption(self):
        # Rounds 1 to 10 are strictly immutable
        for r in range(1, 11):
            with self.assertRaises(ValueError) as ctx:
                execute_stage_rollback(round_num=r, scope="sessao")
            self.assertIn("Proteção de integridade", str(ctx.exception))

    def test_rollback_invalid_scope_rejection(self):
        with self.assertRaises(ValueError) as ctx:
            execute_stage_rollback(round_num=11, scope="qualquer_coisa")
        self.assertIn("Escopo de rollback inválido", str(ctx.exception))

    def test_rollback_execution_granular_sessao(self):
        # Create temporary dummy files in isolated test season
        test_season = "season_test_rollback"
        round_dir = self.root_dir / "data" / "seasons" / test_season / "et_11_austria"
        tel_dir = round_dir / "telemetry"
        photos_dir = round_dir / "photos"
        deb_dir = round_dir / "debriefing"
        tel_dir.mkdir(parents=True, exist_ok=True)
        photos_dir.mkdir(parents=True, exist_ok=True)
        deb_dir.mkdir(parents=True, exist_ok=True)

        dummy_csv = tel_dir / "test_telemetry.csv"
        dummy_csv.write_text("lap,time\n1,70.5\n", encoding="utf-8")

        dummy_photo = photos_dir / "test_tv.jpg"
        dummy_photo.write_bytes(b"\xff\xd8\xff\xe0")

        dummy_m5 = round_dir / "Etapa 11 - Relatório Oficial FIA - Resultado Final - GP da Áustria 2026.md"
        dummy_m5.write_text("# Resultado Final Etapa 11", encoding="utf-8")

        dummy_m1 = round_dir / "Etapa 11 - Dossiê de Bastidores - Semana das Equipes - GP da Áustria 2026.md"
        dummy_m1.write_text("# Semana das Equipes Etapa 11", encoding="utf-8")

        try:
            # Execute rollback for scope 'sessao'
            res = execute_stage_rollback(round_num=11, scope="sessao", season_id=test_season)
            self.assertTrue(res["success"])
            self.assertEqual(res["scope"], "sessao")

            # M5, photos, and telemetry must be deleted; M1 must be PRESERVED
            self.assertFalse(dummy_csv.exists())
            self.assertFalse(dummy_photo.exists())
            self.assertFalse(dummy_m5.exists())
            self.assertTrue(dummy_m1.exists(), "M1 should be preserved in scope 'sessao'")

            # Now execute rollback 'semana'
            res_sem = execute_stage_rollback(round_num=11, scope="semana", season_id=test_season)
            self.assertTrue(res_sem["success"])
            self.assertFalse(dummy_m1.exists(), "M1 should be deleted in scope 'semana'")
        finally:
            import shutil
            test_s_dir = self.root_dir / "data" / "seasons" / test_season
            if test_s_dir.exists():
                shutil.rmtree(test_s_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1.3 Press Conference Turn-Lock Timeout Contingency Tests
    # -------------------------------------------------------------
    def test_press_conference_force_timeout_answer(self):
        pc_sess = PressConferenceSession(self.root_dir, 11, "et_11_austria")
        pc_sess.state["status"] = "AWAITING_PILOT_REPLY"
        pc_sess.state["waiting_for_driver"] = "felipe"
        pc_sess.state["waiting_for_driver_name"] = "Felipe"
        pc_sess.state["pending_question_text"] = "🎙️ **[Pergunta 2 | Mariana Becker para Felipe]:** Como avalia o ritmo?"
        pc_sess.state["current_question_idx"] = 2
        pc_sess.state["question_plan"] = [
            {"driver_id": "verstappen", "journalist": {"name": "Ted Kravitz", "outlet": "Sky Sports"}},
            {"driver_id": "felipe", "journalist": {"name": "Mariana Becker", "outlet": "Band"}},
            {"driver_id": "sarah", "journalist": {"name": "Martin Brundle", "outlet": "Sky Sports"}},
        ]

        # Trigger fallback synthetic answer
        ack = pc_sess.force_timeout_answer(reason="teste unitario de timeout")
        self.assertIsNotNone(ack)
        self.assertIn("RESPOSTA DE FELIPE REGISTRADA NA ATA DA FIA", ack)
        self.assertEqual(pc_sess.state.get("status"), "IN_PROGRESS")
        self.assertIsNone(pc_sess.state.get("waiting_for_driver"))

        # Clean up temporary press conference state
        temp_state_file = self.root_dir / "data" / "state" / "press_conf_et11.json"
        if temp_state_file.exists():
            temp_state_file.unlink()

    # -------------------------------------------------------------
    # 1.4 Listener PID Lifecycle Check
    # -------------------------------------------------------------
    def test_listener_status_when_inactive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            active, msg = get_udp_listener_status(tmp_root)
            self.assertFalse(active)
            self.assertIn("INATIVO", msg)


if __name__ == "__main__":
    unittest.main()

