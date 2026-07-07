import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from docx import Document

from src.drive.upload import upload_file


CAMBODIA_TZ = timezone(timedelta(hours=7))
MASTER_FILE = "data/master/PEARL_master_news.csv"
OUTPUT_WEEKLY = "data/weekly"


def main():
    os.makedirs(OUTPUT_WEEKLY, exist_ok=True)

    if not os.path.exists(MASTER_FILE):
        print("No master file found. Run daily collector first.")
        return

    df = pd.read_csv(MASTER_FILE)

    today = datetime.now(CAMBODIA_TZ).date()
    start_date = today - timedelta(days=7)

    df["date_collected_dt"] = pd.to_datetime(df["date_collected"], errors="coerce").dt.date
    weekly = df[df["date_collected_dt"] >= start_date].copy()

    if weekly.empty:
        print("No weekly records found.")
        return

    report_date = today.strftime("%Y-%m-%d")

    xlsx_path = f"{OUTPUT_WEEKLY}/PEARL_weekly_news_{report_date}.xlsx"
    docx_path = f"{OUTPUT_WEEKLY}/PEARL_weekly_report_{report_date}.docx"

    weekly.to_excel(xlsx_path, index=False)

    doc = Document()
    doc.add_heading("PEARL Weekly Agriculture News Report", 0)
    doc.add_paragraph(f"Report date: {report_date}")
    doc.add_paragraph(f"Coverage period: {start_date} to {today}")

    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(
        f"This report summarizes {len(weekly)} unique agriculture-related news records "
        "for PEARL commonality crops: mango, cashew, rice, and vegetables."
    )

    doc.add_heading("Summary by Crop", level=1)
    for crop, crop_df in weekly.groupby("crop"):
        doc.add_heading(f"{crop} ({len(crop_df)} articles)", level=2)

        for _, row in crop_df.head(10).iterrows():
            doc.add_paragraph(f"• {row.get('title', '')}")
            doc.add_paragraph(f"  Summary: {row.get('Summary', '')}")
            doc.add_paragraph(f"  Topic: {row.get('topic', '')}")
            doc.add_paragraph(f"  Link: {row.get('url', '')}")

    doc.add_heading("Summary by Topic", level=1)
    for topic, count in weekly["topic"].value_counts().items():
        doc.add_paragraph(f"{topic}: {count} articles")

    doc.add_heading("References", level=1)
    for _, row in weekly.iterrows():
        doc.add_paragraph(f"{row.get('title', '')} - {row.get('url', '')}")

    doc.save(docx_path)

    upload_file(xlsx_path)
    upload_file(docx_path)

    print("Weekly report completed and uploaded.")


if __name__ == "__main__":
    main()
