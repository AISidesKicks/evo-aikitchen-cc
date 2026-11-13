# EVO

Notes for a blog series on **EVO**, the Evolutionary Value Delivery method built by Tom
Gilb. The goal is to help people understand how EVO actually works, and why a method
from 1960 keeps showing up in conversations about AI coding agents.

The site lives at [evo.aikitchen.cc](https://evo.aikitchen.cc).

## The angle

EVO is a method for delivering small steps of **measurable** stakeholder value under a
budget, and for letting the measurement decide what happens next. Quantified objectives,
Planguage scalars, impact estimation, weekly steps, "done means value delivered".

Most agile teams never do the measurement half. That was tolerable when engineering
hours were scarce and code was expensive. In the AI era it is the opposite: code is
cheap, and verified value, trustworthy context and inference spend are the scarce
resources. The interesting claim of this series is that EVO maps onto coding agents more
cleanly than the sprint rituals we kept.

## Deep dives

| Document | What it covers |
| --- | --- |
| [EVO in software development](mds/evo-sw-devel.md) | The method: origin, the delivery loop, Planguage, impact estimation, the ten principles, comparison with Scrum and XP, limits and a five-day adoption path |
| [EVO in the AI harness era](mds/evo-in-ai-era.md) | The bridge: what the SWE-EVO benchmark measures, how long agents can run, why harnesses matter more than models, an EVO-to-harness mapping, token economics and a working protocol for one agent step |
| [Building a custom AI harness with EVO principles](mds/evo-in-ai-harness.md) | The design guide: harness evidence from 2026, the ten principles as design rules, a reference architecture, component defaults with measured effects, contracts, budgets, routing and a staged build order |
| [Simulating the EVO process for harness development](mds/evo-simulation.md) | The measurement protocol: scenario corpora, simulated stakeholders, step cards, run variance, ablation, fault injection, multi-session shifts, cost campaigns and how to test EVO's own claims |
| [Simulating and building a self-improving EVO harness](mds/evo-rsi-harness.md) | The loop that improves the harness: RHI, branching search and InfraRSI, plus the three audits (the RSI tax, statistical gates, coverage churn), the frozen-evaluator rule, a reference RSI loop, the three clocks, overfitting curves, guardrails and a staged build order |
| [Choosing a custom AI harness: Tau, JAZ and the minimal Python field](mds/evo-custom-ai-harness.md) | The selection guide: why skills and hooks are two of thirteen layers, Tau in depth, JAZ and its published results, five more Python harnesses, coverage matrices, where Tau loses and what beats it, and the operator-shell plus experiment-bench architecture |
| [Benchmarking and evaluating EVO](mds/evo-benchmark-evals.md) | The instrument check: the five distances between a benchmark and your value, benchmark arithmetic and paired designs, contamination and grader validity, the 2026 benchmark landscape, building an internal bench, what survives in production, and the missing experiment that would test EVO itself |

These are research notes, not marketing. Numbers are cited, vendor claims are labeled as
vendor claims, and open questions are collected at the end of each document.

## Repo layout

```
docs/        static GitHub Pages site (hand-written HTML only)
mds/         research and technology overviews, linked from this README
src/         the measurement loop (evo_bench package)
benchmarks/  task corpus and the task card rules
tests/       pytest suite for the bench
scripts/     pixi activation and the bubblewrap sandbox wrapper
runs/        ledger output, gitignored except .gitkeep
scratch/     logs and artifacts, gitignored except .gitkeep
```

`docs/` holds nothing dynamic on purpose. GitHub Pages serves it directly, so there is
no build step, no bundler and no framework in that directory.

## Environment

Python work runs in the isolated pixi workspace `evo1`:

```sh
pixi shell
pixi info | grep Name   # should print evo1
```

The environment provides Python 3.12, `tau-ai` 0.4.11, pytest and the local `evo-bench`
package, installed editable from `src/`.

```sh
pixi run default   # create the local dirs and print the paths
pixi run test      # run the test suite
pixi run bench     # report the corpus inventory and the Tau version
pixi run control   # gold must pass and null must fail, for every task
```

The bench runs the agent on the host, because it needs network access to the model provider,
and routes only tool execution into bubblewrap: read-only runtime, the locked pixi
environment mounted read-only, the workspace read-write, an empty `HOME`, and no network.
`read`, `write` and `edit` refuse any path outside the workspace, and `.env` files inside
the workspace are masked.

```sh
python -m evo_bench run --provider fake --limit 3
python -m evo_bench compare runs/a.jsonl runs/b.jsonl --labels before,after
python -m evo_bench gate runs/a.jsonl runs/b.jsonl --labels before,after
```

The gate is the decision rule from the docs made executable. It refuses to promote on fewer
than 20 paired tasks, demands a significant paired difference, caps the cost increase at 20
percent, and rejects any regression on the holdout split. `--cache runs/cache.jsonl` stores
model responses by request hash, so a campaign can be replayed without paying twice.

`TMPDIR` points at `/tmp`, because pixi writes its own temp files before activation
scripts run, so `TMPDIR` can never point at a directory pixi has to create. `EVO_TMP` is
the private per-project tmpfs directory, created on activation. `SCRATCH` is the
crash-safe scratch directory. Secrets live in `.env`, which is local only and never
committed. `.env.example` holds empty placeholders.

## Status

- [x] Landing page stub and custom domain
- [x] EVO software development overview
- [x] EVO in the AI harness era
- [x] Harness design guide
- [x] Simulation protocol
- [x] Self-improving harness (RSI) guide
- [x] Custom AI harness comparison (Tau and JAZ)
- [x] Benchmarking and evaluation guide
- [x] pixi `default` task that creates the temp and scratch dirs
- [x] Bench scaffold: task cards, ledger, statistics, sandbox wrapper
- [x] Seven-task corpus with gold and null controls
- [x] Sandboxed tool layer with path containment
- [x] Paired comparison with an exact McNemar test
- [x] Promotion gate with a fixed policy
- [x] Response cache for cheap replay
- [ ] Task corpus with 20 real tasks from commits and incidents
- [ ] Landing page content and navigation
- [ ] Optimised logo asset

Project intent and open questions are in [INTENT.md](INTENT.md). Working conventions for
agents and humans are in [AGENTS.md](AGENTS.md).
