

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from src.languages import validate_language_codes
from src.utils import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_INPUT_CHARS,
    AppError,
    TextTooLongError,
    get_logger,
    load_env_file,
    load_settings,
    validate_text,
)

logger = get_logger(__name__)




# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------


class TranslationError(AppError):
    default_message = "The translation could not be completed."


class DependencyMissingError(TranslationError):
    default_message = "A required package is missing. Run: pip install -r requirements.txt"


class MissingCredentialsError(TranslationError):
    default_message = "Gemini API key not found. Add GEMINI_API_KEY to your .env file."


class InvalidCredentialsError(TranslationError):
    default_message = "Gemini rejected the API key. Check your API key and try again."


class BillingOrQuotaError(TranslationError):
    default_message = "Gemini API quota or usage limit reached. Please try again later."


class NetworkError(TranslationError):
    default_message = "Could not connect to Gemini. Check your internet connection."


class TranslationTimeoutError(TranslationError):
    default_message = "The translation request timed out. Please try again."


class UnexpectedResponseError(TranslationError):
    default_message = "Gemini returned an unexpected response. No translation was produced."


class DemoUnavailableError(TranslationError):
    default_message = (
        "Demo mode only supports a few built-in sample phrases. "
        "Switch off Demo mode to use real Gemini translations."
    )


def classify_exception(exc: BaseException) -> TranslationError:
    """Convert Gemini and network errors into safe user-facing messages."""
    if isinstance(exc, TranslationError):
        return exc

    names = {cls.__name__ for cls in type(exc).__mro__}
    message = str(exc).lower()
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = None

    if status in {401, 403} or names & {"Unauthorized", "Unauthenticated", "PermissionDenied"}:
        result = InvalidCredentialsError()
    elif status == 429 or names & {"ResourceExhausted", "TooManyRequests"} or "quota" in message or "rate limit" in message:
        result = BillingOrQuotaError()
    elif status in {408, 504} or names & {"DeadlineExceeded", "Timeout", "TimeoutError"}:
        result = TranslationTimeoutError()
    elif status is not None and status >= 500 or names & {"ConnectionError", "ConnectError", "ServiceUnavailable"}:
        result = NetworkError()
    else:
        result = UnexpectedResponseError()

    logger.error("Gemini request failed (%s)", type(exc).__name__)
    return result

# ----------------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    source_language: str | None
    target_language: str
    detected_language: str | None = None
    is_demo: bool = False


@dataclass
class TranslatorBackend:
    """Gemini client and model configuration."""

    client: Any
    model: str


# ----------------------------------------------------------------------------
# Gemini client creation
# ----------------------------------------------------------------------------

def create_backend(
    api_key: str | None = None,
    model: str = "gemini-3.8-flash",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranslatorBackend:
    """Create a Gemini client using the API key."""

    if not api_key:
        raise MissingCredentialsError()

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise DependencyMissingError() from exc

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000)
            ),
        )
        return TranslatorBackend(client=client, model=model)

    except Exception as exc:
        raise classify_exception(exc) from exc


@lru_cache(maxsize=1)
def get_default_backend() -> TranslatorBackend:
    """Create the default Gemini backend from environment settings."""

    load_env_file()
    settings = load_settings()

    return create_backend(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout=settings.timeout_seconds,
    )


def reset_default_backend() -> None:
    get_default_backend.cache_clear()


# ----------------------------------------------------------------------------
# Gemini translation
# ----------------------------------------------------------------------------

def translate_text_detailed(
    text: str,
    source_language: str | None,
    target_language: str,
    *,
    backend: TranslatorBackend | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_chars: int = MAX_INPUT_CHARS,
    supported_source: Iterable[str] | None = None,
    supported_target: Iterable[str] | None = None,
) -> TranslationResult:
    """Translate text using Gemini and return translation details."""

    cleaned = validate_text(text, max_chars)

    source, target = validate_language_codes(
        source_language,
        target_language,
        supported_source,
        supported_target,
    )

    active = backend or get_default_backend()

    source_instruction = (
        f"Source language code: {source}"
        if source
        else "Automatically detect the source language."
    )

    prompt = f"""
You are a professional language translation engine.

Translate the supplied text accurately.

{source_instruction}
Target language code: {target}

Requirements:
1. Preserve the original meaning and tone.
2. Preserve names, numbers, punctuation and formatting.
3. Do not explain or summarize the translation.
4. Return valid JSON only.
5. Use the detected source language's ISO language code.
6. Put the complete translated text in translated_text.

Required JSON structure:
{{
    "detected_language": "language-code",
    "translated_text": "translated text"
}}

Text to translate:
{cleaned}
"""

    try:
        response = active.client.models.generate_content(
            model=active.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )

        response_text = getattr(response, "text", None)

        if not isinstance(response_text, str) or not response_text.strip():
            raise UnexpectedResponseError()

        data = json.loads(response_text)

        translated = data.get("translated_text")
        detected = data.get("detected_language")

        if not isinstance(translated, str) or not translated.strip():
            raise UnexpectedResponseError()

        if not isinstance(detected, str) or not detected.strip():
            detected = source

        return TranslationResult(
            translated_text=translated.strip(),
            source_language=source,
            target_language=target,
            detected_language=detected,
            is_demo=False,
        )

    except AppError:
        raise
    except json.JSONDecodeError as exc:
        raise UnexpectedResponseError() from exc
    except Exception as exc:
        raise classify_exception(exc) from exc


def translate_text(
    text: str,
    source_language: str | None,
    target_language: str,
    *,
    backend: TranslatorBackend | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_chars: int = MAX_INPUT_CHARS,
) -> str:
    """Translate text and return only the translated string."""

    return translate_text_detailed(
        text,
        source_language,
        target_language,
        backend=backend,
        timeout=timeout,
        max_chars=max_chars,
    ).translated_text

# ----------------------------------------------------------------------------
# Demo mode (clearly labelled sample phrases - NOT real API output)
# ----------------------------------------------------------------------------

_DEMO_PHRASES: tuple[dict[str, str], ...] = (
    {
        "en": "Hello, how are you?",
        "hi": "नमस्ते, आप कैसे हैं?",
        "bn": "হ্যালো, আপনি কেমন আছেন?",
        "es": "Hola, ¿cómo estás?",
        "fr": "Bonjour, comment allez-vous ?",
        "de": "Hallo, wie geht es dir?",
        "ja": "こんにちは、お元気ですか？",
        "zh-CN": "你好，你好吗？",
        "ar": "مرحباً، كيف حالك؟",
        "pt": "Olá, como você está?",
        "ru": "Привет, как дела?",
        "it": "Ciao, come stai?",
        "ko": "안녕하세요, 어떻게 지내세요?",
        "ta": "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?",
        "te": "హలో, మీరు ఎలా ఉన్నారు?",
    },
    {
        "en": "Thank you very much.",
        "hi": "बहुत-बहुत धन्यवाद।",
        "bn": "অনেক ধন্যবাদ।",
        "es": "Muchas gracias.",
        "fr": "Merci beaucoup.",
        "de": "Vielen Dank.",
        "ja": "どうもありがとうございます。",
        "zh-CN": "非常感谢。",
        "ar": "شكراً جزيلاً.",
        "pt": "Muito obrigado.",
        "ru": "Большое спасибо.",
        "it": "Grazie mille.",
        "ko": "정말 감사합니다.",
        "ta": "மிக்க நன்றி.",
        "te": "చాలా ధన్యవాదాలు.",
    },
    {
        "en": "Good morning.",
        "hi": "सुप्रभात।",
        "bn": "শুভ সকাল।",
        "es": "Buenos días.",
        "fr": "Bonjour.",
        "de": "Guten Morgen.",
        "ja": "おはようございます。",
        "zh-CN": "早上好。",
        "ar": "صباح الخير.",
        "pt": "Bom dia.",
        "ru": "Доброе утро.",
        "it": "Buongiorno.",
        "ko": "좋은 아침입니다.",
        "ta": "காலை வணக்கம்.",
        "te": "శుభోదయం.",
    },
)


def _normalize_for_match(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def get_demo_examples() -> list[str]:
    """English sample phrases that demo mode can translate."""
    return [phrase["en"] for phrase in _DEMO_PHRASES]


def demo_translate(
    text: str,
    source_language: str | None,
    target_language: str,
    *,
    max_chars: int = MAX_INPUT_CHARS,
) -> TranslationResult:
    """Look up a built-in sample phrase. Raises DemoUnavailableError otherwise.

    The result is flagged ``is_demo=True`` and must be labelled as a demo.
    """
    cleaned = validate_text(text, max_chars)
    source, target = validate_language_codes(source_language, target_language)
    key = _normalize_for_match(cleaned)

    for phrase in _DEMO_PHRASES:
        by_code = {code.lower(): value for code, value in phrase.items()}
        for code, sample in phrase.items():
            if _normalize_for_match(sample) != key:
                continue
            if source is not None and source.lower() != code.lower():
                continue
            translated = by_code.get(target.lower())
            if translated is None:
                raise DemoUnavailableError(
                    f"Demo mode has no sample translation into '{target}' for this phrase."
                )
            return TranslationResult(
                translated_text=translated,
                source_language=source,
                target_language=target,
                detected_language=code if source is None else None,
                is_demo=True,
            )
    raise DemoUnavailableError()
