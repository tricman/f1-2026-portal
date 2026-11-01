"""
Base Repository Interface for F1 Showrunner State & Canon Management.
Supports both Local JSON (Desktop offline) and Google Cloud Firestore (GCP Serverless).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDataRepository(ABC):
    """Abstract Data Repository Contract for F1 Showrunner."""

    # 1. Canon Ledger & Reputations
    @abstractmethod
    def get_canon_ledger(self) -> Dict[str, Any]:
        """Returns the full canon ledger dictionary (season, reputation, events)."""
        pass

    @abstractmethod
    def save_canon_ledger(self, data: Dict[str, Any]) -> None:
        """Persists the full canon ledger dictionary."""
        pass

    @abstractmethod
    def append_canon_event(
        self,
        event_id: str,
        round_num: int,
        module: str,
        summary: str,
        entities: List[str],
        status: str = "OPEN",
    ) -> None:
        """Appends a single narrative event to the canon ledger."""
        pass

    # 2. Championship Standings
    @abstractmethod
    def get_standings(self, round_num: Optional[int] = None) -> Dict[str, Any]:
        """Returns drivers and constructors standings for the given round or latest."""
        pass

    @abstractmethod
    def save_standings(self, data: Dict[str, Any], round_num: Optional[int] = None) -> None:
        """Saves drivers and constructors standings."""
        pass

    # 3. Press Conference Interactive State (M2)
    @abstractmethod
    def get_press_conference(self, round_num: int) -> Optional[Dict[str, Any]]:
        """Returns the interactive state of the FIA press conference for a given round."""
        pass

    @abstractmethod
    def save_press_conference(self, round_num: int, data: Dict[str, Any]) -> None:
        """Persists the state of the FIA press conference for a given round."""
        pass

    # 4. Voice Channel & Bot Ingest Session
    @abstractmethod
    def get_session_state(self) -> Dict[str, Any]:
        """Returns the current state machine of the Discord voice channel listener."""
        pass

    @abstractmethod
    def save_session_state(self, data: Dict[str, Any]) -> None:
        """Persists the state machine of the Discord voice channel listener."""
        pass

