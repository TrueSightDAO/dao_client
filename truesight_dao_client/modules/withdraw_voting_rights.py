#!/usr/bin/env python3
"""Submit [VOTING RIGHTS WITHDRAWAL REQUEST] to Edgar.

Browser equivalent: dapp.truesight.me/withdraw_voting_rights.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.withdraw_voting_rights --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='VOTING RIGHTS WITHDRAWAL REQUEST',
    canonical_labels=['Contributor', 'Amount to withdraw', 'Value per voting right', 'Expected total amount (USD)', 'Withdrawal method'],
    dapp_page='withdraw_voting_rights.html',
)

if __name__ == "__main__":
    sys.exit(main())
