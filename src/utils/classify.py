from urllib.parse import urlparse

CAMBODIA_TERMS = [
    "cambodia", "cambodian", ".kh", "phnom penh", "kampong thom", "siem reap",
    "preah vihear", "oddar meanchey", "maff", "ministry of agriculture"
]


def classify_topic(text, topics):
    text = str(text).lower()
    found = []
    for topic, words in topics.items():
        if any(str(w).lower() in text for w in words):
            found.append(topic)
    return "; ".join(found) if found else "general"


def classify_crop(text, crop_names):
    text = str(text).lower()
    for crop in crop_names:
        crop_l = crop.lower()
        if crop_l in text or (crop_l == "vegetables" and "vegetable" in text):
            return crop
    return "Unclassified"


def source_group(title, url):
    text = f"{title} {url}".lower()
    return "Cambodia News" if any(t in text for t in CAMBODIA_TERMS) else "Global Trend"


def get_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def relevance_score(row, priority_domains=None):
    text = f"{row.get('title','')} {row.get('summary','')} {row.get('url','')}".lower()
    keywords = [
        "cambodia", "mango", "cashew", "rice", "vegetable", "price", "market", "export",
        "farmer", "climate", "drought", "flood", "policy", "investment", "processing",
        "pest", "disease", "ghg", "methane", "sustainable"
    ]
    score = sum(1 for k in keywords if k in text)
    domain = get_domain(row.get("url", ""))
    if priority_domains and any(d in domain for d in priority_domains):
        score += 3
    if row.get("source_group") == "Cambodia News":
        score += 2
    return score


def make_summary(title, summary="", max_chars=350):
    text = (summary or title or "").strip()
    text = " ".join(text.split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")
