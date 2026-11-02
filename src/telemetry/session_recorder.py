"""
Live F1 2024 Session Aggregator & Recorder.
Consolidates real-time UDP telemetry into canonical Showrunner artifacts:
- tv_overlay_et{round}.json
- pacedex_{circuit}_summary.csv
- pacedex_{circuit}_laps.csv
- race_telemetry_merged.json
"""
from __future__ import annotations

import csv
import json
import struct
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.logger import log_text
from src.telemetry.f1_2024_structs import (
    PACKET_ID_SESSION,
    PACKET_ID_LAP_DATA,
    PACKET_ID_EVENT,
    PACKET_ID_PARTICIPANTS,
    PACKET_ID_CAR_STATUS,
    PACKET_ID_FINAL_CLASSIFICATION,
    PACKET_ID_CAR_DAMAGE,
    PacketHeader,
    SessionData,
    ParticipantsPacket,
    FinalClassificationPacket,
    TRACK_ID_MAP,
    TEAM_ID_MAP,
    VISUAL_TYRE_COMPOUNDS,
    RESULT_STATUS_MAP,
    SESSION_TYPE_MAP,
)
from src.telemetry_merger import DRIVER_ID_MAP, normalize_driver, merge_race_telemetry
from src.portal_builder import ROUND_METADATA

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def format_ms(ms: int) -> str:
    """Format milliseconds into M:SS.mmm or — if invalid."""
    if ms <= 0 or ms >= 999_999_999:
        return "—"
    mins = ms // 60000
    secs = (ms % 60000) / 1000.0
    if mins > 0:
        return f"{mins}:{secs:06.3f}"
    return f"{secs:.3f}"


def format_race_time(seconds: float) -> str:
    """Format total race seconds into MM:SS.mmm."""
    if seconds <= 0:
        return "—"
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


class SessionRecorder:
    """
    Maintains in-memory state for an active F1 24 session received via UDP.
    Automatically generates required stage files when final classification arrives.
    """

    def __init__(self, override_round: Optional[int] = None):
        self.override_round = override_round
        self.reset()

    def reset(self) -> None:
        self.session_uid: int = 0
        self.session_type: int = 0
        self.track_id: int = -1
        self.total_laps: int = 0
        self.weather: int = 0
        self.air_temp: int = 0
        self.track_temp: int = 0

        # Car Index (0..21) -> metadata
        self.participants: Dict[int, Dict[str, Any]] = {}
        # Car Index (0..21) -> current lap, position, tyre wear, etc.
        self.car_status: Dict[int, Dict[str, Any]] = {}
        self.car_damage: Dict[int, Dict[str, Any]] = {}
        self.car_lap: Dict[int, Dict[str, Any]] = {}

        # Car Index (0..21) -> list of completed laps
        self.lap_history: Dict[int, List[Dict[str, Any]]] = {}
        self.pit_events: Dict[int, List[Dict[str, Any]]] = {}

        self.chequered_flag: bool = False
        self.saved_results: bool = False

    def get_detected_round(self) -> Tuple[int, str]:
        """Return (round_number, stage_folder_name)."""
        if self.override_round:
            r = self.override_round
            for folder, meta in ROUND_METADATA.items():
                if meta["num"] == r:
                    return r, folder
            return r, f"et_{r:02d}"

        # Detect from track ID
        track_info = TRACK_ID_MAP.get(self.track_id, {})
        detected = track_info.get("round")
        if detected:
            folder = track_info.get("folder") or f"et_{detected:02d}"
            return detected, folder

        # Fallback to current season_state.json if available
        state_file = ROOT_DIR / "data" / "state" / "session_state.json"
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    st = json.load(f)
                    curr = st.get("current_round") or st.get("last_completed_round", 10) + 1
                    for folder, meta in ROUND_METADATA.items():
                        if meta["num"] == curr:
                            return curr, folder
                    return curr, f"et_{curr:02d}"
            except Exception:
                pass

        return 11, "et_11_austria"

    def process_packet(self, header: PacketHeader, raw_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Main packet ingestion entry point.
        Returns a result dict if a final classification was completed and exported.
        """
        if header.session_uid != self.session_uid and self.session_uid != 0:
            # New session started
            log_text(f"[SESSION RECORDER] Nova sessão detectada (UID: {header.session_uid}). Reiniciando agregador.")
            self.reset()
        self.session_uid = header.session_uid

        pid = header.packet_id
        if pid == PACKET_ID_SESSION:
            sdata = SessionData.unpack(raw_data)
            if sdata:
                self.session_type = sdata.session_type
                self.track_id = sdata.track_id
                self.total_laps = sdata.total_laps
                self.weather = sdata.weather
                self.air_temp = sdata.air_temperature
                self.track_temp = sdata.track_temperature

        elif pid == PACKET_ID_PARTICIPANTS:
            ppacket = ParticipantsPacket.unpack(raw_data)
            if ppacket:
                for idx, p in enumerate(ppacket.participants):
                    # Canonical driver match
                    canon_id = None
                    canon_name = p.name
                    canon_team = TEAM_ID_MAP.get(p.team_id, "Desconhecida")
                    try:
                        cid, cname, _, cteam = normalize_driver(p.name)
                        canon_id = cid
                        canon_name = cname
                        canon_team = cteam
                    except Exception:
                        pass

                    self.participants[idx] = {
                        "name": p.name,
                        "canon_id": canon_id,
                        "canon_name": canon_name,
                        "team": canon_team,
                        "race_number": p.race_number,
                        "ai_controlled": bool(p.ai_controlled),
                    }

        elif pid == PACKET_ID_LAP_DATA:
            self._process_lap_data(raw_data)

        elif pid == PACKET_ID_CAR_STATUS:
            self._process_car_status(raw_data)

        elif pid == PACKET_ID_CAR_DAMAGE:
            self._process_car_damage(raw_data)

        elif pid == PACKET_ID_EVENT:
            if len(raw_data) >= 33:
                event_code = raw_data[29:33].decode("ascii", errors="ignore")
                if event_code == "CHQF":
                    self.chequered_flag = True
                    log_text("[SESSION RECORDER] 🏁 Bandeira quadriculada detectada no feed UDP!")

        elif pid == PACKET_ID_FINAL_CLASSIFICATION:
            fc_packet = FinalClassificationPacket.unpack(raw_data)
            if fc_packet and not self.saved_results:
                log_text("[SESSION RECORDER] 🏆 Pacote de Classificação Final recebido. Gerando artefatos...")
                res = self._export_session(fc_packet)
                self.saved_results = True
                return res

        return None

    def _process_lap_data(self, raw_data: bytes) -> None:
        offset = 29
        stride = 57 if (len(raw_data) - 29) >= 22 * 57 else 56
        for i in range(22):
            car_offset = offset + (i * stride)
            if car_offset + 32 > len(raw_data):
                break
            # Unpack key lap fields:
            # uint32 lastLapTimeInMS (offset 0)
            # uint32 currentLapTimeInMS (offset 4)
            # uint16 sector1TimeInMS (offset 8)
            # uint8 sector1Minutes (offset 10)
            # uint16 sector2TimeInMS (offset 11)
            # uint8 sector2Minutes (offset 13)
            # ...
            # uint8 carPosition (offset 22)
            # uint8 currentLapNum (offset 23)
            # uint8 pitStatus (offset 24)
            # uint8 numPitStops (offset 25)
            last_ms, curr_ms, s1_ms, s1_m, s2_ms, s2_m = struct.unpack_from("<IIHBHB", raw_data, car_offset)
            pos, lap_num, pit_status, num_pits = struct.unpack_from("<BBBB", raw_data, car_offset + 22)

            prev = self.car_lap.get(i)
            # Detect completed lap
            if prev and lap_num > prev.get("lap_num", 0) and last_ms > 0:
                wear = self.car_damage.get(i, {}).get("max_wear", 0.0)
                tyre = self.car_status.get(i, {}).get("visual_tyre", "M")
                tyre_age = self.car_status.get(i, {}).get("tyre_age", 0)
                part = self.participants.get(i, {})

                s1_total = (s1_m * 60000) + s1_ms
                s2_total = (s2_m * 60000) + s2_ms
                s3_total = max(0, last_ms - s1_total - s2_total) if last_ms > (s1_total + s2_total) else 0

                lap_entry = {
                    "lap": prev.get("lap_num", 1),
                    "pos": pos,
                    "car_number": part.get("race_number", 0),
                    "driver": part.get("canon_id") or part.get("name", f"Car_{i}"),
                    "raw_name": part.get("name", f"Car_{i}"),
                    "team": part.get("team", "Unknown"),
                    "time_str": format_ms(last_ms),
                    "time_ms": last_ms,
                    "s1_str": f"{s1_total / 1000.0:.3f}" if s1_total else "—",
                    "s2_str": f"{s2_total / 1000.0:.3f}" if s2_total else "—",
                    "s3_str": f"{s3_total / 1000.0:.3f}" if s3_total else "—",
                    "tyre": tyre,
                    "tyre_age": tyre_age,
                    "wear_pct": round(wear, 1),
                    "pits": num_pits,
                }
                self.lap_history.setdefault(i, []).append(lap_entry)

            self.car_lap[i] = {
                "lap_num": lap_num,
                "pos": pos,
                "pit_status": pit_status,
                "num_pits": num_pits,
                "curr_ms": curr_ms,
                "last_ms": last_ms,
            }

    def _process_car_status(self, raw_data: bytes) -> None:
        offset = 29
        stride = 47 if (len(raw_data) - 29) >= 22 * 47 else 45
        for i in range(22):
            car_offset = offset + (i * stride)
            if car_offset + 18 > len(raw_data):
                break
            # Visual compound is at offset 15, tyre age at offset 16
            visual_compound = raw_data[car_offset + 15] if car_offset + 15 < len(raw_data) else 17
            tyre_age = raw_data[car_offset + 16] if car_offset + 16 < len(raw_data) else 0
            code = VISUAL_TYRE_COMPOUNDS.get(visual_compound, "M")
            self.car_status[i] = {
                "visual_tyre": code,
                "tyre_age": tyre_age,
            }

    def _process_car_damage(self, raw_data: bytes) -> None:
        offset = 29
        stride = 42 if (len(raw_data) - 29) >= 22 * 42 else 40
        for i in range(22):
            car_offset = offset + (i * stride)
            if car_offset + 16 > len(raw_data):
                break
            # 4 floats = tyres wear: RL, RR, FL, FR
            w_rl, w_rr, w_fl, w_fr = struct.unpack_from("<ffff", raw_data, car_offset)
            max_w = max(w_rl, w_rr, w_fl, w_fr)
            self.car_damage[i] = {
                "max_wear": max_w,
                "rl": w_rl,
                "rr": w_rr,
                "fl": w_fl,
                "fr": w_fr,
            }

    def _export_session(self, fc_packet: FinalClassificationPacket) -> Dict[str, Any]:
        """Generate and save all Showrunner stage artifacts."""
        round_num, stage_folder = self.get_detected_round()
        target_dir = ROOT_DIR / "data" / "seasons" / "season_01" / stage_folder / "telemetry"
        target_dir.mkdir(parents=True, exist_ok=True)

        meta = ROUND_METADATA.get(stage_folder, {})
        gp_name = meta.get("name", f"GP da Etapa {round_num}")

        # Sort classified drivers by finishing position
        classified = sorted(
            [d for d in fc_packet.classification if d.position > 0],
            key=lambda d: d.position
        )

        p1_time = classified[0].total_race_time if classified else 0.0

        race_results: List[Dict[str, Any]] = []
        grid_by_driver: Dict[str, int] = {}
        time_or_gap_by_driver: Dict[str, str] = {}
        status_by_driver: Dict[str, str] = {}

        summary_csv_rows: List[Dict[str, Any]] = []

        for d in classified:
            # Find matching participant
            # Index is typically the position in fc_packet.classification
            idx = fc_packet.classification.index(d)
            part = self.participants.get(idx, {})
            name = part.get("canon_name") or part.get("name", f"Piloto {d.position}")
            canon_id = part.get("canon_id") or part.get("name", f"pilot_{d.position}").lower()
            team = part.get("team", "Equipe F1")
            car_num = part.get("race_number", 0)

            # Total time or gap
            if d.position == 1:
                time_str = format_race_time(d.total_race_time)
            elif d.result_status in (4, 7):
                time_str = "DNF"
            elif d.result_status == 5:
                time_str = "DSQ"
            else:
                gap_s = d.total_race_time - p1_time
                time_str = f"+{gap_s:.3f}" if gap_s > 0 else "—"

            status_str = "Finalizada"
            if d.result_status in (4, 7):
                status_str = "DNF"
            elif d.result_status == 5:
                status_str = "DSQ"

            stints_letters = [VISUAL_TYRE_COMPOUNDS.get(c, "M") for c in d.tyre_stints_visual]
            final_tyre = stints_letters[-1] if stints_letters else "M"

            race_results.append({
                "pos": d.position,
                "driver_number": car_num,
                "driver_name": name,
                "team": team,
                "grid": d.grid_position,
                "stops": d.num_pit_stops,
                "best_lap": format_ms(d.best_lap_time_ms),
                "total_time_or_gap": time_str,
                "points": d.points,
                "status": "FINISHED" if status_str == "Finalizada" else status_str,
            })

            grid_by_driver[canon_id] = d.grid_position
            time_or_gap_by_driver[canon_id] = time_str
            status_by_driver[canon_id] = status_str

            summary_csv_rows.append({
                "Pos": d.position,
                "Nº": car_num,
                "Piloto": name,
                "Equipe": team,
                "Voltas": d.num_laps,
                "Melhor volta": format_ms(d.best_lap_time_ms),
                "Pits": d.num_pit_stops,
                "Pneu final": final_tyre,
            })

        # 1. tv_overlay_et{round}.json
        tv_overlay_data = {
            "round": round_num,
            "grand_prix": gp_name,
            "source": "F1_2024_UDP_LIVE_FEED",
            "qualifying_results": [],
            "race_results": race_results,
            "grid_by_driver": grid_by_driver,
            "time_or_gap_by_driver": time_or_gap_by_driver,
            "status_by_driver": status_by_driver,
            "incidents": [],
        }
        tv_overlay_path = target_dir / f"tv_overlay_et{round_num}.json"
        with open(tv_overlay_path, "w", encoding="utf-8") as f:
            json.dump(tv_overlay_data, f, indent=2, ensure_ascii=False)
        log_text(f"[SESSION RECORDER] Gravado: {tv_overlay_path.name}")

        # 2. Summary CSV
        summary_csv_path = target_dir / f"pacedex_udp_race_summary.csv"
        with open(summary_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["Pos", "Nº", "Piloto", "Equipe", "Voltas", "Melhor volta", "Pits", "Pneu final"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in summary_csv_rows:
                writer.writerow(r)
        log_text(f"[SESSION RECORDER] Gravado: {summary_csv_path.name}")

        # 3. Laps CSV
        all_laps: List[Dict[str, Any]] = []
        for i, laps in self.lap_history.items():
            all_laps.extend(laps)
        all_laps.sort(key=lambda x: (x["lap"], x["pos"]))

        laps_csv_path = target_dir / f"pacedex_udp_race_laps.csv"
        with open(laps_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["Volta", "Pos", "Nº", "Piloto", "Equipe", "Tempo", "S1", "S2", "S3", "Pneu", "Idade do pneu", "Desgaste %", "Pits"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for l in all_laps:
                writer.writerow({
                    "Volta": l["lap"],
                    "Pos": l["pos"],
                    "Nº": l["car_number"],
                    "Piloto": l["raw_name"],
                    "Equipe": l["team"],
                    "Tempo": l["time_str"],
                    "S1": l["s1_str"],
                    "S2": l["s2_str"],
                    "S3": l["s3_str"],
                    "Pneu": l["tyre"],
                    "Idade do pneu": l["tyre_age"],
                    "Desgaste %": l["wear_pct"],
                    "Pits": l["pits"],
                })
        log_text(f"[SESSION RECORDER] Gravado: {laps_csv_path.name} ({len(all_laps)} voltas coletadas)")

        # 4. Synthesize race_telemetry_merged.json
        try:
            merged = merge_race_telemetry(
                summary_csv=summary_csv_path,
                laps_csv=laps_csv_path,
                tv_overlay_data=tv_overlay_data,
            )
            merged_path = target_dir / "race_telemetry_merged.json"
            with open(merged_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            log_text(f"[SESSION RECORDER] ✅ race_telemetry_merged.json sintetizado diretamente do feed UDP!")
        except Exception as e:
            log_text(f"[SESSION RECORDER] ⚠️ Erro ao fundir telemetria automaticamente: {e}")

        return tv_overlay_data
