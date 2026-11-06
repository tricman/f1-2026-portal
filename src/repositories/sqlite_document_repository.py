"""
Local SQLite Document Store Repository for F1 Showrunner.
Provides ACID transactions, WAL mode, JSON document storage, and atomic rollbacks
with zero external dependencies (100% Python standard library).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.repositories.base_repository import IDataRepository


class SqliteDocumentRepository(IDataRepository):
    """
    Embedded SQLite Document Store implementation of IDataRepository.
    Stores schema-less JSON documents in collections, with automatic synchronization
    to/from data/state/*.json for transparent compatibility.
    """

    def __init__(self, root_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent.parent
        self.state_dir = self.root_dir / "data" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (self.state_dir / "showrunner_database.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    collection_name TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection_name, doc_id)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(collection_name);"
            )
            conn.commit()

        # Seed from existing state JSON files if database table is empty
        self._seed_from_files_if_empty()

    def _seed_from_files_if_empty(self) -> None:
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT COUNT(*) FROM collections")
                count = cur.fetchone()[0]
                if count == 0:
                    # Seed canon ledger
                    canon_file = self.state_dir / "canon_ledger.json"
                    if canon_file.exists():
                        data = json.loads(canon_file.read_text(encoding="utf-8"))
                        self._upsert_doc(conn, "canon_ledger", "main", data)

                    # Seed standings
                    standings_file = self.state_dir / "standings.json"
                    if standings_file.exists():
                        data = json.loads(standings_file.read_text(encoding="utf-8"))
                        self._upsert_doc(conn, "standings", "main", data)

                    # Seed snapshots
                    for snap in self.state_dir.glob("standings_et*.json"):
                        data = json.loads(snap.read_text(encoding="utf-8"))
                        self._upsert_doc(conn, "standings_history", snap.stem, data)

                    # Seed session state
                    session_file = self.state_dir / "discord_session_state.json"
                    if session_file.exists():
                        data = json.loads(session_file.read_text(encoding="utf-8"))
                        self._upsert_doc(conn, "session_state", "main", data)
                    conn.commit()
        except Exception:
            pass

    def _upsert_doc(
        self, conn: sqlite3.Connection, collection: str, doc_id: str, data: Dict[str, Any]
    ) -> None:
        json_str = json.dumps(data, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO collections (collection_name, doc_id, data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(collection_name, doc_id) DO UPDATE SET
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (collection, doc_id, json_str),
        )

    def _get_doc(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT data FROM collections WHERE collection_name = ? AND doc_id = ?",
                (collection, doc_id),
            )
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None

    # --------------------------------------------------------------------------
    # Generic Document CRUD
    # --------------------------------------------------------------------------
    def save_document(self, collection: str, doc_id: str, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, collection, doc_id, data)
            conn.commit()

    def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._get_doc(collection, doc_id)

    def find_documents(
        self, collection: str, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT doc_id, data FROM collections WHERE collection_name = ?",
                (collection,),
            )
            rows = cur.fetchall()
            results: List[Dict[str, Any]] = []
            for doc_id, raw_data in rows:
                doc = json.loads(raw_data)
                if filter_dict:
                    match = all(doc.get(k) == v for k, v in filter_dict.items())
                    if not match:
                        continue
                doc_with_meta = dict(doc)
                doc_with_meta["doc_id"] = doc_id
                results.append(doc_with_meta)
            return results

    def delete_document(self, collection: str, doc_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM collections WHERE collection_name = ? AND doc_id = ?",
                (collection, doc_id),
            )
            conn.commit()
            return cur.rowcount > 0

    # --------------------------------------------------------------------------
    # 1. Canon Ledger
    # --------------------------------------------------------------------------
    def get_canon_ledger(self) -> Dict[str, Any]:
        doc = self._get_doc("canon_ledger", "main")
        if doc is not None:
            return doc
        # Fallback to file
        canon_file = self.state_dir / "canon_ledger.json"
        if canon_file.exists():
            try:
                return json.loads(canon_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"season": 2026, "reputation": {}, "events": []}

    def save_canon_ledger(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "canon_ledger", "main", data)
            conn.commit()
        # Keep JSON file in sync
        canon_file = self.state_dir / "canon_ledger.json"
        canon_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def append_canon_event(
        self,
        event_id: str | Dict[str, Any],
        round_num: Optional[int] = None,
        module: Optional[str] = None,
        summary: Optional[str] = None,
        entities: Optional[List[str]] = None,
        status: str = "OPEN",
    ) -> None:
        if isinstance(event_id, dict):
            ev_data = event_id
            e_id = ev_data.get("event_id", "EVENT-000")
            r_num = int(ev_data.get("round_num", ev_data.get("round", 0)))
            mod = ev_data.get("module", "CANON")
            summ = ev_data.get("summary", "")
            ents = ev_data.get("entities", [])
            stat = ev_data.get("status", "OPEN")
        else:
            e_id = event_id
            r_num = round_num or 0
            mod = module or "CANON"
            summ = summary or ""
            ents = entities or []
            stat = status

        ledger = self.get_canon_ledger()
        events = ledger.setdefault("events", [])
        found = False
        for ev in events:
            if ev.get("event_id") == e_id:
                ev["summary"] = summ
                ev["entities"] = ents
                ev["status"] = stat
                found = True
                break
        if not found:
            events.append(
                {
                    "event_id": e_id,
                    "round": r_num,
                    "module": mod,
                    "summary": summ,
                    "entities": ents,
                    "status": stat,
                }
            )
        self.save_canon_ledger(ledger)

    def list_canon_events(self, round_num: Optional[int] = None) -> List[Dict[str, Any]]:
        ledger = self.get_canon_ledger()
        events = ledger.get("events", [])
        if round_num is not None:
            return [e for e in events if e.get("round") == round_num]
        return list(events)

    # --------------------------------------------------------------------------
    # 2. Championship Standings
    # --------------------------------------------------------------------------
    def get_standings(self, round_num: Optional[int] = None) -> Dict[str, Any]:
        doc_id = f"standings_et{round_num:02d}" if round_num is not None else "main"
        collection = "standings_history" if round_num is not None else "standings"
        doc = self._get_doc(collection, doc_id)
        if doc is not None:
            return doc
        # Fallback to file
        f_name = f"standings_et{round_num:02d}.json" if round_num is not None else "standings.json"
        target_f = self.state_dir / f_name
        if target_f.exists():
            try:
                return json.loads(target_f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"season": 2026, "last_completed_round": 0, "drivers": [], "constructors": []}

    def save_standings(self, data: Dict[str, Any], round_num: Optional[int] = None) -> None:
        doc_id = f"standings_et{round_num:02d}" if round_num is not None else "main"
        collection = "standings_history" if round_num is not None else "standings"
        with self._get_connection() as conn:
            self._upsert_doc(conn, collection, doc_id, data)
            if round_num is not None:
                self._upsert_doc(conn, "standings", "main", data)
            conn.commit()
        # Keep JSON files in sync
        if round_num is not None:
            snap_file = self.state_dir / f"standings_et{round_num:02d}.json"
            snap_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        main_file = self.state_dir / "standings.json"
        main_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --------------------------------------------------------------------------
    # 3. Press Conference Interactive State (M2)
    # --------------------------------------------------------------------------
    def get_press_conference(self, round_num: int) -> Optional[Dict[str, Any]]:
        doc = self._get_doc("press_conferences", f"et_{round_num:02d}")
        if doc is not None:
            return doc
        f = self.state_dir / f"press_conf_et{round_num:02d}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def save_press_conference(self, round_num: int, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "press_conferences", f"et_{round_num:02d}", data)
            conn.commit()
        f = self.state_dir / f"press_conf_et{round_num:02d}.json"
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --------------------------------------------------------------------------
    # 4. Voice Channel & Bot Ingest Session
    # --------------------------------------------------------------------------
    def get_session_state(self) -> Dict[str, Any]:
        doc = self._get_doc("session_state", "main")
        if doc is not None:
            return doc
        f = self.state_dir / "discord_session_state.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"status": "IDLE", "active_round_num": 11, "session_files": []}

    def save_session_state(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "session_state", "main", data)
            conn.commit()
        f = self.state_dir / "discord_session_state.json"
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --------------------------------------------------------------------------
    # 5. Paddock Dilemmas (M1.5) & Telemetry Collections
    # --------------------------------------------------------------------------
    def get_paddock_dilemma(self, round_num: int) -> Optional[Dict[str, Any]]:
        doc = self._get_doc("dilemmas", f"et_{round_num:02d}")
        if doc is not None:
            return doc
        f = self.state_dir / f"dilemma_et{round_num:02d}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def save_paddock_dilemma(self, round_num: int, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "dilemmas", f"et_{round_num:02d}", data)
            conn.commit()
        f = self.state_dir / f"dilemma_et{round_num:02d}.json"
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get_dilemma_choice(self, round_num: int) -> Optional[Dict[str, Any]]:
        doc = self._get_doc("dilemma_choices", f"et_{round_num:02d}")
        if doc is not None:
            return doc
        dil = self.get_paddock_dilemma(round_num)
        if dil and "resolution" in dil:
            return dil["resolution"]
        return None

    def save_dilemma_choice(self, round_num: int, choice_data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "dilemma_choices", f"et_{round_num:02d}", choice_data)
            conn.commit()

    def get_race_telemetry(self, round_num: int, season_id: str = "season_01") -> Optional[Dict[str, Any]]:
        return self._get_doc("race_telemetry", f"{season_id}_et_{round_num:02d}")

    def save_race_telemetry(
        self, round_num: int, data: Dict[str, Any], season_id: str = "season_01"
    ) -> None:
        with self._get_connection() as conn:
            self._upsert_doc(conn, "race_telemetry", f"{season_id}_et_{round_num:02d}", data)
            conn.commit()
