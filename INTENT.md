# Intent

## What this is

An educational project about EVO (Evolutionary Value Delivery), the agile method by Tom
Gilb. One central claim:

> AI made code cheap. The parts EVO insisted on, quantified value, measurement and
> resource budgets, are now the expensive parts.

It is also a working bench: tasks mined from real commits, a sandboxed agent, a ledger with
cost, a statistical gate and HTML receipts. The documents explain the method; the code
measures it.

## Who it is for

Engineers and technical leads who are adopting coding agents and suspect that "more
agents, more tokens" is not a delivery strategy.

## Tone

Informal, technical, honest about limits. Fix typos, do not reformat the author's voice.
Plain hyphens only, no em dashes or en dashes.

## State at 2026-11-13

- 67 tasks mined from `pallets/click`, all passing gold and null controls.
- 24 train tasks calibrated to per-task turn budgets of 21 to 62.
- Four campaigns against a live model, 168 billed runs, 1.34 dollars of spend.
- Baseline solves all 24 calibrated train tasks, so the corpus is saturated for capability.
- 157 tests, CI, secret scan, pre-commit hook.

## Next steps

Ordered. Do not skip to the interesting one.

1. **Screen the corpus.** `evo_bench screen`: run the baseline once per task at its own budget
   and label each task `easy` (passes) or `hard` (fails or stops short). This decides whether
   the current corpus can measure anything, in about twenty minutes and thirty cents, instead
   of after another four campaigns.
2. **Filter mining by difficulty.** `mine --min-flips N --min-diff-lines N`: keep commits with
   many flipping tests or large patches, so candidates are hard before paying to screen them.
3. **Split the corpus by role.** `hard` tasks for capability decisions, `easy` tasks as a cheap
   regression gate. Easy tasks are not waste; they are the cheapest way to catch a break.
4. **Re-mine only if step 1 finds fewer than ten hard tasks.** Then the answer is that this
   repository is too easy for this model, and the corpus must come from somewhere harder.
5. **Judge or rubric grading**, so tasks without tests can be measured. This is also the only
   workload that fits batch mode, at half price.

Open questions:

1. Do published harness gains generalize from web apps to brownfield enterprise code?
2. Does better specification measurably reduce agent instruction-following failures?
3. Which metrics survive contact with reality: merged-without-rework, Fix Rate, cost per
   delivered change, or something else? Working answer in `mds/evo-benchmark-evals.md`.
4. How much of the current advantage is model capability versus harness design?
5. What does EVO's "reward results" mean for engineers whose small tasks an agent now
   absorbs?

## Documents

- `mds/evo-sw-devel.md` - EVO as a software development method.
- `mds/evo-in-ai-era.md` - EVO mapped onto AI harnesses, with the benchmark evidence.
- `mds/evo-in-ai-harness.md` - designing a harness with the ten principles.
- `mds/evo-simulation.md` - measuring the harness without fooling yourself.
- `mds/evo-rsi-harness.md` - the self-improving loop and its guardrails.
- `mds/evo-custom-ai-harness.md` - choosing the harness: Tau, JAZ and the Python field.
- `mds/evo-benchmark-evals.md` - instrument quality, contamination, the metrics that survive.
- `README.md` - hackathon deliverables and how to run it.
- `docs/` - static GitHub Pages site, hand-written HTML only.
