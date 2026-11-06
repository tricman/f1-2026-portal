"""
Multi-Season Governance & Driver Transfer Storytelling Engine for F1 Showrunner.
Handles season partitioning (season_01, season_02, etc.), grid transfer delta detection,
and AI-generated blockbuster Silly Season transfer breaking news.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ai_showrunner import GeminiFreeTierClient
from src.canon_ledger import CanonLedgerManager

DEFAULT_SEASON_ID = "season_01"

DEFAULT_NEXT_SEASON_GRID: List[Dict[str, Any]] = [
    {"id": "sarah", "name": "Sarah (SarahMarinsS)", "team": "Mercedes-AMG Petronas", "number": 24},
    {"id": "hamilton", "name": "Lewis Hamilton", "team": "Mercedes-AMG Petronas", "number": 44},
    {"id": "felipe", "name": "Felipe (frdsilva)", "team": "Audi Revolut F1 Team", "number": 5},
    {"id": "hulkenberg", "name": "Nico Hülkenberg", "team": "Audi Revolut F1 Team", "number": 27},
    {"id": "davi", "name": "Davi (DaviMSSon)", "team": "Scuderia Ferrari HP", "number": 15},
    {"id": "leclerc", "name": "Charles Leclerc", "team": "Scuderia Ferrari HP", "number": 16},
    {"id": "verstappen", "name": "Max Verstappen", "team": "Red Bull Racing", "number": 1},
    {"id": "perez", "name": "Sergio Pérez", "team": "Red Bull Racing", "number": 11},
    {"id": "norris", "name": "Lando Norris", "team": "McLaren Formula 1 Team", "number": 4},
    {"id": "piastri", "name": "Oscar Piastri", "team": "McLaren Formula 1 Team", "number": 81},
    {"id": "alonso", "name": "Fernando Alonso", "team": "Aston Martin Aramco", "number": 14},
    {"id": "stroll", "name": "Lance Stroll", "team": "Aston Martin Aramco", "number": 18},
    {"id": "sainz", "name": "Carlos Sainz", "team": "Williams Racing", "number": 55},
    {"id": "albon", "name": "Alexander Albon", "team": "Williams Racing", "number": 23},
    {"id": "gasly", "name": "Pierre Gasly", "team": "Alpine F1 Team", "number": 10},
    {"id": "doohan", "name": "Jack Doohan", "team": "Alpine F1 Team", "number": 7},
    {"id": "tsunoda", "name": "Yuki Tsunoda", "team": "Visa Cash App RB", "number": 22},
    {"id": "lawson", "name": "Liam Lawson", "team": "Visa Cash App RB", "number": 30},
    {"id": "bearman", "name": "Oliver Bearman", "team": "MoneyGram Haas F1 Team", "number": 87},
    {"id": "ocon", "name": "Esteban Ocon", "team": "MoneyGram Haas F1 Team", "number": 31},
]


def get_current_season_id() -> str:
    """Returns active season_id from environment or default."""
    return os.environ.get("SEASON_ID", DEFAULT_SEASON_ID).strip()


def get_season_dir(root_dir: Path, season_id: Optional[str] = None) -> Path:
    """Resolves directory path for the given or active season."""
    s_id = season_id or get_current_season_id()
    s_dir = root_dir / "data" / "seasons" / s_id
    s_dir.mkdir(parents=True, exist_ok=True)
    return s_dir


def list_available_seasons(root_dir: Path) -> List[str]:
    """Scans data/seasons/ and returns list of season folders."""
    seasons_base = root_dir / "data" / "seasons"
    if not seasons_base.exists():
        return [DEFAULT_SEASON_ID]
    found = [d.name for d in seasons_base.iterdir() if d.is_dir() and d.name.startswith("season_")]
    return sorted(found) if found else [DEFAULT_SEASON_ID]


def detect_grid_transfers(
    prev_standings: Dict[str, Any],
    new_grid_registry: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compares driver-team assignments from previous season against the new grid registry.
    Returns list of transfer deltas.
    """
    old_drivers = {d["id"]: d for d in prev_standings.get("drivers", [])}
    transfers: List[Dict[str, Any]] = []

    for new_d in new_grid_registry:
        did = new_d["id"]
        dname = new_d.get("name", did.capitalize())
        new_team = new_d.get("team", "")
        car_number = new_d.get("number", 0)

        if did in old_drivers:
            old_team = old_drivers[did].get("team", "")
            if old_team and new_team and old_team.lower() != new_team.lower():
                transfers.append(
                    {
                        "type": "TRANSFER",
                        "driver_id": did,
                        "driver_name": dname,
                        "old_team": old_team,
                        "new_team": new_team,
                        "number": car_number,
                    }
                )
        else:
            transfers.append(
                {
                    "type": "ROOKIE_ARRIVAL",
                    "driver_id": did,
                    "driver_name": dname,
                    "old_team": "Categorias de Base / Outra Categoria",
                    "new_team": new_team,
                    "number": car_number,
                }
            )

    return transfers


def generate_transfer_announcement(
    root_dir: Path,
    transfer: Dict[str, Any],
    season_id: str,
    ai_client: Optional[GeminiFreeTierClient] = None,
) -> Path:
    """
    Generates an official blockbuster transfer press release and journalistic feature,
    saves it to data/seasons/{season_id}/transfers/ and registers the event in Canon Ledger.
    """
    client = ai_client or GeminiFreeTierClient()
    season_dir = get_season_dir(root_dir, season_id)
    transfers_dir = season_dir / "transfers"
    transfers_dir.mkdir(parents=True, exist_ok=True)

    dname = transfer["driver_name"]
    did = transfer["driver_id"]
    old_team = transfer["old_team"]
    new_team = transfer["new_team"]
    num = transfer.get("number", 0)

    slug_team = re.sub(r"[^a-zA-Z0-9]+", "_", new_team.lower()).strip("_")
    filename = f"TRANSFER_{did.upper()}_{slug_team}.md"
    target_file = transfers_dir / filename

    prompt = (
        f"MUNDO DA FÓRMULA 1 — BOMBA NO MERCADO DE PILOTOS (SILLY SEASON):\n"
        f"Piloto: {dname} (#{num})\n"
        f"Equipe Anterior: {old_team}\n"
        f"Nova Equipe: {new_team}\n"
        f"Temporada Alvo: {season_id.replace('season_', 'Temporada 202')}\n\n"
        f"TAREFA:\n"
        f"Gere um Comunicado Oficial e Matéria Especial da F1 TV / Gazzetta dello Sport / Sky Sports "
        f"anunciando a transferência de {dname} para {new_team}.\n"
        f"Estruture em:\n"
        f"1. Manchete impactante e lead jornalístico de grande circulação;\n"
        f"2. Os bastidores da negociação sigilosa (cláusulas, valores, papel dos empresários);\n"
        f"3. Declaração oficial do chefe de equipe acolhendo o piloto;\n"
        f"4. Declaração do piloto expressando a ambição na nova casa;\n"
        f"5. Repercussão no paddock e termômetro dos rivais.\n"
        f"Escreva em tom de jornalismo de ponta de F1 (adulto, técnico, tenso e vibrante)."
    )

    try:
        report_md = client._call_generate_content(
            model=client.flash_model,
            parts=[{"text": prompt}],
            system_instruction="Você é o correspondente sênior da FIA e da F1 TV World Feed.",
            temperature=0.5,
        ).strip()
    except Exception as exc:
        report_md = (
            f"# 🚨 BOMBA NO MERCADO: {dname.upper()} ASSINA COM A {new_team.upper()}!\n\n"
            f"Em uma das movimentações mais chocantes da Silly Season, {dname} deixa a {old_team} "
            f"para defender as cores da {new_team} na {season_id}.\n\n"
            f"> *\"É o início de um novo capítulo em busca do topo da Fórmula 1.\"* — {dname}\n"
        )

    target_file.write_text(report_md + "\n", encoding="utf-8")

    # Record in Canon Ledger
    from src.repositories.sqlite_document_repository import SqliteDocumentRepository
    repo = SqliteDocumentRepository(root_dir=root_dir)
    summary_line = f"Transferência confirmada para {season_id}: {dname} deixa a {old_team} e assina com a {new_team}."
    repo.append_canon_event(
        event_id=f"TRANSFER-{season_id.upper()}-{did.upper()}",
        round_num=0,
        module="SILLY_SEASON_TRANSFER",
        summary=summary_line,
        entities=[did, "mercado", slug_team, "fia"],
        status="CLOSED",
    )

    return target_file


def initialize_new_season(
    root_dir: Path,
    new_season_id: str,
    new_grid_registry: List[Dict[str, Any]],
    prev_season_id: str = "season_01",
    ai_client: Optional[GeminiFreeTierClient] = None,
) -> Dict[str, Any]:
    """
    Initializes a new season:
    1. Creates target season directory.
    2. Detects grid transfers against previous season standings.
    3. Generates narrative transfer articles for moved drivers.
    4. Initializes a clean, zeroed standings table for the new season.
    5. Returns initialization summary.
    """
    new_season_dir = get_season_dir(root_dir, new_season_id)
    state_dir = root_dir / "data" / "state"

    # 1. Load previous season standings
    prev_standings_file = state_dir / "standings.json"
    prev_standings: Dict[str, Any] = {}
    if prev_standings_file.exists():
        try:
            prev_standings = json.loads(prev_standings_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 2. Detect transfers
    transfers = detect_grid_transfers(prev_standings, new_grid_registry)
    announcements: List[str] = []
    for tr in transfers:
        ann_path = generate_transfer_announcement(root_dir, tr, new_season_id, ai_client=ai_client)
        announcements.append(str(ann_path.relative_to(root_dir)))

    # 3. Create zeroed standings for the new season
    season_year = 2026 + (int(new_season_id.split("_")[-1]) - 1 if new_season_id.split("_")[-1].isdigit() else 1)
    new_standings: Dict[str, Any] = {
        "season": season_year,
        "season_id": new_season_id,
        "last_completed_round": 0,
        "drivers": [],
        "constructors": [],
    }

    # Populate drivers
    constructors_map: Dict[str, List[str]] = {}
    for d in new_grid_registry:
        did = d["id"]
        team = d.get("team", "Equipe F1")
        new_standings["drivers"].append(
            {
                "id": did,
                "name": d.get("name", did.capitalize()),
                "team": team,
                "number": d.get("number", 0),
                "points": 0,
                "points_by_round": [],
                "wins": 0,
                "podiums": 0,
            }
        )
        constructors_map.setdefault(team, []).append(did)

    # Populate constructors
    for team_name, driver_ids in constructors_map.items():
        cid = re.sub(r"[^a-zA-Z0-9]+", "_", team_name.lower()).strip("_")
        new_standings["constructors"].append(
            {
                "id": cid,
                "name": team_name,
                "points": 0,
                "drivers": driver_ids,
            }
        )

    # Persist new season standings in season directory and NoSQL repository
    season_standings_file = new_season_dir / "standings_initial.json"
    season_standings_file.write_text(
        json.dumps(new_standings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Also update repository for this season
    from src.repositories.sqlite_document_repository import SqliteDocumentRepository
    repo = SqliteDocumentRepository(root_dir=root_dir)
    repo.save_document("standings", new_season_id, new_standings)

    # Record Season Kickoff Event in Canon Ledger
    repo.append_canon_event(
        event_id=f"KICKOFF-{new_season_id.upper()}",
        round_num=0,
        module="SEASON_KICKOFF",
        summary=f"Temporada {season_year} ({new_season_id}) oficialmente inicializada com {len(transfers)} transferências registradas.",
        entities=[new_season_id, "fia", "campeonato"],
        status="OPEN",
    )

    return {
        "success": True,
        "new_season_id": new_season_id,
        "season_year": season_year,
        "transfers_count": len(transfers),
        "transfers": transfers,
        "announcements": announcements,
    }
