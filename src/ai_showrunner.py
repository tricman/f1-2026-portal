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
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.canon_ledger import CanonLedgerManager, sample_weekly_themes
from src.portal_builder import ROUND_METADATA

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
FALLBACK_FLASH_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
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
        flash_model: str = "gemini-3.8-flash",
        pro_model: str = "gemini-3.1-pro-preview",
        pacing_seconds: float = 32.0,
    ) -> None:
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.pacing_seconds = pacing_seconds
        self._last_pro_call_ts: float = 0.0

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

        models_to_try = [model] + [m for m in FALLBACK_FLASH_MODELS if m != model]
        total_attempts = max(max_retries, len(models_to_try) + 2)

        for attempt in range(total_attempts):
            active_model = models_to_try[min(attempt, len(models_to_try) - 1)]
            active_url = f"{GEMINI_API_BASE}/{active_model}:generateContent?key={self.api_key}"
            req = urllib.request.Request(active_url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    if active_model == self.pro_model:
                        self._last_pro_call_ts = time.time()
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Resposta vazia do Gemini ({active_model}): {data}")
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text", "") for p in content_parts)
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                if exc.code in (429, 500, 502, 503, 504) and attempt < total_attempts - 1:
                    next_model = models_to_try[min(attempt + 1, len(models_to_try) - 1)]
                    wait_time = 8.0 * (attempt + 1) if exc.code != 429 else 20.0 * (attempt + 1)
                    print(
                        f"[Gemini HTTP {exc.code} em {active_model}] Tentativa {attempt + 1}/{total_attempts}: "
                        f"alternando para {next_model} após {wait_time:.0f}s..."
                    )
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Gemini API HTTP {exc.code} ({active_model}): {err_body}") from exc

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
        seasons_dir = root_dir / "data" / "seasons" / "season_01"
        prev_folders = [d for d in seasons_dir.glob(f"et_{prev_num:02d}_*") if d.is_dir()]
        if prev_folders:
            prev_dir = prev_folders[0]
            for md_file in sorted(prev_dir.glob("*.md")):
                if any(k in md_file.name.lower() for k in ("resultado final", "cerimônia", "repercussão")):
                    text = md_file.read_text(encoding="utf-8")
                    sections.append(f"=== MEMÓRIA DA ETAPA ANTERIOR ({prev_dir.name} / {md_file.name}) ===\n{text[:6000]}")

    # Layer 3B: Current Round Driver Debriefing Notes
    debrief_file = root_dir / "data" / "seasons" / "season_01" / round_folder / "debriefing" / "debriefing_notes.md"
    if debrief_file.exists():
        sections.append(
            f"=== RELATOS DE DEBRIEFING DOS PILOTOS (ETAPA {round_num}) ===\n{debrief_file.read_text(encoding='utf-8')}"
        )

    return "\n\n".join(sections)


def finalize_round_transition(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    ai_client: Optional[GeminiFreeTierClient] = None,
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

    round_dir = root_dir / "data" / "seasons" / "season_01" / round_folder
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


def generate_post_race_modules(
    root_dir: Path,
    round_num: int,
    round_folder: str,
    ai_client: GeminiFreeTierClient,
) -> List[Path]:
    """
    Generate M3 (Treino Livre), M4 (Classificação), M5 (Resultado Final),
    M6 (Cerimônia do Pódio), M7 (Atualização Classificação) and M8 (Repercussão Imprensa)
    automatically via Gemini if they do not exist yet in the round folder.
    """
    round_dir = root_dir / "data" / "seasons" / "season_01" / round_folder
    round_dir.mkdir(parents=True, exist_ok=True)
    tel_dir = round_dir / "telemetry"
    meta = ROUND_METADATA.get(round_folder, {"name": f"GP Etapa {round_num}", "circuit": "", "flag": "🏁"})
    gp_title = f"{meta['name']} 2026"

    base_context = assemble_storytelling_context(root_dir, round_num, round_folder)
    fp_json = (tel_dir / "fp_telemetry_merged.json").read_text(encoding="utf-8") if (tel_dir / "fp_telemetry_merged.json").exists() else "{}"
    race_json = (tel_dir / "race_telemetry_merged.json").read_text(encoding="utf-8") if (tel_dir / "race_telemetry_merged.json").exists() else "{}"
    tv_json_path = tel_dir / f"tv_overlay_et{round_num:02d}.json"
    tv_json = tv_json_path.read_text(encoding="utf-8") if tv_json_path.exists() else "{}"

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
            f"Gere o Relatório Oficial FIA do Resultado Final da Corrida (M5) da Etapa {round_num} ({gp_title}) em Markdown GFM completo com tabela oficial dos 20 pilotos, pit stops, pneus, decisões dos comissários e crônica pós-corrida incluindo os relatos de debriefing.\nDADOS CORRIDA PACEDEX + FIA:\n{race_json}",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Cerimônia do Pódio e Bastidores - {gp_title}.md",
            "06_cerimonia_podio.md",
            f"Gere o módulo Pós-Corrida: Cerimônia do Pódio, Sala de Resfriamento (Cooldown Room) e Bastidores dos Motorhomes (M6) da Etapa {round_num} ({gp_title}) em 4 Atos.\nDADOS CORRIDA:\n{race_json}",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Relatório FIA - Atualização Classificação Pilotos e Construtores.md",
            "07_fia_mundial.md",
            f"Gere o Boletim Oficial FIA de Atualização do Mundial de Pilotos e Construtores (M7) pós-Etapa {round_num} ({gp_title}). PROIBIDO somar pontos manualmente: use estritamente os números da TABELA OFICIAL DO CAMPEONATO FIA no contexto.",
        ),
        (
            f"Etapa {round_num:02d} - Pós - Repercussão Imprensa e Internet - {gp_title}.md",
            "08_repercussao_midia.md",
            f"Gere o módulo de Repercussão na Imprensa Internacional, Brasileira, Podcasts e Redes Sociais (M8) pós-Etapa {round_num} ({gp_title}) repercutindo o resultado e os bastidores da corrida.",
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

        full_prompt = (
            f"{base_context}\n\n"
            + ("\n\n".join(chained_outputs[-2:]) if chained_outputs else "")
            + f"\n\n=== DIRETRIZ DO MÓDULO ({prompt_file}) ===\n{prompt_template}\n\n"
            + f"=== TAREFA DE GERAÇÃO ===\n{task_instructions}"
        )
        print(f"[AI Showrunner] Gerando módulo: {filename}...")
        md_content = ai_client._call_generate_content(
            model=ai_client.flash_model,
            parts=[{"text": full_prompt}],
            system_instruction=(
                "Você é o Showrunner Oficial e Diretor Técnico da FIA para a temporada 2026 de EA Sports F1 24. "
                "Escreva em Português (Brasil) rico, imersivo e 100% fiel aos dados matemáticos fornecidos. "
                "Nos relatórios da FIA (M3, M4, M5 e M7), inclua SEMPRE tabelas Markdown completas (| Pos. | Piloto | Equipe | ... |)."
            ),
            temperature=0.45,
        ).strip()
        target_md.write_text(md_content + "\n", encoding="utf-8")
        generated.append(target_md)
        chained_outputs.append(f"=== MÓDULO GERADO ({filename}) ===\n{md_content[:4000]}")
        time.sleep(4.0)

    return generated


