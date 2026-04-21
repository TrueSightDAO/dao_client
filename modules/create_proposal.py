#!/usr/bin/env python3
"""Submit [PROPOSAL CREATION] to Edgar.

Browser equivalent: dapp.truesight.me/create_proposal.html

Run from the dao_client repo root:
    python3 modules/create_proposal.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='PROPOSAL CREATION',
    canonical_labels=[],
    dapp_page='create_proposal.html',
)

if __name__ == "__main__":
    sys.exit(main())
