import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

SILLY_SEASON_THEMES = [
    "T01 — Pacote Aerodinâmico & Peças Novas: Peças novas de túnel de vento (assoalhos, asas, sidepods) e o drama da correlação entre simulação em fábrica e dados reais de pista.",
    "T02 — Crise Contratual & Mercado de Pilotos: Boatos de transferências para a temporada seguinte, cláusulas de desempenho, pré-contratos e pressão de jovens da academia ou pilotos reservas.",
    "T03 — Clima de Garagem & Conflito Interno: Divergência entre companheiros de equipe, cobranças contundentes dos chefes (Toto Wolff, James Vowles, Mattia Binotto) e prioridade de peças novas.",
    "T04 — Guerra Psicológica & Provocações: Farpas trocadas em coletivas passadas, declarações sobre estilo de pilotagem agressivo e jogos mentais para desestabilizar adversários diretos.",
    "T05 — Teto de Gastos (Cost Cap) & Danos Financeiros: O peso orçamentário de acidentes e quebras nas etapas anteriores, impondo o dilema de reparar peças ou congelar o desenvolvimento do carro.",
    "T06 — Pressão Comercial & Patrocinadores: Exigências de patrocinadores master, pinturas especiais (special liveries), ativações de RP exaustivas roubando horas de sono dos pilotos.",
    "T07 — Confiabilidade de Motor & Punições de Grid: Desgaste de componentes da unidade de potência (ICE, Turbo, MGU-K) atingindo o limite regulamentar e o dilema de trocar motor e largar no fundo do grid.",
    "T08 — Polêmicas Regulatórias & Protestos na FIA: Esclarecimentos técnicos exigidos à FIA sobre flexibilidade de asas (flexi-wings), truques de refrigeração e suspeitas mútuas entre equipes.",
    "T09 — Desafio Biométrico & Clima Extremo: Previsão de calor sufocante, altitude rarefeita, desidratação severa ou chuva torrencial exigindo preparação cardiovascular no limite.",
    "T10 — Acerto de Pista & Tradição do GP: O compromisso clássico entre velocidade de reta e downforce para o traçado específico, histórico dos pilotos na pista e armadilhas de zebras.",
    "T11 — Blindagem de Mídia & Estratégia de Spin: Gerenciamento de crises pessoais, controle de danos contra manchetes caça-cliques de tablóides e vazamento estratégico de informações.",
    "T12 — Dilema de Foco (Ano Atual vs. Temporada Seguinte): A decisão da cúpula da equipe de encerrar o desenvolvimento do carro atual para investir tudo no projeto do ano que vem, frustrando os pilotos titulares.",
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


HOME_CIRCUIT_DRIVERS: Dict[int, List[str]] = {
    1: [],                                                  # Bahrein (Sakhir)
    2: [],                                                  # Arábia Saudita (Jeddah)
    3: ["piastri", "ricciardo"],                            # Austrália (Albert Park)
    4: ["tsunoda"],                                         # Japão (Suzuka)
    5: [],                                                  # China (Xangai)
    6: [],                                                  # Miami (EUA)
    7: ["leclerc", "sainz", "tsunoda", "ricciardo"],       # Emilia-Romagna (Ímola / Ferrari & VCARB)
    8: ["leclerc"],                                         # Mônaco
    9: ["stroll"],                                          # Canadá (Montreal)
    10: ["alonso", "sainz"],                                # Espanha (Barcelona)
    11: ["verstappen", "perez", "tsunoda", "ricciardo"],   # Áustria (Red Bull Ring - Home da Red Bull)
    12: ["hamilton", "norris", "albon"],                    # Grã-Bretanha (Silverstone)
    13: [],                                                 # Hungria (Hungaroring)
    14: ["verstappen", "norris"],                           # Bélgica (Spa-Francorchamps)
    15: ["verstappen"],                                     # Holanda (Zandvoort)
    16: ["leclerc", "sainz", "hamilton"],                  # Itália (Monza / Templo Ferrari)
    17: [],                                                 # Azerbaijão (Baku)
    18: [],                                                 # Cingapura (Marina Bay)
    19: ["hulkenberg", "magnussen"],                        # Estados Unidos (Austin / Haas)
    20: ["perez"],                                          # México (Hermanos Rodríguez)
    21: ["sarah", "felipe", "davi"],                       # Brasil (Interlagos - Brazilian Storm)
    22: [],                                                 # Las Vegas
    23: [],                                                 # Catar (Lusail)
    24: [],                                                 # Abu Dhabi (Yas Marina)
}


def select_press_conference_panel(
    standings: Dict[str, Any],
    round_number: int,
    canon_ledger: Optional[Dict[str, Any]] = None,
    home_driver_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Select 5 or 6 drivers for the FIA Thursday Press Conference based strictly
    on realistic FIA narrative criteria:
      1. Home Race Drivers (+50 pts) (e.g. Alonso/Sainz in Spain, Red Bull in Austria, Brits in Silverstone, Sarah/Felipe/Davi in Brazil).
      2. Current World Championship leader (+40 pts) and Top 5 contenders.
      3. Last Round winner (P1: +35 pts) and podium finishers (P2: +22 pts, P3: +16 pts).
      4. Drivers involved in hot Canon Ledger storylines/scandals (+25 pts).
    Human drivers (Sarah, Felipe, Davi) are NOT forced on every panel; they only participate
    when justified by season momentum, incidents, or home circuit!
    """
    drivers = standings.get("drivers_standings", [])
    if not drivers:
        return []

    by_id = {d["id"]: d for d in drivers}
    scores: Dict[str, float] = {d["id"]: 0.0 for d in drivers}

    # 1. Home circuit drivers (+50 pts)
    home_drivers = list(HOME_CIRCUIT_DRIVERS.get(round_number, []))
    if home_driver_id and home_driver_id in by_id and home_driver_id not in home_drivers:
        home_drivers.append(home_driver_id)
    for d_id in home_drivers:
        if d_id in scores:
            scores[d_id] += 50.0

    # 2. Championship leader (+40 pts)
    leader_id = drivers[0]["id"]
    scores[leader_id] += 40.0

    # 3. Standings position & last round results
    for d in drivers:
        d_id = d["id"]
        pos = d.get("pos", 20)
        if pos <= 5:
            scores[d_id] += max(0, 25 - (pos * 4))
        pbr = d.get("points_by_round", [])
        if pbr:
            last = pbr[-1]
            if last >= 25:
                scores[d_id] += 35.0
            elif last >= 18:
                scores[d_id] += 22.0
            elif last >= 15:
                scores[d_id] += 16.0

    # 4. Canon Ledger hot storylines (+25 pts)
    if canon_ledger:
        events = canon_ledger.get("events", [])
        recent = events[-3:] if events else []
        for ev in recent:
            w = 25.0 if ev.get("status") == "OPEN" else 10.0
            for ent in ev.get("entities", []):
                ent_low = str(ent).lower()
                for d_id in scores:
                    if d_id in ent_low:
                        scores[d_id] += w

    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    selected_ids = ranked[:5]
    if len(ranked) > 5 and scores[ranked[5]] >= 45.0:
        selected_ids = ranked[:6]

    return [by_id[did] for did in selected_ids if did in by_id]


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

