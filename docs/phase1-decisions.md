# Phase 1 decisions (locked for Phase 2)

Match used: **2017461** — Melbourne Victory vs Auckland FC (SkillCorner open data).

## What we decided

### Universe of events
- Press subtypes: `pressure`, `pressing`, `recovery_press`, `counter_press`
- Only while attack phase is `build_up`, `create`, or `direct`
- On this match that is **279** focus presses (of 672 total press-like events)

### Time windows
- Tracking rate: **10 Hz**
- Lane-tax window: **1.0 s** (10 frames) after `frame_start`
- Outcome window: **3.0 s** (30 frames) after `frame_start`

### Lane geometry (for Phase 2 implementation)
- Three carrier-centric corridors: **progressive/inside**, **wide**, **back**
- Progressive/wide length **18 m**, half-width **4 m**
- Back lane length **12 m**
- Sample **5** points along each corridor midline
- Kinematics: reaction **0.2 s**, max accel **4 m/s²**, max speed **7.5 m/s**

### Outcome label (ground-ish truth for validation)
A press is labeled **progressive = 1** only if:
1. Associated possession did **not** end in `possession_loss` or `clearance`, and
2. Carrier/ball advanced ≥ **8 m** in the attacking direction within 3 s

Otherwise **progressive = 0** (forced safe / non-progressive / loss).

This is the label Lane Tax must help predict better than proximity baselines.

### Provisional human-review labels (not the metric)
For the 15-sample review pack only:
- `cut_off` — press closes distance and play does not progress
- `motion_only` — press looks close/closing but play still progresses
- `unclear` — missing geometry

These are heuristics to speed your eyeballing. **Your labels override them.**

## Review pack location

- **Easiest cards (use these):** [`docs/phase1_review/figures_easy/`](phase1_review/figures_easy/)
- Labels summary: [`docs/phase1_review/LABELS.md`](phase1_review/LABELS.md)
- CSV: [`docs/phase1_review/review_sample.csv`](phase1_review/review_sample.csv)

How to read an easy card in 5 seconds:
1. Look at the colored banner (`PRESS WORKED` / `PRESS DIDN'T STOP THEM` / `HARD TO CREDIT THIS PRESS`)
2. Read the 3 numbered sentences
3. Only then glance at BEFORE → AFTER if you want

Older folders `figures/` and `figures_clear/` are obsolete.

## Known limitation to fix in Phase 2
Nearest-defender baseline currently treats all non-carrier players as candidates (teammates included). Phase 2 must use `match.json` home/away rosters so defenders are true opponents.
