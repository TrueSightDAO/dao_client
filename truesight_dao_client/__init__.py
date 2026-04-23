"""TrueSight DAO / Edgar Python client and CLIs (installable as ``truesight-dao-client``)."""

from __future__ import annotations

from .edgar_client import EdgarClient, build_event_cli, generate_keypair

__all__ = ["EdgarClient", "build_event_cli", "generate_keypair", "__version__"]
__version__ = "0.1.0"
