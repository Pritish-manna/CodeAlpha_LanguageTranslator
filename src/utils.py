"""Shared helpers: errors, settings, input validation, history, copy-button HTML.

Nothing in this module imports Streamlit or any Google package, so it can be
unit-tested without network access or credentials.
"""

from __future__ import annotations

import html
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, MutableSequence

MAX_INPUT_CHARS = 5000
DEFAULT_TIMEOUT_SECONDS = 30.0
HISTORY_LIMIT = 50
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------


class AppError(Exception):
    """Base class for errors whose message is safe to show to the user."""

    default_message = "Something went wrong."

    def __init__(self, message: str | None = None) -> None:
        self.user_message = message or self.default_message
        super().__init__(self.user_message)


class ValidationError(AppError):
    default_message = "The input is not valid."


class EmptyTextError(ValidationError):
    default_message = "Please enter some text to translate."


class TextTooLongError(ValidationError):
    default_message = "The text is too long to translate in one request."


# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------


def get_logger(name: str = "translation_tool") -> logging.Logger:
    """Return a logger, configuring basic logging once if nothing else did.

    Never log user text or credentials through this logger.
    """
    if not logging.getLogger().handlers:
        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, level_name, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    return logging.getLogger(name)


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------


def load_env_file(path: str | None = None) -> bool:
    """Load a .env file into os.environ if python-dotenv is installed.

    Existing environment variables are never overridden.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is in requirements.txt
        return False
    return bool(load_dotenv(path, override=False))


def _positive_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


@dataclass(frozen=True)
class Settings:
    """Application settings read from environment variables."""

    gemini_api_key: str | None
    gemini_model: str
    timeout_seconds: float
    max_input_chars: int
    log_level: str


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from .env + environment variables."""

    if env is None:
        load_env_file()
        env = os.environ

    return Settings(
        gemini_api_key=(env.get("GEMINI_API_KEY") or "").strip() or None,
        gemini_model=(env.get("GEMINI_MODEL") or "gemini-3.8-flash").strip(),
        timeout_seconds=_positive_float(
            env.get("TRANSLATION_TIMEOUT_SECONDS"),
            DEFAULT_TIMEOUT_SECONDS,
        ),
        max_input_chars=_positive_int(
            env.get("MAX_INPUT_CHARS"),
            MAX_INPUT_CHARS,
        ),
        log_level=(env.get("LOG_LEVEL") or "INFO").upper(),
    )

# ----------------------------------------------------------------------------
# Text validation
# ----------------------------------------------------------------------------


def validate_text(text: Any, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Return the text ready to send to the API, or raise a ValidationError.

    Only leading/trailing whitespace is stripped; inner line breaks are kept.
    """
    if not isinstance(text, str):
        raise ValidationError("The text to translate must be a string.")
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise EmptyTextError()
    if len(cleaned) > max_chars:
        raise TextTooLongError(
            f"The text has {len(cleaned):,} characters, but the limit is "
            f"{max_chars:,}. Please shorten it or translate it in parts."
        )
    return cleaned


def count_characters(text: str | None) -> int:
    """Number of Unicode characters (code points) in ``text``."""
    return len(text) if text else 0


# ----------------------------------------------------------------------------
# Session history
# ----------------------------------------------------------------------------


def format_timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime(TIMESTAMP_FORMAT)


def make_history_entry(
    original: str,
    translated: str,
    source_label: str,
    target_label: str,
    *,
    is_demo: bool = False,
    entry_id: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "original": original,
        "translated": translated,
        "source": source_label,
        "target": target_label,
        "is_demo": is_demo,
        "timestamp": timestamp or format_timestamp(),
    }


_DEDUPE_KEYS = ("original", "translated", "source", "target", "is_demo")


def add_history_entry(
    history: MutableSequence[dict[str, Any]],
    entry: dict[str, Any],
    limit: int = HISTORY_LIMIT,
) -> bool:
    """Append ``entry`` unless it duplicates a rerun. Returns True if added.

    An entry is a duplicate when its id was already stored, or when it matches
    the most recent entry exactly.
    """
    entry_id = entry.get("id")
    if entry_id is not None and any(item.get("id") == entry_id for item in history):
        return False
    if history and all(history[-1].get(key) == entry.get(key) for key in _DEDUPE_KEYS):
        return False
    history.append(entry)
    while len(history) > limit:
        history.pop(0)
    return True


# ----------------------------------------------------------------------------
# Copy-to-clipboard button (self-contained HTML for an iframe)
# ----------------------------------------------------------------------------


def _js_string(value: str) -> str:
    """Encode ``value`` as a JavaScript string literal that is safe inside <script>."""
    encoded = json.dumps(value)  # ensure_ascii=True -> ASCII-only output
    return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_copy_button_html(text: str, label: str = "Copy translation") -> str:
    """Return a small HTML document with a working copy-to-clipboard button.

    Tries ``navigator.clipboard`` first, then ``document.execCommand('copy')``,
    and always shows a success or failure message.
    """
    payload = _js_string(text)
    safe_label = html.escape(label)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: transparent;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .row {{ display: flex; align-items: center; gap: 10px; padding: 4px 0; }}
  button {{ background: #2563eb; color: #fff; border: 0; border-radius: 8px;
    padding: 8px 14px; font-size: 14px; cursor: pointer; }}
  button:hover {{ background: #1d4ed8; }}
  #msg {{ font-size: 13px; }}
  .ok {{ color: #16a34a; }}
  .err {{ color: #dc2626; }}
</style>
</head>
<body>
<div class="row">
  <button id="copy-btn" type="button">&#128203; {safe_label}</button>
  <span id="msg" role="status" aria-live="polite"></span>
</div>
<script>
  const textToCopy = {payload};
  const button = document.getElementById("copy-btn");
  const message = document.getElementById("msg");

  function fallbackCopy(value) {{
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    let success = false;
    try {{ success = document.execCommand("copy"); }} catch (err) {{ success = false; }}
    document.body.removeChild(area);
    return success;
  }}

  button.addEventListener("click", async () => {{
    let success = false;
    try {{
      if (navigator.clipboard && window.isSecureContext) {{
        await navigator.clipboard.writeText(textToCopy);
        success = true;
      }}
    }} catch (err) {{
      success = false;
    }}
    if (!success) {{ success = fallbackCopy(textToCopy); }}
    message.textContent = success
      ? "Copied to clipboard!"
      : "Copy failed - select the text and press Ctrl+C.";
    message.className = success ? "ok" : "err";
    setTimeout(() => {{ message.textContent = ""; }}, 3500);
  }});
</script>
</body>
</html>
"""
