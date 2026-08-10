#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/demo_record_cut_b.py — PRESENTATION 컷 B 자동 녹화 (Playwright)

사람이 클릭하지 않고, 브라우저가 골든 루트를 진행하며 영상을 저장한다.
- 인트로: 씬을 하나씩 충분히 보여 준 뒤 입장
- 심문: fill 즉시 입력이 아니라 **타자(press_sequentially)** 로 타이핑

준비:
  pip install playwright
  python3 -m playwright install chromium

실행:
  python3 scripts/demo_record_cut_b.py
  python3 scripts/demo_record_cut_b.py --headed
  python3 scripts/demo_record_cut_b.py --base-url http://127.0.0.1:8000 --headed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://web-production-072b8.up.railway.app"
ASK_TIMEOUT_MS = 90_000
NAV_TIMEOUT_MS = 60_000
# 발표용: 720p VP8(~0.5Mbps)는 UI가 뭉개짐 → 1080p 녹화 후 H.264 재인코딩
RECORD_W = 1920
RECORD_H = 1080

# 기본 연출 (풀 스토리 느낌)
DEFAULT_SCENE_DWELL_MS = 4_500  # 인트로 씬당 최소 읽기 시간
DEFAULT_TYPE_DELAY_MS = 85  # 타자 간격
DEFAULT_AFTER_REPLY_MS = 2_800  # 용의자 답 읽기
DEFAULT_SLOW_MO = 80


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Playwright 필요:\n"
            "  pip install playwright\n"
            "  python3 -m playwright install chromium\n"
            f"상세: {exc}"
        ) from exc


def _encode_sharp_mp4(webm: Path, out_mp4: Path) -> Path | None:
    """Playwright webm(저비트레이트 VP8) → 발표용 고화질 MP4."""
    import subprocess

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "14",
        "-b:v",
        "12M",
        "-maxrate",
        "16M",
        "-bufsize",
        "24M",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(out_mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"ffmpeg reencode skipped: {exc}", file=sys.stderr)
        return None
    return out_mp4 if out_mp4.exists() else None


def _encode_frames_mp4(frames_dir: Path, out_mp4: Path, *, fps: float) -> Path | None:
    """CDP 스크린캐스트 JPEG 시퀀스 → 고화질 MP4 (UI 선명)."""
    import subprocess

    pattern = str(frames_dir / "f%06d.jpg")
    fps = max(8.0, min(30.0, float(fps)))
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        f"{fps:.3f}",
        "-i",
        pattern,
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "12",
        "-b:v",
        "10M",
        "-maxrate",
        "14M",
        "-bufsize",
        "20M",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(out_mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"ffmpeg frames encode skipped: {exc}", file=sys.stderr)
        return None
    return out_mp4 if out_mp4.exists() else None


class _HqScreencast:
    """Playwright VP8 대신 CDP JPEG 스크린캐스트로 선명하게 캡처."""

    def __init__(self, page, frames_dir: Path) -> None:
        import base64

        self._base64 = base64
        self._page = page
        self._frames_dir = frames_dir
        self._frames_dir.mkdir(parents=True, exist_ok=True)
        self._session = None
        self.n = 0
        self.t0 = 0.0

    def start(self) -> None:
        self.t0 = time.time()
        self._session = self._page.context.new_cdp_session(self._page)
        self._session.on("Page.screencastFrame", self._on_frame)
        self._session.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": 95,
                "maxWidth": RECORD_W,
                "maxHeight": RECORD_H,
                "everyNthFrame": 1,
            },
        )

    def _on_frame(self, params: dict) -> None:
        self.n += 1
        raw = self._base64.b64decode(params["data"])
        (self._frames_dir / f"f{self.n:06d}.jpg").write_bytes(raw)
        try:
            self._session.send(
                "Page.screencastFrameAck", {"sessionId": params["sessionId"]}
            )
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> float:
        try:
            if self._session:
                self._session.send("Page.stopScreencast")
        except Exception:  # noqa: BLE001
            pass
        elapsed = max(0.1, time.time() - self.t0)
        return (self.n / elapsed) if self.n else 12.0


def _pause(page, ms: int) -> None:
    page.wait_for_timeout(max(0, int(ms)))


def _wait_ask_done(page) -> None:
    spinner = page.locator(".ask-spinner")
    try:
        spinner.wait_for(state="visible", timeout=8_000)
    except Exception:  # noqa: BLE001
        pass
    spinner.wait_for(state="hidden", timeout=ASK_TIMEOUT_MS)
    page.locator(".chat-msg.role-suspect").last.wait_for(state="visible", timeout=20_000)


def _type_question(page, question: str, *, type_delay_ms: int) -> None:
    """사람이 치는 것처럼 한 글자씩 입력 (녹화용)."""
    box = page.get_by_placeholder("질문을 입력하세요")
    box.click()
    _pause(page, 350)
    box.fill("")  # 잔여 입력 제거
    # press_sequentially: 키 이벤트 단위로 입력 → 화면에 타자가 보임
    box.press_sequentially(question, delay=type_delay_ms)
    _pause(page, 550)


def _ask(
    page,
    suspect_label: str,
    question: str,
    *,
    type_delay_ms: int,
    after_reply_ms: int,
) -> None:
    page.get_by_role("button", name="심문").click()
    _pause(page, 500)
    page.get_by_label("심문 대상").select_option(label=suspect_label)
    _pause(page, 700)
    _type_question(page, question, type_delay_ms=type_delay_ms)
    page.get_by_role("button", name="전송").click()
    _wait_ask_done(page)
    _pause(page, after_reply_ms)


def _desk_clue(page, short_label: str) -> None:
    page.get_by_role("button", name="증거 수색").click()
    _pause(page, 1_000)
    item = page.locator(".desk-item", has_text=short_label)
    item.scroll_into_view_if_needed()
    _pause(page, 900)
    item.click()
    page.get_by_role("dialog", name="수색 결과").wait_for(timeout=30_000)
    _pause(page, 2_200)
    page.get_by_role("button", name="단서 확인 · 인벤토리에 보관").click()
    _pause(page, 1_200)


def _scene_dwell_ms(scene, base_dwell_ms: int) -> int:
    """텍스트 길이에 비례해 읽기 시간 가산."""
    try:
        text = (scene.inner_text() or "").strip()
    except Exception:  # noqa: BLE001
        text = ""
    # 한글 기준 대략 초당 8~10자 → 여유 있게
    extra = min(8_000, max(0, (len(text) - 40) * 45))
    return base_dwell_ms + extra


def _advance_intro(page, *, scene_dwell_ms: int) -> None:
    """인트로 씬을 순서대로 충분히 보여 준 뒤 입장 CTA까지."""
    page.locator(".scene").first.wait_for(state="visible", timeout=NAV_TIMEOUT_MS)
    _pause(page, 1_200)

    # 씬이 API로 렌더될 시간
    for _ in range(20):
        if page.locator(".scene").count() >= 2:
            break
        _pause(page, 300)

    scenes = page.locator(".scene")
    n = scenes.count()
    print(f"intro_scenes={n}")

    for i in range(n):
        scene = scenes.nth(i)
        scene.scroll_into_view_if_needed()
        # 활성 표시될 때까지 약간 대기
        _pause(page, 600)
        dwell = _scene_dwell_ms(scene, scene_dwell_ms)
        print(f"  scene[{i}] dwell_ms={dwell}")
        _pause(page, dwell)

        is_final = "scene--final" in (scene.get_attribute("class") or "")
        if is_final:
            break

        # 활성 논-파이널 씬 클릭 → 다음 씬으로 smooth scroll
        try:
            # 텍스트 영역 클릭 (버튼/링크 회피)
            scene.locator(".scene-copy, .scene-text, .scene-card, .scene-body").first.click(
                timeout=3_000
            )
        except Exception:  # noqa: BLE001
            box = scene.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
        _pause(page, 1_100)

    # 마지막 씬 CTA (입장하기) — reveal ~2.8s + 여유
    final = page.locator(".scene--final")
    final.scroll_into_view_if_needed()
    _pause(page, max(3_200, scene_dwell_ms))
    page.locator(".scene-cta.is-ready [data-start-game]").wait_for(timeout=25_000)
    _pause(page, 1_500)


def run_intro_only(page, *, base_url: str, scene_dwell_ms: int, enter_door: bool) -> None:
    """인트로 풀 스토리만 녹화 (편집용 앞부분)."""
    base = base_url.rstrip("/")
    page.goto(f"{base}/", wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    _pause(page, 2_000)
    _advance_intro(page, scene_dwell_ms=scene_dwell_ms)
    if enter_door:
        page.get_by_role("button", name="입장하기").click()
        _pause(page, 2_200)
        try:
            page.wait_for_url("**/game/**", timeout=NAV_TIMEOUT_MS)
            _pause(page, 2_500)
        except Exception:  # noqa: BLE001
            _pause(page, 2_000)
    else:
        # CTA가 보이는 채로 여운
        _pause(page, 3_000)


def run_cut_b(
    page,
    *,
    base_url: str,
    skip_intro: bool,
    scene_dwell_ms: int,
    type_delay_ms: int,
    after_reply_ms: int,
    include_case_overview: bool,
) -> None:
    base = base_url.rstrip("/")

    if skip_intro:
        page.goto(f"{base}/game/", wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    else:
        page.goto(f"{base}/", wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        _pause(page, 1_500)
        _advance_intro(page, scene_dwell_ms=scene_dwell_ms)
        page.get_by_role("button", name="입장하기").click()
        # 문 열림 연출
        _pause(page, 1_800)
        page.wait_for_url("**/game/**", timeout=NAV_TIMEOUT_MS)
        _pause(page, 2_000)

    page.locator(".boot-screen").wait_for(state="detached", timeout=NAV_TIMEOUT_MS)
    briefing = page.get_by_role("dialog", name="수사 브리핑")
    briefing.wait_for(timeout=NAV_TIMEOUT_MS)
    _pause(page, 2_500)
    page.get_by_role("button", name="START").click()
    page.locator(".main-stage .ops-col").wait_for(timeout=30_000)
    _pause(page, 1_500)

    # 사이드바: 게임 방법 (+ 선택적으로 사건개요 — 풀 스토리)
    # 주의: 「메뉴」는 토글 — 연달아 누르면 닫힘
    page.get_by_role("button", name="메뉴").click()
    _pause(page, 900)
    page.get_by_role("button", name="게임 방법").click()
    page.get_by_role("dialog", name="게임 방법").wait_for(timeout=15_000)
    _pause(page, 3_500)
    page.get_by_role("dialog", name="게임 방법").get_by_role("button", name="확인").click()
    _pause(page, 700)

    if include_case_overview:
        # 사이드바가 닫혀 있으면만 다시 연다
        case_btn = page.get_by_role("button", name="사건개요")
        if not case_btn.is_visible():
            page.get_by_role("button", name="메뉴").click()
            _pause(page, 700)
            case_btn = page.get_by_role("button", name="사건개요")
        case_btn.click()
        page.get_by_role("dialog", name="사건개요").wait_for(timeout=15_000)
        _pause(page, 3_500)
        page.get_by_role("dialog", name="사건개요").get_by_role("button", name="확인").click()
        _pause(page, 700)

    close_sb = page.get_by_role("button", name="사이드바 닫기")
    if close_sb.count() and close_sb.is_visible():
        close_sb.click()
    _pause(page, 900)

    _ask(
        page,
        "김팀장",
        "그날 밤 어디에 있었습니까?",
        type_delay_ms=type_delay_ms,
        after_reply_ms=after_reply_ms,
    )
    _desk_clue(page, "법인카드")

    _ask(
        page,
        "박신입",
        "슬랙으로 서버실 관련 메시지를 보낸 적 있습니까?",
        type_delay_ms=type_delay_ms,
        after_reply_ms=after_reply_ms,
    )
    _desk_clue(page, "슬랙 DM")

    _ask(
        page,
        "이대리",
        "라운지에서 노트북으로 무엇을 하고 있었습니까?",
        type_delay_ms=type_delay_ms,
        after_reply_ms=after_reply_ms,
    )
    _desk_clue(page, "네트워크")

    page.get_by_role("button", name="최종 지목").click()
    _pause(page, 1_000)
    page.get_by_label("지목 대상").select_option(label="이대리")
    _pause(page, 800)
    page.locator('.accuse-inventory .inv-slot[title="ev_net_01"]').click()
    _pause(page, 600)
    page.locator('.accuse-inventory .inv-slot[title="ev_card_03"]').click()
    _pause(page, 1_200)
    page.get_by_role("button", name="지목 확정").click()
    result = page.get_by_role("dialog", name="지목 결과")
    result.get_by_text("진실이 밝혀졌습니다").wait_for(timeout=60_000)
    _pause(page, 2_500)
    result.get_by_role("button", name="확인").click()
    page.locator('.arrest-stamp img[alt="검거"]').wait_for(timeout=15_000)
    _pause(page, 3_500)


def main() -> int:
    _require_playwright()
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description="PRESENTATION 컷 B Playwright 자동 녹화")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--skip-intro", action="store_true")
    ap.add_argument("--slow-mo", type=int, default=DEFAULT_SLOW_MO)
    ap.add_argument(
        "--scene-dwell-ms",
        type=int,
        default=DEFAULT_SCENE_DWELL_MS,
        help="인트로 씬당 최소 체류(ms)",
    )
    ap.add_argument(
        "--type-delay-ms",
        type=int,
        default=DEFAULT_TYPE_DELAY_MS,
        help="심문 타자 간격(ms)",
    )
    ap.add_argument(
        "--after-reply-ms",
        type=int,
        default=DEFAULT_AFTER_REPLY_MS,
        help="용의자 답변 후 읽기 대기(ms)",
    )
    ap.add_argument(
        "--include-case-overview",
        action="store_true",
        default=True,
        help="사이드바 사건개요도 열기 (기본 ON)",
    )
    ap.add_argument(
        "--no-case-overview",
        action="store_true",
        help="사건개요 생략",
    )
    ap.add_argument(
        "--intro-only",
        action="store_true",
        help="인트로(+선택적 문 열림)만 녹화 — 편집용",
    )
    ap.add_argument(
        "--no-enter",
        action="store_true",
        help="--intro-only 시 입장하기 클릭 생략 (CTA에서 종료)",
    )
    ap.add_argument(
        "--legacy-webm",
        action="store_true",
        help="Playwright 저화질 webm도 함께 저장 (기본은 CDP HQ만)",
    )
    ap.add_argument(
        "--no-brighten",
        action="store_true",
        help="녹화용 화면 밝기 보정 끄기 (기본은 약간 밝게)",
    )
    ap.add_argument(
        "--keep-frames",
        action="store_true",
        help="frames_hq JPEG 시퀀스 유지 (기본은 MP4 후 삭제)",
    )
    args = ap.parse_args()
    include_case = bool(args.include_case_overview) and not args.no_case_overview
    intro_only = bool(args.intro_only)
    # 인트로 전용은 기본 체류를 더 길게
    scene_dwell = args.scene_dwell_ms
    if intro_only and args.scene_dwell_ms == DEFAULT_SCENE_DWELL_MS:
        scene_dwell = 7_000

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = "intro" if intro_only else "cut_b"
    out_dir = args.out_dir or (ROOT / "runs" / "demo_record" / f"{prefix}_{stamp}")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames_hq"

    print(f"base_url={args.base_url}")
    print(f"out_dir={out_dir}")
    print(
        f"mode={'intro_only' if intro_only else 'cut_b'} "
        f"scene_dwell={scene_dwell} type_delay={args.type_delay_ms} "
        f"after_reply={args.after_reply_ms} case_overview={include_case} "
        f"capture=cdp_hq"
    )

    t0 = time.time()
    hq = None
    hq_fps = 12.0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, slow_mo=args.slow_mo)
        ctx_kwargs = {
            "viewport": {"width": RECORD_W, "height": RECORD_H},
            "device_scale_factor": 1,
            "locale": "ko-KR",
        }
        if args.legacy_webm:
            ctx_kwargs["record_video_dir"] = str(video_dir)
            ctx_kwargs["record_video_size"] = {"width": RECORD_W, "height": RECORD_H}
        context = browser.new_context(**ctx_kwargs)
        context.set_default_timeout(30_000)
        if not args.no_brighten:
            context.add_init_script(
                """
                (() => {
                  const apply = () => {
                    document.documentElement.style.filter =
                      'brightness(1.18) contrast(1.06) saturate(1.04)';
                  };
                  apply();
                  new MutationObserver(apply).observe(document.documentElement, {
                    childList: true, subtree: true
                  });
                })();
                """
            )
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        ok = False
        err = ""
        try:
            hq = _HqScreencast(page, frames_dir)
            hq.start()
            if intro_only:
                run_intro_only(
                    page,
                    base_url=args.base_url,
                    scene_dwell_ms=scene_dwell,
                    enter_door=not args.no_enter,
                )
            else:
                run_cut_b(
                    page,
                    base_url=args.base_url,
                    skip_intro=args.skip_intro,
                    scene_dwell_ms=scene_dwell,
                    type_delay_ms=args.type_delay_ms,
                    after_reply_ms=args.after_reply_ms,
                    include_case_overview=include_case,
                )
            ok = True
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            print(f"FAIL: {exc}", file=sys.stderr)
            try:
                page.screenshot(path=str(out_dir / "failure.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass
        finally:
            if hq is not None:
                hq_fps = hq.stop()
                print(f"hq_frames={hq.n} hq_fps≈{hq_fps:.1f}")
            context.close()
            browser.close()

    videos = sorted(video_dir.glob("*.webm")) if args.legacy_webm else []
    mp4_path = None
    if hq is not None and hq.n > 0:
        mp4_path = _encode_frames_mp4(
            frames_dir, out_dir / "cut_b_sharp.mp4", fps=hq_fps
        )
        if mp4_path and not args.keep_frames:
            import shutil

            shutil.rmtree(frames_dir, ignore_errors=True)
    elif videos:
        mp4_path = _encode_sharp_mp4(videos[0], out_dir / "cut_b_sharp.mp4")
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "cut": "intro_only" if intro_only else "B_full_pace",
        "ok": ok,
        "error": err or None,
        "elapsed_sec": round(time.time() - t0, 1),
        "viewport": f"{RECORD_W}x{RECORD_H}",
        "capture": "cdp_jpeg_hq",
        "hq_frames": getattr(hq, "n", 0),
        "hq_fps": round(hq_fps, 2),
        "scene_dwell_ms": scene_dwell,
        "type_delay_ms": args.type_delay_ms,
        "after_reply_ms": args.after_reply_ms,
        "include_case_overview": include_case,
        "intro_only": intro_only,
        "enter_door": (not args.no_enter) if intro_only else None,
        "videos": [
            str(v.relative_to(ROOT)) if str(v).startswith(str(ROOT)) else str(v) for v in videos
        ],
        "mp4": str(mp4_path.relative_to(ROOT)) if mp4_path else None,
        "note": "CDP JPEG HQ → cut_b_sharp.mp4(권장) · 구 webm은 뭉개짐",
    }
    (out_dir / "report.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    if mp4_path:
        print(f"mp4: {mp4_path}")
    elif videos:
        print(f"video: {videos[0]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
