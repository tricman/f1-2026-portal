"""
Cloud Run HTTP Ingress & 4-Hour Ephemeral Session Listener (SAD v2.0).
Exposes:
  - GET  /healthz         -> Health & readiness probe
  - POST /session/start   -> Starts a 4-hour (14,400s) background listener session for a round
  - POST /discord/webhook -> Discord Interactions HTTP endpoint (/etapa iniciar | /etapa finalizar)
"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from src.ai_showrunner import (
    GeminiFreeTierClient,
    finalize_round_transition,
    generate_post_race_modules,
)
from src.discord_gateway import DiscordGatewayClient
from src.logger import info, warning, error
from src.orchestrator_cli import (
    ROOT_DIR,
    load_dotenv_if_present,
    process_round_10_telemetry,
    publish_round_to_discord,
)

ACTIVE_LISTENER_LOCK = threading.Lock()
ACTIVE_LISTENER_STATUS: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "expires_at": None,
    "active_round_folder": None,
}

FOUR_HOURS_SECONDS = 4 * 3600  # 14,400 seconds


def _execute_round_pipeline(r_folder: str, r_num: int) -> None:
    """
    Executes the full post-round pipeline with structured Cloud Logging:
    Vision OCR -> Telemetry Merge -> AI Editorial Generation -> State Transition -> Discord Teasers & Portal
    """
    load_dotenv_if_present()
    debrief_dir = ROOT_DIR / "data" / "seasons" / "season_01" / r_folder / "debriefing"
    photos_dir = ROOT_DIR / "data" / "seasons" / "season_01" / r_folder / "photos"
    tel_dir = ROOT_DIR / "data" / "seasons" / "season_01" / r_folder / "telemetry"
    ai_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_client = GeminiFreeTierClient(api_key=ai_key)

    try:
        info(f"Iniciando pipeline autônomo para {r_folder}...", event="PIPELINE_START", round_folder=r_folder, round_num=r_num)

        if ai_key:
            if debrief_dir.exists() and any(debrief_dir.iterdir()):
                info("Transcrevendo relatos de áudio e notas...", stage="AUDIO_TRANSCRIPTION", round_num=r_num)
                ai_client.transcribe_audio_debriefs(debrief_dir)
            if photos_dir.exists() and any(photos_dir.iterdir()):
                info("Extraindo dados da TV via Vision OCR...", stage="VISION_OCR", round_num=r_num)
                ai_client.extract_tv_overlay_from_photos(
                    photos_dir=photos_dir,
                    output_json_path=tel_dir / f"tv_overlay_et{r_num:02d}.json",
                    round_num=r_num,
                    round_name=r_folder,
                )

        if r_num == 10:
            info("Executando fusão de telemetria da Etapa 10...", stage="TELEMETRY_MERGE", round_num=10)
            process_round_10_telemetry()

        if ai_key:
            info("Gerando módulos narrativos da FIA via Gemini...", stage="AI_GENERATION", round_num=r_num)
            generate_post_race_modules(ROOT_DIR, r_num, r_folder, ai_client)

        info("Finalizando transição de campeonato para próxima etapa...", stage="STATE_TRANSITION", round_num=r_num)
        finalize_round_transition(ROOT_DIR, r_num, r_folder, ai_client=ai_client)

        info("Publicando teasers e tabelas no Discord...", stage="DISCORD_PUBLISH", round_num=r_num)
        publish_round_to_discord(r_folder, teaser_mode=True)
        info(f"Etapa {r_num} publicada com sucesso no Discord e Portal!", event="ROUND_PUBLISHED", round_num=r_num)
    except Exception as exc:
        error(f"Erro fatal durante execução do pipeline para {r_folder}: {exc}", exc=exc, round_folder=r_folder, round_num=r_num)


def _execute_m1_pipeline(r_folder: str, r_num: int, force_regenerate: bool = False) -> None:
    """
    Generates or loads M1 (A Semana da F1), builds portal and publishes teaser to Discord.
    """
    from src.ai_showrunner import GeminiFreeTierClient, generate_pre_race_m1
    from src.orchestrator_cli import deploy_portal_to_github_pages
    import urllib.parse

    load_dotenv_if_present()
    ai_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_client = GeminiFreeTierClient(api_key=ai_key)

    try:
        info(f"Iniciando produção do Módulo 1 (Pré-Semana) para {r_folder}...", event="M1_START", round_folder=r_folder, round_num=r_num)
        m1_path = generate_pre_race_m1(ROOT_DIR, r_num, r_folder, ai_client, force_regenerate=force_regenerate)
        info(f"Módulo 1 consolidado em {m1_path.name}. Atualizando Portal...", stage="PORTAL_BUILD", round_num=r_num)

        deploy_portal_to_github_pages(f"Publish M1 {r_folder} to F1 2026 Portal")

        client = DiscordGatewayClient()
        base_url = (os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
        encoded_m = urllib.parse.quote(f"{r_folder}__{m1_path.stem}")
        deep_link = f"{base_url}/#r={r_num}&m={encoded_m}"

        info("Publicando Teaser do M1 no Discord (#repercussao-midia)...", stage="DISCORD_TEASER", round_num=r_num)
        msg_id = client.publish_editorial_teaser(
            markdown_text=m1_path.read_text(encoding="utf-8"),
            article_title=f"[M1 · PRÉ-SEMANA] {m1_path.stem}",
            portal_url=deep_link,
            persona_name="F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'",
        )
        info(f"Teaser do M1 publicado com sucesso ({msg_id})!", event="M1_PUBLISHED", round_num=r_num)
    except Exception as exc:
        error(f"Erro fatal na produção do M1 para {r_folder}: {exc}", exc=exc, round_folder=r_folder, round_num=r_num)


def _execute_m1_day_pipeline(r_folder: str, r_num: int, day_num: int) -> None:
    """
    Generates an episodic daily installment of M1 and publishes teaser to Discord.
    """
    from src.ai_showrunner import GeminiFreeTierClient, generate_m1_daily_episode
    from src.orchestrator_cli import deploy_portal_to_github_pages
    import urllib.parse

    load_dotenv_if_present()
    ai_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ai_client = GeminiFreeTierClient(api_key=ai_key)

    try:
        info(f"Iniciando Módulo 1 (Dia {day_num}/4) para {r_folder}...", event="M1_DAY_START", day=day_num, round_folder=r_folder, round_num=r_num)
        m1_path, teaser_text = generate_m1_daily_episode(ROOT_DIR, r_num, r_folder, day_num, ai_client)

        deploy_portal_to_github_pages(f"Publish M1 Day {day_num} {r_folder} to F1 2026 Portal")

        client = DiscordGatewayClient()
        base_url = (os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
        encoded_m = urllib.parse.quote(f"{r_folder}__{m1_path.stem}")
        deep_link = f"{base_url}/#r={r_num}&m={encoded_m}"

        info(f"Publicando Teaser do M1 Dia {day_num} no Discord...", stage="DISCORD_TEASER", day=day_num, round_num=r_num)
        msg_id = client.publish_editorial_teaser(
            markdown_text=f"{teaser_text}\n\n📖 **Leia o dossiê completo atualizado no Portal:**\n{deep_link}",
            article_title=f"[M1 · DIA {day_num}/4] A Semana da F1 ({r_folder})",
            portal_url=deep_link,
            persona_name="F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'",
        )
        info(f"Teaser do M1 Dia {day_num} publicado ({msg_id})!", event="M1_DAY_PUBLISHED", day=day_num, round_num=r_num)
    except Exception as exc:
        error(f"Erro no M1 Dia {day_num} para {r_folder}: {exc}", exc=exc, round_folder=r_folder, round_num=r_num)


def _start_press_conference(r_folder: str, r_num: int) -> None:
    """Starts interactive FIA Press Conference and asks Question 1."""
    from src.press_conference import PressConferenceSession

    load_dotenv_if_present()
    client = DiscordGatewayClient()
    sess = PressConferenceSession(ROOT_DIR, r_num, r_folder)
    opening = sess.start_session()
    client.post_channel_message(client.ingest_channel_id, opening)

    time.sleep(2.0)
    q1_text, is_lock, driver = sess.advance_to_next_question()
    client.post_channel_message(client.ingest_channel_id, q1_text)


def _run_4h_session_listener(
    max_duration_seconds: int = FOUR_HOURS_SECONDS,
    poll_interval: int = 6,
) -> None:
    """
    Runs for up to 4 hours (14,400s) listening to the Discord Voice Channel (#1457392708355096580).
    Automatically executes Early Exit as soon as `final da etapa <N>` is received,
    processed, and published to the Portal and #repercussao-midia.
    """
    load_dotenv_if_present()
    client = DiscordGatewayClient()
    state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"

    start_ts = time.time()
    deadline_ts = start_ts + max_duration_seconds

    with ACTIVE_LISTENER_LOCK:
        ACTIVE_LISTENER_STATUS["running"] = True
        ACTIVE_LISTENER_STATUS["started_at"] = start_ts
        ACTIVE_LISTENER_STATUS["expires_at"] = deadline_ts

    try:
        while time.time() < deadline_ts:
            session_state = client.process_voice_channel_session(ROOT_DIR, state_file)
            stage_ev = session_state.get("last_poll_stage_event")
            r_folder = session_state.get("active_round_folder") or "et_10_espanha"
            r_num = int(session_state.get("active_round_num") or 10)

            with ACTIVE_LISTENER_LOCK:
                ACTIVE_LISTENER_STATUS["active_round_folder"] = r_folder

            if stage_ev and stage_ev.startswith("PRE_ROUND_"):
                info(f"PRE_ROUND detectado para {r_folder}. Executando Módulo 1...", event="PRE_ROUND", round_num=r_num)
                threading.Thread(target=_execute_m1_pipeline, args=(r_folder, r_num), daemon=True).start()

            if stage_ev and stage_ev.startswith("SEMANA_TICK_"):
                parts = stage_ev.split("_")
                day = int(parts[-1]) if len(parts) >= 4 and parts[-1].isdigit() else 1
                info(f"SEMANA_TICK detectado para {r_folder} (Dia {day}). Executando M1 diário...", event="SEMANA_TICK", round_num=r_num, day=day)
                threading.Thread(target=_execute_m1_day_pipeline, args=(r_folder, r_num, day), daemon=True).start()

            if stage_ev and stage_ev.startswith("START_PRESS_CONF_"):
                info(f"START_PRESS_CONF detectado para {r_folder}. Convocando coletiva interativa...", event="START_PRESS_CONF", round_num=r_num)
                threading.Thread(target=_start_press_conference, args=(r_folder, r_num), daemon=True).start()

            if stage_ev and stage_ev.startswith("END_ROUND_") and session_state.get("status") == "READY_FOR_SIMULATION":
                info(f"END_ROUND detectado para {r_folder}. Executando pipeline...", event="END_ROUND", round_num=r_num)
                threading.Thread(target=_execute_round_pipeline, args=(r_folder, r_num), daemon=True).start()

            time.sleep(poll_interval)
    except Exception as exc:
        error(f"Erro fatal durante a sessão do Cloud Run: {exc}", exc=exc)
    finally:
        with ACTIVE_LISTENER_LOCK:
            ACTIVE_LISTENER_STATUS["running"] = False


class CloudRunRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.startswith("/healthz") or self.path == "/":
            with ACTIVE_LISTENER_LOCK:
                status_copy = dict(ACTIVE_LISTENER_STATUS)
            self._send_json(200, {"status": "ok", "service": "f1-2026-showrunner", "listener": status_copy})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body_raw) if body_raw else {}
        except json.JSONDecodeError:
            data = {}

        # Discord Webhook PING verification (type == 1)
        if data.get("type") == 1:
            self._send_json(200, {"type": 1})
            return

        if self.path.startswith("/round/m1/day"):
            r_num = int(data.get("round_num", 10))
            r_folder = data.get("round_folder", f"et_{r_num:02d}_espanha")
            day_num = int(data.get("day", 1))
            worker = threading.Thread(
                target=_execute_m1_day_pipeline,
                args=(r_folder, r_num, day_num),
                daemon=True,
            )
            worker.start()
            self._send_json(
                202,
                {
                    "status": "m1_day_generation_started",
                    "round_folder": r_folder,
                    "round_num": r_num,
                    "day": day_num,
                },
            )
            return

        if self.path.startswith("/round/coletiva"):
            r_num = int(data.get("round_num", 10))
            r_folder = data.get("round_folder", f"et_{r_num:02d}_espanha")
            worker = threading.Thread(
                target=_start_press_conference,
                args=(r_folder, r_num),
                daemon=True,
            )
            worker.start()
            self._send_json(
                202,
                {
                    "status": "press_conference_started",
                    "round_folder": r_folder,
                    "round_num": r_num,
                },
            )
            return

        if self.path.startswith("/round/m1") or self.path.startswith("/session/m1"):
            r_num = int(data.get("round_num", 10))
            r_folder = data.get("round_folder", f"et_{r_num:02d}_espanha")
            force = bool(data.get("force", False))
            worker = threading.Thread(
                target=_execute_m1_pipeline,
                args=(r_folder, r_num, force),
                daemon=True,
            )
            worker.start()
            self._send_json(
                202,
                {
                    "status": "m1_generation_started",
                    "round_folder": r_folder,
                    "round_num": r_num,
                },
            )
            return

        if self.path.startswith("/round/execute") or self.path.startswith("/session/simulate"):
            r_num = int(data.get("round_num", 10))
            r_folder = data.get("round_folder", f"et_{r_num:02d}_espanha")
            worker = threading.Thread(
                target=_execute_round_pipeline,
                args=(r_folder, r_num),
                daemon=True,
            )
            worker.start()
            self._send_json(
                202,
                {
                    "status": "simulation_started",
                    "round_folder": r_folder,
                    "round_num": r_num,
                },
            )
            return

        if self.path.startswith("/session/start") or self.path.startswith("/discord/webhook"):
            ttl = int(data.get("ttl_seconds", FOUR_HOURS_SECONDS))
            with ACTIVE_LISTENER_LOCK:
                already_running = ACTIVE_LISTENER_STATUS["running"]

            if not already_running:
                worker = threading.Thread(
                    target=_run_4h_session_listener,
                    kwargs={"max_duration_seconds": min(ttl, FOUR_HOURS_SECONDS)},
                    daemon=True,
                )
                worker.start()

            # If triggered by Discord Slash Command Interaction (type == 2)
            if data.get("type") == 2:
                self._send_json(
                    200,
                    {
                        "type": 4,
                        "data": {
                            "content": (
                                "🟢 **F1 Showrunner Listener Ativado (Janela de até 4h)!**\n"
                                "Escutando o Canal de Voz (`#1457392708355096580`). "
                                "Digitem `inicio da etapa <N>`, subam as fotos, CSVs e áudios, e finalizem com `final da etapa <N>`!"
                            )
                        },
                    },
                )
                return

            self._send_json(
                202,
                {
                    "status": "listener_started" if not already_running else "already_running",
                    "max_ttl_seconds": min(ttl, FOUR_HOURS_SECONDS),
                },
            )
            return

        self._send_json(404, {"error": "Unknown endpoint"})


def run_cloud_server(port: Optional[int] = None) -> None:
    load_dotenv_if_present()
    listen_port = port or int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", listen_port), CloudRunRequestHandler)
    print(f"[F1 Showrunner Cloud Server] Listening on 0.0.0.0:{listen_port} (Max Session TTL: 4h / 14,400s)")
    server.serve_forever()


if __name__ == "__main__":
    run_cloud_server()

