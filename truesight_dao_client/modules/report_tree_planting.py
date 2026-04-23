#!/usr/bin/env python3
"""Submit [TREE PLANTING EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_tree_planting.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.report_tree_planting --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='TREE PLANTING EVENT',
    canonical_labels=['Latitude', 'Longitude', 'Species', 'Planting Time', 'Photo URL', 'Submission Source'],
    dapp_page='report_tree_planting.html',
)

if __name__ == "__main__":
    sys.exit(main())
