"""
Swappable read sources for `cache/*.py`.

Every cache module exposes a `.fetch()` (and friends) that delegate to a
`DataSource`. That way we can ship today against a GAS endpoint and flip one
line when a GitHub-raw JSON cache lands — callers stay untouched.

Three backends:

- `GithubRawBackend(raw_url)` — GET the given raw.githubusercontent.com URL,
  parse JSON. Preferred: CDN-fast, auth-free, git-history audit trail.
- `GithubContentsBackend(contents_url)` — GET the repo contents API for
  directory listings (e.g. `currency-compositions/`). Rate-limited to 60/hr
  per IP without auth; surface that in error messages.
- `GasBackend(exec_url, params=None)` — GET a Google Apps Script web app's
  `/exec` endpoint with query params. Slower, occasionally flaky, no auth
  required when the script is deployed "Anyone can access".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import requests


DEFAULT_TIMEOUT = 20.0


class DataSource:
    """Marker base — every backend returns parsed JSON from `.fetch(**params)`."""

    def fetch(self, **params: Any) -> Any:  # pragma: no cover - protocol method
        raise NotImplementedError


@dataclass
class GithubRawBackend(DataSource):
    raw_url: str
    timeout: float = DEFAULT_TIMEOUT
    session: requests.Session = field(default_factory=requests.Session)

    def fetch(self, **params: Any) -> Any:
        # raw.githubusercontent.com doesn't support query params; but allow them
        # in the signature so callers can pass through uniformly.
        url = self.raw_url
        if params:
            # Append only if the caller actually wants to reach a templated sibling file.
            path_suffix = params.pop("path_suffix", None)
            if path_suffix:
                url = url.rstrip("/") + "/" + path_suffix.lstrip("/")
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        # GitHub returns text/plain; requests.json() works as long as content is valid JSON.
        return resp.json()


@dataclass
class GithubContentsBackend(DataSource):
    """Used for directory listings where raw.githubusercontent.com can't enumerate files."""

    contents_url: str
    timeout: float = DEFAULT_TIMEOUT
    session: requests.Session = field(default_factory=requests.Session)

    def fetch(self, **params: Any) -> Any:
        resp = self.session.get(self.contents_url, timeout=self.timeout)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise RuntimeError(
                "GitHub contents API rate-limited (60 req/hr unauthenticated). "
                "Set GITHUB_TOKEN and rerun, or wait. URL: " + self.contents_url
            )
        resp.raise_for_status()
        return resp.json()


@dataclass
class GasBackend(DataSource):
    exec_url: str
    base_params: Mapping[str, str] = field(default_factory=dict)
    # GAS cold starts routinely push past 20s; 45s is the empirically safe ceiling.
    timeout: float = 45.0
    session: requests.Session = field(default_factory=requests.Session)

    def fetch(self, **params: Any) -> Any:
        merged = {**self.base_params, **{k: v for k, v in params.items() if v is not None}}
        resp = self.session.get(self.exec_url, params=merged, timeout=self.timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            # GAS web apps occasionally return HTML on cold start / redirect.
            raise RuntimeError(
                f"GAS returned non-JSON (HTTP {resp.status_code}); "
                f"first 200 chars: {resp.text[:200]!r}"
            ) from exc


__all__ = [
    "DEFAULT_TIMEOUT",
    "DataSource",
    "GasBackend",
    "GithubContentsBackend",
    "GithubRawBackend",
]
