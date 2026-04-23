#!/usr/bin/env python3
"""Backward-compatible re-exports; prefer ``from truesight_dao_client import EdgarClient`` or ``truesight_dao_client.edgar_client``."""

from __future__ import annotations

from truesight_dao_client.edgar_client import (
    DEFAULT_EDGAR_BASE,
    DEFAULT_GENERATION_SOURCE,
    DEFAULT_VERIFY_URL,
    EdgarClient,
    build_event_cli,
    build_payload,
    build_share_text,
    generate_keypair,
    load_private_key,
    load_public_key,
    sign_payload,
    verify_signature,
)

__all__ = [
    "DEFAULT_EDGAR_BASE",
    "DEFAULT_GENERATION_SOURCE",
    "DEFAULT_VERIFY_URL",
    "EdgarClient",
    "build_event_cli",
    "build_payload",
    "build_share_text",
    "generate_keypair",
    "load_private_key",
    "load_public_key",
    "sign_payload",
    "verify_signature",
]
