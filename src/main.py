from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from src.collectors.news import collect_news
from src.drive.upload import upload_file
from src.utils.config import load_keywords, OUTPUT_DIR
from src.utils.classify import classify_topic, source_group, relevance_score


def run_daily():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    keywords = load_keywords()
    out_dir = OUTPUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect_news(keywords["crops"])
    for row in rows:
        row["date_collected"] = today
        row["topic"] = classify_topic(f"{row.get('title','')} {row.get('summary','')}", keywords["topics"])
        row["source_group"] = source_group(row.get("title", ""), row.get("url", ""))
        row["relevance_score"] = relevance_score(row)
        row["citation"] = f"{row.get('title','')}. {row.get('source','')}. {row.get('url','')}"

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["url"]).sort_values(["crop", "source_group", "relevance_score"], ascending=[True, True, False])

    csv_path = out_dir / f"PEARL_daily_news_{today}.csv"
    xlsx_path = out_dir / f"PEARL_daily_news_{today}.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)

    upload_file(str(csv_path), csv_path.name)
    upload_file(str(xlsx_path), xlsx_path.name)
    print("Daily collection completed.")


if __name__ == "__main__":
    run_daily()
