"""
Google Cloud Firestore NoSQL Repository Implementation for F1 Showrunner.
Enables resilient, serverless persistence on GCP Cloud Run (Free Tier compliant).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from src.repositories.base_repository import IDataRepository
from src.logger import log_text

try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False


class FirestoreRepository(IDataRepository):
    """
    Serverless Firestore implementation for Google Cloud Run.
    Collections:
      - `f1_seasons/{season_id}` (e.g. '2026') -> document with `canon_ledger`
      - `f1_standings/{round_key}` (e.g. 'current', 'et_10') -> standings document
      - `f1_press_conferences/et_{round:02d}` -> interactive press conference state
      - `f1_sessions/discord_voice_channel` -> state machine for Discord ingest
    """

    def __init__(self, project_id: Optional[str] = None):
        if not HAS_FIRESTORE:
            raise ImportError(
                "google-cloud-firestore não está instalado. Execute: pip install google-cloud-firestore"
            )
        self.project_id = (
            project_id
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        self.db = firestore.Client(project=self.project_id)
        self.season = "2026"

    # 1. Canon Ledger
    def get_canon_ledger(self) -> Dict[str, Any]:
        doc_ref = self.db.collection("f1_seasons").document(self.season)
        snap = doc_ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            return data.get("canon_ledger", {"season": 2026, "reputation": {}, "events": []})
        return {"season": 2026, "reputation": {}, "events": []}

    def save_canon_ledger(self, data: Dict[str, Any]) -> None:
        doc_ref = self.db.collection("f1_seasons").document(self.season)
        doc_ref.set({"canon_ledger": data, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        # Mirror to local file if available for instant editor inspection
        try:
            from pathlib import Path
            import json
            local_file = Path(__file__).resolve().parent.parent.parent / "data" / "state" / "canon_ledger.json"
            local_file.parent.mkdir(parents=True, exist_ok=True)
            local_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

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
        events = ledger.setdefault("events", [])
        found = False
        for ev in events:
            if ev.get("event_id") == event_id:
                ev["summary"] = summary
                ev["entities"] = entities
                ev["status"] = status
                found = True
                break
        if not found:
            events.append({
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
        key = f"et_{round_num:02d}" if round_num is not None else "latest"
        doc_ref = self.db.collection("f1_standings").document(key)
        snap = doc_ref.get()
        if snap.exists:
            return snap.to_dict() or {"drivers_standings": [], "constructors_standings": []}
        return {"drivers_standings": [], "constructors_standings": []}

    def save_standings(self, data: Dict[str, Any], round_num: Optional[int] = None) -> None:
        payload = dict(data)
        payload["updated_at"] = firestore.SERVER_TIMESTAMP
        # Save as latest
        self.db.collection("f1_standings").document("latest").set(payload)
        # If round is specified, save snapshot
        if round_num is not None:
            self.db.collection("f1_standings").document(f"et_{round_num:02d}").set(payload)

    # 3. Press Conference Interactive State
    def get_press_conference(self, round_num: int) -> Optional[Dict[str, Any]]:
        key = f"et_{round_num:02d}"
        doc_ref = self.db.collection("f1_press_conferences").document(key)
        snap = doc_ref.get()
        return snap.to_dict() if snap.exists else None

    def save_press_conference(self, round_num: int, data: Dict[str, Any]) -> None:
        key = f"et_{round_num:02d}"
        payload = dict(data)
        payload["updated_at"] = firestore.SERVER_TIMESTAMP
        self.db.collection("f1_press_conferences").document(key).set(payload)

    # 4. Voice Channel & Bot Ingest Session
    def get_session_state(self) -> Dict[str, Any]:
        doc_ref = self.db.collection("f1_sessions").document("discord_voice_channel")
        snap = doc_ref.get()
        if snap.exists:
            return snap.to_dict() or {}
        return {
            "status": "IDLE",
            "active_round_num": None,
            "active_round_folder": None,
            "last_message_id": None,
            "downloaded_keys": [],
            "debrief_messages": [],
            "processed_msg_ids": [],
        }

    def save_session_state(self, data: Dict[str, Any]) -> None:
        payload = dict(data)
        payload["updated_at"] = firestore.SERVER_TIMESTAMP
        self.db.collection("f1_sessions").document("discord_voice_channel").set(payload)

