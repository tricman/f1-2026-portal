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


class CanonLedgerManager:
    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self._init_default_ledger()

    def _init_default_ledger(self) -> None:
        initial = {
            "season": 2026,
            "reputation": {
                "sarah": {
                    "score": 45,
                    "archetype": "Ice Queen / Prodígio Implacável",
                    "public_perception": "Admirada pela genialidade técnica em Brackley e frieza cirúrgica; respeitada e temida pelos veteranos.",
                },
                "felipe": {
                    "score": 70,
                    "archetype": "O Professor / Monge de Hinwil",
                    "public_perception": "Herói técnico do Paddock; visto como mentor da Brazilian Storm e milagreiro da KICK Sauber.",
                },
                "davi": {
                    "score": 30,
                    "archetype": "O Leão de Grove / Showman Agressivo",
                    "public_perception": "Amado pela velocidade bruta e ultrapassagens no limite, mas visado pelos comissários e pela Red Bull.",
                },
            },
            "events": [
                {
                    "event_id": "ET08-MC-01",
                    "round": 8,
                    "module": "M5_CORRIDA",
                    "summary": "Toque de Verstappen na traseira de Felipe na saída do Túnel em Mônaco causou DNF de Felipe e perda de asa de Davi; WMSC deduziu -10 pts de Construtores da Red Bull.",
                    "entities": ["felipe", "verstappen", "davi", "sauber", "red_bull"],
                    "status": "OPEN",
                },
                {
                    "event_id": "ET08-MC-02",
                    "round": 8,
                    "module": "M5_CORRIDA",
                    "summary": "Sarah foi desclassificada (DSQ) em Mônaco quando liderava com Pole e Volta Mais Rápida por suposto desrespeito a bandeira amarela; Mercedes recorreu em Paris.",
                    "entities": ["sarah", "mercedes", "fia"],
                    "status": "OPEN",
                },
                {
                    "event_id": "ET09-CA-01",
                    "round": 9,
                    "module": "M5_CORRIDA",
                    "summary": "Segundo pódio 100% brasileiro da história no Canadá: Sarah P1, Davi P2 (+VR 1:13.846 pressionando até o fim) e Felipe P3 segurando Hamilton.",
                    "entities": ["sarah", "davi", "felipe", "hamilton"],
                    "status": "RESOLVED",
                },
                {
                    "event_id": "ET10-ES-M1",
                    "round": 10,
                    "module": "M1_SEMANA_EQUIPES",
                    "summary": "Semana pré-Espanha fervendo: Toto Wolff e Jules Moreau alinharam blindagem de 80 milhões de euros para Sarah; Helmut Marko levou porta na cara de James Vowles ao sondar Davi; estafe de Sainz jantou com executivos da Audi/Sauber; ultimato sobre Checo Pérez.",
                    "entities": ["sarah", "davi", "felipe", "sainz", "perez", "verstappen"],
                    "status": "OPEN",
                },
            ],
        }
        self.save(initial)

    def load(self) -> Dict[str, Any]:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def save(self, data: Dict[str, Any]) -> None:
        self.ledger_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def append_event(
        self,
        event_id: str,
        round_num: int,
        module: str,
        summary: str,
        entities: List[str],
        status: str = "OPEN",
    ) -> None:
        data = self.load()
        existing_ids = {e["event_id"] for e in data["events"]}
        if event_id not in existing_ids:
            data["events"].append({
                "event_id": event_id,
                "round": round_num,
                "module": module,
                "summary": summary,
                "entities": entities,
                "status": status,
            })
            self.save(data)

