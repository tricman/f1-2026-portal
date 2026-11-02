"""
F1 2024 UDP Telemetry Proxy & Real-Time Session Recorder.
Listens on UDP 20777 (from F1 24 game), instantly forwards all raw datagrams
to UDP 20778 (for PaceDex), and parses the live stream into Showrunner artifacts.

Usage:
  python -m src.udp_relay [--listen-port 20777] [--relay-port 20778] [--relay-host 127.0.0.1]
"""
from __future__ import annotations

import argparse
import os
import select
import socket
import sys
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.logger import log_text
from src.telemetry.f1_2024_structs import (
    PacketHeader,
    PACKET_FORMAT_2024,
    TRACK_ID_MAP,
    SESSION_TYPE_MAP,
)
from src.telemetry.session_recorder import SessionRecorder

DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 20777
DEFAULT_RELAY_HOST = "127.0.0.1"
DEFAULT_RELAY_PORT = 20778


class UdpTelemetryRelay:
    def __init__(
        self,
        listen_host: str = DEFAULT_LISTEN_HOST,
        listen_port: int = DEFAULT_LISTEN_PORT,
        relay_host: str = DEFAULT_RELAY_HOST,
        relay_port: int = DEFAULT_RELAY_PORT,
        override_round: int | None = None,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.recorder = SessionRecorder(override_round=override_round)

        self.running = False
        self.rx_socket: socket.socket | None = None
        self.tx_socket: socket.socket | None = None

        self.packets_received = 0
        self.packets_relayed = 0
        self.bytes_received = 0
        self.last_status_time = time.time()

    def start(self) -> None:
        """Bind sockets and start the relay loop."""
        # 1. Receiver socket
        self.rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow reuse of port to avoid conflict with lingering sockets
        if hasattr(socket, "SO_REUSEADDR"):
            self.rx_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Large receive buffer (2MB) so bursts during 60Hz telemetry never drop frames
        try:
            self.rx_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        except Exception:
            pass

        self.rx_socket.bind((self.listen_host, self.listen_port))
        self.rx_socket.setblocking(False)

        # 2. Transmitter socket (Relay to PaceDex)
        self.tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = True
        relay_target = f"{self.relay_host}:{self.relay_port}"
        listen_addr = f"{self.listen_host}:{self.listen_port}"

        print("=" * 72)
        print("🏎️  F1 2024 UDP TELEMETRY PROXY & LIVE RECORDER")
        print(f"📡 Escutando telemetria F1 24 em: {listen_addr}")
        print(f"⚡ Replicando em tempo real para PaceDex em: {relay_target}")
        print("💾 Gravação automática de tv_overlay.json e CSVs habilitada.")
        print("=" * 72)

        try:
            while self.running:
                # Use select with 0.1s timeout for non-blocking I/O and responsive Ctrl+C
                ready = select.select([self.rx_socket], [], [], 0.1)
                if ready[0]:
                    while True:
                        try:
                            data, addr = self.rx_socket.recvfrom(4096)
                        except BlockingIOError:
                            break
                        except Exception:
                            break

                        self.packets_received += 1
                        self.bytes_received += len(data)

                        # ZERO-LATENCY RELAY: forward immediately to PaceDex
                        try:
                            self.tx_socket.sendto(data, (self.relay_host, self.relay_port))
                            self.packets_relayed += 1
                        except Exception as e:
                            # Non-critical if PaceDex is temporarily closed
                            pass

                        # PROCESS LOCALLY
                        header = PacketHeader.unpack(data)
                        if header and header.packet_format == PACKET_FORMAT_2024:
                            self.recorder.process_packet(header, data)

                # Periodic Heartbeat & Status Display (every 5 seconds)
                now = time.time()
                if now - self.last_status_time >= 5.0:
                    self._print_heartbeat()
                    self.last_status_time = now

        except KeyboardInterrupt:
            print("\n🛑 Encerrando UDP Relay graciosamente...")
        finally:
            self.stop()

    def _print_heartbeat(self) -> None:
        track_name = TRACK_ID_MAP.get(self.recorder.track_id, {}).get("name", "Aguardando Pista...")
        stype = SESSION_TYPE_MAP.get(self.recorder.session_type, "N/A")
        cars_count = len(self.recorder.participants)
        detected_rnd, folder = self.recorder.get_detected_round()

        rate = self.packets_received
        mb = self.bytes_received / (1024 * 1024)

        status_line = (
            f"🟢 [RELAY STATUS] Pkts: {rate} ({mb:.1f} MB) | "
            f"PaceDex -> :{self.relay_port} (OK) | "
            f"Etapa: {detected_rnd} ({folder}) | "
            f"Pista: {track_name} | Sessão: {stype} | Carros: {cars_count}/22"
        )
        print(status_line)

    def stop(self) -> None:
        self.running = False
        if self.rx_socket:
            try:
                self.rx_socket.close()
            except Exception:
                pass
            self.rx_socket = None
        if self.tx_socket:
            try:
                self.tx_socket.close()
            except Exception:
                pass
            self.tx_socket = None
        print("✅ UDP Relay desconectado.")


def main():
    parser = argparse.ArgumentParser(description="F1 2024 UDP Telemetry Relay & Showrunner Recorder")
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST, help="IP de escuta UDP (default: 0.0.0.0)")
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT, help="Porta do jogo F1 24 (default: 20777)")
    parser.add_argument("--relay-host", default=DEFAULT_RELAY_HOST, help="IP do PaceDex (default: 127.0.0.1)")
    parser.add_argument("--relay-port", type=int, default=DEFAULT_RELAY_PORT, help="Porta configurada no PaceDex (default: 20778)")
    parser.add_argument("--round", type=int, default=None, help="Forçar número da etapa (ex: 11)")

    args = parser.parse_args()
    relay = UdpTelemetryRelay(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        relay_host=args.relay_host,
        relay_port=args.relay_port,
        override_round=args.round,
    )
    relay.start()


if __name__ == "__main__":
    main()
