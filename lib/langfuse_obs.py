"""lib/langfuse_obs.py — 심문 ask 관측 (로컬 버퍼 + 선택적 Langfuse).

게임 UI는 시크릿 키 없이 백엔드 요약 API만 호출한다.
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 가 있으면 Langfuse에도 전송한다.

Langfuse v4 UI는 `/trace/{id}` 딥링크가 Trace not found 를 자주 내므로,
링크는 `/project/{projectId}/sessions/{sessionId}` 를 사용한다.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import requests

_log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_LOCAL: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=24))
_PROJECT_ID: str | None = None

_DEFAULT_HOST = "https://cloud.langfuse.com"


def langfuse_configured() -> bool:
    return bool(
        (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
        and (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    )


def langfuse_host() -> str:
    # 공식 권장: LANGFUSE_BASE_URL · 하위호환: LANGFUSE_HOST
    return (
        (os.environ.get("LANGFUSE_BASE_URL") or "").strip()
        or (os.environ.get("LANGFUSE_HOST") or "").strip()
        or _DEFAULT_HOST
    ).rstrip("/")


def _auth_header() -> dict[str, str]:
    pk = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    sk = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _project_id() -> str | None:
    """Langfuse UI 딥링크용 project id (캐시)."""
    global _PROJECT_ID
    if _PROJECT_ID:
        return _PROJECT_ID
    env_pid = (os.environ.get("LANGFUSE_PROJECT_ID") or "").strip()
    if env_pid:
        _PROJECT_ID = env_pid
        return _PROJECT_ID
    try:
        resp = requests.get(
            f"{langfuse_host()}/api/public/projects",
            headers=_auth_header(),
            timeout=8,
        )
        if resp.status_code >= 300:
            return None
        data = resp.json() or {}
        items = data.get("data") if isinstance(data, dict) else data
        if isinstance(items, list) and items:
            _PROJECT_ID = str(items[0].get("id") or "") or None
    except Exception:  # noqa: BLE001
        return None
    return _PROJECT_ID


def _session_url(session_id: str) -> str | None:
    """Langfuse Sessions UI — /project/{pid}/sessions/{sessionId}?viewId=__langfuse_with_io__"""
    pid = _project_id()
    if not pid or not session_id:
        return None
    return (
        f"{langfuse_host()}/project/{pid}/sessions/{session_id}"
        f"?viewId=__langfuse_with_io__"
    )


def _sessions_list_url() -> str | None:
    """Langfuse Sessions 목록 — /project/{pid}/sessions"""
    pid = _project_id()
    if not pid:
        return None
    return f"{langfuse_host()}/project/{pid}/sessions"


def _traces_list_url() -> str | None:
    """Langfuse Tracing 목록 — /project/{pid}/traces"""
    pid = _project_id()
    if not pid:
        return None
    return f"{langfuse_host()}/project/{pid}/traces"


def _clip(text: str, n: int = 220) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _iso_z(dt: datetime | None = None) -> str:
    d = dt or datetime.now(timezone.utc)
    return d.isoformat().replace("+00:00", "Z")


def record_ask_observation(
    *,
    session_id: str,
    suspect_id: str,
    suspect_name: str,
    question: str,
    answer: str,
    assistant_note: str = "",
    reply_source: str = "stub",
    model: str = "",
    gm_status: str = "",
    elapsed_sec: float | None = None,
    agent_roles: list[str] | None = None,
) -> dict[str, Any]:
    """로컬 버퍼에 남기고, 설정 시 Langfuse에도 전송."""
    now = datetime.now(timezone.utc)
    trace_id = uuid.uuid4().hex
    roles = agent_roles or []
    if not roles:
        if reply_source in ("autogen", "llm", "pipeline"):
            roles = ["suspect", "assistant", "judge"]
        else:
            roles = ["stub"]

    entry: dict[str, Any] = {
        "id": trace_id,
        "ts": _iso_z(now),
        "session_id": session_id,
        "name": "interrogation-ask",
        "suspect_id": suspect_id,
        "suspect_name": suspect_name,
        "question": _clip(question, 160),
        "answer": _clip(answer, 200),
        "assistant_note": _clip(assistant_note, 160) if assistant_note else "",
        "reply_source": reply_source,
        "model": model or "",
        "gm_status": gm_status or "",
        "elapsed_sec": round(float(elapsed_sec), 2) if elapsed_sec is not None else None,
        "roles": roles,
        "langfuse_synced": False,
        "langfuse_url": None,
    }

    with _LOCK:
        _LOCAL[session_id].appendleft(entry)

    if langfuse_configured():
        try:
            _push_langfuse(entry)
            entry["langfuse_synced"] = True
            # 딥링크는 fetch 시 세션 존재 확인 후 붙임 (조기 /sessions/{id} 404 방지)
            entry["langfuse_url"] = None
        except Exception:  # noqa: BLE001 — 관측 실패가 ask를 깨면 안 됨
            _log.warning("Langfuse push 실패", exc_info=False)

    return dict(entry)


def _push_langfuse(entry: dict[str, Any]) -> None:
    """Langfuse public ingestion API (SDK 버전 독립)."""
    host = langfuse_host()
    ts = entry["ts"]
    body = {
        "batch": [
            {
                "id": str(uuid.uuid4()),
                "type": "trace-create",
                "timestamp": ts,
                "body": {
                    "id": entry["id"],
                    "name": entry["name"],
                    "sessionId": entry["session_id"],
                    "timestamp": ts,
                    "input": {
                        "question": entry["question"],
                        "suspect_id": entry["suspect_id"],
                        "suspect_name": entry["suspect_name"],
                    },
                    "output": {
                        "answer": entry["answer"],
                        "assistant_note": entry["assistant_note"],
                        "gm_status": entry["gm_status"],
                        "reply_source": entry["reply_source"],
                    },
                    "metadata": {
                        "model": entry["model"],
                        "elapsed_sec": entry["elapsed_sec"],
                        "roles": entry["roles"],
                    },
                    "tags": ["truth-room", "ask", entry["reply_source"]],
                },
            }
        ]
    }
    resp = requests.post(
        f"{host}/api/public/ingestion",
        headers=_auth_header(),
        json=body,
        timeout=8,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"langfuse ingestion HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        payload = resp.json() or {}
        errs = payload.get("errors") or []
        if errs:
            raise RuntimeError(f"langfuse ingestion errors: {str(errs)[:200]}")
    except ValueError:
        pass


def fetch_session_observations(session_id: str, *, limit: int = 12) -> dict[str, Any]:
    """게임 모달용 요약 — Tracing(프로젝트) / Sessions(현재 세션) 탭 데이터."""
    lim = max(1, min(int(limit or 12), 24))
    with _LOCK:
        local = [dict(x) for x in list(_LOCAL.get(session_id, deque()))[:lim]]
        all_local: list[dict[str, Any]] = []
        for sid, dq in _LOCAL.items():
            for x in dq:
                row = dict(x)
                row.setdefault("session_id", sid)
                all_local.append(row)
        all_local.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
        all_local = all_local[:lim]

    configured = langfuse_configured()
    remote_session: list[dict[str, Any]] = []
    project_traces: list[dict[str, Any]] = []
    project_sessions: list[dict[str, Any]] = []
    remote_error: str | None = None

    if configured:
        try:
            _, remote_session = _fetch_langfuse_session(session_id, limit=lim)
        except Exception as exc:  # noqa: BLE001
            remote_error = str(exc)[:180]
            _log.warning("Langfuse session fetch 실패: %s", remote_error)
        try:
            project_traces = _fetch_langfuse_traces(limit=lim)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)[:180]
            remote_error = remote_error or msg
            _log.warning("Langfuse traces fetch 실패: %s", msg)
        try:
            project_sessions = _fetch_langfuse_sessions(limit=lim)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)[:180]
            remote_error = remote_error or msg
            _log.warning("Langfuse sessions list 실패: %s", msg)

    session_traces = local if local else remote_session
    traces = project_traces if project_traces else all_local

    list_url = _sessions_list_url() if configured else None
    traces_url = _traces_list_url() if configured else None
    sess_url = _session_url(session_id) if configured else None
    for t in session_traces:
        t["langfuse_url"] = list_url or sess_url
    for t in traces:
        t["langfuse_url"] = traces_url or list_url

    if not project_sessions and session_id:
        project_sessions = [
            {
                "id": session_id,
                "created_at": (session_traces[0].get("ts") if session_traces else None),
                "trace_count": len(session_traces),
                "current": True,
                "langfuse_url": sess_url or list_url,
            }
        ]
    else:
        for s in project_sessions:
            s["current"] = str(s.get("id") or "") == str(session_id)

    source = "local" if local else ("langfuse" if remote_session or project_traces else "empty")

    return {
        "enabled": True,
        "langfuse_configured": configured,
        "langfuse_host": langfuse_host() if configured else None,
        "langfuse_traces_url": traces_url,
        "langfuse_sessions_url": list_url,
        "langfuse_session_url": sess_url,
        "source": source,
        "remote_error": remote_error,
        "traces": traces,
        "session_traces": session_traces,
        "sessions": project_sessions,
        "count": len(session_traces),
        "trace_count": len(traces),
        "session_count": len(project_sessions),
    }


def fetch_session_detail(session_id: str, *, limit: int = 12) -> dict[str, Any]:
    """Sessions 아코디언용 — 특정 세션 트레이스 (게임 세션 존재 여부 무관)."""
    lim = max(1, min(int(limit or 12), 24))
    sid = (session_id or "").strip()
    with _LOCK:
        local = [dict(x) for x in list(_LOCAL.get(sid, deque()))[:lim]]

    remote: list[dict[str, Any]] = []
    remote_error: str | None = None
    if langfuse_configured() and sid:
        try:
            _, remote = _fetch_langfuse_session(sid, limit=lim)
        except Exception as exc:  # noqa: BLE001
            remote_error = str(exc)[:180]
            _log.warning("Langfuse session detail 실패: %s", remote_error)

    # 세션 API에 traces가 비면 프로젝트 traces에서 sessionId 필터
    if not remote and langfuse_configured() and sid:
        try:
            project = _fetch_langfuse_traces(limit=max(lim * 3, 24))
            remote = [t for t in project if str(t.get("session_id") or "") == sid][:lim]
        except Exception as exc:  # noqa: BLE001
            remote_error = remote_error or str(exc)[:180]

    traces = local if local else remote
    source = "local" if local else ("langfuse" if remote else "empty")
    return {
        "session_id": sid,
        "source": source,
        "remote_error": remote_error,
        "traces": traces,
        "count": len(traces),
    }


def _normalize_trace_row(t: dict[str, Any], *, session_id: str | None = None) -> dict[str, Any]:
    inp = t.get("input") or {}
    outp = t.get("output") or {}
    meta = t.get("metadata") or {}
    if isinstance(inp, str):
        inp = {"question": inp}
    if isinstance(outp, str):
        outp = {"answer": outp}
    if not isinstance(inp, dict):
        inp = {}
    if not isinstance(outp, dict):
        outp = {}
    if not isinstance(meta, dict):
        meta = {}
    tid = str(t.get("id") or "")
    sid = str(t.get("sessionId") or session_id or "")
    return {
        "id": tid,
        "ts": t.get("timestamp") or t.get("createdAt") or "",
        "session_id": sid,
        "name": t.get("name") or "trace",
        "suspect_id": str(inp.get("suspect_id") or ""),
        "suspect_name": str(inp.get("suspect_name") or ""),
        "question": _clip(str(inp.get("question") or ""), 160),
        "answer": _clip(str(outp.get("answer") or ""), 200),
        "assistant_note": _clip(str(outp.get("assistant_note") or ""), 160),
        "reply_source": str(outp.get("reply_source") or meta.get("reply_source") or ""),
        "model": str(meta.get("model") or ""),
        "gm_status": str(outp.get("gm_status") or ""),
        "elapsed_sec": meta.get("elapsed_sec"),
        "roles": meta.get("roles") or [],
        "langfuse_synced": True,
        "langfuse_url": None,
    }


def _fetch_langfuse_traces(*, limit: int = 12) -> list[dict[str, Any]]:
    host = langfuse_host()
    resp = requests.get(
        f"{host}/api/public/traces",
        headers=_auth_header(),
        params={"limit": int(limit), "orderBy": "timestamp.desc"},
        timeout=12,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"langfuse traces HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json() or {}
    items = list(data.get("data") or [])[: int(limit)]
    return [_normalize_trace_row(t) for t in items]


def _fetch_langfuse_sessions(*, limit: int = 12) -> list[dict[str, Any]]:
    host = langfuse_host()
    resp = requests.get(
        f"{host}/api/public/sessions",
        headers=_auth_header(),
        params={"limit": int(limit)},
        timeout=12,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"langfuse sessions HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json() or {}
    items = list(data.get("data") or [])[: int(limit)]
    out: list[dict[str, Any]] = []
    for s in items:
        sid = str(s.get("id") or "")
        if not sid:
            continue
        out.append(
            {
                "id": sid,
                "created_at": s.get("createdAt") or s.get("created_at") or "",
                "environment": s.get("environment") or "default",
                "trace_count": None,
                "current": False,
                "langfuse_url": _session_url(sid) or _sessions_list_url(),
            }
        )
    return out


def _fetch_langfuse_session(
    session_id: str, *, limit: int = 12
) -> tuple[bool, list[dict[str, Any]]]:
    """Returns (session_exists_on_cloud, traces). 404 → (False, [])."""
    host = langfuse_host()
    resp = requests.get(
        f"{host}/api/public/sessions/{session_id}",
        headers=_auth_header(),
        timeout=12,
    )
    if resp.status_code == 404:
        return False, []
    if resp.status_code >= 300:
        raise RuntimeError(f"langfuse session HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json() or {}
    items = list(data.get("traces") or [])[: int(limit)]
    sess_url = _session_url(session_id)
    out = [_normalize_trace_row(t, session_id=session_id) for t in items]
    for row in out:
        row["langfuse_url"] = sess_url
    return True, out


def observability_status() -> dict[str, Any]:
    return {
        "enabled": True,
        "langfuse_configured": langfuse_configured(),
        "langfuse_host": langfuse_host() if langfuse_configured() else None,
        "note": (
            "Langfuse 키 설정됨 — ask 트레이스가 클라우드에도 전송됩니다."
            if langfuse_configured()
            else "Langfuse 키 없음 — 세션 로컬 관측만 표시됩니다. (.env LANGFUSE_*)"
        ),
    }
