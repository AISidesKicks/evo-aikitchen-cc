# Building a custom AI harness with EVO principles

This is the design guide for the third layer of the stack. The model is rented, the
repository is inherited, and the harness is the part you actually own. It decides what
the model sees, what it can do, when it stops, and how anyone knows whether the work was
worth doing.

EVO is a good fit for that job because a harness is not one decision, it is a portfolio
of small decisions, each with a cost and each with a testable claim. That is exactly the
shape EVO was built for: quantify the objective, estimate the step, deliver it, measure,
keep or revert.

Read [EVO in the AI harness era](evo-in-ai-era.md) for the evidence base, and
[EVO in software development](evo-sw-devel.md) for the method itself.

## Contents

- [What a harness is](#what-a-harness-is)
- [The evidence that harness design is a first-class variable](#the-evidence-that-harness-design-is-a-first-class-variable)
- [The harness is the product](#the-harness-is-the-product)
- [The ten principles as harness requirements](#the-ten-principles-as-harness-requirements)
- [Reference architecture](#reference-architecture)
- [The component portfolio](#the-component-portfolio)
- [Contracts: the artifacts that carry intent](#contracts-the-artifacts-that-carry-intent)
- [Budgets and model routing](#budgets-and-model-routing)
- [Verification: the meter layer](#verification-the-meter-layer)
- [Safety as a Must-level constraint](#safety-as-a-must-level-constraint)
- [Failure modes the harness must handle](#failure-modes-the-harness-must-handle)
- [Build order](#build-order)
- [What not to build](#what-not-to-build)
- [Checklist](#checklist)
- [References](#references)

## What a harness is

The shortest useful definition, from LangChain's anatomy post:

> Agent = Model + Harness. If you are not the model, you are the harness.

Concretely, a harness includes:

- System prompts and instruction files.
- Tools, skills, MCP servers, and their descriptions.
- The execution environment: filesystem, sandbox, browser, language runtimes.
- Orchestration: the agent loop, subagent spawning, handoffs, model routing.
- Hooks and middleware: compaction, continuation, lint gates, permission checks.
- State: progress files, git history, memory, task queues.
- Observability: traces, token accounting, cost attribution.
- Evaluation: how a run is scored, and who scores it.

The 2026 survey literature decomposes harnesses into about a dozen modules. Five of them
carry most of the behavioral weight:

| Module | Question it answers |
| --- | --- |
| Tools | What can the model observe and change? |
| Context and memory | What stays in the window, what gets evicted, what persists? |
| Planning | How does the agent decompose and track work? |
| Subagents | What gets delegated, and with what context? |
| Skills | Which procedures are loaded, and when? |

The other modules (environment, permissions, logging, observability, knowledge sources,
evaluation) are engineering support. They rarely produce a headline performance gain, and
their absence produces spectacular failures. That asymmetry matters for prioritization.

## The evidence that harness design is a first-class variable

Three findings from 2025 and 2026 set the design budget.

### Harness choice rivals model choice

The study *Beyond the Model: Demystifying Harness Effects in Software Engineering Agents*
(arXiv 2609.32459, September 2026) measured this directly. On SWE-bench Verified
leaderboard data with the model held fixed, the gap between the best and worst harness
reaches **19.4 percentage points**. The gap between Claude model generations under a
fixed harness is **22.8 points**. Harness engineering is roughly the same order of
leverage as upgrading the model, which is a strange thing to ignore.

The same paper cites Epoch AI's estimate that a well-designed harness is worth roughly a
20 percent performance improvement.

### The gains are not additive, and not always positive

The authors built **NanoHarness**, a deliberately small modular harness on top of
mini-SWE-agent, and ablated five components on ProgramBench:

| Component | Qwen3.7-Max | DeepSeek-V4-Pro | Reading |
| --- | --- | --- | --- |
| Tool registry | +4.57 pp | +3.54 pp | Stable gain |
| Task-specific subagents | +5.91 pp | +4.46 pp | Stable gain |
| Explicit planning | small | small | Cheap, weak |
| Lazy skills | small | larger | Model-dependent |
| Context compression | -4.86 pp | -3.85 pp | Hurt spec-heavy work |
| General subagents | negative | negative | Overhead without alignment |

Combining everything gave +7.37 pp and +6.21 pp, better than any single component but
**less than the sum of the positive ones**. Components interact. Some cancel out. This is
the empirical case against "add more scaffolding" as a strategy.

It is also the empirical case for EVO: every component is a hypothesis, and hypotheses
need a meter.

### Harness value depends on model capability and task type

On SWE-style issue repair, complex harnesses mostly help weaker models. The gain of
OpenHands over mini-SWE-agent dropped from +13.60 pp on Claude 3.7 Sonnet to +5.47 pp on
Claude 4 Sonnet. For the Qwen family on SWE-bench Pro, the OpenCode advantage narrowed
from about 6 points to 2.67 points as models improved.

On newer, more open-ended repository tasks (ProgramBench, GitTaskBench), the pattern
inverts: only the strongest models can exploit a complex harness, and for them it acts as
a capability amplifier.

Two design rules follow:

1. **A harness is a bet on a model generation.** Re-test it when the model changes,
   because some scaffolding stops being load-bearing.
2. **A harness is a bet on a task distribution.** A harness tuned for issue repair is not
   automatically good at repository generation, and vice versa.

## The harness is the product

EVO's core move is to treat the thing you are building as an object with measurable
objectives. So do that for the harness.

A starting top ten for a coding harness, with plausible scales:

| Tag | Scale | Meter | Must | Plan |
| --- | --- | --- | --- | --- |
| `TaskSuccess` | percent of scenario tasks resolved | eval suite, N runs per task | 55 | 70 |
| `CostPerSuccess` | USD per resolved task | token accounting plus infra | 4.00 | 2.00 |
| `ReviewMinutes` | human minutes per merged change | review timestamps | 30 | 15 |
| `ReworkRate` | percent of merges fixed within 14 days | git and issue links | 20 | 10 |
| `RepoClean` | percent of runs ending in a clean, building state | post-run check | 95 | 100 |
| `RegressionRate` | percent of runs breaking a previously passing test | eval suite | 5 | 1 |
| `TimeToFirstValue` | minutes from task start to first verified result | trace timestamps | 45 | 20 |
| `ContextEfficiency` | prompt tokens per verified step | trace accounting | 250k | 120k |
| `RecoveryRate` | percent of injected faults recovered without human help | fault-injection suite | 60 | 85 |
| `SafetyViolations` | count of blocked or forbidden actions attempted | policy log | 0 | 0 |

Notice the shape: outcome first, cost second, behavior third. And note `SafetyViolations`
has Must = 0, which means no amount of success compensates for a violation. That is the
same structure as the SWE-EVO Fix Rate metric, where breaking a regression test scores
the whole instance zero.

Two practical warnings:

- **Do not put step count or token count in the value column.** They are costs. Optimizing
  them directly produces agents that stop early and do less, which is exactly the failure
  mode the next section describes.
- **Pick fewer than ten.** Five is enough for a first version. A harness with ten
  objectives and no baseline is a harness with none.

## The ten principles as harness requirements

This is the core of the guide. Each principle becomes a design rule, a mechanism, a
meter, and an anti-pattern.

### E1: decompose by performance results and stakeholders

**Design rule.** The unit of work is a vertical slice with an observable result, not a
layer of implementation and not a bag of file edits.

**Mechanism.** A task contract with an explicit acceptance check: a command, a test, a
query or a browser assertion that returns pass or fail. The agent is told what "done"
looks like before it starts, and the harness refuses to mark the task complete without
running the check.

**Meter.** Percent of tasks whose acceptance check the harness ran itself, versus percent
asserted by the model in prose. The second number should trend to zero.

**Anti-pattern.** "Implement authentication" as a task. There is no slice, no result, and
no way to fail fast.

### E2: do high-risk steps early

**Design rule.** The harness should have a cheap spike mode whose only job is to answer a
question, and the scheduler should run the riskiest assumption first.

**Mechanism.** A `spike` task type with a hard budget, no merge requirement, and a
mandatory written answer: what was tested, what happened, what it means. Also: order the
scenario suite so the scariest integration runs first in CI.

**Meter.** Time from project start to the first falsified assumption. Lower is better.
Track how many spikes ended in "does not work" and whether the project changed course.

**Anti-pattern.** Building the happy path for two weeks and discovering in integration
that the sandbox cannot run the browser.

### E3: improve the most valuable objectives first

**Design rule.** Prioritize by value per cost, recomputed at every step. The backlog is a
menu.

**Mechanism.** A scheduler that accepts `value` (expected gap closure on a named
objective), `cost` (tokens, review time, risk) and computes a ratio. Allow tasks to be
reordered or dropped when measurements arrive.

**Meter.** Value delivered per unit of spend, per week. Plus a count of stale items that
survived more than three steps without a value estimate, which should be zero.

**Anti-pattern.** A FIFO queue of tickets where the top item is easy to describe and
worth almost nothing.

### E4: evolve the existing system

**Design rule.** Default to the real repository, the real tests and the real constraints.
Greenfield sandboxes are for spikes only.

**Mechanism.** Repository discovery tools (glob, grep, symbol lookup), a working test
command, and a rule that a task is not done until it applies cleanly to the mainline in a
throwaway branch.

**Meter.** Merge rate of agent work into the mainline, and the share of tasks that
required a rewrite because the agent built against an imaginary system.

**Anti-pattern.** The demo branch that diverges for three weeks and never lands.

### E5: design to cost dynamically

**Design rule.** Every run has a budget in tokens, steps, wall-clock time, tool calls and
money. The harness stops at the budget and returns a partial result with a status, rather
than looping until it accidentally succeeds.

**Mechanism.** A budget manager with hard and soft limits, per-task and per-subagent
accounting, and a `cost_exceeded` terminal state that is a normal outcome, not an error.

**Meter.** Actual cost per resolved task, and the share of runs that hit the budget
without a result. That share is your estimate quality, measured.

**Anti-pattern.** "Let it run until it works." You are not paying for compute, you are
paying for retries with no information gain.

### E6: design to performance dynamically

**Design rule.** Verification measures the attributes you care about, not just whether
tests are green. Green tests on a slower, flakier system is not value.

**Mechanism.** The meter layer: deterministic checks, behavioral checks, and rubric-based
checks, in that order of preference. Quality attributes (latency, error rate, bundle
size, dependency count, complexity delta) recorded per run.

**Meter.** Number of objectives with a meter implemented, out of the top ten.

**Anti-pattern.** A judge model that only reads the diff and says "looks good". It will
say that, reliably, even when the feature is stubbed.

### E7: invest in an open-ended architecture

**Design rule.** Both the product and the harness must be cheap to change. The harness
itself should be a set of pluggable components that can be toggled for ablations.

**Mechanism.** Component interfaces with a registry, configuration-driven enablement,
versioned prompts, and a repository that a fresh agent can navigate in about ten tool
calls: one-command tests, current docs, no stale TODOs.

**Meter.** Hours to swap a component, and agent navigation cost on a cold start. Google's
agent distraction data is the benchmark here: stale TODO references caused 70 percent more
steps and 77 percent more tokens when they derailed a session.

**Anti-pattern.** A monolithic 4,000-line prompt with conditionals for every customer,
where nobody can tell which paragraph is load-bearing.

### E8: reward results, not effort

**Design rule.** The dashboard reports merged-without-rework, value movement, and cost per
delivered change. It does not report lines of code, agent steps, or PR count.

**Mechanism.** Attribution from run to merge to outcome. A rework window (14 days) that
counts follow-up fixes as a cost of the original change.

**Meter.** Merged-without-rework percentage, change failure rate, rework rate.

**Anti-pattern.** A leaderboard of "agent PRs per week". It rewards volume and punishes
quality, and the model has no way to know the difference.

### E9: prioritize by value, not queue position

**Design rule.** Abandonment is a feature. A task that is 80 percent done and no longer
the best value per cost should be cancelled, and the harness must make cancellation cheap.

**Mechanism.** Checkpointed state, resumable tasks, and a scheduler that can preempt. The
specification and progress artifacts live in the repo, so cancellation loses work time but
not knowledge.

**Meter.** Wasted spend on cancelled work, and the number of cancelled tasks that were
never resumed. Some waste is healthy.

**Anti-pattern.** A long-running agent that must be allowed to finish because restarting
would cost more, which is sunk-cost reasoning with an API bill.

### E10: learn fast, change fast

**Design rule.** The harness should be easy to instrument, easy to replay, and easy to
change. Every failure is a trace to read, not a mystery.

**Mechanism.** Structured traces with tool calls, observations and decisions; deterministic
replay where possible; a component ablation switch; a failure taxonomy in the eval report.

**Meter.** Median time from failure observation to a merged harness fix. Also the share of
failures with a classified failure mode.

**Anti-pattern.** Anecdotal tuning: one engineer watches one bad run, changes a prompt, and
declares victory without a rerun of the suite.

## Reference architecture

A compact harness that satisfies the principles above. It is deliberately boring.

```
            +-----------------------------------------------+
            |  task contract (value, acceptance, budget)     |
            +-----------------------+-----------------------+
                                    |
                        +-----------v-----------+
                        |  context builder      |  repo map, docs, AGENTS.md,
                        |  (E1, E4, E7)         |  prior progress, relevant files
                        +-----------+-----------+
                                    |
                        +-----------v-----------+
                        |  planner / router     |  step selection, model choice,
                        |  (E2, E3, E5, E9)     |  budget allocation
                        +-----------+-----------+
                                    |
              +---------------------v----------------------+
              |            agent loop (executor)          |
              |  think -> tool call -> observe -> repeat   |
              +----+--------------+-------------+----------+
                   |              |             |
        +----------v---+  +-------v------+  +---v-----------+
        | tool layer   |  | memory /     |  | budget &      |
        | registry     |  | artifacts    |  | policy guard  |
        | (E6, E7)     |  | (E1, E10)    |  | (E5)          |
        +----------+---+  +-------+------+  +-------+-------+
                   |              |                 |
        +----------v--------------v-----------------v-------+
        |              verifier and evaluator               |
        |   tests, build, behavior probes, rubric, judge     |
        |                    (E6, E8)                        |
        +---------------------------+------------------------+
                                    |
                        +-----------v-----------+
                        |  trace, meter, report |  cost, value, failure taxonomy
                        |  (E8, E10)            |
                        +-----------------------+
```

Module responsibilities, mapped to the evidence:

| Module | Must do | Must not do |
| --- | --- | --- |
| Contract | Carry the objective, acceptance check and budget | Contain implementation instructions |
| Context builder | Assemble the smallest sufficient context | Dump the whole repo |
| Planner | Pick the next step and the model | Write a 40-step plan and follow it blindly |
| Executor | Run one step, call tools, observe | Retry the same failing action forever |
| Tool layer | Give bounded, structured operations | Expose unbounded shell as the only tool |
| Memory | Persist progress and decisions | Persist raw tool output forever |
| Budget guard | Stop at limits, return status | Silently continue |
| Verifier | Produce pass or fail with evidence | Trust the agent's prose |
| Evaluator | Grade quality against a rubric | Share the generator's context and reasoning |
| Trace | Record enough to reproduce and cost | Log secrets |

One detail worth copying from the SWE-EVO and NanoHarness work: **tool registries beat raw
bash**. In the component study, adding four structured file tools (`read_file`,
`write_file`, `edit_file`, `glob`) produced some of the most stable gains. Structured tools
constrain the action space, which reduces syntax failures and makes traces readable.

## The component portfolio

Use this as a starting configuration, then ablate.

| Component | Default | Evidence | When to change the default |
| --- | --- | --- | --- |
| Filesystem plus git | on | Anthropic and LangChain converge on this | Never |
| Sandbox with network off | on | Baseline safety | Never |
| Structured tool registry | on | +4.57 / +3.54 pp | Never |
| Acceptance check runner | on | E1, E6 | Never |
| Progress artifact | on | Anthropic long-running research | Never |
| Budget manager | on | E5 | Never |
| Trace and cost accounting | on | E10 | Never |
| Task-specific subagents | on for broad tasks | +5.91 / +4.46 pp | Off for narrow single-file work |
| Explicit planning | on, lightweight | Small positive | Cap the list at 10 items |
| Lazy skills | on | Model-dependent | Off for small models |
| Separate evaluator | on for risky or subjective work | Anthropic GAN-style result | Off when tasks are inside model capability |
| Context compression | off by default | -4.86 / -3.85 pp on spec-heavy work | On for chat and long exploratory runs |
| General SE subagents | off | Negative in the study | Only with a specific, measurable reason |
| Multi-agent fan-out | off | Unresolved | Only with per-agent budgets and a merge protocol |

Two notes on the surprising entries:

**Context compression is not free.** It saves 54 to 77 percent of prompt tokens and loses
4 to 5 points of resolved rate on specification-heavy tasks. Compression is a cost
optimization, and it should be justified by a cost objective, not by a hunch about
efficiency. This is EVO's E6 in action: measure the quality impact before scaling the
optimization.

**A separate evaluator is worth it only when the task is beyond the generator.** Anthropic
found that on newer, stronger models, the evaluator became unnecessary for tasks inside
the model's reliable capability and still valuable at the edge. Re-evaluate the trade at
every model upgrade. That is the "load-bearing" test from their harness post.

## Contracts: the artifacts that carry intent

The most valuable harness component is not code. It is the set of files that carry intent
across sessions.

### `value/top-ten.md`

The quantified objectives, in Planguage form, with the current baseline. One screen.

### `tasks/feature_list.json`

Machine-readable, with explicit pass flags. Anthropic's research found that models are
less likely to rewrite or silently edit JSON than Markdown, which is why the pass flags
belong there rather than in prose.

```json
{
  "id": "F014",
  "category": "functional",
  "objective": "RefundTime",
  "description": "Support agent can refund a card payment in one click from the order page",
  "steps": [
    "Open order 10042 as support agent",
    "Click Refund",
    "Confirm amount equals captured amount",
    "Verify order state changes to refunded",
    "Verify audit log entry exists"
  ],
  "acceptance": "pnpm test:e2e -- refund.spec.ts",
  "budget": { "tokens": 400000, "minutes": 45 },
  "passes": false
}
```

### `progress.md`

Three questions, answered in under a minute: what state is the system in and how do I
verify it, what was the last step and did it deliver, what is the next step and why.

### `AGENTS.md`

Conventions, not documentation. The test command, the lint command, the directory map, the
things that will break if touched, and the definition of done. Keep it short. A stale
AGENTS.md is worse than none, because agents treat it as ground truth.

### The step contract

Borrowed from Anthropic's planner/generator/evaluator harness: before implementation, the
generator proposes what it will build and how success will be verified, and the evaluator
checks that the proposal actually matches the objective. They iterate until they agree.
Only then does code get written.

In EVO terms, this is the requirement plus the meter, agreed before the step. It is the
cheapest place to catch a misunderstanding, because nothing has been built yet. Given the
SWE-EVO finding that the strongest models fail mostly on instruction following, this
negotiation is likely the highest-leverage prompt in the whole harness.

## Budgets and model routing

### Budget schema

```yaml
budget:
  max_cost_usd: 3.00
  max_prompt_tokens: 800000
  max_steps: 120
  max_tool_calls: 250
  max_wall_clock_minutes: 60
  per_subagent:
    max_cost_usd: 0.75
    max_steps: 40
  on_exceed: return_partial   # options: return_partial, abort, escalate
```

Three rules that make budgets useful:

1. **Budgets are estimates written down before the run**, like an EVO impact estimate.
   Compare them with actuals every time. The ratio is your forecasting accuracy.
2. **Partial results are first class.** A run that stops at budget with a verified
   half-step is a useful outcome. A run that loops for an hour and produces nothing is
   not.
3. **Account per subagent.** Delegation is where costs hide, because each subagent looks
   cheap in isolation.

### Routing table

| Step type | Model tier | Why |
| --- | --- | --- |
| Requirement interpretation, spec negotiation | frontier | SWE-EVO: instruction following is the dominant failure |
| Architecture and API design | frontier | Errors here cascade and are expensive to undo |
| Routine implementation | mid | Good enough, much cheaper |
| Mechanical edits, renaming, formatting | small | Verifiable by tools, low judgement |
| Test writing | mid | Needs judgement but is checked mechanically |
| Final diff review | frontier, separate context | Best place to spend on verification |
| Log triage, search, summarization | small | High volume, low stakes |

Routing is a hypothesis, not a law. Measure resolved rate and cost per step by tier, and
re-route when the numbers disagree with the table.

## Verification: the meter layer

Ordered by trustworthiness:

1. **Deterministic checks.** Build, typecheck, lint, unit tests, migration dry runs. Cheap,
   reproducible, and the agent cannot argue with them.
2. **Behavioral checks.** Run the CLI, drive the browser, call the API, compare outputs.
   This is how Anthropic caught stubbed features that passed unit tests.
3. **Rubric checks.** A separate evaluator with written criteria and thresholds. Use for
   quality attributes that resist binary tests: design coherence, API ergonomics, error
   message quality.
4. **Human review.** The final backstop, and the meter for the other three.

Rules for the rubric layer, learned the hard way by other teams:

- **The evaluator must not see the generator's reasoning.** Give it the objective, the
  criteria, the artifacts and the running system. Not the chat history.
- **Criteria need hard thresholds.** "Any criterion below threshold fails the step" is
  enforceable. "Overall quality 7 out of 10" is not.
- **Calibrate with examples.** Few-shot scored examples reduce drift and align the judge
  with your taste.
- **Expect positivity bias.** LLM judges are generous toward LLM output. A skeptical judge
  helps; a judge told to find problems helps more.
- **Report partial progress carefully.** Fix Rate style scoring is more honest than pass
  or fail, but only with a regression guard.

One more rule, from the agent distraction work: **the evaluator should check that the
change is in scope**. A patch that fixes the asked-for bug and three unrequested ones is
not a better patch. It is a review liability.

## Safety as a Must-level constraint

EVO's Must level is the failure threshold. In a harness, that means constraints that zero
out the step regardless of value delivered.

| Constraint | Mechanism |
| --- | --- |
| No access outside the workspace | Sandbox, mount policy, network off |
| No secrets in context or traces | Secret scanning, env isolation, redaction |
| No destructive commands without approval | Command allowlist, dry-run mode, branch isolation |
| No production access | Separate credentials, no prod network route |
| No silent dependency installs | Pinned lockfile, offline package cache |
| No unreviewed merge | Protected branch, required check, human gate |

Treat a safety violation the way SWE-EVO treats a regression: the whole instance scores
zero. Otherwise a harness can learn that speed is worth a little risk, and it will.

## Failure modes the harness must handle

| Failure | Signal | Mechanism |
| --- | --- | --- |
| Context rot | Quality degrades as the window fills | Tool output offloading, targeted retrieval, resets |
| Context anxiety | Agent wraps up early near the limit | Explicit budget visibility, checkpoint and resume |
| Premature victory | Task marked done, feature stubbed | Acceptance check plus behavioral verification |
| Excessive probing | Hundreds of low-value exploration calls, budget exhausted | Probing budget, task-specific subagent, progress requirement |
| Insufficient probing | Few checks, confident implementation, shallow tests | Minimum evidence threshold, differential testing |
| Tool loop | Same command repeated | Loop detector, action deduplication, escalation |
| Stale plan | Plan unchanged for many rounds while state changed | Plan freshness reminder, replan hook |
| Distraction | Agent works on unrelated TODOs | Scope check, stale TODO cleanup, ignore lists |
| Reward hacking | Tests weakened or deleted, assertions loosened | Diff guard on test files, mutation checks |
| Broken exit state | Repo does not build after a session | Mandatory clean-state check, auto-revert |
| Patch does not apply | Syntactic mismatch | Structured edit tool, apply verification |

The probing table is worth internalizing. The NanoHarness study found agents fail at both
ends: one case made 133 reference probes and passed 24.68 percent of tests, another made 3
probes and passed 61.74 percent. With the better harness the first dropped to 43 probes and
68.17 percent, and the second rose to 45 probes and 75.18 percent. Good harness design
does not maximize exploration. It **regularizes** it.

## Build order

The order matters more than the feature list. Each stage has an exit criterion, which is
the EVO gate.

**Stage 1: the walking skeleton.** Bash plus filesystem in a sandbox, a single loop, a
trace, a token counter, and a hard step limit.

Exit: a real task from your backlog completes or fails cleanly, with a readable trace.

**Stage 2: meters.** An eval suite of 10 to 20 scenarios, a scoring script, and cost
reporting. No new features until this exists.

Exit: you can state resolved rate, cost per success and failure distribution for the
skeleton.

**Stage 3: contracts.** Task contract, acceptance check, progress file, `AGENTS.md`.

Exit: the acceptance check, not the model, decides completion in 100 percent of runs.

**Stage 4: structured tools.** `read_file`, `write_file`, `edit_file`, `glob`, plus a test
runner. Retire raw bash as the primary interface.

Exit: measurable reduction in syntax failures and unparseable patches.

**Stage 5: task-specific subagents.** Localization, implementation, verification, review.
Whitelisted tools per role, fresh context, structured report.

Exit: gain above noise on the suite, measured against the same tasks.

**Stage 6: planning.** A capped todo list with one item in progress.

Exit: small positive gain, or remove it. A component that does not pay for itself is
deleted, not kept "because it is good practice".

**Stage 7: skills.** Lazy-loaded procedures for debugging, build diagnostics, test triage,
final review.

Exit: gain is model-dependent, so record which models benefit and gate by model.

**Stage 8: compression.** Only after there is a cost objective that needs it, and only
with a measured quality delta.

Exit: cost down by the target amount, quality drop within the Must band.

**Stage 9: separate evaluator.** For the task classes where the generator is at its
capability edge.

Exit: it catches defects a human would have caught, and the cost per caught defect is
acceptable.

**Stage 10: routing.** Model tiers per step type, with per-tier measurement.

Exit: same or better resolved rate at lower cost.

The EVO shape here is deliberate: value first, cost second, complexity last. Most teams
invert it, build the multi-agent orchestration, and then discover they cannot tell whether
any of it helped.

## What not to build

- **A generic multi-agent framework before you have a meter.** Coordination cost is real
  and invisible without measurement.
- **A huge prompt library.** It rots, agents misread it, and stale instructions are
  negative value.
- **Compression by default.** It is a cost optimization with a quality price.
- **A dashboard before a metric.** Pretty charts of the wrong number are worse than none.
- **Custom model training.** It is a different project with a different budget.
- **A benchmark leaderboard for its own sake.** Optimize your task distribution, not a
  public score.
- **Step limits as a proxy for quality.** Lower step counts can mean efficiency or
  surrender. Check both.

## Checklist

- [ ] Five quantified harness objectives, with baselines, in `value/top-ten.md`.
- [ ] A scenario suite you can rerun, with cost reporting.
- [ ] Every task carries an acceptance check the harness runs itself.
- [ ] Budgets in tokens, steps, minutes and money, with partial results allowed.
- [ ] Structured tools instead of raw bash as the primary interface.
- [ ] Progress artifact and git history that a cold session can read.
- [ ] Safety constraints at Must level, scoring zero on violation.
- [ ] Failure taxonomy in every report, not just a score.
- [ ] Component toggles so ablations are cheap.
- [ ] A rule that each component must beat the meter or be removed.
- [ ] Re-run the harness evaluation whenever the model changes.

## References

Harness evidence:

- Haichuan Hu et al., "Beyond the Model: Demystifying Harness Effects in Software
  Engineering Agents", arXiv 2609.32459, September 2026. NanoHarness, component ablation,
  probing analysis, 10 models, 3 benchmarks.
  https://arxiv.org/html/2609.32459v1
- Vivek Trivedy, "The Anatomy of an Agent Harness", LangChain, March 2026.
  https://blog.langchain.com/the-anatomy-of-an-agent-harness/
- Birgitta Böckeler, "Harness engineering for coding agent users", April 2026.
  https://martinfowler.com/articles/harness-engineering.html
- Ryan Lopopolo, "Harness engineering: leveraging Codex in an agent-first world", OpenAI,
  February 2026.
  https://openai.com/index/harness-engineering/
- Google, "The anatomy of harness engineering: how to evaluate, iterate, and guard AI
  coding agents".
  https://developers.googleblog.com/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/
- François Zaninotto, "The State Of AI Harness Engineering 2026", Marmelab, September
  2026.
  https://marmelab.com/blog/2026/09/24/the-state-of-ai-harness-engineering-2026.html

Long-running agents and verification:

- Anthropic, "Effective harnesses for long-running agents", November 2025.
  https://www.anthropic.com/research/effective-harnesses-for-long-running-agents
- Prithvi Rajasekaran, "Harness design for long-running application development",
  Anthropic, March 2026. Planner, generator, evaluator, sprint contracts.
  https://www.anthropic.com/research/harness-design-long-running-apps
- OpenAI, Codex prompting guide, on tool logic and model co-training.
  https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide

Measurement:

- Thai et al., "SWE-EVO: Benchmarking Coding Agents in Long-Horizon Software Evolution
  Scenarios", arXiv 2512.18470, December 2025.
  https://arxiv.org/html/2512.18470v1
- METR, "Task-Completion Time Horizons of Frontier AI Models".
  https://metr.org/time-horizons/
- Sergio De Simone, "Google Finds That Technical Debt Can Derail Coding Agents through
  Agent Distraction", InfoQ, November 2026.
  https://www.infoq.com/news/2026/11/google-agent-distraction/

Method:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process", InfoQ, 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- [EVO in software development](evo-sw-devel.md)
- [EVO in the AI harness era](evo-in-ai-era.md)
- [Simulating the EVO process for harness development](evo-simulation.md)
- [Simulating and building a self-improving EVO harness](evo-rsi-harness.md) for the loop
  that improves the harness, and the guardrails it needs.
