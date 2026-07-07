from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from docx import Document
from src.drive.upload import upload_file
from src.utils.config import OUTPUT_DIR


def run_weekly():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    files = list(Path("output").glob("*/PEARL_daily_news_*.csv"))
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f))
        except Exception:
            pass
    if not frames:
        print("No local CSV files found. Run daily collection first.")
        return
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["url"])
    df = df.sort_values("relevance_score", ascending=False)
    report_dir = OUTPUT_DIR / "weekly_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"PEARL_weekly_report_{today}.docx"
    doc = Document()
    doc.add_heading("PEARL Weekly Commonality News Report", 0)
    doc.add_paragraph("Crops: Mango, Cashew, Rice and Vegetables")
    doc.add_heading("Key findings by crop", level=1)
    for crop in ["Mango", "Cashew", "Rice", "Vegetables"]:
        doc.add_heading(crop, level=2)
        crop_df = df[df["crop"] == crop].head(10)
        if crop_df.empty:
            doc.add_paragraph("No articles collected.")
        for _, row in crop_df.iterrows():
            doc.add_paragraph(f"- {row.get('title','')} | {row.get('source','')} | {row.get('topic','')}")
    doc.add_heading("References", level=1)
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        doc.add_paragraph(f"[{i}] {row.get('citation','')}")
    doc.save(path)
    upload_file(str(path), path.name)
    print("Weekly report completed.")

if __name__ == "__main__":
    run_weekly()
