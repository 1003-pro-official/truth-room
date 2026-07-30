# TRAINING_CHECKLIST — RAG / Agent 실험 준비

> 진실의 방 파이프라인 체크리스트.

---

## 환경

- [ ] `.env`에 `OPENAI_API_KEY` (LLM 연동 시)
- [ ] `pip install -r requirements.txt -r requirements-llm.txt`
- [ ] `configs/*.yaml` 존재

## Data

- [ ] 시나리오·페르소나 리뷰 (`case_01` · 100억의 야근자들)
- [ ] `data/raw/` 4소스 (messenger·logs·corporate_card·network) · evidence_id
- [ ] `python3 ingest.py` · `python3 build_index.py` → `runs/rag/index/`

## RAG

- [ ] `python3 rag_pipeline.py --mode baseline`
- [ ] `python3 rag_pipeline.py --mode advanced`
- [ ] 결과를 `runs/rag/exp_*/` · README 표에 반영

## Agent

- [ ] `python3 agent_graph.py --smoke`
- [ ] 페르소나 자백 가드레일 (`ev_net_01` 전 부인) 확인

## Eval · Demo

- [ ] `python3 evaluate.py`
- [ ] API + Streamlit Golden Route 1회
- [ ] `culprit_id` 클라이언트 미노출
