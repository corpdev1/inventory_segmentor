"""Simple on-disk checkpointing for long dump runs.

We store per-artifact classification outputs so a run can resume after transient
API/network failures without reprocessing already-classified artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def checkpoint_path_for_output(output_path: str) -> Path:
    out = Path(output_path).expanduser().resolve()
    return out.with_suffix(out.suffix + ".checkpoint.jsonl")


def load_checkpoint(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}
    by_id: dict[int, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            rid = obj.get("row_id")
            if rid is None:
                continue
            try:
                rid_i = int(rid)
            except Exception:
                continue
            by_id[rid_i] = obj
    return by_id


def append_checkpoint(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

