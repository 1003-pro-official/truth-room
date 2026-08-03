# React game UI — 진실의 방

본선 플레이 UI입니다. 초기 프로토타입은 Streamlit(`app.py`)이었고, **본선은 React**로 이전했습니다.

**전환 이유**

- **직접 원인:** Streamlit 위젯·세션 상태·`st.dialog`/리렌더 한계로 심문·모달·인벤 연동 시 **오류·상태 꼬임이 반복**되어 데모 안정화가 어려웠음
- 커스텀 레이아웃·모션·오디오(검거 연출·효과음 등) 제어가 Streamlit 모델과 맞지 않음
- 정적 `/game` + FastAPI로 UI→API only 경계를 구조적으로 고정
- `/` 인트로와 `/game/` 플레이 분리 배포에 적합

상세: [README.md §5](../../README.md) · [TECH_SPEC.md](../../TECH_SPEC.md)

## 로컬 개발

```bash
# 터미널 1 — API
uvicorn backend.main:app --port 8000

# 터미널 2 — React
cd web/game
npm install
npm run dev
```

브라우저: http://127.0.0.1:5173/game/  
(Vite가 `/api`·`/assets`를 :8000으로 프록시)

인트로에서 입장: uvicorn만 쓸 때 intro가 `http://127.0.0.1:5173/game`으로 연결.  
통합: http://127.0.0.1:8000/ (인트로) · http://127.0.0.1:8000/game/ (빌드 산출물)

## 프로덕션 빌드

```bash
cd web/game && npm ci && npm run build
# → web/game/dist (nginx `/game/` · FastAPI StaticFiles)
```

Streamlit `app.py`는 로컬 백업. nginx `/game-streamlit/` + `ENABLE_STREAMLIT_BACKUP=1`.

## 관측 (Langfuse)

사이드바 **「관측 (Langfuse)」** → 게임 전체를 덮는 **게시판 레이어** (팝업 아님).

- **Tracing** — 프로젝트 ask trace 표
- **Sessions** — 세션 FAQ 펼침 (Input/Output)
- PC 권장 · 모바일은 PC 확인 안내
- API: `/api/v1/session/{id}/observability` · 설정: [docs/LANGFUSE.md](../../docs/LANGFUSE.md)
