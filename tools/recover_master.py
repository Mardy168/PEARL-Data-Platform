from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.master.manager import combine_and_validate_master, normalize_master_schema, validate_master_file
from src.utils.dates import CAMBODIA_TZ
from src.utils.excel import write_qa_workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover PEARL master from a historical backup and current master.")
    parser.add_argument("--backup", required=True, help="Path to historical pre-upgrade master CSV")
    parser.add_argument("--current", required=False, help="Path to current production master CSV")
    parser.add_argument("--output", default="data/master/PEARL_master_news_RECOVERED.csv")
    parser.add_argument("--qa", default="data/qa/PEARL_master_recovery_QA.xlsx")
    args = parser.parse_args()

    backup = normalize_master_schema(pd.read_csv(args.backup))
    current = normalize_master_schema(pd.read_csv(args.current)) if args.current and Path(args.current).exists() else pd.DataFrame()
    recovered = combine_and_validate_master(backup, current)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    recovered.to_csv(args.output, index=False, encoding="utf-8-sig")
    validation = validate_master_file(args.output)
    stats = {
        "Recovery Time Cambodia": datetime.now(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "Historical Backup Records": len(backup),
        "Current Master Records": len(current),
        "Recovered Records": len(recovered),
        **{key.replace("_", " ").title(): value for key, value in validation.items()},
        "Production Master Updated": "NO - review this file first",
    }
    write_qa_workbook(stats, pd.DataFrame(), args.qa)
    print(f"Recovered master written to: {args.output}")
    print(f"Recovery QA written to: {args.qa}")


if __name__ == "__main__":
    main()
