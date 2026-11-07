"""
Structured JSON logger & High-Fidelity Tracing Engine for F1 2026 Showrunner.
Supports:
  - Severity levels: TRACE (5), DEBUG (10), INFO (20), WARNING (30), ERROR (40).
  - High-resolution JSON Lines tracing stream (logs/trace.log) with 20MB rotation and secret redaction.
  - Human-readable operational stream (logs/showrunner.log) for real-time tailing.
  - Native correlation with src.tracer (trace_id, span_id, duration_ms).
  - Explicit purge routine for log lifecycle maintenance.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Force UTF-8 on Windows consoles to prevent charmap UnicodeEncodeError
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SHOWRUNNER_LOG_FILE = LOGS_DIR / "showrunner.log"
TRACE_LOG_FILE = LOGS_DIR / "trace.log"

# Auto-load .env for LOG_LEVEL and credentials
_env_file = ROOT_DIR / ".env"
if _env_file.exists():
    try:
        for _raw_line in _env_file.read_text(encoding="utf-8").splitlines():
            _l = _raw_line.strip()
            if not _l or _l.startswith("#") or "=" not in _l:
                continue
            _k, _v = _l.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'").split("#")[0].strip()
            if _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

LEVEL_MAP: Dict[str, int] = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_current_log_level: int = LEVEL_MAP.get(os.environ.get("LOG_LEVEL", "INFO").upper(), 20)

# Secret redaction regexes
_REDACT_PATTERNS = [
    (re.compile(r"AIza[A-Za-z0-9_\-]{30,45}"), "AIza[REDACTED_GEMINI_KEY]"),
    (re.compile(r"Bot\s+[A-Za-z0-9_\.-]{30,}"), "Bot [REDACTED_DISCORD_TOKEN]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\.-]{30,}"), "Bearer [REDACTED_BEARER_TOKEN]"),
]


def sanitize_secrets(value: Any) -> Any:
    """
    Recursively scans strings, dicts, and lists to mask sensitive API keys and tokens.
    """
    if isinstance(value, str):
        masked = value
        for pattern, repl in _REDACT_PATTERNS:
            masked = pattern.sub(repl, masked)

        # Dynamic redaction from environment secrets
        for env_k, env_v in os.environ.items():
            if any(sub in env_k for sub in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                if len(env_v) >= 8 and env_v in masked:
                    masked = masked.replace(env_v, f"[REDACTED_{env_k}]")
        return masked

    if isinstance(value, dict):
        clean_dict = {}
        for k, v in value.items():
            if any(sub in str(k).upper() for sub in ("TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH")):
                clean_dict[k] = "[REDACTED_SECRET]"
            else:
                clean_dict[k] = sanitize_secrets(v)
        return clean_dict

    if isinstance(value, list):
        return [sanitize_secrets(item) for item in value]

    return value


# Configure 20MB Rotating File Handler for JSON Lines TRACE stream
_trace_handler: Optional[RotatingFileHandler] = None


def _get_trace_handler() -> RotatingFileHandler:
    global _trace_handler
    if _trace_handler is None:
        _trace_handler = RotatingFileHandler(
            str(TRACE_LOG_FILE),
            maxBytes=20 * 1024 * 1024,  # 20 MB
            backupCount=5,
            encoding="utf-8",
        )
    return _trace_handler


def close_trace_handler() -> None:
    """Closes and resets the rotating trace file handler."""
    global _trace_handler
    if _trace_handler is not None:
        try:
            _trace_handler.close()
        except Exception:
            pass
        _trace_handler = None


def set_log_level(level: Union[str, int]) -> None:
    """Dynamically updates the active log level threshold."""
    global _current_log_level
    if isinstance(level, str):
        _current_log_level = LEVEL_MAP.get(level.upper().strip(), 20)
    else:
        _current_log_level = int(level)


def get_log_level() -> int:
    """Returns the current log level numerical threshold."""
    return _current_log_level


def is_trace_enabled() -> bool:
    """True if active level is TRACE (<= 5)."""
    return _current_log_level <= 5


def _append_to_showrunner_log(line: str) -> None:
    """Appends human-readable line to logs/showrunner.log."""
    try:
        with open(SHOWRUNNER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _write_trace_entry(entry: Dict[str, Any]) -> None:
    """Writes a sanitized JSON Line to the rotating logs/trace.log."""
    try:
        handler = _get_trace_handler()
        line = json.dumps(sanitize_secrets(entry), ensure_ascii=False)
        handler.stream.write(line + "\n")
        handler.flush()
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
    Core structured log emitter.
    - If level < active threshold, log is discarded.
    - TRACE logs go exclusively to logs/trace.log (JSON Lines).
    - INFO+ logs go to stdout, logs/showrunner.log, and also logs/trace.log if TRACE is enabled.
    """
    sev_upper = severity.upper()
    sev_level = LEVEL_MAP.get(sev_upper, 20)

    if sev_level < _current_log_level:
        return

    now = datetime.now(timezone.utc)
    entry: Dict[str, Any] = {
        "timestamp": now.isoformat(),
        "severity": sev_upper,
        "message": sanitize_secrets(message),
        "service": "f1-showrunner",
    }

    # Context Tracing Enrichment from src.tracer
    try:
        from src.tracer import (
            get_current_trace_id,
            get_current_span_id,
            get_current_parent_span_id,
            get_trace_context,
        )
        tid = get_current_trace_id()
        sid = get_current_span_id()
        psid = get_current_parent_span_id()
        if tid:
            entry["trace_id"] = tid
        if sid:
            entry["span_id"] = sid
        if psid:
            entry["parent_span_id"] = psid
        tags = get_trace_context()
        if tags:
            entry["context"] = sanitize_secrets(tags)
    except Exception:
        pass

    if event:
        entry["event"] = event
    if round_num is not None:
        entry["round"] = round_num
    if stage:
        entry["stage"] = stage
    if details:
        entry["details"] = sanitize_secrets(details)
    if exc:
        entry["error_type"] = type(exc).__name__
        entry["error_message"] = sanitize_secrets(str(exc))

    for k, v in kwargs.items():
        if k not in entry:
            entry[k] = sanitize_secrets(v)

    # 1. If active level includes TRACE (or event is TRACE), write to trace.log
    if is_trace_enabled() or sev_level <= 5:
        _write_trace_entry(entry)

    # 2. If event is TRACE only, do not spam showrunner.log or console
    if sev_level <= 5:
        return

    # 3. Output to console and showrunner.log for INFO and higher
    stream = sys.stderr if sev_level >= 40 else sys.stdout
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
    trace_tag = f" [trace:{entry.get('trace_id')[:8]}]" if "trace_id" in entry else ""
    _append_to_showrunner_log(f"[{local_time}] [{sev_upper}]{evt_tag}{r_tag}{trace_tag} {sanitize_secrets(message)}")


def log_text(message: str) -> None:
    """Append arbitrary text directly to logs/showrunner.log and stdout."""
    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = sanitize_secrets(message)
    line = f"[{local_time}] {clean_msg}"
    try:
        print(line, flush=True)
    except Exception:
        try:
            print(line.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass
    _append_to_showrunner_log(line)


def trace(message: str, **kwargs: Any) -> None:
    """Emits high-fidelity TRACE log (payloads, internal steps, network dumps)."""
    log_structured("TRACE", message, **kwargs)


def debug(message: str, **kwargs: Any) -> None:
    """Emits DEBUG log."""
    log_structured("DEBUG", message, **kwargs)


def info(message: str, **kwargs: Any) -> None:
    """Emits standard operational INFO log."""
    log_structured("INFO", message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """Emits WARNING log."""
    log_structured("WARNING", message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Emits ERROR log."""
    log_structured("ERROR", message, **kwargs)


def purge_old_trace_logs(
    logs_dir: Optional[Path] = None,
    max_days: int = 7,
    max_files: int = 5,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Purges rotated trace log files older than max_days or exceeding max_files.
    If force=True, also clears the active trace.log file.
    """
    target_dir = logs_dir or LOGS_DIR
    deleted_files: List[str] = []
    freed_bytes = 0
    now = time.time()
    cutoff_seconds = max_days * 86400

    # Collect rotated trace files: trace.log.1, trace.log.2, etc.
    rotated = sorted(
        list(target_dir.glob("trace.log.*")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # 1. Delete files exceeding max_files
    excess_files = rotated[max_files:]
    for f in excess_files:
        try:
            sz = f.stat().st_size
            f.unlink()
            deleted_files.append(f.name)
            freed_bytes += sz
        except Exception:
            pass

    # 2. Delete remaining rotated files older than cutoff
    for f in rotated[:max_files]:
        try:
            age = now - f.stat().st_mtime
            if age > cutoff_seconds:
                sz = f.stat().st_size
                f.unlink()
                deleted_files.append(f.name)
                freed_bytes += sz
        except Exception:
            pass

    # 3. If force is requested, truncate active trace.log
    active_trace = target_dir / "trace.log"
    if force and active_trace.exists():
        try:
            sz = active_trace.stat().st_size
            active_trace.write_text("", encoding="utf-8")
            deleted_files.append("trace.log (truncated)")
            freed_bytes += sz
        except Exception:
            pass

    return {
        "deleted_files_count": len(deleted_files),
        "deleted_files": deleted_files,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
    }
