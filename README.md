# Nightwatch — conditional launch-viewer quantiles

[![make.fun badge](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank badge](https://make.fun/badge/gta6-twitch-ccu-forecast-01/fahriiri206/makefun-gta6-twitch-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard)
[![reward badge](https://make.fun/badge/gta6-twitch-ccu-forecast-01/fahriiri206/makefun-gta6-twitch-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Forecast entry for [gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01):
five quantiles of Twitch's concurrent viewers in the Grand Theft Auto VI category for
each UTC hour 2–24 of release day, given hour 1 and the supplied comparables.
See also the [leaderboard](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard).

## What it does

`main.py` reads every `*.in` case from `$MAKEFUN_INPUT_DIR` (default `/input`) and writes
one `{"hours":[...]}` file per case to `$MAKEFUN_OUTPUT_DIR` (default `/output`), named after
the input stem. It is standard-library Python only, deterministic, and never touches the
network, the clock, or any data outside the case it is handed.

`model.py` is a conditional analogue forecaster:

1. **Release-day curve per analogue.** For every comparable launch, build the 24 hourly
   counts of its own release UTC day from `hourly[].from`. A comparable without all 24
   hours is skipped, as is the pre-release-only GTA category row (no release day).
2. **Normalise in logs.** Each analogue contributes log ratios `ln(hour_h / hour_1)`.
   The target's known hour-1 print `p1` turns those ratios back into counts.
3. **Weights from pre-checkpoint evidence.** Comparables are weighted by generic
   release-shape classes read from free text (`platforms`, `unlock`) — console vs mixed vs
   PC, early-access contamination, global/simultaneous unlocks — and by structural
   similarity in two pre-release features: `p1` versus the recent pre-launch peak and
   versus the previous hourly point, both in log space.
4. **Weighted empirical quantiles** at levels 0.05/0.25/0.5/0.75/0.95, then a mild
   shrinkage of the 25/75 spread (0.80) and the 5/95 tails (0.90) toward the median.
5. **Minimum support.** When the effective analogue count is below 3, the row blends
   toward the documented random-walk persistence spread, so one analogue cannot collapse
   the forecast to a single brittle curve.
6. **No-self-leak guard.** A comparable whose name and release day match the target is
   excluded, and target-side features use only history strictly before `day_start`.
   Nothing at or after the checkpoint is read, even if a synthetic case contains it.
7. **Fallback.** With no usable comparables, or if a case cannot be parsed at all, the
   program still emits exactly 23 ordered, positive rows using the persistence spread.

Output rows are clamped to `[0.01, 1e9]` and rounded to two decimals, so the contract
(23 rows, five finite positive ordered values each, ≤ 65,536 bytes) always holds.

## Measured evidence

Leave-one-comparable-out cross-validation over the 37 complete comparables in the supplied
kit (each held out in turn, removed from its own pool, scored on its provided historical
curve, hours 2–24, log pinball at the five scored levels):

| model | overall loss | console-only loss | console 90% coverage |
| --- | --- | --- | --- |
| persistence baseline | 0.929644 | 0.322549 | 0.799 |
| Nightwatch (production) | **0.671535** | **0.237385** | 0.973 |
| negative control (target leaked into pool) | 0.540625 | 0.191813 | 0.973 |

The negative control is deliberately leaky and is not a candidate result; it confirms the
no-self-leak guard materially changes the numbers. These are leave-one-comparable-out
figures on the supplied historical curves — **not** an official practice or final score.
The final target's own day is unseen.

## Limits and uncertainty

- Comparables come from a different measurement (SullyGnome hourly averages) than the
  final's minute-read mean; the two are close but not identical.
- Release-day behaviour can break the analogue pool: a title with no close structural
  match still receives the persistence-blended spread, which may be too wide or too
  narrow. The upper tail is the least constrained part of the forecast.
- Unlock and platform text is free-form; the classifier is deliberately coarse and
  generic. It is not a title-to-answer lookup and stores no target counts.
- No claim is made that this entry beats any house model or places in the prize table.

## Runtime

- Entry point: `python3 /bot/main.py` (sandbox uses `python3 -P -s`), read-only `/bot`,
  `/input` and `/output` as above, no network, 8 s per case, 1 CPU, 1024 MB.
- Host run: `mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py`
- Tests: `python3 -m unittest discover -s tests -v`

Data attribution: Twitch directory counts via SullyGnome.com, as supplied in the
competition kit. Public analogue data is not a guarantee of future behaviour.
