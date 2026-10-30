from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass(frozen=True)
class LapRecord:
    lap: int
    pos: Optional[int]
    car_number: int
    driver: str
    team: str
    lap_time: str
    lap_time_ms: int
    s1: Optional[str]
    s2: Optional[str]
    s3: Optional[str]
    tyre: str
    tyre_age: Optional[int]
    wear_pct: Optional[float]
    pits: Optional[int]


@dataclass(frozen=True)
class PitStopEvent:
    lap: int
    driver: str
    team: str
    stop_duration_s: float
    repairs: str
    tyre_from: str
    tyre_to: str


@dataclass(frozen=True)
class StewardIncident:
    lap: int
    driver: str
    team: str
    incident: str
    penalty: str


@dataclass
class DriverRaceResult:
    pos: int
    car_number: int
    driver_id: str
    driver_name: str
    team: str
    grid: int
    pos_delta: int
    laps: int
    stops: int
    tyre_strategy: str
    best_lap: str
    best_lap_ms: int
    best_lap_num: int
    is_fastest_lap: bool
    total_time_or_gap: str
    status: str
    points: int
    max_wear_pct: float = 0.0
    final_wear_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

