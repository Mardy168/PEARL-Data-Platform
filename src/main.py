from datetime import datetime, timezone
import pandas as pd
from src.collectors.news import collect_news
from src.drive.upload import upload_file
from src.utils.config import load_keywords, load_sources, OUTPUT_DIR
from src.utils.classify import classify_topic, classify_crop, source_group, relevance_score, make_summary


def enrich_rows(rows, keywords, today):
    crops = list(keywords["crops"].keys())
    priority_domains = keywords.get("priority_domains", [])
    enriched = []
    for row in rows:
        row["date_collected"] = today
        text = f"{row.get('title','')} {row.get('summary','')} {row.get('search_query','')}"
        if row.get("crop") in [None, "", "Unclassified"]:
            row["crop"] = classify_crop(text, crops)
        row["topic"] = classify_topic(text, keywords["topics"])
        row["source_group"] = row.get("source_group") or source_group(row.get("title", ""), row.get("url", ""))
        row["summary_clean"] = make_summary(row.get("title", ""), row.get("summary", ""))
        row["relevance_score"] = relevance_score(row, priority_domains)
        row["citation"] = f"{row.get('title','')}. {row.get('source','')}. {row.get('url','')}"
        enriched.append(row)
    return enriched


def run_daily():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    keywords = load_keywords()
    sources = load_sources()
    out_dir = OUTPUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect_news(keywords["crops"], sources.get("rss_sources", []))
    rows = enrich_rows(rows, keywords, today)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["url"])
        df = df.sort_values(["crop", "source_group", "relevance_score"], ascending=[True, True, False])

    csv_path = out_dir / f"PEARL_daily_news_{today}.csv"
    xlsx_path = out_dir / f"PEARL_daily_news_{today}.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)

    upload_file(str(csv_path), csv_path.name)
    upload_file(str(xlsx_path), xlsx_path.name)
    print(f"Daily collection completed: {len(df)} records")


if __name__ == "__main__":
    run_daily()
