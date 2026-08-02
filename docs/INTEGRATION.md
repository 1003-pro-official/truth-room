# 팀원 작업 → main 반영 (Integration)

> **한 줄:** 어디서 코딩하든 **GitHub PR merge**가 유일한 합류 지점입니다.  
> **관련:** [WORKFLOW.md](WORKFLOW.md) · [ENVIRONMENTS.md](ENVIRONMENTS.md) · [ROLES.md](ROLES.md)

---

## 1. 흐름

```
feature/data-*     (시나리오·raw)     ─┐
feature/rag-*      (ingest·index·eval) ─┼─ PR + 리뷰 + Smoke CI ─► main
feature/agent-*    (agent_graph·tools) ─┤
feature/service-*  (API·React UI · Streamlit 백업)     ─┘
```

| 역할 | 브랜치 예 | merge에 넣을 것 |
| :--- | :--- | :--- |
| Scenario / Prompt | `feature/data-*` | `data/scenarios/`, `data/personas/`, `data/raw/` |
| RAG / Tools | `feature/rag-*` | `lib/`, ingest/index/rag/eval, `runs/rag/exp_*/` 요약 |
| Agent | `feature/agent-*` | `agent_graph.py`, `lib/langgraph_runtime.py`, `lib/autogen_runtime.py`, `configs/agent.yaml`, `runs/agent/` |
| Service | `feature/service-*` | `backend/`, `app.py`, `configs/api.yaml` |

---

## 2. 공통 절차

```bash
git checkout main && git pull origin main
git checkout -b feature/<role>-<topic>

# 작업 후
git add <변경 파일만>    # .env 제외
git commit -m "feat(rag): …"
git push -u origin HEAD
# GitHub에서 PR → 리뷰 → merge
```

---

## 3. PR에 넣을 것 / 넣지 말 것

| ✅ 포함 | ❌ 제외 |
| :--- | :--- |
| `.py`, `configs/*.yaml`, `data/scenarios|personas|raw|tools` | `.env` |
| `runs/rag/exp_*/last_query.json`, `runs/eval/report.json` | `runs/rag/index/vectors.json` 대용량(팀 합의) |
| README 메트릭 표 | API 키 · 개인 노트북 전체 |

---

## 4. 리뷰 · CI

| 게이트 | 내용 |
| :--- | :--- |
| CODEOWNERS | 역할별 리뷰어 |
| Smoke CI | `.github/workflows/smoke.yml` |
| 로컬 | `python3 -m pytest tests/smoke -q` (API 기동 시) |

---

## 5. 자주 하는 실수

| 실수 | 해결 |
| :--- | :--- |
| Colab/로컬에만 코드 | `.py` 변경 → PR |
| `main` 직접 push | feature 브랜치 + PR |
| UI에서 LLM 직결 | FastAPI만 호출 |
| `culprit_id` UI 노출 | `accuse` 결과만 |
