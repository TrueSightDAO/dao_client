# dao_client

Python client library + CLI for **TrueSight DAO**'s contribution server, **Edgar**.

Every public DAO action (contribution, inventory movement, notarization, QR update, etc.) is submitted as an **RSA-signed event payload** to Edgar's `POST /dao/submit_contribution` endpoint. The browser-side reference implementation lives in [`TrueSightDAO/dapp`](https://github.com/TrueSightDAO/dapp) (each HTML page under `dapp.truesight.me/`). This repo is the **terminal / script / automation** equivalent: the same signing, the same payload shape, the same endpoint — just from Python instead of a browser tab.

## What's in this repo

| Path | Purpose |
|------|---------|
| [`edgar_client.py`](edgar_client.py) | Core library. Key generation (RSA-2048, SPKI/PKCS#8 base64 to match WebCrypto), canonical payload formatting, RSASSA-PKCS1-v1_5 / SHA-256 signing, and the multipart POST to Edgar. Python port of `dapp/scripts/edgar_payload_helper.js`. |
| [`auth.py`](auth.py) | CLI for onboarding this machine's keypair. `login` runs a full **OAuth-loopback-style** flow: sign `[EMAIL REGISTERED EVENT]` with a `127.0.0.1` callback URL, spin up a one-shot listener, wait for the email click, capture `vk`+`em`, sign `[EMAIL VERIFICATION EVENT]`, POST. `verify` is the manual fallback. `status` / `rotate` round out the lifecycle. |
| **AI agent ledger submissions** | When automation completes repo work that should appear as a **`[CONTRIBUTION EVENT]`**, use [`modules/report_ai_agent_contribution.py`](modules/report_ai_agent_contribution.py) with **at least one** `https://github.com/TrueSightDAO/.../pull/N` URL and an explicit body. Full convention: [**TrueSightDAO/agentic_ai_context** — `DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md). |
| [`dapp_digital_signature_onboarding/`](dapp_digital_signature_onboarding/) | Read-mostly operator demo that mirrors Edgar's own Google-Sheets side of the flow (append `VERIFYING` row, flip to `ACTIVE`, call the verification-email web app). Previously hosted in [`TrueSightDAO/tokenomics`](https://github.com/TrueSightDAO/tokenomics). |
| `.env` | **Never committed.** Holds `EMAIL`, `PUBLIC_KEY` (SPKI base64), `PRIVATE_KEY` (PKCS#8 base64) for the active identity. Written by `auth.py` with mode `0600`. |

## Quick start

```bash
cd ~/Applications/dao_client
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 auth.py login --email you@example.com
#  → generates an RSA-2048 keypair in .env
#  → POSTs [EMAIL REGISTERED EVENT] with generation source set to
#    http://127.0.0.1:<random-port>/verify
#  → waits for you to click the email link (on THIS machine)
#  → captures em+vk, signs [EMAIL VERIFICATION EVENT], POSTs, prints result

python3 auth.py status          # ask Edgar what it knows about this key
python3 auth.py rotate --email you@example.com   # wipe .env keys and start over
python3 auth.py verify --vk <value-from-email-url>   # manual fallback if you click on a different device
```

## How the loopback auth flow works

1. **`edgar_client.py`** signs an `[EMAIL REGISTERED EVENT]` payload. Every payload carries a `This submission was generated using <URL>` line.
2. Edgar parses that URL and passes it as `return_url` to the Apps Script mail web app (`edgar_send_email_verification.gs`).
3. The mailer embeds `return_url?em=<email>&vk=<verification key>` in the email it sends you.
4. Because the CLI set the URL to `http://127.0.0.1:<random-port>/verify`, clicking the link hits the local listener `auth.py` spun up a moment earlier.
5. The listener captures `em` + `vk`, hands them to `edgar_client.submit("EMAIL VERIFICATION EVENT", ...)`, which signs the verification payload with the **same** keypair and POSTs it to Edgar.
6. Edgar flips the **Contributors Digital Signatures** row from `VERIFYING` → `ACTIVE` and stamps column **H** (Verification Key Consumed). See the [sheet-flow demo](dapp_digital_signature_onboarding/) and [tokenomics SCHEMA.md](https://github.com/TrueSightDAO/tokenomics/blob/main/SCHEMA.md) for the column contract.

### Constraints worth knowing

- **Click the email link on the same machine** that ran `auth.py login`. Loopback ports don't leave `127.0.0.1`. For a different device, use `python3 auth.py verify --vk <value>` and paste the `vk` from the email URL.
- Your mail client may warn that the `http://127.0.0.1:…` link is "unsafe". That's expected — it's a local URL, not a secure webpage.
- The DAO allows **multiple simultaneously-active keys per contributor**, so running `auth.py login` on another machine (or after `rotate`) adds a new key without invalidating prior ones.

## Per-event CLI modules (`modules/`)

Every signed-event page on `dapp.truesight.me/` has a matching script under `modules/`. Each one hardcodes the event name, exposes canonical attributes as named CLI flags, and accepts `--attr 'Label=Value'` for anything not covered. All modules support `--dry-run` to print the signed share text without hitting Edgar.

Run any module from the repo root:

```bash
python3 modules/report_contribution.py \
    --type "Time (Minutes)" --amount 30 \
    --description "Closing out Townhall" \
    --contributors "Gary Teh" \
    --tdg-issued 50.00
```

| Module | Event tag | Browser equivalent |
|--------|-----------|--------------------|
| `modules/batch_qr_generator.py` | `[BATCH QR CODE REQUEST]` | `batch_qr_generator.html` |
| `modules/create_proposal.py` | `[PROPOSAL CREATION]` | `create_proposal.html` |
| `modules/notarize.py` | `[NOTARIZATION EVENT]` | `notarize.html` |
| `modules/register_farm.py` | `[FARM REGISTRATION]` | `register_farm.html` |
| `modules/repackaging_planner.py` | `[REPACKAGING BATCH EVENT]` | `repackaging_planner.html` |
| `modules/report_capital_injection.py` | `[CAPITAL INJECTION EVENT]` | `report_capital_injection.html` |
| `modules/report_contribution.py` | `[CONTRIBUTION EVENT]` | `report_contribution.html` |
| `modules/report_ai_agent_contribution.py` | `[CONTRIBUTION EVENT]` (AI agent — **PR URLs required**) | *Convention doc:* [`agentic_ai_context/DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/DAO_CLIENT_AI_AGENT_CONTRIBUTIONS.md) |
| `modules/report_dao_expenses.py` | `[DAO Inventory Expense Event]` | `report_dao_expenses.html` |
| `modules/report_inventory_movement.py` | `[INVENTORY MOVEMENT]` | `report_inventory_movement.html` |
| `modules/report_sales.py` | `[SALES EVENT]` | `report_sales.html` |
| `modules/report_tree_planting.py` | `[TREE PLANTING EVENT]` | `report_tree_planting.html` |
| `modules/review_proposal.py` | `[PROPOSAL VOTE]` | `review_proposal.html` |
| `modules/scanner.py` | `[QR CODE EVENT]` | `scanner.html` |
| `modules/update_qr_code.py` | `[QR CODE UPDATE EVENT]` | `update_qr_code.html` |
| `modules/withdraw_voting_rights.py` | `[VOTING RIGHTS WITHDRAWAL REQUEST]` | `withdraw_voting_rights.html` |

Read the browser-equivalent HTML for the canonical attribute list and any value-format expectations (dates, coords, currency). Pages that don't emit a signed event (read-only dashboards, `stores_nearby.html`, `view_open_proposals.html`, etc.) aren't mirrored here — they'd need a different client surface.

## Read-side caches (`cache/`)

Four wrappers over the DAO's read-only data sources. Each one has a library API and a `python3 -m cache.<name>` CLI.

| Module | Source today | CLI example |
|--------|--------------|-------------|
| `cache.treasury` | `TrueSightDAO/treasury-cache/dao_offchain_treasury.json` (GitHub raw) | `python3 -m cache.treasury --ledger AGL4` |
| `cache.freight` | `TrueSightDAO/agroverse-freight-audit/pointers/freight_lanes.json` (GitHub raw) | `python3 -m cache.freight --to "San Francisco"` |
| `cache.compositions` | `TrueSightDAO/agroverse-inventory/currency-compositions/{uuid}.json` (per-UUID receipts) | `python3 -m cache.compositions --list` |
| `cache.contributors` | GAS `assetVerify` web app (today); planned flip to `dao_members.json` on GitHub | `python3 -m cache.contributors` (looks up self from `.env`) |

### Backend-swappable architecture

Every cache module delegates reads to a `DataSource` in `cache/_source.py`. Three implementations ship:

- `GithubRawBackend(raw_url)` — CDN-fast, auth-free, git-history audit trail. Default for the three existing JSON caches.
- `GithubContentsBackend(contents_url)` — for directory listings that can't be enumerated over `raw.githubusercontent.com`. Rate-limited to 60/hr per IP without auth.
- `GasBackend(exec_url, params=...)` — for GAS web apps. 45 s timeout to survive cold starts. Used today for `cache.contributors`.

When a `dao_members.json` cache publisher lands under `tdg_identity_management` (follow-up), flipping `cache/contributors.py` from GAS to GitHub is a one-line change:

```python
def _default_lookup_source() -> DataSource:
    # return GasBackend(GAS_EXEC_URL, base_params={"full": "true"})
    return GithubRawBackend("https://raw.githubusercontent.com/TrueSightDAO/treasury-cache/main/dao_members.json")
```

Callers (`Contributors.for_self()`, `Contributors.for_public_key(pk)`, `Contributors.list_all()`) keep the same signatures.

## Using `edgar_client.py` from your own scripts

Every additional DAO event is a three-line call:

```python
from edgar_client import EdgarClient

client = EdgarClient.from_env()
resp = client.submit(
    "CONTRIBUTION EVENT",
    {
        "Type": "Time (Minutes)",
        "Amount": "30",
        "Description": "Closing out Townhall",
        "Contributor(s)": "Gary Teh",
    },
)
print(resp.status_code, resp.text)
```

Attribute names and event strings mirror what the corresponding `dapp/*.html` page emits — read that file as the contract.

## Related repos

- [`TrueSightDAO/dapp`](https://github.com/TrueSightDAO/dapp) — the browser-side reference implementation (each HTML page is one event).
- [`TrueSightDAO/sentiment_importer`](https://github.com/TrueSightDAO/sentiment_importer) — Edgar itself (Rails). The signature-verify + sheet-write logic lives in `app/services/dao_email_registration_service.rb` and `app/models/gdrive/contributors_digital_signatures.rb`.
- [`TrueSightDAO/tokenomics`](https://github.com/TrueSightDAO/tokenomics) — canonical schema (`SCHEMA.md`) and the Apps Script web app that sends the verification email (`google_app_scripts/tdg_identity_management/edgar_send_email_verification.gs`).
