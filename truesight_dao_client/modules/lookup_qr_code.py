#!/usr/bin/env python3
"""Read-only inspector for an Agroverse QR code.

Hits the same GAS web app the DApp `update_qr_code.html` page uses
(`?lookup=true&qr_code=<code>`) and prints the resolved record:
currency, ledger shortcut, status, owner email, manager name, plus the
linked Stripe session ID + shipping provider + tracking number (if the
QR row's column Z, or the legacy column P fallback on the Stripe sheet,
links a Stripe checkout).

Useful before submitting a `[QR CODE UPDATE EVENT]` so the operator (or
an AI agent on their behalf) knows what's already on the row.

Run from the dao_client repo root:

    python -m truesight_dao_client.modules.lookup_qr_code --qr 2024OSCAR_20260121_12

    # JSON output (for piping into jq / other agents)
    python -m truesight_dao_client.modules.lookup_qr_code --qr <code> --json
"""
from __future__ import annotations

import argparse
import json
import sys

from ..cache._source import GasBackend


# Same `qrCodes` GAS web app used by dapp/update_qr_code.html (window.Routes.gas.qrCodes).
QR_CODE_GAS_EXEC_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxigq4-J0izShubqIC5k6Z7fgNRyVJLakfQ34HPuENiSpxuCG-wSq0g-wOAedZzzgaL/exec"
)


def lookup(qr_code: str) -> dict:
    """Fetch the GAS lookup payload for ``qr_code`` and return it as a dict."""
    backend = GasBackend(
        exec_url=QR_CODE_GAS_EXEC_URL,
        base_params={"lookup": "true"},
    )
    return backend.fetch(qr_code=qr_code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Look up an Agroverse QR code's current ledger record. "
            "Read-only — does not submit any event to Edgar."
        ),
    )
    parser.add_argument(
        "--qr",
        required=True,
        metavar="QR_CODE",
        help="The QR code identifier (e.g. 2024OSCAR_20260121_12).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of the human-readable summary.",
    )
    args = parser.parse_args(argv)

    try:
        data = lookup(args.qr)
    except Exception as exc:
        print(f"Lookup failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
        return 0 if data.get("status") == "success" else 1

    if data.get("status") != "success":
        print(f"Error: {data.get('message', data)}", file=sys.stderr)
        return 1

    fields = [
        ("QR code",            data.get("qr_code", "")),
        ("Currency",           data.get("currency", "")),
        ("Ledger shortcut",    data.get("ledger_shortcut", "")),
        ("Status",             data.get("qr_status", "")),
        ("Owner email",        data.get("email", "")),
        ("Manager name",       data.get("manager_name", "")),
        ("Stripe session ID",  data.get("stripe_session_id", "")),
        ("Shipping provider",  data.get("shipping_provider", "")),
        ("Tracking number",    data.get("tracking_number", "")),
    ]
    width = max(len(label) for label, _ in fields)
    for label, value in fields:
        print(f"{label.ljust(width)}  {value or '(empty)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
