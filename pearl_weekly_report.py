import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from docx import Document

from src.drive.upload import upload_file


CAMBODIA_TZ = timezone(timedelta(hours=7))
MASTER_FILE = "data/master/PEARL_master_news.csv"
OUTPUT_DIR = "data/weekly"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(MASTER_FILE):
        print("No master CSV found. Run daily collector first.")
        return

    df = pd.read_csv(MASTER_FILE)

    if df.empty:
        print("Master file is empty.")
        return

    today = datetime.now(CAMBODIA_TZ).date()
    start_week = today - timedelta(days=7)

    df["date_collected_dt"] = pd.to_datetime(df["date_collected"], errors="coerce").dt.date
    weekly = df[df["date_collected_dt"] >= start_week].copy()

    if weekly.empty:
        print("No weekly records found.")
        return

    report_date = today.strftime("%Y-%m-%d")

    xlsx_path = f"{OUTPUT_DIR}/PEARL_weekly_news_{report_date}.xlsx"
    docx_path = f"{OUTPUT_DIR}/PEARL_weekly_report_{report_date}.docx"

    weekly.to_excel(xlsx_path, index=False)

    doc = Document()
    doc.add_heading("PEARL Weekly Agriculture News Report", 0)
    doc.add_paragraph(f"Report date: {report_date}")
    doc.add_paragraph(f"Coverage period: {start_week} to {today}")

    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(
        f"This weekly report summarizes {len(weekly)} unique agriculture-related news items "
        "for PEARL commonality crops: mango, cashew, rice, and vegetables."
    )

    doc.add_heading("Summary by Crop", level=1)
    crop_counts = weekly["crop"].value_counts()

    for crop, count in crop_counts.items():
        doc.add_heading(f"{crop} ({count} articles)", level=2)
        crop_df = weekly[weekly["crop"] == crop].head(10)

        for _, row in crop_df.iterrows():
            doc.add_paragraph(f"• {row.get('title', '')}", style=None)
            doc.add_paragraph(f"  Summary: {row.get('Summary', '')}")
            doc.add_paragraph(f"  Source: {row.get('url', '')}")

    doc.add_heading("Summary by Topic", level=1)
    if "topic" in weekly.columns:
        topic_counts = weekly["topic"].value_counts()
        for topic, count in topic_counts.items():
            doc.add_paragraph(f"{topic}: {count} articles")

    doc.add_heading("References", level=1)
    for _, row in weekly.iterrows():
        doc.add_paragraph(f"{row.get('title', '')} - {row.get('url', '')}")

    doc.save(docx_path)

    upload_file(xlsx_path)
    upload_file(docx_path)

    print("Weekly report completed.")


if __name__ == "__main__":
    main()
