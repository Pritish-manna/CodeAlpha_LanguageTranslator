"""Language metadata, validation and swapping (no network access needed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from src.utils import AppError

AUTO_DETECT_LABEL = "Auto Detect"
DEFAULT_SOURCE = AUTO_DETECT_LABEL
DEFAULT_TARGET = "English"

# Display name -> language code (ordered as shown in the dropdowns).
DEFAULT_LANGUAGES: dict[str, str] = {
    "English": "en",
    "Hindi": "hi",
    "Bengali": "bn",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Japanese": "ja",
    "Chinese (Simplified)": "zh-CN",
    "Arabic": "ar",
    "Portuguese": "pt",
    "Russian": "ru",
    "Italian": "it",
    "Korean": "ko",
    "Tamil": "ta",
    "Telugu": "te",
}

# Alternative codes the API may use for one of the configured languages.
# The first alias that the API actually lists is the one we send.
LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "zh-CN": ("zh-CN", "zh"),
}

_CODE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------


class LanguageError(AppError):
    default_message = "The selected language is not valid."


class SameLanguageError(LanguageError):
    default_message = (
        "The source and target languages are the same. "
        "Choose a different target language to translate."
    )


class UnsupportedLanguageError(LanguageError):
    default_message = "That language is not supported by the translation service."


# ----------------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ApiLanguage:
    """One entry from the API's supported-language list."""

    code: str
    name: str
    support_source: bool = True
    support_target: bool = True


@dataclass(frozen=True)
class LanguageOptions:
    """Dropdown contents. ``source`` maps Auto Detect to ``None``."""

    source: dict[str, str | None]
    target: dict[str, str]
    unsupported: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    verified_with_api: bool = False


@dataclass(frozen=True)
class SwapResult:
    source: str
    target: str
    swapped: bool
    message: str | None = None


# ----------------------------------------------------------------------------
# Options
# ----------------------------------------------------------------------------


def build_language_options(
    api_languages: Iterable[ApiLanguage] | None = None,
) -> LanguageOptions:
    """Build dropdown options.

    Without ``api_languages`` the built-in list is used unverified. With it,
    the built-in languages are checked against the API list, unsupported ones
    are removed (and reported), and extra languages from the API are appended.
    """
    if api_languages is None:
        return LanguageOptions(
            source={AUTO_DETECT_LABEL: None, **DEFAULT_LANGUAGES},
            target=dict(DEFAULT_LANGUAGES),
        )

    api_list = list(api_languages)
    api_source = {item.code.lower(): item.code for item in api_list if item.support_source}
    api_target = {item.code.lower(): item.code for item in api_list if item.support_target}

    source: dict[str, str | None] = {AUTO_DETECT_LABEL: None}
    target: dict[str, str] = {}
    unsupported: list[str] = []
    known_codes: set[str] = set()

    for name, code in DEFAULT_LANGUAGES.items():
        aliases = LANGUAGE_ALIASES.get(code, (code,))
        known_codes.update(alias.lower() for alias in aliases)
        source_code = next((api_source[a.lower()] for a in aliases if a.lower() in api_source), None)
        target_code = next((api_target[a.lower()] for a in aliases if a.lower() in api_target), None)
        if source_code:
            source[name] = source_code
        if target_code:
            target[name] = target_code
        if not (source_code and target_code):
            unsupported.append(name)

    extras: list[str] = []
    for item in sorted(api_list, key=lambda entry: (entry.name or entry.code).lower()):
        if item.code.lower() in known_codes:
            continue
        name = item.name or item.code
        if name in source or name in target:
            continue
        added = False
        if item.support_source:
            source[name] = item.code
            added = True
        if item.support_target:
            target[name] = item.code
            added = True
        if added:
            extras.append(name)

    return LanguageOptions(
        source=source,
        target=target,
        unsupported=tuple(unsupported),
        extra=tuple(extras),
        verified_with_api=True,
    )


def get_language_code(name: str, options: LanguageOptions | None = None, *, role: str = "target") -> str | None:
    """Return the code for a display name (``None`` for Auto Detect)."""
    options = options or build_language_options()
    table: Mapping[str, str | None] = options.source if role == "source" else options.target
    if name not in table:
        raise LanguageError(f"'{name}' is not an available {role} language.")
    return table[name]


def get_language_name(code: str | None, options: LanguageOptions | None = None) -> str:
    """Return a display name for ``code`` (falls back to the code itself)."""
    if not code:
        return AUTO_DETECT_LABEL
    lowered = code.lower()
    for name, default_code in DEFAULT_LANGUAGES.items():
        aliases = LANGUAGE_ALIASES.get(default_code, (default_code,))
        if lowered in {alias.lower() for alias in aliases}:
            return name
    if options is not None:
        for table in (options.target, options.source):
            for name, table_code in table.items():
                if table_code and table_code.lower() == lowered:
                    return name
    return code


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------


def _check_code_format(code: str, role: str) -> None:
    if not _CODE_PATTERN.match(code):
        raise LanguageError(f"'{code}' is not a valid {role} language code.")


def validate_language_codes(
    source_code: str | None,
    target_code: str | None,
    allowed_source: Iterable[str] | None = None,
    allowed_target: Iterable[str] | None = None,
) -> tuple[str | None, str]:
    """Validate a language pair and return ``(source_or_None, target)``.

    ``None``, an empty string or ``"auto"`` as source means auto-detect.
    Raises LanguageError, SameLanguageError or UnsupportedLanguageError.
    """
    target = (target_code or "").strip()
    if not target:
        raise LanguageError("Please select a target language.")
    _check_code_format(target, "target")

    source = (source_code or "").strip()
    if not source or source.lower() == "auto":
        source_value: str | None = None
    else:
        _check_code_format(source, "source")
        source_value = source

    if source_value and source_value.lower() == target.lower():
        raise SameLanguageError()

    if allowed_source is not None and source_value is not None:
        if source_value.lower() not in {code.lower() for code in allowed_source}:
            raise UnsupportedLanguageError(f"'{source_value}' is not supported as a source language.")
    if allowed_target is not None:
        if target.lower() not in {code.lower() for code in allowed_target}:
            raise UnsupportedLanguageError(f"'{target}' is not supported as a target language.")

    return source_value, target


def resolve_language_pair(
    source_name: str,
    target_name: str,
    options: LanguageOptions | None = None,
) -> tuple[str | None, str]:
    """Convert dropdown names to validated codes."""
    options = options or build_language_options()
    if source_name not in options.source:
        raise LanguageError("Please choose a valid source language.")
    if target_name not in options.target:
        raise LanguageError("Please choose a valid target language.")
    return validate_language_codes(options.source[source_name], options.target[target_name])


# ----------------------------------------------------------------------------
# Swapping
# ----------------------------------------------------------------------------


def swap_languages(
    source_name: str,
    target_name: str,
    detected_name: str | None = None,
    options: LanguageOptions | None = None,
) -> SwapResult:
    """Swap source and target, handling Auto Detect.

    With Auto Detect as source, the detected language (if known and selectable
    as a target) becomes the new target. Otherwise nothing changes and a
    message explains why.
    """
    options = options or build_language_options()
    if source_name != AUTO_DETECT_LABEL:
        if source_name not in options.target or target_name not in options.source:
            return SwapResult(source_name, target_name, False, "These languages cannot be swapped.")
        return SwapResult(target_name, source_name, True)

    if not detected_name:
        return SwapResult(
            source_name,
            target_name,
            False,
            "Auto Detect has no detected language yet. Translate something first, "
            "or pick a source language, then swap.",
        )
    if detected_name == target_name or detected_name not in options.target:
        return SwapResult(
            source_name,
            target_name,
            False,
            f"Cannot swap: '{detected_name}' cannot be used as the new target language.",
        )
    return SwapResult(target_name, detected_name, True)
