#!/usr/bin/env python3
"""Submit [BATCH QR CODE REQUEST] to Edgar.

Browser equivalent: dapp.truesight.me/batch_qr_generator.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.batch_qr_generator --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='BATCH QR CODE REQUEST',
    canonical_labels=[],
    dapp_page='batch_qr_generator.html',
)

if __name__ == "__main__":
    sys.exit(main())
