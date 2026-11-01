"""
Repository Factory for F1 Showrunner.
Dynamically resolves Local JSON vs GCP Firestore based on STORAGE_BACKEND.
"""
from __future__ import annotations

import os
from typing import Optional
from src.repositories.base_repository import IDataRepository
from src.repositories.local_repository import LocalJsonRepository
from src.logger import log_text

_GLOBAL_REPO_INSTANCE: Optional[IDataRepository] = None


def get_repository(force_refresh: bool = False) -> IDataRepository:
    """
    Returns the configured IDataRepository singleton:
      - 'firestore': Google Cloud Firestore NoSQL
      - 'local': Local filesystem JSON in data/state/
    Defaults to 'local' if STORAGE_BACKEND is not set or if Firestore cannot be reached.
    """
    global _GLOBAL_REPO_INSTANCE
    if _GLOBAL_REPO_INSTANCE is not None and not force_refresh:
        return _GLOBAL_REPO_INSTANCE

    try:
        from src.orchestrator_cli import load_dotenv_if_present
        load_dotenv_if_present()
    except Exception:
        pass

    backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()

    if backend == "firestore":
        try:
            from src.repositories.firestore_repository import FirestoreRepository
            project_id = os.environ.get("GCP_PROJECT_ID")
            repo = FirestoreRepository(project_id=project_id)
            log_text(f"[REPOSITORY FACTORY] Conectado ao Google Cloud Firestore (Projeto: {repo.project_id or 'default'}).")
            _GLOBAL_REPO_INSTANCE = repo
            return repo
        except Exception as exc:
            log_text(f"[REPOSITORY FACTORY WARNING] Falha ao conectar ao Firestore ({exc}). Fazendo fallback para LocalJsonRepository.")
            repo = LocalJsonRepository()
            _GLOBAL_REPO_INSTANCE = repo
            return repo

    repo = LocalJsonRepository()
    _GLOBAL_REPO_INSTANCE = repo
    return repo

