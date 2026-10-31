"""
Structured JSON logger for Google Cloud Logging (Log Explorer)
and Local Log File (logs/showrunner.log) for real-time tailing.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Force UTF-8 on Windows consoles to prevent charmap UnicodeEncodeError
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "showrunner.log"


def _append_to_file(line: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
    Emits a structured JSON log line to stdout and appends a clean
    human-readable line to logs/showrunner.log.
    """
    now = datetime.now(timezone.utc)
    entry: Dict[str, Any] = {
        "severity": severity.upper(),
        "message": message,
        "service": "f1-showrunner",
        "timestamp": now.isoformat(),
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
    try:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        stream.flush()
    except Exception:
        try:
            stream.write(json.dumps(entry, ensure_ascii=True) + "\n")
            stream.flush()
        except Exception:
            pass

    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    evt_tag = f" [{event}]" if event else ""
    r_tag = f" [R{round_num}]" if round_num else ""
    _append_to_file(f"[{local_time}] [{severity.upper()}]{evt_tag}{r_tag} {message}")


def log_text(message: str) -> None:
    """Append arbitrary text directly to logs/showrunner.log and stdout."""
    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{local_time}] {message}"
    try:
        print(line, flush=True)
    except Exception:
        try:
            print(line.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass
    _append_to_file(line)


def info(message: str, **kwargs: Any) -> None:
    log_structured("INFO", message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    log_structured("WARNING", message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    log_structured("ERROR", message, **kwargs)
