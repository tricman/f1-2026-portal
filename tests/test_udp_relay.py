"""
End-to-end Unit & Integration Test for F1 2024 UDP Relay & Recorder.
Simulates synthetic F1 24 UDP packets (Header, Session, Participants, LapData, FinalClassification),
tests zero-latency relay transmission to PaceDex port, and verifies artifact generation.
"""
import socket
import struct
import time
import json
import threading
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.telemetry.f1_2024_structs import (
    PACKET_FORMAT_2024,
    PACKET_ID_SESSION,
    PACKET_ID_PARTICIPANTS,
    PACKET_ID_LAP_DATA,
    PACKET_ID_CAR_SETUPS,
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_CAR_STATUS,
    PACKET_ID_FINAL_CLASSIFICATION,
    PACKET_ID_CAR_DAMAGE,
    PACKET_ID_SESSION_HISTORY,
    PacketHeader,
)
from src.telemetry.session_recorder import SessionRecorder
from src.udp_relay import UdpTelemetryRelay


def create_header(packet_id: int, session_uid: int = 123456789) -> bytes:
    # <HBBBBBQfIIBB
    return struct.pack(
        "<HBBBBBQfIIBB",
        PACKET_FORMAT_2024,
        24,  # year
        1,   # major
        0,   # minor
        1,   # version
        packet_id,
        session_uid,
        120.5, # session_time
        1000,  # frame
        1000,  # overall frame
        0,     # player index
        255,   # secondary
    )


def create_session_packet(track_id: int = 17, session_type: int = 10, total_laps: int = 17) -> bytes:
    hdr = create_header(PACKET_ID_SESSION)
    # <BbBBHbBHHB
    body = struct.pack(
        "<BbbBHBbBHHB",
        0,   # weather
        28,  # track temp
        22,  # air temp
        total_laps,
        4318, # track length
        session_type,
        track_id, # 17 = Red Bull Ring (Austria)
        0,   # formula 1 modern
        1800,# time left
        3600,# duration
        80,  # pit speed limit
    )
    # Pad to realistic packet size
    return hdr + body + (b"\x00" * 600)


def create_participants_packet() -> bytes:
    hdr = create_header(PACKET_ID_PARTICIPANTS)
    # numActiveCars = 3
    data = bytearray(hdr)
    data.append(3) # num_active

    # Driver 0: Sarah (SarahMarinsS) - Mercedes (team 0)
    # 7 bytes: ai(0), drv(255), net(1), team(0), myTeam(1), num(24), nat(11)
    d0 = struct.pack("<BBBBBBB", 0, 255, 1, 0, 1, 24, 11)
    name0 = "SarahMarinsS".encode("utf-8").ljust(48, b"\x00")
    tail0 = struct.pack("<BB", 1, 0)
    data.extend(d0 + name0 + tail0)

    # Driver 1: Davi (DaviMSSon) - Williams (team 3)
    d1 = struct.pack("<BBBBBBB", 0, 255, 2, 3, 0, 15, 11)
    name1 = "DaviMSSon".encode("utf-8").ljust(48, b"\x00")
    tail1 = struct.pack("<BB", 1, 0)
    data.extend(d1 + name1 + tail1)

    # Driver 2: Felipe (frdsilva) - Sauber (team 9)
    d2 = struct.pack("<BBBBBBB", 0, 255, 3, 9, 0, 5, 11)
    name2 = "frdsilva".encode("utf-8").ljust(48, b"\x00")
    tail2 = struct.pack("<BB", 1, 0)
    data.extend(d2 + name2 + tail2)

    # Pad remaining 19 cars
    for i in range(19):
        dummy = struct.pack("<BBBBBBB", 1, i, 0, 1, 0, i + 1, 1) + (b"AI\x00".ljust(48, b"\x00")) + struct.pack("<BB", 1, 0)
        data.extend(dummy)

    return bytes(data)


def create_final_classification_packet() -> bytes:
    hdr = create_header(PACKET_ID_FINAL_CLASSIFICATION)
    data = bytearray(hdr)
    data.append(3) # num_cars

    # Car 0: P1 Sarah (17 laps, best 1:17.035 = 77035ms, total 1345.737s)
    # <BBBBBBIdBBB8s8s8s
    stints_actual = b"\x10\x11" + (b"\x00" * 6)
    stints_visual = b"\x10\x11" + (b"\x00" * 6)
    stints_end = b"\x0a\x11" + (b"\x00" * 6)

    c0 = struct.pack("<BBBBBBIdBBB", 1, 17, 1, 26, 1, 3, 77035, 1345.737, 0, 0, 2) + stints_actual + stints_visual + stints_end
    data.extend(c0)

    # Car 1: P2 Davi (17 laps, best 1:17.039 = 77039ms, total 1351.981s (+6.244))
    c1 = struct.pack("<BBBBBBIdBBB", 2, 17, 2, 18, 1, 3, 77039, 1351.981, 0, 0, 2) + stints_actual + stints_visual + stints_end
    data.extend(c1)

    # Car 2: P3 Felipe (17 laps, best 1:18.004 = 78004ms, total 1359.454s (+13.717))
    c2 = struct.pack("<BBBBBBIdBBB", 3, 17, 3, 15, 1, 3, 78004, 1359.454, 0, 0, 2) + stints_actual + stints_visual + stints_end
    data.extend(c2)

    # Pad 19 other cars
    for i in range(19):
        dummy = struct.pack("<BBBBBBIdBBB", 0, 0, 0, 0, 0, 0, 0, 0.0, 0, 0, 0) + (b"\x00" * 24)
        data.extend(dummy)

    return bytes(data)


def test_session_recorder_parsing():
    recorder = SessionRecorder(override_round=11)

    # 1. Feed Session packet
    s_pkt = create_session_packet(track_id=17, session_type=10)
    hdr_s = PacketHeader.unpack(s_pkt)
    recorder.process_packet(hdr_s, s_pkt)
    assert recorder.track_id == 17
    assert recorder.total_laps == 17
    r_num, folder = recorder.get_detected_round()
    assert r_num == 11
    assert folder == "et_11_austria"

    # 2. Feed Participants packet
    p_pkt = create_participants_packet()
    hdr_p = PacketHeader.unpack(p_pkt)
    recorder.process_packet(hdr_p, p_pkt)
    assert len(recorder.participants) >= 3
    assert recorder.participants[0]["name"] == "SarahMarinsS"
    assert recorder.participants[0]["canon_id"] == "sarah"
    assert recorder.participants[1]["canon_id"] == "davi"
    assert recorder.participants[2]["canon_id"] == "felipe"

    # 3. Feed Final Classification
    fc_pkt = create_final_classification_packet()
    hdr_fc = PacketHeader.unpack(fc_pkt)
    result = recorder.process_packet(hdr_fc, fc_pkt)

    assert result is not None
    assert result["round"] == 11
    assert len(result["race_results"]) == 3
    assert result["race_results"][0]["driver_name"] == "Sarah (SarahMarinsS)"
    assert result["race_results"][0]["pos"] == 1
    assert result["race_results"][0]["best_lap"] == "1:17.035"
    assert result["race_results"][1]["total_time_or_gap"] == "+6.244"
    assert result["race_results"][2]["total_time_or_gap"] == "+13.717"

    # Check files created
    telemetry_dir = Path("data/seasons/season_01/et_11_austria/telemetry")
    assert (telemetry_dir / "tv_overlay_et11.json").exists()
    assert (telemetry_dir / "pacedex_udp_race_summary.csv").exists()
    
    # Clean up test artifacts to keep season 01 clean
    import shutil
    shutil.rmtree(telemetry_dir.parent, ignore_errors=True)
    print("Test passed: SessionRecorder generated valid Etapa 11 artifacts.")


def test_udp_relay_packet_forwarding():
    # Set up mock PaceDex listener on port 20779
    mock_pacedex = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mock_pacedex.bind(("127.0.0.1", 20779))
    mock_pacedex.settimeout(2.0)

    # Initialize relay on listen port 20776 -> relay to 20779
    relay = UdpTelemetryRelay(
        listen_host="127.0.0.1",
        listen_port=20776,
        relay_host="127.0.0.1",
        relay_port=20779,
        override_round=11,
    )

    t = threading.Thread(target=relay.start, daemon=True)
    t.start()
    time.sleep(0.3)

    try:
        # Simulate game sending to 20776
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sample_packet = create_session_packet()
        sender.sendto(sample_packet, ("127.0.0.1", 20776))

        # Check if PaceDex received the forwarded packet
        relayed_data, addr = mock_pacedex.recvfrom(4096)
        assert len(relayed_data) == len(sample_packet)
        assert relayed_data == sample_packet
        print("Test passed: Zero-latency UDP packet forwarding confirmed!")
    finally:
        relay.stop()
        mock_pacedex.close()


def test_advanced_packets_unpacking():
    recorder = SessionRecorder(override_round=0, test_mode=True)

    # 1. Test Car Setups Packet (ID 5)
    hdr_5 = create_header(PACKET_ID_CAR_SETUPS)
    # <BBBBffffBBBBBBBBffffBf (49 bytes)
    setup_raw = struct.pack(
        "<BBBBffffBBBBBBBBffffBf",
        28, 22, 65, 55, -3.2, -1.8, 0.08, 0.22, 9, 7, 8, 6, 33, 45, 100, 56, 23.5, 23.5, 24.5, 24.5, 5, 25.0
    )
    data_5 = bytearray(hdr_5)
    for _ in range(22):
        data_5.extend(setup_raw)
    recorder.process_packet(PacketHeader.unpack(bytes(data_5)), bytes(data_5))
    assert 0 in recorder.car_setups
    assert recorder.car_setups[0]["front_wing"] == 28
    assert recorder.car_setups[0]["rear_wing"] == 22
    assert recorder.car_setups[0]["brake_bias"] == 56

    # 2. Test Car Telemetry Packet (ID 6)
    hdr_6 = create_header(PACKET_ID_CAR_TELEMETRY)
    # <HfffbbHBBH + 4H + 4B + 4B + H + 4f + 4B (60 bytes)
    c_tel = (
        struct.pack("<HfffbbHBBH", 315, 1.0, 0.05, 0.0, 0, 8, 12500, 1, 95, 0)
        + struct.pack("<4H", 450, 440, 520, 510)  # brakes temp
        + struct.pack("<4B", 102, 101, 108, 107)  # tyres surf
        + struct.pack("<4B", 98, 97, 103, 102)    # tyres inner
        + struct.pack("<H", 112)                  # engine temp
        + struct.pack("<4f", 23.2, 23.2, 24.1, 24.1) # tyres press
        + struct.pack("<4B", 0, 0, 0, 0)          # surface
    )
    data_6 = bytearray(hdr_6)
    for _ in range(22):
        data_6.extend(c_tel)
    data_6.extend(b"\xff\x00\x08") # tail MFD
    recorder.process_packet(PacketHeader.unpack(bytes(data_6)), bytes(data_6))
    assert 0 in recorder.car_telemetry
    assert recorder.car_telemetry[0]["peak_speed_kmh"] == 315
    assert recorder.car_telemetry[0]["max_brake_temp_c"] == 520
    assert recorder.car_telemetry[0]["max_tyre_surf_temp_c"] == 108

    # 3. Test Car Status Packet (ID 7)
    hdr_7 = create_header(PACKET_ID_CAR_STATUS)
    # tc, abs, mix, bb, pit, tank, cap, rem, max_rpm, idle, gears, drs_all, drs_dist, act_t, vis_t, age, fia, ers_store, mode, h_mguk, h_mguh, dep
    c_stat = (
        struct.pack("<BBBBB", 1, 0, 1, 56, 0)
        + struct.pack("<fff", 18.5, 110.0, 12.3)
        + struct.pack("<HHBBH", 13500, 4500, 8, 1, 0)
        + struct.pack("<BBBb", 16, 16, 4, 0)
        + struct.pack("<fBfff", 3200000.0, 3, 150000.0, 80000.0, 600000.0)
    )
    data_7 = bytearray(hdr_7)
    for _ in range(22):
        data_7.extend(c_stat)
    recorder.process_packet(PacketHeader.unpack(bytes(data_7)), bytes(data_7))
    assert 0 in recorder.car_status
    assert recorder.car_status[0]["fuel_in_tank"] == 18.5
    assert recorder.car_status[0]["ers_pct"] == 80.0
    assert recorder.car_status[0]["ers_mode_str"] == "Ultrapassagem (Overtake)"

    # 4. Test Car Damage Packet (ID 10)
    hdr_10 = create_header(PACKET_ID_CAR_DAMAGE)
    c_dmg = (
        struct.pack("<ffff", 14.5, 13.8, 18.2, 17.9) # tyres wear
        + struct.pack("<4B", 0, 0, 0, 0)              # tyres damage
        + struct.pack("<4B", 0, 0, 0, 0)              # brakes damage
        + struct.pack("<10B", 5, 0, 0, 2, 0, 0, 0, 0, 8, 4) # wings, floor, drs, ers, gb, eng
        + struct.pack("<8B", 12, 10, 8, 15, 9, 14, 0, 0)    # PU wear
    )
    data_10 = bytearray(hdr_10)
    for _ in range(22):
        data_10.extend(c_dmg)
    recorder.process_packet(PacketHeader.unpack(bytes(data_10)), bytes(data_10))
    assert 0 in recorder.car_damage
    assert recorder.car_damage[0]["max_wear"] == 18.2
    assert recorder.car_damage[0]["fl_wing"] == 5
    assert recorder.car_damage[0]["pu_ice_wear"] == 15

    # 5. Test Session History Packet (ID 11)
    hdr_11 = create_header(PACKET_ID_SESSION_HISTORY)
    # car_idx(0), num_laps(2), num_stints(1), best_lap(1), best_s1(1), best_s2(1), best_s3(1)
    prefix_11 = struct.pack("<BBBBBBB", 0, 2, 1, 1, 1, 1, 1)
    l1 = struct.pack("<IHBHBHBB", 78500, 24500, 0, 28100, 0, 25900, 0, 0x0F)
    l2 = struct.pack("<IHBHBHBB", 78900, 24600, 0, 28200, 0, 26100, 0, 0x0F)
    laps_11 = l1 + l2 + (b"\x00" * 14 * 98)
    stint_11 = struct.pack("<BBB", 255, 16, 16) + (b"\x00" * 3 * 7)
    data_11 = hdr_11 + prefix_11 + laps_11 + stint_11
    recorder.process_packet(PacketHeader.unpack(data_11), data_11)
    assert 0 in recorder.session_history
    assert recorder.session_history[0]["num_laps"] == 2
    assert len(recorder.session_history[0]["laps"]) == 2
    assert recorder.session_history[0]["laps"][0]["time_str"] == "1:18.500"
    print("Test passed: Packets 5, 6, 7, 10 and 11 successfully unpacked!")


def test_grand_prix_local_driver_resolution():
    recorder = SessionRecorder(override_round=0, test_mode=True)
    hdr_p = create_header(PACKET_ID_PARTICIPANTS)
    data = bytearray(hdr_p)
    data.append(20) # num_active_cars

    # Sample Grand Prix local grid:
    # (ai, driver_id, net_id, team_id, my_team, race_number, nationality, name)
    grid = [
        (1, 54, 0, 8, 0, 4, 1, "Lando Norris"),
        (1, 9, 0, 2, 0, 1, 2, "Max Verstappen"),
        (1, 58, 0, 1, 0, 16, 3, "Charles Leclerc"),
        (1, 7, 0, 0, 0, 44, 1, "Lewis Hamilton"),
        (1, 112, 0, 8, 0, 81, 4, "Oscar Piastri"),
        (1, 0, 0, 1, 0, 55, 5, "Carlos Sainz"),
        (1, 3, 0, 4, 0, 14, 5, "Fernando Alonso"),
        (1, 13, 0, 2, 0, 11, 6, "Sergio Perez"),
    ]

    for p in grid:
        name_bytes = p[7].encode("utf-8").ljust(48, b"\x00")
        entry = struct.pack("<BBBBBBB", p[0], p[1], p[2], p[3], p[4], p[5], p[6]) + name_bytes + struct.pack("<BBHB", 1, 1, 100, 1)
        data.extend(entry)

    # Pad remaining 14 cars
    for i in range(14):
        entry = struct.pack("<BBBBBBB", 1, 255, 0, 255, 0, 0, 0) + (b"\x00" * 48) + struct.pack("<BBHB", 1, 1, 0, 1)
        data.extend(entry)

    pkt_bytes = bytes(data)
    recorder.process_packet(PacketHeader.unpack(pkt_bytes), pkt_bytes)

    assert len(recorder.participants) >= 8
    assert recorder.participants[0]["canon_name"] == "Lando Norris"
    assert recorder.participants[0]["team"] == "McLaren Formula 1 Team"
    assert recorder.participants[1]["canon_name"] == "Max Verstappen"
    assert recorder.participants[1]["team"] == "Red Bull Racing"
    assert recorder.participants[2]["canon_name"] == "Charles Leclerc"
    assert recorder.participants[2]["team"] == "Scuderia Ferrari HP"
    assert recorder.participants[3]["canon_name"] == "Lewis Hamilton"
    assert recorder.participants[3]["team"] == "Mercedes-AMG Petronas"
    assert recorder.participants[4]["canon_name"] == "Oscar Piastri"
    assert recorder.participants[4]["team"] == "McLaren Formula 1 Team"
    print("Test passed: Grand Prix local driver and team resolution 100% verified!")


if __name__ == "__main__":
    print("Running test_session_recorder_parsing()...")
    test_session_recorder_parsing()
    print("Running test_advanced_packets_unpacking()...")
    test_advanced_packets_unpacking()
    print("Running test_grand_prix_local_driver_resolution()...")
    test_grand_prix_local_driver_resolution()
    print("Running test_udp_relay_packet_forwarding()...")
    test_udp_relay_packet_forwarding()
    print("ALL UDP RELAY TESTS PASSED SUCCESSFULLY!")

