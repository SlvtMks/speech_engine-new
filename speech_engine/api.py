from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import SpeechToText, TextToSpeech, __version__
from .agent import AgentEngine
from .storage import CallStore
from .telephony import MockTelephonyProvider
from .voice import PremiumTTSUnavailable, get_voice_status, synthesize_premium_tts


logger = logging.getLogger(__name__)


app = FastAPI(title="Speech Engine API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Простое логирование HTTP-запросов с временем обработки.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "HTTP %s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        getattr(response, "status_code", "unknown"),
        process_time_ms,
    )
    return response


class TTSPayload(BaseModel):
    text: str
    language: str
    speaker: Optional[str] = None


class STTPayload(BaseModel):
    audio_path: str
    language: Optional[str] = None


class AgentPayload(BaseModel):
    text: str
    current_step: Optional[str] = None


class LeadCreatePayload(BaseModel):
    phone: str
    name: Optional[str] = None
    notes: Optional[str] = None


class LeadUpdatePayload(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class CallStartPayload(BaseModel):
    lead_id: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    direction: str = "outbound"
    scenario: str = "cold_sales_intro"
    synthesize: bool = False
    speaker: Optional[str] = "aidar"
    voice_instructions: Optional[str] = None


class CallRespondPayload(BaseModel):
    text: str
    synthesize: bool = False
    speaker: Optional[str] = "aidar"
    voice_instructions: Optional[str] = None


@lru_cache(maxsize=1)
def get_tts_service() -> Any:
    return TextToSpeech()


@lru_cache(maxsize=1)
def get_stt_service() -> Any:
    return SpeechToText()


@lru_cache(maxsize=1)
def get_agent_engine() -> AgentEngine:
    return AgentEngine()


@lru_cache(maxsize=1)
def get_call_store() -> CallStore:
    return CallStore()


@lru_cache(maxsize=1)
def get_telephony_provider() -> MockTelephonyProvider:
    return MockTelephonyProvider()


def unique_wav_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}.wav"


def synthesize_agent_audio(
    text: str,
    speaker: Optional[str] = "aidar",
    voice_instructions: Optional[str] = None,
) -> Optional[str]:
    output_dir = Path("data/tts_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / unique_wav_name("agent")

    try:
        return synthesize_premium_tts(
            text=text,
            output_path=str(output_path),
            instructions=voice_instructions,
        )
    except PremiumTTSUnavailable:
        pass

    tts = get_tts_service()
    return tts.synthesize(
        text=text,
        language="ru",
        output_path=str(output_path),
        speaker=speaker,
    )


@app.post("/tts")
def tts_endpoint(payload: TTSPayload) -> Dict[str, Any]:
    """
    Синтез речи и возврат пути к сгенерированному аудиофайлу.

    Клиент может затем скачать файл по /audio/{filename}.
    """
    try:
        tts = get_tts_service()
        output_dir = Path("data/tts_outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = unique_wav_name("speech")
        output_path = output_dir / safe_name

        audio_path = tts.synthesize(
            text=payload.text,
            language=payload.language,
            output_path=str(output_path),
            speaker=payload.speaker,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"path": audio_path}


@app.post("/agent/start")
def agent_start() -> Dict[str, Any]:
    try:
        return get_agent_engine().start().to_dict()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/agent/respond")
def agent_respond(payload: AgentPayload) -> Dict[str, Any]:
    try:
        return get_agent_engine().respond(
            customer_text=payload.text,
            current_step=payload.current_step,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/leads")
def create_lead(payload: LeadCreatePayload) -> Dict[str, Any]:
    try:
        return get_call_store().create_lead(
            phone=payload.phone,
            name=payload.name,
            notes=payload.notes,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/leads")
def list_leads() -> List[Dict[str, Any]]:
    return get_call_store().list_leads()


@app.get("/leads/{lead_id}")
def get_lead(lead_id: str) -> Dict[str, Any]:
    try:
        return get_call_store().get_lead(lead_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/leads/{lead_id}")
def update_lead(lead_id: str, payload: LeadUpdatePayload) -> Dict[str, Any]:
    try:
        return get_call_store().update_lead(
            lead_id=lead_id,
            status=payload.status,
            notes=payload.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/calls/start")
def start_call(payload: CallStartPayload) -> Dict[str, Any]:
    store = get_call_store()
    agent = get_agent_engine()
    telephony = get_telephony_provider()

    try:
        lead_id = payload.lead_id
        if lead_id:
            lead = store.get_lead(lead_id)
        else:
            if not payload.phone:
                raise HTTPException(status_code=400, detail="phone is required when lead_id is not provided")
            lead = store.create_lead(phone=payload.phone, name=payload.name)
            lead_id = lead["id"]

        if payload.direction == "outbound":
            telephony_call = telephony.start_outbound_call(lead["phone"])
        elif payload.direction == "inbound":
            telephony_call = telephony.accept_inbound_call()
        else:
            raise HTTPException(status_code=400, detail="direction must be 'inbound' or 'outbound'")

        reply = agent.start()
        audio_path = (
            synthesize_agent_audio(reply.text, payload.speaker, payload.voice_instructions)
            if payload.synthesize
            else None
        )
        call = store.create_call(
            lead_id=lead_id,
            direction=payload.direction,
            scenario=payload.scenario,
            current_step=reply.next_step,
            status=reply.status,
            external_call_id=telephony_call.external_call_id,
        )
        store.add_message(
            call_id=call["id"],
            role="agent",
            text=reply.text,
            intent=reply.intent,
            step=reply.next_step,
            audio_path=audio_path,
        )
        store.update_lead(lead_id, status=reply.status)
        call = store.get_call(call["id"])
        return {
            "call": call,
            "lead": store.get_lead(lead_id),
            "reply": reply.to_dict(),
            "audio_path": audio_path,
            "telephony": {
                "provider": "mock",
                "external_call_id": telephony_call.external_call_id,
                "status": telephony_call.status,
            },
        }
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/calls/{call_id}/respond")
def respond_to_call(call_id: str, payload: CallRespondPayload) -> Dict[str, Any]:
    store = get_call_store()
    agent = get_agent_engine()

    try:
        call = store.get_call(call_id)
        store.add_message(
            call_id=call_id,
            role="customer",
            text=payload.text,
            step=call["current_step"],
        )
        reply = agent.respond(payload.text, current_step=call["current_step"])
        audio_path = (
            synthesize_agent_audio(reply.text, payload.speaker, payload.voice_instructions)
            if payload.synthesize
            else None
        )
        store.add_message(
            call_id=call_id,
            role="agent",
            text=reply.text,
            intent=reply.intent,
            step=reply.next_step,
            audio_path=audio_path,
        )
        updated_call = store.update_call(
            call_id=call_id,
            current_step=reply.next_step,
            status=reply.status,
            finished=reply.finish,
        )
        if updated_call.get("lead_id"):
            store.update_lead(updated_call["lead_id"], status=reply.status)

        return {
            "call": updated_call,
            "reply": reply.to_dict(),
            "audio_path": audio_path,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/calls")
def list_calls() -> List[Dict[str, Any]]:
    return get_call_store().list_calls()


@app.get("/calls/{call_id}")
def get_call(call_id: str) -> Dict[str, Any]:
    try:
        return get_call_store().get_call(call_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/health")
def health() -> Dict[str, Any]:
    """
    Простой health-check эндпоинт для мониторинга.
    """
    return {"status": "ok", "version": __version__}


@app.get("/voice/status")
def voice_status() -> Dict[str, Any]:
    return get_voice_status()


@app.get("/audio/{filename}")
def get_audio(filename: str) -> FileResponse:
    """
    Отдаёт ранее сгенерированный аудиофайл.
    """
    file_path = Path("data/tts_outputs") / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, media_type="audio/wav", filename=file_path.name)


@app.post("/stt")
def stt_endpoint(payload: STTPayload) -> Dict[str, Any]:
    """
    Распознаёт речь из аудиофайла и возвращает текст.

    Ожидает путь к файлу на сервере.
    Для браузера удобнее будет реализовать отдельную загрузку файла.
    """
    try:
        stt = get_stt_service()
        result = stt.transcribe(payload.audio_path, language=payload.language)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result


@app.post("/stt/upload")
async def stt_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Загрузка аудиофайла из браузера и офлайн‑распознавание речи.

    Принимает multipart/form-data с полем "file".
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Не указан файл для распознавания.")

    uploads_dir = Path("data/stt_uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Сохраняем файл под безопасным именем
    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix or ".wav"
    safe_stem = Path(original_name).stem[:40] or "upload"
    safe_name = f"{safe_stem}_{uuid.uuid4().hex}{suffix}"
    target_path = uploads_dir / safe_name

    try:
        content = await file.read()
        target_path.write_bytes(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить файл: {exc}") from exc

    try:
        stt = get_stt_service()
        result = stt.transcribe(str(target_path), language=None)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Возвращаем только ключевые поля для фронта
    return {
        "text": result.get("text", ""),
        "language": result.get("language", "unknown"),
        "segments": result.get("segments", []),
    }

