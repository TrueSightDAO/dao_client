#!/usr/bin/env python3
"""Submit [CONTRIBUTION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_contribution.html

Run from the dao_client repo root:
    python3 modules/report_contribution.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='CONTRIBUTION EVENT',
    canonical_labels=['Type', 'Amount', 'Description', 'Contributor(s)', 'TDG Issued', 'Attached Filename', 'Destination Contribution File Location'],
    dapp_page='report_contribution.html',
)

if __name__ == "__main__":
    sys.exit(main())
