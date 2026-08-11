# DLthon 이후 백로그 — 보완(PROBLEM) · 발전(TRY)

> **범위:** PRT·발표 피드백 — **아쉬운 점** 보완 + **발전시키고 싶은 점** 로드맵.  
> **비범위:** README 실험 리포트 갱신 · 신규 케이스·진범 랜덤 상세(→ [ROADMAP_EXPANSION.md](ROADMAP_EXPANSION.md))  
> **운영:** 항목 완료 시 체크만 갱신. 큰 기능은 PR 단위로 쪼갠다.

관련: [GAME_RULES.md](GAME_RULES.md) · [TEAM_EXP_BRIEFING.md](TEAM_EXP_BRIEFING.md) · `backend/game_engine.py` · `web/game/`

---

## 0. 배경

### 0.1 PROBLEM — 남아 있는 문제점

| 출처 | 이슈 |
| :--- | :--- |
| **천세문** | 캐릭터별 답변이 비슷함 → 페르소나 분리 필요 |
| **최병철** | 심문 답변이 가끔 어색함 |
| **최병철** | 증거 4개 수집 후 **완료 알림 없음** → 계속 클릭 → 수사권 소진·게임 오버 |
| **박정우** | **심문 없이** 증거만 보고 추론 가능 → 진행 순서·게이트 약함 |
| **이근목** | 캐릭터별 **페르소나 평가 지표** 미정립 |

### 0.2 TRY — 발전시키고 싶은 점

| 출처 | 방향 |
| :--- | :--- |
| **천세문** | 대화·스토리 **흐름에 맞는 이미지** 생성 → 캐릭터챗처럼 **몰입** |
| **박정우** | **단일 고정 테마**에서 벗어나, 유저 질문에 따라 **진행·분위기가 자동 변화** |
| **최병철** | **장편 챕터** — 한 사건을 더 길고 알차게 |
| **이근목** | **게임 vs 캐릭터챗** 비중 결정 (한쪽 우선 vs 균형) |

### 0.3 PROBLEM ↔ TRY 한눈에

```
[보완] P0 UX·게이트 ──→ [발전] 박정우: 동적 흐름의 전제 (룰 안정)
[보완] P1 페르소나  ──→ [발전] 천세문: 몰입 연출의 전제 (말투 차별)
[보완] P2 평가      ──→ [발전] 이근목: 비중 결정의 근거 (수치·루브릭)
[발전] P3 장면·이미지 ←── 천세문 TRY
[발전] T2 동적 분기  ←── 박정우 TRY
[발전] T3 장편       ←── 최병철 TRY · ROADMAP_EXPANSION
```

---

## 1. 작업 원칙

1. **본선 파이프라인 유지** — ask는 Prompt + AutoGen, RAG는 Advanced Hybrid ([references.md](../references.md) 스택 준수).
2. **서버 권위** — 승패·증거 unlock·`culprit_id`는 API/엔진; UI는 연출만.
3. **작은 PR** — UX 1건, 페르소나 1인, eval 1스크립트 단위.
4. **측정 후 반영** — 말투·LoRA는 probe/루브릭 통과 시에만 본선 교체 검토.

---

## 2. PROBLEM 백로그 (보완)

### P0 — 플레이 막힘·오해 (먼저)

| # | 목표 | 작업 | 주요 위치 | 완료 |
| :-: | :--- | :--- | :--- | :---: |
| P0-1 | 증거 **4/4 수집**을 플레이어가 인지 | `public_state`에 `evidence_complete` 또는 `required_evidence_count` 노출 · React 토스트/모달 · 「지목 준비」 CTA | `game_engine.py` · `web/game/` | [x] |
| P0-2 | 수사권 낭비 방지 | 증거 완료 후 **책상 추가 클릭** 시 안내(턴 소모 없음 또는 confirm) | `backend/` · 증거 desk API · React | [x] |
| P0-3 | **심문 → 증거** 순서 강화 | Smoking Gun별 **관련 질문/용의자 심문 N턴** 또는 `break_count` 조건 후 해당 증거 unlock | `configs/agent.yaml` · `game_engine.py` · [GAME_RULES.md](GAME_RULES.md) | [ ] |
| P0-4 | 증거만으로 추론 차단 | 미 unlock 증거는 책상·지목 UI 비활성 + 서버에서 `force_evidence_id` 검증 | `game_engine.py` · React evidence desk | [ ] |

**성공 기준:** 골든 루트 B를 모르는 신규 플레이어가 「다 모았다」를 알고, 심문 없이 3장만으로 지목 성공하지 못함.

---

### P1 — 페르소나·대화 품질

| # | 목표 | 작업 | 주요 위치 | 완료 |
| :-: | :--- | :--- | :--- | :---: |
| P1-1 | 캐릭터 **말투 분리** | `data/personas/*.yaml` — 금지어·口癖·문장 길이·예시 대화 3~5쌍/인물 | personas YAML | [ ] |
| P1-2 | AutoGen 역할 분리 | 용의자/조수 system prompt에 **상호 모방 금지** · 용의자별 temperature/스타일 힌트 | `lib/autogen_runtime.py` | [ ] |
| P1-3 | 어색한 심문 완화 | topic별 few-shot · RAG 컨텍스트 길이 cap · 증거 미보유 시 「모른다/부인」 가드 | `game_engine.py` · personas | [ ] |
| P1-4 | 멘탈 붕괴 연출 연동 | `break_count`·`mental_break` 시 일러스트 `s1→s3` 전환 ([GAME_RULES.md §3](GAME_RULES.md)) | `web/game/` · `assets/suspects/` | [ ] |

**성공 기준:** 블라인드 10문항에서 리뷰어가 용의자 A/B/C 구분 가능(≥7/10).

---

### P2 — 페르소나 평가 (이근목)

| # | 목표 | 작업 | 주요 위치 | 완료 |
| :-: | :--- | :--- | :--- | :---: |
| P2-1 | **probe 질문셋** | 용의자×주제(알리바이·증거·압박) 고정 질문 15~30 · 기대 행동(부인/동요/회피) 정의 | `data/eval/persona_probes.yaml` (신규) | [ ] |
| P2-2 | 자동 스코어 (1차) | 키워드·금지어·알리바이 유지 여부 · 길이·반복 패널티 | `scripts/eval_persona.py` (신규) | [ ] |
| P2-3 | 회귀 게이트 | ask/autogen 변경 PR 전 probe smoke | `tests/smoke/` | [ ] |
| P2-4 | (선택) 휴먼 루브릭 | 1~5: 말투 일관 · 알리바이 · 스포일러 · 몰입 | 스프레드시트 또는 Langfuse 태그 | [ ] |

**성공 기준:** 페르소나 YAML/autogen 수정 시 숫자로 Before/After 비교 가능.

---

### P3 — 캐릭터챗형 몰입 (중기)

| # | 목표 | 작업 | 주요 위치 | 완료 |
| :-: | :--- | :--- | :--- | :---: |
| P3-1 | **장면 상태** 레이어 | `intro → interrogate → evidence → pressure → accuse` · `scene_id` | `game_engine.py` public_state · React | [ ] |
| P3-2 | 프리셋 일러스트 매핑 | 기존 `assets/intro/` · `suspects/*_s*.webp` · `game_bg*` 상태별 표시 | `web/game/` | [ ] |
| P3-3 | (선택) 조건부 생성 | `scene_hint` + 레퍼런스 얼굴 · 캐시 우선 · 실시간은 이벤트만 | 별도 `/tool` 또는 배치 스크립트 | [ ] |
| P3-4 | 대화 기억 요약 | 세션별 suspect별 3~5줄 memory · ask 프롬프트 주입 | `game_engine.py` session | [ ] |

**성공 기준:** 심문 턴마다 배경·표정이 바뀌어 「채팅앱」보다 「장면」 느낌.

---

### P4 — 선택 (여유 있을 때)

| # | 목표 | 비고 |
| :-: | :--- | :--- |
| P4-1 | LoRA 말투 재검토 | P2 probe 통과 시에만 ask 교체 실험 · [CONVERSATION_LOG.md](CONVERSATION_LOG.md) |
| P4-2 | Langfuse 페르소나 대시보드 | ask별 suspect·pressure·break 태그 |
| P4-3 | BGM·SE | React only · `/assets` |

---

## 3. TRY 로드맵 (발전)

> PROBLEM(P0~P2)으로 **플레이·말투·평가**를 먼저 안정한 뒤, 아래를 단계적으로 확장.

### T0 — 제품 방향 결정 (이근목)

**질문:** 「추리 게임」과 「캐릭터챗」 중 어디에 무게를 둘까?

| 옵션 | 강점 | 약점 | 우리 엔진과의 궁합 |
| :--- | :--- | :--- | :--- |
| **A. 게임 우선** | 정답·증거·승패·골든 루트 | 자유 대화·로맨스型 몰입 약함 | **현재 구조와 최적** (RAG·win_condition) |
| **B. 캐릭터챗 우선** | 말투·감정·장면 몰입 | 스포일러·일관성·밸런스 어려움 | 페르소나·scene 레이어 확장 필요 |
| **C. 하이브리드 (권장)** | 심문은 챗型, 승패는 게임型 | 설계·평가 지표가 둘 다 필요 | **case_01 + P3/T1/T2** 와 일치 |

**합의 초안 (팀 논의용):**

- **코어 정체성:** AI 추리 게임 (정답·증거·지목은 서버 권위)
- **차별 연출:** 캐릭터챗형 **장면·말투·기억**으로 몰입 보강
- **측정:** 게임 KPI = Hit@k·클리어율 · 챗 KPI = P2 persona probe·휴먼 루브릭

---

### T1 — 흐름형 이미지·몰입 (천세문)

**목표:** 심문·압박·증거 턴마다 **장면이 바뀌는** 캐릭터챗型 UX.

| 단계 | 내용 | 연결 백로그 |
| :--- | :--- | :--- |
| 1 | 상태 → `scene_id` → **프리셋** 일러스트 (기존 에셋) | P3-1, P3-2 |
| 2 | ask 응답·`pressure`·`break_count` → **표정 슬롯** (`s1~s3`) | P1-4 |
| 3 | (선택) `scene_hint`로 **조건부 생성** · 캐릭터 레퍼런스 고정 · 캐시 | P3-3 |
| 4 | BGM·SE 턴 전환 | P4-3 |

**원칙:** 매 턴 전량 생성 X · **자주 쓰는 장면은 프리젠**, 키 이벤트만 생성.

---

### T2 — 고정 테마 탈피·동적 흐름 (박정우)

**목표:** 유저 질문·행동에 따라 **분위기·추천 루트·연출**이 달라지되, **진범·증거 정본**은 유지.

| 단계 | 내용 | 주요 위치 |
| :--- | :--- | :--- |
| 1 | **소프트 라우팅** — 질문 intent(알리바이/증거/대질)별 RAG·프롬프트 분기 | `lib/rag_core.py` · ask |
| 2 | **동적 힌트** — 막힐 때 조수가 「다른 용의자」「CCTV」 등 제안 (스포 없음) | AutoGen assistant |
| 3 | **압력·멘탈 상태**에 따른 배경·BGM·조수 톤 변화 | `public_state` · React |
| 4 | (장기) LangGraph **사이클** 본선화 — pressure·break 분기 | `lib/langgraph_runtime.py` · [GAME_RULES.md](GAME_RULES.md) |

**전제:** P0-3·P0-4 **게이트** 후에야 “자유로워 보이는” 흐름이 깨지지 않음.

**비목표:** 세션마다 진범·증거 코퍼스를 LLM이 임의 생성 (→ [ROADMAP_EXPANSION.md](ROADMAP_EXPANSION.md) 변형 케이스로).

---

### T3 — 장편·챕터 확장 (최병철)

**목표:** 한 플레이가 **30분~1시간** 체감 — 사건을 **챕터·서브플롯**으로 나눔.

| 단계 | 내용 | 연결 |
| :--- | :--- | :--- |
| 1 | `case_01` **Act 1~3** — 인트로·심문·종결 구간 명시 · 챕터 전환 연출 | scenario YAML |
| 2 | 챕터별 **증거 풀·미끼** 분리 · 챕터 클리어 조건 | ingest · game_engine |
| 3 | **`case_02`** 신규 사건 · 용의자 4~5 · 더 긴 raw | [ROADMAP_EXPANSION.md §3](ROADMAP_EXPANSION.md) |
| 4 | (선택) **진범 변형 세트**로 재플레이 | [ROADMAP_EXPANSION.md §2](ROADMAP_EXPANSION.md) |

**성공 기준:** 골든 루트 외 **2~3개 합리적 클리어 경로** · 챕터 간 save/session 이어하기.

---

### TRY 추천 타임라인

```
단기 (보완)     P0 → P1 → P2           문제 해소 + 평가 기반
중기 (발전)     T0 합의 → P3/T1       몰입·장면 (천세문)
중기 (발전)     T2 1~3단계            동적 흐름 (박정우)
장기 (발전)     T3 + ROADMAP          장편·케이스 확장 (최병철)
```

---

## 4. 추천 진행 순서 (틈틈히)

```
1주차 스프린트 (짧게)     P0-1, P0-2          UX 즉시 체감
2주차                     P0-3, P0-4          게임 디자인 정합
병행                      P1-1, P1-2          페르소나 YAML
다음                      P2-1, P2-2          “개선됐는지” 말할 근거
여유                      P3/T1                 몰입·이미지 (천세문 TRY)
중기                      T2                    동적 흐름 (박정우 TRY)
장기                      T3 · ROADMAP          장편·케이스 (최병철 TRY)
```

한 번에 1~2개만. P0 끝나기 전 LoRA·이미지 생성 본선 투입은 하지 않는다.

---

## 5. 항목 ↔ 코드 힌트

| 이슈 | 확인할 파일 |
| :--- | :--- |
| 증거 수집·수사권 | `game_engine.py` (session.evidence_ids) · React evidence desk |
| 심문 게이트 | `question_hits_pressure` · `apply_break_count` · scenario win_condition |
| 페르소나 | `data/personas/suspect_*.yaml` |
| ask 품질 | `lib/autogen_runtime.py` · `backend/game_engine.py` ask() |
| UI 연출 | `web/game/src/` · [GAME_RULES.md](GAME_RULES.md) §3·§8 |

| 동적 흐름 | `lib/langgraph_runtime.py` · intent 라우팅 · assistant 힌트 |
| 장면·이미지 | `public_state.scene_id` · `assets/` · React layout |
| 장편·챕터 | scenario YAML · `data/scenarios/` · ROADMAP case_02 |

---

## 6. 완료 기록

| 날짜 | 항목 | PR/커밋 | 메모 |
| :--- | :--- | :--- | :--- |
| 2026-08-11 | P0-1, P0-2 | | 증거 진행 public_state · 완료 모달 · 책상 4/4 후 헛수색 수사권 보호 |
