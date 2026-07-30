# -*- coding: utf-8 -*-
"""
app.py — Phase 3 Streamlit「진실의 방」(API 단일 경로)

실행:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  streamlit run app.py

게임 룰: docs/GAME_RULES.md
  UI: 캐릭터 선택 · 증거 인벤토리 · 단서 배너 · 조합 지목 (다크 테마)
"""

from __future__ import annotations

import base64
import html
import os
import time
from datetime import timedelta
from pathlib import Path

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
SUSPECT_PORTRAITS = {
    "suspect_a": ROOT / "assets" / "suspects" / "suspect_a.png",
    "suspect_b": ROOT / "assets" / "suspects" / "suspect_b.png",
    "suspect_c": ROOT / "assets" / "suspects" / "suspect_c.png",
}

CLUE_LABELS = {
    "ev_card_03": "법인카드 · 강남역 룸살롱 결제",
    "ev_msg_12": "슬랙 DM · 박신입 서버실 침입",
    "ev_net_01": "라운지 Wi-Fi · ~100GB 외부 전송",
    "ev_log_07": "출입 로그 · 김팀장 지문",
}

CLUE_FLAVOR = {
    "ev_card_03": "법인카드 전표가 책상 위로 떨어진다.",
    "ev_msg_12": "슬랙 DM 캡처가 화면에 고정된다.",
    "ev_net_01": "라운지 AP 로그 — 전송량 그래프가 치솟는다.",
    "ev_log_07": "서버실 출입 로그가 프린터에서 나온다.",
}

st.set_page_config(
    page_title="진실의 방으로",
    page_icon="🚪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _api() -> str:
    return st.session_state.get("api_url", API_URL).rstrip("/")


def _reset_timer() -> None:
    turn_sec = int((st.session_state.get("game") or {}).get("turn_seconds") or 20)
    st.session_state["turn_deadline"] = time.time() + turn_sec


def _evidence_label(eid: str) -> str:
    return CLUE_LABELS.get(eid, eid)


def _inject_theme(*, mental: bool = False, revoked: bool = False) -> None:
    # 저채도 블루그레이 — 눈 피로 완화
    accent = "#7A9BB8" if not mental and not revoked else "#8A9BB5"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap');

        :root {{
          --ink: #d5d8de;
          --muted: #8b919c;
          --accent: {accent};
          --accent-soft: rgba(122,155,184,0.22);
          --line: rgba(200,210,220,0.12);
          --surface: #1a1e26;
        }}

        .stApp {{
          background: #151820;
          color: var(--ink);
        }}
        .stApp, .stApp p, .stApp label, .stMarkdown, .stCaption {{
          font-family: "IBM Plex Sans KR", sans-serif !important;
        }}
        /* Material Icons는 폰트 덮어쓰기 금지 — 깨진 keyboard_* 텍스트 방지 */
        span[data-testid="stIconMaterial"],
        [data-testid="stIconMaterial"],
        .material-icons,
        .material-symbols-rounded,
        .material-symbols-outlined,
        [data-testid="collapsedControl"] span,
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stBaseButton-headerNoPadding"] span,
        button[kind="headerNoPadding"] span {{
          font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
          font-style: normal !important;
          font-weight: normal !important;
          letter-spacing: normal !important;
          text-transform: none !important;
          speak: never;
        }}
        h1, h2, h3, .brand-title {{
          font-family: "Black Han Sans", sans-serif !important;
          letter-spacing: 0.02em;
          color: #c8ced8 !important;
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{
          background: #12151b;
          border-right: 1px solid var(--line);
        }}
        /* 사이드바 열기/닫기 버튼 — 호버 없이 항상 표시 */
        [data-testid="collapsedControl"] {{
          display: flex !important;
          opacity: 1 !important;
          visibility: visible !important;
          pointer-events: auto !important;
          left: 0.35rem !important;
          top: 0.55rem !important;
          z-index: 1000 !important;
        }}
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stBaseButton-headerNoPadding"],
        button[kind="headerNoPadding"] {{
          opacity: 1 !important;
          visibility: visible !important;
          pointer-events: auto !important;
        }}
        /* 헤더 호버 전에는 툴바 버튼이 흐려지는 기본 동작 완화 */
        header[data-testid="stHeader"] {{
          opacity: 1 !important;
        }}
        header[data-testid="stHeader"] * {{
          opacity: 1 !important;
        }}

        .stButton > button {{
          border-radius: 6px !important;
          border: 1px solid rgba(200,210,220,0.18) !important;
          font-weight: 500 !important;
          background: #222832 !important;
          color: var(--ink) !important;
        }}
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {{
          background: #3d5568 !important;
          border-color: #4a657a !important;
          color: #e8eef4 !important;
        }}
        .stButton > button[kind="primary"]:hover {{
          background: #4a657a !important;
          border-color: #5a7890 !important;
        }}
        .stButton > button[kind="secondary"],
        .stButton > button[data-testid="baseButton-secondary"] {{
          background: #1e2430 !important;
          border-color: rgba(200,210,220,0.16) !important;
          color: #b8c0cc !important;
        }}

        div[data-baseweb="select"] > div,
        .stTextInput input,
        .stMultiSelect div[data-baseweb="select"] > div {{
          background: #1e2430 !important;
          border-radius: 6px !important;
          border-color: rgba(200,210,220,0.16) !important;
        }}

        /* 탭: Streamlit 기본 빨강 밑줄 제거 */
        /* 탭 → 세그먼트/버튼형 */
        .stTabs [data-baseweb="tab-list"] {{
          gap: 0.5rem;
          border-bottom: none !important;
          background: #12151b;
          padding: 0.4rem;
          border-radius: 8px;
          border: 1px solid var(--line);
          margin-bottom: 0.35rem !important;
        }}
        .stTabs [data-baseweb="tab"] {{
          color: var(--muted) !important;
          background: transparent !important;
          border: 1px solid transparent !important;
          border-radius: 6px !important;
          padding: 0.55rem 1.1rem !important;
          height: auto !important;
          min-height: 2.5rem !important;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
          background: rgba(122,155,184,0.12) !important;
          color: #c8ced8 !important;
        }}
        .stTabs [aria-selected="true"] {{
          color: #e8eef4 !important;
          background: #3d5568 !important;
          border: 1px solid #4a657a !important;
          border-bottom: 1px solid #4a657a !important;
          font-weight: 600 !important;
        }}
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {{
          display: none !important;
          height: 0 !important;
          background: transparent !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
          padding-top: 1.25rem !important;
        }}

        /* 상태 배너(타이머·3진 아웃) — 동일 높이로 레이아웃 점프 방지 */
        .status-banner {{
          box-sizing: border-box;
          height: 40px;
          min-height: 40px;
          max-height: 40px;
          margin: 0 0 0.75rem 0 !important;
          padding: 0 0.85rem !important;
          display: flex !important;
          align-items: center !important;
          gap: 0.75rem;
          border-radius: 0.5rem;
          border: 1px solid rgba(122,155,184,0.35);
          background: rgba(90,110,130,0.18);
          overflow: hidden;
        }}
        .status-banner--alert {{
          border-color: rgba(180,100,100,0.45);
          background: rgba(90,40,40,0.35);
        }}
        .status-banner .timer-track {{
          flex: 1 1 auto;
          height: 6px;
          min-height: 6px;
          background: rgba(200,210,220,0.12);
          border-radius: 3px;
          overflow: hidden;
        }}
        .status-banner .timer-fill {{
          height: 6px;
          background: #5f7a90;
          border-radius: 3px;
        }}
        .status-banner-text {{
          margin: 0 !important;
          padding: 0 !important;
          font-size: 0.9rem !important;
          line-height: 1.2 !important;
          color: #c8ced8 !important;
          white-space: nowrap;
          flex-shrink: 0;
        }}

        .hud {{
          display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
          gap: 0.75rem; padding: 0 0 0.75rem; border-bottom: 1px solid var(--line);
          margin-bottom: 0.75rem;
        }}
        .brand-title {{
          font-size: clamp(1.35rem, 2.4vw, 1.85rem); line-height: 1.15;
          margin: 0 !important; padding: 0 !important;
          text-shadow: none !important; display: block !important;
        }}
        .brand-sub {{
          margin: 0 !important; padding: 0 !important;
          color: var(--muted); font-size: 0.9rem; line-height: 1.5;
          display: block !important;
        }}
        .brand-gap {{
          display: block !important;
          height: 1.35rem !important;
          min-height: 1.35rem !important;
          line-height: 1.35rem !important;
        }}
        .stMarkdown p.brand-title,
        .stMarkdown p.brand-sub,
        .stMarkdown div.brand-title,
        .stMarkdown div.brand-sub {{
          margin-top: 0 !important;
          margin-bottom: 0 !important;
        }}
        .hud-stats {{ display: flex; gap: 0.75rem; align-items: center; }}
        .stat {{
          min-width: 6.5rem; padding: 0.4rem 0.7rem;
          border: 1px solid var(--line); background: var(--surface);
          border-radius: 6px;
        }}
        .stat-label {{
          display: block; font-size: 0.65rem; letter-spacing: 0.1em;
          text-transform: uppercase; color: var(--muted); margin-bottom: 0.15rem;
        }}
        .stat-value {{ font-size: 1.1rem; color: #b7c6d4; font-weight: 600; }}
        .hearts {{ letter-spacing: 0.1em; color: #8FA8C0; }}

        .panel-title {{
          font-family: "Black Han Sans", sans-serif; font-size: 1rem;
          margin: 0 0 0.5rem; color: #c8ced8;
        }}
        .inv-empty {{ color: var(--muted); font-size: 0.85rem; padding: 0.35rem 0; }}
        .inv-item {{
          border-left: 3px solid #6d879c;
          padding: 0.45rem 0.6rem; margin-bottom: 0.4rem;
          background: var(--surface);
          border-radius: 0 6px 6px 0;
        }}
        .inv-id {{ font-size: 0.68rem; color: var(--muted); }}
        .inv-name {{ font-weight: 600; margin-top: 0.1rem; font-size: 0.9rem; }}

        /* 용의자 이미지 행 ↔ 인벤토리 박스 상단 정렬용 (높이 강제 없음) */
        .suspect-session-marker {{
          display: block;
          height: 0;
          margin: 0;
          padding: 0;
        }}
        .inventory-session {{
          border: 1px solid var(--line);
          border-radius: 8px;
          background: rgba(30,36,48,0.7);
          padding: 0.85rem 0.9rem;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          margin-top: 8px;
          margin-bottom: 0;
        }}
        .inventory-session .panel-title {{
          margin-bottom: 0.75rem;
        }}
        .inventory-body {{
          display: flex;
          flex-direction: column;
        }}
        .inventory-body.is-empty {{
          justify-content: flex-start;
          align-items: flex-start;
        }}

        .clue-banner {{
          margin: 0 0 0.75rem; padding: 0.9rem 1.1rem;
          border: 1px solid rgba(122,155,184,0.4);
          background: rgba(50,65,82,0.45);
          border-radius: 6px;
        }}
        .clue-kicker {{
          font-size: 0.68rem; letter-spacing: 0.14em; text-transform: uppercase;
          color: var(--accent); margin-bottom: 0.25rem;
        }}
        .clue-title {{
          font-family: "Black Han Sans", sans-serif; font-size: 1.2rem;
          margin: 0 0 0.25rem; color: #d5d8de;
        }}
        .clue-snip {{ color: var(--muted); font-size: 0.85rem; margin: 0; }}
        .suspect-grid-hint {{
          color: var(--muted);
          font-size: 0.8rem;
          margin: 0 0 0.45rem !important;
          padding-bottom: 0.1rem !important;
          display: block !important;
        }}
        .suspect-title-gap {{
          display: block !important;
          height: 6px !important;
          min-height: 6px !important;
          line-height: 6px !important;
        }}
        .suspect-block {{
          margin-bottom: 0.5rem !important;
          padding-bottom: 0 !important;
        }}
        .stTabs {{
          margin-top: 0.5rem !important;
        }}
        /* 용의자 초상 ↔ 선택 버튼: 살짝만 띄움 (완전 밀착/과대 간격 방지) */
        [data-testid="stColumn"] > div {{
          gap: 0.45rem !important;
        }}
        [data-testid="column"] > div {{
          gap: 0.45rem !important;
        }}
        [data-testid="stColumn"] [data-testid="stVerticalBlock"] {{
          gap: 0.45rem !important;
        }}
        .suspect-pick-wrap {{
          line-height: 0;
          margin: 0 !important;
        }}
        .suspect-pick-wrap img {{
          width: 100%;
          display: block;
          margin: 0;
          padding: 0;
        }}
        .suspect-pick-gap {{
          display: block;
          height: 8px;
          min-height: 8px;
          line-height: 8px;
        }}
        div[data-testid="stMarkdownContainer"]:has(.suspect-pick-wrap) {{
          margin-bottom: 0 !important;
          padding-bottom: 0 !important;
        }}
        [data-testid="stColumn"] .stButton {{
          margin-top: 0 !important;
          padding-top: 0 !important;
        }}
        [data-testid="stColumn"] .stButton > button {{
          min-height: 2.4rem !important;
          padding-top: 0.45rem !important;
          padding-bottom: 0.45rem !important;
        }}

        [data-testid="stProgress"] > div > div {{
          background-color: #5f7a90 !important;
        }}
        [data-testid="stProgress"] > div {{
          background-color: rgba(200,210,220,0.12) !important;
        }}

        .pressure-row {{
          margin: 0 0 0.55rem;
          padding: 0.7rem 0.85rem;
          background: rgba(30,36,48,0.7);
          border: 1px solid var(--line);
          border-radius: 6px;
        }}
        .pressure-row:last-child {{
          margin-bottom: 0;
        }}
        .pressure-block {{
          margin-top: calc(0.75rem + 20px);
          margin-bottom: 0.75rem;
          padding-bottom: 0;
        }}
        .pressure-block .panel-title {{
          margin: 0 0 0.5rem !important;
          display: block !important;
        }}
        .pressure-block .pressure-row:first-of-type {{
          margin-top: 0;
        }}
        .log-block {{
          margin-top: calc(0.75rem + 10px);
          padding-top: 0;
          margin-bottom: 0;
        }}
        .log-block .panel-title {{
          margin: 0 0 calc(0.5rem - 5px) !important;
          padding: 0 !important;
          display: block !important;
        }}
        .log-title-gap {{
          display: block !important;
          height: 0 !important;
          min-height: 0 !important;
          line-height: 0 !important;
        }}
        /* 심문 기록 제목 ↔ 첫 카드 간격 */
        div[data-testid="stMarkdownContainer"]:has(.log-block) {{
          margin-bottom: calc(0.5rem - 5px) !important;
        }}
        .pressure-meta {{
          display: flex; justify-content: space-between; align-items: baseline;
          gap: 0.5rem; margin-bottom: 0.4rem;
          font-size: 0.88rem; color: var(--ink);
        }}
        .pressure-meta span {{ color: var(--muted); font-size: 0.78rem; }}
        .pressure-track {{
          height: 3px; width: 100%;
          background: rgba(200,210,220,0.14);
          border-radius: 2px; overflow: hidden;
        }}
        .pressure-fill {{
          height: 100%;
          background: #6d879c;
          border-radius: 2px;
          max-width: 100%;
        }}

        /* 채팅 아바타 오렌지 톤 완화 */
        [data-testid="stChatMessage"] {{
          background: rgba(30,36,48,0.7) !important;
          border: 1px solid var(--line);
          border-radius: 6px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _queue_clues(clues: list) -> None:
    if not clues:
        return
    pending = list(st.session_state.get("pending_clues") or [])
    pending.extend(clues)
    st.session_state["pending_clues"] = pending
    for c in clues:
        title = c.get("title") or c.get("evidence_id")
        st.session_state.setdefault("log", []).append(f"단서 획득 — {title}")


def _render_clue_banner() -> None:
    pending = list(st.session_state.get("pending_clues") or [])
    if not pending:
        return
    c = pending[0]
    eid = str(c.get("evidence_id") or "")
    title = html.escape(str(c.get("title") or _evidence_label(eid)))
    snip = html.escape(str(c.get("snippet") or CLUE_FLAVOR.get(eid, ""))[:140])
    flavor = html.escape(CLUE_FLAVOR.get(eid, "결정적 단서가 확보되었습니다."))
    st.markdown(
        f"""
        <div class="clue-banner">
          <div class="clue-kicker">Evidence Secured</div>
          <div class="clue-title">{title}</div>
          <p class="clue-snip">{flavor}</p>
          <p class="clue-snip" style="margin-top:0.3rem;">{snip}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("단서 확인 · 인벤토리에 보관", type="primary", key="dismiss_clue"):
        st.session_state["pending_clues"] = pending[1:]
        st.rerun()


def _render_hud(game: dict) -> None:
    stamina = int(game.get("stamina") or 0)
    stamina_max = int(game.get("stamina_max") or 3)
    hearts = "♥" * stamina + "♡" * max(0, stamina_max - stamina)
    strikes = int(game.get("timeout_strikes") or 0)
    strike_max = int(game.get("timeout_strike_max") or 3)
    title = html.escape(str(game.get("title") or "진실의 방"))
    st.markdown(
        f"""
        <div class="hud">
          <div>
            <div class="brand-title">진실의 방</div>
            <div class="brand-gap" style="height:28px;min-height:28px;" aria-hidden="true">&nbsp;</div>
            <div class="brand-sub">{title}</div>
          </div>
          <div class="hud-stats">
            <div class="stat">
              <span class="stat-label">수사 권한</span>
              <div class="stat-value hearts">{hearts}</div>
            </div>
            <div class="stat">
              <span class="stat-label">타임아웃</span>
              <div class="stat-value">{strikes}/{strike_max}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_inventory(owned: list[str]) -> None:
    if not owned:
        body = (
            '<div class="inventory-body is-empty">'
            '<p class="inv-empty">아직 확보한 단서가 없습니다.</p>'
            "</div>"
        )
    else:
        blocks = []
        for eid in owned:
            name = html.escape(_evidence_label(eid))
            blocks.append(
                f'<div class="inv-item"><div class="inv-id">{html.escape(eid)}</div>'
                f'<div class="inv-name">{name}</div></div>'
            )
        body = f'<div class="inventory-body">{"".join(blocks)}</div>'

    st.markdown(
        '<div class="inventory-session">'
        '<p class="panel-title">증거 인벤토리</p>'
        f"{body}"
        "</div>",
        unsafe_allow_html=True,
    )


def _pick_suspect(
    suspects: list[dict],
    broken: list[str],
    *,
    show_title: bool = True,
) -> str:
    if not suspects:
        return "suspect_a"

    ids = [str(s.get("id") or "") for s in suspects]
    if st.session_state.get("suspect_id") not in ids:
        st.session_state["suspect_id"] = ids[0]

    if show_title:
        st.markdown(
            '<p class="suspect-grid-hint">대상 용의자</p>'
            '<div class="suspect-title-gap" aria-hidden="true">&nbsp;</div>',
            unsafe_allow_html=True,
        )
    cols = st.columns(len(suspects), gap="small")
    for col, s in zip(cols, suspects):
        sid = str(s.get("id") or "")
        name = str(s.get("name") or sid)
        is_broken = sid in broken
        selected = st.session_state["suspect_id"] == sid
        portrait = SUSPECT_PORTRAITS.get(sid)
        with col:
            if selected:
                border = "2px solid #7A9BB8"
            elif is_broken:
                border = "2px solid #8A9BB5"
            else:
                border = "1px solid rgba(200,210,220,0.14)"

            if portrait and portrait.exists():
                b64 = base64.b64encode(portrait.read_bytes()).decode("ascii")
                img_html = (
                    f'<img alt="{html.escape(name)}" '
                    f'src="data:image/png;base64,{b64}" />'
                )
            else:
                img_html = (
                    f"<div style='aspect-ratio:1;display:flex;align-items:center;"
                    f"justify-content:center;background:#1a1f28;color:#9a9488;"
                    f"font-size:1.2rem;line-height:1.2;'>{html.escape(name[:1])}</div>"
                )

            # 이미지+여백을 한 블록으로 — st.image/버튼 사이 기본 gap 회피
            st.markdown(
                f'<div class="suspect-pick-wrap" style="border:{border};'
                f'border-radius:6px;overflow:hidden;background:#1a1e26;'
                f'margin:0;padding:0;">{img_html}</div>'
                f'<div class="suspect-pick-gap" aria-hidden="true">&nbsp;</div>',
                unsafe_allow_html=True,
            )
            mark = "●" if selected else "○"
            suffix = " · 붕괴" if is_broken else ""
            if st.button(
                f"{mark} {name}{suffix}",
                key=f"suspect_radio_{sid}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                st.session_state["suspect_id"] = sid
                st.rerun()

    suspect_id = str(st.session_state["suspect_id"])
    if suspect_id in broken:
        st.error("선택 중인 용의자는 멘탈 붕괴 상태입니다.")
    # 탭과의 간격은 행 분리로 처리 (여기서 spacer 없음)
    return suspect_id


def _render_status_banner(
    text: str,
    *,
    kind: str = "timer",
    fill_pct: float | None = None,
) -> None:
    """타이머·3진 아웃 공통 배너 (iframe 없음 · 높이 고정)."""
    track = ""
    if fill_pct is not None:
        pct = max(0, min(100, int(round(fill_pct))))
        track = (
            f'<div class="timer-track">'
            f'<div class="timer-fill" style="width:{pct}%;"></div>'
            f"</div>"
        )
    cls = "status-banner status-banner--alert" if kind == "alert" else "status-banner"
    st.markdown(
        f'<div class="{cls}">{track}'
        f'<span class="status-banner-text">{html.escape(text)}</span></div>',
        unsafe_allow_html=True,
    )


def _handle_timeout(sid: str) -> None:
    try:
        resp = requests.post(f"{_api()}/api/v1/session/{sid}/pass_turn", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("state"):
                st.session_state["game"] = data["state"]
            strikes = data.get("timeout_strikes", "?")
            max_s = data.get("timeout_strike_max", 3)
            if data.get("turn_out"):
                st.session_state.setdefault("log", []).append(
                    f"(턴 3진 아웃) {data.get('ending') or '시간 초과 3회 · 미션 실패'}"
                )
            else:
                st.session_state.setdefault("log", []).append(
                    f"(타임아웃) 턴 패스 — 스트라이크 {strikes}/{max_s}"
                )
            if not data.get("turn_out"):
                _reset_timer()
            return
    except requests.RequestException:
        pass
    st.session_state.setdefault("log", []).append("(타임아웃) 턴이 패스되었습니다.")
    _reset_timer()


with st.sidebar:
    st.markdown("### 콘솔")
    api_input = st.text_input("API URL", value=API_URL)
    st.session_state["api_url"] = api_input
    timer_ui = st.checkbox("20초 타임어택", value=True)
    if st.button("새 수사 개시", type="primary", use_container_width=True):
        try:
            r = requests.post(f"{_api()}/api/v1/session", timeout=10)
            r.raise_for_status()
            st.session_state["game"] = r.json()
            st.session_state["log"] = []
            st.session_state["hits"] = []
            st.session_state["pending_clues"] = []
            st.session_state["last_ending"] = None
            _reset_timer()
        except requests.RequestException as exc:
            st.error(f"세션 생성 실패: {exc}")

try:
    health = requests.get(f"{_api()}/health", timeout=3)
    if health.status_code != 200:
        st.error(f"API 비정상: {health.status_code}")
        st.stop()
except requests.RequestException as exc:
    st.error(f"API 연결 실패: {exc}\n\n`uvicorn backend.main:app --port 8000` 후 새로고침.")
    st.stop()

game = st.session_state.get("game")
if not game:
    _inject_theme()
    st.markdown(
        """
        <div class="hud">
          <div>
            <div class="brand-title">진실의 방</div>
            <div class="brand-gap" style="height:28px;min-height:28px;" aria-hidden="true">&nbsp;</div>
            <div class="brand-sub">사이드바에서 새 수사를 개시하세요.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

sid = game["session_id"]
status = game.get("status") or "playing"
mental = status == "mental_break" or bool(game.get("mental_break_suspects"))
revoked = status == "authority_revoked" or (
    game.get("ended") and int(game.get("stamina") or 0) <= 0
)
stamina = int(game.get("stamina") or 0)

_inject_theme(mental=mental, revoked=revoked)
_render_hud(game)
_render_clue_banner()

if revoked:
    st.error("감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다.")
elif mental:
    st.warning("알리바이 3-Out — 용의자 멘탈 마스크가 깨졌습니다.")

timer_on = (
    timer_ui
    and bool(game.get("timer_enabled", True))
    and not game.get("ended")
    and game.get("status") not in ("turn_out", "authority_revoked")
)
total_sec = int(game.get("turn_seconds") or 20)
turn_out_now = game.get("status") == "turn_out" or (
    game.get("ended")
    and int(game.get("timeout_strikes") or 0) >= int(game.get("timeout_strike_max") or 3)
    and stamina > 0
)

# 타이머 ↔ 3진 아웃 전환 시 높이 고정 슬롯 (iframe 제거로 레이아웃 점프 방지)
if turn_out_now:
    _render_status_banner(
        f"턴 3진 아웃 — 시간 초과 "
        f"{game.get('timeout_strikes', 3)}/{game.get('timeout_strike_max', 3)}. 미션 실패.",
        kind="alert",
    )
elif timer_on:
    if "turn_deadline" not in st.session_state:
        _reset_timer()

    @st.fragment(run_every=timedelta(seconds=1))
    def _timer_slot() -> None:
        deadline = float(st.session_state.get("turn_deadline") or 0)
        left = max(0, int(deadline - time.time()))
        pct = (100.0 * left / total_sec) if total_sec else 0.0
        _render_status_banner(
            f"턴 남은 시간  {left}s / {total_sec}s",
            kind="timer",
            fill_pct=pct,
        )
        if left <= 0:
            _handle_timeout(sid)
            st.rerun()

    _timer_slot()

if st.session_state.get("last_ending"):
    if st.session_state.get("last_ending_ok"):
        st.success(st.session_state["last_ending"])
    else:
        st.error(st.session_state["last_ending"])

# 제목 행(상단 정렬) + 본문 한 줄: 왼쪽 용의자/탭, 오른쪽 인벤토리·압박·기록
suspects = game.get("suspects") or []
broken = list(game.get("mental_break_suspects") or [])
g = st.session_state["game"]

head_l, head_r = st.columns([1.55, 1], gap="medium")
with head_l:
    st.markdown(
        '<p class="suspect-grid-hint">대상 용의자</p>'
        '<div class="suspect-title-gap" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )
with head_r:
    st.markdown(
        '<p class="suspect-grid-hint" style="visibility:hidden;">대상 용의자</p>'
        '<div class="suspect-title-gap" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )

left, right = st.columns([1.55, 1], gap="medium")
with left:
    st.markdown(
        '<div class="suspect-session-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    suspect_id = _pick_suspect(suspects, broken, show_title=False)

    tab_ask, tab_search, tab_accuse = st.tabs(["심문", "증거 수색", "최종 지목"])

    with tab_ask:
        question = st.text_input("심문 질문", placeholder="그날 밤 어디에 있었습니까?")
        if st.button("질문하기", type="primary", key="btn_ask") and question and not game.get("ended"):
            if timer_on and time.time() > st.session_state.get("turn_deadline", 0):
                st.warning("시간 초과 — 턴이 패스됩니다.")
                _handle_timeout(sid)
            else:
                resp = requests.post(
                    f"{_api()}/api/v1/session/{sid}/ask",
                    json={"suspect_id": suspect_id, "question": question},
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["game"] = data.get("state", game)
                    line = data.get("answer")
                    if data.get("is_alibi_broken"):
                        line = f"알리바이 붕괴! (break {data.get('break_count')}/3) — {line}"
                    st.session_state.setdefault("log", []).append(line)
                    _reset_timer()
                    st.rerun()
                else:
                    st.error(resp.text)

    with tab_search:
        query = st.text_input("검색 키워드", placeholder="법인카드 룸살롱 / Wi-Fi 100GB")
        if st.button("수색 실행", type="primary", key="btn_search") and query and not game.get("ended"):
            resp = requests.post(
                f"{_api()}/api/v1/session/{sid}/search",
                json={"query": query},
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["game"] = data.get("state", game)
                st.session_state["hits"] = data.get("hits", [])
                _queue_clues(data.get("new_clues") or [])
                if data.get("useless_search"):
                    st.session_state.setdefault("log", []).append(
                        f"헛수색 — 수사 권한 {data.get('stamina', '?')}/{data.get('stamina_max', 3)}"
                    )
                    if data.get("authority_revoked"):
                        st.session_state["last_ending"] = data.get("ending")
                        st.session_state["last_ending_ok"] = False
                _reset_timer()
                st.rerun()
            else:
                st.error(resp.text)
        hits = st.session_state.get("hits") or []
        if hits:
            st.caption("최근 검색 히트")
            for h in hits[:4]:
                eid = h.get("evidence_id") or "—"
                snip = str(h.get("snippet") or "")[:100]
                st.markdown(f"**{eid}** — {snip}")

    with tab_accuse:
        st.caption("용의자 1명 + 결정적 증거 정확히 2장")
        owned = list(game.get("evidence_ids") or [])
        ev_options = {_evidence_label(e): e for e in owned}
        selected_labels = st.multiselect(
            "인벤토리에서 증거 2장",
            options=list(ev_options.keys()),
            max_selections=2,
            key="accuse_ev",
        )
        ready = len(selected_labels) == 2 and not game.get("ended")
        if st.button("진범으로 지목한다", type="primary", disabled=not ready, key="btn_accuse"):
            eids = [ev_options[lab] for lab in selected_labels]
            resp = requests.post(
                f"{_api()}/api/v1/session/{sid}/accuse",
                json={"suspect_id": suspect_id, "evidence_ids": eids},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["game"] = data.get("state", game)
                st.session_state["last_ending"] = data.get("ending")
                st.session_state["last_ending_ok"] = bool(data.get("correct"))
                if data.get("correct"):
                    st.balloons()
                st.rerun()
            else:
                st.error(resp.text)

with right:
    _render_inventory(list(g.get("evidence_ids") or []))

    pressure = g.get("pressure") or {}
    breaks = g.get("break_count") or {}
    if suspects:
        rows = [
            '<div class="pressure-block"><p class="panel-title">용의자 압박</p>'
        ]
        for s in suspects:
            sid_s = s.get("id")
            name = html.escape(str(s.get("name") or sid_s))
            p = min(1.0, max(0.0, float(pressure.get(sid_s, 0) or 0)))
            b = int(breaks.get(sid_s, 0) or 0)
            pct = int(round(p * 100))
            rows.append(
                f'<div class="pressure-row">'
                f'<div class="pressure-meta"><strong>{name}</strong>'
                f'<span>압박 {pct}% · 붕괴 {b}/3</span></div>'
                f'<div class="pressure-track">'
                f'<div class="pressure-fill" style="width:{pct}%;"></div>'
                f'</div></div>'
            )
        rows.append("</div>")
        st.markdown("".join(rows), unsafe_allow_html=True)

    if st.session_state.get("log"):
        st.markdown(
            '<div class="log-block">'
            '<p class="panel-title">심문 기록</p>'
            '<div class="log-title-gap" aria-hidden="true">&nbsp;</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        for line in st.session_state["log"][-8:]:
            st.chat_message("assistant").write(line)

st.caption(f"API {_api()} · docs/GAME_RULES.md")
