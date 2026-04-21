#!/usr/bin/env python3
"""
CLI auth for TrueSight DAO / Edgar.

Subcommands:
    login          register this machine's keypair and finalise via email click (loopback flow)
    verify         manual fallback — submit EMAIL VERIFICATION EVENT for a pasted vk
    status         ask Edgar whether the stored public key is ACTIVE / VERIFYING / unknown
    rotate         wipe keys from .env, regenerate, and start a fresh login

The loopback flow mirrors the OAuth out-of-band pattern:
    1. We sign an [EMAIL REGISTERED EVENT] whose "generation source" is
       http://127.0.0.1:<port>/verify on this machine.
    2. Edgar hands that URL to the Apps Script mailer, so the email link points
       at our listener instead of dapp.truesight.me.
    3. Clicking the email link (on this same machine) hits the listener with
       ?em=<email>&vk=<verification key>.
    4. The CLI signs [EMAIL VERIFICATION EVENT] with the same keypair and POSTs
       it to Edgar. Edgar writes column H (Verification Key Consumed), row
       flips to ACTIVE.

If you click the email link on a different device (phone, etc.), fall back to
`python auth.py verify --vk <value>`.
"""
from __future__ import annotations

import argparse
import http.server
import json
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from edgar_client import EdgarClient, generate_keypair

DEFAULT_EMAIL_FALLBACK = "garyjob@gmail.com"
LOOPBACK_TIMEOUT_SECONDS = 10 * 60  # 10 minutes


# ---------------------------------------------------------------------- server


@dataclass
class Capture:
    email: str
    verification_key: str


class _CaptureHandler(http.server.BaseHTTPRequestHandler):
    capture: Capture | None = None  # class-level shared state

    def do_GET(self):  # noqa: N802 (http.server API)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/verify":
            self.send_response(404)
            self.end_headers()
            return
        qs = dict(urllib.parse.parse_qsl(parsed.query))
        vk = (qs.get("vk") or "").strip()
        em = (qs.get("em") or "").strip()
        if not vk or not em:
            self._respond(400, b"Missing 'em' or 'vk' in query string.", "text/plain")
            return
        _CaptureHandler.capture = Capture(email=em, verification_key=vk)
        body = (
            b"<!doctype html><html><head><meta charset='utf-8'>"
            b"<title>Signature received</title></head>"
            b"<body style='font-family:sans-serif;max-width:560px;margin:4rem auto;"
            b"padding:2rem;background:#f5f5f5;border-radius:8px;'>"
            b"<h2>Verification received</h2>"
            b"<p>Your CLI is finalising the signature with Edgar &mdash; "
            b"check the terminal for the result.</p>"
            b"<p>You can close this tab.</p>"
            b"</body></html>"
        )
        self._respond(200, body, "text/html; charset=utf-8")

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args, **_kwargs):  # silence default stderr noise
        return


def _start_listener() -> tuple[socketserver.TCPServer, int]:
    _CaptureHandler.capture = None
    server = socketserver.TCPServer(("127.0.0.1", 0), _CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _await_capture(server: socketserver.TCPServer, timeout_s: int) -> Capture | None:
    deadline = time.time() + timeout_s
    try:
        while time.time() < deadline:
            if _CaptureHandler.capture is not None:
                return _CaptureHandler.capture
            time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()
    return _CaptureHandler.capture


# ----------------------------------------------------------------- subcommands


def _ensure_keys(email: str, *, rotate: bool) -> EdgarClient:
    env = EdgarClient.env_path()
    existing = None
    if env.exists() and not rotate:
        try:
            existing = EdgarClient.from_env()
        except RuntimeError:
            existing = None
    if existing and existing.email == email:
        print(f"Reusing keypair in {env} (public key tail …{existing.public_key_b64[-24:]}).")
        return existing

    if rotate and env.exists():
        print(f"Rotating keys in {env} …")
    elif existing and existing.email != email:
        print(f".env email {existing.email!r} != requested {email!r}; rotating keys.")
    else:
        print(f"Generating new RSA-2048 keypair into {env} …")

    pub, priv = generate_keypair()
    EdgarClient.write_env(email, pub, priv)
    print(f"  pub tail: …{pub[-24:]}")
    return EdgarClient(email=email, public_key_b64=pub, private_key_b64=priv)


def _loopback_generation_source(port: int) -> str:
    return f"http://127.0.0.1:{port}/verify"


def _cmd_login(args: argparse.Namespace) -> int:
    email = (args.email or DEFAULT_EMAIL_FALLBACK).strip().lower()

    # Key management first so we can report the keypair before the listener starts.
    client = _ensure_keys(email, rotate=False)

    # If Edgar already knows this key, short-circuit the mail round-trip.
    if not args.force:
        resp = client.check_signature()
        if resp.ok:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if data.get("registered"):
                print(f"This key is already ACTIVE on Edgar for {data.get('contributor_email') or email}. No action needed.")
                return 0
            if data.get("pending_verification"):
                print(
                    "This key is pending verification on Edgar. Either click the earlier email link, "
                    "run `auth.py verify --vk <value>` with a vk you still have, or `auth.py rotate --email <addr>`."
                )
                return 0

    # Spin up the loopback listener first so we can include its port in generationSource.
    server, port = _start_listener()
    client.generation_source = _loopback_generation_source(port)
    print(f"Loopback listener on http://127.0.0.1:{port}/verify (waits up to {LOOPBACK_TIMEOUT_SECONDS // 60} min).")

    print(f"POST {client.base_url}/dao/submit_contribution  (EMAIL REGISTERED EVENT, email={email})")
    resp = client.submit("EMAIL REGISTERED EVENT", {"Email": email})
    print(f"  HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not resp.ok:
        print(resp.text)
        server.shutdown()
        server.server_close()
        return 1

    er = data.get("email_registration") or {}
    if er.get("skipped"):
        print(
            "Edgar skipped sending a new verification email — this key is already pending or active.\n"
            "Click the earlier email, or run `auth.py rotate` to start fresh."
        )
        server.shutdown()
        server.server_close()
        return 0
    if not er.get("verification_email_sent"):
        print(f"Edgar did not send a verification email: {json.dumps(data)}")
        server.shutdown()
        server.server_close()
        return 1

    print(f"Verification email sent to {email}. Click the link on this machine to continue.")
    capture = _await_capture(server, LOOPBACK_TIMEOUT_SECONDS)
    if capture is None:
        print(
            f"Timed out after {LOOPBACK_TIMEOUT_SECONDS // 60} min without a loopback hit.\n"
            "Fallback: `auth.py verify --vk <value>` with the vk from the email URL."
        )
        return 2

    print(f"Captured vk for {capture.email} — submitting [EMAIL VERIFICATION EVENT]")
    client.generation_source = _loopback_generation_source(port)
    resp = client.submit(
        "EMAIL VERIFICATION EVENT",
        {"Verification Key": capture.verification_key, "Email": capture.email},
    )
    print(f"  HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        data = {}
    print(json.dumps(data, indent=2) if data else resp.text)
    if not resp.ok:
        return 1
    er = data.get("email_registration") or {}
    if er.get("activated"):
        print("Signature ACTIVE on Edgar.")
    elif er.get("already_consumed"):
        print("Verification link was already consumed by this key — signature already ACTIVE.")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    client = EdgarClient.from_env()
    email = (args.email or client.email).strip().lower()
    vk = args.vk.strip()
    if args.vk.startswith("http"):  # user pasted the entire email URL
        parsed = urllib.parse.urlparse(args.vk)
        qs = dict(urllib.parse.parse_qsl(parsed.query))
        vk = (qs.get("vk") or "").strip()
        email = (qs.get("em") or email).strip().lower()
        if not vk:
            print("Could not extract 'vk' from the URL.")
            return 1

    print(f"POST {client.base_url}/dao/submit_contribution  (EMAIL VERIFICATION EVENT, vk tail …{vk[-8:]})")
    resp = client.submit(
        "EMAIL VERIFICATION EVENT",
        {"Verification Key": vk, "Email": email},
    )
    print(f"  HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        data = {}
    print(json.dumps(data, indent=2) if data else resp.text)
    return 0 if resp.ok else 1


def _cmd_status(_args: argparse.Namespace) -> int:
    client = EdgarClient.from_env()
    print(f"Email: {client.email}")
    print(f"Pub key tail: …{client.public_key_b64[-40:]}")
    resp = client.check_signature()
    print(f"GET {client.base_url}/dao/check_digital_signature  HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    return 0 if resp.ok else 1


def _cmd_rotate(args: argparse.Namespace) -> int:
    email = (args.email or DEFAULT_EMAIL_FALLBACK).strip().lower()
    _ensure_keys(email, rotate=True)
    print("Keys rotated. Run `auth.py login` to register them.")
    return 0


# ------------------------------------------------------------------ dispatch


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TrueSight DAO / Edgar CLI auth.")
    sub = p.add_subparsers(dest="cmd", required=True)

    login = sub.add_parser("login", help="Register + verify this machine's keypair via email click.")
    login.add_argument("--email", help=f"Registration email (default: {DEFAULT_EMAIL_FALLBACK} or .env EMAIL).")
    login.add_argument("--force", action="store_true", help="Skip the is-it-already-active shortcut.")
    login.set_defaults(func=_cmd_login)

    verify = sub.add_parser("verify", help="Manual fallback: submit EMAIL VERIFICATION EVENT for a pasted vk.")
    verify.add_argument("--vk", required=True, help="Verification key, or the full email URL.")
    verify.add_argument("--email", help="Override email (default: EMAIL from .env).")
    verify.set_defaults(func=_cmd_verify)

    status = sub.add_parser("status", help="Ask Edgar about the stored public key.")
    status.set_defaults(func=_cmd_status)

    rotate = sub.add_parser("rotate", help="Wipe keys from .env and regenerate.")
    rotate.add_argument("--email", help="Email to associate with the new keys.")
    rotate.set_defaults(func=_cmd_rotate)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
