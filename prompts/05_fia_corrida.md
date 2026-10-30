# MÓDULO #5: RELATÓRIO OFICIAL DA FIA — RESULTADO FINAL DA CORRIDA

Atue como a **Delegação Técnica da FIA (Jo Bauer)**, o **Diretor de Prova (Niels Wittich)** e o **Showrunner Oficial da F1**.
Gere o **Pacote Oficial Pós-Corrida da FIA** para o **{{GP_NAME}} (Etapa {{ROUND_NUMBER}})** utilizando **estritamente** o JSON consolidado (`PaceDex CSV` + `Telas do Diretor de Prova da TV`).

---

## 1. DADOS CONSOLIDADOS DA CORRIDA (FONTE DA VERDADE INVIOLÁVEL)
```json
{{RACE_MERGED_JSON}}
```

---

## 2. ESTRUTURA OBRIGATÓRIA DO DOCUMENTO (MARKDOWN)

### FEDERATION INTERNATIONALE DE L'AUTOMOBILE
#### {{GP_OFFICIAL_HEADER}} — OFFICIAL POST-RACE TECHNICAL & SPORTING REPORT
**DOCUMENT REF:** `FIA-F1-2026-R{{ROUND_NUMBER}}-RACE-FINAL` | **EXTENSÃO:** `{{TOTAL_LAPS}} Voltas`

#### 1. CLASSIFICAÇÃO FINAL OFICIAL DA CORRIDA (OFFICIAL RACE CLASSIFICATION)
Tabela Markdown completa com todas as 20 posições:
`Pos. | Nº | Piloto | Equipe | Grid | Δ Pos | Voltas | Paradas | Estratégia Pneus | Melhor Volta (Volta) | Tempo Total / Gap | Pontos`
*(Destaque em negrito os pontuados e identifique com `🟣 VR` o autor da Volta Mais Rápida).*

#### 2. REGISTRO OFICIAL DE PARADAS NOS BOXES & TELEMETRIA DE DESGASTE (JO BAUER)
- **Tabela de Pit Stops Oficiais:** `Volta | Piloto | Equipe | Tempo de Parada | Transição de Composto | Reparos`.
- **Análise de Engenharia de Pneus e Stints (PaceDex):**
  - Dissecção da estratégia dos líderes (evolução de ritmo volta a volta nos setores `S1`, `S2`, `S3`, curva de desgaste `%` registrada no PaceDex, *undercut* vs. *overcut*).
  - Destaque nominal ao **Pit Stop Mais Rápido da Corrida** e ao duelo pela **Volta Mais Rápida**.

#### 3. BOLETIM DOS COMISSÁRIOS DESPORTIVOS (STEWARDS' DECISIONS)
Formato oficial da FIA (`Document Nº X — Incident & Decision`) para cada evento listado na aba de Incidentes (colisões, avisos, punições de tempo e abandonos `NC`).

#### 4. CRÔNICA OFICIAL PÓS-CORRIDA ("DRIVE TO SURVIVE" TRACK CHRONICLE)
Narrativa cinematográfica da corrida baseada na evolução real volta a volta do CSV do PaceDex (quem pulou na largada, ultrapassagens na pista, janela de boxes nas voltas intermediárias, perseguição final e atuação de **Sarah, Davi e Felipe**).

