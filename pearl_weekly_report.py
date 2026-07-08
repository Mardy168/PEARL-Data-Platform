import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from docx import Document

from src.drive.drive import upload_file, download_file_by_name


CAMBODIA_TZ = timezone(timedelta(hours=7))

OUTPUT_WEEKLY = "data/weekly"
OUTPUT_MASTER = "data/master"

MASTER_FILENAME = "PEARL_master_news.csv"
MASTER_FILE = f"{OUTPUT_MASTER}/{MASTER_FILENAME}"


def main():
    os.makedirs(OUTPUT_WEEKLY, exist_ok=True)
    os.makedirs(OUTPUT_MASTER, exist_ok=True)

    download_file_by_name(MASTER_FILENAME, MASTER_FILE)

    if not os.path.exists(MASTER_FILE):
        print("No master file found. Run daily collector first.")
        return

    df = pd.read_csv(MASTER_FILE)

    if df.empty:
        print("Master file is empty.")
        return

    today = datetime.now(CAMBODIA_TZ).date()
    start_date = today - timedelta(days=7)

    df["date_collected_dt"] = pd.to_datetime(
        df["date_collected"],
        errors="coerce"
    ).dt.date

    weekly = df[df["date_collected_dt"] >= start_date].copy()

    if weekly.empty:
        print("No weekly records found.")
        return

    report_date = today.strftime("%Y-%m-%d")

    weekly_xlsx = f"{OUTPUT_WEEKLY}/PEARL_weekly_news_{report_date}.xlsx"
    weekly_docx = f"{OUTPUT_WEEKLY}/PEARL_weekly_report_{report_date}.docx"

    weekly.to_excel(weekly_xlsx, index=False)

    doc = Document()

    doc.add_heading("PEARL Weekly Agriculture News Report", 0)
    doc.add_paragraph(f"Report date: {report_date}")
    doc.add_paragraph(f"Coverage period: {start_date} to {today}")
    doc.add_paragraph(f"Total unique records: {len(weekly)}")

    doc.add_heading("1. Executive Summary", level=1)
    doc.add_paragraph(
        f"This weekly report summarizes {len(weekly)} unique agriculture-related news records "
        "collected for PEARL commonality crops: mango, cashew, rice, and vegetables."
    )

    doc.add_heading("2. News Statistics", level=1)

    if "crop" in weekly.columns:
        doc.add_heading("Articles by Crop", level=2)
        for crop, count in weekly["crop"].value_counts().items():
            doc.add_paragraph(f"{crop}: {count}")

    if "topic" in weekly.columns:
        doc.add_heading("Articles by Topic", level=2)
        for topic, count in weekly["topic"].value_counts().items():
            doc.add_paragraph(f"{topic}: {count}")

    if "country" in weekly.columns:
        doc.add_heading("Articles by Country", level=2)
        for country, count in weekly["country"].value_counts().items():
            doc.add_paragraph(f"{country}: {count}")

    doc.add_heading("3. Summary by Crop", level=1)

    for crop, crop_df in weekly.groupby("crop"):
        doc.add_heading(f"{crop} ({len(crop_df)} articles)", level=2)

        for _, row in crop_df.head(10).iterrows():
            doc.add_paragraph(f"• {row.get('title', '')}")
            doc.add_paragraph(f"  Summary: {row.get('Summary', '')}")
            doc.add_paragraph(f"  Topic: {row.get('topic', '')}")
            doc.add_paragraph(f"  Source: {row.get('source', '')}")
            doc.add_paragraph(f"  Link: {row.get('url', '')}")

    doc.add_heading("4. References", level=1)

    for _, row in weekly.iterrows():
        doc.add_paragraph(f"{row.get('title', '')} - {row.get('url', '')}")

    doc.save(weekly_docx)

    upload_file(weekly_xlsx)
    upload_file(weekly_docx)

    print("Weekly report completed successfully.")


if __name__ == "__main__":
    main()
