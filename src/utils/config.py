import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"


def load_json(filename: str):
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_keywords():
    return load_json("keywords.json")


def load_sources():
    try:
        return load_json("sources.json")
    except FileNotFoundError:
        return {"rss_sources": []}
