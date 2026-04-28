#!/usr/bin/env python3
"""Submit ``[STORE ADD EVENT]`` to add a new row to the holistic-wellness Hit List.

Routes through the canonical async pattern (DApp / dao_client signs → Edgar
``/dao/submit_contribution`` → Telegram Chat Logs → ``WebhookTriggerWorker``
fires the ``processStoreAddsFromTelegramChatLogs`` GAS scanner → adds the row
to **Hit List** and records the Telegram row on **Store Adds** (the dedup log
on the Telegram compilation workbook so the same Telegram row is never parsed
twice).

Use case:
  When AI processes a referral email (e.g. *"Try Clary Sage / Casa de Ritual /
  La Sirena Botanica"*) or any other discovery surface, this CLI is the
  signed, audited, idempotent path to add the rows. Replaces the older
  ``dapp/stores_nearby.html`` Add Store form's direct-to-GAS POST for AI use.

Dedup: GAS ``addNewStore()`` already case-insensitively matches on
``(shop_name + address + city + state)`` and refuses to add a second row for
the same store; the GAS scanner preserves that protection. So submitting the
same shop twice is safe — the second attempt records ``status: duplicate`` on
**Store Adds** and points at the existing Hit List row.

Required:
  - ``./.env`` with EMAIL, PUBLIC_KEY, PRIVATE_KEY (run ``truesight-dao-auth login``).
  - ``--shop-name`` plus at least one of ``--address`` / ``--city`` / ``--state``
    (matches GAS ``createStoreKey_`` requirement; without one of those, dedup
    is unreliable and the GAS handler refuses the row).

Run:
  python -m truesight_dao_client.modules.add_hit_list_store --help

Convention:
  https://github.com/TrueSightDAO/agentic_ai_context/blob/main/OPEN_FOLLOWUPS.md
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

from ..edgar_client import EdgarClient

DEFAULT_GEN = (
    "https://github.com/TrueSightDAO/agentic_ai_context/blob/main/OPEN_FOLLOWUPS.md"
)
DEFAULT_STATUS = "Research"
EVENT_NAME = "STORE ADD EVENT"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Submit [STORE ADD EVENT] (signed) so a new row lands on the "
            "holistic-wellness Hit List via Edgar + GAS scanner. Dedup is at "
            "GAS (case-insensitive shop_name + address + city + state); "
            "submitting the same shop twice is safe."
        ),
    )
    # Required identity
    p.add_argument("--shop-name", required=True, help="Required. Maps to Hit List `Shop Name`.")
    p.add_argument(
        "--status",
        default=DEFAULT_STATUS,
        help=(
            f"Hit List `Status` for the new row. Default: {DEFAULT_STATUS!r}. "
            "Other valid values come from the Main Ledger `States` tab — "
            "see `tokenomics/SCHEMA.md` for the canonical list."
        ),
    )
    # Location (at least one required by GAS createStoreKey_)
    p.add_argument("--address", default="", help="Street address. At least one of address/city/state is required.")
    p.add_argument("--city", default="", help="City. At least one of address/city/state is required.")
    p.add_argument("--state", default="", help="State (US 2-letter abbreviation when applicable).")
    p.add_argument("--country", default="", help="Country (default empty; assumed US for state-only rows).")
    # Common Hit List fields
    p.add_argument("--shop-type", default="", help="`Metaphysical/Spiritual`, `Holistic`, etc. — values from Main Ledger `States` tab.")
    p.add_argument("--website", default="")
    p.add_argument("--instagram", default="", help="Instagram handle (with or without leading `@`).")
    p.add_argument("--phone", default="")
    p.add_argument("--cell-phone", default="")
    p.add_argument("--email", default="")
    p.add_argument("--owner-name", default="")
    p.add_argument("--contact-person", default="")
    # Provenance — explicitly captured so warm-lead chains stay searchable
    p.add_argument(
        "--referred-by",
        default="",
        help=(
            "Source of the referral (shop name, contributor name, URL, etc.). "
            "Lands on Hit List `Notes` and on the **Store Adds** dedup log so "
            "warm-lead chains stay traceable."
        ),
    )
    p.add_argument(
        "--notes",
        default="",
        help="Free-form remark. Concatenated with --referred-by in the Hit List Notes column.",
    )
    p.add_argument(
        "--submission-id",
        default="",
        help=(
            "Optional explicit Submission ID. Default: generate "
            "`STORE_ADD_<14-char timestamp>_<8-hex>` so retries / dedup work even "
            "when the same shop is referred multiple times."
        ),
    )
    p.add_argument(
        "--generation-source",
        default=DEFAULT_GEN,
        help="`This submission was generated using …` link. Default: OPEN_FOLLOWUPS convention doc.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print signed share text; do not POST to Edgar.")

    args = p.parse_args(argv)

    # Validate at least one location field
    if not (args.address.strip() or args.city.strip() or args.state.strip()):
        p.error(
            "At least one of --address / --city / --state is required "
            "(GAS createStoreKey_ refuses otherwise)."
        )

    # Build / accept the Submission ID (matches the SFR_… convention used for retail field reports).
    submission_id = (args.submission_id or "").strip()
    if not submission_id:
        import datetime as dt
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        submission_id = f"STORE_ADD_{ts}_{uuid.uuid4().hex[:8]}"

    client = EdgarClient.from_env()
    client.generation_source = args.generation_source.strip()

    # Event attributes — mirror the field names the GAS scanner parses
    # (`processStoreAddsFromTelegramChatLogs`). Order is significant only for
    # human readability of the signed text; GAS parses by label.
    attrs: list[tuple[str, str]] = []
    def _add(label: str, value: str) -> None:
        v = (value or "").strip()
        if v:
            attrs.append((label, v))

    _add("Submission ID", submission_id)
    _add("Shop Name", args.shop_name)
    _add("Status", args.status)
    _add("Shop Type", args.shop_type)
    _add("Address", args.address)
    _add("City", args.city)
    _add("State", args.state)
    _add("Country", args.country)
    _add("Website", args.website)
    _add("Instagram", args.instagram)
    _add("Phone", args.phone)
    _add("Cell Phone", args.cell_phone)
    _add("Email", args.email)
    _add("Owner Name", args.owner_name)
    _add("Contact Person", args.contact_person)
    _add("Referred By", args.referred_by)
    _add("Notes", args.notes)

    if args.dry_run:
        payload, txn_id, share_text = client.sign(EVENT_NAME, attrs)
        print(share_text)
        return 0

    resp = client.submit(EVENT_NAME, attrs)
    body = resp.text
    print(f"HTTP {resp.status_code}")
    print(body)
    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
