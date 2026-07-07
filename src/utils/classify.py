def classify_topic(text, topics):
    text = str(text).lower()
    found = []
    for topic, words in topics.items():
        if any(w.lower() in text for w in words):
            found.append(topic)
    return "; ".join(found) if found else "general"


def source_group(title, url):
    text = f"{title} {url}".lower()
    cambodia_terms = ["cambodia", ".kh", "khmertimeskh", "phnompenhpost", "akp.gov.kh", "cambodianess"]
    return "Cambodia News" if any(t in text for t in cambodia_terms) else "Global Trend"


def relevance_score(row):
    text = f"{row.get('title','')} {row.get('summary','')}".lower()
    keywords = ["cambodia", "mango", "cashew", "rice", "vegetable", "price", "market", "export", "farmer", "climate", "drought", "flood", "policy", "investment", "processing"]
    return sum(1 for k in keywords if k in text)
