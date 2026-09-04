#!/usr/bin/env python3
"""
BuyAndSell Solicitation Monitor — Early Warning System
AI for Canadians — Competition Bureau Proactive Enforcement

Monitors federal procurement data for new contracts that match the
ArriveCan/Dalian pattern signature. Designed to detect procurement risk
patterns as early as possible — before amendment inflation compounds.

The ArriveCan Pattern Signature (flags on 3+ of 7 elements):
  1. PSIB Indigenous procurement set-aside
  2. IT services commodity (staffing, consulting, infrastructure)
  3. Federal department with major IT delivery history (CBSA, DND, IRCC, SSC)
  4. Small vendor (original value below competitive tendering threshold)
  5. Amendment inflation (contract value >> original)
  6. Crisis/emergency procurement period (2020-2022)
  7. Vendor on known risk watchlist (Dalian, Coradix, GCStrategies)

Run:
    python3 buyandsell_monitor.py                   # Check last 7 days
    python3 buyandsell_monitor.py --days 30         # Check last 30 days
    python3 buyandsell_monitor.py --output alert.txt
    python3 buyandsell_monitor.py --watchlist vendors.txt

Designed to run daily on a cron schedule or via GitHub Actions.
No external API calls. No data leaves the machine.
"""

import urllib.request
import urllib.parse
import json
import collections
import argparse
from datetime import datetime, timedelta

PROCUREMENT_API = "https://open.canada.ca/data/api/3/action/datastore_search"
RESOURCE_ID = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"

HIGH_RISK_DEPARTMENTS = {
    "cbsa-asfc": "Canada Border Services Agency",
    "dnd-mdn": "National Defence",
    "ircc-ircc": "Immigration, Refugees and Citizenship Canada",
    "ssc-spc": "Shared Services Canada",
    "tbs-sct": "Treasury Board Secretariat",
    "cra-arc": "Canada Revenue Agency",
    "phac-aspc": "Public Health Agency of Canada",
}

IT_COMMODITY_CODES = {
    "369", "370", "371", "372", "373", "374",
    "473",
    "491", "499",
    "362", "363",
    "672",
}

CRISIS_YEARS = {"2020", "2021", "2022"}

KNOWN_RISK_VENDORS = {
    "dalian enterprises",
    "coradix technology",
    "gcstrategies",
    "gc strategies",
}

AMENDMENT_WATCHLIST = {
    "dalian enterprises inc.",
    "amazon web services canada",
    "cgi information systems",
}

def score_arrivecan_pattern(record):
    score = 0
    matched = []

    indigenous = str(record.get("indigenous_business", "") or "").strip().upper()
    if indigenous in ("Y", "YES", "1"):
        score += 1
        matched.append("PSIB Indigenous set-aside")

    commodity = str(record.get("economic_object_code", "") or "").strip().lstrip("0")
    if commodity in IT_COMMODITY_CODES:
        score += 1
        matched.append(f"IT commodity: {commodity}")

    dept = str(record.get("owner_org", "") or "").lower()
    for dept_code, dept_name in HIGH_RISK_DEPARTMENTS.items():
        if dept_code in dept:
            score += 1
            matched.append(f"High-risk dept: {dept_name}")
            break

    try:
        orig = float(record.get("original_value") or 0)
        if 0 < orig < 250_000:
            score += 1
            matched.append(f"Below threshold: ${orig:,.0f}")
    except:
        pass

    try:
        orig = float(record.get("original_value") or 0)
        curr = float(record.get("contract_value") or 0)
        if orig > 0 and (curr / orig) > 2:
            score += 1
            pct = int((curr - orig) / orig * 100)
            matched.append(f"Amendment inflation: +{pct}%")
    except:
        pass

    contract_date = str(record.get("contract_date", "") or "")[:4]
    if contract_date in CRISIS_YEARS:
        score += 1
        matched.append(f"Crisis-period: {contract_date}")

    vendor = str(record.get("vendor_name", "") or "").lower()
    for known in KNOWN_RISK_VENDORS:
        if known in vendor:
            score += 2
            matched.append(f"Known risk vendor: {vendor[:40]}")
            break
    for watchlisted in AMENDMENT_WATCHLIST:
        if watchlisted.lower() in vendor:
            score += 1
            matched.append(f"Amendment watchlist: {vendor[:40]}")
            break

    return score, matched


def screen_psib_concentration(records, min_total=250_000):
    vendor_dept = collections.defaultdict(lambda: {"total": 0, "count": 0, "dates": []})
    for r in records:
        if str(r.get("indigenous_business", "") or "").upper() not in ("Y", "YES"):
            continue
        commodity = str(r.get("economic_object_code", "") or "").strip().lstrip("0")
        if commodity not in IT_COMMODITY_CODES:
            continue
        vendor = r.get("vendor_name", "UNKNOWN")
        dept = (r.get("owner_org_title") or r.get("owner_org", "")).split("|")[0].strip()[:50]
        try:
            val = float(r.get("contract_value") or 0)
            vendor_dept[(vendor, dept)]["total"] += val
            vendor_dept[(vendor, dept)]["count"] += 1
            vendor_dept[(vendor, dept)]["dates"].append(r.get("contract_date", ""))
        except:
            pass
    results = []
    for (vendor, dept), data in vendor_dept.items():
        if data["total"] >= min_total:
            results.append({
                "vendor": vendor, "dept": dept,
                "total": round(data["total"], 0),
                "count": data["count"],
            })
    return sorted(results, key=lambda x: x["total"], reverse=True)


def fetch_contracts(days_back=7, limit=5000):
    params = {"resource_id": RESOURCE_ID, "limit": limit}
    url = f"{PROCUREMENT_API}?{urllib.parse.urlencode(params)}"
    print(f"  Fetching contracts (last {days_back} days)...")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ERROR: {e}")
        return []
    records = data.get("result", {}).get("records", [])
    print(f"  Retrieved {len(records):,}")
    return records


def main():
    parser = argparse.ArgumentParser(description="BuyAndSell Early Warning Monitor")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--output")
    parser.add_argument("--watchlist")
    parser.add_argument("--min-score", type=int, default=3)
    args = parser.parse_args()

    if args.watchlist:
        try:
            with open(args.watchlist) as f:
                KNOWN_RISK_VENDORS.update(l.strip().lower() for l in f if l.strip())
        except:
            pass

    print(f"\nBUYANDSELL EARLY WARNING MONITOR")
    print(f"Checking last {args.days} days | Min score: {args.min_score}/7")

    records = fetch_contracts(days_back=args.days, limit=args.limit)
    if not records:
        print("No records.")
        return

    flags = []
    for r in records:
        score, matched = score_arrivecan_pattern(r)
        if score >= args.min_score:
            vendor = r.get("vendor_name", "UNKNOWN")
            dept = (r.get("owner_org_title") or r.get("owner_org", "")).split("|")[0].strip()[:50]
            try:
                val = float(r.get("contract_value") or 0)
            except:
                val = 0
            flags.append({"score": score, "matched": matched, "vendor": vendor,
                          "dept": dept, "value": val,
                          "date": r.get("contract_date", ""),
                          "ref": r.get("reference_number", "")})

    flags.sort(key=lambda x: x["score"], reverse=True)
    psib = screen_psib_concentration(records)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "=" * 72,
        "BUYANDSELL EARLY WARNING MONITOR",
        "AI for Canadians | Competition Bureau Proactive Enforcement",
        f"Run: {now} | Records: {len(records):,} | Flags: {len(flags)}",
        "All flags are intelligence leads requiring human review.",
        "=" * 72, "",
    ]

    high = [f for f in flags if f["score"] >= 5]
    med  = [f for f in flags if 3 <= f["score"] < 5]

    lines += [f"HIGH PRIORITY (score 5-7): {len(high)}", ""]
    for i, f in enumerate(high[:10], 1):
        lines += [
            f"  [{i}] Score {f['score']}/7 | {f['vendor'][:50]}",
            f"      Dept: {f['dept']} | ${f['value']:,.0f} | {f['date']}",
            f"      Signals: {' | '.join(f['matched'][:4])}",
            f"      Ref: {f['ref']}", "",
        ]

    lines += [f"MEDIUM PRIORITY (score 3-4): {len(med)}", ""]
    for i, f in enumerate(med[:10], 1):
        lines += [
            f"  [{i}] Score {f['score']}/7 | {f['vendor'][:50]}",
            f"      {f['dept']} | ${f['value']:,.0f} | {' | '.join(f['matched'][:3])}",
            f"      Ref: {f['ref']}", "",
        ]

    lines += [f"PSIB IT CONCENTRATION: {len(psib)}", ""]
    for i, f in enumerate(psib[:5], 1):
        lines += [
            f"  [{i}] {f['vendor'][:50]}",
            f"      {f['dept']} | ${f['total']:,.0f} across {f['count']} contracts", "",
        ]

    lines += [
        "=" * 72,
        "github.com/ai-for-canadians/proactive-competition-ai",
        "=" * 72,
    ]

    report = "\n".join(lines)
    print(report)
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nSaved to: {args.output}")

if __name__ == "__main__":
    main()
