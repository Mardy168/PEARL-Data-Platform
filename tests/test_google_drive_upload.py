from pathlib import Path, PurePosixPath
import unittest

from tools.upload_google_drive import destination_for


class GoogleDriveDestinationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("data")

    def test_daily_destination(self):
        path = self.root / "daily" / "PEARL_daily_news_2026-07-15.xlsx"
        self.assertEqual(
            destination_for(path, self.root),
            PurePosixPath("daily/2026/07/15/PEARL_daily_news_2026-07-15.xlsx"),
        )

    def test_weekly_destination(self):
        path = self.root / "weekly" / "PEARL_weekly_news_2026-07-17.xlsx"
        self.assertEqual(
            destination_for(path, self.root),
            PurePosixPath("weekly/2026/W29/PEARL_weekly_news_2026-07-17.xlsx"),
        )

    def test_monthly_destination(self):
        path = self.root / "monthly" / "PEARL_monthly_news_2026-06.xlsx"
        self.assertEqual(
            destination_for(path, self.root),
            PurePosixPath("monthly/2026/06/PEARL_monthly_news_2026-06.xlsx"),
        )

    def test_log_destination(self):
        path = self.root / "logs" / "PEARL_daily_log_2026-07-15.txt"
        self.assertEqual(
            destination_for(path, self.root),
            PurePosixPath("logs/2026/07/PEARL_daily_log_2026-07-15.txt"),
        )


if __name__ == "__main__":
    unittest.main()
