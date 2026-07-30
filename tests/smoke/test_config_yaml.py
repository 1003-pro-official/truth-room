"""설정 YAML 예시가 파싱 가능한지 검증."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


@pytest.mark.parametrize(
    "name",
    [
        "ingest.yaml.example",
        "rag.yaml.example",
        "agent.yaml.example",
        "eval.yaml.example",
        "api.yaml.example",
    ],
)
def test_config_example_parses(name: str) -> None:
    path = CONFIGS / name
    assert path.exists(), f"missing {path}"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data is not None
