# [복사해서 감마 AI에 붙여넣을 텍스트]

> 발표 2026-08-11 14:00 · 15분 · 슬라이드 10장  
> 정본 골격: [PRESENTATION.md](PRESENTATION.md) · 역할: [docs/ROLES.md](docs/ROLES.md) · 실험: [docs/TEAM_EXP_BRIEFING.md](docs/TEAM_EXP_BRIEFING.md)  
> **사용법:** 아래 `---` 사이 본문만 복사 → Gamma에 붙여넣기 → 슬라이드 자동 생성 후 데모 영상·그래프 삽입

---

방구석 프로파일러: 「진실의 방으로」
LLM · RAG · Multi-Agent로 만드는 인터랙티브 텍스트 추리 게임
케이스 — 「100억의 야근자들」

---

[슬라이드 1] 타이틀

방구석 프로파일러: 「진실의 방으로」
Interactive Mystery · Advanced RAG · Multi-Agent
AIFFEL · 2026-08-11
라이브: web-production-072b8.up.railway.app

---

[슬라이드 2] 팀원 및 역할

최승현 — Agent / LangGraph · PM
아키텍처 · 상태그래프 · 에이전트 연결

최병철 — Scenario
세계관 · 알리바이 · RAG 원천 데이터

박성우 — Prompt
용의자·조수 페르소나 프롬프트

이근목 — RAG / Data · Tools
검색·인덱싱 · Function Calling

천세문 — Service / Demo · QA
React UI · API 연동 · 데모

---

[슬라이드 3] 기존 RAG 서비스의 한계와 새로운 제안

문제
현재 대부분의 RAG·LLM 서비스는 단순 질의응답이나 요약에 그칩니다. 사용자는 수동적으로 답을 받기만 해 금방 지루해집니다.

솔루션 (우리의 제안)
LLM과 RAG를 에이전트 워크플로와 결합해, 사용자가 직접 증거를 수집하고 AI와 심리전을 벌이는 고몰입 텍스트 추리 게임으로 만들었습니다.

기대 효과
건조한 정보보안·IT 로그 데이터를 게임의 「증거」로 재해석해, 누구나 데이터 분석과 추론을 즐기며 경험하는 새로운 LLM 활용 사례를 제시합니다.

---

[슬라이드 4] 솔루션 — 플레이 가능한 추론

한 줄
심문 × Advanced RAG × Function Calling × AutoGen × LangGraph-style 상태머신

심문
용의자 AI와 대화하며 알리바이를 흔듭니다.

Advanced RAG
메신저·출입로그·법인카드·네트워크에서 Smoking Gun을 회수합니다.

Function Calling
CCTV·포렌식처럼 RAG만으로 안 되는 구멍을 툴로 메웁니다.

Multi-Agent (AutoGen)
용의자·조수가 협의해 답합니다. 본선 ask 엔진입니다.

상태·엔딩
압박·증거·지목 조건으로 승패가 갈립니다. 진범 ID는 클라이언트에 노출하지 않습니다.

---

[슬라이드 5] 시스템 아키텍처

한 줄 파이프라인
Data → Hybrid RAG → Agent → FastAPI → React UI

Data
시나리오 YAML · 페르소나 3 · 원천 4소스 (messenger / logs / corporate_card / network)

Hybrid RAG
dense + sparse RRF · evidence rerank · source soft routing

Agent
AutoGen 심문 ask · 툴 호출 · 압박·지목 상태

API / UI
FastAPI 세션 API · React 골든 루트 UI · Railway 실서버 · Langfuse 관측

---

[슬라이드 6] 게임 스토리와 배경 (Logline)

사건
업계 1위 보안 기업 「Omega / Shield Tech」. 누군가 차세대 AI 엔진의 핵심 코드를 경쟁사에 유출했습니다. (피해 규모: 100억 원)

당신의 미션
당신은 내부 감사팀의 에이스. 사건 당일 밤 11시, 서버실에 접근 권한이 있던 야근 용의자 3명을 심문해야 합니다.

승리 조건
용의자들은 모두 완벽한 가짜 알리바이를 주장합니다. 메신저·서버 로그·법인카드·네트워크 디지털 증거를 뒤져 거짓을 깨고 진범을 찾으세요.

용의자 3인 (정교한 AI 페르소나)
김팀장 (꼰대형) — 「내가 이 회사에 청춘을 얼마나 바쳤는데!」 화를 내며 회피. 11시엔 혼자 야근하며 서류를 봤다고 주장.
이대리 (엘리트형) — 논리적이고 차분하게 답변. 11시엔 사내 라운지·식당에서 쉬고 있었다고 주장.
박신입 (피해자형) — 횡설수설하며 매우 당황. 11시 서버실 앞을 지나가긴 했지만 화장실 때문이라고 강하게 주장.

---

[슬라이드 7] 핵심 플레이 (How to play?)

STEP 1. 심문 (Chat)
유저가 용의자를 골라 질문합니다. 용의자 AI는 「가짜 알리바이 문서」(RAG)를 근거로 뻔뻔하게 답합니다.

STEP 2. 증거 수집 (Function Calling · 증거 책상)
수상한 점이 보이면 조수 AI·수색으로 조사합니다. 예: 「이대리 11시 법인카드 내역을 확인해줘」 → 숨겨진 진짜 단서를 확보합니다.
대표 Smoking Gun: 법인카드 `ev_card_03` · 슬랙 DM `ev_msg_12` · 네트워크 `ev_net_01`

STEP 3. 자백 유도 · 지목 (Stateful Loop)
모은 단서로 모순을 지적하면 용의자 「스트레스(상태)」가 오릅니다. 한계를 넘기면 멘탈이 붕괴하고, 결정 증거를 조합해 진범을 지목하면 검거됩니다.
규칙: 3-Out · 헛수색 시 수사 권한 감소 · 권한 0이면 박탈

---

[슬라이드 8] 실험 — 숫자로 고른 본선

검색 KPI (고정 4쿼리 Hit@5)
Baseline (dense only) → 0/4
Advanced (Hybrid RRF + rerank) → 4/4 (전원 top-1) ← 본선 채택
OpenAI Embedding + Chroma → 0/4 ← 미채택
부가: source soft routing → Context Precision 0.22 → 0.40 (Hit@5 유지)

평가 (RAGAS n=30, Python 3.12)
Faithfulness ≈ 0.64 · Context Precision ≈ 0.75 · Context Recall ≈ 0.77

말투 · 파인튜닝
프롬프트 가드레일 → live 통과 → 본선 축
OpenAI FT 78쌍 → 403 (self-serve FT 종료)
로컬 LoRA: SmolLM → 0.5B → 1.5B → 3B 완주 · 7B는 16GB memory_limit
165턴 수집→재학습 루프 완주, 품질 붕괴로 본선 ask 미적용
결론: 게임 ask 본선은 prompt + AutoGen (gpt)

한 줄 메시지
검색은 Advanced를 숫자로 이겼고, 생성은 prompt+AutoGen이 본선이며, LoRA는 「돌릴 수 있음」을 증명했지만 품질상 넣지 않았다.

---

[슬라이드 9] 데모 — Golden Route

라이브
https://web-production-072b8.up.railway.app

발표 컷 (약 2분 30초~3분)
인트로 → 입장 → START
김팀장 심문 → 법인카드 증거
박신입 심문 → 슬랙 DM
이대리 심문 → 네트워크 Wi-Fi → 조합 지목 · 검거
(선택) Langfuse 「관측」 보드 1컷

플레이어가 할 일
심문하고, 증거를 모으고, 모순을 찔러, 진범을 지목한다.

---

[슬라이드 10] 회고 · 한계 · Next · Q&A

잘한 점
Hit@5 0/4 → 4/4로 검색 본선을 숫자로 확정
플레이 가능한 추론 루프를 실서버까지 배포
실험 실패(Embedding·OpenAI FT·7B·retrain 붕괴)를 기록하고 본선과 분리

한계
Embedding은 Smoking Gun ID KPI에서 Advanced를 이기지 못함
7B LoRA는 로컬 16GB 상한
165턴 재학습은 루프 검증까지 — 말투 품질은 미달

Next
진범 랜덤 · 용의자 확장 → 변형 케이스·case_02로 (엔진보다 시나리오·RAG 코퍼스가 본체)

Q&A
질문 환영합니다.
로드맵·실험 상세는 README · TEAM_EXP_BRIEFING에 정리되어 있습니다.

감사합니다.
방구석 프로파일러: 진실의 방으로

---

## Gamma 작업 체크 (사람용 · 붙여넣기 후)

- [ ] 슬라이드 1: 타이틀 비주얼 · 팀 로고(있으면)
- [ ] 슬라이드 6~7: 용의자 일러스트 `assets/suspects/`
- [ ] 슬라이드 8: 그래프 `report/assets/metrics/hit5_by_mode.png` · `ragas_n6_vs_n30.png` · `lora_train_loss_ladder.png`
- [ ] 슬라이드 9: **컷 B** `runs/demo_record/cut_b_20260810T031258Z/cut_b_sharp.mp4` (구 webm 사용 금지)
- [ ] (선택) 프로모 오프닝 `runs/demo_record/promo_intro_*/promo_intro_sharp.mp4`
- [ ] 슬라이드 수·말투 Gamma에서 다듬기 · 15분 배분 확인
