# EVO in the AI harness era

EVO was designed for a world where engineering hours were the scarce resource. In 2026
the scarce resources are different: verified value, trustworthy context and money spent
on inference. This page argues that the EVO loop is a better fit for coding agents than
the sprint rituals most teams still use, and then shows the mapping with evidence from
benchmarks, harness research and field reports.

Read [EVO in software development](evo-sw-devel.md) first if the terms are new.

## The short argument

Coding agents changed the cost structure of software work:

- Writing code became cheap and fast.
- Reading, specifying, verifying and integrating code did not.
- Running an agent became metered. Every step has a price in tokens and wall-clock time.
- The failure mode moved from "we cannot build it" to "we built the wrong thing, at
  scale, and cannot tell whether it works".

Those four sentences describe an EVO problem. EVO is a method for buying measurable
value in small increments under a budget, with the estimate checked against reality at
every step. Replace "budget" with "tokens and review attention" and the method still
applies, almost without edits.

## What actually changed

Some context numbers worth keeping in mind:

- **Maintenance dominates.** Up to 80 percent of software engineering effort goes into
  maintaining and evolving existing systems rather than building new ones. The SWE-EVO
  paper cites this, and every experienced engineer recognizes it.
- **Adoption is near total.** DORA 2025 reports over 90 percent of engineering teams
  integrating generative AI into their practices, up from 61 percent in 2024, as cited
  in the same paper.
- **Capability is uneven.** Agents are excellent at local, well-specified edits and much
  weaker at sustained, multi-file evolution under an ambiguous requirement. The rest of
  this page is mostly about that gap.
- **Cost is real.** A frontier model at medium reasoning effort doing 100 tool calls per
  task is not free. Teams that ignore cost per step discover it at the end of the
  quarter.

So the interesting question in 2026 is not "can the model write this function". It is
"can the system deliver this result, and what did it cost to find out". That is the EVO
question.

## Evidence: the benchmark that looks like an EVO step

SWE-EVO (arXiv 2512.18470, December 2025, FPT Software AI Center and University of
Melbourne) is the most directly relevant benchmark for this page, because of how the
tasks are constructed.

### How the tasks are built

The authors take release notes and version history from seven mature open source Python
projects, for example scikit-learn and pydantic. An instance is defined as:

- **Input**: the release note delta between version N and version N+1, plus the complete
  codebase at version N.
- **Output**: a patch that implements the change described in the release notes.
- **Verification**: the project's own test suite, with at least one test that fails
  before the change and passes after, plus regression tests that must keep passing.

That is an EVO step in everything but name. A stakeholder-facing statement of intended
value, applied to an existing system, verified against a measurement.

The dataset is small and deliberately hard: 48 validated instances across 7
repositories.

### What the tasks look like

| Attribute | Mean | Max |
| --- | --- | --- |
| Issue text length (words) | 2390.5 | 22344 |
| Non-test files in codebase | 363 | 1046 |
| Non-test lines in codebase | 78K | 272K |
| Lines edited by the gold patch | 610.5 | 4113 |
| Files edited by the gold patch | 20.9 | 105 |
| Functions edited | 51.0 | 379 |
| Tests that must go from fail to pass | 81.4 | 2774 |
| Total tests per instance | 874.0 | 8552 |

Compare that with the habit of asking an agent to "add OAuth login" in one prompt. The
average task touches 21 files and 51 functions, and is verified against 874 tests. The
release notes are often thousands of words and reference upstream pull requests and
issues.

### What the results say

The headline number: GPT-5 with OpenHands resolves about 21 percent of SWE-EVO tasks,
against 65 percent on SWE-bench Verified. In the stricter release-note-only setting, the
same model resolves about 15 percent with OpenHands and 17 percent with SWE-agent.

Selected results with release note plus PR or issue context:

| Model | SWE-EVO OpenHands, resolved | SWE-EVO SWE-agent, resolved | SWE-bench Verified |
| --- | --- | --- | --- |
| gpt-5 | 18.75 | 20.83 | 65.00 |
| kimi-k2-instruct | 16.67 | 18.75 | 43.80 |
| glm-4.5 | 16.67 | 16.67 | 54.20 |
| qwen3-coder-480b | 14.58 | 14.58 | 55.40 |
| deepseek-r1 | 10.42 | 8.33 | 57.60 |
| gpt-5-mini | 10.42 | 10.42 | 59.80 |
| gpt-4.1 | 2.08 | 10.42 | 39.58 |

Three observations that matter for method design:

1. **Ranking is sane.** Models that do well on SWE-Bench also do well on SWE-EVO, so the
   benchmark is measuring software ability, not noise.
2. **Scale still matters.** gpt-5 beats gpt-5-mini beats gpt-5-nano, consistently.
3. **Context barely helps.** Giving the agent the referenced PR and issue content
   improves results only modestly. Even with the specification spelled out, agents
   struggle to reconstruct the right implementation. The bottleneck is interpretation
   and coordination, not missing information.

The authors also propose **Fix Rate**, a soft metric: the share of fail-to-pass tests a
patch fixes, with the whole instance scored zero if any previously passing test breaks.
For gpt-5 the Fix Rate is about 28 to 31 percent, meaning the agent often makes real
partial progress that the binary resolved rate hides. This is a very EVO idea: partial
value is still value, but never at the price of a regression.

### Why agents fail

The failure taxonomy is the most useful part of the paper for practitioners:

| Failure mode | What it means |
| --- | --- |
| Instruction following | The agent misreads or ignores the release note and solves the wrong task |
| Incorrect implementation | Right area of the code, wrong behavior |
| Tool use | Fails to run tests, misuses edit commands, opens the wrong paths |
| Syntax error | Patch does not parse or apply cleanly |
| Stuck in loop | Repeats reads or test runs without progress |
| Gave up prematurely | Stops while viable steps remain |

The distribution is the punchline. gpt-5 almost never fails on syntax or tools. Over 60
percent of its remaining failures are **instruction following**: it misreads a long,
nuanced release note. Smaller models fail more on tools and syntax. Open models such as
kimi-k2 fail mostly on incorrect implementation, around 70 percent, with almost no tool
errors.

Translation into EVO terms: the strongest agents have mastered the mechanics and are
now limited by understanding intent. That is precisely the problem Planguage and a
quantified top ten are designed to solve. A release note is a narrative. A scalar
requirement with Must, Plan and a meter is a machine-checkable intent.

## Evidence: how long agents can run

METR measures the **task-completion time horizon**: the human-expert task duration at
which an agent succeeds with a given probability. Their estimates come from fitting a
logistic curve over performance on over a hundred software, ML and cybersecurity tasks,
with six runs per task.

Findings relevant here, from the time horizon page last updated in September 2026:

- The 50 percent horizon has grown exponentially, with no sign of the curve flattening
  yet in the data they have.
- As an illustration of scale, GPT-5 is reported at roughly 2 hours 17 minutes at the 50
  percent level.
- Measurements above 16 hours are unreliable with the current task suite.
- Task performance is measured on self-contained, well-specified tasks with automatic
  scoring. The authors are explicit that real work is messier, and that agent
  performance drops substantially when work is scored holistically rather than
  algorithmically.
- The horizon describes task difficulty relative to a low-context human, such as a new
  hire or contractor, not relative to an expert with project history.

Method consequences:

1. **A step must be shorter than the reliable horizon.** If an agent's 80 percent
   horizon is a couple of hours, then a multi-day task is a sequence of steps with
   checkpoints, not one prompt.
2. **The horizon is a budget input, not a promise.** Exponential growth is a trend, not
   a guarantee, and the measurement says nothing about your specific codebase.
3. **Holistic scoring is where humans live.** The gap between algorithmic test scores
   and holistic review is exactly the gap EVO's stakeholder measurement covers.

## Evidence: agents work in shifts and declare victory

Anthropic published a study of long-running agents (November 2025) that is, functionally,
a description of EVO failures in agent form. Their setup: a model working across many
context windows, each session starting with no memory of the last.

Two failure patterns dominated:

- **One-shotting.** The agent tried to build everything at once, ran out of context
  mid-feature, and left the next session to guess what had happened.
- **Premature victory.** A later session looked around, saw progress, and declared the
  job done.

Their fix is a two-role harness:

1. **Initializer agent.** Runs once. Writes an `init.sh` to start and test the app, a
   `claude-progress.txt` log, an initial git commit, and a `feature_list.json` with
   hundreds of end-to-end feature descriptions, every one marked `"passes": false`.
2. **Coding agent.** Runs per session. Reads the progress log and git history, runs a
   basic end-to-end check to confirm the app is not broken, picks exactly one failing
   feature, implements it, verifies it like a user would, then commits and updates the
   progress log.

They also found the agents would mark features complete without testing them end to
end. The fix was tooling: browser automation so the agent can check the feature as a
human would, not just run unit tests.

Their own summary table maps problem to mechanism:

| Problem | Mechanism |
| --- | --- |
| Declares the whole project done early | Feature list with explicit pass flags |
| Leaves the repo broken or undocumented | Progress file plus git commits each session |
| Marks features done prematurely | Self-verification through end-to-end tooling |
| Wastes time rediscovering how to run things | `init.sh` and a fixed start-of-session routine |

Now read that as EVO:

- Feature list with pass flags = quantified objectives with a meter.
- One feature per session = one step.
- Progress log and git = the measurement record.
- End-to-end check before new work = baseline verification, so you do not build on a
  broken system.
- Clean state at session end = the step is delivered, not half-delivered.

The researchers arrived at EVO's shape from engineering pressure, not from reading
Gilb. That convergence is the strongest argument on this page.

## Evidence: the repository is the context

Google published an analysis of what they call **agent distraction** (November 2026, via
InfoQ). The finding: stale artifacts in a codebase actively mislead agents.

Using distributed traces from thousands of engineers and hundreds of millions of agent
steps, they looked at `TODO` and `FIXME` comments that reference bugs:

- About 13 percent of sessions exposed the agent to such a reference.
- In 6 percent of those sessions the agent took action on the referenced bug.
- In most of those cases the user prompt never mentioned the bug.
- 41 percent of the unprompted detours targeted tickets that were already closed.
- 57 percent targeted open bugs outside the scope of the request, which they classify as
  scope creep.
- The cost per session when a detour happened: 70 percent more steps, 77 percent more
  tokens, 105 percent more wait time.

Their mitigation was scanner agents that verify a TODO is obsolete against git history
and open a removal PR. Over six months this removed thousands of obsolete references
with over 95 percent human acceptance.

Read this as an EVO measurement:

- Technical debt has a token price now. E7, "invest in an open-ended architecture",
  turns into "keep the repository legible to the next agent".
- Documentation and comments are inputs to the next step. Stale ones are negative
  value, not neutral.
- The 70/77/105 percent numbers are a rare, concrete estimate of what unmanaged
  maintainability costs in the AI era. Use them in your own impact table.

## Evidence: harness engineering is the new method layer

The 2026 consensus is that the model is only half of the system. The other half is the
**harness**: tools, context management, memory, control loop, permissions, verification.

The most quoted experiment: the same model, run through eight different harnesses on
the same 25 tasks, with the same provider and tools. Success went from 68 percent to 88
percent. Method choice moved the result by 20 points, with the model held constant.

Thoughtworks' Birgitta Böckeler (April 2026) gave the field its mental model:

> Agent = Model + Harness

Field reports, treated as vendor claims but useful as scale markers:

| Organisation | Reported outcome |
| --- | --- |
| OpenAI (Codex harness engineering, Feb 2026) | About 1M lines, zero manually written, about 1500 merged PRs, 3.5 per engineer per day, over five months |
| Stripe (Minions) | About 1300 PRs per week, roughly 70 percent merged with no human rework |
| Anthropic (long-running apps) | Sustained multi-session progress using initializer plus coding agent roles |
| Google (harness anatomy) | Evaluate, iterate, guard: behavioral evals and tool-call tests |

The Stripe number is the interesting one for EVO. Seventy percent merged without rework
is a value statement, not an activity statement. The other 30 percent is the cost of
learning, and it should be measured, not hidden.

The survey behind these numbers (246 repositories audited, 57 publications read)
reported a less flattering finding too: most published harnesses are documentation, not
constraint. Very few test their own harness. That is the same failure as an agile team
with a beautiful board and no measurement.

## The translation table

Here is the core of the page. Each EVO principle, with the harness practice that
implements it and the artifact you can point at.

### E1: decompose by performance results and stakeholders

Harness practice: break the requirement into vertical slices that produce an
observable result, and express each as a checkable feature entry.

Artefact: `feature_list.json` with end-to-end descriptions and pass flags, or a
`value/top-ten.md` with scalars. Not a task list of files to edit.

Failure it prevents: the agent producing a plausible layer of code that changes nothing
a stakeholder can see.

### E2: do high-risk steps early

Harness practice: run the scariest part first, as a spike, with an explicit question.
Which is riskier, the unfamiliar API, the migration, or the model's ability to follow
the spec? Test that in step one, in an isolated branch, with a throwaway budget.

Artefact: a spike note with the question, the budget, and the answer. The answer is
allowed to be "this approach does not work".

Failure it prevents: discovering in week six that the whole plan rests on an assumption
nobody tested, after 40 million tokens.

### E3: focus on the most valuable objectives first

Harness practice: rank candidate steps by value per cost where cost includes tokens,
review time and risk. Regenerate the ranking every step.

Artefact: the Impact Estimation table, with a token column.

Failure it prevents: agents grinding through low-value cleanup because it is easy to
describe and easy to verify.

### E4: evolve the existing system

Harness practice: point the agent at the real repository and the real tests. No
greenfield sandbox, no rewrite branch that never merges.

Artefact: the actual repo at the actual commit, with the actual test command.

Failure it prevents: the demo that works in isolation and cannot be integrated, which is
exactly what SWE-EVO measures and agents fail at.

### E5: design to cost dynamically

Harness practice: give every session and every step a budget in tokens, tool calls and
wall-clock time. Stop when the budget is spent, then decide, do not let the loop run
until it succeeds by exhaustion.

Artefact: a per-step budget in the harness config, and a log of actual spend.

Failure it prevents: silent cost blowup, which is the AI equivalent of an unbounded
scope creep.

### E6: design to performance dynamically

Harness practice: measure the quality attributes you actually care about, not only
"tests pass". Latency, error rate, review rework and regression rate all belong in the
step report.

Artefact: an eval suite plus a per-step report with numbers.

Failure it prevents: a green test suite on a system that got slower, flakier and harder
to maintain.

### E7: invest in an open-ended architecture

Harness practice: make the repository agent-legible. Small modules, explicit entry
points, a working `init.sh`, current docs, no stale TODOs, tests that run in one
command, and a short `AGENTS.md` that states conventions.

Artefact: a repository a fresh agent can navigate in ten tool calls.

Failure it prevents: agent distraction, the 70 percent extra steps and 77 percent extra
tokens measured by Google.

### E8: reward results, not effort

Harness practice: measure merged changes that survive review, rework rate, and movement
on stakeholder numbers. Do not celebrate lines of code, PR count or token spend.

Artefact: a delivery dashboard with merged-without-rework percentage, like Stripe's 70
percent, and change failure rate.

Failure it prevents: the team that ships 300 agent PRs a week and spends the next month
reverting them.

### E9: prioritize by value, not queue position

Harness practice: the backlog is a menu, not a queue. An idea that appears mid-session
can be the next step if the value per cost is better. Half-finished agent work is
allowed to be abandoned.

Artefact: the ranked table, recomputed at every step boundary.

Failure it prevents: sunk-cost commitment to a plan generated by a model in minute one.

### E10: learn fast, change fast

Harness practice: short sessions, explicit handoff artifacts, evals that run in
minutes, and a habit of reading the trace when something fails. Failure modes are data.

Artefact: session log, trace review, eval results, updated estimate.

Failure it prevents: the same failure repeating across 20 sessions because nobody
looked at why the first one failed.

## Which pocket pays for intelligence

The project framing for this site: large models need large and complex infrastructure,
and not every step deserves the expensive one. EVO gives a language for that decision.

### A simple cost ladder

Prices change, so use relative cost and re-measure quarterly:

| Tier | Typical use | Relative cost per step |
| --- | --- | --- |
| Frontier reasoning model | Specification, planning, ambiguous release notes, architecture review, final review of risky diffs | 10 |
| Strong mid-tier coding model | Normal implementation, refactors, test writing | 2 to 3 |
| Small fast model | Mechanical edits, formatting, summarization, log triage, first-pass search | 1 |

Two rules of thumb:

- **Spend on interpretation, save on production.** The SWE-EVO failure data says
  interpretation is where strong models separate. Pay for the planning and the review,
  not for typing.
- **Spend on verification, not on retries.** A second model reviewing a diff is usually
  cheaper than three failed attempts by the first model.

### Impact estimation with a token column

The EVO table survives with one extra column:

| Candidate step | Value (weighted gap closure) | Tokens, estimated | Review hours | Value per cost | Decision |
| --- | --- | --- | --- | --- | --- |
| Migrate auth to OAuth | 22 | 1.2M | 6 | 3.1 | next |
| Add request caching | 9 | 0.3M | 2 | 3.6 | next |
| Rewrite the reporting module | 18 | 8.0M | 40 | 0.4 | no |
| Clean obsolete TODOs | 3 | 0.2M | 1 | 2.7 | batch later |

The scoring is rough. Its job is to make the trade-offs explicit and arguable. The
rewrite looks valuable and is a bad buy, which is exactly the kind of conclusion an
unstructured agent session will never reach on its own.

### Measure cost per delivered change

Track, per step:

- Tokens and money spent.
- Review minutes per merged change.
- Rework rate: share of merged changes that need a follow-up fix within two weeks.
- Change failure rate: share of changes that cause an incident.
- Value moved on the top objectives.

Cost per delivered change is the number to watch. It moves when the harness improves,
when the repo gets cleaner, and when you route the right model to the right step. It is
the AI-era equivalent of cost per story point, with the advantage that it is denominated
in something real.

## Anti-patterns and their EVO fixes

| Anti-pattern | Symptom | EVO fix |
| --- | --- | --- |
| One-shot prompting | Agent runs out of context mid-feature, repo left broken | E1 plus E10: one step, clean exit, handoff artifacts |
| Giant diffs | 40 files changed, review takes days, regressions slip in | E1: vertical slices with independent verification |
| Agent declares done | Tests pass, feature does not work end to end | E6: meter includes end-to-end behavior |
| Unbounded loops | Same failing test retried 30 times | E5: budget per step, stop and reassess |
| Context stuffing | Whole repo in the prompt, cost explodes, attention degrades | E7: legible repo plus targeted retrieval |
| Stale documentation | Agent chases closed tickets and dead specs | E7: docs and TODOs are maintained artifacts |
| Activity metrics | Reporting PRs per week with no outcome data | E8: merged-without-rework and value movement |
| Model maximalism | Frontier model used for formatting | E5: cost ladder and routing |
| Plan worship | Model-generated plan followed for a month | E9: recompute value per cost every step |
| Hidden rework | Successful demo, broken production | E8 plus E6: change failure rate and Fix Rate style partial credit |

## A working protocol for one EVO step with agents

This is a concrete protocol you can adopt on Monday. It assumes one repository, one
human owner, and a coding agent with shell access.

### Before the step

1. **Write the objective.** One scalar with scale, meter, current level, Must, Plan.
   Store it in `value/top-ten.md`.
2. **Write the acceptance check.** How will we know, mechanically, that the step
   delivered? A command, a test, a query, a screenshot diff.
3. **Estimate.** Value, tokens, review hours, risk. Add the row to the impact table.
4. **Prepare the context.** Confirm `AGENTS.md` is current, the test command works, and
   `init.sh` (or equivalent) brings the app up. Fix the repo before giving it to the
   agent, not after.

### During the step

5. **One feature per session.** Start the agent with the objective, the acceptance check,
   the budget, and the instruction to leave the repo clean.
6. **Force verification.** The agent must run the acceptance check and report the
   result, not just edit files.
7. **Commit with a message that names the objective.** The git log becomes the step
   record.

### After the step

8. **Review against the objective, not the diff style.** Did the number move? Did
   anything regress? Reviewing 400 lines of style is the new bike-shedding.
9. **Measure and record.** Actual value, actual tokens, actual review time, estimate
   versus result.
10. **Decide the next step from the table.** Not from the plan written in minute one.

### The handoff artifact

Keep a small progress file, as Anthropic's research does. It should answer three
questions in under a minute of reading:

- What is the current state of the system, and how do I verify it?
- What was the last step, and did it deliver?
- What is the next step, and why is it the best value per cost right now?

That file is the difference between an agent that resumes work and an agent that
re-explores the repository from scratch every session.

## Worked example: one week, one evolution step

A realistic sequence, with EVO annotations.

**Monday.** Objective: reduce median checkout failure rate from 1.8 to 0.8 percent, Must
stay under 1.5, measured from payment provider logs. Candidate steps: retry logic,
provider failover, better error messages, checkout rewrite. Impact table puts retry
logic first at 55 percent estimated gap closure for 0.4M tokens and three review hours.
The rewrite is rejected: 8M tokens, 0.3 value per cost.

**Tuesday.** Agent implements retry logic on a branch with a token budget of 400k and an
acceptance check: replay 500 failed test transactions in staging, assert the success
rate. It runs the check itself and reports. First attempt fails the regression test for
idempotency. The trace shows the agent retried non-idempotent calls.

**Wednesday.** Human review identifies the real issue: the retry classification needs
domain knowledge about which errors are safe. The human writes a five-line spec, not
code. The agent implements it. Acceptance check passes.

**Thursday.** Rollout to 10 percent of traffic. Measured failure rate: 1.1 percent, not
the predicted 0.8. The estimate was wrong. That is recorded.

**Friday.** Next step chosen from the new data: provider failover, now estimated at 40
percent gap closure with better confidence, because the retry data revealed the error
distribution. No rewrite, no new plan document. The table simply has one more row and
one fewer unknown.

Total: 0.35M tokens, about five review hours, one measurable improvement, one wrong
estimate turned into knowledge. That is a good EVO week.

## Open questions

Being explicit about what is not settled:

1. **Do harness gains generalize?** The 68 to 88 percent experiment is small, and the
   published field reports skew towards web applications and greenfield or
   greenfield-adjacent code. Brownfield enterprise systems are underrepresented.
2. **How much of SWE-EVO difficulty is specification?** The instruction-following
   failures suggest better specifications would help. That is a hypothesis, not a
   demonstrated result, and it is testable.
3. **Is Fix Rate a good business metric?** Partial credit is more honest than pass or
   fail, but it can reward patches that fix symptoms. It needs a regression guard, which
   the paper includes, and it still needs human judgement.
4. **What is the real cost curve?** Token prices move fast, and the mix of planning,
   coding and reviewing changes the bill. Any cost ladder is a snapshot.
5. **Does the time horizon hold on messy work?** METR's own caveats say no, at least not
   yet. Holistic scoring drops performance, and real projects are holistic.
6. **Single agent or multi-agent?** Anthropic's own future work section says this is
   unresolved. Role specialization helps on some tasks and adds coordination cost on
   others.
7. **Who owns the meter?** In a team, the measurement owner matters more than the tool.
   EVO assumes a named owner. Most AI rollouts do not assign one.
8. **What happens to junior engineers?** If the harness absorbs the small steps, the
   learning ladder changes. EVO's answer, measure value rather than activity, applies to
   people as well as agents, and the implications are not comfortable.

## Checklist

- [ ] Write five quantified objectives with scales and meters, and publish the baseline.
- [ ] Give every agent session a budget in tokens and wall-clock time.
- [ ] Require an acceptance check the agent runs itself.
- [ ] Keep a progress file and a git history an agent can read cold.
- [ ] Review against the objective, not the diff aesthetics.
- [ ] Track merged-without-rework, rework rate and cost per delivered change.
- [ ] Keep the repository legible: current docs, no stale TODOs, one-command tests.
- [ ] Route models by step type, and re-measure the routing quarterly.
- [ ] Recompute value per cost at every step boundary.
- [ ] Record every estimate and every result. The gap is your real method.

## References

Benchmarks and measurement:

- Thai, Le, Manh, Phan, Bui, "SWE-EVO: Benchmarking Coding Agents in Long-Horizon
  Software Evolution Scenarios", arXiv 2512.18470, December 2025.
  https://arxiv.org/html/2512.18470v1
- SWE-EVO code and dataset.
  https://github.com/FSoft-AI4Code/SWE-EVO
- METR, "Task-Completion Time Horizons of Frontier AI Models", last updated September
  2026.
  https://metr.org/time-horizons/
- METR, "Measuring AI Ability to Complete Long Tasks", arXiv 2503.14499.
  https://arxiv.org/abs/2503.14499

Harness research and practice:

- Anthropic, "Effective harnesses for long-running agents", November 2025.
  https://www.anthropic.com/research/effective-harnesses-for-long-running-agents
- Anthropic, "Harness design for long-running application development", 2026.
  https://www.anthropic.com/research/harness-design-long-running-apps
- Anthropic, "Building a C compiler with a team of parallel Claudes".
  https://www.anthropic.com/engineering/building-c-compiler
- Birgitta Böckeler, "Harness engineering for coding agent users", April 2026.
  https://martinfowler.com/articles/harness-engineering.html
- Ryan Lopopolo, "Harness engineering: leveraging Codex in an agent-first world",
  OpenAI, February 2026.
  https://openai.com/index/harness-engineering/
- Google, "The anatomy of harness engineering: how to evaluate, iterate, and guard AI
  coding agents".
  https://developers.googleblog.com/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/
- François Zaninotto, "The State Of AI Harness Engineering 2026", Marmelab, September
  2026. 246 repositories audited, 57 publications read.
  https://marmelab.com/blog/2026/09/24/the-state-of-ai-harness-engineering-2026.html
- HumanLayer, "Advanced context engineering for coding agents".
  https://www.humanlayer.dev/blog/advanced-context-engineering
- Shopify Engineering, "Introducing Roast".
  https://shopify.engineering/introducing-roast
- Stripe, "You can't whisper at an AI agent".
  https://stripe.dev/blog/ai-steering-experiments
- Addy Osmani, "Agent harness engineering".
  https://addyosmani.com/blog/agent-harness-engineering/

Technical debt and agent distraction:

- Sergio De Simone, "Google Finds That Technical Debt Can Derail Coding Agents through
  Agent Distraction", InfoQ, November 2026.
  https://www.infoq.com/news/2026/11/google-agent-distraction/
- Sam Saccone and Madhuri Garikapati, original Google post.
  https://developers.googleblog.com/agent-distraction/

Method background:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process", InfoQ, 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- Tom Gilb, *Competitive Engineering*, Elsevier, 2005.
- [EVO in software development](evo-sw-devel.md) for the method itself.

Next in the series:

- [Building a custom AI harness with EVO principles](evo-in-ai-harness.md) turns the
  mapping into a design guide.
- [Simulating the EVO process for harness development](evo-simulation.md) shows how to
  measure the harness without fooling yourself.
