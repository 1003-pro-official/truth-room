"""
backend/main.py — Phase 2 FastAPI (진실의 방으로)

실행:
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
문서:
  http://localhost:8000/docs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.game_engine import engine, load_api_config

ROOT = Path(__file__).resolve().parent.parent
API_CONFIG = ROOT / "configs" / "api.yaml"


def _cors_origins() -> list[str]:
    # Docker / Cloudflare Containers — Streamlit이 같은 오리진 또는 workers.dev
    if os.environ.get("CORS_ALLOW_ALL", "").strip() in ("1", "true", "yes"):
        return ["*"]
    cfg = load_api_config(API_CONFIG) if API_CONFIG.exists() else load_api_config()
    return list(cfg.get("cors_origins", ["http://localhost:8501"]))


def _cors_credentials() -> bool:
    # allow_origins=["*"] 와 credentials 동시 사용 불가
    return "*" not in _cors_origins()


app = FastAPI(
    title="진실의 방으로 API",
    description="심문 · 증거 검색 · 지목 세션 API (초안)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=_cors_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskBody(BaseModel):
    suspect_id: str
    question: str = Field(min_length=1)


class SearchBody(BaseModel):
    query: str = Field(min_length=1)


class AccuseBody(BaseModel):
    suspect_id: str
    evidence_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="결정적 증거 2장 (세션 보유분)",
    )


class ToolBody(BaseModel):
    name: str = Field(
        min_length=1,
        description="check_card_history | run_forensic | search_messenger | request_cctv_log",
    )
    args: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/session")
def create_session() -> dict[str, Any]:
    session = engine.create_session()
    return engine.public_state(session)


@app.get("/api/v1/session/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return engine.public_state(session)


@app.get("/api/v1/session/{session_id}/case")
def get_case_overview(session_id: str) -> dict[str, Any]:
    """공개 사건개요 (culprit_id 미포함)."""
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return engine.public_case_overview()


@app.get("/api/v1/session/{session_id}/suspects/{suspect_id}/profile")
def get_suspect_profile(session_id: str, suspect_id: str) -> dict[str, Any]:
    """용의자 공개 프로필 + 사건개요. secrets/role/culprit 미포함."""
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    profile = engine.public_suspect_profile(suspect_id)
    if not profile:
        raise HTTPException(status_code=404, detail="suspect not found")
    return profile


@app.post("/api/v1/session/{session_id}/ask")
def ask(session_id: str, body: AskBody) -> dict[str, Any]:
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.ask(session, body.suspect_id, body.question)
    if result.get("error") == "session_ended":
        raise HTTPException(status_code=409, detail="session already ended")
    return {
        **result,
        "state": engine.public_state(session, focus_suspect=body.suspect_id),
    }


@app.post("/api/v1/session/{session_id}/search")
def search(session_id: str, body: SearchBody) -> dict[str, Any]:
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.search(session, body.query)
    if result.get("error") == "session_ended":
        raise HTTPException(status_code=409, detail="session already ended")
    return {**result, "state": engine.public_state(session)}


@app.post("/api/v1/session/{session_id}/tool")
def tool(session_id: str, body: ToolBody) -> dict[str, Any]:
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.tool(session, body.name, body.args)
    if result.get("error") == "session_ended":
        raise HTTPException(status_code=409, detail="session already ended")
    return {**result, "state": engine.public_state(session)}


@app.post("/api/v1/session/{session_id}/accuse")
def accuse(session_id: str, body: AccuseBody) -> dict[str, Any]:
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.accuse(session, body.suspect_id, body.evidence_ids)
    if result.get("error") == "session_ended":
        raise HTTPException(status_code=409, detail="session already ended")
    return {**result, "state": engine.public_state(session)}


@app.post("/api/v1/session/{session_id}/pass_turn")
def pass_turn(session_id: str) -> dict[str, Any]:
    """타임어택 만료 등 — break/pressure 미증가 (docs/GAME_RULES.md)."""
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    result = engine.pass_turn(session, reason="timeout")
    if result.get("error") == "session_ended":
        raise HTTPException(status_code=409, detail="session already ended")
    return {**result, "state": engine.public_state(session)}
