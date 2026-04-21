#!/usr/bin/env python3
"""
Python emulation of dapp.truesight.me/create_signature.html.

Generates an RSA-2048 (RSASSA-PKCS1-v1_5 / SHA-256) key pair that matches the
WebCrypto flow used by the DApp, persists it into `.env`, and submits an
EMAIL REGISTERED EVENT to the Edgar endpoint so the contributor gets a
verification email.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from dotenv import load_dotenv, set_key

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

EDGAR_BASE = "https://edgar.truesight.me"
EDGAR_SUBMIT_URL = f"{EDGAR_BASE}/dao/submit_contribution"
VERIFY_URL = "https://dapp.truesight.me/verify_request.html"
GENERATION_SOURCE = "https://dapp.truesight.me/create_signature.html"


def generate_key_pair() -> tuple[str, str, rsa.RSAPrivateKey]:
    """Generate a 2048-bit RSA key pair. Returns (public_b64_spki, private_b64_pkcs8, key)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return (
        base64.b64encode(pub_der).decode("ascii"),
        base64.b64encode(priv_der).decode("ascii"),
        private_key,
    )


def load_private_key(private_b64: str) -> rsa.RSAPrivateKey:
    der = base64.b64decode(private_b64)
    return serialization.load_der_private_key(der, password=None)


def build_payload(event_name: str, attributes: dict[str, str]) -> str:
    """Mirror EdgarPayloadHelper.buildPayloadString."""
    lines = []
    for label, raw in attributes.items():
        value = "N/A" if raw is None else str(raw)
        if "\n" in value:
            value = value.replace("\r\n", "\n").replace("\n", "\n  ")
        lines.append(f"- {label}: {value}")
    return f"[{event_name.strip()}]\n" + "\n".join(lines) + "\n--------"


def sign_payload(private_key: rsa.RSAPrivateKey, payload: str) -> str:
    sig = private_key.sign(
        payload.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def build_share_text(payload: str, request_txn_id: str, public_key_b64: str) -> str:
    return (
        f"{payload}\n\n"
        f"My Digital Signature: {public_key_b64}\n\n"
        f"Request Transaction ID: {request_txn_id}\n\n"
        f"This submission was generated using {GENERATION_SOURCE}\n\n"
        f"Verify submission here: {VERIFY_URL}"
    )


def verify_signature(public_b64: str, payload: str, request_txn_id: str) -> bool:
    pub_der = base64.b64decode(public_b64)
    public_key = serialization.load_der_public_key(pub_der)
    try:
        public_key.verify(
            base64.b64decode(request_txn_id),
            payload.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def ensure_env_with_keys() -> dict[str, str]:
    """Return dict with EMAIL / PUBLIC_KEY / PRIVATE_KEY, creating .env if absent."""
    load_dotenv(ENV_PATH)
    email = os.getenv("EMAIL") or "garyjob@gmail.com"
    public_b64 = os.getenv("PUBLIC_KEY")
    private_b64 = os.getenv("PRIVATE_KEY")

    if not ENV_PATH.exists():
        ENV_PATH.touch(mode=0o600)

    # Always make sure EMAIL is persisted so it's visible on disk.
    set_key(str(ENV_PATH), "EMAIL", email, quote_mode="never")

    if not public_b64 or not private_b64:
        print("No key pair in .env — generating a new RSA-2048 pair.")
        public_b64, private_b64, _ = generate_key_pair()
        set_key(str(ENV_PATH), "PUBLIC_KEY", public_b64, quote_mode="never")
        set_key(str(ENV_PATH), "PRIVATE_KEY", private_b64, quote_mode="never")
        ENV_PATH.chmod(0o600)
        print(f"Keys written to {ENV_PATH} (chmod 600).")
    else:
        print(f"Reusing existing key pair from {ENV_PATH}.")

    return {"EMAIL": email, "PUBLIC_KEY": public_b64, "PRIVATE_KEY": private_b64}


def submit_email_registration(email: str, public_b64: str, private_b64: str) -> requests.Response:
    payload = build_payload(
        "EMAIL REGISTERED EVENT",
        {"Email": email.strip().lower()},
    )
    private_key = load_private_key(private_b64)
    request_txn_id = sign_payload(private_key, payload)

    # Sanity check: verify locally before hitting the wire.
    assert verify_signature(public_b64, payload, request_txn_id), "local signature verify failed"

    share_text = build_share_text(payload, request_txn_id, public_b64)

    # Mirror the browser FormData multipart POST.
    resp = requests.post(
        EDGAR_SUBMIT_URL,
        files={"text": (None, share_text)},
        timeout=30,
    )
    return resp


def main() -> int:
    env = ensure_env_with_keys()
    print(f"Email: {env['EMAIL']}")
    print(f"Public key (first 40 chars): {env['PUBLIC_KEY'][:40]}…")

    print(f"POST {EDGAR_SUBMIT_URL}")
    resp = submit_email_registration(env["EMAIL"], env["PUBLIC_KEY"], env["PRIVATE_KEY"])
    print(f"HTTP {resp.status_code}")
    print(resp.text)

    if resp.status_code == 409:
        print(
            "\nEdgar says this submission was already processed — the browser key "
            "may already be active or pending. Check your inbox."
        )
        return 0
    if not resp.ok:
        print("\nSubmission failed. Inspect the response body above.")
        return 1

    print("\nSubmission accepted. Check the registered inbox for a verification link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
