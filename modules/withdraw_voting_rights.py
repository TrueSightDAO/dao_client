#!/usr/bin/env python3
"""Submit [VOTING RIGHTS WITHDRAWAL REQUEST] to Edgar.

Browser equivalent: dapp.truesight.me/withdraw_voting_rights.html

Run from the dao_client repo root:
    python3 modules/withdraw_voting_rights.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='VOTING RIGHTS WITHDRAWAL REQUEST',
    canonical_labels=['Contributor', 'Amount to withdraw', 'Value per voting right', 'Expected total amount (USD)', 'Withdrawal method'],
    dapp_page='withdraw_voting_rights.html',
)

if __name__ == "__main__":
    sys.exit(main())
