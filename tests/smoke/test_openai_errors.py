# -*- coding: utf-8 -*-
from lib.openai_errors import classify_openai_error, llm_notice_for_local_fallback


def test_classify_quota() -> None:
    assert classify_openai_error("Error code: 429 - insufficient_quota") == "quota"
    assert classify_openai_error("RateLimitError: Too Many Requests") == "quota"
    assert (
        llm_notice_for_local_fallback("quota")
        == "OpenAI 토큰 소진으로 로컬 답변 중"
    )


def test_classify_auth() -> None:
    assert classify_openai_error("OPENAI_API_KEY missing") == "auth"
    assert llm_notice_for_local_fallback("auth") == "OpenAI 키 문제로 로컬 답변 중"


def test_classify_other_no_notice() -> None:
    assert classify_openai_error("connection timed out") == "other"
    assert llm_notice_for_local_fallback("other") is None
    assert llm_notice_for_local_fallback(None) is None
