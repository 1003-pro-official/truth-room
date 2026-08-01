# PRESENTATION — 방구석 프로파일러: 진실의 방으로

> 슬라이드 초안. 발표일 기준 D-2까지 확정.

---

## 슬라이드 구성 (8~10장)

1. **타이틀** — 방구석 프로파일러: 진실의 방으로 · 「100억의 야근자들」
2. **문제** — 단순 RAG 챗봇의 한계 →「플레이 가능한 추론」필요
3. **솔루션** — 심문 × Advanced RAG × Function Calling × **AutoGen** × **LangGraph** 압박 루프
4. **아키텍처** — Data → Hybrid RAG → Agent(AutoGen ask + LangGraph StateGraph) → FastAPI → UI
5. **데이터** — 용의자 3 · 증거 소스 6종 · Smoking Gun 4 ID · win_condition
6. **실험** — Baseline vs Advanced Hit@5 **0/4→4/4** · RAGAS n=30 · LoRA ladder · AutoGen ask
7. **데모** — Golden Route 라이브 (https://web-production-072b8.up.railway.app) 또는 녹화 2~3분
8. **회고 · 한계 · Next** (Embedding 미채택 · 7B memory_limit)
9. **역할 분담 · Q&A**

---

## 데모 스크립트 (5분 · Golden Route)

1. `/` 인트로 브리핑 — Omega · 100억 · 야근 3인 (30초) → **입장하기**
2. 김팀장 심문 → 증거 책상에서 법인카드 확보 → 현장 제외 (1분)
3. 박신입 심문 → 슬랙 DM 확보 → 목격자화 (1분)
4. 이대리 대질 → Wi-Fi 100GB 확보 → 조합 지목 (1분 30초)
5. 지목 확정 → 결과 모달 · 검거 도장 (30초)
6. 기술 한 줄: Hybrid RAG + Function Calling + LangGraph + AutoGen (30초)

> 라이브: https://web-production-072b8.up.railway.app · `/game/` 새로고침 시 인트로로 돌아감.

---

## 멘트로 쓸 숫자 (측정 완료)

- **Hit@5 (고정 4쿼리):** Baseline **0/4** · Advanced **4/4** · Embedding **0/4**
- **Context Precision:** soft routing **0.22→0.40** (Hit@5 유지)
- **로컬 Faith / RAGAS Faith:** ≈0.27 / ≈**0.64** (n=30, Python 3.12)
- **RAGAS C-Prec / C-Recall:** ≈**0.75** / ≈**0.77** (n=30)
- **LoRA:** SmolLM→0.5B→1.5B→**3B** 완주 · **7B** 16GB `memory_limit`
- **그래프:** `report/assets/` · `python3 scripts/plot_metrics.py`
