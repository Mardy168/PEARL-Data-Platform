from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from src.utils.dates import CAMBODIA_TZ, add_published_columns, previous_month_window
from src.utils.duplicate import deduplicate_articles, exclude_existing


class CoreTests(unittest.TestCase):
    def test_deduplicate_preserves_different_publishers(self):
        df = pd.DataFrame([
            {"title": "Rice exports rise", "url": "https://a.example/news?id=1&utm_source=x", "publisher_domain": "a.example"},
            {"title": "Rice exports rise", "url": "https://a.example/news?id=1", "publisher_domain": "a.example"},
            {"title": "Rice exports rise", "url": "https://b.example/rice", "publisher_domain": "b.example"},
        ])
        result = deduplicate_articles(df)
        self.assertEqual(len(result), 2)

    def test_exclude_existing(self):
        master = pd.DataFrame([{"title": "Mango market", "url": "https://example.com/a", "publisher_domain": "example.com"}])
        incoming = pd.DataFrame([
            {"title": "Mango market", "url": "https://example.com/a?utm_source=x", "publisher_domain": "example.com"},
            {"title": "New cashew factory", "url": "https://example.com/b", "publisher_domain": "example.com"},
        ])
        result = exclude_existing(incoming, master)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["title"], "New cashew factory")

    def test_published_date_cambodia_conversion(self):
        df = pd.DataFrame({"published_date": ["2026-07-10T00:00:00Z"]})
        out = add_published_columns(df)
        self.assertEqual(out.loc[0, "Published Date"], "2026-07-10 07:00:00")

    def test_previous_month_window(self):
        now = datetime(2026, 7, 11, 10, 0, tzinfo=CAMBODIA_TZ)
        start, end, label = previous_month_window(now)
        self.assertEqual(label, "2026-06")
        self.assertEqual((start.day, start.month), (1, 6))
        self.assertEqual((end.day, end.month), (1, 7))


if __name__ == "__main__":
    unittest.main()
