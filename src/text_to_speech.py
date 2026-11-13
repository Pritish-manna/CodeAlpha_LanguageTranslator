"""Text-to-speech with gTTS, provided separately from the Gemini translation backend.

gTTS needs internet access. Audio is generated only when explicitly requested.
"""

from __future__ import annotations

import io
from typing import Any, Callable

from src.utils import AppError, get_logger, validate_text

logger = get_logger(__name__)

MAX_TTS_CHARS = 5000

# Used only if gTTS cannot list its languages (e.g. not installed).
FALLBACK_TTS_LANGUAGES = frozenset(
    {"en", "hi", "bn", "es", "fr", "de", "ja", "zh-CN", "ar", "pt", "ru", "it", "ko", "ta", "te"}
)

_TTS_ALIASES = {"zh": "zh-CN"}


class TextToSpeechError(AppError):
    default_message = "Could not generate speech for this text."


def get_tts_languages() -> set[str]:
    """Language codes supported by gTTS."""
    try:
        from gtts.lang import tts_langs

        return set(tts_langs().keys())
    except Exception:  # noqa: BLE001 - fall back to the built-in list
        return set(FALLBACK_TTS_LANGUAGES)


def normalize_tts_code(code: str | None) -> str | None:
    """Map a translation language code to the matching gTTS code, or None."""
    if not code:
        return None
    candidate = _TTS_ALIASES.get(code, code)
    lookup = {item.lower(): item for item in get_tts_languages()}
    return lookup.get(candidate.lower())


def is_tts_supported(code: str | None) -> bool:
    return normalize_tts_code(code) is not None


def synthesize_speech(
    text: str,
    language_code: str,
    *,
    tts_factory: Callable[..., Any] | None = None,
    max_chars: int = MAX_TTS_CHARS,
) -> bytes:
    """Return MP3 bytes for ``text`` spoken in ``language_code``.

    ``tts_factory`` lets tests inject a fake gTTS class.
    """
    try:
        cleaned = validate_text(text, max_chars)
    except AppError as exc:
        raise TextToSpeechError(exc.user_message) from exc

    tts_code = normalize_tts_code(language_code)
    if tts_code is None:
        raise TextToSpeechError(f"Text-to-speech is not available for language '{language_code}'.")

    if tts_factory is None:
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise TextToSpeechError("The gTTS package is not installed. Run: pip install -r requirements.txt") from exc
        tts_factory = gTTS

    try:
        speech = tts_factory(text=cleaned, lang=tts_code)
        buffer = io.BytesIO()
        speech.write_to_fp(buffer)
        audio = buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - gTTS raises several types (network, HTTP, value)
        logger.error("Speech generation failed (%s)", type(exc).__name__)
        raise TextToSpeechError(
            "Speech generation failed. gTTS needs internet access and may be temporarily unavailable."
        ) from exc

    if not audio:
        raise TextToSpeechError("Speech generation returned no audio.")
    return audio
