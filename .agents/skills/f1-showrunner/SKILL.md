---
name: f1-showrunner
description: Orquestra a temporada do simulador EA F1 24 (Felipe, Davi e Sarah), fundindo CSVs de telemetria PaceDex com fotos das 4 abas da TV, calculando a tabela oficial da FIA e gerando os 8 módulos narrativos para o Discord e NotebookLM.
---

# F1 24 Showrunner & FIA Engine Skill

Use esta skill sempre que o usuário enviar novas fotos da TV, arquivos `.csv` do **PaceDex**, ou solicitar qualquer um dos **8 Módulos de Simulação** de uma etapa da temporada 2026.

## 1. Fluxo Operacional de uma Etapa (8 Módulos)

1. **Módulo #1 — Semana das Equipes (`prompts/01_semana_equipes.md`):**
   - Sorteie 4 temas distintos via `src.canon_ledger.sample_weekly_themes(round_number, team_id)` (Segunda a Quinta).
   - Consuma o resultado da etapa anterior e os eventos abertos em `data/state/canon_ledger.json`.
2. **Módulo #2 — Coletiva FIA Pré-Etapa (`prompts/02_coletiva_pre_gp.md`):**
   - Escale 5–6 pilotos via `src.canon_ledger.select_press_conference_panel()`.
   - Repercuta diretamente os vazamentos gerados no Módulo #1.
   - Em modo interativo, respeite a **Trava de Turno** (`[Pergunta X de Y | Microfone direcionado para...]`).
3. **Módulo #3 — Report FIA Treino Livre (`prompts/03_fia_treino_livre.md`):**
   - Processe os arquivos `pacedex_*_TL.csv` e `pacedex_*_laps_TL.csv` via `src.telemetry_merger.parse_free_practice_summary()`.
4. **Módulo #4 — Report FIA Classificação & Grid (`prompts/04_fia_classificacao.md`):**
   - Gere a classificação e o Grid Final de Largada (`GRID` extraído da aba `RESULTADOS (GERAL)`).
5. **Módulo #5 — Report FIA Resultado Final da Corrida (`prompts/05_fia_corrida.md`):**
   - Funda o `pacedex_*.csv` + `pacedex_*_laps.csv` com os dados das 4 telas da TV (`tv_overlay_etXX.json`) usando `src.telemetry_merger.merge_race_telemetry()`.
6. **Módulo #6 — Cerimônia do Pódio & Bastidores (`prompts/06_cerimonia_podio.md`):**
   - Gere os 4 Atos (*Parc Fermé*, *Cooldown Room*, *Pódio* e *Zona Mista / Motorhomes*).
7. **Módulo #7 — Boletim FIA Mundial de Pilotos e Construtores (`prompts/07_fia_mundial.md`):**
   - **Proibido somar pontos manualmente.** Execute `src.fia_calculator.update_championship_standings()` para obter o JSON auditado e gere o boletim oficial.
8. **Módulo #8 — Repercussão na Imprensa e Internet (`prompts/08_repercussao_midia.md`):**
   - Gere os 4 Blocos (*Imprensa Internacional*, *Imprensa Brasileira*, *YouTube/Podcasts* e *Termômetro da Internet*).

## 2. Comandos de Verificação, Deploy do Portal e Publicação no Discord
- **Rodar suíte de testes SDET:**
  `python -m unittest discover -s tests -v`
- **Sincronizar fotos/CSVs enviados no Canal de Voz (`1457392708355096580`):**
  `python -m src.orchestrator_cli --action sync-ingest --round-folder et_11_austria`
- **Compilar e fazer Deploy Automático do Portal Editorial no GitHub Pages (`https://tricman.github.io/f1-2026-portal/`):**
  `python -m src.orchestrator_cli --action deploy-portal`
- **Publicar Teaser Executivo (Zero-Scroll + PNGs + Deep Link do Portal) no `#repercussao-midia` (`1536416375969685524`):**
  `python -m src.orchestrator_cli --action publish-teaser --file "<caminho_relatorio.md>"`
- **Publicar todos os módulos de uma etapa (Deploy do Portal + Teasers no Discord):**
  `python -m src.orchestrator_cli --action publish-round --round-folder et_11_austria`

