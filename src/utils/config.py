import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"


def load_keywords():
    with open(CONFIG_DIR / "keywords.json", "r", encoding="utf-8") as f:
        return json.load(f)
