# 실서버 심문 로그 → 재학습 데이터셋

> **목적:** Railway 등 실서버에서 플레이 테스트한 **심문 채팅(ask 턴)**을 JSONL로 모아, 페르소나 **말투** 소량 SFT/LoRA 재학습 후보로 쓴다.  
> **비목적:** 알리바이·승패·GM 판정 로직을 학습 데이터로 바꾸지 않는다. 룰 권위는 코드·YAML 유지.

관련 구현: `lib/conversation_log.py` · `scripts/export_conversation_log.py` · `configs/agent.yaml` `conversation_log` · [data/sft/README.md](../data/sft/README.md)

---

## 1. 합의된 운영 흐름

```
실서버 플레이 테스트
    → ask 성공 턴 append (opt-in)
    → runs/conversation_log/ask_turns.jsonl
    → python3 scripts/export_conversation_log.py
    → persona_ft_candidates.jsonl (말투 FT 후보)
    → build_persona_sft / local_lora_persona 로 재학습 (소량)
```

| 단계 | 내용 |
| :--- | :--- |
| 수집 | `POST .../ask` 성공 후 `append_ask_turn` (질문·용의자 답·선택적 조수 멘트) |
| 보관 | `runs/conversation_log/ask_turns.jsonl` (`runs/` gitignore) |
| 보내기 | `export_conversation_log.py` → OpenAI `messages` 형식 후보 |
| 재학습 | 기존 소량 SFT/LoRA ladder에 병합·재실행 ([data/sft/README.md](../data/sft/README.md)) |

---

## 2. 켜는 방법 (실서버만)

로컬 기본은 **OFF**.

```yaml
# configs/agent.yaml
conversation_log:
  enabled: false   # 로컬 기본
  path: runs/conversation_log/ask_turns.jsonl
```

실서버에서만 아래 중 하나:

- Railway 등 환경변수: `CONVERSATION_LOG=1` (권장 — 이미지/yaml 재배포 없이 토글)
- 또는 배포용 yaml에서 `conversation_log.enabled: true`

---

## 3. 안정장치 (Safeguards)

| 안정장치 | 설명 |
| :--- | :--- |
| **기본 OFF** | `enabled: false`. 실서버에서만 env/`true`로 켠다 |
| **ask 비차단** | 로깅 예외는 warning만. 심문 API 성공 경로를 깨지 않음 |
| **비밀·정답 미기록** | `culprit_id` · persona `secrets` · 내부 디버그 필드를 로그에 넣지 않음 |
| **누수 문구 편집** | `culprit_id` /「진범은 이대리」등 패턴 → `[편집됨]` (`lib/conversation_log.py`) |
| **길이 상한** | question≤500 · answer≤800 · assistant_note≤400 자 클립 |
| **말투 전용** | `ft_candidate: persona_speech`. 승패·알리바이 3-Out·지목 판정은 **코드 권위** |
| **Export 필터** | 너무 짧은/의미없는 질문·`[편집됨]` 답변 스킵 |
| **Git 미포함** | `runs/` 무시. 원본 대화 로그를 레포에 커밋하지 않음 |
| **클라이언트 비노출** | 로그 파일·경로를 UI/공개 API 응답에 넣지 않음 |

---

## 4. 명령 치트시트

```bash
# 실서버: CONVERSATION_LOG=1 후 플레이 테스트
# 로그 확인 (서버 볼륨/SSH)
#   runs/conversation_log/ask_turns.jsonl

# 말투 FT 후보로 보내기
python3 scripts/export_conversation_log.py
# → runs/conversation_log/persona_ft_candidates.jsonl
# → …manifest.yaml

# (선택) 조수 멘트 샘플 포함
python3 scripts/export_conversation_log.py --include-assistant

# 기존 소량 SFT 파이프라인과 병합 후 LoRA
python3 scripts/build_persona_sft.py
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-3B-Instruct ...
```

---

## 5. 하지 말 것

- 로그로 **진범·win_condition·secrets**를 학습시키려 하지 말 것
- 로컬 개발에서 `enabled: true`를 기본값으로 올리지 말 것
- `ask_turns.jsonl`을 GitHub에 올리지 말 것
- 로깅 실패를 “심문 버그”로 오인하지 말 것 — ask는 성공했을 수 있음
