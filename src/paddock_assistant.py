"""
Paddock Personal Assistant & Interactive Q&A Engine (Sprint 4).
Empowers human drivers (Felipe, Sarah, Davi) to ask questions in Discord
and receive contextual briefings from their personal management & paddock staff.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.repositories.base_repository import IDataRepository
from src.repositories.factory import get_repository
from src.logger import info, warning, trace
from src.tracer import trace_span


PILOT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "felipe": {
        "driver_id": "felipe",
        "display_name": "Felipe",
        "full_name": "Felipe (frdsilva)",
        "team_id": "sauber",
        "team_name": "Stake F1 Team Kick Sauber / Audi",
        "car_number": 5,
        "agent_name": "Marcus Thorne",
        "agent_role": "O Tubarão de Silverstone (Gestão de Carreira & Contratos)",
        "voice_persona": "Marcus Thorne (Staff Felipe)",
        "discord_user_id": "1424052555943514194",
        "keywords": ["felipe", "frdsilva", "frdsilva83", "professor", "hinwil", "sauber", "audi"],
    },
    "sarah": {
        "driver_id": "sarah",
        "display_name": "Sarah",
        "full_name": "Sarah (SarahMarinsS)",
        "team_id": "mercedes",
        "team_name": "Mercedes-AMG Petronas F1 Team",
        "car_number": 24,
        "agent_name": "Jules Moreau",
        "agent_role": "Brackley PR & Proteção de Carreira",
        "voice_persona": "Jules Moreau (Assessoria Sarah)",
        "discord_user_id": "1549908557372198984",
        "keywords": ["sarah", "sarahmarinss", "sarahms2013", "ice queen", "brackley", "mercedes"],
    },
    "davi": {
        "driver_id": "davi",
        "display_name": "Davi",
        "full_name": "Davi (DaviMSSon)",
        "team_id": "williams",
        "team_name": "Williams Racing",
        "car_number": 15,
        "agent_name": "Chloe Vance",
        "agent_role": "Grove Management & Captação Global",
        "voice_persona": "Chloe Vance (Staff Davi)",
        "discord_user_id": "1438310004280262689",
        "keywords": ["davi", "davimsson", "leão de grove", "grove", "williams"],
    },
}

TEAM_DISPLAY_NAMES = {
    "mercedes": "Mercedes-AMG Petronas F1 Team",
    "sauber": "Stake F1 Team Kick Sauber",
    "williams": "Williams Racing",
    "red_bull": "Red Bull Racing",
    "ferrari": "Scuderia Ferrari HP",
    "mclaren": "McLaren Formula 1 Team",
    "aston_martin": "Aston Martin Aramco F1 Team",
    "alpine": "BWT Alpine F1 Team",
    "haas": "MoneyGram Haas F1 Team",
    "vcarb": "Visa Cash App RB F1 Team",
}

QUESTION_INTENT_STANDINGS_KEYWORDS = [
    "classificação", "classificacao", "pontuação", "pontuacao", "pontos", "tabela",
    "campeonato", "posição", "posicao", "líder", "lider", "vice", "pontuar", "construtores",
    "campeã", "campea", "campeão", "campeao", "título", "titulo", "distância", "distancia",
    "diferença", "diferenca", "vantagem", "desvantagem", "chance", "chances", "matemática", "matematica"
]

QUESTION_TRIGGER_KEYWORDS = [
    "aconteceu", "relevante", "bastidor", "bastidores", "semana", "fofoca", "notícia", "noticia",
    "boato", "imprensa", "jornalista", "falaram", "comigo", "minha equipe", "meu carro",
    "como estou", "como foi", "situação", "situacao", "briefing", "o que houve", "novidade", "novidades",
    "sarah", "davi", "felipe", "verstappen", "mercedes", "williams", "sauber", "audi", "ferrari", "red bull",
    "perto", "longe", "ganhar", "vencer", "esperar", "opinião", "opiniao"
]


def resolve_caller_driver(author_name: str, author_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Identifies which driver is communicating in Discord based on author username or display name.
    Defaults to Felipe (#5) if no explicit match is found.
    """
    author_clean = (author_name or "").strip().lower()
    for driver_id, data in PILOT_REGISTRY.items():
        if any(kw in author_clean for kw in data["keywords"]):
            return data
    return PILOT_REGISTRY["felipe"]


def resolve_target_subject(query_text: str, caller_driver: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identifies who the query is inquiring about.
    If the question mentions another pilot (e.g. 'com o Davi', 'sobre a Sarah'), returns that pilot.
    If the question uses first-person pronouns ('comigo', 'meu carro') or doesn't mention another pilot,
    returns the caller_driver.
    """
    clean = (query_text or "").strip().lower()

    # 1. Explicit first-person keywords always refer to caller
    first_person_patterns = [r"\bcomigo\b", r"\bmeu\b", r"\bminha\b", r"\beu\b", r"\bpara mim\b", r"\bpra mim\b"]
    if any(re.search(pat, clean) for pat in first_person_patterns):
        return caller_driver

    # 2. Check if another specific driver is mentioned in the query
    for driver_id, data in PILOT_REGISTRY.items():
        if any(kw in clean for kw in data["keywords"][:2]):  # e.g. "sarah", "davi", "felipe"
            return data

    # 3. Default: subject is the caller himself
    return caller_driver


def resolve_driver_identity(author_name: str, author_id: Optional[str], content: str) -> Dict[str, Any]:
    """
    Backward-compatible resolver. Returns the target subject of the query.
    """
    caller = resolve_caller_driver(author_name, author_id)
    return resolve_target_subject(content, caller)


def is_assistant_query(content: str, is_mentioned: bool = False, in_dedicated_channel: bool = False) -> bool:
    """
    Evaluates whether an incoming Discord message is intended for the Paddock Assistant.
    Avoids catching game stage commands (e.g. 'avancar dia', 'iniciar etapa').
    """
    if not content:
        return False

    clean = content.strip().lower()

    # Ignore explicit ChatOps stage commands
    stage_command_patterns = [
        r"\b(?:avancar|avançar|proximo|próximo)\s+dia\b",
        r"\b(?:iniciar|comecar|começar|start)\s+(?:a\s+)?etapa\b",
        r"\b(?:finalizar|encerrar|fim\s+da)\s+etapa\b",
        r"\b(?:coletiva|press)\s+(?:da\s+|de\s+|fia\s+)?(?:etapa)?\b",
        r"\b(?:forcar|forçar|avancar|avançar)\s+(?:avanco\s+|avanço\s+)?coletiva\b",
        r"\b(?:opcao|opção)\s+[ab]\b",
        r"\b(?:iniciar|status|parar)\s+escuta\b",
        r"\b(?:rollback|reverter)\s+etapa\b",
    ]
    for pat in stage_command_patterns:
        if re.search(pat, clean):
            return False

    has_question_mark = "?" in content
    has_standings_kw = any(w in clean for w in QUESTION_INTENT_STANDINGS_KEYWORDS)
    has_trigger_kw = any(w in clean for w in QUESTION_TRIGGER_KEYWORDS)

    # Trigger conditions:
    # 1. Any message with '?' that is not a game stage command is an assistant query
    if has_question_mark:
        return True

    # 2. User explicitly tagged the bot or asked in dedicated channel
    if is_mentioned or in_dedicated_channel:
        return has_standings_kw or has_trigger_kw or len(clean.split()) >= 2

    return has_standings_kw or has_trigger_kw


def classify_query_intent(query: str) -> str:
    """
    Classifies the user query as 'STANDINGS' (deterministic) or 'PADDOCK_LORE' (semantic Gemini RAG).
    Complex inquiries involving 'perto', 'campeã', 'título' or 'chance' are routed to RAG.
    """
    clean = query.strip().lower()
    has_complex_lore = any(w in clean for w in [
        "aconteceu", "relevante", "bastidor", "fofoca", "notícia", "noticia", "boato", "semana", "falaram",
        "perto", "longe", "chance", "chances", "ser campeã", "ser campea", "ser campeão", "ser campeao",
        "título", "titulo", "ganhar", "vencer", "opinião", "opiniao"
    ])
    has_pure_standings = any(w in clean for w in [
        "classificação", "classificacao", "tabela", "pontuação", "pontuacao", "pontos", "posição", "posicao",
        "construtores", "construtor", "equipes", "equipe", "escuderias", "escuderia"
    ])

    if has_pure_standings and not has_complex_lore:
        return "STANDINGS"
    return "PADDOCK_LORE"


@trace_span("paddock_assistant_standings")
def handle_deterministic_standings_query(
    driver_data: Dict[str, Any],
    repo: Optional[IDataRepository] = None,
    target_subject: Optional[Dict[str, Any]] = None,
    query_text: str = "",
) -> str:
    """
    Generates a sub-50ms instant deterministic briefing of current official standings.
    Reads directly from SQLite Document Store / JSON without invoking LLM tokens.
    Handles:
    - Constructors table (when requested)
    - Drivers table (when requested)
    - Specific driver card (default for personal standing queries)
    """
    active_repo = repo or get_repository()
    standings = active_repo.get_standings()

    subject = target_subject or driver_data
    caller = driver_data
    is_about_rival = (subject["driver_id"] != caller["driver_id"])

    last_r = standings.get("last_completed_round", 10)
    drivers = standings.get("drivers_standings") or standings.get("drivers") or []
    constructors = standings.get("constructors_standings") or standings.get("constructors") or []
    portal_url = "https://tricman.github.io/f1-2026-portal/"

    clean_q = (query_text or "").strip().lower()

    # 1. Check if user specifically requested Constructors Standing
    is_constructors_query = any(w in clean_q for w in [
        "construtor", "construtores", "equipe", "equipes", "escuderia", "escuderias", "marca", "marcas"
    ])

    if is_constructors_query:
        lines = []
        for idx, c in enumerate(constructors):
            pos = c.get("pos", idx + 1)
            t_key = (c.get("team_id") or c.get("id") or "").lower()
            name = c.get("name") or TEAM_DISPLAY_NAMES.get(t_key, t_key.title() or f"Equipe {pos}")
            pts = c.get("net_points", c.get("points", 0))
            pen = c.get("fia_penalty_points", 0)
            pen_str = f" *(Penalidade FIA: {pen} pts)*" if pen and pen < 0 else ""
            medal = "🥇 " if pos == 1 else "🥈 " if pos == 2 else "🥉 " if pos == 3 else ""
            is_caller_team = (c.get("team_id") == caller.get("team_id") or c.get("id") == caller.get("team_id"))
            tag = " 📍" if is_caller_team else ""
            lines.append(f"• **{pos}º** {medal}**{name}** — **{pts} pts**{pen_str}{tag}")

        table_body = "\n".join(lines) if lines else "Tabela de construtores em consolidação."
        card = (
            f"🏛️ **[MUNDIAL DE CONSTRUTORES FIA 2026]**\n"
            f"📍 *Situação após Etapa {last_r}*\n\n"
            f"{table_body}\n\n"
            f"🔗 *Tabela completa e telemetria no Portal:* {portal_url}#standings"
        )
        return card

    # 2. Check if user requested Drivers Ranking (General / Grid / Top)
    is_drivers_query = any(w in clean_q for w in [
        "pilotos", "grid", "lideres", "líderes", "mundial de pilotos", "tabela de pilotos", "classificação de pilotos", "top 10"
    ]) and not any(w in clean_q for w in ["minha", "meu", "comigo", "felipe", "sarah", "davi", "eu", "estou", "como fico"])

    if is_drivers_query:
        lines = []
        for idx, d in enumerate(drivers[:10]):
            pos = d.get("pos", idx + 1)
            name = d.get("name") or d.get("id") or f"Piloto {pos}"
            pts = d.get("points", 0)
            wins = d.get("wins", 0)
            w_str = f" ({wins} vitórias)" if wins > 0 else ""
            medal = "🥇 " if pos == 1 else "🥈 " if pos == 2 else "🥉 " if pos == 3 else ""
            is_caller = (d.get("id") == caller.get("driver_id"))
            tag = " 📍" if is_caller else ""
            lines.append(f"• **{pos}º** {medal}**{name}** — **{pts} pts**{w_str}{tag}")

        table_body = "\n".join(lines) if lines else "Tabela de pilotos em consolidação."
        card = (
            f"🏆 **[MUNDIAL DE PILOTOS FIA 2026]**\n"
            f"📍 *Situação após Etapa {last_r} (Top 10)*\n\n"
            f"{table_body}\n\n"
            f"🔗 *Tabela completa e telemetria no Portal:* {portal_url}#standings"
        )
        return card

    # 3. Individual Driver Briefing Card (Default for personal / single pilot queries)
    d_id = subject["driver_id"]
    driver_entry = next((d for d in drivers if d.get("id") == d_id), None)
    leader_entry = drivers[0] if drivers else None

    pos = driver_entry.get("pos", 2) if driver_entry else 2
    pts = driver_entry.get("points", 0) if driver_entry else 0
    wins = driver_entry.get("wins", 0) if driver_entry else 0
    podiums = driver_entry.get("podiums", 0) if driver_entry else 0
    poles = driver_entry.get("poles", 0) if driver_entry else 0

    # Construct team entry with robust team_id / id lookup
    c_id = subject["team_id"]
    team_entry = next((c for c in constructors if (c.get("team_id") == c_id or c.get("id") == c_id)), None)
    team_pos = team_entry.get("pos", 2) if team_entry else 2
    team_pts = team_entry.get("net_points", team_entry.get("points", 0)) if team_entry else 0
    team_name = team_entry.get("name") if (team_entry and team_entry.get("name")) else subject["team_name"]

    # Calculate delta
    delta_str = ""
    if leader_entry and leader_entry.get("id") != d_id:
        gap = leader_entry.get("points", 0) - pts
        delta_str = f" • *-{gap} pts do líder ({leader_entry.get('name', 'P1')})*"
    elif len(drivers) > 1:
        p2_gap = pts - drivers[1].get("points", 0)
        delta_str = f" • *+{p2_gap} pts de vantagem sobre P2*"

    inquiry_footer = f"\n*Solicitado por {caller['display_name']} ({caller['team_name']})*" if is_about_rival else ""

    card = (
        f"📋 **[BRIEFING OFICIAL FIA] Campeonato Mundial de F1 2026**\n"
        f"📍 *Situação após Etapa {last_r}*\n\n"
        f"👤 **{subject['display_name']} (#{subject['car_number']}):**\n"
        f"• **Posição no Mundial:** **{pos}º Lugar** com **{pts} pontos**{delta_str}\n"
        f"• **Desempenho:** {wins} Vitórias | {podiums} Pódios | {poles} Poles\n"
        f"🏢 **{team_name}:** {team_pos}º Lugar nos Construtores ({team_pts} pts){inquiry_footer}\n\n"
        f"🔗 *Tabela completa e telemetria detalhada no Portal:* {portal_url}#standings"
    )
    return card


@trace_span("paddock_assistant_semantic_lore")
def handle_semantic_paddock_query(
    driver_data: Dict[str, Any],
    query: str,
    round_num: int,
    round_folder: str,
    root_dir: Path,
    repo: Optional[IDataRepository] = None,
    ai_client: Optional[Any] = None,
    season_id: Optional[str] = None,
    target_subject: Optional[Dict[str, Any]] = None,
) -> str:
    """
    RAG-grounded semantic query processed via Gemini Flash-Lite.
    Retrieves current week M1 chronicles (Days 1 to 4), Canon Ledger events,
    and formats as an exclusive confidential agent memorandum.
    Supports asking about oneself or gathering intelligence on rivals.
    """
    from src.season_manager import get_season_dir
    from src.ai_showrunner import GeminiFreeTierClient

    active_repo = repo or get_repository()
    client = ai_client or GeminiFreeTierClient()

    caller = driver_data
    subject = target_subject or driver_data
    is_about_rival = (subject["driver_id"] != caller["driver_id"])

    # 1. Collect Standings overview for mathematical / championship context
    standings_info = active_repo.get_standings()
    drivers_list = standings_info.get("drivers_standings") or standings_info.get("drivers") or []
    standings_summary_lines = []
    for d in drivers_list[:6]:
        standings_summary_lines.append(f"- P{d.get('pos', '?')}: {d.get('name')} ({d.get('points', 0)} pts, {d.get('wins', 0)} vitórias)")
    standings_context = "\n".join(standings_summary_lines) if standings_summary_lines else "Tabela em consolidação."

    # 2. Collect open Canon Ledger events for this round & target subject
    ledger = active_repo.get_canon_ledger()
    events = ledger.get("events", [])
    relevant_events = []
    subject_kw = subject["keywords"]
    for ev in events:
        if ev.get("round") == round_num or subject["driver_id"] in ev.get("entities", []):
            summary_lower = str(ev.get("summary", "")).lower()
            entities_lower = [str(e).lower() for e in ev.get("entities", [])]
            if any(k in entities_lower for k in subject_kw) or any(k in summary_lower for k in subject_kw) or not is_about_rival:
                relevant_events.append(f"- [{ev.get('module')}] {ev.get('summary')}")

    events_summary = "\n".join(relevant_events) if relevant_events else "Nenhum incidente disciplinar ou queixa registrada pela FIA sobre esta equipe."

    # 2. Collect generated daily chronicles of M1 for this round
    season_dir = get_season_dir(root_dir, season_id)
    target_round_dir = season_dir / round_folder
    daily_snippets = []
    if target_round_dir.exists():
        for day_file in sorted(target_round_dir.glob("ET*_PRE_A_Semana_da_F1_Dia_*.md")):
            text = day_file.read_text(encoding="utf-8")
            lines = [l for l in text.splitlines() if any(k in l.lower() for k in subject_kw)]
            if lines:
                daily_snippets.append(f"### {day_file.stem}:\n" + "\n".join(lines[:8]))

    chronicles_context = "\n\n".join(daily_snippets) if daily_snippets else f"A semana de preparação em fábrica decorre dentro do cronograma padrão para {subject['display_name']}."

    # 3. Assemble RAG Prompt according to relationship (self vs rival)
    if is_about_rival:
        system_instruction = (
            f"Você é {caller['agent_name']}, assessor pessoal e estrategista do piloto {caller['display_name']}. "
            f"Seu piloto {caller['display_name']} perguntou a você sobre o rival {subject['display_name']} ({subject['team_name']}). "
            f"Responda diretamente a {caller['display_name']} apresentando um memorando de inteligência confidencial, perspicaz e mordaz "
            f"sobre o que você apurou a respeito de {subject['display_name']} e sua equipe. "
            f"Dirija-se a {caller['display_name']} pelo nome dele ({caller['display_name']}) e JAMAIS o confunda com {subject['display_name']}."
        )
        relationship_prompt = (
            f"=== RELAÇÃO DE INTERLOCUÇÃO ===\n"
            f"Interlocutor (Seu Piloto): {caller['display_name']} (#{caller['car_number']}, {caller['team_name']})\n"
            f"Seu Papel: {caller['agent_name']} ({caller['agent_role']})\n"
            f"Alvo da Investigação (Rival): {subject['display_name']} (#{subject['car_number']}, {subject['team_name']})\n\n"
            f"DIRETRIZES DE RESPOSTA:\n"
            f"1. Responda ESTRITAMENTE em Português (Brasil) como {caller['agent_name']} falando com seu piloto {caller['display_name']}.\n"
            f"2. Fale com {caller['display_name']} em tom íntimo, mordaz e analítico sobre o que você apurou sobre o rival {subject['display_name']}.\n"
            f"3. Destaque de 2 a 3 pontos essenciais (máximo 140 palavras) baseando-se RIGOROSAMENTE nos fatos fornecidos acima.\n"
            f"4. NUNCA trate {caller['display_name']} como se ele fosse o {subject['display_name']}."
        )
    else:
        system_instruction = (
            f"Você é {caller['agent_name']}, assessor pessoal e estrategista do piloto {caller['display_name']}. "
            f"Responda ao seu piloto com precisão cirúrgica de bastidor sobre a equipe dele ({caller['team_name']}), sem inventar fatos inexistentes."
        )
        relationship_prompt = (
            f"=== RELAÇÃO DE INTERLOCUÇÃO ===\n"
            f"Interlocutor (Seu Piloto): {caller['display_name']} (#{caller['car_number']}, {caller['team_name']})\n"
            f"Seu Papel: {caller['agent_name']} ({caller['agent_role']})\n\n"
            f"DIRETRIZES DE RESPOSTA:\n"
            f"1. Responda ESTRITAMENTE em Português (Brasil) como {caller['agent_name']} falando com seu piloto {caller['display_name']}.\n"
            f"2. Fale diretamente com {caller['display_name']} em tom íntimo, profissional, inteligente e mordaz de bastidor de F1.\n"
            f"3. Destaque de 2 a 3 pontos essenciais (máximo 140 palavras) baseando-se RIGOROSAMENTE nos fatos acima.\n"
            f"4. Se nenhum fato dramático tiver acontecido, afirme com segurança que a semana na equipe está estável e focada na engenharia."
        )

    prompt = (
        f"=== CONTEXTO OFICIAL DO PADDOCK DE FÓRMULA 1 2026 ===\n"
        f"Etapa Atual: Etapa {round_num} ({round_folder}) de um total de 24 etapas na temporada (Restam {max(24 - round_num + 1, 0)} etapas e até {max(24 - round_num + 1, 0) * 26} pontos em disputa).\n"
        f"Sujeito em Análise: {subject['full_name']} ({subject['team_name']})\n\n"
        f"=== CLASSIFICAÇÃO ATUAL DO CAMPEONATO (TOP 6) ===\n"
        f"{standings_context}\n\n"
        f"=== EVENTOS CANÔNICOS RELEVANTES ===\n"
        f"{events_summary}\n\n"
        f"=== BASTIDORES & CRÔNICAS DA SEMANA (DIAS GERADOS) ===\n"
        f"{chronicles_context}\n\n"
        f"=== PERGUNTA DE {caller['display_name'].upper()} ===\n"
        f"\"{query}\"\n\n"
        f"{relationship_prompt}"
    )

    try:
        raw_answer = client._call_generate_content(
            model=client.flash_model,
            parts=[{"text": prompt}],
            system_instruction=system_instruction,
            temperature=0.25,
        ).strip()
    except Exception as exc:
        warning(f"[PADDOCK ASSISTANT GEMINI ERROR] Fallback ativado: {exc}")
        if is_about_rival:
            raw_answer = (
                f"{caller['display_name']}, nossos contatos no paddock indicam que {subject['display_name']} e a {subject['team_name']} "
                f"mantêm o foco estrito no acerto aerodinâmico para a pista. Sem crises imediatas no radar deles até o momento."
            )
        else:
            raw_answer = (
                f"{caller['display_name']}, nossos relatórios de bastidores para esta etapa indicam foco absoluto "
                f"na calibração do carro para o circuito. Sem crises contratuais ou rumores fora do planejado até o momento."
            )

    card = (
        f"📱 **[MEMORANDO CONFIDENCIAL • {caller['agent_name'].upper()}]**\n"
        f"*{caller['agent_role']}*\n\n"
        f"{raw_answer}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return card


def process_paddock_assistant_query(
    author_name: str,
    author_id: Optional[str],
    query_text: str,
    round_num: int,
    round_folder: str,
    root_dir: Path,
    repo: Optional[IDataRepository] = None,
    ai_client: Optional[Any] = None,
    season_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Main entrypoint for processing driver queries.
    Identifies the speaking driver (caller) and the target subject being asked about.
    The response is always voiced by the caller's personal agent.
    Returns: (formatted_response, sender_persona_name)
    """
    caller_driver = resolve_caller_driver(author_name, author_id)
    target_subject = resolve_target_subject(query_text, caller_driver)
    intent = classify_query_intent(query_text)

    trace(
        f"Processing assistant query for {caller_driver['display_name']} about {target_subject['display_name']} | Intent: {intent}",
        event="PADDOCK_ASSISTANT_QUERY",
        caller_id=caller_driver["driver_id"],
        target_id=target_subject["driver_id"],
        intent=intent,
    )

    if intent == "STANDINGS":
        response = handle_deterministic_standings_query(
            caller_driver,
            repo=repo,
            target_subject=target_subject,
            query_text=query_text,
        )
    else:
        response = handle_semantic_paddock_query(
            driver_data=caller_driver,
            query=query_text,
            round_num=round_num,
            round_folder=round_folder,
            root_dir=root_dir,
            repo=repo,
            ai_client=ai_client,
            season_id=season_id,
            target_subject=target_subject,
        )

    sender_persona = caller_driver["voice_persona"]
    return response, sender_persona
