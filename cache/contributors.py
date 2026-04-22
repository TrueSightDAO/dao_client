#!/usr/bin/env python3
"""
Reader for DAO member info — voting rights + contributor name lookups.

**Today (2026-04):** backed by the GAS web app at
`AKfycbygmwRbyqse…/exec` — the same one `dapp/tdg_balance.js` hits for the
in-browser TDG balance badge. Per-public-key query; no list endpoint.

**Future:** switch the default source to a `GithubRawBackend` pointing at a
forthcoming `dao_members.json` (proposed cache under `TrueSightDAO/
treasury-cache` or a new `contributors-cache` repo, published on every
CONTRIBUTION EVENT + safety-net cron by `tdg_identity_management`). Callers
stay untouched, but the **internal lookup path changes** — a contributor
has 1:N active public keys (see `agentic_ai_context` memory
`project_edgar_multiple_active_keys`), so `for_public_key(pk)` must scan
`contributors[*].public_keys[*]` instead of relying on the GAS endpoint's
server-side signature filter. Proposed cache shape:

    {
      "generated_at": "...", "schema_version": 1,
      "contributors": [
        {
          "name": "Gary Teh",
          "voting_rights": 955414.06,
          "asset_per_circulated_voting_right": 0.00644,
          "public_keys": [
            {"public_key": "MIIB...", "status": "ACTIVE", "created_at": "...", "last_active_at": "..."}
          ]
        }
      ]
    }

CLI:
    python3 -m cache.contributors                      # look up self via .env PUBLIC_KEY
    python3 -m cache.contributors --pubkey MIIB...     # look up someone else
    python3 -m cache.contributors --list               # pending GitHub cache — errors today
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cache._source import DataSource, GasBackend
    from edgar_client import EdgarClient
else:
    from ._source import DataSource, GasBackend
    from edgar_client import EdgarClient  # type: ignore[import-not-found]


# `assetVerify` GAS web app (see dapp/tdg_balance.js). `full=true` returns the
# expanded record: voting_rights, asset_per_circulated_voting_right, etc.
GAS_EXEC_URL = "https://script.google.com/macros/s/AKfycbygmwRbyqse-dpCYMco0rb93NSgg-Jc1QIw7kUiBM7CZK6jnWnMB5DEjdoX_eCsvVs7/exec"

# Placeholder for the future GitHub-raw cache. Flip `DEFAULT_SOURCE` when this
# exists; see module docstring.
GITHUB_RAW_URL_PLACEHOLDER = "https://raw.githubusercontent.com/TrueSightDAO/treasury-cache/main/dao_members.json"


def _default_lookup_source() -> DataSource:
    return GasBackend(GAS_EXEC_URL, base_params={"full": "true"})


@dataclass
class Contributors:
    """Per-public-key voting-rights lookups (today GAS-backed)."""

    source: DataSource = field(default_factory=_default_lookup_source)

    # ---- lookups -----------------------------------------------------------

    def for_public_key(self, public_key_b64: str) -> dict[str, Any]:
        return self.source.fetch(signature=public_key_b64)

    def for_self(self) -> dict[str, Any]:
        client = EdgarClient.from_env()
        return self.for_public_key(client.public_key_b64)

    # ---- list ---------------------------------------------------------------

    def list_all(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Full contributor list is not yet published to GitHub. "
            "See module docstring for the planned tdg_identity_management → dao_members.json path. "
            "Until then, use `for_self()` or `for_public_key(pk)` for per-key lookups."
        )


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Look up DAO contributor voting rights / name.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pubkey", help="SPKI base64 public key to look up.")
    g.add_argument("--list", action="store_true", help="Full member list (pending GitHub cache — errors today).")
    args = p.parse_args(argv)

    contributors = Contributors()
    if args.list:
        print(json.dumps(contributors.list_all(), indent=2))
        return 0

    record = contributors.for_public_key(args.pubkey) if args.pubkey else contributors.for_self()
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
