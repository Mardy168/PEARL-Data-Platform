from __future__ import annotations

import argparse
import json

from src.master.manager import validate_master_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Master CSV path")
    args = parser.parse_args()
    print(json.dumps(validate_master_file(args.path), indent=2))


if __name__ == "__main__":
    main()
