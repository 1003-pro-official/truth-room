# 팀 개발 · 연구 워크플로 (Workflow) — 진실의 방으로

> **Single Source of Truth:** GitHub (`*.py` + `configs/*.yaml` + `data/scenarios|personas`)  
> **관련:** [INTEGRATION.md](INTEGRATION.md) · [ROLES.md](ROLES.md) · [ANTIPATTERNS.md](ANTIPATTERNS.md) · [AI_CONVENTION.md](../AI_CONVENTION.md)

---

## 1. 전체 파이프라인

```
[Data]  ingest (scenarios · evidence)
         ↓
[RAG]   build_index → rag_pipeline (baseline | advanced)
         ↓
[Agent] agent_graph + lib/langgraph_runtime (공식 StateGraph) · ask=autogen_runtime
         ↓
[Eval]  evaluate · RAGAS (`scripts/eval_ragas.py`, n=30) · plot_metrics
         ↓
[Service] FastAPI (세션·search·tool·ask) → **React** (`web/game`) · Streamlit 백업
         ↓
[Docs]  README / PRT / 발표 / Notion
```

> **서빙 단일 경로:** UI ❌ LLM/Chroma 직접 · ✅ `POST /api/v1/session/...`  
> **본선 UI:** React. Streamlit→React **직접 원인** — 상태·다이얼로그 오류 반복. [README.md §5](../README.md).

---

## 2. Git 브랜치

| 브랜치 | 용도 |
| :--- | :--- |
| `main` | 제출·발표 안정본 |
| `feature/data-*` | Scenario · ingest |
| `feature/rag-*` | index · pipeline · eval |
| `feature/agent-*` | LangGraph · AutoGen |
| `feature/service-*` | API · UI |

**흐름:** `feature/*` → PR → 리뷰 → Smoke CI → `main`

---

## 3. 명령 치트시트

```bash
pip install -r requirements.txt -r requirements-llm.txt

python3 ingest.py
python3 build_index.py
python3 rag_pipeline.py --mode baseline
python3 rag_pipeline.py --mode advanced
python3 agent_graph.py --smoke
python3 scripts/smoke_autogen_ask.py
python3 evaluate.py
python3 scripts/eval_ragas.py          # Python ≥3.10 · n=30
python3 scripts/plot_metrics.py        # report/assets/

python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
python3 -m streamlit run app.py

python3 -m pytest tests/smoke -q
```

---

## 4. 원격 · Colab

`localhost` API는 Colab/타 머신에서 접근 불가 → ngrok 또는 동일 런타임에서 UI·API 함께 실행.

---

## 5. Handoff 체크

| From → To | 넘길 것 |
| :--- | :--- |
| Data → RAG | `chunks.jsonl` · evidence_id 목록 |
| RAG → Agent | retriever 인터페이스 · top_k 설정 |
| Agent → Service | State JSON · endpoint 계약 ([TECH_SPEC](../TECH_SPEC.md) §4) |
| Service → Docs | `/docs` 스크린 · 데모 GIF/영상 |
