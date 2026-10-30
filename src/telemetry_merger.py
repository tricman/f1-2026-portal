import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from src.models import LapRecord, PitStopEvent, StewardIncident, DriverRaceResult

DRIVER_ID_MAP = {
    "sarahmarinss": ("sarah", "Sarah (SarahMarinsS)", 24, "Mercedes-AMG Petronas"),
    "frdsilva": ("felipe", "Felipe (frdsilva)", 5, "Stake F1 Team Kick Sauber"),
    "davimsson": ("davi", "Davi (DaviMSSon)", 15, "Williams Racing"),
    "alonso": ("alonso", "Fernando Alonso", 14, "Aston Martin Aramco"),
    "hamilton": ("hamilton", "Lewis Hamilton", 44, "Mercedes-AMG Petronas"),
    "verstappen": ("verstappen", "Max Verstappen", 1, "Red Bull Racing"),
    "leclerc": ("leclerc", "Charles Leclerc", 16, "Scuderia Ferrari HP"),
    "norris": ("norris", "Lando Norris", 4, "McLaren Formula 1 Team"),
    "piastri": ("piastri", "Oscar Piastri", 81, "McLaren Formula 1 Team"),
    "pérez": ("perez", "Sergio Pérez", 11, "Red Bull Racing"),
    "perez": ("perez", "Sergio Pérez", 11, "Red Bull Racing"),
    "sainz": ("sainz", "Carlos Sainz", 55, "Scuderia Ferrari HP"),
    "gasly": ("gasly", "Pierre Gasly", 10, "BWT Alpine F1 Team"),
    "hulkenberg": ("hulkenberg", "Nico Hülkenberg", 27, "MoneyGram Haas F1 Team"),
    "hülkenberg": ("hulkenberg", "Nico Hülkenberg", 27, "MoneyGram Haas F1 Team"),
    "stroll": ("stroll", "Lance Stroll", 18, "Aston Martin Aramco"),
    "albon": ("albon", "Alexander Albon", 23, "Williams Racing"),
    "tsunoda": ("tsunoda", "Yuki Tsunoda", 22, "Visa Cash App RB"),
    "ocon": ("ocon", "Esteban Ocon", 31, "BWT Alpine F1 Team"),
    "ricciardo": ("ricciardo", "Daniel Ricciardo", 3, "Visa Cash App RB"),
    "bottas": ("bottas", "Valtteri Bottas", 77, "Stake F1 Team Kick Sauber"),
    "magnussen": ("magnussen", "Kevin Magnussen", 20, "MoneyGram Haas F1 Team"),
}

FIA_RACE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}


def parse_lap_time_ms(time_str: str) -> int:
    """Convert 'M:SS.mmm' or 'SS.mmm' into integer milliseconds."""
    if not time_str or not time_str.strip():
        return 999_999_999
    clean = time_str.strip()
    if ":" in clean:
        mins_part, secs_part = clean.split(":", 1)
        mins = int(mins_part)
        secs = float(secs_part)
        return int(round((mins * 60.0 + secs) * 1000))
    return int(round(float(clean) * 1000))


def normalize_driver(raw_name: str) -> Tuple[str, str, int, str]:
    key = raw_name.strip().lower()
    if key in DRIVER_ID_MAP:
        return DRIVER_ID_MAP[key]
    for k, val in DRIVER_ID_MAP.items():
        if k in key:
            return val
    raise ValueError(f"Unknown driver identifier: {raw_name}")


def parse_pacedex_laps_csv(csv_path: Path) -> List[LapRecord]:
    records: List[LapRecord] = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lap_num = int(row["Volta"])
            pos_val = int(row["Pos"]) if row.get("Pos") and row["Pos"].strip() else None
            car_num = int(row["Nº"])
            driver_raw = row["Piloto"].strip()
            team_raw = row["Equipe"].strip()
            t_str = row["Tempo"].strip()
            t_ms = parse_lap_time_ms(t_str)
            wear = float(row["Desgaste %"]) if row.get("Desgaste %") and row["Desgaste %"].strip() else None
            age = int(row["Idade do pneu"]) if row.get("Idade do pneu") and row["Idade do pneu"].strip() else None
            pits = int(row["Pits"]) if row.get("Pits") and row["Pits"].strip() else None
            records.append(
                LapRecord(
                    lap=lap_num,
                    pos=pos_val,
                    car_number=car_num,
                    driver=driver_raw,
                    team=team_raw,
                    lap_time=t_str,
                    lap_time_ms=t_ms,
                    s1=row.get("S1", "").strip() or None,
                    s2=row.get("S2", "").strip() or None,
                    s3=row.get("S3", "").strip() or None,
                    tyre=row.get("Pneu", "").strip(),
                    tyre_age=age,
                    wear_pct=wear,
                    pits=pits,
                )
            )
    return records


def parse_free_practice_summary(summary_csv: Path, laps_csv: Path) -> Dict[str, Any]:
    laps = parse_pacedex_laps_csv(laps_csv)
    by_driver: Dict[str, List[LapRecord]] = {}
    for rec in laps:
        d_id, _, _, _ = normalize_driver(rec.driver)
        by_driver.setdefault(d_id, []).append(rec)

    classification = []
    leader_ms: Optional[int] = None

    with open(summary_csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pos = int(row["Pos"])
            d_id, d_name, canon_num, canon_team = normalize_driver(row["Piloto"])
            best_lap = row["Melhor volta"].strip()
            best_ms = parse_lap_time_ms(best_lap)
            if leader_ms is None or best_ms < leader_ms:
                leader_ms = best_ms
            d_laps = by_driver.get(d_id, [])
            # Find sectors of the best lap
            best_rec = min(d_laps, key=lambda r: r.lap_time_ms) if d_laps else None
            tyres_used = []
            for r in sorted(d_laps, key=lambda x: x.lap):
                if r.tyre and (not tyres_used or tyres_used[-1] != r.tyre):
                    tyres_used.append(r.tyre)
            max_wear = max((r.wear_pct or 0.0 for r in d_laps), default=0.0)
            gap_s = 0.0 if pos == 1 else (best_ms - (leader_ms or best_ms)) / 1000.0
            classification.append({
                "pos": pos,
                "car_number": canon_num,
                "driver_id": d_id,
                "driver_name": d_name,
                "team": canon_team,
                "laps": int(row["Voltas"]),
                "best_lap": best_lap,
                "gap": "—" if pos == 1 else f"+{gap_s:.3f}s",
                "best_lap_num": best_rec.lap if best_rec else 1,
                "best_s1": best_rec.s1 if best_rec else None,
                "best_s2": best_rec.s2 if best_rec else None,
                "best_s3": best_rec.s3 if best_rec else None,
                "tyre_sequence": " ➔ ".join(tyres_used) if tyres_used else row["Pneu final"].strip(),
                "final_tyre": row["Pneu final"].strip(),
                "pits": int(row["Pits"]),
                "max_wear_pct": round(max_wear, 1),
            })
    return {
        "session_type": "FREE_PRACTICE",
        "total_laps_logged": len(laps),
        "classification": classification,
    }


def merge_race_telemetry(
    summary_csv: Path,
    laps_csv: Path,
    tv_overlay_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge PaceDex Race Summary + PaceDex Lap-by-Lap CSV + TV Screen Overlay Data
    (Grid, Total Time / Gaps, Pit Stop Durations, Stewards Incidents).
    """
    laps = parse_pacedex_laps_csv(laps_csv)
    by_driver: Dict[str, List[LapRecord]] = {}
    for rec in laps:
        d_id, _, _, _ = normalize_driver(rec.driver)
        by_driver.setdefault(d_id, []).append(rec)

    raw_rows = []
    global_fastest_ms = 999_999_999
    global_fastest_driver = ""

    with open(summary_csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_id, d_name, canon_num, canon_team = normalize_driver(row["Piloto"])
            best_str = row["Melhor volta"].strip()
            best_ms = parse_lap_time_ms(best_str)
            if best_ms < global_fastest_ms:
                global_fastest_ms = best_ms
                global_fastest_driver = d_id
            raw_rows.append((row, d_id, d_name, canon_num, canon_team, best_str, best_ms))

    grid_map: Dict[str, int] = tv_overlay_data.get("grid_by_driver", {})
    gap_map: Dict[str, str] = tv_overlay_data.get("time_or_gap_by_driver", {})
    status_map: Dict[str, str] = tv_overlay_data.get("status_by_driver", {})

    results: List[DriverRaceResult] = []
    for row, d_id, d_name, canon_num, canon_team, best_str, best_ms in raw_rows:
        pos = int(row["Pos"])
        d_laps = sorted(by_driver.get(d_id, []), key=lambda x: x.lap)
        best_rec = min(d_laps, key=lambda r: r.lap_time_ms) if d_laps else None
        tyres_used = []
        for r in d_laps:
            if r.tyre and (not tyres_used or tyres_used[-1] != r.tyre):
                tyres_used.append(r.tyre)
        strategy_str = " ➔ ".join(tyres_used) if tyres_used else row["Pneu final"].strip()
        max_wear = max((r.wear_pct or 0.0 for r in d_laps), default=0.0)
        wear_values = [r.wear_pct for r in d_laps if r.wear_pct is not None]
        final_wear = wear_values[-1] if wear_values else 0.0

        grid_pos = grid_map.get(d_id, pos)
        status = status_map.get(d_id, "Finalizada")
        is_fl = (d_id == global_fastest_driver)
        base_pts = FIA_RACE_POINTS.get(pos, 0) if status != "NC" and status != "DSQ" else 0
        fl_bonus = 1 if (is_fl and pos <= 10 and status == "Finalizada") else 0

        results.append(
            DriverRaceResult(
                pos=pos,
                car_number=canon_num,
                driver_id=d_id,
                driver_name=d_name,
                team=canon_team,
                grid=grid_pos,
                pos_delta=grid_pos - pos,
                laps=int(row["Voltas"]),
                stops=int(row["Pits"]),
                tyre_strategy=strategy_str,
                best_lap=best_str,
                best_lap_ms=best_ms,
                best_lap_num=best_rec.lap if best_rec else 1,
                is_fastest_lap=is_fl,
                total_time_or_gap=gap_map.get(d_id, "—"),
                status=status,
                points=base_pts + fl_bonus,
                max_wear_pct=round(max_wear, 1),
                final_wear_pct=round(final_wear, 1),
            )
        )

    # Sort best laps to find the runner-up fastest lap delta
    sorted_by_fl = sorted(results, key=lambda r: r.best_lap_ms)
    fl_winner = sorted_by_fl[0]
    fl_second = sorted_by_fl[1]
    fl_delta_s = (fl_second.best_lap_ms - fl_winner.best_lap_ms) / 1000.0

    pit_stops = tv_overlay_data.get("pit_stops", [])
    fastest_pit = min(pit_stops, key=lambda p: p["stop_duration_s"]) if pit_stops else None

    return {
        "session_type": "RACE",
        "total_laps": max((r.laps for r in results), default=0),
        "fastest_lap_summary": {
            "driver_id": fl_winner.driver_id,
            "driver_name": fl_winner.driver_name,
            "team": fl_winner.team,
            "lap_time": fl_winner.best_lap,
            "lap_number": fl_winner.best_lap_num,
            "runner_up_driver": fl_second.driver_name,
            "runner_up_time": fl_second.best_lap,
            "delta_seconds": round(fl_delta_s, 3),
        },
        "fastest_pit_stop": fastest_pit,
        "classification": [r.to_dict() for r in results],
        "pit_stops": pit_stops,
        "incidents": tv_overlay_data.get("incidents", []),
    }
