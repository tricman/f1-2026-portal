"""
Autonomous Multimodal AI Showrunner Engine (SAD v2.0 - Google AI Studio Free Tier).
Uses Gemini 2.5 Flash (Vision OCR + Audio Debrief Transcription + Canon Digest)
and Gemini 2.5 Pro (Chained Narrative Generation M1..M8 with 3-Layer Storytelling Memory).
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.canon_ledger import CanonLedgerManager, sample_weekly_themes
from src.logger import log_text, trace
from src.portal_builder import ROUND_METADATA
from src.season_manager import get_season_dir, get_current_season_id
from src.tracer import trace_span

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


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_FLASH_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
]


class GeminiFreeTierClient:
    """
    Zero-dependency client for Google AI Studio (Gemini Developer API)
    with built-in rate-limit pacing and exponential backoff for Free Tier (R$ 0,00).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        flash_model: str = "gemini-flash-lite-latest",
        pro_model: str = "gemini-3.1-pro-preview",
        pacing_seconds: float = 32.0,
    ) -> None:
        load_dotenv_if_present()
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.pacing_seconds = pacing_seconds
        self._last_pro_call_ts: float = 0.0

    @trace_span("gemini_generate_content")
    def _call_generate_content(
        self,
        model: str,
        parts: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.4,
        response_mime_type: str = "text/plain",
        max_retries: int = 4,
    ) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY não configurada no ambiente ou .env.")

        if model == self.pro_model and self._last_pro_call_ts > 0:
            elapsed = time.time() - self._last_pro_call_ts
            if elapsed < self.pacing_seconds:
                wait_s = self.pacing_seconds - elapsed
                print(f"[AI Pacer - Free Tier] Aguardando {wait_s:.1f}s para respeitar limite gratuito do {model}...")
                time.sleep(wait_s)

        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": response_mime_type,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        chars_in = len(body_bytes)
        t_start = time.time()

        models_to_try = [model] + [m for m in FALLBACK_FLASH_MODELS if m != model]
        total_attempts = max(max_retries, len(models_to_try) + 2)

        for attempt in range(total_attempts):
            active_model = models_to_try[min(attempt, len(models_to_try) - 1)]
            active_url = f"{GEMINI_API_BASE}/{active_model}:generateContent?key={self.api_key}"
            log_text(f"🤖 [GEMINI REQUEST] Modelo: {active_model} | Payload: {chars_in:,} bytes (~{chars_in // 4:,} tokens) | Tentativa {attempt + 1}/{total_attempts}")
            trace(
                f"Disparando chamada Gemini ({active_model})",
                event="LLM_DISPATCH",
                model=active_model,
                details={
                    "payload_bytes": chars_in,
                    "estimated_tokens": chars_in // 4,
                    "temperature": temperature,
                    "attempt": attempt + 1,
                    "max_attempts": total_attempts,
                    "system_instruction_len": len(system_instruction) if system_instruction else 0,
                    "prompt_preview": str(parts)[:400],
                },
            )
            req = urllib.request.Request(active_url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    if active_model == self.pro_model:
                        self._last_pro_call_ts = time.time()
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Resposta vazia do Gemini ({active_model}): {data}")
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    result_text = "".join(p.get("text", "") for p in content_parts)
                    elapsed = time.time() - t_start
                    duration_ms = round(elapsed * 1000, 2)
                    log_text(f"✨ [GEMINI RESPONSE] 200 OK ({active_model}) em {elapsed:.2f}s | Gerados: {len(result_text):,} chars")
                    trace(
                        f"Resposta recebida Gemini ({active_model}) em {elapsed:.2f}s",
                        event="LLM_RESPONSE",
                        model=active_model,
                        duration_ms=duration_ms,
                        details={
                            "output_chars": len(result_text),
                            "estimated_output_tokens": len(result_text) // 4,
                            "candidates_count": len(candidates),
                            "output_preview": result_text[:400],
                        },
                    )
                    return result_text
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                trace(
                    f"Erro HTTP {exc.code} ao chamar Gemini ({active_model})",
                    event="LLM_HTTP_ERROR",
                    model=active_model,
                    details={"http_code": exc.code, "error_body": err_body[:500]},
                    exc=exc,
                )
                if exc.code in (429, 500, 502, 503, 504) and attempt < total_attempts - 1:
                    next_model = models_to_try[min(attempt + 1, len(models_to_try) - 1)]
                    wait_time = 4.0 * (attempt + 1) if exc.code != 429 else 12.0 * (attempt + 1)
                    log_text(
                        f"⚠️ [GEMINI HTTP {exc.code} em {active_model}] Tentativa {attempt + 1}/{total_attempts}. "
                        f"Aguardando {wait_time:.0f}s e tentando {next_model}..."
                    )
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Gemini API HTTP {exc.code} ({active_model}): {err_body}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                trace(
                    f"Timeout/Rede ao chamar Gemini ({active_model}): {exc}",
                    event="LLM_NETWORK_ERROR",
                    model=active_model,
                    exc=exc,
                )
                if attempt < total_attempts - 1:
                    next_model = models_to_try[min(attempt + 1, len(models_to_try) - 1)]
                    log_text(
                        f"⚠️ [GEMINI TIMEOUT/NETWORK em {active_model}] Tentativa {attempt + 1}/{total_attempts}. "
                        f"Alternando para {next_model}..."
                    )
                    time.sleep(3.0)
                    continue
                raise RuntimeError(f"Gemini Timeout ({active_model}): {exc}") from exc

        raise RuntimeError(f"Falha ao chamar Gemini ({model}) após {total_attempts} tentativas.")

    def extract_tv_overlay_from_photos(
        self,
        photos_dir: Path,
        output_json_path: Path,
        round_num: int,
        round_name: str,
    ) -> Dict[str, Any]:
        """
        Stage 1A: Read TV photos (.jpg/.png) using Gemini 2.5 Flash Vision OCR
        and output the canonical `tv_overlay_etXX.json` schema.
        """
        if output_json_path.exists():
            print(f"[Vision OCR] Usando overlay existente: {output_json_path.name}")
            return json.loads(output_json_path.read_text(encoding="utf-8"))

        photo_files = sorted(
            [p for p in photos_dir.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        )
        if not photo_files:
            raise FileNotFoundError(f"Nenhuma foto da TV encontrada em {photos_dir}")

        parts: List[Dict[str, Any]] = []
        for img_path in photo_files:
            mime_type = mimetypes.guess_type(img_path.name)[0] or "image/jpeg"
            b64_data = base64.b64encode(img_path.read_bytes()).decode("ascii")
            parts.append({"inlineData": {"mimeType": mime_type, "data": b64_data}})

        prompt = (
            f"Extraia com 100% de precisão todos os dados das telas da TV do jogo EA Sports F1 24 "
            f"referentes à Etapa {round_num} ({round_name}).\n"
            "Retorne ESTRITAMENTE um objeto JSON válido seguindo este schema:\n"
            "{\n"
            '  "round": int,\n'
            '  "grand_prix": str,\n'
            '  "qualifying_results": [{"pos": int, "driver_number": int, "driver_name": str, "team": str, "best_lap": str, "gap": str}],\n'
            '  "race_results": [{"pos": int, "driver_number": int, "driver_name": str, "team": str, "grid": int, "stops": int, "best_lap": str, "total_time_or_gap": str, "points": int, "status": "FINISHED"|"DNF"|"DSQ"}],\n'
            '  "incidents": [{"lap": int, "driver": str, "incident": str, "penalty": str}]\n'
            "}"
        )
        parts.append({"text": prompt})

        raw_json = self._call_generate_content(
            model=self.flash_model,
            parts=parts,
            temperature=0.1,
            response_mime_type="application/json",
        )
        parsed = json.loads(raw_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return parsed

    def transcribe_audio_debriefs(self, debrief_dir: Path) -> str:
        """
        Stage 1B: Transcribe any .ogg, .mp3, .wav, .m4a audio files in `debriefing/`
        using Gemini 2.5 Flash and append them to `debriefing_notes.md`.
        """
        notes_file = debrief_dir / "debriefing_notes.md"
        existing_notes = (
            notes_file.read_text(encoding="utf-8")
            if notes_file.exists()
            else "# Relatos de Debriefing Pós-Corrida (Discord Voice Chat)\n\n"
        )
        if not debrief_dir.exists():
            return existing_notes

        audio_files = sorted(
            [p for p in debrief_dir.glob("*") if p.suffix.lower() in (".ogg", ".mp3", ".wav", ".m4a", ".opus")]
        )
        for audio_path in audio_files:
            marker = f"[Áudio: {audio_path.name}]"
            if marker in existing_notes:
                continue
            mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/ogg"
            b64_audio = base64.b64encode(audio_path.read_bytes()).decode("ascii")
            parts = [
                {"inlineData": {"mimeType": mime_type, "data": b64_audio}},
                {
                    "text": (
                        "Transcreva fielmente em Português (Brasil) este áudio de debriefing pós-corrida "
                        "enviado por um dos pilotos (Felipe, Davi ou Sarah) e indique o tom emocional."
                    )
                },
            ]
            try:
                transcript = self._call_generate_content(
                    model=self.flash_model,
                    parts=parts,
                    temperature=0.2,
                ).strip()
                entry = f"- **{marker} Transcrição de Áudio:** {transcript}\n"
                existing_notes += entry
            except Exception as exc:
                print(f"[Audio Debrief Warning] Falha ao transcrever {audio_path.name}: {exc}")

        if audio_files:
            debrief_dir.mkdir(parents=True, exist_ok=True)
            notes_file.write_text(existing_notes, encoding="utf-8")
        return existing_notes


def assemble_storytelling_context(root_dir: Path, round_num: int, round_folder: str) -> str:
    """
    Build the 3-Layer Storytelling Context (Long-Term Canon Ledger + Mid-Term FIA Standings
    + Rolling Window of Previous Round Reports & Current Driver Debriefs).
    """
    sections: List[str] = []

    # Layer 1: Master Canon Index & Setup Docs
    setup_dir = root_dir / "data" / "setup"
    if setup_dir.exists():
        for doc in sorted(setup_dir.glob("*.md"))[:4]:
            sections.append(f"=== DOCUMENTO CANÔNICO: {doc.name} ===\n{doc.read_text(encoding='utf-8')}")

    # Layer 1B: Canon Ledger JSON
    ledger_path = root_dir / "data" / "state" / "canon_ledger.json"
    if ledger_path.exists():
        sections.append(f"=== CANON LEDGER (EVENTOS E REPUTAÇÃO) ===\n{ledger_path.read_text(encoding='utf-8')}")

    # Layer 2: FIA Championship Standings (latest available up to round_num)
    state_dir = root_dir / "data" / "state"
    st_file = state_dir / "standings.json"
    for r_check in range(round_num, 0, -1):
        candidate = state_dir / f"standings_et{r_check:02d}.json"
        if candidate.exists():
            st_file = candidate
            break
    if st_file.exists():
        sections.append(f"=== TABELA OFICIAL DO CAMPEONATO FIA ({st_file.name}) ===\n{st_file.read_text(encoding='utf-8')}")

    # Layer 3A: Previous Round Narrative Summary (Rolling Window)
    prev_num = round_num - 1
    if prev_num >= 1:
        seasons_dir = get_season_dir(root_dir)
        prev_folders = [d for d in seasons_dir.glob(f"et_{prev_num:02d}_*") if d.is_dir()]
        if prev_folders:
            prev_dir = prev_folders[0]
            for md_file in sorted(prev_dir.glob("*.md")):
                if any(k in md_file.name.lower() for k in ("resultado final", "cerimônia", "repercussão")):
                    text = md_file.read_text(encoding="utf-8")
                    sections.append(f"=== MEMÓRIA DA ETAPA ANTERIOR ({prev_dir.name} / {md_file.name}) ===\n{text[:6000]}")

    # Layer 3B: Current Round Driver Debriefing Notes
    debrief_file = get_season_dir(root_dir) / round_folder / "debriefing" / "debriefing_notes.md"
    if debrief_file.exists():
        sections.append(
            f"=== RELATOS DE DEBRIEFING DOS PILOTOS (ETAPA {round_num}) ===\n{debrief_file.read_text(encoding='utf-8')}"
        )

    return "\n\n".join(sections)


@trace_span("finalize_round_transition")
def finalize_round_transition(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    ai_client: Optional[GeminiFreeTierClient] = None,
    season_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the deterministic + narrative transition from Round N to Round N+1:
    1. Promote `standings_et{N}.json` to `standings.json` so Round N+1 starts from the updated table.
    2. Extract a structured Canon Digest from Round N's race/podium reports and append to `canon_ledger.json`.
    """
    state_dir = root_dir / "data" / "state"
    et_standings = state_dir / f"standings_et{round_num:02d}.json"
    main_standings = state_dir / "standings.json"
    if et_standings.exists():
        main_standings.write_text(et_standings.read_text(encoding="utf-8"), encoding="utf-8")

    ledger_path = state_dir / "canon_ledger.json"
    ledger_mgr = CanonLedgerManager(ledger_path)
    ledger = ledger_mgr.load()
    event_id = f"ET{round_num:02d}-AUTO-M5"
    existing_ids = {ev.get("event_id") for ev in ledger.get("events", [])}

    round_dir = get_season_dir(root_dir, season_id) / round_folder
    md_summaries = []
    for f in sorted(round_dir.glob("*.md")):
        md_summaries.append(f"## {f.name}\n{f.read_text(encoding='utf-8')[:2500]}")

    if event_id not in existing_ids and md_summaries:
        summary_text = f"Resumo canônico consolidado da Etapa {round_num} ({round_folder})."
        if ai_client and ai_client.api_key:
            try:
                digest_prompt = (
                    f"Resuma em 1 parágrafo denso (máximo 450 caracteres) os principais fatos canônicos "
                    f"da Etapa {round_num} ({round_folder}): vencedor, pódio, incidentes de pista, "
                    f"destaques de telemetria e ganchos dramáticos para a próxima corrida:\n\n"
                    + "\n\n".join(md_summaries[:4])
                )
                summary_text = ai_client._call_generate_content(
                    model=ai_client.flash_model,
                    parts=[{"text": digest_prompt}],
                    temperature=0.2,
                ).strip()
            except Exception as exc:
                print(f"[Canon Digest Warning] Usando resumo padrão: {exc}")

        ledger_mgr.append_event(
            event_id=event_id,
            round_num=round_num,
            module="M5_CORRIDA",
            summary=summary_text,
            entities=["sarah", "davi", "felipe"],
            status="OPEN",
        )

    return {
        "round_finalized": round_num,
        "next_round": round_num + 1,
        "standings_promoted": et_standings.exists(),
    }


@trace_span("generate_post_race_modules")
def generate_post_race_modules(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    ai_client: GeminiFreeTierClient,
    season_id: Optional[str] = None,
) -> List[Path]:
    """
    Generate M3 (Treino Livre), M4 (Classificação), M5 (Resultado Final),
    M6 (Cerimônia do Pódio), M7 (Atualização Classificação) and M8 (Repercussão Imprensa)
    automatically via Gemini if they do not exist yet in the round folder.
    """
    round_dir = get_season_dir(root_dir, season_id) / round_folder
    round_dir.mkdir(parents=True, exist_ok=True)
    tel_dir = round_dir / "telemetry"
    meta = ROUND_METADATA.get(round_folder, {"name": f"GP Etapa {round_num}", "circuit": "", "flag": "🏁"})
    gp_title = f"{meta['name']} 2026"

    base_context = assemble_storytelling_context(root_dir, round_num, round_folder)[:18000]
    fp_json = (tel_dir / "fp_telemetry_merged.json").read_text(encoding="utf-8")[:12000] if (tel_dir / "fp_telemetry_merged.json").exists() else "{}"
    race_json = (tel_dir / "race_telemetry_merged.json").read_text(encoding="utf-8")[:14000] if (tel_dir / "race_telemetry_merged.json").exists() else "{}"
    tv_json_path = tel_dir / f"tv_overlay_et{round_num:02d}.json"
    tv_json = tv_json_path.read_text(encoding="utf-8")[:12000] if tv_json_path.exists() else "{}"
    debrief_file = round_dir / "debriefing" / "debriefing_notes.md"
    debrief_text = debrief_file.read_text(encoding="utf-8").strip() if debrief_file.exists() else ""

    module_specs = [
        (
            f"Etapa {round_num:02d} - Relatório Oficial FIA - Treino Livre - {gp_title}.md",
            "03_fia_treino_livre.md",
            f"Gere o Relatório Oficial FIA do Treino Livre (M3) da Etapa {round_num} ({gp_title}) em Markdown GFM completo com tabela de 20 pilotos e análise técnica PaceDex.\nDADOS TELEMETRIA TL:\n{fp_json}",
        ),
        (
            f"Etapa {round_num:02d} - Relatório Oficial FIA - Treino de Classificação - {gp_title}.md",
            "04_fia_classificacao.md",
            f"Gere o Relatório Oficial FIA do Treino de Classificação e Grid Final de Largada (M4) da Etapa {round_num} ({gp_title}) em Markdown GFM completo com tabela dos 20 pilotos.\nDADOS TV OVERLAY / GRID:\n{tv_json}",
        ),
        (
            f"Etapa {round_num:02d} - Relatório Oficial FIA - Resultado Final - {gp_title}.md",
            "05_fia_corrida.md",
            f"Gere o Relatório Oficial FIA do Resultado Final da Corrida (M5) da Etapa {round_num} ({gp_title}) em Markdown GFM completo com tabela oficial dos 20 pilotos, pit stops, pneus, decisões dos comissários e crônica pós-corrida incluindo os relatos de debriefing.\nDADOS CORRIDA PACEDEX + FIA:\n{race_json}\nRELATOS DE DEBRIEFING:\n{debrief_text}",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Cerimônia do Pódio e Bastidores - {gp_title}.md",
            "06_cerimonia_podio.md",
            f"Gere o módulo Pós-Corrida: Cerimônia do Pódio, Sala de Resfriamento (Cooldown Room), Bastidores dos Motorhomes, Declarações de Pilotos NPCs Relevantes e Ingestão dos Áudios de Debriefing (M6) da Etapa {round_num} ({gp_title}) em 4 Atos estruturados.\nDADOS CORRIDA:\n{race_json}\nRELATOS DE DEBRIEFING DE ÁUDIO:\n{debrief_text}",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Relatório FIA - Atualização Classificação Pilotos e Construtores.md",
            "07_fia_mundial.md",
            f"Gere o Boletim Oficial FIA de Atualização do Mundial de Pilotos e Construtores (M7) pós-Etapa {round_num} ({gp_title}). PROIBIDO somar pontos manualmente: use estritamente os números da TABELA OFICIAL DO CAMPEONATO FIA no contexto.",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Repercussão Imprensa e Internet - {gp_title}.md",
            "08_repercussao_midia.md",
            f"Gere o módulo M8 da Etapa {round_num} ({gp_title}) em 4 Partes estruturadas:\n"
            f"1. A Crônica Geral do Grande Prêmio (Race Chronicle);\n"
            f"2. A Bancada de Lendas da Fórmula 1 (Notas de 0 a 10 e análises técnicas detalhadas de Alain Prost, Nigel Mansell e Jacques Villeneuve);\n"
            f"3. Repercussão na Imprensa Internacional e Brasileira;\n"
            f"4. Podcasts, YouTube e Redes Sociais.\n"
            f"DADOS DE TELEMETRIA E INCIDENTES:\n{race_json}\nDEBRIEFINGS DE ÁUDIO:\n{debrief_text}",
        ),
    ]

    generated: List[Path] = []
    chained_outputs: List[str] = []

    for filename, prompt_file, task_instructions in module_specs:
        target_md = round_dir / filename
        if target_md.exists():
            chained_outputs.append(f"=== MÓDULO JÁ GERADO ({filename}) ===\n{target_md.read_text(encoding='utf-8')[:4000]}")
            continue

        prompt_template_path = root_dir / "prompts" / prompt_file
        prompt_template = prompt_template_path.read_text(encoding="utf-8") if prompt_template_path.exists() else ""

        extra_persona_context = ""
        if "08_repercussao_midia" in prompt_file:
            prost_path = root_dir / "personas" / "alain_prost_ex_driver.md"
            mansell_path = root_dir / "personas" / "nigel_mansell.md"
            villeneuve_path = root_dir / "personas" / "jacques_villeneuve.md"
            prost_txt = prost_path.read_text(encoding="utf-8") if prost_path.exists() else ""
            mansell_txt = mansell_path.read_text(encoding="utf-8") if mansell_path.exists() else ""
            villeneuve_txt = villeneuve_path.read_text(encoding="utf-8") if villeneuve_path.exists() else ""
            extra_persona_context = (
                f"\n\n=== PERSONAS DA BANCADA DE LENDAS DA FÓRMULA 1 ===\n"
                f"--- ALAIN PROST (O Professor) ---\n{prost_txt}\n\n"
                f"--- NIGEL MANSELL (Il Leone) ---\n{mansell_txt}\n\n"
                f"--- JACQUES VILLENEUVE (O Franco-Atirador) ---\n{villeneuve_txt}\n"
            )

        full_prompt = (
            f"{base_context}\n\n"
            + ("\n\n".join(chained_outputs[-2:]) if chained_outputs else "")
            + extra_persona_context
            + f"\n\n=== DIRETRIZ DO MÓDULO ({prompt_file}) ===\n{prompt_template}\n\n"
            + f"=== TAREFA DE GERAÇÃO ===\n{task_instructions}"
        )
        print(f"[AI Showrunner] Gerando módulo: {filename}...")
        template_fallback = root_dir / "data" / "templates" / round_folder / filename
        debrief_file = round_dir / "debriefing" / "debriefing_notes.md"
        debrief_text = debrief_file.read_text(encoding="utf-8").strip() if debrief_file.exists() else ""

        try:
            md_content = ai_client._call_generate_content(
                model=ai_client.flash_model,
                parts=[{"text": full_prompt}],
                system_instruction=(
                    "Você é o Showrunner Oficial e Diretor Técnico da FIA para a temporada 2026 de EA Sports F1 24. "
                    "Escreva em Português (Brasil) rico, imersivo e 100% fiel aos dados matemáticos fornecidos. "
                    "Nos relatórios da FIA (M3, M4, M5 e M7), inclua SEMPRE tabelas Markdown completas (| Pos. | Piloto | Equipe | ... |)."
                ),
                temperature=0.45,
                max_retries=2,
            ).strip()
        except Exception as exc:
            print(f"[Circuit Breaker Fallback] Usando template auditado da FIA para {filename} ({exc})")
            if template_fallback.exists():
                md_content = template_fallback.read_text(encoding="utf-8").strip()
                if debrief_text and ("Resultado Final" in filename or "Cerimônia" in filename):
                    md_content += f"\n\n---\n### 🎙️ Relatos e Áudios de Debriefing (Discord Voice Chat)\n\n{debrief_text}\n"
            else:
                md_content = f"# {filename.replace('.md', '')}\n\n{debrief_text}\n"

        target_md.write_text(md_content + "\n", encoding="utf-8")
        generated.append(target_md)
        chained_outputs.append(f"=== MÓDULO GERADO ({filename}) ===\n{md_content[:4000]}")
        time.sleep(2.0)

    return generated


ALL_10_CONSTRUCTORS = [
    ("Mercedes-AMG Petronas", "mercedes", "Sarah (#24) & Hamilton (#44)", "The Silver Bullet / Lady Paddock"),
    ("Stake F1 Team Kick Sauber", "sauber", "Felipe (#5) & Bottas (#77)", "The Paddock Mole / Lady Paddock"),
    ("Red Bull Racing", "red_bull", "Verstappen (#1) & Pérez (#11)", "The Paddock Mole"),
    ("McLaren F1 Team", "mclaren", "Norris (#4) & Piastri (#81)", "The Paddock Mole"),
    ("Aston Martin Aramco", "aston_martin", "Alonso (#14) & Stroll (#18)", "El Chisme de Montmeló"),
    ("Scuderia Ferrari", "ferrari", "Leclerc (#16) & Sainz (#55)", "Il Cavallino Spia"),
    ("Williams Racing", "williams", "Davi (#15) & Albon (#23)", "The Paddock Mole / Lady Paddock"),
    ("Alpine F1 Team", "alpine", "Gasly (#10) & Ocon (#31)", "El Chisme de Montmeló"),
    ("MoneyGram Haas F1 Team", "haas", "Magnussen (#20) & Hülkenberg (#27)", "The Paddock Mole"),
    ("Visa Cash App RB", "vcarb", "Tsunoda (#22) & Ricciardo (#3)", "Il Cavallino Spia"),
]


def generate_pre_race_m1(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    ai_client: GeminiFreeTierClient,
    force_regenerate: bool = False,
    season_id: Optional[str] = None,
) -> Path:
    """
    Generate or load M1 (A F1 Que Você Não Vê — Quadro: A Semana da F1) for Round N,
    grounded on Round N-1 standings, canon ledger events and deterministically sampled RNG weekly themes
    covering all 10 constructors of the 2026 grid.
    """
    from src.canon_ledger import sample_weekly_themes

    round_dir = get_season_dir(root_dir, season_id) / round_folder
    round_dir.mkdir(parents=True, exist_ok=True)
    target_file = round_dir / f"ET{round_num:02d}_PRE_A_Semana_da_F1.md"

    if target_file.exists() and target_file.stat().st_size > 1000 and not force_regenerate:
        print(f"[M1 Showrunner] M1 já existe para {round_folder} ({target_file.name})")
        return target_file

    prompt_file = root_dir / "prompts" / "01_semana_equipes.md"
    prompt_template = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
    base_context = assemble_storytelling_context(root_dir, round_num, round_folder)[:18000]

    # Sample RNG themes for all 10 constructors
    sampled_bullets = []
    for team_name, team_id, drivers, insider in ALL_10_CONSTRUCTORS:
        themes = sample_weekly_themes(round_num, team_id)
        sampled_bullets.append(
            f"- **{team_name}** ({drivers}) | Insider: *{insider}* | "
            f"Seg: {themes['monday']} | Ter: {themes['tuesday']} | Qua: {themes['wednesday']} | Qui: {themes['thursday']}"
        )

    rng_context = f"\n\n=== TEMAS RNG SORTEADOS PARA TODAS AS 10 EQUIPES (ETAPA {round_num}) ===\n" + "\n".join(sampled_bullets)

    full_prompt = (
        f"{base_context}\n{rng_context}\n\n=== DIRETRIZ DE GERAÇÃO DO MÓDULO 1 ===\n{prompt_template}\n\n"
        f"Gere o Módulo 1 completo cobrindo as 10 equipes da temporada 2026 de Segunda a Quinta-feira, "
        f"amarrando a tabela real da última etapa, a reputação dos pilotos e os temas sorteados acima."
    )

    print(f"[M1 Showrunner] Gerando Módulo 1 (A Semana da F1) para {round_folder}...")
    try:
        md_content = ai_client._call_generate_content(
            model=ai_client.flash_model,
            parts=[{"text": full_prompt}],
            system_instruction=(
                "Você é o coletivo de jornalistas insiders 'A F1 Que Você Não Vê'. "
                "Escreva crônicas mordazes, dinâmicas e ricas sobre os bastidores da F1 de Segunda a Quinta, cobrindo todas as 10 equipes."
            ),
            temperature=0.5,
            max_retries=2,
        ).strip()
    except Exception as exc:
        print(f"[M1 Fallback] Falha na geração do Gemini: {exc}")
        md_content = f"# 🏁 A F1 QUE VOCÊ NÃO VÊ — A Semana da F1 (Etapa {round_num})\n\nBastidores e intrigas no Paddock pré-{round_folder}.\n"

    target_file.write_text(md_content + "\n", encoding="utf-8")
    try:
        extract_and_record_m1_canon_event(root_dir, round_num, round_folder, md_content, ai_client)
    except Exception as exc:
        print(f"[Canon Event Warning] Falha ao sintetizar evento M1: {exc}")
    return target_file


@trace_span("generate_m1_daily_episode")
def generate_m1_daily_episode(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    day_num: int,
    ai_client: GeminiFreeTierClient,
    season_id: Optional[str] = None,
) -> Tuple[Path, str]:
    """
    Generates an episodic daily installment of M1 (A Semana da F1):
    day_num: 1=Segunda, 2=Terça, 3=Quarta, 4=Quinta.
    Covers ALL 10 CONSTRUCTORS and updates ET{round_num:02d}_PRE_A_Semana_da_F1.md
    with section-based deduplication (never duplicates existing days).
    """
    from src.canon_ledger import sample_weekly_themes

    day_names = {
        1: ("SEGUNDA-FEIRA", "A Ressaca da Corrida Anterior & Diagnóstico"),
        2: ("TERÇA-FEIRA", "Eventos VIP, Micos de Marketing & Bastidores"),
        3: ("QUARTA-FEIRA", "Simulador, Fábricas & Crises Contratuais"),
        4: ("QUINTA-FEIRA", "Desembarque no Paddock, Farpas & Comentários da Internet"),
    }
    day_label, day_theme_focus = day_names.get(day_num, ("SEGUNDA-FEIRA", "Bastidores da F1"))

    round_dir = get_season_dir(root_dir, season_id) / round_folder
    round_dir.mkdir(parents=True, exist_ok=True)
    target_file = round_dir / f"ET{round_num:02d}_PRE_A_Semana_da_F1.md"

    base_context = assemble_storytelling_context(root_dir, round_num, round_folder)[:15000]

    # Meta for current and previous GP
    meta_curr = ROUND_METADATA.get(round_folder, {"name": f"GP Etapa {round_num}", "circuit": "Circuito"})
    prev_num = round_num - 1
    prev_folder = f"et_{prev_num:02d}_espanha" if prev_num == 10 else f"et_{prev_num:02d}"
    meta_prev = ROUND_METADATA.get(prev_folder, {"name": f"GP Etapa {prev_num}"})

    day_key = {1: "monday", 2: "tuesday", 3: "wednesday", 4: "thursday"}.get(day_num, "monday")

    # Sample deterministic themes for ALL 10 teams
    sampled_bullets = []
    for team_name, team_id, drivers, insider in ALL_10_CONSTRUCTORS:
        themes = sample_weekly_themes(round_num, team_id)
        theme_for_day = themes.get(day_key, "Bastidores técnicos e políticos")
        sampled_bullets.append(f"- **{team_name}** ({drivers}) | Insider: *{insider}* | Tema sorteado: {theme_for_day}")

    themes_block = "\n".join(sampled_bullets)

    daily_prompt = (
        f"{base_context}\n\n"
        f"=== DIRETRIZ CRUCIAL: MÓDULO 1 · DIA {day_num} DE 4 ({day_label}) ===\n"
        f"GP Atual em Preparação: Etapa {round_num}: {meta_curr['name']} ({meta_curr.get('circuit', '')})\n"
        f"GP Anterior Concluído: Etapa {prev_num}: {meta_prev['name']}\n"
        f"Foco Narrativo do Dia: {day_theme_focus}\n\n"
        f"=== TEMAS SORTEADOS PARA TODAS AS 10 EQUIPES ===\n"
        f"{themes_block}\n\n"
        f"REGRAS DE CONTEÚDO:\n"
        f"1. Você DEVE cobrir TODAS AS 10 EQUIPES acima, em ordem, sem pular nenhuma.\n"
        f"2. Para CADA equipe, inclua:\n"
        f"   - Título da Equipe\n"
        f"   - **Local / Cidade:** (Onde a equipe/piloto está nesta {day_label})\n"
        f"   - **O Fato de Bastidor:** (O relato dramático, a fofoca ácida, a treta de garagem ou marketing)\n"
        f"   - **O comentário ácido do Insider:** (Citação em bloco `>` do correspondente indicado)\n"
        f"3. Atenção aos pilotos da Brazilian Storm (Sarah líder pela Mercedes, Felipe vice pela Sauber, Davi destaque pela Williams).\n"
        + ("4. Como é Quinta-Feira (Dia 4), conclua com a SÍNTESE DOS INSIDERS e 5 COMENTÁRIOS ÁCIDOS DE INTERNAUTAS (@fans).\n" if day_num == 4 else "")
    )

    try:
        episode_md = ai_client._call_generate_content(
            model=ai_client.flash_model,
            parts=[{"text": daily_prompt}],
            system_instruction=(
                "Você é o consórcio internacional de jornalistas investigativos 'A F1 Que Você Não Vê'. "
                "Escreva em Português (Brasil) com humor mordaz, alta imersão, sem alucinar pontos e cobrindo as 10 equipes."
            ),
            temperature=0.45,
        ).strip()
    except Exception as exc:
        episode_md = f"### 📝 {day_label}: {day_theme_focus}\n\nBastidores das 10 equipes em ritmo de preparação para {meta_curr['name']}.\n"

    # Section-based storage (Deduplication engine)
    existing_days: Dict[int, str] = {}
    if target_file.exists():
        raw_existing = target_file.read_text(encoding="utf-8")
        day_splits = re.split(r"(## 📅 DIA \d/4:[^\n]*)", raw_existing)
        if len(day_splits) > 1:
            for i in range(1, len(day_splits), 2):
                hdr = day_splits[i]
                body = day_splits[i + 1] if i + 1 < len(day_splits) else ""
                match_d = re.search(r"DIA (\d)/4", hdr)
                if match_d:
                    existing_days[int(match_d.group(1))] = body.strip().lstrip("-").strip()

    # Overwrite current day with fresh generation
    existing_days[day_num] = episode_md.strip()

    # Reconstruct whole file cleanly with no duplicates
    doc_header = (
        f"# 🏁 A F1 QUE VOCÊ NÃO VÊ — A Semana da F1 (Etapa {round_num}: {meta_curr['name']})\n"
        f"## 💣 ESPECIAL SILLY SEASON PRÉ-{round_folder.upper()}\n\n"
    )
    sections = []
    for d_idx in sorted(existing_days.keys()):
        d_lbl, _ = day_names.get(d_idx, (f"DIA {d_idx}", ""))
        sections.append(f"## 📅 DIA {d_idx}/4: {d_lbl}\n\n{existing_days[d_idx]}")

    full_md = doc_header + "\n\n---\n\n".join(sections) + "\n"
    target_file.write_text(full_md, encoding="utf-8")

    clean_snippet = re.sub(r"[#*`]", "", episode_md)[:180].strip()
    teaser_summary = (
        f"🚨 **[M1 · DIA {day_num}/4] A SEMANA DA F1: {day_label}**\n"
        f"• **Foco:** *{day_theme_focus}*\n"
        f"> *\"{clean_snippet}...\"*"
    )
    # If day 4 is reached (Thursday), synthesize and record canon event
    if day_num == 4:
        try:
            extract_and_record_m1_canon_event(root_dir, round_num, round_folder, full_md, ai_client)
        except Exception as exc:
            print(f"[Canon Event Warning] Falha ao sintetizar evento M1 (Dia 4): {exc}")

    return target_file, teaser_summary


def extract_and_record_m1_canon_event(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    m1_content: str,
    ai_client: GeminiFreeTierClient,
) -> Dict[str, Any]:
    """
    Synthesizes the key political/contractual events from M1 and registers
    an official Canon Ledger event with status 'OPEN'.
    """
    from src.canon_ledger import CanonLedgerManager

    prompt = (
        f"Analise o dossiê da semana pré-corrida da F1 (Módulo 1) abaixo para a Etapa {round_num} ({round_folder}):\n\n"
        f"{m1_content[:15000]}\n\n"
        f"TAREFA:\n"
        f"Identifique os 3 a 5 fatos políticos, contratuais, atritos de garagem ou vazamentos mais impactantes da semana "
        f"que devem virar memória canônica permanente para os próximos GPs (ex: blindagens contratuais, sondagens rivais, ultimatos de chefia).\n"
        f"Resuma em um único parágrafo conciso (250 a 450 caracteres) com tom analítico e jornalístico.\n"
        f"Na última linha, forneça 'ENTIDADES: ' seguido das entidades separadas por vírgula (ex: sarah, felipe, davi, verstappen, audi, red_bull, mercedes)."
    )

    try:
        raw_res = ai_client._call_generate_content(
            model=ai_client.flash_model,
            parts=[{"text": prompt}],
            system_instruction="Você é o arquivista e curador histórico da FIA e do Paddock de 2026.",
            temperature=0.3,
        ).strip()
    except Exception as exc:
        raw_res = f"Semana pré-{round_folder} fervendo com movimentações contratuais e especulações técnicas de bastidores."

    # Parse summary and entities
    lines = [l.strip() for l in raw_res.splitlines() if l.strip()]
    summary_parts = []
    entities = ["f1", round_folder]
    for line in lines:
        if line.upper().startswith("ENTIDADES:"):
            clean_line = re.sub(r"(?i)^entidades?:\s*", "", line).strip()
            found = [w.strip().lower() for w in re.split(r"[,;]", clean_line) if w.strip()]
            if found:
                entities = found
        else:
            summary_parts.append(line)

    summary = " ".join(summary_parts).strip()
    if not summary:
        summary = raw_res

    # Auto-tag Brazilian Storm and major key players if mentioned
    for d in ("sarah", "felipe", "davi", "verstappen", "hamilton", "alonso", "sauber", "mercedes", "williams", "red_bull", "audi"):
        if d in summary.lower() and d not in entities:
            entities.append(d)

    event_id = f"ET{round_num:02d}-ES-M1" if round_num == 10 else f"ET{round_num:02d}-M1-WEEK"
    mgr = CanonLedgerManager()
    mgr.append_event(
        event_id=event_id,
        round_num=round_num,
        module="M1_SEMANA_EQUIPES",
        summary=summary,
        entities=entities,
        status="OPEN",
    )
    return {
        "event_id": event_id,
        "round_num": round_num,
        "module": "M1_SEMANA_EQUIPES",
        "summary": summary,
        "entities": entities,
        "status": "OPEN",
    }


# ==============================================================================
# SUBMÓDULO M1.5: DILEMA INTERATIVO DE PADDOCK (INTERACTIVE STORYTELLING)
# ==============================================================================

DRIVER_SETUP_MAP: Dict[str, Tuple[str, str, str, str, str]] = {
    "felipe": ("Felipe", "frdsilva83", "Carro #5 · Stake F1 Team Kick Sauber (Audi)", "sauber", "Stake F1 Team Kick Sauber (Audi)"),
    "davi": ("Davi", "DaviMSSon", "Carro #15 · Williams Racing", "williams", "Williams Racing"),
    "sarah": ("Sarah", "SarahMarinsS", "Carro #24 · Mercedes-AMG Petronas", "mercedes", "Mercedes-AMG Petronas"),
}


@trace_span("generate_paddock_dilemma")
def generate_paddock_dilemma(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    target_driver: Optional[str] = None,
    ai_client: Optional[GeminiFreeTierClient] = None,
    season_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates a high-stakes, polarized paddock dilemma (M1.5) for a human driver,
    grounded on Wednesday's theme and psychological profile, pausing in TURN_LOCKED.
    """
    from src.canon_ledger import sample_weekly_themes

    client = ai_client or GeminiFreeTierClient()
    round_dir = get_season_dir(root_dir, season_id) / round_folder
    round_dir.mkdir(parents=True, exist_ok=True)
    state_file = root_dir / "data" / "state" / f"dilemma_et{round_num:02d}.json"

    # Select target driver deterministically if not specified: rotate Felipe, Davi, Sarah
    available_drivers = ["felipe", "davi", "sarah"]
    driver_id = target_driver.lower() if target_driver and target_driver.lower() in DRIVER_SETUP_MAP else available_drivers[(round_num - 1) % len(available_drivers)]
    driver_name, discord_tag, car_desc, team_id, team_name = DRIVER_SETUP_MAP[driver_id]

    meta = ROUND_METADATA.get(round_folder, {"name": f"GP da Etapa {round_num}"})
    gp_name = meta.get("name", f"Etapa {round_num}")

    # Sample theme for Wednesday
    themes = sample_weekly_themes(round_num, team_id)
    wed_theme = themes.get("wednesday", "Crise Contratual & Mercado de Pilotos")

    # Load context & prompt template
    prompt_file = root_dir / "prompts" / "01b_dilema_paddock.md"
    prompt_template = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
    base_context = assemble_storytelling_context(root_dir, round_num, round_folder)[:12000]

    # Driver profile context
    profile_path = root_dir / "data" / "setup" / f"Setup - Perfil {driver_name}.md"
    profile_text = profile_path.read_text(encoding="utf-8")[:1500] if profile_path.exists() else ""

    prompt = (
        f"{base_context}\n\n"
        f"=== PERFIL DO PILOTO ===\n{profile_text}\n\n"
        f"=== DIRETRIZ DO DILEMA ===\n{prompt_template}\n\n"
        f"Gere agora o dilema de paddock polarizado para {driver_name} ({team_name}), "
        f"centrado no tema obrigatório: '{wed_theme}', para a Etapa {round_num} ({gp_name})."
    )

    try:
        dilemma_md = client._call_generate_content(
            model=client.flash_model,
            parts=[{"text": prompt}],
            system_instruction=(
                "Você é o Game Master de RPG esportivo e Diretor Narrativo da F1 2026. "
                "Crie escolhas dramáticas polarizadas com alto custo e ganho real."
            ),
            temperature=0.5,
        ).strip()
    except Exception as exc:
        dilemma_md = (
            f"# ⚡ DILEMA DE PADDOCK — {gp_name.upper()} (MÓDULO #1.5)\n"
            f"### 🛑 DECISÃO ESTRATÉGICA CONVOCADA: @{discord_tag} ({driver_name} · {team_name})\n\n"
            f"**Cenário de Bastidor:**\n"
            f"Nos bastidores desta quarta-feira, a cúpula técnica apresentou uma proposta crítica em torno de {wed_theme}.\n\n"
            f"### ⚖️ SUAS OPÇÕES DE DECISÃO:\n"
            f"* **[OPÇÃO A] — Rota Agressiva:** Assumir o pacote experimental com risco de confiabilidade.\n"
            f"* **[OPÇÃO B] — Rota Conservadora:** Manter a especificação padrão e focar em pontos seguros.\n\n"
            f"🛑 **[TRAVA DE TURNO ATIVA | Aguardando resposta de @{discord_tag}]**\n"
            f"> 💬 *Piloto, digite 'Opção A' ou 'Opção B' no chat do canal de voz para registrar a decisão no Canon Oficial!*"
        )

    # Save Markdown file
    target_md = round_dir / f"Etapa {round_num:02d} - Relatório de Bastidores - M1.5 Dilema de Paddock - {gp_name} 2026.md"
    target_md.write_text(dilemma_md + "\n", encoding="utf-8")

    state_data = {
        "round_num": round_num,
        "round_folder": round_folder,
        "target_driver": driver_id,
        "driver_name": driver_name,
        "discord_tag": discord_tag,
        "status": "AWAITING_DILEMMA_CHOICE",
        "dilemma_text": dilemma_md,
        "timestamp": time.time(),
        "completed": False,
        "chosen_option": None,
        "resolution_text": None,
    }
    state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return state_data


@trace_span("resolve_paddock_dilemma")
def resolve_paddock_dilemma(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    raw_choice: str,
    ai_client: Optional[GeminiFreeTierClient] = None,
    season_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Receives player's choice from Discord, incorporates into Canon Ledger and generates
    context-aware paddock consequence, unlocking the weekly state machine.
    """
    from src.canon_ledger import CanonLedgerManager

    client = ai_client or GeminiFreeTierClient()
    state_file = root_dir / "data" / "state" / f"dilemma_et{round_num:02d}.json"
    if not state_file.exists():
        raise FileNotFoundError(f"Dilema da Etapa {round_num} não encontrado em {state_file}")

    st = json.loads(state_file.read_text(encoding="utf-8"))
    driver_id = st.get("target_driver", "felipe")
    driver_name = st.get("driver_name", "Felipe")
    discord_tag = st.get("discord_tag", "piloto")
    clean_choice = raw_choice.strip()

    prompt = (
        f"DILEMA DE PADDOCK APRESENTADO (Etapa {round_num}):\n"
        f"{st.get('dilemma_text', '')[:3000]}\n\n"
        f"ESCOLHA FEITA PELO PILOTO {driver_name.upper()} (@{discord_tag}):\n"
        f"\"{clean_choice}\"\n\n"
        f"TAREFA:\n"
        f"1. Como Game Master e narrador de F1, gere em 2 parágrafos curtos a reação imediata nos bastidores da equipe e o impacto político/técnico da escolha feita pelo piloto.\n"
        f"2. Escreva em tom realista, tenso e cinematográfico.\n"
        f"3. Finalize com um resumo executivo de 1 linha da consequência para o Canon Ledger."
    )

    try:
        consequence_text = client._call_generate_content(
            model=client.flash_model,
            parts=[{"text": prompt}],
            system_instruction="Você é o Game Master esportivo de F1 2026.",
            temperature=0.45,
        ).strip()
    except Exception as exc:
        consequence_text = (
            f"A decisão de {driver_name} foi comunicada à chefia de equipe, gerando debates intensos entre os engenheiros. "
            f"A escolha sela o direcionamento estratégico para o restante do Grande Prêmio."
        )

    # Register in Canon Ledger
    ledger_path = root_dir / "data" / "state" / "canon_ledger.json"
    mgr = CanonLedgerManager(ledger_path)
    mgr.append_event(
        event_id=f"ET{round_num:02d}-M1.5-DILEMMA",
        round_num=round_num,
        module="M1_5_DILEMA",
        summary=f"No Dilema de Paddock da Etapa {round_num}, {driver_name} decidiu: '{clean_choice[:140]}'. Consequência: {consequence_text[:200]}",
        entities=[driver_id, "fia", "equipe", round_folder],
        status="OPEN",
    )

    st["status"] = "COMPLETED"
    st["completed"] = True
    st["chosen_option"] = clean_choice
    st["resolution_text"] = consequence_text
    st["resolved_timestamp"] = time.time()
    state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Append consequence to target markdown
    round_dir = get_season_dir(root_dir, season_id) / round_folder
    meta = ROUND_METADATA.get(round_folder, {"name": f"GP da Etapa {round_num}"})
    gp_name = meta.get("name", f"Etapa {round_num}")
    target_md = round_dir / f"Etapa {round_num:02d} - Relatório de Bastidores - M1.5 Dilema de Paddock - {gp_name} 2026.md"
    if target_md.exists():
        append_res = (
            f"\n\n---\n\n"
            f"### ✅ DECISÃO REGISTRADA NO CANON OFICIAL\n"
            f"**Escolha do Piloto @{discord_tag} ({driver_name}):**\n> *\"{clean_choice}\"*\n\n"
            f"**Repercussão Imediata nos Bastidores:**\n{consequence_text}\n"
        )
        target_md.write_text(target_md.read_text(encoding="utf-8") + append_res, encoding="utf-8")

    ack_message = (
        f"✅ **DECISÃO DE {driver_name.upper()} REGISTRADA NO CANON LEDGER DA F1 2026!**\n"
        f"> *\"{clean_choice}\"*\n\n"
        f"📋 **Repercussão nos Bastidores:**\n{consequence_text}\n\n"
        f"🔓 **Trava de Turno Liberada!** A semana da F1 avança rumo à Coletiva de Imprensa Oficial da FIA (M2)!"
    )
    return {
        "status": "COMPLETED",
        "driver_id": driver_id,
        "driver_name": driver_name,
        "choice": clean_choice,
        "consequence": consequence_text,
        "ack_message": ack_message,
    }





