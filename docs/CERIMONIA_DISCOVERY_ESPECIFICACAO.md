# Protocolo de Cerimônia: Discovery & EventStorming de Especificação Funcional
**Projeto:** Motor de Simulação F1 2026 (Showrunner & FIA Engine)  
**Padrão Metodológico:** Three Amigos Expandido / EventStorming (DDD) / Grill-Me Protocol  
**Documento Alvo:** `docs/ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx` (Modelo Word Corporativo)  
**Versão:** v1.0.0  
**Data:** 05/11/2026  

---

## 1. Propósito e Objetivos da Cerimônia

O objetivo desta cerimônia é alinhar, confrontar e validar exaustivamente todos os contratos funcionais, regras regulatórias desportivas da FIA, comportamento do bot no Discord e fluxos de dados de telemetria UDP (Módulos M1 a M8), garantindo que o documento final de **Especificação Funcional e Técnica de Sistema (EFS)** seja redigido sem ambiguidades, suposições incorretas ou omissões técnicas.

---

## 2. Composição da Mesa Técnica & Funcional (Personas Participantes)

A cerimônia é conduzida pela atuação coordenada de 6 papéis especializados:

| Persona | Categoria | Foco de Interrogação e Alinhamento |
| :--- | :--- | :--- |
| **Product Owner & Game Master (Showrunner)** | Funcional | Experiência de jogo dos pilotos reais (Felipe, Davi e Sarah), cadência de postagens, narrativa de bastidores, *Canon Ledger* e coerência da *Silly Season*. |
| **Auditor Desportivo & Diretor de Prova FIA** | Funcional / Compliance | Conformidade com o Regulamento Desportivo Internacional da FIA (sistema de pontos, volta mais rápida em P1-P10, critérios de desempate, penalidades de grid e tempo). |
| **Arquiteto de Integração & ChatOps (Discord)** | Técnica | Ciclo de vida do bot, polling com backoff adaptativo em `#geral`, publicação via webhooks em `#repercussao-midia`, timeout e persistência da **Trava de Turno**. |
| **Engenheiro de Telemetria & Sistemas UDP** | Técnica | Mapeamento dinâmico de pilotos em modo Grand Prix local vs. Multiplayer, desempacotamento binário de structs C (Codemasters F1 2024), taxas de amostragem e resiliência a nulos/DNF. |
| **Engenheiro de IA Generativa & Prompting** | Técnica | Isolamento estrito entre determinismo e criatividade, arquitetura de prompts de M1 a M8, controle de cotas (Free Tier Gemini) e persona técnica de **Alain Prost**. |
| **Arquiteto de Qualidade & Testes (QA / BDD)** | Técnica | Formalização dos critérios de aceite no padrão *Gherkin* (`Given-When-Then`), idempotência de processamento e planos de contingência. |

---

## 3. Dinâmica Operacional da Cerimônia (`/grill-me`)

A cerimônia opera sob o protocolo interativo sequencial (**uma decisão por vez**), percorrendo os quatro quadrantes do sistema:

```
                      ┌───────────────────────────────────────────────┐
                      │          QUADRANTE 1: CHATOPS & M1-M2         │
                      │  Interação no Discord, Trava de Turno e Canon │
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │          QUADRANTE 2: TELEMETRIA UDP          │
                      │ Mapeamento de Pilotos, Pacotes 4-11 e Sessão  │
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │          QUADRANTE 3: FIA & MECÂNICAS M3-M8   │
                      │   Invariantes Matemáticas e Papel do Gemini   │
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │          QUADRANTE 4: MODELO CORPORATIVO      │
                      │   Estrutura, Normas ABNT/ISO e Layout .docx   │
                      └───────────────────────────────────────────────┘
```

### Regras de Condução:
1. **Pergunta Única e Focada:** Uma pergunta por interação, eliminando sobrecarga cognitiva.
2. **Recomendação Embasada:** Cada pergunta traz uma resposta recomendada baseada no estado atual do código e nas regras de governança do projeto.
3. **Exploração Prévia do Código:** Perguntas cuja resposta já esteja resolvida no código ou nas definições de setup não são feitas ao usuário; apenas decisões de negócio ou regras não especificadas são levadas à mesa.
4. **Resolução de Dependências:** Decisões do Quadrante 1 alimentam as premissas dos Quadrantes seguintes.

---

## 4. Decisões Consolidadas na Cerimônia (/grill-me)

Durante a sessão interativa realizada em 05/11/2026, a Mesa Técnica e Funcional deliberou e aprovou as seguintes definições arquiteturais e de negócio:

1. **[M2 & Trava de Turno] Contingência de Pilotos Ausentes:**
   * Caso o tempo limite de resposta de um piloto humano (Felipe, Davi ou Sarah) expire, o sistema aciona a **Geração Sintética via IA**: o modelo Gemini assume temporariamente a persona do piloto ausente com base nos perfis canônicos oficiais (`Setup - Perfil Felipe/Davi/Sarah.md`), mantendo o realismo e evitando bloqueio indefinido da semana.
2. **[M1: Silly Season] Cadência Operacional Híbrida:**
   * A publicação dos 4 episódios diários (Segunda a Quinta) opera em **Modo Híbrido**: disparo agendado (Cron) nos horários pré-definidos ao longo da semana real, combinado com comandos manuais sob demanda (`avancar dia`, `publicar semana completa`) para controle operacional flexível do organizador.
3. **[UDP & Sessões de Pista] Máquina de Estados Finitos (FSM) Contínua:**
   * O listener local opera como daemon contínuo na porta `20777`, identificando automaticamente as transições de sessão via campo `m_sessionType` dos datagramas da Codemasters (Treino Livre $\rightarrow$ Classificação $\rightarrow$ Corrida) e acionando o processamento de M3, M4 e M5 automaticamente ao final de cada sessão.
4. **[Resolução de Grid] Modalidade Operacional Canônica:**
   * O ecossistema de simulação oficial é **sempre o Grand Prix Multiplayer Online** (onde os 3 pilotos competem simultaneamente). A execução em modo *Grand Prix Local* (contra 19 IAs) foi restrita ao teste piloto isolado de validação de rede.
5. **[FIA & Apuração de Resultados] Sistema Híbrido Auditado:**
   * As punições desportivas de tempo e limites de pista registradas pelo simulador são somadas diretamente na classificação oficial (M5), enquanto sanções administrativas complementares (perda de pontos de construtores, investigações pós-corrida e reprimendas disciplinares) são registradas pelo Diretor de Prova no `canon_ledger.json` e incorporadas no cálculo oficial de M7.
6. **[M8: Paddock & Alain Prost] Distribuição Segmentada no Discord:**
   * A entrega no canal `#repercussao-midia` é dividida em dois blocos distintos: Bloco 1 com a *Crônica Técnica & Notas de Pilotagem de Alain Prost* (notas de 0 a 10 baseadas em telemetria mecânica) e Bloco 2 com a *Cobertura Editorial Internacional & Imprensa Brasileira*.
7. **[Diretriz do Documento Word] Bipartição Funcional & Técnica:**
   * A entrega corporativa contemplará duas partes integradas: uma **Especificação Funcional** estritamente orientada ao negócio e jornadas dos pilotos, e uma **Especificação Técnica** exaustiva cobrindo protocolos de rede, contratos de dados, invariantes e engenharia de software.

---

## 5. Critérios de Saída (Definition of Done da Cerimônia)

- [x] 100% das decisões de negócio e regras de fluxo do Discord aprovadas pelo usuário.
- [x] Comportamento da telemetria UDP (modo Grand Prix multiplayer oficial) delimitado.
- [x] Critérios de pontuação, contingência de falhas e Trava de Turno definidos.
- [x] Geração do documento Word `docs/ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx`.
