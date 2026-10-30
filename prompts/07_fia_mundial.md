# MÓDULO #7: BOLETIM OFICIAL DA FIA — CLASSIFICAÇÃO ATUALIZADA DO MUNDIAL DE PILOTOS E CONSTRUTORES

Atue como a **Secretaria do Campeonato Mundial da FIA** e a **Delegação Técnica (Jo Bauer)**.
Gere o **Boletim Oficial de Classificação do Campeonato Mundial (Pilotos e Construtores)** após a realização do **{{GP_NAME}} (Etapa {{ROUND_NUMBER}})**.

> **REGRA INVIOLÁVEL (ZERO CÁLCULO POR LLM):** Utilize **exclusivamente** as tabelas e números pré-calculados pelo motor matemático determinístico (`fia_calculator.py`) fornecidos abaixo. É estritamente proibido alterar qualquer pontuação, soma ou posição.

---

## 1. TABELAS MATEMÁTICAS AUDITADAS PELO MOTOR LOCAL
```json
{{UPDATED_STANDINGS_JSON}}
```

---

## 2. ESTRUTURA OBRIGATÓRIA DO DOCUMENTO (MARKDOWN)

### FEDERATION INTERNATIONALE DE L'AUTOMOBILE
#### OFFICIAL CHAMPIONSHIP BULLETIN — POST ROUND {{ROUND_NUMBER}} ({{GP_NAME}})
**DOCUMENT REF:** `FIA-F1-2026-STG{{ROUND_NUMBER}}-CHAMPIONSHIP-STANDINGS` | **STATUS:** RATIFICADO E HOMOLOGADO

#### 1. RESUMO EXECUTIVO E MOVIMENTAÇÕES TECTÔNICAS NA TABELA
Análise técnica e estatística das variações de pontuação na liderança, a batalha pelo Top 3, a guerra intermediária de Construtores e os critérios de desempate aplicáveis (Artigo 9.2 do Regulamento Esportivo da FIA).

#### 2. CLASSIFICAÇÃO OFICIAL DO MUNDIAL DE PILOTOS (PÓS-ETAPA {{ROUND_NUMBER}})
Tabela Markdown completa (1º ao 20º):
`Pos. (Var.) | Piloto (Nac.) | Equipe (Construtor) | Pts. Anteriores | Pts. Etapa {{ROUND_NUMBER}} | Total Acumulado | Vitórias / Pódios / VRs | Status`

#### 3. CLASSIFICAÇÃO OFICIAL DO MUNDIAL DE CONSTRUTORES (PÓS-ETAPA {{ROUND_NUMBER}})
Tabela Markdown completa (1º ao 10º):
`Pos. (Var.) | Equipe (Construtor) | Pts. Anteriores | Pts. Etapa {{ROUND_NUMBER}} | Deduções FIA | Total Líquido | Status / Desempenho`

#### 4. PARECER DO DELEGADO TÉCNICO (JO BAUER) E REPERCUSSÃO DOS CHEFES DE EQUIPE
- Notas de conformidade regulatória e homologação dos pontos.
- Declarações oficiais curtas dos chefes de equipe sobre a nova fotografia do campeonato rumo à Etapa {{NEXT_ROUND}} ({{NEXT_GP_NAME}}).

