"""Firstpass Quotes web chat + Sales IVR pipeline API."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sales_ivr.web.chat_service import create_chat, get_chat, handle_user_message, run_pending_quote
from sales_ivr.web.pulse_ledger import summary as pulse_summary

# Shared admin gate for the on-page Pulse panel.
PULSE_ADMIN_PASSWORD = "12345"

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Firstpass Quotes",
    description="Conversational quote agent backed by the Sales IVR agent pipeline",
    version="0.2.0",
)


class ChatStartResponse(BaseModel):
    session_id: str
    reply: str
    step: str


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=2000)
    channel: Literal["web_chat", "voice"] | None = None


class ChatQuoteRequest(BaseModel):
    session_id: str


class PulseAdminRequest(BaseModel):
    password: str = Field(min_length=1, max_length=64)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "firstpass-quotes"}


@app.post("/api/chat/start", response_model=ChatStartResponse)
def chat_start(
    channel: Literal["web_chat", "voice"] = Query(default="web_chat"),
) -> ChatStartResponse:
    chat = create_chat(channel=channel)
    return ChatStartResponse(
        session_id=chat.session_id,
        reply=chat.messages[-1]["content"],
        step=chat.step,
    )


@app.post("/api/chat/message")
def chat_message(body: ChatMessageRequest) -> dict:
    chat = get_chat(body.session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found. Start a new chat.")
    return handle_user_message(chat, body.message, channel=body.channel)


@app.post("/api/chat/quote")
def chat_quote(body: ChatQuoteRequest) -> dict:
    chat = get_chat(body.session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found. Start a new chat.")
    return run_pending_quote(chat)


@app.get("/api/chat/{session_id}")
def chat_state(session_id: str) -> dict:
    chat = get_chat(session_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {
        "session_id": chat.session_id,
        "step": chat.step,
        "messages": chat.messages,
        "context": chat.context(),
        "quote_revisions": len(chat.quote_history) + (1 if chat.pipeline_result else 0),
        "result": chat.pipeline_result,
    }


@app.post("/api/admin/pulse")
def admin_pulse(body: PulseAdminRequest) -> dict:
    if not hmac.compare_digest(body.password, PULSE_ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Wrong password")
    return pulse_summary()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/robots.txt")
def robots() -> FileResponse:
    return FileResponse(STATIC_DIR / "robots.txt", media_type="text/plain")


@app.get("/sitemap.xml")
def sitemap() -> FileResponse:
    return FileResponse(STATIC_DIR / "sitemap.xml", media_type="application/xml")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "sales_ivr.web.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
