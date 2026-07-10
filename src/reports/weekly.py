"""Compatibility wrapper. The production weekly workflow is pearl_weekly_report.py."""
from pearl_weekly_report import main


def run_weekly():
    return main()


if __name__=='__main__':
    main()
