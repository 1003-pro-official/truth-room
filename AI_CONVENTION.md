# AI_CONVENTION — 진실의 방으로

> 에이전트·사람 공통 코딩 규칙. 충돌 시 **본 문서 > TECH_SPEC > references > 템플릿 docs**.  
> 스택·아이디어 범위의 정본 지도: [references.md](references.md)  
> 핵심 파이프라인은 이미 구현됨 — references를 보고 **범위 안에서** 채우고 고도화한다.

---

## 1. 문서 우선순위

1. `AI_CONVENTION.md` (본 파일)
2. `TECH_SPEC.md` (스키마·API·스택 선택)
3. `references.md` (채택 OSS · 논문 활용 · **비범위**)
4. `MASTER_PLAN.md`
5. `CLAUDE.md` (Phase 게이트 · 실행 명령 · references→경로 매핑)
6. `docs/*` (팀 OS · PRT)

구현 요청을 받으면: **CLAUDE.md §0.5 + references.md**로 대상 경로·비범위를 확정한 뒤 수정한다.

---

## 2. 역할 경계

| 역할 | 수정 가능 경로 |
| :--- | :--- |
| Data / Scenario | `data/`, `ingest.py`, `configs/ingest.yaml` |
| RAG / Eval | `build_index.py`, `rag_pipeline.py`, `evaluate.py`, `configs/rag.yaml`, `configs/eval.yaml`, `runs/rag/`, `runs/eval/` |
| Agent | `agent_graph.py`, `configs/agent.yaml`, `runs/agent/` · 페르소나 프롬프트 |
| Service | `backend/`, `app.py`, `configs/api.yaml` |
| Docs / PM | `README.md`, `PRESENTATION.md`, `references.md`, `update_report.py`, `update_notion.py` |

역할 밖 파일은 **해당 역할 PR/리뷰 없이** 대규모 수정 금지.

---

## 3. 구현 규칙

1. **설정 하드코딩 금지** — 모델명·top_k·온도는 `configs/*.yaml`
2. **비밀값** — `.env` only
3. **서빙 단일 경로** — UI → FastAPI only (LLM/인덱스 직접 로드 금지)
4. **정본은 `.py`** — 노트북은 실험 래퍼
5. **비범위** — AutoGen 필수화 · YOLO/CV · UI→LLM 직결 ([references.md](references.md) §1)
6. **범인 ID** — `culprit_id`를 클라이언트 응답에 넣지 말 것 (`accuse` 결과만)
7. **한국어 페르소나** — 시스템 프롬프트·UI 카피는 한국어 기본 (Generative Agents 참고 가능)
8. **최소 변경** — 요청과 무관한 리팩터·문서 양산 금지 · **기존 뼈대 재작성 금지**
9. **커밋/푸시** — 사용자 요청 없이 금지
10. **스모크** — API/`configs` 변경 후 `pytest tests/smoke` 또는 동등 명령
11. **인덱스 정본** — `runs/rag/index/`
12. **references 준수** — Modular RAG·역할 분리·Stateful 루프는 기존 모듈에 확장. 표에 없는 OSS는 도입 전 사용자 확인
13. **실험 후 리포트** — 메트릭 변경 시 `update_report.py` (Notion은 요청 시 `update_notion.py`)

---

## 4. 브랜치 · PR

- `feature/data-*` · `feature/rag-*` · `feature/agent-*` · `feature/service-*`
- PR 본문에 가설·재현 명령·스크린/메트릭 링크 · (해당 시) references ID(S1~S6) 언급
- `main` 직접 push 금지 (팀 합의 시)

---

## 5. 네이밍

- 파일: `snake_case.py`
- 증거 ID: `ev_{source}_{nn}` (예: `ev_msg_12`)
- 용의자 ID: `suspect_a|b|c`
- 실험 run: `runs/rag/exp_{slug}/`
