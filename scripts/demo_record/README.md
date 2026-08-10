# 시연 자동 녹화 (컷 B)

사람이 클릭하지 않고 Playwright가 [PRESENTATION.md](../PRESENTATION.md) **발표 컷(B)** 동선을 진행하며 화면을 녹화한다.

## 준비

```bash
pip install playwright
python3 -m playwright install chromium
```

## 실행

```bash
# Railway 라이브 (기본)
python3 scripts/demo_record_cut_b.py

# 창을 보면서
python3 scripts/demo_record_cut_b.py --headed

# 로컬 API
python3 scripts/demo_record_cut_b.py --base-url http://127.0.0.1:8000 --headed

# 인트로 스킵 (/game 직행)
python3 scripts/demo_record_cut_b.py --skip-intro
```

## 산출

```
runs/demo_record/cut_b_<timestamp>/
  cut_b_sharp.mp4       # **발표 삽입용** (CDP JPEG HQ → H.264)
  frames_hq/            # 캡처 프레임 (용량 큼 · 확인 후 삭제 가능)
  report.json
  failure.png           # 실패 시
  video/*.webm          # `--legacy-webm` 일 때만 (저비트레이트 · 비권장)
```

**구버전 webm** (`cut_b_20260807…`, ~720p · ~0.5Mbps VP8)은 UI가 뭉개집니다. 발표·편집에는 **`cut_b_sharp.mp4`만** 쓰세요.

`runs/demo_record/` 산출은 **git 미추적**(용량). 로컬·Drive에 보관 후 슬라이드에 삽입.

## 연출 (기본 = 풀 페이스)

- **인트로:** 씬마다 수 초 체류(텍스트 길이에 비례) 후 다음으로 진행 → 마지막에「입장하기」
- **심문:** `fill`이 아니라 **한 글자씩 타자** (`--type-delay-ms`, 기본 85)
- **사이드바:** 게임 방법 + 사건개요(기본 ON)

```bash
# 더 느리게
python3 scripts/demo_record_cut_b.py --scene-dwell-ms 6000 --type-delay-ms 110 --after-reply-ms 4000

# 인트로만 (편집용 · 씬당 기본 7초 · 문 열림까지)
python3 scripts/demo_record_cut_b.py --intro-only
python3 scripts/demo_record_cut_b.py --intro-only --no-enter   # CTA에서 종료
```

예상 길이: 컷B 풀 페이스 **약 2~8분** · 인트로만 **약 40~70초** (씬 수·체류에 따라).
