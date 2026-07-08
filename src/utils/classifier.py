TOPIC_KEYWORDS = {
    "Market": ["market", "price", "demand", "supply", "buyer", "seller"],
    "Export": ["export", "shipment", "trade", "china", "vietnam", "eu", "japan", "import"],
    "Production": ["production", "harvest", "yield", "farmer", "cultivation", "crop"],
    "Climate Risk": ["drought", "flood", "rain", "climate", "heat", "weather", "storm"],
    "Policy": ["policy", "ministry", "government", "strategy", "regulation", "law"],
    "Investment": ["investment", "factory", "processing", "loan", "finance", "credit"],
    "Pest/Disease": ["pest", "disease", "outbreak", "insect"],
}


def classify_topic(text):
    text = str(text).lower()
    topics = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in text for k in keywords):
            topics.append(topic)

    return "; ".join(topics) if topics else "General"


def detect_country(text):
    text = str(text).lower()

    if "cambodia" in text or "phnom penh" in text or "khmer" in text:
        return "Cambodia"

    return "Global"
