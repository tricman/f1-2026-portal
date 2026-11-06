#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador do Manual de Operações do F1 2026 Showrunner em formato DOCX.
Produz um documento técnico de alto padrão visual e funcional para o operador do sistema.
"""

import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DOCS_DIR / "MANUAL_DE_OPERACOES_SHOWRUNNER_F1.docx"

# Palette: Paddock Dark & FIA Corporate
HEX_NAVY = "1B365D"       # FIA Navy
HEX_RED = "E10600"        # F1 Red
HEX_SLATE = "0B131E"      # Paddock Slate Dark
HEX_CARD = "131D2E"       # Card Background
HEX_LIGHT_BG = "F1F5F9"   # Light Table/Code Background
HEX_BORDER = "CBD5E1"     # Table Border Gray
HEX_TEXT_DARK = "0F172A"   # Slate 900
HEX_TEXT_MUTED = "475569"  # Slate 600
HEX_WHITE = "FFFFFF"

COLOR_NAVY = RGBColor(0x1B, 0x36, 0x5D)
COLOR_RED = RGBColor(0xE1, 0x06, 0x00)
COLOR_SLATE = RGBColor(0x0B, 0x13, 0x1E)
COLOR_TEXT_DARK = RGBColor(0x0F, 0x17, 0x2A)
COLOR_TEXT_MUTED = RGBColor(0x47, 0x55, 0x69)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def set_cell_background(cell, hex_color: str):
    """Aplica cor de fundo a uma célula de tabela."""
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Define margens internas de uma célula em dxa."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def set_table_borders(table, hex_color=HEX_BORDER):
    """Aplica bordas suaves a uma tabela."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{hex_color}"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="{HEX_NAVY}"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{hex_color}"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)


def add_code_block(doc, code_text: str):
    """Adiciona um bloco de código estilizado com fundo claro e borda esquerda destacada."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, HEX_LIGHT_BG)
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{HEX_NAVY}"/>'
        f'<w:top w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    
    # Parágrafo vazio para espaçamento pós tabela
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(2)
    spacer.paragraph_format.space_after = Pt(4)


def add_callout(doc, title: str, text: str, alert_type="NOTE"):
    """Adiciona uma caixa de destaque (Callout Box)."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    border_color = HEX_NAVY
    bg_color = "F8FAFC"
    icon = "ℹ️"
    if alert_type == "WARNING":
        border_color = HEX_RED
        bg_color = "FFF1F2"
        icon = "⚠️"
    elif alert_type == "TIP":
        border_color = "0D9488"
        bg_color = "F0FDFA"
        icon = "💡"
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
        f'<w:top w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p_run = p.add_run(f"{icon} {title}")
    p_run.bold = True
    p_run.font.name = "Segoe UI"
    p_run.font.size = Pt(10)
    p_run.font.color.rgb = RGBColor.from_string(border_color)
    
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_before = Pt(0)
    p2.paragraph_format.space_after = Pt(0)
    p2.paragraph_format.line_spacing = 1.15
    p2_run = p2.add_run(text)
    p2_run.font.name = "Segoe UI"
    p2_run.font.size = Pt(9.5)
    p2_run.font.color.rgb = COLOR_TEXT_DARK
    
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(2)
    spacer.paragraph_format.space_after = Pt(4)


def build_manual_docx():
    doc = docx.Document()
    
    # Page setup - Margens moderadas
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        section.different_first_page_header_footer = True
        
        # Header / Footer nas páginas internas
        footer = section.footer
        f_p = footer.paragraphs[0]
        f_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        f_run = f_p.add_run("F1 2026 Showrunner Engine · Manual de Operações (CLI & ChatOps)")
        f_run.font.name = "Segoe UI"
        f_run.font.size = Pt(8.5)
        f_run.font.color.rgb = COLOR_TEXT_MUTED
        
        header = section.header
        h_p = header.paragraphs[0]
        h_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        h_run = h_p.add_run("CONFIDENCIAL & OPERACIONAL · EA SPORTS F1 24 AUTONOMOUS ENGINE")
        h_run.font.name = "Segoe UI"
        h_run.font.size = Pt(8)
        h_run.font.color.rgb = COLOR_TEXT_MUTED
    
    # ---------------------------------------------------------------------------
    # CAPA DO DOCUMENTO
    # ---------------------------------------------------------------------------
    p_pre = doc.add_paragraph()
    p_pre.paragraph_format.space_before = Pt(20)
    p_pre.paragraph_format.space_after = Pt(6)
    r_pre = p_pre.add_run("FEDERAÇÃO INTERNACIONAL DO AUTOMÓVEL · LIGA BRASILEIRA")
    r_pre.font.name = "Segoe UI"
    r_pre.font.size = Pt(10)
    r_pre.bold = True
    r_pre.font.color.rgb = COLOR_RED

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("MANUAL DE OPERAÇÕES DO SISTEMA")
    r_title.font.name = "Segoe UI"
    r_title.font.size = Pt(26)
    r_title.bold = True
    r_title.font.color.rgb = COLOR_NAVY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(16)
    r_sub = p_sub.add_run("Guia Técnico de Execução: Linha de Comando Python (CLI) & Chatbot Discord (ChatOps)")
    r_sub.font.name = "Segoe UI"
    r_sub.font.size = Pt(14)
    r_sub.font.color.rgb = COLOR_TEXT_MUTED

    # Linha divisória técnica
    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_before = Pt(0)
    p_div.paragraph_format.space_after = Pt(16)
    r_div = p_div.add_run("━" * 55)
    r_div.font.color.rgb = COLOR_RED
    r_div.bold = True

    # Metadados em Tabela Limpa
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.columns[0].width = Inches(2.2)
    meta_table.columns[1].width = Inches(4.3)
    
    metadata_rows = [
        ("Sistema:", "EA F1 24 Autonomous Showrunner Engine (Sprints 1 a 4)"),
        ("Versão do Manual:", "2.0 (Homologado para Etapa 11 e Multi-Temporada)"),
        ("Ambiente de Execução:", "On-Premise Windows x64 (Python 3.12+ Standard Library)"),
        ("Arquitetura de Dados:", "SQLite WAL Local NoSQL (showrunner.db) + Canon Ledger JSON"),
        ("Data de Homologação:", "Novembro de 2026 · Cobertura de Testes: 100% (40/40)"),
    ]
    for idx, (label, val) in enumerate(metadata_rows):
        c0 = meta_table.cell(idx, 0)
        c1 = meta_table.cell(idx, 1)
        set_cell_background(c0, "F8FAFC")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(label)
        r0.font.name = "Segoe UI"
        r0.font.size = Pt(9.5)
        r0.bold = True
        r0.font.color.rgb = COLOR_NAVY
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(val)
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = COLOR_TEXT_DARK
        
    set_table_borders(meta_table)

    doc.add_page_break()

    # ---------------------------------------------------------------------------
    # SEÇÃO 1: VISÃO GERAL DA ARQUITETURA & PRÉ-REQUISITOS
    # ---------------------------------------------------------------------------
    h1 = doc.add_heading("1. Visão Geral da Arquitetura & Pré-Requisitos", level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    for r in h1.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = COLOR_NAVY

    p = doc.add_paragraph(
        "O F1 2026 Showrunner é um motor de narrativa e orquestração autônoma projetado para operar sobre a liga "
        "EA Sports F1 24 disputada pelos pilotos Felipe (Kick Sauber), Davi (Williams) e Sarah (Mercedes-AMG). "
        "O sistema opera 100% em ambiente local (On-Premise) com consumo otimizado das APIs gratuitas do Google AI Studio "
        "(Gemini 2.5 Flash Free Tier) e banco de dados SQLite nativo configurado como repositório NoSQL orientado a documentos."
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)

    doc.add_heading("1.1 Canais de Operação e Visualização", level=2)
    p = doc.add_paragraph(
        "A interação entre o operador humano, os pilotos reais e o ecossistema autônomo é distribuída em três interfaces primárias:"
    )
    p.paragraph_format.space_after = Pt(6)

    chan_tbl = doc.add_table(rows=4, cols=3)
    chan_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    chan_tbl.columns[0].width = Inches(1.8)
    chan_tbl.columns[1].width = Inches(1.8)
    chan_tbl.columns[2].width = Inches(2.9)
    
    chan_headers = ["Interface", "Identificador / URL", "Função Principal"]
    for i, title in enumerate(chan_headers):
        c = chan_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    chan_data = [
        ("Discord #geral", "Canal de Voz (Chat de Texto)\nID: 1457392708355096580", "Console de comando do Chatbot, envio de fotos da TV, upload de CSVs PaceDex, respostas de pilotos na coletiva e escolha de dilemas."),
        ("Discord #repercussao-midia", "Canal de Texto Público\nID: 1536416375969685524", "Canal editorial de saída. Publicação automática dos teasers com deep links, crônicas jornalísticas, pódio e notas da Bancada de Lendas."),
        ("Portal Editorial Web", "GitHub Pages Público\nhttps://tricman.github.io/f1-2026-portal/", "Paddock Dark Mode com visualização oficial da FIA, sequência de abas de módulos (M1..M8), deltas de posição e relatórios técnicos."),
    ]
    for row_idx, row in enumerate(chan_data, start=1):
        for col_idx, text in enumerate(row):
            c = chan_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Segoe UI"
            r.font.size = Pt(9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(chan_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("1.2 Configuração do Arquivo de Ambiente (.env)", level=2)
    p = doc.add_paragraph(
        "Certifique-se de que o arquivo .env localizado na raiz do projeto contenha as seguintes variáveis devidamente preenchidas:"
    )
    p.paragraph_format.space_after = Pt(4)

    env_sample = (
        "# Discord Bot Gateway Credentials\n"
        "DISCORD_BOT_TOKEN=seu_token_de_bot_aqui\n"
        "DISCORD_CHANNEL_ID=1457392708355096580          # Canal de operacao (#geral)\n"
        "DISCORD_PUBLISH_CHANNEL_ID=1536416375969685524  # Canal de publicacao (#repercussao-midia)\n"
        "\n"
        "# Google AI Studio (Gemini Free Tier)\n"
        "GEMINI_API_KEY=sua_chave_gemini_aqui\n"
        "\n"
        "# Telemetria UDP EA Sports F1 24\n"
        "UDP_PORT=20777\n"
        "UDP_HOST=0.0.0.0\n"
        "\n"
        "# Portal Public URL\n"
        "PORTAL_PUBLIC_URL=https://tricman.github.io/f1-2026-portal/"
    )
    add_code_block(doc, env_sample)

    add_callout(
        doc,
        "Imutabilidade Histórica das Etapas 01 a 10",
        "Por diretriz regulamentar da FIA e do Showrunner, as Etapas 01 a 10 da Temporada 1 (season_01) "
        "são estritamente canônicas e protegidas contra sobreescrita ou rollback. O motor de execução rejeitará "
        "qualquer solicitação de purga ou reinicialização nessas etapas históricas.",
        alert_type="WARNING"
    )

    # ---------------------------------------------------------------------------
    # SEÇÃO 2: LINHA DE COMANDO PYTHON (ORCHESTRATOR CLI)
    # ---------------------------------------------------------------------------
    h1 = doc.add_heading("2. Linha de Comando Python (Orchestrator CLI)", level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    for r in h1.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = COLOR_NAVY

    p = doc.add_paragraph(
        "O utilitário central do sistema é o módulo orchestrator_cli.py. Todas as operações administrativas, "
        "geração de módulos em lote, compilação de portal, transições de temporada e controle do serviço de escuta "
        "podem ser executadas via terminal PowerShell."
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)

    doc.add_heading("2.1 Tabela Sintética de Ações da CLI", level=2)
    cli_tbl = doc.add_table(rows=11, cols=3)
    cli_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cli_tbl.columns[0].width = Inches(2.0)
    cli_tbl.columns[1].width = Inches(2.1)
    cli_tbl.columns[2].width = Inches(2.4)
    
    headers = ["Ação (--action)", "Parâmetros Principais", "Descrição Funcional"]
    for i, title in enumerate(headers):
        c = cli_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    cli_actions = [
        ("start-listener", "--interval 15", "Inicia o listener de ChatOps do Discord como processo em segundo plano."),
        ("stop-listener", "--", "Encerra com segurança o processo ativo do listener do Discord."),
        ("status-listener", "--", "Exibe a integridade, PID e status de monitoramento do processo de escuta."),
        ("generate-m1", "--round 11 --round-folder et_11_austria [--season season_01]", "Gera os 4 episódios diários da pré-semana (M1) cobrindo as 10 equipes do grid."),
        ("generate-dilemma", "--round 11 --round-folder et_11_austria --persona felipe", "Gera o Dilema de Paddock M1.5 com trava de turno e opções estratégicas A/B."),
        ("autonomous-session", "--round 11 --round-folder et_11_austria", "Executa a pipeline autônoma pós-corrida: fusão PaceDex + TV, M3..M8 e deploy portal."),
        ("rollback", "--round 11 --scope sessao [--scope coletiva|semana|tudo]", "Executa o rollback granular e seguro de uma etapa, expurgando arquivos e revertendo tabela."),
        ("build-portal", "[--season season_01]", "Recompila o Portal Editorial Paddock Dark Mode e atualiza os índices de busca."),
        ("deploy-portal", "[--season season_01]", "Recompila o Portal e efetua o commit e push automatizado no branch do GitHub Pages."),
        ("start-season", "--new-season season_02 [--grid-file grid.json]", "Inicializa formalmente uma nova temporada com análise de Dança das Cadeiras e tabela zerada."),
    ]
    for row_idx, row in enumerate(cli_actions, start=1):
        for col_idx, text in enumerate(row):
            c = cli_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(cli_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("2.2 Exemplos Práticos de Comandos PowerShell", level=2)

    p = doc.add_paragraph("A) Inicialização e Gestão do Robô de Escuta do Discord:")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_1 = (
        "# 1. Iniciar o processo do listener em background (escuta a cada 15 segundos)\n"
        "python -m src.orchestrator_cli --action start-listener\n\n"
        "# 2. Verificar a saude e PID do processo ativo\n"
        "python -m src.orchestrator_cli --action status-listener\n\n"
        "# 3. Encerrar o processo ativo com seguranca\n"
        "python -m src.orchestrator_cli --action stop-listener"
    )
    add_code_block(doc, cmd_sample_1)

    p = doc.add_paragraph("B) Ciclo Pré-Semana e Dilemas de Paddock (M1 & M1.5):")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_2 = (
        "# Gerar a crônica semanal completa (10 equipes do grid) para a Etapa 11 (Austria)\n"
        "python -m src.orchestrator_cli --action generate-m1 --round-folder et_11_austria --round 11\n\n"
        "# Gerar o dilema interativo para Felipe (Kick Sauber)\n"
        "python -m src.orchestrator_cli --action generate-dilemma --round-folder et_11_austria --round 11 --persona felipe"
    )
    add_code_block(doc, cmd_sample_2)

    p = doc.add_paragraph("C) Sessão Autônoma de Corrida (Processamento Pós-Bandeirada):")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_3 = (
        "# Executa fusao PaceDex CSV + TV Overlay, FIA Standings, M3..M8 e publicacao no portal\n"
        "python -m src.orchestrator_cli --action autonomous-session --round-folder et_11_austria --round 11"
    )
    add_code_block(doc, cmd_sample_3)

    p = doc.add_paragraph("D) Execução de Rollback Granular de Etapa:")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_4 = (
        "# 1. Rollback de Sessao (purga M3..M8, telemetria e reverte tabela de pontuacao)\n"
        "python -m src.orchestrator_cli --action rollback --round 11 --scope sessao\n\n"
        "# 2. Rollback de Coletiva (reseta a coletiva M2 e seus registros no Canon Ledger)\n"
        "python -m src.orchestrator_cli --action rollback --round 11 --scope coletiva\n\n"
        "# 3. Rollback Completo da Etapa (reseta M1, M1.5, M2, sessao e telemetria)\n"
        "python -m src.orchestrator_cli --action rollback --round 11 --scope tudo"
    )
    add_code_block(doc, cmd_sample_4)

    p = doc.add_paragraph("E) Compilação e Deploy do Portal Web Editorial:")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_5 = (
        "# Compilar o portal localmente em portal/index.html\n"
        "python -m src.orchestrator_cli --action build-portal\n\n"
        "# Compilar e realizar deploy direto no GitHub Pages\n"
        "python -m src.orchestrator_cli --action deploy-portal"
    )
    add_code_block(doc, cmd_sample_5)

    p = doc.add_paragraph("F) Gestão de Múltiplas Temporadas (Multi-Season & Dança das Cadeiras):")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_6 = (
        "# Listar temporadas registradas no sistema e temporada ativa\n"
        "python -m src.orchestrator_cli --action list-seasons\n\n"
        "# Inicializar formalmente a Temporada 2 com registro de novo grid e transferencias\n"
        "python -m src.orchestrator_cli --action start-season --new-season season_02 --grid-file data/setup/grid_season_02.json"
    )
    add_code_block(doc, cmd_sample_6)

    p = doc.add_paragraph("G) Execução da Suíte de Testes Automatizados:")
    p.paragraph_format.space_after = Pt(4)
    p.runs[0].bold = True
    cmd_sample_7 = (
        "# 1. Executar a suite completa com todos os 40 testes de regressao\n"
        "python -m unittest discover tests -v\n\n"
        "# 2. Executar teste de homologacao E2E da Etapa 11 (Austria)\n"
        "python -m unittest tests/test_e2e_showrunner.py -v"
    )
    add_code_block(doc, cmd_sample_7)

    # ---------------------------------------------------------------------------
    # SEÇÃO 3: GUIA COMPLETO DO CHATBOT DISCORD (CHATOPS)
    # ---------------------------------------------------------------------------
    doc.add_page_break()
    h1 = doc.add_heading("3. Guia Completo do Chatbot Discord (ChatOps)", level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    for r in h1.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = COLOR_NAVY

    p = doc.add_paragraph(
        "O operador ou os pilotos não precisam necessariamente tocar no terminal para operar uma corrida. "
        "O módulo chatops_listener monitora continuamente as mensagens postadas no canal de voz #geral e executa "
        "as ações correspondentes. Abaixo está o catálogo completo de comandos reconhecidos pelo motor de ChatOps."
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)

    doc.add_heading("3.1 FASE 1: Pré-Semana M1 (A Semana da F1)", level=2)
    p = doc.add_paragraph(
        "Dispara as crônicas da 'Silly Season' cobrindo crises contratuais, espionagem técnica e declarações "
        "de motorhome das 10 equipes do campeonato."
    )
    p.paragraph_format.space_after = Pt(6)

    m1_tbl = doc.add_table(rows=4, cols=3)
    m1_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    m1_tbl.columns[0].width = Inches(2.2)
    m1_tbl.columns[1].width = Inches(2.0)
    m1_tbl.columns[2].width = Inches(2.3)
    
    headers_m1 = ["Comando no Discord (#geral)", "Variações Aceitas", "Comportamento do Showrunner"]
    for i, title in enumerate(headers_m1):
        c = m1_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    m1_cmds = [
        ("inicio da semana etapa XX", "inicio da semana, semana etapa XX", "Inicia a simulação da semana gerando o Dia 1 (Segunda-Feira) cobrindo as 10 equipes com temas sorteados sem duplicidade."),
        ("dia 2 / dia 3 / dia 4", "avancar dia, proximo dia", "Avança a narrativa dia a dia. No Dia 4 (Quinta-Feira), gera a ata consolidada e grava evento oficial no Canon Ledger e SQLite."),
        ("pre etapa XX", "preview etapa XX, lote semana XX", "Gera os 4 episódios diários da pré-semana de forma instantânea em lote (modo rápido para etapas com cronograma apertado)."),
    ]
    for row_idx, row in enumerate(m1_cmds, start=1):
        for col_idx, text in enumerate(row):
            c = m1_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(m1_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("3.2 FASE 1.5: Dilema Interativo de Paddock (M1.5)", level=2)
    p = doc.add_paragraph(
        "Coloca um dos pilotos reais (Felipe, Davi ou Sarah) diante de uma encruzilhada estratégica com a diretoria "
        "da sua escuderia (ex: escolha entre peças aerodinâmicas novas ou foco em telemetria)."
    )
    p.paragraph_format.space_after = Pt(6)

    dilemma_tbl = doc.add_table(rows=4, cols=3)
    dilemma_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    dilemma_tbl.columns[0].width = Inches(2.2)
    dilemma_tbl.columns[1].width = Inches(2.0)
    dilemma_tbl.columns[2].width = Inches(2.3)
    
    headers_dilemma = ["Comando no Discord (#geral)", "Variações Aceitas", "Comportamento do Showrunner"]
    for i, title in enumerate(headers_dilemma):
        c = dilemma_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    dilemma_cmds = [
        ("dilema etapa XX", "dilema, gerar dilema", "Gera o dilema com menção ao piloto no Discord. Ativa a trava de turno DILEMMA_LOCKED aguardando resposta."),
        ("opcao A / opcao B", "escolha A, escolha B, alternativa A", "Registra a decisão do piloto, gera a narrativa de consequência imediata e salva no Canon Ledger (M1_5_DILEMA)."),
        ("forcar avanco dilema", "timeout dilema, pular dilema", "Contingência operacional para quando o piloto não puder responder: a assessoria escolhe a opção mais conservadora automaticamente."),
    ]
    for row_idx, row in enumerate(dilemma_cmds, start=1):
        for col_idx, text in enumerate(row):
            c = dilemma_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(dilemma_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("3.3 FASE 2: Coletiva de Imprensa Oficial da FIA (M2)", level=2)
    p = doc.add_paragraph(
        "Simula a coletiva de quinta-feira da FIA com bancada dinâmica de pilotos e jornalistas internacionais "
        "(Mariana Becker, Ted Kravitz, Roberto Chinchero, etc.)."
    )
    p.paragraph_format.space_after = Pt(6)

    conf_tbl = doc.add_table(rows=4, cols=3)
    conf_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    conf_tbl.columns[0].width = Inches(2.2)
    conf_tbl.columns[1].width = Inches(2.0)
    conf_tbl.columns[2].width = Inches(2.3)
    
    headers_conf = ["Comando no Discord (#geral)", "Variações Aceitas", "Comportamento do Showrunner"]
    for i, title in enumerate(headers_conf):
        c = conf_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    conf_cmds = [
        ("coletiva etapa XX", "coletiva, coletiva fia etapa XX", "Abre a sala de imprensa, convoca a bancada de pilotos e inicia a primeira rodada de perguntas."),
        ("[Digitar texto normalmente]", "Qualquer mensagem de texto", "Quando o microfone estiver aberto para o piloto humano (TRAVA DE TURNO ATIVA), qualquer mensagem enviada por ele é capturada como resposta oficial."),
        ("timeout coletiva", "forcar resposta coletiva, pular coletiva", "Avança a coletiva imediatamente injetando nota padrão da assessoria de imprensa caso o piloto convocado esteja ausente."),
    ]
    for row_idx, row in enumerate(conf_cmds, start=1):
        for col_idx, text in enumerate(row):
            c = conf_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(conf_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("3.4 FASE 3: Fim de Semana de Pista, Telemetria e Módulos M3 a M8", level=2)
    p = doc.add_paragraph(
        "Gerencia a abertura da janela de corrida, a ingestão de telemetria e o encerramento autônomo com cálculo FIA."
    )
    p.paragraph_format.space_after = Pt(6)

    race_tbl = doc.add_table(rows=4, cols=3)
    race_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    race_tbl.columns[0].width = Inches(2.2)
    race_tbl.columns[1].width = Inches(2.0)
    race_tbl.columns[2].width = Inches(2.3)
    
    headers_race = ["Comando no Discord (#geral)", "Variações Aceitas", "Comportamento do Showrunner"]
    for i, title in enumerate(headers_race):
        c = race_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    race_cmds = [
        ("inicio da etapa XX", "abrir etapa XX, comecar etapa XX", "Abre a janela de coleta de dados no Discord, habilita listener para download de fotos e CSVs enviados."),
        ("[Upload de Fotos e CSVs]", "Anexos no chat #geral", "O bot baixa automaticamente os arquivos para data/seasons/season_01/et_XX/telemetry/ e photos/."),
        ("final da etapa XX", "fim da etapa XX, encerrar etapa XX", "Dispara o ciclo autônomo completo: OCR da TV, fusão PaceDex, Standings com deltas, geração de M3 a M8, publicação no #repercussao-midia e deploy no Portal."),
    ]
    for row_idx, row in enumerate(race_cmds, start=1):
        for col_idx, text in enumerate(row):
            c = race_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(race_tbl)

    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(6)

    doc.add_heading("3.5 Rollback Granular e Gestão de Temporada no Discord", level=2)
    p = doc.add_paragraph(
        "Permite executar correções cirúrgicas ou inaugurar novas fases do campeonato diretamente pelo Discord:"
    )
    p.paragraph_format.space_after = Pt(6)

    extra_tbl = doc.add_table(rows=6, cols=3)
    extra_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    extra_tbl.columns[0].width = Inches(2.2)
    extra_tbl.columns[1].width = Inches(2.0)
    extra_tbl.columns[2].width = Inches(2.3)
    
    headers_extra = ["Comando no Discord (#geral)", "Variações Aceitas", "Comportamento do Showrunner"]
    for i, title in enumerate(headers_extra):
        c = extra_tbl.cell(0, i)
        set_cell_background(c, HEX_NAVY)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(title)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = COLOR_WHITE
        
    extra_cmds = [
        ("rollback etapa XX sessao", "reverter etapa XX sessao", "Purga os relatórios M3..M8, telemetria e restaura a tabela de classificação anterior."),
        ("rollback etapa XX coletiva", "reverter etapa XX coletiva", "Reseta a ata oficial da Coletiva M2 e seus registros no Canon Ledger."),
        ("rollback etapa XX semana", "reverter etapa XX semana", "Reseta os arquivos de pré-semana M1 e o dilema M1.5."),
        ("iniciar telemetria udp", "start udp, conectar telemetria", "Ativa o listener local para captura de telemetria UDP ao vivo na porta 20777."),
        ("nova temporada season_02", "iniciar nova temporada season_02", "Inaugura a nova temporada, processa transferências de pilotos e sela evento no Canon Ledger."),
    ]
    for row_idx, row in enumerate(extra_cmds, start=1):
        for col_idx, text in enumerate(row):
            c = extra_tbl.cell(row_idx, col_idx)
            set_cell_background(c, "F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Consolas" if col_idx < 2 else "Segoe UI"
            r.font.size = Pt(8.5 if col_idx < 2 else 9)
            r.font.color.rgb = COLOR_TEXT_DARK
            if col_idx == 0:
                r.bold = True
    set_table_borders(extra_tbl)

    # ---------------------------------------------------------------------------
    # SEÇÃO 4: MATRIZ DE RESOLUÇÃO DE PROBLEMAS (TROUBLESHOOTING)
    # ---------------------------------------------------------------------------
    doc.add_page_break()
    h1 = doc.add_heading("4. Matriz de Resolução de Problemas (Troubleshooting)", level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    for r in h1.runs:
        r.font.name = "Segoe UI"
        r.font.color.rgb = COLOR_NAVY

    p = doc.add_paragraph(
        "Diagnóstico e correção rápida para as intercorrências operacionais mais comuns durante o fim de semana de corrida:"
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)

    trouble_data = [
        (
            "Piloto ausente durante a Coletiva Pré-GP (Trava de Turno travada)",
            "O microfone fica aberto indefinidamente para um piloto humano que não está conectado ao Discord.",
            "Digite no chat #geral: timeout coletiva ou execute via PowerShell: python -m src.orchestrator_cli --action rollback --round XX --scope coletiva. A IA registrará uma resposta institucional padrão da assessoria de imprensa da equipe e avançará automaticamente."
        ),
        (
            "Fotos da TV com baixa resolução ou reflexo (Falha no OCR Vision)",
            "O Gemini Vision não consegue extrair com precisão os tempos de volta ou pilotos classificados.",
            "Certifique-se de que a foto enquadre as 4 abas completas da TV sem corte de laterais. Se o arquivo estiver corrompido, suba uma foto nítida e rode: python -m src.orchestrator_cli --action autonomous-session --round-folder et_XX --round XX."
        ),
        (
            "Erro de Permissão no Rollback (Tentativa em Etapas 01 a 10)",
            "O operador tenta rodar rollback na Etapa 05 e recebe erro: Proteção de integridade ativada.",
            "Comportamento esperado por projeto. As etapas 01 a 10 são canônicas. O rollback só é autorizado para a Etapa 11 em diante. Nenhuma intervenção necessária."
        ),
        (
            "Portal Web não atualizou após a publicação",
            "O GitHub Pages ainda exibe a etapa anterior após a finalização da corrida.",
            "Execute manualmente: python -m src.orchestrator_cli --action deploy-portal. O script forçará a recompilação do JSON de busca (portal_data.json), gerará um hash de timestamp nos assets e efetuará o push no branch remoto."
        ),
        (
            "Processo do Listener do Discord não responde",
            "Mensagens digitadas no Discord não geram resposta do bot.",
            "Verifique se o processo está em execução via: python -m src.orchestrator_cli --action status-listener. Se inativo, inicie-o com: python -m src.orchestrator_cli --action start-listener. Se houver falha de rede, reinicie o processo com stop-listener seguido de start-listener."
        ),
    ]

    for title, causa, solucao in trouble_data:
        p_t = doc.add_paragraph()
        p_t.paragraph_format.space_before = Pt(8)
        p_t.paragraph_format.space_after = Pt(2)
        r_t = p_t.add_run(f"🔴 Problema: {title}")
        r_t.font.name = "Segoe UI"
        r_t.font.size = Pt(10.5)
        r_t.bold = True
        r_t.font.color.rgb = COLOR_NAVY
        
        p_c = doc.add_paragraph()
        p_c.paragraph_format.space_before = Pt(0)
        p_c.paragraph_format.space_after = Pt(2)
        r_c = p_c.add_run(f"• Causa Provável: {causa}")
        r_c.font.name = "Segoe UI"
        r_c.font.size = Pt(9.5)
        r_c.font.color.rgb = COLOR_TEXT_MUTED
        
        p_s = doc.add_paragraph()
        p_s.paragraph_format.space_before = Pt(0)
        p_s.paragraph_format.space_after = Pt(6)
        r_s = p_s.add_run(f"• Solução Técnica: {solucao}")
        r_s.font.name = "Segoe UI"
        r_s.font.size = Pt(9.5)
        r_s.font.color.rgb = COLOR_TEXT_DARK

    # Salva o documento
    doc.save(str(OUTPUT_FILE))
    print(f"Manual de Operações gerado com sucesso em: {OUTPUT_FILE}")
    print(f"Tamanho do arquivo: {OUTPUT_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    build_manual_docx()
