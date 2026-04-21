#!/usr/bin/env python3
"""Submit [QR CODE EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/scanner.html

Run from the dao_client repo root:
    python3 modules/scanner.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='QR CODE EVENT',
    canonical_labels=['Attached Filename', 'Submission Source'],
    dapp_page='scanner.html',
)

if __name__ == "__main__":
    sys.exit(main())
