#!/usr/bin/env python3
"""Submit [BATCH QR CODE REQUEST] to Edgar.

Browser equivalent: dapp.truesight.me/batch_qr_generator.html

Run from the dao_client repo root:
    python3 modules/batch_qr_generator.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='BATCH QR CODE REQUEST',
    canonical_labels=[],
    dapp_page='batch_qr_generator.html',
)

if __name__ == "__main__":
    sys.exit(main())
