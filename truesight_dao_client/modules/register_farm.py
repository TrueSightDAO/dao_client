#!/usr/bin/env python3
"""Submit [FARM REGISTRATION] to Edgar.

Browser equivalent: dapp.truesight.me/register_farm.html

Run from the dao_client repo root:
    python -m truesight_dao_client.modules.register_farm --help
"""
import sys

from ..edgar_client import build_event_cli

main = build_event_cli(
    event_name='FARM REGISTRATION',
    canonical_labels=['Farm Name', 'Farm Location', 'Latitude', 'Longitude', 'Area for Tree Planting (hectares)', 'Current Land Use', 'Ownership Status'],
    dapp_page='register_farm.html',
)

if __name__ == "__main__":
    sys.exit(main())
