#!/usr/bin/env python3
"""
Reader for `agroverse-inventory/currency-compositions/{request_id}.json`.

Per-request repackaging receipts — one JSON file per REPACKAGING BATCH EVENT.
This is an **audit log**: you read it to verify what happened, not to decide
what to do. Consumed by `dapp/repackaging_planner.html`.

    python -m truesight_dao_client.cache.compositions --list                              # request IDs in the repo
    python -m truesight_dao_client.cache.compositions --request 67c88267-b41c-4eab-…      # fetch one receipt

`--list` uses GitHub's contents API, which is rate-limited to **60 requests
per hour per IP** unauthenticated. If you hit the limit, set `GITHUB_TOKEN`
and pass it via header to lift to 5000/hr (not implemented here yet — open
an issue when you need it).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from ._source import DataSource, GithubContentsBackend, GithubRawBackend


RAW_BASE = "https://raw.githubusercontent.com/TrueSightDAO/agroverse-inventory/main/currency-compositions"
CONTENTS_URL = "https://api.github.com/repos/TrueSightDAO/agroverse-inventory/contents/currency-compositions"


@dataclass
class CurrencyCompositions:
    fetch_source: DataSource = field(default_factory=lambda: GithubRawBackend(RAW_BASE))
    list_source: DataSource = field(default_factory=lambda: GithubContentsBackend(CONTENTS_URL))

    def fetch(self, request_id: str) -> dict[str, Any]:
        suffix = request_id.strip()
        if not suffix.endswith(".json"):
            suffix += ".json"
        return self.fetch_source.fetch(path_suffix=suffix)

    def list_request_ids(self) -> list[str]:
        entries = self.list_source.fetch() or []
        ids: list[str] = []
        for entry in entries:
            name = entry.get("name", "")
            if name.endswith(".json"):
                ids.append(name[:-5])
        return sorted(ids)


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read TrueSightDAO/agroverse-inventory/currency-compositions/*.json receipts.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="List request IDs present in the repo.")
    g.add_argument("--request", help="Fetch one receipt by request ID (uuid, with or without .json).")
    args = p.parse_args(argv)

    cc = CurrencyCompositions()
    if args.list:
        ids = cc.list_request_ids()
        print(json.dumps(ids, indent=2))
        return 0
    print(json.dumps(cc.fetch(args.request), indent=2))
    return 0


main = _cli

if __name__ == "__main__":
    sys.exit(_cli())
