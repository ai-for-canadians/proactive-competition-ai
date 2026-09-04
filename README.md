# Proactive Competition AI
**Open-source AI tools for proactive competition enforcement and regulatory modernization**

Built by [AI for Canadians](https://aiforcanadians.org) in collaboration with the Competition Bureau of Canada.  
September 2026 · MIT License · All data public · No confidential sources.

---

## What this is

Two Python tools that surface competition-relevant intelligence from fully public Canadian government data — designed to help enforcement teams move from reactive (complaint-driven) to proactive (pattern-detected) investigation.

Built for:
- The Competition Bureau's Digital Enforcement and Intelligence Branch
- Provincial regulators and policy advocates
- Academic researchers studying competition in Canada
- Citizens and organizations using the new private access rights (Bill C-59, June 2025)

---

## Tools

### `procurement_screen.py` — Federal Procurement Bid-Rigging Screen

Pulls 1.3M+ federal contract records from open.canada.ca and applies five statistical screens for bid-rigging patterns.

| Signal | What it detects |
|--------|-----------------|
| Vendor concentration | One vendor capturing 60%+ of a dept+commodity spend |
| High-value sole-source | Contracts >$100K awarded without competition |
| Amendment inflation | Contracts growing >50% from original award |
| Rotation patterns | Vendor clusters sharing wins across same dept+category |
| Multi-bid consistency | Vendors winning repeatedly despite declared competition |

**Run:**
```bash
pip install requests pandas
python3 procurement_screen.py                                # 5,000 records, 2022+
python3 procurement_screen.py --limit 32000 --year-from 2019 --output report.txt
python3 procurement_screen.py --dept dnd-mdn                 # Filter by department
python3 procurement_screen.py --sector IT --output it.txt    # Filter by sector
```

**First run findings (Sep 4, 2026, 695 contracts):**
- Microsoft Canada: contract inflated 348% ($270K → $1.2M)
- CGI Information Systems: appears 4× in amendment inflation, 187–330% growth
- Thomson Reuters + LexisNexis rotating in legal research at Administrative Tribunals (HHI 3,554)
- Engineers in Motion: 5 wins, avg 4.4 competing bids per tender

---

### `regulatory_triage.py` — Federal Regulatory Corpus Triage

Downloads and analyzes the full federal laws XML corpus (971 acts, 1,000+ regulations) from `justicecanada/laws-lois-xml` and flags instruments for reform.

| Signal | What it detects |
|--------|-----------------|
| Staleness | Acts not amended in 15+ years |
| Tech-specificity | Provisions requiring physical presence, paper, fax, legacy media |
| Anti-competitive structure | Price floors/ceilings, membership barriers, exclusivity, geographic restrictions |

**Run:**
```bash
python3 regulatory_triage.py --sample 100         # Quick sample (2-3 min)
python3 regulatory_triage.py                      # Full corpus (971 acts, ~15 min)
python3 regulatory_triage.py --type regulations   # Analyze regulations
python3 regulatory_triage.py --sector financial health --output financial.txt
```

**First run findings (100 acts):**
- 63/100 acts flagged (score ≥ 15)
- Bank Act: score 138 — 48 in-person requirements, 492 branch references, facsimile still in text
- Agricultural Marketing Programs Act: price floors AND price ceilings in same act
- 34 acts not amended in 15+ years; 7 bilateral tax treaties from 2002–2006 still live
- Bills of Exchange Act: corporate seal and wet signature requirements still in force

---

## Data Sources

| Tool | Dataset | Source |
|------|---------|--------|
| Procurement | Proactive Publication — Contracts over $10,000 | [open.canada.ca](https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b) |
| Regulatory | Federal laws XML corpus | [justicecanada/laws-lois-xml](https://github.com/justicecanada/laws-lois-xml) |

Both datasets are fully public. No authentication required.

---

## Requirements

```bash
pip install requests pandas
# Python 3.8+ required
```

No other dependencies. All other imports are Python standard library.

---

## Limitations

**Procurement tool:**
- API limit: 32,000 records per call out of 1.3M total
- No individual bid prices — only winning contract value and declared bid count
- Amendment inflation can be legitimate (genuine scope changes) — not evidence of wrongdoing
- Rotation flags require cross-checking corporate registries for related parties

**Regulatory tool:**
- NLP pattern matching produces false positives — "physical location" catches real offices, not just anti-digital provisions
- Anti-competitive flags require legal review — some provisions reflect intentional policy
- Text extraction from XML may miss context; provision-level reading required for any action

**Both tools produce intelligence leads, not evidence.** Every flag requires qualified human review before any action.

---

## What's next

- [ ] Scale procurement to full 1.3M population with pagination
- [ ] Corporate registry cross-reference for rotation patterns (ISED company database)
- [ ] Provincial procurement portals (Ontario, BC, Quebec)
- [ ] Full regulatory corpus run: 971 acts + 1,000 regulations
- [ ] Provincial regulatory corpus (starting with ON and NS)
- [ ] Gazette scraper: monitor live consultations for competition concerns
- [ ] Judge analytics dashboard (separate track — legal aid / Judicial Council audience)

---

## Contribute

Built by [Patrick Farrar](https://linkedin.com/in/matthew-chiasson) / [AI for Canadians](https://aiforcanadians.org).  
Contact: patrick@aiforcanadians.org

Interested in building on this? [Build Canada](https://buildcanada.com) is actively looking for engineers to build open-source AI tools for government. This repo is a natural home for that collaboration.

Pull requests welcome. Issues welcome. Fork freely — this is public interest infrastructure.
