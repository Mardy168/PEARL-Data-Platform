import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from docx import Document
from docx.shared import Inches

from src.drive.drive import upload_file, download_file_by_name


CAMBODIA_TZ = timezone(timedelta(hours=7))

OUTPUT_WEEKLY = "data/weekly"
OUTPUT_MASTER = "data/master"

MASTER_FILENAME = "PEARL_master_news.csv"
MASTER_FILE = f"{OUTPUT_MASTER}/{MASTER_FILENAME}"


def add_weekly_section(doc, title, df, max_items=15):
    doc.add_heading(title, level=1)

    if df.empty:
        doc.add_paragraph("No major news identified for this section.")
        return

    doc.add_paragraph(f"Total articles: {len(df)}")

    if "crop" in df.columns:
        doc.add_paragraph("Articles by crop:")
        for crop, count in df["crop"].value_counts().items():
            doc.add_paragraph(f"- {crop}: {count}")

    if "topic" in df.columns:
        doc.add_paragraph("Articles by topic:")
        for topic, count in df["topic"].value_counts().items():
            doc.add_paragraph(f"- {topic}: {count}")

    doc.add_heading("Key News", level=2)

    for _, row in df.head(max_items).iterrows():
        title_text = str(row.get("title", "")).strip()
        summary = str(row.get("Summary", "")).strip()
        crop = str(row.get("crop", "")).strip()
        topic = str(row.get("topic", "")).strip()

        if title_text:
            doc.add_paragraph(f"• {title_text}")

        if summary:
            doc.add_paragraph(f"  Summary: {summary}")

        doc.add_paragraph(f"  Crop: {crop} | Topic: {topic}")


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
    report_date = today.strftime("%Y-%m-%d")

    df["date_collected_dt"] = pd.to_datetime(
        df["date_collected"],
        errors="coerce"
    ).dt.date

    weekly = df[df["date_collected_dt"] >= start_date].copy()

    if weekly.empty:
        print("No weekly records found.")
        return

    weekly_xlsx = f"{OUTPUT_WEEKLY}/PEARL_weekly_news_{report_date}.xlsx"
    weekly_docx = f"{OUTPUT_WEEKLY}/PEARL_weekly_summary_{report_date}.docx"

    weekly.to_excel(weekly_xlsx, index=False)

    doc = Document()

    section = doc.sections[0]
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.6)
    section.right_margin = Inches(0.6)

    doc.add_heading("PEARL Weekly Agriculture News Summary", 0)
    doc.add_paragraph(f"Report date: {report_date}")
    doc.add_paragraph(f"Coverage period: {start_date} to {today}")
    doc.add_paragraph(
        "This two-page summary separates Cambodia and global agriculture news. "
        "News links are excluded from this Word report and retained in the Excel file."
    )

    cambodia = weekly[weekly["country"].astype(str).str.lower() == "cambodia"].copy()
    global_news = weekly[weekly["country"].astype(str).str.lower() != "cambodia"].copy()

    add_weekly_section(doc, "Page 1: Cambodia News", cambodia, max_items=12)

    doc.add_page_break()

    add_weekly_section(doc, "Page 2: Global News", global_news, max_items=12)

    doc.save(weekly_docx)

    upload_file(weekly_xlsx)
    upload_file(weekly_docx)

    print("Weekly report completed successfully.")


if __name__ == "__main__":
    main()
