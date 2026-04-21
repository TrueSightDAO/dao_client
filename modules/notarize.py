#!/usr/bin/env python3
"""Submit [NOTARIZATION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/notarize.html

Run from the dao_client repo root:
    python3 modules/notarize.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='NOTARIZATION EVENT',
    canonical_labels=['Submitter', 'Latitude', 'Longitude', 'Document Type', 'Description', 'Attached Filename', 'Destination Notarized File Location', 'Submission Source'],
    dapp_page='notarize.html',
)

if __name__ == "__main__":
    sys.exit(main())
