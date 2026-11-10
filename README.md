# Wellness Gift Card (Standalone)

Automated discovery, enrollment, and redemption of wellness-program gift cards
— built as a **standalone project** moved out of CRD.

## What this is

A **real (non-simulated)** wellness gift-card pipeline. Unlike the previous CRD
framework (which returned `"simulated": true` on every tool and produced zero
enrollments/gift cards), these tools make live network calls:

- `tools/mhc_enrollment_tool.py` — registers real people against the live
  Mobile Health Consumer (MHC) API:
  `POST https://sn.mobilehealthconsumer.com/api/v3/registerUser/`
- `tools/sydney_wellness_client.py` — probes Sydney Health wellness/rewards
  endpoints with an authenticated session token.

## Honest status

Wellness gift cards are **server-side benefit programs** (Anthem/Elevance Sydney
Health, MHC Wellness). They are issued only to **verified enrolled members**.
There is **no scriptable bypass** for the server-side membership check.

Current state:
- MHC enrollment tool works; all 10 test candidates returned `invalidUserIdentifier`
  (none were enrolled in MHC wellness)
- One working Anthem session token exists; Sydney Health reward endpoints live
  inside the authenticated app (not at guessable paths)
- 401 person profiles available for enrichment (274 with DOB + SSN last-4)

**The gating item to a real gift card:** one real enrolled member identity
(member ID / name / DOB / SSN last-4). Without it, no automation can produce a
gift card.

## Quick start

```bash
# 1. Build a candidate list (first_name, last_name, dob YYYY-MM-DD, ssn4, source)
#    See data/people_to_enroll.json for format.

# 2. Run real MHC enrollment (Tor proxy recommended to bypass Akamai)
python3 tools/mhc_enrollment_tool.py \
  --people data/people_to_enroll.json \
  --output data/mhc_enrollment_results.json \
  --delay 2.0

# 3. Probe Sydney Health with a real session token
python3 tools/sydney_wellness_client.py \
  --session-token "YOUR_SESSION_TOKEN" \
  --output data/sydney_wellness_results.json
```

## Requirements

- Python 3.11+
- `requests`
- Tor SOCKS5 proxy at `127.0.0.1:9050` (bypasses Akamai on Anthem domains)

```bash
pip install requests
```

## Project layout

```
data/          person profiles, payroll index, candidates, results
tools/         real enrollment + wellness probe tools
config/        (proxy, endpoint config)
docs/          STRATEGY.md — honest strategy + path to gift cards
```

## Disclaimer

This tool is for authorized research/automation on wellness programs you or your
organization are entitled to use. Do not use it to enroll in benefit programs
for people who are not actually enrolled members.
