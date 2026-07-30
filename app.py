"""
app.py — Phase 3 Streamlit「진실의 방」(API 단일 경로)

실행:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  streamlit run app.py
"""

from __future__ import annotations

import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="진실의 방으로", page_icon="🚪", layout="wide")
st.title("방구석 프로파일러: 진실의 방으로")
st.caption("심문 → 증거 RAG → 지목 · Streamlit → FastAPI only")

with st.sidebar:
    st.header("설정")
    api_input = st.text_input("API URL", value=API_URL)
    if st.button("새 세션", type="primary", use_container_width=True):
        try:
            r = requests.post(f"{api_input.rstrip('/')}/api/v1/session", timeout=10)
            r.raise_for_status()
            st.session_state["game"] = r.json()
            st.session_state["log"] = []
        except requests.RequestException as exc:
            st.error(f"세션 생성 실패: {exc}")

try:
    health = requests.get(f"{api_input.rstrip('/')}/health", timeout=3)
    if health.status_code != 200:
        st.error(f"API 비정상: {health.status_code}")
        st.stop()
except requests.RequestException as exc:
    st.error(f"API 연결 실패: {exc}\n\n`uvicorn backend.main:app --port 8000` 후 새로고침.")
    st.stop()

game = st.session_state.get("game")
if not game:
    st.info("사이드바에서 **새 세션**을 시작하세요.")
    st.stop()

sid = game["session_id"]
st.subheader(game.get("title") or game.get("case_id"))
c1, c2 = st.columns([2, 1])

with c1:
    suspects = game.get("suspects") or []
    suspect_labels = {f"{s.get('name')} ({s.get('id')})": s.get("id") for s in suspects}
    pick = st.selectbox("용의자", list(suspect_labels.keys()) if suspect_labels else ["suspect_a"])
    suspect_id = suspect_labels.get(pick, "suspect_a")
    question = st.text_input("심문", placeholder="그날 밤 어디에 있었습니까?")
    if st.button("질문하기", type="primary") and question:
        resp = requests.post(
            f"{api_input.rstrip('/')}/api/v1/session/{sid}/ask",
            json={"suspect_id": suspect_id, "question": question},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["game"] = data.get("state", game)
            st.session_state.setdefault("log", []).append(data.get("answer"))
        else:
            st.error(resp.text)

    query = st.text_input("증거 검색", placeholder="USB 법인카드 창고")
    if st.button("증거 찾기") and query:
        resp = requests.post(
            f"{api_input.rstrip('/')}/api/v1/session/{sid}/search",
            json={"query": query},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["game"] = data.get("state", game)
            st.session_state["hits"] = data.get("hits", [])
        else:
            st.error(resp.text)

    if st.button("이 용의자 지목하기"):
        resp = requests.post(
            f"{api_input.rstrip('/')}/api/v1/session/{sid}/accuse",
            json={"suspect_id": suspect_id},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["game"] = data.get("state", game)
            st.success(data.get("ending"))
            st.write("정답 여부:", data.get("correct"))
        else:
            st.error(resp.text)

with c2:
    st.markdown("### 상태")
    st.json(
        {
            "session_id": sid,
            "evidence_ids": st.session_state["game"].get("evidence_ids"),
            "pressure": st.session_state["game"].get("pressure"),
            "ended": st.session_state["game"].get("ended"),
        }
    )
    if st.session_state.get("hits"):
        st.markdown("### 검색 히트")
        st.json(st.session_state["hits"])
    if st.session_state.get("log"):
        st.markdown("### 심문 로그")
        for line in st.session_state["log"]:
            st.write(line)

st.divider()
st.caption(f"API: {api_input} · Phase 3 초안")
