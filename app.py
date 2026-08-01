# -*- coding: utf-8 -*-
"""
app.py — Phase 3 Streamlit「진실의 방」(API 단일 경로)

실행:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  streamlit run app.py

게임 룰: docs/GAME_RULES.md
  UI: 캐릭터 선택 · 프로필 수사 파일 · 증거 인벤토리 · 단서 배너 · 조합 지목 (다크 테마)
"""

from __future__ import annotations

import base64
import html
import os
import re
import time
from datetime import timedelta
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
SUSPECT_PORTRAITS = {
    "suspect_a": ROOT / "assets" / "suspects" / "suspect_a.jpg",
    "suspect_b": ROOT / "assets" / "suspects" / "suspect_b.jpg",
    "suspect_c": ROOT / "assets" / "suspects" / "suspect_c.jpg",
}
# 압력 단계별 표정 초상 (0=평온 · 1=긴장 · 2=균열 · 3=붕괴)
SUSPECT_PORTRAIT_STAGES: dict[str, dict[int, Path]] = {
    sid: {
        0: base,
        1: ROOT / "assets" / "suspects" / f"{sid}_s1.jpg",
        2: ROOT / "assets" / "suspects" / f"{sid}_s2.jpg",
        3: ROOT / "assets" / "suspects" / f"{sid}_s3.jpg",
    }
    for sid, base in SUSPECT_PORTRAITS.items()
}
# 수사 파일(프로필) 전신 — 웹용 JPEG (선택 그리드는 bust PNG)
SUSPECT_FULLBODY = {
    "suspect_a": ROOT / "assets" / "suspects" / "suspect_a_full.jpg",
    "suspect_b": ROOT / "assets" / "suspects" / "suspect_b_full.jpg",
    "suspect_c": ROOT / "assets" / "suspects" / "suspect_c_full.jpg",
}
# 심문 채팅 아바타
CHAT_AVATARS = {
    "detective": ROOT / "assets" / "characters" / "detective.jpg",
    "assistant": ROOT / "assets" / "characters" / "assistant.jpg",
}
SUSPECT_NAME_TO_ID = {
    "김팀장": "suspect_a",
    "이대리": "suspect_b",
    "박신입": "suspect_c",
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

# 일시 OFF — 타임어택·턴 타임아웃 스트라이크 (다시 켤 때 True + configs timer_enabled)
TIMER_FEATURE_ENABLED = False

# Golden Route UI 연출 (카드→슬랙→네트워크→조합 지목) — culprit_id 미사용
GOLDEN_ROUTE_STEPS = [
    {
        "evidence_id": "ev_card_03",
        "short": "법인카드",
        "kicker": "STEP 01 · CARD",
        "query": "법인카드 룸살롱",
        "beat": "김팀장 알리바이를 흔드는 결제 전표",
    },
    {
        "evidence_id": "ev_msg_12",
        "short": "슬랙 DM",
        "kicker": "STEP 02 · SLACK",
        "query": "슬랙 DM 박신입 서버실",
        "beat": "박신입을 목격자로 고정하는 DM",
    },
    {
        "evidence_id": "ev_net_01",
        "short": "네트워크",
        "kicker": "STEP 03 · NETWORK",
        "query": "라운지 Wi-Fi 100GB",
        "beat": "라운지 ~100GB 전송 — 결정타",
    },
]
GOLDEN_ROUTE_ACCUSE = {
    "short": "조합 지목",
    "kicker": "STEP 04 · ACCUSE",
    "beat": "이대리 + 네트워크 + (카드 또는 슬랙)",
    "suspect_name": "이대리",
}


# 수사 파일 · CHARACTER PROFILE (인적사항) — 명탐정S 상단 블록
PROFILE_IDENTITY_FIELDS = [
    ("archetype", "유형"),
    ("age_group", "나이대"),
    ("rank", "직급"),
    ("personality", "성격"),
    ("gender", "성별"),
    ("birth_date", "생년월일"),
    ("height", "키"),
    ("weight", "몸무게"),
    ("eye_color", "눈 색"),
    ("hair_color", "머리 색"),
    ("occupation", "직업"),
    ("marital_status", "결혼유무"),
    ("family", "가족관계"),
    ("criminal_record", "범죄이력"),
    ("notes", "특이사항"),
]
# 수사 파일 · INTERROGATION NOTE (심문 노트) — 말투·알리바이 분리 블록
PROFILE_INTERROGATION_FIELDS = [
    ("speech_style", "말투"),
    ("fluster_reaction", "당황 시 반응"),
    ("sample_line", "예시 대사"),
    ("claimed_alibi", "주장 알리바이"),
]
PROFILE_FIELD_ORDER = PROFILE_IDENTITY_FIELDS + PROFILE_INTERROGATION_FIELDS

_qp = st.query_params
_embed = str(_qp.get("embed") or "") in ("1", "true", "yes")
if _embed:
    # 인트로 셸 iframe — 부모 페이지가 game.mp3 재생 (이중 재생 방지)
    st.session_state["from_intro_shell"] = True
st.set_page_config(
    page_title="진실의 방으로",
    page_icon="🚪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit 기본 primary(빨강) flash 방지 — 어떤 위젯보다 먼저 주입
st.markdown(
    """
    <style>
    :root {
      --primary-color: #7A9BB8 !important;
      --app-topbar-h: 3.15rem;
    }
    /* ST 1.50+: 사이드바 열기 버튼은 stToolbar 안 stExpandSidebarButton.
       툴바 전체를 숨기면 햄버거도 사라지므로 상태 위젯만 숨김. */
    [data-testid="stStatusWidget"],
    [data-testid="stDecoration"],
    #MainMenu {
      display: none !important;
      visibility: hidden !important;
      pointer-events: none !important;
    }
    header[data-testid="stHeader"],
    [data-testid="stToolbar"] {
      display: flex !important;
      visibility: visible !important;
      background: transparent !important;
      pointer-events: none !important;
      min-height: var(--app-topbar-h) !important;
      height: var(--app-topbar-h) !important;
    }
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      visibility: visible !important;
      pointer-events: auto !important;
      /* 탑바보다 위 — 헤더 스택을 탑바 위로 끌어올림 */
      z-index: 1000040 !important;
    }
    /* 헤더 전체를 탑바 위로 — 자식 z-index가 탑바에 가려지지 않게 */
    header[data-testid="stHeader"] {
      z-index: 1000035 !important;
      background: transparent !important;
    }
    /* 뤼튼형 상단: 투명 히트영역(실제 클릭) + 탑바 안 시각 햄버거 */
    [data-testid="stExpandSidebarButton"] {
      position: fixed !important;
      top: 0.4rem !important;
      left: 0.45rem !important;
      width: 2.4rem !important;
      height: 2.4rem !important;
      margin: 0 !important;
      padding: 0 !important;
      border-radius: 6px !important;
      border: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
      opacity: 1 !important;
      color: #e8eef4 !important;
    }
    [data-testid="stExpandSidebarButton"] span,
    [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
      font-size: 0 !important;
      line-height: 0 !important;
      color: transparent !important;
      opacity: 0 !important;
    }
    .app-topbar {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      height: var(--app-topbar-h) !important;
      z-index: 1000020 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
      gap: 0.55rem !important;
      padding: 0 3.4rem 0 0.45rem !important;
      box-sizing: border-box !important;
      pointer-events: none !important;
      background: rgba(13, 16, 22, 0.94) !important;
      border-bottom: 1px solid rgba(122, 155, 184, 0.18) !important;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }
    .app-topbar-burger {
      flex: 0 0 2.4rem !important;
      width: 2.4rem !important;
      height: 2.4rem !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      overflow: visible !important;
    }
    .app-topbar-burger::before {
      content: "" !important;
      display: block !important;
      width: 1.15rem !important;
      height: 2px !important;
      border-radius: 1px !important;
      background: #e8eef4 !important;
      box-shadow:
        0 6px 0 #e8eef4,
        0 12px 0 #e8eef4 !important;
      transform: translateY(-6px) !important;
    }
    .app-topbar-brand {
      font-size: 1.05rem !important;
      font-weight: 700 !important;
      letter-spacing: 0.04em !important;
      color: #e8eef4 !important;
      line-height: 1 !important;
      white-space: nowrap !important;
      text-align: left !important;
    }
    div[data-testid="stElementContainer"]:has(.app-topbar),
    div[data-testid="stMarkdownContainer"]:has(.app-topbar) {
      position: absolute !important;
      width: 0 !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: visible !important;
      opacity: 1 !important;
      pointer-events: none !important;
    }
    [data-testid="stMainBlockContainer"],
    .stMainBlockContainer,
    .stMain .block-container,
    .main .block-container {
      padding-top: calc(var(--app-topbar-h) + 0.35rem) !important;
      margin-top: 0 !important;
    }
    /* st.markdown(<style>) 빈 박스가 flex gap(16px)을 쌓아 상단 여백을 만듦 → 레이아웃 제외 */
    div[data-testid="stElementContainer"]:has(style),
    div[data-testid="stElementContainer"]:has(.stMarkdownContainer > style) {
      display: none !important;
      height: 0 !important;
      max-height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: 0 !important;
      overflow: hidden !important;
      position: absolute !important;
      pointer-events: none !important;
    }
    @media (max-width: 900px) {
      [data-testid="stMainBlockContainer"],
      .stMainBlockContainer,
      .stMain .block-container,
      .main .block-container {
        padding-top: calc(var(--app-topbar-h) + 30px) !important;
        margin-top: 0 !important;
      }
    }
    @media (min-width: 901px) {
      [data-testid="stMainBlockContainer"],
      .stMainBlockContainer,
      .stMain .block-container,
      .main .block-container {
        margin-top: auto !important;
      }
    }
    /* 사이드바 본문 여백 — 조기 적용 (헤더와 분리된 UserContent) */
    [data-testid="stSidebarContent"] {
      padding: 0 !important;
    }
    [data-testid="stSidebarUserContent"] {
      padding: 0.9rem 0.95rem 1.35rem !important;
      box-sizing: border-box !important;
    }
    button[kind="primary"],
    [data-testid="baseButton-primary"],
    [data-testid="stBaseButton-primary"],
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
      background-color: #3d5568 !important;
      background-image: none !important;
      border-color: #4a657a !important;
      color: #e8eef4 !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
      background-color: #4a657a !important;
      border-color: #5a7890 !important;
      color: #e8eef4 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _api() -> str:
    return API_URL.rstrip("/")


def _start_new_investigation(*, with_tab_intro: bool = False) -> None:
    """새 세션 생성. with_tab_intro=True면 Streamlit 탭 인트로, 아니면 바로 본편."""
    r = requests.post(f"{_api()}/api/v1/session", timeout=10)
    r.raise_for_status()
    st.session_state["game"] = r.json()
    st.session_state["log"] = []
    st.session_state["interrogation_chat"] = []
    st.session_state.pop("last_agent_turn", None)
    st.session_state["hits"] = []
    st.session_state["pending_clues"] = []
    st.session_state["last_ending"] = None
    st.session_state.pop("last_ending_ok", None)
    st.session_state["show_intro"] = bool(with_tab_intro)
    st.session_state["intro_scene_idx"] = 0
    st.session_state["turn_deadline"] = None
    st.session_state["game_started"] = False
    st.session_state.pop("bgm_should_play", None)
    st.rerun()


def _append_chat(
    role: str,
    content: str,
    *,
    name: str = "",
    suspect_id: str = "",
    portrait_stage: int | None = None,
) -> None:
    """심문 채팅 스레드에 메시지 추가."""
    text = (content or "").strip()
    if role == "suspect":
        text = _strip_question_echo(text)
    if not text:
        return
    st.session_state.setdefault("interrogation_chat", []).append(
        {
            "role": role,
            "name": name or "",
            "content": text,
            "suspect_id": suspect_id or "",
            "portrait_stage": portrait_stage,
        }
    )


def _strip_question_echo(text: str) -> str:
    """채팅에 질문이 따로 있으므로 답변 끝 질문 요약 접미 제거."""
    cleaned = re.sub(r"\s*\(질문\s*요약:\s*[^)]*\)\s*$", "", text or "")
    cleaned = re.sub(r"\s*\(질문:\s*[^)]*\)\s*$", "", cleaned)
    return cleaned.strip()


def _portrait_path(suspect_id: str, stage: int = 0) -> Path | None:
    """압력 단계에 맞는 용의자 초상. 없으면 낮은 단계·기본 초상으로 폴백."""
    stages = SUSPECT_PORTRAIT_STAGES.get(suspect_id) or {}
    stage_i = max(0, min(3, int(stage)))
    for s in range(stage_i, -1, -1):
        path = stages.get(s)
        if path and path.exists():
            return path
    base = SUSPECT_PORTRAITS.get(suspect_id)
    if base and base.exists():
        return base
    return None


def _chat_avatar_path(
    role: str,
    *,
    name: str = "",
    suspect_id: str = "",
    portrait_stage: int | None = None,
) -> str | None:
    """채팅 버블용 캐릭터 초상 경로."""
    if role == "user":
        path = CHAT_AVATARS["detective"]
    elif role == "assistant":
        path = CHAT_AVATARS["assistant"]
    elif role == "suspect":
        sid = suspect_id or SUSPECT_NAME_TO_ID.get(name, "")
        stage = 0 if portrait_stage is None else int(portrait_stage)
        path = _portrait_path(sid, stage)
    else:
        return None
    if path and Path(path).exists():
        return str(path)
    return None


def _render_interrogation_chat() -> None:
    """심문 탭 채팅 스레드 (스크롤은 목록만, 입력창과 분리)."""
    if "interrogation_chat" not in st.session_state:
        st.session_state["interrogation_chat"] = []
    # 기존 세션 메시지에도 질문 요약 접미가 있으면 정리
    for msg in st.session_state["interrogation_chat"]:
        if str(msg.get("role") or "") == "suspect":
            msg["content"] = _strip_question_echo(str(msg.get("content") or ""))
    messages = list(st.session_state.get("interrogation_chat") or [])
    st.markdown(
        '<div class="interrogation-chat-mark" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    if not messages:
        return
    # height 지정 → 메시지 목록만 독립 스크롤 (chat_input은 바깥에 고정)
    with st.container(height=360, border=False):
        for msg in messages:
            role = str(msg.get("role") or "system")
            name = str(msg.get("name") or "")
            content = str(msg.get("content") or "")
            sid = str(msg.get("suspect_id") or "")
            stage_raw = msg.get("portrait_stage")
            stage = None if stage_raw is None else int(stage_raw)
            avatar = _chat_avatar_path(
                role, name=name, suspect_id=sid, portrait_stage=stage
            )
            if role == "user":
                with st.chat_message("user", avatar=avatar):
                    st.caption(name or "탐정")
                    st.markdown(content)
            elif role == "suspect":
                with st.chat_message("assistant", avatar=avatar):
                    st.caption(name or "용의자")
                    st.markdown(content)
            elif role == "assistant":
                with st.chat_message("assistant", avatar=avatar):
                    st.caption(name or "조수")
                    st.markdown(content)
            else:
                st.caption(content)


def _browser_asset_url(rel: str) -> str:
    """브라우저가 직접 받는 정적 URL (서버 루프백 API_URL과 분리)."""
    base = (os.environ.get("ASSET_PUBLIC_URL") or "").rstrip("/")
    if not base:
        if os.environ.get("RAILWAY_ENVIRONMENT") or Path("/.dockerenv").exists():
            base = "/assets"
        else:
            base = f"{API_URL.rstrip('/')}/assets"
    return f"{base}/{rel.lstrip('/')}"


def _inject_game_bgm(*, muted: bool = False, force_play: bool = False) -> None:
    """Streamlit 게임 화면 BGM + 인트로와 동일한 EQ 토글 버튼."""
    if st.session_state.get("from_intro_shell"):
        return
    src = html.escape(_browser_asset_url("audio/game.mp3"), quote=True)
    muted_js = "true" if muted else "false"
    force_js = "true" if force_play else "false"
    # 마커 → 다음 iframe 컨테이너를 우상단 고정
    st.markdown(
        '<div class="game-bgm-dock-mark" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    components.html(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<style>
  html,body{{margin:0;padding:0;background:transparent;overflow:hidden;}}
  .bgm-toggle{{
    margin:0;width:2.5rem;height:2rem;padding:0;
    display:inline-grid;place-items:center;
    border-radius:0.4rem;border:1px solid rgba(255,255,255,0.35);
    background:rgba(18,22,30,0.9);color:#e8e4dc;cursor:pointer;
  }}
  .bgm-toggle:hover{{border-color:#fff;}}
  .bgm-toggle[aria-pressed="true"]{{border-color:#7A9BB8;}}
  .eq{{display:flex;align-items:flex-end;justify-content:center;gap:2px;width:14px;height:12px;}}
  .eq i{{display:block;width:2px;height:40%;border-radius:1px;background:#c5ccd6;transform-origin:bottom center;}}
  .bgm-toggle[aria-pressed="true"] .eq i{{
    background:#7A9BB8;animation:eq-bounce .9s ease-in-out infinite;
  }}
  .bgm-toggle[aria-pressed="true"] .eq i:nth-child(1){{animation-delay:0s;}}
  .bgm-toggle[aria-pressed="true"] .eq i:nth-child(2){{animation-delay:.15s;}}
  .bgm-toggle[aria-pressed="true"] .eq i:nth-child(3){{animation-delay:.35s;}}
  .bgm-toggle[aria-pressed="true"] .eq i:nth-child(4){{animation-delay:.22s;}}
  .bgm-toggle[aria-pressed="false"] .eq i{{height:35%;opacity:.55;}}
  @keyframes eq-bounce{{0%,100%{{height:30%;}}50%{{height:100%;}}}}
</style></head>
<body>
<button type="button" class="bgm-toggle" id="bgmToggle" aria-pressed="false" aria-label="배경음악" title="BGM OFF">
  <span class="eq" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
</button>
<audio id="a" src="{src}" loop preload="auto" playsinline></audio>
<script>
(function(){{
  const a=document.getElementById("a");
  const btn=document.getElementById("bgmToggle");
  const VOL=0.06;
  let userMuted={muted_js};
  let audible=false;
  a.volume=VOL;
  function setUi(on){{
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.setAttribute("aria-label", on ? "배경음악 끄기" : "배경음악 켜기");
    btn.title = on ? "BGM ON" : "BGM OFF";
  }}
  async function play(){{
    if(userMuted){{a.pause();setUi(false);return false;}}
    a.volume=VOL;
    try{{
      await a.play();
      a.volume=VOL;
      audible=true;
      setUi(true);
      return true;
    }}catch(e){{
      audible=false;
      setUi(false);
      return false;
    }}
  }}
  function stop(){{
    a.pause();
    audible=false;
    setUi(false);
  }}
  btn.addEventListener("click", async function(e){{
    e.preventDefault();
    e.stopPropagation();
    if(audible && !a.paused && !userMuted){{
      userMuted=true;
      stop();
      return;
    }}
    userMuted=false;
    await play();
  }});
  if({force_js} && !userMuted){{ play(); }}
  else if(!userMuted){{
    ["pointerdown","keydown","touchstart"].forEach(function(ev){{
      try{{window.parent.addEventListener(ev,function(){{if(!userMuted&&!audible)play();}},{{once:true,passive:true}});}}catch(err){{}}
    }});
  }}
}})();
</script>
</body></html>""",
        height=36,
        width=44,
    )


def _sync_ops_rail_width() -> None:
    """우측 패널 폭은 CSS --ops-rail-width 고정. (버튼 실측 연동은 패널을 과도하게 줄여 비활성)"""
    return


def _reset_timer() -> None:
    turn_sec = int((st.session_state.get("game") or {}).get("turn_seconds") or 20)
    st.session_state["turn_deadline"] = time.time() + turn_sec
    st.session_state["timer_paused"] = False
    st.session_state.pop("timer_remaining", None)


def _pause_timer() -> None:
    """프로필 등 팝업 오픈 시 — 남은 시간 동결."""
    if st.session_state.get("timer_paused"):
        return
    deadline = float(st.session_state.get("turn_deadline") or 0)
    if deadline <= 0:
        return
    st.session_state["timer_remaining"] = max(0.0, deadline - time.time())
    st.session_state["timer_paused"] = True


def _resume_timer() -> None:
    """팝업 닫힘(on_dismiss) — 동결된 남은 시간으로 재개."""
    if not st.session_state.get("timer_paused"):
        return
    remaining = float(st.session_state.get("timer_remaining") or 0)
    st.session_state["turn_deadline"] = time.time() + remaining
    st.session_state["timer_paused"] = False
    st.session_state.pop("timer_remaining", None)


def _timer_seconds_left() -> float:
    if st.session_state.get("timer_paused"):
        return max(0.0, float(st.session_state.get("timer_remaining") or 0))
    deadline = float(st.session_state.get("turn_deadline") or 0)
    return max(0.0, deadline - time.time())


def _evidence_label(eid: str) -> str:
    return CLUE_LABELS.get(eid, eid)


@st.cache_data(show_spinner=False)
def _file_data_uri(path_str: str, mtime_ns: int = 0) -> str:
    """초상 base64 캐시 — 파일 변경(mtime) 시 자동 무효화."""
    path = Path(path_str)
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    _ = mtime_ns  # cache key
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _portrait_data_uri(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    return _file_data_uri(str(path), mtime_ns)


def _inject_theme(*, mental: bool = False, revoked: bool = False) -> None:
    # 저채도 블루그레이 — 눈 피로 완화 · 야근 오피스 배경
    accent = "#7A9BB8" if not mental and not revoked else "#8A9BB5"
    bg_url = html.escape(_browser_asset_url("ui/game_bg.jpg"), quote=True)
    st.markdown(
        f"""
        <style>
        /* 외부 폰트 CDN 제거 — 한국에서 첫 로딩 지연 완화 */
        :root {{
          --ink: #d5d8de;
          --muted: #8b919c;
          --accent: {accent};
          --accent-soft: rgba(122,155,184,0.22);
          --line: rgba(200,210,220,0.14);
          --surface: rgba(18, 22, 30, 0.72);
          --surface-solid: #1a1e26;
          --panel-glass: rgba(12, 16, 22, 0.62);
          /* 우측 패널 폭 — 버튼 실측 연동 제거(패널이 과도하게 좁아지던 원인) */
          --ops-rail-width: 22rem;
          --game-left-max: 78rem;
          /* 용의자 카드 간격 = 좌·우 스테이지 간격 */
          --suspect-gutter: 2.5rem;
          --game-stage-gap: var(--suspect-gutter);
          /* 실측: span.profile-pill = 72 × 24.8 */
          --profile-pill-w: 72px;
          --profile-pill-h: 25px;
          --font-ui: "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", "Segoe UI", sans-serif;
          --font-display: "Apple SD Gothic Neo", "Malgun Gothic", "Black Han Sans", sans-serif;
          --app-topbar-h: 3.15rem;
        }}

        .stApp {{
          background-color: #0b0e14 !important;
          background-image:
            linear-gradient(180deg, rgba(7,9,13,0.78) 0%, rgba(7,9,13,0.52) 42%, rgba(7,9,13,0.82) 100%),
            radial-gradient(ellipse at 50% 35%, transparent 18%, rgba(5,7,10,0.62) 100%),
            url("{bg_url}") !important;
          background-position: center, center, center !important;
          background-size: cover, cover, cover !important;
          background-repeat: no-repeat !important;
          background-attachment: fixed, fixed, fixed !important;
          color: var(--ink);
          min-height: 100dvh !important;
          overflow-x: hidden !important;
        }}
        /* 뷰포트 세로 중앙 — 콘텐츠가 짧을 때만 가운데, 길면 상단부터 스크롤.
           height:100% + min-height:100vh 중첩은 맥북에서 불필요 스크롤을 만듦. */
        html, body {{
          min-height: 100% !important;
          height: auto !important;
          overflow-x: hidden !important;
        }}
        [data-testid="stAppViewContainer"] {{
          min-height: 100dvh !important;
          display: flex !important;
          flex-direction: column !important;
          overflow-x: hidden !important;
        }}
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stAppViewContainer"] > .stMain,
        [data-testid="stMain"],
        section.main,
        section.stMain {{
          flex: 1 1 auto !important;
          min-height: 0 !important;
          display: flex !important;
          flex-direction: column !important;
          justify-content: flex-start !important;
        }}
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stAppViewContainer"] > .stMain,
        [data-testid="stMain"],
        section.main,
        section.stMain,
        .main .block-container,
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        [data-testid="stHeader"] {{
          background: transparent !important;
        }}
        /* Streamlit 1.50+: class가 .main → .stMain. 기본 padding-top은 6rem이라
           옛 선택자(.main .block-container)는 무시되어 위로 안 올라감. */
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        .stMain .block-container,
        .main .block-container {{
          padding-top: calc(var(--app-topbar-h, 3.15rem) + 0.35rem) !important;
          padding-bottom: 0.75rem !important;
          /* 맥북 등 좁은 화면: 좌우 최소 여백 / 광폭 모니터: max-width 가운데 정렬 */
          padding-left: clamp(1.25rem, 3.5vw, 2.25rem) !important;
          padding-right: clamp(1.25rem, 3.5vw, 2.25rem) !important;
          /* 좌·우 묶음이 화면 가운데에 오도록 스테이지 폭 제한 */
          max-width: calc(
            var(--game-left-max) + var(--game-stage-gap) + var(--ops-rail-width) + 4.5rem
          ) !important;
          margin-left: auto !important;
          margin-right: auto !important;
          /* 기본은 상단 고정 — PC에서만 세로 중앙 */
          margin-top: 0 !important;
          margin-bottom: 0.5rem !important;
          width: 100% !important;
          box-sizing: border-box !important;
        }}
        @media (min-width: 901px) {{
          [data-testid="stMainBlockContainer"],
          .stMainBlockContainer,
          .stMain .block-container,
          .main .block-container {{
            /* 짧으면 세로 중앙, 길면 auto→0 으로 상단 스크롤 가능 */
            margin-top: auto !important;
            margin-bottom: auto !important;
          }}
        }}
        /* height=0 components.html 이 남기는 세로 틈 제거 */
        div[data-testid="stElementContainer"]:has(iframe[height="0"]),
        div[data-testid="stElementContainer"]:has(iframe[height="0px"]),
        div[data-testid="element-container"]:has(iframe[height="0"]),
        iframe[height="0"],
        iframe[height="0px"] {{
          display: none !important;
          height: 0 !important;
          max-height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          width: 0 !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }}
        /* st.markdown(<style>) 빈 박스가 VerticalBlock flex gap을 누적 → 상단 여백 주범 */
        div[data-testid="stElementContainer"]:has(style),
        div[data-testid="stElementContainer"]:has(.stMarkdownContainer > style) {{
          display: none !important;
          height: 0 !important;
          max-height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          width: 0 !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }}
        /* BGM 토글 — 예전 Streamlit 개발 알림(우상단) 자리 */
        div[data-testid="stElementContainer"]:has(.game-bgm-dock-mark) {{
          position: absolute !important;
          width: 0 !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: hidden !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.game-bgm-dock-mark)
          + div[data-testid="stElementContainer"],
        div[data-testid="stElementContainer"]:has(iframe[height="36"]) {{
          position: fixed !important;
          top: 0.4rem !important;
          right: 0.75rem !important;
          z-index: 1000025 !important;
          width: 2.75rem !important;
          height: 2.25rem !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: visible !important;
          background: transparent !important;
        }}
        div[data-testid="stElementContainer"]:has(.game-bgm-dock-mark)
          + div[data-testid="stElementContainer"] iframe,
        div[data-testid="stElementContainer"]:has(iframe[height="36"]) iframe {{
          width: 44px !important;
          height: 36px !important;
          border: 0 !important;
          background: transparent !important;
        }}
        /* 좌·우 메인: 한 덩어리로 붙이고 가운데 정렬 — 좌우 패딩 제거
           (안쪽 대상|Ops 행은 .suspect-ops-row-mark 전용 — grid-hint로 잡지 않음) */
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker),
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker) {{
          justify-content: center !important;
          align-items: flex-start !important;
          gap: var(--game-stage-gap) !important;
          column-gap: var(--game-stage-gap) !important;
          width: 100% !important;
          max-width: 100% !important;
          margin-top: 0 !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
          padding-left: 0 !important;
          padding-right: 0 !important;
          padding-inline: 0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="stColumn"] {{
          padding-left: 0 !important;
          padding-right: 0 !important;
          padding-inline: 0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="column"]:first-child,
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="stColumn"]:first-child {{
          flex: 1 1 auto !important;
          width: auto !important;
          max-width: var(--game-left-max) !important;
          min-width: 0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="column"]:last-child,
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="stColumn"]:last-child,
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="column"]:last-child,
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="stColumn"]:last-child {{
          flex: 0 0 var(--ops-rail-width) !important;
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
        }}
        /* 용의자|Ops 안쪽 행 — pick-frame 간격 규칙이 메인 행을 덮지 않게 */
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark) {{
          gap: 2.75rem !important;
          column-gap: 2.75rem !important;
          flex-wrap: nowrap !important;
          justify-content: flex-start !important;
          align-items: flex-start !important;
          width: 100% !important;
          max-width: 100% !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
          margin-bottom: 0 !important;
          padding: 0 !important;
        }}
        /* 용의자 카드 가로 간격 — 3열 레거시 (ops 행 제외) */
        div[data-testid="stHorizontalBlock"]:has(.suspect-pick-frame):not(:has(.suspect-ops-row-mark)):not(:has(.ops-kicker)) {{
          gap: var(--suspect-gutter) !important;
          column-gap: var(--suspect-gutter) !important;
          flex-wrap: nowrap !important;
          padding-left: 0 !important;
          padding-right: 0 !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-pick-frame)
          > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.suspect-pick-frame)
          > div[data-testid="stColumn"] {{
          padding-left: 0 !important;
          padding-right: 0 !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
        }}
        div[data-testid="column"]:has(.suspect-pick-frame) > div,
        div[data-testid="stColumn"]:has(.suspect-pick-frame) > div {{
          padding-left: 0 !important;
          padding-right: 0 !important;
        }}
        .panel-stack-gap {{
          display: block !important;
          height: 0.85rem !important;
          min-height: 0.85rem !important;
          line-height: 0.85rem !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        .right-panel-marker {{
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        .stApp, .stApp p, .stApp label, .stMarkdown, .stCaption {{
          font-family: var(--font-ui) !important;
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
          font-family: var(--font-display) !important;
          letter-spacing: 0.02em;
          color: #c8ced8 !important;
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        /* File change · Rerun 등 — 툴바 전체 숨김 금지(ST1.50 사이드바 열기 버튼이 툴바 안) */
        [data-testid="stStatusWidget"],
        [data-testid="stDecoration"],
        #MainMenu {{
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
        }}
        header[data-testid="stHeader"],
        [data-testid="stToolbar"] {{
          display: flex !important;
          visibility: visible !important;
          background: transparent !important;
          pointer-events: none !important;
        }}
        /* 사이드바 — 헤더/탑바보다 위 (닫기 X가 가려지지 않게) */
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"] {{
          position: fixed !important;
          left: 0 !important;
          top: 0 !important;
          bottom: 0 !important;
          z-index: 1000100 !important;
          background: #0e1014 !important;
          border-right: 1px solid rgba(255,255,255,0.08) !important;
          height: 100dvh !important;
          min-height: 100dvh !important;
          max-height: 100dvh !important;
          box-sizing: border-box !important;
          /* 폭은 항상 동일 — 접을 때 width:0 이면 골든루트 등 레이아웃이 리플로우됨 */
          width: min(78vw, 19.5rem) !important;
          min-width: min(78vw, 19.5rem) !important;
          max-width: min(78vw, 19.5rem) !important;
          transition: transform 280ms ease !important;
        }}
        section[data-testid="stSidebar"][aria-expanded="true"],
        [data-testid="stSidebar"][aria-expanded="true"] {{
          transform: none !important;
          visibility: visible !important;
          pointer-events: auto !important;
          overflow: hidden !important;
          border-right: 1px solid rgba(255,255,255,0.08) !important;
        }}
        /* 접힘: 폭 유지한 채 화면 밖으로만 이동 (내용 레이아웃 = 펼침과 동일) */
        section[data-testid="stSidebar"][aria-expanded="false"],
        [data-testid="stSidebar"][aria-expanded="false"] {{
          transform: translateX(-105%) !important;
          visibility: hidden !important;
          pointer-events: none !important;
          overflow: hidden !important;
          border-right: 0 !important;
          box-shadow: none !important;
        }}
        /* 사이드바 열림 시 탑바·햄버거가 닫기(X)를 가리지 않게 */
        .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .app-topbar,
        .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) [data-testid="stExpandSidebarButton"],
        .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) header[data-testid="stHeader"] {{
          z-index: 1 !important;
        }}
        [data-testid="stSidebar"] > div:first-child {{
          background: transparent !important;
          position: relative !important;
          width: 100% !important;
          max-width: 100% !important;
          min-width: 0 !important;
          height: 100% !important;
          min-height: 100% !important;
          max-height: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          box-sizing: border-box !important;
          padding: 0 !important;
          margin: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
          flex: 1 1 auto !important;
          width: 100% !important;
          height: 100% !important;
          min-height: 0 !important;
          max-height: 100% !important;
          overflow-x: hidden !important;
          overflow-y: auto !important;
          overscroll-behavior: contain !important;
          box-sizing: border-box !important;
          /* 헤더·본문 패딩을 분리 — Content 자체는 0 */
          padding: 0 !important;
          padding-left: 0 !important;
          padding-right: 0 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarContent"],
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
          gap: 0.35rem !important;
        }}
        /* 사이드바 본문(헤더 아래) — 좌우·상단 여백 */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
          box-sizing: border-box !important;
          width: 100% !important;
          padding: 0.85rem 0.95rem 1.35rem !important;
          padding-top: 0.9rem !important;
          padding-left: 0.95rem !important;
          padding-right: 0.95rem !important;
          padding-bottom: 1.35rem !important;
          margin: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"]
          > div[data-testid="stVerticalBlock"],
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"]
          [data-testid="stVerticalBlockBorderWrapper"] {{
          padding-left: 0 !important;
          padding-right: 0 !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
        }}
        [data-testid="stSidebar"] .side-nav-shell {{
          box-sizing: border-box !important;
          width: 100% !important;
          padding: 0 !important;
          margin: 0 !important;
        }}
        /* 골든 루트: 접힘/펼침 모두 펼침 레이아웃 고정 */
        [data-testid="stSidebar"] .side-section-label {{
          margin: 0 0 0.55rem !important;
          position: static !important;
          transform: none !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.side-section-gap-before) {{
          margin-top: var(--side-block-gap, 2.2rem) !important;
        }}
        [data-testid="stSidebar"] .golden-route,
        [data-testid="stSidebar"] .golden-steps,
        [data-testid="stSidebar"] .golden-step,
        [data-testid="stSidebar"] .golden-hint {{
          position: static !important;
          transform: none !important;
          transition: none !important;
        }}
        @media (max-width: 900px) {{
          section[data-testid="stSidebar"],
          [data-testid="stSidebar"] {{
            height: 100dvh !important;
            min-height: 100dvh !important;
            max-height: 100dvh !important;
            width: min(78vw, 19.5rem) !important;
            min-width: min(78vw, 19.5rem) !important;
            max-width: min(78vw, 19.5rem) !important;
          }}
          /* 모바일: 탑바 직후 본문 밀착 */
          [data-testid="stMainBlockContainer"],
          .stMainBlockContainer,
          .stMain .block-container,
          .main .block-container {{
            margin-top: 0 !important;
            margin-bottom: 0.35rem !important;
            padding-top: calc(var(--app-topbar-h, 3.15rem) + 30px) !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
          }}
          div[data-testid="stElementContainer"]:has(.status-banner) {{
            margin-top: 0.1rem !important;
            margin-bottom: 0.65rem !important;
          }}
        }}
        [data-testid="stSidebarHeader"] {{
          display: flex !important;
          align-items: center !important;
          justify-content: flex-start !important;
          gap: 0 !important;
          /* static → 닫기 버튼 absolute 기준을 사이드바(fixed)로 */
          position: static !important;
          z-index: 2 !important;
          box-sizing: border-box !important;
          width: 100% !important;
          max-width: 100% !important;
          height: var(--app-topbar-h, 3.15rem) !important;
          min-height: var(--app-topbar-h, 3.15rem) !important;
          max-height: var(--app-topbar-h, 3.15rem) !important;
          padding: 0 2.75rem 0 0.95rem !important;
          margin: 0 !important;
          margin-bottom: 0 !important;
          border-bottom: 1px solid rgba(122, 155, 184, 0.18) !important;
          background: rgba(13, 16, 22, 0.94) !important;
          flex-shrink: 0 !important;
        }}
        [data-testid="stSidebarHeader"]::before {{
          content: "진실의 방" !important;
          flex: 1 1 auto !important;
          min-width: 0 !important;
          font-family: var(--font-display) !important;
          font-size: 1.05rem !important;
          font-weight: 700 !important;
          letter-spacing: 0.04em !important;
          color: #e8eef4 !important;
          line-height: 1 !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
        }}
        [data-testid="stSidebarHeader"] [data-testid="stLogoSpacer"],
        [data-testid="stSidebarHeader"] [data-testid="stSidebarLogo"] {{
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          width: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        /* 닫기 X — 히트영역·아이콘 동일 정사각, 정중앙 */
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          visibility: visible !important;
          pointer-events: auto !important;
          position: absolute !important;
          top: calc(var(--app-topbar-h, 3.15rem) / 2) !important;
          right: 0.25rem !important;
          left: auto !important;
          bottom: auto !important;
          transform: translateY(-50%) !important;
          z-index: 5 !important;
          box-sizing: border-box !important;
          width: 2.4rem !important;
          min-width: 2.4rem !important;
          max-width: 2.4rem !important;
          height: 2.4rem !important;
          min-height: 2.4rem !important;
          max-height: 2.4rem !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 6px !important;
          background: transparent !important;
          background-image: none !important;
          opacity: 1 !important;
          color: #e8eef4 !important;
          box-shadow: none !important;
          overflow: hidden !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] > button,
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] [data-testid="stBaseButton-headerNoPadding"],
        [data-testid="stSidebar"] button[kind="headerNoPadding"],
        section[data-testid="stSidebar"] button[kind="headerNoPadding"],
        [data-testid="stSidebar"] [data-testid="stBaseButton-headerNoPadding"] {{
          position: absolute !important;
          inset: 0 !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          box-sizing: border-box !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          height: 100% !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 6px !important;
          background: transparent !important;
          background-image: none !important;
          box-shadow: none !important;
          transform: none !important;
        }}
        /* Streamlit 리사이즈 핸들 — 헤더가 좁아 보이는 원인 */
        [data-testid="stSidebar"] > div[style*="cursor"],
        [data-testid="stSidebar"] [class*="resize-handle"],
        .stSidebar [data-testid="StyledResizeHandle"],
        [data-testid="stSidebar"] > div > div[style*="width: 6px"],
        [data-testid="stSidebar"] > div > div[style*="width:6px"] {{
          display: none !important;
          width: 0 !important;
          pointer-events: none !important;
        }}
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
        [data-testid="stSidebar"] button[kind="headerNoPadding"] span,
        [data-testid="stSidebar"] button[kind="headerNoPadding"] [data-testid="stIconMaterial"] {{
          display: none !important;
          font-size: 0 !important;
          width: 0 !important;
          height: 0 !important;
          opacity: 0 !important;
        }}
        [data-testid="stSidebarCollapseButton"]::before {{
          content: "×" !important;
          position: absolute !important;
          left: 50% !important;
          top: 50% !important;
          transform: translate(-50%, -50%) !important;
          display: block !important;
          width: auto !important;
          height: auto !important;
          margin: 0 !important;
          padding: 0 !important;
          font-size: 1.55rem !important;
          line-height: 1 !important;
          color: #e8eef4 !important;
          font-weight: 300 !important;
          opacity: 1 !important;
          pointer-events: none !important;
        }}
        /* 사이드바 블록 간격 — 부제↔버튼(기존 넓은 간격) 기준으로 통일 */
        [data-testid="stSidebar"],
        section[data-testid="stSidebar"] {{
          --side-block-gap: 2.2rem;
          --side-auth-h: 2.35rem;
        }}
        .side-nav-brand {{
          display: flex;
          flex-direction: column;
          gap: 0;
          padding: 0 !important;
          border-bottom: 0;
          margin: 0 !important;
        }}
        .side-nav-brand-name {{
          display: none !important;
        }}
        .side-nav-case {{
          font-size: 0.78rem;
          color: rgba(180, 186, 196, 0.78);
          line-height: 1.35;
          margin: 0 !important;
        }}
        /* 1) 부제 → 수사 권한/새 수사 개시 (기존 넓은 간격 ≈ 1.75+0.45) */
        div[data-testid="stElementContainer"]:has(.side-nav-shell) {{
          margin: 0 0 var(--side-block-gap, 2.2rem) !important;
          padding: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.side-auth-row-mark) {{
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        .side-status-card {{
          margin: 0 !important;
          padding: 0.4rem 0.55rem;
          border-radius: 10px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.07);
          height: var(--side-auth-h, 2.35rem);
          min-height: var(--side-auth-h, 2.35rem);
          max-height: var(--side-auth-h, 2.35rem);
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          justify-content: center;
        }}
        .side-status-row {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.45rem;
        }}
        .side-status-row + .side-status-row {{
          margin-top: 0.35rem;
          padding-top: 0.35rem;
          border-top: 1px solid rgba(255,255,255,0.06);
        }}
        .side-status-label {{
          font-size: 0.65rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: rgba(160, 168, 180, 0.85);
        }}
        .side-status-hearts,
        .side-status-value {{
          font-size: 0.9rem;
          color: #e8eef4;
          font-weight: 600;
          letter-spacing: 0.06em;
        }}
        /* 수사 권한 | 새 수사 개시 한 줄 + 2) 버튼행 → 메뉴
           (모바일에서도 Streamlit 기본 세로 스택 방지) */
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.side-auth-row-mark),
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark),
        section[data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark) {{
          display: flex !important;
          flex-direction: row !important;
          flex-wrap: nowrap !important;
          align-items: center !important;
          gap: 0.45rem !important;
          margin: 0 0 var(--side-block-gap, 2.2rem) !important;
          width: 100% !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark)
          > div[data-testid="column"],
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark)
          > div[data-testid="stColumn"],
        section[data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark)
          > div[data-testid="column"],
        section[data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-restart-mark)
          > div[data-testid="stColumn"] {{
          flex: 1 1 0 !important;
          min-width: 0 !important;
          width: auto !important;
          max-width: none !important;
          height: var(--side-auth-h, 2.35rem) !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="column"]:has(.hud-restart-mark),
        [data-testid="stSidebar"]
          div[data-testid="stColumn"]:has(.hud-restart-mark) {{
          display: flex !important;
          flex-direction: column !important;
          justify-content: center !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="column"]:has(.hud-restart-mark)
          > div,
        [data-testid="stSidebar"]
          div[data-testid="stColumn"]:has(.hud-restart-mark)
          > div {{
          height: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          justify-content: center !important;
        }}
        .side-section-label {{
          margin: 0 0 0.55rem !important;
          padding: 0 0.1rem !important;
          font-size: 0.7rem !important;
          letter-spacing: 0.1em !important;
          text-transform: uppercase !important;
          color: rgba(150, 158, 170, 0.8) !important;
          font-weight: 600 !important;
        }}
        /* 3) 사건개요 → 골든 루트 (부제↔버튼과 동일) + 구분선 */
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.side-section-gap-before) {{
          margin-top: var(--side-block-gap, 2.2rem) !important;
          margin-bottom: 0.55rem !important;
          padding-top: 1.1rem !important;
          border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.side-section-label):not(:has(.side-section-gap-before)) {{
          margin-top: 0 !important;
          margin-bottom: 0.55rem !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark) {{
          margin-top: 0 !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] {{
          margin-top: 0 !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          margin-top: 0 !important;
        }}
        /* 사이드바 CTA · 메뉴 버튼 — 수사 권한 카드와 동일 높이 */
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"],
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] {{
          height: var(--side-auth-h, 2.35rem) !important;
          min-height: var(--side-auth-h, 2.35rem) !important;
          max-height: var(--side-auth-h, 2.35rem) !important;
          margin: 0 !important;
          padding: 0 !important;
          display: flex !important;
          align-items: stretch !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton,
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton {{
          width: 100% !important;
          height: 100% !important;
          margin: 0 !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          background: #3d5568 !important;
          border: 1px solid #4a657a !important;
          border-radius: 10px !important;
          width: 100% !important;
          min-height: var(--side-auth-h, 2.35rem) !important;
          height: var(--side-auth-h, 2.35rem) !important;
          max-height: var(--side-auth-h, 2.35rem) !important;
          font-size: 0.82rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
          color: #eef3f8 !important;
          box-shadow: none !important;
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          padding: 0 0.35rem !important;
          white-space: nowrap !important;
          box-sizing: border-box !important;
          line-height: 1 !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton > button p {{
          font-size: 0.82rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
          margin: 0 !important;
          white-space: nowrap !important;
          line-height: 1 !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.case-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          background: transparent !important;
          border: 0 !important;
          border-radius: 8px !important;
          box-shadow: none !important;
          min-height: 2.55rem !important;
          justify-content: flex-start !important;
          padding: 0.55rem 0.7rem !important;
          color: #e8eef4 !important;
          font-size: 0.92rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
        }}
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button:hover,
        [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.case-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button:hover {{
          background: rgba(255,255,255,0.06) !important;
          transform: none !important;
        }}
        [data-testid="stSidebar"] .golden-route {{
          margin: 0.25rem 0 0.5rem !important;
          padding: 0.35rem 0 !important;
          border: 0 !important;
          background: transparent !important;
          backdrop-filter: none !important;
          gap: 0.25rem !important;
        }}
        [data-testid="stSidebar"] .golden-route .panel-title {{
          display: none !important;
        }}
        [data-testid="stSidebar"] .golden-steps {{
          gap: 0.2rem !important;
        }}
        [data-testid="stSidebar"] .golden-step {{
          width: 100% !important;
          max-width: 100% !important;
          border-radius: 8px !important;
          border: 0 !important;
          background: transparent !important;
          padding: 0.5rem 0.55rem !important;
          white-space: normal !important;
        }}
        [data-testid="stSidebar"] .golden-step.is-done {{
          background: rgba(122,155,184,0.1) !important;
        }}
        [data-testid="stSidebar"] .golden-step.is-next {{
          background: rgba(212,175,105,0.12) !important;
        }}
        [data-testid="stSidebar"] .golden-step.is-locked {{
          opacity: 0.45 !important;
        }}
        [data-testid="stSidebar"] .golden-step-body strong {{
          font-size: 0.88rem !important;
          color: #e8eef4 !important;
          font-weight: 550 !important;
        }}
        [data-testid="stSidebar"] .golden-step-desc {{
          font-size: 0.72rem !important;
          color: rgba(180, 186, 196, 0.85) !important;
        }}
        [data-testid="stSidebar"] .golden-hint {{
          margin: 0.45rem 0.15rem 0 !important;
          font-size: 0.75rem !important;
          color: rgba(212,175,105,0.88) !important;
          font-weight: 550 !important;
        }}
        .sidebar-hud-title,
        .sidebar-case-sub {{
          display: none !important;
        }}
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          visibility: visible !important;
          pointer-events: auto !important;
          z-index: 1000040 !important;
        }}
        header[data-testid="stHeader"] {{
          z-index: 1000035 !important;
          background: transparent !important;
          opacity: 1 !important;
        }}
        [data-testid="stExpandSidebarButton"] {{
          position: fixed !important;
          top: 0.4rem !important;
          left: 0.45rem !important;
          width: 2.4rem !important;
          height: 2.4rem !important;
          margin: 0 !important;
          padding: 0 !important;
          border-radius: 6px !important;
          border: 0 !important;
          background: transparent !important;
          color: #e8eef4 !important;
          box-shadow: none !important;
          opacity: 1 !important;
        }}
        [data-testid="stExpandSidebarButton"] span,
        [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
          font-size: 0 !important;
          line-height: 0 !important;
          color: transparent !important;
          opacity: 0 !important;
        }}
        .app-topbar {{
          position: fixed !important;
          top: 0 !important;
          left: 0 !important;
          right: 0 !important;
          height: var(--app-topbar-h, 3.15rem) !important;
          z-index: 1000020 !important;
          display: flex !important;
          align-items: center !important;
          justify-content: flex-start !important;
          gap: 0.55rem !important;
          padding: 0 3.4rem 0 0.45rem !important;
          box-sizing: border-box !important;
          pointer-events: none !important;
          background: rgba(13, 16, 22, 0.94) !important;
          border-bottom: 1px solid rgba(122, 155, 184, 0.18) !important;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
        }}
        .app-topbar-burger {{
          flex: 0 0 2.4rem !important;
          width: 2.4rem !important;
          height: 2.4rem !important;
          display: inline-flex !important;
          align-items: center !important;
          justify-content: center !important;
          overflow: visible !important;
        }}
        .app-topbar-burger::before {{
          content: "" !important;
          display: block !important;
          width: 1.15rem !important;
          height: 2px !important;
          border-radius: 1px !important;
          background: #e8eef4 !important;
          box-shadow:
            0 6px 0 #e8eef4,
            0 12px 0 #e8eef4 !important;
          transform: translateY(-6px) !important;
        }}
        .app-topbar-brand {{
          font-family: var(--font-display) !important;
          font-size: 1.05rem !important;
          font-weight: 700 !important;
          letter-spacing: 0.04em !important;
          color: #e8eef4 !important;
          line-height: 1 !important;
          white-space: nowrap !important;
          text-align: left !important;
        }}
        div[data-testid="stElementContainer"]:has(.app-topbar),
        div[data-testid="stMarkdownContainer"]:has(.app-topbar) {{
          position: absolute !important;
          width: 0 !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: visible !important;
          pointer-events: none !important;
        }}

        .stButton > button {{
          border-radius: 4px !important;
          border: 1px solid rgba(170,190,210,0.28) !important;
          font-weight: 600 !important;
          letter-spacing: 0.04em !important;
          background: linear-gradient(180deg, rgba(36,44,56,0.92), rgba(22,28,38,0.92)) !important;
          color: var(--ink) !important;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 18px rgba(0,0,0,0.25) !important;
          transition: border-color 0.15s ease, background 0.15s ease, transform 0.12s ease !important;
        }}
        .stButton > button:hover {{
          border-color: rgba(210,225,240,0.55) !important;
          transform: translateY(-1px);
        }}
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"],
        .stButton > button[data-testid="stBaseButton-primary"],
        button[kind="primary"],
        [data-testid="baseButton-primary"],
        [data-testid="stBaseButton-primary"] {{
          background: linear-gradient(180deg, #4a657a, #354a5c) !important;
          background-image: linear-gradient(180deg, #4a657a, #354a5c) !important;
          border-color: #6d879c !important;
          color: #eef3f8 !important;
          text-transform: none !important;
        }}
        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover,
        [data-testid="stBaseButton-primary"]:hover {{
          background: linear-gradient(180deg, #5a7890, #3d5568) !important;
          border-color: #8aa4b8 !important;
          color: #e8eef4 !important;
        }}
        .stButton > button[kind="secondary"],
        .stButton > button[data-testid="baseButton-secondary"],
        .stButton > button[data-testid="stBaseButton-secondary"],
        button[kind="secondary"],
        [data-testid="stBaseButton-secondary"] {{
          background: rgba(18, 24, 34, 0.78) !important;
          border-color: rgba(200,210,220,0.22) !important;
          color: #c5ccd6 !important;
        }}
        /* 사이드바 메뉴 버튼 — 일반 secondary 스타일보다 우선 */
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.case-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.case-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          background: transparent !important;
          background-image: none !important;
          border: 0 !important;
          border-radius: 8px !important;
          box-shadow: none !important;
          min-height: 2.55rem !important;
          justify-content: flex-start !important;
          text-align: left !important;
          padding: 0.55rem 0.7rem !important;
          color: #e8eef4 !important;
          font-size: 0.92rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.howto-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button p,
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.case-hud-mark)
          + div[data-testid="stElementContainer"] .stButton > button p {{
          text-align: left !important;
          font-size: 0.92rem !important;
          color: #e8eef4 !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          background: #3d5568 !important;
          background-image: none !important;
          border: 1px solid #4a657a !important;
          border-radius: 10px !important;
          min-height: var(--side-auth-h, 2.35rem) !important;
          height: var(--side-auth-h, 2.35rem) !important;
          max-height: var(--side-auth-h, 2.35rem) !important;
          justify-content: center !important;
          box-shadow: none !important;
          color: #eef3f8 !important;
          font-size: 0.82rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] .stButton > button p {{
          font-size: 0.82rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
          margin: 0 !important;
        }}

        div[data-baseweb="select"] > div,
        .stTextInput input,
        .stMultiSelect div[data-baseweb="select"] > div {{
          background: rgba(10, 14, 20, 0.78) !important;
          border-radius: 4px !important;
          border: 1px solid rgba(170,190,210,0.24) !important;
          color: #e4e8ee !important;
          box-shadow: inset 0 0 0 1px rgba(0,0,0,0.25) !important;
        }}
        .stTextInput label,
        .stMultiSelect label,
        .stSelectbox label {{
          color: #9aa8b8 !important;
          font-size: 0.78rem !important;
          letter-spacing: 0.08em !important;
          text-transform: uppercase !important;
        }}

        /* Field Ops · Command Deck — 뤼튼형: 탭(가운데) 위 / composer 아래 */
        .stTabs,
        div[data-testid="stTabs"] {{
          width: 100% !important;
          display: flex !important;
          flex-direction: column !important;
          align-items: stretch !important;
        }}
        .stTabs > div,
        div[data-testid="stTabs"] > div {{
          display: flex !important;
          flex-direction: column !important;
          align-items: center !important;
          width: 100% !important;
          max-width: 100% !important;
        }}
        .stTabs > div:first-child {{
          gap: 0.75rem !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
          gap: 0.15rem !important;
          display: inline-flex !important;
          justify-content: center !important;
          align-items: center !important;
          width: fit-content !important;
          max-width: 100% !important;
          align-self: center !important;
          border-bottom: none !important;
          background: var(--panel-glass) !important;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 0.28rem !important;
          border-radius: 999px !important;
          border: 1px solid rgba(200, 210, 220, 0.14) !important;
          margin: 0 auto !important;
          box-shadow: 0 14px 36px rgba(0, 0, 0, 0.18) !important;
        }}
        .stTabs [data-baseweb="tab-list"] > * {{
          flex: 0 0 auto !important;
        }}
        .stTabs [data-baseweb="tab"] {{
          color: #8b969f !important;
          background: transparent !important;
          border: 1px solid transparent !important;
          border-radius: 999px !important;
          padding: 0.55rem 1.15rem !important;
          height: auto !important;
          min-height: 2.35rem !important;
          letter-spacing: 0.02em !important;
          font-weight: 500 !important;
          font-size: 0.92rem !important;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
          background: rgba(122, 155, 184, 0.12) !important;
          color: #d5dde6 !important;
          border-color: transparent !important;
        }}
        .stTabs [aria-selected="true"] {{
          color: #f0f4f8 !important;
          background: rgba(30, 36, 48, 0.7) !important;
          border: 1px solid var(--line) !important;
          border-bottom: 1px solid var(--line) !important;
          font-weight: 600 !important;
          box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {{
          display: none !important;
          height: 0 !important;
          background: transparent !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
          align-self: stretch !important;
          width: 100% !important;
          max-width: 100% !important;
          box-sizing: border-box !important;
          padding: 1.15rem 1.2rem 1rem !important;
          margin-top: 0 !important;
          border: 1px solid rgba(200, 210, 220, 0.14) !important;
          border-radius: 22px !important;
          background: var(--panel-glass) !important;
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          box-shadow: 0 14px 36px rgba(0, 0, 0, 0.22) !important;
        }}
        @media (max-width: 900px) {{
          .stTabs [data-baseweb="tab-panel"] {{
            padding: 0.55rem 0.85rem 0.75rem !important;
          }}
          .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
            div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark)
            + div[data-testid="stElementContainer"] {{
            margin-top: 0 !important;
            margin-bottom: 0.45rem !important;
          }}
        }}
        .stTabs [data-baseweb="tab-panel"] .stTextInput label,
        .stTabs [data-baseweb="tab-panel"] .stTextArea label,
        .stTabs [data-baseweb="tab-panel"] .stMultiSelect label,
        .stTabs [data-baseweb="tab-panel"] .stSelectbox label,
        .stTabs [data-baseweb="tab-panel"] .stCaption,
        .stTabs [data-baseweb="tab-panel"] label {{
          font-weight: 500 !important;
          text-transform: none !important;
          letter-spacing: 0.01em !important;
          color: #8e8e8e !important;
          font-size: 0.86rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"] div[data-baseweb="select"] > div,
        .stTabs [data-baseweb="tab-panel"] .stTextInput input,
        .stTabs [data-baseweb="tab-panel"] .stMultiSelect div[data-baseweb="select"] > div {{
          background: transparent !important;
          border-radius: 12px !important;
          border: 1px solid rgba(255, 255, 255, 0.1) !important;
          color: #f2f2f2 !important;
          box-shadow: none !important;
          font-size: 0.98rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stTextArea,
        .stTabs [data-baseweb="tab-panel"] .stTextArea > div,
        .stTabs [data-baseweb="tab-panel"] .stTextArea > div > div,
        .stTabs [data-baseweb="tab-panel"] .stTextArea [data-baseweb="base-input"],
        .stTabs [data-baseweb="tab-panel"] .stTextArea [data-baseweb="textarea"],
        .stTabs [data-baseweb="tab-panel"] .stTextArea textarea {{
          background: transparent !important;
          background-color: transparent !important;
          border: none !important;
          box-shadow: none !important;
          outline: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stTextArea textarea {{
          min-height: 5.5rem !important;
          padding: 0.35rem 0.15rem !important;
          color: #f2f2f2 !important;
          font-size: 0.98rem !important;
          resize: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stTextArea textarea:focus {{
          background: transparent !important;
          background-color: transparent !important;
          box-shadow: none !important;
          outline: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stButton > button {{
          font-weight: 600 !important;
          border-radius: 999px !important;
          background: #2f2f2f !important;
          border: 1px solid rgba(255, 255, 255, 0.14) !important;
          color: #f0f0f0 !important;
          box-shadow: none !important;
          letter-spacing: 0.02em !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stButton > button:hover {{
          background: #3a3a3a !important;
          border-color: rgba(255, 255, 255, 0.28) !important;
          transform: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"] .stButton > button[kind="primary"],
        .stTabs [data-baseweb="tab-panel"] .stButton > button[data-testid="baseButton-primary"],
        .stTabs [data-baseweb="tab-panel"] .stButton > button[data-testid="stBaseButton-primary"] {{
          background: #3a3a3a !important;
          background-image: none !important;
          border-color: rgba(255, 255, 255, 0.22) !important;
          color: #ffffff !important;
        }}
        /* 심문 composer: 채팅 입력(Enter 전송) — 마커는 flex gap을 먹지 않게 제외 */
        div[data-testid="stElementContainer"]:has(.ops-composer-mark) {{
          display: none !important;
          margin: 0 !important;
          padding: 0 !important;
          height: 0 !important;
          min-height: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          pointer-events: none !important;
        }}
        .ops-composer-meta {{
          display: flex;
          align-items: center;
          margin: 0 0 1.65rem !important;
        }}
        div[data-testid="stElementContainer"]:has(.ops-composer-meta) {{
          margin-bottom: 0.35rem !important;
        }}
        /* 심문 채팅 스레드 — 목록만 스크롤 (입력창과 분리) */
        div[data-testid="stElementContainer"]:has(.interrogation-chat-mark) {{
          display: none !important;
          margin: 0 !important;
          padding: 0 !important;
          height: 0 !important;
          min-height: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          pointer-events: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatMessage"] {{
          background: rgba(18, 24, 34, 0.55) !important;
          border: 1px solid rgba(200, 210, 220, 0.12) !important;
          border-radius: 12px !important;
          padding: 0.55rem 0.75rem !important;
          margin-bottom: 0.55rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatMessage"] img {{
          object-fit: cover !important;
          border-radius: 50% !important;
          border: 1px solid rgba(200, 210, 220, 0.22) !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          .stChatMessage {{
          max-width: 100% !important;
        }}
        /* height 컨테이너 = 대화 목록 전용 */
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stChatMessage"]) {{
          margin-bottom: 0.85rem !important;
          border: 1px solid rgba(200, 210, 220, 0.1) !important;
          border-radius: 12px !important;
          background: rgba(10, 14, 20, 0.35) !important;
        }}
        /* 입력창은 목록 스크롤과 분리 · 항상 노출 */
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] {{
          position: relative !important;
          z-index: 5 !important;
          margin-top: 0.35rem !important;
          margin-bottom: 0.25rem !important;
        }}
        /* 채팅 영역 ↔ AutoGen 내역 분리 */
        .ops-autogen-gap {{
          height: 1.35rem;
          margin: 0;
          padding: 0;
          border: none;
          pointer-events: none;
        }}
        div[data-testid="stElementContainer"]:has(.ops-autogen-gap) {{
          margin: 0.85rem 0 0.35rem !important;
          padding: 0 !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stExpander"] {{
          margin-top: 0.5rem !important;
          border-top: 1px solid rgba(200, 210, 220, 0.12) !important;
          padding-top: 0.85rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"],
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] > div {{
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] textarea,
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] [data-baseweb="base-input"],
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] [data-baseweb="textarea"] {{
          background: transparent !important;
          background-color: transparent !important;
          border: none !important;
          box-shadow: none !important;
          color: #f2f2f2 !important;
          font-size: 0.98rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button {{
          position: relative !important;
          border-radius: 50% !important;
          width: 2.5rem !important;
          min-width: 2.5rem !important;
          height: 2.5rem !important;
          min-height: 2.5rem !important;
          padding: 0 !important;
          background: linear-gradient(180deg, #4a657a, #354a5c) !important;
          background-image: linear-gradient(180deg, #4a657a, #354a5c) !important;
          border: 1px solid #6d879c !important;
          color: transparent !important;
          font-size: 0 !important;
          line-height: 0 !important;
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button svg,
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button span[data-testid="stIconMaterial"],
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button [data-testid="stIconMaterial"],
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button img {{
          display: none !important;
          visibility: hidden !important;
          opacity: 0 !important;
          width: 0 !important;
          height: 0 !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          [data-testid="stChatInput"] button::before {{
          content: "" !important;
          position: absolute !important;
          inset: 0 !important;
          display: block !important;
          margin: auto !important;
          width: 1.05rem !important;
          height: 1.05rem !important;
          background-color: #eef3f8 !important;
          -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'%3E%3Cpath d='M12 4v14' stroke='black' stroke-width='3.2' stroke-linecap='round'/%3E%3Cpath d='M6.5 10.5 12 4.5l5.5 6' stroke='black' stroke-width='3.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat !important;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'%3E%3Cpath d='M12 4v14' stroke='black' stroke-width='3.2' stroke-linecap='round'/%3E%3Cpath d='M6.5 10.5 12 4.5l5.5 6' stroke='black' stroke-width='3.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat !important;
        }}
        .ops-role-pill {{
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          padding: 0.42rem 0.85rem;
          border-radius: 999px;
          background: rgba(30, 36, 48, 0.7);
          border: 1px solid var(--line);
          color: #f0f0f0;
          font-size: 0.84rem;
          font-weight: 500;
          letter-spacing: 0.01em;
          white-space: nowrap;
          line-height: 1.2;
        }}
        .ops-role-pill::before {{
          content: "";
          width: 0.55rem;
          height: 0.55rem;
          border-radius: 999px;
          background: #c8c8c8;
          flex: 0 0 auto;
        }}
        .ops-suspect-select-label {{
          display: none;
        }}
        div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark) {{
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          pointer-events: none !important;
        }}
        /* 심문 대상 select — 필 형태 */
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark)
          + div[data-testid="stElementContainer"] {{
          width: fit-content !important;
          max-width: 12rem !important;
          margin: 0 0 0.85rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark)
          + div[data-testid="stElementContainer"] [data-baseweb="select"] > div {{
          background: rgba(30, 36, 48, 0.7) !important;
          border: 1px solid var(--line) !important;
          border-radius: 999px !important;
          min-height: 2.1rem !important;
          box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark)
          + div[data-testid="stElementContainer"] [data-baseweb="select"] {{
          min-width: 7.5rem !important;
        }}
        .stTabs [data-baseweb="tab-panel"]:has(.ops-composer-mark)
          div[data-testid="stElementContainer"]:has(.ops-suspect-select-mark)
          + div[data-testid="stElementContainer"]
          [data-baseweb="select"] span {{
          color: #f0f0f0 !important;
          font-size: 0.84rem !important;
          font-weight: 500 !important;
        }}
        /* 드롭다운 메뉴 (역할 설정 스타일) */
        div[data-baseweb="popover"] [role="listbox"] {{
          background: rgba(22, 26, 34, 0.98) !important;
          border: 1px solid rgba(200, 210, 220, 0.16) !important;
          border-radius: 10px !important;
          padding: 0.35rem !important;
        }}
        div[data-baseweb="popover"] [role="option"] {{
          border-radius: 8px !important;
          color: #e8eaef !important;
          font-size: 0.88rem !important;
        }}
        div[data-baseweb="popover"] [role="option"][aria-selected="true"] {{
          background: rgba(70, 90, 110, 0.45) !important;
        }}
        .ops-kicker {{
          margin: 0 0 0.55rem !important;
          font-size: 0.78rem !important;
          letter-spacing: 0.14em !important;
          text-transform: uppercase !important;
          color: var(--accent) !important;
          font-weight: 500 !important;
        }}
        /* Field Ops ↔ 탭 패널 */
        div[data-testid="stElementContainer"]:has(.ops-kicker) {{
          margin-bottom: 0.15rem !important;
        }}
        /* 대상 용의자 | Field Ops 한 줄 — 마커는 좌측 열 안쪽에 둠 */
        div[data-testid="stElementContainer"]:has(.suspect-ops-row-mark) {{
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: hidden !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark) {{
          display: flex !important;
          flex-direction: row !important;
          align-items: flex-start !important;
          justify-content: flex-start !important;
          gap: 2.75rem !important;
          column-gap: 2.75rem !important;
          width: 100% !important;
          max-width: 100% !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
          margin-bottom: 0 !important;
          padding: 0 !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
          > div[data-testid="column"]:first-child,
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
          > div[data-testid="stColumn"]:first-child {{
          flex: 0 0 360px !important;
          width: 360px !important;
          max-width: 360px !important;
          min-width: 320px !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
          > div[data-testid="column"]:last-child,
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
          > div[data-testid="stColumn"]:last-child {{
          flex: 1 1 auto !important;
          width: auto !important;
          max-width: none !important;
          min-width: 0 !important;
        }}
        /* 태블릿·아이패드(가로/세로 공통): 뷰포트 가로폭 기준 스택
           ※ orientation 조건은 DevTools 세로(1024×1366)에서 안 걸려 제외 */
        @media (max-width: 1200px) {{
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark) {{
            display: flex !important;
            flex-direction: column !important;
            flex-wrap: nowrap !important;
            align-items: stretch !important;
            gap: 1.35rem !important;
            row-gap: 1.35rem !important;
            column-gap: 0 !important;
          }}
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="column"],
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="stColumn"] {{
            flex: 0 0 auto !important;
            flex-basis: 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
          }}
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="column"]:first-child,
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="stColumn"]:first-child {{
            width: min(380px, 100%) !important;
            max-width: 420px !important;
            align-self: center !important;
          }}
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="column"]:last-child,
          div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark)
            > div[data-testid="stColumn"]:last-child {{
            width: 100% !important;
            max-width: 100% !important;
            align-self: stretch !important;
            margin-top: 20px !important;
          }}
        }}
        /* HOW TO / CASE FILE 마커 — 레이아웃에서 제거 */
        div[data-testid="stElementContainer"]:has(.howto-hud-mark),
        div[data-testid="stElementContainer"]:has(.case-hud-mark),
        div[data-testid="stElementContainer"]:has(.nav-hud-row-mark) {{
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        /* HOW TO · CASE FILE 한 줄 */
        div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark) {{
          display: flex !important;
          flex-direction: row !important;
          flex-wrap: nowrap !important;
          align-items: stretch !important;
          gap: 0.5rem !important;
          width: 100% !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark)
          > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark)
          > div[data-testid="stColumn"] {{
          flex: 1 1 0 !important;
          width: 50% !important;
          max-width: 50% !important;
          min-width: 0 !important;
        }}
        /* 데스크톱: 예전 [1,1,3]처럼 좌측 ~40%만 사용 — 메인은 사이드바로 이전, 사이드바는 전체 폭 */
        section[data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark),
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark) {{
          max-width: 100% !important;
          margin-right: 0 !important;
        }}
        @media (max-width: 900px) {{
          div[data-testid="stHorizontalBlock"]:has(.howto-hud-mark) {{
            max-width: 100% !important;
            flex-wrap: nowrap !important;
            flex-direction: row !important;
          }}
        }}
        /* 아이패드 에어 세로(~820) 등: HUD·안내 버튼 폰트 축소 + 세로 중앙
           (사이드바 수사 권한 행은 --side-auth-h 고정이므로 제외) */
        @media (max-width: 900px) {{
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button,
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button p {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 0.62rem !important;
            letter-spacing: 0.01em !important;
            min-height: 2.6rem !important;
            height: 2.6rem !important;
            padding: 0 0.4rem !important;
            line-height: 1.2 !important;
            text-align: center !important;
          }}
          [data-testid="stSidebar"]
            div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button,
          [data-testid="stSidebar"]
            div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button p,
          section[data-testid="stSidebar"]
            div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button,
          section[data-testid="stSidebar"]
            div[data-testid="stElementContainer"]:has(.hud-restart-mark)
            + div[data-testid="stElementContainer"]
            .stButton > button p {{
            font-size: 0.82rem !important;
            min-height: var(--side-auth-h, 2.35rem) !important;
            height: var(--side-auth-h, 2.35rem) !important;
            max-height: var(--side-auth-h, 2.35rem) !important;
            padding: 0 0.35rem !important;
            line-height: 1 !important;
          }}
          div[data-testid="column"]:has(.howto-hud-mark) .stButton > button,
          div[data-testid="stColumn"]:has(.howto-hud-mark) .stButton > button,
          div[data-testid="column"]:has(.case-hud-mark) .stButton > button,
          div[data-testid="stColumn"]:has(.case-hud-mark) .stButton > button {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 0.62rem !important;
            letter-spacing: 0.01em !important;
            line-height: 1.2 !important;
            white-space: normal !important;
            min-height: 2.6rem !important;
            height: auto !important;
            padding: 0.4rem 0.35rem !important;
            text-align: center !important;
          }}
          div[data-testid="column"]:has(.howto-hud-mark) .stButton > button p,
          div[data-testid="stColumn"]:has(.howto-hud-mark) .stButton > button p,
          div[data-testid="column"]:has(.case-hud-mark) .stButton > button p,
          div[data-testid="stColumn"]:has(.case-hud-mark) .stButton > button p {{
            display: block !important;
            margin: 0 !important;
            padding: 0 !important;
            font-size: 0.62rem !important;
            line-height: 1.25 !important;
            text-align: center !important;
            min-height: 0 !important;
            height: auto !important;
          }}
          .hud-stat {{
            min-height: 2.6rem;
            padding: 0.3rem 0.4rem;
          }}
          .hud-stat .stat-label {{
            font-size: 0.52rem;
          }}
          .hud-stat .stat-value {{
            font-size: 0.88rem;
          }}
        }}
        /* Ops 열 안 채팅/탭은 가로 전체 사용 */
        div[data-testid="stColumn"]:has(.ops-kicker),
        div[data-testid="column"]:has(.ops-kicker) {{
          min-width: 0 !important;
        }}
        div[data-testid="stColumn"]:has(.ops-kicker) .stTabs,
        div[data-testid="column"]:has(.ops-kicker) .stTabs,
        div[data-testid="stColumn"]:has(.ops-kicker)
          [data-testid="stChatInput"],
        div[data-testid="column"]:has(.ops-kicker)
          [data-testid="stChatInput"] {{
          width: 100% !important;
          max-width: 100% !important;
        }}
        div[data-testid="stColumn"]:has(.ops-kicker)
          [data-testid="stChatInput"] textarea,
        div[data-testid="column"]:has(.ops-kicker)
          [data-testid="stChatInput"] textarea {{
          white-space: pre-wrap !important;
          word-break: keep-all !important;
        }}
        .suspect-grid-hint {{
          margin: 0 0 0.45rem !important;
          font-size: 0.9rem !important;
          letter-spacing: 0.14em !important;
          text-transform: uppercase !important;
          color: var(--accent) !important;
          white-space: nowrap !important;
        }}

        /* 상태 배너(타이머·3진 아웃) — 동일 높이로 레이아웃 점프 방지 */
        .status-banner {{
          box-sizing: border-box;
          height: 40px;
          min-height: 40px;
          max-height: 40px;
          margin: 0 !important;
          padding: 0 0.85rem !important;
          display: flex !important;
          align-items: center !important;
          gap: 0.75rem;
          border-radius: 0.5rem;
          border: 1px solid rgba(122,155,184,0.35);
          background: rgba(12, 18, 26, 0.7);
          backdrop-filter: blur(8px);
          overflow: hidden;
        }}
        /* 타임아웃 안내 ↔ 대상 용의자/초상 사이 여백 */
        div[data-testid="stElementContainer"]:has(.status-banner) {{
          margin-top: 0.2rem !important;
          margin-bottom: 2.5rem !important;
        }}
        .status-banner--alert {{
          border-color: rgba(180,100,100,0.45);
          background: rgba(50,20,20,0.55);
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
          display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between;
          gap: 0.75rem; padding: 0.85rem 0 0.95rem;
          border: 0 !important;
          border-radius: 10px;
          background: transparent !important;
          backdrop-filter: none;
          -webkit-backdrop-filter: none;
          box-shadow: none;
          margin-top: 0 !important;
          margin-bottom: 0.85rem;
        }}
        /* 게임 HUD (컬럼) — 시작 화면 .hud 와 동일 패딩/정렬 */
        div[data-testid="stHorizontalBlock"]:has(.hud-brand) {{
          gap: 0.85rem !important;
          padding: 0.85rem 0 0.95rem !important;
          border: 0 !important;
          border-radius: 10px !important;
          background: transparent !important;
          backdrop-filter: none;
          -webkit-backdrop-filter: none;
          box-shadow: none;
          align-items: flex-start !important;
          margin-top: 0 !important;
        }}
        /* HUD만 올리면 아래 컨텐츠와 분리되므로 개별 리프트 금지 */
        [class*="st-key-game_hud_lift"] {{
          margin-top: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-stats-mark)
          > div[data-testid="stHorizontalBlock"],
        div[data-testid="column"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"],
        div[data-testid="stColumn"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"] {{
          align-items: stretch !important;
          gap: 0.5rem !important;
          display: flex !important;
          flex-direction: row !important;
          flex-wrap: nowrap !important;
          width: 100% !important;
        }}
        /* 사이드바: 수사 권한·새 수사 개시 전체 폭 */
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-stats-mark)
          > div[data-testid="stHorizontalBlock"],
        section[data-testid="stSidebar"]
          div[data-testid="column"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"],
        section[data-testid="stSidebar"]
          div[data-testid="stColumn"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"],
        [data-testid="stSidebar"]
          div[data-testid="stHorizontalBlock"]:has(.hud-stats-mark),
        [data-testid="stSidebar"]
          div[data-testid="column"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"],
        [data-testid="stSidebar"]
          div[data-testid="stColumn"]:has(.hud-stats-mark)
          div[data-testid="stHorizontalBlock"] {{
          max-width: 100% !important;
          margin-left: 0 !important;
          margin-right: 0 !important;
          width: 100% !important;
        }}
        .sidebar-hud-title,
        .sidebar-case-sub {{
          display: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.sidebar-hud-mark) {{
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        .hud-brand {{
          padding: 0 !important;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          align-items: flex-start;
          min-height: 0 !important;
        }}
        .hud-stat {{
          box-sizing: border-box;
          min-height: 3.5rem;
          height: 100%;
          padding: 0.45rem 0.7rem;
          border: 1px solid var(--line);
          background: rgba(20,24,32,0.72);
          border-radius: 6px;
          backdrop-filter: blur(6px);
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          text-align: center;
        }}
        .hud-stat .stat-label {{
          display: block;
          font-size: 0.65rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 0.15rem;
          text-align: center;
        }}
        .hud-stat .stat-value {{
          font-size: 1.1rem;
          color: #b7c6d4;
          font-weight: 600;
          line-height: 1.2;
          text-align: center;
        }}
        div[data-testid="column"]:has(.hud-restart-mark) {{
          display: flex !important;
          flex-direction: column !important;
          justify-content: flex-start !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-restart-mark) {{
          display: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"] {{
          height: auto !important;
          display: flex !important;
          align-items: flex-start !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"]
          .stButton {{
          width: 100% !important;
          margin: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button {{
          width: 100% !important;
          min-height: 2.7rem !important;
          height: auto !important;
          margin: 0 !important;
          white-space: nowrap !important;
          font-size: 0.92rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          box-sizing: border-box !important;
        }}
        [data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button,
        section[data-testid="stSidebar"]
          div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button {{
          min-height: var(--side-auth-h, 2.35rem) !important;
          height: var(--side-auth-h, 2.35rem) !important;
          max-height: var(--side-auth-h, 2.35rem) !important;
          font-size: 0.82rem !important;
        }}
        div[data-testid="stElementContainer"]:has(.hud-restart-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button p {{
          font-size: 0.92rem !important;
          font-weight: 500 !important;
          letter-spacing: 0.01em !important;
          margin: 0 !important;
        }}
        .brand-title {{
          font-size: clamp(1.35rem, 2.4vw, 1.85rem); line-height: 1.15;
          margin: 0 !important; padding: 0 !important;
          text-shadow: 0 2px 18px rgba(0,0,0,0.45) !important; display: block !important;
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
          border: 1px solid var(--line); background: rgba(20,24,32,0.72);
          border-radius: 6px;
          backdrop-filter: blur(6px);
        }}
        .stat-label {{
          display: block; font-size: 0.65rem; letter-spacing: 0.1em;
          text-transform: uppercase; color: var(--muted); margin-bottom: 0.15rem;
        }}
        .stat-value {{ font-size: 1.1rem; color: #b7c6d4; font-weight: 600; }}
        .hearts {{ letter-spacing: 0.1em; color: #8FA8C0; }}

        .panel-title {{
          font-family: var(--font-display); font-size: 1rem;
          margin: 0 0 0.5rem; color: #c8ced8;
        }}
        .inventory-session {{
          border: 1px solid rgba(200,210,220,0.14);
          border-radius: 10px;
          background: var(--panel-glass);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 1rem 1.05rem 1.15rem;
          margin-bottom: 0 !important;
          box-shadow: 0 14px 36px rgba(0,0,0,0.22);
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
          box-sizing: border-box !important;
          margin-left: auto !important;
          margin-right: 0 !important;
        }}
        .inventory-session .panel-title {{
          margin-bottom: 0.65rem;
        }}
        .pressure-block, .log-block {{
          border: 1px solid rgba(200,210,220,0.14);
          border-radius: 10px;
          background: var(--panel-glass);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 1rem 1.05rem 1.15rem;
          margin-bottom: 0 !important;
          box-shadow: 0 14px 36px rgba(0,0,0,0.22);
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
          box-sizing: border-box !important;
          margin-left: auto !important;
          margin-right: 0 !important;
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

        /* 마커 DOM은 선택자용 — 세로 간격에 끼지 않게 완전 제거 */
        .suspect-session-marker,
        .right-panel-marker {{
          display: none !important;
          height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-session-marker),
        div[data-testid="stElementContainer"]:has(.right-panel-marker) {{
          display: none !important;
          height: 0 !important;
          max-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          overflow: hidden !important;
          position: absolute !important;
          pointer-events: none !important;
        }}
        /*
          「대상 용의자」 라벨은 일반 흐름에 둠 (절대배치 시 초상 열 폭 붕괴 유발).
        */
        div[data-testid="column"]:has(.suspect-session-marker),
        div[data-testid="stColumn"]:has(.suspect-session-marker),
        div[data-testid="column"]:has(.right-panel-marker),
        div[data-testid="stColumn"]:has(.right-panel-marker) {{
          position: relative !important;
          padding-top: 0 !important;
          margin-top: 0 !important;
        }}
        div[data-testid="column"]:has(.suspect-session-marker) > div,
        div[data-testid="stColumn"]:has(.suspect-session-marker) > div,
        div[data-testid="column"]:has(.right-panel-marker) > div,
        div[data-testid="stColumn"]:has(.right-panel-marker) > div,
        div[data-testid="stVerticalBlock"]:has(.suspect-session-marker),
        div[data-testid="stVerticalBlock"]:has(.right-panel-marker) {{
          padding-top: 0 !important;
          margin-top: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-heading) {{
          position: static !important;
          height: auto !important;
          margin: 0 0 0.28rem !important;
          padding: 0 !important;
          z-index: auto;
          pointer-events: auto;
        }}
        .suspect-heading {{
          margin: 0 !important;
          padding: 0 !important;
        }}
        .suspect-heading .suspect-grid-hint {{
          margin: 0 !important;
          padding: 0 !important;
          white-space: nowrap !important;
        }}
        div[data-testid="stMarkdownContainer"]:has(.suspect-heading) {{
          margin-bottom: 0 !important;
          padding-bottom: 0 !important;
        }}
        .inventory-session {{
          border: 1px solid rgba(200,210,220,0.14);
          border-radius: 10px;
          background: var(--panel-glass);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          padding: 1rem 1.05rem 1.15rem;
          box-sizing: border-box !important;
          display: flex;
          flex-direction: column;
          margin-top: 0 !important;
          margin-bottom: 0 !important;
          box-shadow: 0 14px 36px rgba(0,0,0,0.22);
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
          margin-left: auto !important;
          margin-right: 0 !important;
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
          margin: 0 0 1.15rem; padding: 1rem 1.15rem;
          border: 1px solid rgba(122,155,184,0.4);
          background: rgba(18, 24, 34, 0.72);
          backdrop-filter: blur(8px);
          border-radius: 8px;
        }}
        .clue-banner.is-smoking {{
          border-color: rgba(212, 175, 105, 0.55);
          background: linear-gradient(
            135deg,
            rgba(28, 24, 18, 0.88),
            rgba(14, 18, 26, 0.82)
          );
          box-shadow: 0 0 0 1px rgba(212,175,105,0.12), 0 12px 32px rgba(0,0,0,0.35);
        }}
        .clue-kicker {{
          font-size: 0.68rem; letter-spacing: 0.14em; text-transform: uppercase;
          color: var(--accent); margin-bottom: 0.25rem;
        }}
        .clue-banner.is-smoking .clue-kicker {{
          color: #d4af69;
        }}
        .clue-title {{
          font-family: var(--font-display); font-size: 1.2rem;
          margin: 0 0 0.25rem; color: #d5d8de;
        }}
        .clue-snip {{ color: var(--muted); font-size: 0.85rem; margin: 0; }}
        .clue-route {{
          margin-top: 0.55rem;
          font-size: 0.78rem;
          color: rgba(212,175,105,0.9);
          letter-spacing: 0.04em;
        }}
        .golden-route {{
          margin: 0.55rem 0 0.35rem;
          padding: 0.45rem 0.75rem;
          border: 1px solid var(--line);
          border-radius: 6px;
          background: var(--panel-glass);
          backdrop-filter: blur(8px);
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          flex-wrap: nowrap;
          align-items: stretch;
          gap: 0.45rem;
        }}
        .golden-route .panel-title {{
          margin: 0;
          flex: 0 0 auto;
          font-size: 0.68rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--accent);
          white-space: nowrap;
        }}
        .golden-steps {{
          display: flex;
          flex-direction: column;
          flex: 1 1 auto;
          flex-wrap: nowrap;
          align-items: stretch;
          gap: 0.35rem;
          min-width: 0;
          width: 100%;
        }}
        .golden-step {{
          display: inline-flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.18rem 0.45rem 0.18rem 0.28rem;
          border-radius: 999px;
          border: 1px solid transparent;
          white-space: nowrap;
          line-height: 1.2;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
        }}
        .golden-step.is-done {{
          border-color: rgba(122,155,184,0.28);
          background: rgba(122,155,184,0.1);
        }}
        .golden-step.is-next {{
          border-color: rgba(212,175,105,0.5);
          background: rgba(212,175,105,0.1);
        }}
        .golden-step.is-locked {{
          opacity: 0.5;
        }}
        .golden-dot {{
          flex: 0 0 auto;
          width: 1rem;
          height: 1rem;
          border-radius: 999px;
          border: 1px solid rgba(200,210,220,0.35);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 0.6rem;
          line-height: 1;
          color: var(--muted);
        }}
        .golden-step.is-done .golden-dot {{
          border-color: rgba(122,155,184,0.7);
          background: rgba(122,155,184,0.25);
          color: #d5d8de;
        }}
        .golden-step.is-next .golden-dot {{
          border-color: #d4af69;
          color: #d4af69;
        }}
        .golden-step-body {{
          display: inline-flex;
          align-items: baseline;
          gap: 0.35rem;
          min-width: 0;
          max-width: 100%;
        }}
        .golden-step-body strong {{
          display: inline;
          flex: 0 0 auto;
          font-size: 0.76rem;
          color: #d5d8de;
          font-weight: 600;
        }}
        /* 설명글: 활성(is-next)만 한 줄 표시 */
        .golden-step-desc {{
          display: none;
          flex: 0 1 auto;
          min-width: 0;
          font-size: 0.7rem;
          font-weight: 500;
          color: rgba(212, 175, 105, 0.9);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          line-height: 1.2;
        }}
        .golden-step.is-next .golden-step-desc {{
          display: inline;
          white-space: normal;
          overflow: visible;
          text-overflow: unset;
        }}
        .golden-step.is-next {{
          max-width: 100%;
          white-space: normal;
          align-items: flex-start;
        }}
        .golden-step.is-next .golden-step-body {{
          flex-wrap: wrap;
        }}
        .golden-hint,
        .golden-route .golden-hint,
        div[data-testid="stMarkdownContainer"] .golden-hint {{
          display: block !important;
          margin: 0.25rem 0 0 !important;
          padding: 0 !important;
          border: 0 !important;
          flex: 0 1 auto;
          min-width: 0;
          font-size: 0.76rem !important;
          font-weight: 600 !important;
          color: rgba(212,175,105,0.92) !important;
          line-height: 1.25 !important;
          white-space: normal;
          overflow: visible;
          text-overflow: unset;
        }}
        .ending-banner {{
          margin: 0 0 1rem;
          padding: 1rem 1.15rem;
          border-radius: 8px;
          border: 1px solid rgba(122,155,184,0.35);
          background: rgba(14, 18, 26, 0.82);
        }}
        .ending-banner.is-win {{
          border-color: rgba(212,175,105,0.55);
          background: linear-gradient(
            135deg,
            rgba(32, 28, 18, 0.9),
            rgba(14, 18, 26, 0.85)
          );
        }}
        .ending-banner.is-lose {{
          border-color: rgba(180, 90, 90, 0.45);
        }}
        .app-footer-sig {{
          /* 음수 margin으로만 살짝 올림 (레이아웃 높이 유지) */
          margin: -0.35rem 0 0.35rem !important;
          padding: 0 !important;
          text-align: center !important;
          font-size: 0.72rem !important;
          letter-spacing: 0.06em !important;
          color: rgba(139, 145, 156, 0.38) !important;
          user-select: none;
          position: static;
          top: auto;
        }}
        div[data-testid="stElementContainer"]:has(.app-footer-sig),
        div[data-testid="stMarkdownContainer"]:has(.app-footer-sig) {{
          margin-bottom: 0 !important;
          padding-bottom: 0 !important;
        }}
        .ending-kicker {{
          font-size: 0.68rem;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--accent);
          margin-bottom: 0.3rem;
        }}
        .ending-banner.is-win .ending-kicker {{ color: #d4af69; }}
        .ending-title {{
          font-family: var(--font-display);
          font-size: 1.15rem;
          color: #d5d8de;
          margin: 0 0 0.35rem;
        }}
        .ending-body {{
          margin: 0;
          color: var(--muted);
          font-size: 0.88rem;
          line-height: 1.45;
        }}
        .suspect-grid-hint {{
          color: var(--accent);
          font-size: 0.9rem !important;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          margin: 0 0 0.45rem !important;
          padding-bottom: 0.1rem !important;
          display: block !important;
        }}
        .suspect-title-gap {{
          display: none !important;
          height: 0 !important;
          min-height: 0 !important;
          line-height: 0 !important;
        }}
        .suspect-block {{
          margin-bottom: 0.5rem !important;
          padding-bottom: 0 !important;
        }}
        .stTabs {{
          margin-top: 0 !important;
        }}
        /* 용의자 초상 ↔ 선택 버튼: 간격 재축소 */
        div[data-testid="column"]:has(.suspect-pick-frame) > div,
        div[data-testid="stColumn"]:has(.suspect-pick-frame) > div,
        div[data-testid="column"]:has(.suspect-pick-frame)
          [data-testid="stVerticalBlock"],
        div[data-testid="stColumn"]:has(.suspect-pick-frame)
          [data-testid="stVerticalBlock"] {{
          gap: 0.15rem !important;
          row-gap: 0.15rem !important;
        }}
        /* 좌측: 용의자 그리드 ↔ Field Ops */
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="column"]:first-child > div,
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="stColumn"]:first-child > div,
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="column"]:first-child
          > div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"]:has(.suspect-session-marker)
          > div[data-testid="stColumn"]:first-child
          > div[data-testid="stVerticalBlock"] {{
          gap: 1.35rem !important;
          row-gap: 1.35rem !important;
        }}
        /* 우측 패널 스택 — 상단 패딩 0, 초상과 동일 시작선 */
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="column"]:last-child > div,
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="stColumn"]:last-child > div,
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="column"]:last-child
          > div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"]:has(.right-panel-marker)
          > div[data-testid="stColumn"]:last-child
          > div[data-testid="stVerticalBlock"],
        div[data-testid="stVerticalBlock"]:has(.right-panel-marker) {{
          gap: 1.35rem !important;
          row-gap: 1.35rem !important;
          align-items: flex-end !important;
          width: 100% !important;
          padding-top: 0 !important;
          margin-top: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.inventory-session) {{
          margin-top: 0 !important;
          padding-top: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.inventory-session),
        div[data-testid="stElementContainer"]:has(.pressure-block),
        div[data-testid="stElementContainer"]:has(.log-block),
        div[data-testid="stElementContainer"]:has(.panel-stack-gap),
        div[data-testid="stMarkdownContainer"]:has(.inventory-session),
        div[data-testid="stMarkdownContainer"]:has(.pressure-block),
        div[data-testid="stMarkdownContainer"]:has(.log-block) {{
          display: flex !important;
          justify-content: flex-end !important;
          width: 100% !important;
          max-width: 100% !important;
        }}
        div[data-testid="stElementContainer"]:has(.inventory-session) > div,
        div[data-testid="stElementContainer"]:has(.pressure-block) > div,
        div[data-testid="stElementContainer"]:has(.log-block) > div,
        div[data-testid="stMarkdownContainer"]:has(.inventory-session),
        div[data-testid="stMarkdownContainer"]:has(.pressure-block),
        div[data-testid="stMarkdownContainer"]:has(.log-block) {{
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
        }}
        /* Golden Route: 사이드바 보조 HUD 안 세로 스택 */
        div[data-testid="stElementContainer"]:has(.golden-route),
        div[data-testid="stMarkdownContainer"]:has(.golden-route) {{
          display: block !important;
          width: 100% !important;
          max-width: 100% !important;
          justify-content: unset !important;
          margin-bottom: 0.5rem !important;
          padding-bottom: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.golden-route) > div,
        div[data-testid="stMarkdownContainer"]:has(.golden-route) {{
          width: 100% !important;
          min-width: 0 !important;
          max-width: 100% !important;
        }}
        /* Golden Route ↔ 대상 용의자 / Field Ops */
        div[data-testid="stHorizontalBlock"]:has(.suspect-ops-row-mark) {{
          margin-top: 0 !important;
          position: relative !important;
          top: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.panel-stack-gap) {{
          min-height: 0 !important;
        }}
        .suspect-pick-frame {{
          position: relative;
          width: 100%;
          margin: 0 !important;
          padding: 0 !important;
        }}
        .suspect-pick-wrap {{
          line-height: 0;
          margin: 0 !important;
          position: relative;
          width: 100%;
          aspect-ratio: 1 / 1;
          overflow: hidden;
          background: #1a1e26;
        }}
        .suspect-pick-wrap img {{
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          margin: 0;
          padding: 0;
          transition: filter 0.35s ease, transform 0.35s ease;
        }}
        /* 압박·붕괴 단계 — 표정 초상 + 약한 톤 보정 */
        .suspect-pick-wrap.stress-1 img {{
          filter: saturate(0.94) contrast(1.03) brightness(0.98);
        }}
        .suspect-pick-wrap.stress-2 img {{
          filter: saturate(0.88) contrast(1.06) brightness(0.95) hue-rotate(-6deg);
        }}
        .suspect-pick-wrap.stress-3 img {{
          filter: saturate(0.72) contrast(1.1) brightness(0.9) hue-rotate(-10deg);
          transform: scale(1.02);
        }}
        .suspect-pick-wrap::after {{
          content: "";
          position: absolute;
          inset: 0;
          pointer-events: none;
          z-index: 2;
          box-shadow: inset 0 0 0 0 transparent;
          background: transparent;
          transition: background 0.35s ease, box-shadow 0.35s ease;
        }}
        .suspect-pick-wrap.stress-1::after {{
          background: linear-gradient(
            180deg,
            rgba(40, 55, 75, 0.12),
            rgba(20, 24, 32, 0.18)
          );
        }}
        .suspect-pick-wrap.stress-2::after {{
          background: linear-gradient(
            180deg,
            rgba(90, 35, 35, 0.18),
            rgba(20, 12, 16, 0.35)
          );
          box-shadow: inset 0 0 28px rgba(120, 40, 40, 0.25);
        }}
        .suspect-pick-wrap.stress-3::after {{
          background: linear-gradient(
            180deg,
            rgba(120, 25, 30, 0.28),
            rgba(10, 6, 10, 0.55)
          );
          box-shadow: inset 0 0 40px rgba(160, 30, 40, 0.4);
        }}
        .stress-chip {{
          position: absolute;
          left: 8px;
          top: 8px;
          z-index: 4;
          pointer-events: none;
          display: inline-flex;
          align-items: center;
          padding: 0.18rem 0.45rem;
          border-radius: 999px;
          font-size: 0.62rem;
          font-weight: 600;
          letter-spacing: 0.06em;
          line-height: 1.2;
          color: #e8eaef;
          background: rgba(8, 10, 14, 0.78);
          border: 1px solid rgba(200, 210, 220, 0.28);
          white-space: nowrap;
        }}
        .suspect-pick-wrap.stress-2 .stress-chip {{
          border-color: rgba(200, 120, 120, 0.45);
          color: #f0d0d0;
        }}
        .suspect-pick-wrap.stress-3 .stress-chip {{
          border-color: rgba(220, 90, 90, 0.65);
          background: rgba(60, 12, 16, 0.85);
          color: #ffd0d0;
        }}
        /* 초상 하단 — 압력 게이지 */
        .portrait-pressure {{
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 4;
          pointer-events: none;
          padding: 1.6rem 0.45rem 0.4rem;
          background: linear-gradient(
            180deg,
            transparent 0%,
            rgba(6, 8, 12, 0.72) 55%,
            rgba(6, 8, 12, 0.88) 100%
          );
        }}
        .portrait-pressure-meta {{
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 0.35rem;
          margin-bottom: 0.22rem;
          font-size: 0.58rem;
          font-weight: 600;
          letter-spacing: 0.08em;
          color: rgba(230, 234, 240, 0.92);
          line-height: 1;
          text-transform: uppercase;
        }}
        .portrait-pressure-meta span {{
          font-variant-numeric: tabular-nums;
          color: rgba(200, 210, 220, 0.88);
          letter-spacing: 0.04em;
        }}
        .portrait-pressure-track {{
          height: 4px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.12);
          overflow: hidden;
        }}
        .portrait-pressure-fill {{
          height: 100%;
          border-radius: 999px;
          background: linear-gradient(
            90deg,
            #5a7a9a 0%,
            #8aa4bc 55%,
            #c9a070 100%
          );
          transition: width 0.35s ease;
        }}
        .suspect-pick-wrap.stress-2 .portrait-pressure-fill {{
          background: linear-gradient(
            90deg,
            #8a5a5a 0%,
            #c08070 60%,
            #d4a060 100%
          );
        }}
        .suspect-pick-wrap.stress-3 .portrait-pressure-fill {{
          background: linear-gradient(
            90deg,
            #a03038 0%,
            #d06050 55%,
            #e09060 100%
          );
        }}
        .suspect-pick-gap {{
          display: block;
          height: 2px;
          min-height: 2px;
          line-height: 2px;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-pick-gap),
        div[data-testid="stMarkdownContainer"]:has(.suspect-pick-gap) {{
          margin: 0 !important;
          padding: 0 !important;
          min-height: 0 !important;
        }}
        /* 카드 열: 프로필 뱃지 absolute 기준 (정사각 이미지 = 100cqw) */
        div[data-testid="column"]:has(.suspect-pick-frame),
        div[data-testid="stColumn"]:has(.suspect-pick-frame) {{
          position: relative !important;
          container-type: inline-size;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-pick-frame),
        div[data-testid="stMarkdownContainer"]:has(.suspect-pick-frame) {{
          margin-bottom: 0 !important;
          padding-bottom: 0 !important;
        }}
        /*
          프로필 = HTML 필(시각) + 투명 hit(클릭).
          카드 스택(.suspect-card-root) 기준 absolute로 좌표·크기(72×25) 일치.
        */
        .suspect-card-root {{
          display: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-card-root),
        div[data-testid="stMarkdownContainer"]:has(.suspect-card-root) {{
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          overflow: hidden !important;
        }}
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        ),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          > div[data-testid="stVerticalBlock"] {{
          position: relative !important;
        }}
        .suspect-pick-wrap .profile-pill {{
          position: absolute;
          right: 8px;
          top: 12px;
          bottom: auto;
          z-index: 5;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          box-sizing: border-box;
          width: var(--profile-pill-w);
          min-width: var(--profile-pill-w);
          height: var(--profile-pill-h);
          min-height: var(--profile-pill-h);
          padding: 0 0.75rem;
          font-size: 0.72rem;
          font-weight: 600;
          letter-spacing: 0.02em;
          line-height: 1;
          border-radius: 999px;
          color: #ffffff;
          background: rgba(8, 10, 14, 0.92);
          border: 1px solid rgba(255, 255, 255, 0.92);
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
          pointer-events: none;
          white-space: nowrap;
        }}
        /* 앵커는 레이아웃에서 제거 */
        div[data-testid="stElementContainer"]:has(.profile-badge-mark),
        div[data-testid="stMarkdownContainer"]:has(.profile-badge-mark) {{
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          overflow: hidden !important;
        }}
        /* 투명 hit — 필과 동일 좌표·크기 */
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] {{
          position: absolute !important;
          top: 16px !important;
          right: 8px !important;
          left: auto !important;
          bottom: auto !important;
          width: var(--profile-pill-w) !important;
          min-width: var(--profile-pill-w) !important;
          max-width: var(--profile-pill-w) !important;
          height: var(--profile-pill-h) !important;
          min-height: var(--profile-pill-h) !important;
          max-height: var(--profile-pill-h) !important;
          margin: 0 !important;
          padding: 0 !important;
          z-index: 80 !important;
          background: transparent !important;
          overflow: hidden !important;
          pointer-events: auto !important;
        }}
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] > div,
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton,
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button[data-testid="baseButton-secondary"],
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button *,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] > div,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"]
          .stButton > button[data-testid="baseButton-secondary"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button * {{
          position: static !important;
          inset: auto !important;
          display: block !important;
          box-sizing: border-box !important;
          margin: 0 !important;
          width: 100% !important;
          min-width: 100% !important;
          max-width: 100% !important;
          height: 100% !important;
          min-height: 100% !important;
          max-height: 100% !important;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 999px !important;
          background: transparent !important;
          background-image: none !important;
          box-shadow: none !important;
          outline: none !important;
          color: transparent !important;
          font-size: 0 !important;
          line-height: 0 !important;
          opacity: 0 !important;
          cursor: pointer !important;
          pointer-events: auto !important;
        }}
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton,
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.suspect-card-root)
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
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
        /* 프로필 hit만 25px — :has(.suspect-card-root) 광역 선택자는
           메인 블록의 HOW TO/CASE FILE까지 눌러 버리므로 금지 */
        div[data-testid="stVerticalBlock"]:has(
          > div[data-testid="stElementContainer"] .suspect-card-root
        )
          > div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(
          > div[data-testid="stVerticalBlock"]
            > div[data-testid="stElementContainer"] .suspect-card-root
        )
          div[data-testid="stElementContainer"]:has(.profile-badge-mark)
          + div[data-testid="stElementContainer"] .stButton > button {{
          min-height: var(--profile-pill-h) !important;
          height: var(--profile-pill-h) !important;
          max-height: var(--profile-pill-h) !important;
          padding: 0 !important;
        }}
        /* 용의자 이름 — 표시 전용 div (클릭 없음) */
        .suspect-name-plate {{
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          min-height: 2.4rem;
          margin: 0;
          padding: 0.5rem 0.75rem;
          box-sizing: border-box;
          border-radius: 4px;
          font-size: 0.95rem;
          font-weight: 600;
          letter-spacing: 0.03em;
          line-height: 1.25;
          color: #c5ccd6;
          background: rgba(18, 24, 34, 0.78);
          border: 1px solid rgba(200, 210, 220, 0.22);
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05),
            0 8px 18px rgba(0, 0, 0, 0.25);
          pointer-events: none;
          user-select: none;
        }}
        .suspect-name-plate.is-selected {{
          color: #eef3f8;
          background: linear-gradient(180deg, #4a657a, #354a5c);
          border-color: #6d879c;
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08),
            0 8px 18px rgba(0, 0, 0, 0.25);
        }}
        div[data-testid="stElementContainer"]:has(.suspect-name-plate),
        div[data-testid="stMarkdownContainer"]:has(.suspect-name-plate) {{
          margin: 0 !important;
          padding: 0 !important;
        }}
        /* 단일 용의자 카드 중앙 정렬 */
        .suspect-pick-frame--solo {{
          width: min(100%, 280px);
          margin-left: auto;
          margin-right: auto;
        }}
        .suspect-name-plate--solo {{
          width: min(100%, 280px);
          margin-left: auto;
          margin-right: auto;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-pick-frame--solo),
        div[data-testid="stMarkdownContainer"]:has(.suspect-pick-frame--solo),
        div[data-testid="stElementContainer"]:has(.suspect-name-plate--solo),
        div[data-testid="stMarkdownContainer"]:has(.suspect-name-plate--solo) {{
          display: flex !important;
          justify-content: center !important;
        }}
        .suspect-focus-hint {{
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 2.2rem;
          margin: 0 0 0.55rem;
          font-size: 0.72rem;
          letter-spacing: 0.12em;
          color: rgba(180, 190, 200, 0.7);
          font-variant-numeric: tabular-nums;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-focus-hint),
        div[data-testid="stMarkdownContainer"]:has(.suspect-focus-hint) {{
          margin: 0 !important;
          padding: 0 !important;
        }}
        div[data-testid="stElementContainer"]:has(.suspect-nav-mark),
        div[data-testid="stMarkdownContainer"]:has(.suspect-nav-mark) {{
          height: 0 !important;
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: hidden !important;
        }}
        div[data-testid="column"]:has(.suspect-nav-mark) .stButton > button,
        div[data-testid="stColumn"]:has(.suspect-nav-mark) .stButton > button {{
          min-height: 2.2rem !important;
          height: 2.2rem !important;
          padding: 0 !important;
          font-size: 1.35rem !important;
          line-height: 1 !important;
          border-radius: 4px !important;
          background: rgba(18, 24, 34, 0.78) !important;
          border: 1px solid rgba(200, 210, 220, 0.22) !important;
          color: #c5ccd6 !important;
          box-shadow: none !important;
        }}

        .dossier-shell {{
          border: 1px solid rgba(200,210,220,0.16);
          border-radius: 8px;
          background: linear-gradient(160deg, #1c222c 0%, #171b22 100%);
          padding: 0.85rem 1rem 1rem;
          margin-bottom: 0.5rem;
        }}
        .dossier-kicker {{
          font-size: 0.68rem;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--accent);
          margin: 0 0 0.55rem !important;
        }}
        .dossier-grid {{
          display: grid;
          grid-template-columns: 120px 1fr;
          gap: 0.85rem;
          align-items: start;
        }}
        .dossier-portrait {{
          border: 1px solid rgba(200,210,220,0.18);
          border-radius: 6px;
          overflow: hidden;
          background: #141820;
          line-height: 0;
        }}
        .dossier-portrait img {{
          width: 100%;
          display: block;
        }}
        .dossier-name {{
          font-family: var(--font-display);
          font-size: 1.35rem;
          color: #d5d8de;
          margin: 0 0 0.35rem !important;
        }}
        .dossier-meta {{
          color: var(--muted);
          font-size: 0.8rem;
          margin: 0 0 0.65rem !important;
        }}
        .dossier-row {{
          display: grid;
          grid-template-columns: 6.2rem 1fr;
          gap: 0.55rem;
          align-items: start;
          font-size: 0.95rem;
          line-height: 1.55;
          padding: 0.42rem 0;
          border-bottom: 1px solid rgba(200,210,220,0.14);
        }}
        .dossier-label {{
          color: #9aa3b0 !important;
          font-weight: 500;
        }}
        .dossier-value {{
          color: #e8eaef !important;
          white-space: pre-wrap;
          font-weight: 500;
        }}
        [data-testid="stDialog"] .dossier-label {{ color: #9aa3b0 !important; }}
        [data-testid="stDialog"] .dossier-value {{ color: #e8eaef !important; }}
        /*
          Streamlit stDialog = Modal Root(오버레이).
          오버레이는 뷰포트 풀사이즈, 카드만 내용 높이.
        */
        div[data-testid="stDialog"] {{
          position: fixed !important;
          top: 0 !important;
          left: 0 !important;
          right: 0 !important;
          bottom: 0 !important;
          inset: 0 !important;
          width: 100vw !important;
          height: 100dvh !important;
          max-width: none !important;
          max-height: none !important;
          margin: 0 !important;
          padding: 1rem !important;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          overflow-y: auto !important;
          -webkit-overflow-scrolling: touch;
          z-index: 1000000 !important;
          background: rgba(5, 7, 10, 0.72) !important;
          box-sizing: border-box !important;
        }}
        div[data-testid="stDialog"] > div {{
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          padding: 0 !important;
          margin: 0 !important;
          width: 100% !important;
          max-width: none !important;
          min-height: 100% !important;
          height: 100% !important;
          box-sizing: border-box !important;
          background: transparent !important;
        }}
        div[data-testid="stDialog"] [data-testid="stVerticalBlock"] {{
          padding-bottom: 0.75rem !important;
        }}
        div[data-testid="stDialog"] [role="dialog"] {{
          position: relative !important;
          inset: auto !important;
          left: auto !important;
          right: auto !important;
          top: auto !important;
          bottom: auto !important;
          margin: 0 auto !important;
          transform: none !important;
          align-self: center !important;
          justify-self: center !important;
          width: min(42rem, calc(100vw - 2rem)) !important;
          max-width: min(42rem, calc(100vw - 2rem)) !important;
          height: auto !important;
          min-height: 0 !important;
          max-height: min(90dvh, calc(100dvh - 2rem)) !important;
          overflow-x: hidden !important;
          overflow-y: auto !important;
          -webkit-overflow-scrolling: touch;
          box-sizing: border-box !important;
          flex: 0 1 auto !important;
        }}
        /* 수사파일(전신 이미지)만 조금 더 넓게 */
        div[data-testid="stDialog"]:has(.dossier-fullbody) [role="dialog"] {{
          width: min(56rem, calc(100vw - 2rem)) !important;
          max-width: min(56rem, calc(100vw - 2rem)) !important;
        }}
        /* Streamlit 버전에 따라 dialog가 section/div로 감싸일 때 */
        div[data-testid="stDialog"] div:has(> [role="dialog"]),
        div[data-testid="stDialog"] section:has(> [role="dialog"]) {{
          display: flex !important;
          justify-content: center !important;
          align-items: center !important;
          width: 100% !important;
          height: 100% !important;
          min-height: 100% !important;
          margin: 0 !important;
          background: transparent !important;
        }}
        /* 진입 브리핑: X 닫기 숨김 — 스타트로만 진행 */
        div[data-testid="stDialog"]:has(.case-briefing-lock)
          button[aria-label="Close"],
        div[data-testid="stDialog"]:has(.case-briefing-lock)
          button[aria-label="close"],
        div[data-testid="stDialog"]:has(.case-briefing-lock)
          [data-testid="stBaseButton-headerNoPadding"],
        div[data-testid="stDialog"]:has(.case-briefing-lock)
          button[kind="headerNoPadding"] {{
          display: none !important;
          visibility: hidden !important;
          pointer-events: none !important;
        }}
        div[data-testid="stDialog"]:has(.case-briefing-lock) .stButton {{
          width: auto !important;
          max-width: 12rem !important;
          margin-left: auto !important;
          margin-right: auto !important;
          display: flex !important;
          justify-content: center !important;
        }}
        div[data-testid="stDialog"]:has(.case-briefing-lock)
          div[data-testid="stElementContainer"]:has(.stButton) {{
          display: flex !important;
          justify-content: center !important;
          width: 100% !important;
        }}
        div[data-testid="stDialog"]:has(.case-briefing-lock) .stButton > button {{
          width: auto !important;
          min-width: 8.5rem !important;
          padding-left: 1.6rem !important;
          padding-right: 1.6rem !important;
        }}
        .dossier-foot-pad {{
          display: block !important;
          height: 1.35rem !important;
          min-height: 1.35rem !important;
          line-height: 1.35rem !important;
        }}
        .dossier-fullbody {{
          border: 1px solid rgba(200,210,220,0.16);
          border-radius: 6px;
          overflow: hidden;
          background: #141820;
          line-height: 0;
          max-height: min(52vh, 28rem);
        }}
        .dossier-fullbody img {{
          width: 100%;
          max-height: min(52vh, 28rem);
          display: block;
          object-fit: contain;
          object-position: top center;
        }}
        @media (max-height: 900px) {{
          .dossier-fullbody,
          .dossier-fullbody img {{
            max-height: min(38vh, 18rem);
          }}
        }}
        .dossier-case-block {{ margin: 0.35rem 0 0.75rem; }}
        .dossier-case-block p {{
          margin: 0.2rem 0 !important;
          font-size: 0.9rem;
          line-height: 1.45;
          color: #d5d8de;
        }}
        .intro-shell {{
          border: 1px solid rgba(200,210,220,0.14);
          border-radius: 12px;
          background:
            radial-gradient(120% 80% at 50% 0%, rgba(90,120,150,0.18), transparent 55%),
            linear-gradient(180deg, #1a2029 0%, #12161d 100%);
          padding: 0;
          margin: 0.15rem 0 0.85rem;
          overflow: hidden;
          min-height: min(62vh, 520px);
          display: flex;
          flex-direction: column;
          cursor: pointer;
          user-select: none;
          animation: intro-fade 0.45s ease-out;
        }}
        @keyframes intro-fade {{
          from {{ opacity: 0; transform: translateY(10px); }}
          to {{ opacity: 1; transform: translateY(0); }}
        }}
        .intro-visual {{
          width: 100%;
          aspect-ratio: 16 / 9;
          max-height: min(38vh, 320px);
          overflow: hidden;
          background: #0d1016;
          border-bottom: 1px solid rgba(200,210,220,0.1);
        }}
        .intro-visual img {{
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          filter: saturate(0.92) contrast(1.05);
        }}
        .intro-visual.is-trio {{
          aspect-ratio: 21 / 9;
          max-height: min(34vh, 280px);
        }}
        .intro-visual.is-trio img {{
          object-fit: contain;
          background: linear-gradient(180deg, #161b24 0%, #10141b 100%);
          padding: 0.55rem 0.75rem;
        }}
        .intro-panel {{
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 1.45rem 1.6rem 1.25rem;
          min-height: 0;
        }}
        .intro-shell:has(.intro-visual) .intro-panel {{
          min-height: auto;
        }}
        .intro-shell:has(.intro-visual) {{
          min-height: auto;
        }}
        .intro-kicker {{
          font-size: 0.72rem;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: var(--accent);
          margin: 0 0 0.85rem !important;
        }}
        .intro-caption {{
          font-family: var(--font-display);
          font-size: 1.05rem;
          letter-spacing: 0.04em;
          color: #9eb0c2;
          margin: 0 0 1.1rem !important;
        }}
        .intro-body {{
          color: #e8eaef;
          font-size: 1.28rem;
          line-height: 1.75;
          margin: 0 !important;
          white-space: pre-wrap;
          font-weight: 500;
        }}
        .intro-foot {{
          padding: 0.85rem 1.35rem 1.1rem;
          border-top: 1px solid rgba(200,210,220,0.1);
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }}
        .intro-progress {{
          display: flex;
          gap: 0.35rem;
          align-items: center;
        }}
        .intro-dot {{
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: rgba(200,210,220,0.25);
        }}
        .intro-dot.is-on {{
          background: var(--accent);
          box-shadow: 0 0 0 3px rgba(122,155,184,0.22);
        }}
        .intro-hint {{
          color: var(--muted);
          font-size: 0.82rem;
          margin: 0 !important;
          letter-spacing: 0.02em;
        }}
        /* 장면 탭 버튼 — 패널 바로 아래 full-bleed */
        div[data-testid="stVerticalBlock"]:has(.intro-shell) + div [data-testid="stBaseButton-primary"],
        div[data-testid="stVerticalBlock"]:has(.intro-shell) ~ div [data-testid="stBaseButton-primary"] {{
          min-height: 3rem;
        }}

        [data-testid="stProgress"] > div > div {{
          background-color: #5f7a90 !important;
        }}
        [data-testid="stProgress"] > div {{
          background-color: rgba(200,210,220,0.12) !important;
        }}

        .pressure-row {{
          margin: 0 0 0.75rem;
          padding: 0.8rem 0.9rem;
          background: rgba(30,36,48,0.7);
          border: 1px solid var(--line);
          border-radius: 6px;
        }}
        .pressure-row:last-child {{
          margin-bottom: 0.2rem;
        }}
        .pressure-block {{
          margin-top: 0 !important;
          margin-bottom: 0 !important;
          margin-left: auto !important;
          margin-right: 0 !important;
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
          box-sizing: border-box !important;
          padding: 1rem 1.05rem 1.2rem !important;
        }}
        .pressure-block .panel-title {{
          margin: 0 0 0.65rem !important;
          display: block !important;
        }}
        .pressure-block .pressure-row:first-of-type {{
          margin-top: 0;
        }}
        .pressure-block .pressure-row:last-child {{
          margin-bottom: 0.2rem;
        }}
        .log-block {{
          margin-top: 0 !important;
          margin-bottom: 0 !important;
          margin-left: auto !important;
          margin-right: 0 !important;
          width: var(--ops-rail-width) !important;
          min-width: var(--ops-rail-width) !important;
          max-width: var(--ops-rail-width) !important;
          box-sizing: border-box !important;
          padding: 1rem 1.05rem 1.2rem !important;
        }}
        .log-block .panel-title {{
          margin: 0 0 0.65rem !important;
          padding: 0 !important;
          display: block !important;
        }}
        .log-row {{
          margin: 0 0 0.7rem;
          padding: 0.8rem 0.9rem;
          background: rgba(30,36,48,0.7);
          border: 1px solid var(--line);
          border-radius: 6px;
        }}
        .log-row:last-child {{
          margin-bottom: 0.2rem;
        }}
        .log-row.is-alert {{
          border-color: rgba(180,100,100,0.35);
          background: rgba(50,24,28,0.55);
        }}
        .log-row.is-assist {{
          border-color: rgba(122,155,184,0.28);
        }}
        .log-row-meta {{
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 0.5rem;
          margin-bottom: 0.35rem;
          font-size: 0.78rem;
          color: var(--muted);
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }}
        .log-row-body {{
          margin: 0;
          font-size: 0.9rem;
          line-height: 1.45;
          color: var(--ink);
          white-space: pre-wrap;
          word-break: break-word;
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


def _fetch_case_overview(session_id: str) -> dict | None:
    try:
        resp = requests.get(f"{_api()}/api/v1/session/{session_id}/case", timeout=10)
    except requests.RequestException as exc:
        st.error(f"사건개요 요청 실패: {exc}")
        return None
    if resp.status_code != 200:
        st.error(resp.text)
        return None
    data = resp.json()
    return data if isinstance(data, dict) else None


def _resolve_intro_image(image_key: str) -> Path | None:
    """intro_scenes.image — assets 상대경로 또는 파일명."""
    key = str(image_key or "").strip().lstrip("/")
    if not key:
        return None
    candidates = [
        ROOT / "assets" / key,
        ROOT / "assets" / "intro" / key,
        ROOT / key,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _intro_scenes_from_case(case: dict, game: dict) -> list[dict[str, str]]:
    """API intro_scenes 우선. 없으면 overview 필드로 한 장면씩 폴백."""
    raw = case.get("intro_scenes") or []
    scenes: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            body = str(item.get("text") or "").strip()
            if not body:
                continue
            scenes.append(
                {
                    "caption": str(item.get("caption") or "").strip(),
                    "text": body,
                    "image": str(item.get("image") or "").strip(),
                }
            )
    if scenes:
        return scenes
    # 폴백: 필드 단위 장면
    fallback = [
        ("사건", case.get("incident")),
        ("시각", case.get("discovered_at")),
        ("장소", case.get("location")),
        ("역할", case.get("player_role")),
        ("목표", case.get("objective")),
        ("브리핑", case.get("synopsis") or case.get("notes")),
    ]
    for caption, val in fallback:
        body = str(val or "").strip()
        if body:
            scenes.append({"caption": caption, "text": body, "image": ""})
    if not scenes:
        scenes.append(
            {
                "caption": str(case.get("case_id") or game.get("case_id") or "case"),
                "text": str(case.get("title") or game.get("title") or "수사를 시작합니다."),
                "image": "",
            }
        )
    return scenes


def _render_case_intro(game: dict) -> None:
    """웹툰형 인트로 — 한 장면씩 표시, 탭하면 다음 장면."""
    sid = str(game.get("session_id") or "")
    case = _fetch_case_overview(sid) or {}
    scenes = _intro_scenes_from_case(case, game)
    total = len(scenes)
    idx = int(st.session_state.get("intro_scene_idx") or 0)
    idx = max(0, min(idx, total - 1))
    st.session_state["intro_scene_idx"] = idx
    scene = scenes[idx]
    caption = str(scene.get("caption") or "")
    body = str(scene.get("text") or "")
    image_key = str(scene.get("image") or "")
    case_no = str(case.get("case_id") or game.get("case_id") or "case_01")
    is_last = idx >= total - 1

    dots = "".join(
        f'<span class="intro-dot{" is-on" if i == idx else ""}"></span>'
        for i in range(total)
    )
    caption_html = (
        f'<p class="intro-caption">{html.escape(caption)}</p>' if caption else ""
    )
    visual_html = ""
    img_path = _resolve_intro_image(image_key)
    if img_path is not None:
        data_uri = _file_data_uri(str(img_path))
        trio_cls = " is-trio" if "trio" in img_path.stem.lower() else ""
        visual_html = (
            f'<div class="intro-visual{trio_cls}">'
            f'<img src="{data_uri}" alt="{html.escape(caption or "장면")}" />'
            f"</div>"
        )
    hint = "탭하여 수사 시작" if is_last else "탭하여 다음 장면"
    # key에 idx를 넣어 장면마다 fade 애니메이션이 다시 걸리게 함
    st.markdown(
        f'<div class="intro-shell" key="scene-{idx}">'
        f"{visual_html}"
        f'<div class="intro-panel">'
        f'<p class="intro-kicker">CASE · {html.escape(case_no)} · SCENE {idx + 1}/{total}</p>'
        f"{caption_html}"
        f'<p class="intro-body">{html.escape(body)}</p>'
        f"</div>"
        f'<div class="intro-foot">'
        f'<div class="intro-progress">{dots}</div>'
        f'<p class="intro-hint">{html.escape(hint)}</p>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    btn_label = "수사 시작" if is_last else "다음 장면"
    if st.button(btn_label, type="primary", use_container_width=True, key=f"intro_tap_{idx}"):
        if is_last:
            st.session_state["show_intro"] = False
            st.session_state["intro_scene_idx"] = 0
            _reset_timer()
        else:
            st.session_state["intro_scene_idx"] = idx + 1
        st.rerun()


def _queue_clues(clues: list) -> None:
    if not clues:
        return
    pending = list(st.session_state.get("pending_clues") or [])
    pending.extend(clues)
    st.session_state["pending_clues"] = pending
    for c in clues:
        title = c.get("title") or c.get("evidence_id")
        st.session_state.setdefault("log", []).append(f"단서 획득 — {title}")


def _golden_step_meta(evidence_id: str) -> dict | None:
    for i, step in enumerate(GOLDEN_ROUTE_STEPS, start=1):
        if step["evidence_id"] == evidence_id:
            return {**step, "index": i, "total": len(GOLDEN_ROUTE_STEPS)}
    return None


def _render_clue_banner() -> None:
    pending = list(st.session_state.get("pending_clues") or [])
    if not pending:
        return
    c = pending[0]
    eid = str(c.get("evidence_id") or "")
    title = html.escape(str(c.get("title") or _evidence_label(eid)))
    snip = html.escape(str(c.get("snippet") or CLUE_FLAVOR.get(eid, ""))[:140])
    flavor = html.escape(CLUE_FLAVOR.get(eid, "결정적 단서가 확보되었습니다."))
    meta = _golden_step_meta(eid)
    smoking = bool(c.get("smoking_gun")) or meta is not None
    kicker = "Evidence Secured"
    route_line = ""
    if meta:
        kicker = html.escape(str(meta["kicker"]))
        route_line = (
            f'<p class="clue-route">Golden Route {meta["index"]}/{meta["total"]} · '
            f'{html.escape(str(meta["beat"]))}</p>'
        )
    elif smoking:
        kicker = "Smoking Gun"
    banner_cls = "clue-banner is-smoking" if smoking else "clue-banner"
    st.markdown(
        f"""
        <div class="{banner_cls}">
          <div class="clue-kicker">{kicker}</div>
          <div class="clue-title">{title}</div>
          <p class="clue-snip">{flavor}</p>
          <p class="clue-snip" style="margin-top:0.3rem;">{snip}</p>
          {route_line}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("단서 확인 · 인벤토리에 보관", type="primary", key="dismiss_clue"):
        st.session_state["pending_clues"] = pending[1:]
        st.rerun()


def _render_golden_route(owned: list[str], *, ended: bool = False, won: bool = False) -> None:
    owned_set = set(owned)
    guns = [s["evidence_id"] for s in GOLDEN_ROUTE_STEPS]
    have_n = sum(1 for g in guns if g in owned_set)
    next_step = next((s for s in GOLDEN_ROUTE_STEPS if s["evidence_id"] not in owned_set), None)
    accuse_ready = have_n >= 2 and "ev_net_01" in owned_set
    accuse_done = bool(ended and won)

    if accuse_done:
        hint = "클리어 — 자백 엔딩"
    elif next_step is not None:
        hint = f"다음: 「{next_step['query']}」"
    elif accuse_ready:
        hint = f"최종 지목 · {GOLDEN_ROUTE_ACCUSE['short']}"
    else:
        hint = "결정적 증거 조합으로 진범 지목"

    rows = [
        '<div class="golden-route">',
        '<p class="panel-title">Golden Route</p>',
        '<div class="golden-steps">',
    ]
    for i, step in enumerate(GOLDEN_ROUTE_STEPS, start=1):
        eid = step["evidence_id"]
        done = eid in owned_set
        is_next = (not done) and next_step is not None and next_step["evidence_id"] == eid
        cls = "golden-step"
        if done:
            cls += " is-done"
        elif is_next:
            cls += " is-next"
        else:
            cls += " is-locked"
        mark = "✓" if done else str(i)
        title = html.escape(step["short"])
        tip = html.escape(step["beat"])
        desc = html.escape(step["beat"])
        rows.append(
            f'<div class="{cls}" title="{tip}">'
            f'<span class="golden-dot">{mark}</span>'
            f'<div class="golden-step-body">'
            f"<strong>{title}</strong>"
            f'<span class="golden-step-desc">{desc}</span>'
            f"</div></div>"
        )

    accuse_cls = "golden-step"
    if accuse_done:
        accuse_cls += " is-done"
        accuse_mark = "✓"
    elif accuse_ready:
        accuse_cls += " is-next"
        accuse_mark = "4"
    else:
        accuse_cls += " is-locked"
        accuse_mark = "4"
    accuse_tip = html.escape(GOLDEN_ROUTE_ACCUSE["beat"])
    accuse_desc = html.escape(GOLDEN_ROUTE_ACCUSE["beat"])
    rows.append(
        f'<div class="{accuse_cls}" title="{accuse_tip}">'
        f'<span class="golden-dot">{accuse_mark}</span>'
        f'<div class="golden-step-body">'
        f'<strong>{html.escape(GOLDEN_ROUTE_ACCUSE["short"])}</strong>'
        f'<span class="golden-step-desc">{accuse_desc}</span>'
        f"</div></div>"
    )
    rows.append("</div>")  # .golden-steps
    rows.append(f'<span class="golden-hint">{html.escape(hint)}</span></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_ending_banner() -> None:
    text = st.session_state.get("last_ending")
    if not text:
        return
    ok = bool(st.session_state.get("last_ending_ok"))
    cls = "ending-banner is-win" if ok else "ending-banner is-lose"
    kicker = "CASE CLOSED · GOLDEN ROUTE" if ok else "JUDGEMENT FAILED"
    title = "진실이 밝혀졌습니다" if ok else "지목이 빗나갔습니다"
    st.markdown(
        f"""
        <div class="{cls}">
          <div class="ending-kicker">{kicker}</div>
          <div class="ending-title">{html.escape(title)}</div>
          <p class="ending-body">{html.escape(str(text))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hud_brand(game: dict) -> None:
    """상단 고정 바: 햄버거 옆 「진실의 방」(본문 타이틀 제거)."""
    case_title = html.escape(str(game.get("title") or "진실의 방"))
    st.markdown(
        f"""
        <div class="app-topbar" data-case-title="{case_title}">
          <span class="app-topbar-burger" aria-hidden="true"></span>
          <span class="app-topbar-brand">진실의 방</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_hud(game: dict, *, sid: str) -> None:
    """보조 HUD — 뤼튼형 사이드 메뉴 레이아웃."""
    stamina = int(game.get("stamina") or 0)
    stamina_max = int(game.get("stamina_max") or 3)
    hearts = "♥" * stamina + "♡" * max(0, stamina_max - stamina)
    strikes = int(game.get("timeout_strikes") or 0)
    strike_max = int(game.get("timeout_strike_max") or 3)
    case_title = html.escape(str(game.get("title") or "진실의 방"))
    timer_on_hud = TIMER_FEATURE_ENABLED and bool(game.get("timer_enabled", False))
    timeout_html = ""
    if timer_on_hud:
        timeout_html = (
            f'<div class="side-status-row">'
            f'<span class="side-status-label">타임아웃</span>'
            f'<span class="side-status-value">{strikes}/{strike_max}</span>'
            f"</div>"
        )

    st.markdown('<div class="sidebar-hud-mark" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="side-nav-shell">
          <div class="side-nav-brand">
            <span class="side-nav-case">{case_title}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    auth_l, auth_r = st.columns([1.05, 1], gap="small")
    with auth_l:
        st.markdown('<div class="side-auth-row-mark" aria-hidden="true"></div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="side-status-card">
              <div class="side-status-row">
                <span class="side-status-label">수사 권한</span>
                <span class="side-status-hearts">{hearts}</span>
              </div>
              {timeout_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with auth_r:
        st.markdown('<div class="hud-restart-mark" aria-hidden="true"></div>', unsafe_allow_html=True)
        if st.button(
            "새 수사 개시",
            type="primary",
            key="btn_restart_hud",
            use_container_width=True,
        ):
            try:
                _start_new_investigation(with_tab_intro=False)
            except requests.RequestException as exc:
                st.error(f"세션 생성 실패: {exc}")

    st.markdown(
        '<p class="side-section-label">메뉴</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="howto-hud-mark" aria-hidden="true"></div>', unsafe_allow_html=True)
    if st.button("게임 방법", type="secondary", use_container_width=True, key="btn_howto_hud"):
        _request_howto()
    st.markdown('<div class="case-hud-mark" aria-hidden="true"></div>', unsafe_allow_html=True)
    if st.button("사건개요", type="secondary", use_container_width=True, key="btn_case_info_hud"):
        _request_case_info(sid, title_fallback=str(game.get("title") or "사건개요"))

    st.markdown(
        '<p class="side-section-label side-section-gap-before">골든 루트</p>',
        unsafe_allow_html=True,
    )
    _render_golden_route(
        list(game.get("evidence_ids") or []),
        ended=bool(game.get("ended")),
        won=bool(st.session_state.get("last_ending_ok")),
    )


def _render_hud(game: dict) -> None:
    """하위 호환 — 메인 브랜드만."""
    _render_hud_brand(game)


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


def _fetch_suspect_profile(suspect_id: str) -> tuple[dict | None, str | None]:
    """Returns (data, error_message)."""
    game = st.session_state.get("game") or {}
    session_id = game.get("session_id") or st.session_state.get("session_id")
    if not session_id:
        return None, "세션이 없습니다. 새 수사를 개시하세요."
    try:
        resp = requests.get(
            f"{_api()}/api/v1/session/{session_id}/suspects/{suspect_id}/profile",
            timeout=10,
        )
    except requests.RequestException as exc:
        return None, f"프로필 요청 실패: {exc}"
    if resp.status_code != 200:
        return None, f"프로필 API 오류 ({resp.status_code}): {resp.text[:240]}"
    data = resp.json()
    if not isinstance(data, dict):
        return None, "프로필 응답 형식이 올바르지 않습니다."
    return data, None


def _profile_field_rows(
    name: str,
    profile: dict,
    field_order: list[tuple[str, str]],
    *,
    include_name: bool = False,
    include_unknown: bool = False,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if include_name:
        rows.append(("이름", name))
    known = {k for k, _ in field_order}
    for key, label in field_order:
        val = profile.get(key)
        if val is None or str(val).strip() == "":
            continue
        rows.append((label, str(val)))
    if include_unknown:
        all_known = {k for k, _ in PROFILE_FIELD_ORDER}
        for key, val in profile.items():
            if key in all_known or key in known or val is None or str(val).strip() == "":
                continue
            rows.append((str(key), str(val)))
    return rows


def _dossier_rows_html(rows: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for label, val in rows:
        parts.append(
            '<div style="display:grid;grid-template-columns:6.2rem 1fr;'
            "gap:0.55rem;align-items:start;font-size:0.95rem;line-height:1.55;"
            'padding:0.45rem 0;border-bottom:1px solid rgba(200,210,220,0.16);">'
            f'<span style="color:#9aa3b0;font-weight:500;">{html.escape(label)}</span>'
            f'<span style="color:#e8eaef;font-weight:500;white-space:pre-wrap;">'
            f"{html.escape(val)}</span>"
            "</div>"
        )
    return "".join(parts)


@st.dialog("수사 파일", width="large", on_dismiss=_resume_timer)
def _open_dossier(suspect_id: str, data: dict) -> None:
    """용의자 프로필만 — 인적사항 / 심문 노트 (사건개요는 별도 다이얼로그)."""
    name = str(data.get("name") or suspect_id)
    mbti = str(data.get("mbti") or "")
    traits = data.get("traits") or []
    if not isinstance(traits, list):
        traits = []
    profile = data.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    case = data.get("case_overview") or {}
    if not isinstance(case, dict):
        case = {}

    case_no = str(case.get("case_id") or "case_01")
    trait_line = " · ".join(str(t) for t in traits) if traits else "—"

    identity_rows = _profile_field_rows(
        name, profile, PROFILE_IDENTITY_FIELDS, include_name=True, include_unknown=True
    )
    interrog_rows = _profile_field_rows(
        name, profile, PROFILE_INTERROGATION_FIELDS, include_name=False
    )

    st.markdown(
        f'<p style="margin:0 0 0.35rem;font-size:0.72rem;letter-spacing:0.14em;'
        f'color:#7A9BB8;text-transform:uppercase;">CHARACTER PROFILE · CASE {html.escape(case_no)}</p>',
        unsafe_allow_html=True,
    )
    col_img, col_info = st.columns([1, 1.35], gap="medium")
    with col_img:
        full = SUSPECT_FULLBODY.get(suspect_id)
        bust = SUSPECT_PORTRAITS.get(suspect_id)
        img_path = full if full and full.exists() else bust
        if img_path and img_path.exists():
            st.markdown('<div class="dossier-fullbody">', unsafe_allow_html=True)
            st.image(str(img_path), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info(name[:1])
    with col_info:
        st.markdown(f"### {name}")
        st.caption(f"MBTI {mbti or '—'} · {trait_line}")
        st.markdown(_dossier_rows_html(identity_rows), unsafe_allow_html=True)

    if interrog_rows:
        st.markdown(
            '<div style="margin:1.15rem 0 0.55rem;padding-top:0.85rem;'
            'border-top:1px solid rgba(200,210,220,0.18);">'
            '<p style="margin:0 0 0.45rem;font-size:0.72rem;letter-spacing:0.14em;'
            'color:#7A9BB8;text-transform:uppercase;">INTERROGATION NOTE</p>'
            '<p style="margin:0 0 0.55rem;font-size:0.9rem;color:#c5cbd4;">'
            "말투 · 당황 반응 · 예시 대사 · 주장 알리바이</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(_dossier_rows_html(interrog_rows), unsafe_allow_html=True)

    st.markdown(
        '<div class="dossier-foot-pad" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )


def _on_case_dialog_dismiss() -> None:
    """사건개요 닫힘 — 게임 시작 후에만 타이머 재개."""
    if st.session_state.get("game_started"):
        _resume_timer()


def _render_case_info_body(case: dict, *, title_fallback: str = "사건개요") -> None:
    case_no = str(case.get("case_id") or "case_01")
    st.markdown(
        f'<p style="margin:0 0 0.45rem;font-size:0.72rem;letter-spacing:0.14em;'
        f'color:#7A9BB8;text-transform:uppercase;">CASE INFO · {html.escape(case_no)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(f"### {case.get('title') or title_fallback}")
    blocks = [
        ("발견·발생 시각", case.get("discovered_at")),
        ("장소", case.get("location")),
        ("사건", case.get("incident")),
        ("역할", case.get("player_role")),
        ("목표", case.get("objective")),
        ("기타", case.get("notes") or case.get("synopsis")),
    ]
    case_rows: list[tuple[str, str]] = []
    for label, val in blocks:
        text = str(val or "").strip()
        if text:
            case_rows.append((label, text))
    if case_rows:
        st.markdown(_dossier_rows_html(case_rows), unsafe_allow_html=True)
    else:
        st.caption("공개된 사건 정보가 없습니다.")


@st.dialog("사건개요", width="large", on_dismiss=_on_case_dialog_dismiss)
def _open_case_info(case: dict, *, title_fallback: str = "사건개요") -> None:
    """메인 HUD CASE INFO."""
    _render_case_info_body(case, title_fallback=title_fallback)
    st.markdown(
        '<div class="dossier-foot-pad" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )


@st.dialog("사건개요", width="large", dismissible=False)
def _open_case_briefing(case: dict, *, title_fallback: str = "사건개요") -> None:
    """진입 브리핑 — 닫기(X) 없음, 스타트로만 진행."""
    st.markdown(
        '<div class="case-briefing-lock" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    _render_case_info_body(case, title_fallback=title_fallback)
    st.markdown(
        '<p style="margin:1rem 0 0.65rem;color:#9aa8b8;font-size:0.85rem;">'
        "브리핑을 확인한 뒤 START를 누르면 수사가 시작됩니다. "
        "조작법은 시작 후 「HOW TO · 게임 방법」에서 볼 수 있습니다.</p>",
        unsafe_allow_html=True,
    )
    if st.button("START", type="primary", use_container_width=False, key="btn_case_briefing_start"):
        st.session_state["game_started"] = True
        st.session_state["bgm_should_play"] = True
        st.session_state["timer_paused"] = False
        st.session_state.pop("timer_remaining", None)
        _reset_timer()
        st.rerun()


def _render_howto_body() -> None:
    st.markdown(
        '<p style="margin:0 0 0.45rem;font-size:0.72rem;letter-spacing:0.14em;'
        'color:#7A9BB8;text-transform:uppercase;">HOW TO · FIELD MANUAL</p>',
        unsafe_allow_html=True,
    )
    st.markdown("### 수사 진행 방법")
    st.markdown(
        "당신은 외부 디지털 포렌식 감사관입니다. "
        "**심문 → 증거 수색 → 조합 지목** 순으로 진범을 밝히세요."
    )
    steps = [
        (
            "01 용의자 선택",
            "초상 아래 ○ / ● 이름 버튼으로 심문 대상을 고릅니다. "
            "우측 하단 「프로필」은 프로필 조회용이며, 선택과는 별개입니다.",
        ),
        (
            "02 심문",
            "「심문」 탭에서 질문을 입력하고 Enter로 전송합니다. "
            "알리바이가 흔들리면 압박·붕괴 수치가 오릅니다.",
        ),
        (
            "03 증거 수색",
            "「증거 수색」 탭에서 쿼리를 입력하거나 Golden Route 추천 칩을 누른 뒤 수색 실행. "
            "새로 찾은 Smoking Gun은 단서 배너 → 인벤토리에 보관됩니다.",
        ),
        (
            "04 최종 지목",
            "「최종 지목」에서 용의자 1명 + 인벤토리 증거 정확히 2장을 조합해 지목합니다. "
            "오답이면 수사 권한(♥)이 감소합니다.",
        ),
        (
            "05 Golden Route",
            "우측 Golden Route 패널은 데모용 정석 루트 힌트입니다. "
            "법인카드 → 슬랙 → 네트워크 → 조합 지목 순을 따라가면 클리어에 가깝습니다.",
        ),
    ]
    rows = [(title, body) for title, body in steps]
    st.markdown(_dossier_rows_html(rows), unsafe_allow_html=True)
    st.caption("사건 배경은 「CASE FILE · 사건개요」에서 다시 볼 수 있습니다.")


@st.dialog("게임 방법", width="large", on_dismiss=_on_case_dialog_dismiss)
def _open_howto() -> None:
    _render_howto_body()
    st.markdown(
        '<div class="dossier-foot-pad" aria-hidden="true">&nbsp;</div>',
        unsafe_allow_html=True,
    )


def _request_howto() -> None:
    _pause_timer()
    _open_howto()


def _request_dossier(suspect_id: str) -> None:
    """프로필 선조회 후 dialog 오픈 (실패 시 빈 창 방지)."""
    data, err = _fetch_suspect_profile(suspect_id)
    if err or not data:
        st.session_state["dossier_error"] = err or "프로필을 불러오지 못했습니다."
        return
    st.session_state.pop("dossier_error", None)
    _pause_timer()
    _open_dossier(suspect_id, data)


def _request_case_info(
    session_id: str,
    *,
    title_fallback: str = "사건개요",
    show_start: bool = False,
) -> None:
    case = _fetch_case_overview(session_id)
    if not case:
        if show_start:
            case = {"title": title_fallback, "case_id": "case_01"}
        else:
            st.session_state["dossier_error"] = "사건개요를 불러오지 못했습니다."
            return
    st.session_state.pop("dossier_error", None)
    if show_start:
        _open_case_briefing(case, title_fallback=title_fallback)
        return
    _pause_timer()
    _open_case_info(case, title_fallback=title_fallback)


def _stress_stage(*, break_n: int, pressure: float, is_broken: bool) -> int:
    """초상·게이지 단계 0(평온)~3(붕괴). 압력·붕괴 카운트에 민감."""
    p = min(1.0, max(0.0, float(pressure or 0.0)))
    if is_broken or break_n >= 3 or p >= 0.75:
        return 3
    if break_n >= 2 or p >= 0.45:
        return 2
    # break 1회 또는 압력 15%부터 표정 전환
    if break_n >= 1 or p >= 0.15:
        return 1
    return 0


def _stress_chip_label(stage: int, *, break_n: int) -> str:
    if stage >= 3:
        return "MENTAL BREAK"
    if stage == 2:
        return f"CRACK {max(break_n, 1)}/3" if break_n else "CRACK"
    if stage == 1:
        return f"STRESS {break_n}/3" if break_n else "STRESS"
    return ""


def _pick_suspect(
    suspects: list[dict],
    broken: list[str],
    *,
    show_title: bool = True,
    pressure: dict | None = None,
    break_count: dict | None = None,
) -> str:
    if not suspects:
        return "suspect_a"

    pressure = pressure or {}
    break_count = break_count or {}

    ids = [str(s.get("id") or "") for s in suspects]
    if st.session_state.get("suspect_id") not in ids:
        st.session_state["suspect_id"] = ids[0]

    # 버튼 클릭 → 다음 런에서 dialog (같은 런에서 열면 놓치는 경우 방지)
    pending = st.session_state.pop("pending_dossier_id", None)
    if pending and str(pending) in ids:
        _request_dossier(str(pending))

    if show_title:
        st.markdown(
            '<p class="suspect-grid-hint">대상 용의자</p>'
            '<div class="suspect-title-gap" aria-hidden="true">&nbsp;</div>',
            unsafe_allow_html=True,
        )

    by_id = {str(s.get("id") or ""): s for s in suspects}
    sid = str(st.session_state["suspect_id"])
    s = by_id.get(sid) or suspects[0]
    name = str(s.get("name") or sid)
    is_broken = sid in broken
    break_n = int(break_count.get(sid, 0) or 0)
    press = float(pressure.get(sid, 0) or 0)
    stage = _stress_stage(break_n=break_n, pressure=press, is_broken=is_broken)
    portrait = _portrait_path(sid, stage)

    if stage >= 3:
        border = "2px solid rgba(180, 70, 80, 0.85)"
    elif stage == 2:
        border = "2px solid rgba(160, 90, 90, 0.55)"
    else:
        border = "1px solid rgba(200,210,220,0.14)"

    if portrait and portrait.exists():
        data_uri = _portrait_data_uri(portrait)
        img_html = f'<img alt="{html.escape(name)}" src="{data_uri}" />'
    else:
        img_html = (
            f"<div style='aspect-ratio:1;display:flex;align-items:center;"
            f"justify-content:center;background:#1a1f28;color:#9a9488;"
            f"font-size:1.2rem;line-height:1.2;'>{html.escape(name[:1])}</div>"
        )

    stress_cls = f" stress-{stage}" if stage > 0 else ""
    chip = _stress_chip_label(stage, break_n=break_n)
    chip_html = (
        f'<span class="stress-chip">{html.escape(chip)}</span>' if chip else ""
    )
    press_clamped = min(1.0, max(0.0, press))
    press_pct = int(round(press_clamped * 100))
    gauge_html = (
        f'<div class="portrait-pressure">'
        f'<div class="portrait-pressure-meta">'
        f"<span>PRESSURE</span><span>{press_pct}%</span>"
        f"</div>"
        f'<div class="portrait-pressure-track">'
        f'<div class="portrait-pressure-fill" style="width:{press_pct}%;"></div>'
        f"</div></div>"
    )

    # 단일 카드 — 초상+프로필 hit를 같은 relative 스택에 둠
    with st.container():
        st.markdown(
            '<div class="suspect-card-root" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="suspect-pick-frame">'
            f'<div class="suspect-pick-wrap{stress_cls}" style="border:{border};'
            f'border-radius:6px;">'
            f"{img_html}"
            f"{chip_html}"
            f"{gauge_html}"
            f'<span class="profile-pill">프로필</span>'
            f"</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="profile-badge-mark" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "프로필",
            key=f"suspect_profile_{sid}",
            type="secondary",
            help=f"{name} 프로필",
        ):
            st.session_state["pending_dossier_id"] = sid
            st.rerun()
        st.markdown(
            '<div class="suspect-pick-gap" aria-hidden="true">&nbsp;</div>',
            unsafe_allow_html=True,
        )
        suffix = " · 붕괴" if is_broken else ""
        st.markdown(
            f'<div class="suspect-name-plate">'
            f"{html.escape(name)}{html.escape(suffix)}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if sid in broken:
        st.error("선택 중인 용의자는 멘탈 붕괴 상태입니다.")
    return sid


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


# 본문 위젯보다 먼저 테마 적용 (기본 빨강 primary flash 방지)
_inject_theme()

# 스크롤 인트로 핸드오프: ?intro_done=1&session_id=...
if not st.session_state.get("game"):
    _handoff_sid = _qp.get("session_id")
    _intro_done = str(_qp.get("intro_done") or "") in ("1", "true", "yes")
    if isinstance(_handoff_sid, (list, tuple)):
        _handoff_sid = _handoff_sid[0] if _handoff_sid else None
    if _intro_done and _handoff_sid:
        try:
            _hr = requests.get(
                f"{_api()}/api/v1/session/{_handoff_sid}",
                timeout=10,
            )
            if _hr.status_code == 200:
                st.session_state["game"] = _hr.json()
                st.session_state["log"] = []
                st.session_state["interrogation_chat"] = []
                st.session_state.pop("last_agent_turn", None)
                st.session_state["hits"] = []
                st.session_state["pending_clues"] = []
                st.session_state["last_ending"] = None
                st.session_state["show_intro"] = False
                st.session_state["intro_scene_idx"] = 0
                st.session_state["game_started"] = False
                st.session_state.pop("bgm_should_play", None)
                st.session_state["turn_deadline"] = None
                # 쿼리 정리 (재실행 루프 방지)
                for _k in ("intro_done", "session_id", "embed"):
                    try:
                        if _k in st.query_params:
                            del st.query_params[_k]
                    except Exception:
                        pass
        except requests.RequestException:
            pass

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
    try:
        _start_new_investigation(with_tab_intro=False)
    except requests.RequestException as exc:
        st.error(f"세션 생성 실패: {exc}")
        st.stop()
    st.stop()  # _start_new_investigation가 rerun하지만, 실패 경로 외 안전망

sid = game["session_id"]
status = game.get("status") or "playing"
mental = status == "mental_break" or bool(game.get("mental_break_suspects"))
revoked = status == "authority_revoked" or (
    game.get("ended") and int(game.get("stamina") or 0) <= 0
)
stamina = int(game.get("stamina") or 0)

_inject_theme(mental=mental, revoked=revoked)

# 인트로/시작 화면 생략 — 사건개요 브리핑 후 스타트로 본편
st.session_state["show_intro"] = False
if "game_started" not in st.session_state:
    st.session_state["game_started"] = False

# 스타트 클릭 이후 BGM (인트로 셸 iframe은 부모에서 재생)
if st.session_state.get("game_started"):
    _force_bgm = bool(st.session_state.pop("bgm_should_play", False))
    _inject_game_bgm(muted=False, force_play=_force_bgm)

_render_hud_brand(game)
with st.sidebar:
    _render_sidebar_hud(game, sid=sid)
_render_clue_banner()

# 진입 시 사건개요 팝업 + 스타트 (닫아도 미시작이면 다시 염)
if (
    not st.session_state.get("game_started")
    and not game.get("ended")
    and not revoked
):
    _request_case_info(
        sid,
        title_fallback=str(game.get("title") or "사건개요"),
        show_start=True,
    )

if st.session_state.get("dossier_error"):
    st.error(st.session_state.pop("dossier_error"))

if revoked:
    st.error("감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다.")
elif mental:
    st.warning("알리바이 3-Out — 용의자 멘탈 마스크가 깨졌습니다.")

timer_on = (
    TIMER_FEATURE_ENABLED
    and bool(game.get("timer_enabled", False))
    and not game.get("ended")
    and game.get("status") not in ("turn_out", "authority_revoked")
    and not st.session_state.get("show_intro")
    and bool(st.session_state.get("game_started"))
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
        left_f = _timer_seconds_left()
        left = max(0, int(left_f))
        pct = (100.0 * left_f / total_sec) if total_sec else 0.0
        paused = bool(st.session_state.get("timer_paused"))
        label = (
            f"턴 일시정지  {left}s / {total_sec}s"
            if paused
            else f"턴 남은 시간  {left}s / {total_sec}s"
        )
        _render_status_banner(label, kind="timer", fill_pct=pct)
        if not paused and left_f <= 0:
            _handle_timeout(sid)
            st.rerun()

    _timer_slot()

if st.session_state.get("last_ending"):
    _render_ending_banner()

# 본문 한 줄: 왼쪽 용의자/탭, 오른쪽 인벤토리·압박·기록
# (제목·스페이서를 같은 행에 두어 인벤토리 상단 = 용의자 초상 상단)
suspects = game.get("suspects") or []
broken = list(game.get("mental_break_suspects") or [])
g = st.session_state["game"]
# 심문 탭 select → 초상 동기화 (위젯이 다른 탭에서 사라져도 suspect_id 유지)
_ask_sel = st.session_state.get("ask_suspect_select")
if _ask_sel and any(str(s.get("id")) == str(_ask_sel) for s in suspects):
    st.session_state["suspect_id"] = str(_ask_sel)

# 현장 로그 미리 수집 (우측 빈 레일이 본문을 찌르지 않게)
field_log: list[str] = []
for line in st.session_state.get("log") or []:
    text = str(line or "")
    if any(
        key in text
        for key in ("단서 획득", "타임아웃", "턴 패스", "헛수색", "수사 권한")
    ):
        field_log.append(text)

st.markdown(
    '<div class="suspect-session-marker" aria-hidden="true"></div>',
    unsafe_allow_html=True,
)
col_suspect, col_ops = st.columns([1.35, 2.2], gap="large")
with col_suspect:
    st.markdown(
        '<div class="suspect-ops-row-mark" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="suspect-heading">'
        '<p class="suspect-grid-hint">대상 용의자</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    suspect_id = _pick_suspect(
        suspects,
        broken,
        show_title=False,
        pressure=g.get("pressure") or {},
        break_count=g.get("break_count") or {},
    )

with col_ops:
    st.markdown(
        '<p class="ops-kicker">Field Ops · Command Deck</p>',
        unsafe_allow_html=True,
    )
    tab_ask, tab_search, tab_accuse = st.tabs(["심문", "증거 수색", "최종 지목"])

    with tab_ask:
        st.markdown(
            '<div class="ops-composer-mark" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        id_options = [str(s.get("id") or "") for s in suspects if s.get("id")]
        name_by_id = {
            str(s.get("id") or ""): str(s.get("name") or s.get("id") or "")
            for s in suspects
        }
        if id_options:
            if st.session_state.get("suspect_id") not in id_options:
                st.session_state["suspect_id"] = id_options[0]
            if st.session_state.get("ask_suspect_select") not in id_options:
                st.session_state["ask_suspect_select"] = st.session_state["suspect_id"]
            st.markdown(
                '<div class="ops-suspect-select-mark" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            chosen = st.selectbox(
                "심문 대상",
                options=id_options,
                format_func=lambda i: name_by_id.get(str(i), str(i)),
                key="ask_suspect_select",
                label_visibility="collapsed",
            )
            suspect_id = str(chosen)
            st.session_state["suspect_id"] = suspect_id
        _suspect_name = name_by_id.get(suspect_id, suspect_id)
        _render_interrogation_chat()
        # Streamlit 네이티브 채팅 입력 — Enter 전송·한글 IME를 프레임워크가 처리
        question = st.chat_input(
            "그날 밤 어디에 있었습니까?",
            key="ask_chat",
            disabled=bool(game.get("ended")),
        )
        if question and not game.get("ended"):
            if timer_on and not st.session_state.get("timer_paused") and _timer_seconds_left() <= 0:
                st.warning("시간 초과 — 턴이 패스됩니다.")
                _handle_timeout(sid)
            else:
                with st.spinner("에이전트 협의 중… (용의자 · 조수 · 심판)"):
                    resp = requests.post(
                        f"{_api()}/api/v1/session/{sid}/ask",
                        json={"suspect_id": suspect_id, "question": question},
                        timeout=90,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["game"] = data.get("state", game)
                    line = data.get("answer") or ""
                    if data.get("is_alibi_broken"):
                        line = f"알리바이 붕괴! (break {data.get('break_count')}/3) — {line}"
                    _append_chat("user", question, name="탐정")
                    state_now = data.get("state") or st.session_state.get("game") or {}
                    press_now = float(
                        (state_now.get("pressure") or {}).get(suspect_id, 0) or 0
                    )
                    break_now = int(
                        (state_now.get("break_count") or {}).get(suspect_id, 0) or 0
                    )
                    broken_now = suspect_id in (
                        state_now.get("mental_break_suspects") or []
                    )
                    stage_now = _stress_stage(
                        break_n=break_now,
                        pressure=press_now,
                        is_broken=broken_now,
                    )
                    _append_chat(
                        "suspect",
                        line,
                        name=_suspect_name,
                        suspect_id=str(suspect_id),
                        portrait_stage=stage_now,
                    )
                    note = (data.get("assistant_note") or "").strip()
                    if note:
                        _append_chat("assistant", note, name="조수")
                    transcript = data.get("agent_transcript") or []
                    if transcript:
                        st.session_state["last_agent_turn"] = {
                            "question": question,
                            "transcript": transcript,
                            "autogen": data.get("autogen") or {},
                            "gm_status": data.get("gm_status"),
                        }
                    _reset_timer()
                    st.rerun()
                else:
                    st.error(resp.text)

        last_ag = st.session_state.get("last_agent_turn")
        if last_ag and last_ag.get("transcript"):
            st.markdown(
                '<div class="ops-autogen-gap" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            meta = last_ag.get("autogen") or {}
            label = "멀티에이전트 대화 (AutoGen)"
            if meta.get("used"):
                label += f" · {meta.get('n_messages', '?')}msgs · {meta.get('elapsed_sec', '?')}s"
            elif meta.get("fallback"):
                label = "멀티에이전트 (폴백 — 스텁 응답)"
            with st.expander(label, expanded=False):
                st.caption(f"Q: {last_ag.get('question') or ''}")
                role_label = {
                    "Detective": "탐정",
                    "Suspect": "용의자",
                    "ForensicAssistant": "포렌식 조수",
                    "Judge": "심판",
                }
                for turn in last_ag["transcript"]:
                    role = str(turn.get("role") or "")
                    content = str(turn.get("content") or "")
                    if role == "Judge":
                        st.caption(
                            f"**심판** · status=`{last_ag.get('gm_status') or '—'}`"
                        )
                        continue
                    who = role_label.get(role, role or "agent")
                    st.markdown(f"**{who}** — {content}")

    with tab_search:
        owned_now = list(game.get("evidence_ids") or [])
        owned_set = set(owned_now)
        st.caption("Golden Route 추천 수색 — 카드 → 슬랙 → 네트워크")
        chip_cols = st.columns(len(GOLDEN_ROUTE_STEPS))
        for col, step in zip(chip_cols, GOLDEN_ROUTE_STEPS):
            eid = step["evidence_id"]
            done = eid in owned_set
            label = f"✓ {step['short']}" if done else step["short"]
            with col:
                if st.button(
                    label,
                    key=f"golden_q_{eid}",
                    disabled=done or bool(game.get("ended")),
                    use_container_width=True,
                    help=step["query"],
                ):
                    st.session_state["search_q"] = step["query"]
                    st.rerun()
        query = st.text_input(
            "수색 쿼리",
            placeholder="법인카드 룸살롱 / Wi-Fi 100GB",
            key="search_q",
            label_visibility="collapsed",
        )
        _sq_l, _sq_r = st.columns([5, 1.2])
        with _sq_r:
            search_go = st.button(
                "수색",
                type="primary",
                key="btn_search",
                use_container_width=True,
            )
        if search_go and query and not game.get("ended"):
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
        owned = list(game.get("evidence_ids") or [])
        owned_set = set(owned)
        guns_ready = (
            "ev_net_01" in owned_set
            and ("ev_card_03" in owned_set or "ev_msg_12" in owned_set)
        )
        if guns_ready and not game.get("ended"):
            st.info(
                f"Golden Route 준비됨 — {GOLDEN_ROUTE_ACCUSE['beat']}. "
                "대상 용의자를 선택한 뒤 증거 2장을 조합하세요."
            )
            target = next(
                (
                    s
                    for s in suspects
                    if str(s.get("name") or "") == GOLDEN_ROUTE_ACCUSE["suspect_name"]
                ),
                None,
            )
            if target and str(st.session_state.get("suspect_id") or "") != str(target.get("id")):
                if st.button(
                    f"데모 · {GOLDEN_ROUTE_ACCUSE['suspect_name']} 선택",
                    key="btn_golden_pick_suspect",
                ):
                    st.session_state["suspect_id"] = target["id"]
                    st.session_state["ask_suspect_select"] = target["id"]
                    st.rerun()
        else:
            st.caption("용의자 1명 + 결정적 증거 정확히 2장")
        ev_options = {_evidence_label(e): e for e in owned}
        selected_labels = st.multiselect(
            "인벤토리에서 증거 2장",
            options=list(ev_options.keys()),
            max_selections=2,
            key="accuse_ev",
        )
        ready = len(selected_labels) == 2 and not game.get("ended")
        if st.button("지목 확정", type="primary", disabled=not ready, key="btn_accuse"):
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

if field_log:
    entries = list(field_log[-8:])
    parts = ['<div class="log-block"><p class="panel-title">현장 로그</p>']
    for i, line in enumerate(entries, start=1):
        text = str(line or "")
        kind = "LOG"
        row_cls = "log-row"
        if "타임아웃" in text or "턴 패스" in text:
            kind = "TIMEOUT"
            row_cls += " is-alert"
        elif "단서 획득" in text:
            kind = "CLUE"
        elif "헛수색" in text or "수사 권한" in text:
            kind = "SEARCH"
            row_cls += " is-alert"
        parts.append(
            f'<div class="{row_cls}">'
            f'<div class="log-row-meta"><span>{kind}</span>'
            f"<span>#{i:02d}</span></div>"
            f'<p class="log-row-body">{html.escape(text)}</p>'
            f"</div>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

st.markdown(
    '<p class="app-footer-sig">© 2026 어쩌다 팀 · All rights reserved.</p>',
    unsafe_allow_html=True,
)
_sync_ops_rail_width()
