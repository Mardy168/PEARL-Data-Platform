from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.master.manager import combine_and_validate_master, normalized_master_for_reporting, save_master_transaction, MasterState
from src.utils.dates import CAMBODIA_TZ, add_published_columns, daily_window, previous_month_window
from src.utils.duplicate import deduplicate_articles, exclude_existing


class CoreTests(unittest.TestCase):
    def test_deduplicate_preserves_different_publishers(self):
        frame = pd.DataFrame([
            {"title": "Rice exports rise", "url": "https://a.example/news?id=1&utm_source=x", "publisher_domain": "a.example"},
            {"title": "Rice exports rise", "url": "https://a.example/news?id=1", "publisher_domain": "a.example"},
            {"title": "Rice exports rise", "url": "https://b.example/rice", "publisher_domain": "b.example"},
        ])
        self.assertEqual(len(deduplicate_articles(frame)), 2)

    def test_mixed_dates_do_not_raise(self):
        frame = pd.DataFrame({
            "title": ["A", "B", "A"],
            "url": ["https://example.com/a", "https://example.com/b", "https://example.com/a?utm_source=x"],
            "publisher_domain": ["example.com"] * 3,
            "published_dt_kh": ["2026-07-10", pd.Timestamp("2026-07-11", tz="Asia/Phnom_Penh"), None],
        })
        result = deduplicate_articles(frame)
        self.assertEqual(result["title"].tolist(), ["B", "A"])

    def test_exclude_existing(self):
        master = pd.DataFrame([{"title": "Mango market", "url": "https://example.com/a", "publisher_domain": "example.com"}])
        incoming = pd.DataFrame([
            {"title": "Mango market", "url": "https://example.com/a?utm_source=x", "publisher_domain": "example.com"},
            {"title": "New cashew factory", "url": "https://example.com/b", "publisher_domain": "example.com"},
        ])
        result = exclude_existing(incoming, master)
        self.assertEqual(result["title"].tolist(), ["New cashew factory"])

    def test_published_date_cambodia_conversion(self):
        out = add_published_columns(pd.DataFrame({"published_date": ["2026-07-10T00:00:00Z"]}))
        self.assertEqual(out.loc[0, "Published Date"], "2026-07-10 07:00:00")

    def test_daily_boundary_is_fixed_at_0900(self):
        now = datetime(2026, 7, 12, 9, 37, tzinfo=CAMBODIA_TZ)
        start, end = daily_window(now)
        self.assertEqual((start.hour, end.hour), (9, 9))
        self.assertEqual((end - start).total_seconds(), 86400)

    def test_previous_month_window(self):
        now = datetime(2026, 7, 11, 10, 0, tzinfo=CAMBODIA_TZ)
        start, end, label = previous_month_window(now)
        self.assertEqual(label, "2026-06")
        self.assertEqual((start.day, start.month), (1, 6))
        self.assertEqual((end.day, end.month), (1, 7))

    def test_all_reports_can_read_same_saved_master(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PEARL_master_news.csv"
            old = pd.DataFrame()
            new = pd.DataFrame([{
                "title": "Rice update", "url": "https://example.com/rice",
                "publisher_domain": "example.com", "published_date": "2026-07-10T00:00:00Z",
                "status": "ARTICLE",
            }])
            combined = combine_and_validate_master(old, new)
            state = MasterState(old, path, 0)
            save_master_transaction(state, combined)
            reporting = normalized_master_for_reporting(path)
            self.assertEqual(len(reporting), 1)
            self.assertEqual(reporting.iloc[0]["title"], "Rice update")


if __name__ == "__main__":
    unittest.main()
