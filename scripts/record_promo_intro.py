#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/record_promo_intro.py — 시연 영상용 멀티디바이스 프로모 인트로 녹화

게임 사이트 스토리 인트로가 아님.
다른 조 시연처럼 ‘여러 기기에서도 잘 보인다’는 오프닝 클립.

  python3 scripts/record_promo_intro.py
  → runs/demo_record/promo_intro_<ts>/video/*.webm
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "promo_intro" / "index.html"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "pip install playwright && python3 -m playwright install chromium\n" + str(exc)
        ) from exc

    if not HTML.exists():
        raise SystemExit(f"missing {HTML}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "runs" / "demo_record" / f"promo_intro_{stamp}"
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    url = HTML.resolve().as_uri()
    print(f"url={url}")
    print(f"out_dir={out_dir}")

    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 720},
            locale="ko-KR",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        # HTML 시퀀스 전체 (~14s) + 여유
        page.wait_for_selector("html[data-done='1']", timeout=30_000)
        page.wait_for_timeout(800)
        context.close()
        browser.close()

    videos = sorted(video_dir.glob("*.webm"))
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kind": "promo_intro_multidevice",
        "elapsed_sec": round(time.time() - t0, 1),
        "ok": bool(videos),
        "videos": [str(v.relative_to(ROOT)) for v in videos],
        "note": "시연 오프닝 · Desktop/Tablet/Mobile · 본편 골든루트 앞에 붙이기",
    }
    (out_dir / "report.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    if videos:
        print(f"video: {videos[0]}")
    return 0 if videos else 1


if __name__ == "__main__":
    raise SystemExit(main())
