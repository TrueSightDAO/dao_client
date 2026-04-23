#!/usr/bin/env python3
"""
Reader for `agroverse-freight-audit/pointers/freight_lanes.json`.

Registry of freight lanes (origin → destination pairs with pricing/time
metadata). Consumed by `dapp/shipping_planner.html`. Rarely changes —
manual / GAS publisher.

    python -m truesight_dao_client.cache.freight                                 # list every lane
    python -m truesight_dao_client.cache.freight --from "Altamira, Pará"         # lanes from that origin
    python -m truesight_dao_client.cache.freight --to "Singapore"                 # lanes to that destination
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from ._source import DataSource, GithubRawBackend


RAW_URL = "https://raw.githubusercontent.com/TrueSightDAO/agroverse-freight-audit/main/pointers/freight_lanes.json"


@dataclass
class FreightLanes:
    data: dict[str, Any] = field(default_factory=dict)
    source: DataSource = field(default_factory=lambda: GithubRawBackend(RAW_URL))

    @classmethod
    def fetch(cls, source: DataSource | None = None) -> "FreightLanes":
        src = source or GithubRawBackend(RAW_URL)
        return cls(data=src.fetch(), source=src)

    def lanes(self) -> list[dict[str, Any]]:
        return list(self.data.get("lanes") or [])

    def registry_id(self) -> str:
        return str(self.data.get("registry_id", ""))

    def filter(self, *, origin: str | None = None, destination: str | None = None) -> list[dict[str, Any]]:
        o = (origin or "").strip().lower()
        d = (destination or "").strip().lower()
        out = []
        for lane in self.lanes():
            if o and o not in str(lane.get("origin", "")).lower():
                continue
            if d and d not in str(lane.get("destination", "")).lower():
                continue
            out.append(lane)
        return out


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read agroverse-freight-audit/pointers/freight_lanes.json.")
    p.add_argument("--from", dest="origin", help="Filter lanes by origin (substring, case-insensitive).")
    p.add_argument("--to", dest="destination", help="Filter lanes by destination (substring, case-insensitive).")
    args = p.parse_args(argv)

    fl = FreightLanes.fetch()
    if args.origin or args.destination:
        results = fl.filter(origin=args.origin, destination=args.destination)
    else:
        results = fl.lanes()
    print(json.dumps({"registry_id": fl.registry_id(), "lanes": results}, indent=2))
    return 0


main = _cli

if __name__ == "__main__":
    sys.exit(_cli())
