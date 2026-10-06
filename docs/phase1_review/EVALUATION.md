# Evaluating a press (and what the GIFs show)

A press is **not** only "defender got close."

## The four beats that matter

1. **Close quality** — Did this presser actually shrink useful options, or stay too far?
2. **Forced action** — Pass, clearance, foul, shot, or turnover on that touch?
3. **Ball destination** — After the ball leaves, does it go forward, back to safety, or into trouble?
4. **Aftermath** — Does the attacking team keep the ball, or does the pressing team regain / force a phase loss?

If you only watch the close, you miss presses that look busy but gift a free progressive pass — and you over-credit far-away defenders when a turnover happens for other reasons.

## How to read the new GIFs

Each clip runs ~5 seconds after press start so you can see the pass land.

| On screen | Meaning |
|---|---|
| Top 4 lines | The four beats for this event |
| `PRESS ON BALL` | Still deciding with the first carrier |
| `AFTER PASS — TRACK THE BALL` | Ball has left; follow the yellow ball + black trail |
| `GOT BALL` | Someone collected the pass |
| `TURNOVER — OTHER TEAM HAS THE BALL` | Possession flipped during the clip |
| Camera pan | Follows the ball after the pass so destination stays in view |

## Labels we use

- **PRESS WORKED (`cut_off`)** — closed hard AND attack broke down / went backwards / turned over in a way that fits the close
- **PRESS DIDN'T STOP THEM (`motion_only`)** — attack still progressed after the ball moved on
- **HARD TO CREDIT / TURNOVER UNCLEAR (`unclear`)** — bad outcome for the attack, but this presser may not deserve credit

Regenerate:

```bash
python scripts/make_press_gifs.py
```
