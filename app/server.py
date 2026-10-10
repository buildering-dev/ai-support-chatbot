"""Web API + embeddable chat widget.

Run:  uvicorn app.server:app --port 8000
Then open http://localhost:8000 for the demo page.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bot import SupportBot
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC = Path(__file__).parent / "static"
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI(title="AI Support Chatbot", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

bot = SupportBot(settings)
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_min:
        raise HTTPException(429, "Too many messages - please wait a minute.")
    q.append(now)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str


class LeadIn(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    question: str = Field(default="", max_length=2000)


def _check_session(sid: str) -> None:
    if not SESSION_RE.match(sid):
        raise HTTPException(400, "Invalid session id")


@app.get("/")
def demo_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "provider": bot.llm.name, "passages": len(bot.kb.passages), "business": settings.business_name}


@app.post("/api/chat")
def chat(body: ChatIn, request: Request) -> dict:
    _check_session(body.session_id)
    _rate_limit(request)
    return bot.answer(body.message, session=body.session_id, channel="web").as_dict()


@app.post("/api/lead")
def lead(body: LeadIn, request: Request) -> dict:
    _check_session(body.session_id)
    _rate_limit(request)
    if not EMAIL_RE.match(body.email):
        raise HTTPException(422, "Please enter a valid email address.")
    bot.save_lead("web", body.session_id, body.name.strip(), body.email.strip(), body.question.strip())
    return {"ok": True, "message": "Thanks! The team will email you shortly."}


@app.post("/api/reset")
def reset(body: dict) -> dict:
    sid = str(body.get("session_id", ""))
    _check_session(sid)
    bot.reset(sid)
    return {"ok": True}
