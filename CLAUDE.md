# 🛠️ AI 에이전트 개발 행동 강령 — 진실의 방으로

> `CLAUDE.md` — 사람 규칙: [AI_CONVENTION.md](AI_CONVENTION.md)  
> **구현 착수 전:** [references.md](references.md)의 채택 OSS·비범위·논문 활용 방안을 확인한다.  
> 핵심 파이프라인(ingest→RAG→agent→API→eval)은 **이미 뼈대 구현됨**. references는 *무엇을 더 채울지*의 지도이다.

| 문서 | 역할 |
| :--- | :--- |
| `README.md` | 결과 분석 리포트 (메트릭·실험) |
| `GETTING_STARTED.md` | 설치·실행·온보딩 |
| `references.md` | 아이디어·논문·채택 OSS · **구현 범위 지도** |
| `docs/PEER_REVIEW.md` | AIFFEL PRT (에이전트 수정 금지) |
| `MASTER_PLAN.md` / `TECH_SPEC.md` | 제품·기술 원본 |
| `docs/ROLES.md` | 역할 경계 |
| `CLAUDE.md` (본 파일) | Phase 게이트 · 실행 규칙 |
| `PROJECT_SCHEDULE.md` | DLthon2 전략·마일스톤 (**변경 가능**) |

---

## 0. Phase 게이트 · Handoff

| Phase | 게이트 산출물 | 상태 |
| :--- | :--- | :---: |
| **0** | `.env`, `configs/*.yaml`, `docs/ROLES.md` 담당 | 🟡 |
| **1a** | `case_01`(100억의 야근자들), personas 3, raw 4소스, `runs/ingest/` | 🟢 |
| **1b** | `runs/rag/index/` · baseline/advanced `exp_*/` | 🟢 |
| **1c** | `agent_graph.py --smoke` (LangGraph) · AutoGen ask · `runs/agent/` | 🟢 |
| **1d** | `runs/eval/` · RAGAS n=30 · `report/assets/` | 🟢 |
| **2** | FastAPI session · `/tool` · `/ask` · `/docs` | 🟢 |
| **3** | Streamlit → API only · Golden Route UI 연출 | 🟡 |

**안티패턴 금지:** Only Me · UI에서 LLM 직결 · `culprit_id` 클라이언트 노출 · 무제한 AutoGen 티키타카 · YOLO/CV

### 스냅샷

- **프로젝트:** 방구석 프로파일러: 진실의 방으로
- **도메인:** Interactive Mystery · Advanced RAG · Multi-Agent(AutoGen 심문 + 역할 분리)
- **케이스:** `case_01` — 100억의 야근자들 (Omega)
- **범인(내부):** `suspect_b` 이대리 · win `[ev_card_03, ev_msg_12, ev_net_01]`
- **인덱스:** `runs/rag/index/`
- **RAG KPI:** Advanced Hit@5 **4/4** · soft routing C-Prec **0.40**
- **Eval:** `data/eval/eval_questions.jsonl` n=30 · RAGAS py3.12 Faith≈0.64 / Prec≈0.75 / Recall≈0.77
- **Agent:** LangGraph smoke · AutoGen ask 본선
- **레퍼런스 정본:** [references.md](references.md)
- **GitHub:** https://github.com/toryhyeon80/truth-room
- **Deploy:** https://web-production-072b8.up.railway.app

---

## 0.5 references.md → 구현 지침

기능 추가·고도화 시 **새 스택을 임의 도입하지 말고** 아래 매핑을 따른다.

| references 개념 | 구현 위치 (기존) | 에이전트 할 일 |
| :--- | :--- | :--- |
| 조력 AI ↔ 용의자 AI 분리 | `data/personas/` · `lib/autogen_runtime.py` · `agent_graph.py` | 페르소나·조수·심판 프롬프트 강화 (Generative Agents 참고) |
| Modular / Hybrid RAG | `lib/rag_core.py` · `rag_pipeline.py` | Routing·rerank·eval 개선 (RAG Survey 참고) |
| Stateful 압박 루프 | `lib/langgraph_runtime.py` · `agent_graph.py` · `backend/game_engine.py` · pressure · **break_count** | Cyclic 분기 · `langgraph.enabled` · [docs/GAME_RULES.md](docs/GAME_RULES.md) |
| AutoGen GroupChat 심문 | `lib/autogen_runtime.py` · `/ask` | `autogen.enabled` · max_round · timeout · 폴백 |
| Streamlit 심문 UI | `app.py` | `st.chat_message` · transcript · 타이머 · **FastAPI만** |
| Function Calling | `lib/tools.py` · `/tool` | CCTV·포렌식 페이로드 확장 |
| 리포트 자동화 | `update_report.py` · `update_notion.py` · `scripts/plot_metrics.py` | 실험 후 README/Notion/그래프 동기화 |

**비범위 (references·TECH_SPEC 공통):** 무제한 AutoGen 티키타카 · UI→LLM 직결 · YOLO/CV · `culprit_id` 클라이언트 노출

**프롬프트 템플릿:** `@CLAUDE.md @references.md @TECH_SPEC.md` — 상세는 [references.md §4](references.md)

---

## 1. 공통 규칙

1. 역할 경로 밖 대규모 수정 금지 — [docs/ROLES.md](docs/ROLES.md)
2. 설정은 `configs/*.yaml` only
3. 비밀값 `.env` only · 커밋 금지
4. `docs/PEER_REVIEW.md` 에이전트 미수정
5. 사용자 요청 없이 `git commit` / `push` 금지
6. API·config 변경 후 smoke 테스트
7. [AI_CONVENTION.md](AI_CONVENTION.md) 준수
8. **구현·고도화 전 [references.md](references.md) 채택 OSS·비범위 확인** — 표에 없는 스택 도입 금지(사용자 명시 요청 제외)

---

## 2. 명령어

```bash
pip install -r requirements.txt -r requirements-llm.txt
python3 ingest.py
python3 build_index.py
python3 rag_pipeline.py --mode baseline
python3 rag_pipeline.py --mode advanced
python3 agent_graph.py --smoke
python3 scripts/smoke_autogen_ask.py   # AutoGen 본선 ask (OPENAI_API_KEY)
python3 evaluate.py
python3 scripts/eval_ragas.py         # RAGAS · Python ≥3.10 · n=30
python3 scripts/plot_metrics.py       # report/assets/
python3 update_report.py          # runs/ → README.md
python3 update_notion.py          # .env NOTION_* 필수
python3 -m uvicorn backend.main:app --port 8000   # `/` 스크롤 인트로 · `/api` · `/assets`
python3 -m streamlit run app.py --server.port 8501
# Docker 원페이지: `/` 인트로 스크롤 → `/game` Streamlit
python3 -m pytest tests/smoke -q
```

**리포트 자동화:** `update_report.py`가 `report:auto:{ingest,rag,agent,eval}` 블록을 갱신.  
`update_notion.py`는 기본으로 `update_report.py` 후 Notion 페이지 전체 교체(+이미지 업로드).
