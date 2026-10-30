import re
import io
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

# F1 Official Dark Theme Broadcast Palette
BG_DARK = (15, 17, 23)
HEADER_RED = (225, 6, 0)
HEADER_SUB = (28, 32, 44)
ROW_EVEN = (22, 26, 36)
ROW_ODD = (29, 34, 48)
PODIUM_GOLD = (58, 49, 18)
PODIUM_SILVER = (45, 50, 60)
PODIUM_BRONZE = (54, 36, 24)
PURPLE_FL = (155, 38, 182)
TEXT_WHITE = (245, 247, 250)
TEXT_MUTED = (165, 175, 195)
TEXT_ACCENT = (0, 230, 118)
BORDER_COLOR = (52, 60, 82)

TEAM_COLORS: Dict[str, Tuple[int, int, int]] = {
    "mercedes": (0, 210, 190),
    "sauber": (0, 230, 77),
    "kick sauber": (0, 230, 77),
    "williams": (0, 160, 255),
    "red bull": (30, 91, 198),
    "ferrari": (232, 0, 32),
    "mclaren": (255, 128, 0),
    "aston martin": (0, 111, 98),
    "alpine": (0, 147, 221),
    "haas": (182, 186, 189),
    "visa cash app": (102, 146, 255),
    "vcarb": (102, 146, 255),
}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/consolab.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/consola.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def clean_cell_text(raw: str) -> str:
    """Strip Markdown bold/code/italics and normalize whitespace for clean rendering."""
    txt = raw.strip()
    txt = re.sub(r"\*\*(.*?)\*\*", r"\1", txt)
    txt = re.sub(r"\*(.*?)\*", r"\1", txt)
    txt = re.sub(r"`(.*?)`", r"\1", txt)
    # Replace emojis that standard Windows fonts don't render in PIL with clean tags
    txt = txt.replace("🟣", "[VR]").replace("⚡", "[FAST]").replace("🇧🇷", "BRA")
    txt = txt.replace("🇪🇸", "ESP").replace("🇳🇱", "NED").replace("🇬🇧", "GBR")
    txt = txt.replace("🇲🇨", "MON").replace("🇦🇺", "AUS").replace("🇲🇽", "MEX")
    txt = txt.replace("🇫🇷", "FRA").replace("🇩🇪", "GER").replace("🇨🇦", "CAN")
    txt = txt.replace("🇹🇭", "THA").replace("🇯🇵", "JPN").replace("🇫🇮", "FIN")
    txt = txt.replace("🇩🇰", "DEN").replace("👑", "").replace("🟢", "").replace("🔴", "")
    txt = txt.replace("🥈", "").replace("🔷", "").replace("🐎", "").replace("🟧", "")
    txt = txt.replace("📈", "").replace("⚠", "")
    return re.sub(r"\s+", " ", txt).strip()


def clean_cell_for_mobile(raw: str) -> str:
    """Keep emojis for Discord mobile cards, stripping backticks and outer bold/italics."""
    txt = raw.strip()
    txt = re.sub(r"\*\*(.*?)\*\*", r"\1", txt)
    txt = re.sub(r"\*(.*?)\*", r"\1", txt)
    txt = re.sub(r"`(.*?)`", r"\1", txt)
    return re.sub(r"\s+", " ", txt).strip()


def detect_team_color(row_cells: List[str]) -> Optional[Tuple[int, int, int]]:
    joined = " ".join(row_cells).lower()
    for key, color in TEAM_COLORS.items():
        if key in joined:
            return color
    return None


def render_markdown_table_to_png(
    headers: List[str],
    rows: List[List[str]],
    title: str = "FIA OFFICIAL TELEMETRY & CLASSIFICATION",
) -> bytes:
    """
    Render a Markdown table into a high-contrast F1 TV / FIA dark-mode PNG image.
    Returns PNG bytes ready to be uploaded to Discord.
    """
    clean_headers = [clean_cell_text(h) for h in headers]
    clean_rows = [[clean_cell_text(c) for c in r] for r in rows]

    font_title = _load_font(22, bold=True)
    font_header = _load_font(16, bold=True)
    font_cell = _load_font(15, bold=False)
    font_cell_bold = _load_font(15, bold=True)

    dummy_img = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)

    num_cols = len(clean_headers)
    col_widths = [0] * num_cols
    padding_x = 18

    for col_idx, h_text in enumerate(clean_headers):
        bbox = dummy_draw.textbbox((0, 0), h_text, font=font_header)
        col_widths[col_idx] = max(col_widths[col_idx], (bbox[2] - bbox[0]) + padding_x * 2)

    for row in clean_rows:
        for col_idx in range(min(num_cols, len(row))):
            c_text = row[col_idx]
            bbox = dummy_draw.textbbox((0, 0), c_text, font=font_cell_bold)
            col_widths[col_idx] = max(col_widths[col_idx], (bbox[2] - bbox[0]) + padding_x * 2)

    margin = 24
    title_bar_h = 54
    header_h = 44
    row_h = 38
    footer_h = 32

    total_w = max(sum(col_widths) + margin * 2, 780)
    # Distribute extra width proportionally if table is narrower than 780px
    extra_w = total_w - (sum(col_widths) + margin * 2)
    if extra_w > 0 and num_cols > 0:
        per_col = extra_w // num_cols
        col_widths = [w + per_col for w in col_widths]

    total_h = margin * 2 + title_bar_h + header_h + len(clean_rows) * row_h + footer_h

    img = Image.new("RGB", (total_w, total_h), color=BG_DARK)
    draw = ImageDraw.Draw(img)

    # Top F1 Red Banner
    draw.rectangle([margin, margin, total_w - margin, margin + title_bar_h], fill=HEADER_RED)
    draw.text(
        (margin + 18, margin + 13),
        f"FIA F1 2026  |  {clean_cell_text(title).upper()}",
        fill=TEXT_WHITE,
        font=font_title,
    )

    # Column Header Row
    y_cursor = margin + title_bar_h
    draw.rectangle([margin, y_cursor, total_w - margin, y_cursor + header_h], fill=HEADER_SUB)

    x_cursor = margin
    for col_idx, h_text in enumerate(clean_headers):
        draw.text((x_cursor + padding_x, y_cursor + 12), h_text, fill=TEXT_MUTED, font=font_header)
        x_cursor += col_widths[col_idx]

    y_cursor += header_h

    # Data Rows
    for row_idx, row in enumerate(clean_rows):
        pos_str = row[0] if row else ""
        has_vr = any("[VR]" in c or "VR" in c.split() for c in row)
        if pos_str.startswith("1º") or pos_str == "1":
            bg = PODIUM_GOLD
        elif pos_str.startswith("2º") or pos_str == "2":
            bg = PODIUM_SILVER
        elif pos_str.startswith("3º") or pos_str == "3":
            bg = PODIUM_BRONZE
        else:
            bg = ROW_EVEN if row_idx % 2 == 0 else ROW_ODD

        draw.rectangle([margin, y_cursor, total_w - margin, y_cursor + row_h], fill=bg)
        draw.line([margin, y_cursor + row_h, total_w - margin, y_cursor + row_h], fill=BORDER_COLOR, width=1)

        # Team color accent bar on the left
        team_color = detect_team_color(row)
        if team_color:
            draw.rectangle([margin, y_cursor + 2, margin + 6, y_cursor + row_h - 2], fill=team_color)

        x_cursor = margin
        is_top3 = pos_str.startswith(("1º", "2º", "3º"))
        for col_idx in range(min(num_cols, len(row))):
            c_text = row[col_idx]
            use_bold = is_top3 or col_idx in (0, 2, num_cols - 1)
            fnt = font_cell_bold if use_bold else font_cell

            if "[VR]" in c_text:
                color = (224, 130, 255)
            elif col_idx == num_cols - 1 and is_top3:
                color = TEXT_ACCENT
            else:
                color = TEXT_WHITE if use_bold else (215, 220, 232)

            draw.text((x_cursor + padding_x, y_cursor + 9), c_text, fill=color, font=fnt)
            x_cursor += col_widths[col_idx]

        y_cursor += row_h

    # Footer
    draw.text(
        (margin + 10, y_cursor + 8),
        "OFFICIAL FIA TIMING & PACEDEX TELEMETRY ENGINE  •  BRAZILIAN STORM 2026",
        fill=TEXT_MUTED,
        font=font_cell,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def format_table_as_mobile_cards(headers: List[str], rows: List[List[str]]) -> str:
    """
    Convert a wide Markdown table into compact, vertical mobile-friendly cards
    so smartphone readers can scan Top drivers & results without horizontal scrolling.
    """
    clean_h = [clean_cell_for_mobile(h) for h in headers]
    cards: List[str] = []

    for row in rows:
        cells = [clean_cell_for_mobile(c) for c in row]
        if not cells:
            continue

        pos = cells[0]
        # Badge decoration for Podium
        if pos.startswith("1º"):
            badge = "🥇 **1º**"
        elif pos.startswith("2º"):
            badge = "🥈 **2º**"
        elif pos.startswith("3º"):
            badge = "🥉 **3º**"
        elif "NC" in pos or "DNF" in pos:
            badge = "❌ **NC**"
        else:
            badge = f"🔹 **{pos}**"

        # Heuristic formatting based on table structure
        # Case A: Race Classification (Pos | Nº | Piloto | Equipe | Grid | Δ | Voltas | Paradas | Estratégia | Melhor Volta | Gap | Desgaste | Pontos)
        if len(cells) >= 12 and "Piloto" in " ".join(clean_h):
            num, driver, team = cells[1], cells[2], cells[3]
            grid, delta = cells[4], cells[5]
            strat, best_lap, gap, wear, pts = cells[8], cells[9], cells[10], cells[11], cells[12]
            pts_str = f" 🏆 **{pts} pts**" if pts != "0" else ""
            cards.append(
                f"> {badge} `{num}` **{driver}** — *{team}*{pts_str}\n"
                f"> ⏱️ **Tempo/Gap:** `{gap}` | **VR:** `{best_lap}` | **Grid:** {grid} (`{delta}`)\n"
                f"> 🛞 **Pneus:** `{strat}` (Desgaste: `{wear}`)"
            )
        # Case B: Pit Stops Table (Pos. Pit | Volta | Nº | Piloto | Equipe | Tempo | Transição | Reparos)
        elif len(cells) >= 7 and ("Parada" in " ".join(clean_h) or "Pit" in " ".join(clean_h)):
            lap, num, driver, team, stop_time, transition = (
                cells[1],
                cells[2],
                cells[3],
                cells[4],
                cells[5],
                cells[6],
            )
            cards.append(
                f"> {badge} `{stop_time}` — **{driver}** (`{num}` *{team}*) na **{lap}** (`{transition}`)"
            )
        # Case C: Championship Drivers Standings
        elif len(cells) >= 8 and ("Total" in " ".join(clean_h) or "Acumulado" in " ".join(clean_h)):
            num, driver, team = cells[1], cells[2], cells[4]
            prev_pts, round_pts, total_pts = cells[5], cells[6], cells[7]
            cards.append(
                f"> {badge} `{num}` **{driver}** (*{team}*) — 🏆 **{total_pts} pts** *(Ant: {prev_pts} | Etapa: {round_pts})*"
            )
        # Case D: Generic table fallback (compact 2-line card)
        else:
            headline = " • ".join(cells[: min(4, len(cells))])
            details = " | ".join(
                f"**{clean_h[i]}:** {cells[i]}" for i in range(min(4, len(cells)), len(cells))
            )
            if details:
                cards.append(f"> {badge} {headline}\n> ↳ {details}")
            else:
                cards.append(f"> {badge} {headline}")

    return "\n\n".join(cards)


def transform_markdown_tables_for_discord(
    markdown_text: str,
) -> Tuple[str, List[Tuple[str, bytes]]]:
    """
    Scan a Markdown document for pipe tables (`| ... |`).
    For each table found:
      1. Generate a high-res F1 TV style PNG image (`table_01.png`, etc.).
      2. Replace the raw pipe table in the Markdown text with Mobile-First Cards
         so smartphone users get clean vertical cards + the attached broadcast PNG!
    Returns (transformed_markdown, list_of_(filename, png_bytes)).
    """
    lines = markdown_text.splitlines()
    out_lines: List[str] = []
    images: List[Tuple[str, bytes]] = []

    i = 0
    current_section_title = "FIA OFFICIAL CLASSIFICATION"
    table_counter = 0

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("#"):
            current_section_title = line.strip().lstrip("#").strip()

        # Detect start of a Markdown pipe table (header row followed by | :--- | separator)
        if (
            line.strip().startswith("|")
            and line.strip().endswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|[\s:\-\|]+\|\s*$", lines[i + 1])
        ):
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2  # Skip header and separator line
            table_rows: List[List[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                table_rows.append(row_cells)
                i += 1

            table_counter += 1
            png_bytes = render_markdown_table_to_png(
                header_cells, table_rows, title=current_section_title
            )
            img_filename = f"fia_table_{table_counter:02d}.png"
            images.append((img_filename, png_bytes))

            mobile_cards = format_table_as_mobile_cards(header_cells, table_rows)
            out_lines.append(
                f"📱 **Resumo Mobile ({current_section_title}):** *(Tabela oficial completa em alta definição anexa)*\n\n"
                + mobile_cards
            )
            continue

        out_lines.append(line)
        i += 1

    return "\n".join(out_lines), images
