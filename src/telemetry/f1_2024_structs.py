"""
F1 2024 UDP Telemetry Specification & Struct Unpackers (Codemasters / EA Sports F1 24).
Provides zero-copy, resilient binary unpacking of UDP telemetry packets.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

PACKET_FORMAT_2024 = 2024

# Packet IDs in EA Sports F1 24
PACKET_ID_MOTION = 0
PACKET_ID_SESSION = 1
PACKET_ID_LAP_DATA = 2
PACKET_ID_EVENT = 3
PACKET_ID_PARTICIPANTS = 4
PACKET_ID_CAR_SETUPS = 5
PACKET_ID_CAR_TELEMETRY = 6
PACKET_ID_CAR_STATUS = 7
PACKET_ID_FINAL_CLASSIFICATION = 8
PACKET_ID_LOBBY_INFO = 9
PACKET_ID_CAR_DAMAGE = 10
PACKET_ID_SESSION_HISTORY = 11
PACKET_ID_TYRE_SETS = 12
PACKET_ID_MOTION_EX = 13

# Visual Tyre Compound Mapping (F1 Modern)
VISUAL_TYRE_COMPOUNDS = {
    16: "S",  # Soft
    17: "M",  # Medium
    18: "H",  # Hard
    7: "I",   # Intermediate
    8: "W",   # Wet
}

# Result Status
RESULT_STATUS_MAP = {
    0: "INVALID",
    1: "INACTIVE",
    2: "ACTIVE",
    3: "FINISHED",
    4: "DNF",
    5: "DSQ",
    6: "NC",
    7: "RETIRED",
}

# Session Type Mapping
SESSION_TYPE_MAP = {
    0: "UNKNOWN",
    1: "P1",
    2: "P2",
    3: "P3",
    4: "SHORT_P",
    5: "Q1",
    6: "Q2",
    7: "Q3",
    8: "SHORT_Q",
    9: "OSQ",
    10: "RACE",
    11: "RACE_2",
    12: "RACE_3",
    13: "TIME_TRIAL",
}

# Track IDs mapping to Showrunner round metadata and circuit names
TRACK_ID_MAP = {
    0: {"name": "Melbourne", "round": 3, "folder": "et_03_australia"},
    1: {"name": "Paul Ricard", "round": None, "folder": None},
    2: {"name": "Shanghai", "round": 5, "folder": "et_05_china"},
    3: {"name": "Sakhir", "round": 1, "folder": "et_01_bahrein"},
    4: {"name": "Catalunya", "round": 10, "folder": "et_10_espanha"},
    5: {"name": "Monaco", "round": 8, "folder": "et_08_monaco"},
    6: {"name": "Montreal", "round": 9, "folder": "et_09_canada"},
    7: {"name": "Silverstone", "round": 12, "folder": "et_12_inglaterra"},
    8: {"name": "Hockenheim", "round": None, "folder": None},
    9: {"name": "Hungaroring", "round": 13, "folder": "et_13_hungria"},
    10: {"name": "Spa-Francorchamps", "round": 14, "folder": "et_14_belgica"},
    11: {"name": "Monza", "round": 16, "folder": "et_16_italia"},
    12: {"name": "Marina Bay", "round": 18, "folder": "et_18_singapura"},
    13: {"name": "Suzuka", "round": 4, "folder": "et_04_japao"},
    14: {"name": "Yas Marina", "round": 24, "folder": "et_24_abu_dhabi"},
    15: {"name": "Circuit of the Americas", "round": 19, "folder": "et_19_eua"},
    16: {"name": "Interlagos", "round": 21, "folder": "et_21_brasil"},
    17: {"name": "Red Bull Ring", "round": 11, "folder": "et_11_austria"},
    18: {"name": "Sochi", "round": None, "folder": None},
    19: {"name": "Autodromo Hermanos Rodriguez", "round": 20, "folder": "et_20_mexico"},
    20: {"name": "Baku City Circuit", "round": 17, "folder": "et_17_azerbaijao"},
    26: {"name": "Zandvoort", "round": 15, "folder": "et_15_holanda"},
    27: {"name": "Imola", "round": 7, "folder": "et_07_imola"},
    28: {"name": "Portimao", "round": None, "folder": None},
    29: {"name": "Jeddah Corniche", "round": 2, "folder": "et_02_jeddah"},
    30: {"name": "Miami International Autodrome", "round": 6, "folder": "et_06_miami"},
    31: {"name": "Las Vegas Strip Circuit", "round": 22, "folder": "et_22_las_vegas"},
    32: {"name": "Losail International Circuit", "round": 23, "folder": "et_23_catar"},
}

# Team ID Mapping (Codemasters F1 24)
TEAM_ID_MAP = {
    0: "Mercedes-AMG Petronas",
    1: "Scuderia Ferrari HP",
    2: "Red Bull Racing",
    3: "Williams Racing",
    4: "Aston Martin Aramco",
    5: "BWT Alpine F1 Team",
    6: "Visa Cash App RB",
    7: "MoneyGram Haas F1 Team",
    8: "McLaren Formula 1 Team",
    9: "Stake F1 Team Kick Sauber",
}


@dataclass
class PacketHeader:
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int

    HEADER_SIZE = 29
    HEADER_FORMAT = "<HBBBBBQfIIBB"

    @classmethod
    def unpack(cls, data: bytes) -> Optional[PacketHeader]:
        if len(data) < cls.HEADER_SIZE:
            return None
        values = struct.unpack(cls.HEADER_FORMAT, data[:cls.HEADER_SIZE])
        return cls(*values)


@dataclass
class SessionData:
    weather: int
    track_temperature: int
    air_temperature: int
    total_laps: int
    track_length: int
    session_type: int
    track_id: int
    formula: int
    session_time_left: int
    session_duration: int
    pit_speed_limit: int

    @classmethod
    def unpack(cls, data: bytes) -> Optional[SessionData]:
        if len(data) < 29 + 17:
            return None
        # offset 29: weather (B), trackTemp (b), airTemp (b), totalLaps (B), trackLength (H), sessionType (B), trackId (b), formula (B), timeLeft (H), duration (H), pitSpeedLimit (B)
        fmt = "<BbbBHBbBHHB"
        sub = data[29:29 + struct.calcsize(fmt)]
        values = struct.unpack(fmt, sub)
        # values: (weather, trackTemp, airTemp, totalLaps, trackLength, sessionType, trackId, formula, timeLeft, duration, pitSpeedLimit)
        return cls(
            weather=values[0],
            track_temperature=values[1],
            air_temperature=values[2],
            total_laps=values[3],
            track_length=values[4],
            session_type=values[5],
            track_id=values[6],
            formula=values[7],
            session_time_left=values[8],
            session_duration=values[9],
            pit_speed_limit=values[10],
        )


@dataclass
class ParticipantData:
    ai_controlled: int
    driver_id: int
    network_id: int
    team_id: int
    my_team: int
    race_number: int
    nationality: int
    name: str
    your_telemetry: int


@dataclass
class ParticipantsPacket:
    num_active_cars: int
    participants: List[ParticipantData] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[ParticipantsPacket]:
        if len(data) < 30:
            return None
        num_active = data[29]
        cars: List[ParticipantData] = []
        offset = 30
        remaining = len(data) - 30
        stride = remaining // 22 if remaining >= 22 * 54 else 56

        for i in range(min(num_active, 22)):
            car_offset = offset + (i * stride)
            if car_offset + 54 > len(data):
                break
            # Unpack first 7 uint8 fields
            ai, drv_id, net_id, team, my_t, race_num, nat = struct.unpack_from("<BBBBBBB", data, car_offset)
            raw_name_bytes = data[car_offset + 7: car_offset + 7 + 48]
            name = raw_name_bytes.split(b"\x00")[0].decode("utf-8", errors="ignore").strip()
            your_telemetry = data[car_offset + 55] if car_offset + 55 < len(data) else 1
            cars.append(
                ParticipantData(
                    ai_controlled=ai,
                    driver_id=drv_id,
                    network_id=net_id,
                    team_id=team,
                    my_team=my_t,
                    race_number=race_num,
                    nationality=nat,
                    name=name,
                    your_telemetry=your_telemetry,
                )
            )
        return cls(num_active_cars=num_active, participants=cars)


@dataclass
class LapDataRecord:
    last_lap_time_ms: int
    current_lap_time_ms: int
    sector1_ms: int
    sector2_ms: int
    car_position: int
    current_lap_num: int
    pit_status: int
    num_pit_stops: int
    penalties: int
    grid_position: int
    driver_status: int
    result_status: int
    pit_stop_timer_ms: int


@dataclass
class FinalClassificationDriver:
    position: int
    num_laps: int
    grid_position: int
    points: int
    num_pit_stops: int
    result_status: int
    best_lap_time_ms: int
    total_race_time: float
    penalties_time: int
    num_penalties: int
    num_tyre_stints: int
    tyre_stints_visual: List[int] = field(default_factory=list)


@dataclass
class FinalClassificationPacket:
    num_cars: int
    classification: List[FinalClassificationDriver] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[FinalClassificationPacket]:
        if len(data) < 30:
            return None
        num_cars = data[29]
        drivers: List[FinalClassificationDriver] = []
        offset = 30
        remaining = len(data) - 30
        stride = remaining // 22 if remaining >= 22 * 40 else 44

        for i in range(min(num_cars, 22)):
            car_offset = offset + (i * stride)
            if car_offset + 40 > len(data):
                break
            # Struct: position(B), numLaps(B), gridPos(B), points(B), numPitStops(B), resultStatus(B), bestLapTimeMS(I), totalRaceTime(d), penaltiesTime(B), numPenalties(B), numTyreStints(B)
            prefix_fmt = "<BBBBBBIdBBB"
            prefix_size = struct.calcsize(prefix_fmt)
            vals = struct.unpack_from(prefix_fmt, data, car_offset)
            pos, laps, grid, pts, stops, status, best_lap_ms, total_time, pen_time, n_pens, n_stints = vals

            # Next 8 bytes: tyreStintsActual, Next 8 bytes: tyreStintsVisual
            visual_offset = car_offset + prefix_size + 8
            visual_stints = list(data[visual_offset: visual_offset + 8]) if visual_offset + 8 <= len(data) else []
            valid_stints = [stint for stint in visual_stints[:n_stints] if stint in VISUAL_TYRE_COMPOUNDS]

            drivers.append(
                FinalClassificationDriver(
                    position=pos,
                    num_laps=laps,
                    grid_position=grid,
                    points=pts,
                    num_pit_stops=stops,
                    result_status=status,
                    best_lap_time_ms=best_lap_ms,
                    total_race_time=total_time,
                    penalties_time=pen_time,
                    num_penalties=n_pens,
                    num_tyre_stints=n_stints,
                    tyre_stints_visual=valid_stints,
                )
            )
        return cls(num_cars=num_cars, classification=drivers)
