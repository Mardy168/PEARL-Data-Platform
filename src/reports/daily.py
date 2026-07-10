from src.reports.common import configure_document, add_news_section


def create_daily_word_report(df, output_path, report_date):
    doc = configure_document("PEARL Daily Agriculture News Summary", f"Report date: {report_date}")
    articles = df[df.get("status", "ARTICLE").astype(str).eq("ARTICLE")].copy() if "status" in df.columns else df.copy()
    cambodia = articles[articles["country"].astype(str).str.lower().eq("cambodia")]
    global_news = articles[~articles["country"].astype(str).str.lower().eq("cambodia")]
    add_news_section(doc, "Cambodia News", cambodia, 5)
    add_news_section(doc, "Global News", global_news, 5)
    doc.save(output_path)
    return output_path
