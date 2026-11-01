"""
FIA Thursday Press Conference Interactive Engine (Módulo #2 · Coletiva Pré-GP).
Features:
  - Interactive Turn-Lock (Trava de Turno) in Discord for Human Drivers (Felipe, Davi, Sarah).
  - Grounded in M1 Silly Season leaks, Canon Ledger, and FIA Standings.
  - Generates realistic questions from accredited media (Mariana Becker, Erik van Haren, Martin Brundle, etc.).
  - Simulates instant answers for NPCs (Verstappen, Alonso, Hamilton, Leclerc) and pauses for humans.
  - Injects human driver responses directly into Canon Ledger and compiles the final official FIA report.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ai_showrunner import GeminiFreeTierClient, assemble_storytelling_context
from src.canon_ledger import CanonLedgerManager, select_press_conference_panel
from src.logger import info, warning, error
from src.orchestrator_cli import ROUND_METADATA, deploy_portal_to_github_pages

DRIVER_MENTIONS = {
    "felipe": ("Felipe", "frdsilva83", "Carro #5 · Kick Sauber"),
    "davi": ("Davi", "DaviMSSon", "Carro #15 · Williams"),
    "sarah": ("Sarah", "SarahMarinsS", "Carro #24 · Mercedes-AMG"),
}

JOURNALISTS = [
    ("Mariana Becker", "Band / Grupo Bandeirantes (Brasil)", "Curiosa, elegante, focada no lado humano e bastidores de paddock."),
    ("Erik van Haren", "De Telegraaf (Holanda)", "Incisivo, direto, agressivo, muito ligado ao clã Verstappen e Red Bull."),
    ("Martin Brundle", "Sky Sports F1 (Reino Unido)", "Cirúrgico, analítico, ex-piloto, focado em disputas roda a roda e regulamento."),
    ("Julianne Cerasoli", "UOL Esporte / Band (Brasil)", "Técnica, investigativa, conectada às reuniões políticas da FIA e contratos."),
    ("Roberto Chinchero", "Motorsport.com / Sky Sport (Itália)", "Passional, focado em estratégia, pneus e nas intrigas de Maranello e Hinwil."),
]


class PressConferenceSession:
    def __init__(
        self,
        root_dir: Path,
        round_num: int,
        round_folder: str,
        ai_client: Optional[GeminiFreeTierClient] = None,
    ):
        self.root_dir = root_dir
        self.round_num = round_num
        self.round_folder = round_folder
        self.round_dir = root_dir / "data" / "seasons" / "season_01" / round_folder
        self.state_file = root_dir / "data" / "state" / f"press_conf_et{round_num:02d}.json"
        self.meta = ROUND_METADATA.get(round_folder, {"name": f"GP Etapa {round_num}", "flag": "🏁"})
        ai_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.ai_client = ai_client or GeminiFreeTierClient(api_key=ai_key)
        self.state: Dict[str, Any] = self._load_or_init_state()

    def _load_or_init_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load standings to select panel
        st_path = self.root_dir / "data" / "state" / "standings.json"
        st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {"drivers_standings": []}
        panel = select_press_conference_panel(st, self.round_num)
        panel_names = [f"{d['name']} ({d['team_id'].upper()})" for d in panel]

        initial = {
            "round_num": self.round_num,
            "round_folder": self.round_folder,
            "status": "INITIALIZED",
            "panel": panel,
            "panel_summary": panel_names,
            "current_question_idx": 0,
            "total_questions": 5,
            "waiting_for_driver": None,
            "waiting_for_driver_name": None,
            "transcript_blocks": [],
            "completed": False,
        }
        self._save_state(initial)
        return initial

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.state = state

    def start_session(self) -> str:
        """Generates opening preamble by Tom Clarkson (FIA) and returns opening Discord text."""
        gp_name = self.meta["name"]
        panel_str = ", ".join(self.state.get("panel_summary", []))

        opening = (
            f"🏛️ **FEDERATION INTERNATIONALE DE L'AUTOMOBILE | COLETIVA OFICIAL PRÉ-GP**\n"
            f"🏁 **{self.meta['flag']} Etapa {self.round_num}: {gp_name}** | Sala de Imprensa Oficial\n\n"
            f"🎙️ **Moderador Tom Clarkson (FIA):** *\"Boa tarde a todos os jornalistas credenciados. "
            f"Damos início à coletiva oficial de quinta-feira aqui no circuito. Convocados para a bancada: "
            f"{panel_str}. Abriremos agora as perguntas da bancada.\"*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        self.state["status"] = "IN_PROGRESS"
        self.state["current_question_idx"] = 0
        self.state.setdefault("transcript_blocks", []).append(f"### Abertura Oficial FIA\n\n{opening}\n")
        self._save_state(self.state)
        return opening

    def advance_to_next_question(self) -> Tuple[str, bool, Optional[str]]:
        """
        Advances to the next question in the press conference.
        Returns: (message_text, is_turn_lock, waiting_driver_id)
        """
        idx = self.state["current_question_idx"] + 1
        total = self.state["total_questions"]

        if idx > total:
            return self._conclude_session()

        self.state["current_question_idx"] = idx

        # Determine target driver for this question
        # Plan: Q1 = NPC (Verstappen/Alonso), Q2 = Felipe, Q3 = Davi, Q4 = NPC, Q5 = Sarah
        question_targets = {
            1: "verstappen",
            2: "felipe",
            3: "davi",
            4: "alonso",
            5: "sarah",
        }
        target_id = question_targets.get(idx, "felipe")
        journo_name, journo_outlet, journo_desc = JOURNALISTS[(idx - 1) % len(JOURNALISTS)]

        # Context assembly from M1 and standings
        context = assemble_storytelling_context(self.root_dir, self.round_num, self.round_folder)[:12000]
        recent_blocks = "\n".join(self.state.get("transcript_blocks", [])[-2:])

        is_human = target_id in DRIVER_MENTIONS

        prompt = (
            f"{context}\n\n=== TRANSCRIÇÃO ATÉ O MOMENTO ===\n{recent_blocks}\n\n"
            f"=== TAREFA DA PERGUNTA {idx} DE {total} ===\n"
            f"Jornalista: {journo_name} ({journo_outlet}) — {journo_desc}\n"
            f"Piloto Alvo: {target_id.upper()}\n"
            f"Cenário: É a Pergunta {idx} de {total} da Coletiva Pré-GP da FIA.\n"
            f"O jornalista deve fazer uma pergunta ácida, instigante e realista baseada nos vazamentos do Módulo 1 (Silly Season da semana) "
            f"e no resultado da etapa anterior.\n"
        )

        if not is_human:
            prompt += (
                f"Como {target_id.upper()} é um NPC, gere a pergunta do jornalista e em seguida a resposta completa e autêntica de {target_id.upper()}, "
                f"mantendo a sua personalidade e desdém ou competitividade. "
                f"IMPORTANTE: Mantenha a pergunta e a resposta concisas e diretas (máximo de 1.200 caracteres no total) para dinamismo no Discord.\n"
                f"Formate como:\n"
                f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {target_id.capitalize()}]:** \"...\"\n\n"
                f"💬 **{target_id.capitalize()}:** \"...\"\n"
            )
            try:
                gen_text = self.ai_client._call_generate_content(
                    model=self.ai_client.flash_model,
                    parts=[{"text": prompt}],
                    system_instruction="Você é o moderador e narrador da Coletiva Oficial da FIA.",
                    temperature=0.4,
                ).strip()
            except Exception as exc:
                gen_text = (
                    f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {target_id.capitalize()}]:** "
                    f"\"Como você avalia as chances da equipe neste fim de semana após os problemas do último GP?\"\n\n"
                    f"💬 **{target_id.capitalize()}:** \"Estamos focados em nosso trabalho e confiantes no ritmo.\""
                )

            self.state.setdefault("transcript_blocks", []).append(gen_text)
            self._save_state(self.state)
            return (gen_text, False, None)

        else:
            # Human Pilot: Generate question and pause (Trava de Turno)
            driver_name, discord_tag, car_desc = DRIVER_MENTIONS[target_id]
            prompt += (
                f"Como {driver_name} é um PILOTO HUMANO, gere APENAS a pergunta provocativa de {journo_name} "
                f"e a reação corporal dos outros pilotos na bancada. NÃO responda pelo piloto! "
                f"Encerre estritamente com a chamada para o piloto responder.\n"
                f"Formate como:\n"
                f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {driver_name} ({car_desc})]:**\n"
                f"\"...\"\n\n"
                f"*Reação da Bancada:* ...\n"
            )
            try:
                gen_text = self.ai_client._call_generate_content(
                    model=self.ai_client.flash_model,
                    parts=[{"text": prompt}],
                    system_instruction="Você é o moderador e narrador da Coletiva Oficial da FIA.",
                    temperature=0.45,
                ).strip()
            except Exception as exc:
                gen_text = (
                    f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {driver_name} ({car_desc})]:**\n"
                    f"\"Os vazamentos desta semana apontam forte pressão sobre você. Como você responde a essas especulações?\"\n"
                )

            call_to_action = (
                f"\n\n🛑 **[TRAVA DE TURNO ATIVA | Microfone aberto para @{discord_tag} ({driver_name})]**\n"
                f"> 💬 *Digite sua resposta aqui no chat do canal de voz para que ela seja registrada oficialmente na ata da FIA!*"
            )
            full_msg = gen_text + call_to_action

            self.state["waiting_for_driver"] = target_id
            self.state["waiting_for_driver_name"] = driver_name
            self.state["pending_question_text"] = gen_text
            self.state["status"] = "AWAITING_PILOT_REPLY"
            self._save_state(self.state)
            return (full_msg, True, target_id)

    def submit_pilot_answer(self, driver_id: str, raw_answer: str) -> str:
        """
        Receives human pilot answer from Discord, incorporates into transcript and Canon Ledger,
        and generates immediate room reaction.
        """
        clean_answer = raw_answer.strip()
        driver_name, discord_tag, car_desc = DRIVER_MENTIONS.get(driver_id, (driver_id.capitalize(), driver_id, "Piloto"))
        idx = self.state.get("current_question_idx", 1)
        total = self.state.get("total_questions", 5)

        # 1. Register in Canon Ledger
        ledger_path = self.root_dir / "data" / "state" / "canon_ledger.json"
        mgr = CanonLedgerManager(ledger_path)
        mgr.append_event(
            event_id=f"ET{self.round_num:02d}-M2-Q{idx}",
            round_num=self.round_num,
            module="M2_COLETIVA",
            summary=f"Na Coletiva Oficial FIA da Etapa {self.round_num}, {driver_name} declarou à imprensa: '{clean_answer[:200]}'",
            entities=[driver_id, "fia"],
            status="OPEN",
        )

        # 2. Generate room reaction via Gemini
        q_text = self.state.get("pending_question_text", "")
        prompt = (
            f"Pergunta feita: {q_text}\n"
            f"Resposta de {driver_name}: \"{clean_answer}\"\n\n"
            f"Gere em 1 parágrafo curto (máximo 250 caracteres) a reação no recinto: como os jornalistas anotaram nos laptops, "
            f"o olhar dos chefes de equipe ou dos rivais na bancada (como Verstappen ou Hamilton), e o moderador Tom Clarkson chamando o próximo tópico."
        )
        try:
            reaction = self.ai_client._call_generate_content(
                model=self.ai_client.flash_model,
                parts=[{"text": prompt}],
                temperature=0.3,
            ).strip()
        except Exception:
            reaction = "Os jornalistas digitam furiosamente nos laptops enquanto o moderador Tom Clarkson agradece e reorganiza as anotações."

        qa_block = (
            f"{q_text}\n\n"
            f"💬 **{driver_name} (@{discord_tag}):** \"{clean_answer}\"\n\n"
            f"*{reaction}*\n"
        )
        self.state.setdefault("transcript_blocks", []).append(qa_block)
        self.state["waiting_for_driver"] = None
        self.state["waiting_for_driver_name"] = None
        self.state["pending_question_text"] = None
        self.state["status"] = "IN_PROGRESS"
        self._save_state(self.state)

        ack = (
            f"✅ **RESPOSTA DE {driver_name.upper()} REGISTRADA NA ATA DA FIA!**\n"
            f"> *\"{clean_answer}\"*\n\n"
            f"*{reaction}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return ack

    def _conclude_session(self) -> Tuple[str, bool, Optional[str]]:
        """Concludes the press conference, saves Markdown report, and triggers Portal deploy."""
        gp_name = self.meta["name"]
        filename = f"Etapa {self.round_num:02d} - Relatório Oficial FIA - Coletiva de Imprensa Pré-GP - {gp_name} 2026.md"
        target_md = self.round_dir / filename

        full_transcript = (
            f"# FEDERATION INTERNATIONALE DE L'AUTOMOBILE\n"
            f"## RELATÓRIO OFICIAL — COLETIVA DE IMPRENSA PRÉ-GP (MÓDULO #2)\n"
            f"**Grande Prêmio:** {gp_name} 2026 (Etapa {self.round_num})\n"
            f"**Local:** Sala de Imprensa do Circuito | Quinta-Feira Oficial\n\n"
            f"---\n\n"
            + "\n\n".join(self.state.get("transcript_blocks", []))
            + f"\n\n---\n*Ata lavrada pela Diretoria de Comunicação e Relações com a Imprensa da FIA.*"
        )
        target_md.write_text(full_transcript, encoding="utf-8")
        deploy_portal_to_github_pages(f"Publish M2 Press Conference {self.round_folder}")

        self.state["status"] = "COMPLETED"
        self.state["completed"] = True
        self._save_state(self.state)

        closing_msg = (
            f"🏛️ **COLETIVA DE IMPRENSA OFICIAL DA FIA ENCERRADA!**\n"
            f"• Ata e crônica completa compiladas em `{filename}`.\n"
            f"• As respostas de Sarah, Felipe e Davi foram incorporadas ao Canon Oficial de 2026.\n"
            f"👉 O fim de semana de corrida está aberto! Quando prontos, digitem **`inicio da etapa {self.round_num}`** no canal de voz!"
        )
        return (closing_msg, False, None)

