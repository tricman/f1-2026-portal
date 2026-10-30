# SAD v2.0 — F1 2026 Showrunner: Arquitetura 100% Autônoma (Custo Zero `R$ 0,00`)

> **Status:** Implementado | **Versão:** 2.0.0  
> **Autoria:** Marcus V. Silveira (*Principal Software Architect*) & Squad F1 Showrunner  
> **Pilar Central:** *Zero-Waste, Scale-to-Zero & Free-Tier Lock (`R$ 0,00`)*

---

## 1. Visão Geral da Solução Autônoma

A versão 2.0 elimina 100% da dependência do **Antigravity-IDE** ativo combinando três pilares a **Custo Zero (`R$ 0,00` e sem necessidade de cartão de crédito)**:

1. **Gatilho Automático via Discord (`--action autonomous-session --sentinel --max-hours 4` em [`src/orchestrator_cli.py`](../src/orchestrator_cli.py)):**
   - O workflow [`.github/workflows/f1_showrunner_session.yml`](../.github/workflows/f1_showrunner_session.yml) executa pulsos sentinela no Canal de Voz (`#1457392708355096580`).
   - Se ninguém enviou `inicio da etapa <N>`, o processo encerra em **2 segundos**.
   - Ao detectar `inicio da etapa <N>`, o runner **trava a sessão aberta por até 4 horas (`14.400s`)** com `concurrency: group: f1-discord-voice-session`, respondendo em tempo real a cada foto, CSV PaceDex e áudio/texto de debriefing enviado, até receber `final da etapa <N>`.
2. **Motor Multimodal Gemini (`gemini-3.8-flash` / `gemini-3.1-pro-preview` em [`src/ai_showrunner.py`](../src/ai_showrunner.py)):**
   - Usa a `GEMINI_API_KEY` gratuita do Google AI Studio (`Projeto: F1-Siimulator / gen-lang-client-0811633956` — mantido **sem faturamento** para travar o uso em `R$ 0,00`).
   - Executa OCR estruturado das fotos da TV (`extract_tv_overlay_from_photos`), transcrição de áudios `.ogg`/`.mp3` (`transcribe_audio_debriefs`), montagem da memória de *storytelling* em 3 camadas (`assemble_storytelling_context`), geração encadeada dos módulos `M3` a `M8` (`generate_post_race_modules`) e transição de estado entre etapas (`finalize_round_transition`).
3. **Persistência Git-as-a-Database & Portal Mobile (`tricman/f1-2026-portal`):**
   - Ao final da etapa, commita automaticamente `data/state/`, `data/seasons/` e o `index.html` do Portal Mobile no GitHub Pages e publica os Teasers com gráficos PNG em ordem cronológica (`M1 ➔ M3 ➔ M4 ➔ M5 ➔ M6 ➔ M7 ➔ M8`) no canal `#repercussao-midia`.
