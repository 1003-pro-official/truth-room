# -*- coding: utf-8 -*-
"""OpenAI API 오류 분류 — UI 안내용 (비밀·스택 미노출)."""

from __future__ import annotations

# 쿼터·일일 한도·결제 한도 (토큰/예산 소진으로 안내)
_QUOTA_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "billing_hard_limit",
    "billing hard limit",
    "quota",
    "rate_limit",
    "ratelimit",
    "rate limit",
    "429",
    "too many requests",
)


def classify_openai_error(exc: BaseException | str | None) -> str | None:
    """반환: 'quota' | 'auth' | 'other' | None."""
    if exc is None:
        return None
    text = str(exc).strip().lower()
    if not text:
        return None
    if "api_key" in text or "authentication" in text or "invalid_api_key" in text:
        if "missing" in text or "incorrect" in text or "invalid" in text or "auth" in text:
            return "auth"
    for m in _QUOTA_MARKERS:
        if m in text:
            return "quota"
    return "other"


def llm_notice_for_local_fallback(kind: str | None) -> str | None:
    """로컬(스텁) 답변일 때 플레이어에게 보여줄 짧은 안내."""
    if kind == "quota":
        return "OpenAI 토큰 소진으로 로컬 답변 중"
    if kind == "auth":
        return "OpenAI 키 문제로 로컬 답변 중"
    return None
