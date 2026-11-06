import unittest
import json
from pathlib import Path
from src.telemetry_merger import (
    parse_lap_time_ms,
    parse_free_practice_summary,
    merge_race_telemetry,
)
from src.fia_calculator import update_championship_standings
from src.canon_ledger import sample_weekly_themes, select_press_conference_panel
from src.discord_gateway import split_markdown_for_discord, detect_stage_command
from src.orchestrator_cli import resolve_persona_for_filename
from src.table_renderer import transform_markdown_tables_for_discord
from src.portal_builder import build_editorial_portal

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestFIAEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.standings_et9 = json.loads(
            (ROOT_DIR / "data" / "state" / "standings.json").read_text(encoding="utf-8")
        )
        self.standings_et9["last_completed_round"] = 9
        for d in self.standings_et9.get("drivers_standings", []):
            if "points_anterior" in d:
                d["points"] = d["points_anterior"]
        for c in self.standings_et9.get("constructors_standings", []):
            if "points_round" in c:
                round_pts = c.get("points_round", 0)
                c["gross_points"] = c.get("gross_points", 0) - round_pts
                c["net_points"] = c.get("net_points", 0) - round_pts
        self.tv_overlay_et10 = json.loads(
            (
                ROOT_DIR
                / "data"
                / "seasons"
                / "season_01"
                / "et_10_espanha"
                / "telemetry"
                / "tv_overlay_et10.json"
            ).read_text(encoding="utf-8")
        )

    def test_parse_lap_time_ms(self) -> None:
        self.assertEqual(parse_lap_time_ms("1:17.035"), 77035)
        self.assertEqual(parse_lap_time_ms("1:17.039"), 77039)
        self.assertEqual(parse_lap_time_ms("0:56.252"), 56252)

    def test_free_practice_parser_et10(self) -> None:
        tel_dir = ROOT_DIR / "data" / "seasons" / "season_01" / "et_10_espanha" / "telemetry"
        fp_data = parse_free_practice_summary(
            tel_dir / "pacedex_catalunya-espanha_2026-10-17_TL.csv",
            tel_dir / "pacedex_catalunya-espanha_2026-10-17_laps_TL.csv",
        )
        self.assertEqual(fp_data["session_type"], "FREE_PRACTICE")
        self.assertEqual(len(fp_data["classification"]), 20)
        p1 = fp_data["classification"][0]
        p2 = fp_data["classification"][1]
        self.assertEqual(p1["driver_id"], "alonso")
        self.assertEqual(p1["best_lap"], "1:16.969")
        self.assertEqual(p2["driver_id"], "davi")
        self.assertEqual(p2["best_lap"], "1:16.991")
        self.assertEqual(p2["gap"], "+0.022s")

    def test_merge_race_telemetry_and_standings_et10(self) -> None:
        tel_dir = ROOT_DIR / "data" / "seasons" / "season_01" / "et_10_espanha" / "telemetry"
        merged = merge_race_telemetry(
            tel_dir / "pacedex_catalunya-espanha_2026-10-17.csv",
            tel_dir / "pacedex_catalunya-espanha_2026-10-17_laps.csv",
            self.tv_overlay_et10,
        )
        self.assertEqual(merged["total_laps"], 17)
        fl = merged["fastest_lap_summary"]
        self.assertEqual(fl["driver_id"], "sarah")
        self.assertEqual(fl["lap_time"], "1:17.035")
        self.assertEqual(fl["delta_seconds"], 0.004)

        fastest_pit = merged.get("fastest_pit_stop")
        if fastest_pit:
            self.assertEqual(fastest_pit["driver"], "Felipe (frdsilva)")
            self.assertEqual(fastest_pit["stop_duration_s"], 2.434)

        # Verify updated standings after Round 10 (Spain)
        updated = update_championship_standings(
            self.standings_et9,
            merged,
            round_number=10,
            gp_name="GP da Espanha (Barcelona)",
        )
        drivers_by_id = {d["id"]: d for d in updated["drivers_standings"]}
        self.assertEqual(drivers_by_id["sarah"]["points"], 171 + 26)   # 197
        self.assertEqual(drivers_by_id["felipe"]["points"], 131 + 15)  # 146
        self.assertEqual(drivers_by_id["alonso"]["points"], 104 + 10)  # 114
        self.assertEqual(drivers_by_id["verstappen"]["points"], 94 + 8) # 102
        self.assertEqual(drivers_by_id["hamilton"]["points"], 97 + 2)   # 99
        self.assertEqual(drivers_by_id["leclerc"]["points"], 83 + 0)    # 83
        self.assertEqual(drivers_by_id["davi"]["points"], 65 + 18)      # 83 (Tied with Leclerc, Davi has 3 podiums vs 2!)

        teams_by_id = {t["team_id"]: t for t in updated["constructors_standings"]}
        self.assertEqual(teams_by_id["mercedes"]["net_points"], 268 + 28)     # 296
        self.assertEqual(teams_by_id["sauber"]["net_points"], 131 + 15)       # 146
        self.assertEqual(teams_by_id["red_bull"]["net_points"], 123 + 12)     # 135 (8 Max + 4 Perez)
        self.assertEqual(teams_by_id["mclaren"]["net_points"], 110 + 18)      # 128 (12 Piastri + 6 Norris)
        self.assertEqual(teams_by_id["aston_martin"]["net_points"], 105 + 10) # 115
        self.assertEqual(teams_by_id["ferrari"]["net_points"], 98 + 1)        # 99
        self.assertEqual(teams_by_id["williams"]["net_points"], 65 + 18)      # 83

        # Verify Idempotency guard raises if Round 10 is applied twice
        with self.assertRaises(ValueError):
            update_championship_standings(
                updated, merged, round_number=10, gp_name="GP da Espanha (Barcelona)"
            )

    def test_rng_theme_sampling_no_duplicates(self) -> None:
        themes = sample_weekly_themes(round_number=10, team_id="mercedes")
        self.assertEqual(len(set(themes.values())), 4)

    def test_discord_markdown_chunking(self) -> None:
        sample_md = "\n".join([f"Linha de teste número {i} com dados da FIA." for i in range(150)])
        chunks = split_markdown_for_discord(sample_md, max_chars=1950)
        self.assertTrue(len(chunks) >= 3)
        for c in chunks:
            self.assertLessEqual(len(c), 1950)

    def test_persona_resolution_for_discord(self) -> None:
        self.assertEqual(
            resolve_persona_for_filename("Etapa 10 - Relatório Oficial FIA - Treino Livre - GP da Espanha 2026.md"),
            "FIA Technical Delegate — Jo Bauer",
        )
        self.assertEqual(
            resolve_persona_for_filename("Etapa 10 - Pós - Repercussão Imprensa e Internet - GP da Espanha 2026.md"),
            "Global F1 Media Hub (Band / Sky / Gazzetta / X)",
        )

    def test_table_renderer_mobile_cards_and_png(self) -> None:
        race_md_path = (
            ROOT_DIR
            / "data"
            / "seasons"
            / "season_01"
            / "et_10_espanha"
            / "Etapa 10 - Relatório Oficial FIA - Resultado Final - GP da Espanha 2026.md"
        )
        raw_md = race_md_path.read_text(encoding="utf-8")
        transformed_md, images = transform_markdown_tables_for_discord(raw_md)
        self.assertNotIn("| :--- |", transformed_md)
        self.assertIn("🔹 **1**", transformed_md)
        self.assertGreaterEqual(len(images), 1)
        for fname, png_bytes in images:
            self.assertTrue(fname.endswith(".png"))
            self.assertTrue(png_bytes.startswith(b"\x89PNG"))

    def test_build_editorial_portal(self) -> None:
        portal_path = build_editorial_portal(ROOT_DIR)
        self.assertTrue(portal_path.exists())
        html = portal_path.read_text(encoding="utf-8")
        self.assertIn("PADDOCK INSIDER & FIA WIKI", html)
        self.assertIn("et_10_espanha", html)
        self.assertIn("SarahMarinsS", html)

    def test_detect_stage_commands(self) -> None:
        self.assertEqual(detect_stage_command("inicio da etapa 10"), ("START", 10))
        self.assertEqual(detect_stage_command("Início da Etapa 11"), ("START", 11))
        self.assertEqual(detect_stage_command("final da etapa 10"), ("END", 10))
        self.assertEqual(detect_stage_command("fim da etapa"), ("END", None))
        self.assertIsNone(detect_stage_command("Que corrida absurda hoje!"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

