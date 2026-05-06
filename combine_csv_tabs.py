"""Combine "exported sheets" CSVs back into a single multi-sheet .xlsx.

Some spreadsheet tools export each tab as a separate CSV named like:
  "Company X_Data_Inventory.xlsx - Operations & HR.csv"

This script merges those CSVs into one workbook with one sheet per CSV.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


def _safe_sheet_name(name: str) -> str:
    # Excel sheet name constraints: <= 31 chars; cannot contain : \ / ? * [ ]
    cleaned = re.sub(r"[:\\/?*\[\]]+", " ", name).strip()
    return (cleaned or "Sheet")[:31]


def _infer_sheet_name(csv_path: Path) -> str:
    stem = csv_path.stem  # drops ".csv"
    # common export format: "<workbook>.xlsx - <sheet>"
    if " - " in stem:
        stem = stem.split(" - ", 1)[1].strip()
    return _safe_sheet_name(stem)


def combine_csv_tabs(csv_paths: list[str], output_xlsx: str) -> None:
    out_path = Path(output_xlsx).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for p in csv_paths:
            csv_path = Path(p).expanduser().resolve()
            df = pd.read_csv(csv_path)
            sheet = _infer_sheet_name(csv_path)
            # Ensure uniqueness
            base = sheet
            i = 2
            while sheet in seen:
                suffix = f" {i}"
                sheet = (base[: 31 - len(suffix)] + suffix)[:31]
                i += 1
            seen.add(sheet)
            df.to_excel(writer, index=False, sheet_name=sheet)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage:\n"
            "  python combine_csv_tabs.py OUTPUT.xlsx INPUT1.csv INPUT2.csv ...\n",
            file=sys.stderr,
        )
        return 2
    output = argv[1]
    inputs = argv[2:]
    combine_csv_tabs(inputs, output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

