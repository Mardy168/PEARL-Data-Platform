from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.utils.dates import add_published_columns, remove_timezone_columns
from src.utils.duplicate import deduplicate_articles
from src.utils.excel import write_excel

MASTER = Path("data/master/PEARL_master_news.csv")
QA_DIR = Path("data/qa")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    if not MASTER.exists():
        raise FileNotFoundError(MASTER)
    original = pd.read_csv(MASTER)
    dated = add_published_columns(original)
    invalid = dated[dated["published_dt_kh"].isna()].copy()
    valid = dated[dated["published_dt_kh"].notna()].copy()
    cleaned = deduplicate_articles(valid)
    backup = MASTER.with_name("PEARL_master_news_before_v2_cleanup.csv")
    original.to_csv(backup, index=False, encoding="utf-8-sig")
    remove_timezone_columns(cleaned).to_csv(MASTER, index=False, encoding="utf-8-sig")
    write_excel(remove_timezone_columns(invalid), str(QA_DIR / "PEARL_master_invalid_dates.xlsx"))
    with open(QA_DIR / "PEARL_master_cleanup_log.txt", "w", encoding="utf-8") as f:
        f.write(f"Original rows: {len(original)}\n")
        f.write(f"Invalid-date rows excluded: {len(invalid)}\n")
        f.write(f"Clean unique rows: {len(cleaned)}\n")
        f.write(f"True duplicates removed: {len(valid) - len(cleaned)}\n")
    print("Master cleanup completed.")

if __name__ == "__main__":
    main()
