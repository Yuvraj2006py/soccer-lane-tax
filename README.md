# Soccer Lane Tax

Measure whether a defensive press actually cuts off useful options for the ball
carrier — not just whether a defender ran toward the ball.

**Data:** [SkillCorner Open Data](https://github.com/SkillCorner/opendata) (A-League
broadcast tracking). Credit SkillCorner / PySport if you reuse this work.

## Setup

```bash
cd "C:\Users\yuvi2\Downloads\Lane Tax Metric"
python -m pip install -r requirements.txt
```

On Windows PowerShell, set the project on `PYTHONPATH` (or run pytest, which adds it via `tests/conftest.py`):

```powershell
$env:PYTHONPATH = "C:\Users\yuvi2\Downloads\Lane Tax Metric"
```

## Phase 0 smoke test

Loads one match, filters press-like events, joins them to tracking frames:

```bash
python scripts/smoke_phase0.py
python -m pytest tests/test_data_load.py -v
```

Default match: `2017461` (Melbourne Victory vs Auckland FC).

Tracking JSONL is cached to `.cache/tracking/*.parquet` on first load.

## Phase 1 review pack

Locked decisions: [`docs/phase1-decisions.md`](docs/phase1-decisions.md)

```bash
python scripts/phase1_review.py
python -m pytest tests/ -q
```

Then open `docs/phase1_review/review_sample.csv` and the PNGs under `docs/phase1_review/figures/`.

## Phase 2 — the metric

Design and football reasoning: [`docs/phase2-design.md`](docs/phase2-design.md). Results: [`docs/phase2/summary.md`](docs/phase2/summary.md).

```bash
python scripts/phase2_lane_tax.py          # all focus presses in match 2017461 (~8 min)
python -m pytest tests/ -q
```

Every press gets two kinds of number:

- **Team:** `ways_out`. How shut in was the carrier at the moment he played it?
- **Credit:** `lane_tax` and `credit_share`. How much of that was this presser, worked out by deleting him from
  the frame and re-scoring?

`docs/phase2/lane_maps/` shows each reviewed press twice: as it happened, and with the presser deleted.

## Phase 3 — all 20 matches

Constants frozen. Leave-one-match-out vs proximity and SkillCorner baselines.

```bash
python scripts/phase3_validate.py            # score + validate (~30–40 min first time; caches per match)
python scripts/phase3_validate.py --skip-score   # rebuild tables from docs/phase3/events/
```

Results: [`docs/phase3/summary.md`](docs/phase3/summary.md).

**Headline:** on held-out matches, **ways out left** beats “he was close” and SkillCorner’s options-ahead
for whether the attack was contained. **Lane Tax** stays a credit metric (~0.50 on team outcomes).

## Layout

```text
opendata/          # SkillCorner data (do not modify for analysis)
lane_tax/          # our package
scripts/           # smoke / batch runners
tests/
notebooks/         # later phases
docs/              # decisions, review packs, Phase 2 results
```
