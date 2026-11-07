# Auditoria Oficial de Pontuação — Temporada 2026 (Etapas 1 a 9)

> **Data da Auditoria:** 2026-10-29  
> **Escopo:** Reconciliação matemática integral dos Relatórios Oficiais de Corrida (ET1 a ET9) vs. Tabelas do NotebookLM ([00_INDEX_CANON_TEMPORADA_2026.md](file:///c:/Users/tricm/.gemini/antigravity-ide/scratch/f1-simulator/data/setup/00_INDEX_CANON_TEMPORADA_2026.md)).  
> **Regra de Pontuação:** $P_1..P_{10} = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]$ + $1\text{ pt}$ de Volta Mais Rápida (se classificado no Top 10).

---

## 1. Matriz Corrida a Corrida — Mundial de Pilotos (ET1 a ET9)

| Pos Real | Piloto | Equipe | ET1 BH | ET2 AS | ET3 AU | ET4 JP | ET5 CN | ET6 MI | ET7 IM | ET8 MC | ET9 CA | **Total Real** | **Total Notebook** | **Delta** |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1º** | **Sarah** 🇧🇷 | Mercedes-AMG | **26*** | 0 | **25** | **26*** | **25** | 18 | **26*** | 0 (DSQ) | **25** | **171** | 171 | `0` ✅ |
| **2º** | **Felipe** 🇧🇷 | KICK Sauber | 0 | **26*** | 19* | 12 | 18 | **26*** | 15 | 0 (NC) | 15 | **131** | 131 | `0` ✅ |
| **3º** | **Fernando Alonso** 🇪🇸 | Aston Martin | 0 | 15 | 6 | 18 | 6 | 12 | 12 | **25** | 10 | **104** | 104 | `0` ✅ |
| **4º** | **Lewis Hamilton** 🇬🇧 | Mercedes-AMG | 15 | 18 | 2 | 8 | 8 | 6 | 10 | 18 | 12 | **97** | 97 | `0` ✅ |
| **5º** | **Max Verstappen** 🇳🇱 | Red Bull Racing | 12 | 10 | 15 | 10 | 10 | 10 | 8 | 15 | 4 | **94** | 94 | `0` ✅ |
| **6º** | **Charles Leclerc** 🇲🇨 | Scuderia Ferrari | 10 | 12 | 8 | 4 | 15 | 2 | 18 | 6 | 8 | **83** | 83 | `0` ✅ |
| **7º** | **Davi** 🇧🇷 | Williams Racing | 18 | 0 | 0 | 0 | 13* | 15 | 0 | 0 | 19* | **65** | 66 | **`+1` ⚠️** |
| **8º** | **Lando Norris** 🇬🇧 | McLaren | 1 | 8 | 10 | 15 | 4 | 1 | 2 | 12 | 6 | **59** | 59 | `0` ✅ |
| **9º** | **Oscar Piastri** 🇦🇺 | McLaren | 6 | 4 | 12 | 6 | 1 | 4 | 6 | 10 | 2 | **51** | 51 | `0` ✅ |
| **10º** | **Sergio Pérez** 🇲🇽 | Red Bull Racing | 8 | 6 | 4 | 1 | 0 | 8 | 4 | 8 | 0 | **39** | 39 | `0` ✅ |
| **11º** | **Carlos Sainz** 🇪🇸 | Scuderia Ferrari | 4 | 1 | 1 | 2 | 2 | 0 | 0 | 4 | 1 | **15** | 15 | `0` ✅ |
| **12º** | **Pierre Gasly** 🇫🇷 | BWT Alpine | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | **6** | 6 | `0` ✅ |
| **13º** | **Nico Hülkenberg** 🇩🇪 | MoneyGram Haas | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | **1** | 1 | `0` ✅ |
| **14º** | **Lance Stroll** 🇨🇦 | Aston Martin | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | **1** | 1 | `0` ✅ |
| **15º–20º** | *Albon, Tsunoda, Ocon, Ricciardo, Bottas, Magnussen* | *Demais Equipes* | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0 | `0` ✅ |

*\*Inclui $+1\text{ ponto}$ bônus pela Volta Mais Rápida da corrida.*

### Causa-Raiz da Divergência no Mundial de Pilotos:
* **Davi (+1 pt no NotebookLM):** Na [Etapa 5 (China)](file:///c:/Users/tricm/.gemini/antigravity-ide/scratch/f1-simulator/data/seasons/season_01/et_05_china/Etapa%205%20-%20P%C3%B3s%20%20-%20Clasifica%C3%A7%C3%A3o%20Campeonato%20de%20Pilotos.md#L81), Davi tinha $18\text{ pts}$ (do P2 no Bahrein) e somou $13\text{ pts}$ (P4 + Volta Mais Rápida). A soma correta era $18 + 13 = 31\text{ pts}$, porém o LLM registrou **$32\text{ pts}$**. Nas etapas seguintes somou corretamente ($+15$ em Miami $= 47$; $+19$ no Canadá $= 66$, quando o real é **$65\text{ pts}$**).

---

## 2. Matriz Corrida a Corrida — Mundial de Construtores (ET1 a ET9)

| Pos Real | Construtor (Pilotos) | ET1 BH | ET2 AS | ET3 AU | ET4 JP | ET5 CN | ET6 MI | ET7 IM | ET8 MC | ET9 CA | **Total Real** | **Total Notebook** | **Delta** |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1º** | **Mercedes-AMG Petronas** (*Sarah + Hamilton*) | 41 | 18 | 27 | 34 | 33 | 24 | 36 | 18 | 37 | **268** | 268 | `0` ✅ |
| **2º** | **Red Bull Racing** (*Verstappen + Pérez*) | 20 | 16 | 19 | 11 | 10 | 18 | 12 | 23 | 4 | **133** | 123 | **`-10` ⚠️** |
| **3º** | **Stake F1 Team Kick Sauber** (*Felipe + Bottas*) | 0 | 26 | 19 | 12 | 18 | 26 | 15 | 0 | 15 | **131** | 132 | **`+1` ⚠️** |
| **4º** | **McLaren Formula 1 Team** (*Norris + Piastri*) | 7 | 12 | 22 | 21 | 5 | 5 | 8 | 22 | 8 | **110** | 110 | `0` ✅ |
| **5º** | **Aston Martin Aramco** (*Alonso + Stroll*) | 0 | 15 | 6 | 18 | 6 | 12 | 13 | 25 | 10 | **105** | 108 | **`+3` ⚠️** |
| **6º** | **Scuderia Ferrari HP** (*Leclerc + Sainz*) | 14 | 13 | 9 | 6 | 17 | 2 | 18 | 10 | 9 | **98** | 107 | **`+9` ⚠️** |
| **7º** | **Williams Racing** (*Davi + Albon*) | 18 | 0 | 0 | 0 | 13 | 15 | 0 | 0 | 19 | **65** | 62 | **`-3` ⚠️** |
| **8º** | **BWT Alpine F1 Team** (*Gasly + Ocon*) | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | **6** | 6 | `0` ✅ |
| **9º** | **MoneyGram Haas F1 Team** (*Hülkenberg + Magnussen*) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | **1** | 1 | `0` ✅ |
| **10º** | **Visa Cash App RB** (*Tsunoda + Ricciardo*) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0 | `0` ✅ |

### Causa-Raiz das Divergências nos Construtores (O "Bug de Melbourne" na Etapa 3):
Ao gerar o documento [Etapa 3 - 15_08 - Classificação Construtores Atualizada.md](file:///c:/Users/tricm/.gemini/antigravity-ide/scratch/f1-simulator/data/seasons/season_01/et_03_australia/Etapa%203%20-%2015_08%20-%20Classifica%C3%A7%C3%A3o%20Construtores%20Atualizada.md#L16-L22), o LLM embaralhou as colunas de pontuação das Etapas 1 (Bahrein) e 2 (Arábia Saudita) entre cinco equipes:
1. **Sauber (`+1 pt`):** Recebeu os pontos da Ferrari das Etapas 1 e 2 ($14 + 13 = 27$) em vez dos seus próprios ($0 + 26 = 26$).
2. **Red Bull (`-10 pts`):** Recebeu os pontos da Sauber das Etapas 1 e 2 ($0 + 26 = 26$) em vez dos seus próprios ($20 + 16 = 36$).
3. **Ferrari (`+9 pts`):** Recebeu os pontos da Red Bull das Etapas 1 e 2 ($20 + 16 = 36$) em vez dos seus próprios ($14 + 13 = 27$).
4. **Aston Martin (`+3 pts`) e Williams (`-3 pts`):** Tiveram seus pontos das Etapas 1 e 2 invertidos entre si ($18$ do Davi no Bahrein foi parar na Aston Martin, e $15$ do Alonso em Jeddah foi parar na Williams).
5. Da Etapa 4 até a Etapa 9, o LLM somou corretamente os pontos de cada corrida em cima da base corrompida da Etapa 3, perpetuando os deltas (`-10`, `+1`, `+3`, `+9`, `-3`).

