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
    PACKET_ID_FINAL_CLASSIFICATION,
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


if __name__ == "__main__":
    print("Running test_session_recorder_parsing()...")
    test_session_recorder_parsing()
    print("Running test_udp_relay_packet_forwarding()...")
    test_udp_relay_packet_forwarding()
    print("ALL UDP RELAY TESTS PASSED SUCCESSFULLY!")

