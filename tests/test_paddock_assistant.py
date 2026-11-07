"""
Unit and integration tests for the Paddock Personal Assistant & Interactive Q&A Engine (Sprint 4).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.paddock_assistant import (
    PILOT_REGISTRY,
    resolve_driver_identity,
    is_assistant_query,
    classify_query_intent,
    handle_deterministic_standings_query,
    handle_semantic_paddock_query,
    process_paddock_assistant_query,
)
from src.repositories.local_repository import LocalJsonRepository


class TestPaddockAssistantEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="f1_test_assistant_"))
        self.state_dir = self.temp_dir / "data" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.r11_dir = self.temp_dir / "data" / "seasons" / "season_01" / "et_11_austria"
        self.r11_dir.mkdir(parents=True, exist_ok=True)

        # Mock Standings Data
        standings_data = {
            "season": 2026,
            "last_completed_round": 10,
            "drivers_standings": [
                {"pos": 1, "id": "sarah", "name": "Sarah", "points": 197, "wins": 6, "podiums": 7, "poles": 6},
                {"pos": 2, "id": "felipe", "name": "Felipe", "points": 146, "wins": 2, "podiums": 7, "poles": 1},
                {"pos": 6, "id": "davi", "name": "Davi", "points": 83, "wins": 0, "podiums": 4, "poles": 1},
            ],
            "constructors_standings": [
                {"pos": 1, "id": "mercedes", "points": 296, "net_points": 296},
                {"pos": 2, "id": "sauber", "points": 146, "net_points": 146},
                {"pos": 5, "id": "williams", "points": 83, "net_points": 83},
            ],
        }
        (self.state_dir / "standings.json").write_text(json.dumps(standings_data), encoding="utf-8")

        # Mock Canon Ledger
        ledger_data = {
            "events": [
                {
                    "event_id": "ET11-M1-CANON",
                    "round": 11,
                    "module": "M1_SEMANA",
                    "summary": "Audi e Sauber debatem bônus de Felipe enquanto Mercedes blinda Sarah.",
                    "entities": ["felipe", "sarah", "audi", "mercedes"],
                }
            ]
        }
        (self.state_dir / "canon_ledger.json").write_text(json.dumps(ledger_data), encoding="utf-8")

        # Mock Day 1 Chronicle
        (self.r11_dir / "ET11_PRE_A_Semana_da_F1_Dia_1.md").write_text(
            "# A Semana da F1 · Dia 1\nFelipe e Sauber analisaram a telemetria do Red Bull Ring em Hinwil.\n",
            encoding="utf-8",
        )

        self.repo = LocalJsonRepository(root_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_driver_identity(self):
        # 1. Author Felipe
        id_felipe = resolve_driver_identity("frdsilva", "123", "Como estou hoje?")
        self.assertEqual(id_felipe["driver_id"], "felipe")
        self.assertEqual(id_felipe["agent_name"], "Marcus Thorne")

        # 2. Author Sarah
        id_sarah = resolve_driver_identity("SarahMarinsS", "456", "Qual a programação?")
        self.assertEqual(id_sarah["driver_id"], "sarah")
        self.assertEqual(id_sarah["agent_name"], "Jules Moreau")

        # 3. Author Davi
        id_davi = resolve_driver_identity("DaviMSSon", "789", "Aconteceu algo?")
        self.assertEqual(id_davi["driver_id"], "davi")
        self.assertEqual(id_davi["agent_name"], "Chloe Vance")

        # 4. Third-party inquiry: Felipe asks about Sarah
        id_third = resolve_driver_identity("frdsilva", "123", "O que falaram da Sarah esta semana?")
        self.assertEqual(id_third["driver_id"], "sarah")

    def test_is_assistant_query_detection(self):
        # Standings questions
        self.assertTrue(is_assistant_query("Qual é a classificação atualizada?"))
        self.assertTrue(is_assistant_query("quantos pontos eu tenho?"))
        self.assertTrue(is_assistant_query("como está a tabela do campeonato?"))

        # Lore questions
        self.assertTrue(is_assistant_query("Aconteceu algum fato relevante comigo essa semana?"))
        self.assertTrue(is_assistant_query("houve alguma fofoca nos bastidores?"))

        # Bot tag triggers
        self.assertTrue(is_assistant_query("qual o plano?", is_mentioned=True))

        # Ignore game commands
        self.assertFalse(is_assistant_query("avancar dia"))
        self.assertFalse(is_assistant_query("iniciar etapa 11"))
        self.assertFalse(is_assistant_query("coletiva etapa 11"))
        self.assertFalse(is_assistant_query("opcao a"))

    def test_classify_query_intent(self):
        self.assertEqual(classify_query_intent("qual minha pontuação no campeonato?"), "STANDINGS")
        self.assertEqual(classify_query_intent("como está a classificação dos construtores?"), "STANDINGS")
        self.assertEqual(classify_query_intent("aconteceu algo relevante comigo essa semana?"), "PADDOCK_LORE")
        self.assertEqual(classify_query_intent("o que a imprensa falou da minha pilotagem?"), "PADDOCK_LORE")

    def test_deterministic_standings_response(self):
        driver_felipe = PILOT_REGISTRY["felipe"]
        reply = handle_deterministic_standings_query(driver_felipe, repo=self.repo)

        self.assertIn("Felipe (#5)", reply)
        self.assertIn("2º Lugar", reply)
        self.assertIn("146 pontos", reply)
        self.assertIn("Stake F1 Team Kick Sauber / Audi", reply)
        self.assertIn("Portal", reply)

    def test_semantic_lore_with_mock_ai(self):
        driver_felipe = PILOT_REGISTRY["felipe"]
        mock_ai = MagicMock()
        mock_ai.flash_model = "gemini-flash-test"
        mock_ai._call_generate_content.return_value = (
            "Felipe, o Marcus Thorne esteve em Hinwil para blindar seus bônus de contrato da Audi. "
            "A telemetria do Red Bull Ring foi aprovada pelos engenheiros suíços."
        )

        reply = handle_semantic_paddock_query(
            driver_data=driver_felipe,
            query="Aconteceu algo relevante comigo essa semana?",
            round_num=11,
            round_folder="et_11_austria",
            root_dir=self.temp_dir,
            repo=self.repo,
            ai_client=mock_ai,
        )

        self.assertIn("MEMORANDO CONFIDENCIAL • MARCUS THORNE", reply)
        self.assertIn("Marcus Thorne esteve em Hinwil", reply)
        mock_ai._call_generate_content.assert_called_once()

    def test_process_paddock_assistant_query_end_to_end(self):
        mock_ai = MagicMock()
        mock_ai.flash_model = "gemini-flash-test"
        mock_ai._call_generate_content.return_value = "Sem novidades negativas. Semana tranquila em Hinwil."

        # Case 1: Standings query
        res_standings, voice1 = process_paddock_assistant_query(
            author_name="frdsilva",
            author_id="123",
            query_text="Qual é a classificação atualizada?",
            round_num=11,
            round_folder="et_11_austria",
            root_dir=self.temp_dir,
            repo=self.repo,
            ai_client=mock_ai,
        )
        self.assertIn("BRIEFING OFICIAL FIA", res_standings)
        self.assertEqual(voice1, "Marcus Thorne (Staff Felipe)")

        # Case 3: Cross-driver inquiry (Felipe asks about Davi)
        res_cross, voice3 = process_paddock_assistant_query(
            author_name="Felipe Rodrigues",
            author_id="123",
            query_text="E aconteceu algo relevante com o Davi essa semana?",
            round_num=11,
            round_folder="et_11_austria",
            root_dir=self.temp_dir,
            repo=self.repo,
            ai_client=mock_ai,
        )
        self.assertIn("MEMORANDO CONFIDENCIAL • MARCUS THORNE", res_cross)
        self.assertEqual(voice3, "Marcus Thorne (Staff Felipe)")

        # Verify that Gemini was instructed that caller is Felipe and target is Davi
        call_args = mock_ai._call_generate_content.call_args[1]
        self.assertIn("Interlocutor (Seu Piloto): Felipe", call_args["parts"][0]["text"])
        self.assertIn("Alvo da Investigação (Rival): Davi", call_args["parts"][0]["text"])


if __name__ == "__main__":
    unittest.main()

