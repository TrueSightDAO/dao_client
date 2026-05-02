#!/usr/bin/env python3
"""Submit [CONTRIBUTION EVENT] to Edgar.

Browser equivalent: dapp.truesight.me/report_contribution.html

Run:
    python -m truesight_dao_client.modules.report_contribution --help
    # or: truesight-dao-report-contribution --help
"""
import sys

from ..edgar_client import build_event_cli

# Canonical rubric types from the TrueSight DAO Intiatives Scoring Rubric.
# See Main Ledger & Contributors spreadsheet, tab "Intiatives Scoring Rubric".
VALID_CONTRIBUTION_TYPES = {
    "Time (Minutes)",
    "USD",
    "USDT sent",
    "USDT received",
}


def _validate_contribution_type(value: str) -> None:
    """Raise ValueError if the contribution Type is not a valid rubric entry."""
    if value not in VALID_CONTRIBUTION_TYPES:
        raise ValueError(
            f"Invalid contribution Type: {value!r}. "
            f"Must be one of: {', '.join(sorted(VALID_CONTRIBUTION_TYPES))}. "
            f"See Intiatives Scoring Rubric in Main Ledger."
        )


main = build_event_cli(
    event_name='CONTRIBUTION EVENT',
    canonical_labels=['Type', 'Amount', 'Description', 'Contributor(s)', 'TDG Issued', 'Attached Filename', 'Destination Contribution File Location'],
    dapp_page='report_contribution.html',
    validators={'Type': _validate_contribution_type},
)

if __name__ == "__main__":
    sys.exit(main())
