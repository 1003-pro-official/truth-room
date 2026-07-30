# data/ — RAG 코퍼스 · 시나리오

## 생성

```bash
python3 scripts/generate_rag_dataset.py
python3 ingest.py
python3 build_index.py
```

## 스펙 (목표)

| 유형 | 경로 | 목표 분량 |
| :--- | :--- | :--- |
| 비정형 진술 | `raw/statements/` | 용의자 3 · 인당 약 1,000~1,500자 |
| 현장/CCTV 기술 | `raw/forensics/` | 약 800자 × 1~2 |
| 메신저 | `raw/messenger/*.jsonl` | 약 3,000~5,000줄 |
| 출입 로그 | `raw/logs/*.txt` | 약 10,000~20,000줄 |
| 법인카드 | `raw/corporate_card/*.csv` | 약 500~1,000줄 |
| 네트워크 | `raw/network/*.txt` | Smoking Gun + 노이즈 |

핵심 `evidence_id`: `ev_card_03` · `ev_msg_12` · `ev_log_07` · `ev_net_01`  
시나리오: `scenarios/case_01.yaml` · 페르소나: `personas/`
