# Phase 2 — the Lane Tax, rebuilt to think like a coach

Results for match 2017461: [`docs/phase2/summary.md`](phase2/summary.md). Run it with `python scripts/phase2_lane_tax.py`.

## The question, restated

A press does two different jobs, and Phase 1 taught us they have to be judged separately:

1. **Did the press as a whole leave the carrier with no way out?** That is a team question. The presser,
   the man screening the pass, the cover behind and the shape of the block all play a part.
2. **How much of that was *this* presser?** That is a credit question. R15 shows why: Auckland won the ball,
   but you said "the diamond just had good positioning". Gallegos running at Inserra was not what shut him in.

The Phase 1 metric (fixed corridors, scored 1 s after the press started) tried to answer both with a single number.
Phase 2 splits them.

## What changed from Phase 1, and why

| Phase 1 | Phase 2 | Football reason |
|---|---|---|
| 3 fixed corridors (inside, wide, back) | A real option for **every teammate**, plus dribbles straight on and at 40° to each side | Carriers pass to people, not to corridors. A lane only exists if somebody is at the end of it. |
| Openness = "is a defender inside the box?" | **Who gets there first** (Spearman pitch control): reaction, top speed, body reach, a leg stuck out | A defender 1.5 m off the line still cuts a ground pass. One 4 m away doesn't. |
| Every pass treated the same | **Lofted balls** (> 25 m) can only be won as they're struck or where they land | A diagonal switch goes over the midfielder in between. |
| Offside ignored | Receivers beyond the second-last defender don't count | A run in behind from an offside position isn't a way out. |
| Read 1 s after the press starts | Read **0.3 s before the ball leaves his foot** (also reported at 1 s and at the peak) | The carrier chooses at the moment he plays it. At 1 s in, R01's presser hadn't arrived yet, and R08 was a first-time ball. |
| Tax = drop in openness over time | Tax = **reality minus the same frame with the presser deleted** | Only the counterfactual says what *he* took. The drop over time mixes in his teammates and the carrier's own movement. |
| — | **Rush** calibrated on SkillCorner xPass | Being closed down hurries the pass even when the lane is open. The data says the effect starts ~1.2 s out: xPass falls from 0.96 to about 0.75 on 25 m+ passes. |
| — | **Carrier momentum**: running the wrong way costs time to stop and turn | R04: the carrier was running at his own goal at 4.4 m/s and can't play forward immediately. |
| — | **Dribble physics**: about 1.5 s for the first 6 m from standing; defenders react in 0.3 s because they're already watching him | In the first build, the 6 m dribble was the "best way out" in 171 of 276 presses. That was too generous to the carrier. |
| — | **Team / unit / credit split** | See the next section. |

## The numbers we now produce for each press

Each option (a pass or dribble) gets:

- **on** = chance that no defender wins it × accuracy (longer passes miss more, and passes miss more when rushed);
- **escape value** = whether it actually gets him out of trouble. Escape options are a progressive gain of at least 5 m (or taking 2+ opponents out), a switch of 25 m+, getting past a presser who is goal-side, or a dribble. The value grows with ground gained, opponents bypassed, a switch, and moving into a more dangerous area.

Back passes and square balls count towards **retention** (can he keep it?) but not towards **escape**.

### Team level: how shut in was he?

| Column | Meaning |
|---|---|
| `escape` | Value of the best way out that is still on. |
| `ways_out` | Chance at least one escape is on, weighting each by its value. Unlike `escape`, cutting two of three lanes moves this. **Headline team number.** |
| `squeeze_total` | Sum of what each nearby defender (within 20 m) takes on his own. |
| `unit_tax` | What the whole pressing chain (SkillCorner `pressing_chain`) takes together. |

### Credit level: how much of it was him?

| Column | Meaning |
|---|---|
| `lane_tax` | Best escape without him minus best escape with him. **Headline presser number.** |
| `lane_tax_block` / `lane_tax_rush` | The part his body takes (standing in lanes, sitting on receivers) vs the part his arrival takes (hurried passes). |
| `ways_tax` | His dent in `ways_out`. |
| `lanes_cut` | Escape value he removes across *every* lane, even ones a teammate also covered. Rewards work that the outcome hides. |
| `credit_share` | His removal tax ÷ the sum of everyone's: his share of the squeeze. `top_squeezer` names whoever did the most. |
| `trap_tax` | His dent in the carrier's best option of *any* kind: pushing him towards losing it. |
| `run_gain` | Tax at release minus tax at the start. Did the run itself take lanes, or was he already standing in the right place? |

## Baselines (what the tax has to beat)

All baselines are oriented so that a higher value means more pressure:

- presser gap;
- nearest opponent;
- opponents within 5 m;
- closing speed;
- presser time-to-carrier;
- SkillCorner pressure band;
- SkillCorner option ease;
- SkillCorner number of passing options;
- SkillCorner number of options ahead.

The last four are SkillCorner's own models, which are tougher opposition than plain distance.

## Labels (how we check it)

No single label is the truth, so there are five:

| Label | Worked = |
|---|---|
| `y_press_success` | Team outcome from the story engine (won, forced long and won, forced out) within ~8 s |
| `y_contained` | The attack did **not** get out under control within 4 s. Escaping means controlled progress of 8 m+ or a completed switch, measured only where an attacker actually has the ball. This fixes the Phase 1 label, which tracked the carrier's movement and could read the wrong team's attacking direction. |
| `y_sc_effect` | SkillCorner says the press forced it back, or reduced or stopped the danger (only 17 positives in this match) |
| `y_forced_error` | The carrier's response was a failed pass, a loss or a clearance |
| `y_regain` | The press team won it back within 5 s |

These labels judge the **team** numbers. The **credit** numbers can't be validated by team outcomes, because a press can be won by the cover (R15) or lost despite a perfect presser. We check credit against the hand review and the lane maps instead.

## What match 2017461 says (in-sample smoke test)

- **The physics is sound.** Our "is this pass on?" ranks SkillCorner's own 2,022 passing options in the same order as their xPass (Spearman **0.72**).
- **Team level works.** `ways_out` separates presses that worked from those that didn't:
  - 0.61 AUC on team outcome, 0.65 on containment and 0.60 on forced errors;
  - it **holds among presses at the same distance** (0.61 / 0.66), where presser gap, nearest opponent and opponents-within-5 m all fall to about 0.5;
  - it beats every proximity baseline;
  - it is tied with SkillCorner's options-ahead count (difference −0.01, interval ±0.08), although the two are only loosely related (Spearman 0.38). Combined they reach 0.69 on containment, and ours clearly wins on forced errors (0.60 vs 0.49).
- **Credit matches the hand review**:
  - R15: credit share 0.02, top squeezer De Vries. The cover did it, not Gallegos.
  - R14 and R05: credit 0.06 and 0.22. "Not a good press" and "could have closed the gaps".
  - R13: 0.00, "barely a press".
  - R01 and R03: May gets 100% of the squeeze, matching a cut-off and a good press.
  - R12: a real tax (0.21), but 0.57 escape is still on. "So many options around him."
- **The individual tax does not predict team outcomes** (about 0.50). That's expected under the split above, and it is the honest version of what Phase 1 called "the presser's verdict vs the team outcome".

## Known limits

- **One match, and tuned on it.** Two changes were made after seeing this match's results: the dribble physics and the switch to read at release. Both have a football rationale, but Phase 3 must judge them on the other 19 matches without further tuning.
- **No body orientation.** Momentum stands in for which way he's facing, and broadcast tracking can't see hips or shoulders.
- **Ball height is unknown.** Lofted vs ground is inferred from pass length alone.
- **Broadcast extrapolation.** Off-camera players get wider timing uncertainty (σ 0.9 s), and receivers who are off camera count for less. R07's presser is off camera.
- **Presses that move from one receiver to the next.** The tax is read on the possession the press is tagged to. R08 was a first-time ball, and the good part of that press happened on the next receiver.
- **The escape-value weights are hand-set** and simple: ground gained, men bypassed, a switch, danger. A learned value model (xT/EPV) would be better, but it is out of scope for v1.

## Phase 3 plan

1. Run all 20 matches with the constants **frozen** as they are now.
2. Primary scores: `ways_out` (team) and `lane_tax` (credit). Primary labels: `y_contained` and `y_forced_error`.
3. Leave-one-match-out, with paired bootstrap AUC against the best baseline. Then check whether `ways_out` adds to SkillCorner options-ahead in a two-feature logistic model fit on 19 matches and tested on the 20th.
4. Collect at least 5 "looks like a press, tax says no" clips per side for the writeup. Candidates from this match are in the summary.
