import copy
import json
from pathlib import Path
from typing import Dict, Any, List


def update_championship_standings(
    previous_standings: Dict[str, Any],
    race_merged: Dict[str, Any],
    round_number: int,
    gp_name: str,
) -> Dict[str, Any]:
    """
    Deterministically compute updated Drivers' and Constructors' standings
    after `round_number`, enforcing the FIA mathematical invariant:
    sum(team_drivers_points) + fia_penalty_points == constructor_net_points.
    """
    state = copy.deepcopy(previous_standings)

    # Idempotency guard: if already at or past round_number, truncate or raise
    if state.get("last_completed_round", 0) >= round_number:
        raise ValueError(
            f"Idempotency violation: Round {round_number} has already been processed "
            f"(last_completed_round={state.get('last_completed_round')})."
        )

    race_by_driver: Dict[str, Dict[str, Any]] = {
        row["driver_id"]: row for row in race_merged["classification"]
    }

    prev_driver_pos = {d["id"]: d["pos"] for d in state["drivers_standings"]}
    prev_team_pos = {t["team_id"]: t["pos"] for t in state["constructors_standings"]}

    team_round_points: Dict[str, int] = {t["team_id"]: 0 for t in state["constructors_standings"]}

    for driver in state["drivers_standings"]:
        d_id = driver["id"]
        r_info = race_by_driver.get(d_id)
        pts_earned = int(r_info["points"]) if r_info else 0
        pos_finish = int(r_info["pos"]) if r_info else 20
        grid_pos = int(r_info["grid"]) if r_info else 20
        is_fl = bool(r_info["is_fastest_lap"]) if r_info else False

        driver["points_anterior"] = driver["points"]
        driver["points_round"] = pts_earned
        driver["points"] += pts_earned
        driver["points_by_round"].append(pts_earned)
        driver["round_finish_pos"] = pos_finish
        driver["round_status"] = r_info["status"] if r_info else "DNS"

        if pos_finish == 1:
            driver["wins"] += 1
        if pos_finish <= 3:
            driver["podiums"] += 1
        if grid_pos == 1:
            driver["poles"] += 1
        if is_fl:
            driver["fastest_laps"] += 1

        team_round_points[driver["team_id"]] += pts_earned

    # Sort drivers: 1) Total Points DESC, 2) Wins DESC, 3) Podiums DESC, 4) Previous pos ASC
    state["drivers_standings"].sort(
        key=lambda d: (-d["points"], -d["wins"], -d["podiums"], prev_driver_pos[d["id"]])
    )

    for idx, driver in enumerate(state["drivers_standings"], start=1):
        old_p = prev_driver_pos[driver["id"]]
        driver["pos"] = idx
        driver["pos_delta"] = old_p - idx

    # Update constructors and verify mathematical invariant
    driver_pts_lookup = {d["id"]: d["points"] for d in state["drivers_standings"]}
    driver_wins_lookup = {d["id"]: d["wins"] for d in state["drivers_standings"]}

    for team in state["constructors_standings"]:
        t_id = team["team_id"]
        r_pts = team_round_points[t_id]
        team["points_anterior"] = team["net_points"]
        team["points_round"] = r_pts
        team["gross_points"] += r_pts
        team["net_points"] = team["gross_points"] + team.get("fia_penalty_points", 0)

        # Strict Invariant Check
        sum_drivers = sum(driver_pts_lookup[d_id] for d_id in team["drivers"])
        if sum_drivers != team["gross_points"]:
            raise AssertionError(
                f"Constructor invariant failed for {t_id}: "
                f"sum(drivers)={sum_drivers} != gross_points={team['gross_points']}"
            )
        team["team_wins"] = sum(driver_wins_lookup[d_id] for d_id in team["drivers"])

    state["constructors_standings"].sort(
        key=lambda t: (-t["net_points"], -t["team_wins"], prev_team_pos[t["team_id"]])
    )

    for idx, team in enumerate(state["constructors_standings"], start=1):
        old_p = prev_team_pos[team["team_id"]]
        team["pos"] = idx
        team["pos_delta"] = old_p - idx

    state["last_completed_round"] = round_number
    state["last_completed_gp"] = gp_name
    return state

