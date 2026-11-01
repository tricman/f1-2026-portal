"""
FIA Thursday Press Conference Interactive Engine (Módulo #2 · Coletiva Pré-GP).
Features:
  - Interactive Turn-Lock (Trava de Turno) in Discord for Human Drivers (Felipe, Davi, Sarah).
  - Grounded in M1 Silly Season leaks, Canon Ledger, and FIA Standings.
  - Dynamic International Press Pool (17 accredited journalists across 8 countries).
  - Shuffled question sequence and themed topic sampling per round.
  - Context-aware, human, non-cliché room reactions based on Canon Ledger relationships.
  - Simulates instant answers for NPCs and pauses for human drivers.
  - Injects human driver responses directly into Canon Ledger, compiles the final official FIA report,
    and publishes automated media dispatches to `#repercussao-midia` and Portal.
"""
from __future__ import annotations

import json
import os
import random
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

JOURNALISTS_CATALOG = [
    # Brasil
    {"name": "Mariana Becker", "outlet": "Band / Grupo Bandeirantes (Brasil)", "desc": "Curiosa, elegante, focada no lado humano, bastidores e psicologia dos pilotos."},
    {"name": "Julianne Cerasoli", "outlet": "UOL Esporte / Band (Brasil)", "desc": "Técnica, investigativa, muito conectada às reuniões políticas da FIA e contratos."},
    {"name": "Reginaldo Leme", "outlet": "Band (Brasil)", "desc": "Histórico, analítico, busca comparações com grandes lendas e regulamentos do passado."},
    # Reino Unido
    {"name": "Martin Brundle", "outlet": "Sky Sports F1 (Reino Unido)", "desc": "Cirúrgico, analítico, ex-piloto, focado em disputas roda a roda e dinâmica de chassi."},
    {"name": "Ted Kravitz", "outlet": "Sky Sports F1 'The Notebook' (Reino Unido)", "desc": "Obsessivo por detalhes técnicos, asas, assoalhos e teorias de conspiração de paddock."},
    {"name": "Andrew Benson", "outlet": "BBC Sport (Reino Unido)", "desc": "Político, incisivo sobre governança da FIA, acordos comerciais e bastidores de diretoria."},
    {"name": "Will Buxton", "outlet": "F1 TV / Formula 1 Official (Global)", "desc": "Dramático, focado em narrativas épicas, linguagem corporal e pressão pelo título."},
    # Itália
    {"name": "Roberto Chinchero", "outlet": "Motorsport.com / Sky Sport (Itália)", "desc": "Passional, focado em estratégia, pneus e nas intrigas de Maranello e Hinwil."},
    {"name": "Mara Sangiorgio", "outlet": "Sky Sport F1 (Itália)", "desc": "Direta, rápida, focada no clima interno e tensões de garagem das equipes de fábrica."},
    # Holanda
    {"name": "Erik van Haren", "outlet": "De Telegraaf (Holanda)", "desc": "Agressivo, leal ao clã Verstappen, sempre cutuca rivais e expõe atritos internos."},
    {"name": "Jack Plooij", "outlet": "Ziggo Sport (Holanda)", "desc": "Provocativo e irreverente, busca desestabilizar pilotos com perguntas inusitadas."},
    # Espanha
    {"name": "Antonio Lobato", "outlet": "DAZN F1 (Espanha)", "desc": "Eufórico, patriótico, acompanha cada suspiro de Alonso, Sainz e a torcida espanhola."},
    {"name": "Cristóbal Rosaleny", "outlet": "SoyMotor (Espanha)", "desc": "Técnico em aerodinâmica, telemetria de classificação e histórico de pistas europeias."},
    # Alemanha
    {"name": "Michael Schmidt", "outlet": "Auto Motor und Sport (Alemanha)", "desc": "Maior autoridade técnica do paddock, números exatos de downforce, motor e CFD."},
    # França
    {"name": "Julien Fébreau", "outlet": "Canal+ (França)", "desc": "Intenso, perspicaz, focado em disputas internas de equipe e na geopolítica de Enstone."},
    # América Latina / México
    {"name": "Diego Mejía", "outlet": "Fox Sports México / América Latina", "desc": "Atento às disputas do pelotão intermediário e pressão sobre pilotos latino-americanos."},
    # Japão
    {"name": "Ken Tanaka", "outlet": "Autosport Japan", "desc": "Respeitoso, detalhista, focado na transição de motores e gestão térmica de pneus."},
]

PRESS_THEMES = [
    "Silly Season, cláusulas contratuais de 2027 e sondagens rivais",
    "Atritos de garagem, convivência com companheiro de equipe e preferência de desenvolvimento",
    "Evolução aerodinâmica, eficiência de assoalho e saltos de ritmo de rivais",
    "Gestão térmica de pneus, janelas de operação e ritmo de corrida vs volta única",
    "Polêmicas de regulamento, critérios dos comissários da FIA e disputas roda a roda",
    "Pressão psicológica pelo topo, expectativa de pódio e maturidade de pilotagem",
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

    def _generate_conference_plan(self, panel: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Dynamically plan 5 questions exclusively from the drivers summoned to the panel.
        No driver is artificially forced. Human drivers participate ONLY if summoned to the panel!
        """
        rng = random.Random(f"press_conf_plan_season2026_r{self.round_num}")
        panel_driver_ids = [d["id"] for d in panel]
        if not panel_driver_ids:
            panel_driver_ids = ["verstappen", "sarah", "felipe", "hamilton", "alonso"]

        # Shuffle the panel order for the 5 questions
        shuffled_drivers = list(panel_driver_ids)
        rng.shuffle(shuffled_drivers)

        driver_sequence = []
        for i in range(5):
            driver_sequence.append(shuffled_drivers[i % len(shuffled_drivers)])
        rng.shuffle(driver_sequence)

        # Sample 5 distinct journalists and themes
        shuffled_journos = rng.sample(JOURNALISTS_CATALOG, k=5)
        shuffled_themes = rng.sample(PRESS_THEMES, k=5)

        plan = []
        for i in range(5):
            plan.append({
                "idx": i + 1,
                "driver_id": driver_sequence[i],
                "journalist": shuffled_journos[i],
                "theme": shuffled_themes[i],
            })
        return plan

    def _load_or_init_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load standings and Canon Ledger to select panel dynamically
        st_path = self.root_dir / "data" / "state" / "standings.json"
        st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {"drivers_standings": []}

        ledger_path = self.root_dir / "data" / "state" / "canon_ledger.json"
        ledger_data = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}

        panel = select_press_conference_panel(st, self.round_num, canon_ledger=ledger_data)
        panel_names = [f"{d['name']} ({d['team_id'].upper()})" for d in panel]

        question_plan = self._generate_conference_plan(panel)

        initial = {
            "round_num": self.round_num,
            "round_folder": self.round_folder,
            "status": "INITIALIZED",
            "panel": panel,
            "panel_summary": panel_names,
            "question_plan": question_plan,
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

        # Determine target driver and journalist from dynamic plan or fallback
        plan = self.state.get("question_plan", [])
        if plan and len(plan) >= idx:
            item = plan[idx - 1]
            target_id = item["driver_id"]
            journo = item["journalist"]
            journo_name = journo["name"]
            journo_outlet = journo["outlet"]
            journo_desc = journo["desc"]
            theme_hint = item.get("theme", "Silly Season e bastidores da F1")
        else:
            # Fallback
            default_targets = {1: "verstappen", 2: "felipe", 3: "davi", 4: "alonso", 5: "sarah"}
            target_id = default_targets.get(idx, "felipe")
            journo = JOURNALISTS_CATALOG[(idx - 1) % len(JOURNALISTS_CATALOG)]
            journo_name, journo_outlet, journo_desc = journo["name"], journo["outlet"], journo["desc"]
            theme_hint = "Silly Season e bastidores da F1"

        # Context assembly from M1, Canon Ledger, and standings
        context = assemble_storytelling_context(self.root_dir, self.round_num, self.round_folder)[:12000]
        recent_blocks = "\n".join(self.state.get("transcript_blocks", [])[-2:])

        is_human = target_id in DRIVER_MENTIONS

        prompt = (
            f"{context}\n\n=== TRANSCRIÇÃO ATÉ O MOMENTO ===\n{recent_blocks}\n\n"
            f"=== TAREFA DA PERGUNTA {idx} DE {total} ===\n"
            f"Jornalista: {journo_name} ({journo_outlet}) — Estilo: {journo_desc}\n"
            f"Piloto Alvo: {target_id.upper()}\n"
            f"Eixo Temático Obrigatório: {theme_hint}\n"
            f"Cenário: Pergunta {idx} de {total} da Coletiva Pré-GP da FIA.\n"
            f"O jornalista deve formular uma pergunta ácida, instigante, realista e bem fundamentada nos fatos do M1 e no último GP.\n"
        )

        if not is_human:
            prompt += (
                f"Como {target_id.upper()} é um NPC, gere a pergunta do jornalista, a resposta completa de {target_id.upper()} "
                f"e a reação corporal imediata no recinto ou bancada.\n"
                f"IMPORTANTE: Pergunta, resposta e reação concisas (máximo de 1.100 caracteres no total) para dinamismo no Discord.\n"
                f"Formate como:\n"
                f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {target_id.capitalize()}]:** \"...\"\n\n"
                f"💬 **{target_id.capitalize()}:** \"...\"\n\n"
                f"*Reação do Recinto:* ...\n"
            )
            try:
                gen_text = self.ai_client._call_generate_content(
                    model=self.ai_client.flash_model,
                    parts=[{"text": prompt}],
                    system_instruction="Você é o moderador e narrador da Coletiva Oficial da FIA.",
                    temperature=0.5,
                ).strip()
            except Exception:
                gen_text = (
                    f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {target_id.capitalize()}]:** "
                    f"\"Como você avalia as chances da equipe neste fim de semana após as especulações de bastidor?\"\n\n"
                    f"💬 **{target_id.capitalize()}:** \"Estamos focados em nosso trabalho e confiantes no ritmo do carro.\"\n\n"
                    f"*Reação do Recinto:* Os comissários e repórteres registram as declarações em silêncio concentrado."
                )

            # Persist NPC answer & reaction into Canon Ledger
            try:
                ledger_path = self.root_dir / "data" / "state" / "canon_ledger.json"
                mgr = CanonLedgerManager(ledger_path)
                
                resp_match = re.search(r"💬\s*\*\*?[^:]+\*\*?:\s*["']?([^"'\n]+(?:["']?[^\n]+)?)", gen_text)
                clean_npc_ans = resp_match.group(1).strip() if resp_match else "Declaração aos repórteres da FIA."
                
                react_match = re.search(r"\*([^*]+)\*\s*$", gen_text.strip())
                npc_react = react_match.group(1).strip() if react_match else "A sala de imprensa acompanha em silêncio atento."
                
                entities = [target_id, "fia", "imprensa"]
                for d in ("sarah", "felipe", "davi", "verstappen", "hamilton", "alonso", "leclerc", "norris", "perez", "sainz", "audi", "red_bull", "mercedes", "ferrari", "aston_martin", "williams", "sauber", "vcarb"):
                    if d in gen_text.lower() and d not in entities:
                        entities.append(d)
                
                mgr.append_event(
                    event_id=f"ET{self.round_num:02d}-M2-Q{idx}",
                    round_num=self.round_num,
                    module="M2_COLETIVA",
                    summary=f"Na Coletiva Oficial FIA da Etapa {self.round_num}, {target_id.capitalize()} respondeu a {journo_name} ({journo_outlet}): '{clean_npc_ans[:200]}'. Reação no recinto: {npc_react[:180]}",
                    entities=entities,
                    status="OPEN",
                )
            except Exception as e_reg:
                warning(f"[PRESS CONF CANON REGISTRATION ERROR] Falha ao registrar NPC no Canon Ledger: {e_reg}")

            self.state.setdefault("transcript_blocks", []).append(gen_text)
            self._save_state(self.state)
            return (gen_text, False, None)

        else:
            # Human Pilot: Generate question and pause (Trava de Turno)
            driver_name, discord_tag, car_desc = DRIVER_MENTIONS[target_id]
            prompt += (
                f"Como {driver_name} é um PILOTO HUMANO, gere APENAS a pergunta provocativa de {journo_name} "
                f"e a reação corporal inicial da sala ou bancada. NÃO responda pelo piloto humano!\n"
                f"IMPORTANTE: NUNCA use clichês batidos como 'digitam freneticamente nos laptops', 'sorriso de canto de boca' ou 'fita o horizonte'.\n"
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
                    temperature=0.55,
                ).strip()
            except Exception:
                gen_text = (
                    f"🎙️ **[Pergunta {idx} de {total} | {journo_name} ({journo_outlet}) para {driver_name} ({car_desc})]:**\n"
                    f"\"Os vazamentos desta semana apontam forte pressão sobre o seu desempenho. Como você responde a essas especulações?\"\n"
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
        and generates context-aware, organic room reaction based on Canon Ledger relationships.
        """
        clean_answer = raw_answer.strip()
        driver_name, discord_tag, car_desc = DRIVER_MENTIONS.get(driver_id, (driver_id.capitalize(), driver_id, "Piloto"))
        idx = self.state.get("current_question_idx", 1)

        # 1. Load relationships and journalist context
        ledger_path = self.root_dir / "data" / "state" / "canon_ledger.json"
        mgr = CanonLedgerManager(ledger_path)
        ledger_data = mgr.load()
        relationships = ledger_data.get("relationships", {})
        storm_core = relationships.get("brazilian_storm_core", {})
        grid_dynamics = relationships.get("grid_rivalries_and_dynamics", {})
        rel_str = f"Brazilian Storm: {json.dumps(storm_core, ensure_ascii=False)} | Grid: {json.dumps(grid_dynamics, ensure_ascii=False)}"

        plan = self.state.get("question_plan", [])
        item = plan[idx - 1] if plan and len(plan) >= idx else {}
        journo = item.get("journalist", {})
        journo_name = journo.get("name", "Imprensa Credenciada")
        journo_outlet = journo.get("outlet", "FIA Media Hub")

        # 2. Generate room reaction via Gemini
        q_text = self.state.get("pending_question_text", "")
        prompt = (
            f"SITUAÇÃO DA COLETIVA FIA (Etapa {self.round_num}):\n"
            f"Pergunta feita: {q_text}\n"
            f"Resposta de {driver_name}: \"{clean_answer}\"\n\n"
            f"RELAÇÕES DO CANON LEDGER:\n{rel_str}\n\n"
            f"TAREFA:\n"
            f"Gere em 1 parágrafo curto (máximo 220 caracteres) a reação no recinto.\n\n"
            f"REGRAS DE OURO:\n"
            f"- PROIBIDO usar clichês repetitivos como 'digitam freneticamente nos laptops', 'sorriso de canto de boca', 'canto de sorriso', 'Hamilton fita o horizonte', 'Tom Clarkson pigarreia cortando o clima'.\n"
            f"- Varie a perspectiva entre: a postura de um dos chefes de equipe no fundo da sala (Toto, Vowles, Binotto, Marko); a cumplicidade ou ironia entre Sarah, Felipe e Davi (irmãos competitivos/mentor e pupilos); a reação irritada ou indiferente de Verstappen/Alonso; ou um burburinho agudo entre os correspondentes italianos, espanhóis ou britânicos."
        )
        try:
            reaction = self.ai_client._call_generate_content(
                model=self.ai_client.flash_model,
                parts=[{"text": prompt}],
                temperature=0.65,
            ).strip()
        except Exception:
            reaction = "Um silêncio momentâneo toma a sala enquanto comissários e repórteres trocam olhares rápidos após a declaração enfática."

        # 3. Register in Canon Ledger WITH answer and reaction
        entities = [driver_id, "fia", "imprensa"]
        full_ctx = f"{clean_answer} {reaction} {q_text}"
        for d in ("sarah", "felipe", "davi", "verstappen", "hamilton", "alonso", "leclerc", "norris", "perez", "sainz", "audi", "red_bull", "mercedes", "ferrari", "aston_martin", "williams", "sauber", "vcarb"):
            if d in full_ctx.lower() and d not in entities:
                entities.append(d)

        mgr.append_event(
            event_id=f"ET{self.round_num:02d}-M2-Q{idx}",
            round_num=self.round_num,
            module="M2_COLETIVA",
            summary=f"Na Coletiva Oficial FIA da Etapa {self.round_num}, {driver_name} declarou a {journo_name} ({journo_outlet}): '{clean_answer[:200]}'. Reação no recinto: {reaction[:180]}",
            entities=entities,
            status="OPEN",
        )

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
        """
        Concludes the press conference, saves Markdown report, triggers Portal deploy,
        and posts automated media coverage dispatch to #repercussao-midia.
        """
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

        portal_url = os.environ.get("PORTAL_PUBLIC_URL", "https://tricman.github.io/f1-2026-portal/")

        # Post dispatch to #repercussao-midia (Media publish channel)
        try:
            from src.discord_gateway import DiscordGatewayClient
            gw = DiscordGatewayClient()
            dispatch = (
                f"🏛️ **COLETIVA OFICIAL DA FIA CONCLUÍDA — {self.meta['flag']} {gp_name.upper()} 2026 (ETAPA {self.round_num})**\n"
                f"📍 *Sala de Imprensa Oficial do Circuito*\n\n"
                f"🎙️ **DECLARAÇÕES DE BASTIDORES & ATA OFICIAL ENCERRADA!**\n"
                f"A bancada de pilotos da Formula 1 e da Brazilian Storm encarou a imprensa mundial em uma sessão inflamada em {gp_name}.\n\n"
                f"📰 **Confira a Ata Oficial na Íntegra e a Cobertura Editorial Completa no Portal F1 2026:**\n"
                f"🔗 {portal_url}"
            )
            gw.post_channel_message(gw.publish_channel_id, dispatch)
        except Exception as exc:
            warning(f"[PRESS CONF DISPATCH ERROR] Falha ao enviar para canal de mídia: {exc}")

        closing_msg = (
            f"🏛️ **COLETIVA DE IMPRENSA OFICIAL DA FIA ENCERRADA!**\n"
            f"• Ata oficial e crônica compiladas em `{filename}`.\n"
            f"• As respostas de Sarah, Felipe e Davi foram incorporadas ao Canon Oficial de 2026.\n"
            f"📰 **Crônica Publicada:** Canal <#1536416375969685524> e no Portal Mobile: {portal_url}\n"
            f"👉 O fim de semana de corrida está aberto! Quando prontos, digitem **`inicio da etapa {self.round_num}`** no canal de voz!"
        )
        return (closing_msg, False, None)
