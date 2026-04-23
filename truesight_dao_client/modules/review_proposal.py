#!/usr/bin/env python3
"""Submit [PROPOSAL VOTE] to Edgar.

Browser equivalent: dapp.truesight.me/review_proposal.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.review_proposal --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='PROPOSAL VOTE',
    canonical_labels=[],
    dapp_page='review_proposal.html',
)

if __name__ == "__main__":
    sys.exit(main())
