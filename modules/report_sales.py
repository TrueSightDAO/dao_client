#!/usr/bin/env python3
"""Submit [SALES EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_sales.html

Run from the dao_client repo root:
    python3 modules/report_sales.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='SALES EVENT',
    canonical_labels=['Item', 'Sales price', 'Sold by', 'Cash proceeds collected by', 'Owner email', 'Stripe Session ID', 'Shipping Provider', 'Tracking number', 'Attached Filename', 'Submission Source'],
    dapp_page='report_sales.html',
)

if __name__ == "__main__":
    sys.exit(main())
