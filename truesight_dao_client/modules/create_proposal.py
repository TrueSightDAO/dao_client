#!/usr/bin/env python3
"""Submit [PROPOSAL CREATION] to Edgar.

Browser equivalent: dapp.truesight.me/create_proposal.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.create_proposal --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='PROPOSAL CREATION',
    canonical_labels=[],
    dapp_page='create_proposal.html',
)

if __name__ == "__main__":
    sys.exit(main())
