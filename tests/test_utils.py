"""Tests for src/utils.py."""

import pytest

from src.utils import (
    EmptyTextError,
    TextTooLongError,
    ValidationError,
    add_history_entry,
    build_copy_button_html,
    count_characters,
    load_settings,
    make_history_entry,
    validate_text,
)


def test_valid_text_is_returned_and_line_breaks_are_kept():
    assert validate_text("  Hello\nWorld  ") == "Hello\nWorld"


def test_windows_line_endings_are_normalised():
    assert validate_text("a\r\nb") == "a\nb"


@pytest.mark.parametrize("value", ["", "   ", "\n\t  \n"])
def test_empty_or_whitespace_text_is_rejected(value):
    with pytest.raises(EmptyTextError):
        validate_text(value)


def test_non_string_input_is_rejected():
    with pytest.raises(ValidationError):
        validate_text(None)


def test_text_over_limit_is_rejected():
    with pytest.raises(TextTooLongError):
        validate_text("a" * 11, max_chars=10)


def test_text_at_limit_is_accepted():
    assert validate_text("a" * 10, max_chars=10) == "a" * 10


def test_unicode_text_is_preserved():
    text = "नमस्ते 你好 مرحبا こんにちは"
    assert validate_text(text) == text


def test_count_characters_counts_code_points():
    assert count_characters("") == 0
    assert count_characters(None) == 0
    assert count_characters("नमस्ते") == len("नमस्ते")


def _entry(original="hi", translated="hola", entry_id=None):
    return make_history_entry(original, translated, "English", "Spanish", entry_id=entry_id)


def test_history_adds_entries_in_order():
    history = []
    assert add_history_entry(history, _entry("a", "A"))
    assert add_history_entry(history, _entry("b", "B"))
    assert [item["original"] for item in history] == ["a", "b"]


def test_history_ignores_duplicate_from_rerun():
    history = []
    assert add_history_entry(history, _entry(entry_id=1))
    assert not add_history_entry(history, _entry(entry_id=1))
    assert not add_history_entry(history, _entry(entry_id=2))  # identical to latest
    assert len(history) == 1


def test_history_respects_limit():
    history = []
    for number in range(5):
        add_history_entry(history, _entry(str(number), str(number)), limit=3)
    assert [item["original"] for item in history] == ["2", "3", "4"]


def test_load_settings_reads_values_and_falls_back_to_defaults():
    settings = load_settings(
        {
            "GEMINI_API_KEY": " test-key ",
            "GEMINI_MODEL": " gemini-test-model ",
            "TRANSLATION_TIMEOUT_SECONDS": "12.5",
            "MAX_INPUT_CHARS": "not-a-number",
        }
    )
    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model == "gemini-test-model"
    assert settings.timeout_seconds == 12.5
    assert settings.max_input_chars == 5000


def test_copy_button_html_escapes_script_breaking_text():
    html_doc = build_copy_button_html("</script><b>x</b> & more")
    assert html_doc.count("</script>") == 1  # only our own closing tag
    assert "navigator.clipboard" in html_doc
    assert "execCommand" in html_doc


def test_copy_button_html_embeds_unicode_safely():
    html_doc = build_copy_button_html("नमस्ते")
    assert "const textToCopy" in html_doc
    assert "\\u0928" in html_doc  # Devanagari 'na' encoded as a JS escape
