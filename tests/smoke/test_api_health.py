"""API 스모크 — session 플로우 최소 검증.

실행:
  uvicorn backend.main:app --port 8000
  pytest tests/smoke/ -v
"""

from __future__ import annotations

import os

import pytest
import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


@pytest.fixture(scope="module")
def api_available() -> str:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        if r.status_code != 200:
            pytest.skip(f"API not healthy: {r.status_code}")
        return API_BASE
    except requests.RequestException as exc:
        pytest.skip(f"API not running at {API_BASE}: {exc}")


def test_health(api_available: str) -> None:
    r = requests.get(f"{api_available}/health", timeout=5)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_session_flow(api_available: str) -> None:
    r = requests.post(f"{api_available}/api/v1/session", timeout=10)
    assert r.status_code == 200
    session = r.json()
    sid = session["session_id"]
    assert sid

    ask = requests.post(
        f"{api_available}/api/v1/session/{sid}/ask",
        json={"suspect_id": "suspect_b", "question": "어디에 있었나?"},
        timeout=10,
    )
    assert ask.status_code == 200
    assert "answer" in ask.json()

    search = requests.post(
        f"{api_available}/api/v1/session/{sid}/search",
        json={"query": "Wi-Fi 100GB"},
        timeout=10,
    )
    assert search.status_code == 200
    assert search.json().get("hits")

    tool = requests.post(
        f"{api_available}/api/v1/session/{sid}/tool",
        json={"name": "request_cctv_log", "args": {"location": "lounge"}},
        timeout=10,
    )
    assert tool.status_code == 200
    body = tool.json()
    assert body.get("name") == "request_cctv_log"
    assert body.get("result", {}).get("tool") == "request_cctv_log"

    profile = requests.get(
        f"{api_available}/api/v1/session/{sid}/suspects/suspect_a/profile",
        timeout=10,
    )
    assert profile.status_code == 200
    pdata = profile.json()
    assert pdata.get("name")
    assert "profile" in pdata
    assert "secrets" not in pdata
    assert "role" not in pdata
    assert "culprit_id" not in (pdata.get("case_overview") or {})

    case = requests.get(f"{api_available}/api/v1/session/{sid}/case", timeout=10)
    assert case.status_code == 200
    assert "culprit_id" not in case.json()
