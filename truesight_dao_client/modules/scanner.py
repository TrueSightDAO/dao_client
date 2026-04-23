#!/usr/bin/env python3
"""Submit [QR CODE EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/scanner.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.scanner --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='QR CODE EVENT',
    canonical_labels=['Attached Filename', 'Submission Source'],
    dapp_page='scanner.html',
)

if __name__ == "__main__":
    sys.exit(main())
