#!/usr/bin/env python3
"""Submit [CAPITAL INJECTION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_capital_injection.html

Run from the dao_client repo root:
    python3 modules/report_capital_injection.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='CAPITAL INJECTION EVENT',
    canonical_labels=['Ledger', 'Ledger URL', 'Amount', 'Description', 'Attached Filename', 'Destination Capital Injection File Location'],
    dapp_page='report_capital_injection.html',
)

if __name__ == "__main__":
    sys.exit(main())
