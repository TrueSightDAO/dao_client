#!/usr/bin/env python3
"""Submit [DAO Inventory Expense Event] to Edgar.

Browser equivalent: dapp.truesight.me/report_dao_expenses.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.report_dao_expenses --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='DAO Inventory Expense Event',
    canonical_labels=['DAO Member Name', 'Target Ledger', 'Latitude', 'Longitude', 'Inventory Type', 'Inventory Quantity', 'Description', 'Attached Filename', 'Destination Expense File Location', 'Submission Source'],
    dapp_page='report_dao_expenses.html',
)

if __name__ == "__main__":
    sys.exit(main())
