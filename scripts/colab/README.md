# scripts/colab — 코랩 원본 스크립트 보관

Colab에서 만든 **초기 RAW 데이터셋 생성기**를 내려받아 둔 폴더입니다.

| 파일 | 설명 |
| :--- | :--- |
| [`dateset.py`](dateset.py) | Colab → `.py` 변환본 (파일명 오타 `dateset` 유지 · 원본 식별용) |

## 역할

- 비정형/반정형/정형/시스템 로그 샘플·노이즈 + Smoking Gun 주입
- (실험) ChromaDB 적재·검색 라우터 스케치
- case_01~10 메타·대용량 CSV/로그 생성 실험

당시 이 출력물을 바탕으로 프로젝트 `data/raw/` 구축에 활용했습니다.

## 주의

- **본선 재생성 경로가 아님.** 현재 정본은 [`scripts/generate_rag_dataset.py`](../generate_rag_dataset.py) → `data/raw/` → `ingest.py` → `build_index.py`
- 노트북 매직(`!pip install …`)이 포함되어 있어 **로컬에서 그대로 `python3 dateset.py` 실행하면 실패**할 수 있음 (Colab용)
- 실행 시 CWD에 `1_*.txt/csv` 등을 씀 — 레포 루트에서 돌리지 말 것
- Chroma 경로는 본선 Hybrid(`runs/rag/index/`)와 다름 (실험용)

원본 Colab: 파일 헤더의 drive 링크 참고.
