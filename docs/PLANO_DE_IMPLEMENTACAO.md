# Plano de Implementação: Showrunner F1 2026 (As-Built Roadmap)
**Documento de Origem:** `docs/ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx` (v2.2.0)  
**Status:** Planejado | **Linha de Base:** Especificação Aprovada  
**Liderança Técnica:** Desenvolvedor Sênior / Engenheiro de Solução  
**Meta Operacional:** Habilitar 100% dos requisitos aprovados preservando a integridade da Etapa 11 (Áustria) e das etapas concluídas (Etapas 01 a 10).  

---

## 1. Matriz de Rastreabilidade: Especificação Aprovada vs. Código Atual (Gap Analysis)

| ID Requisito | Funcionalidade na Especificação Aprovada | Estado no Código Atual | Severidade / Esforço |
| :---: | :--- | :---: | :---: |
| **REQ-01** | Catálogo das 12 Verticais Temáticas da Silly Season | ✅ Implementado em `src/canon_ledger.py` | Baixo (Concluído) |
| **REQ-02** | Cobertura M1 de todas as 10 Equipes (Reais e NPCs) | ⚠️ Parcial (cobre 4 equipes no gerador) | Médio (2 horas) |
| **REQ-03** | Módulo M1.5: Dilema Interativo de Paddock com Trava de Turno | ❌ Não Implementado no código | Médio (3 horas) |
| **REQ-04** | Coletiva M2: Contingência por Timeout de Piloto via IA | ✅ Implementado (`force_timeout_answer` + fallback Gemini) | Baixo (Concluído no Sprint 1) |
| **REQ-05** | Ingestão UDP 20777 e Descarte de Slots Residuais (`m_numActiveCars`) | ✅ Implementado em `src/telemetry/session_recorder.py` | Baixo (Concluído) |
| **REQ-06** | Ingestão de Áudios de Debriefing de Voz nos Módulos M5 e M6 | ⚠️ Parcial (transcrição existe, falta hook no Discord) | Médio (2 horas) |
| **REQ-07** | M6 Ato 4: Declarações de Pilotos NPCs Relevantes | ⚠️ Parcial (prompt precisa de ajuste) | Baixo (1 hora) |
| **REQ-08** | M7: Cálculo Determinístico e Dispensa de Imagem PNG | ✅ Implementado (basta suprimir renderizador PNG) | Baixo (0.5 hora) |
| **REQ-09** | M8: Crônica de Corrida + Bancada de Lendas (Prost, Mansell, Villeneuve) | ⚠️ Parcial (prompts focam apenas em Prost) | Médio (2.5 horas) |
| **REQ-10** | ChatOps: Comando `iniciar escuta f1` para o Listener UDP | ✅ Implementado em `discord_gateway.py` e `orchestrator_cli.py` | Médio (Concluído no Sprint 1) |
| **REQ-11** | ChatOps: Rotina de Rollback Granular de Etapa (`rollback etapa XX`) | ✅ Implementado em `orchestrator_cli.py` com 4 escopos e trava | Médio (Concluído no Sprint 1) |
| **REQ-12** | Persistência: Base NoSQL Local Unificada (TinyDB / SQLite Document) | ❌ Não Implementado (JSONs puros atuais) | Alto (4 horas) |
| **REQ-13** | Arquitetura Multi-Temporada (Particionamento por `season_id`) | ⚠️ Parcial (pastas `season_01` fixas em código) | Médio (2.5 horas) |
| **REQ-14** | Portal Web: Design Paddock Dark Mode & Navegação por Abas | ⚠️ Parcial (layout funcional, falta tema dark F1) | Médio (3 horas) |

---

## 2. Cronograma de Execução em 4 Sprints Técnicos

```mermaid
flowchart TD
    subgraph Sprint1["Sprint 1: ChatOps & Automação de Corrida (Imediato)"]
        S1_1["1.1 Comando 'iniciar escuta f1'"]
        S1_2["1.2 Rotina de Rollback Granular"]
        S1_3["1.3 Timeout de Piloto no M2"]
    end

    subgraph Sprint2["Sprint 2: Storytelling & Prompts M1 a M8"]
        S2_1["2.1 M1: Cobertura das 10 Equipes"]
        S2_2["2.2 M1.5: Dilema Interativo com Trava"]
        S2_3["2.3 M6: NPCs & Debriefing de Voz"]
        S2_4["2.4 M8: Crônica & Bancada de Lendas"]
    end

    subgraph Sprint3["Sprint 3: NoSQL Local & Multi-Temporada"]
        S3_1["3.1 Repositório NoSQL Local (TinyDB/SQLite)"]
        S3_2["3.2 Parametrização por season_id"]
        S3_3["3.3 Storytelling de Transferências"]
    end

    subgraph Sprint4["Sprint 4: Portal Web Dark Mode & Polish"]
        S4_1["4.1 Layout Paddock Dark Mode"]
        S4_2["4.2 Cards da Bancada de Lendas"]
        S4_3["4.3 Homologação Ponta a Ponta"]
    end

    Sprint1 --> Sprint2
    Sprint2 --> Sprint3
    Sprint3 --> Sprint4
```

---

## 3. Detalhamento dos Pacotes de Trabalho (Work Packages)

### Sprint 1: ChatOps & Automação Operacional (Habilitação da Etapa 11) — ✅ CONCLUÍDO
* **Atividade 1.1 — Comando `iniciar escuta f1`:** ✅
  * Arquivos: `src/discord_gateway.py`, `src/orchestrator_cli.py`, `tests/test_sprint1.py`.
  * Status: Implementado. Comandos `iniciar escuta f1`, `status telemetria` e `parar escuta f1` habilitados no ChatOps e via CLI (`--action start-listener`, `--action status-listener`, `--action stop-listener`). Rastreamento via `data/state/listener.pid` e processo `python -m src.udp_relay` em background não-bloqueante na porta 20777.
* **Atividade 1.2 — Rotina de Rollback Granular de Etapa:** ✅
  * Arquivos: `src/orchestrator_cli.py`, `src/discord_gateway.py`, `tests/test_sprint1.py`.
  * Status: Implementado. Método `execute_stage_rollback(round_num, scope)` implementado com suporte aos escopos `sessao`, `coletiva`, `semana`, `tudo`. Proteção de integridade estrita para as Etapas 01 a 10 (imutáveis). No ChatOps, comando `rollback etapa XX [escopo]` exige confirmação explícita via `confirmar rollback` (com expiração em 60s) ou `cancelar rollback`.
* **Atividade 1.3 — Contingência por Timeout de Coletiva (M2):** ✅
  * Arquivos: `src/press_conference.py`, `src/discord_gateway.py`, `tests/test_sprint1.py`.
  * Status: Implementado. Adicionado método `force_timeout_answer(reason)` em `PressConferenceSession` com sintetização de resposta in-character via Gemini fundamentada no arquivo `Setup - Perfil [Piloto].md`. Integração do comando `forcar avanco coletiva` e verificação de auto-timeout regulamentar no polling do Discord.

### Sprint 2: Enriquecimento de Storytelling & Prompts M1 a M8
* **Atividade 2.1 — M1 para as 10 Equipes do Grid:**
  * Arquivos: `src/ai_showrunner.py`, `src/canon_ledger.py`, `prompts/01_semana_equipes.md`.
  * Tarefa: Atualizar `generate_m1_daily_episode` para sortear temas e redigir o noticiário cobrindo o grid completo (incluindo Ferrari, Red Bull, McLaren, etc.), integrando as 12 verticais temáticas.
* **Atividade 2.2 — Submódulo M1.5 (Dilema Interativo de Paddock):**
  * Arquivos: `src/ai_showrunner.py`, `prompts/01b_dilema_paddock.md`, `src/discord_gateway.py`.
  * Tarefa: Criar prompt de geração de dilemas polarizados; disparar às quartas-feiras no `#geral`; pausar em `TURN_LOCKED` até resposta do jogador real; registrar a escolha no Canon Ledger.
* **Atividade 2.3 — M6 com NPCs e Áudios de Voz:**
  * Arquivos: `prompts/06_cerimonia_podio.md`, `src/ai_showrunner.py`.
  * Tarefa: Inserir no Ato 4 declarações dos NPCs de destaque da prova e conectar a transcrição de notas de voz enviadas no canal de debriefing.
* **Atividade 2.4 — M8 com Crônica de Corrida & Bancada de Lendas:**
  * Arquivos: `prompts/08_repercussao_midia.md`, `personas/alain_prost_ex_driver.md`, novas personas `personas/nigel_mansell.md` e `personas/jacques_villeneuve.md`.
  * Tarefa: Formatar a publicação no Discord em Bloco 1 (Crônica de Corrida estilo *L'Équipe/Autosport*) e Bloco 2 (Bancada de Lendas no formato *CBS Golazo Show* com Prost, Mansell e Villeneuve debatendo a pilotagem).

### Sprint 3: Camada de Dados NoSQL Local & Multi-Temporada
* **Atividade 3.1 — Camada de Abstração NoSQL Local:**
  * Arquivos: `src/db/repository.py` (usando `tinydb` ou `sqlite3` nativo em modo documento JSON).
  * Tarefa: Criar repositório atômico para leitura e gravação de `standings`, `canon_ledger`, `race_telemetry` e `press_conferences`, com transações seguras e rollback facilitado.
* **Atividade 3.2 — Parametrização Multi-Temporada (`season_id`):**
  * Arquivos: `src/orchestrator_cli.py`, `src/portal_builder.py`, `src/ai_showrunner.py`.
  * Tarefa: Substituir caminhos fixos `data/seasons/season_01/` pelo parâmetro dinâmico `data/seasons/{season_id}/`.
* **Atividade 3.3 — Motor de Storytelling de Dança das Cadeiras:**
  * Tarefa: Comparador de grid entre etapas/temporadas com disparo de anúncios de transferências de pilotos.

### Sprint 4: Portal Web Paddock Dark Mode & Homologação
* **Atividade 4.1 — Refatoração de Design do Portal Web:**
  * Arquivos: `src/portal_builder.py`, templates HTML/CSS.
  * Tarefa: Aplicar o design system *Paddock Dark Mode* (Slate `#0B131E`, FIA Navy `#1B365D`, F1 Red `#E10600`), navegação de abas para M1 a M8 e tabela responsiva com $\Delta$ de posições.
* **Atividade 4.2 — Testes Automatizados E2E:**
  * Arquivos: `tests/test_e2e_showrunner.py`.
  * Tarefa: Validar todo o fluxo automatizado da Etapa 11 (Áustria) antes da abertura para os pilotos reais.

---

## 4. Critérios de Aceite para Início da Execução (Definition of Ready)
- [x] Especificação funcional e técnica aprovada e comitada em `docs/ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx`.
- [x] Matriz de dependências de rede e pacotes de telemetria UDP 20777 validados e testados (`test_udp_relay.py` com exit code 0).
- [x] Chaves de API do Discord e Google AI Studio configuradas em `.env`.
- [x] Diretório `data/seasons/season_01/et_11_austria/` limpo e pronto para receber o novo ciclo.

