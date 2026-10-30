"""Mock interview interviewer TTS (ElevenLabs + OpenAI fallback)."""

from unittest.mock import patch

from backend.app.core.errors import AppError
from backend.app.services import mock_interview_tts


def test_elevenlabs_provider_uses_agent_voice(monkeypatch):
    calls: list[str] = []

    def fake_agent(agent_id: str, db=None) -> str:
        calls.append(agent_id)
        return "voice-abc"

    def fake_tts(text: str, *, voice_id: str, model_id: str = "eleven_multilingual_v2", db=None) -> bytes:
        assert voice_id == "voice-abc"
        assert "Hello" in text
        return b"mp3-bytes"

    monkeypatch.setattr(
        "backend.app.services.elevenlabs_client.get_agent_voice_id",
        fake_agent,
    )
    monkeypatch.setattr(
        "backend.app.services.elevenlabs_client.synthesize_speech",
        fake_tts,
    )

    with patch.object(mock_interview_tts, "_merge_voice_settings") as merge:
        merge.return_value = {
            "provider": "elevenlabs",
            "elevenlabs_agent_id": "fA4eSDsx5xNZ1RV7zEu5",
            "elevenlabs_model_id": "eleven_multilingual_v2",
        }
        out = mock_interview_tts.synthesize_interviewer_speech(None, "Hello candidate")
    assert out == b"mp3-bytes"
    assert calls == ["fA4eSDsx5xNZ1RV7zEu5"]


def test_elevenlabs_missing_key_falls_back_to_openai(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.elevenlabs_client.get_agent_voice_id",
        lambda _aid: (_ for _ in ()).throw(AppError("ELEVENLABS_DISABLED", "no key", 503)),
    )
    with patch.object(mock_interview_tts, "_merge_voice_settings") as merge:
        merge.return_value = {
            "provider": "elevenlabs",
            "elevenlabs_agent_id": "agent-1",
            "model": "gpt-4o-mini-tts",
            "voice": "shimmer",
        }
        with patch.object(mock_interview_tts, "_synthesize_openai_interviewer") as openai_tts:
            openai_tts.return_value = b"openai-audio"
            out = mock_interview_tts.synthesize_interviewer_speech(None, "Next question?")
    assert out == b"openai-audio"
    openai_tts.assert_called_once()


def test_voice_id_from_agent_payload_nested():
    from backend.app.services.elevenlabs_client import _voice_id_from_agent_payload

    assert _voice_id_from_agent_payload({"conversation_config": {"tts": {"voice_id": "v1"}}}) == "v1"
    assert _voice_id_from_agent_payload({"voice_id": "v2"}) == "v2"


def test_elevenlabs_verify_error_message_parses_json():
    import httpx

    from backend.app.services.elevenlabs_client import _verify_error_message

    body = (
        '{"type":"authentication_error","code":"unauthorized","message":"Invalid API key",'
        '"status":"invalid_api_key","request_id":"abc"}'
    )
    msg = _verify_error_message(httpx.Response(401, text=body))
    assert "Invalid API key" in msg
    assert "request_id" not in msg
    assert "authentication_error" not in msg
