# 팀원용 실험 브리핑 (1페이지)

> **목적:** 혼자 진행한 실험을 팀이 **한 타임라인**으로 이해·발표에 쓰기 위함.  
> **정본 수치·표:** [README.md](../README.md) §3 · 그래프 `report/assets/metrics/` · 산출 `runs/`  
> **일정:** [PROJECT_SCHEDULE.md](../PROJECT_SCHEDULE.md) · **발표:** [PRESENTATION.md](../PRESENTATION.md)

---

## 0. 한 줄 메시지

**검색은 Advanced를 숫자로 이겼고, 생성은 prompt + AutoGen이 본선이며, LoRA·165턴 재학습은 “돌릴 수 있음”을 증명했지만 품질상 본선에는 안 넣었다.**

KPI는 리더보드 순위가 아니라 **Hit@5 · 페르소나 유지 · 서비스 안정**.

---

## 1. 우리가 실험한 순서 (설명용 타임라인)

아래 순서대로 말하면 “왜 다음을 했는지”가 자연스럽게 이어진다.

### ① 기반 깔기 — 7/30 (Day 1)

시나리오·용의자 3 · Smoking Gun · 가짜 원천 데이터(`data/raw/`) · ingest.  
**아직 모델 대결이 아니라 “무엇을 찾아야 하는지”를 고정.**

### ② 검색 본선 고르기 — 7/31 전반 (Day 2)

| 순서 | 실험 | 한 줄 결과 | 다음으로 간 이유 |
| ---: | :--- | :--- | :--- |
| 1 | **Baseline** (dense only) | Hit@5 **0/4** · 출입로그 오탐 (FAIL-1) | 카드 쿼리도 못 올림 → Hybrid 필요 |
| 2 | **Advanced** (hybrid RRF + rerank) | Hit@5 **4/4** · 전원 top-1 | 본선 후보. 다만 `ev_msg_12` 등 exact ID 이슈 → 청킹·쿼리 확장으로 **해결**(FAIL-2) |
| 3 | **Embedding** (OpenAI + Chroma) | Hit@5 **0/4** (FAIL-3) | “상용 의미검색이면 이기나?” → **못 이김** → 본선 **미채택** |
| 4 | **source soft routing** | C-Prec **0.22→0.40**, Hit@5 유지 | Advanced 위에 정밀도 한 번 더 |

**채택:** Advanced (+ routing). **기각:** Embedding을 본선 검색으로.

### ③ 생성·말투 — 7/31 중반 (같은 Day 2, 검색 다음)

| 순서 | 실험 | 한 줄 결과 | 다음으로 간 이유 |
| ---: | :--- | :--- | :--- |
| 5 | **Prompt** (알리바이·환각 금지) | live 통과 | **본선 축으로 유지** |
| 6 | **OpenAI FT** (78쌍 submit) | **403** training_not_available (FAIL-4) | 상용 FT 막힘 → 로컬로 대체 |
| 7 | **LoRA ladder** SmolLM → 0.5B → 1.5B → **3B** | 3B loss≈**2.66** 완주 | 파이프라인은 됨. 품질은 gpt 대체 못 함 → ask **미교체** |
| 8 | **7B LoRA** | 16GB **memory_limit** | 상한 확정. 더 키우기 중단 |

**채택:** prompt (+ 이후 AutoGen). **기각:** LoRA를 게임 ask에 꽂기.

### ④ 숫자로 남기기 · 에이전트 붙이기 — 7/31 후반 ~ 8/1–2

| 순서 | 실험 | 한 줄 결과 |
| ---: | :--- | :--- |
| 9 | **로컬 eval** (`evaluate.py`) | Faithfulness 등 overlap 루브릭 |
| 10 | **RAGAS n=30** (Python 3.12) | Faith≈**0.64** · C-Prec≈**0.75** · C-Recall≈**0.77** |
| 11 | **Function Calling** | CCTV 결측 · 포렌식 MAC — RAG만으로 안 되는 구멍 |
| 12 | **Agent smoke** | 심문→retrieve→CCTV→pressure 1턴 |
| 13 | **AutoGen** | ask **본선** (용의자·조수 GroupChat) |
| 14 | FE↔BE · React · Golden Route · 프롬프트 밸런스 | 플레이 가능한 제품으로 고정 |

### ⑤ 실서비스 · 관측 — 8/3

| 순서 | 실험 | 한 줄 결과 |
| ---: | :--- | :--- |
| 15 | Railway 배포 | 라이브 플레이 |
| 16 | **Langfuse** 관측 게시판 | 사이드바「관측」· ask I/O |

### ⑥ 수집 → 재학습 루프 — 8/4~8/7 (추가 실험)

| 순서 | 날짜 | 내용 | 결과 |
| ---: | :--- | :--- | :--- |
| 17 | 8/4 | auto_ask Day1 | **45**턴 |
| 18 | 8/5 | Day2 증거 압박 | **45**턴 |
| 19 | 8/6 | Day3 압박·모순 | **45**턴 |
| 20 | 8/7 오전 | Day4 보충 | **30**턴 → 누적 **165** |
| 21 | 8/7 | export → merge | 165 · skip 0 / **243**예 |
| 22 | 8/7 | **3B LoRA retrain** | loss≈**2.72** 완주 · probe **붕괴** → **본선 ask 미교체** |

**의미:** 말투가 좋아진 게 아니라 **수집→export→LoRA가 도는 것을 증명**. 품질 미달이라 서비스는 그대로.

### ⑦ 발표 준비 (실험 아님 · 타임라인만)

8/9 시연 녹화 · 8/10 슬라이드 · 8/11 14:00 발표.

---

## 2. 발표 슬라이드 7 (≈2분) — 위 순서 압축

1. Baseline **0/4** → Advanced **4/4** → Embedding **탈락** (+ routing 한 줄)  
2. Prompt 본선 → OpenAI FT 실패 → LoRA ≤3B 완주·7B 불가 → **ask는 prompt+AutoGen**  
3. RAGAS n=30 숫자 세 개  
4. (한 줄) 165턴 재학습 루프 완주, **품질 미달로 미적용**

회고: Embedding · 7B · retrain after 붕괴 = **한계**.

---

## 3. 역할별 “깊게 볼 구간”

| 담당 | 타임라인에서 | 발표 한 줄 |
| :--- | :--- | :--- |
| Scenario | ① | Smoking Gun·노이즈 때문에 Hit@k가 어려웠다 |
| RAG | ② | 그래서 Advanced를 골랐다 |
| Prompt | ③ | 말투 본선은 프롬프트다 |
| Agent / PM | ④·⑥ | AutoGen 본선 · retrain은 루프만 |
| Service | ⑤ | Railway·Langfuse로 실험이 서비스에 붙었다 |

---

## 4. Q&A 대비

**Q. 데이터 적어서 Embedding 실패한 거 아니야?**  
A. 같은 4쿼리에서 Advanced는 4/4. 양보다 **희소 증거 + 노이즈**.

**Q. LoRA 했는데 왜 게임에 안 넣어?**  
A. 학습은 끝났지만 생성 샘플 붕괴. 발표 직전 **본선 안정** 우선.

**Q. 165턴이면 부족한 거 아냐?**  
A. 더 쌓아도 짧은 step면 비슷할 수 있음. 이번 목표는 **루프 검증**.

**Q. 산출물은 어디?**  
A. `git pull` → `runs/` · 표 `README.md` · 그림 `report/assets/metrics/`.

---

## 5. 30분 팀 미팅 안건 (복붙)

| 시간 | 내용 |
| ---: | :--- |
| 0–5 | 라이브 골든 루트 한 판 |
| 5–15 | **§1 타임라인** 순서대로 + 그래프 3장 |
| 15–20 | 역할별 발표 한 줄 |
| 20–25 | Q&A (Embedding / LoRA) |
| 25–30 | 리허설·발표 역할 확정 |

라이브: https://web-production-072b8.up.railway.app
