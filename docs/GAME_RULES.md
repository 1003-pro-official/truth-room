# GAME_RULES — 진실의 방 진행 룰

> **정본:** 팀 합의 게임플레이 규칙. 구현은 [TECH_SPEC.md](../TECH_SPEC.md) · `configs/agent.yaml` · `backend/game_engine.py` · `app.py`.  
> **출처:** 팀원 진행 룰 아이디어 → 프로젝트 적용 가능분 정리 (3-Out · 멘탈 붕괴 UI · 타임어택).  
> **전제:** 핵심 파이프라인은 이미 있음. 본 룰은 그 위에 **압박·연출·긴장감**을 얹는다.  
> LLM GM의 `is_alibi_broken` 정밀 판정·실페르소나 톤은 **AI 프롬프트 + 실 RAG 데이터** 이후 고도화.

---

## 1. 목표 플레이 루프

```
심문(질문) → (증거 RAG / CCTV·포렌식) → 알리바이 붕괴 판정
  → break_count +1 (최대 3) → [3회 시] mental_break
  → 압박·대질 → 지목/자백
```

골든 루트(데모): 카드(`ev_card_03`) → 슬랙(`ev_msg_12`) → 네트워크(`ev_net_01`) → **조합 지목** (용의자+증거 2장).

참고 연출 원형: [명탐정 S 플레이 영상](https://youtu.be/tRW30RCBicI?list=PLxYDBTF4gIAYorlIaL28u9_gpwgmCNmNg) — 아래 §8에서 진실의 방 매핑.

---

## 2. 3-Out 시스템 (알리바이 Break Point)

| 항목 | 내용 |
| :--- | :--- |
| **개념** | 용의자 알리바이를 **3번** 깨야 멘탈 붕괴 모드로 전환 |
| **상태** | `break_count: {suspect_a\|b\|c: 0..3}` (용의자별) |
| **트리거** | GM/엔진이 `is_alibi_broken: true` 판정 시 해당 용의자 `break_count += 1` (턴당 최대 1) |
| **임계** | `break_count >= break_threshold` (기본 **3**) |
| **효과** | 페르소나 프롬프트를 **Normal → Mental Breakdown** 으로 전환 |
| **병행** | 기존 `pressure` (0~1 float)는 유지. 3-Out은 **모드 전환 트리거**, pressure는 **자백 기울기** |

### 2.1 알리바이 붕괴 판정 (현재 스텁 → 이후 GM)

**현재(코드):** 질문 키워드 + 보유 `evidence_id` 규칙 매칭 (프롬프트 전 단계).  
**목표(프롬프트 후):** Judge(GM) AI가 JSON으로 `is_alibi_broken` 반환 → 동일 카운터 증가.

| 용의자 | 알리바이 요지 | 붕괴에 쓰는 증거 예 |
| :--- | :--- | :--- |
| 김팀장 `suspect_a` | 자리·기획안 검토 | `ev_card_03` (룸살롱) |
| 이대리 `suspect_b` | 라운지·넷플릭스 | `ev_net_01` (Wi-Fi 100GB) · 미끼 `ev_log_07` |
| 박신입 `suspect_c` | 화장실 | `ev_msg_12` (서버실 DM) |

### 2.2 멘탈 붕괴 모드

- `break_count[sid] >= 3` → `status: "mental_break"` (해당 세션·용의자 기준 `mental_break_suspects`에 포함)
- 대사: `system_prompt_mental_break` (페르소나 YAML) 사용
- 자백 가드레일(`ev_net_01` 전 부인 등)은 **유지** — 멘탈 붕괴 ≠ 즉시 자백

---

## 3. 멘탈 마스크 붕괴 (UI/UX)

| 항목 | 내용 |
| :--- | :--- |
| **신호** | API `public_state` / ask 응답에 `status`, `mental_break_suspects`, `break_count` |
| **프론트** | `status == "mental_break"`(또는 선택 용의자가 mental 목록)일 때 일러스트·배경 전환 |
| **연출** | 평온 초상 → 당황 초상 · 배경을 붉은 「진실의 방」톤으로 (에셋은 Front 담당) |
| **에셋 경로(권장)** | `report/assets/ui/{suspect_id}_normal.png` · `{suspect_id}_break.png` (없으면 텍스트/색상 폴백) |

---

## 4. 20초 타임어택 · 턴 3진 아웃

| 항목 | 내용 |
| :--- | :--- |
| **위치** | **클라이언트(Streamlit)** 타이머 + 서버 `pass_turn` |
| **설정** | `game.turn_seconds` (기본 **20**) · `game.timeout_strike_max` (기본 **3**) |
| **타임아웃 1회** | `timeout_strikes += 1` · 턴 패스 · **알리바이 `break_count`는 증가하지 않음** |
| **턴 3진 아웃** | `timeout_strikes >= 3` → `status: "turn_out"` · 세션 종료(패배) |
| **알리바이 3-Out과 분리** | 용의자 멘탈 붕괴(`break_count`) ≠ 탐정 시간 초과 아웃(`timeout_strikes`) |
| **전제** | RAG/프롬프트 경량화로 응답 지연 완화 |
| **권장** | 데모 시 타이머 ON · 디버그 시 OFF |

```
타임아웃 → strike 1/3 → 2/3 → 3/3 turn_out (미션 실패)
알리바이 붕괴 → break 1/3 → 2/3 → 3/3 mental_break (용의자 모드 전환)
```

---

## 5. API · 설정 계약

### 5.1 `public_state` 추가 필드

```yaml
break_count: {suspect_a: 0, suspect_b: 0, suspect_c: 0}
mental_break_suspects: []
timeout_strikes: 0                 # 턴 타임아웃 누적 (0..3)
timeout_strike_max: 3
status: "playing" | "mental_break" | "turn_out" | "authority_revoked"
stamina: 3
stamina_max: 3
turn_seconds: 20
timer_enabled: true
```

### 5.2 `POST /ask` 응답 추가

```yaml
is_alibi_broken: bool
break_count: int          # 해당 용의자
status: "playing" | "mental_break" | "turn_out"
```

### 5.2b `POST /pass_turn` 응답

```yaml
passed: true
reason: timeout
timeout_strikes: 1        # 누적
turn_out: false           # true면 3진 아웃 · ended
status: "playing" | "turn_out"
```

### 5.2c 공개 프로필 · 사건개요

| Method | Path | 내용 |
| :--- | :--- | :--- |
| `GET` | `/api/v1/session/{id}/suspects/{sid}/profile` | `name` · `mbti` · `traits` · `profile{}` · `case_overview` |
| `GET` | `/api/v1/session/{id}/case` | `title` · `synopsis` · `discovered_at` · `location` · `incident` · `notes` |

- UI: 용의자 카드 **「프로필」** 버튼 → 수사 파일 dialog (○/● 심문 대상 선택과 분리). 초상 클릭으로 열지 않음.
- **미노출:** `secrets` · `role` · `system_prompt*` · `culprit_id` · `win_condition`

### 5.3 `configs/agent.yaml` · `game` 블록

```yaml
game:
  break_threshold: 3
  turn_seconds: 20
  timer_enabled: true
  max_break_per_turn: 1
  timeout_strike_max: 3
  stamina_max: 3
```

---

## 8. 명탐정 S → 진실의 방 매핑

> 팀원 제안 · 제미나이 초안을 **기존 상태머신·RAG·API**에 맞게 재해석.  
> 원형: 하트/스테미나 · 용의자+무기+동기 조합 · 단서 획득 연출.

| 명탐정 S | 진실의 방 | 기존 룰과의 관계 |
| :--- | :--- | :--- |
| 잘못된 장소 클릭 → 하트 감소 | **수사 권한(`stamina`)** 감소 | 타임아웃 3진(`timeout_strikes`)·알리바이 3-Out과 **별도** |
| 엔딩 카드 조합 | **조합 지목**: 용의자 + 결정적 증거 **2장** | 단순 `accuse(suspect)` 폐기 → 콤보 필수 |
| 단서 발견 팝업 | RAG로 **신규 smoking gun** 획득 시 UI 팝업 | `new_clues[]` 신호 |

### 8.1 수사 권한 (Stamina) — 오답/헛수색 패널티

| 항목 | 내용 |
| :--- | :--- |
| **상태** | `stamina` / `stamina_max` (기본 **3**) |
| **감소** | (1) RAG 검색이 **신규 `evidence_id` 0건** (헛수색) (2) 조합 지목 **오답** |
| **감소 안 함** | 알리바이 붕괴 성공 · 유효 증거 획득 · 타임아웃(이미 `timeout_strikes`로 처리) |
| **0** | `status: "authority_revoked"` · 세션 종료 · *"감사관, 수사 권한이 박탈되었습니다."* |

### 8.2 조합 지목 (클리어 조건)

| 항목 | 내용 |
| :--- | :--- |
| **입력** | `suspect_id` + `evidence_ids` (길이 **2**, 세션에 보유한 ID만) |
| **정답(스텁 Judge)** | `suspect_id == culprit_id` **AND** `ev_net_01 ∈ evidence_ids` **AND** 나머지 1장 ∈ `win_condition.min_evidence_ids` |
| **오답** | `stamina -= 1` · 세션 유지(권한 남으면) · GM 판정 JSON 필드는 이후 LLM 고도화 |
| **정답** | 자백 엔딩 · `ended=true` |

### 8.3 단서 획득 연출

| 항목 | 내용 |
| :--- | :--- |
| **트리거** | `search`로 smoking gun ID가 **새로** `evidence_ids`에 추가될 때 |
| **응답** | `new_clues: [{evidence_id, title, snippet}]` |
| **UI** | 토스트/배너 + (가능 시) `st.balloons` · 에셋 있으면 이미지 팝업 |
| **smoking gun** | `ev_card_03` · `ev_msg_12` · `ev_net_01` · (미끼 `ev_log_07`도 연출 가능) |

---

## 9. 구현 체크리스트

| ID | 항목 | 담당 힌트 | 상태 |
| :--- | :--- | :--- | :---: |
| G1 | 본 문서 · TECH_SPEC 반영 | Docs/PM | ✅ |
| G2 | Session `break_count` · mental 상태 · ask 판정 | Agent/API | ✅ |
| G3 | 페르소나 `system_prompt_mental_break` | Prompt | ✅ 스텁 |
| G4 | Streamlit 타이머 · mental_break UI 폴백 | Front | ✅ |
| G4b | 턴 타임아웃 3진 아웃 (`timeout_strikes`) | Agent/API/Front | ✅ |
| G7 | 수사 권한 stamina · 헛수색/오심 패널티 | Agent/API | ✅ |
| G8 | 조합 지목 (용의자+증거 2) | API/Front | ✅ |
| G9 | 단서 획득 `new_clues` UI · 인벤토리 · HUD | Front | ✅ |
| G5 | GM LLM `is_alibi_broken` JSON | Prompt+Agent | ✅ `lib/gm_judge.py` (로컬 스텁+스키마, LLM 훅 준비) |
| G6 | 용의자 초상 에셋 · 라디오 선택 UI | Front | ✅ (스텁 일러스트) |
| G11 | 용의자 공개 프로필 · 수사 파일 dialog | API/Front | ✅ |
| G10 | Judge LLM 조합 지목 JSON | Prompt+Agent | ⏳ 프롬프트 후 |

---

## 10. 비범위 · 주의

- `culprit_id` 클라이언트 미노출 (기존 안티패널 유지)
- 프로필 API도 `secrets` / `role` / 내부 프롬프트 미노출
- UI → LLM 직결 금지
- 알리바이 3-Out만으로 엔딩 강제 금지 — **조합 지목**이 최종 클리어
- AutoGen 심문 턴은 본선(`lib/autogen_runtime.py`) — 무제한 티키타카·상한/폴백 없는 구성은 비범위 ([references.md](../references.md))
- 명탐정 S의 「무기·동기」카드는 본작에서 **결정적 증거 2장**으로 치환 (세계관상 무기 개념 없음)
