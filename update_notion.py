#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
README.md를 읽어 Notion 페이지를 자동 업데이트합니다.

파이프라인 (기본):
  1. update_report.py (runs/ → README.md 반영)
  2. Notion 페이지 전체 교체 + 로컬 이미지 업로드

환경 변수:
  NOTION_TOKEN   - Notion Integration API 토큰 (필수)
  NOTION_PAGE_ID - 업데이트할 페이지 ID (필수)

사용 예:
  export NOTION_TOKEN="ntn_..."
  export NOTION_PAGE_ID="..."
  python3 update_notion.py
  python3 update_notion.py --skip-report-sync
  python3 update_notion.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

BLOCK_CHUNK_SIZE = 100
NOTION_FILE_UPLOAD_VERSION = "2025-09-03"
ROOT = Path(__file__).resolve().parent
IMAGE_MD_PATTERN = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
BULLET_LINE_PATTERN = re.compile(r"^(\s*)[-*]\s+(.*)$")

# Notion code block language allowlist aliases
_NOTION_LANG_ALIAS = {
    "": "plain text",
    "text": "plain text",
    "txt": "plain text",
    "plaintext": "plain text",
    "plain-text": "plain text",
    "sh": "shell",
    "zsh": "shell",
    "bash": "bash",
    "yml": "yaml",
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "md": "markdown",
    "dockerfile": "docker",
}


def _notion_code_language(lang: str) -> str:
    raw = (lang or "").strip().lower()
    return _NOTION_LANG_ALIAS.get(raw, raw or "plain text")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="README.md 내용을 Notion 페이지에 반영합니다.")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("README.md"),
        help="업로드할 마크다운 리포트 경로 (기본: README.md)",
    )
    parser.add_argument(
        "--page-id",
        type=str,
        default=None,
        help="Notion 페이지 ID (미지정 시 NOTION_PAGE_ID 환경 변수 사용)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Notion API 호출 없이 파싱 결과만 확인",
    )
    parser.add_argument(
        "--skip-report-sync",
        action="store_true",
        help="update_report.py 동기화 건너뛰기 (README.md 원문만 업로드)",
    )
    return parser.parse_args()


def format_page_id(page_id: str) -> str:
    clean = page_id.replace("-", "").strip()
    if len(clean) != 32:
        raise ValueError(f"유효하지 않은 페이지 ID입니다: {page_id}")
    return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"


def strip_html_comments(content: str) -> str:
    return HTML_COMMENT_PATTERN.sub("", content)


def strip_leading_document_title(content: str) -> str:
    lines = content.splitlines()
    if not lines or not lines[0].strip().startswith("# "):
        return content

    idx = 1
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            idx += 1
            continue
        if stripped == "---":
            idx += 1
        break

    return "\n".join(lines[idx:]).lstrip("\n")


def upload_local_image(token: str, image_path: Path) -> str:
    content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_FILE_UPLOAD_VERSION,
        "Content-Type": "application/json",
    }
    create_resp = requests.post(
        "https://api.notion.com/v1/file_uploads",
        headers=headers,
        json={"filename": image_path.name, "content_type": content_type},
        timeout=60,
    )
    create_resp.raise_for_status()
    payload = create_resp.json()
    upload_id = payload["id"]
    upload_url = payload.get("upload_url") or f"https://api.notion.com/v1/file_uploads/{upload_id}/send"

    send_headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_FILE_UPLOAD_VERSION,
    }
    with image_path.open("rb") as file_obj:
        send_resp = requests.post(
            upload_url,
            headers=send_headers,
            files={"file": (image_path.name, file_obj, content_type)},
            timeout=120,
        )
    send_resp.raise_for_status()
    return upload_id


def _image_block_external(url: str, caption: str = "") -> dict:
    block: dict = {
        "object": "block",
        "type": "image",
        "image": {"type": "external", "external": {"url": url}},
    }
    if caption:
        block["image"]["caption"] = [{"type": "text", "text": {"content": caption}}]
    return block


def _image_block_upload(upload_id: str, caption: str = "") -> dict:
    block: dict = {
        "object": "block",
        "type": "image",
        "image": {"type": "file_upload", "file_upload": {"id": upload_id}},
    }
    if caption:
        block["image"]["caption"] = [{"type": "text", "text": {"content": caption}}]
    return block


def _pending_image_block(src: str, caption: str) -> dict:
    return {"_pending_image": src, "_caption": caption}


def resolve_image_blocks(token: str, blocks: list[dict], root: Path) -> list[dict]:
    resolved: list[dict] = []
    for block in blocks:
        if "_pending_image" not in block:
            resolved.append(block)
            continue

        src = block["_pending_image"]
        caption = block.get("_caption", "")

        if src.startswith(("http://", "https://")):
            resolved.append(_image_block_external(src, caption))
            continue

        image_path = (root / src).resolve()
        if not image_path.exists():
            print(f"[경고] 이미지 파일 없음 — 텍스트로 대체: {src}", file=sys.stderr)
            resolved.append(_block("paragraph", parse_inline_rich_text(f"_(이미지 없음: {src})_")))
            continue

        try:
            upload_id = upload_local_image(token, image_path)
            resolved.append(_image_block_upload(upload_id, caption))
            print(f"이미지 업로드 완료: {image_path.name}")
        except requests.RequestException as exc:
            print(f"[경고] 이미지 업로드 실패 ({image_path.name}): {exc}", file=sys.stderr)
            resolved.append(
                _block("paragraph", parse_inline_rich_text(f"_(이미지 업로드 실패: {src})_"))
            )
    return resolved


def parse_inline_rich_text(text: str) -> list[dict]:
    parts: list[dict] = []
    pattern = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")
    cursor = 0

    for match in pattern.finditer(text):
        if match.start() > cursor:
            parts.append(_text_segment(text[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("**"):
            parts.append(_text_segment(token[2:-2], bold=True))
        else:
            parts.append(_text_segment(token[1:-1], code=True))
        cursor = match.end()

    if cursor < len(text):
        parts.append(_text_segment(text[cursor:]))
    return parts or [_text_segment("")]


def _text_segment(content: str, bold: bool = False, code: bool = False) -> dict:
    segment: dict = {"type": "text", "text": {"content": content}}
    annotations: dict[str, bool] = {}
    if bold:
        annotations["bold"] = True
    if code:
        annotations["code"] = True
    if annotations:
        segment["annotations"] = annotations
    return segment


def _block(block_type: str, rich_text: list[dict], **extra) -> dict:
    payload = {"rich_text": rich_text, **extra}
    return {"object": "block", "type": block_type, block_type: payload}


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _parse_table_rows(lines: list[str]) -> dict | None:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(cells)

    if not rows:
        return None

    table_width = max(len(row) for row in rows)
    normalized = [row + [""] * (table_width - len(row)) for row in rows]
    table_rows = []
    for row in normalized:
        cells = [parse_inline_rich_text(cell) for cell in row]
        table_rows.append(
            {
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": cells},
            }
        )

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": table_width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _is_bullet_line(line: str) -> bool:
    return bool(BULLET_LINE_PATTERN.match(line))


def _nest_bullet_blocks(items: list[tuple[int, str]]) -> list[dict]:
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []

    for indent, text in items:
        block: dict = {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": parse_inline_rich_text(text),
                "children": [],
            },
        }

        while stack and indent <= stack[-1][0]:
            stack.pop()

        if stack:
            stack[-1][1]["bulleted_list_item"]["children"].append(block)
        else:
            roots.append(block)

        stack.append((indent, block))

    def _strip_empty_children(node: dict) -> None:
        children = node["bulleted_list_item"].get("children", [])
        if not children:
            node["bulleted_list_item"].pop("children", None)
        else:
            for child in children:
                _strip_empty_children(child)

    for root in roots:
        _strip_empty_children(root)

    return roots


def markdown_to_notion_blocks(markdown: str) -> list[dict]:
    lines = markdown.splitlines()
    blocks: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            blocks.append(_divider_block())
            i += 1
            continue

        if stripped.startswith("# "):
            blocks.append(_block("heading_1", parse_inline_rich_text(stripped[2:].strip())))
            i += 1
            continue

        if stripped.startswith("## "):
            blocks.append(_block("heading_2", parse_inline_rich_text(stripped[3:].strip())))
            i += 1
            continue

        if stripped.startswith("### "):
            blocks.append(_block("heading_3", parse_inline_rich_text(stripped[4:].strip())))
            i += 1
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(_block("quote", parse_inline_rich_text(" ".join(quote_lines))))
            continue

        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            table_block = _parse_table_rows(table_lines)
            if table_block:
                blocks.append(table_block)
            continue

        if _is_bullet_line(line):
            items: list[tuple[int, str]] = []
            while i < len(lines) and _is_bullet_line(lines[i]):
                match = BULLET_LINE_PATTERN.match(lines[i])
                assert match is not None
                items.append((len(match.group(1)), match.group(2).strip()))
                i += 1
            blocks.extend(_nest_bullet_blocks(items))
            continue

        image_match = IMAGE_MD_PATTERN.match(stripped)
        if image_match:
            caption, src = image_match.groups()
            blocks.append(_pending_image_block(src.strip(), caption.strip()))
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [_text_segment("\n".join(code_lines)[:2000])],
                        "language": _notion_code_language(lang),
                    },
                }
            )
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt == "---"
                or nxt.startswith(">")
                or nxt.startswith("|")
                or nxt.startswith("```")
                or _is_bullet_line(lines[i])
            ):
                break
            paragraph_lines.append(nxt)
            i += 1
        blocks.append(_block("paragraph", parse_inline_rich_text(" ".join(paragraph_lines))))

    return blocks


def chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def archive_block_tree(notion: Client, block_id: str) -> None:
    cursor = None
    while True:
        response = notion.blocks.children.list(block_id=block_id, start_cursor=cursor)
        for child in response["results"]:
            if child.get("has_children"):
                archive_block_tree(notion, child["id"])
            notion.blocks.delete(block_id=child["id"])
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")


def append_blocks(notion: Client, page_id: str, blocks: list[dict]) -> None:
    for chunk in chunked(blocks, BLOCK_CHUNK_SIZE):
        notion.blocks.children.append(block_id=page_id, children=chunk)


def update_page_title(notion: Client, page_id: str, title: str) -> None:
    page = notion.pages.retrieve(page_id=page_id)
    title_key = next(
        (key for key, value in page["properties"].items() if value["type"] == "title"),
        None,
    )
    if not title_key:
        return
    notion.pages.update(
        page_id=page_id,
        properties={title_key: {"title": [{"text": {"content": title}}]}},
    )


def load_eval_metrics_note() -> str:
    path = ROOT / "runs" / "eval" / "report.json"
    if not path.is_file():
        return "eval 결과 없음"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "eval 결과 파싱 실패"
    m = data.get("metrics") or {}
    if not m:
        return "eval metrics 없음"
    return (
        f"Faithfulness={float(m.get('faithfulness', 0)):.3f} · "
        f"C-Precision={float(m.get('context_precision', 0)):.3f} · "
        f"C-Recall={float(m.get('context_recall', 0)):.3f}"
    )


def sync_report_md() -> None:
    print("README.md 동기화 중 (update_report.py)...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "update_report.py")],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(
            "[경고] update_report.py 실패 — README.md 원문만 Notion에 업로드합니다.",
            file=sys.stderr,
        )


def main() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
    args = parse_args()

    token = os.getenv("NOTION_TOKEN")
    page_id_raw = args.page_id or os.getenv("NOTION_PAGE_ID")
    if not token:
        raise SystemExit(
            "NOTION_TOKEN 환경 변수를 설정해 주세요.\n"
            f"  → 프로젝트 루트에 `.env` 파일을 만드세요 (`.env.example`을 복사).\n"
            f"  → 현재 `.env` 존재 여부: {env_path.exists()}\n"
            "  → 참고: `.env.example`에만 입력하면 읽히지 않습니다."
        )
    if not page_id_raw:
        raise SystemExit("NOTION_PAGE_ID 환경 변수 또는 --page-id 옵션을 설정해 주세요.")
    report_path = (ROOT / args.report).resolve() if not args.report.is_absolute() else args.report
    if not report_path.exists():
        raise SystemExit(f"리포트 파일을 찾을 수 없습니다: {report_path}")

    if not args.skip_report_sync:
        sync_report_md()

    page_id = format_page_id(page_id_raw)
    content = report_path.read_text(encoding="utf-8")
    content = strip_html_comments(content)

    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    page_title = title_match.group(1).strip() if title_match else "진실의 방 리포트"
    content = strip_leading_document_title(content)

    updated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    header = f"> 마지막 자동 업데이트: {updated_at} | {load_eval_metrics_note()}\n\n"
    blocks = markdown_to_notion_blocks(header + content)

    print(f"페이지 ID: {page_id}")
    print(f"생성 블록 수: {len(blocks)}")
    print(f"메트릭 요약: {load_eval_metrics_note()}")

    if args.dry_run:
        pending = sum(1 for b in blocks if "_pending_image" in b)
        print(f"이미지 블록(업로드 예정): {pending}개")
        print("dry-run 모드 — Notion API를 호출하지 않았습니다.")
        return

    notion = Client(auth=token)
    try:
        blocks = resolve_image_blocks(token, blocks, ROOT)
        archive_block_tree(notion, page_id)
        append_blocks(notion, page_id, blocks)
        update_page_title(notion, page_id, page_title)
    except APIResponseError as exc:
        raise SystemExit(
            "Notion API 오류가 발생했습니다. "
            "토큰·페이지 ID·Integration 연결(페이지 공유)을 확인해 주세요.\n"
            f"상세: {exc}"
        ) from exc

    print("Notion 페이지 업데이트가 완료되었습니다.")


if __name__ == "__main__":
    main()
