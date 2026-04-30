#!/usr/bin/env python3
"""Submit `[DONATION MINT EVENT]` to Edgar for a serialized SunMint Pledge QR code.

Mints one row on `Agroverse QR codes` (status=MINTED) representing a cash donation
toward SunMint Tree Planting. The operator's subsequent `report_sales` call flips
the status to SOLD via the existing sales pipeline (no separate ledger logic
needed in the new GAS handler — see
`agentic_ai_context/notes/claude_serialized_qr_sales_2026-04-29.md`).

Three gates enforced by the GAS handler before minting (this CLI is a thin signer
that only assembles the payload — server-side gates are authoritative):

  1. Currency must be `SunMint Tree Planting Pledge - QR Code` (V1 allowlist).
  2. Signer must be a DAO governor (Pattern A — GAS reads the `Governors` tab).
  3. Visual proof URL must point to `github.com/TrueSightDAO/...`.

The QR code identifier is **client-generated** so the operator can immediately fire
`report_sales --item <qr_id>` without polling. Default prefix is `PLEDGE`; format
is `<PREFIX>_<YYYYMMDD>_<8hex>` (e.g., `PLEDGE_20260430_a1b2c3d4`).

Required browser equivalent: there is none — this is dao_client only because
governor authorization is enforced server-side.

Usage:

    cd ~/Applications/dao_client
    source .venv/bin/activate

    # 1. Upload the proof photo to GitHub first (e.g., to TrueSightDAO/.github
    #    assets/donations/), get the resulting URL.
    # 2. Run the mint:

    python -m truesight_dao_client.modules.mint_donation \\
        --donation-amount 25 \\
        --donor-name "Will" \\
        --donor-email will@example.com \\
        --proof-url https://github.com/TrueSightDAO/.github/blob/main/assets/donations/will_20260430.jpg

    # The CLI prints the freshly-minted QR code id (e.g. PLEDGE_20260430_a1b2c3d4).
    # Use it in the next step:

    python -m truesight_dao_client.modules.report_sales \\
        --item PLEDGE_20260430_a1b2c3d4 \\
        --sales-price 25 \\
        --sold-by "Gary Teh" --cash-proceeds-collected-by "Gary Teh" \\
        --owner-email will@example.com \\
        --stripe-session-id "(none)" \\
        --shipping-provider N/A --tracking-number N/A
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import secrets
import sys
from pathlib import Path

from ..edgar_client import EdgarClient

EVENT_NAME = "DONATION MINT EVENT"
DEFAULT_CURRENCY = "SunMint Tree Planting Pledge - QR Code"
DEFAULT_LEDGER_NAME = "AGL4"
DEFAULT_QR_PREFIX = "PLEDGE"
PROOF_URL_PATTERN = re.compile(r"^https?://(www\.)?github\.com/TrueSightDAO/", re.IGNORECASE)


def _today_yyyymmdd() -> str:
    return _dt.datetime.utcnow().strftime("%Y%m%d")


def generate_qr_code(prefix: str = DEFAULT_QR_PREFIX) -> str:
    """Stable, client-generated QR id: ``<PREFIX>_<YYYYMMDD>_<8hex>``."""
    return f"{prefix}_{_today_yyyymmdd()}_{secrets.token_hex(4)}"


def _basename_from_url(url: str) -> str:
    return os.path.basename(url.split("?", 1)[0].rstrip("/"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Submit [DONATION MINT EVENT] to Edgar for a serialized SunMint Pledge QR. "
            "Server-side: 3-gate validation (currency / governor / visual proof) before "
            "minting on Agroverse QR codes."
        ),
    )
    parser.add_argument("--donation-amount", required=True, help="USD amount of the donation (numeric).")
    parser.add_argument("--donor-name", required=True, help="Display name of the donor.")
    parser.add_argument("--donor-email", required=True, help="Donor's email — written to Owner Email on Agroverse QR codes.")
    parser.add_argument(
        "--proof-url",
        required=True,
        help=(
            "Full URL to the visual proof on github.com/TrueSightDAO/... (upload the photo to "
            "TrueSightDAO/.github/blob/main/assets/donations/ before running this)."
        ),
    )
    parser.add_argument(
        "--currency",
        default=DEFAULT_CURRENCY,
        help=f'Override the donation-eligible currency (default: "{DEFAULT_CURRENCY}"). '
             "GAS server-side allowlist will reject unknown values.",
    )
    parser.add_argument(
        "--ledger-name",
        default=DEFAULT_LEDGER_NAME,
        help=f"Override the AGL ledger name (default: {DEFAULT_LEDGER_NAME}).",
    )
    parser.add_argument(
        "--qr-code",
        default=None,
        help="Override the auto-generated QR code id (advanced; rarely needed).",
    )
    parser.add_argument(
        "--qr-code-prefix",
        default=DEFAULT_QR_PREFIX,
        help=f"Prefix for the auto-generated QR id (default: {DEFAULT_QR_PREFIX}).",
    )
    parser.add_argument("--notes", default="", help='Free-form notes appended to the event payload.')
    parser.add_argument(
        "--generation-source",
        default=None,
        help='Override the "This submission was generated using ..." footer.',
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the signed share text only; do not submit.")
    args = parser.parse_args(argv)

    # Local pre-flight: amount is numeric, proof URL points to TrueSightDAO GitHub.
    try:
        amount = float(args.donation_amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        parser.error(f"--donation-amount must be a positive number, got {args.donation_amount!r}")

    if not PROOF_URL_PATTERN.search(args.proof_url):
        parser.error(
            f"--proof-url must point to github.com/TrueSightDAO/... — got {args.proof_url!r}. "
            "Upload the photo to TrueSightDAO/.github (or another TrueSightDAO repo) first."
        )

    qr_code = (args.qr_code or generate_qr_code(args.qr_code_prefix)).strip()

    attached_filename = _basename_from_url(args.proof_url)
    cash_collected_iso = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    attrs: list[tuple[str, str]] = [
        ("QR Code", qr_code),
        ("Currency", args.currency),
        ("Donation Amount", f"{amount:g}"),  # 25.00 → "25", 25.5 → "25.5"
        ("Donor Name", args.donor_name),
        ("Donor Email", args.donor_email),
        ("Ledger Name", args.ledger_name),
        ("Cash collected at (UTC)", cash_collected_iso),
        ("Attached Filename", attached_filename),
        ("Destination Contribution File Location", args.proof_url),
    ]
    if args.notes.strip():
        attrs.append(("Notes", args.notes.strip()))

    client = EdgarClient.from_env()
    if args.generation_source:
        client.generation_source = args.generation_source

    if args.dry_run:
        _, _, share_text = client.sign(EVENT_NAME, attrs)
        print(share_text)
        print(f"\nGenerated QR Code: {qr_code}")
        return 0

    resp = client.submit(EVENT_NAME, attrs)
    print(f"HTTP {resp.status_code}")
    try:
        import json
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)

    if resp.ok:
        print(f"\nMinted QR Code: {qr_code}")
        print(
            "Next step — fire the SALES EVENT to flip MINTED → SOLD and land funds on the AGL ledger:\n"
            f"  python -m truesight_dao_client.modules.report_sales \\\n"
            f"    --item {qr_code} \\\n"
            f"    --sales-price {amount:g} \\\n"
            f'    --sold-by "<your-name>" --cash-proceeds-collected-by "<your-name>" \\\n'
            f"    --owner-email {args.donor_email} \\\n"
            f'    --stripe-session-id "(none)" --shipping-provider N/A --tracking-number N/A'
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
