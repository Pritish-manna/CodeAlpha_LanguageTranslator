"""Tests for the Gemini translation backend. No live API calls are made."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.languages import SameLanguageError, UnsupportedLanguageError
from src.translator import (
    BillingOrQuotaError,
    DemoUnavailableError,
    InvalidCredentialsError,
    MissingCredentialsError,
    NetworkError,
    TranslationError,
    TranslationTimeoutError,
    TranslatorBackend,
    UnexpectedResponseError,
    classify_exception,
    demo_translate,
    get_demo_examples,
    translate_text,
    translate_text_detailed,
)
from src.utils import EmptyTextError, TextTooLongError


def _backend(translated="Hello, how are you?", detected="hi"):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"translated_text": translated, "detected_language": detected})
    )
    return TranslatorBackend(client=client, model="gemini-test-model")


def test_valid_translation_returns_details_and_sends_json_request():
    backend = _backend(translated="Hola", detected="en")
    result = translate_text_detailed("Hello", "en", "es", backend=backend)
    assert result.translated_text == "Hola"
    assert result.detected_language == "en"
    assert result.is_demo is False
    call = backend.client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-test-model"
    assert "Target language code: es" in call["contents"]
    assert "Hello" in call["contents"]
    assert call["config"]["response_mime_type"] == "application/json"


def test_translate_text_returns_plain_string():
    assert translate_text("Hello", "en", "es", backend=_backend("Hola")) == "Hola"


def test_auto_detect_source_is_included_in_prompt():
    backend = _backend(detected="hi")
    result = translate_text_detailed("नमस्ते", None, "en", backend=backend)
    prompt = backend.client.models.generate_content.call_args.kwargs["contents"]
    assert "Automatically detect the source language" in prompt
    assert result.detected_language == "hi"


def test_multiline_unicode_text_is_preserved_in_prompt():
    text = "Hello\n\nThanks 你好"
    backend = _backend("مرحبا\nشكرا", "en")
    result = translate_text_detailed(text, "en", "ar", backend=backend)
    prompt = backend.client.models.generate_content.call_args.kwargs["contents"]
    assert text in prompt
    assert result.translated_text == "مرحبا\nشكرا"


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_text_never_calls_api(text):
    backend = _backend()
    with pytest.raises(EmptyTextError):
        translate_text(text, "en", "es", backend=backend)
    backend.client.models.generate_content.assert_not_called()


def test_same_language_never_calls_api():
    backend = _backend()
    with pytest.raises(SameLanguageError):
        translate_text("Hello", "en", "en", backend=backend)
    backend.client.models.generate_content.assert_not_called()


def test_too_long_text_never_calls_api():
    backend = _backend()
    with pytest.raises(TextTooLongError):
        translate_text("a" * 20, "en", "es", backend=backend, max_chars=10)
    backend.client.models.generate_content.assert_not_called()


def test_unsupported_language_is_rejected_before_api_call():
    backend = _backend()
    with pytest.raises(UnsupportedLanguageError):
        translate_text_detailed("Hello", "en", "xx", backend=backend, supported_target=["es", "en"])
    backend.client.models.generate_content.assert_not_called()


def test_api_failure_is_mapped_to_network_error():
    class ServiceUnavailable(Exception):
        pass
    backend = _backend()
    backend.client.models.generate_content.side_effect = ServiceUnavailable("503")
    with pytest.raises(NetworkError):
        translate_text("Hello", "en", "es", backend=backend)


@pytest.mark.parametrize("response", [None, "", "not-json", '{"translated_text": ""}', '{"translated_text": 12}'])
def test_unexpected_response_raises_safe_error(response):
    backend = _backend()
    backend.client.models.generate_content.return_value = SimpleNamespace(text=response)
    with pytest.raises(UnexpectedResponseError):
        translate_text("Hello", "en", "es", backend=backend)


def test_missing_credentials_error_from_default_backend():
    with patch("src.translator.get_default_backend", side_effect=MissingCredentialsError()):
        with pytest.raises(MissingCredentialsError):
            translate_text("Hello", "en", "es")


def _raise(name, message="", status=None):
    cls = type(name, (Exception,), {})
    exc = cls(message)
    if status is not None:
        exc.status_code = status
    return classify_exception(exc)


def test_classifies_authentication_quota_timeout_and_network_errors():
    assert isinstance(_raise("Unauthorized"), InvalidCredentialsError)
    assert isinstance(_raise("APIError", status=403), InvalidCredentialsError)
    assert isinstance(_raise("APIError", "quota exceeded", 429), BillingOrQuotaError)
    assert isinstance(_raise("TimeoutError"), TranslationTimeoutError)
    assert isinstance(_raise("APIError", status=503), NetworkError)


def test_unknown_exception_does_not_expose_sensitive_details():
    result = classify_exception(RuntimeError("private-token-value"))
    assert isinstance(result, TranslationError)
    assert "private-token-value" not in result.user_message


# ---- demo mode -------------------------------------------------------------

def test_demo_translation_is_flagged_as_demo():
    result = demo_translate("Hello, how are you?", "en", "hi")
    assert result.is_demo is True
    assert result.translated_text == "नमस्ते, आप कैसे हैं?"


def test_demo_auto_detect_reports_detected_language():
    result = demo_translate("नमस्ते, आप कैसे हैं?", None, "en")
    assert result.translated_text == "Hello, how are you?"
    assert result.detected_language == "hi"


def test_demo_matching_ignores_case_and_extra_spaces():
    assert demo_translate("  good   MORNING. ", "en", "es").translated_text == "Buenos días."


def test_demo_unknown_text_is_refused_not_invented():
    with pytest.raises(DemoUnavailableError):
        demo_translate("This sentence is not a sample.", "en", "es")


def test_demo_wrong_source_language_is_refused():
    with pytest.raises(DemoUnavailableError):
        demo_translate("Hello, how are you?", "hi", "es")


def test_demo_same_language_is_rejected():
    with pytest.raises(SameLanguageError):
        demo_translate("Good morning.", "en", "en")


def test_every_demo_example_translates_to_every_default_language():
    for phrase in get_demo_examples():
        for code in ["hi", "bn", "es", "fr", "de", "ja", "zh-CN", "ar", "pt", "ru", "it", "ko", "ta", "te"]:
            assert demo_translate(phrase, "en", code).translated_text
