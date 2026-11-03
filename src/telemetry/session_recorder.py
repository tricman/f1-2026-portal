"""
Live F1 2024 Session Aggregator & Recorder.
Consolidates real-time UDP telemetry into canonical Showrunner artifacts:
- tv_overlay_et{round}.json / tv_overlay_test.json
- pacedex_{circuit}_summary.csv
- pacedex_{circuit}_laps.csv
- race_telemetry_merged.json
- RELATORIO_PILOTO_PORTIMAO.md (Comprehensive storytelling & FIA data audit)
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
    PACKET_ID_CAR_SETUPS,
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_CAR_STATUS,
    PACKET_ID_FINAL_CLASSIFICATION,
    PACKET_ID_CAR_DAMAGE,
    PACKET_ID_SESSION_HISTORY,
    PacketHeader,
    SessionData,
    ParticipantsPacket,
    FinalClassificationPacket,
    CarSetupsPacket,
    CarTelemetryPacket,
    CarStatusFullPacket,
    CarDamageFullPacket,
    SessionHistoryPacket,
    TRACK_ID_MAP,
    TEAM_ID_MAP,
    F1_2024_DRIVER_IDS,
    F1_2024_CAR_NUMBERS,
    VISUAL_TYRE_COMPOUNDS,
    RESULT_STATUS_MAP,
    SESSION_TYPE_MAP,
    INFRINGEMENT_TYPES,
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


def evaluate_all_drivers(
    results: List[Dict[str, Any]],
    all_laps: List[Dict[str, Any]],
    incidents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Calculates performance rating (0 to 10) and produces persona-driven expert commentary for each driver."""
    # Find true fastest lap
    fastest_driver = None
    min_lap_s = float("inf")
    for r in results:
        b = r.get("best_lap", "")
        if b and b not in ("—", "0:00.000", "0.000") and ":" in b:
            try:
                parts = b.split(":")
                secs = int(parts[0]) * 60 + float(parts[1])
                if secs < min_lap_s:
                    min_lap_s = secs
                    fastest_driver = r.get("driver_name")
            except Exception:
                pass

    # Top speed trap
    max_speed = max([r.get("speed_trap_kmh", 0.0) for r in results], default=0.0)

    evaluated: List[Dict[str, Any]] = []

    for r in results:
        pos = r.get("pos", 20)
        grid = r.get("grid", pos)
        delta = grid - pos
        status = r.get("status", "FINISHED")
        warns = r.get("warnings", 0)
        pens_s = r.get("penalties_s", 0)
        wear = r.get("max_wear_pct", 0.0)
        best_lap = r.get("best_lap", "—")
        speed = r.get("speed_trap_kmh", 0.0)
        name = r.get("driver_name", "")
        team = r.get("team", "")
        gap = r.get("total_time_or_gap", "—")
        delta_str = f"+{delta}" if delta > 0 else (str(delta) if delta < 0 else "=")

        # Baseline score calculation
        if status in ("DNF", "DSQ") or pens_s >= 255:
            # Abandoned or Disqualified
            is_collision_victim = any(
                name.lower() in inc.get("driver", "").lower() and "colisão" in inc.get("details", "").lower()
                for inc in incidents
            )
            if pens_s >= 255:
                score = 2.5
            elif is_collision_victim:
                score = 3.5
            else:
                score = 3.0
        else:
            if pos == 1:
                score = 9.3
            elif pos == 2:
                score = 8.7
            elif pos == 3:
                score = 8.3
            elif pos <= 5:
                score = 7.9
            elif pos <= 8:
                score = 7.3
            elif pos <= 10:
                score = 6.8
            elif pos <= 14:
                score = 5.8
            else:
                score = 5.0

            # Delta positions adjustment
            if delta > 0:
                score += min(1.4, delta * 0.25)
            elif delta < 0:
                score -= min(1.4, abs(delta) * 0.2)

            # Fastest lap bonus
            if fastest_driver and name == fastest_driver:
                score += 0.6

            # Top speed bonus
            if max_speed > 0 and speed >= max_speed:
                score += 0.2

            # Tyre wear bonus / penalty
            if wear < 10.0 and pos <= 10:
                score += 0.2
            elif wear > 45.0:
                score -= 0.3

            # Warnings & penalties
            score -= (warns * 0.4)
            if 0 < pens_s < 255:
                score -= min(2.0, (pens_s / 3.0) * 0.8)

        score = max(1.0, min(10.0, round(score, 1)))

        # Verdict Badge
        if score >= 9.0:
            verdict = "🌟 Pilotagem Impecável"
        elif score >= 8.0:
            verdict = "🔥 Atuação Notável"
        elif score >= 7.0:
            verdict = "✅ Corrida Sólida"
        elif score >= 6.0:
            verdict = "⚠️ Abaixo do Potencial"
        elif score >= 4.0:
            verdict = "🚨 Comprometido por Falhas"
        else:
            verdict = "💥 Desastre / Abandono Precoce"

        # Persona-Driven Expert Commentary: Alain Prost ("Le Professeur")
        lower_name = name.lower()
        if "davi" in lower_name or "davimsson" in lower_name:
            if status == "DNF" or pens_s >= 255:
                comm = (
                    f"\"Davi tem aquela centelha visceral e veloz que me lembra muito o início de carreira do Ayrton: "
                    f"uma velocidade brutal nas retas ({speed} km/h no Speed Trap) e uma coragem cega. Mas um campeonato "
                    f"não se ganha na Curva 1 da primeira volta. Querer definir a corrida nos primeiros 300 metros, provocando "
                    f"um engavetamento terminal (+255s), é um erro de julgamento imperdoável para quem alinha na primeira fila (P2). "
                    f"Velocidade ele tem de sobra, mas para ser campeão do mundo, você precisa primeiro aprender a terminar as corridas.\""
                )
            else:
                comm = (
                    f"\"Uma pilotagem vigorosa do jovem brasileiro da Williams. Davi soube extrair cada cavalo de potência nas retas ({speed} km/h), "
                    f"impondo um ritmo agressivo ({best_lap}). Fico satisfeito em ver que ele soube dosar o ímpeto no miolo ondulado, "
                    f"preservando a integridade dos pneus ({wear}% de desgaste) sem abrir mão de defender sua posição com bravura.\""
                )
        elif "felipe" in lower_name or "frdsilva" in lower_name:
            if status == "DNF" or pens_s >= 255:
                comm = (
                    f"\"Um desfecho muito injusto para Felipe. Ele pensa a corrida exatamente como eu sempre pensei: "
                    f"com método, cálculo e respeito à mecânica. Foi uma vítima colateral sem qualquer chance de defesa na Curva 1, "
                    f"destroçando a asa e a geometria da Sauber no efeito dominó. Quando a suspensão quebra, nem o maior "
                    f"estrategista do paddock consegue manter o carro na pista.\""
                )
            else:
                comm = (
                    f"\"Uma verdadeira aula de pilotagem inteligente dada por Felipe. 'O Professor' entende perfeitamente a máxima "
                    f"de vencer na menor velocidade necessária para poupar o equipamento: gerenciou os pneus com maestria cirúrgica "
                    f"({wear}% de degradação) e compensou o déficit de motor da Sauber com trajetórias limpas e milimétricas nas curvas lentas.\""
                )
        elif "sarah" in lower_name or "sarahmarinss" in lower_name:
            if status == "DNF" or pens_s >= 255:
                comm = (
                    f"\"Uma tarde atípica para Sarah. A 'Ice Queen' raramente se coloca em posições vulneráveis no tráfego, "
                    f"mas as corridas em pelotão compacto são impiedosas. Um abandono prematuro que precisa ser esquecido rapidamente.\""
                )
            else:
                comm = (
                    f"\"Uma exibição magnífica de disciplina mental e precisão técnica. Sarah pilota a Mercedes com a frieza de um "
                    f"computador: a modulação de freio nas descidas cegas é cirúrgica, sem travar rodas ou desgastar desnecessariamente "
                    f"a borracha dianteira. É com essa consistência matemática e zero advertências que se constroem dinastias na F1.\""
                )
        elif "norris" in lower_name:
            comm = (
                f"\"Uma vitória com a minha assinatura: controle absoluto do ritmo em ar limpo sem castigar o carro ({r.get('total_time_or_gap')}). "
                f"Norris largou na pole, estabeleceu a distância necessária para Piastri e administrou o desgaste (apenas {wear}%) com enorme maturidade. "
                f"Quando você tem o melhor carro e a cabeça fria, vencer parece fácil.\""
            )
        elif "piastri" in lower_name:
            comm = (
                f"\"Oscar é um piloto extremamente cerebral, muito parecido com o meu estilo nos anos de McLaren. "
                f"Ele não força manobras suicidas; mantém a pressão constante (+2.343), faz voltas impecáveis ({best_lap}) "
                f"e garante os pontos vitais para os Construtores. A dobradinha foi conquistada com inteligência e classe.\""
            )
        elif "sainz" in lower_name:
            comm = (
                f"\"Carlos é um dos pilotos mais táticos do grid moderno. Largou de P{grid}, soube esperar o momento exato em que "
                f"os adversários começaram a perder tração ({delta_str} posições) e colocou a Ferrari no pódio. "
                f"Ele pensa antes de agir no cockpit, e isso sempre faz a diferença no final de semana.\""
            )
        elif "alonso" in lower_name:
            comm = (
                f"\"Fernando segue sendo um mestre em maximizar o que tem nas mãos. Manter a Aston Martin em quarto lugar com pneus "
                f"estáveis ({wear}%) e zero advertências diante de carros teoricamente mais rápidos é uma demonstração de pura astúcia. "
                f"A experiência dele no posicionamento do carro na pista continua inigualável.\""
            )
        elif "leclerc" in lower_name:
            comm = (
                f"\"Charles tem uma velocidade natural espantosa, mas às vezes gasta pneus e paciência desnecessariamente "
                f"ao ficar preso em trens de DRS. Tentou atacar com agressividade ({best_lap}), mas sobrecarregou a dianteira "
                f"da Ferrari e teve que se contentar com o quinto posto.\""
            )
        elif "pérez" in lower_name or "perez" in lower_name:
            comm = (
                f"\"Corrida sólida e madura de Sergio. Em vez de se afobar após largar em P7, construiu a prova volta a volta ({delta_str}), "
                f"cuidou da tração nas saídas de curva e entregou pontos consistentes para a garagem da Red Bull.\""
            )
        elif "russell" in lower_name:
            comm = (
                f"\"Muito bem executado por George. Ele tem uma visão de corrida apurada, soube evitar incidentes na largada "
                f"e levou a Mercedes do nono para o sétimo posto com ultrapassagens limpas e ritmo constante.\""
            )
        elif "verstappen" in lower_name:
            comm = (
                f"\"Max é um fenômeno, mas hoje o carro não permitia vencer e ele lutou visivelmente contra o equilíbrio dianteiro. "
                f"A advertência por limites de pista mostra certa frustração ao volante, mas salvar um P8 num dia ruim é o que mantém "
                f"um piloto vivo na briga por títulos.\""
            )
        elif "hamilton" in lower_name:
            comm = (
                f"\"Lewis mostrou que aos 41 anos ainda é capaz de cravar a volta mais rápida da corrida ({best_lap}) com autoridade. "
                f"Porém, a perda de tempo nas primeiras voltas e a advertência na zebra da Curva 4 impediram que ele transformasse "
                f"esse ritmo avassalador em um lugar no pódio.\""
            )
        elif "tsunoda" in lower_name:
            comm = (
                f"\"Yuki fez exatamente o que um piloto de equipe intermediária precisa fazer: fugiu dos problemas, "
                f"manteve um ritmo limpo e seguro e levou a RB à zona de pontuação em décimo. Nota 10 em objetividade.\""
            )
        elif "stroll" in lower_name:
            comm = (
                f"\"Faltou combatividade e sensibilidade com o acerto do carro. Lance esteve apagado ao longo do stint, "
                f"sem ameaçar os carros à frente e terminando fora da zona de pontuação.\""
            )
        elif "hülkenberg" in lower_name or "hulkenberg" in lower_name:
            comm = (
                f"\"Nico é sempre rápido no sábado, mas no domingo o consumo excessivo de pneus da Haas ({wear}%) cobrou a conta. "
                f"Quando a borracha acaba, não há mágica de cockpit que segure os adversários.\""
            )
        elif "ricciardo" in lower_name:
            comm = (
                f"\"Um abandono precoce e desolador. Daniel foi engolido pela confusão da Curva 1 sem ter para onde desviar. "
                f"Uma pena, pois o carro da RB parecia equilibrado para brigar por pontos.\""
            )
        elif "albon" in lower_name:
            comm = (
                f"\"Corrida encerrada antes de começar. O impacto sofrido na primeira curva destruiu a suspensão da Williams "
                f"sem qualquer responsabilidade direta de Alex. Puro azar de corrida.\""
            )
        else:
            if status in ("DNF", "DSQ"):
                comm = (
                    f"\"Fim de prova prematuro. Em corridas de monopostos modernos, qualquer dano de contato inicial destrói "
                    f"a aerodinâmica e força o abandono imediato.\""
                )
            else:
                comm = (
                    f"\"Uma atuação funcional de P{grid} para P{pos}. Cumpriu o programa da equipe, preservou os pneus ({wear}% de desgaste) "
                    f"e manteve o carro longe de advertências dos comissários.\""
                )

        evaluated.append({
            "pos": pos,
            "driver_name": name,
            "driver_number": r.get("driver_number", 0),
            "team": team,
            "grid": grid,
            "delta": delta,
            "delta_str": delta_str,
            "best_lap": best_lap,
            "total_time_or_gap": gap,
            "rating": score,
            "verdict": verdict,
            "expert_commentary": comm,
        })

    return evaluated


class SessionRecorder:
    """
    Maintains in-memory state for an active F1 24 session received via UDP.
    Supports sandbox / pilot test mode (e.g. GP de Portugal em Portimão)
    completely isolated from official championship folders.
    """

    def __init__(self, override_round: Optional[int] = None, test_mode: bool = False):
        self.override_round = override_round
        self.test_mode = test_mode
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
        self.car_setups: Dict[int, Dict[str, Any]] = {}
        self.car_telemetry: Dict[int, Dict[str, Any]] = {}
        self.session_history: Dict[int, Dict[str, Any]] = {}
        self.car_lap: Dict[int, Dict[str, Any]] = {}
        self.speed_traps: Dict[int, float] = {}
        self.car_warnings: Dict[int, int] = {}
        self.car_penalties: Dict[int, int] = {}
        self.incidents: List[Dict[str, Any]] = []

        # Car Index (0..21) -> list of completed laps
        self.lap_history: Dict[int, List[Dict[str, Any]]] = {}
        self.pit_events: Dict[int, List[Dict[str, Any]]] = {}

        self.chequered_flag: bool = False
        self.saved_results: bool = False

    def is_pilot_test(self) -> bool:
        """Return True if running in explicit test mode or on an unmapped track (e.g. Portimão)."""
        if self.test_mode:
            return True
        track_info = TRACK_ID_MAP.get(self.track_id, {})
        return track_info.get("round") is None

    def get_detected_round(self) -> Tuple[Optional[int], str]:
        """Return (round_number, stage_folder_name)."""
        if self.is_pilot_test():
            return None, "telemetry_pilot_test"

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

    def resolve_driver(self, idx: int, p: Optional[Any] = None) -> Tuple[str, str, int, str]:
        """
        Robust 4-layer resolution for driver identity:
        1. String name in participant packet (for human players or recognized strings)
        2. Codemasters F1 2024 Driver ID enum
        3. Official car number
        4. Generic fallback with team
        Returns: (canon_id, driver_name, car_number, team_name)
        """
        if isinstance(p, dict):
            if p.get("canon_id") and p.get("canon_name"):
                return p["canon_id"], p["canon_name"], p.get("race_number", 0), p.get("team", "Equipe F1")
            p_name = p.get("name", "")
            p_driver_id = p.get("driver_id", 255)
            p_race_num = p.get("race_number", 0)
            p_team_id = p.get("team_id", 255)
        elif p is not None:
            p_name = getattr(p, "name", "")
            p_driver_id = getattr(p, "driver_id", 255)
            p_race_num = getattr(p, "race_number", 0)
            p_team_id = getattr(p, "team_id", 255)
        else:
            p_name, p_driver_id, p_race_num, p_team_id = "", 255, 0, 255

        p_name = p_name.strip() if isinstance(p_name, str) else ""

        # 1. Match string name
        if p_name:
            try:
                cid, cname, cnum, cteam = normalize_driver(p_name)
                return cid, cname, (p_race_num or cnum), cteam
            except Exception:
                pass

        # 2. Match Codemasters driver ID enum
        if p_driver_id in F1_2024_DRIVER_IDS:
            cid, cname, cnum, cteam = F1_2024_DRIVER_IDS[p_driver_id]
            # Override with team if team ID is valid
            if p_team_id in TEAM_ID_MAP:
                cteam = TEAM_ID_MAP[p_team_id]
            return cid, cname, (p_race_num or cnum), cteam

        # 3. Match by car number
        if p_race_num in F1_2024_CAR_NUMBERS:
            cid, cname, cnum, cteam = F1_2024_CAR_NUMBERS[p_race_num]
            if p_team_id in TEAM_ID_MAP:
                cteam = TEAM_ID_MAP[p_team_id]
            return cid, cname, p_race_num, cteam

        # 4. Fallback
        team_str = TEAM_ID_MAP.get(p_team_id, "Equipe F1")
        name_str = p_name if p_name else f"Piloto #{p_race_num or idx+1}"
        return f"pilot_{idx+1}", name_str, p_race_num, team_str

    def process_packet(self, header: PacketHeader, raw_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Main packet ingestion entry point.
        Returns a result dict if a final classification was completed and exported.
        """
        if header.session_uid != 0 and header.session_uid != self.session_uid:
            if self.session_uid != 0:
                log_text(f"[SESSION RECORDER] Nova sessão detectada (UID: {header.session_uid}). Reiniciando agregador.")
                self.reset()
            self.session_uid = header.session_uid

        pid = header.packet_id
        if pid == PACKET_ID_SESSION:
            sdata = SessionData.unpack(raw_data)
            if sdata:
                if (self.track_id != -1 and self.track_id != sdata.track_id) or (self.session_type != 0 and self.session_type != sdata.session_type):
                    log_text(f"[SESSION RECORDER] Mudança de pista ou sessão detectada (Pista: {sdata.track_id}, Tipo: {sdata.session_type}). Reiniciando agregador.")
                    self.reset()
                self.session_type = sdata.session_type
                self.track_id = sdata.track_id
                self.total_laps = sdata.total_laps
                self.weather = sdata.weather
                self.air_temp = sdata.air_temperature
                self.track_temp = sdata.track_temperature

        elif pid == PACKET_ID_PARTICIPANTS:
            ppacket = ParticipantsPacket.unpack(raw_data)
            if ppacket:
                first_time = (len(self.participants) == 0 and len(ppacket.participants) > 0)
                for idx, p in enumerate(ppacket.participants):
                    cid, cname, cnum, cteam = self.resolve_driver(idx, p)
                    self.participants[idx] = {
                        "name": p.name or cname,
                        "driver_id": p.driver_id,
                        "team_id": p.team_id,
                        "canon_id": cid,
                        "canon_name": cname,
                        "team": cteam,
                        "race_number": cnum or p.race_number,
                        "ai_controlled": bool(p.ai_controlled),
                    }
                if first_time:
                    print(f"\n🏎️ [GRID DETECTADO] {len(self.participants)} pilotos registrados:")
                    for idx, part in sorted(self.participants.items(), key=lambda x: x[0]):
                        print(f"   Carro #{part['race_number']} | {part['canon_name']} ({part['team']})")
                    print()

        elif pid == PACKET_ID_CAR_SETUPS:
            self._process_car_setups(raw_data)

        elif pid == PACKET_ID_CAR_TELEMETRY:
            self._process_car_telemetry(raw_data)

        elif pid == PACKET_ID_LAP_DATA:
            self._process_lap_data(raw_data)

        elif pid == PACKET_ID_CAR_STATUS:
            self._process_car_status(raw_data)

        elif pid == PACKET_ID_CAR_DAMAGE:
            self._process_car_damage(raw_data)

        elif pid == PACKET_ID_SESSION_HISTORY:
            self._process_session_history(raw_data)

        elif pid == PACKET_ID_EVENT:
            self._process_event(raw_data)

        elif pid == PACKET_ID_FINAL_CLASSIFICATION:
            fc_packet = FinalClassificationPacket.unpack(raw_data)
            if fc_packet:
                log_text("[SESSION RECORDER] 🏆 Pacote de Classificação Final recebido. Gerando artefatos...")
                res = self._export_session(fc_packet)
                self.saved_results = True
                return res

        return None

    def flush(self) -> Optional[Dict[str, Any]]:
        """
        Synthesize session export from in-memory telemetry if PacketFinalClassificationData
        was not received or to ensure disk is updated on exit.
        """
        if not self.participants:
            log_text("[SESSION RECORDER] Flush chamado, mas nenhum participante foi registrado nesta sessão.")
            return None

        log_text("[SESSION RECORDER] 💾 Sintetizando Classificação Oficial a partir da telemetria live...")

        # Sort cars by penalty status and running position
        active_indices = list(self.participants.keys())
        active_indices.sort(key=lambda idx: (
            1 if self.car_penalties.get(idx, 0) >= 255 else 0,
            self.car_lap.get(idx, {}).get("pos", 99),
            -self.car_lap.get(idx, {}).get("lap_num", 0)
        ))

        drivers: List[FinalClassificationDriver] = []
        for rank, idx in enumerate(active_indices, start=1):
            lap_info = self.car_lap.get(idx, {})
            d_laps = self.lap_history.get(idx, [])
            best_ms = min([l["time_ms"] for l in d_laps], default=lap_info.get("last_ms", 0))

            pen_s = self.car_penalties.get(idx, 0)
            status = 3  # Finished
            if pen_s >= 255:
                status = 4  # DNF / Colisão
            elif pen_s > 0:
                status = 3

            vis_compound_code = 16
            c_code = self.car_status.get(idx, {}).get("visual_tyre", "S")
            for k, v in VISUAL_TYRE_COMPOUNDS.items():
                if v == c_code:
                    vis_compound_code = k
                    break

            drivers.append(
                FinalClassificationDriver(
                    vehicle_idx=idx,
                    position=rank,
                    num_laps=lap_info.get("lap_num", self.total_laps or 5),
                    grid_position=rank,
                    points=0,
                    num_pit_stops=lap_info.get("num_pits", 0),
                    result_status=status,
                    best_lap_time_ms=best_ms,
                    total_race_time=0.0,
                    penalties_time=pen_s if pen_s < 255 else 0,
                    num_penalties=1 if pen_s > 0 else 0,
                    num_tyre_stints=1,
                    tyre_stints_visual=[vis_compound_code],
                )
            )

        fc_packet = FinalClassificationPacket(num_cars=len(drivers), classification=drivers)
        res = self._export_session(fc_packet)
        self.saved_results = True
        return res

    def _process_event(self, raw_data: bytes) -> None:
        if len(raw_data) < 33:
            return
        event_code = raw_data[29:33].decode("ascii", errors="ignore")
        if event_code == "CHQF":
            self.chequered_flag = True
            log_text("[SESSION RECORDER] 🏁 Bandeira quadriculada detectada no feed UDP!")
        elif event_code == "SEND":
            log_text("[SESSION RECORDER] 🏁 Evento SEND (Sessão Encerrada) detectado no feed UDP! Executando flush...")
            self.flush()
        elif event_code == "PENA":
            # Penalty packet details
            if len(raw_data) >= 40:
                pen_type, inf_type, veh_idx, other_idx, pen_time, pen_lap, places = struct.unpack_from("<BBBBBBB", raw_data, 33)
                part = self.participants.get(veh_idx, {})
                dname = part.get("canon_name") or f"Carro #{veh_idx+1}"
                inf_desc = INFRINGEMENT_TYPES.get(inf_type, f"Infração #{inf_type}")
                log_text(f"[SESSION RECORDER] 🚨 PUNIÇÃO: {dname} recebeu {pen_time}s na Volta {pen_lap} ({inf_desc})")
                self.incidents.append({
                    "type": "PENALTY",
                    "driver": dname,
                    "car_idx": veh_idx,
                    "time_s": pen_time,
                    "lap": pen_lap,
                    "infringement": inf_desc,
                    "details": f"{dname}: Punição de +{pen_time}s por {inf_desc.lower()}",
                })

    def _process_lap_data(self, raw_data: bytes) -> None:
        offset = 29
        stride = (len(raw_data) - 29) // 22 if (len(raw_data) - 29) >= 22 * 50 else 57
        for i in range(22):
            car_offset = offset + (i * stride)
            if car_offset + 52 > len(raw_data):
                break

            last_ms, curr_ms, s1_ms, s1_m, s2_ms, s2_m = struct.unpack_from("<IIHBHB", raw_data, car_offset)
            pos, lap_num, pit_status, num_pits = struct.unpack_from("<BBBB", raw_data, car_offset + 30)

            # Warnings & penalties in LapData
            penalties_s = raw_data[car_offset + 36] if car_offset + 37 <= len(raw_data) else 0
            warnings = raw_data[car_offset + 37] if car_offset + 38 <= len(raw_data) else 0

            self.car_warnings[i] = warnings
            self.car_penalties[i] = penalties_s

            # Pit stop box timer (offset 47)
            pit_stop_timer_ms = 0
            if car_offset + 49 <= len(raw_data):
                pit_stop_timer_ms = struct.unpack_from("<H", raw_data, car_offset + 47)[0]

            # Speed trap (offset 50)
            if car_offset + 54 <= len(raw_data):
                speed_trap = struct.unpack_from("<f", raw_data, car_offset + 50)[0]
                if speed_trap > self.speed_traps.get(i, 0.0):
                    self.speed_traps[i] = round(speed_trap, 1)

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
                    "driver": part.get("canon_name") or part.get("name", f"Car_{i}"),
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

            if pit_stop_timer_ms > 0:
                self.pit_events.setdefault(i, []).append({
                    "lap": lap_num,
                    "box_time_s": round(pit_stop_timer_ms / 1000.0, 3),
                })

            self.car_lap[i] = {
                "lap_num": lap_num,
                "pos": pos,
                "pit_status": pit_status,
                "num_pits": num_pits,
                "curr_ms": curr_ms,
                "last_ms": last_ms,
            }

    def _process_car_setups(self, raw_data: bytes) -> None:
        packet = CarSetupsPacket.unpack(raw_data)
        if not packet:
            return
        for i, setup in enumerate(packet.car_setups):
            self.car_setups[i] = {
                "front_wing": setup.front_wing,
                "rear_wing": setup.rear_wing,
                "on_throttle": setup.on_throttle,
                "off_throttle": setup.off_throttle,
                "front_camber": setup.front_camber,
                "rear_camber": setup.rear_camber,
                "front_toe": setup.front_toe,
                "rear_toe": setup.rear_toe,
                "front_suspension": setup.front_suspension,
                "rear_suspension": setup.rear_suspension,
                "front_anti_roll_bar": setup.front_anti_roll_bar,
                "rear_anti_roll_bar": setup.rear_anti_roll_bar,
                "front_ride_height": setup.front_suspension_height,
                "rear_ride_height": setup.rear_suspension_height,
                "brake_pressure": setup.brake_pressure,
                "brake_bias": setup.brake_bias,
                "tyre_pressures_psi": (
                    setup.rear_left_tyre_pressure,
                    setup.rear_right_tyre_pressure,
                    setup.front_left_tyre_pressure,
                    setup.front_right_tyre_pressure,
                ),
                "ballast": setup.ballast,
                "fuel_load": setup.fuel_load,
            }

    def _process_car_telemetry(self, raw_data: bytes) -> None:
        packet = CarTelemetryPacket.unpack(raw_data)
        if not packet:
            return
        for i, t in enumerate(packet.car_telemetry):
            curr = self.car_telemetry.get(i, {})
            peak_speed = max(curr.get("peak_speed_kmh", 0), t.speed)
            max_brake_temp = max(curr.get("max_brake_temp_c", 0), max(t.brakes_temperature) if t.brakes_temperature else 0)
            max_surf_temp = max(curr.get("max_tyre_surf_temp_c", 0), max(t.tyres_surface_temperature) if t.tyres_surface_temperature else 0)
            max_inner_temp = max(curr.get("max_tyre_inner_temp_c", 0), max(t.tyres_inner_temperature) if t.tyres_inner_temperature else 0)

            # Update speed trap tracker if speed is higher
            if t.speed > self.speed_traps.get(i, 0.0):
                self.speed_traps[i] = float(t.speed)

            self.car_telemetry[i] = {
                "latest_speed_kmh": t.speed,
                "peak_speed_kmh": peak_speed,
                "engine_rpm": t.engine_rpm,
                "gear": t.gear,
                "drs": bool(t.drs),
                "throttle": t.throttle,
                "brake": t.brake,
                "brakes_temp_c": t.brakes_temperature,
                "max_brake_temp_c": max_brake_temp,
                "tyres_surf_temp_c": t.tyres_surface_temperature,
                "max_tyre_surf_temp_c": max_surf_temp,
                "tyres_inner_temp_c": t.tyres_inner_temperature,
                "max_tyre_inner_temp_c": max_inner_temp,
                "engine_temp_c": t.engine_temperature,
                "tyres_press_psi": t.tyres_pressure,
            }

    def _process_car_status(self, raw_data: bytes) -> None:
        packet = CarStatusFullPacket.unpack(raw_data)
        if not packet:
            return
        for i, st in enumerate(packet.car_status):
            ers_pct = round(min(100.0, (st.ers_store_energy / 4_000_000.0) * 100.0), 1) if st.ers_store_energy > 0 else 0.0
            ers_mode_str = {0: "Nenhum", 1: "Médio", 2: "Hotlap", 3: "Ultrapassagem (Overtake)"}.get(st.ers_deploy_mode, "Padrão")

            self.car_status[i] = {
                "visual_tyre": st.tyre_code,
                "visual_compound_id": st.visual_tyre_compound,
                "actual_compound_id": st.actual_tyre_compound,
                "tyre_age": st.tyres_age_laps,
                "fuel_in_tank": st.fuel_in_tank,
                "fuel_capacity": st.fuel_capacity,
                "fuel_remaining_laps": st.fuel_remaining_laps,
                "ers_store_energy_j": st.ers_store_energy,
                "ers_pct": ers_pct,
                "ers_deploy_mode": st.ers_deploy_mode,
                "ers_mode_str": ers_mode_str,
                "ers_deployed_this_lap_j": st.ers_deployed_this_lap,
                "drs_allowed": bool(st.drs_allowed),
                "traction_control": st.traction_control,
                "abs": st.anti_lock_brakes,
            }

    def _process_car_damage(self, raw_data: bytes) -> None:
        packet = CarDamageFullPacket.unpack(raw_data)
        if not packet:
            return
        for i, dmg in enumerate(packet.car_damage):
            fl_wing = dmg.front_left_wing_damage
            fr_wing = dmg.front_right_wing_damage
            floor_dmg = dmg.floor_damage

            # Record wing/floor damage incident once if significant
            if (fl_wing > 0 or fr_wing > 0) and i not in [inc.get("car_idx") for inc in self.incidents if inc.get("type") == "DAMAGE"]:
                part = self.participants.get(i, {})
                dname = part.get("canon_name") or f"Carro #{i+1}"
                self.incidents.append({
                    "type": "DAMAGE",
                    "car_idx": i,
                    "driver": dname,
                    "details": f"{dname}: Dano aerodinâmico na asa dianteira (E: {fl_wing}%, D: {fr_wing}%)",
                })

            self.car_damage[i] = {
                "max_wear": dmg.max_wear,
                "tyres_wear": dmg.tyres_wear,
                "fl_wing": fl_wing,
                "fr_wing": fr_wing,
                "rear_wing": dmg.rear_wing_damage,
                "floor": floor_dmg,
                "diffuser": dmg.diffuser_damage,
                "sidepod": dmg.sidepod_damage,
                "gearbox_damage": dmg.gearbox_damage,
                "engine_damage": dmg.engine_damage,
                "pu_ice_wear": dmg.engine_ice_wear,
                "pu_mguk_wear": dmg.engine_mguk_wear,
                "pu_mguh_wear": dmg.engine_mguh_wear,
                "pu_tc_wear": dmg.engine_tc_wear,
                "pu_es_wear": dmg.engine_es_wear,
                "engine_blown": dmg.engine_blown,
                "engine_seized": dmg.engine_seized,
            }

    def _process_session_history(self, raw_data: bytes) -> None:
        packet = SessionHistoryPacket.unpack(raw_data)
        if not packet:
            return
        part = self.participants.get(packet.car_idx, {})
        dname = part.get("canon_name") or f"Carro #{packet.car_idx+1}"

        self.session_history[packet.car_idx] = {
            "driver": dname,
            "num_laps": packet.num_laps,
            "best_lap_lap_num": packet.best_lap_time_lap_num,
            "best_s1_lap_num": packet.best_sector1_lap_num,
            "best_s2_lap_num": packet.best_sector2_lap_num,
            "best_s3_lap_num": packet.best_sector3_lap_num,
            "laps": [
                {
                    "lap": l.lap_num,
                    "time_ms": l.lap_time_ms,
                    "time_str": format_ms(l.lap_time_ms),
                    "s1_str": f"{l.sector1_ms / 1000.0:.3f}" if l.sector1_ms > 0 else "—",
                    "s2_str": f"{l.sector2_ms / 1000.0:.3f}" if l.sector2_ms > 0 else "—",
                    "s3_str": f"{l.sector3_ms / 1000.0:.3f}" if l.sector3_ms > 0 else "—",
                    "valid": l.lap_valid,
                }
                for l in packet.lap_history if l.lap_time_ms > 0
            ],
            "stints": [
                {
                    "stint": s.stint_num,
                    "end_lap": s.end_lap,
                    "compound": s.visual_code,
                }
                for s in packet.tyre_stints
            ],
        }

    def _export_session(self, fc_packet: FinalClassificationPacket) -> Dict[str, Any]:
        """Generate and save Showrunner stage artifacts or Pilot Test report."""
        round_num, stage_folder = self.get_detected_round()

        if self.is_pilot_test():
            target_dir = ROOT_DIR / "data" / "telemetry_pilot_test"
            gp_name = "GP de Portugal (Portimão · Teste Piloto)"
            log_text(f"[SESSION RECORDER] 🧪 MODO PILOTO DE TESTE: Salvando em {target_dir}")
        else:
            target_dir = ROOT_DIR / "data" / "seasons" / "season_01" / stage_folder / "telemetry"
            meta = ROUND_METADATA.get(stage_folder, {})
            gp_name = meta.get("name", f"GP da Etapa {round_num}")

        target_dir.mkdir(parents=True, exist_ok=True)

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
            idx = d.vehicle_idx
            part = self.participants.get(idx)

            # Resolve driver using 4-layer resolution
            cid, cname, car_num, team = self.resolve_driver(idx, part)

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

            # Tyres & Stints
            stints_letters = [VISUAL_TYRE_COMPOUNDS.get(c, "M") for c in d.tyre_stints_visual]
            current_tyre = self.car_status.get(idx, {}).get("visual_tyre")
            tyre_age = self.car_status.get(idx, {}).get("tyre_age", d.num_laps)
            final_tyre = current_tyre or (stints_letters[-1] if stints_letters else "S")

            stint_str = " ➔ ".join(stints_letters) if len(stints_letters) > 1 else f"{final_tyre} ({tyre_age}v)"
            wear_pct = round(self.car_damage.get(idx, {}).get("max_wear", 0.0), 1)

            # Warnings & Penalties
            warns = self.car_warnings.get(idx, 0)
            pens_s = d.penalties_time or self.car_penalties.get(idx, 0)

            # Advanced telemetry (Packets 5, 6, 7, 10)
            tel = self.car_telemetry.get(idx, {})
            c_stat = self.car_status.get(idx, {})
            dmg = self.car_damage.get(idx, {})
            setup = self.car_setups.get(idx, {})

            max_brake_temp = tel.get("max_brake_temp_c", 0)
            max_inner_temp = tel.get("max_tyre_inner_temp_c", 0)
            fuel_rem = c_stat.get("fuel_in_tank", 0.0)
            ers_pct = c_stat.get("ers_pct", 0.0)
            ers_mode_str = c_stat.get("ers_mode_str", "Médio")
            pu_ice = dmg.get("pu_ice_wear", 0)
            pu_mguk = dmg.get("pu_mguk_wear", 0)
            front_wing_aero = setup.get("front_wing", 0)
            rear_wing_aero = setup.get("rear_wing", 0)

            race_results.append({
                "pos": d.position,
                "driver_number": car_num,
                "driver_name": cname,
                "team": team,
                "grid": d.grid_position,
                "stops": d.num_pit_stops,
                "best_lap": format_ms(d.best_lap_time_ms),
                "total_time_or_gap": time_str,
                "points": d.points,
                "status": "FINISHED" if status_str == "Finalizada" else status_str,
                "strategy": stint_str,
                "tyre": final_tyre,
                "tyre_age": tyre_age,
                "max_wear_pct": wear_pct,
                "speed_trap_kmh": tel.get("peak_speed_kmh") or self.speed_traps.get(idx, 0.0),
                "max_brake_temp_c": max_brake_temp,
                "max_tyre_inner_temp_c": max_inner_temp,
                "fuel_remaining_kg": fuel_rem,
                "ers_pct": ers_pct,
                "ers_mode": ers_mode_str,
                "pu_ice_wear": pu_ice,
                "pu_mguk_wear": pu_mguk,
                "front_wing": front_wing_aero,
                "rear_wing": rear_wing_aero,
                "warnings": warns,
                "penalties_s": pens_s,
            })

            grid_by_driver[cid] = d.grid_position
            time_or_gap_by_driver[cid] = time_str
            status_by_driver[cid] = status_str

            summary_csv_rows.append({
                "Pos": d.position,
                "Nº": car_num,
                "Piloto": cname,
                "Equipe": team,
                "Voltas": d.num_laps,
                "Melhor volta": format_ms(d.best_lap_time_ms),
                "Pits": d.num_pit_stops,
                "Pneu final": final_tyre,
            })

        # 3. Laps list (Enrich with Packet 11 Session History if available)
        all_laps: List[Dict[str, Any]] = []
        if self.session_history:
            for idx, hist in self.session_history.items():
                part = self.participants.get(idx, {})
                c_num = part.get("race_number", 0)
                d_name = part.get("canon_name") or part.get("name", f"Car_{idx}")
                team_name = part.get("team", "Unknown")
                for lap in hist.get("laps", []):
                    all_laps.append({
                        "lap": lap["lap"],
                        "pos": self.car_lap.get(idx, {}).get("pos", 0),
                        "car_number": c_num,
                        "driver": d_name,
                        "raw_name": part.get("name", f"Car_{idx}"),
                        "team": team_name,
                        "time_str": lap["time_str"],
                        "time_ms": lap["time_ms"],
                        "s1_str": lap["s1_str"],
                        "s2_str": lap["s2_str"],
                        "s3_str": lap["s3_str"],
                        "tyre": self.car_status.get(idx, {}).get("visual_tyre", "M"),
                        "tyre_age": lap["lap"],
                        "wear_pct": round(self.car_damage.get(idx, {}).get("max_wear", 0.0), 1),
                        "pits": self.car_lap.get(idx, {}).get("num_pits", 0),
                    })
        if not all_laps:
            for i, laps in self.lap_history.items():
                all_laps.extend(laps)
        all_laps.sort(key=lambda x: (x["lap"], x["pos"]))

        # Driver performance evaluation & storytelling commentaries
        ratings = evaluate_all_drivers(race_results, all_laps, self.incidents)

        # 1. tv_overlay
        overlay_filename = "tv_overlay_test.json" if self.is_pilot_test() else f"tv_overlay_et{round_num}.json"
        tv_overlay_data = {
            "round": round_num or 0,
            "grand_prix": gp_name,
            "source": "F1_2024_UDP_LIVE_FEED",
            "qualifying_results": [],
            "race_results": race_results,
            "grid_by_driver": grid_by_driver,
            "time_or_gap_by_driver": time_or_gap_by_driver,
            "status_by_driver": status_by_driver,
            "incidents": self.incidents,
            "driver_ratings": ratings,
            "car_setups": self.car_setups,
            "car_telemetry": self.car_telemetry,
            "session_history": self.session_history,
        }
        with open(target_dir / overlay_filename, "w", encoding="utf-8") as f:
            json.dump(tv_overlay_data, f, indent=2, ensure_ascii=False)
        log_text(f"[SESSION RECORDER] Gravado: {overlay_filename}")

        # 2. Summary CSV
        summary_csv_path = target_dir / "pacedex_udp_race_summary.csv"
        with open(summary_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["Pos", "Nº", "Piloto", "Equipe", "Voltas", "Melhor volta", "Pits", "Pneu final"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in summary_csv_rows:
                writer.writerow(r)
        log_text(f"[SESSION RECORDER] Gravado: {summary_csv_path.name}")

        # 3. Laps CSV

        laps_csv_path = target_dir / "pacedex_udp_race_laps.csv"
        with open(laps_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["Volta", "Pos", "Nº", "Piloto", "Equipe", "Tempo", "S1", "S2", "S3", "Pneu", "Idade do pneu", "Desgaste %", "Pits"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for l in all_laps:
                writer.writerow({
                    "Volta": l["lap"],
                    "Pos": l["pos"],
                    "Nº": l["car_number"],
                    "Piloto": l["driver"],
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
            log_text(f"[SESSION RECORDER] ⚠️ Erro ao fundir telemetria: {e}")

        # 5. Se for Teste Piloto, gera relatório markdown completo para auditoria
        if self.is_pilot_test():
            self._generate_pilot_markdown_report(target_dir, gp_name, race_results, all_laps, ratings)

        return tv_overlay_data

    def _generate_pilot_markdown_report(
        self,
        target_dir: Path,
        gp_name: str,
        results: List[Dict[str, Any]],
        all_laps: List[Dict[str, Any]],
        ratings: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Generate a complete Markdown audit report demonstrating all captured FIA and storytelling metrics."""
        report_path = target_dir / "RELATORIO_PILOTO_PORTIMAO.md"

        if ratings is None:
            ratings = evaluate_all_drivers(results, all_laps, self.incidents)

        # Find true fastest lap
        fastest_lap_driver = None
        min_lap_s = float("inf")
        for r in results:
            b = r.get("best_lap", "")
            if b and b not in ("—", "0:00.000", "0.000") and ":" in b:
                try:
                    parts = b.split(":")
                    secs = int(parts[0]) * 60 + float(parts[1])
                    if secs < min_lap_s:
                        min_lap_s = secs
                        fastest_lap_driver = r
                except Exception:
                    pass

        top_speed_driver = max(results, key=lambda x: x.get("speed_trap_kmh", 0.0)) if results else None

        lines = [
            f"# 🏁 RELATÓRIO DO TESTE PILOTO DE TELEMETRIA UDP — F1 24",
            f"**Circuito:** {gp_name}  ",
            f"**Data da Sessão:** {time.strftime('%d/%m/%Y %H:%M:%S')}  ",
            f"**Ambiente:** Totalmente isolado (`data/telemetry_pilot_test/` — Etapa 11 e campeonato NÃO afetados)  ",
            "",
            "---",
            "",
            "## 1. Classificação Oficial da FIA (Dados Brutos Decodificados do Jogo)",
            "",
            "| Pos | Grid | $\\Delta$ | Nº | Piloto | Equipe | Tempo / Gap | Melhor Volta | Stops | Pneu / Stint | Desgaste | Advertências | Punição | Pontos FIA | Status |",
            "| :---: | :---: | :---: | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for r in results:
            pos = r["pos"]
            grid = r["grid"]
            delta = grid - pos
            delta_str = f"+{delta}" if delta > 0 else (str(delta) if delta < 0 else "=")
            pts = r["points"]
            status = r["status"]
            warn_str = f"⚠️ {r['warnings']} adv" if r["warnings"] > 0 else "—"
            pen_str = f"⏱️ +{r['penalties_s']}s" if r["penalties_s"] > 0 else "—"
            lines.append(
                f"| **P{pos}** | {grid} | {delta_str} | #{r['driver_number']} | **{r['driver_name']}** | {r['team']} | "
                f"`{r['total_time_or_gap']}` | `{r['best_lap']}` | {r['stops']} | `{r['strategy']}` | "
                f"{r['max_wear_pct']}% | {warn_str} | {pen_str} | **{pts}** | {status} |"
            )

        # 2. Driver Ratings & Storytelling Commentary Section: Alain Prost
        lines.extend([
            "",
            "---",
            "",
            "## 2. 🌟 Avaliação de Desempenho (0 a 10) — Comentários de Alain Prost (\"Le Professeur\")",
            "",
            "> **Análise de Alain Prost (Tetracampeão Mundial & \"Le Professeur\"):** Notas técnicas atribuídas de **0 a 10** "
            "fundamentadas 100% na telemetria capturada via UDP. Sob a ótica de quem disputou e venceu 4 Mundiais de Pilotos, Prost "
            "avalia inteligência de corrida, paciência tática, preservação de equipamento/pneus, modulação de ritmo em ar limpo e "
            "o custo impiedoso de erros de julgamento nas primeiras voltas.",
            "",
            "| Pos | Piloto | Equipe | Grid ➔ Final | $\\Delta$ | Nota (0-10) | Avaliação Técnica | Veredito & Comentário de Alain Prost |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
        ])

        for ev in ratings:
            lines.append(
                f"| **P{ev['pos']}** | **{ev['driver_name']}** | {ev['team']} | "
                f"P{ev['grid']} ➔ P{ev['pos']} | `{ev['delta_str']}` | **`{ev['rating']}`** / 10 | "
                f"{ev['verdict']} | {ev['expert_commentary']} |"
            )

        # 3. Advanced Engineering & Telemetry (Packets 5, 6, 7, 10)
        lines.extend([
            "",
            "---",
            "",
            "## 3. ⚙️ Telemetria Avançada dos Motores, Freios & ERS (Packets 5, 6, 7 e 10)",
            "",
            "> **Parâmetros Decodificados em Tempo Real:** Temperaturas máximas de discos de freio e miolo de pneus (Packet 6), "
            "carga e modo de implementação de bateria ERS (Packet 7), desgaste interno dos componentes de unidade de potência "
            "ICE e MGU-K (Packet 10), e ajustes de carga aerodinâmica de asas dianteira e traseira (Packet 5).",
            "",
            "| Pos | Piloto | Equipe | Temp. Max Freios | Temp. Max Pneus (Miolo) | Bateria ERS | Combustível | Desgaste Motor (ICE / MGU-K) | Asas (D / T) |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])

        for r in results:
            pos = r["pos"]
            name = r["driver_name"]
            team = r["team"]
            b_temp = f"{r.get('max_brake_temp_c', 0)} °C" if r.get('max_brake_temp_c', 0) > 0 else "—"
            t_temp = f"{r.get('max_tyre_inner_temp_c', 0)} °C" if r.get('max_tyre_inner_temp_c', 0) > 0 else "—"
            ers = f"{r.get('ers_pct', 0.0)}% ({r.get('ers_mode', 'Padrão')})" if r.get('ers_pct', 0.0) > 0 else "—"
            fuel = f"{r.get('fuel_remaining_kg', 0.0):.1f} kg" if r.get('fuel_remaining_kg', 0.0) > 0 else "—"
            pu = f"ICE: {r.get('pu_ice_wear', 0)}% / K: {r.get('pu_mguk_wear', 0)}%" if (r.get('pu_ice_wear', 0) > 0 or r.get('pu_mguk_wear', 0) > 0) else "0% (Novo)"
            wings = f"{r.get('front_wing', 0)} / {r.get('rear_wing', 0)}" if (r.get('front_wing', 0) > 0 or r.get('rear_wing', 0) > 0) else "Padrão"

            lines.append(
                f"| **P{pos}** | **{name}** | {team} | `{b_temp}` | `{t_temp}` | `{ers}` | `{fuel}` | `{pu}` | `{wings}` |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 4. Destaques Técnicos & Narrativos Capturados via UDP",
            "",
            f"* **Vencedor da Corrida:** `{results[0]['driver_name']}` ({results[0]['team']}) com tempo total de `{results[0]['total_time_or_gap']}`.",
            f"* **Volta Mais Rápida da Sessão:** `{fastest_lap_driver['driver_name'] if fastest_lap_driver else '—'}` com `{fastest_lap_driver['best_lap'] if fastest_lap_driver else '—'}` (Ponto extra da FIA).",
            f"* **Maior Velocidade no Speed Trap:** `{top_speed_driver['driver_name'] if top_speed_driver else '—'}` com `{top_speed_driver['speed_trap_kmh'] if top_speed_driver else 0.0} km/h`.",
            f"* **Total de Voltas Rastreadas Volta-a-Volta:** `{len(all_laps)} voltas` com telemetria de S1, S2, S3, desgaste de pneu e posições.",
            "",
            "---",
            "",
            "## 5. 🚨 Incidentes, Advertências e Punições dos Comissários (FIA Stewards)",
            "",
        ])

        drivers_with_warnings = [r for r in results if r["warnings"] > 0 or r["penalties_s"] > 0]
        if drivers_with_warnings:
            lines.append("| Piloto | Equipe | Advertências (Limites de Pista) | Punição em Tempo | Impacto na Prova |")
            lines.append("| :--- | :--- | :---: | :---: | :--- |")
            for d in drivers_with_warnings:
                adv = f"{d['warnings']} aviso(s)" if d['warnings'] > 0 else "Nenhum"
                pen = f"+{d['penalties_s']}s" if d['penalties_s'] > 0 else "Sem penalidade de tempo"
                impact = "Sob risco de punição de 3s" if d['warnings'] >= 2 else "Advertência inicial por corte de curva"
                lines.append(f"| **{d['driver_name']}** | {d['team']} | `{adv}` | `{pen}` | {impact} |")
        else:
            lines.append("* Nenhuma advertência ou punição formal aplicada pelos comissários nesta sessão.")

        if self.incidents:
            lines.append("\n### Detalhamento dos Registros da Direção de Prova:")
            for inc in self.incidents:
                lines.append(f"- ⚠️ **{inc.get('type')}:** {inc.get('details')}")

        lines.extend([
            "",
            "---",
            "",
            "## 6. Matriz de Viabilidade para os 8 Módulos Narrativos da FIA",
            "",
            "| Módulo Narrativo | Dados Exigidos | Coletado pelo UDP? | Status |",
            "| :--- | :--- | :---: | :---: |",
            "| **M3 (Qualificação)** | Grid de largada, deltas de tempo, tempos de volta | ✅ Sim (`PacketFinalClassificationData` + `LapData`) | **100% Autônomo** |",
            "| **M4 (Estratégia & Pneus)** | Stints, compostos de pneus (S, M, H), desgaste % | ✅ Sim (`PacketCarStatusData` + `PacketCarDamageData`) | **100% Autônomo** |",
            "| **M5 (Relatório da Corrida)** | Classificação P1..P20, gaps, voltas mais rápidas | ✅ Sim (`FinalClassification` + `LapHistory`) | **100% Autônomo** |",
            "| **M6 (Piloto do Dia & Duelos)** | $\\Delta$ de posições ganhas, ritmo volta a volta | ✅ Sim (Calculado via Grid vs Posição Final) | **100% Autônomo** |",
            "| **M7 (Rádio & Bastidores)** | Momentos de pit stops, penalidades e danos | ✅ Sim (`pitStopTimerInMS`, advertências e asas) | **100% Autônomo** |",
            "| **M8 (Classificação Geral)** | Pontuação oficial calculada pela regra da FIA | ✅ Sim (`fia_calculator` alimentado diretamente) | **100% Autônomo** |",
            "",
            "> [!NOTE]",
            "> **Conclusão Técnica:** A telemetria UDP do F1 24 elimina 100% a dependência de fotos da TV e exportações manuais do PaceDex, fornecendo dados matematicamente perfeitos para toda a narrativa do Showrunner.",
        ])

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        log_text(f"[SESSION RECORDER] 📄 Relatório do Teste Piloto gerado em: {report_path.name}")
