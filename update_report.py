#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runs/ingest · runs/rag · runs/agent · runs/eval 산출물을 스캔하여 README.md를 자동 갱신합니다.

갱신 블록:
  - report:auto:ingest
  - report:auto:rag
  - report:auto:agent
  - report:auto:eval
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_REPORT = ROOT / "README.md"

INGEST_START = "<!-- report:auto:ingest -->"
INGEST_END = "<!-- /report:auto:ingest -->"
RAG_START = "<!-- report:auto:rag -->"
RAG_END = "<!-- /report:auto:rag -->"
AGENT_START = "<!-- report:auto:agent -->"
AGENT_END = "<!-- /report:auto:agent -->"
EVAL_START = "<!-- report:auto:eval -->"
EVAL_END = "<!-- /report:auto:eval -->"

# 모드별 대표 쿼리의 목표 evidence (Hit@k 판정)
TARGET_EVIDENCE = {
    "baseline": "ev_card_03",
    "advanced": "ev_net_01",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="runs/ 결과를 README.md에 반영합니다.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def replace_block(content: str, start: str, end: str, body: str) -> str:
    block = f"{start}\n{body}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(content):
        return pattern.sub(block, content, count=1)
    print(f"[경고] 마커를 찾지 못함: {start}", file=sys.stderr)
    return content


def hit_rank(hits: list[dict[str, Any]], target: str) -> int | None:
    for i, h in enumerate(hits, start=1):
        if h.get("evidence_id") == target:
            return i
    return None


def format_hit_cell(rank: int | None, target: str, top_k: int = 5) -> str:
    if rank is None:
        return f"❌ `{target}` ∉ top-{top_k}"
    if rank == 1:
        return f"✅ `{target}` top-1"
    if rank <= top_k:
        return f"✅ `{target}` ∈ top-{top_k} (rank {rank})"
    return f"❌ `{target}` rank {rank}"


def build_ingest_body(summary: dict[str, Any], updated_at: str) -> str | None:
    if not summary:
        return None
    n_chunks = int(summary.get("n_chunks", 0))
    with_eid = int(summary.get("with_evidence_id", 0))
    by_source = summary.get("by_source") or {}
    lines = [
        f"- **갱신:** `runs/ingest/summary.yaml` · {updated_at}",
        f"- **총 청크:** **{n_chunks}**",
        f"- **evidence_id 포함 청크:** **{with_eid}** "
        f"(`ev_card_03` · `ev_msg_12` · `ev_log_07` · `ev_net_01`)",
        "",
        "| source_type | 청크 수 |",
        "| :--- | ---: |",
    ]
    total = 0
    for source, count in by_source.items():
        lines.append(f"| {source} | {int(count)} |")
        total += int(count)
    lines.append(f"| **합계** | **{total or n_chunks}** |")
    return "\n".join(lines)


def build_rag_row(payload: dict[str, Any]) -> str | None:
    if not payload:
        return None
    mode = str(payload.get("mode", "?"))
    query = str(payload.get("query", "—")).replace("|", "\\|")
    hits = payload.get("hits") or []
    top1 = hits[0].get("evidence_id") if hits else None
    top1_text = f"`{top1}`" if top1 else "—"
    if top1 and mode == "baseline" and top1 != TARGET_EVIDENCE.get("baseline"):
        top1_text = f"`{top1}` (비목표)"
    if top1 and mode == "advanced" and top1 == TARGET_EVIDENCE.get("advanced"):
        top1_text = f"**`{top1}`**"

    target = TARGET_EVIDENCE.get(mode, "")
    rank = hit_rank(hits, target) if target else None
    hit_cell = format_hit_cell(rank, target) if target else "—"

    if mode == "baseline":
        pipe = "**Baseline**"
        mode_label = "dense only"
        note = "관련 카드가 뒤로 밀림" if rank and rank > 1 else "목표 증거 회수"
    else:
        pipe = "**Advanced**"
        mode_label = "hybrid RRF + rerank"
        note = "결정타 증거 정밀 회수" if rank == 1 else "순위 재확인 필요"

    return (
        f"| {pipe} | {mode_label} | `{query}` | {top1_text} | {hit_cell} | {note} |"
    )


def build_rag_body(
    baseline: dict[str, Any],
    advanced: dict[str, Any],
    updated_at: str,
) -> str | None:
    rows = [
        build_rag_row(baseline) if baseline else None,
        build_rag_row(advanced) if advanced else None,
    ]
    rows = [r for r in rows if r]
    if not rows:
        return None
    lines = [
        f"| 파이프라인 | 모드 | 대표 쿼리 | top-1 evidence | Hit@5 (목표 ID) | 비고 |",
        f"| :--- | :--- | :--- | :--- | :---: | :--- |",
        *rows,
        "",
        f"- **자동 반영:** {updated_at}",
    ]
    return "\n".join(lines)


def build_agent_body(smoke: dict[str, Any], updated_at: str) -> str | None:
    if not smoke:
        return None
    state = smoke.get("state") or {}
    eids = state.get("evidence_ids") or []
    pressure = state.get("pressure") or {}
    tools = state.get("tool_results") or []
    tool_note = "—"
    if tools:
        t0 = tools[0]
        tool_note = (
            f"`{t0.get('tool')}`({t0.get('location', '—')}) → "
            f"status `{t0.get('status', '—')}`"
        )
        if t0.get("reason"):
            tool_note += f" ({t0['reason']})"

    nodes = [t.get("node") for t in (smoke.get("trace") or []) if t.get("node")]
    node_path = " → ".join(nodes) if nodes else "—"

    lines = [
        f"- **상태:** `{smoke.get('status', '—')}` · case `{smoke.get('case_id', '—')}` · {updated_at}",
        f"- **목표 입력:** 김팀장 알리바이 검증 + CCTV",
        f"- **수집 evidence:** {', '.join(f'`{e}`' for e in eids) or '—'}",
        f"- **clue / pressure:** {state.get('clue_count', '—')} / "
        f"{pressure.get('suspect_a', pressure) if isinstance(pressure, dict) else pressure}",
        f"- **툴:** {tool_note}",
        f"- **노드:** `{node_path}`",
    ]
    return "\n".join(lines)


def build_eval_body(report: dict[str, Any], updated_at: str) -> str | None:
    metrics = report.get("metrics") or {}
    if not metrics:
        return None

    def fmt(key: str) -> str:
        val = metrics.get(key)
        if val is None:
            return "—"
        return f"**{float(val):.3f}**"

    lines = [
        "| 메트릭 | 값 | 해석 |",
        "| :--- | ---: | :--- |",
        f"| **Faithfulness** | {fmt('faithfulness')} | "
        "답변 토큰이 제공 컨텍스트에 근거하는 비율 (로컬 overlap) |",
        f"| **Context Precision** | {fmt('context_precision')} | "
        "검색 top-k 중 골드 근거와 맞는 비율 |",
        f"| **Context Recall** | {fmt('context_recall')} | "
        "골드 evidence_id가 검색 결과에 포함되는 비율 |",
        f"| **Answer Relevancy** | {fmt('answer_relevancy')} | "
        "질문–답변 토큰 겹침 proxy |",
        "",
        f"- **자동 반영:** {updated_at} · sample_size={report.get('sample_size', '—')} · "
        f"backend=`{report.get('backend', '—')}`",
    ]
    return "\n".join(lines)


def apply_report_updates(content: str) -> tuple[str, list[str]]:
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes: list[str] = []
    updated = content

    ingest = load_yaml(ROOT / "runs" / "ingest" / "summary.yaml")
    body = build_ingest_body(ingest, updated_at)
    if body:
        updated = replace_block(updated, INGEST_START, INGEST_END, body)
        notes.append(f"ingest: n_chunks={ingest.get('n_chunks')}")
    else:
        notes.append("ingest: summary 없음 — 스킵")

    baseline = load_json(ROOT / "runs" / "rag" / "exp_baseline" / "last_query.json")
    advanced = load_json(ROOT / "runs" / "rag" / "exp_advanced" / "last_query.json")
    body = build_rag_body(baseline, advanced, updated_at)
    if body:
        updated = replace_block(updated, RAG_START, RAG_END, body)
        notes.append(
            f"rag: baseline={'ok' if baseline else '—'} · advanced={'ok' if advanced else '—'}"
        )
    else:
        notes.append("rag: exp_*/last_query.json 없음 — 스킵")

    smoke = load_json(ROOT / "runs" / "agent" / "smoke.json")
    body = build_agent_body(smoke, updated_at)
    if body:
        updated = replace_block(updated, AGENT_START, AGENT_END, body)
        notes.append(f"agent: status={smoke.get('status')}")
    else:
        notes.append("agent: smoke.json 없음 — 스킵")

    eval_report = load_json(ROOT / "runs" / "eval" / "report.json")
    body = build_eval_body(eval_report, updated_at)
    if body:
        updated = replace_block(updated, EVAL_START, EVAL_END, body)
        m = eval_report.get("metrics") or {}
        notes.append(f"eval: faithfulness={m.get('faithfulness')}")
    else:
        notes.append("eval: report.json 없음 — 스킵")

    return updated, notes


def main() -> None:
    args = parse_args()
    report_path = args.report.resolve()
    if not report_path.exists():
        raise SystemExit(f"리포트 파일을 찾을 수 없습니다: {report_path}")

    original = report_path.read_text(encoding="utf-8")
    updated, notes = apply_report_updates(original)
    for note in notes:
        print(note)

    if updated == original:
        print("변경 사항이 없습니다.")
        return

    if args.dry_run:
        print("\n--- dry-run (변경된 블록만 반영된 전체 길이) ---")
        print(f"chars: {len(original)} → {len(updated)}")
        return

    report_path.write_text(updated, encoding="utf-8")
    print(f"README.md 갱신 완료: {report_path}")


if __name__ == "__main__":
    main()
