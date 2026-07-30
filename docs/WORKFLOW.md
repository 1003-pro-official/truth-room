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
[Agent] agent_graph (LangGraph-style 상태머신 + tools)
         ↓
[Eval]  evaluate (Faithfulness · 루브릭)
         ↓
[Service] FastAPI (세션·search·tool) → Streamlit (API 호출)
         ↓
[Docs]  README / PRT / 발표
```

> **서빙 단일 경로:** Streamlit ❌ LLM/Chroma 직접 · ✅ `POST /api/v1/session/...`

---

## 2. Git 브랜치

| 브랜치 | 용도 |
| :--- | :--- |
| `main` | 제출·발표 안정본 |
| `feature/data-*` | Scenario · ingest |
| `feature/rag-*` | index · pipeline · eval |
| `feature/agent-*` | LangGraph |
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
python3 evaluate.py

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
