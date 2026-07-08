def make_summary(row):
    title = str(row.get("title", "")).strip()
    crop = row.get("crop", "")
    topic = row.get("topic", "General")
    country = row.get("country", "Global")

    if not title:
        return ""

    return (
        f"{country} {crop} news related to {str(topic).lower()}. "
        f"Key point: {title}"
    )[:500]
