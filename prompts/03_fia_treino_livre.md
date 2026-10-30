# MÓDULO #3: RELATÓRIO TÉCNICO OFICIAL DA FIA — TREINO LIVRE (FREE PRACTICE)

Atue como a **Delegação Técnica da FIA (Jo Bauer)** em conjunto com a **Secretaria Desportiva da FIA**.
Gere o **Relatório Oficial de Treino Livre** para o **{{GP_NAME}} (Etapa {{ROUND_NUMBER}})** utilizando **estritamente** os dados extraídos do PaceDex CSV injetados abaixo.

---

## 1. DADOS DE TELEMETRIA PACEDEX (FONTE DA VERDADE)
```json
{{FP_TELEMETRY_JSON}}
```

---

## 2. ESTRUTURA OBRIGATÓRIA DO DOCUMENTO (MARKDOWN)

### FEDERATION INTERNATIONALE DE L'AUTOMOBILE
#### {{GP_OFFICIAL_HEADER}} — OFFICIAL FREE PRACTICE TECHNICAL REPORT
**DOCUMENT REF:** `FIA-F1-2026-R{{ROUND_NUMBER}}-FP01` | **DELEGADO TÉCNICO:** Jo Bauer

#### 1. CLASSIFICAÇÃO OFICIAL DO TREINO LIVRE (FREE PRACTICE CLASSIFICATION)
Tabela Markdown completa (Pos | Nº | Piloto | Equipe | Voltas | Melhor Volta | Dif. Líder | Melhor S1 | Melhor S2 | Melhor S3 | Pits | Composto Final).

#### 2. ANÁLISE DE TELEMETRIA E PROGRAMAS DE PISTA (JO BAUER & ENGENHARIA)
- **Simulação de Classificação (Pneus Macios [S]):** Quem liderou em volta única, análise dos micro-setores (`S1`, `S2`, `S3`) e diferenças na frente.
- **Simulação de Ritmo de Corrida & Gestão de Carcaça (Pneus Médios [M] e Duros [H]):** Destaque a quilometragem acumulada (quem deu mais voltas, ex: Davi, Felipe, Sarah), quem escondeu o jogo (*sandbagging* com pneus Duros/Médios) e as taxas de desgaste (`Desgaste %`) observadas na telemetria do PaceDex.
- **Desempenho da *Brazilian Storm* (Sarah, Felipe e Davi):** Leitura técnica individualizada de cada um dos três brasileiros na sessão.

#### 3. BOLETIM DA DIREÇÃO DE PROVA (NIELS WITTICH)
Conformidade de Parque Fechado, evolução do emborrachamento da pista (*track evolution*) e notas de monitoramento de limites de pista para a sessão classificatória.

