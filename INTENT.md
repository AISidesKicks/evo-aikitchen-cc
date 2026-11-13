# Intent

## What this is

An educational project about EVO (Evolutionary Value Delivery), the agile method by Tom
Gilb. One central claim:

> AI made code cheap. The parts EVO insisted on, quantified value, measurement and
> resource budgets, are now the expensive parts.

## Who it is for

Engineers and technical leads who are adopting coding agents and suspect that "more
agents, more tokens" is not a delivery strategy.

## Tone

Informal, technical, honest about limits. Fix typos, do not reformat the author's voice.
Plain hyphens only, no em dashes or en dashes.

## Documents

- `mds/evo-sw-devel.md` - EVO as a software development method: the loop, Planguage,
  impact estimation, the ten principles, comparison with Scrum and XP, limits.
- `mds/evo-in-ai-era.md` - EVO mapped onto AI harnesses: SWE-EVO benchmark results,
  METR time horizons, long-running agent research, agent distraction, harness
  engineering, token economics.
- `mds/evo-in-ai-harness.md` - how to design a custom harness using the ten principles:
  evidence, reference architecture, component defaults, contracts, budgets, routing,
  staged build order.
- `mds/evo-simulation.md` - how to simulate the EVO process when developing a harness:
  scenario corpora, simulated stakeholders, measurement design, ablations, fault
  injection, multi-session shifts, and testing EVO's own claims.
- `mds/evo-rsi-harness.md` - how to simulate and build a self-improving harness: prompt
  level RHI, branching search with routing, contract locked infra RSI, the three audits
  (RSI tax, statistical gates, task turnover), the frozen evaluator rule, the three clocks,
  overfitting curves, guardrails, build order.
- `mds/evo-custom-ai-harness.md` - how to choose the harness itself: the thirteen layers
  behind skills and hooks, Tau in depth, JAZ and its StuLife and AppWorld results, five more
  Python harnesses, coverage matrices, where Tau loses, and the operator-shell plus
  experiment-bench architecture.
- `README.md` - short overview linking the deep dives.
- `docs/` - static GitHub Pages site, hand-written HTML only.

## Open questions

1. Do published harness gains generalize from web apps to brownfield enterprise code?
2. Does better specification measurably reduce agent instruction-following failures?
3. Which metrics survive contact with reality: merged-without-rework, Fix Rate, cost per
   delivered change, or something else?
4. How much of the current advantage is model capability versus harness design?
5. What does EVO's "reward results" mean for engineers whose small tasks an agent now
   absorbs?
