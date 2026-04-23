#!/usr/bin/env python3
"""Submit [REPACKAGING BATCH EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/repackaging_planner.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.repackaging_planner --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='REPACKAGING BATCH EVENT',
    canonical_labels=[],
    dapp_page='repackaging_planner.html',
)

if __name__ == "__main__":
    sys.exit(main())
