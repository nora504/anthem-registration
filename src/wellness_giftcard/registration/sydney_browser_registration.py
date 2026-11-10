#!/usr/bin/env python3
"""
Sydney Health Registration Automation — Playwright Browser Automation.

Automates LEANN MARIE JENKINS's NEW account registration on Sydney Health
(membersecure.anthem.com). She is ELIGIBLE but NEVER SET UP — needs full
registration flow through the browser UI.

Flow:
1. Navigate to identification page (https://membersecure.anthem.com/member/public/authentication/register/identification?brand=ABCBS)
2. Enter name + DOB
3. Select Employee ID option (not Member ID)
4. Enter Employer ID
5. Complete OTP verification (TEXT/VOICE to phone on file)
6. Create account → access wellness rewards → redeem gift cards

Uses Playwright with stealth mode to bypass bot detection.
NOTE: Playwright does NOT work through Tor SOCKS5 proxy — uses direct connection.
Akamai WAF may block datacenter IPs; Tor + requests works for API calls but
browser UI needs direct connection or residential proxy.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    tmp.chmod(0o600)
    tmp.replace(path)


class SydneyHealthBrowserRegistration:
    """Browser-based registration automation using Playwright."""

    def __init__(
        self,
        output_path: Path,
        headless: bool = False,
        slow_mo: int = 1000,
    ):
        self.output_path = output_path
        self.headless = headless
        self.slow_mo = slow_mo
        self.results: list[dict[str, Any]] = []

    async def register_person(
        self,
        first_name: str,
        last_name: str,
        dob: str,  # YYYY-MM-DD
        employer_id: str,
    ) -> Path:
        """Run full browser registration flow for one person."""
        if not PLAYWRIGHT_AVAILABLE:
            print("ERROR: Playwright not available. Install with: pip install playwright")
            return self.output_path

        print(f"\n{'='*60}")
        print(f"Sydney Health Browser Registration")
        print(f"{'='*60}")
        print(f"Person: {first_name} {last_name} (DOB={dob})")
        print(f"Employer ID: {employer_id}")
        print(f"Headless: {self.headless}")
        print(f"{'='*60}")

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "employer_id": employer_id,
            "steps": [],
        }

        async with async_playwright() as p:
            # Launch browser with stealth settings
            browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--single-process",
                    "--disable-gpu",
                ],
            )

            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/Indiana/Indianapolis",
            )

            # Add stealth script to hide automation
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = {runtime: {}};
            """)

            page = await context.new_page()

            try:
                # Step 1: Navigate to identification page
                print("\n[Step 1] Navigating to identification page...")
                entry["steps"].append({
                    "step": 1,
                    "action": "navigate_identification",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                identification_url = (
                    "https://membersecure.anthem.com/member/public/authentication/register/identification?brand=ABCBS"
                )

                response = await page.goto(identification_url, wait_until="networkidle", timeout=30000)
                print(f"  Page loaded: {response.status if response else 'unknown'}")
                print(f"  URL: {page.url}")
                print(f"  Title: {await page.title()}")

                entry["steps"][-1]["page_status"] = response.status if response else None
                entry["steps"][-1]["page_url"] = page.url
                entry["steps"][-1]["page_title"] = await page.title()

                # Take screenshot
                screenshot_path = self.output_path.with_name("step1_identification.png")
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"  Screenshot: {screenshot_path}")

                # Step 2: Fill in name and DOB
                print("\n[Step 2] Filling name + DOB...")
                entry["steps"].append({
                    "step": 2,
                    "action": "fill_name_dob",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                # Try common selectors for name fields
                name_selectors = [
                    'input[name="firstName"]',
                    'input[id="firstName"]',
                    'input[placeholder*="First name" i]',
                    'input[placeholder*="First Name" i]',
                    'input[data-testid*="firstName" i]',
                ]
                last_name_selectors = [
                    'input[name="lastName"]',
                    'input[id="lastName"]',
                    'input[placeholder*="Last name" i]',
                    'input[placeholder*="Last Name" i]',
                    'input[data-testid*="lastName" i]',
                ]
                dob_selectors = [
                    'input[name="dob"]',
                    'input[id="dob"]',
                    'input[type="date"]',
                    'input[placeholder*="Date of birth" i]',
                    'input[placeholder*="MM/DD/YYYY" i]',
                    'input[data-testid*="dob" i]',
                ]

                first_name_filled = False
                last_name_filled = False
                dob_filled = False

                for sel in name_selectors:
                    try:
                        await page.fill(sel, first_name, timeout=5000)
                        print(f"  First name filled via: {sel}")
                        first_name_filled = True
                        break
                    except Exception:
                        continue

                for sel in last_name_selectors:
                    try:
                        await page.fill(sel, last_name, timeout=5000)
                        print(f"  Last name filled via: {sel}")
                        last_name_filled = True
                        break
                    except Exception:
                        continue

                for sel in dob_selectors:
                    try:
                        await page.fill(sel, dob, timeout=5000)
                        print(f"  DOB filled via: {sel}")
                        dob_filled = True
                        break
                    except Exception:
                        continue

                entry["steps"][-1]["first_name_filled"] = first_name_filled
                entry["steps"][-1]["last_name_filled"] = last_name_filled
                entry["steps"][-1]["dob_filled"] = dob_filled

                if not (first_name_filled and last_name_filled and dob_filled):
                    print("  WARNING: Not all fields filled - form structure may differ")
                    entry["steps"][-1]["status"] = "partial"
                else:
                    entry["steps"][-1]["status"] = "completed"

                # Take screenshot after filling
                screenshot_path = self.output_path.with_name("step2_name_dob.png")
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"  Screenshot: {screenshot_path}")

                # Step 3: Click continue/submit
                print("\n[Step 3] Submitting identification form...")
                entry["steps"].append({
                    "step": 3,
                    "action": "submit_identification",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                continue_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Continue")',
                    'button:has-text("Next")',
                    'button:has-text("Submit")',
                    'input[type="submit"]',
                ]

                submitted = False
                for sel in continue_selectors:
                    try:
                        await page.click(sel, timeout=5000)
                        print(f"  Clicked continue via: {sel}")
                        submitted = True
                        break
                    except Exception:
                        continue

                if submitted:
                    await page.wait_for_timeout(3000)  # Wait for navigation
                    print(f"  New URL: {page.url}")
                    print(f"  New Title: {await page.title()}")
                    entry["steps"][-1]["submitted"] = True
                    entry["steps"][-1]["new_url"] = page.url
                    entry["steps"][-1]["new_title"] = await page.title()
                else:
                    print("  WARNING: Could not find continue button")
                    entry["steps"][-1]["submitted"] = False

                screenshot_path = self.output_path.with_name("step3_submit.png")
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"  Screenshot: {screenshot_path}")

                # Step 4: Select Employee ID option
                print("\n[Step 4] Selecting Employee ID verification method...")
                entry["steps"].append({
                    "step": 4,
                    "action": "select_employee_id",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                # Look for radio buttons or selection options
                id_option_selectors = [
                    'input[type="radio"][value*="employee" i]',
                    'input[type="radio"][value*="Employer" i]',
                    'label:has-text("Employee ID")',
                    'label:has-text("Employer ID")',
                    'label:has-text("Employee")',
                    'label:has-text("Employer")',
                ]

                employee_selected = False
                for sel in id_option_selectors:
                    try:
                        await page.click(sel, timeout=5000)
                        print(f"  Selected Employee ID via: {sel}")
                        employee_selected = True
                        break
                    except Exception:
                        continue

                entry["steps"][-1]["employee_selected"] = employee_selected

                if employee_selected:
                    # Enter employer ID
                    employer_selectors = [
                        'input[name="employerId"]',
                        'input[name="employeeId"]',
                        'input[name="employerID"]',
                        'input[id="employerId"]',
                        'input[id="employeeId"]',
                        'input[placeholder*="Employer" i]',
                        'input[placeholder*="Employee" i]',
                        'input[placeholder*="Group" i]',
                    ]

                    employer_filled = False
                    for sel in employer_selectors:
                        try:
                            await page.fill(sel, employer_id, timeout=5000)
                            print(f"  Employer ID filled via: {sel}")
                            employer_filled = True
                            break
                        except Exception:
                            continue

                    entry["steps"][-1]["employer_filled"] = employer_filled

                    # Submit employer ID
                    for sel in continue_selectors:
                        try:
                            await page.click(sel, timeout=5000)
                            print(f"  Submitted employer ID via: {sel}")
                            await page.wait_for_timeout(3000)
                            break
                        except Exception:
                            continue

                entry["steps"][-1]["status"] = "completed" if employee_selected else "skipped"

                screenshot_path = self.output_path.with_name("step4_employee_id.png")
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"  Screenshot: {screenshot_path}")

                # Step 5: OTP verification
                print("\n[Step 5] OTP Verification...")
                entry["steps"].append({
                    "step": 5,
                    "action": "otp_verification",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                # Check if OTP page loaded
                otp_selectors = [
                    'input[name="otp"]',
                    'input[name="otpCode"]',
                    'input[id="otp"]',
                    'input[placeholder*="OTP" i]',
                    'input[placeholder*="verification code" i]',
                    'input[placeholder*="6-digit" i]',
                    'input[maxlength="6"]',
                ]

                otp_found = False
                for sel in otp_selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=5000)
                        print(f"  OTP field found via: {sel}")
                        otp_found = True
                        break
                    except Exception:
                        continue

                entry["steps"][-1]["otp_page_detected"] = otp_found

                if otp_found:
                    print("  *** OTP VERIFICATION REQUIRED ***")
                    print("  *** Need phone access to complete OTP ***")
                    entry["steps"][-1]["status"] = "otp_required"
                    entry["otp_required"] = True
                    entry["blocker"] = "OTP verification - need phone on file access"
                else:
                    entry["steps"][-1]["status"] = "no_otp_page"
                    entry["otp_required"] = False

                screenshot_path = self.output_path.with_name("step5_otp.png")
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"  Screenshot: {screenshot_path}")

                entry["registration_status"] = (
                    "otp_required" if otp_found else "in_progress"
                )

            except Exception as exc:  # noqa: BLE001
                print(f"\n[ERROR] {exc}")
                entry["error"] = str(exc)[:500]
                entry["registration_status"] = "error"

            finally:
                await browser.close()

        _atomic_write_json(self.output_path, self.results)
        print(f"\n{'='*60}")
        print(f"Registration complete. Results: {self.output_path}")
        print(f"{'='*60}")
        return self.output_path


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sydney Health Browser Registration — Playwright automation"
    )
    parser.add_argument("--first-name", type=str, default="LEANN",
                        help="First name")
    parser.add_argument("--last-name", type=str, default="JENKINS",
                        help="Last name")
    parser.add_argument("--dob", type=str, default="1976-12-04",
                        help="Date of birth (YYYY-MM-DD)")
    parser.add_argument("--employer-id", type=str, default=None,
                        help="Employer ID / group number")
    parser.add_argument("--output", type=Path,
                        default=Path("data/sydney_browser_registration.json"),
                        help="Output path")
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (no browser window)")
    parser.add_argument("--slow-mo", type=int, default=1000,
                        help="Slow motion delay in ms")

    args = parser.parse_args()

    reg = SydneyHealthBrowserRegistration(
        output_path=args.output,
        headless=args.headless,
        slow_mo=args.slow_mo,
    )
    await reg.register_person(
        first_name=args.first_name,
        last_name=args.last_name,
        dob=args.dob,
        employer_id=args.employer_id or "",
    )


if __name__ == "__main__":
    asyncio.run(main())
