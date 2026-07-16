"""Opt-in real-model smoke test using project-owned multilingual speech."""

import base64
from pathlib import Path

import pytest

from clipfetch.transcription import FasterWhisperTranscriber

pytestmark = [pytest.mark.integration, pytest.mark.transcription_integration]
pytest.importorskip("faster_whisper")


def test_real_base_model_transcribes_project_owned_multilingual_fixture(tmp_path: Path):
    encoded = Path(__file__).parents[1] / "fixtures" / "multilingual_speech.mp3.b64"
    fixture = tmp_path / "multilingual_speech.mp3"
    fixture.write_bytes(base64.b64decode(encoded.read_text(encoding="ascii")))
    result = FasterWhisperTranscriber("base").transcribe(fixture)
    normalized = result.text.casefold()
    assert normalized
    assert any(word in normalized for word in ("hello", "speech", "hola", "voz"))
