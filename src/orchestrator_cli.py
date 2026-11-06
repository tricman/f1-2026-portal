import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Tuple, Optional, List, Any
from src.telemetry_merger import parse_free_practice_summary, merge_race_telemetry
from src.fia_calculator import update_championship_standings
from src.canon_ledger import CanonLedgerManager
from src.discord_gateway import DiscordGatewayClient
from src.portal_builder import build_editorial_portal, ROUND_METADATA, classify_module_badge
from src.season_manager import (
    get_season_dir,
    get_current_season_id,
    initialize_new_season,
    DEFAULT_NEXT_SEASON_GRID,
    list_available_seasons,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_dotenv_if_present() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith('"'):
            end_q = v.find('"', 1)
            v = v[1:end_q] if end_q != -1 else v.strip('"')
        elif v.startswith("'"):
            end_q = v.find("'", 1)
            v = v[1:end_q] if end_q != -1 else v.strip("'")
        else:
            v = v.split("#")[0].strip()
        if k not in os.environ:
            os.environ[k] = v


MODULE_PERSONAS: Dict[str, str] = {
    "Semana das Equipes": "F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'",
    "Coletiva de Imprensa FIA": "FIA Communications — Tom Clarkson",
    "Treino Livre": "FIA Technical Delegate — Jo Bauer",
    "Treino de Classificação": "FIA Race Direction — Niels Wittich & Jo Bauer",
    "Resultado Final": "FIA Stewards & Race Control",
    "Cerimônia do Pódio": "F1 TV World Feed & Drive to Survive Crew",
    "Atualização Classificação": "FIA World Motor Sport Council Secretariat",
    "Repercussão Imprensa": "Global F1 Media Hub (Band / Sky / Gazzetta / X)",
}


def resolve_persona_for_filename(filename: str) -> str:
    low = filename.lower()
    if "semana" in low:
        return "F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'"
    for key, persona in MODULE_PERSONAS.items():
        if key.lower() in low:
            return persona
    return "FIA Official Media Center"


def process_round_telemetry(r_num: int, r_folder: str, season_id: Optional[str] = None) -> None:
    round_dir = get_season_dir(ROOT_DIR, season_id) / r_folder
    tel_dir = round_dir / "telemetry"
    tel_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve CSV files dynamically (PaceDex manual export or UDP live recorder)
    tl_summary_files = [p for p in tel_dir.glob("*_TL.csv") if not p.name.endswith("_laps_TL.csv")]
    tl_laps_files = list(tel_dir.glob("*_laps_TL.csv"))
    race_laps_files = [p for p in tel_dir.glob("*_laps.csv") if not p.name.endswith("_laps_TL.csv")]
    race_summary_files = [
        p for p in tel_dir.glob("*.csv")
        if not p.name.endswith("_TL.csv") and not p.name.endswith("_laps.csv")
    ]

    tl_csv = tl_summary_files[0] if tl_summary_files else None
    tl_laps_csv = tl_laps_files[0] if tl_laps_files else None
    race_csv = race_summary_files[0] if race_summary_files else None
    race_laps_csv = race_laps_files[0] if race_laps_files else None

    if tl_csv and tl_laps_csv and tl_csv.exists() and tl_laps_csv.exists():
        fp_summary = parse_free_practice_summary(tl_csv, tl_laps_csv)
        (tel_dir / "fp_telemetry_merged.json").write_text(
            json.dumps(fp_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # 2. TV Overlay resolution (either from UDP Relay or Gemini Vision)
    tv_candidates = [
        tel_dir / f"tv_overlay_et{r_num:02d}.json",
        tel_dir / f"tv_overlay_et{r_num}.json",
        tel_dir / "tv_overlay.json",
    ]
    tv_file = next((f for f in tv_candidates if f.exists()), None)
    tv_overlay = json.loads(tv_file.read_text(encoding="utf-8")) if tv_file else {}

    if race_csv and race_laps_csv and race_csv.exists() and race_laps_csv.exists() and tv_overlay:
        race_merged = merge_race_telemetry(race_csv, race_laps_csv, tv_overlay)
    elif (tel_dir / "race_telemetry_merged.json").exists():
        race_merged = json.loads((tel_dir / "race_telemetry_merged.json").read_text(encoding="utf-8"))
    else:
        race_merged = tv_overlay

    (tel_dir / "race_telemetry_merged.json").write_text(
        json.dumps(race_merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # 3. Update standings
    meta = ROUND_METADATA.get(r_folder, {"name": f"GP da Etapa {r_num}"})
    standings_path = ROOT_DIR / "data" / "state" / "standings.json"
    if standings_path.exists() and race_merged:
        prev_standings = json.loads(standings_path.read_text(encoding="utf-8"))
        if prev_standings.get("last_completed_round", 0) == r_num - 1:
            updated_standings = update_championship_standings(
                prev_standings,
                race_merged,
                round_number=r_num,
                gp_name=meta.get("name", f"Etapa {r_num}"),
            )
            (ROOT_DIR / "data" / "state" / f"standings_et{r_num:02d}.json").write_text(
                json.dumps(updated_standings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    print(f"Round {r_num} ({r_folder}) telemetry merged and state updated successfully.")


def process_round_10_telemetry() -> None:
    process_round_telemetry(10, "et_10_espanha")


def deploy_portal_to_github_pages(commit_msg: str = "Auto-update F1 2026 Editorial Portal & FIA Wiki", season_id: Optional[str] = None) -> Path:
    """
    Rebuild `portal/index.html` and root `index.html` from all current Markdown/JSON files in `data/`
    and push directly to `https://github.com/tricman/f1-2026-portal.git` (GitHub Pages).
    """
    from src.logger import log_text

    out_path = build_editorial_portal(ROOT_DIR, season_id=season_id)
    log_text("[PORTAL BUILD] index.html e portal/portal_data.json recompilados com sucesso.")
    try:
        git_target_dir = ROOT_DIR if (ROOT_DIR / ".git").exists() else (ROOT_DIR / "portal")
        if (git_target_dir / ".git").exists():
            if git_target_dir == ROOT_DIR:
                subprocess.run(["git", "-C", str(git_target_dir), "add", "index.html", "portal", "data"], check=True)
            else:
                subprocess.run(["git", "-C", str(git_target_dir), "add", "index.html"], check=True)
            diff_res = subprocess.run(
                ["git", "-C", str(git_target_dir), "diff", "--cached", "--quiet"],
                check=False,
            )
            if diff_res.returncode != 0:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(git_target_dir),
                        "-c",
                        "user.name=tricman",
                        "-c",
                        "user.email=tricman@gmail.com",
                        "commit",
                        "-m",
                        commit_msg,
                    ],
                    check=True,
                )
                push_res = subprocess.run(
                    ["git", "-C", str(git_target_dir), "push", "origin", "main"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if push_res.returncode == 0:
                    log_text(f"[PORTAL PUSH] ✅ Portal publicado no GitHub Pages com sucesso! ({commit_msg})")
                else:
                    log_text(f"[PORTAL PUSH WARNING] Falha inicial no git push: {push_res.stderr.strip()}. Tentando auto-rebase...")
                    subprocess.run(["git", "-C", str(git_target_dir), "pull", "--rebase", "origin", "main"], check=False)
                    push_retry = subprocess.run(
                        ["git", "-C", str(git_target_dir), "push", "origin", "main"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if push_retry.returncode == 0:
                        log_text(f"[PORTAL PUSH] ✅ Portal publicado no GitHub Pages com sucesso após rebase! ({commit_msg})")
                    else:
                        log_text(f"[PORTAL PUSH WARNING] Falha no git push: {push_retry.stderr.strip()}")
            else:
                log_text("[PORTAL PUSH] Portal já estava sincronizado na última revisão (sem alterações pendentes).")
    except Exception as exc:
        log_text(f"[PORTAL ERROR] Erro durante o deploy do portal: {exc}")
    return out_path


def publish_round_to_discord(round_folder: str, teaser_mode: bool = True, base_portal_url: str = "", season_id: Optional[str] = None) -> None:
    round_dir = get_season_dir(ROOT_DIR, season_id) / round_folder
    if not round_dir.exists():
        raise FileNotFoundError(f"Round folder not found: {round_dir}")

    # Always rebuild & deploy the Portal first so deep links are immediately live
    deploy_portal_to_github_pages(f"Publish {round_folder} to F1 2026 Portal", season_id=season_id)

    client = DiscordGatewayClient()
    base_url = (base_portal_url or os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
    r_num = ROUND_METADATA.get(round_folder, {}).get("num", 10)

    # Sort strictly by F1 Weekend Chronological Order (M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8)
    md_files = sorted(
        round_dir.glob("*.md"),
        key=lambda f: (classify_module_badge(f.name)[0], f.name),
    )
    for md_file in md_files:
        order_num, short_tag, badge_label, _ = classify_module_badge(md_file.name)
        persona = resolve_persona_for_filename(md_file.name)
        if teaser_mode:
            encoded_m = urllib.parse.quote(f"{round_folder}__{md_file.stem}")
            deep_link = f"{base_url}/?v={int(time.time())}#r={r_num}&m={encoded_m}"
            print(f"Publishing Teaser [{short_tag}: {md_file.name}] as '{persona}' -> {deep_link}...")
            msg_id = client.publish_editorial_teaser(
                markdown_text=md_file.read_text(encoding="utf-8"),
                article_title=f"[{short_tag}] {md_file.stem}",
                portal_url=deep_link,
                persona_name=persona,
            )
            print(f"  -> Sent single Teaser message ({msg_id})")
        else:
            print(f"Publishing Full Report [{md_file.name}] as '{persona}'...")
            msg_ids = client.publish_markdown_report(
                md_file.read_text(encoding="utf-8"),
                persona_name=persona,
            )
            print(f"  -> Sent {len(msg_ids)} chunks ({msg_ids})")
        time.sleep(1.0)

    if client.bot_token and client.ingest_channel_id:
        meta = ROUND_METADATA.get(round_folder, {"name": f"Etapa {r_num}", "flag": "🏁"})
        client.post_channel_message(
            client.ingest_channel_id,
            f"✅ **PUBLICAÇÃO CONCLUÍDA — {meta['flag']} Etapa {r_num}: {meta['name']}**\n"
            f"• **{len(md_files)} Módulos Narrativos** publicados em ordem cronológica (`M1 ➔ M3 ➔ M4 ➔ M5 ➔ M6 ➔ M7 ➔ M8`) em <#{client.publish_channel_id}>!\n"
            f"• 🌐 **Portal Editorial Mobile & FIA Wiki Atualizado:** <{base_url}/#r={r_num}>",
        )


ROUND_NUMBER_TO_FOLDER: Dict[int, str] = {
    meta["num"]: folder for folder, meta in ROUND_METADATA.items()
}


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in res.stdout
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def start_udp_listener(root_dir: Optional[Path] = None, round_num: Optional[int] = None) -> Tuple[bool, str]:
    import sys
    root = root_dir or ROOT_DIR
    lock_file = root / "data" / "state" / "listener.pid"
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                return False, (
                    f"⚠️ **O LISTENER UDP JÁ ESTÁ ATIVO!**\n"
                    f"• **PID:** `{pid}` (Porta 20777)\n"
                    f"• Digite `status telemetria` para monitorar ou `parar escuta f1` para encerrar."
                )
            else:
                lock_file.unlink(missing_ok=True)
        except Exception:
            lock_file.unlink(missing_ok=True)

    cmd = [sys.executable, "-m", "src.udp_relay"]
    if round_num is not None:
        cmd.extend(["--round", str(round_num)])

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)
        if proc.poll() is None:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            lock_file.write_text(str(proc.pid), encoding="utf-8")
            target_round = round_num or 11
            target_folder = ROUND_NUMBER_TO_FOLDER.get(target_round, f"et_{target_round:02d}")
            return True, (
                f"🟢 **LISTENER UDP DE TELEMETRIA F1 24 INICIADO COM SUCESSO!**\n"
                f"• **Porta UDP:** `20777` (Pronto para receber dados em tempo real do jogo EA F1 24)\n"
                f"• **Processo (PID):** `{proc.pid}`\n"
                f"• **Destino:** `data/seasons/season_01/{target_folder}/telemetry/`\n"
                f"• Digite `status telemetria` para monitorar ou `parar escuta f1` para encerrar."
            )
        else:
            return False, "❌ Falha ao inicializar o Listener UDP. O processo encerrou prematuramente."
    except Exception as exc:
        return False, f"❌ Erro ao disparar processo do Listener UDP: {exc}"


def get_udp_listener_status(root_dir: Optional[Path] = None) -> Tuple[bool, str]:
    root = root_dir or ROOT_DIR
    lock_file = root / "data" / "state" / "listener.pid"
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                return True, (
                    f"🟢 **STATUS DA TELEMETRIA UDP (F1 24):**\n"
                    f"• **Estado:** ATIVO / ESCUTANDO\n"
                    f"• **PID:** `{pid}`\n"
                    f"• **Porta UDP:** `20777`\n"
                    f"• Digite `parar escuta f1` para encerrar o serviço."
                )
            else:
                lock_file.unlink(missing_ok=True)
        except Exception:
            lock_file.unlink(missing_ok=True)
    return False, (
        f"⚪ **STATUS DA TELEMETRIA UDP:**\n"
        f"• **Estado:** 🔴 INATIVO\n"
        f"• O Listener UDP não está em execução no momento.\n"
        f"• Digite `iniciar escuta f1` para iniciar a escuta na porta 20777."
    )


def stop_udp_listener(root_dir: Optional[Path] = None) -> Tuple[bool, str]:
    root = root_dir or ROOT_DIR
    lock_file = root / "data" / "state" / "listener.pid"
    if not lock_file.exists():
        return False, "ℹ️ Nenhum Listener UDP de Telemetria está ativo no momento."
    try:
        pid = int(lock_file.read_text(encoding="utf-8").strip())
        if is_pid_running(pid):
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        lock_file.unlink(missing_ok=True)
        return True, (
            f"🛑 **LISTENER UDP DE TELEMETRIA ENCERRADO!**\n"
            f"• Processo PID `{pid}` finalizado com sucesso.\n"
            f"• Porta 20777 liberada."
        )
    except Exception as exc:
        lock_file.unlink(missing_ok=True)
        return True, f"🛑 Listener encerrado: {exc}"


def execute_stage_rollback(round_num: int, scope: str = "sessao", season_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes a granular rollback for a given round.
    
    Scopes:
      - 'sessao': Reverts post-race session (M3 to M8, telemetry, photos, debriefs, standings).
      - 'coletiva': Reverts M2 Coletiva de Imprensa and its Canon Ledger events.
      - 'semana': Resets M1 Semana das Equipes and M1.5 Dilema.
      - 'tudo': Complete round reset (resets everything for the round).
      
    Safety:
      - Rounds 1 to 10 in season_01 are canonical history and cannot be rolled back.
    """
    eff_season = season_id or get_current_season_id()
    if eff_season == "season_01" and round_num < 11:
        raise ValueError(
            f"Proteção de integridade ativada: As Etapas 01 a 10 da Temporada 1 são canônicas e imutáveis. "
            f"O rollback só é permitido para a Etapa 11 em diante (solicitado: Etapa {round_num})."
        )

    scope_norm = scope.lower().strip().replace("sessão", "sessao")
    valid_scopes = {"sessao", "coletiva", "semana", "tudo"}
    if scope_norm not in valid_scopes:
        raise ValueError(f"Escopo de rollback inválido: '{scope}'. Opções válidas: {sorted(list(valid_scopes))}")

    round_folder = ROUND_NUMBER_TO_FOLDER.get(round_num, f"et_{round_num:02d}")
    round_dir = get_season_dir(ROOT_DIR, eff_season) / round_folder

    deleted_files: List[str] = []
    purged_events = 0
    reverted_standings = False

    # 1. ROLLBACK DE SESSÃO (M3 A M8, TELEMETRIA, FOTOS, DEBRIEFING, STANDINGS)
    if scope_norm in ("sessao", "tudo"):
        if round_dir.exists():
            # Delete telemetry files
            tel_dir = round_dir / "telemetry"
            if tel_dir.exists():
                for p in list(tel_dir.iterdir()):
                    if p.is_file():
                        p.unlink()
                        deleted_files.append(str(p.relative_to(ROOT_DIR)))

            # Delete photos
            photos_dir = round_dir / "photos"
            if photos_dir.exists():
                for p in list(photos_dir.iterdir()):
                    if p.is_file():
                        p.unlink()
                        deleted_files.append(str(p.relative_to(ROOT_DIR)))

            # Delete debriefing
            deb_dir = round_dir / "debriefing"
            if deb_dir.exists():
                for p in list(deb_dir.iterdir()):
                    if p.is_file():
                        p.unlink()
                        deleted_files.append(str(p.relative_to(ROOT_DIR)))

            # Delete M3 to M8 markdown files
            for md_file in list(round_dir.glob("*.md")):
                order_num, _, _, _ = classify_module_badge(md_file.name)
                if order_num >= 3:
                    md_file.unlink()
                    deleted_files.append(str(md_file.relative_to(ROOT_DIR)))

        # Standings rollback
        standings_et_snap = ROOT_DIR / "data" / "state" / f"standings_et{round_num:02d}.json"
        if standings_et_snap.exists():
            standings_et_snap.unlink()
            deleted_files.append(str(standings_et_snap.relative_to(ROOT_DIR)))

        prev_standings_file = ROOT_DIR / "data" / "state" / f"standings_et{round_num - 1:02d}.json"
        standings_file = ROOT_DIR / "data" / "state" / "standings.json"
        if prev_standings_file.exists():
            shutil.copy2(prev_standings_file, standings_file)
            reverted_standings = True
        elif standings_file.exists():
            try:
                curr_st = json.loads(standings_file.read_text(encoding="utf-8"))
                if curr_st.get("last_completed_round", 0) >= round_num:
                    curr_st["last_completed_round"] = round_num - 1
                    drivers_key = "drivers_standings" if "drivers_standings" in curr_st else "drivers"
                    constructors_key = "constructors_standings" if "constructors_standings" in curr_st else "constructors"

                    driver_pts_map = {}
                    for d in curr_st.get(drivers_key, []):
                        pts_by_r = d.get("points_by_round", [])
                        if len(pts_by_r) >= round_num:
                            d["points_by_round"] = pts_by_r[:round_num - 1]
                            d["points"] = sum(d["points_by_round"])
                        driver_pts_map[d.get("id")] = d.get("points", 0)

                    for c in curr_st.get(constructors_key, []):
                        if "drivers" in c:
                            pts = sum(driver_pts_map.get(did, 0) for did in c.get("drivers", []))
                            if "net_points" in c:
                                c["net_points"] = pts
                            if "gross_points" in c:
                                c["gross_points"] = pts
                            c["points"] = pts

                    if drivers_key in curr_st:
                        curr_st[drivers_key] = sorted(curr_st[drivers_key], key=lambda x: x.get("points", 0), reverse=True)
                    if constructors_key in curr_st:
                        curr_st[constructors_key] = sorted(
                            curr_st[constructors_key],
                            key=lambda x: x.get("net_points", x.get("points", 0)),
                            reverse=True,
                        )
                    standings_file.write_text(json.dumps(curr_st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    reverted_standings = True
            except Exception as exc:
                print(f"[Rollback Warning] Standings fallback error: {exc}")

        # Purge Canon Ledger events for M3 to M8
        ledger_file = ROOT_DIR / "data" / "state" / "canon_ledger.json"
        if ledger_file.exists():
            try:
                ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
                events = ledger_data.get("events", [])
                kept_events = []
                for ev in events:
                    if ev.get("round") == round_num:
                        mod = str(ev.get("module", "")).upper()
                        if any(x in mod for x in ["M3", "M4", "M5", "M6", "M7", "M8", "TELEMETRIA", "CORRIDA", "QUALIFYING"]):
                            purged_events += 1
                            continue
                    kept_events.append(ev)
                ledger_data["events"] = kept_events
                ledger_file.write_text(json.dumps(ledger_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

        # Reset discord session state if active
        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        if state_file.exists():
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                if int(st.get("active_round_num", 0)) == round_num:
                    st["status"] = "IDLE"
                    st["session_files"] = []
                    st["debrief_messages"] = []
                    state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

    # 2. ROLLBACK DE COLETIVA (M2)
    if scope_norm in ("coletiva", "tudo"):
        if round_dir.exists():
            for md_file in list(round_dir.glob("*.md")):
                order_num, _, _, _ = classify_module_badge(md_file.name)
                if order_num == 2 or "coletiva" in md_file.name.lower():
                    md_file.unlink()
                    deleted_files.append(str(md_file.relative_to(ROOT_DIR)))

        press_file = ROOT_DIR / "data" / "state" / f"press_conf_et{round_num:02d}.json"
        if press_file.exists():
            press_file.unlink()
            deleted_files.append(str(press_file.relative_to(ROOT_DIR)))

        ledger_file = ROOT_DIR / "data" / "state" / "canon_ledger.json"
        if ledger_file.exists():
            try:
                ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
                events = ledger_data.get("events", [])
                kept_events = []
                for ev in events:
                    if ev.get("round") == round_num and "M2" in str(ev.get("module", "")).upper():
                        purged_events += 1
                        continue
                    kept_events.append(ev)
                ledger_data["events"] = kept_events
                ledger_file.write_text(json.dumps(ledger_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

    # 3. ROLLBACK DE SEMANA (M1 E M1.5)
    if scope_norm in ("semana", "tudo"):
        if round_dir.exists():
            for md_file in list(round_dir.glob("*.md")):
                order_num, _, _, _ = classify_module_badge(md_file.name)
                if order_num == 1 or "semana" in md_file.name.lower() or "dilema" in md_file.name.lower():
                    md_file.unlink()
                    deleted_files.append(str(md_file.relative_to(ROOT_DIR)))

        ledger_file = ROOT_DIR / "data" / "state" / "canon_ledger.json"
        if ledger_file.exists():
            try:
                ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
                events = ledger_data.get("events", [])
                kept_events = []
                for ev in events:
                    if ev.get("round") == round_num and any(x in str(ev.get("module", "")).upper() for x in ["M1", "DILEMA"]):
                        purged_events += 1
                        continue
                    kept_events.append(ev)
                ledger_data["events"] = kept_events
                ledger_file.write_text(json.dumps(ledger_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        if state_file.exists():
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                if int(st.get("active_round_num", 0)) == round_num:
                    st["semana_day"] = 1
                    state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

    # 4. ROLLBACK TUDO (CLEANUP RESIDUAL)
    if scope_norm == "tudo":
        if round_dir.exists():
            for sub in ["telemetry", "photos", "debriefing"]:
                (round_dir / sub).mkdir(parents=True, exist_ok=True)
            for f in list(round_dir.iterdir()):
                if f.is_file():
                    f.unlink()
                    deleted_files.append(str(f.relative_to(ROOT_DIR)))

        ledger_file = ROOT_DIR / "data" / "state" / "canon_ledger.json"
        if ledger_file.exists():
            try:
                ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
                events = ledger_data.get("events", [])
                kept_events = [ev for ev in events if ev.get("round") != round_num]
                purged_events += (len(events) - len(kept_events))
                ledger_data["events"] = kept_events
                ledger_file.write_text(json.dumps(ledger_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        if state_file.exists():
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                st["status"] = "IDLE"
                st["session_files"] = []
                st["debrief_messages"] = []
                st["semana_day"] = 1
                state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

    # Always recompile the editorial portal to reflect the purged state
    build_editorial_portal(ROOT_DIR)

    return {
        "success": True,
        "round_num": round_num,
        "round_folder": round_folder,
        "scope": scope_norm,
        "deleted_files_count": len(deleted_files),
        "deleted_files": deleted_files,
        "purged_canon_events": purged_events,
        "reverted_standings": reverted_standings,
    }


def acquire_listener_lock(lock_file: Path) -> None:
    """Ensure strictly ONE listener instance runs on the machine at any time."""
    import atexit
    current_pid = os.getpid()
    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text(encoding="utf-8").strip())
            if old_pid != current_pid:
                res = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {old_pid}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if str(old_pid) in res.stdout:
                    subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True, check=False)
                    time.sleep(0.5)
        except Exception:
            pass

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(str(current_pid), encoding="utf-8")

    def _cleanup():
        try:
            if lock_file.exists() and int(lock_file.read_text(encoding="utf-8").strip()) == os.getpid():
                lock_file.unlink()
        except Exception:
            pass

    atexit.register(_cleanup)


def main() -> None:
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(description="F1 24 Showrunner & FIA Orchestrator CLI")
    parser.add_argument(
        "--action",
        choices=[
            "process-et10",
            "build-portal",
            "deploy-portal",
            "publish-discord",
            "publish-teaser",
            "publish-round",
            "sync-ingest",
            "watch-discord",
            "autonomous-session",
            "generate-m1",
            "generate-dilemma",
            "rollback",
            "start-listener",
            "stop-listener",
            "status-listener",
            "start-season",
            "list-seasons",
        ],
        default="process-et10",
        help="Action to execute",
    )
    parser.add_argument("--file", type=str, help="Markdown file to publish to Discord")
    parser.add_argument("--round-folder", type=str, default="et_10_espanha", help="Season round folder name")
    parser.add_argument("--round", type=int, default=11, help="Championship round number (e.g. 11 for Áustria)")
    parser.add_argument("--season", type=str, default=None, help="Active season identifier (e.g. season_01, season_02)")
    parser.add_argument("--new-season", type=str, default="season_02", help="Target new season identifier to initialize")
    parser.add_argument("--grid-file", type=str, default=None, help="Path to JSON file with new season driver grid registry")
    parser.add_argument(
        "--scope",
        type=str,
        default="sessao",
        choices=["sessao", "coletiva", "semana", "tudo"],
        help="Rollback scope (sessao, coletiva, semana, tudo)",
    )
    parser.add_argument("--persona", type=str, default=None)
    parser.add_argument("--portal-url", type=str, default=None, help="Base public URL of the Editorial Portal")
    parser.add_argument("--interval", type=int, default=15, help="Polling interval in seconds for watch-discord")
    parser.add_argument("--max-hours", type=float, default=4.0, help="Max session listener duration in hours (default: 4h)")
    parser.add_argument(
        "--sentinel",
        action="store_true",
        help="Exit immediately on first poll if no active 'inicio da etapa' session is found; otherwise stay alive for up to --max-hours",
    )
    args = parser.parse_args()

    if args.action == "process-et10":
        process_round_10_telemetry()
    elif args.action == "build-portal":
        out_path = build_editorial_portal(ROOT_DIR, season_id=args.season)
        print(f"Editorial Portal & Season Wiki built successfully at: {out_path}")
    elif args.action == "deploy-portal":
        out_path = deploy_portal_to_github_pages(season_id=args.season)
        print(f"Editorial Portal deployed from: {out_path}")
    elif args.action == "publish-discord":
        if not args.file:
            raise ValueError("--file is required when --action=publish-discord")
        file_path = Path(args.file)
        md_text = file_path.read_text(encoding="utf-8")
        persona = args.persona or resolve_persona_for_filename(file_path.name)
        client = DiscordGatewayClient()
        msg_ids = client.publish_markdown_report(md_text, persona_name=persona)
        print(f"Published {len(msg_ids)} chunks to Discord as '{persona}': {msg_ids}")
    elif args.action == "publish-teaser":
        if not args.file:
            raise ValueError("--file is required when --action=publish-teaser")
        deploy_portal_to_github_pages(f"Update portal for {Path(args.file).stem}")
        file_path = Path(args.file)
        md_text = file_path.read_text(encoding="utf-8")
        persona = args.persona or resolve_persona_for_filename(file_path.name)
        base_url = (args.portal_url or os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
        folder_name = file_path.parent.name
        r_num = ROUND_METADATA.get(folder_name, {}).get("num", 10)
        encoded_m = urllib.parse.quote(f"{folder_name}__{file_path.stem}")
        deep_link = f"{base_url}/?v={int(time.time())}#r={r_num}&m={encoded_m}"
        client = DiscordGatewayClient()
        msg_id = client.publish_editorial_teaser(
            markdown_text=md_text,
            article_title=file_path.stem,
            portal_url=deep_link,
            persona_name=persona,
        )
        print(f"Published single-message Teaser to Discord as '{persona}' (Message ID: {msg_id})")
    elif args.action == "generate-m1":
        from src.ai_showrunner import GeminiFreeTierClient, generate_pre_race_m1
        r_num = ROUND_METADATA.get(args.round_folder, {}).get("num", 10)
        ai_client = GeminiFreeTierClient()
        m1_file = generate_pre_race_m1(ROOT_DIR, r_num, args.round_folder, ai_client, force_regenerate=getattr(args, "force", False))
        print(f"M1 consolidado com sucesso: {m1_file}")
        deploy_portal_to_github_pages(f"Publish M1 {args.round_folder} to F1 2026 Portal")
        client = DiscordGatewayClient()
        base_url = (args.portal_url or os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
        import urllib.parse
        encoded_m = urllib.parse.quote(f"{args.round_folder}__{m1_file.stem}")
        deep_link = f"{base_url}/?v={int(time.time())}#r={r_num}&m={encoded_m}"
        msg_id = client.publish_editorial_teaser(
            markdown_text=m1_file.read_text(encoding="utf-8"),
            article_title=f"[M1 · PRÉ-SEMANA] {m1_file.stem}",
            portal_url=deep_link,
            persona_name="F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'",
        )
        print(f"M1 Teaser publicado no Discord: {msg_id} -> {deep_link}")
    elif args.action == "generate-dilemma":
        from src.ai_showrunner import generate_paddock_dilemma
        r_num = getattr(args, "round", 11)
        r_folder = getattr(args, "round_folder", f"et_{r_num:02d}")
        res = generate_paddock_dilemma(ROOT_DIR, r_num, r_folder)
        print(f"Dilema M1.5 gerado com sucesso para {res.get('driver_name')} ({res.get('target_driver')})")
    elif args.action == "publish-round":
        publish_round_to_discord(args.round_folder, teaser_mode=True, base_portal_url=args.portal_url or "", season_id=args.season)
    elif args.action == "rollback":
        res = execute_stage_rollback(round_num=args.round, scope=args.scope, season_id=args.season)
        print(f"Rollback executado com sucesso:\n{json.dumps(res, indent=2, ensure_ascii=False)}")
    elif args.action == "start-season":
        grid_data = DEFAULT_NEXT_SEASON_GRID
        if args.grid_file:
            g_path = Path(args.grid_file)
            if g_path.exists():
                grid_data = json.loads(g_path.read_text(encoding="utf-8"))
        res = initialize_new_season(
            root_dir=ROOT_DIR,
            new_season_id=args.new_season,
            new_grid_registry=grid_data,
            prev_season_id=args.season or "season_01",
        )
        print(f"Nova temporada inicializada com sucesso:\n{json.dumps(res, indent=2, ensure_ascii=False)}")
    elif args.action == "list-seasons":
        seasons = list_available_seasons(ROOT_DIR)
        print(f"Temporadas disponíveis no diretório 'data/seasons/': {seasons}")
    elif args.action == "start-listener":
        ok, msg = start_udp_listener(ROOT_DIR, round_num=args.round)
        print(msg)
    elif args.action == "stop-listener":
        ok, msg = stop_udp_listener(ROOT_DIR)
        print(msg)
    elif args.action == "status-listener":
        ok, msg = get_udp_listener_status(ROOT_DIR)
        print(msg)
    elif args.action == "sync-ingest":
        client = DiscordGatewayClient()
        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        session_state = client.process_voice_channel_session(ROOT_DIR, state_file)
        print(
            f"Session Status: {session_state.get('status')} | "
            f"Active Round: {session_state.get('active_round_folder')} | "
            f"New Files: {session_state.get('last_poll_new_files')}"
        )
    elif args.action == "watch-discord":
        client = DiscordGatewayClient()
        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        if state_file.exists():
            st = json.loads(state_file.read_text(encoding="utf-8"))
            if st.get("status") == "READY_FOR_SIMULATION":
                st["status"] = "IDLE"
                state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            f"[F1 Showrunner Bot] Escutando o Canal de Voz (#1457392708355096580) a cada {args.interval}s...\n"
            f"  -> Digite 'inicio da etapa <N>' no chat do canal de voz para abrir o pacote da corrida.\n"
            f"  -> Suba as fotos da TV, CSVs do PaceDex e áudios/textos de debriefing.\n"
            f"  -> Digite 'final da etapa <N>' para encerrar a coleta e disparar o processamento!"
        )
        while True:
            session_state = client.process_voice_channel_session(ROOT_DIR, state_file)
            stage_ev = session_state.get("last_poll_stage_event")
            new_f = session_state.get("last_poll_new_files", [])
            if stage_ev:
                print(f"[STAGE EVENT] {stage_ev} -> Status: {session_state.get('status')}")
            if new_f:
                log_text(f"[FILES DOWNLOADED] {len(new_f)} arquivos salvos: {new_f}")
            if stage_ev and stage_ev.startswith("END_ROUND_") and session_state.get("status") == "READY_FOR_SIMULATION":
                r_folder = session_state.get("active_round_folder") or args.round_folder
                print(f"[READY FOR SIMULATION] Etapa encerrada no Discord ({r_folder})!")
                break
            time.sleep(args.interval)
    elif args.action == "autonomous-session":
        acquire_listener_lock(ROOT_DIR / "data" / "state" / "listener.pid")
        from src.ai_showrunner import (
            GeminiFreeTierClient,
            finalize_round_transition,
            generate_post_race_modules,
        )

        client = DiscordGatewayClient()
        state_file = ROOT_DIR / "data" / "state" / "discord_session_state.json"
        if state_file.exists():
            st = json.loads(state_file.read_text(encoding="utf-8"))
            if st.get("status") == "READY_FOR_SIMULATION":
                st["status"] = "IDLE"
                state_file.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        max_seconds = int(args.max_hours * 3600)
        deadline = time.time() + max_seconds
        first_poll = True
        from src.logger import log_text
        log_text(
            f"[Autonomous Showrunner Session] Sentinel={args.sentinel} | Janela máxima: {args.max_hours:.1f}h ({max_seconds}s) "
            f"escutando #1457392708355096580 a cada {args.interval}s..."
        )
        poll_count = 0
        while time.time() < deadline:
            poll_count += 1
            session_state = client.process_voice_channel_session(ROOT_DIR, state_file)
            stage_ev = session_state.get("last_poll_stage_event")
            new_f = session_state.get("last_poll_new_files", [])
            status_now = session_state.get("status", "IDLE")

            if poll_count % 8 == 1:
                r_curr = session_state.get("active_round_num", 11)
                d_curr = session_state.get("semana_day", 1)
                log_text(f"[HEARTBEAT] Listener escutando #1457392708355096580 a cada {args.interval}s | Status: {status_now} (Etapa {r_curr}, Dia {d_curr}/4)")

            if stage_ev:
                log_text(f"🔔 [STAGE EVENT DETECTADO] {stage_ev} -> Status: {status_now}")
            if new_f:
                log_text(f"📥 [DOWNLOAD CONCLUÍDO] {len(new_f)} arquivos salvos: {new_f}")

            # In --sentinel mode (scheduled pulse), exit in 2s if no round was started
            if first_poll and args.sentinel and status_now == "IDLE":
                print("[Sentinel Check] Nenhum 'inicio da etapa <N>' pendente no Canal de Voz. Encerrando em 2s (Scale-to-Zero).")
                break
            first_poll = False

            if stage_ev and stage_ev.startswith("SEMANA_TICK_"):
                parts = stage_ev.split("_")
                day = int(parts[-1]) if len(parts) >= 4 and parts[-1].isdigit() else 1
                r_num = int(session_state.get("active_round_num") or 10)
                r_folder = session_state.get("active_round_folder") or f"et_{r_num:02d}"
                from src.ai_showrunner import generate_m1_daily_episode
                ai_client = GeminiFreeTierClient()
                m1_path, teaser = generate_m1_daily_episode(ROOT_DIR, r_num, r_folder, day, ai_client)
                deploy_portal_to_github_pages(f"Publish M1 Day {day} {r_folder} to F1 2026 Portal")
                import urllib.parse
                base_url = (args.portal_url or os.environ.get("PORTAL_PUBLIC_URL") or "https://tricman.github.io/f1-2026-portal/").rstrip("/")
                encoded_m = urllib.parse.quote(f"{r_folder}__{m1_path.stem}")
                deep_link = f"{base_url}/?v={int(time.time())}#r={r_num}&m={encoded_m}"
                client.publish_editorial_teaser(
                    markdown_text=f"{teaser}\n\n📖 **Leia o dossiê completo atualizado no Portal:**\n{deep_link}",
                    article_title=f"[M1 · DIA {day}/4] A Semana da F1 ({r_folder})",
                    portal_url=deep_link,
                    persona_name="F1 Paddock Insider | Blog 'A F1 Que Você Não Vê'",
                )

            if stage_ev and stage_ev.startswith("START_PRESS_CONF_"):
                r_num = int(session_state.get("active_round_num") or 10)
                r_folder = session_state.get("active_round_folder") or f"et_{r_num:02d}"
                eff_season = session_state.get("active_season_id") or args.season or get_current_season_id()
                from src.press_conference import PressConferenceSession
                sess = PressConferenceSession(ROOT_DIR, r_num, r_folder, season_id=eff_season)
                opening = sess.start_session()
                client.post_channel_message(client.ingest_channel_id, opening)
                time.sleep(2.0)
                is_lock = False
                while not is_lock and not sess.state.get("completed"):
                    q_text, is_lock, driver = sess.advance_to_next_question()
                    if q_text:
                        client.post_channel_message(client.ingest_channel_id, q_text)
                    if not is_lock and not sess.state.get("completed"):
                        time.sleep(3.0)

            if stage_ev and stage_ev.startswith("END_ROUND_") and status_now == "READY_FOR_SIMULATION":
                r_folder = session_state.get("active_round_folder") or args.round_folder
                r_num = int(session_state.get("active_round_num") or 10)
                eff_season = session_state.get("active_season_id") or args.season or get_current_season_id()
                print(f"[AUTONOMOUS PIPELINE] Iniciando simulação 100% autônoma para {r_folder} (Etapa {r_num}, {eff_season})...")
                round_dir = get_season_dir(ROOT_DIR, eff_season) / r_folder
                debrief_dir = round_dir / "debriefing"
                photos_dir = round_dir / "photos"
                tel_dir = round_dir / "telemetry"
                meta = ROUND_METADATA.get(r_folder, {"name": f"Etapa {r_num}"})
                ai_client = GeminiFreeTierClient()
                if ai_client.api_key:
                    ai_client.transcribe_audio_debriefs(debrief_dir)
                    if photos_dir.exists() and any(photos_dir.iterdir()):
                        ai_client.extract_tv_overlay_from_photos(
                            photos_dir=photos_dir,
                            output_json_path=tel_dir / f"tv_overlay_et{r_num:02d}.json",
                            round_num=r_num,
                            round_name=meta["name"],
                        )
                process_round_telemetry(r_num, r_folder, season_id=eff_season)
                if ai_client.api_key:
                    if client.bot_token and client.ingest_channel_id:
                        client.post_channel_message(
                            client.ingest_channel_id,
                            f"🤖 **[Gemini 3.8 Flash — Modo Autônomo]** Telemetria PaceDex fundida e pontuação da FIA calculada! "
                            f"Redigindo os 6 Módulos Oficiais da Etapa {r_num} (`M3 ➔ M8`)... (~60s)",
                        )
                    generate_post_race_modules(ROOT_DIR, r_num, r_folder, ai_client)
                finalize_round_transition(ROOT_DIR, r_num, r_folder, ai_client=ai_client)
                publish_round_to_discord(r_folder, teaser_mode=True, base_portal_url=args.portal_url or "", season_id=eff_season)
                print(f"[AUTONOMOUS PIPELINE] Etapa {r_num} concluída e publicada! Encerrando sessão (Early Exit).")
                break
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

