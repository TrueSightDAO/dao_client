#!/usr/bin/env python3
"""Submit [CONTRIBUTION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_contribution.html

Run:
    python -m truesight_dao_client.modules.report_contribution --help
    # or: truesight-dao-report-contribution --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='CONTRIBUTION EVENT',
    canonical_labels=['Type', 'Amount', 'Description', 'Contributor(s)', 'TDG Issued', 'Attached Filename', 'Destination Contribution File Location'],
    dapp_page='report_contribution.html',
)

if __name__ == "__main__":
    sys.exit(main())
