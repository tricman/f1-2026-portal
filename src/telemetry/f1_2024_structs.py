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
    28: {"name": "Autódromo Internacional do Algarve (Portimão)", "round": None, "folder": "telemetry_pilot_test"},
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

# Complete Codemasters Official F1 Driver IDs
F1_2024_DRIVER_IDS = {
    0: ("sainz", "Carlos Sainz", 55, "Scuderia Ferrari HP"),
    2: ("ricciardo", "Daniel Ricciardo", 3, "Visa Cash App RB"),
    3: ("alonso", "Fernando Alonso", 14, "Aston Martin Aramco"),
    6: ("hamilton", "Lewis Hamilton", 44, "Mercedes-AMG Petronas"),
    8: ("verstappen", "Max Verstappen", 1, "Red Bull Racing"),
    9: ("hulkenberg", "Nico Hülkenberg", 27, "MoneyGram Haas F1 Team"),
    10: ("magnussen", "Kevin Magnussen", 20, "MoneyGram Haas F1 Team"),
    13: ("perez", "Sergio Pérez", 11, "Red Bull Racing"),
    14: ("bottas", "Valtteri Bottas", 77, "Stake F1 Team Kick Sauber"),
    15: ("ocon", "Esteban Ocon", 31, "BWT Alpine F1 Team"),
    17: ("stroll", "Lance Stroll", 18, "Aston Martin Aramco"),
    41: ("norris", "Lando Norris", 4, "McLaren Formula 1 Team"),
    42: ("russell", "George Russell", 63, "Mercedes-AMG Petronas"),
    49: ("zhou", "Guanyu Zhou", 24, "Stake F1 Team Kick Sauber"),
    58: ("leclerc", "Charles Leclerc", 16, "Scuderia Ferrari HP"),
    62: ("gasly", "Pierre Gasly", 10, "BWT Alpine F1 Team"),
    69: ("albon", "Alexander Albon", 23, "Williams Racing"),
    74: ("tsunoda", "Yuki Tsunoda", 22, "Visa Cash App RB"),
    80: ("zhou", "Guanyu Zhou", 24, "Stake F1 Team Kick Sauber"),
    84: ("piastri", "Oscar Piastri", 81, "McLaren Formula 1 Team"),
    89: ("sargeant", "Logan Sargeant", 2, "Williams Racing"),
    90: ("sargeant", "Logan Sargeant", 2, "Williams Racing"),
}

# Race Number to Canonical Driver Map
F1_2024_CAR_NUMBERS = {
    4: ("norris", "Lando Norris", 4, "McLaren Formula 1 Team"),
    81: ("piastri", "Oscar Piastri", 81, "McLaren Formula 1 Team"),
    15: ("davi", "Davi (DaviMSSon)", 15, "Williams Racing"),
    5: ("felipe", "Felipe (frdsilva)", 5, "Stake F1 Team Kick Sauber"),
    24: ("sarah", "Sarah (SarahMarinsS)", 24, "Mercedes-AMG Petronas"),
    1: ("verstappen", "Max Verstappen", 1, "Red Bull Racing"),
    33: ("verstappen", "Max Verstappen", 33, "Red Bull Racing"),
    11: ("perez", "Sergio Pérez", 11, "Red Bull Racing"),
    16: ("leclerc", "Charles Leclerc", 16, "Scuderia Ferrari HP"),
    55: ("sainz", "Carlos Sainz", 55, "Scuderia Ferrari HP"),
    14: ("alonso", "Fernando Alonso", 14, "Aston Martin Aramco"),
    18: ("stroll", "Lance Stroll", 18, "Aston Martin Aramco"),
    44: ("hamilton", "Lewis Hamilton", 44, "Mercedes-AMG Petronas"),
    63: ("russell", "George Russell", 63, "Mercedes-AMG Petronas"),
    10: ("gasly", "Pierre Gasly", 10, "BWT Alpine F1 Team"),
    31: ("ocon", "Esteban Ocon", 31, "BWT Alpine F1 Team"),
    23: ("albon", "Alexander Albon", 23, "Williams Racing"),
    3: ("ricciardo", "Daniel Ricciardo", 3, "Visa Cash App RB"),
    22: ("tsunoda", "Yuki Tsunoda", 22, "Visa Cash App RB"),
    27: ("hulkenberg", "Nico Hülkenberg", 27, "MoneyGram Haas F1 Team"),
    20: ("magnussen", "Kevin Magnussen", 20, "MoneyGram Haas F1 Team"),
    77: ("bottas", "Valtteri Bottas", 77, "Stake F1 Team Kick Sauber"),
}

# Infringement Types (Codemasters F1)
INFRINGEMENT_TYPES = {
    0: "Bloqueio na pista",
    1: "Corte de curva / Limites de pista",
    2: "Corte de curva com ganho de vantagem",
    3: "Colisão causando dano",
    4: "Colisão causando abandono",
    5: "Colisão com outro veículo",
    6: "Ultrapassagem sob Safety Car",
    7: "Excesso de velocidade no pit lane",
    8: "Ignorar bandeira amarela",
    9: "Ignorar bandeira azul",
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
        fmt = "<BbbBHBbBHHB"
        sub = data[29:29 + struct.calcsize(fmt)]
        values = struct.unpack(fmt, sub)
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
        stride = remaining // 22 if remaining >= 22 * 54 else 57

        for i in range(min(num_active, 22)):
            car_offset = offset + (i * stride)
            if car_offset + 54 > len(data):
                break
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
class FinalClassificationDriver:
    vehicle_idx: int
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
        stride = remaining // 22 if remaining >= 22 * 40 else 45

        for i in range(min(num_cars, 22)):
            car_offset = offset + (i * stride)
            if car_offset + 40 > len(data):
                break
            prefix_fmt = "<BBBBBBIdBBB"
            prefix_size = struct.calcsize(prefix_fmt)
            vals = struct.unpack_from(prefix_fmt, data, car_offset)
            pos, laps, grid, pts, stops, status, best_lap_ms, total_time, pen_time, n_pens, n_stints = vals

            visual_offset = car_offset + prefix_size + 8
            visual_stints = list(data[visual_offset: visual_offset + 8]) if visual_offset + 8 <= len(data) else []
            valid_stints = [stint for stint in visual_stints[:n_stints] if stint in VISUAL_TYRE_COMPOUNDS]

            drivers.append(
                FinalClassificationDriver(
                    vehicle_idx=i,
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


# ==============================================================================
# PACKET 5: CAR SETUPS
# ==============================================================================
@dataclass
class CarSetupData:
    front_wing: int
    rear_wing: int
    on_throttle: int
    off_throttle: int
    front_camber: float
    rear_camber: float
    front_toe: float
    rear_toe: float
    front_suspension: int
    rear_suspension: int
    front_anti_roll_bar: int
    rear_anti_roll_bar: int
    front_suspension_height: int
    rear_suspension_height: int
    brake_pressure: int
    brake_bias: int
    rear_left_tyre_pressure: float
    rear_right_tyre_pressure: float
    front_left_tyre_pressure: float
    front_right_tyre_pressure: float
    ballast: int
    fuel_load: float


@dataclass
class CarSetupsPacket:
    car_setups: List[CarSetupData] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[CarSetupsPacket]:
        if len(data) < 29 + 40:
            return None
        offset = 29
        setups: List[CarSetupData] = []
        stride = 49 if (len(data) - 29) >= 22 * 49 else (len(data) - 29) // 22

        for i in range(22):
            c_off = offset + (i * stride)
            if c_off + 40 > len(data):
                break
            try:
                vals = struct.unpack_from("<BBBBffffBBBBBBBBffffBf", data, c_off)
                setups.append(
                    CarSetupData(
                        front_wing=vals[0],
                        rear_wing=vals[1],
                        on_throttle=vals[2],
                        off_throttle=vals[3],
                        front_camber=round(vals[4], 2),
                        rear_camber=round(vals[5], 2),
                        front_toe=round(vals[6], 2),
                        rear_toe=round(vals[7], 2),
                        front_suspension=vals[8],
                        rear_suspension=vals[9],
                        front_anti_roll_bar=vals[10],
                        rear_anti_roll_bar=vals[11],
                        front_suspension_height=vals[12],
                        rear_suspension_height=vals[13],
                        brake_pressure=vals[14],
                        brake_bias=vals[15],
                        rear_left_tyre_pressure=round(vals[16], 1),
                        rear_right_tyre_pressure=round(vals[17], 1),
                        front_left_tyre_pressure=round(vals[18], 1),
                        front_right_tyre_pressure=round(vals[19], 1),
                        ballast=vals[20],
                        fuel_load=round(vals[21], 1),
                    )
                )
            except Exception:
                break
        return cls(car_setups=setups)


# ==============================================================================
# PACKET 6: CAR TELEMETRY
# ==============================================================================
@dataclass
class CarTelemetryData:
    speed: int
    throttle: float
    steer: float
    brake: float
    clutch: int
    gear: int
    engine_rpm: int
    drs: int
    rev_lights_percent: int
    rev_lights_bit_value: int
    brakes_temperature: Tuple[int, int, int, int]  # RL, RR, FL, FR
    tyres_surface_temperature: Tuple[int, int, int, int]  # RL, RR, FL, FR
    tyres_inner_temperature: Tuple[int, int, int, int]  # RL, RR, FL, FR
    engine_temperature: int
    tyres_pressure: Tuple[float, float, float, float]  # RL, RR, FL, FR
    surface_type: Tuple[int, int, int, int]


@dataclass
class CarTelemetryPacket:
    car_telemetry: List[CarTelemetryData] = field(default_factory=list)
    mfd_panel_index: int = 255
    suggested_gear: int = 0

    @classmethod
    def unpack(cls, data: bytes) -> Optional[CarTelemetryPacket]:
        if len(data) < 29 + 50:
            return None
        offset = 29
        telemetry: List[CarTelemetryData] = []
        stride = 60 if (len(data) - 29) >= 22 * 60 else (len(data) - 29) // 22

        for i in range(22):
            c_off = offset + (i * stride)
            if c_off + 54 > len(data):
                break
            try:
                # <HfffbbHBBH4H4B4BH4f4B
                base = struct.unpack_from("<HfffbbHBBH", data, c_off)
                sub_off = c_off + 22
                brakes = struct.unpack_from("<4H", data, sub_off)
                sub_off += 8
                tyres_surf = struct.unpack_from("<4B", data, sub_off)
                sub_off += 4
                tyres_inner = struct.unpack_from("<4B", data, sub_off)
                sub_off += 4
                eng_temp = struct.unpack_from("<H", data, sub_off)[0]
                sub_off += 2
                tyres_press = struct.unpack_from("<4f", data, sub_off)
                sub_off += 16
                surf_type = struct.unpack_from("<4B", data, sub_off) if sub_off + 4 <= len(data) else (0, 0, 0, 0)

                telemetry.append(
                    CarTelemetryData(
                        speed=base[0],
                        throttle=round(base[1], 2),
                        steer=round(base[2], 2),
                        brake=round(base[3], 2),
                        clutch=base[4],
                        gear=base[5],
                        engine_rpm=base[6],
                        drs=base[7],
                        rev_lights_percent=base[8],
                        rev_lights_bit_value=base[9],
                        brakes_temperature=brakes,
                        tyres_surface_temperature=tyres_surf,
                        tyres_inner_temperature=tyres_inner,
                        engine_temperature=eng_temp,
                        tyres_pressure=tuple(round(p, 1) for p in tyres_press),
                        surface_type=surf_type,
                    )
                )
            except Exception:
                break

        tail_off = 29 + (22 * stride)
        mfd = data[tail_off] if tail_off < len(data) else 255
        sug_gear = struct.unpack_from("<b", data, tail_off + 2)[0] if tail_off + 3 <= len(data) else 0

        return cls(car_telemetry=telemetry, mfd_panel_index=mfd, suggested_gear=sug_gear)


# ==============================================================================
# PACKET 7: CAR STATUS (FULL EXPANDED)
# ==============================================================================
@dataclass
class CarStatusFullData:
    traction_control: int
    anti_lock_brakes: int
    fuel_mix: int
    front_brake_bias: int
    pit_limiter_status: int
    fuel_in_tank: float
    fuel_capacity: float
    fuel_remaining_laps: float
    max_rpm: int
    idle_rpm: int
    max_gears: int
    drs_allowed: int
    drs_activation_distance: int
    actual_tyre_compound: int
    visual_tyre_compound: int
    tyre_code: str
    tyres_age_laps: int
    vehicle_fia_flags: int
    ers_store_energy: float
    ers_deploy_mode: int
    ers_harvested_this_lap_mguk: float
    ers_harvested_this_lap_mguh: float
    ers_deployed_this_lap: float


@dataclass
class CarStatusFullPacket:
    car_status: List[CarStatusFullData] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[CarStatusFullPacket]:
        if len(data) < 29 + 40:
            return None
        offset = 29
        statuses: List[CarStatusFullData] = []
        stride = 55 if (len(data) - 29) >= 22 * 55 else 47

        for i in range(22):
            c_off = offset + (i * stride)
            if c_off + 35 > len(data):
                break
            try:
                tc, abs_b, f_mix, bb, pit_lim = struct.unpack_from("<BBBBB", data, c_off)
                fuel_tank, fuel_cap, fuel_laps = struct.unpack_from("<fff", data, c_off + 5)
                max_rpm, idle_rpm, max_gears, drs_all, drs_dist = struct.unpack_from("<HHBBH", data, c_off + 17)
                act_tyre, vis_tyre, tyre_age, fia_flags = struct.unpack_from("<BBBb", data, c_off + 25)

                code = VISUAL_TYRE_COMPOUNDS.get(vis_tyre, "M")

                ers_store = 0.0
                ers_mode = 1
                ers_h_mguk, ers_h_mguh, ers_dep = 0.0, 0.0, 0.0

                if c_off + 45 <= len(data):
                    # Check ERS offset
                    ers_off = c_off + 37 if stride >= 55 else c_off + 29
                    if ers_off + 17 <= len(data):
                        ers_store, ers_mode = struct.unpack_from("<fB", data, ers_off)
                        ers_h_mguk, ers_h_mguh, ers_dep = struct.unpack_from("<fff", data, ers_off + 5)

                statuses.append(
                    CarStatusFullData(
                        traction_control=tc,
                        anti_lock_brakes=abs_b,
                        fuel_mix=f_mix,
                        front_brake_bias=bb,
                        pit_limiter_status=pit_lim,
                        fuel_in_tank=round(fuel_tank, 2),
                        fuel_capacity=round(fuel_cap, 2),
                        fuel_remaining_laps=round(fuel_laps, 2),
                        max_rpm=max_rpm,
                        idle_rpm=idle_rpm,
                        max_gears=max_gears,
                        drs_allowed=drs_all,
                        drs_activation_distance=drs_dist,
                        actual_tyre_compound=act_tyre,
                        visual_tyre_compound=vis_tyre,
                        tyre_code=code,
                        tyres_age_laps=tyre_age,
                        vehicle_fia_flags=fia_flags,
                        ers_store_energy=round(ers_store, 0),
                        ers_deploy_mode=ers_mode,
                        ers_harvested_this_lap_mguk=round(ers_h_mguk, 0),
                        ers_harvested_this_lap_mguh=round(ers_h_mguh, 0),
                        ers_deployed_this_lap=round(ers_dep, 0),
                    )
                )
            except Exception:
                break
        return cls(car_status=statuses)


# ==============================================================================
# PACKET 10: CAR DAMAGE (FULL EXPANDED)
# ==============================================================================
@dataclass
class CarDamageFullData:
    tyres_wear: Tuple[float, float, float, float]  # RL, RR, FL, FR
    max_wear: float
    tyres_damage: Tuple[int, int, int, int]
    brakes_damage: Tuple[int, int, int, int]
    front_left_wing_damage: int
    front_right_wing_damage: int
    rear_wing_damage: int
    floor_damage: int
    diffuser_damage: int
    sidepod_damage: int
    drs_fault: int
    ers_fault: int
    gearbox_damage: int
    engine_damage: int
    engine_mguh_wear: int
    engine_es_wear: int
    engine_ce_wear: int
    engine_ice_wear: int
    engine_mguk_wear: int
    engine_tc_wear: int
    engine_blown: int
    engine_seized: int


@dataclass
class CarDamageFullPacket:
    car_damage: List[CarDamageFullData] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[CarDamageFullPacket]:
        if len(data) < 29 + 35:
            return None
        offset = 29
        damages: List[CarDamageFullData] = []
        stride = 42 if (len(data) - 29) >= 22 * 42 else (len(data) - 29) // 22

        for i in range(22):
            c_off = offset + (i * stride)
            if c_off + 30 > len(data):
                break
            try:
                w_rl, w_rr, w_fl, w_fr = struct.unpack_from("<ffff", data, c_off)
                tyre_wear = (round(w_rl, 1), round(w_rr, 1), round(w_fl, 1), round(w_fr, 1))
                max_w = max(tyre_wear)

                t_dmg = struct.unpack_from("<4B", data, c_off + 16)
                b_dmg = struct.unpack_from("<4B", data, c_off + 20)

                fl_wing, fr_wing, rw_wing, floor, diff, sidepod, drs_f, ers_f, gb, eng = struct.unpack_from(
                    "<10B", data, c_off + 24
                )

                pu_w = (0, 0, 0, 0, 0, 0, 0, 0)
                if c_off + 42 <= len(data):
                    pu_w = struct.unpack_from("<8B", data, c_off + 34)

                damages.append(
                    CarDamageFullData(
                        tyres_wear=tyre_wear,
                        max_wear=max_w,
                        tyres_damage=t_dmg,
                        brakes_damage=b_dmg,
                        front_left_wing_damage=fl_wing,
                        front_right_wing_damage=fr_wing,
                        rear_wing_damage=rw_wing,
                        floor_damage=floor,
                        diffuser_damage=diff,
                        sidepod_damage=sidepod,
                        drs_fault=drs_f,
                        ers_fault=ers_f,
                        gearbox_damage=gb,
                        engine_damage=eng,
                        engine_mguh_wear=pu_w[0],
                        engine_es_wear=pu_w[1],
                        engine_ce_wear=pu_w[2],
                        engine_ice_wear=pu_w[3],
                        engine_mguk_wear=pu_w[4],
                        engine_tc_wear=pu_w[5],
                        engine_blown=pu_w[6],
                        engine_seized=pu_w[7],
                    )
                )
            except Exception:
                break
        return cls(car_damage=damages)


# ==============================================================================
# PACKET 11: SESSION HISTORY (FULL EXPANDED)
# ==============================================================================
@dataclass
class LapHistoryRecord:
    lap_num: int
    lap_time_ms: int
    sector1_ms: int
    sector2_ms: int
    sector3_ms: int
    lap_valid: bool
    s1_valid: bool
    s2_valid: bool
    s3_valid: bool


@dataclass
class TyreStintRecord:
    stint_num: int
    end_lap: int
    actual_compound: int
    visual_compound: int
    visual_code: str


@dataclass
class SessionHistoryPacket:
    car_idx: int
    num_laps: int
    num_tyre_stints: int
    best_lap_time_lap_num: int
    best_sector1_lap_num: int
    best_sector2_lap_num: int
    best_sector3_lap_num: int
    lap_history: List[LapHistoryRecord] = field(default_factory=list)
    tyre_stints: List[TyreStintRecord] = field(default_factory=list)

    @classmethod
    def unpack(cls, data: bytes) -> Optional[SessionHistoryPacket]:
        if len(data) < 29 + 7:
            return None
        header_size = 29
        car_idx, num_laps, num_stints, best_lap_num, best_s1_num, best_s2_num, best_s3_num = struct.unpack_from(
            "<BBBBBBB", data, header_size
        )

        laps: List[LapHistoryRecord] = []
        laps_offset = header_size + 7
        lap_stride = 14

        for l_idx in range(min(num_laps, 100)):
            curr_off = laps_offset + (l_idx * lap_stride)
            if curr_off + 14 > len(data):
                break
            try:
                lap_ms, s1_ms, s1_m, s2_ms, s2_m, s3_ms, s3_m, flags = struct.unpack_from(
                    "<IHBHBHBB", data, curr_off
                )
                total_s1 = (s1_m * 60000) + s1_ms
                total_s2 = (s2_m * 60000) + s2_ms
                total_s3 = (s3_m * 60000) + s3_ms

                laps.append(
                    LapHistoryRecord(
                        lap_num=l_idx + 1,
                        lap_time_ms=lap_ms,
                        sector1_ms=total_s1,
                        sector2_ms=total_s2,
                        sector3_ms=total_s3,
                        lap_valid=bool(flags & 0x01),
                        s1_valid=bool(flags & 0x02),
                        s2_valid=bool(flags & 0x04),
                        s3_valid=bool(flags & 0x08),
                    )
                )
            except Exception:
                break

        stints_offset = header_size + 7 + (100 * 14)
        stints: List[TyreStintRecord] = []
        for s_idx in range(min(num_stints, 8)):
            curr_off = stints_offset + (s_idx * 3)
            if curr_off + 3 > len(data):
                break
            try:
                end_l, act_c, vis_c = struct.unpack_from("<BBB", data, curr_off)
                stints.append(
                    TyreStintRecord(
                        stint_num=s_idx + 1,
                        end_lap=end_l,
                        actual_compound=act_c,
                        visual_compound=vis_c,
                        visual_code=VISUAL_TYRE_COMPOUNDS.get(vis_c, "M"),
                    )
                )
            except Exception:
                break

        return cls(
            car_idx=car_idx,
            num_laps=num_laps,
            num_tyre_stints=num_stints,
            best_lap_time_lap_num=best_lap_num,
            best_sector1_lap_num=best_s1_num,
            best_sector2_lap_num=best_s2_num,
            best_sector3_lap_num=best_s3_num,
            lap_history=laps,
            tyre_stints=stints,
        )
