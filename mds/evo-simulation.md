# Simulating the EVO process for harness development

You cannot improve a harness with vibes. The harness is a system that makes decisions
under uncertainty, and the only honest way to improve it is to put it in front of work
you understand, measure what it does, and change one thing at a time.

That is simulation, in the engineering sense: a controlled replica of the delivery process
that is cheap enough to run often, repeatable enough to compare, and realistic enough to
transfer.

This page is the practical protocol. It covers what to simulate, how to build the scenario
corpus, how to score it, how to run ablations without fooling yourself, and how to move
from simulation to production without a rude surprise.

EVO provides the structure: quantified objectives, small steps, estimates before
measurements, and a decision at every boundary. Simulation provides the compression of
time that makes the loop fast enough to matter.

## Contents

- [Why simulate at all](#why-simulate-at-all)
- [Two things called simulation](#two-things-called-simulation)
- [The model of the loop](#the-model-of-the-loop)
- [Four simulation layers](#four-simulation-layers)
- [Building the scenario corpus](#building-the-scenario-corpus)
- [Simulating a stakeholder](#simulating-a-stakeholder)
- [Running one simulated EVO step](#running-one-simulated-evo-step)
- [Measurement design](#measurement-design)
- [Ablation and component attribution](#ablation-and-component-attribution)
- [Simulating failure and recovery](#simulating-failure-and-recovery)
- [Simulating multi-session work](#simulating-multi-session-work)
- [Simulating cost and budget](#simulating-cost-and-budget)
- [Testing EVO itself](#testing-evo-itself)
- [From simulation to production](#from-simulation-to-production)
- [Anti-patterns](#anti-patterns)
- [A 30-day plan](#a-30-day-plan)
- [Worked example](#worked-example)
- [References](#references)

## Why simulate at all

Direct experimentation on real projects is slow, expensive and confounded:

- A real task takes days. You get a handful of observations per quarter.
- Every real task is different, so you cannot compare two harness variants on the same
  work.
- Failure is costly, so teams avoid the risky experiments that produce the most
  information.
- The customer changes the requirement midway, which is realistic but ruins attribution.

Simulation fixes all four. It compresses time, holds the work constant, makes failure
cheap, and gives you a counterfactual. This is EVO's E2, do the high-risk step early, and
E10, learn fast, applied to the harness itself.

There is also a budget argument. The harness-effect study (arXiv 2609.32459) ran 10 models
across 3 benchmarks with over 10 billion Qwen prompt tokens and over 20 billion DeepSeek
prompt tokens, at an estimated cost above 7,000 USD, and still had to sample benchmarks to
keep it affordable. Your budget is smaller. Simulation design is how you get a useful
answer anyway: fewer scenarios, more runs on the ones that discriminate, and a stopping
rule.

## Two things called simulation

Keep them separate, because they answer different questions.

**1. Simulating the work.** You replay historical changes, synthesized specs or benchmark
tasks through the harness. This tests the harness: does it resolve the task, at what cost,
with what failure modes.

**2. Simulating the method.** You compare ways of running the work: quantified objectives
versus vague stories, value-ranked scheduling versus FIFO, step contracts versus one-shot
prompts. This tests EVO itself: does the discipline change outcomes.

The first is engineering. The second is the research question of this whole site, and it
is directly testable. Most teams do neither, and then argue about prompt styles.

## The model of the loop

Write the simulation down as a game with explicit parts. If you cannot name the parts, the
results will not be interpretable.

| Part | In the simulation | In production |
| --- | --- | --- |
| Stakeholder | Scenario author, release notes, rubric | Product owner, customer, support |
| Value request | Task contract with objective and acceptance check | Ticket, spec, requirement |
| Product | Repository at a pinned commit plus tests | The real system |
| Team | Harness plus model plus tools | Harness plus model plus humans |
| Budget | Tokens, steps, minutes, dollars | Same, plus salaries |
| Meter | Eval script, tests, rubric | Tests, monitoring, stakeholder metrics |
| Step | One task, or one release delta | One increment of delivered value |
| Learning | Report, ablation, harness change | Retrospective with numbers |

Two properties to preserve:

- **The same meter across variants.** If variant A is scored by tests and variant B by a
  judge, you are comparing meters, not harnesses.
- **The same tasks across variants.** Paired comparison on identical scenarios is far more
  sensitive than comparing averages over different samples.

## Four simulation layers

Not every question needs the full apparatus. Pick the cheapest layer that can answer it.

| Layer | What it is | Cost per run | Fidelity | Cadence |
| --- | --- | --- | --- | --- |
| L1 unit | Tool tests, parser tests, prompt snapshots, permission checks | Cents | Low | Every commit |
| L2 scenario | One full task, start to verified patch, with trace | Dollars | Medium | Every change |
| L3 suite | Many tasks, several runs each, statistical report | Hundreds of dollars | Medium-high | Weekly, and per model change |
| L4 campaign | A sequence of steps simulating a project over days, with rework and changing requirements | Thousands | High | Monthly or per major version |

Use L1 for regressions and safety. Use L2 while developing a component. Use L3 to decide
whether a component stays. Use L4 to test the things that only appear over time:
continuity, drift, compounding rework, cost accumulation.

A common mistake is to jump to L3 or L4 because it feels rigorous, spend the quarter's
budget, and learn nothing because the scenarios were never validated. Start at L2.

## Building the scenario corpus

### Sources, best to worst

1. **Your own history.** Take a merged change from your repository, check out the parent
   commit, and use the real requirement text plus the real tests as the acceptance check.
   This is exactly how SWE-EVO is built from release notes and version tags. It has the
   best realism-to-effort ratio, and it is private, which avoids contamination.
2. **Your incidents.** Postmortems contain a requirement, a failure, and a verification.
   Convert one into a scenario per quarter.
3. **Public benchmarks.** SWE-bench Pro, ProgramBench, GitTaskBench and friends. Useful for
   comparability, risky for contamination, and often far from your stack.
4. **Synthesized scenarios.** Written by a person or generated from a spec. Cheap, but
   tends to test what the author imagined rather than what happens.
5. **Mutation.** Inject a bug mechanically, keep the tests. Good for robustness, weak for
   requirement interpretation.

### Stratification

Do not build a corpus of 50 similar tasks. Stratify by what changes harness behavior:

| Dimension | Levels |
| --- | --- |
| Task type | Bug fix, small feature, refactor, new module, migration, repository generation |
| Scope | One file, several files, cross-module, cross-service |
| Spec quality | Crisp scalar, normal ticket, vague request, contradictory request |
| Risk | Local change, data migration, security relevant, performance relevant |
| Starter state | Clean repo, dirty repo, failing tests, stale docs |
| Model tier | Small, mid, frontier |

A workable starter corpus is 3 tasks per task type, 18 total, with at least two spec
qualities and two scope levels. That is enough to see a 5-point effect, not enough to see
a 1-point effect. Be honest about which one you have.

### Scenario card

Every scenario is a versioned artifact. If it is not in git, it does not exist.

```yaml
id: refund-one-click-014
source: internal-history        # internal-history | benchmark | synthetic | mutation
repo: acme/billing
base_commit: 9f3c2a1
requirement: |
  Support agents must be able to refund a captured card payment from the order page
  in one click. The refund must equal the captured amount, and the order state must
  change to refunded within 5 seconds. Every refund must produce an audit entry.
acceptance:
  command: pnpm test:e2e -- refund.spec.ts
  regression: pnpm test:unit
difficulty: medium
tags: [feature, multi-file, audit, money]
budget: { tokens: 800000, minutes: 60, usd: 4.00 }
baseline:                       # filled by the first measurement, not by hope
  resolved: null
  fix_rate: null
  cost_usd: null
  review_minutes: null
```

Two fields do most of the work. `base_commit` makes the scenario reproducible. `acceptance`
makes success mechanical. Without both, you have an anecdote in YAML.

### Contamination and holdout

Keep a holdout set that is never used for tuning, only for reporting. Refresh scenarios
periodically, because prompts, model versions and your own harness will overfit to a fixed
set. If a scenario's solution is likely in the model's training data, flag it. Public
benchmarks are not exempt from this, especially the older ones.

A simple discipline: 70 percent development set, 30 percent holdout, and a rule that a
holdout result is reported once per harness version.

## Simulating a stakeholder

Value needs a source. In simulation, you manufacture one.

**Historical replay.** The release note is the requirement, the tests are the acceptance,
and the diff is the ground truth. This is the most defensible option and it is free.

**Planguage scalars as requirements.** Convert a ticket into a scalar with a scale and a
meter, then run two variants: one with the scalar, one with the original narrative. If the
scalar version reduces instruction-following failures, you have measured EVO's core claim
in your own environment. That experiment is the subject of a later section.

**Perturbation.** Take a solved task and change one constraint: make the latency target
tighter, add a backward compatibility requirement, remove a permitted dependency. This
tests whether the harness notices constraints at all, which is where long specs fail.

**Adversarial ambiguity.** Write a requirement that is genuinely underspecified and see
whether the harness asks, assumes, or invents. All three are informative. Track which one
it chose, because that is a policy question, not a model question.

What you cannot simulate well: taste, politics, and the stakeholder who changes their mind
because of a meeting. That is what L4 and production shadowing are for.

## Running one simulated EVO step

Map the EVO loop onto the harness experiment directly.

| EVO step | Harness simulation |
| --- | --- |
| Define the objective | Pick the harness objective: resolved rate, cost, rework, recovery |
| Establish the baseline | Run the current harness on the suite |
| Generate candidate steps | List harness variants: add tool registry, add subagent, enable compression |
| Estimate impact | Predict the effect and the cost, and write both down |
| Choose by value per cost | Rank variants, pick one or two |
| Deliver the step | Implement the variant behind a flag |
| Measure | Run the same scenarios, same runs, same model, temperature 0 |
| Update the model | Keep, revert, or combine, with the numbers as the reason |

The estimate is not ceremony. Writing "I expect +4 points and +15 percent cost" before the
run and comparing afterwards is how a team learns to forecast. It also prevents the most
common failure: reading a result and inventing the hypothesis afterwards.

### A step card

```yaml
step: 07
objective: TaskSuccess
hypothesis: >
  Adding four structured file tools will reduce unparseable edits and raise resolved
  rate on multi-file tasks by 3 to 6 points, at roughly 10 percent more tool calls.
variant: tools-only
estimate:
  resolved_delta_pp: [3, 6]
  cost_delta_pct: 10
  review_delta_minutes: 0
runs: 5
scenarios: dev-set-v3
model: pinned-snapshot-2026-10-01
decision: null
measurement: null
```

### The impact table for harness variants

| Variant | Value (estimated pp) | Tokens (M) | Review (h) | $ | Value per cost | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| tools-only | +4 | 3.8 | 0 | 12 | 0.33 | test first |
| tools plus task subagents | +7 | 6.1 | 0 | 21 | 0.33 | test second |
| plus planning | +8 | 7.0 | 0 | 24 | 0.33 | marginal |
| plus compression | +7 | 3.2 | 0 | 11 | 0.64 | cost play |
| full | +8 | 9.5 | 0 | 33 | 0.24 | only if others fail |

The numbers are illustrative, but the structure is the point. Compression looks
attractive on cost until you remember the quality hit measured in the component study,
where it lost 4 to 5 points while saving 54 to 77 percent of prompt tokens. A table with
both columns makes that trade visible.

## Measurement design

### Metrics

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Resolved rate | Share of scenarios whose acceptance check passes and regression check passes | Primary value metric |
| Fix rate | Share of failing tests fixed, zeroed by any regression | Partial credit, less noisy on big suites |
| Patch apply rate | Share of patches that apply cleanly | Harness mechanical quality |
| Regression rate | Share of runs breaking a previously passing test | Quality guard |
| Steps | Agent steps per scenario | Effort, not value |
| Tool calls | Tool invocations per scenario | Exploration behavior |
| Prompt tokens | Input tokens per scenario | Cost driver |
| Response tokens | Output tokens per scenario | Cost driver |
| Cost per resolved task | Total spend divided by resolved count | The number the business cares about |
| Wall clock | Minutes per scenario | Latency and human attention |
| Review minutes | Human minutes per merged change | Hidden cost |
| Rework rate | Share of merges needing a fix within 14 days | The honesty metric |
| Failure distribution | Share of failures by taxonomy class | Tells you what to fix next |
| Probing distribution | Probes before implementation | Excessive or insufficient exploration |
| Clean exit rate | Share of runs ending in a building, clean repo | Production readiness |

Report distributions, not just means. A harness that is excellent on 80 percent of tasks
and catastrophically bad on 20 percent is a different product from one that is mediocre
everywhere, even at the same average.

### Runs and variance

Model sampling makes single runs meaningless for small effects. Practical defaults:

- **3 runs per scenario** for development decisions.
- **5 to 6 runs per scenario** for a publishable comparison. METR uses six.
- **Temperature 0** reduces but does not eliminate variance, so still repeat.
- **Report intervals, not points.** A 3-point difference with overlapping intervals is not
  a result.
- **Use paired comparisons.** Same scenario, same run count, two variants. Compare per
  scenario and then aggregate.

A rough heuristic for a binary outcome: with 20 paired scenarios, you can detect a
difference of about 15 to 20 percentage points reliably. Smaller effects need more
scenarios, more runs, or a softer metric like Fix Rate. Do not claim a 2-point win on 12
tasks. That is noise with a chart.

### Contamination checks

- Does the model produce the exact ground-truth patch when prompted with the requirement
  and no repository?
- Is the scenario's solution likely present in public training data?
- Does performance drop when you rename identifiers and reorder files?
- Does the model succeed on the test command without reading the code?

If any of these is suspicious, mark the scenario and weight it down. Contamination
inflates resolved rates and, worse, changes which harness looks best.

## Ablation and component attribution

This is where the harness-effect study is most instructive. Its method:

1. Start from a minimal harness.
2. Add one component at a time.
3. Measure individually.
4. Measure all together.
5. Compare behavior, not just score.

Two results to remember:

- Individual effects were heterogeneous: tools +4.57, task subagents +5.91, compression
  -4.86 on one model, with different magnitudes on another.
- The combined gain (+7.37) was less than the sum of the positive individual gains, and
  the negative components did not simply subtract. Interaction effects are real.

So do not sum your way to a design. Measure the combination.

### An ablation table you can actually fill in

| Variant | Resolved | Fix rate | Cost/task | Steps | Probes | Failure top class |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 42.9 | 51.0 | 2.10 | 104 | 22 | incorrect implementation |
| + tools | 47.5 | 55.2 | 2.35 | 106 | 26 | incorrect implementation |
| + task subagents | 48.8 | 57.9 | 3.05 | 141 | 31 | instruction following |
| + planning | 43.6 | 52.1 | 2.60 | 102 | 21 | incorrect implementation |
| + compression | 38.0 | 45.4 | 1.05 | 62 | 14 | missing requirement |
| + all | 50.3 | 60.1 | 3.30 | 134 | 33 | instruction following |

Read the failure column carefully. A component that raises the score but shifts failures
to instruction following is telling you the next bottleneck is specification, not tooling.
That is the kind of finding that changes a roadmap, and it only appears if you report the
taxonomy.

### The load-bearing test

When a new model lands, remove components one at a time and measure. Anthropic did exactly
this when Opus 4.6 arrived: the sprint construct became unnecessary, and the per-sprint
evaluator could become a single end-of-run pass. Their conclusion is worth quoting in
spirit: every harness component encodes an assumption about what the model cannot do, and
those assumptions go stale.

A practical rule: after each model upgrade, re-run the suite with the full harness, then
with each component disabled. Components whose removal does not hurt are deleted or gated
by model tier.

## Simulating failure and recovery

Happy paths are the easy half. The harness earns its keep when things break.

### Fault injection catalogue

| Fault | Injection | What to measure |
| --- | --- | --- |
| Broken build on entry | Break a type or import in the base commit | Does the agent detect and fix it before new work? |
| Flaky test | Add a test that fails 30 percent of the time | Does it retry forever, or classify flakiness? |
| Missing dependency | Remove a package from the environment | Recovery time, whether it installs silently |
| Network failure | Disable network mid-run | Graceful degradation versus crash loop |
| Context overflow | Force a long trace | Compression behavior, requirement retention |
| Malformed patch | Truncate a diff | Apply failure handling |
| Tool timeout | Slow a command past the limit | Retry policy, budget accounting |
| Stale TODO | Add a TODO referencing a closed ticket | Distraction rate, scope adherence |
| Poisoned docs | Add an outdated `AGENTS.md` claim | Does it follow the lie or verify? |
| Reward hack bait | Make a test trivially passable | Does it weaken or delete the test? |

The last two are the most valuable and the least common. Google found that about 13 percent
of agent sessions encountered stale TODO references, and in 6 percent of those the agent
acted on them, costing 70 percent more steps, 77 percent more tokens and 105 percent more
wait time. You can reproduce that in an afternoon by planting a stale comment.

### Recovery metrics

- Percent of faults recovered without human intervention.
- Cost to recover, in tokens and minutes.
- Percent of runs that end in a clean state after a fault.
- Percent of recovery attempts that make things worse, such as reverting unrelated work.

The last one is the important one. An agent that recovers by deleting the failing test has
not recovered.

## Simulating multi-session work

Long-horizon behavior is not the sum of single-session behavior. This is where L4 earns
its cost.

### The shift protocol

Simulate the Anthropic setup:

1. **Session 1** starts from a task and produces code plus artifacts.
2. **Reset the context completely.** Nothing carries over except the repository, the
   progress file, the task list and git.
3. **Session 2** must resume, using only the artifacts.

Measure:

| Metric | Question |
| --- | --- |
| Continuity | Did session 2 start the right work without re-exploring? |
| Rediscovery cost | Tool calls spent reconstructing known state |
| Duplicate work | Lines or tests produced twice |
| Artifact sufficiency | Did the progress file answer the three questions? |
| Drift | Did the objective silently change between sessions? |
| Cumulative cost | Total spend across the project, not per session |
| Value per step | Movement on the objective per step |

Anthropic's research suggests two failure shapes: a session that tries to do everything at
once and leaves a half-implemented feature, and a later session that sees progress and
declares victory. Both are measurable in the shift protocol.

### A project-shaped campaign

A campaign is a sequence of 5 to 10 steps drawn from one repository's history, run in
order, with the harness producing a change at each step. This lets you observe compounding:
technical debt created by step 3 slowing step 6, cost drift as context grows, quality decay
as the repository gets messier.

It also lets you test EVO's central claim in simulation: does choosing steps by value per
cost beat following the historical order? That is a real experiment with a real answer.

## Simulating cost and budget

Cost is a first-class metric, not an afterthought.

### The cost model

```
cost = prompt_tokens * input_price
     + response_tokens * output_price
     + cached_tokens * cache_price
     + infra_minutes * infra_rate
     + review_minutes * loaded_hourly_rate
```

Add failure cost: a resolved task that later needs rework is not resolved at the original
price.

### Sizing a campaign

| Campaign | Scenarios | Variants | Runs | Est. calls | Est. cost |
| --- | --- | --- | --- | --- | --- |
| Smoke | 5 | 1 | 1 | 5 | 10 to 30 USD |
| Component test | 20 | 2 | 3 | 120 | 200 to 600 USD |
| Ablation | 20 | 6 | 3 | 360 | 600 to 1800 USD |
| Release gate | 40 | 2 | 5 | 400 | 800 to 2500 USD |

The ranges are wide because token prices and task sizes vary. The point is to budget the
campaign before running it, and to have a stopping rule.

### Spending rules

1. **Smoke first.** One variant, five scenarios, one run. If the harness cannot complete a
   task at all, do not run the suite.
2. **Sequential testing.** Run a few scenarios, inspect traces, and stop early if the
   harness is obviously broken. Do not burn the budget to discover a missing dependency.
3. **Cache and replay.** Deterministic tool outputs and cached model responses make
   reruns cheaper, when the cache is honest about invalidation.
4. **Cap subagents.** Delegation is where budgets leak.
5. **Record actuals against estimates.** The forecast error is a metric, like any other.

## Testing EVO itself

This is the part most method writing avoids: does the discipline change outcomes, or does
it just feel more rigorous?

You can test it, because EVO makes specific, falsifiable claims.

### Experiment 1: quantified requirements versus narratives

- **Variants:** task described as a normal ticket, versus a Planguage scalar with Must,
  Plan and a meter, and an explicit acceptance check.
- **Scenarios:** 20 tasks with long, nuanced requirements. Long is important: that is where
  SWE-EVO found instruction-following failures dominate.
- **Metric:** resolved rate, plus failure taxonomy share of instruction following.

**Hypothesis from the evidence:** the scalar version reduces instruction-following failures
and raises resolved rate on large suites. If it does not, EVO's requirement discipline is
not paying for itself in your context, and you should know that.

### Experiment 2: value-ranked scheduling versus FIFO

- **Variants:** steps ordered by an impact table, versus ordered by ticket age.
- **Scenarios:** a campaign with 8 steps and a fixed total budget, so ordering matters.
- **Metric:** weighted objective movement per dollar at the end of the campaign.

**Hypothesis:** value ranking wins on the weighted objective, especially when one cheap
high-value step exists. If the two are equal, your backlog was already well ordered.

### Experiment 3: estimate before, measure after

- **Variants:** harness runs where the agent must state an expected impact and a
  verification plan before editing, versus editing immediately.
- **Metric:** resolved rate, cost, and the calibration of stated expectations.

**Hypothesis:** forcing an explicit prediction improves verification behavior, because the
agent has something to check against. This is the mechanism behind Anthropic's step
contracts, and it is testable rather than assumed.

### Experiment 4: small steps versus one-shot

- **Variants:** one task per session with a clean handoff, versus one long session.
- **Scenarios:** a project-shaped campaign of 6 deltas.
- **Metric:** cumulative resolved value, cumulative cost, and clean-exit rate.

**Hypothesis:** small steps win on long projects because context resets and artifacts
reduce drift. The evidence is suggestive, not settled, which is exactly why it is worth
measuring in your environment.

A note on rigor: these are not controlled clinical trials. They are controlled engineering
experiments, with a fixed scenario set, a fixed model snapshot, and a pre-registered
hypothesis. That is enough to make a decision, and far more than most teams have.

## From simulation to production

Simulation results do not transfer automatically. Close the loop deliberately.

1. **Shadow mode.** Run the harness on real tickets without merging. Compare the simulated
   score with human judgment, and record disagreements. Google's TODO-cleaner project used
   human acceptance as its real meter, achieving over 95 percent acceptance.
2. **Canary.** Let the harness merge a small share of low-risk changes, with human review
   still on. Measure rework and review minutes.
3. **Drift detection.** Compare simulated resolved rate with production merge rate monthly.
   A widening gap means the corpus no longer represents the work.
4. **Recalibrate the corpus.** Add scenarios from recent production failures. Retire
   scenarios that no model fails anymore, or keep them as regression guards.
5. **Version the harness.** Every prompt, tool spec and config change gets a version. A
   score without a version is not a measurement.
6. **Report the cost of learning.** Failed variants are a cost of the method, not waste.
   Put them in the decision log so the next person does not repeat them.

The 70 percent merged-without-rework figure reported by Stripe is a useful production
benchmark for this transition, but treat it as a vendor claim. Your own number is the one
that matters.

## Anti-patterns

| Anti-pattern | Symptom | Fix |
| --- | --- | --- |
| Single-run conclusions | "It felt better" | 3 to 6 runs, paired comparison |
| Tiny n | Winning by 2 points on 10 tasks | Power calculation or softer metric |
| Single model | Harness tuned to one snapshot | Test at least two model tiers |
| Cherry-picked scenarios | Great score, bad production | Stratified corpus, holdout set |
| Proxy optimization | Fewer steps, less delivered | Track value and cost together |
| No holdout | Everything improves, nothing transfers | 70/30 split, holdout reported once |
| Judge collusion | Evaluator approves everything | Separate context, skeptical prompt, calibration |
| Unversioned prompts | Scores move for no reason | Version prompts and configs with results |
| Contamination | Suspiciously high resolved rate | Paraphrase test, rename identifiers |
| Ignoring cost | Quality up, bill up | Cost per resolved task is a primary metric |
| Summing ablations | Design by addition | Measure the combination |
| Simulator drift | Simulated and real diverge | Shadow mode, recalibration |

## A 30-day plan

A realistic first month for one engineer, part time.

**Week 1: corpus and meters**

- Day 1: pick 5 historical changes from your repo. Write scenario cards.
- Day 2: script the acceptance check and the regression check. Prove they fail on the
  parent commit and pass on the merged commit.
- Day 3: add 5 more scenarios across two task types.
- Day 4: build the scoring script. Output resolved, fix rate, cost, steps, failure class.
- Day 5: baseline run, 3 runs each. Write the numbers down. Expect embarrassment.

**Week 2: one component**

- Day 6: pick one component with evidence behind it, usually structured tools.
- Day 7: implement behind a flag.
- Day 8: run the paired comparison. 15 scenarios, 3 runs, both variants.
- Day 9: read ten traces, not just the score. Classify failures.
- Day 10: decide keep or revert, and write the decision down with the estimate versus the
  result.

**Week 3: one more component and fault injection**

- Day 11: second component, for example task-specific subagents or planning.
- Day 12: paired run.
- Day 13: plant three faults: broken build, stale TODO, flaky test.
- Day 14: measure recovery. Read the traces.
- Day 15: write the failure taxonomy into the report.

**Week 4: multi-session and the decision memo**

- Day 16: build a 4-step campaign from one repository's history.
- Day 17: run the shift protocol with context resets.
- Day 18: compare one-session versus shift-protocol variants.
- Day 19: write the decision memo: what stayed, what was removed, what to test next.
- Day 20: update the harness version and the eval report template.

The output of the month is not a better harness. It is a better **instrument**. The harness
improves as a consequence.

## Worked example

A team wants to know whether a separate evaluator is worth its cost. They run an L3 suite.

**Setup**

- 20 scenarios from the last two quarters: 8 features, 7 bugs, 5 refactors.
- Two variants: generator only, and generator plus evaluator with a 5-criterion rubric.
- 4 runs per scenario, same model snapshot, temperature 0.
- Budget: 2.2M tokens per run, 45 minutes, 3 USD.

**Estimates, written before the run**

| Variant | Resolved | Cost per task | Review minutes | Hypothesis |
| --- | --- | --- | --- | --- |
| generator only | 55 percent | 1.80 USD | 22 | Baseline |
| plus evaluator | 63 percent | 2.60 USD | 14 | Catches stubbed features, saves review |

**Results**

| Variant | Resolved | Fix rate | Cost/task | Review minutes | Rework rate |
| --- | --- | --- | --- | --- | --- |
| generator only | 52 percent | 61 percent | 1.75 USD | 24 | 18 percent |
| plus evaluator | 61 percent | 72 percent | 2.55 USD | 13 | 9 percent |

**Reading**

- Resolved rate up 9 points. Fix rate up 11 points, so the gain is not just luck on whole
  tasks.
- Review minutes halved. At a loaded rate of 60 USD per hour, that saves about 11 USD per
  task, which more than covers the 0.80 USD inference increase.
- Rework rate halved. That is the number that matters in production.

**Decision**

The evaluator stays, gated to tasks the generator finds hard. For trivial tasks it is
disabled, which recovers some cost. The team writes the decision down with the estimate
error: they predicted +8 points and got +9, predicted +0.80 USD and got +0.80. That
calibration is the real asset.

**Next step, chosen by value per cost**

The failure taxonomy shows instruction-following is now the top class, at 41 percent of
remaining failures. So the next experiment is the quantified-requirement test from the
previous section, not another harness component. The simulation told them where the
bottleneck moved.

## Checklist

- [ ] Scenario cards are versioned, with base commit and acceptance command.
- [ ] The acceptance check fails before the change and passes after.
- [ ] The corpus is stratified, and there is a holdout set.
- [ ] The same model snapshot is used across variants.
- [ ] At least 3 runs per scenario, 5 or more for a decision you will publish.
- [ ] Estimates are written before the run.
- [ ] Results report cost, review time and failure taxonomy, not just score.
- [ ] The holdout is reported once per harness version.
- [ ] Components are added one at a time, and combinations are measured.
- [ ] Faults are injected, not just happy paths.
- [ ] Multi-session behavior is tested with real context resets.
- [ ] Every harness change has a version and a decision log entry.
- [ ] Simulation results are checked against production shadow mode.
- [ ] The corpus is refreshed from real failures.

## References

Harness measurement:

- Haichuan Hu et al., "Beyond the Model: Demystifying Harness Effects in Software
  Engineering Agents", arXiv 2609.32459, September 2026.
  https://arxiv.org/html/2609.32459v1
- François Zaninotto, "The State Of AI Harness Engineering 2026", Marmelab, September
  2026.
  https://marmelab.com/blog/2026/09/24/the-state-of-ai-harness-engineering-2026.html
- Birgitta Böckeler, "Harness engineering for coding agent users", April 2026.
  https://martinfowler.com/articles/harness-engineering.html
- Google, "The anatomy of harness engineering".
  https://developers.googleblog.com/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/

Benchmarks and evaluation design:

- Thai et al., "SWE-EVO: Benchmarking Coding Agents in Long-Horizon Software Evolution
  Scenarios", arXiv 2512.18470, December 2025. Includes the Fix Rate metric.
  https://arxiv.org/html/2512.18470v1
- ProgramBench, "Can language models rebuild programs from scratch?", arXiv 2605.03546.
- SWE-bench Pro, arXiv 2509.16941.
- GitTaskBench, AAAI 2026.
- METR, "Task-Completion Time Horizons of Frontier AI Models", for run counts and
  caveats.
  https://metr.org/time-horizons/

Long-running and multi-session behavior:

- Anthropic, "Effective harnesses for long-running agents", November 2025.
  https://www.anthropic.com/research/effective-harnesses-for-long-running-agents
- Prithvi Rajasekaran, "Harness design for long-running application development",
  Anthropic, March 2026.
  https://www.anthropic.com/research/harness-design-long-running-apps

Method:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process", InfoQ, 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- [EVO in software development](evo-sw-devel.md)
- [EVO in the AI harness era](evo-in-ai-era.md)
- [Building a custom AI harness with EVO principles](evo-in-ai-harness.md)
- [Simulating and building a self-improving EVO harness](evo-rsi-harness.md) for the next
  layer: a harness that revises itself under a frozen evaluator.
