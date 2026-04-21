#!/usr/bin/env python3
"""Submit [QR CODE UPDATE EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/update_qr_code.html

Run from the dao_client repo root:
    python3 modules/update_qr_code.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='QR CODE UPDATE EVENT',
    canonical_labels=[],
    dapp_page='update_qr_code.html',
)

if __name__ == "__main__":
    sys.exit(main())
