#!/usr/bin/env python3
"""Submit ``[RETAIL FIELD REPORT EVENT]`` to update a Hit List store row.

Routes through the canonical async pattern (DApp / dao_client signs → Edgar
``/dao/submit_contribution`` → Telegram Chat Logs → ``WebhookTriggerWorker``
fires the ``processRetailFieldReportsFromTelegramChatLogs`` GAS scanner →
updates **Hit List** Status / contact fields, appends to **DApp Remarks**,
and records a row on **Stores Visits Field Reports** as the dedup log.

Use cases:
  - Mark a referring shop as ``Not Appropriate`` after a polite-no email
    (e.g. *"We don't carry consumables, try Clary Sage instead"* — same
    flow `dapp/store_interaction_history.html` exposes via the **Update
    Store Information** form, just from the CLI).
  - Move a shop through the pipeline (``Manager Follow-up`` → ``Followed
    Up`` → ``Partnered``) from automation.
  - Backfill / batch-correct Hit List statuses with audit-trail signatures.

Required:
  - ``./.env`` with EMAIL, PUBLIC_KEY, PRIVATE_KEY (run ``truesight-dao-auth login``).
  - ``--shop-name`` (must match the Hit List ``Shop Name`` for an existing row).

Run:
  python -m truesight_dao_client.modules.update_store --help

Convention:
  https://github.com/TrueSightDAO/agentic_ai_context/blob/main/OPEN_FOLLOWUPS.md

Attachments are intentionally NOT supported in this v1 — the DApp page
uploads attachments to ``TrueSightDAO/store_interaction_attachments`` via
Edgar's GitHub PAT after deriving a deterministic blob URL. Adding that
to the CLI is a non-trivial second slice (file hashing + URL
construction + GitHub PUT timing) and most CLI use cases (status
updates, remark logging, follow-up scheduling) don't need a file.
File a follow-up in OPEN_FOLLOWUPS if attachment support becomes a
recurring need.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import uuid

from ..edgar_client import EdgarClient

DEFAULT_GEN = (
    "https://github.com/TrueSightDAO/agentic_ai_context/blob/main/OPEN_FOLLOWUPS.md"
)
EVENT_NAME = "RETAIL FIELD REPORT EVENT"


def _store_key_from_shop(shop_name: str, address: str, city: str, state: str) -> str:
    """Mirror the DApp's ``createStoreKey_`` (lowercase, hyphenate, double-underscore-separated)
    so the GAS scanner sees the same key the existing DApp pages produce.
    Used purely for the optional Store Key column on the audit row; not load-bearing
    for the actual update_status (which keys on shop_name)."""
    def slug(s: str) -> str:
        s = (s or "").strip().lower()
        if not s:
            return ""
        # Lowercase ASCII, replace non-alnum with hyphens, collapse multiples.
        out = []
        prev_dash = False
        for ch in s:
            if ch.isalnum():
                out.append(ch)
                prev_dash = False
            elif not prev_dash:
                out.append("-")
                prev_dash = True
        return "".join(out).strip("-")

    parts = [slug(shop_name), slug(address), slug(city), slug(state)]
    parts = [p for p in parts if p]
    return "__".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Submit [RETAIL FIELD REPORT EVENT] (signed) so an existing Hit "
            "List row's Status / contact fields update via Edgar + GAS "
            "scanner. CLI counterpart to dapp/store_interaction_history.html."
        ),
    )
    # Identity (required)
    p.add_argument("--shop-name", required=True, help="Required. Must match the Hit List `Shop Name`.")
    # The event the operator is recording — at least one of these is the point of the call.
    p.add_argument("--new-status", default="", help="New Hit List `Status` value (e.g. `Not Appropriate`, `Manager Follow-up`, `Partnered`). Values from Main Ledger `States` tab.")
    p.add_argument("--previous-status", default="", help="Optional — the prior status for audit clarity. Only stamped on the signed text; the GAS scanner reads the row's current status anyway.")
    p.add_argument("--remarks", default="", help="Free-form remark; lands on DApp Remarks col D and on Hit List `Sales Process Notes` (timestamp + signature prefix added by GAS).")
    # Hit List columns (any of these will be applied if non-blank)
    p.add_argument("--shop-type", default="")
    p.add_argument("--owner-name", default="")
    p.add_argument("--contact-person", default="")
    p.add_argument("--email", default="")
    p.add_argument("--phone", default="")
    p.add_argument("--cell-phone", default="")
    p.add_argument("--website", default="")
    p.add_argument("--instagram", default="")
    p.add_argument("--visit-date", default="", help="ISO date or `MM/DD/YYYY` per Hit List convention.")
    p.add_argument("--contact-date", default="")
    p.add_argument("--follow-up-date", default="")
    p.add_argument("--contact-method", default="", help="`email`, `phone`, `in-person`, etc.")
    # Store Key / Update ID — both auto-generated when absent
    p.add_argument(
        "--store-key",
        default="",
        help=(
            "Hit List Store Key (mirror of DApp `createStoreKey_`). When omitted "
            "and --address/--city/--state are provided, it's derived from those."
        ),
    )
    p.add_argument("--address", default="", help="Used to derive Store Key when --store-key is omitted.")
    p.add_argument("--city", default="", help="Used to derive Store Key when --store-key is omitted.")
    p.add_argument("--state", default="", help="Used to derive Store Key when --store-key is omitted.")
    p.add_argument(
        "--update-id",
        default="",
        help=(
            "Optional explicit Update ID. Default: generate `SFR_<14-digit timestamp>` "
            "matching the DApp convention so the GAS scanner's dedup-log on "
            "**Stores Visits Field Reports** col G works."
        ),
    )
    p.add_argument(
        "--generation-source",
        default=DEFAULT_GEN,
        help="`This submission was generated using …` link. Default: OPEN_FOLLOWUPS convention doc.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print signed share text; do not POST to Edgar.")

    args = p.parse_args(argv)

    # Soft validation — at least one of new_status / remarks / a contact field
    # should be present, or this submission has no effect.
    has_change = any([
        args.new_status.strip(),
        args.remarks.strip(),
        args.shop_type.strip(),
        args.owner_name.strip(),
        args.contact_person.strip(),
        args.email.strip(),
        args.phone.strip(),
        args.cell_phone.strip(),
        args.website.strip(),
        args.instagram.strip(),
        args.visit_date.strip(),
        args.contact_date.strip(),
        args.follow_up_date.strip(),
        args.contact_method.strip(),
    ])
    if not has_change:
        p.error("Provide at least one of --new-status / --remarks / a contact field — otherwise this submission has nothing to apply.")

    # Auto-generate Update ID if absent (matches DApp `SFR_<timestamp>` shape).
    update_id = args.update_id.strip()
    if not update_id:
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        update_id = f"SFR_{ts}"

    # Auto-derive Store Key when not provided.
    store_key = args.store_key.strip()
    if not store_key:
        store_key = _store_key_from_shop(args.shop_name, args.address, args.city, args.state)

    client = EdgarClient.from_env()
    client.generation_source = args.generation_source.strip()

    # Event attributes — labels match the DApp's signed text exactly so
    # parse_retail_field_report (Edgar) and parseRetailFieldReportText_
    # (GAS) read them without changes.
    attrs: list[tuple[str, str]] = []

    def _add(label: str, value: str) -> None:
        v = (value or "").strip()
        if v:
            attrs.append((label, v))

    _add("Shop Name", args.shop_name)
    _add("Store Key", store_key)
    _add("Update ID", update_id)
    _add("New Status", args.new_status)
    _add("Previous Status", args.previous_status)
    _add("Shop Type", args.shop_type)
    _add("Owner Name", args.owner_name)
    _add("Contact Person", args.contact_person)
    _add("Email", args.email)
    _add("Phone", args.phone)
    _add("Cell Phone", args.cell_phone)
    _add("Website", args.website)
    _add("Instagram", args.instagram)
    _add("Visit Date", args.visit_date)
    _add("Contact Date", args.contact_date)
    _add("Follow Up Date", args.follow_up_date)
    _add("Contact Method", args.contact_method)
    _add("Remarks", args.remarks)

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
