"""
Unit & Integration Tests for Sprint 3:
1. SQLite Document Store (NoSQL Layer with WAL mode and ACID transactions).
2. Factory resolution (SqliteDocumentRepository vs LocalJsonRepository).
3. Multi-Season Governance & Directory Resolution.
4. Silly Season Transfer Engine & Announcement Generation.
5. New Season Initialization & Zeroed Standings.
6. ChatOps Command Detection for New Season.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.repositories.sqlite_document_repository import SqliteDocumentRepository
from src.repositories.local_repository import LocalJsonRepository
from src.repositories.factory import get_repository
from src.season_manager import (
    DEFAULT_SEASON_ID,
    DEFAULT_NEXT_SEASON_GRID,
    get_season_dir,
    list_available_seasons,
    detect_grid_transfers,
    generate_transfer_announcement,
    initialize_new_season,
)
from src.discord_gateway import detect_stage_command


class TestSprint3SqliteDocumentRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="f1_test_sprint3_sqlite_"))
        self.state_dir = self.temp_dir / "data" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_dir / "data" / "state" / "test_showrunner.db"

        # Pre-seed a JSON file
        sample_standings = {
            "season": 2026,
            "last_completed_round": 10,
            "drivers": [
                {"id": "sarah", "name": "Sarah", "team": "Mercedes", "points": 180},
                {"id": "davi", "name": "Davi", "team": "Williams", "points": 140},
                {"id": "felipe", "name": "Felipe", "team": "Kick Sauber", "points": 120},
            ],
            "constructors": [],
        }
        (self.state_dir / "standings.json").write_text(
            json.dumps(sample_standings, indent=2), encoding="utf-8"
        )

        self.repo = SqliteDocumentRepository(
            root_dir=self.temp_dir,
            db_path=self.db_path,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_initialization_and_wal_mode(self):
        self.assertTrue(self.db_path.exists())
        # Check WAL mode
        with self.repo._get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_auto_seed_from_existing_json(self):
        standings = self.repo.get_standings()
        self.assertEqual(standings.get("season"), 2026)
        self.assertEqual(standings.get("last_completed_round"), 10)
        self.assertEqual(len(standings.get("drivers", [])), 3)

    def test_crud_document_operations(self):
        # Save custom document
        doc_data = {"test_key": "test_val", "score": 99}
        self.repo.save_document("telemetry_cache", "round_11", doc_data)

        # Retrieve
        retrieved = self.repo.get_document("telemetry_cache", "round_11")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.get("score"), 99)

        # Find documents with filter
        docs = self.repo.find_documents("telemetry_cache", {"test_key": "test_val"})
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["doc_id"], "round_11")

        # Delete document
        deleted = self.repo.delete_document("telemetry_cache", "round_11")
        self.assertTrue(deleted)
        self.assertIsNone(self.repo.get_document("telemetry_cache", "round_11"))

    def test_standings_and_json_sync(self):
        new_standings = {
            "season": 2027,
            "last_completed_round": 1,
            "drivers": [{"id": "davi", "team": "Ferrari", "points": 25}],
            "constructors": [],
        }
        self.repo.save_standings(new_standings)

        # In DB
        from_db = self.repo.get_standings()
        self.assertEqual(from_db["season"], 2027)

        # On Disk (auto-sync)
        disk_standings = json.loads((self.state_dir / "standings.json").read_text(encoding="utf-8"))
        self.assertEqual(disk_standings["season"], 2027)

    def test_canon_ledger_and_dilemma_operations(self):
        # Canon event append
        self.repo.append_canon_event({
            "event_id": "TEST-EVENT-001",
            "round_num": 11,
            "module": "TEST",
            "summary": "Evento de teste de persistência",
        })
        events = self.repo.list_canon_events()
        self.assertTrue(any(e.get("event_id") == "TEST-EVENT-001" for e in events))

        # Dilemma choice save & get
        self.repo.save_dilemma_choice(11, {
            "driver_id": "sarah",
            "choice": "Opção B",
            "timestamp": 123456789.0,
        })
        choice = self.repo.get_dilemma_choice(11)
        self.assertEqual(choice.get("choice"), "Opção B")
        self.assertEqual(choice.get("driver_id"), "sarah")


class TestSprint3FactoryAndMultiSeason(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="f1_test_sprint3_seasons_"))
        self.seasons_dir = self.temp_dir / "data" / "seasons"
        self.state_dir = self.temp_dir / "data" / "state"
        self.seasons_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Create season_01
        (self.seasons_dir / "season_01" / "et_10_espanha").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_factory_defaults_to_sqlite(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "sqlite"}):
            repo = get_repository(force_refresh=True)
            self.assertIsInstance(repo, SqliteDocumentRepository)

        with patch.dict(os.environ, {"STORAGE_BACKEND": "json"}):
            repo_json = get_repository(force_refresh=True)
            self.assertIsInstance(repo_json, LocalJsonRepository)

    def test_season_manager_directories_and_listing(self):
        s1_dir = get_season_dir(self.temp_dir, "season_01")
        self.assertTrue(s1_dir.exists())
        self.assertEqual(s1_dir.name, "season_01")

        s2_dir = get_season_dir(self.temp_dir, "season_02")
        self.assertTrue(s2_dir.exists())
        self.assertEqual(s2_dir.name, "season_02")

        seasons = list_available_seasons(self.temp_dir)
        self.assertIn("season_01", seasons)
        self.assertIn("season_02", seasons)

    def test_detect_grid_transfers(self):
        prev_standings = {
            "drivers": [
                {"id": "sarah", "name": "Sarah", "team": "Mercedes-AMG Petronas", "points": 180},
                {"id": "davi", "name": "Davi", "team": "Williams Racing", "points": 140},
                {"id": "felipe", "name": "Felipe", "team": "Kick Sauber", "points": 120},
            ]
        }
        new_grid = [
            {"id": "sarah", "name": "Sarah (SarahMarinsS)", "team": "Mercedes-AMG Petronas", "number": 24},
            {"id": "davi", "name": "Davi (DaviMSSon)", "team": "Scuderia Ferrari HP", "number": 15},
            {"id": "felipe", "name": "Felipe (frdsilva)", "team": "Audi Revolut F1 Team", "number": 5},
            {"id": "bearman", "name": "Oliver Bearman", "team": "MoneyGram Haas F1 Team", "number": 87},
        ]

        transfers = detect_grid_transfers(prev_standings, new_grid)
        # Sarah stayed at Mercedes -> no transfer
        # Davi moved Williams -> Ferrari -> transfer
        # Felipe moved Kick Sauber -> Audi -> transfer
        # Bearman not in prev -> rookie arrival
        driver_ids = [t["driver_id"] for t in transfers]
        self.assertNotIn("sarah", driver_ids)
        self.assertIn("davi", driver_ids)
        self.assertIn("felipe", driver_ids)
        self.assertIn("bearman", driver_ids)

        davi_t = next(t for t in transfers if t["driver_id"] == "davi")
        self.assertEqual(davi_t["type"], "TRANSFER")
        self.assertEqual(davi_t["old_team"], "Williams Racing")
        self.assertEqual(davi_t["new_team"], "Scuderia Ferrari HP")

    def test_generate_transfer_announcement_fallback(self):
        transfer = {
            "type": "TRANSFER",
            "driver_id": "davi",
            "driver_name": "Davi",
            "old_team": "Williams Racing",
            "new_team": "Scuderia Ferrari HP",
            "number": 15,
        }
        mock_ai = MagicMock()
        mock_ai._call_generate_content.side_effect = Exception("API rate limited")

        ann_path = generate_transfer_announcement(
            root_dir=self.temp_dir,
            transfer=transfer,
            season_id="season_02",
            ai_client=mock_ai,
        )
        self.assertTrue(ann_path.exists())
        content = ann_path.read_text(encoding="utf-8")
        self.assertIn("BOMBA NO MERCADO", content)
        self.assertIn("DAVI", content)
        self.assertIn("FERRARI", content)

    def test_initialize_new_season_full_flow(self):
        # Setup previous standings
        prev_standings = {
            "season": 2026,
            "last_completed_round": 10,
            "drivers": [
                {"id": "sarah", "name": "Sarah", "team": "Mercedes-AMG Petronas", "points": 180},
                {"id": "davi", "name": "Davi", "team": "Williams Racing", "points": 140},
                {"id": "felipe", "name": "Felipe", "team": "Kick Sauber", "points": 120},
            ],
            "constructors": [],
        }
        (self.state_dir / "standings.json").write_text(
            json.dumps(prev_standings, indent=2), encoding="utf-8"
        )

        mock_ai = MagicMock()
        mock_ai._call_generate_content.return_value = "Comunicado Oficial F1 TV: Transferência confirmada!"

        res = initialize_new_season(
            root_dir=self.temp_dir,
            new_season_id="season_02",
            new_grid_registry=DEFAULT_NEXT_SEASON_GRID,
            prev_season_id="season_01",
            ai_client=mock_ai,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["new_season_id"], "season_02")
        self.assertEqual(res["season_year"], 2027)
        self.assertGreaterEqual(res["transfers_count"], 2)

        # Check season 02 directory and files
        s2_dir = self.temp_dir / "data" / "seasons" / "season_02"
        self.assertTrue((s2_dir / "standings_initial.json").exists())
        self.assertTrue((s2_dir / "transfers").exists())

        s2_standings = json.loads((s2_dir / "standings_initial.json").read_text(encoding="utf-8"))
        self.assertEqual(s2_standings["season"], 2027)
        self.assertEqual(s2_standings["last_completed_round"], 0)
        # All drivers should start with 0 points
        for d in s2_standings["drivers"]:
            self.assertEqual(d["points"], 0)


class TestSprint3ChatOpsNewSeason(unittest.TestCase):
    def test_chatops_new_season_detection(self):
        cmd1 = detect_stage_command("nova temporada 2")
        self.assertIsNotNone(cmd1)
        self.assertEqual(cmd1[0], "START_NEW_SEASON")
        self.assertEqual(cmd1[1], 2)
        self.assertEqual(cmd1[2], "season_02")

        cmd2 = detect_stage_command("iniciar nova temporada season_03")
        self.assertIsNotNone(cmd2)
        self.assertEqual(cmd2[0], "START_NEW_SEASON")
        self.assertEqual(cmd2[1], 3)
        self.assertEqual(cmd2[2], "season_03")

        cmd3 = detect_stage_command("iniciar nova temporada 2")
        self.assertIsNotNone(cmd3)
        self.assertEqual(cmd3[0], "START_NEW_SEASON")
        self.assertEqual(cmd3[1], 2)
        self.assertEqual(cmd3[2], "season_02")


if __name__ == "__main__":
    unittest.main()
