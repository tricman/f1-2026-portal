# MÓDULO 1: ARQUITETURA, GATILHOS E ENGENHARIA DO PRÉ-GP (M1 · A SEMANA DA F1)

---

## 1. Visão Geral e Propósito do Módulo #1

O **Módulo #1 (M1 · A Semana da F1 / Especial Silly Season)** é o componente de **Storytelling Preditivo e Pré-Corrida** do ecossistema F1 Showrunner. Ele atua no intervalo entre o fim da corrida anterior ($N-1$) e o início das atividades de pista da próxima etapa ($N$).

Seu objetivo é **construir o drama, a rivalidade e o contexto político-técnico** antes que qualquer piloto humano (Felipe, Davi ou Sarah) acelere no simulador EA F1 24.

```mermaid
flowchart LR
    A["Etapa N-1 Finalizada<br/>(Tabela Standings & Canon Ledger)"] --> B["Gatilho Pré-Etapa<br/>(Discord / Cron / REST)"]
    B --> C["Motor de Grounding M1<br/>(RNG Seed + Fatos Reais)"]
    C --> D["Gemini IA Showrunner<br/>(Persona: Paddock Insiders)"]
    D --> E["ET(N)_PRE_A_Semana_da_F1.md<br/>(10 Equipes x 4 Dias)"]
    E --> F["Deploy Portal Mobile<br/>(tricman.github.io/f1-2026-portal)"]
    E --> G["Teaser #repercussao-midia<br/>(Discord Webhook)"]
```

---

## 2. Anatomia Narrativa do M1 (Segunda a Quinta-Feira)

O M1 simula o blog clandestino e respeitado de bastidores **"A F1 Que Você Não Vê"**, operado por um consórcio de informantes anônimos espalhados pelo globo:
* 🇬🇧 **The Paddock Mole** (Londres, Milton Keynes e Montreal)
* 🇮🇹 **Lady Paddock & Il Cavallino Spia** (Maranello, Mônaco e Faenza)
* 🇪🇸 **El Chisme de Montmeló** (Espanha e América Latina)
* 🇩🇪 **The Silver Bullet** (Brackley, Stuttgart e Hinwil)

### Estrutura Diária por Equipe (10 Construtores)
Para cada uma das 10 equipes da temporada 2026, o M1 detalha cronologicamente:

```
Segunda-feira ──► A Ressaca da Corrida Anterior & Crise de Telemetria
Terça-feira   ──► Festas VIP, Micos de Marketing & Sondagens Contratuais
Quarta-feira  ──► Pânico no Simulador, Fábrica & Negociações de Bastidores
Quinta-feira  ──► Desembarque no Paddock do Novo GP & Clima nas Hospitalidades
                   │
                   ▼
               SÍNTESE DOS INSIDERS (Pressão da Equipe)
                   │
                   ▼
               5 COMENTÁRIOS DE INTERNAUTAS (@fans, memes e ironias)
```

---

## 3. Matriz de Grounding Anti-Alucinação (Tríplice Camada)

Para evitar alucinações de IA e garantir que as intrigas façam sentido estrito com a realidade da liga, o gerador do M1 amarra:

| Camada | Fonte de Dados | Função no Módulo M1 |
| :--- | :--- | :--- |
| **1. Ground Truth Numérico** | `data/state/standings.json` | Pontuação real, posições exatas nos Construtores e Pilotos após a Etapa $N-1$. Proibido inventar dados de pontuação. |
| **2. Memória Canônica** | `data/state/canon_ledger.json` | Punições vigentes da FIA, toques de pista não resolvidos, disputas de contrato da *Brazilian Storm*. |
| **3. Sorteador RNG Determinístico** | `sample_weekly_themes(round, team)` | Sorteia 4 temas distintos por equipe sem repetição via semente matemática `season_2026_r{N}_{team_id}`. |

### Banco de Temas da Silly Season:
1. `Glamour & Celebridades`: Galas de luxo, iates, estreias e flagras com astros pop.
2. `Silly Season & Crise Contratual`: Reuniões secretas em motorhomes, multas rescisórias, sondagens.
3. `Treta & Vestiário`: Discussões vazadas por garçons em restaurantes VIP, climão no hospitality.
4. `Marketing & Mico Corporativo`: Vídeos de TikTok forçados, ativismos constrangedores de patrocinador.
5. `Entrevista Surpresa / Flagra de Tabloid`: Microfone aberto, áudios vazados de engenheiro.
6. `Preparação & Simulador`: Brigas de acerto na fábrica, turnos triplos de madrugada.

---

## 4. Quais são os Gatilhos do M1? (Como se Inicia o Pré)

O ciclo pré-corrida de uma nova etapa pode ser acionado por três caminhos complementares:

```mermaid
sequenceDiagram
    autonumber
    actor Piloto as Piloto (Discord)
    participant Gateway as Discord Gateway / Cloud Run
    participant Engine as AI Showrunner (M1 Engine)
    participant Portal as GitHub Pages / Discord Webhook

    alt Gatilho 1: Discord Chat (Canal de Voz / Admin)
        Piloto->>Gateway: Digita "pre etapa 11" ou "semana etapa 11"
        Gateway->>Engine: Dispara generate_pre_race_m1(11, "et_11_austria")
    else Gatilho 2: Transição Automática Pós-Etapa
        Note over Gateway,Engine: Após "final da etapa 10" e publicação de M8,<br/>o Cloud Run agenda/executa o M1 da etapa seguinte
    else Gatilho 3: API REST Direta (Cloud Run)
        Note over Gateway,Engine: POST /round/m1 { "round_num": 11 }
    end

    Engine->>Engine: Sorteia Temas RNG + Carrega Standings N-1 + Canon Ledger
    Engine->>Engine: Gemini Flash/Pro gera ET11_PRE_A_Semana_da_F1.md
    Engine->>Portal: Recompila index.html do Portal com deep link #r=11&m=...
    Engine->>Gateway: Envia Teaser com Persona "F1 Paddock Insider" no #repercussao-midia
    Gateway-->>Piloto: Notificação no Discord: "🚨 [M1 · PRÉ-SEMANA] ET11_PRE..."
```

### Gatilho A: Mensagem no Discord (Interativo)
No mesmo canal de voz `#1457392708355096580`:
* Comando: **`pre etapa <N>`** ou **`semana etapa <N>`**
* O bot identifica o comando via Regex, confirma o início da produção pré-GP e devolve a publicação no canal `#repercussao-midia`.

### Gatilho B: Encadeamento Autônomo Pós-Etapa
Na função `finalize_round_transition()`, logo após calcular a nova tabela da FIA e promover os pontos da Etapa $N-1$, o motor inicia automaticamente a síntese da Pré-Semana da Etapa $N$.

### Gatilho C: Endpoint HTTP (Cloud Run)
```bash
POST https://f1-showrunner-service-267450575916.southamerica-east1.run.app/round/m1
Content-Type: application/json

{
  "round_num": 11,
  "round_folder": "et_11_austria"
}
```

---

## 5. Próximo Passo na Linha do Tempo: Módulo #2 (Coletiva FIA)

Assim que o M1 é publicado:
1. Os pilotos leem as fofocas e os vazamentos da semana no Portal Mobile.
2. O **Módulo #2 (Coletiva de Imprensa Oficial da FIA - Quinta-feira)** entra em cena, convocando 5 a 6 pilotos para a bancada oficial (`prompts/02_coletiva_pre_gp.md`).
3. Os jornalistas confrontam diretamente os pilotos com base nos vazamentos revelados no M1!
4. Só então a sessão de pista é aberta com o comando `inicio da etapa <N>`.
