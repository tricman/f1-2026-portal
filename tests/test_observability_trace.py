"""
Unit & Integration Tests for Observability Engine & TRACE Logging (Sprint O1).
Validates:
  1. TRACE severity level filtering and dynamic level toggling.
  2. JSON Lines emission to logs/trace.log with secret redaction.
  3. Context Tracing with contextvars and @trace_span nesting.
  4. Precise duration_ms calculation and parent_span_id hierarchy.
  5. Purge routine for rotated log lifecycle management.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.logger import (
    set_log_level,
    get_log_level,
    is_trace_enabled,
    trace,
    info,
    error,
    sanitize_secrets,
    purge_old_trace_logs,
    close_trace_handler,
)
from src.tracer import (
    generate_trace_id,
    generate_span_id,
    get_current_trace_id,
    get_current_span_id,
    get_current_parent_span_id,
    set_trace_context,
    clear_trace_context,
    trace_span,
)


class TestObservabilityTraceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_logs_dir = Path(tempfile.mkdtemp(prefix="f1_trace_logs_"))
        self.patcher_logs = patch("src.logger.LOGS_DIR", self.temp_logs_dir)
        self.patcher_trace_file = patch("src.logger.TRACE_LOG_FILE", self.temp_logs_dir / "trace.log")
        self.patcher_showrunner_file = patch("src.logger.SHOWRUNNER_LOG_FILE", self.temp_logs_dir / "showrunner.log")
        self.patcher_handler = patch("src.logger._trace_handler", None)
        self.patcher_logs.start()
        self.patcher_trace_file.start()
        self.patcher_showrunner_file.start()
        self.patcher_handler.start()

        clear_trace_context()
        set_log_level("INFO")

    def tearDown(self):
        close_trace_handler()
        clear_trace_context()
        set_log_level("INFO")
        self.patcher_logs.stop()
        self.patcher_trace_file.stop()
        self.patcher_showrunner_file.stop()
        self.patcher_handler.stop()
        shutil.rmtree(self.temp_logs_dir, ignore_errors=True)

    def test_log_level_switching(self):
        self.assertFalse(is_trace_enabled())
        self.assertEqual(get_log_level(), 20)  # INFO

        set_log_level("TRACE")
        self.assertTrue(is_trace_enabled())
        self.assertEqual(get_log_level(), 5)

        set_log_level("DEBUG")
        self.assertFalse(is_trace_enabled())
        self.assertEqual(get_log_level(), 10)

        set_log_level("ERROR")
        self.assertEqual(get_log_level(), 40)

    def test_trace_logging_to_trace_log_file(self):
        set_log_level("TRACE")
        trace_file = self.temp_logs_dir / "trace.log"
        showrunner_file = self.temp_logs_dir / "showrunner.log"

        trace("Payload bruto recebido", event="RAW_PAYLOAD", details={"bytes": 1024, "data": "test"})
        info("Operação de rotina concluída", event="OP_DONE")

        self.assertTrue(trace_file.exists())
        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["severity"], "TRACE")
        self.assertEqual(lines[0]["event"], "RAW_PAYLOAD")
        self.assertEqual(lines[0]["details"]["bytes"], 1024)

        self.assertEqual(lines[1]["severity"], "INFO")
        self.assertEqual(lines[1]["event"], "OP_DONE")

        # Verify that TRACE log was NOT written to showrunner.log
        if showrunner_file.exists():
            sh_text = showrunner_file.read_text(encoding="utf-8")
            self.assertNotIn("RAW_PAYLOAD", sh_text)
            self.assertIn("OP_DONE", sh_text)

    def test_trace_disabled_drops_trace_logs(self):
        set_log_level("INFO")
        trace_file = self.temp_logs_dir / "trace.log"

        trace("Isto nao deve ser gravado", event="SHOULD_DROP")
        self.assertFalse(trace_file.exists() and trace_file.read_text(encoding="utf-8").strip() != "")

    def test_secret_redaction(self):
        fake_gemini_key = "AIzaSyD-abc123456789012345678901234567"
        fake_discord_token = "Bot MTA1Mzg3NjUzNTcyNTk4OTk5MA.GYX89a.sampleSampleSampleSampleSampleSample"
        
        raw_msg = f"Requisicao disparada com key {fake_gemini_key} e {fake_discord_token}"
        clean_msg = sanitize_secrets(raw_msg)

        self.assertNotIn(fake_gemini_key, clean_msg)
        self.assertNotIn(fake_discord_token, clean_msg)
        self.assertIn("REDACTED", clean_msg)

        # Dictionary sanitization
        data = {
            "api_key": "secret_key_12345",
            "normal_field": "public_data",
            "nested": {"discord_token": "token_abc"},
        }
        clean_data = sanitize_secrets(data)
        self.assertEqual(clean_data["api_key"], "[REDACTED_SECRET]")
        self.assertEqual(clean_data["normal_field"], "public_data")
        self.assertEqual(clean_data["nested"]["discord_token"], "[REDACTED_SECRET]")

    def test_contextvars_tracing_and_span_hierarchy(self):
        set_log_level("TRACE")
        trace_file = self.temp_logs_dir / "trace.log"

        @trace_span("inner_step", extract_args=True)
        def inner_function(x: int) -> int:
            time.sleep(0.01)
            trace(f"Executando passo interno com {x}", step=x)
            return x * 2

        @trace_span("outer_pipeline")
        def outer_function():
            trace("Iniciando pipeline externa")
            val = inner_function(10)
            trace("Finalizando pipeline externa", result=val)
            return val

        res = outer_function()
        self.assertEqual(res, 20)

        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        # Verify trace_id is consistent across all spans and entries
        trace_ids = {l.get("trace_id") for l in lines if "trace_id" in l}
        self.assertEqual(len(trace_ids), 1)
        root_trace_id = list(trace_ids)[0]
        self.assertIsNotNone(root_trace_id)

        # Verify inner_step has parent_span_id pointing to outer_pipeline's span_id
        outer_start = next(l for l in lines if l.get("event") == "SPAN_START" and l.get("span_name") == "outer_pipeline")
        inner_start = next(l for l in lines if l.get("event") == "SPAN_START" and l.get("span_name") == "inner_step")
        self.assertEqual(inner_start.get("parent_span_id"), outer_start.get("span_id"))

        # Verify duration_ms is recorded on SPAN_END
        outer_end = next(l for l in lines if l.get("event") == "SPAN_END" and l.get("span_name") == "outer_pipeline")
        self.assertIn("duration_ms", outer_end)
        self.assertGreater(outer_end["duration_ms"], 5.0)

    def test_trace_span_error_handling(self):
        set_log_level("TRACE")
        trace_file = self.temp_logs_dir / "trace.log"

        @trace_span("failing_operation")
        def failing_function():
            raise ValueError("Simulacao de falha de I/O de telemetria")

        with self.assertRaises(ValueError):
            failing_function()

        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        error_span = next(l for l in lines if l.get("event") == "SPAN_ERROR")
        self.assertEqual(error_span["span_name"], "failing_operation")
        self.assertIn("duration_ms", error_span)
        self.assertEqual(error_span["error_type"], "ValueError")

    def test_purge_old_trace_logs(self):
        # Create dummy rotated files
        now = time.time()
        f1 = self.temp_logs_dir / "trace.log.1"
        f2 = self.temp_logs_dir / "trace.log.2"
        f3 = self.temp_logs_dir / "trace.log.3"
        f1.write_text("x" * 100, encoding="utf-8")
        f2.write_text("y" * 100, encoding="utf-8")
        f3.write_text("z" * 100, encoding="utf-8")

        # Artificially age f3 by 10 days
        os.utime(f3, (now - 10 * 86400, now - 10 * 86400))

        # Purge with max_days=7 and max_files=2
        purge_res = purge_old_trace_logs(self.temp_logs_dir, max_days=7, max_files=2)
        self.assertGreaterEqual(purge_res["deleted_files_count"], 1)
        self.assertFalse(f3.exists())

    def test_sqlite_layer_instrumentation(self):
        set_log_level("TRACE")
        from src.repositories.sqlite_document_repository import SqliteDocumentRepository
        db = SqliteDocumentRepository(root_dir=self.temp_logs_dir, db_path=self.temp_logs_dir / "test.db")

        db.save_document("test_col", "doc_1", {"name": "Audit Test"})
        doc = db.get_document("test_col", "doc_1")
        self.assertIsNotNone(doc)
        docs = db.find_documents("test_col", {"name": "Audit Test"})
        self.assertEqual(len(docs), 1)
        deleted = db.delete_document("test_col", "doc_1")
        self.assertTrue(deleted)

        trace_file = self.temp_logs_dir / "trace.log"
        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        events = [l.get("event") for l in lines]
        self.assertIn("SQLITE_SAVE_DOC", events)
        self.assertIn("SQLITE_GET_DOC", events)
        self.assertIn("SQLITE_FIND_DOCS", events)
        self.assertIn("SQLITE_DELETE_DOC", events)

    @patch("urllib.request.urlopen")
    def test_gemini_layer_instrumentation(self, mock_urlopen):
        set_log_level("TRACE")
        from src.ai_showrunner import GeminiFreeTierClient

        # Setup mock response
        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.read.return_value = json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Texto gerado em teste de observabilidade"}]}
            }]
        }).encode("utf-8")

        client = GeminiFreeTierClient(api_key="fake_test_key_gemini")
        res = client._call_generate_content(
            model="gemini-flash-test",
            parts=[{"text": "Escreva um resumo de TL"}],
        )
        self.assertIn("Texto gerado em teste", res)

        trace_file = self.temp_logs_dir / "trace.log"
        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        events = [l.get("event") for l in lines]
        self.assertIn("LLM_DISPATCH", events)
        self.assertIn("LLM_RESPONSE", events)

        span_names = [l.get("span_name") for l in lines]
        self.assertIn("gemini_generate_content", span_names)

    @patch("urllib.request.urlopen")
    def test_discord_layer_instrumentation(self, mock_urlopen):
        set_log_level("TRACE")
        from src.discord_gateway import DiscordGatewayClient

        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"id": "msg_9999", "content": "Ok"}).encode("utf-8")

        gw = DiscordGatewayClient()
        gw.bot_token = "fake_token_discord"
        res = gw._request_with_backoff("https://discord.com/api/v10/channels/123/messages", method="POST", payload={"content": "Oi"})
        self.assertEqual(res.get("id"), "msg_9999")

        trace_file = self.temp_logs_dir / "trace.log"
        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        events = [l.get("event") for l in lines]
        self.assertIn("DISCORD_HTTP_REQUEST", events)
        self.assertIn("DISCORD_HTTP_RESPONSE", events)

    def test_fia_calculator_layer_instrumentation(self):
        set_log_level("TRACE")
        from src.fia_calculator import update_championship_standings

        sample_prev = {
            "last_completed_round": 0,
            "last_completed_gp": "Inicio",
            "drivers_standings": [
                {
                    "pos": 1, "id": "sarah", "name": "Sarah", "points": 0, "wins": 0,
                    "podiums": 0, "poles": 0, "fastest_laps": 0, "points_by_round": [],
                    "team_id": "mercedes"
                },
                {
                    "pos": 2, "id": "hamilton", "name": "Hamilton", "points": 0, "wins": 0,
                    "podiums": 0, "poles": 0, "fastest_laps": 0, "points_by_round": [],
                    "team_id": "mercedes"
                }
            ],
            "constructors_standings": [
                {
                    "pos": 1, "team_id": "mercedes", "name": "Mercedes", "gross_points": 0,
                    "net_points": 0, "drivers": ["sarah", "hamilton"], "team_wins": 0
                }
            ]
        }
        sample_race = {
            "classification": [
                {"driver_id": "sarah", "pos": 1, "grid": 1, "status": "Finalizada", "points": 25, "is_fastest_lap": False},
                {"driver_id": "hamilton", "pos": 2, "grid": 2, "status": "Finalizada", "points": 18, "is_fastest_lap": False}
            ]
        }

        res = update_championship_standings(sample_prev, sample_race, round_number=1, gp_name="GP do Bahrein")
        self.assertEqual(res["last_completed_round"], 1)

        trace_file = self.temp_logs_dir / "trace.log"
        lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").strip().split("\n")]
        events = [l.get("event") for l in lines]
        self.assertIn("FIA_STANDINGS_COMPUTED", events)


if __name__ == "__main__":
    unittest.main()
