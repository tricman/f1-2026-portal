import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

SILLY_SEASON_THEMES = [
    "Glamour & Celebridades: Festas VIP (iates, galas de luxo, estreias), parcerias com grifes e flagras com astros pop/cinema.",
    "Silly Season & Crise Contratual: Reuniões sigilosas em motorhomes fechados, empresários negociando multas rescisórias e sondagens rivais.",
    "Treta & Vestiário: Encontros tensos ou alianças improváveis em restaurantes, discussões vazadas por garçons ou comissários de bordo.",
    "Marketing & Mico Corporativo: Ações promocionais constrangedoras de patrocinadores, vídeos de TikTok recusados ou gravados a contragosto.",
    "Entrevista Surpresa / Flagra de Tabloid: Microfone ambiente indiscreto captando desabafo técnico, fotos de paparazzi ou vazamento de mensagens.",
    "Preparação & Simulador: Comparações ácidas de telemetria na fábrica, turnos triplos no simulador e reflexo das disputas online na garagem.",
]


def sample_weekly_themes(round_number: int, team_id: str) -> Dict[str, str]:
    """
    Deterministically sample 4 distinct themes (Monday to Thursday) without replacement
    using a seed derived from (round_number, team_id) to eliminate LLM sampling bias.
    """
    rng = random.Random(f"season_2026_r{round_number}_{team_id}")
    chosen = rng.sample(SILLY_SEASON_THEMES, k=4)
    return {
        "monday": chosen[0],
        "tuesday": chosen[1],
        "wednesday": chosen[2],
        "thursday": chosen[3],
    }


def select_press_conference_panel(
    standings: Dict[str, Any],
    round_number: int,
    home_driver_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Select 5 drivers for the FIA Thursday Press Conference:
    - All 3 human players (Sarah, Felipe, Davi) or a subset + key rivals
    - Home driver (e.g., Alonso/Sainz in Spain) or last winner
    - Main championship rival with recent friction (e.g., Verstappen)
    """
    by_id = {d["id"]: d for d in standings["drivers_standings"]}
    panel_ids = ["sarah", "felipe", "davi"]
    if home_driver_id and home_driver_id in by_id and home_driver_id not in panel_ids:
        panel_ids.append(home_driver_id)
    for rival_id in ["verstappen", "alonso", "hamilton", "leclerc", "norris"]:
        if len(panel_ids) >= 6:
            break
        if rival_id not in panel_ids and rival_id in by_id:
            panel_ids.append(rival_id)
    return [by_id[d_id] for d_id in panel_ids]


from src.repositories.factory import get_repository
from src.repositories.base_repository import IDataRepository


class CanonLedgerManager:
    def __init__(self, ledger_path: Optional[Path] = None, repo: Optional[IDataRepository] = None):
        self.repo = repo or get_repository()
        self.ledger_path = ledger_path or (Path(__file__).resolve().parent.parent / "data" / "state" / "canon_ledger.json")

    def load(self) -> Dict[str, Any]:
        return self.repo.get_canon_ledger()

    def save(self, data: Dict[str, Any]) -> None:
        self.repo.save_canon_ledger(data)

    def append_event(
        self,
        event_id: str,
        round_num: int,
        module: str,
        summary: str,
        entities: List[str],
        status: str = "OPEN",
    ) -> None:
        self.repo.append_canon_event(
            event_id=event_id,
            round_num=round_num,
            module=module,
            summary=summary,
            entities=entities,
            status=status,
        )

