#!/usr/bin/env python3
"""Submit a [DAPP PERMISSION CHANGE EVENT] from the terminal.

Governor-only. Each call edits one action's ``required_roles`` array on
``treasury-cache/permissions.json`` end-to-end via the same Edgar →
Telegram Chat Logs → GAS pipeline that the DApp's permissions viewer
uses (`dapp/governor_permissions.html` edit mode). Real authorization
is the per-event RSA signature + Governors-tab membership check inside
the GAS handler — no shared secret on the wire.

Spec:
  https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAPP_PERMISSION_CHANGE_FLOW.md

Requires:
  - ``./.env`` with EMAIL, PUBLIC_KEY, PRIVATE_KEY (see README / `auth.py login`).
    Signer's display name must currently appear on the Governors tab on Main
    Ledger; otherwise the GAS handler rejects with status=unauthorized.

Run:
  python -m truesight_dao_client.modules.report_dapp_permission_change --help

Examples:
  # Promote contributor.add to also accept operator (auto-resolves
  # the current Required Roles (before) + Manifest Schema Version
  # from raw.githubusercontent.com):
  python -m truesight_dao_client.modules.report_dapp_permission_change \
      --action contributor.add \
      --roles-after "governor,operator"

  # Explicit roles-before + schema-version (skip the auto-fetch):
  python -m truesight_dao_client.modules.report_dapp_permission_change \
      --action governor_chat.access \
      --roles-before governor \
      --roles-after "governor,member" \
      --schema-version 1

  # Print the signed payload for review without POSTing:
  python -m truesight_dao_client.modules.report_dapp_permission_change \
      --action contributor.add \
      --roles-after "governor,operator" \
      --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone

from ..edgar_client import EdgarClient

DEFAULT_GEN = (
    "https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAPP_PERMISSION_CHANGE_FLOW.md"
)
PERMISSIONS_RAW_URL = (
    "https://raw.githubusercontent.com/TrueSightDAO/treasury-cache/main/permissions.json"
)
EVENT_NAME = "DAPP PERMISSION CHANGE EVENT"


def _parse_roles(s: str) -> list[str]:
    if s is None:
        return []
    return [r.strip() for r in str(s).split(",") if r.strip()]


def _fetch_permissions_manifest() -> dict:
    with urllib.request.urlopen(PERMISSIONS_RAW_URL, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_action(manifest: dict, action: str) -> tuple[str, dict] | None:
    """Return (bucket_name, def_dict) for the action, or None."""
    actions = manifest.get("actions") or {}
    deferred = manifest.get("deferred_actions") or {}
    if action in actions:
        return ("actions", actions[action])
    if action != "comment" and action in deferred:
        return ("deferred_actions", deferred[action])
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Submit a [DAPP PERMISSION CHANGE EVENT] to Edgar to edit one action's "
            "required_roles on treasury-cache/permissions.json. Governor-only."
        ),
    )
    p.add_argument(
        "--action",
        required=True,
        help='The action key to edit (e.g. "contributor.add").',
    )
    p.add_argument(
        "--roles-after",
        required=True,
        help='Comma-separated new roles, e.g. "governor,operator". Empty string makes the action public.',
    )
    p.add_argument(
        "--roles-before",
        default=None,
        help=(
            "Comma-separated current roles. Optional — auto-resolved from the live manifest if omitted. "
            "Pass explicitly only when you want to override the optimistic-concurrency check baseline."
        ),
    )
    p.add_argument(
        "--schema-version",
        default=None,
        help="Manifest schema version (auto-resolved from the live manifest if omitted).",
    )
    p.add_argument(
        "--generation-source",
        default=DEFAULT_GEN,
        help='"This submission was generated using …" (default: spec doc).',
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the signed share text; do not POST.",
    )
    args = p.parse_args(argv)

    after = _parse_roles(args.roles_after)
    # Empty roles_after is intentional ("public"); we keep the empty list.

    manifest = None
    before: list[str] | None = None
    if args.roles_before is not None:
        before = _parse_roles(args.roles_before)
    schema_version = args.schema_version

    if before is None or schema_version is None:
        try:
            manifest = _fetch_permissions_manifest()
        except Exception as e:
            sys.stderr.write(f"Failed to fetch live permissions.json from {PERMISSIONS_RAW_URL}: {e}\n")
            return 2
        resolved = _resolve_action(manifest, args.action)
        if not resolved:
            keys = sorted(
                list((manifest.get("actions") or {}).keys())
                + [k for k in (manifest.get("deferred_actions") or {}).keys() if k != "comment"]
            )
            sys.stderr.write(
                f"Action {args.action!r} not found in live manifest.\n"
                f"Known actions: {', '.join(keys)}\n"
            )
            return 2
        _, def_dict = resolved
        if before is None:
            before = list(def_dict.get("required_roles") or [])
        if schema_version is None:
            schema_version = manifest.get("schema_version")

    if before is None:
        sys.stderr.write("Could not determine --roles-before.\n")
        return 2
    if schema_version is None:
        sys.stderr.write("Could not determine --schema-version.\n")
        return 2

    # Surface a no-op early so the operator knows nothing will change.
    if sorted(before) == sorted(after):
        sys.stderr.write(
            f"No-op: roles-before {before!r} == roles-after {after!r}. "
            "Nothing to submit.\n"
        )
        return 0

    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    submission_source = (
        "dao_client://truesight_dao_client.modules.report_dapp_permission_change"
    )

    attrs: list[tuple[str, str]] = [
        ("Action", args.action.strip()),
        ("Required Roles (before)", ", ".join(before)),
        ("Required Roles (after)", ", ".join(after)),
        ("Manifest Schema Version", str(schema_version)),
        ("Submitted At", submitted_at),
        ("Submission Source", submission_source),
    ]

    client = EdgarClient.from_env()
    client.generation_source = args.generation_source.strip()

    if args.dry_run:
        _, _, share_text = client.sign(EVENT_NAME, attrs)
        print(share_text)
        return 0

    print(f"Action:        {args.action}")
    print(f"Roles before:  {before!r}")
    print(f"Roles after:   {after!r}")
    print(f"Schema:        v{schema_version}")
    print()

    resp = client.submit(EVENT_NAME, attrs)
    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)

    if resp.ok:
        print()
        print(
            "Edgar accepted the event. Outcome will appear on the "
            "'Dapp Permission Changes' tab once the GAS handler processes it "
            "(typically <30s):"
        )
        print(
            "  https://docs.google.com/spreadsheets/d/"
            "1qbZZhf-_7xzmDTriaJVWj6OZshyQsFkdsAV8-pyzASQ/edit?gid=1054656840"
        )
        print(
            "Or open the diff on treasury-cache once it commits:"
            "\n  https://github.com/TrueSightDAO/treasury-cache/commits/main/permissions.json"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
