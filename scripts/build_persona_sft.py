#!/usr/bin/env python3
"""scripts/build_persona_sft.py — 소량 페르소나 SFT JSONL 생성 (대규모 FT 아님)

OpenAI fine-tuning messages 형식.
출력: data/sft/persona_sft.jsonl · data/sft/manifest.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.persona_prompt import render_suspect_prompt  # noqa: E402

PERSONAS = [
    ROOT / "data" / "personas" / "suspect_a.yaml",
    ROOT / "data" / "personas" / "suspect_b.yaml",
    ROOT / "data" / "personas" / "suspect_c.yaml",
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# (질문, 기대 행동 태그, 모범 답변 템플릿 키)
BANK: list[tuple[str, str, str]] = [
    ("그날 밤 어디에 있었습니까?", "alibi_hold", "alibi"),
    ("서버실에 들어갔습니까?", "deny_crime", "deny_server"),
    ("알리바이를 증명할 수 있습니까?", "alibi_hold", "prove"),
    ("다른 용의자를 의심합니까?", "no_accuse", "deflect"),
    ("당신이 범인입니까?", "deny_crime", "not_culprit"),
    ("법인카드 룸살롱 결제 내역(ev_card_03)을 봤습니다. 설명하세요.", "evidence_react", "card"),
    ("라운지 Wi-Fi 100GB 전송(ev_net_01) 기록입니다.", "evidence_react", "net"),
    ("슬랙 DM에 서버실 침입 정황(ev_msg_12)이 있습니다.", "evidence_react", "msg"),
    ("출입 로그 23시 지문(ev_log_07)은 어떻게 된 겁니까?", "evidence_react", "log"),
    ("스트레스를 받고 있는 것 같군요.", "style", "stress"),
]


def _answer(persona: dict[str, Any], tag: str, kind: str) -> str:
    name = persona.get("name") or persona.get("id")
    sid = persona.get("id")
    is_c = str((persona.get("prompt_vars") or {}).get("is_culprit", "")).lower() == "true"
    alibi = str((persona.get("prompt_vars") or {}).get("주장_알리바이") or persona.get("alibi") or "")
    style = str((persona.get("prompt_vars") or {}).get("말투_특징") or "")

    if kind == "alibi":
        return f"{alibi}. 그 이상은 말씀드릴 게 없습니다."
    if kind == "deny_server":
        return "서버실에는 가지 않았습니다. 제 알리바이를 확인해 보십시오."
    if kind == "prove":
        return f"말씀드린 대로입니다. {alibi}"
    if kind == "deflect":
        return "다른 분을 함부로 단정하진 않겠습니다. 저는 제 일정만 말할 수 있습니다."
    if kind == "not_culprit":
        if is_c:
            return "근거 없이 몰아붙이지 마십시오. 라운지에 있었습니다."
        return "저는 범인이 아닙니다. 그날 그 자리에도 없었습니다."
    if kind == "card":
        if sid == "suspect_a":
            return "에헴… 그 시간엔 룸살롱에 있었습니다. 그래도 파일을 훔칠 수는 없습니다. 현장에 없었으니까요."
        return "제 카드 얘기가 아닙니다. 알리바이와 무관합니다."
    if kind == "net":
        if is_c:
            return "……그 MAC이 제 노트북이라면, 변명하기 어렵겠군요. 한 번에 다 말할 수는 없습니다."
        return "라운지 Wi-Fi 전송과는 무관합니다. 제 알리바이를 보십시오."
    if kind == "msg":
        if sid == "suspect_c":
            return "그 DM… 화장실에 있었다고요. 서버실 이야기는 과장입니다."
        return "슬랙 DM은 제가 확인할 수 있는 범위가 아닙니다."
    if kind == "log":
        if is_c:
            return "출입 로그에 제 이름이 없는 이유를 아시겠죠. 김팀장 쪽을 먼저 보십시오."
        return "지문 로그는 위조 가능성도 있습니다. 저는 그 자리에 없었습니다."
    if kind == "stress":
        return f"괜찮습니다. ({style}) 질문만 해 주십시오."
    return f"{name}: 더 말씀드릴 내용이 없습니다."


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in PERSONAS:
        persona = load_yaml(path)
        for stress in (15, 45, 80):
            mental = stress >= 71
            system = render_suspect_prompt(
                persona, stress_level=stress, mental_break=mental
            )
            for q, tag, kind in BANK:
                # 증거 질문만 stress 중고에서 강하게
                if kind in {"card", "net", "msg", "log"} and stress < 45:
                    continue
                ans = _answer(persona, tag, kind)
                rows.append(
                    {
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": ans},
                        ],
                        "meta": {
                            "suspect_id": persona.get("id"),
                            "stress_level": stress,
                            "tag": tag,
                            "kind": kind,
                        },
                    }
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/sft/persona_sft.jsonl")
    args = parser.parse_args()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            # OpenAI FT는 messages만 필요 — meta는 별도 라인 주석 대신 sidecar
            f.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
    meta_path = out.parent / "persona_sft_meta.jsonl"
    with meta_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r["meta"], ensure_ascii=False) + "\n")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_examples": len(rows),
        "path": str(out.relative_to(ROOT)),
        "meta_path": str(meta_path.relative_to(ROOT)),
        "purpose": "소량 페르소나 SFT (OpenAI FT messages) · 대규모 FT 아님",
        "suspects": 3,
        "note": "제출: scripts/openai_finetune_persona.py --submit (비용 발생)",
    }
    with (out.parent / "manifest.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
