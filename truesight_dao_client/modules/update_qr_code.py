#!/usr/bin/env python3
"""Submit [QR CODE UPDATE EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/update_qr_code.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.update_qr_code --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='QR CODE UPDATE EVENT',
    canonical_labels=[],
    dapp_page='update_qr_code.html',
)

if __name__ == "__main__":
    sys.exit(main())
