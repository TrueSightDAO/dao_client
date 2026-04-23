#!/usr/bin/env python3
"""Submit [CAPITAL INJECTION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_capital_injection.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.report_capital_injection --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='CAPITAL INJECTION EVENT',
    canonical_labels=['Ledger', 'Ledger URL', 'Amount', 'Description', 'Attached Filename', 'Destination Capital Injection File Location'],
    dapp_page='report_capital_injection.html',
)

if __name__ == "__main__":
    sys.exit(main())
