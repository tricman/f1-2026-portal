import os
import re
import time
import json
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from src.table_renderer import transform_markdown_tables_for_discord
from src.portal_builder import ROUND_METADATA

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv_if_present() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith('"'):
            end_q = v.find('"', 1)
            v = v[1:end_q] if end_q != -1 else v.strip('"')
        elif v.startswith("'"):
            end_q = v.find("'", 1)
            v = v[1:end_q] if end_q != -1 else v.strip("'")
        else:
            v = v.split("#")[0].strip()
        if k not in os.environ:
            os.environ[k] = v


DISCORD_GUILD_ID = "1457392707604578460"
DISCORD_VOICE_INGEST_CHANNEL_ID = "1457392708355096580"
DISCORD_MEDIA_PUBLISH_CHANNEL_ID = "1536416375969685524"
DISCORD_API_BASE = "https://discord.com/api/v10"

INGEST_ALLOWED_EXTENSIONS = (
    ".csv",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".ogg",
    ".mp3",
    ".wav",
    ".m4a",
    ".opus",
    ".txt",
)

ROUND_NUMBER_TO_FOLDER: Dict[int, str] = {
    meta["num"]: folder for folder, meta in ROUND_METADATA.items()
}


def detect_stage_command(text: str) -> Optional[Tuple[Any, ...]]:
    """
    Detect stage lifecycle and ChatOps commands in a Discord message:
      - 'inicio semana etapa 11' -> ('START_SEMANA', 11)
      - 'avancar dia' / 'dia 2 etapa 11' -> ('TICK_SEMANA_2', 11) or ('TICK_SEMANA', None)
      - 'coletiva etapa 11' / 'coletiva fia etapa 11' -> ('START_PRESS_CONF', 11)
      - 'forcar avanco coletiva' -> ('FORCE_PRESS_CONF_ADVANCE', None)
      - 'inicio da etapa 10' / '!iniciar 10' -> ('START', 10)
      - 'final da etapa 10' / 'fim da etapa' -> ('END', 10)
      - 'pre etapa 10' / 'preview etapa 10' -> ('PRE', 10)
      - 'iniciar escuta f1' / 'escutar corrida' -> ('START_UDP_LISTENER', None)
      - 'status telemetria' -> ('STATUS_UDP_LISTENER', None)
      - 'parar escuta f1' -> ('STOP_UDP_LISTENER', None)
      - 'rollback etapa 11 sessao' -> ('STAGE_ROLLBACK', 11, 'sessao')
      - 'confirmar rollback' -> ('CONFIRM_ROLLBACK', None)
      - 'cancelar rollback' -> ('CANCEL_ROLLBACK', None)
    Returns (command_type, round_number_or_None, [optional_extra]) or None.
    """
    clean = text.strip().lower()

    # 1. Telemetry UDP Listener ChatOps
    if re.search(r"\b(?:iniciar|comecar|começar|escutar)\s+(?:a\s+)?(?:escuta\s+f1|escuta|corrida|telemetria|udp)\b", clean):
        return ("START_UDP_LISTENER", None)

    if re.search(r"\bstatus\s+(?:da\s+)?(?:telemetria|escuta|udp)\b", clean):
        return ("STATUS_UDP_LISTENER", None)

    if re.search(r"\b(?:parar|encerrar|interromper|stop)\s+(?:a\s+)?(?:escuta\s+f1|escuta|telemetria|udp)\b", clean):
        return ("STOP_UDP_LISTENER", None)

    # 2. Granular Stage Rollback ChatOps
    rollback_match = re.search(
        r"\b(?:rollback|reverter)\s+(?:da\s+)?etapa\s+(\d+)(?:\s+(sessao|sessão|coletiva|semana|tudo))?\b",
        clean,
    )
    if rollback_match:
        r_num = int(rollback_match.group(1))
        scope = (rollback_match.group(2) or "sessao").replace("sessão", "sessao")
        return ("STAGE_ROLLBACK", r_num, scope)

    if re.search(r"\bconfirmar\s+rollback\b", clean):
        return ("CONFIRM_ROLLBACK", None)

    if re.search(r"\bcancelar\s+rollback\b", clean):
        return ("CANCEL_ROLLBACK", None)

    # 3. Press Conference Force Timeout Advance
    if re.search(r"\b(?:forcar|forçar|avancar|avançar)\s+(?:avanco\s+|avanço\s+)?coletiva\b|\btimeout\s+coletiva\b", clean):
        return ("FORCE_PRESS_CONF_ADVANCE", None)

    # 4. Weekly Silly Season Schedule
    semana_start = re.search(
        r"\b(?:inicio|início|iniciar|start)\s+(?:da\s+|de\s+)?semana(?:\s+(?:da\s+|de\s+)?etapa)?(?:\s+#?(\d+))?",
        clean,
    )
    if semana_start:
        r_num = int(semana_start.group(1)) if semana_start.group(1) else None
        return ("START_SEMANA", r_num)

    day_match = re.search(
        r"\b(?:avancar|avançar|proximo|próximo)\s+dia\b|\bdia\s+(\d+)(?:\s+(?:da\s+|de\s+)?etapa\s+(\d+))?",
        clean,
    )
    if day_match:
        day_num = int(day_match.group(1)) if day_match.group(1) else None
        r_num = int(day_match.group(2)) if day_match.group(2) else None
        return (f"TICK_SEMANA_{day_num}" if day_num else "TICK_SEMANA", r_num)

    # 2. Interactive FIA Press Conference
    press_match = re.search(
        r"\b(?:coletiva|press)\s+(?:da\s+|de\s+|fia\s+)?(?:etapa)?(?:\s+#?(\d+))?",
        clean,
    )
    if press_match:
        r_num = int(press_match.group(1)) if press_match.group(1) else None
        return ("START_PRESS_CONF", r_num)

    # 3. Standard Race Weekend Ingest
    start_match = re.search(
        r"\b(?:inicio|início|iniciar|start)\s+(?:da\s+|de\s+)?etapa(?:\s+#?(\d+))?",
        clean,
    )
    if start_match:
        r_num = int(start_match.group(1)) if start_match.group(1) else None
        return ("START", r_num)

    end_match = re.search(
        r"\b(?:final|fim|finalizar|encerrar|end)\s+(?:da\s+|de\s+)?etapa(?:\s+#?(\d+))?",
        clean,
    )
    if end_match:
        r_num = int(end_match.group(1)) if end_match.group(1) else None
        return ("END", r_num)

    pre_match = re.search(
        r"\b(?:pre|pré|semana|bastidores|preview)\s+(?:da\s+|de\s+)?etapa(?:\s+#?(\d+))?",
        clean,
    )
    if pre_match:
        r_num = int(pre_match.group(1)) if pre_match.group(1) else None
        return ("PRE", r_num)

    return None


def split_markdown_for_discord(content: str, max_chars: int = 1950) -> List[str]:
    """
    Semantically chunk a Markdown document so every chunk is <= max_chars,
    splitting strictly on paragraph/line boundaries and preserving code blocks/tables.
    """
    if len(content) <= max_chars:
        return [content.strip()]

    lines = content.splitlines(keepends=True)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        if current_len + len(line) > max_chars and current:
            chunk_str = "".join(current).rstrip()
            if in_code_block:
                chunk_str += "\n```"
            chunks.append(chunk_str)
            current = ["```\n"] if in_code_block else []
            current_len = len(current[0]) if current else 0

        current.append(line)
        current_len += len(line)

    if current:
        final_str = "".join(current).strip()
        if final_str:
            chunks.append(final_str)

    return chunks


class DiscordGatewayClient:
    """
    Fault-tolerant Discord REST v10 & Webhook client with exponential backoff,
    configured for the F1 Simulator channels.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
        guild_id: str = DISCORD_GUILD_ID,
        ingest_channel_id: str = DISCORD_VOICE_INGEST_CHANNEL_ID,
        publish_channel_id: str = DISCORD_MEDIA_PUBLISH_CHANNEL_ID,
    ):
        load_dotenv_if_present()
        self.bot_token = bot_token or os.environ.get("DISCORD_BOT_TOKEN")
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        self.guild_id = guild_id
        self.ingest_channel_id = ingest_channel_id
        self.publish_channel_id = publish_channel_id

    def _request_with_backoff(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Any:
        headers = {
            "User-Agent": "F1SimulatorBot (https://antigravity.google, 1.0)",
            "Content-Type": "application/json",
        }
        if self.bot_token:
            headers["Authorization"] = f"Bot {self.bot_token}"

        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None

        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limited
                    retry_after = float(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                    time.sleep(retry_after)
                    continue
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except urllib.error.URLError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def post_channel_message(self, channel_id: str, content: str) -> Dict[str, Any]:
        """Post a message directly to a Discord channel using the Bot Token, splitting safely if > 1900 chars."""
        if not self.bot_token:
            raise PermissionError("DISCORD_BOT_TOKEN is required to post channel messages.")
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"

        # Discord limit is 2000 chars. Split at paragraph/line boundaries if exceeding 1900 chars.
        if len(content) <= 1900:
            res = self._request_with_backoff(url, method="POST", payload={"content": content})
            return res if isinstance(res, dict) else {}

        chunks: List[str] = []
        rem = content
        while len(rem) > 1900:
            cut = rem.rfind("\n\n", 0, 1900)
            if cut == -1:
                cut = rem.rfind("\n", 0, 1900)
            if cut == -1:
                cut = rem.rfind(" ", 0, 1900)
            if cut == -1:
                cut = 1900
            chunks.append(rem[:cut].strip())
            rem = rem[cut:].strip()
        if rem:
            chunks.append(rem)

        last_res: Dict[str, Any] = {}
        for idx, chunk in enumerate(chunks):
            if chunk:
                last_res = self._request_with_backoff(url, method="POST", payload={"content": chunk})
                if idx < len(chunks) - 1:
                    time.sleep(0.8)
        return last_res if isinstance(last_res, dict) else {}

    def fetch_recent_ingest_attachments(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Poll the voice channel's text chat (#1457392708355096580) for uploaded
        PaceDex CSVs (.csv), TV screenshots (.jpg/.png), and debriefing audio/text (.ogg/.mp3/.wav/.m4a/.txt).
        """
        if not self.bot_token:
            raise PermissionError("DISCORD_BOT_TOKEN is required to read channel messages.")
        url = f"{DISCORD_API_BASE}/channels/{self.ingest_channel_id}/messages?limit={limit}"
        messages = self._request_with_backoff(url, method="GET")
        attachments = []
        for msg in messages:
            for att in msg.get("attachments", []):
                fname = att.get("filename", "")
                if fname.lower().endswith(INGEST_ALLOWED_EXTENSIONS):
                    attachments.append({
                        "message_id": msg["id"],
                        "author": msg.get("author", {}).get("username"),
                        "timestamp": msg.get("timestamp"),
                        "filename": fname,
                        "url": att["url"],
                    })
        return attachments

    def process_voice_channel_session(
        self,
        root_dir: Path,
        state_file: Path,
        limit: int = 50,
        send_bot_replies: bool = True,
    ) -> Dict[str, Any]:
        """
        Stateful Race-Weekend Session Machine for the Voice Channel (#1457392708355096580):
          1. Watches for 'inicio da etapa <N>' -> opens session for Round N (e.g. et_10_espanha / et_11_austria).
          2. While session is COLLECTING, downloads all uploaded .csv (PaceDex), .jpg/.png (TV),
             and .ogg/.mp3/.wav/.m4a (audio debriefs), plus saves text debrief messages into `debriefing_notes.md`.
          3. Watches for 'final da etapa' -> marks session READY_FOR_SIMULATION and returns summary.
        """
        state: Dict[str, Any] = {
            "status": "IDLE",
            "active_round_num": None,
            "active_round_folder": None,
            "last_message_id": None,
            "downloaded_keys": [],
            "debrief_messages": [],
        }
        if state_file.exists():
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            state.update(loaded)

        processed_keys = set(state.get("downloaded_keys", []))
        processed_msg_ids = set(state.get("processed_msg_ids", []))

        url = f"{DISCORD_API_BASE}/channels/{self.ingest_channel_id}/messages?limit={limit}"
        messages = self._request_with_backoff(url, method="GET")
        if not isinstance(messages, list):
            return state

        # Find latest message ID already posted by F1 Showrunner bot to prevent duplicate replies on resume
        bot_msg_ids = [
            int(m["id"])
            for m in messages
            if m.get("author", {}).get("bot") and "Showrunner" in (m.get("author", {}).get("username") or "")
        ]
        last_bot_msg_id = max(bot_msg_ids) if bot_msg_ids else 0

        # Process in chronological order (oldest -> newest)
        new_files: List[str] = []
        new_debriefs: List[str] = []
        stage_event: Optional[str] = None

        for msg in reversed(messages):
            msg_id = msg.get("id", "")
            author_obj = msg.get("author", {})
            if author_obj.get("bot"):
                continue

            # If this message was posted before the bot's latest reply, it belongs to a past session:
            # mark as processed and do not re-trigger actions.
            if last_bot_msg_id and int(msg_id) <= last_bot_msg_id:
                processed_msg_ids.add(msg_id)
                continue

            should_reply = send_bot_replies and (int(msg_id) > last_bot_msg_id)
            author_name = author_obj.get("global_name") or author_obj.get("username") or "Piloto"
            raw_content = (msg.get("content") or "").strip()
            # Clean any @Bot mentions (<@123456> or <@!123456>) so both mentioned and plain text work
            content = re.sub(r"<@!?\d+>", "", raw_content).strip()
            cmd = detect_stage_command(content) if content else None

            if cmd and msg_id not in processed_msg_ids:
                cmd_type = cmd[0]
                cmd_round = cmd[1]
                cmd_extra = cmd[2] if len(cmd) > 2 else None
                processed_msg_ids.add(msg_id)

                if cmd_type == "START_UDP_LISTENER":
                    from src.orchestrator_cli import start_udp_listener
                    r_num = cmd_round or state.get("active_round_num") or 11
                    ok, reply_txt = start_udp_listener(root_dir, round_num=r_num)
                    if should_reply:
                        self.post_channel_message(self.ingest_channel_id, reply_txt)
                    continue

                if cmd_type == "STATUS_UDP_LISTENER":
                    from src.orchestrator_cli import get_udp_listener_status
                    ok, reply_txt = get_udp_listener_status(root_dir)
                    if should_reply:
                        self.post_channel_message(self.ingest_channel_id, reply_txt)
                    continue

                if cmd_type == "STOP_UDP_LISTENER":
                    from src.orchestrator_cli import stop_udp_listener
                    ok, reply_txt = stop_udp_listener(root_dir)
                    if should_reply:
                        self.post_channel_message(self.ingest_channel_id, reply_txt)
                    continue

                if cmd_type == "STAGE_ROLLBACK":
                    r_num = cmd_round or state.get("active_round_num") or 11
                    scope = (cmd_extra or "sessao").lower().strip()
                    if r_num < 11:
                        if should_reply:
                            self.post_channel_message(
                                self.ingest_channel_id,
                                f"🛡️ **OPERAÇÃO BLOQUEADA — INTEGRIDADE DO CAMPEONATO:**\n"
                                f"As Etapas 01 a 10 são canônicas e imutáveis. O rollback só é permitido para a Etapa 11 em diante."
                            )
                        continue

                    state["pending_rollback"] = {
                        "round_num": r_num,
                        "scope": scope,
                        "timestamp": time.time(),
                    }
                    scope_desc = {
                        "sessao": "reverte telemetria, fotos, debriefings, classificação da FIA e módulos M3 a M8 (preserva M1 e M2)",
                        "coletiva": "reverte ata oficial M2 e purga declarações da coletiva no Canon Ledger",
                        "semana": "reverte pré-semana M1 / M1.5 e reseta o cronograma diário",
                        "tudo": "apaga todos os dados e módulos da etapa, purga o Canon Ledger e reseta o estado para IDLE",
                    }.get(scope, scope)

                    if should_reply:
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"⚠️ **SOLICITAÇÃO DE ROLLBACK DETECTADA — ETAPA {r_num} (Escopo: `{scope.upper()}`)**\n\n"
                            f"• **Ação que será executada:** {scope_desc}.\n"
                            f"• **Confirmação Obrigatória:** Para confirmar a reversão imediata, digite **`confirmar rollback`** em até 60 segundos.\n"
                            f"• Para desistir, digite **`cancelar rollback`**."
                        )
                    continue

                if cmd_type == "CONFIRM_ROLLBACK":
                    pending = state.get("pending_rollback")
                    now = time.time()
                    if pending and (now - float(pending.get("timestamp", 0))) <= 60.0:
                        r_num = pending.get("round_num", 11)
                        scope = pending.get("scope", "sessao")
                        state["pending_rollback"] = None
                        from src.orchestrator_cli import execute_stage_rollback
                        try:
                            res = execute_stage_rollback(r_num, scope)
                            if should_reply:
                                self.post_channel_message(
                                    self.ingest_channel_id,
                                    f"✅ **ROLLBACK EXECUTADO COM SUCESSO — ETAPA {r_num} (Escopo: `{scope.upper()}`)**\n"
                                    f"• **Arquivos excluídos:** `{res['deleted_files_count']}`\n"
                                    f"• **Eventos removidos do Canon Ledger:** `{res['purged_canon_events']}`\n"
                                    f"• **Classificação da FIA:** `{'Restaurada etapa anterior' if res['reverted_standings'] else 'Preservada'}`\n"
                                    f"• 🌐 **Portal Editorial Recompilado:** Sincronizado e pronto para nova execução."
                                )
                        except Exception as exc:
                            if should_reply:
                                self.post_channel_message(
                                    self.ingest_channel_id,
                                    f"❌ **ERRO AO EXECUTAR ROLLBACK:** {exc}"
                                )
                    else:
                        state["pending_rollback"] = None
                        if should_reply:
                            self.post_channel_message(
                                self.ingest_channel_id,
                                f"ℹ️ Não há nenhuma solicitação de rollback pendente ou o tempo limite de 60 segundos expirou."
                            )
                    continue

                if cmd_type == "CANCEL_ROLLBACK":
                    state["pending_rollback"] = None
                    if should_reply:
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"🛑 **Solicitação de rollback cancelada.** Nenhum dado ou arquivo foi alterado."
                        )
                    continue

                if cmd_type == "FORCE_PRESS_CONF_ADVANCE":
                    active_r_num = int(state.get("active_round_num") or 11)
                    active_folder = state.get("active_round_folder") or ROUND_NUMBER_TO_FOLDER.get(active_r_num, f"et_{active_r_num:02d}")
                    press_conf_file = root_dir / "data" / "state" / f"press_conf_et{active_r_num:02d}.json"
                    if press_conf_file.exists():
                        try:
                            pc_data = json.loads(press_conf_file.read_text(encoding="utf-8"))
                            if pc_data.get("status") == "AWAITING_PILOT_REPLY":
                                from src.press_conference import PressConferenceSession
                                pc_sess = PressConferenceSession(root_dir, active_r_num, active_folder)
                                ack_msg = pc_sess.force_timeout_answer(reason="Comando manual de avanço da assessoria")
                                if should_reply and ack_msg:
                                    self.post_channel_message(self.ingest_channel_id, ack_msg)
                                next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                                if should_reply and next_msg:
                                    self.post_channel_message(self.ingest_channel_id, next_msg)
                                while not is_lock and not pc_sess.state.get("completed"):
                                    time.sleep(3.0)
                                    next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                                    if should_reply and next_msg:
                                        self.post_channel_message(self.ingest_channel_id, next_msg)
                            else:
                                if should_reply:
                                    self.post_channel_message(
                                        self.ingest_channel_id,
                                        f"ℹ️ A Coletiva da FIA da Etapa {active_r_num} não está aguardando resposta de piloto humano no momento."
                                    )
                        except Exception as exc:
                            if should_reply:
                                self.post_channel_message(self.ingest_channel_id, f"⚠️ Erro ao forçar avanço da coletiva: {exc}")
                    else:
                        if should_reply:
                            self.post_channel_message(
                                self.ingest_channel_id,
                                f"ℹ️ Nenhuma coletiva ativa encontrada para a Etapa {active_r_num}."
                            )
                    continue

                if cmd_type == "START_SEMANA":
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    state["status"] = "SEMANA_ACTIVE"
                    state["semana_day"] = 1
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    stage_event = f"SEMANA_TICK_{r_num}_1"
                    if should_reply:
                        meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"📅 **AGENDADOR DIÁRIO DA SILLY SEASON ATIVADO — {meta['flag']} Etapa {r_num}: {meta['name']}**!\n"
                            f"• Simulando a cobertura de Segunda a Quinta-feira.\n"
                            f"• 🚨 **Disparando Dia 1/4 (Segunda-Feira: Ressaca & Diagnóstico Técnico)**...\n"
                            f"💡 *Para avançar de dia rapidamente no teste, digite `avancar dia` ou `dia 2`.*",
                        )
                    continue

                if cmd_type.startswith("TICK_SEMANA"):
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    parts = cmd_type.split("_")
                    target_day = int(parts[-1]) if len(parts) >= 3 and parts[-1].isdigit() else min(state.get("semana_day", 1) + 1, 4)
                    state["status"] = "SEMANA_ACTIVE"
                    state["semana_day"] = target_day
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    stage_event = f"SEMANA_TICK_{r_num}_{target_day}"
                    if should_reply:
                        meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"⏩ **AVANÇANDO SILLY SEASON: DIA {target_day}/4 — {meta['flag']} Etapa {r_num}: {meta['name']}**!\n"
                            f"• Gerando dossiê de bastidores e publicando no Portal + `#repercussao-midia`...",
                        )
                    continue

                if cmd_type == "START_PRESS_CONF":
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    stage_event = f"START_PRESS_CONF_{r_num}"
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    if should_reply:
                        meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"🏛️ **COLETIVA OFICIAL DA FIA CONVOCADA — {meta['flag']} Etapa {r_num}: {meta['name']}**!\n"
                            f"• Convocando Sarah, Felipe, Davi e rivais para a bancada oficial.\n"
                            f"• 🎙️ A imprensa mundial fará perguntas aos pilotos humanos com **Trava de Turno** no chat!",
                        )
                    continue

                if cmd_type == "PRE":
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    stage_event = f"PRE_ROUND_{r_num}"
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    if should_reply:
                        meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"📰 **DOSSIÊ SILLY SEASON DISPARADO — {meta['flag']} Etapa {r_num}: {meta['name']}** (`{r_folder}`)\n"
                            f"Coletando fofocas de fábrica, contratos e sorteando temas RNG. Gerando 'A Semana da F1' (Módulo #1) para o Portal e `#repercussao-midia`!",
                        )
                    continue

                if cmd_type == "START":
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    state["status"] = "COLLECTING"
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    state["start_message_id"] = msg_id
                    state["session_files"] = []
                    state["debrief_messages"] = []
                    stage_event = f"START_ROUND_{r_num}"
                    if should_reply:
                        meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"🟢 **SESSÃO INICIADA — {meta['flag']} Etapa {r_num}: {meta['name']}** (`{r_folder}`)\n"
                            f"Estou escutando este canal! Podem subir:\n"
                            f"• 📸 **Fotos da TV** (TL, Classificação e 4 abas da Corrida)\n"
                            f"• 📊 **Arquivos `.csv` do PaceDex** (TL e Corrida)\n"
                            f"• 🎙️ **Áudios ou Textos de Debriefing** (sensações pós-corrida de Felipe, Davi e Sarah)\n"
                            f"Quando terminarem tudo, digitem **`final da etapa {r_num}`**!",
                        )
                    continue

                if cmd_type == "END" and state.get("status") == "COLLECTING":
                    r_num = cmd_round or state.get("active_round_num") or 10
                    r_folder = state.get("active_round_folder") or ROUND_NUMBER_TO_FOLDER.get(r_num, f"et_{r_num:02d}")
                    state["status"] = "READY_FOR_SIMULATION"
                    state["active_round_num"] = r_num
                    state["active_round_folder"] = r_folder
                    stage_event = f"END_ROUND_{r_num}"
                    total_session_files = len(state.get("session_files", []))
                    if should_reply:
                        self.post_channel_message(
                            self.ingest_channel_id,
                            f"🏁 **ETAPA {r_num} ENCERRADA (`{r_folder}`) — PACOTE RECEBIDO!**\n"
                            f"• Total de arquivos baixados na sessão: `{total_session_files}` (`{state.get('session_files', [])}`)\n"
                            f"• Relatos de Debriefing capturados: `{len(state.get('debrief_messages', []))}`\n"
                            f"⚙️ Iniciando fusão de telemetria PaceDex, cálculo oficial da FIA, geração dos relatórios e publicação no Portal Mobile + `#repercussao-midia`!",
                        )
                    continue

            # Interactive Press Conference Answer Detection (Trava de Turno)
            active_r_num = int(state.get("active_round_num") or 11)
            active_folder = state.get("active_round_folder") or ROUND_NUMBER_TO_FOLDER.get(active_r_num, f"et_{active_r_num:02d}")
            press_conf_file = root_dir / "data" / "state" / f"press_conf_et{active_r_num:02d}.json"
            if content and not cmd and msg_id not in processed_msg_ids and press_conf_file.exists():
                try:
                    pc_data = json.loads(press_conf_file.read_text(encoding="utf-8"))
                    if pc_data.get("status") == "AWAITING_PILOT_REPLY":
                        processed_msg_ids.add(msg_id)
                        waiting_driver = pc_data.get("waiting_for_driver") or "felipe"
                        from src.press_conference import PressConferenceSession
                        pc_sess = PressConferenceSession(root_dir, active_r_num, active_folder)
                        ack_msg = pc_sess.submit_pilot_answer(waiting_driver, content)
                        if should_reply:
                            self.post_channel_message(self.ingest_channel_id, ack_msg)
                        next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                        if should_reply and next_msg:
                            self.post_channel_message(self.ingest_channel_id, next_msg)

                        # Se a pergunta seguinte for de NPC (is_lock == False), avança automaticamente até atingir o próximo piloto humano ou o término
                        while not is_lock and not pc_sess.state.get("completed"):
                            time.sleep(3.0)
                            next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                            if should_reply and next_msg:
                                self.post_channel_message(self.ingest_channel_id, next_msg)
                        continue
                except Exception as exc:
                    print(f"[Press Conf Answer Warning] {exc}")

            # Auto-timeout check for Press Conference (Turn-Lock Fallback)
            if press_conf_file.exists() and not cmd:
                try:
                    pc_data = json.loads(press_conf_file.read_text(encoding="utf-8"))
                    if pc_data.get("status") == "AWAITING_PILOT_REPLY":
                        asked_ts = float(pc_data.get("question_asked_timestamp", 0))
                        timeout_limit = float(os.environ.get("PRESS_CONF_TIMEOUT_SECONDS", "300"))
                        if asked_ts > 0 and (time.time() - asked_ts) > timeout_limit:
                            from src.press_conference import PressConferenceSession
                            pc_sess = PressConferenceSession(root_dir, active_r_num, active_folder)
                            ack_msg = pc_sess.force_timeout_answer(reason=f"tempo regulamentar esgotado ({int(timeout_limit)}s)")
                            if should_reply and ack_msg:
                                self.post_channel_message(self.ingest_channel_id, f"⏰ **TEMPO REGULAMENTAR ESGOTADO NA COLETIVA FIA:**\n{ack_msg}")
                            next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                            if should_reply and next_msg:
                                self.post_channel_message(self.ingest_channel_id, next_msg)
                            while not is_lock and not pc_sess.state.get("completed"):
                                time.sleep(3.0)
                                next_msg, is_lock, next_driver = pc_sess.advance_to_next_question()
                                if should_reply and next_msg:
                                    self.post_channel_message(self.ingest_channel_id, next_msg)
                except Exception as exc:
                    print(f"[Press Conf Auto-Timeout Check Warning] {exc}")

            # Only collect attachments and debrief notes sent AFTER the current session's `start_message_id`
            start_id = state.get("start_message_id")
            if state.get("status") != "COLLECTING" or (start_id and int(msg_id) <= int(start_id)):
                continue

            tel_dir = root_dir / "data" / "seasons" / "season_01" / active_folder / "telemetry"
            photos_dir = root_dir / "data" / "seasons" / "season_01" / active_folder / "photos"
            debrief_dir = root_dir / "data" / "seasons" / "season_01" / active_folder / "debriefing"

            # 1. Download any attachments (.csv -> telemetry/, .jpg/.png -> photos/, audio -> debriefing/)
            msg_photos: List[str] = []
            msg_csvs: List[str] = []
            msg_audios: List[str] = []
            for att in msg.get("attachments", []):
                fname = att.get("filename", "")
                lower_f = fname.lower()
                if not lower_f.endswith(INGEST_ALLOWED_EXTENSIONS):
                    continue
                unique_key = f"{msg_id}_{fname}"
                if unique_key in processed_keys:
                    continue
                if lower_f.endswith((".ogg", ".mp3", ".wav", ".m4a", ".opus")):
                    dest_dir = debrief_dir
                    msg_audios.append(fname)
                elif lower_f.endswith(".csv"):
                    dest_dir = tel_dir
                    msg_csvs.append(fname)
                else:
                    dest_dir = photos_dir
                    msg_photos.append(fname)
                dest_path = dest_dir / fname
                self.download_attachment(att["url"], dest_path)
                processed_keys.add(unique_key)
                new_files.append(fname)
                state.setdefault("session_files", []).append(fname)

            if should_reply and (msg_photos or msg_csvs or msg_audios):
                ack_parts: List[str] = []
                if msg_photos:
                    ack_parts.append(f"📸 **{len(msg_photos)} foto(s) da TV** arquivadas em `photos/`")
                if msg_csvs:
                    ack_parts.append(f"📊 **{len(msg_csvs)} telemetria(s) PaceDex (`.csv`)** arquivadas em `telemetry/` (`{', '.join(msg_csvs)}`)")
                if msg_audios:
                    ack_parts.append(f"🎙️ **{len(msg_audios)} áudio(s) de debriefing** arquivados em `debriefing/`")
                self.post_channel_message(
                    self.ingest_channel_id,
                    f"📥 **Recebido de {author_name}:** " + " | ".join(ack_parts),
                )

            # 2. Capture non-command text messages as driver debriefing notes
            if content and not cmd and msg_id not in processed_msg_ids and state.get("status") == "COLLECTING":
                processed_msg_ids.add(msg_id)
                note_entry = f"- **[{msg.get('timestamp', '')}] {author_name}:** {content}"
                state.setdefault("debrief_messages", []).append(note_entry)
                new_debriefs.append(note_entry)
                debrief_dir.mkdir(parents=True, exist_ok=True)
                notes_file = debrief_dir / "debriefing_notes.md"
                existing_notes = notes_file.read_text(encoding="utf-8") if notes_file.exists() else "# Relatos de Debriefing Pós-Corrida (Discord Voice Chat)\n\n"
                notes_file.write_text(existing_notes + note_entry + "\n", encoding="utf-8")
                if should_reply:
                    self.post_channel_message(
                        self.ingest_channel_id,
                        f"📝 **Debriefing de {author_name} registrado!** (`\"{content[:80]}{'...' if len(content) > 80 else ''}\"`)",
                    )

        state["downloaded_keys"] = sorted(processed_keys)
        state["processed_msg_ids"] = sorted(processed_msg_ids)
        state["last_poll_new_files"] = new_files
        state["last_poll_stage_event"] = stage_event

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return state

    def download_attachment(self, url: str, target_path: Path) -> Path:
        """
        Download a Discord CDN attachment (.csv, .jpg, .png) to local disk.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "F1SimulatorBot (https://antigravity.google, 1.0)"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            target_path.write_bytes(resp.read())
        return target_path

    def sync_ingest_channel_to_dir(
        self,
        target_dir: Path,
        state_file: Path,
        limit: int = 50,
    ) -> List[Path]:
        """
        Idempotently scan the Voice Channel's text chat (#1457392708355096580),
        download any new PaceDex CSVs and TV screenshots not yet in state_file,
        and record their message_id + filename to prevent duplicate downloads.
        """
        seen: Dict[str, Any] = {}
        if state_file.exists():
            seen = json.loads(state_file.read_text(encoding="utf-8"))
        processed_keys = set(seen.get("downloaded_keys", []))

        attachments = self.fetch_recent_ingest_attachments(limit=limit)
        downloaded_files: List[Path] = []

        for att in reversed(attachments):
            unique_key = f"{att['message_id']}_{att['filename']}"
            if unique_key in processed_keys:
                continue
            dest = target_dir / att["filename"]
            self.download_attachment(att["url"], dest)
            downloaded_files.append(dest)
            processed_keys.add(unique_key)

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"downloaded_keys": sorted(processed_keys)}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return downloaded_files

    def _post_multipart_with_files(
        self,
        url: str,
        payload_json: Dict[str, Any],
        files: List[Tuple[str, bytes, str]],
        max_retries: int = 3,
    ) -> Any:
        """
        Send a multipart/form-data POST request to Discord Webhook or REST API
        with `payload_json` and binary file attachments (e.g. PNG tables).
        """
        boundary = f"----F1SimBoundary{uuid.uuid4().hex}"
        body_parts: List[bytes] = []

        # Part 1: payload_json
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(b'Content-Disposition: form-data; name="payload_json"\r\n')
        body_parts.append(b"Content-Type: application/json\r\n\r\n")
        body_parts.append(json.dumps(payload_json).encode("utf-8"))
        body_parts.append(b"\r\n")

        # Part 2..N: files[i]
        for idx, (filename, file_bytes, mime_type) in enumerate(files):
            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(
                f'Content-Disposition: form-data; name="files[{idx}]"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body_parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
            body_parts.append(file_bytes)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body_bytes = b"".join(body_parts)

        headers = {
            "User-Agent": "F1SimulatorBot (https://antigravity.google, 1.0)",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if self.bot_token and "webhooks" not in url:
            headers["Authorization"] = f"Bot {self.bot_token}"

        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_after = float(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                    time.sleep(retry_after)
                    continue
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def publish_markdown_report(
        self,
        markdown_text: str,
        persona_name: str = "FIA Official Media Center",
        avatar_url: Optional[str] = None,
        render_tables: bool = True,
    ) -> List[str]:
        """
        Transform Markdown pipe tables into Mobile-First Cards + F1 TV PNG graphics,
        chunk the text, and publish to #repercussao-midia (#1536416375969685524).
        """
        table_images: List[Tuple[str, bytes]] = []
        if render_tables:
            markdown_text, table_images = transform_markdown_tables_for_discord(markdown_text)

        chunks = split_markdown_for_discord(markdown_text, max_chars=1950)
        message_ids: List[str] = []

        for chunk in chunks:
            if self.webhook_url:
                payload: Dict[str, Any] = {"content": chunk, "username": persona_name}
                if avatar_url:
                    payload["avatar_url"] = avatar_url
                res = self._request_with_backoff(f"{self.webhook_url}?wait=true", method="POST", payload=payload)
                if isinstance(res, dict) and "id" in res:
                    message_ids.append(res["id"])
            elif self.bot_token:
                url = f"{DISCORD_API_BASE}/channels/{self.publish_channel_id}/messages"
                res = self._request_with_backoff(url, method="POST", payload={"content": chunk})
                if isinstance(res, dict) and "id" in res:
                    message_ids.append(res["id"])
            else:
                raise PermissionError("Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN must be configured.")
            time.sleep(0.5)

        # Attach high-res F1 TV PNG tables at the end of the report
        if table_images:
            files_payload = [(fname, fbytes, "image/png") for fname, fbytes in table_images]
            caption = "📊 **Painéis Oficiais FIA / F1 TV (Alta Resolução — Toque para ampliar):**"
            if self.webhook_url:
                payload = {"content": caption, "username": persona_name}
                if avatar_url:
                    payload["avatar_url"] = avatar_url
                res = self._post_multipart_with_files(
                    f"{self.webhook_url}?wait=true", payload_json=payload, files=files_payload
                )
                if isinstance(res, dict) and "id" in res:
                    message_ids.append(res["id"])
            elif self.bot_token:
                url = f"{DISCORD_API_BASE}/channels/{self.publish_channel_id}/messages"
                res = self._post_multipart_with_files(
                    url, payload_json={"content": caption}, files=files_payload
                )
                if isinstance(res, dict) and "id" in res:
                    message_ids.append(res["id"])

        return message_ids

    def publish_editorial_teaser(
        self,
        markdown_text: str,
        article_title: str,
        portal_url: str,
        persona_name: str = "FIA Official Media Center",
        avatar_url: Optional[str] = None,
    ) -> str:
        """
        Publish a single zero-scroll Breaking News Teaser to Discord (#repercussao-midia)
        containing:
          - Headline & Top 3 / Executive Bullet Summary
          - Direct Mobile Link to the Editorial Portal & Season Wiki
          - High-Resolution F1 TV / FIA PNG Table attachments (if any)
        """
        transformed_md, table_images = transform_markdown_tables_for_discord(markdown_text)

        # Extract the first 3 mobile cards or first 2 paragraphs as an executive teaser
        lines = [ln.strip() for ln in transformed_md.splitlines() if ln.strip()]
        quote_lines = [ln for ln in lines if ln.startswith("> ")][:9]
        body_paragraphs = [
            ln for ln in lines if not ln.startswith(("#", "*", ">", "---", "📱"))
        ][:2]

        teaser_parts = [f"🚨 **{article_title.upper()}**"]
        if body_paragraphs:
            teaser_parts.append("\n".join(body_paragraphs)[:450])
        if quote_lines:
            teaser_parts.append("\n".join(quote_lines)[:750])

        teaser_parts.append(
            f"📖 **Leia a matéria completa, crônica de pista e tabelas interativas no Portal Mobile:**\n"
            f"👉 {portal_url}"
        )
        content_str = "\n\n".join(teaser_parts)[:1950]

        files_payload = [(fname, fbytes, "image/png") for fname, fbytes in table_images[:4]]

        if self.webhook_url:
            payload: Dict[str, Any] = {"content": content_str, "username": persona_name}
            if avatar_url:
                payload["avatar_url"] = avatar_url
            if files_payload:
                res = self._post_multipart_with_files(
                    f"{self.webhook_url}?wait=true", payload_json=payload, files=files_payload
                )
            else:
                res = self._request_with_backoff(f"{self.webhook_url}?wait=true", method="POST", payload=payload)
            return res.get("id", "") if isinstance(res, dict) else ""

        if self.bot_token:
            url = f"{DISCORD_API_BASE}/channels/{self.publish_channel_id}/messages"
            if files_payload:
                res = self._post_multipart_with_files(
                    url, payload_json={"content": content_str}, files=files_payload
                )
            else:
                res = self._request_with_backoff(url, method="POST", payload={"content": content_str})
            return res.get("id", "") if isinstance(res, dict) else ""

        raise PermissionError("Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN must be configured.")

