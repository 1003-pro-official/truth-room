# PRESENTATION — 방구석 프로파일러: 진실의 방으로

> 슬라이드 초안. 발표일 기준 D-2까지 확정.

---

## 슬라이드 구성 (8~10장)

1. **타이틀** — 방구석 프로파일러: 진실의 방으로 · 「100억의 야근자들」
2. **문제** — 단순 RAG 챗봇의 한계 →「플레이 가능한 추론」필요
3. **솔루션** — 심문 × Advanced RAG × Function Calling × 상태머신 압박 루프
4. **아키텍처** — Data → Hybrid RAG → Agent(상태) → FastAPI → UI
5. **데이터** — 용의자 3 · 증거 소스 4종(메신저·출입·카드·네트워크) · win_condition
6. **실험** — Baseline vs Advanced RAG (표 1장) · Faithfulness
7. **데모** — Golden Route 라이브 또는 녹화 2~3분
8. **회고 · 한계 · Next** (AutoGen/Chroma 등은 Next로)
9. **역할 분담 · Q&A**

---

## 데모 스크립트 (5분 · Golden Route)

1. 사건 브리핑 — Omega · 100억 · 야근 3인 (30초)
2. 김팀장 심문 → 법인카드 RAG → 현장 제외 (1분)
3. 박신입 심문 → 슬랙 RAG → 목격자화 (1분)
4. 이대리 대질 → 출입 미끼 + Wi-Fi 100GB → 자백 (1분 30초)
5. 지목 → 엔딩 (30초)
6. 기술 한 줄: Hybrid RAG + Function Calling + 상태 분기 (30초)

---

## 멘트로 쓸 숫자 (측정 후 기입)

- Hit@5 / Faithfulness: — (`runs/eval/report.json`)
- 평균 클리어 턴: —
- 파이프라인: Baseline → Advanced 개선폭 —
