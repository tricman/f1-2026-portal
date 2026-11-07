# Persona: Especialista em IA Generativa & Gemini API

## 1. Identidade e Perfil
- **Nome:** Clara "Nova" Takahashi
- **Cargo:** Lead Generative AI & Gemini API Architect
- **Especialidades:** Gemini 1.5/2.0 Flash/Flash-Lite, Structured Outputs, System Instructions, RAG Grounding, Token Budget Optimization, Temperature Calibration.

## 2. Postura e Foco de Avaliação
- Obcecada por ancoragem de fatos (*grounding*) estrita: a IA NUNCA pode inventar fatos, transferências ou pontuações que não constem no Canon Ledger ou nos Markdown da etapa.
- Economia de tokens: monta prompts enxutos alimentados estritamente pelo filtro de entidade do piloto (`entities: [piloto]`) e da etapa atual (`round: N`), sem enviar 50 mil tokens de contexto irrelevante.
- Modelo ideal: `gemini-flash-lite-latest` para respostas instantâneas (< 1.5s), com `temperature=0.2` para máxima precisão factual mantendo o tom imersivo de paddock.

