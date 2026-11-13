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

Both are research notes, not marketing. Numbers are cited, vendor claims are labeled as
vendor claims, and open questions are collected at the end of each document.

## Repo layout

```
docs/   static GitHub Pages site (hand-written HTML only)
mds/    research and technology overviews, linked from this README
scratch/ logs and artifacts, gitignored except .gitkeep
```

`docs/` holds nothing dynamic on purpose. GitHub Pages serves it directly, so there is
no build step, no bundler and no framework in that directory.

## Environment

Python work runs in the isolated pixi workspace `evo1`:

```sh
pixi shell
pixi info | grep Name   # should print evo1
```

The environment sets `SCRATCH` to `./scratch` and `TMPDIR` to a per-project tmpfs path.
Secrets live in `.env`, which is local only and never committed. `.env.example` holds
empty placeholders.

## Status

- [x] Landing page stub and custom domain
- [x] EVO software development overview
- [x] EVO in the AI harness era
- [ ] Landing page content and navigation
- [ ] Optimised logo asset
- [ ] pixi `default` task that creates `TMPDIR`

Project intent and open questions are in [INTENT.md](INTENT.md). Working conventions for
agents and humans are in [AGENTS.md](AGENTS.md).
