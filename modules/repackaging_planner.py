#!/usr/bin/env python3
"""Submit [REPACKAGING BATCH EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/repackaging_planner.html

Run from the dao_client repo root:
    python3 modules/repackaging_planner.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='REPACKAGING BATCH EVENT',
    canonical_labels=[],
    dapp_page='repackaging_planner.html',
)

if __name__ == "__main__":
    sys.exit(main())
