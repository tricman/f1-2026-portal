import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple

ROUND_METADATA: Dict[str, Dict[str, Any]] = {
    "et_01_bahrein": {"num": 1, "name": "GP do Bahrein", "circuit": "Sakhir", "flag": "🇧🇭"},
    "et_02_jeddah": {"num": 2, "name": "GP da Arábia Saudita", "circuit": "Jeddah", "flag": "🇸🇦"},
    "et_03_australia": {"num": 3, "name": "GP da Austrália", "circuit": "Melbourne", "flag": "🇦🇺"},
    "et_04_japao": {"num": 4, "name": "GP do Japão", "circuit": "Suzuka", "flag": "🇯🇵"},
    "et_05_china": {"num": 5, "name": "GP da China", "circuit": "Xangai", "flag": "🇨🇳"},
    "et_06_miami": {"num": 6, "name": "GP de Miami", "circuit": "Miami Autodrome", "flag": "🇺🇸"},
    "et_07_imola": {"num": 7, "name": "GP da Emília-Romanha", "circuit": "Ímola", "flag": "🇮🇹"},
    "et_08_monaco": {"num": 8, "name": "GP de Mônaco", "circuit": "Monte Carlo", "flag": "🇲🇨"},
    "et_09_canada": {"num": 9, "name": "GP do Canadá", "circuit": "Montreal", "flag": "🇨🇦"},
    "et_10_espanha": {"num": 10, "name": "GP da Espanha", "circuit": "Barcelona-Catalunya", "flag": "🇪🇸"},
    "et_11_austria": {"num": 11, "name": "GP da Áustria", "circuit": "Red Bull Ring (Spielberg)", "flag": "🇦🇹"},
    "et_12_inglaterra": {"num": 12, "name": "GP da Grã-Bretanha", "circuit": "Silverstone", "flag": "🇬🇧"},
    "et_13_hungria": {"num": 13, "name": "GP da Hungria", "circuit": "Hungaroring (Budapeste)", "flag": "🇭🇺"},
    "et_14_belgica": {"num": 14, "name": "GP da Bélgica", "circuit": "Spa-Francorchamps", "flag": "🇧🇪"},
    "et_15_holanda": {"num": 15, "name": "GP dos Países Baixos", "circuit": "Zandvoort", "flag": "🇳🇱"},
    "et_16_italia": {"num": 16, "name": "GP da Itália", "circuit": "Monza", "flag": "🇮🇹"},
    "et_17_azerbaijao": {"num": 17, "name": "GP do Azerbaijão", "circuit": "Baku", "flag": "🇦🇿"},
    "et_18_singapura": {"num": 18, "name": "GP de Singapura", "circuit": "Marina Bay", "flag": "🇸🇬"},
    "et_19_eua": {"num": 19, "name": "GP dos Estados Unidos", "circuit": "COTA (Austin)", "flag": "🇺🇸"},
    "et_20_mexico": {"num": 20, "name": "GP da Cidade do México", "circuit": "Hermanos Rodríguez", "flag": "🇲🇽"},
    "et_21_brasil": {"num": 21, "name": "GP de São Paulo", "circuit": "Interlagos", "flag": "🇧🇷"},
    "et_22_las_vegas": {"num": 22, "name": "GP de Las Vegas", "circuit": "Las Vegas Strip", "flag": "🇺🇸"},
    "et_23_catar": {"num": 23, "name": "GP do Catar", "circuit": "Lusail", "flag": "🇶🇦"},
    "et_24_abu_dhabi": {"num": 24, "name": "GP de Abu Dhabi", "circuit": "Yas Marina", "flag": "🇦🇪"},
}


def classify_module_badge(filename: str) -> Tuple[int, str, str, str]:
    """
    Return (sort_order, short_tag, badge_label, color_class) for a given Markdown file.
    """
    low = filename.lower()
    if "semana" in low or "bastidores pré" in low or "bastidores da semana" in low:
        return (1, "M1 • PRÉ-SEMANA", "Blog: A F1 Que Você Não Vê", "badge-amber")
    if "coletiva" in low:
        return (2, "M2 • COLETIVA FIA", "Coletiva Oficial Pré-GP", "badge-blue")
    if "treino livre" in low or "treinos livres" in low:
        return (3, "M3 • TREINO LIVRE", "Relatório Técnico FIA (TL)", "badge-cyan")
    if "classificação" in low and ("treino" in low or "qualifying" in low or "grid" in low):
        return (4, "M4 • QUALIFYING", "Relatório FIA Qualifying & Grid", "badge-purple")
    if "resultado final" in low or "relatório oficial da fia_ grande prêmio" in low or "relatório oficial fia - gp" in low:
        return (5, "M5 • CORRIDA OFICIAL", "Resultado Final & Stewards FIA", "badge-red")
    if "pódio" in low or "podio" in low:
        return (6, "M6 • PÓDIO & VIP", "Cerimônia do Pódio & Cooldown", "badge-gold")
    if "atualização" in low or "construtores" in low or "mundial" in low:
        return (7, "M7 • CAMPEONATO FIA", "Boletim Oficial do Mundial", "badge-emerald")
    if "repercussão" in low or "imprensa" in low or "mídia" in low:
        return (8, "M8 • IMPRENSA & REDES", "Repercussão Global & Internet", "badge-pink")
    return (9, "ARQUIVO", filename.replace(".md", ""), "badge-slate")


def collect_portal_data(root_dir: Path) -> Dict[str, Any]:
    season_dir = root_dir / "data" / "seasons" / "season_01"
    setup_dir = root_dir / "data" / "setup"
    state_dir = root_dir / "data" / "state"

    # Dynamically pick the latest standings_etXX.json or fallback to standings.json
    standings_candidates = sorted(
        state_dir.glob("standings_et*.json"),
        key=lambda p: int(re.sub(r"\D", "", p.stem) or "0"),
        reverse=True,
    )
    standings_path = standings_candidates[0] if standings_candidates else (state_dir / "standings.json")
    standings = json.loads(standings_path.read_text(encoding="utf-8")) if standings_path.exists() else {}

    rounds_list: List[Dict[str, Any]] = []
    if season_dir.exists():
        for folder in sorted(season_dir.iterdir()):
            if not folder.is_dir() or folder.name not in ROUND_METADATA:
                continue
            meta = ROUND_METADATA[folder.name]
            articles: List[Dict[str, Any]] = []
            for md_file in sorted(folder.glob("*.md")):
                order, short_tag, label, color_cls = classify_module_badge(md_file.name)
                content = md_file.read_text(encoding="utf-8")
                # Extract first heading or fallback to filename
                first_h = None
                for line in content.splitlines():
                    if line.strip().startswith("#"):
                        first_h = line.strip().lstrip("#").strip()
                        break
                articles.append({
                    "id": f"{folder.name}__{md_file.stem}",
                    "filename": md_file.name,
                    "title": first_h or md_file.stem,
                    "order": order,
                    "short_tag": short_tag,
                    "badge_label": label,
                    "color_class": color_cls,
                    "markdown": content,
                })
            articles.sort(key=lambda a: (a["order"], a["filename"]))
            rounds_list.append({
                "folder": folder.name,
                "num": meta["num"],
                "name": meta["name"],
                "circuit": meta["circuit"],
                "flag": meta["flag"],
                "articles": articles,
            })

    setup_docs: List[Dict[str, Any]] = []
    if setup_dir.exists():
        for md_file in sorted(setup_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            setup_docs.append({
                "id": f"setup__{md_file.stem}",
                "filename": md_file.name,
                "title": md_file.stem.replace("Setup - ", "📖 "),
                "short_tag": "CANON & REGRAS",
                "badge_label": "Enciclopédia Oficial 2026",
                "color_class": "badge-emerald",
                "markdown": content,
            })

    return {
        "season": 2026,
        "standings": standings,
        "rounds": rounds_list,
        "setup_docs": setup_docs,
    }


def build_editorial_portal(root_dir: Path) -> Path:
    """
    Compile all Season 01 rounds (Etapas 1..10), Setup Lore, and FIA Standings
    into a self-contained, mobile-first Editorial Portal & Wiki (`portal/index.html`).
    """
    portal_data = collect_portal_data(root_dir)
    portal_dir = root_dir / "portal"
    portal_dir.mkdir(parents=True, exist_ok=True)

    data_json_str = json.dumps(portal_data, ensure_ascii=False)
    (portal_dir / "portal_data.json").write_text(data_json_str, encoding="utf-8")

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0" />
  <title>F1 2026 Paddock Insider & FIA Official Wiki — Brazilian Storm</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&family=Titillium+Web:ital,wght@0,600;0,700;0,900;1,700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --f1-red: #e10600;
      --bg-carbon: #0b0d13;
      --bg-card: #131722;
      --bg-elevated: #1c2230;
    }}
    body {{
      background-color: var(--bg-carbon);
      color: #e2e8f0;
      font-family: 'Inter', sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .font-f1 {{
      font-family: 'Titillium Web', sans-serif;
    }}
    .font-mono-code {{
      font-family: 'JetBrains Mono', monospace;
    }}
    /* Custom Scrollbars */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #0f131d; }}
    ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #e10600; }}

    /* Editorial Article Typography & Responsive Tables */
    .editorial-content h1 {{
      font-family: 'Titillium Web', sans-serif;
      font-size: 1.75rem;
      font-weight: 900;
      line-height: 1.2;
      color: #ffffff;
      margin-top: 0.5rem;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 2px solid #e10600;
      letter-spacing: -0.01em;
    }}
    .editorial-content h2 {{
      font-family: 'Titillium Web', sans-serif;
      font-size: 1.35rem;
      font-weight: 700;
      color: #f8fafc;
      margin-top: 2rem;
      margin-bottom: 0.85rem;
      padding-left: 0.75rem;
      border-left: 4px solid #e10600;
    }}
    .editorial-content h3, .editorial-content h4 {{
      font-family: 'Titillium Web', sans-serif;
      font-size: 1.12rem;
      font-weight: 700;
      color: #38bdf8;
      margin-top: 1.5rem;
      margin-bottom: 0.6rem;
    }}
    .editorial-content p {{
      font-size: 1.02rem;
      line-height: 1.75;
      color: #cbd5e1;
      margin-bottom: 1.15rem;
    }}
    .editorial-content ul, .editorial-content ol {{
      margin-bottom: 1.25rem;
      padding-left: 1.35rem;
    }}
    .editorial-content li {{
      font-size: 1rem;
      line-height: 1.7;
      color: #cbd5e1;
      margin-bottom: 0.5rem;
      list-style-type: disc;
    }}
    .editorial-content strong {{
      color: #ffffff;
      font-weight: 700;
    }}
    .editorial-content code {{
      font-family: 'JetBrains Mono', monospace;
      background: rgba(56, 189, 248, 0.12);
      color: #7dd3fc;
      padding: 0.15rem 0.4rem;
      border-radius: 0.3rem;
      font-size: 0.88em;
    }}
    .editorial-content pre {{
      background: #090b10;
      border: 1px solid #1e293b;
      border-radius: 0.6rem;
      padding: 1rem;
      overflow-x: auto;
      margin-bottom: 1.25rem;
    }}
    .editorial-content pre code {{
      background: transparent;
      color: #e2e8f0;
      padding: 0;
    }}
    .editorial-content blockquote {{
      background: linear-gradient(90deg, rgba(225, 6, 0, 0.12) 0%, rgba(19, 23, 34, 0.9) 100%);
      border-left: 4px solid #e10600;
      padding: 1rem 1.25rem;
      border-radius: 0 0.6rem 0.6rem 0;
      margin: 1.35rem 0;
      color: #f1f5f9;
    }}
    .editorial-content hr {{
      border-color: #1e293b;
      margin: 2rem 0;
    }}
    /* Horizontal Scroll Wrapper for Wide FIA Tables on Mobile */
    .table-scroll-wrapper {{
      width: 100%;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      margin: 1.25rem 0 1.75rem 0;
      border-radius: 0.65rem;
      border: 1px solid #263044;
      background: #0e121b;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }}
    .editorial-content table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      white-space: nowrap;
    }}
    .editorial-content thead th {{
      background: #181f2e;
      color: #94a3b8;
      font-family: 'Titillium Web', sans-serif;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.75rem 0.9rem;
      border-bottom: 2px solid #e10600;
      text-align: left;
    }}
    .editorial-content tbody tr {{
      border-bottom: 1px solid #1e2638;
      transition: background 0.15s ease;
    }}
    .editorial-content tbody tr:nth-child(even) {{
      background: rgba(255, 255, 255, 0.015);
    }}
    .editorial-content tbody tr:hover {{
      background: rgba(225, 6, 0, 0.08);
    }}
    .editorial-content td {{
      padding: 0.65rem 0.9rem;
      color: #e2e8f0;
    }}
    /* Sticky first column on mobile tables so driver/pos stays visible while scrolling */
    .editorial-content th:first-child,
    .editorial-content td:first-child {{
      position: sticky;
      left: 0;
      background: #131824;
      z-index: 1;
      border-right: 1px solid #263044;
      font-weight: 700;
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col selection:bg-red-600 selection:text-white">

  <!-- TOP F1 BROADCAST HEADER -->
  <header class="sticky top-0 z-40 bg-[#0b0d13]/95 backdrop-blur-md border-b border-slate-800/80">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 h-14 flex items-center justify-between gap-2">
      <div class="flex items-center gap-3">
        <button id="mobileMenuBtn" onclick="toggleSidebar()" class="lg:hidden p-2 rounded-lg bg-slate-800/80 text-slate-200 hover:bg-red-600 hover:text-white transition">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <div class="flex items-center gap-2.5 cursor-pointer" onclick="selectRound(10)">
          <span class="bg-[#e10600] text-white font-f1 font-black italic px-2.5 py-0.5 rounded text-sm tracking-wider">F1 26</span>
          <div>
            <h1 class="font-f1 font-bold text-white text-sm sm:text-base leading-none tracking-wide">PADDOCK INSIDER & FIA WIKI</h1>
            <p class="text-[10px] text-slate-400 font-medium hidden sm:block">TEMPORADA 2026 • BRAZILIAN STORM CHRONICLES</p>
          </div>
        </div>
      </div>

      <!-- Quick Top Navigation Pills -->
      <div class="flex items-center gap-1.5 sm:gap-2">
        <button onclick="openStandingsModal()" class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-xs font-semibold text-amber-400 border border-amber-500/30 transition">
          <span>🏆</span>
          <span class="hidden xs:inline">Mundial</span>
          <span id="topStandingsRoundBadge" class="font-mono-code text-[11px] text-white">R10</span>
        </button>
        <button onclick="openSetupWiki()" class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-xs font-semibold text-emerald-400 border border-emerald-500/30 transition">
          <span>📚</span>
          <span class="hidden sm:inline">Enciclopédia & Personas</span>
          <span class="sm:hidden">Wiki</span>
        </button>
        <button id="mobilePreviewToggleBtn" onclick="toggleMobileFramePreview()" class="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-xs font-semibold text-sky-400 border border-sky-500/30 transition" title="Simular tela de celular (390px) no navegador desktop">
          <span>📱</span>
          <span>Simular Mobile</span>
        </button>
        <div class="relative hidden md:block">
          <input id="searchInput" oninput="handleSearch(this.value)" type="text" placeholder="Buscar piloto, etapa, incidente..." class="w-52 lg:w-64 bg-slate-900/90 border border-slate-700/80 rounded-lg px-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-red-500" />
        </div>
      </div>
    </div>

    <!-- HORIZONTAL ROUND SELECTOR BAR (MOBILE-FIRST SWIPEABLE) -->
    <div class="border-t border-slate-800/60 bg-[#0f131c]">
      <div id="roundSelectorBar" class="max-w-7xl mx-auto px-3 sm:px-6 py-2 flex items-center gap-2 overflow-x-auto no-scrollbar">
        <!-- Populated by JS -->
      </div>
    </div>
  </header>

  <!-- MAIN EDITORIAL WORKSPACE -->
  <div class="max-w-7xl mx-auto w-full flex-1 flex relative px-3 sm:px-6 py-4 sm:py-6 gap-6">

    <!-- LEFT DRAWER / SIDEBAR: MODULE TIMELINE & SEARCH -->
    <aside id="leftSidebar" class="fixed lg:static inset-y-0 left-0 z-50 w-80 lg:w-72 bg-[#111520] lg:bg-transparent border-r lg:border-r-0 border-slate-800 p-4 lg:p-0 transform -translate-x-full lg:translate-x-0 transition-transform duration-200 ease-in-out flex flex-col shrink-0 overflow-y-auto">
      <div class="flex items-center justify-between lg:hidden mb-4 pb-3 border-b border-slate-800">
        <span class="font-f1 font-bold text-sm text-white uppercase tracking-wider">Navegação da Etapa</span>
        <button onclick="toggleSidebar()" class="p-1.5 text-slate-400 hover:text-white">✕</button>
      </div>

      <!-- Mobile Search Input -->
      <div class="mb-4 md:hidden">
        <input id="mobileSearchInput" oninput="handleSearch(this.value)" type="text" placeholder="🔍 Buscar em toda a temporada..." class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white" />
      </div>

      <!-- Brazilian Storm Quick Telemetry Trio Card (Dynamic from latest Standings) -->
      <div class="mb-4 p-3 rounded-xl bg-gradient-to-br from-slate-900 via-[#141a29] to-slate-900 border border-slate-800/90 shadow-lg">
        <div class="flex items-center justify-between mb-2">
          <span id="stormWidgetHeader" class="text-[11px] font-f1 font-bold uppercase tracking-wider text-emerald-400">🇧🇷 Brazilian Storm</span>
          <span class="text-[10px] font-mono-code text-slate-400">2026</span>
        </div>
        <div id="stormWidgetRows" class="space-y-1.5 text-xs">
          <!-- Populated dynamically by JS -->
        </div>
      </div>

      <!-- Current Context Header -->
      <div class="mb-2 flex items-center justify-between">
        <h2 id="sidebarSectionTitle" class="font-f1 font-bold text-xs uppercase tracking-wider text-slate-400">CADERNOS DA ETAPA</h2>
        <span id="sidebarArticleCount" class="text-[11px] font-mono-code text-slate-500"></span>
      </div>

      <!-- Module List -->
      <nav id="moduleListNav" class="space-y-2 flex-1">
        <!-- Populated by JS -->
      </nav>
    </aside>

    <!-- Backdrop for Mobile Sidebar -->
    <div id="sidebarBackdrop" onclick="toggleSidebar()" class="fixed inset-0 bg-black/60 z-40 hidden lg:hidden"></div>

    <!-- CENTER MAGAZINE READER -->
    <main class="flex-1 min-w-0">
      <!-- Module Horizontal Pill Switcher for fast thumb navigation on Mobile -->
      <div id="mobileModulePills" class="flex items-center gap-1.5 overflow-x-auto pb-3 mb-3 border-b border-slate-800/80 lg:hidden">
        <!-- Populated by JS -->
      </div>

      <!-- Article Container -->
      <article class="bg-[#131722] border border-slate-800/90 rounded-2xl shadow-2xl p-4 sm:p-8 lg:p-10">
        <!-- Article Metadata Banner -->
        <div id="articleMetaHeader" class="mb-6 pb-4 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-2">
          <!-- Populated by JS -->
        </div>

        <!-- Rendered Markdown Body -->
        <div id="articleBody" class="editorial-content">
          <!-- Populated by JS -->
        </div>

        <!-- Prev / Next Module Footer Navigation -->
        <div id="articleFooterNav" class="mt-10 pt-6 border-t border-slate-800 flex items-center justify-between gap-4">
          <!-- Populated by JS -->
        </div>
      </article>
    </main>

  </div>

  <!-- MODAL: FIA CHAMPIONSHIP STANDINGS (DRIVERS & CONSTRUCTORS) -->
  <div id="standingsModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden items-center justify-center p-3 sm:p-6">
    <div class="bg-[#131722] border border-slate-700 rounded-2xl max-w-5xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
      <div class="bg-[#e10600] px-4 sm:px-6 py-3.5 flex items-center justify-between">
        <div>
          <h2 class="font-f1 font-black text-white text-base sm:text-lg tracking-wide uppercase">🏆 FIA WORLD CHAMPIONSHIP STANDINGS — PÓS-ETAPA 10 (ESPANHA)</h2>
          <p class="text-xs text-red-100">Homologação Oficial WMSC FIA • Opção 1 (Dedução -10 pts Construtores Red Bull Racing)</p>
        </div>
        <button onclick="closeStandingsModal()" class="text-white hover:bg-black/20 rounded-lg px-2.5 py-1 text-lg font-bold">✕</button>
      </div>
      <div class="p-4 sm:p-6 overflow-y-auto space-y-6" id="standingsModalBody">
        <!-- Populated by JS -->
      </div>
    </div>
  </div>

  <script>
    const PORTAL_DATA = {data_json_str};

    let currentMode = 'round'; // 'round' | 'setup' | 'search'
    let currentRoundNum = 10;
    let currentArticleId = null;

    function getBadgeStyle(colorClass) {{
      const map = {{
        'badge-amber': 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        'badge-blue': 'bg-sky-500/15 text-sky-300 border-sky-500/30',
        'badge-cyan': 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
        'badge-purple': 'bg-purple-500/15 text-purple-300 border-purple-500/30',
        'badge-red': 'bg-red-500/20 text-red-300 border-red-500/40',
        'badge-gold': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
        'badge-emerald': 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        'badge-pink': 'bg-pink-500/15 text-pink-300 border-pink-500/30',
        'badge-slate': 'bg-slate-700/40 text-slate-300 border-slate-600'
      }};
      return map[colorClass] || map['badge-slate'];
    }}

    function toggleSidebar() {{
      const sb = document.getElementById('leftSidebar');
      const bd = document.getElementById('sidebarBackdrop');
      const isHidden = sb.classList.contains('-translate-x-full');
      if (isHidden) {{
        sb.classList.remove('-translate-x-full');
        bd.classList.remove('hidden');
      }} else {{
        sb.classList.add('-translate-x-full');
        bd.classList.add('hidden');
      }}
    }}

    function renderRoundSelector() {{
      const bar = document.getElementById('roundSelectorBar');
      bar.innerHTML = PORTAL_DATA.rounds.map(r => {{
        const active = (currentMode === 'round' && r.num === currentRoundNum);
        const cls = active
          ? 'bg-[#e10600] text-white border-[#e10600] shadow-md shadow-red-950/50'
          : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:border-slate-600 hover:text-white';
        return `
          <button onclick="selectRound(${{r.num}})" class="shrink-0 px-3 py-1.5 rounded-lg border text-xs font-f1 font-bold tracking-wide transition flex items-center gap-1.5 ${{cls}}">
            <span>${{r.flag}}</span>
            <span>R${{String(r.num).padStart(2, '0')}}</span>
            <span class="hidden sm:inline">• ${{r.name.replace('GP ', '')}}</span>
          </button>
        `;
      }}).join('');
    }}

    function selectRound(roundNum, targetArticleId = null) {{
      currentMode = 'round';
      currentRoundNum = roundNum;
      const roundObj = PORTAL_DATA.rounds.find(r => r.num === roundNum) || PORTAL_DATA.rounds[PORTAL_DATA.rounds.length - 1];
      if (!roundObj) return;

      renderRoundSelector();
      document.getElementById('sidebarSectionTitle').textContent = `${{roundObj.flag}} ETAPA ${{roundObj.num}} — ${{roundObj.name.toUpperCase()}}`;
      document.getElementById('sidebarArticleCount').textContent = `${{roundObj.articles.length}} docs`;

      //Default to M5 (Race Final Report) if selecting Round 10 for the first time, else first article
      if (!targetArticleId) {{
        const m5 = roundObj.articles.find(a => a.order === 5);
        targetArticleId = m5 ? m5.id : (roundObj.articles[0] ? roundObj.articles[0].id : null);
      }}
      window.location.hash = `r=${{roundNum}}&m=${{encodeURIComponent(targetArticleId || '')}}`;
      renderArticleList(roundObj.articles, targetArticleId);
    }}

    function openSetupWiki(targetId = null) {{
      currentMode = 'setup';
      renderRoundSelector();
      document.getElementById('sidebarSectionTitle').textContent = '📚 ENCICLOPÉDIA & PERSONAS (CANON)';
      document.getElementById('sidebarArticleCount').textContent = `${{PORTAL_DATA.setup_docs.length}} docs`;
      const firstId = targetId || (PORTAL_DATA.setup_docs[0] ? PORTAL_DATA.setup_docs[0].id : null);
      renderArticleList(PORTAL_DATA.setup_docs, firstId);
    }}

    function handleSearch(query) {{
      const q = (query || '').trim().toLowerCase();
      if (q.length < 2) {{
        selectRound(currentRoundNum, currentArticleId);
        return;
      }}
      currentMode = 'search';
      renderRoundSelector();
      const results = [];
      PORTAL_DATA.rounds.forEach(r => {{
        r.articles.forEach(a => {{
          if (a.title.toLowerCase().includes(q) || a.markdown.toLowerCase().includes(q) || a.badge_label.toLowerCase().includes(q)) {{
            results.push({{
              ...a,
              short_tag: `${{r.flag}} R${{r.num}} • ${{a.short_tag}}`
            }});
          }}
        }});
      }});
      PORTAL_DATA.setup_docs.forEach(s => {{
        if (s.title.toLowerCase().includes(q) || s.markdown.toLowerCase().includes(q)) {{
          results.push(s);
        }}
      }});

      document.getElementById('sidebarSectionTitle').textContent = `🔍 RESULTADOS PARA "${{query.toUpperCase()}}"`;
      document.getElementById('sidebarArticleCount').textContent = `${{results.length}} encontrados`;
      renderArticleList(results, results[0] ? results[0].id : null);
    }}

    function renderArticleList(articles, selectedId) {{
      currentArticleId = selectedId;
      const nav = document.getElementById('moduleListNav');
      const mobilePills = document.getElementById('mobileModulePills');

      if (!articles || articles.length === 0) {{
        nav.innerHTML = `<div class="p-4 text-xs text-slate-500 text-center">Nenhum documento encontrado.</div>`;
        mobilePills.innerHTML = '';
        document.getElementById('articleBody').innerHTML = `<p class="text-slate-400">Nenhum conteúdo selecionado.</p>`;
        return;
      }}

      nav.innerHTML = articles.map(a => {{
        const isSelected = a.id === selectedId;
        const cardCls = isSelected
          ? 'bg-slate-800/95 border-red-500/80 shadow-md'
          : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700';
        return `
          <button onclick="selectArticle('${{a.id}}')" class="w-full text-left p-2.5 rounded-xl border transition block ${{cardCls}}">
            <div class="flex items-center justify-between gap-2 mb-1">
              <span class="px-2 py-0.5 text-[10px] font-f1 font-bold rounded border ${{getBadgeStyle(a.color_class)}}">${{a.short_tag}}</span>
            </div>
            <div class="text-xs font-semibold text-slate-100 line-clamp-2 leading-snug">${{a.badge_label}}</div>
            <div class="text-[11px] text-slate-400 truncate mt-0.5">${{a.filename.replace('.md', '')}}</div>
          </button>
        `;
      }}).join('');

      mobilePills.innerHTML = articles.map(a => {{
        const isSelected = a.id === selectedId;
        const pillCls = isSelected
          ? 'bg-red-600 text-white border-red-500'
          : 'bg-slate-900 text-slate-300 border-slate-800';
        return `
          <button onclick="selectArticle('${{a.id}}')" class="shrink-0 px-2.5 py-1 rounded-lg border text-[11px] font-f1 font-bold ${{pillCls}}">
            ${{a.short_tag}}
          </button>
        `;
      }}).join('');

      const activeArticle = articles.find(a => a.id === selectedId) || articles[0];
      displayArticle(activeArticle, articles);
    }}

    function selectArticle(articleId) {{
      let pool = [];
      if (currentMode === 'round') {{
        const r = PORTAL_DATA.rounds.find(x => x.num === currentRoundNum);
        pool = r ? r.articles : [];
        window.location.hash = `r=${{currentRoundNum}}&m=${{encodeURIComponent(articleId)}}`;
      }} else if (currentMode === 'setup') {{
        pool = PORTAL_DATA.setup_docs;
        window.location.hash = `setup=${{encodeURIComponent(articleId)}}`;
      }} else {{
        PORTAL_DATA.rounds.forEach(r => pool.push(...r.articles));
        pool.push(...PORTAL_DATA.setup_docs);
      }}
      renderArticleList(pool, articleId);
      // Close mobile drawer if open
      const sb = document.getElementById('leftSidebar');
      if (!sb.classList.contains('-translate-x-full')) {{
        toggleSidebar();
      }}
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function displayArticle(article, pool) {{
      if (!article) return;
      const metaHeader = document.getElementById('articleMetaHeader');
      metaHeader.innerHTML = `
        <div class="flex items-center gap-2">
          <span class="px-2.5 py-1 text-xs font-f1 font-bold rounded-md border ${{getBadgeStyle(article.color_class)}}">${{article.short_tag}}</span>
          <span class="text-xs font-semibold text-slate-300">${{article.badge_label}}</span>
        </div>
        <span class="text-[11px] font-mono-code text-slate-400 bg-slate-900 px-2.5 py-1 rounded border border-slate-800">${{article.filename}}</span>
      `;

      // Pre-process GitHub callouts (> [!WARNING], > [!IMPORTANT], etc.) into clean badges
      let md = article.markdown.replace(/\\[!IMPORTANT\\]/g, '**🚨 IMPORTANTE — FIA:**')
                               .replace(/\\[!WARNING\\]/g, '**⚠️ DECISÃO DOS COMISSÁRIOS:**')
                               .replace(/\\[!CAUTION\\]/g, '**🛑 BOLETIM TÉCNICO:**')
                               .replace(/\\[!NOTE\\]/g, '**📌 NOTA OFICIAL:**');

      const rawHtml = marked.parse(md);
      const bodyEl = document.getElementById('articleBody');
      bodyEl.innerHTML = rawHtml;

      // Wrap all <table> elements in a smooth horizontal scroll container for mobile screens
      bodyEl.querySelectorAll('table').forEach(tbl => {{
        const wrapper = document.createElement('div');
        wrapper.className = 'table-scroll-wrapper';
        tbl.parentNode.insertBefore(wrapper, tbl);
        wrapper.appendChild(tbl);
      }});

      // Prev / Next navigation buttons
      const idx = pool.findIndex(x => x.id === article.id);
      const prev = idx > 0 ? pool[idx - 1] : null;
      const next = idx >= 0 && idx < pool.length - 1 ? pool[idx + 1] : null;

      document.getElementById('articleFooterNav').innerHTML = `
        <div>
          ${{prev ? `<button onclick="selectArticle('${{prev.id}}')" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition flex items-center gap-2"><span>←</span><span>${{prev.short_tag}}</span></button>` : '<div></div>'}}
        </div>
        <div>
          ${{next ? `<button onclick="selectArticle('${{next.id}}')" class="px-3.5 py-2 rounded-xl bg-[#e10600] hover:bg-red-700 text-xs font-semibold text-white transition flex items-center gap-2"><span>${{next.short_tag}}</span><span>→</span></button>` : '<div></div>'}}
        </div>
      `;
    }}

    function openStandingsModal() {{
      const modal = document.getElementById('standingsModal');
      const body = document.getElementById('standingsModalBody');
      const st = PORTAL_DATA.standings;

      const driversRows = (st.drivers_standings || []).map(d => {{
        const isBr = d.nationality === 'BRA';
        const rowBg = isBr ? 'bg-emerald-950/30 font-semibold' : '';
        return `
          <tr class="${{rowBg}} border-b border-slate-800">
            <td class="p-2.5 font-mono-code font-bold text-white">${{d.pos}}º</td>
            <td class="p-2.5 font-mono-code text-slate-400">#${{d.car_number}}</td>
            <td class="p-2.5 text-white">${{d.name}} ${{isBr ? '🇧🇷' : ''}}</td>
            <td class="p-2.5 text-slate-300 text-xs uppercase">${{d.team_id.replace('_', ' ')}}</td>
            <td class="p-2.5 font-mono-code text-slate-400">${{d.wins}}</td>
            <td class="p-2.5 font-mono-code text-slate-400">${{d.podiums}}</td>
            <td class="p-2.5 font-mono-code font-bold text-emerald-400 text-right">${{d.points}} pts</td>
          </tr>
        `;
      }}).join('');

      const teamsRows = (st.constructors_standings || []).map(t => {{
        const pen = t.fia_penalty_points ? `<span class="text-red-400 text-xs">(${{t.fia_penalty_points}} WMSC)</span>` : '0';
        return `
          <tr class="border-b border-slate-800">
            <td class="p-2.5 font-mono-code font-bold text-white">${{t.pos}}º</td>
            <td class="p-2.5 text-white font-semibold">${{t.name}}</td>
            <td class="p-2.5 font-mono-code text-slate-400">${{t.gross_points}}</td>
            <td class="p-2.5 font-mono-code">${{pen}}</td>
            <td class="p-2.5 font-mono-code font-bold text-amber-400 text-right">${{t.net_points}} pts</td>
          </tr>
        `;
      }}).join('');

      body.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <h3 class="font-f1 font-bold text-sm uppercase tracking-wider text-amber-400 mb-3">🏎️ Mundial de Pilotos (Pós-Etapa 10)</h3>
            <div class="table-scroll-wrapper !m-0">
              <table class="w-full text-xs text-left">
                <thead>
                  <tr class="bg-slate-900 text-slate-400">
                    <th class="p-2.5">Pos</th><th class="p-2.5">Nº</th><th class="p-2.5">Piloto</th><th class="p-2.5">Equipe</th><th class="p-2.5">Vit</th><th class="p-2.5">Pód</th><th class="p-2.5 text-right">Pontos</th>
                  </tr>
                </thead>
                <tbody>${{driversRows}}</tbody>
              </table>
            </div>
          </div>
          <div>
            <h3 class="font-f1 font-bold text-sm uppercase tracking-wider text-sky-400 mb-3">🛠️ Mundial de Construtores (Pós-Etapa 10)</h3>
            <div class="table-scroll-wrapper !m-0">
              <table class="w-full text-xs text-left">
                <thead>
                  <tr class="bg-slate-900 text-slate-400">
                    <th class="p-2.5">Pos</th><th class="p-2.5">Construtor</th><th class="p-2.5">Brutos</th><th class="p-2.5">Dedução FIA</th><th class="p-2.5 text-right">Total Líquido</th>
                  </tr>
                </thead>
                <tbody>${{teamsRows}}</tbody>
              </table>
            </div>
          </div>
        </div>
      `;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }}

    function closeStandingsModal() {{
      const modal = document.getElementById('standingsModal');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }}

    let isMobilePreview = false;
    function toggleMobileFramePreview() {{
      isMobilePreview = !isMobilePreview;
      const btn = document.getElementById('mobilePreviewToggleBtn');
      if (isMobilePreview) {{
        document.body.style.maxWidth = '412px';
        document.body.style.margin = '12px auto';
        document.body.style.border = '8px solid #263044';
        document.body.style.borderRadius = '32px';
        document.body.style.boxShadow = '0 25px 60px rgba(0,0,0,0.85)';
        document.getElementById('leftSidebar').classList.add('lg:hidden');
        document.getElementById('mobileModulePills').classList.remove('lg:hidden');
        btn.innerHTML = '<span>🖥️</span><span>Voltar p/ Desktop</span>';
      }} else {{
        document.body.style.maxWidth = '';
        document.body.style.margin = '';
        document.body.style.border = '';
        document.body.style.borderRadius = '';
        document.body.style.boxShadow = '';
        document.getElementById('leftSidebar').classList.remove('lg:hidden');
        document.getElementById('mobileModulePills').classList.add('lg:hidden');
        btn.innerHTML = '<span>📱</span><span>Simular Mobile</span>';
      }}
    }}

    function renderStormWidget() {{
      const st = PORTAL_DATA.standings || {{}};
      const lastR = st.last_completed_round || PORTAL_DATA.rounds.length || 10;
      const topBadge = document.getElementById('topStandingsRoundBadge');
      if (topBadge) topBadge.textContent = `R${{lastR}}`;
      const header = document.getElementById('stormWidgetHeader');
      if (header) header.textContent = `🇧🇷 Brazilian Storm • Pós-R${{lastR}}`;

      const colors = {{ sarah: '#00d2be', felipe: '#00e64d', davi: '#00a0ff' }};
      const brDrivers = (st.drivers_standings || []).filter(d => ['sarah', 'felipe', 'davi'].includes(d.id));
      const container = document.getElementById('stormWidgetRows');
      if (!container) return;
      container.innerHTML = brDrivers.map(d => {{
        const c = colors[d.id] || '#38bdf8';
        const shortName = d.name.split(' ')[0];
        const statTag = d.wins > 0 ? `${{d.wins}}V` : `${{d.podiums}}P`;
        return `
          <div class="flex items-center justify-between py-1 px-2 rounded bg-slate-800/60" style="border-left: 2px solid ${{c}}">
            <span class="font-semibold text-white">${{d.pos}}º ${{shortName}} <span class="text-slate-400 font-mono-code">#${{d.car_number}}</span></span>
            <span class="font-mono-code font-bold" style="color: ${{c}}">${{d.points}} pts (${{statTag}})</span>
          </div>
        `;
      }}).join('');
    }}

    function parseUrlHashAndNavigate() {{
      renderStormWidget();
      const latestRound = PORTAL_DATA.rounds.length ? PORTAL_DATA.rounds[PORTAL_DATA.rounds.length - 1].num : 10;
      const hash = (window.location.hash || '').replace(/^#/, '');
      if (!hash) {{
        selectRound(latestRound);
        return;
      }}
      const params = new URLSearchParams(hash);
      if (params.has('setup')) {{
        openSetupWiki(params.get('setup'));
        return;
      }}
      const rNum = parseInt(params.get('r') || String(latestRound), 10);
      const artId = params.get('m') || null;
      selectRound(isNaN(rNum) ? latestRound : rNum, artId);
    }}

    // Initialize on URL Hash or Round 10 (GP da Espanha)
    window.addEventListener('DOMContentLoaded', () => {{
      parseUrlHashAndNavigate();
    }});
  </script>
</body>
</html>
"""
    index_path = portal_dir / "index.html"
    index_path.write_text(html_template, encoding="utf-8")
    root_index_path = root_dir / "index.html"
    root_index_path.write_text(html_template, encoding="utf-8")
    return index_path

