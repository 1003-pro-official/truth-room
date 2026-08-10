# 시연 영상용 프로모 인트로 (멀티 디바이스)

게임 `/` 스토리 인트로와 **별개**.  
다른 조 시연처럼 **“여러 기기에서도 잘 보인다”** 를 고급스럽게 여는 오프닝 클립.

## 구성

| 파일 | 역할 |
| :--- | :--- |
| `index.html` | 1920×1080 모션 시퀀스 (~15초) · 하단 밴드 카피 · 마지막 CTA 카드 분리 |
| `media/devices_*.png` | 노트북·폰·태블릿 시네마틱 키프레임 |
| `media/case_mood.webp` | 사건 무드 오프닝 |

## 밝기 · 선명도

- 원본 키프레임이 노이르라 CSS brightness는 소량만 올림.
- **글자·기기 UI가 같은 픽셀에 겹치면** webm 압축에서 뭉개짐 → 카피는 하단 밴드, 엔딩은 **플랫 CTA**.
- 녹화: **1920×1080** + `promo_intro_sharp.mp4` (CRF 16).

더 밝게: `.scene img.bg` · `.frame img`의 `brightness()`만 올리기.

## 녹화

```bash
python3 scripts/record_promo_intro.py
# → runs/demo_record/promo_intro_<ts>/video/*.webm
# → runs/demo_record/promo_intro_<ts>/promo_intro_sharp.mp4  (권장)
```

브라우저에서 미리보기:

```bash
open web/promo_intro/index.html
```

## 편집 붙이는 법

1. **이 프로모 인트로** (원배속)
2. 기존 Playwright **골든 루트 본편** (1.15~1.3×)
3. 마지막에 라이브 URL 카드

CapCut / DaVinci / ffmpeg concat.
