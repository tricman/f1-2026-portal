# Plano de Implementação: Arquitetura de Observabilidade & Logs em Modo TRACE

**Sistema:** F1 2026 Showrunner Engine (EA Sports F1 24 League)  
**Autor:** Beatriz "Beat" Ramos (Lead Observability & Telemetry Architect)  
**Status:** Planejado e Alinhado via `/grill-me`  
**Data:** Novembro de 2026  
**Versão:** 1.0  

---

## 1. Visão Geral e Objetivos Arquiteturais

A integridade do F1 Showrunner depende de fluxos assíncronos e pipelines determinísticas complexas: ingestão de pacotes UDP/CSVs PaceDex, OCR de telas de TV via visão computacional, chamadas com retry ao Gemini Flash/Pro, transações ACID em banco SQLite (WAL) e interações em tempo real com travas de turno no Discord.

Este plano introduz uma **Camada Unificada de Observabilidade de Alta Resolução** com suporte nativo ao nível **TRACE**, provendo rastreabilidade forense ponta a ponta sem degradação de desempenho no ambiente Windows on-premise.

### Pilares Fundamentais:
1. **Segregação de Canais de Log:**
   - `logs/showrunner.log`: Registros operacionais de alto nível (`INFO`, `WARNING`, `ERROR`).
   - `logs/trace.log`: Dumps completos de depuração em formato **JSON Lines (`.jsonl`)** com rotação por tamanho (20 MB / 5 arquivos) e política de expurgo periódico (*purge*).
2. **Context Tracing & Correlation ID Nativo (Zero Dependências Externas):**
   - Propagação de `trace_id`, `span_id` e `parent_span_id` via módulo padrão `contextvars`.
   - Decorador `@trace_span(name)` para cronometragem precisa (`duration_ms`), captura de argumentos/retornos e metadados contextuais (round, etapa, driver).
3. **Instrumentação Profunda em 4 Camadas Críticas:**
   - **IA / LLM (Gemini):** Prompts integrais, system instructions, payloads de resposta, contagem de tokens estimada, tempos de round-trip e contadores de retry.
   - **Discord Gateway:** Payloads brutos de eventos recebidos, headers de rate-limit, requests REST e fragmentação de mensagens.
   - **Telemetria / Visão:** Parsing detalhado linha a linha de CSVs do PaceDex, mapeamento OCR de TV e cálculo dos deltas do campeonato FIA.
   - **Camada de Dados (SQLite NoSQL):** Queries SQL executadas, parâmetros vinculados, tempos de transação e status de locks em modo WAL.
4. **Controle Híbrido de Ativação:**
   - Estático via arquivo `.env` (`LOG_LEVEL=TRACE`) e flag de CLI `--trace`.
   - Dinâmico em tempo de execução via ChatOps no Discord (`ativar trace` e `desativar trace`).
5. **Sanitização de Segredos (Redaction) & Rotina de Purge:**
   - Filtro de regex interceptor que mascara tokens sensíveis (`GEMINI_API_KEY`, `DISCORD_BOT_TOKEN`, Authorization Headers).
   - Rotina automatizada e comando CLI `--action purge-logs [--days N]` para retenção higiênica de disco.

---

## 2. Estrutura de Diretórios e Componentes

```
f1-simulator/
├── logs/
│   ├── showrunner.log              # Logs operacionais (INFO, WARN, ERROR)
│   ├── trace.log                   # Log ativo em JSON Lines com modo TRACE
│   └── trace.log.1..5              # Backups rotacionados (máx 20MB cada)
├── personas/
│   └── observability_specialist.md # Persona: Beatriz "Beat" Ramos
├── src/
│   ├── logger.py                   # Motor de log estendido (TRACE, JSON Lines, Rotação e Redaction)
│   ├── tracer.py                   # Engine de Tracing (contextvars, @trace_span, Correlation IDs)
│   ├── ai_showrunner.py            # Instrumentação Gemini (prompts, latências e tokens)
│   ├── discord_gateway.py          # Instrumentação Discord REST e Webhooks
│   ├── telemetry_merger.py         # Instrumentação de fusão PaceDex e OCR
│   ├── repositories/
│   │   └── sqlite_document_repository.py # Instrumentação de queries e transações SQLite
│   ├── chatops_listener.py         # Comandos dinâmicos 'ativar trace' / 'desativar trace'
│   └── orchestrator_cli.py         # Flags --trace e ação --action purge-logs
└── tests/
    └── test_observability_trace.py # Suíte de testes automatizados de observabilidade
```

---

## 3. Detalhamento dos Sprints de Implementação

### Sprint O1: Motor Central de Tracing, Rotação e Sanitização
* **Objetivo:** Estabelecer a infraestrutura de baixo nível para emissão de logs estruturados em formato JSON Lines, gerenciamento de contexto assíncrono e proteção contra vazamento de credenciais.
* **Tarefas Técnicas:**
  1. **Criação de `src/tracer.py`:**
     - Implementar gerenciador de contexto baseado em `contextvars.ContextVar`.
     - Definir gerador de `trace_id` (UUIDv4 compacto) e gerador hierárquico de `span_id`.
     - Criar o decorador `@trace_span(name, extract_args=True)` que computa `start_time`, `end_time` e `duration_ms`.
  2. **Refatoração de `src/logger.py`:**
     - Adicionar nível `TRACE` (valor numérico 5, abaixo de `DEBUG` 10 e `INFO` 20).
     - Configurar `RotatingFileHandler` para `logs/trace.log` (limite de 20 MB por arquivo, até 5 backups).
     - Implementar sanitizador regex para mascaramento de segredos: chaves terminadas em `_KEY`, `_TOKEN`, valores correspondentes às variáveis do `.env` e padrões de chave Gemini (`AIza...`).
     - Adicionar função `trace(message, event=None, details=None, **kwargs)`.
  3. **Rotina de Purge:**
     - Implementar função `purge_old_trace_logs(logs_dir, max_days=7, force=False)` que expurga arquivos rotacionados obsoletos.
  4. **Testes Unitários:**
     - Criar `tests/test_observability_trace.py` validando propagação de `trace_id`, rotação de arquivos, redaction de API keys e rotina de purge.

---

### Sprint O2: Instrumentação Profunda das 4 Camadas Críticas
* **Objetivo:** Plugar os spans de tracing e logs detalhados nos módulos vitais do sistema.
* **Tarefas Técnicas:**
  1. **Camada 1 — IA Showrunner (`src/ai_showrunner.py`):**
     - Instrumentar `GeminiFreeTierClient._call_generate_content`:
       - Emissão de log `TRACE` com payload bruto do prompt antes do disparo.
       - Captura do tempo de resposta (RTT) em milissegundos.
       - Registro do payload de resposta, estimativa de tokens gerados e headers de cota.
  2. **Camada 2 — Discord Gateway (`src/discord_gateway.py`):**
     - Instrumentar `publish_markdown_report`, `post_channel_message` e listener de mensagens.
     - Registro de status HTTP, tempo de resposta da API do Discord, divisão de chunks e IDs das mensagens geradas.
  3. **Camada 3 — Telemetria & TV OCR (`src/telemetry_merger.py` e `src/fia_calculator.py`):**
     - Rastreamento dos arquivos CSV carregados, contagem de voltas processadas e detecção de pilotos na TV Overlay.
     - Log detalhado de cada cálculo de pontuação e deltas de posição no encerramento da corrida.
  4. **Camada 4 — Repositório SQLite NoSQL (`src/repositories/sqlite_document_repository.py`):**
     - Instrumentar execuções de queries SQL, tempo de escrita na tabela de documentos, locks de transação WAL e sincronização bidirecional de JSON.

---

### Sprint O3: Ativação Híbrida (CLI + ChatOps Discord) e Homologação
* **Objetivo:** Disponibilizar os controles operacionais para o operador humano no terminal e pilotos no Discord.
* **Tarefas Técnicas:**
  1. **Controle na CLI (`src/orchestrator_cli.py`):**
     - Adicionar flag global `--trace` que força `LOG_LEVEL=TRACE` durante a execução do comando.
     - Adicionar ação `--action purge-logs [--days 7]` para manutenção manual ou agendada dos arquivos de log.
  2. **Controle no ChatOps (`src/chatops_listener.py`):**
     - Implementar detecção de comandos no chat `#geral`:
       - `ativar trace` / `ligar trace`: Comuta o nível ativo para `TRACE` e confirma no canal.
       - `desativar trace` / `desligar trace`: Retorna o nível para `INFO`.
       - `limpar logs` / `purge logs`: Executa a rotina de limpeza de logs rotacionados antigos.
  3. **Validação E2E e Documentação:**
     - Adicionar cenários de teste em `tests/test_observability_trace.py` cobrindo o fluxo dinâmico de ativação/desativação.
     - Atualizar o Manual de Operações DOCX com a nova seção de Observabilidade e Diagnóstico via TRACE.

---

## 4. Esquema Estruturado do Log TRACE (`logs/trace.log`)

Cada linha gravada em `logs/trace.log` será um objeto JSON estritamente tipado:

```json
{
  "timestamp": "2026-11-06T20:15:30.123456Z",
  "severity": "TRACE",
  "service": "f1-showrunner",
  "trace_id": "a8f3b9c2-10d4-4e89",
  "span_id": "span_7f1c4a",
  "parent_span_id": "span_root",
  "span_name": "gemini_generate_m1",
  "duration_ms": 1420.5,
  "round": 11,
  "stage": "pre_race_m1",
  "event": "LLM_REQUEST_DISPATCH",
  "details": {
    "model": "gemini-flash-latest",
    "prompt_bytes": 4820,
    "prompt_preview": "## DIRETRIZES DA FIA...",
    "response_chars": 3410,
    "http_status": 200,
    "retry_attempt": 1
  }
}
```

---

## 5. Matriz de Risco & Mitigações

| Risco Identificado | Impacto | Mitigação Técnica |
| :--- | :--- | :--- |
| **Crescimento Descontrolado do Disco** | Esgotamento do armazenamento local em corridas longas. | Rotação automática configurada para 20 MB com no máximo 5 arquivos de histórico (teto de 100 MB) + rotina de *purge*. |
| **Degradação de Desempenho (I/O Bottleneck)** | Latência nas respostas do Discord ou na ingestão UDP. | Gravação síncrona com buffers de escrita do Python e execução de dumps pesados em blocos atômicos. |
| **Vazamento de Chaves de API no Log** | Exposição de credenciais sensíveis em artefatos de log. | Interceptor de sanitização obrigatório baseado em expressões regulares executado antes de qualquer escrita no stream. |

