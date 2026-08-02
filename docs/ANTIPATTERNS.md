# 안티패턴 & 대응 (진실의 방으로)

> **관련:** [ROLES.md](ROLES.md) · [WORKFLOW.md](WORKFLOW.md) · [../AI_CONVENTION.md](../AI_CONVENTION.md)

---

## 하지 말 것 → 대신 할 것

| 안티패턴 | 대응 |
| :--- | :--- |
| **Only Me** — 혼자만 돌리고 PR 없음 | 역할별 `feature/*` → PR → 리뷰 |
| **UI → LLM 직결** | **React / Streamlit → FastAPI only** |
| **`culprit_id` 클라이언트 노출** | 세션 상태에 넣지 않음 · `accuse` 판정만 |
| **설정 하드코딩** | `configs/*.yaml` only |
| **`.env` 커밋** | `.gitignore` · 키는 각자 로컬 |
| **노트북에 로직 전부** | 정본은 `.py` · 노트북은 실행 래퍼만 |
| **로컬에서만 “완료”** | Smoke CI · `/docs` · 데모 리허설 |
| **증거/프롬프트 불일치** | `evidence_id` ↔ `win_condition` ↔ 페르소나 동기화 |
| **실서버 대화 로그를 룰 학습에 사용** | 로그는 **말투 FT 후보만** · 승패/알리바이는 코드 권위 ([CONVERSATION_LOG.md](CONVERSATION_LOG.md)) |
| **로컬에서 conversation_log 기본 ON** | 기본 OFF · 실서버만 `CONVERSATION_LOG=1` |
| **ask_turns.jsonl 커밋** | `runs/` gitignore · 원본 대화 비공개 |

---

## 서빙 단일 경로

```
React (web/game)  →  FastAPI (backend/)  →  RAG/Agent/Tools
     ↑ 본선
Streamlit (app.py) →  동일 API          →  (백업 경로)
```

UI에서 Chroma/인덱스/OpenAI를 직접 import 하지 않습니다.

**본선 UI:** React (`web/game`). Streamlit은 초기 프로토타입·백업.  
전환 이유: Streamlit 한계로 **개발 중 오류 반복** → React 본선 — [README.md §5](../README.md).

---

## PR 자가 점검

- [ ] 역할 경로 밖 대규모 수정 없음
- [ ] API only · culprit 비노출
- [ ] 재현 명령 PR 본문에 있음
