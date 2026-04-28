#!/usr/bin/env python3
"""Onboard a new retail partner end-to-end (MVP — ledger + inventory only).

Collapses the manual steps in
``agentic_ai_context/RETAILER_TECHNICAL_ONBOARDING.md`` §3 into a single
manifest-driven CLI invocation. Implements the **deterministic** parts of
the onboarding sequence:

  Step 1.  Submit ``[CONTRIBUTOR ADD EVENT]`` for the retail contact, with
           name pre-formatted as ``<First Name> - <Store Name>``.
  Step 2.  Set ``Contributors contact information`` col **U** (Mailing
           Address). **Does not** set col T — that flag is reserved for
           online-fulfillment managers (Gary + Kirsten only).
  Step 3.  Append ``Agroverse Partners`` row with all required fields.
  Step 13. Submit one ``[INVENTORY MOVEMENT]`` event per opening-order
           QR code.
  Step 14. Run inventory + velocity syncs locally so the JSON snapshots
           in ``agroverse-inventory`` are fresh.

Skipped in MVP (operator handles via Claude / manual edits + PRs):
  Steps 4 (geocoding — manifest must include lat/lon),
  5–10 (partner page + discovery surfaces in ``agroverse_shop``),
  11 (photo download),
  12 (PR creation in ``agroverse_shop``),
  15 (PR creation in ``agroverse-inventory``).

Why MVP scope: the *ledger* steps cause the most pain (Edgar auto-rename
trap, col T semantics, brittle name joins). HTML/JS surface updates are
mechanical for an AI to do correctly the first time. Future v1 fills in
the website work.

Idempotency: every step checks "is this already done?" before acting.
Re-running the same manifest is safe.

Usage:
    cd dao_client
    python -m truesight_dao_client.modules.onboard_retail_partner \\
        --manifest path/to/manifest.yaml --dry-run
    python -m truesight_dao_client.modules.onboard_retail_partner \\
        --manifest path/to/manifest.yaml --execute

Manifest schema (YAML):
    partner_id: the-way-home-shop          # slug; canonical key
    partner_name: The Way Home Shop
    contact_first_name: Gergana
    email: info@thewayhomeshop.com
    address: "8437 SE Stark Street, Portland, OR 97216"
    location: "Portland, Oregon"           # used for Agroverse Partners col F
    partner_type: Consignment              # or Wholesale / Operator / Supplier / Manufacturer
    notes: ""                              # optional; col G
    opening_order:                         # optional; omit to skip step 13
      source_manager: "Kirsten Ritschel"
      inventory_item: "<full Currency string from Agroverse QR codes col I>"
      qr_codes:
        - 2024OSCAR_20260330_23
        - 2024OSCAR_20260330_24
        # …
    run_syncs: true                        # default true; runs sync_*.py if available

Requires:
- dao_client ``.env`` (signing identity for Edgar) — same as other modules.
- A ``google_credentials.json`` with editor access to the Main Ledger
  (``1GE7PUq-…``). Searched in this order:
    1. ``$DAO_CLIENT_GOOGLE_CREDENTIALS`` env var
    2. ``dao_client/google_credentials.json``
    3. ``../market_research/google_credentials.json``
- ``gspread`` and ``google-auth`` installed (see requirements.txt of the
  market_research repo or install: ``pip install gspread google-auth``).
- (Optional, for step 14) a sibling clone of
  ``TrueSightDAO/go_to_market`` checked out at ``../market_research`` so
  the inventory + velocity sync scripts can be invoked.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

from ..edgar_client import EdgarClient

MAIN_LEDGER_ID = "1GE7PUq-UT6x2rBN-Q2ksogbWpgyuh2SaxJyG_uEK6PU"
PARTNERS_SHEET = "Agroverse Partners"
CONTRIBUTORS_SHEET = "Contributors contact information"

# Contributors column indices (1-based for gspread cell ops).
CCI_COL_NAME = 1   # A
CCI_COL_EMAIL = 4  # D
CCI_COL_T_STORE_MGR = 20  # T — DO NOT SET TRUE for retail partners
CCI_COL_U_MAILING = 21    # U — set this with the address

ALLOWED_PARTNER_TYPES = {"Wholesale", "Consignment", "Operator", "Supplier", "Manufacturer"}

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Manifest loading + validation
# ---------------------------------------------------------------------------

@dataclass
class OpeningOrder:
    source_manager: str
    inventory_item: str
    qr_codes: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    partner_id: str
    partner_name: str
    contact_first_name: str
    email: str
    address: str
    location: str
    partner_type: str = "Consignment"
    notes: str = ""
    opening_order: OpeningOrder | None = None
    run_syncs: bool = True

    @property
    def contributor_full_name(self) -> str:
        """Canonical retail-partner contact name: ``<First> - <Store>``.

        Pre-formatting prevents Edgar's auto-rename from breaking the
        ``Agroverse Partners.E`` ↔ ``Contributors.A`` join. See
        ``RETAILER_TECHNICAL_ONBOARDING.md`` §3.1 + §6a.
        """
        return f"{self.contact_first_name.strip()} - {self.partner_name.strip()}"

    @property
    def partner_page_url(self) -> str:
        return f"https://agroverse.shop/partners/{self.partner_id}"


def load_manifest(path: Path) -> Manifest:
    if yaml is None:
        raise SystemExit("PyYAML is required: pip install pyyaml")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise SystemExit(f"Manifest must be a YAML mapping (got {type(raw).__name__}).")

    required = ["partner_id", "partner_name", "contact_first_name", "email", "address", "location"]
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise SystemExit(f"Manifest missing required fields: {', '.join(missing)}")

    ptype = (raw.get("partner_type") or "Consignment").strip()
    if ptype not in ALLOWED_PARTNER_TYPES:
        raise SystemExit(
            f"partner_type must be one of {sorted(ALLOWED_PARTNER_TYPES)}; got {ptype!r}."
        )

    oo = None
    if raw.get("opening_order"):
        oo_raw = raw["opening_order"]
        for k in ("source_manager", "inventory_item", "qr_codes"):
            if not oo_raw.get(k):
                raise SystemExit(f"opening_order.{k} required when opening_order is provided")
        oo = OpeningOrder(
            source_manager=str(oo_raw["source_manager"]).strip(),
            inventory_item=str(oo_raw["inventory_item"]).strip(),
            qr_codes=[str(q).strip() for q in oo_raw["qr_codes"] if str(q).strip()],
        )

    return Manifest(
        partner_id=str(raw["partner_id"]).strip(),
        partner_name=str(raw["partner_name"]).strip(),
        contact_first_name=str(raw["contact_first_name"]).strip(),
        email=str(raw["email"]).strip(),
        address=str(raw["address"]).strip(),
        location=str(raw["location"]).strip(),
        partner_type=ptype,
        notes=str(raw.get("notes") or "").strip(),
        opening_order=oo,
        run_syncs=bool(raw.get("run_syncs", True)),
    )


# ---------------------------------------------------------------------------
# Google Sheets helpers (gspread)
# ---------------------------------------------------------------------------

def _find_google_credentials() -> Path:
    env = os.environ.get("DAO_CLIENT_GOOGLE_CREDENTIALS")
    if env and Path(env).is_file():
        return Path(env)
    here = REPO_ROOT / "google_credentials.json"
    if here.is_file():
        return here
    sibling = REPO_ROOT.parent / "market_research" / "google_credentials.json"
    if sibling.is_file():
        return sibling
    raise SystemExit(
        "google_credentials.json not found. Set DAO_CLIENT_GOOGLE_CREDENTIALS, "
        "place it at dao_client/google_credentials.json, or have a sibling "
        "market_research/google_credentials.json checkout."
    )


def _gspread_client():
    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials as SACreds  # type: ignore
    except ImportError as e:
        raise SystemExit(f"Missing dependency for sheet operations: {e}. pip install gspread google-auth")
    creds = SACreds.from_service_account_file(
        str(_find_google_credentials()),
        scopes=("https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.readonly"),
    )
    return gspread.authorize(creds)


def _retry(fn, *, attempts: int = 5, base_delay: float = 1.0):
    """Tiny retry for Sheets transient errors. Mirrors market_research helper."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(base_delay * (2 ** i))
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Step 1: [CONTRIBUTOR ADD EVENT]
# ---------------------------------------------------------------------------

def _find_contributor_row(cci_data: list[list[str]], name: str) -> int | None:
    """Return 1-based row index for a Contributors row whose col A matches ``name``.

    Header row is at row 4 on this sheet (rows 1-3 are title + description),
    so iterate from row 5.
    """
    for i, row in enumerate(cci_data[4:], start=5):
        if row and row[0].strip().lower() == name.strip().lower():
            return i
    return None


def step1_contributor_add(client: EdgarClient, manifest: Manifest, *, dry_run: bool, verbose: bool) -> None:
    print("\n=== Step 1 — [CONTRIBUTOR ADD EVENT] ===")
    name = manifest.contributor_full_name
    print(f"  Contributor Name: {name!r}")
    print(f"  Contributor Email: {manifest.email!r}")

    # Idempotency: check if row already exists.
    gc = _gspread_client()
    sh = _retry(lambda: gc.open_by_key(MAIN_LEDGER_ID))
    cci = _retry(lambda: sh.worksheet(CONTRIBUTORS_SHEET))
    cci_data = _retry(lambda: cci.get_all_values())
    existing = _find_contributor_row(cci_data, name)
    if existing:
        print(f"  ✓ Already on sheet at row {existing}; skipping Edgar submit.")
        return

    if dry_run:
        print("  (dry-run) would submit [CONTRIBUTOR ADD EVENT] now.")
        return

    attributes = [
        ("Contributor Name", name),
        ("Contributor Email", manifest.email),
        ("Initial Digital Signature", "(none — store-manager contact, no key needed)"),
        ("Submitted At", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        ("Submission Source", "dao_client/onboard_retail_partner"),
    ]
    resp = client.submit("CONTRIBUTOR ADD EVENT", attributes)
    if not resp.ok:
        raise SystemExit(f"Edgar [CONTRIBUTOR ADD EVENT] failed HTTP {resp.status_code}: {resp.text[:300]}")
    print(f"  ✓ HTTP {resp.status_code} — Edgar accepted; row will land within ~30s.")
    if verbose:
        print(f"    response: {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Step 2: Contributors col U (Mailing Address) — explicitly NOT col T
# ---------------------------------------------------------------------------

def step2_set_mailing_address(manifest: Manifest, *, dry_run: bool, max_wait_s: int = 90) -> None:
    print("\n=== Step 2 — Contributors!U (Mailing Address) ===")
    print(f"  (col T 'Is Store Manager' intentionally NOT set — reserved for Gary + Kirsten only)")

    gc = _gspread_client()
    sh = _retry(lambda: gc.open_by_key(MAIN_LEDGER_ID))
    cci = _retry(lambda: sh.worksheet(CONTRIBUTORS_SHEET))

    # Wait for the row to land (step 1 is async via Edgar processing).
    name = manifest.contributor_full_name
    deadline = time.time() + max_wait_s
    row_idx: int | None = None
    while time.time() < deadline:
        cci_data = _retry(lambda: cci.get_all_values())
        row_idx = _find_contributor_row(cci_data, name)
        if row_idx:
            break
        if dry_run:
            break
        time.sleep(5)

    if not row_idx:
        if dry_run:
            print("  (dry-run) would wait for row + write col U with the address.")
            return
        raise SystemExit(
            f"Contributors row {name!r} did not land within {max_wait_s}s. "
            "Verify the [CONTRIBUTOR ADD EVENT] processed; re-run when present."
        )

    # Idempotency: only write if differs.
    current_u = ""
    cci_data = _retry(lambda: cci.get_all_values())
    if row_idx <= len(cci_data) and len(cci_data[row_idx - 1]) >= CCI_COL_U_MAILING:
        current_u = (cci_data[row_idx - 1][CCI_COL_U_MAILING - 1] or "").strip()
    if current_u == manifest.address:
        print(f"  ✓ Row {row_idx} col U already = {manifest.address!r}; skipping.")
        return

    if dry_run:
        print(f"  (dry-run) would write Contributors!U{row_idx} = {manifest.address!r}.")
        return

    _retry(lambda: cci.update_cell(row_idx, CCI_COL_U_MAILING, manifest.address))
    print(f"  ✓ Wrote Contributors!U{row_idx} = {manifest.address!r}.")


# ---------------------------------------------------------------------------
# Step 3: Append Agroverse Partners row
# ---------------------------------------------------------------------------

def step3_append_partners_row(manifest: Manifest, *, dry_run: bool) -> None:
    print("\n=== Step 3 — Append Agroverse Partners row ===")
    gc = _gspread_client()
    sh = _retry(lambda: gc.open_by_key(MAIN_LEDGER_ID))
    ap = _retry(lambda: sh.worksheet(PARTNERS_SHEET))
    ap_data = _retry(lambda: ap.get_all_values())

    # Idempotency: exact partner_id match in col A.
    for r in ap_data[1:]:
        if r and r[0].strip() == manifest.partner_id:
            print(f"  ✓ Row already exists for partner_id={manifest.partner_id!r}; skipping.")
            return

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_row = [
        manifest.partner_id,                   # A partner_id
        manifest.partner_name,                 # B partner_name
        manifest.partner_page_url,             # C partner_page_url
        "active",                              # D status
        manifest.contributor_full_name,        # E contributor_contact_id (MUST match Contributors.A)
        manifest.location,                     # F location
        manifest.notes,                        # G notes
        now_iso,                               # H last_synced_at
        manifest.partner_type,                 # I partner type
    ]
    print(f"  partner_id: {manifest.partner_id}")
    print(f"  contributor_contact_id (col E): {manifest.contributor_full_name!r}")
    print(f"  partner type (col I): {manifest.partner_type}")

    if dry_run:
        print("  (dry-run) would append the row.")
        return

    _retry(lambda: ap.append_row(new_row, value_input_option="USER_ENTERED"))
    print("  ✓ Appended.")


# ---------------------------------------------------------------------------
# Step 13: Inventory movement loop
# ---------------------------------------------------------------------------

def _movement_already_logged(qr_code: str, recipient: str, gc) -> bool:
    """Idempotency check — skip if Inventory Movement already has the QR row.

    Reads the Telegram & Submissions spreadsheet (1qbZZhf-…) Inventory
    Movement tab and looks for any row whose F column ('Contribution Made')
    contains both this QR code and this recipient.
    """
    try:
        tg = _retry(lambda: gc.open_by_key("1qbZZhf-_7xzmDTriaJVWj6OZshyQsFkdsAV8-pyzASQ"))
        ws = _retry(lambda: tg.worksheet("Inventory Movement"))
        rows = _retry(lambda: ws.get_all_values())
    except Exception:
        # If we can't read the dedup source, fall through and submit anyway.
        return False
    for row in rows[1:]:
        if not row:
            continue
        contribution = " ".join(row[:14]).lower()
        if qr_code.lower() in contribution and recipient.lower() in contribution:
            return True
    return False


def step13_submit_movements(client: EdgarClient, manifest: Manifest, *, dry_run: bool) -> None:
    print("\n=== Step 13 — [INVENTORY MOVEMENT] events ===")
    if not manifest.opening_order:
        print("  No opening_order in manifest; skipping.")
        return
    oo = manifest.opening_order
    recipient = manifest.contributor_full_name
    print(f"  Manager Name (sender): {oo.source_manager}")
    print(f"  Recipient Name: {recipient}")
    print(f"  Inventory Item: {oo.inventory_item[:60]}…")
    print(f"  QR codes: {len(oo.qr_codes)}")

    gc = _gspread_client()

    submitted = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for qr in oo.qr_codes:
        if _movement_already_logged(qr, recipient, gc):
            print(f"  - {qr}: ✓ already logged; skip")
            skipped += 1
            continue
        if dry_run:
            print(f"  - {qr}: (dry-run) would submit")
            continue
        attrs = [
            ("Manager Name", oo.source_manager),
            ("Recipient Name", recipient),
            ("Inventory Item", oo.inventory_item),
            ("QR Code", qr),
            ("Quantity", "1"),
        ]
        resp = client.submit("INVENTORY MOVEMENT", attrs)
        if resp.ok:
            print(f"  - {qr}: HTTP {resp.status_code}")
            submitted += 1
        else:
            print(f"  - {qr}: HTTP {resp.status_code} — {resp.text[:120]}")
            failed.append((qr, f"HTTP {resp.status_code}"))
    print(f"\n  submitted={submitted} skipped={skipped} failed={len(failed)}")
    if failed:
        for qr, why in failed:
            print(f"    failed: {qr} ({why})")
        raise SystemExit("One or more movements failed; re-run after investigating.")


# ---------------------------------------------------------------------------
# Step 14: Run inventory + velocity syncs
# ---------------------------------------------------------------------------

def step14_run_syncs(*, dry_run: bool, market_research_path: Path | None = None) -> None:
    print("\n=== Step 14 — Run inventory + velocity syncs ===")
    mr = market_research_path or (REPO_ROOT.parent / "market_research")
    if not mr.is_dir():
        print(f"  Skipping: {mr} not a directory. Have a sibling clone of TrueSightDAO/go_to_market.")
        return
    inventory_script = mr / "scripts" / "sync_agroverse_store_inventory.py"
    velocity_script = mr / "scripts" / "sync_partners_velocity.py"

    for label, script in (("inventory", inventory_script), ("velocity", velocity_script)):
        if not script.is_file():
            print(f"  Skipping {label} sync: {script} missing.")
            continue
        if dry_run:
            print(f"  (dry-run) would run: python3 {script} --execute")
            continue
        print(f"  Running {label} sync…")
        result = subprocess.run(
            ["python3", str(script), "--execute"],
            cwd=str(mr),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            print(f"  ✗ {label} sync failed (rc={result.returncode}):")
            print(f"    stderr: {result.stderr[-500:]}")
            raise SystemExit(f"{label} sync failed; partners-{label}.json not refreshed.")
        # Print last 4 lines of stdout for confirmation.
        tail = "\n".join(result.stdout.strip().splitlines()[-4:])
        print(f"  ✓ {label} sync ok:\n{tail}")


# ---------------------------------------------------------------------------
# Manual-step instructions (printed at end)
# ---------------------------------------------------------------------------

_MANUAL_STEPS_TEMPLATE = """
=== Manual steps remaining (script-deferred MVP scope) ===

After the script finishes, complete these in agroverse_shop:

1. partners/{slug}/index.html
   Clone partners/lumin-earth-apothecary/index.html and find-replace:
     - lumin-earth-apothecary  →  {slug}
     - Lumin Earth Apothecary  →  {name}
     - Morro Bay / 875 Main St → {address}
     - lat / lon coords         → operator-supplied
   Then rewrite the about/mission paragraph (Lumin's is owner-specific).

2. js/partners-data.js — append:
     '{slug}': {{
         name: '{name}',
         slug: '{slug}',
         lat: <operator-supplied>,
         lon: <operator-supplied>,
         location: '{location}',
         description: '<2-sentence pitch>'
     }}

3. partner_locations.json — append:
     "{slug}": {{ "name": "{name}", "location": "{location}" }}

4. wholesale/index.html — alphabetical insert:
     <li><a href="../partners/{slug}/index.html">{name}</a><span class="city">{location_short}</span></li>

5. partners/index.html — alphabetical insert (use Lumin Earth's card structure as template).

6. cacao-journeys/pacific-west-coast-path/index.html — if your hero is .jpeg
   (not .jpg), append '{slug}' to the imageExt conditional at the bottom.

7. assets/partners/headers/{slug}-header.<ext> — upload hero.
   assets/partners/logos/{slug}-logo.<ext>     — upload logo.

8. Open + merge PRs in agroverse_shop and agroverse-inventory.

The full reference doc (with worked example): agentic_ai_context/RETAILER_TECHNICAL_ONBOARDING.md
"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(manifest: Manifest, *, dry_run: bool, verbose: bool) -> None:
    label = "DRY RUN" if dry_run else "EXECUTE"
    print(f"=== Onboarding {manifest.partner_id} ({manifest.partner_name}) [{label}] ===")
    print(f"contributor: {manifest.contributor_full_name}")
    print(f"address:     {manifest.address}")
    print(f"location:    {manifest.location}")
    print(f"type:        {manifest.partner_type}")

    client = EdgarClient.from_env(generation_source="dao_client/onboard_retail_partner")
    step1_contributor_add(client, manifest, dry_run=dry_run, verbose=verbose)
    step2_set_mailing_address(manifest, dry_run=dry_run)
    step3_append_partners_row(manifest, dry_run=dry_run)
    step13_submit_movements(client, manifest, dry_run=dry_run)
    if manifest.run_syncs:
        step14_run_syncs(dry_run=dry_run)

    location_short = ", ".join(p.strip() for p in manifest.location.split(",")[:2])
    print(_MANUAL_STEPS_TEMPLATE.format(
        slug=manifest.partner_id,
        name=manifest.partner_name,
        location=manifest.location,
        location_short=location_short,
        address=manifest.address,
    ))


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Onboard a retail partner end-to-end (MVP scope).")
    p.add_argument("--manifest", type=Path, required=True, help="Path to YAML manifest.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="Print intended actions without side effects (default).")
    g.add_argument("--execute", action="store_true",
                   help="Perform side effects (Edgar submits, sheet writes, sync runs).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.manifest.is_file():
        raise SystemExit(f"Manifest not found: {args.manifest}")
    manifest = load_manifest(args.manifest)
    run(manifest, dry_run=not args.execute, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
