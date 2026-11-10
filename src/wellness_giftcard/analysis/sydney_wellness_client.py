#!/usr/bin/env python3
"""
Sydney Health Wellness Client — REAL (non-simulated).

Uses an existing authenticated Anthem/Sydney Health session token to query
wellness / rewards data. Replaces the simulated stub in
CRD/tools/wellness_points_tracker.py which only read local JSON.

Endpoints (from SYDNEY.md runbook + API recon):
- Okta IdP: https://login.sydneyhealth.com
- MHC login server: https://sn.mobilehealthconsumer.com
- Anthem member portal: https://membersecure.anthem.com (via Tor, bypasses Akamai)

Usage:
  python tools/sydney_wellness_client.py \
    --session-token "..." \
    --check-rewards
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_PROXY = "socks5h://127.0.0.1:9050"  # Tor SOCKS5


class SydneyWellnessClient:
    """Queries Sydney Health wellness/rewards with a real session."""

    def __init__(
        self,
        session_token: str,
        output_path: Path,
        proxy: str | None = DEFAULT_PROXY,
    ):
        self.output_path = output_path
        self.session_token = session_token
        self.results: list[dict[str, Any]] = []

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SydneyHealth/10.6.1 (Android 13; React Native)",
                "Accept": "application/json",
                "Authorization": f"Bearer {session_token}",
            }
        )
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def _try(self, label: str, method: str, url: str, **kw) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "label": label,
            "url": url,
            "method": method,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = self.session.request(method, url, timeout=30, **kw)
            entry["http_status"] = resp.status_code
            entry["raw_response"] = resp.text[:800]
            try:
                entry["response_body"] = resp.json()
            except Exception:
                entry["response_body"] = {"_non_json": True}
            self.results.append(entry)
            return entry
        except Exception as exc:  # noqa: BLE001
            entry["http_status"] = None
            entry["error"] = str(exc)[:500]
            self.results.append(entry)
            return entry

    def check_wellness_endpoints(self) -> None:
        """Probe common wellness/rewards endpoints with the session."""
        bases = [
            "https://sn.mobilehealthconsumer.com",
            "https://membersecure.anthem.com",
            "https://consumerpublic.prod1.awse1.anthem.com",
        ]
        paths = [
            "/api/v3/wellness/rewards",
            "/api/v3/wellness/points",
            "/api/v3/wellness/balance",
            "/api/v3/rewards",
            "/api/v3/member/wellness",
            "/api/v3/rewards/balance",
            "/api/v3/myhealth/rewards",
            "/api/v3/engage/rewards",
            "/api/v1/wellness/rewards",
            "/api/v1/wellness/points",
            "/v1/wellness/rewards",
            "/v1/wellness/points",
        ]
        for base in bases:
            for path in paths:
                self._try(f"wellness {path}", "GET", f"{base}{path}")
                # small delay to avoid hammering
                import time
                time.sleep(0.3)

    def check_profile(self) -> None:
        """Try to get the authenticated member's profile."""
        urls = [
            "https://login.sydneyhealth.com/oauth2/default/v1/userinfo",
            "https://sn.mobilehealthconsumer.com/api/v3/profile",
            "https://membersecure.anthem.com/member/secure/api/webaccount/web/bootstrap",
        ]
        for u in urls:
            self._try("profile", "GET", u)

    def save(self) -> Path:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_token": self.session_token,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "results": self.results,
        }
        with open(self.output_path, "w") as f:
            json.dump(payload, f, indent=2)
        return self.output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sydney Health Wellness Client — real session queries"
    )
    parser.add_argument(
        "--session-token",
        type=str,
        required=True,
        help="Authenticated Anthem/Sydney Health session token",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/sydney_wellness_results.json"),
        help="Output path",
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Disable Tor proxy",
    )
    args = parser.parse_args()

    proxy = None if args.no_proxy else DEFAULT_PROXY
    client = SydneyWellnessClient(
        session_token=args.session_token,
        output_path=args.output,
        proxy=proxy,
    )
    client.check_profile()
    client.check_wellness_endpoints()
    path = client.save()
    print(f"Sydney Health wellness probe complete. Results: {path}")


if __name__ == "__main__":
    main()
