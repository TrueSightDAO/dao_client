#!/usr/bin/env python3
"""Backward-compatible wrapper; prefer ``python -m truesight_dao_client.auth`` or ``truesight-dao-auth``."""

from __future__ import annotations

import sys

from truesight_dao_client.auth import main

if __name__ == "__main__":
    raise SystemExit(main())
