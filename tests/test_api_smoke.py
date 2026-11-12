from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict
import unittest

from fastapi.testclient import TestClient

import speech_engine.api as api
from speech_engine.storage import CallStore


class _FakeTTS:
    def __init__(self) -> None:  # pragma: no cover - trivial
        self.calls: list[Dict[str, Any]] = []

    def synthesize(
        self, text: str, language: str, output_path: str, speaker: str | None = None
    ) -> str:
        self.calls.append(
            {
                "text": text,
                "language": language,
                "output_path": output_path,
                "speaker": speaker,
            }
        )
        # Эндпоинту важно только, что возвращается строка с путем
        return output_path


class _FakeSTT:
    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def transcribe(self, audio_path: str, language: str | None = None) -> Dict[str, Any]:
        return {
            "text": "ok",
            "language": language or "ru",
            "segments": [],
        }


# Подменяем реальные реализации лёгкими заглушками,
# чтобы не загружать большие модели в тестах.
api.TextToSpeech = _FakeTTS  # type: ignore[assignment]
api.SpeechToText = _FakeSTT  # type: ignore[assignment]
_tmp = TemporaryDirectory()
_store = CallStore(Path(_tmp.name) / "api-test.db")
api.get_call_store = lambda: _store  # type: ignore[assignment]

client = TestClient(api.app)


class APISmokeTests(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("version", data)

    def test_tts_endpoint_smoke(self) -> None:
        payload = {"text": "hello", "language": "en", "speaker": None}
        resp = client.post("/tts", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("path", data)
        self.assertIsInstance(data["path"], str)
        self.assertIn("speech_", data["path"])

    def test_agent_start_endpoint_smoke(self) -> None:
        resp = client.post("/agent/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertEqual(data.get("next_step"), "greeting")

    def test_agent_respond_endpoint_smoke(self) -> None:
        payload = {"text": "Да, удобно", "current_step": "greeting"}
        resp = client.post("/agent/respond", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("intent"), "positive")
        self.assertEqual(data.get("next_step"), "qualification")

    def test_lead_and_call_flow_smoke(self) -> None:
        lead_resp = client.post(
            "/leads",
            json={"phone": "+79990000000", "name": "Иван"},
        )
        self.assertEqual(lead_resp.status_code, 200)
        lead = lead_resp.json()

        start_resp = client.post(
            "/calls/start",
            json={
                "lead_id": lead["id"],
                "direction": "outbound",
                "synthesize": False,
                "voice_instructions": "Говорить спокойно и естественно.",
            },
        )
        self.assertEqual(start_resp.status_code, 200)
        started = start_resp.json()
        call_id = started["call"]["id"]
        self.assertEqual(started["call"]["status"], "started")
        self.assertEqual(started["reply"]["next_step"], "greeting")

        respond_resp = client.post(
            f"/calls/{call_id}/respond",
            json={
                "text": "Да, говорите",
                "synthesize": False,
                "voice_instructions": "Говорить спокойно и естественно.",
            },
        )
        self.assertEqual(respond_resp.status_code, 200)
        data = respond_resp.json()
        self.assertEqual(data["reply"]["intent"], "positive")
        self.assertEqual(data["call"]["current_step"], "qualification")

    def test_stt_upload_endpoint_smoke(self) -> None:
        # Минимальный фейковый WAV-подобный контент
        file_content = b"RIFF....WAVEfmt "
        files = {"file": ("test.wav", file_content, "audio/wav")}
        resp = client.post("/stt/upload", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("text", data)
        self.assertIn("language", data)
        self.assertIn("segments", data)

