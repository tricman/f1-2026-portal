"""
Local Filesystem JSON Repository Implementation for F1 Showrunner.
Operates on data/state/*.json for 100% local, offline development.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.repositories.base_repository import IDataRepository


class LocalJsonRepository(IDataRepository):
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent.parent
        self.state_dir = self.root_dir / "data" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.canon_file = self.state_dir / "canon_ledger.json"
        self.standings_file = self.state_dir / "standings.json"
        self.session_file = self.state_dir / "discord_session_state.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return default
        return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 1. Canon Ledger
    def get_canon_ledger(self) -> Dict[str, Any]:
        default = {
            "season": 2026,
            "reputation": {},
            "events": [],
        }
        return self._read_json(self.canon_file, default)

    def save_canon_ledger(self, data: Dict[str, Any]) -> None:
        self._write_json(self.canon_file, data)

    def append_canon_event(
        self,
        event_id: str,
        round_num: int,
        module: str,
        summary: str,
        entities: List[str],
        status: str = "OPEN",
    ) -> None:
        ledger = self.get_canon_ledger()
        existing_ids = {e.get("event_id") for e in ledger.get("events", [])}
        if event_id not in existing_ids:
            ledger.setdefault("events", []).append({
                "event_id": event_id,
                "round": round_num,
                "module": module,
                "summary": summary,
                "entities": entities,
                "status": status,
            })
            self.save_canon_ledger(ledger)

    # 2. Championship Standings
    def get_standings(self, round_num: Optional[int] = None) -> Dict[str, Any]:
        if round_num is not None:
            r_file = self.state_dir / f"standings_et{round_num:02d}.json"
            if r_file.exists():
                return self._read_json(r_file, {"drivers_standings": [], "constructors_standings": []})
        return self._read_json(self.standings_file, {"drivers_standings": [], "constructors_standings": []})

    def save_standings(self, data: Dict[str, Any], round_num: Optional[int] = None) -> None:
        self._write_json(self.standings_file, data)
        if round_num is not None:
            r_file = self.state_dir / f"standings_et{round_num:02d}.json"
            self._write_json(r_file, data)

    # 3. Press Conference Interactive State
    def get_press_conference(self, round_num: int) -> Optional[Dict[str, Any]]:
        pc_file = self.state_dir / f"press_conf_et{round_num:02d}.json"
        if pc_file.exists():
            return self._read_json(pc_file, None)
        return None

    def save_press_conference(self, round_num: int, data: Dict[str, Any]) -> None:
        pc_file = self.state_dir / f"press_conf_et{round_num:02d}.json"
        self._write_json(pc_file, data)

    # 4. Voice Channel & Bot Ingest Session
    def get_session_state(self) -> Dict[str, Any]:
        default = {
            "status": "IDLE",
            "active_round_num": None,
            "active_round_folder": None,
            "last_message_id": None,
            "downloaded_keys": [],
            "debrief_messages": [],
            "processed_msg_ids": [],
        }
        return self._read_json(self.session_file, default)

    def save_session_state(self, data: Dict[str, Any]) -> None:
        self._write_json(self.session_file, data)

