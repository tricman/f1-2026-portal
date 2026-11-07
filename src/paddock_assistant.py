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
        "keywords": ["felipe", "frdsilva", "professor", "hinwil", "sauber", "audi"],
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
        "keywords": ["sarah", "sarahmarinss", "ice queen", "brackley", "mercedes"],
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
        "keywords": ["davi", "davimsson", "leão de grove", "grove", "williams"],
    },
}

QUESTION_INTENT_STANDINGS_KEYWORDS = [
    "classificação", "classificacao", "pontuação", "pontuacao", "pontos", "tabela",
    "campeonato", "posição", "posicao", "líder", "lider", "vice", "pontuar", "construtores"
]

QUESTION_TRIGGER_KEYWORDS = [
    "aconteceu", "relevante", "bastidor", "bastidores", "semana", "fofoca", "notícia", "noticia",
    "boato", "imprensa", "jornalista", "falaram", "comigo", "minha equipe", "meu carro",
    "como estou", "como foi", "situação", "situacao", "briefing", "o que houve"
]


def resolve_driver_identity(author_name: str, author_id: Optional[str], content: str) -> Dict[str, Any]:
    """
    Resolves the driver identity from the message author and contextual inquiry.
    Supports first-person questions ("comigo", "meu carro") and third-party inquires ("o que houve com a Sarah?").
    """
    author_clean = (author_name or "").strip().lower()
    content_clean = (content or "").strip().lower()

    # 1. Check if the question explicitly asks about another Brazilian Storm driver
    if "sarah" in content_clean and not any(k in author_clean for k in ["sarah", "marinss"]):
        return PILOT_REGISTRY["sarah"]
    if "davi" in content_clean and not any(k in author_clean for k in ["davi", "msson"]):
        return PILOT_REGISTRY["davi"]
    if "felipe" in content_clean and not any(k in author_clean for k in ["felipe", "frdsilva"]):
        return PILOT_REGISTRY["felipe"]

    # 2. Match author against pilot registry
    for driver_id, data in PILOT_REGISTRY.items():
        for kw in data["keywords"]:
            if kw in author_clean:
                return data

    # 3. Fallback: Default to Felipe (#5) as default human team principal/driver
    return PILOT_REGISTRY["felipe"]


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
    # 1. User explicitly tagged the bot or asked a question
    # 2. In a dedicated chat, any question mark or assistant keyword triggers it
    if is_mentioned:
        return has_question_mark or has_standings_kw or has_trigger_kw or len(clean.split()) >= 2

    if has_question_mark and (has_standings_kw or has_trigger_kw):
        return True

    if in_dedicated_channel and (has_standings_kw or has_trigger_kw):
        return True

    return False


def classify_query_intent(query: str) -> str:
    """
    Classifies the user query as 'STANDINGS' (deterministic) or 'PADDOCK_LORE' (semantic Gemini RAG).
    """
    clean = query.strip().lower()
    has_standings = any(w in clean for w in QUESTION_INTENT_STANDINGS_KEYWORDS)
    has_lore = any(w in clean for w in ["aconteceu", "relevante", "bastidor", "fofoca", "notícia", "noticia", "boato", "semana", "falaram"])

    if has_standings and not has_lore:
        return "STANDINGS"
    return "PADDOCK_LORE"


@trace_span("paddock_assistant_standings")
def handle_deterministic_standings_query(
    driver_data: Dict[str, Any],
    repo: Optional[IDataRepository] = None,
) -> str:
    """
    Generates a sub-50ms instant deterministic briefing of current official standings.
    Reads directly from SQLite Document Store / JSON without invoking LLM tokens.
    """
    active_repo = repo or get_repository()
    standings = active_repo.get_standings()

    last_r = standings.get("last_completed_round", 10)
    drivers = standings.get("drivers_standings") or standings.get("drivers") or []
    constructors = standings.get("constructors_standings") or standings.get("constructors") or []

    d_id = driver_data["driver_id"]
    driver_entry = next((d for d in drivers if d.get("id") == d_id), None)
    leader_entry = drivers[0] if drivers else None

    pos = driver_entry.get("pos", 2) if driver_entry else 2
    pts = driver_entry.get("points", 0) if driver_entry else 0
    wins = driver_entry.get("wins", 0) if driver_entry else 0
    podiums = driver_entry.get("podiums", 0) if driver_entry else 0
    poles = driver_entry.get("poles", 0) if driver_entry else 0

    # Construct team entry
    c_id = driver_data["team_id"]
    team_entry = next((c for c in constructors if c.get("id") == c_id), None)
    team_pos = team_entry.get("pos", 2) if team_entry else 2
    team_pts = team_entry.get("net_points", team_entry.get("points", 0)) if team_entry else 0

    # Calculate delta
    delta_str = ""
    if leader_entry and leader_entry.get("id") != d_id:
        gap = leader_entry.get("points", 0) - pts
        delta_str = f" • *-{gap} pts de Sarah (P1)*"
    elif len(drivers) > 1:
        p2_gap = pts - drivers[1].get("points", 0)
        delta_str = f" • *+{p2_gap} pts de vantagem sobre P2*"

    portal_url = "https://tricman.github.io/f1-2026-portal/"

    card = (
        f"📋 **[BRIEFING OFICIAL FIA] Campeonato Mundial de F1 2026**\n"
        f"📍 *Situação após Etapa {last_r}*\n\n"
        f"👤 **{driver_data['display_name']} (#{driver_data['car_number']}):**\n"
        f"• **Posição no Mundial:** **{pos}º Lugar** com **{pts} pontos**{delta_str}\n"
        f"• **Desempenho:** {wins} Vitórias | {podiums} Pódios | {poles} Poles\n"
        f"🏢 **{driver_data['team_name']}:** {team_pos}º Lugar nos Construtores ({team_pts} pts)\n\n"
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
) -> str:
    """
    RAG-grounded semantic query processed via Gemini Flash-Lite.
    Retrieves current week M1 chronicles (Days 1 to 4), Canon Ledger events,
    and formats as an exclusive confidential agent memorandum.
    """
    from src.season_manager import get_season_dir
    from src.ai_showrunner import GeminiFreeTierClient

    active_repo = repo or get_repository()
    client = ai_client or GeminiFreeTierClient()

    # 1. Collect open Canon Ledger events for this round & driver
    ledger = active_repo.get_canon_ledger()
    events = ledger.get("events", [])
    relevant_events = []
    for ev in events:
        if ev.get("round") == round_num or driver_data["driver_id"] in ev.get("entities", []):
            relevant_events.append(f"- [{ev.get('module')}] {ev.get('summary')}")

    events_summary = "\n".join(relevant_events) if relevant_events else "Nenhum incidente disciplinar ou queixa registrada pela FIA."

    # 2. Collect generated daily chronicles of M1 for this round
    season_dir = get_season_dir(root_dir, season_id)
    target_round_dir = season_dir / round_folder
    daily_snippets = []
    if target_round_dir.exists():
        for day_file in sorted(target_round_dir.glob("ET*_PRE_A_Semana_da_F1_Dia_*.md")):
            text = day_file.read_text(encoding="utf-8")
            # Extract sections relevant to the driver's team or driver name
            team_kw = driver_data["keywords"][0]
            lines = [l for l in text.splitlines() if any(k in l.lower() for k in driver_data["keywords"])]
            if lines:
                daily_snippets.append(f"### {day_file.stem}:\n" + "\n".join(lines[:6]))

    chronicles_context = "\n\n".join(daily_snippets) if daily_snippets else "A semana de preparação em fábrica decorre dentro do cronograma padrão."

    # 3. Assemble RAG Prompt
    prompt = (
        f"=== CONTEXTO OFICIAL DO PADDOCK DE FÓRMULA 1 2026 ===\n"
        f"Etapa Atual: Etapa {round_num} ({round_folder})\n"
        f"Piloto Alvo: {driver_data['full_name']} ({driver_data['team_name']})\n"
        f"Agente Responsável: {driver_data['agent_name']} ({driver_data['agent_role']})\n\n"
        f"=== EVENTOS CANÔNICOS RELEVANTES ===\n"
        f"{events_summary}\n\n"
        f"=== BASTIDORES & CRÔNICAS DA SEMANA (DIAS GERADOS) ===\n"
        f"{chronicles_context}\n\n"
        f"=== PERGUNTA DO PILOTO ===\n"
        f"\"{query}\"\n\n"
        f"DIRETRIZES DE RESPOSTA:\n"
        f"1. Responda ESTRITAMENTE em Português (Brasil) como o agente/assessor {driver_data['agent_name']}.\n"
        f"2. Fale diretamente com {driver_data['display_name']} em tom íntimo, profissional, inteligente e mordaz de bastidor de F1.\n"
        f"3. Destaque de 2 a 3 pontos essenciais (máximo 140 palavras) baseando-se RIGOROSAMENTE nos fatos acima.\n"
        f"4. Se nenhum fato dramático tiver acontecido com o piloto, afirme com segurança que a semana na equipe está estável e focada na engenharia.\n"
        f"5. NUNCA alucine pontuações ou acidentes que não estejam no contexto."
    )

    try:
        raw_answer = client._call_generate_content(
            model=client.flash_model,
            parts=[{"text": prompt}],
            system_instruction=(
                f"Você é {driver_data['agent_name']}, assessor pessoal e estrategista do piloto {driver_data['display_name']}. "
                "Responda ao seu piloto com precisão cirúrgica de bastidor, sem inventar fatos inexistentes."
            ),
            temperature=0.25,
        ).strip()
    except Exception as exc:
        warning(f"[PADDOCK ASSISTANT GEMINI ERROR] Fallback ativado: {exc}")
        raw_answer = (
            f"{driver_data['display_name']}, nossos relatórios de bastidores para esta etapa indicam foco absoluto "
            f"na calibração do carro para o circuito. Sem crises contratuais ou rumores fora do planejado até o momento."
        )

    card = (
        f"📱 **[MEMORANDO CONFIDENCIAL • {driver_data['agent_name'].upper()}]**\n"
        f"*{driver_data['agent_role']}*\n\n"
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
    Returns: (formatted_response, sender_persona_name)
    """
    driver_data = resolve_driver_identity(author_name, author_id, query_text)
    intent = classify_query_intent(query_text)

    trace(
        f"Processing assistant query for {driver_data['display_name']} | Intent: {intent}",
        event="PADDOCK_ASSISTANT_QUERY",
        driver_id=driver_data["driver_id"],
        intent=intent,
    )

    if intent == "STANDINGS":
        response = handle_deterministic_standings_query(driver_data, repo=repo)
    else:
        response = handle_semantic_paddock_query(
            driver_data=driver_data,
            query=query_text,
            round_num=round_num,
            round_folder=round_folder,
            root_dir=root_dir,
            repo=repo,
            ai_client=ai_client,
            season_id=season_id,
        )

    sender_persona = driver_data["voice_persona"]
    return response, sender_persona
