"""Tests for src/text_to_speech.py. gTTS is replaced by a fake."""

import pytest

from src.text_to_speech import (
    TextToSpeechError,
    is_tts_supported,
    normalize_tts_code,
    synthesize_speech,
)


class FakeTTS:
    calls = []

    def __init__(self, text, lang):
        FakeTTS.calls.append((text, lang))

    def write_to_fp(self, fp):
        fp.write(b"ID3-fake-mp3")


class FailingTTS:
    def __init__(self, text, lang):
        pass

    def write_to_fp(self, fp):
        raise ConnectionError("no network")


class SilentTTS(FakeTTS):
    def write_to_fp(self, fp):
        return None


def test_supported_and_unsupported_languages():
    assert is_tts_supported("en")
    assert is_tts_supported("hi")
    assert not is_tts_supported("xx")
    assert not is_tts_supported(None)


def test_chinese_alias_is_normalised():
    assert normalize_tts_code("zh") == "zh-CN"
    assert normalize_tts_code("zh-CN") == "zh-CN"


def test_successful_synthesis_returns_audio_bytes():
    FakeTTS.calls.clear()
    audio = synthesize_speech("नमस्ते", "hi", tts_factory=FakeTTS)
    assert audio == b"ID3-fake-mp3"
    assert FakeTTS.calls == [("नमस्ते", "hi")]


def test_unsupported_language_raises():
    with pytest.raises(TextToSpeechError):
        synthesize_speech("hello", "xx", tts_factory=FakeTTS)


def test_empty_text_raises():
    with pytest.raises(TextToSpeechError):
        synthesize_speech("   ", "en", tts_factory=FakeTTS)


def test_network_failure_is_reported_without_details():
    with pytest.raises(TextToSpeechError) as info:
        synthesize_speech("hello", "en", tts_factory=FailingTTS)
    assert "internet" in info.value.user_message


def test_empty_audio_raises():
    with pytest.raises(TextToSpeechError):
        synthesize_speech("hello", "en", tts_factory=SilentTTS)
