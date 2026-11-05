"""
Script para geração automatizada da Especificação Funcional e Técnica de TI (EFS/ETS)
do Motor de Simulação F1 2026 (Showrunner & FIA Engine).
Gera o documento corporativo docs/ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx.
"""
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "ESPECIFICACAO_FUNCIONAL_SHOWRUNNER_F1.docx"

# Paleta Corporativa
COLOR_NAVY = RGBColor(27, 54, 93)      # #1B365D - FIA Navy
COLOR_RED = RGBColor(225, 6, 0)        # #E10600 - F1 Racing Red
COLOR_DARK = RGBColor(43, 43, 43)      # #2B2B2B - Charcoal Text
COLOR_GRAY = RGBColor(110, 110, 110)   # #6E6E6E - Muted Subtitle
HEX_NAVY = "1B365D"
HEX_RED = "E10600"
HEX_LIGHT_BG = "F4F6F8"
HEX_BORDER = "CCCCCC"


def set_cell_background(cell, hex_color: str):
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for margin_name, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(margin_name)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_callout(doc, text: str, title: str = "NOTA TÉCNICA / INVARIANTE"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, HEX_LIGHT_BG)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    # Borda esquerda grossa vermelha
    tcPr = cell._tc.get_or_add_tcPr()
    borders_xml = (
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:left w:val="single" w:sz="36" w:space="0" w:color="{HEX_RED}"/>'
        f'  <w:top w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'  <w:bottom w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(parse_xml(borders_xml))

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"📌 {title}: ")
    run_t.bold = True
    run_t.font.name = "Arial"
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = COLOR_NAVY

    run_b = p.add_run(text)
    run_b.font.name = "Arial"
    run_b.font.size = Pt(9.5)
    run_b.font.color.rgb = COLOR_DARK
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def style_table_header(row, col_widths=None):
    for idx, cell in enumerate(row.cells):
        set_cell_background(cell, HEX_NAVY)
        set_cell_margins(cell, top=120, bottom=120, left=150, right=150)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if col_widths and idx < len(col_widths):
            cell.width = col_widths[idx]
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            for r in p.runs:
                r.bold = True
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(255, 255, 255)


def style_table_row(row, is_even=False, col_widths=None):
    bg_color = HEX_LIGHT_BG if is_even else "FFFFFF"
    for idx, cell in enumerate(row.cells):
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if col_widths and idx < len(col_widths):
            cell.width = col_widths[idx]
        for p in cell.paragraphs:
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9)
                r.font.color.rgb = COLOR_DARK


def build_specification_document():
    doc = docx.Document()

    # Configuração de Margens (Padrão A4 Corporativo: 2,5 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

        # Cabeçalho e Rodapé
        header = section.header
        hp = header.paragraphs[0]
        hp.text = "F1 SIMULATOR SHOWRUNNER — ESPECIFICAÇÃO FUNCIONAL & TÉCNICA"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.style.font.name = "Arial"
        hp.style.font.size = Pt(8.5)
        hp.style.font.color.rgb = COLOR_GRAY

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.text = "Documento Oficial de Engenharia & Governança Esportiva | Confidencial — Uso Interno | 2026"
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.style.font.name = "Arial"
        fp.style.font.size = Pt(8)
        fp.style.font.color.rgb = COLOR_GRAY

    # =========================================================================
    # CAPA CORPORATIVA
    # =========================================================================
    p_pre = doc.add_paragraph()
    p_pre.paragraph_format.space_before = Pt(36)
    p_pre.paragraph_format.space_after = Pt(6)
    r_pre = p_pre.add_run("FEDERATION INTERNATIONALE DE L'AUTOMOBILE & SHOWRUNNER ENTERTAINMENT")
    r_pre.font.name = "Arial"
    r_pre.font.size = Pt(10)
    r_pre.font.bold = True
    r_pre.font.color.rgb = COLOR_RED

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(12)
    r_title = p_title.add_run("ESPECIFICAÇÃO FUNCIONAL E TÉCNICA DE SISTEMA (EFS/ETS)")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = COLOR_NAVY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(24)
    r_sub = p_sub.add_run("Plataforma Integrada de Simulação EA Sports F1 24, Telemetria UDP 20777, ChatOps Discord e Motor de Storytelling Multi-Persona (M1 a M8)")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(13)
    r_sub.font.color.rgb = COLOR_GRAY

    # Linha divisória corporativa
    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_after = Pt(24)
    r_div = p_div.add_run("―" * 55)
    r_div.font.color.rgb = COLOR_RED
    r_div.font.bold = True

    # Metadados de Controle de Projeto
    tbl_meta = doc.add_table(rows=7, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Código do Documento:", "EFS-ETS-F1-2026-v2.0.0"),
        ("Padrão Arquitetural:", "arc42 (IEEE 42010 / ISO/IEC/IEEE 42020) & Specification by Example (BDD)"),
        ("Ambiente de Implantação:", "Estação de Trabalho Local (Windows 11 / Python 3.12+ / 100% On-Premise)"),
        ("Pilotos Titulares Reais:", "Felipe (Sauber #5), Davi (Williams #15), Sarah (Mercedes #24)"),
        ("Data de Emissão:", "05 de Novembro de 2026"),
        ("Status de Aprovação:", "Aprovado em Sessão Discovery (/grill-me) — Linha de Base v2.0.0"),
        ("Classificação de Segurança:", "Confidencial — Propriedade Intelectual & Regras da Liga"),
    ]
    widths_meta = [Inches(2.5), Inches(4.2)]
    for i, (k, v) in enumerate(meta_data):
        row = tbl_meta.rows[i]
        c0, c1 = row.cells
        c0.text = k
        c0.paragraphs[0].runs[0].bold = True
        c0.paragraphs[0].runs[0].font.color.rgb = COLOR_NAVY
        c1.text = v
        style_table_row(row, is_even=(i % 2 == 1), col_widths=widths_meta)

    doc.add_page_break()

    # =========================================================================
    # SEÇÃO 1: INTRODUÇÃO, VISÃO DE PRODUTO E STAKEHOLDERS
    # =========================================================================
    h1 = doc.add_heading(level=1)
    r = h1.add_run("1. Introdução, Visão de Produto e Stakeholders")
    r.font.name = "Arial"
    r.font.color.rgb = COLOR_NAVY

    doc.add_paragraph(
        "O presente documento estabelece as especificações funcionais (regras de negócio, jornadas esportivas "
        "e interação no Discord) e técnicas (protocolos de rede, decodificação de telemetria UDP, esquemas JSON "
        "e chamadas de IA generativa) do ecossistema F1 Simulator Showrunner. A solução orquestra a temporada "
        "2026 de Fórmula 1 disputada em modo Grand Prix Multiplayer Online no simulador EA Sports F1 24."
    )

    doc.add_heading("1.1. Propósito e Metas de Negócio", level=2)
    p = doc.add_paragraph()
    p.add_run("A solução tem como meta erradicar atritos operacionais e elevar a imersão da liga através de dois pilares invioláveis:\n")
    p.add_run("1. Auditoria Regulatória Determinística (FIA): ").bold = True
    p.add_run("Garantir conformidade matemática de 100% nas tabelas de tempos, voltas mais rápidas, pontuações de Pilotos e Construtores, desempates e penalidades desportivas, eliminando qualquer risco de alucinação aritmética típica de modelos de linguagem.\n")
    p.add_run("2. Storytelling Cinematográfico Multi-Persona (Showrunner): ").bold = True
    p.add_run("Transformar telemetria fina de pista (temperaturas de freio, degradação percentual de pneus por roda, eficiência de ERS) em crônicas de imprensa internacional, coletivas de imprensa dinâmicas com os pilotos humanos e análises técnicas avaliadas pela lenda Alain Prost.")

    doc.add_heading("1.2. Matriz de Stakeholders e Perfis dos Pilotos", level=2)
    tbl_stk = doc.add_table(rows=6, cols=4)
    tbl_stk.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_stk = ["Stakeholder", "Função no Ecossistema", "Canal de Interação", "Expectativa Principal"]
    for j, h in enumerate(headers_stk):
        tbl_stk.rows[0].cells[j].text = h
    style_table_header(tbl_stk.rows[0], [Inches(1.5), Inches(1.8), Inches(1.6), Inches(2.1)])

    stk_rows = [
        ("Felipe (frdsilva)", "Piloto Titular Sauber #5\n'O Monge de Hinwil'", "Discord #geral +\nSimulador F1 24", "Pilotagem cirúrgica, zero atrito operacional no bot e consistência de setup."),
        ("Davi (DaviMSSon)", "Piloto Titular Williams #15\n'O Leão de Grove'", "Discord #geral +\nSimulador F1 24", "Agressividade nas disputas de pista, rivalidade acirrada e respostas em coletivas."),
        ("Sarah (SarahMarinsS)", "Piloto Titular Mercedes #24\n'A Rainha do Gelo'", "Discord #geral +\nSimulador F1 24", "Ritmo dominante, busca incansável por voltas mais rápidas e rigor de dados."),
        ("Direção de Prova FIA", "Órgão Regulador Esportivo\n(Jo Bauer / Comissários)", "Relatórios .md +\nPortal Mobile", "Classificação auditada, aplicação de sanções e conformidade de construtores."),
        ("Alain Prost", "Consultor Técnico Especial\n'Le Professeur'", "Discord #repercussao-midia", "Notas de pilotagem (0 a 10) baseadas estritamente na preservação mecânica do carro."),
    ]
    for idx, (s, f, c, e) in enumerate(stk_rows, start=1):
        r_curr = tbl_stk.rows[idx]
        r_curr.cells[0].text = s
        r_curr.cells[1].text = f
        r_curr.cells[2].text = c
        r_curr.cells[3].text = e
        style_table_row(r_curr, is_even=(idx % 2 == 0), col_widths=[Inches(1.5), Inches(1.8), Inches(1.6), Inches(2.1)])

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # PARTE I: ESPECIFICAÇÃO FUNCIONAL (NEGÓCIO, JORNADAS E MECÂNICAS)
    # =========================================================================
    h1_func = doc.add_heading(level=1)
    r = h1_func.add_run("2. PARTE I: Especificação Funcional (Visão de Negócio & Jornadas)")
    r.font.name = "Arial"
    r.font.color.rgb = COLOR_NAVY

    doc.add_paragraph(
        "A dimensão funcional compreende as regras de negócio, a dinâmica do RPG esportivo, o fluxo "
        "editorial das etapas e a máquina de estados que governa a experiência dos jogadores no Discord."
    )

    doc.add_heading("2.1. O Ciclo Semanal da Etapa (Macro-Jornada)", level=2)
    doc.add_paragraph(
        "Cada Grande Prêmio da temporada percorre uma jornada em 4 fases distintas ao longo da semana:\n"
        "1. Fase Pré-Pista (Segunda a Quinta): Cobertura de bastidores da Silly Season (M1) e Coletiva de Imprensa oficial da FIA (M2).\n"
        "2. Fase de Pista (Fim de Semana): Sessões no simulador EA Sports F1 24 englobando Treino Livre (M3), Classificação (M4) e Corrida Principal (M5).\n"
        "3. Fase de Pódio e Apuração (Pós-Bandeirada): Cerimônia de premiação, sala de descompressão (M6) e emissão do Boletim Oficial de Pontuação do Campeonato (M7).\n"
        "4. Fase de Análise e Debate (Segunda Pós-GP): Avaliação técnica rigorosa de Alain Prost e repercussão nos tablóides esportivos internacionais (M8)."
    )

    doc.add_heading("2.2. Detalhamento Funcional das 8 Mecânicas (M1 a M8)", level=2)

    modules_spec = [
        (
            "M1 — Semana das Equipes (Silly Season & Bastidores)",
            "Gera a narrativa de desenvolvimento, crises de motorhome, rumores de mercado de pilotos e intrigas entre equipes de Segunda a Quinta-feira.",
            "Comando 'inicio da semana etapa XX' ou disparo programado (Cron).",
            "Sorteio aleatório controlado de 4 temas por equipe (Segunda a Quinta); consulta ao canon_ledger.json para resgatar promessas e rivalidades anteriores.",
            "• Publicação em Modo Híbrido: postagens automáticas agendadas ao longo da semana real OU avanço manual sob demanda via 'avancar dia' ou 'publicar semana completa'.\n• O conteúdo destaca os bastidores das equipes de Felipe (Sauber), Davi (Williams) e Sarah (Mercedes).",
            "Documento 01_semana_equipes.md + Teasers diários no Discord #repercussao-midia."
        ),
        (
            "M2 — Coletiva de Imprensa Oficial da FIA",
            "Simula a coletiva de imprensa oficial da FIA na quinta-feira, confrontando pilotos humanos e rivais da IA com perguntas afiadas da mídia especializada.",
            "Comando 'coletiva etapa XX' ou término da publicação do Dia 4 do M1.",
            "Pauta editorial do M1, classificação atual do campeonato e seleção de 5 a 6 pilotos para a bancada.",
            "• Protocolo de Trava de Turno (Turn-Lock): O avanço para a próxima pergunta fica bloqueado até que o piloto humano convocado responda no chat #geral.\n• Contingência por Timeout de Piloto: Se um piloto humano não responder no prazo limite, o Gemini assume sinteticamente a persona do piloto ausente com base nos perfis canônicos oficiais, mantendo a verossimilhança sem travar a semana.",
            "Documento 02_coletiva_pre_gp.md + Ata transcrita e declarações registradas no canon_ledger.json."
        ),
        (
            "M3 — Relatório FIA: Treino Livre (Free Practice)",
            "Audita e consolida a telemetria da sessão de treinos, revelando o equilíbrio mecânico, velocidades de reta e desgaste de compostos em ritmo de corrida.",
            "Conclusão da sessão de treino livre no simulador (detecção FSM UDP m_sessionType in [1, 2, 3]).",
            "Datagramas de telemetria de voltas (Packets 2, 6 e 11).",
            "• Extração de tempos de volta por piloto e parciais dos três setores da pista (S1, S2, S3).\n• Mapeamento de velocidades máximas no Speed Trap.\n• Análise de degradação térmica e mecânica por composto de pneu.",
            "Documento 03_fia_treino_livre.md (Boletim Técnico Oficial da FIA)."
        ),
        (
            "M4 — Classificação & Grid Oficial de Largada",
            "Estabelece as posições de largada (P1 a P20), os deltas de tempo para a pole position e a composição definitiva das dez filas da grelha.",
            "Conclusão da sessão de qualificação no simulador (detecção FSM UDP m_sessionType in [5, 6, 7, 8, 9]).",
            "Pacote de classificação final da sessão (Packet 8) e histórico de infrações.",
            "• Ordenação determinística decrescente pelo melhor tempo de volta válido.\n• Aplicação matemática de eventuais punições de perda de posições no grid oriundas de etapas anteriores ou infrações de parque fechado.\n• Cálculo exato dos gaps para a pole position com precisão de milissegundos.",
            "Documento 04_fia_classificacao.md (Grid Oficial da FIA publicado no Discord e Portal)."
        ),
        (
            "M5 — Relatório da Corrida (FIA Official Sporting Report)",
            "Documento master que audita a prova: classificação final, voltas percorridas, paradas nos boxes, compostos de pneus utilizados e incidentes com punições.",
            "Bandeira quadriculada da corrida (Packet 8 FinalClassification recebido pelo listener UDP).",
            "Arquivo consolidado race_telemetry_merged.json sintetizado nativamente pelo listener UDP.",
            "• Verificação obrigatória do regulamento de pneus (mínimo de 2 compostos secos distintos utilizados em provas secas).\n• Consolidação de tempo total de corrida ou gap em relação ao líder.\n• Apuração de tempos de paradas nos boxes e voltas das trocas.\n• Registro formal das deliberações dos comissários (Stewards' Decisions).",
            "Documento 05_fia_corrida.md + Atualização do estado de corrida para disparo de M6 e M7."
        ),
        (
            "M6 — Pódio, Sala de Descompressão & Zona Mista",
            "Crônica de dramaturgia esportiva narrada no formato 'Drive to Survive', dividida em 4 atos cinematográficos de bastidores.",
            "Conclusão da auditoria esportiva do M5.",
            "Resultado oficial da corrida, deltas de chegada, incidentes e danos mecânicos de telemetria.",
            "• Ato 1: Parque Fechado (reações viscerais ao sair do cockpit, abraços nas garagens).\n• Ato 2: Sala de Descompressão (Cooldown Room - conversas sem filtro entre os 3 primeiros colocados antes de subir ao pódio).\n• Ato 3: Cerimônia do Pódio (entrega de troféus e banho de champanhe).\n• Ato 4: Zona Mista (declarações de Felipe, Davi e Sarah aos repórteres).",
            "Documento 06_cerimonia_podio.md + Teaser ilustrado no Discord #repercussao-midia."
        ),
        (
            "M7 — Boletim Mundial de Pilotos e Construtores (FIA World Championship)",
            "Apuração estritamente matemática e atualização irreversível da tabela do Campeonato Mundial da temporada.",
            "Validação do resultado final de M5 e registro no standings.json.",
            "Tabela de pontuação anterior (standings.json) + Classificação final oficial auditada de M5.",
            "• Atribuição da pontuação clássica da FIA: 25-18-15-12-10-8-6-4-2-1 para os dez primeiros colocados.\n• Ponto extra de Volta Mais Rápida (1 pt) condicionado ao piloto terminar entre os 10 primeiros ($P \\le 10$).\n• Aplicação da Invariante de Construtores: $\\sum \\text{Pilotos} \\equiv \\text{Construtor}$.\n• Incorporação de eventuais sanções disciplinares administrativas aplicadas pela Direção de Prova no Canon Ledger.",
            "Documento 07_fia_mundial.md + standings.json atualizado + Card PNG em alta resolução."
        ),
        (
            "M8 — Repercussão de Mídia & Análise Técnica de Alain Prost",
            "Fechamento da etapa com análise tática refinada e repercussão jornalística internacional sobre a atuação dos pilotos.",
            "Atualização completa da tabela mundial em M7.",
            "Pacotes de telemetria UDP (desgaste de pneus, superaquecimento de freios, uso de ERS) e crônicas anteriores.",
            "• Divisão da publicação no Discord em 2 Blocos:\n  - Bloco 1: Crônica Técnica & Notas de Pilotagem de Alain Prost ('Le Professeur'), com notas de 0 a 10 avaliando o gerenciamento do carro.\n  - Bloco 2: Cobertura Editorial Internacional (tablóides britânicos, imprensa italiana e mídia brasileira).\n• O veredito de Prost não é punitivo, mas uma masterclass de gerenciamento de pneus e inteligência de corrida.",
            "Documento 08_repercussao_midia.md + 2 Publicações segmentadas no canal #repercussao-midia."
        ),
    ]

    for title, desc, trig, inp, rules, outp in modules_spec:
        doc.add_heading(title, level=3)
        doc.add_paragraph(desc)
        tbl_m = doc.add_table(rows=4, cols=2)
        tbl_m.alignment = WD_TABLE_ALIGNMENT.CENTER
        m_items = [
            ("Evento Disparador (Gatilho):", trig),
            ("Entradas Canônicas (Inputs):", inp),
            ("Regras Funcionais & Invariantes:", rules),
            ("Saídas Oficiais (Outputs):", outp),
        ]
        for idx_m, (lbl, val) in enumerate(m_items):
            row_m = tbl_m.rows[idx_m]
            row_m.cells[0].text = lbl
            row_m.cells[0].paragraphs[0].runs[0].bold = True
            row_m.cells[0].paragraphs[0].runs[0].font.color.rgb = COLOR_NAVY
            row_m.cells[1].text = val
            style_table_row(row_m, is_even=(idx_m % 2 == 1), col_widths=[Inches(2.2), Inches(4.5)])
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # Invariante Funcional
    add_callout(
        doc,
        "A integridade esportiva da simulação proíbe que qualquer resultado de corrida ou pontuação do campeonato seja redigido "
        "livremente pelo modelo de linguagem. O LLM atua sob contratos de dados rígidos gerados pelo núcleo em Python.",
        "PRINCÍPIO DE CONFORMIDADE DETERMINÍSTICA"
    )

    doc.add_page_break()

    # =========================================================================
    # PARTE II: ESPECIFICAÇÃO TÉCNICA (ENGENHARIA, REDE E ARQUITETURA)
    # =========================================================================
    h1_tech = doc.add_heading(level=1)
    r = h1_tech.add_run("3. PARTE II: Especificação Técnica Exaustiva (Engenharia & Arquitetura)")
    r.font.name = "Arial"
    r.font.color.rgb = COLOR_NAVY

    doc.add_paragraph(
        "A dimensão técnica documenta exaustivamente a infraestrutura de software, topologia de rede local, "
        "estruturas binárias de datagramas UDP, contratos de interfaces de API, persistência em disco e algoritmos determinísticos."
    )

    doc.add_heading("3.1. Arquitetura de Software e Topologia Local (Windows)", level=2)
    doc.add_paragraph(
        "Conforme estabelecido pela decisão ADR-001, o sistema opera 100% On-Premise na máquina de simulação "
        "(Windows 11 / Python 3.12+), garantindo custo operacional zero (R$ 0,00) e independência de conexões externas "
        "para o processamento de regras determinísticas. A comunicação externa restringe-se às APIs do Discord e do Google AI Studio."
    )

    doc.add_heading("3.2. Especificação do Pipeline de Telemetria UDP (Porta 20777)", level=2)
    doc.add_paragraph(
        "O módulo udp_relay.py implementa um servidor UDP de alta performance escutando no endereço 127.0.0.1:20777. "
        "O socket é configurado com buffer de recepção de 4.194.304 bytes (4 MB) via SO_RCVBUF para prevenir perda "
        "de datagramas durante os picos de transmissão a 60 Hz do simulador EA Sports F1 24."
    )

    doc.add_heading("3.2.1. Estrutura Binária do Cabeçalho Universal (Codemasters 2024 Header)", level=3)
    doc.add_paragraph(
        "Todos os pacotes transmitidos pelo simulador iniciam com um cabeçalho canônico imutável de 29 bytes, "
        "cuja especificação C-struct em Python é representada por struct.unpack('<HBBBBBQfIIBB', data[:29]):"
    )

    tbl_hdr = doc.add_table(rows=12, cols=4)
    tbl_hdr.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_hdr = ["Campo", "Tipo C", "Tamanho", "Descrição e Propósito"]
    for j, h in enumerate(headers_hdr):
        tbl_hdr.rows[0].cells[j].text = h
    style_table_header(tbl_hdr.rows[0], [Inches(1.8), Inches(1.1), Inches(1.1), Inches(2.7)])

    hdr_fields = [
        ("m_packetFormat", "uint16", "2 bytes", "Ano do formato do pacote (sempre 2024)."),
        ("m_gameYear", "uint8", "1 byte", "Versão do jogo (sempre 24)."),
        ("m_gameMajorVersion", "uint8", "1 byte", "Versão maior do patch do simulador."),
        ("m_gameMinorVersion", "uint8", "1 byte", "Versão menor do patch do simulador."),
        ("m_packetVersion", "uint8", "1 byte", "Versão interna do pacote."),
        ("m_packetId", "uint8", "1 byte", "Identificador do tipo de payload (0 a 14)."),
        ("m_sessionUID", "uint64", "8 bytes", "Identificador numérico exclusivo de 64 bits da sessão atual."),
        ("m_sessionTime", "float", "4 bytes", "Tempo decorrido de sessão em segundos desde o início."),
        ("m_frameIdentifier", "uint32", "4 bytes", "Identificador do frame de renderização."),
        ("m_overallFrameIdentifier", "uint32", "4 bytes", "Identificador global do frame desde o início do jogo."),
        ("m_playerCarIndex", "uint8", "1 byte", "Índice do carro do jogador local na lista (0 a 21)."),
    ]
    for idx_h, (cf, tc, sz, ds) in enumerate(hdr_fields, start=1):
        r_h = tbl_hdr.rows[idx_h]
        r_h.cells[0].text = cf
        r_h.cells[1].text = tc
        r_h.cells[2].text = sz
        r_h.cells[3].text = ds
        style_table_row(r_h, is_even=(idx_h % 2 == 0), col_widths=[Inches(1.8), Inches(1.1), Inches(1.1), Inches(2.7)])

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    doc.add_heading("3.2.2. Mapeamento de Pacotes Críticos Desempacotados pelo SessionRecorder", level=3)
    doc.add_paragraph(
        "O motor de telemetria desempacota nativamente em tempo real as seguintes estruturas de dados:"
    )

    tbl_pkts = doc.add_table(rows=7, cols=3)
    tbl_pkts.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_pkts = ["Packet ID & Nome", "Estrutura C / Tamanho", "Dados Extraídos e Mapeados para o Showrunner"]
    for j, h in enumerate(headers_pkts):
        tbl_pkts.rows[0].cells[j].text = h
    style_table_header(tbl_pkts.rows[0], [Inches(1.8), Inches(1.6), Inches(3.3)])

    pkts_data = [
        ("Packet 4\n(Participants)", "60 bytes por carro\n(22 carros)", "Nomes dos pilotos de IA e humanos, números oficiais de corrida, equipes (m_teamId) e telemetria pública."),
        ("Packet 5\n(CarSetups)", "49 bytes por carro\n(22 carros)", "Ângulos de asa dianteira/traseira, pressão dos 4 pneus e parâmetros aerodinâmicos."),
        ("Packet 6\n(CarTelemetry)", "60 bytes por carro\n(22 carros)", "Velocidade pontual (km/h), temperatura interna dos 4 pneus (°C), temperatura dos freios (°C) e marcha."),
        ("Packet 7\n(CarStatus)", "55 bytes por carro\n(22 carros)", "Composto de pneu atual (S/M/H/I/W), voltas no pneu, carga percentual de ERS (0-100%) e modo de motor."),
        ("Packet 8\n(FinalClassification)", "45 bytes por carro\n(22 carros)", "Posição final P1-P20, número de voltas concluídas, status de corrida (FINISHED/DNF/DSQ), tempo total e melhor volta."),
        ("Packet 10\n(CarDamage)", "46 bytes por carro\n(22 carros)", "Desgaste percentual dos 4 pneus (0 a 100%), dano de asa, desgaste de freios e desgaste mecânico do motor (ICE/MGU-K)."),
    ]
    for idx_p, (pn, es, de) in enumerate(pkts_data, start=1):
        r_p = tbl_pkts.rows[idx_p]
        r_p.cells[0].text = pn
        r_p.cells[1].text = es
        r_p.cells[2].text = de
        style_table_row(r_p, is_even=(idx_p % 2 == 0), col_widths=[Inches(1.8), Inches(1.6), Inches(3.3)])

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    doc.add_heading("3.3. Contrato de Interface Canônica (race_telemetry_merged.json)", level=2)
    doc.add_paragraph(
        "O listener UDP sintetiza ao término da sessão o arquivo JSON canônico que alimenta diretamente "
        "os módulos de inteligência artificial e o motor matemático da FIA, sem necessidade de fotos de TV ou OCR."
    )

    doc.add_heading("3.4. Especificação do Gateway Discord (ChatOps & FSM)", level=2)
    doc.add_paragraph(
        "O cliente discord_gateway.py gerencia a conexão com a guilda oficial através da API REST v10. "
        "A máquina de estados finitos opera com polling assíncrono controlado (intervalo de 3 segundos), "
        "armazenando o estado da conversação em data/state/discord_session_state.json."
    )

    tbl_fsm = doc.add_table(rows=6, cols=3)
    tbl_fsm.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_fsm = ["Estado FSM", "Gatilho de Transição", "Ação Operacional Executada pelo Bot"]
    for j, h in enumerate(headers_fsm):
        tbl_fsm.rows[0].cells[j].text = h
    style_table_header(tbl_fsm.rows[0], [Inches(1.8), Inches(2.0), Inches(2.9)])

    fsm_data = [
        ("IDLE", "Mensagem 'inicio da semana etapa XX'", "Valida número da etapa, cria diretório et_XX se inexistente e transita para SEMANA_ACTIVE."),
        ("SEMANA_ACTIVE", "Avanço de dia (Cron ou comando 'avancar dia')", "Gera o episódio diário via Gemini, publica teaser em #repercussao-midia e incrementa o dia."),
        ("PRESS_ACTIVE", "Comando 'coletiva etapa XX' ou fim do Dia 4", "Dispara convocação da coletiva, publica perguntas e transita para TURN_LOCKED."),
        ("TURN_LOCKED", "Resposta do piloto humano convocado", "Captura declaração, salva no canon_ledger.json, publica próxima pergunta ou encerra coletiva."),
        ("RACE_RECORDING", "Bandeira quadriculada (Packet 8 UDP)", "Executa flush() dos buffers de telemetria, atualiza standings.json e dispara M5 a M8."),
    ]
    for idx_f, (es, gt, ao) in enumerate(fsm_data, start=1):
        r_f = tbl_fsm.rows[idx_f]
        r_f.cells[0].text = es
        r_f.cells[1].text = gt
        r_f.cells[2].text = ao
        style_table_row(r_f, is_even=(idx_f % 2 == 0), col_widths=[Inches(1.8), Inches(2.0), Inches(2.9)])

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Invariante de Rede
    add_callout(
        doc,
        "A conexão com o Discord opera com política de backoff exponencial adaptativo caso encontre o status HTTP 429 (Too Many Requests), "
        "assegurando conformidade com as diretrizes da API do Discord sem bloquear a escuta local de telemetria UDP.",
        "RESILIÊNCIA DE REDE & RATE LIMITING"
    )

    doc.add_page_break()

    # =========================================================================
    # SEÇÃO 4: CRITÉRIOS DE ACEITE E CENÁRIOS BDD (GHERKIN)
    # =========================================================================
    h1_bdd = doc.add_heading(level=1)
    r = h1_bdd.add_run("4. Critérios de Aceite e Especificação BDD (Gherkin)")
    r.font.name = "Arial"
    r.font.color.rgb = COLOR_NAVY

    doc.add_paragraph(
        "Os cenários de aceitação formalizam o comportamento esperado do sistema nas situações críticas "
        "de negócio e engenharia, servindo como base para os testes automatizados de homologação."
    )

    bdd_scenarios = [
        (
            "Cenário 1: Trava de Turno na Coletiva FIA com Resposta do Piloto Humano",
            "Funcionalidade: Condução da Coletiva de Imprensa Interativa no Discord (M2)\n"
            "Dado que a coletiva da Etapa 11 foi iniciada com o comando 'coletiva etapa 11'\n"
            "E que a Pergunta 2 foi direcionada ao piloto humano Felipe (Sauber #5)\n"
            "Quando o bot publicar a mensagem marcando @Felipe no canal #geral\n"
            "Então o estado da sessão deve mudar imediatamente para 'TURN_LOCKED'\n"
            "E nenhuma pergunta subsequente deve ser postada pelo bot\n"
            "E quando Felipe responder com 'Vamos buscar o pódio com a Sauber!'\n"
            "Então a resposta deve ser salva no canon_ledger.json\n"
            "E o bot deve desbloquear a trava e publicar a Pergunta 3."
        ),
        (
            "Cenário 2: Timeout de Piloto Humano com Contingência Sintética via Gemini",
            "Funcionalidade: Contingência de Ausência de Piloto na Coletiva (M2)\n"
            "Dado que o estado da sessão está 'TURN_LOCKED' aguardando resposta de Davi (Williams #15)\n"
            "E que o tempo limite configurado de espera expirou (ou o organizador emitiu 'forcar avanco coletiva')\n"
            "Quando a rotina de timeout de turno for acionada\n"
            "Então o módulo Gemini deve assumir a persona de Davi baseando-se no arquivo 'Setup - Perfil Davi.md'\n"
            "E o bot deve publicar a resposta simulada no canal #geral identificada como assessoria de Davi\n"
            "E o estado da sessão deve retornar para 'PRESS_ACTIVE', permitindo o encerramento da ata."
        ),
        (
            "Cenário 3: Recepção da Bandeira Quadriculada e Atualização Determinística da Tabela",
            "Funcionalidade: Pipeline Automático de Pós-Corrida (UDP -> M5 -> M7)\n"
            "Dado que o listener UDP está escutando na porta 20777 durante a corrida da Etapa 11\n"
            "Quando o simulador EA Sports F1 24 transmitir o pacote PacketFinalClassificationData (Packet 8)\n"
            "Então o listener deve disparar automaticamente o método flush()\n"
            "E gerar o arquivo race_telemetry_merged.json com 20 pilotos ordenados por posição oficial\n"
            "E executar a função fia_calculator.update_championship_standings()\n"
            "E verificar se a soma dos pontos dos pilotos da Mercedes é rigorosamente igual aos pontos de construtor da Mercedes\n"
            "E atualizar o arquivo standings.json no disco sem lançar qualquer exceção."
        ),
        (
            "Cenário 4: Geração das Avaliações Técnicas de Pilotagem por Alain Prost",
            "Funcionalidade: Emissão de Notas de Pilotagem no Paddock (M8)\n"
            "Dado que a Etapa 11 foi finalizada e os dados de telemetria fina de pneus e freios foram gravados\n"
            "Quando o orquestrador invocar o módulo de geração de M8\n"
            "Então o Gemini deve incorporar a persona de Alain Prost ('Le Professeur') definida em personas/alain_prost_ex_driver.md\n"
            "E atribuir notas de 0 a 10 para os três pilotos brasileiros baseando-se no desgaste mecânico\n"
            "E o bot deve publicar a análise no canal #repercussao-midia dividida em Bloco 1 (Prost) e Bloco 2 (Imprensa)."
        ),
    ]

    for title_b, scenario_text in bdd_scenarios:
        doc.add_heading(title_b, level=3)
        p_b = doc.add_paragraph()
        p_b.paragraph_format.left_indent = Inches(0.3)
        p_b.paragraph_format.space_before = Pt(2)
        p_b.paragraph_format.space_after = Pt(4)
        run_b = p_b.add_run(scenario_text)
        run_b.font.name = "Consolas"
        run_b.font.size = Pt(8.5)
        run_b.font.color.rgb = COLOR_DARK

    doc.add_page_break()

    # =========================================================================
    # SEÇÃO 5: GESTÃO DE RISCOS, TRATAMENTO DE FALHAS E GLOSSÁRIO
    # =========================================================================
    h1_risks = doc.add_heading(level=1)
    r = h1_risks.add_run("5. Gestão de Riscos, Tratamento de Falhas e Glossário")
    r.font.name = "Arial"
    r.font.color.rgb = COLOR_NAVY

    doc.add_heading("5.1. Matriz de Riscos Técnicos e Planos de Contingência", level=2)
    tbl_rsk = doc.add_table(rows=5, cols=4)
    tbl_rsk.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_rsk = ["Risco Mapeado", "Impacto / Probabilidade", "Mecanismo de Detecção", "Ação de Mitigação Implementada"]
    for j, h in enumerate(headers_rsk):
        tbl_rsk.rows[0].cells[j].text = h
    style_table_header(tbl_rsk.rows[0], [Inches(1.8), Inches(1.3), Inches(1.5), Inches(2.1)])

    rsk_data = [
        ("Queda de Conexão no Discord durante Coletiva", "Alto / Média", "Exceção de timeout na chamada REST v10.", "Persistência do estado a cada pergunta em discord_session_state.json; retomada automática do ponto de parada."),
        ("Esgotamento da Cota Gratuita do Gemini API", "Médio / Baixa", "Erro HTTP 429 ou cota TPM/RPM atingida.", "Pacing obrigatório de 32 segundos entre chamadas Pro e chaveamento automático para gemini-flash-lite."),
        ("Queda ou Crash do Simulador F1 24 em Corrida", "Alto / Baixa", "Cessação abrupta de datagramas UDP sem Packet 8.", "SessionRecorder preserva o último frame íntegro gravado e permite reconstrução da sessão pelo Session UID."),
        ("Tentativa de Reprocessamento Acidental de Etapa", "Crítico / Baixa", "Comando de reprocessamento em etapa consolidada.", "Trava de idempotência: etapas concluídas são imutáveis; reprocessamento exige flag explícita --force-reprocess."),
    ]
    for idx_r, (rm, ip, md, am) in enumerate(rsk_data, start=1):
        r_r = tbl_rsk.rows[idx_r]
        r_r.cells[0].text = rm
        r_r.cells[1].text = ip
        r_r.cells[2].text = md
        r_r.cells[3].text = am
        style_table_row(r_r, is_even=(idx_r % 2 == 0), col_widths=[Inches(1.8), Inches(1.3), Inches(1.5), Inches(2.1)])

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    doc.add_heading("5.2. Glossário de Termos Canônicos (Domain-Driven Design)", level=2)
    tbl_glo = doc.add_table(rows=7, cols=2)
    tbl_glo.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_glo.rows[0].cells[0].text = "Termo / Conceito"
    tbl_glo.rows[0].cells[1].text = "Definição no Domínio do Showrunner F1"
    style_table_header(tbl_glo.rows[0], [Inches(2.0), Inches(4.7)])

    glo_data = [
        ("Canon Ledger", "Livro-razão em arquivo JSON imutável que registra todos os fatos históricos, promessas, multas e rivalidades criadas ao longo da temporada."),
        ("Trava de Turno (Turn-Lock)", "Estado bloqueante do bot do Discord em que o avanço da coletiva é condicionado ao envio de resposta pelo piloto humano designado."),
        ("Session UID", "Identificador único de 64 bits transmitido pelo simulador que distingue inequivocamente sessões de treinos, qualificação e corrida."),
        ("Invariante de Construtores", "Regra matemática estrita da FIA segundo a qual a pontuação de uma equipe deve ser rigorosamente idêntica à soma de seus dois pilotos."),
        ("Le Professeur (Alain Prost)", "Persona de consultoria técnica que avalia a condução esportiva e preservação dos componentes mecânicos dos carros com notas de 0 a 10."),
        ("Pacing de Chamadas", "Mecanismo de espaçamento temporal entre requisições ao Google AI Studio para manter a taxa abaixo dos limites do plano gratuito."),
    ]
    for idx_g, (tm, df) in enumerate(glo_data, start=1):
        r_g = tbl_glo.rows[idx_g]
        r_g.cells[0].text = tm
        r_g.cells[0].paragraphs[0].runs[0].bold = True
        r_g.cells[0].paragraphs[0].runs[0].font.color.rgb = COLOR_NAVY
        r_g.cells[1].text = df
        style_table_row(r_g, is_even=(idx_g % 2 == 0), col_widths=[Inches(2.0), Inches(4.7)])

    # Salvamento do Documento
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DOC_PATH))
    print(f"✅ Documento corporativo gerado com sucesso em: {DOC_PATH}")


if __name__ == "__main__":
    build_specification_document()
