#!/usr/bin/env python3
"""Submit [FARM REGISTRATION] to Edgar.

Browser equivalent: dapp.truesight.me/register_farm.html

Run from the dao_client repo root:
    python3 modules/register_farm.py --help
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar_client import build_event_cli

main = build_event_cli(
    event_name='FARM REGISTRATION',
    canonical_labels=['Farm Name', 'Farm Location', 'Latitude', 'Longitude', 'Area for Tree Planting (hectares)', 'Current Land Use', 'Ownership Status'],
    dapp_page='register_farm.html',
)

if __name__ == "__main__":
    sys.exit(main())
