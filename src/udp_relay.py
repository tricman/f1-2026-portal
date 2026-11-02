"""
F1 2024 UDP Telemetry Proxy & Real-Time Session Recorder.
Listens on UDP 20777 (from F1 24 game), instantly forwards all raw datagrams
to UDP 20778 (for PaceDex), and parses the live stream into Showrunner artifacts.

Usage:
  # Modo Piloto de Teste (Isolado em data/telemetry_pilot_test/):
  python -m src.udp_relay --test

  # Modo Oficial da Etapa (Etapa correspondente detectada automaticamente):
  python -m src.udp_relay
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
        test_mode: bool = False,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.test_mode = test_mode
        self.recorder = SessionRecorder(override_round=override_round, test_mode=test_mode)

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
        if hasattr(socket, "SO_REUSEADDR"):
            self.rx_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

        print("=" * 76)
        if self.recorder.is_pilot_test():
            print("🏎️  F1 2024 UDP TELEMETRY PROXY & LIVE RECORDER [MODO PILOTO DE TESTE]")
            print("🧪 Pista Alvo: GP de Portugal (Portimão) ou Sessão de Treino")
            print("🛡️  ISOLAMENTO TOTAL ATIVO: Nenhum dado será gravado na Etapa 11 ou campeonato.")
            print("📁 Resultados e Relatório da FIA serão salvos em: data/telemetry_pilot_test/")
        else:
            print("🏎️  F1 2024 UDP TELEMETRY PROXY & LIVE RECORDER [MODO OFICIAL]")
            print("💾 Gravação automática de tv_overlay.json e CSVs habilitada.")

        print(f"📡 Escutando telemetria F1 24 em: {listen_addr}")
        print(f"⚡ Replicando em tempo real para PaceDex em: {relay_target}")
        print("=" * 76)

        try:
            while self.running:
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
                        except Exception:
                            pass

                        # PROCESS LOCALLY
                        header = PacketHeader.unpack(data)
                        if header and header.packet_format == PACKET_FORMAT_2024:
                            res = self.recorder.process_packet(header, data)
                            if res and self.recorder.is_pilot_test():
                                print("\n" + "🎉 " * 15)
                                print("🏆 TESTE PILOTO CONCLUÍDO COM SUCESSO!")
                                print("📄 Relatório completo gerado em: data/telemetry_pilot_test/RELATORIO_PILOTO_PORTIMAO.md")
                                print("🎉 " * 15 + "\n")

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

        prefix = "🧪 [PILOTO TESTE]" if self.recorder.is_pilot_test() else "🟢 [RELAY STATUS]"
        rnd_info = "PORTIMÃO (ISOLADO)" if self.recorder.is_pilot_test() else f"Etapa: {detected_rnd} ({folder})"

        status_line = (
            f"{prefix} Pkts: {rate} ({mb:.1f} MB) | "
            f"PaceDex -> :{self.relay_port} (OK) | "
            f"{rnd_info} | "
            f"Pista: {track_name} | Sessão: {stype} | Carros: {cars_count}/22"
        )
        print(status_line)

    def stop(self) -> None:
        self.running = False
        if not self.recorder.saved_results and len(self.recorder.participants) > 0:
            print("💾 Gravando resultados e relatório da sessão antes de encerrar...")
            self.recorder.flush()
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
    parser.add_argument("--test", "--pilot", dest="test_mode", action="store_true", help="Ativar modo teste piloto isolado (não afeta etapa oficial)")

    args = parser.parse_args()
    relay = UdpTelemetryRelay(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        relay_host=args.relay_host,
        relay_port=args.relay_port,
        override_round=args.round,
        test_mode=args.test_mode,
    )
    relay.start()


if __name__ == "__main__":
    main()
