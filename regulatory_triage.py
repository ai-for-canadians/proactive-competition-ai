#!/usr/bin/env python3
"""
Federal Regulatory Corpus Triage
AI for Canadians — Competition Bureau Regulatory Modernization PoC

Analyzes the federal laws XML corpus (justicecanada/laws-lois-xml) to surface
regulatory instruments ripe for reform: outdated, technology-specific, or
anti-competitive in structure.

Usage:
    python3 regulatory_triage.py --sample 50       # Quick run
    python3 regulatory_triage.py                   # Full corpus (971 acts, ~15 min)
    python3 regulatory_triage.py --type regulations
    python3 regulatory_triage.py --sector financial health
    python3 regulatory_triage.py --output report.txt
"""

import urllib.request
import xml.etree.ElementTree as ET
import json, re, collections, argparse, time
from datetime import datetime

GITHUB_API = "https://api.github.com/repos/justicecanada/laws-lois-xml/contents/eng"

TECH_SPECIFICITY_PATTERNS = [
    (r'\b(in person|in-person|physical presence|face.to.face|attend in person)\b', "physical_presence", "HIGH"),
    (r'\b(branch|branches|office|branch office|bricks and mortar)\b', "physical_location", "MEDIUM"),
    (r'\b(written notice|in writing|printed|paper copy|paper form)\b', "paper_requirement", "MEDIUM"),
    (r'\b(telegraph|telex|facsimile|fax|telecopier)\b', "legacy_telecom", "HIGH"),
    (r'\b(microfilm|microfiche|punch card|magnetic tape)\b', "legacy_storage", "HIGH"),
    (r'\b(disk|diskette|compact disc|CD-ROM)\b', "legacy_media", "HIGH"),
    (r'\b(wet signature|original signature|notarized|notarize|under seal)\b', "signature_requirement", "MEDIUM"),
    (r'\b(seal of the corporation|corporate seal|common seal)\b', "corporate_seal", "MEDIUM"),
    (r'\b(registered mail|registered post|courier|hand deliver)\b', "physical_delivery", "LOW"),
    (r'\b(cheque|check|bank draft|money order|postal order)\b', "legacy_payment", "LOW"),
    (r'\b(passbook|bankbook|savings book)\b', "legacy_banking", "HIGH"),
]

ANTICOMP_PATTERNS = [
    (r'\b(only.*licensed|only.*certified|must be.*member)\b', "membership_barrier", "HIGH"),
    (r'\b(maximum.*price|price.*shall not exceed|price.cap)\b', "price_ceiling", "MEDIUM"),
    (r'\b(minimum.*price|price.*shall not be less|floor price)\b', "price_floor", "HIGH"),
    (r'\b(one.*supplier|single.*supplier|sole.*supplier|exclusive.*supplier)\b', "exclusivity", "HIGH"),
    (r'\b(quota|production quota|supply quota)\b', "production_quota", "HIGH"),
    (r'\b(geographic.*restriction|territory.*restriction|area.*restriction)\b', "geographic_barrier", "MEDIUM"),
]

SECTOR_KEYWORDS = {
    "financial":    ["bank", "banking", "financial institution", "credit union", "insurance", "fintech", "payment"],
    "telecom":      ["telecommunication", "telephone", "wireless", "broadband", "internet service"],
    "health":       ["pharmacy", "pharmacist", "medical", "health service", "hospital", "drug"],
    "professional": ["lawyer", "accountant", "engineer", "architect", "real estate agent", "broker"],
    "transport":    ["truck", "carrier", "shipping", "air carrier", "railway"],
    "energy":       ["electricity", "natural gas", "petroleum", "utility"],
    "agriculture":  ["agricultural", "farming", "grain", "dairy", "supply management"],
}

STALE_YEARS, VERY_STALE_YEARS = 15, 25

def fetch_file_list(instrument_type="acts", limit=None):
    url = f"{GITHUB_API}/{instrument_type}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AIFC-RegTriage/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            files = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error: {e}")
        return []
    xml_files = [f for f in files if f["name"].endswith(".xml")]
    return xml_files[:limit] if limit else xml_files

def fetch_xml(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AIFC-RegTriage/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
        return ET.fromstring(content)
    except:
        return None

def parse_statute(root, filename):
    if root is None:
        return None
    short_title, long_title = "", ""
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "ShortTitle" and not short_title:
            short_title = (elem.text or "").strip()
        elif tag == "LongTitle" and not long_title:
            long_title = (elem.text or "").strip()
    attribs = root.attrib
    last_amended = attribs.get("{http://justice.gc.ca/lims}lastAmendedDate", "")
    in_force = attribs.get("{http://justice.gc.ca/lims}inforce-start-date", "")
    parts = []
    for elem in root.iter():
        if elem.text: parts.append(elem.text.strip())
        if elem.tail: parts.append(elem.tail.strip())
    full_text = " ".join(p for p in parts if p).lower()
    return {"filename": filename, "short_title": short_title or filename.replace(".xml",""),
            "long_title": long_title, "last_amended": last_amended, "in_force_start": in_force,
            "text": full_text, "text_length": len(full_text)}

def score_statute(statute):
    score, signals = 0, []
    amended = statute.get("last_amended","")
    if amended:
        try:
            age = datetime.now().year - int(amended[:4])
            if age >= VERY_STALE_YEARS:
                score += 40; signals.append(("STALE", "HIGH", f"Last amended {amended[:4]} — {age} years ago"))
            elif age >= STALE_YEARS:
                score += 20; signals.append(("STALE", "MEDIUM", f"Last amended {amended[:4]} — {age} years ago"))
        except: pass

    text = statute.get("text","")
    for pattern, category, severity in TECH_SPECIFICITY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            unique = list(set(m if isinstance(m, str) else m[0] for m in matches))[:2]
            pts = {"HIGH": 15, "MEDIUM": 8, "LOW": 3}[severity]
            score += pts
            signals.append((f"TECH:{category}", severity, f"{', '.join(str(e) for e in unique)} ({len(matches)}x)"))

    for pattern, category, severity in ANTICOMP_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            unique = list(set(m if isinstance(m, str) else m[0] for m in matches))[:2]
            pts = {"HIGH": 20, "MEDIUM": 10}[severity]
            score += pts
            signals.append((f"ANTICOMP:{category}", severity, f"{', '.join(str(e) for e in unique)} ({len(matches)}x)"))

    if statute.get("text_length",0) < 500:
        score += 5; signals.append(("SHORT", "LOW", f"{statute['text_length']} chars — may be vestigial"))
    return score, signals

def get_sectors(statute):
    text = statute.get("text","") + statute.get("short_title","").lower()
    found = [(s, sum(text.count(k) for k in kws)) for s, kws in SECTOR_KEYWORDS.items()]
    return [s for s, c in sorted(found, key=lambda x: x[1], reverse=True) if c > 5][:3]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["acts","regulations"], default="acts")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--sector", nargs="+", choices=list(SECTOR_KEYWORDS.keys()))
    parser.add_argument("--min-score", type=int, default=15)
    parser.add_argument("--output")
    args = parser.parse_args()

    print(f"\nFEDERAL REGULATORY CORPUS TRIAGE")
    print(f"Instrument type: {args.type}{f' (sample: {args.sample})' if args.sample else ' (full corpus)'}")

    files = fetch_file_list(args.type, limit=args.sample)
    print(f"Found {len(files)} instruments\n")

    results, errors = [], 0
    for i, f in enumerate(files):
        if (i+1) % 50 == 0 or i < 2:
            print(f"  [{i+1}/{len(files)}] {f['name']}...")
        root = fetch_xml(f["download_url"])
        statute = parse_statute(root, f["name"])
        if statute is None:
            errors += 1; continue
        score, signals = score_statute(statute)
        if score >= args.min_score:
            results.append((statute, score, signals))
        time.sleep(0.05)

    ranked = sorted(results, key=lambda x: x[1], reverse=True)
    print(f"\nAnalyzed {len(files)} ({errors} errors) | Flagged: {len(ranked)}")

    stale_n = sum(1 for _,_,s in ranked if any(x[0]=="STALE" for x in s))
    tech_n  = sum(1 for _,_,s in ranked if any(x[0].startswith("TECH") for x in s))
    ac_n    = sum(1 for _,_,s in ranked if any(x[0].startswith("ANTICOMP") for x in s))

    lines = ["=" * 72, "FEDERAL REGULATORY CORPUS TRIAGE — REFORM OPPORTUNITY MAP",
             "AI for Canadians | github.com/ai-for-canadians/proactive-competition-ai",
             f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Analyzed: {len(files)} | Flagged: {len(ranked)}",
             "=" * 72, "",
             f"Stale (15+ yrs): {stale_n}  |  Tech-specific: {tech_n}  |  Anti-competitive: {ac_n}", "",
             "-" * 72]

    for rank, (statute, score, signals) in enumerate(ranked[:25], 1):
        lines.append(f"[{rank:2}] {statute['short_title']} — Score: {score}")
        if statute.get("last_amended"):
            lines.append(f"     Amended: {statute['last_amended']} | In force: {statute.get('in_force_start','?')}")
        sectors = get_sectors(statute)
        if sectors:
            lines.append(f"     Sectors: {', '.join(sectors)}")
        for sig_type, severity, note in signals[:4]:
            badge = {"HIGH": "⚠ ", "MEDIUM": "△ ", "LOW": "· "}.get(severity, "  ")
            lines.append(f"     {badge}[{sig_type}] {note[:75]}")
        lines.append("")

    lines += ["=" * 72,
              "TECH flags → technology-neutral redraft candidates",
              "ANTICOMP flags → Bureau advocacy candidates",
              "STALE flags → sunset review candidates",
              "All flags require legal review before any action.",
              "=" * 72]

    report = "\n".join(lines)
    print(report)
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Saved to: {args.output}")

if __name__ == "__main__":
    main()
