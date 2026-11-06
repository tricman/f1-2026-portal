"""
Showrunner Unified Document Database Interface.
Exposes the active IDataRepository instance (SqliteDocumentRepository by default).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.repositories.factory import get_repository
from src.repositories.sqlite_document_repository import SqliteDocumentRepository


def get_db():
    """Returns the active showrunner document repository."""
    return get_repository()
