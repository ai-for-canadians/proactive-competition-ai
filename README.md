# Proactive Competition AI
**Open-source AI tools for proactive competition enforcement and regulatory modernization**

Built by [AI for Canadians](https://aiforcanadians.org) in collaboration with the Competition Bureau of Canada.  
September 2026 · MIT License · All data public · No confidential sources · Zero AI API costs to run.

---

## What this is

Three Python tools that surface competition-relevant intelligence from fully public Canadian government data. Designed to help enforcement teams, regulators, researchers, and private litigants move from reactive (complaint-driven) to proactive (pattern-detected) investigation.

**Proof of concept:** The procurement screen independently identified Dalian Enterprises at CBSA as the highest amendment inflation flag in 19,870 contracts — a 2-person company with a $404K original award that grew to $31.2M. When we looked it up: already under RCMP investigation and federal suspension from the ArriveCan fallout. The tool found it from math on public data, before we knew what the company was.

---

## Tools

### `procurement_screen.py` — Federal Procurement Bid-Rigging Screen

Pulls 1.3M+ federal contract records from open.canada.ca and applies five statistical screens.

| Signal | What it detects |
|--------|-----------------|
| Vendor concentration | One vendor >60% of dept+commodity spend |
| High-value sole-source | Contracts >$100K without competition |
| Amendment inflation | Contracts growing >50% from original award |
| Rotation patterns | Vendor clusters sharing wins in same category |
| Multi-bid consistency | Winning repeatedly despite declared competition |

```bash
python3 procurement_screen.py                                # 5,000 records, 2022+
python3 procurement_screen.py --limit 32000 --year-from 2019 --output report.txt
python3 procurement_screen.py --sector IT                    # IT services focus
```

---

### `regulatory_triage.py` — Federal Regulatory Corpus Triage

Analyzes all 971 federal acts + 1,000+ regulations from the Justice Laws XML corpus.

| Signal | What it detects |
|--------|-----------------|
| Staleness | Acts not amended in 15+ years |
| Tech-specificity | Physical presence, paper, fax, legacy media requirements |
| Anti-competitive structure | Price floors/ceilings, membership barriers, exclusivity |

**First full-corpus run (Sep 2026):** 645 of 971 acts flagged. Excise Tax Act + Income Tax Act scored highest (147). 322 acts not amended in 15+ years. Criminal Code still has 9 telegraph references.

```bash
python3 regulatory_triage.py --sample 100      # Quick run
python3 regulatory_triage.py                   # Full corpus (~15 min)
python3 regulatory_triage.py --sector financial health
```

---

### `buyandsell_monitor.py` — Early Warning Monitor

Scores new federal contracts against the **ArriveCan/Dalian pattern signature** — 7 elements that collectively identify high-risk procurement before amendment inflation compounds.

| Pattern Element | Signal |
|----------------|--------|
| PSIB set-aside | Indigenous procurement bypasses competitive tendering |
| IT commodity | High-risk services category (codes 473, 369-374, 491, 499) |
| High-risk dept | CBSA, DND, IRCC, SSC, TBS |
| Below-threshold original | Award below $250K competitive tender threshold |
| Amendment inflation | Contract value >2x original |
| Crisis period | Signed 2020-2022 (emergency procurement era) |
| Known risk vendor | Matches investigation watchlist |

**Score 3+ = flag for review. Score 5+ = immediate attention.**

```bash
python3 buyandsell_monitor.py                  # Last 7 days
python3 buyandsell_monitor.py --days 30 --output alerts.txt
python3 buyandsell_monitor.py --watchlist my_vendors.txt
```

---

## Automated Weekly Scanning — GitHub Actions

The repo includes a GitHub Actions workflow (`.github/workflows/monitor.yml`) that runs every Monday at 8am UTC:

- Runs all three tools
- Commits results to `results/` folder
- Uploads as downloadable artifact
- Zero cost, zero infrastructure

To enable: just push to main. Actions runs automatically. Results appear in `results/` within ~5 minutes.

To run manually: GitHub → Actions tab → "Weekly Procurement Monitor" → Run workflow.

---

## For the Competition Bureau's Digital Enforcement & Intelligence Branch

No hosting needed. Runs on your sovereign servers:

```bash
git clone https://github.com/ai-for-canadians/proactive-competition-ai
pip install requests pandas
python3 buyandsell_monitor.py --days 7 --output alert.txt
python3 procurement_screen.py --limit 32000 --output results.txt
```

- No external API calls for sensitive data
- No data leaves the machine
- Swap `RESOURCE_ID` in config to point at internal PSPC data
- MIT licensed — your team owns whatever you build on top

---

## Data Sources

| Tool | Dataset | Source |
|------|---------|--------|
| Procurement | Proactive Publication — Contracts over $10,000 | [open.canada.ca](https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b) |
| Regulatory | Federal laws XML corpus | [justicecanada/laws-lois-xml](https://github.com/justicecanada/laws-lois-xml) |
| BuyAndSell monitor | Same procurement API, pattern screening | open.canada.ca |

---

## Requirements

```bash
pip install requests pandas
# Python 3.8+ required. All other imports are standard library.
```

---

## What's Next

- [ ] Provincial procurement portals (Ontario/BC/Quebec)
- [ ] Corporate registry cross-reference (ISED API)
- [ ] Property covenant mapping (municipal land registries)
- [ ] AI-washing audit (C-59 deceptive marketing screen)
- [ ] Private litigant version (legal evidentiary output format)
- [ ] Next.js dashboard on Vercel reading GitHub Actions results

---

## Built by

[Patrick Farrar](https://linkedin.com/in/matthew-chiasson) / [AI for Canadians](https://aiforcanadians.org)  
Contact: patrick@aiforcanadians.org  

Collaborating with the Competition Bureau of Canada, Build Canada, and the Canadian Shield Institute.

Pull requests welcome. Issues welcome. Fork freely — this is public interest infrastructure.
