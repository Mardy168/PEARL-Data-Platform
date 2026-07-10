from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.drive.drive import download_file_by_name, upload_file
from src.master.manager import (
    MASTER_FILENAME,
    combine_and_validate_master,
    load_master_safely,
    normalize_master_schema,
    save_master_transaction,
    validate_master_file,
)
from src.utils.excel import write_qa_workbook

RECOVERY_INPUT = os.getenv("RECOVERY_INPUT_FILENAME", "PEARL_master_news_RECOVERY_INPUT.csv")
MASTER_PATH = Path("data/master") / MASTER_FILENAME
INPUT_PATH = Path("data/master") / RECOVERY_INPUT
RECOVERED_PATH = Path("data/master/PEARL_master_news_RECOVERED_REVIEW.csv")
QA_PATH = Path("data/qa/PEARL_master_recovery_QA.xlsx")


def main() -> None:
    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not download_file_by_name(RECOVERY_INPUT, str(INPUT_PATH), require_unique=True):
        raise FileNotFoundError(f"Recovery input {RECOVERY_INPUT!r} was not found in the configured Drive folder.")

    state = load_master_safely(MASTER_PATH, create_backup=True)
    historical = normalize_master_schema(pd.read_csv(INPUT_PATH))
    recovered = combine_and_validate_master(historical, state.dataframe)
    recovered.to_csv(RECOVERED_PATH, index=False, encoding="utf-8-sig")
    validation = validate_master_file(RECOVERED_PATH)

    stats = {
        "Historical Input Records": len(historical),
        "Current Production Records": state.record_count,
        "Recovered Records": len(recovered),
        "Production Backup": state.backup_name,
        **{key.replace("_", " ").title(): value for key, value in validation.items()},
        "Safety Requirement": "Recovered total must be >= historical input total",
    }
    write_qa_workbook(stats, pd.DataFrame(), str(QA_PATH))
    upload_file(str(RECOVERED_PATH), RECOVERED_PATH.name, replace=True)
    upload_file(str(QA_PATH), QA_PATH.name, replace=True)

    if len(recovered) < len(historical):
        raise RuntimeError("Recovery safety check failed. Production master was not updated.")
    save_master_transaction(state, recovered, local_path=MASTER_PATH)
    print(f"Production master safely recovered to {len(recovered)} records.")


if __name__ == "__main__":
    main()
