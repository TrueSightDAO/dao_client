#!/usr/bin/env python3
"""Submit [INVENTORY MOVEMENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_inventory_movement.html

Run from the dao_client repo root:
    python3 modules/report_inventory_movement.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='INVENTORY MOVEMENT',
    canonical_labels=['Manager Name', 'Recipient Name', 'Inventory Item', 'QR Code', 'Quantity', 'Latitude', 'Longitude', 'Attached Filename', 'Destination Inventory File Location', 'Submission Source'],
    dapp_page='report_inventory_movement.html',
)

if __name__ == "__main__":
    sys.exit(main())
