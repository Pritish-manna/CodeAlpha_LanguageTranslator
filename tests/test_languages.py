"""Tests for src/languages.py."""

import pytest

from src.languages import (
    AUTO_DETECT_LABEL,
    ApiLanguage,
    LanguageError,
    SameLanguageError,
    UnsupportedLanguageError,
    build_language_options,
    get_language_code,
    get_language_name,
    resolve_language_pair,
    swap_languages,
    validate_language_codes,
)

EXPECTED = [
    "English", "Hindi", "Bengali", "Spanish", "French", "German", "Japanese",
    "Chinese (Simplified)", "Arabic", "Portuguese", "Russian", "Italian",
    "Korean", "Tamil", "Telugu",
]


def test_default_options_match_the_specification():
    options = build_language_options()
    assert list(options.source) == [AUTO_DETECT_LABEL] + EXPECTED
    assert list(options.target) == EXPECTED
    assert options.source[AUTO_DETECT_LABEL] is None
    assert options.target["Chinese (Simplified)"] == "zh-CN"
    assert options.verified_with_api is False


def test_get_language_code_and_invalid_name():
    assert get_language_code("Hindi") == "hi"
    with pytest.raises(LanguageError):
        get_language_code("Klingon")


def test_get_language_name_handles_known_alias_and_unknown_codes():
    assert get_language_name("hi") == "Hindi"
    assert get_language_name("zh") == "Chinese (Simplified)"
    assert get_language_name("zh-CN") == "Chinese (Simplified)"
    assert get_language_name(None) == AUTO_DETECT_LABEL
    assert get_language_name("xx") == "xx"


def test_valid_pair_is_accepted():
    assert validate_language_codes("hi", "en") == ("hi", "en")


@pytest.mark.parametrize("source", [None, "", "auto", "AUTO"])
def test_auto_detect_source_becomes_none(source):
    assert validate_language_codes(source, "en") == (None, "en")


def test_same_language_is_rejected():
    with pytest.raises(SameLanguageError):
        validate_language_codes("en", "EN")


@pytest.mark.parametrize("target", [None, "", "  "])
def test_missing_target_is_rejected(target):
    with pytest.raises(LanguageError):
        validate_language_codes("en", target)


@pytest.mark.parametrize("code", ["e", "english!", "12", "en_US"])
def test_malformed_codes_are_rejected(code):
    with pytest.raises(LanguageError):
        validate_language_codes("hi", code)


def test_unsupported_language_is_rejected_when_allowed_lists_are_given():
    with pytest.raises(UnsupportedLanguageError):
        validate_language_codes("xx", "en", allowed_source=["en", "hi"], allowed_target=["en"])
    with pytest.raises(UnsupportedLanguageError):
        validate_language_codes("hi", "xx", allowed_source=["hi"], allowed_target=["en"])


def test_resolve_language_pair_uses_names():
    assert resolve_language_pair("Auto Detect", "English") == (None, "en")
    with pytest.raises(LanguageError):
        resolve_language_pair("Auto Detect", "Auto Detect")
    with pytest.raises(SameLanguageError):
        resolve_language_pair("English", "English")


def test_swap_normal_languages():
    result = swap_languages("English", "Bengali")
    assert (result.source, result.target, result.swapped) == ("Bengali", "English", True)


def test_swap_with_auto_detect_uses_detected_language():
    result = swap_languages(AUTO_DETECT_LABEL, "English", detected_name="Hindi")
    assert (result.source, result.target, result.swapped) == ("English", "Hindi", True)


def test_swap_with_auto_detect_and_no_detection_changes_nothing():
    result = swap_languages(AUTO_DETECT_LABEL, "English")
    assert (result.source, result.target, result.swapped) == (AUTO_DETECT_LABEL, "English", False)
    assert result.message


def test_swap_rejects_detected_language_equal_to_target():
    result = swap_languages(AUTO_DETECT_LABEL, "English", detected_name="English")
    assert result.swapped is False


def test_options_are_verified_against_api_list():
    api = [
        ApiLanguage("en", "English"),
        ApiLanguage("hi", "Hindi"),
        ApiLanguage("zh", "Chinese (Simplified)"),
        ApiLanguage("zh-TW", "Chinese (Traditional)"),
        ApiLanguage("ceb", "Cebuano", support_source=True, support_target=False),
    ]
    options = build_language_options(api)
    assert options.verified_with_api is True
    assert options.target["Chinese (Simplified)"] == "zh"  # alias the API actually lists
    assert "Bengali" in options.unsupported
    assert "Bengali" not in options.target and "Bengali" not in options.source
    assert "Chinese (Traditional)" in options.extra
    assert options.target["Chinese (Traditional)"] == "zh-TW"
    assert "Cebuano" in options.source and "Cebuano" not in options.target


def test_api_list_with_zh_cn_keeps_zh_cn():
    options = build_language_options([ApiLanguage("en", "English"), ApiLanguage("zh-CN", "Chinese (Simplified)")])
    assert options.target["Chinese (Simplified)"] == "zh-CN"
