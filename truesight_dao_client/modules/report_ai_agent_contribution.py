#!/usr/bin/env python3
"""Submit [CONTRIBUTION EVENT] for AI agent work to Edgar (signed, DApp-equivalent).

Convention (full detail):
  https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md

Requires:
  - ``./.env`` (cwd) with EMAIL, PUBLIC_KEY, PRIVATE_KEY (see README / ``truesight-dao-auth login``).
  - At least one --pr URL under https://github.com/TrueSightDAO/ (merged or open PR).

Run:
  python -m truesight_dao_client.modules.report_ai_agent_contribution --help
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from ..edgar_client import EdgarClient

DEFAULT_TYPE = "AI Agent (software & documentation)"
DEFAULT_GEN = (
    "https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md"
)
PR_PATTERN = re.compile(
    r"^https://github\.com/TrueSightDAO/[^/]+/pull/\d+/?(\?.*)?$",
    re.IGNORECASE,
)


def _contributors_from_email(email: str) -> str:
    email = (email or "").strip()
    if "@" in email:
        return email.split("@", 1)[0].replace(".", " ").title() + f" <{email}>"
    return email or "AI Agent"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Submit [CONTRIBUTION EVENT] for AI agent work with mandatory TrueSightDAO PR links.",
    )
    p.add_argument("--title", required=True, help="Short title (prepended to Description).")
    p.add_argument(
        "--body",
        default=None,
        help="Multi-line description (include PR URLs here too). Use --body-file for long text.",
    )
    p.add_argument(
        "--body-file",
        default=None,
        metavar="PATH",
        help="Read description body from file (UTF-8).",
    )
    p.add_argument(
        "--pr",
        action="append",
        default=[],
        metavar="URL",
        help="Repeatable. Must match https://github.com/TrueSightDAO/<repo>/pull/<n>",
    )
    p.add_argument("--type", default=DEFAULT_TYPE, metavar="TYPE", help=f"Contribution Type (default: {DEFAULT_TYPE})")
    p.add_argument("--amount", default="0", help='Maps to "Amount" (default 0 for non-monetary agent work).')
    p.add_argument("--tdg-issued", default="0", dest="tdg_issued", help='Maps to "TDG Issued" (default 0).')
    p.add_argument(
        "--contributors",
        default=None,
        help='Maps to "Contributor(s)". Default: derived from EMAIL in .env.',
    )
    p.add_argument(
        "--generation-source",
        default=DEFAULT_GEN,
        help="This submission was generated using … (default: agentic_ai_context convention doc).",
    )
    p.add_argument("--dry-run", action="store_true", help="Print signed share text; do not POST.")
    args = p.parse_args(argv)

    if args.body and args.body_file:
        p.error("Use only one of --body or --body-file")

    body = args.body or ""
    if args.body_file:
        path = os.path.abspath(args.body_file)
        with open(path, "r", encoding="utf-8") as f:
            body = f.read()
    body = body.strip()
    if not body:
        p.error("Description body is required (--body or --body-file)")

    prs = list(args.pr or [])
    if not prs:
        p.error("At least one --pr URL is required (TrueSightDAO org pull request).")
    for url in prs:
        u = url.strip()
        if not PR_PATTERN.match(u):
            p.error(f"Invalid --pr (must be TrueSightDAO pull URL): {u!r}")

    pr_block = "Pull requests (GitHub evidence):\n" + "\n".join(f"- {u.strip()}" for u in prs)
    description = f"{args.title.strip()}\n\n{pr_block}\n\nDetails:\n{body}"

    client = EdgarClient.from_env()
    client.generation_source = args.generation_source.strip()

    contributors = args.contributors or _contributors_from_email(client.email)

    attrs: list[tuple[str, str]] = [
        ("Type", args.type),
        ("Amount", str(args.amount)),
        ("Description", description),
        ("Contributor(s)", contributors),
        ("TDG Issued", str(args.tdg_issued)),
        ("Attached Filename", "N/A"),
        ("Destination Contribution File Location", "N/A"),
    ]

    event_name = "CONTRIBUTION EVENT"
    if args.dry_run:
        payload, txn_id, share_text = client.sign(event_name, attrs)
        print(share_text)
        return 0

    resp = client.submit(event_name, attrs)
    print(f"HTTP {resp.status_code}")
    try:
        import json

        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    return 0 if resp.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
