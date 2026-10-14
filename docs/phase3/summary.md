# Phase 3 — leave-one-match-out validation

Constants frozen from Phase 2. No further tuning.

- Matches: **20**
- Focus presses scored: **7474** (excluded `not_a_press`)
- Scoring errors logged: 0

## How to read this

**AUC** = pick one press that worked and one that didn't; how often the score ranks the good one higher.
**0.50 = coin flip.** Leave-one-match-out = compute that on each match separately, then average
(so one weird game can't carry the result).

### Headline scores

- **Ways out left** — team squeeze. Should predict containment / forced errors.
- **Lane Tax** — presser credit. Should *not* need to predict team outcomes; checked via examples.

## Leave-one-match-out mean AUC

### attack did NOT escape under control within 4 s

| score | mean AUC | std across matches |
|---|---|---|
| Ways out left (fewer = higher) | 0.687 | 0.043 |
| Best way out left (fewer = higher) | 0.670 | 0.043 |
| SkillCorner fewer options ahead | 0.634 | 0.040 |
| Nearest opponent | 0.583 | 0.038 |
| Opponents within 5 m | 0.575 | 0.043 |
| Presser time-to-carrier | 0.574 | 0.032 |
| Presser gap | 0.573 | 0.033 |
| SkillCorner pressure | 0.559 | 0.042 |
| Ways-out tax (presser) | 0.552 | 0.032 |
| Total squeeze near ball | 0.532 | 0.043 |
| SkillCorner option ease | 0.530 | 0.046 |
| Pressing-chain tax | 0.513 | 0.041 |
| Lane Tax (presser credit) | 0.503 | 0.033 |
| SkillCorner fewer options | 0.479 | 0.039 |
| Closing speed | 0.430 | 0.028 |

### carrier's response was a failed pass / loss / clearance

| score | mean AUC | std across matches |
|---|---|---|
| SkillCorner option ease | 0.671 | 0.039 |
| SkillCorner pressure | 0.661 | 0.044 |
| Nearest opponent | 0.644 | 0.055 |
| Opponents within 5 m | 0.616 | 0.047 |
| Presser gap | 0.605 | 0.045 |
| Best way out left (fewer = higher) | 0.594 | 0.051 |
| Ways out left (fewer = higher) | 0.583 | 0.045 |
| Presser time-to-carrier | 0.564 | 0.038 |
| Total squeeze near ball | 0.549 | 0.044 |
| SkillCorner fewer options | 0.488 | 0.055 |
| Ways-out tax (presser) | 0.481 | 0.044 |
| Closing speed | 0.480 | 0.044 |
| Lane Tax (presser credit) | 0.479 | 0.046 |
| Pressing-chain tax | 0.459 | 0.049 |
| SkillCorner fewer options ahead | 0.450 | 0.055 |

### team outcome good (~8 s story)

| score | mean AUC | std across matches |
|---|---|---|
| Ways out left (fewer = higher) | 0.573 | 0.046 |
| Best way out left (fewer = higher) | 0.566 | 0.047 |
| SkillCorner fewer options ahead | 0.547 | 0.039 |
| Opponents within 5 m | 0.530 | 0.054 |
| Nearest opponent | 0.529 | 0.054 |
| Presser time-to-carrier | 0.528 | 0.037 |
| SkillCorner pressure | 0.527 | 0.041 |
| Presser gap | 0.526 | 0.043 |
| Pressing-chain tax | 0.526 | 0.041 |
| Ways-out tax (presser) | 0.520 | 0.037 |
| SkillCorner option ease | 0.519 | 0.036 |
| Total squeeze near ball | 0.512 | 0.035 |
| SkillCorner fewer options | 0.509 | 0.039 |
| Lane Tax (presser credit) | 0.504 | 0.033 |
| Closing speed | 0.496 | 0.032 |

### press team won it back within 5 s

| score | mean AUC | std across matches |
|---|---|---|
| SkillCorner option ease | 0.616 | 0.049 |
| SkillCorner pressure | 0.606 | 0.049 |
| Closing speed | 0.554 | 0.049 |
| Nearest opponent | 0.547 | 0.053 |
| Opponents within 5 m | 0.544 | 0.051 |
| Best way out left (fewer = higher) | 0.544 | 0.053 |
| Presser gap | 0.537 | 0.055 |
| Ways out left (fewer = higher) | 0.533 | 0.053 |
| Total squeeze near ball | 0.530 | 0.054 |
| Presser time-to-carrier | 0.522 | 0.046 |
| SkillCorner fewer options | 0.520 | 0.057 |
| Ways-out tax (presser) | 0.497 | 0.046 |
| Lane Tax (presser credit) | 0.495 | 0.048 |
| Pressing-chain tax | 0.470 | 0.041 |
| SkillCorner fewer options ahead | 0.453 | 0.057 |

## Ways out vs best proximity baseline (pooled, paired bootstrap)

| label | score | vs | auc_gain | ci_lo | ci_hi |
|---|---|---|---|---|---|
| y_contained | Ways out left (fewer = higher) | Nearest opponent | 0.108 | 0.094 | 0.121 |
| y_contained | Lane Tax (presser credit) | Nearest opponent | -0.072 | -0.092 | -0.052 |
| y_contained | Ways out left (fewer = higher) | SkillCorner fewer options ahead | 0.051 | 0.037 | 0.067 |
| y_forced_error | Ways out left (fewer = higher) | Nearest opponent | -0.060 | -0.074 | -0.046 |
| y_forced_error | Lane Tax (presser credit) | Nearest opponent | -0.174 | -0.198 | -0.152 |
| y_forced_error | Ways out left (fewer = higher) | SkillCorner fewer options ahead | 0.138 | 0.120 | 0.156 |
| y_press_success | Ways out left (fewer = higher) | Presser time-to-carrier | 0.046 | 0.031 | 0.061 |
| y_press_success | Lane Tax (presser credit) | Presser time-to-carrier | -0.020 | -0.036 | -0.002 |
| y_press_success | Ways out left (fewer = higher) | SkillCorner fewer options ahead | 0.023 | 0.007 | 0.037 |
| y_regain | Ways out left (fewer = higher) | Closing speed | -0.015 | -0.043 | 0.013 |
| y_regain | Lane Tax (presser credit) | Closing speed | -0.061 | -0.082 | -0.041 |
| y_regain | Ways out left (fewer = higher) | SkillCorner fewer options ahead | 0.084 | 0.065 | 0.103 |

## Does ways out add to SkillCorner options-ahead?

Logistic regression fit on 19 matches, tested on the held-out match.
Features are rank-percentiles so units don't matter.

| model | mean_auc | std_auc | n_matches |
|---|---|---|---|
| Logistic: ways out + SC options-ahead | 0.630 | 0.052 | 40 |
| SC options-ahead alone (rank) | 0.578 | 0.062 | 40 |
| Ways out alone (rank) | 0.616 | 0.059 | 40 |

Per held-out match:

| match_id | n | auc | label | model |
|---|---|---|---|---|
| 1874553 | 392 | 0.645 | y_contained | rank_ways |
| 1886347 | 468 | 0.627 | y_contained | rank_ways |
| 1899585 | 352 | 0.520 | y_contained | rank_ways |
| 1925299 | 330 | 0.716 | y_contained | rank_ways |
| 1927964 | 430 | 0.625 | y_contained | rank_ways |
| 1953632 | 448 | 0.674 | y_contained | rank_ways |
| 1959846 | 354 | 0.630 | y_contained | rank_ways |
| 1986691 | 335 | 0.695 | y_contained | rank_ways |
| 1996435 | 482 | 0.661 | y_contained | rank_ways |
| 1996436 | 281 | 0.652 | y_contained | rank_ways |
| 2006229 | 469 | 0.702 | y_contained | rank_ways |
| 2006363 | 389 | 0.694 | y_contained | rank_ways |
| 2007448 | 347 | 0.732 | y_contained | rank_ways |
| 2007721 | 321 | 0.680 | y_contained | rank_ways |
| 2010085 | 348 | 0.657 | y_contained | rank_ways |
| 2011166 | 296 | 0.626 | y_contained | rank_ways |
| 2013725 | 393 | 0.638 | y_contained | rank_ways |
| 2015213 | 431 | 0.632 | y_contained | rank_ways |
| 2016236 | 331 | 0.660 | y_contained | rank_ways |
| 2017461 | 276 | 0.577 | y_contained | rank_ways |
| 1874553 | 392 | 0.588 | y_contained | rank_sc |
| 1886347 | 468 | 0.590 | y_contained | rank_sc |
| 1899585 | 352 | 0.560 | y_contained | rank_sc |
| 1925299 | 330 | 0.653 | y_contained | rank_sc |
| 1927964 | 430 | 0.585 | y_contained | rank_sc |
| 1953632 | 448 | 0.662 | y_contained | rank_sc |
| 1959846 | 354 | 0.588 | y_contained | rank_sc |
| 1986691 | 335 | 0.614 | y_contained | rank_sc |
| 1996435 | 482 | 0.655 | y_contained | rank_sc |
| 1996436 | 281 | 0.565 | y_contained | rank_sc |
| 2006229 | 469 | 0.675 | y_contained | rank_sc |
| 2006363 | 389 | 0.601 | y_contained | rank_sc |
| 2007448 | 347 | 0.645 | y_contained | rank_sc |
| 2007721 | 321 | 0.654 | y_contained | rank_sc |
| 2010085 | 348 | 0.662 | y_contained | rank_sc |
| 2011166 | 296 | 0.571 | y_contained | rank_sc |
| 2013725 | 393 | 0.609 | y_contained | rank_sc |
| 2015213 | 431 | 0.565 | y_contained | rank_sc |
| 2016236 | 331 | 0.639 | y_contained | rank_sc |
| 2017461 | 276 | 0.615 | y_contained | rank_sc |
| 1874553 | 392 | 0.645 | y_contained | logistic_both |
| 1886347 | 468 | 0.635 | y_contained | logistic_both |
| 1899585 | 352 | 0.549 | y_contained | logistic_both |
| 1925299 | 330 | 0.739 | y_contained | logistic_both |
| 1927964 | 430 | 0.616 | y_contained | logistic_both |
| 1953632 | 448 | 0.693 | y_contained | logistic_both |
| 1959846 | 354 | 0.625 | y_contained | logistic_both |
| 1986691 | 335 | 0.693 | y_contained | logistic_both |
| 1996435 | 482 | 0.687 | y_contained | logistic_both |
| 1996436 | 281 | 0.645 | y_contained | logistic_both |
| 2006229 | 469 | 0.714 | y_contained | logistic_both |
| 2006363 | 389 | 0.686 | y_contained | logistic_both |
| 2007448 | 347 | 0.732 | y_contained | logistic_both |
| 2007721 | 321 | 0.692 | y_contained | logistic_both |
| 2010085 | 348 | 0.664 | y_contained | logistic_both |
| 2011166 | 296 | 0.629 | y_contained | logistic_both |
| 2013725 | 393 | 0.638 | y_contained | logistic_both |
| 2015213 | 431 | 0.625 | y_contained | logistic_both |
| 2016236 | 331 | 0.681 | y_contained | logistic_both |
| 2017461 | 276 | 0.609 | y_contained | logistic_both |
| 1874553 | 392 | 0.602 | y_forced_error | rank_ways |
| 1886347 | 468 | 0.576 | y_forced_error | rank_ways |
| 1899585 | 353 | 0.617 | y_forced_error | rank_ways |
| 1925299 | 330 | 0.596 | y_forced_error | rank_ways |
| 1927964 | 430 | 0.594 | y_forced_error | rank_ways |
| 1953632 | 448 | 0.533 | y_forced_error | rank_ways |
| 1959846 | 354 | 0.545 | y_forced_error | rank_ways |
| 1986691 | 335 | 0.618 | y_forced_error | rank_ways |
| 1996435 | 482 | 0.565 | y_forced_error | rank_ways |
| 1996436 | 281 | 0.590 | y_forced_error | rank_ways |
| 2006229 | 469 | 0.553 | y_forced_error | rank_ways |
| 2006363 | 389 | 0.623 | y_forced_error | rank_ways |
| 2007448 | 347 | 0.494 | y_forced_error | rank_ways |
| 2007721 | 321 | 0.596 | y_forced_error | rank_ways |
| 2010085 | 348 | 0.474 | y_forced_error | rank_ways |
| 2011166 | 296 | 0.647 | y_forced_error | rank_ways |
| 2013725 | 393 | 0.645 | y_forced_error | rank_ways |
| 2015213 | 431 | 0.543 | y_forced_error | rank_ways |
| 2016236 | 331 | 0.561 | y_forced_error | rank_ways |
| 2017461 | 276 | 0.625 | y_forced_error | rank_ways |
| 1874553 | 392 | 0.482 | y_forced_error | rank_sc |
| 1886347 | 468 | 0.512 | y_forced_error | rank_sc |
| 1899585 | 353 | 0.481 | y_forced_error | rank_sc |
| 1925299 | 330 | 0.576 | y_forced_error | rank_sc |
| 1927964 | 430 | 0.496 | y_forced_error | rank_sc |
| 1953632 | 448 | 0.596 | y_forced_error | rank_sc |
| 1959846 | 354 | 0.549 | y_forced_error | rank_sc |
| 1986691 | 335 | 0.584 | y_forced_error | rank_sc |
| 1996435 | 482 | 0.467 | y_forced_error | rank_sc |
| 1996436 | 281 | 0.542 | y_forced_error | rank_sc |
| 2006229 | 469 | 0.531 | y_forced_error | rank_sc |
| 2006363 | 389 | 0.503 | y_forced_error | rank_sc |
| 2007448 | 347 | 0.695 | y_forced_error | rank_sc |
| 2007721 | 321 | 0.551 | y_forced_error | rank_sc |
| 2010085 | 348 | 0.628 | y_forced_error | rank_sc |
| 2011166 | 296 | 0.461 | y_forced_error | rank_sc |
| 2013725 | 393 | 0.548 | y_forced_error | rank_sc |
| 2015213 | 431 | 0.519 | y_forced_error | rank_sc |
| 2016236 | 331 | 0.619 | y_forced_error | rank_sc |
| 2017461 | 276 | 0.501 | y_forced_error | rank_sc |
| 1874553 | 392 | 0.579 | y_forced_error | logistic_both |
| 1886347 | 468 | 0.575 | y_forced_error | logistic_both |
| 1899585 | 353 | 0.614 | y_forced_error | logistic_both |
| 1925299 | 330 | 0.649 | y_forced_error | logistic_both |
| 1927964 | 430 | 0.584 | y_forced_error | logistic_both |
| 1953632 | 448 | 0.580 | y_forced_error | logistic_both |
| 1959846 | 354 | 0.560 | y_forced_error | logistic_both |
| 1986691 | 335 | 0.680 | y_forced_error | logistic_both |
| 1996435 | 482 | 0.550 | y_forced_error | logistic_both |
| 1996436 | 281 | 0.607 | y_forced_error | logistic_both |
| 2006229 | 469 | 0.590 | y_forced_error | logistic_both |
| 2006363 | 389 | 0.607 | y_forced_error | logistic_both |
| 2007448 | 347 | 0.593 | y_forced_error | logistic_both |
| 2007721 | 321 | 0.652 | y_forced_error | logistic_both |
| 2010085 | 348 | 0.552 | y_forced_error | logistic_both |
| 2011166 | 296 | 0.590 | y_forced_error | logistic_both |
| 2013725 | 393 | 0.627 | y_forced_error | logistic_both |
| 2015213 | 431 | 0.537 | y_forced_error | logistic_both |
| 2016236 | 331 | 0.645 | y_forced_error | logistic_both |
| 2017461 | 276 | 0.614 | y_forced_error | logistic_both |

## Per-match AUC: ways out → contained

| match_id | n | positives | auc |
|---|---|---|---|
| 1874553 | 392 | 273 | 0.702 |
| 1886347 | 468 | 297 | 0.657 |
| 1899585 | 353 | 260 | 0.562 |
| 1925299 | 330 | 226 | 0.732 |
| 1927964 | 430 | 324 | 0.660 |
| 1953632 | 448 | 362 | 0.704 |
| 1959846 | 354 | 256 | 0.664 |
| 1986691 | 335 | 247 | 0.715 |
| 1996435 | 482 | 317 | 0.687 |
| 1996436 | 281 | 198 | 0.663 |
| 2006229 | 469 | 357 | 0.727 |
| 2006363 | 389 | 242 | 0.723 |
| 2007448 | 347 | 260 | 0.744 |
| 2007721 | 321 | 243 | 0.725 |
| 2010085 | 348 | 258 | 0.751 |
| 2011166 | 296 | 200 | 0.649 |
| 2013725 | 393 | 292 | 0.673 |
| 2015213 | 431 | 317 | 0.671 |
| 2016236 | 331 | 247 | 0.669 |
| 2017461 | 276 | 192 | 0.651 |

## 'Looks like a press, tax says no' (324 across all matches)

Presser within 2.5 m, bottom-quartile Lane Tax.

| kind | match_id | clock | presser | press_team | carrier | press_type | outcome | lane_tax | credit_share | ways_out | escape | b_presser_gap | y_contained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| looks_like_press_tax_says_no | 1874553 | 7' (H1) | Waddingham | BRR | Alagich | chase_from_behind | forced_back | 0.016 | 0.057 | 0.226 | 0.216 | -2.198 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 8' (H1) | Alagich | ADE | Jelacic | chase_from_behind | played_through | 0.006 | 0.158 | 0.002 | 0.001 | -1.684 | 0.000 |
| looks_like_press_tax_says_no | 1874553 | 8' (H1) | Kitto | ADE | Jelacic | front_on | played_through | 0.027 | 0.686 | 0.002 | 0.001 | -1.850 | 0.000 |
| looks_like_press_tax_says_no | 1874553 | 8' (H1) | Ayoubi | ADE | Jelacic | chase_from_behind | won_by_presser | 0.002 | 0.056 | 0.002 | 0.001 | -1.565 | 0.000 |
| looks_like_press_tax_says_no | 1874553 | 19' (H1) | Mauk | ADE | Halloran | chase_from_behind | won_fast | 0.030 | 0.101 | 0.044 | 0.023 | -1.404 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 20' (H1) | Jovanovic | ADE | Caletti | chase_from_behind | contained | 0.040 | 0.102 | 0.175 | 0.152 | -2.266 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 31' (H1) | Waddingham | BRR | Clough | chase_from_behind | forced_back | 0.054 | 0.185 | 0.060 | 0.042 | -2.461 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 31' (H1) | Bility | BRR | Alagich | front_on | won_fast | 0.001 | 0.020 | 0.000 | 0.000 | -0.649 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 31' (H1) | Caletti | BRR | Alagich | chase_from_behind | won_by_presser | 0.000 | 0.004 | 0.000 | 0.000 | -1.874 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 31' (H1) | Ayoubi | ADE | O'Shea | chase_from_behind | contained | 0.057 | 0.151 | 0.256 | 0.254 | -2.435 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 47' (H2) | Burke-Gilroy | BRR | Folami | front_on | played_through | 0.040 | 0.258 | 0.197 | 0.143 | -1.335 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 47' (H2) | Jelacic | BRR | Folami | chase_from_behind | forced_out | 0.027 | 0.174 | 0.197 | 0.143 | -1.948 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 63' (H2) | Goodwin | ADE | Walid Shour | chase_from_behind | played_through | 0.048 | 0.222 | 0.408 | 0.396 | -2.274 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 68' (H2) | O'Shea | BRR | Goodwin | chase_from_behind | contained | 0.000 | 0.016 | 0.001 | 0.001 | -1.657 | 1.000 |
| looks_like_press_tax_says_no | 1874553 | 68' (H2) | Walid Shour | BRR | Clough | chase_from_behind | played_through | 0.016 | 0.041 | 0.039 | 0.032 | -1.507 | 0.000 |

## 'Quiet press' (435 across all matches)

Presser 5 m+ away, top-quartile Lane Tax.

| kind | match_id | clock | presser | press_team | carrier | press_type | outcome | lane_tax | credit_share | ways_out | escape | b_presser_gap | y_contained |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| quiet_press_tax_says_yes | 1874553 | 4' (H1) | Jelacic | BRR | Kitto | front_on | played_through | 0.560 | 0.999 | 0.511 | 0.330 | -6.373 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 6' (H1) | Waddingham | BRR | Delianov | front_on | played_through | 0.658 | 1.000 | 0.454 | 0.182 | -9.349 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 9' (H1) | Clough | ADE | Brown | front_on | forced_back | 0.364 | 0.590 | 0.463 | 0.351 | -6.301 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 11' (H1) | Jelacic | BRR | Kitto | front_on | played_through | 0.392 | 0.971 | 0.549 | 0.480 | -5.202 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 18' (H1) | Jelacic | BRR | Kitto | front_on | forced_back | 0.671 | 0.378 | 0.095 | 0.058 | -5.984 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 19' (H1) | Jelacic | BRR | Kikianis | front_on | won_fast | 0.704 | 0.650 | 0.561 | 0.331 | -6.779 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 19' (H1) | Clough | ADE | Brown | front_on | played_through | 0.430 | 1.000 | 0.675 | 0.570 | -7.353 | 0.000 |
| quiet_press_tax_says_yes | 1874553 | 29' (H1) | Barnett | ADE | Walid Shour | front_on | forced_back | 0.313 | 0.389 | 0.154 | 0.072 | -6.523 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 31' (H1) | Clough | ADE | Brown | front_on | played_through | 0.510 | 0.709 | 0.579 | 0.255 | -6.139 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 34' (H1) | Halloran | BRR | Mauk | front_on | forced_back | 0.499 | 0.892 | 0.199 | 0.166 | -5.326 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 34' (H1) | O'Shea | BRR | Vriends | front_on | played_through | 0.428 | 1.000 | 0.146 | 0.077 | -5.750 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 36' (H1) | O'Shea | BRR | Kitto | front_on | contained | 0.415 | 0.963 | 0.803 | 0.588 | -6.598 | 0.000 |
| quiet_press_tax_says_yes | 1874553 | 46' (H1) | Burke-Gilroy | BRR | Ayoubi | front_on | forced_out | 0.733 | 0.973 | 0.114 | 0.047 | -5.654 | 1.000 |
| quiet_press_tax_says_yes | 1874553 | 49' (H2) | Halloran | BRR | Vriends | front_on | played_through | 0.546 | 0.491 | 0.569 | 0.289 | -5.100 | 0.000 |
| quiet_press_tax_says_yes | 1874553 | 51' (H2) | Brown | BRR | Pierias | front_on | played_through | 0.853 | 0.807 | 0.079 | 0.102 | -6.110 | 1.000 |

## Verdict

**Team squeeze works on held-out matches.**

- **Ways out left** mean AUC on “did not escape”: **0.687** across 20 matches.
  - Beats presser gap (**0.573**) and nearest opponent (**0.583**).
  - Beats SkillCorner’s fewer-options-ahead (**0.634**); pooled gain **+0.05** (CI 0.04–0.07).
- Combining ways-out + SC options-ahead in a logistic fit on 19 matches and testing on the 20th
  averages about **0.63**, a small lift over ways-out alone (~0.62) and a clear lift over SC alone (~0.58).
- **Lane Tax** stays near **0.50** on team outcomes — as designed. Credit is for “whose positioning,”
  not “did the team win the ball.” There are hundreds of “close but tax says no” and “far but tax says yes” examples.

**Where it is weaker:** predicting failed passes / regains, SkillCorner’s pressure / option-ease bands still win.
Those are “how hurried is he?” questions more than “are the lanes shut?”

See `auc_lomo.csv` / `logistic_lomo.csv` / `disagreements.csv` for the full numbers.
