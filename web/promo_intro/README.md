# 시연 영상용 프로모 인트로 (멀티 디바이스)

게임 `/` 스토리 인트로와 **별개**.  
다른 조 시연처럼 **“여러 기기에서도 잘 보인다”** 를 고급스럽게 여는 오프닝 클립.

## 구성

| 파일 | 역할 |
| :--- | :--- |
| `index.html` | 1280×720 모션 시퀀스 (~14초) |
| `media/devices_*.png` | 노트북·폰·태블릿 시네마틱 키프레임 |
| `media/case_mood.webp` | 사건 무드 오프닝 |

## 녹화

```bash
python3 scripts/record_promo_intro.py
# → runs/demo_record/promo_intro_<ts>/video/*.webm
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
