#!/usr/bin/env python3
"""
Procurement Bid-Rigging Screen
AI for Canadians — Competition Bureau Proactive Enforcement PoC

Pulls federal contract award data from open.canada.ca and applies statistical
screens for bid-rigging patterns. All data is public. No confidential sources.

Usage:
    python3 procurement_screen.py
    python3 procurement_screen.py --dept DND --commodity 0399 --limit 5000
    python3 procurement_screen.py --sector IT --output report.md

Signals screened:
  1. Vendor lock-in concentration (one vendor dominates a dept + commodity)
  2. Single-bid dominance (high-value contracts with no competition)
  3. Rotational win patterns (vendor cluster sharing wins in a category)
  4. Amendment inflation (contracts ballooning post-award)
  5. Solicitation procedure anomalies (sole-source on high-value work)
"""

import json
import urllib.request
import urllib.parse
import collections
import statistics
import sys
import argparse
from datetime import datetime

API_BASE = "https://open.canada.ca/data/api/3/action/datastore_search"
RESOURCE_ID = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"

SOLE_SOURCE_CODES = {"NN", "NO"}

SECTORS = {
    "IT":       ["0369","0370","0371","0372","0373","0374"],
    "IT_BROAD": ["0369","0371","0372","0499","0362","0363"],
    "CONSULT":  ["0491","0499","0412","0414","0415"],
    "INFRA":    ["0541","0542","0543","0544","0545","0546"],
    "LEGAL":    ["0222","0223"],
    "COMMS":    ["0351","0352","0353"],
}

RISK_THRESHOLDS = {
    "high_value_sole_source": 100_000,
    "amendment_inflation_pct": 50,
    "vendor_concentration_pct": 60,
    "min_contracts_for_rotation": 5,
}

def fetch_contracts(limit=10000, dept=None, commodity=None, sector=None, year_from=2020):
    filters = {}
    if dept:
        filters["owner_org"] = dept
    if commodity:
        filters["economic_object_code"] = commodity

    params = {"resource_id": RESOURCE_ID, "limit": min(limit, 32000)}
    if filters:
        params["filters"] = json.dumps(filters)

    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    print(f"  Fetching from open.canada.ca...")

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

    if not data.get("success"):
        print(f"  API error: {data.get('error')}")
        return []

    records = data["result"]["records"]
    total = data["result"]["total"]
    print(f"  Retrieved {len(records):,} of {total:,} total contracts")

    if sector and sector in SECTORS:
        codes = SECTORS[sector]
        records = [r for r in records if r.get("economic_object_code","") in codes]
        print(f"  After sector filter ({sector}): {len(records):,}")

    filtered = []
    for r in records:
        try:
            year = int(str(r.get("contract_date","2000"))[:4])
            if year >= year_from:
                filtered.append(r)
        except:
            filtered.append(r)

    if year_from > 2000:
        print(f"  After year filter (>={year_from}): {len(filtered):,}")

    return filtered

def screen_vendor_concentration(records, threshold_pct=60):
    groups = collections.defaultdict(list)
    for r in records:
        dept = (r.get("owner_org_title") or r.get("owner_org","UNKNOWN")).split("|")[0].strip()[:50]
        commodity = r.get("economic_object_code","??")
        try:
            val = float(r.get("contract_value") or 0)
        except:
            val = 0
        groups[(dept, commodity)].append((r.get("vendor_name","UNKNOWN"), val))

    results = []
    for (dept, commodity), contracts in groups.items():
        if len(contracts) < 5:
            continue
        total_val = sum(v for _, v in contracts)
        if total_val < 50_000:
            continue
        vendor_totals = collections.defaultdict(float)
        for vendor, val in contracts:
            vendor_totals[vendor] += val
        top_vendor = max(vendor_totals, key=vendor_totals.get)
        top_val = vendor_totals[top_vendor]
        pct = (top_val / total_val * 100) if total_val > 0 else 0
        if pct >= threshold_pct:
            results.append({"signal": "VENDOR_CONCENTRATION", "dept": dept, "commodity": commodity,
                           "top_vendor": top_vendor, "pct_of_spend": round(pct,1),
                           "vendor_total": round(top_val,0), "category_total": round(total_val,0),
                           "contract_count": len(contracts)})

    return sorted(results, key=lambda x: x["pct_of_spend"], reverse=True)[:20]

def screen_sole_source(records, threshold=100_000):
    results = []
    for r in records:
        if r.get("solicitation_procedure","") not in SOLE_SOURCE_CODES:
            continue
        try:
            val = float(r.get("contract_value") or 0)
        except:
            continue
        if val < threshold:
            continue
        results.append({"signal": "SOLE_SOURCE_HIGH_VALUE", "vendor": r.get("vendor_name","UNKNOWN"),
                       "dept": (r.get("owner_org_title") or r.get("owner_org","")).split("|")[0].strip()[:50],
                       "value": round(val,0), "date": r.get("contract_date",""),
                       "description": r.get("description_en","")[:60],
                       "procedure_code": r.get("solicitation_procedure",""),
                       "ref": r.get("reference_number","")})
    return sorted(results, key=lambda x: x["value"], reverse=True)[:20]

def screen_amendment_inflation(records, threshold_pct=50, min_value=50_000):
    results = []
    for r in records:
        try:
            original = float(r.get("original_value") or 0)
            current = float(r.get("contract_value") or 0)
            amendment = float(r.get("amendment_value") or 0)
        except:
            continue
        if original < min_value or original <= 0:
            continue
        inflation_pct = ((current - original) / original) * 100
        if inflation_pct >= threshold_pct:
            results.append({"signal": "AMENDMENT_INFLATION", "vendor": r.get("vendor_name","UNKNOWN"),
                           "dept": (r.get("owner_org_title") or r.get("owner_org","")).split("|")[0].strip()[:50],
                           "original_value": round(original,0), "current_value": round(current,0),
                           "inflation_pct": round(inflation_pct,1), "amendment_value": round(amendment,0),
                           "date": r.get("contract_date",""), "description": r.get("description_en","")[:60],
                           "ref": r.get("reference_number","")})
    return sorted(results, key=lambda x: x["inflation_pct"], reverse=True)[:20]

def screen_rotation(records, min_contracts=5):
    groups = collections.defaultdict(list)
    for r in records:
        dept = (r.get("owner_org_title") or r.get("owner_org","UNKNOWN")).split("|")[0].strip()[:50]
        commodity = r.get("economic_object_code","??")
        vendor = r.get("vendor_name","UNKNOWN")
        try:
            val = float(r.get("contract_value") or 0)
        except:
            val = 0
        groups[(dept, commodity)].append((vendor, val, r.get("contract_date","")))

    results = []
    for (dept, commodity), contracts in groups.items():
        if len(contracts) < min_contracts:
            continue
        vendors = [v for v, _, _ in contracts]
        unique_vendors = set(vendors)
        if len(unique_vendors) < 2:
            continue
        win_counts = collections.Counter(vendors)
        n = len(contracts)
        hhi = sum((count/n * 100)**2 for count in win_counts.values())
        total_val = sum(v for _, v, _ in contracts)
        if hhi < 5000 and 2 <= len(unique_vendors) <= 6:
            sorted_contracts = sorted(contracts, key=lambda x: x[2])
            sequence = [v for v, _, _ in sorted_contracts]
            half = len(sequence) // 2
            first_set = set(sequence[:half])
            second_set = set(sequence[half:])
            overlap = len(first_set & second_set) / len(first_set | second_set) if first_set | second_set else 0
            if overlap >= 0.5:
                results.append({"signal": "ROTATION_PATTERN", "dept": dept, "commodity": commodity,
                               "vendors": ", ".join(sorted(unique_vendors)), "vendor_count": len(unique_vendors),
                               "contract_count": len(contracts), "hhi": round(hhi,0),
                               "temporal_overlap": round(overlap,2), "total_value": round(total_val,0),
                               "win_distribution": dict(win_counts.most_common())})
    return sorted(results, key=lambda x: x["temporal_overlap"], reverse=True)[:15]

def screen_bid_convergence(records):
    multi_bid = [r for r in records if r.get("number_of_bids") and
                 str(r.get("number_of_bids","")).strip() not in ("", "0", "1", "None")]
    if not multi_bid:
        return []
    groups = collections.defaultdict(list)
    for r in multi_bid:
        vendor = r.get("vendor_name","UNKNOWN")
        commodity = r.get("economic_object_code","??")
        try:
            val = float(r.get("contract_value") or 0)
            bids = int(str(r.get("number_of_bids")).split(".")[0])
        except:
            continue
        groups[(vendor, commodity)].append((val, bids))
    results = []
    for (vendor, commodity), records_g in groups.items():
        if len(records_g) < 3:
            continue
        avg_bids = statistics.mean(b for _, b in records_g)
        total_val = sum(v for v, _ in records_g)
        if avg_bids >= 2.0 and len(records_g) >= 5:
            results.append({"signal": "CONSISTENT_MULTI_BID_WINNER", "vendor": vendor,
                           "commodity": commodity, "wins": len(records_g),
                           "avg_competing_bids": round(avg_bids,1), "total_value_won": round(total_val,0)})
    return sorted(results, key=lambda x: x["total_value_won"], reverse=True)[:10]

def print_report(results, records_count, args):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["=" * 72, "FEDERAL PROCUREMENT BID-RIGGING SCREEN",
             "AI for Canadians — Competition Bureau PoC",
             f"Run: {now} | Records: {records_count:,} | All data: public",
             "=" * 72, "",
             "NOTE: Intelligence leads only. All flags require human review.", ""]

    for key, (label, desc) in {
        "concentration": ("SIGNAL 1 — VENDOR CONCENTRATION", "One vendor >60% of dept+commodity spend"),
        "sole_source":   ("SIGNAL 2 — HIGH-VALUE SOLE-SOURCE", "Contracts >$100K without competition"),
        "amendments":    ("SIGNAL 3 — AMENDMENT INFLATION", "Contracts growing >50% from original value"),
        "rotation":      ("SIGNAL 4 — ROTATIONAL WIN PATTERNS", "Vendor clusters sharing wins in same category"),
        "convergence":   ("SIGNAL 5 — CONSISTENT MULTI-BID WINNERS", "Winning repeatedly despite declared competition"),
    }.items():
        items = results.get(key, [])
        lines += ["-" * 72, label, desc, f"Flags: {len(items)}", ""]
        if not items:
            lines += ["  No flags above threshold.", ""]
            continue
        for i, item in enumerate(items[:10], 1):
            sig = item.get("signal","")
            if sig == "VENDOR_CONCENTRATION":
                lines += [f"  [{i}] {item['top_vendor']}",
                          f"      Dept: {item['dept']} | Code: {item['commodity']}",
                          f"      Share: {item['pct_of_spend']}% of ${item['category_total']:,.0f} | Contracts: {item['contract_count']}", ""]
            elif sig == "SOLE_SOURCE_HIGH_VALUE":
                lines += [f"  [{i}] ${item['value']:,.0f} — {item['vendor']}",
                          f"      Dept: {item['dept']} | {item['date']} | Ref: {item['ref']}", ""]
            elif sig == "AMENDMENT_INFLATION":
                lines += [f"  [{i}] +{item['inflation_pct']}% — {item['vendor']}",
                          f"      ${item['original_value']:,.0f} → ${item['current_value']:,.0f} | {item['dept']}",
                          f"      {item['description']} | Ref: {item['ref']}", ""]
            elif sig == "ROTATION_PATTERN":
                lines += [f"  [{i}] {item['vendor_count']} vendors rotating — {item['dept']} / {item['commodity']}",
                          f"      {item['vendors'][:80]}",
                          f"      HHI: {item['hhi']} | Overlap: {item['temporal_overlap']} | Total: ${item['total_value']:,.0f}", ""]
            elif sig == "CONSISTENT_MULTI_BID_WINNER":
                lines += [f"  [{i}] {item['vendor']} (code {item['commodity']})",
                          f"      Wins: {item['wins']} | Avg competing bids: {item['avg_competing_bids']} | Total: ${item['total_value_won']:,.0f}", ""]

    lines += ["=" * 72,
              "SOURCE: open.canada.ca — Proactive Publication: Contracts over $10,000",
              "All findings require investigative validation before any action.",
              "github.com/ai-for-canadians/proactive-competition-ai",
              "=" * 72]
    report = "\n".join(lines)
    print(report)
    return report

def main():
    parser = argparse.ArgumentParser(description="Federal Procurement Bid-Rigging Screen")
    parser.add_argument("--dept", help="Department org code (e.g. dnd-mdn)")
    parser.add_argument("--commodity", help="Economic object code (e.g. 0369)")
    parser.add_argument("--sector", help=f"Sector: {', '.join(SECTORS.keys())}")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--year-from", type=int, default=2021)
    parser.add_argument("--output", help="Save to file")
    args = parser.parse_args()

    print("\nFEDERAL PROCUREMENT BID-RIGGING SCREEN")
    print("-" * 50)
    records = fetch_contracts(limit=args.limit, dept=args.dept,
                              commodity=args.commodity, sector=args.sector,
                              year_from=args.year_from)
    if not records:
        print("No records. Check connection or filters.")
        return

    print(f"\nRunning screens on {len(records):,} contracts...")
    results = {
        "concentration": screen_vendor_concentration(records, RISK_THRESHOLDS["vendor_concentration_pct"]),
        "sole_source":   screen_sole_source(records, RISK_THRESHOLDS["high_value_sole_source"]),
        "amendments":    screen_amendment_inflation(records, RISK_THRESHOLDS["amendment_inflation_pct"]),
        "rotation":      screen_rotation(records, RISK_THRESHOLDS["min_contracts_for_rotation"]),
        "convergence":   screen_bid_convergence(records),
    }
    report = print_report(results, len(records), args)
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nSaved to: {args.output}")

if __name__ == "__main__":
    main()
