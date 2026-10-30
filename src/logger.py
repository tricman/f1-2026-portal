"""
Structured JSON logger for Google Cloud Logging (Log Explorer).
Outputs standard GCP severity levels (INFO, WARNING, ERROR, CRITICAL)
and attaches arbitrary metadata for easy querying in Cloud Console.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def log_structured(
    severity: str,
    message: str,
    event: Optional[str] = None,
    round_num: Optional[int] = None,
    stage: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    exc: Optional[Exception] = None,
    **kwargs: Any,
) -> None:
    """
    Emits a structured JSON log line to stdout (or stderr for ERRORs),
    which is automatically parsed by Google Cloud Logging.
    """
    entry: Dict[str, Any] = {
        "severity": severity.upper(),
        "message": message,
        "service": "f1-showrunner",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if event:
        entry["event"] = event
    if round_num is not None:
        entry["round"] = round_num
    if stage:
        entry["stage"] = stage
    if details:
        entry["details"] = details
    if exc:
        entry["error_type"] = type(exc).__name__
        entry["error_message"] = str(exc)

    for k, v in kwargs.items():
        if k not in entry:
            entry[k] = v

    stream = sys.stderr if severity.upper() in ("ERROR", "CRITICAL") else sys.stdout
    stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    stream.flush()


def info(message: str, **kwargs: Any) -> None:
    log_structured("INFO", message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    log_structured("WARNING", message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    log_structured("ERROR", message, **kwargs)

