# Simulating and building a self-improving EVO harness

A harness that improves itself sounds like science fiction until you write down what it
actually means. In practice it means this: the harness runs a task, something observes the
result, and a program rewrites part of the harness so the next attempt is better. That is
it. No new model weights, no gradient, no magic. Just a loop with a feedback signal.

The uncomfortable part is that "better" has to be defined by something the loop cannot
edit. Every credible result in this space freezes the evaluator before the search starts.
Every failure in this space comes from a loop that found a way around the evaluator. That
single asymmetry explains most of the design decisions in this page.

Six 2026 papers make the topic concrete. Three of them build a loop that works. Three of
them measure whether the loop is worth having.

The three methods:

- **Recursive Harness Self-Improvement** (RHI, arXiv 2607.15524) shows that a harness
  written as a prompt can be revised in two or three iterations to beat the strongest
  test-time scaling setting of the same model, at up to 60 percent lower cost.
- **Mixture of Self-Improving Branches** (arXiv 2609.37834) shows that a single search
  trajectory stalls, and that branching the search with evolving development subsets and
  a router recovers complementary harnesses.
- **InfraRSI** (arXiv 2611.11558) shows what it takes to run this loop against real
  hardware: a locked task contract, sixteen invariants, a noise model, and a cross-cluster
  experience bank that survives the transfer.

The three audits:

- **The RSI Tax** (arXiv 2611.13524) prices the loop. On continual task streams, the token
  cost of self-improvement exceeds the cost of executing the tasks for three of the four
  published methods, and a 2,048-token note beats all of them on accuracy per token.
- **TRUST** (arXiv 2611.10787) puts a statistical gate on the loop. A greedy accept rule
  keeps bad updates 45.59 percent of the time; a sequential test with a declared error
  budget cuts that to 2.78 percent and still ends with a higher score.
- **Beneath the Surface** (arXiv 2611.07624) audits what the loop actually changed. All
  sixteen evolved agents it studies gain tasks and lose tasks, and the highest scoring agent
  never yields the largest further improvement.

Alongside them sits the measurement base from
[Beyond the Model](https://arxiv.org/html/2609.32459v1), which established that harness
choice is worth roughly a model generation in points.

This page is the synthesis. It covers what the six papers actually did, how to read them
through EVO, how to simulate the loop before you build it, and where the whole idea breaks.
The order is deliberate: the methods first, because that is the exciting part, then the
three audits, because that is the part that decides whether you should run any of it.

Read [Building a custom AI harness with EVO principles](evo-in-ai-harness.md) first if you
want the harness design itself. Read [Simulating the EVO process for harness development](evo-simulation.md)
for the measurement protocol that this page reuses. This page is about the loop that
optimizes the harness, not the harness that runs the task.

## Contents

- [What recursive self-improvement means here](#what-recursive-self-improvement-means-here)
- [The measurement base](#the-measurement-base)
- [RHI: recursion at the prompt level](#rhi-recursion-at-the-prompt-level)
- [Branching search: recursion without collapse](#branching-search-recursion-without-collapse)
- [InfraRSI: recursion under a locked contract](#infrarsi-recursion-under-a-locked-contract)
- [The RSI tax: recursion that costs more than it delivers](#the-rsi-tax-recursion-that-costs-more-than-it-delivers)
- [TRUST: recursion with a statistical gate](#trust-recursion-with-a-statistical-gate)
- [Beneath the Surface: recursion that moves tasks around](#beneath-the-surface-recursion-that-moves-tasks-around)
- [The rest of the 2026 wave](#the-rest-of-the-2026-wave)
- [The same loop in three costumes](#the-same-loop-in-three-costumes)
- [The EVO reading](#the-evo-reading)
- [A reference RSI loop for a coding harness](#a-reference-rsi-loop-for-a-coding-harness)
- [The three clocks](#the-three-clocks)
- [Simulating the loop before building it](#simulating-the-loop-before-building-it)
- [The overfitting curve](#the-overfitting-curve)
- [Guardrails](#guardrails)
- [What breaks](#what-breaks)
- [Build order](#build-order)
- [What does not transfer](#what-does-not-transfer)
- [Worked example: one week of harness RSI](#worked-example-one-week-of-harness-rsi)
- [Open questions](#open-questions)
- [Checklist](#checklist)
- [References](#references)

## What recursive self-improvement means here

The phrase carries a lot of baggage. Strip it down to something you can build.

**Recursive self-improvement, working definition.** A system where the output of one
improvement cycle becomes the input to the next, and the thing being improved is part of
the system doing the improving.

The recursion can happen at four levels, and they are not equally practical.

| Level | What changes | Cost per cycle | Reversible | Who can do it |
| --- | --- | --- | --- | --- |
| Weights | The model itself | Months, millions | No | Labs only |
| Training code | The recipe that makes the model | Weeks | Partly | Labs and serious infra teams |
| Harness code | Tools, loop, orchestration | Hours | Yes | Any team |
| Harness prompt | Roles, instructions, contracts | Minutes | Yes | Anyone |

Everything below the top two is a software problem, which is why the 2026 literature lives
there. RHI operates at the prompt level and treats the harness as text. The branching paper
operates at the code level and treats the harness as a program. InfraRSI operates at both,
plus a configuration layer, and adds a verification contract.

The important consequence of that table: **prompt-level and code-level RSI are cheap enough
to run often and cheap enough to revert.** If an experiment costs twenty minutes and a
`git revert`, you can afford a hundred of them. That is the whole reason this is tractable
now and was not in 2020.

### The one design rule that matters

Look for the frozen thing in each paper.

In RHI, the evaluator prompt `x_eval` is deliberately withheld from the harness optimizer.
The optimizer sees only the preference history that the evaluator produced. It never sees
the rubric it is being scored against.

In the branching paper, the task reward comes from benchmark tests the proposer does not
write, and the router is fitted on development cases only. Test outcomes never enter
selection.

In InfraRSI, frozen files are pinned by SHA-256 digest at `init`, and sixteen deterministic
invariants are checked before any candidate is promoted. The agent is not allowed to touch
the dataset loader, the loss definition, or the timer.

Three papers, three mechanisms, one pattern: **the optimizer must not be able to edit its
own judge.** When that holds, the loop is a search. When it fails, the loop is a
rationalization engine.

This is also, quietly, the same rule as EVO's Must level. A Must is a constraint that zeroes
out the delivery regardless of the value delivered. A frozen evaluator is the harness
equivalent: no amount of speed or task success compensates for a violated invariant.

### Five ways it goes wrong

| Failure | What it looks like | First paper to name it |
| --- | --- | --- |
| Reward hacking | Tests weakened, work moved outside the timing window, precision lowered beyond the declared menu | InfraRSI |
| Search collapse | Every proposal resembles the last one, the loop plateaus in one basin | Branching paper |
| Cost blowup | Search costs more than the delivery it enables, so the "gain" is negative | RHI motivates it, citing Wang et al. 2026 |
| Coverage churn | The average rises because new tasks are gained, while previously solved tasks quietly regress | Beneath the Surface |
| Gate noise | The loop accepts an update that scored higher by luck, then builds the next revision on top of it | TRUST |

Every design decision in the rest of this page exists to address one of those five.

## The measurement base

RSI is only worth doing if harness changes are worth a lot. The 2026 harness study measured
that directly, and the numbers are the reason this literature exists.

On SWE-bench Verified leaderboard data, with the model held fixed, the gap between the best
and worst harness is **19.4 percentage points**. The gap between Claude model generations
under a fixed harness is **22.8 points**. Harness engineering is roughly the same order of
leverage as upgrading the model.

The same study's component ablation on ProgramBench is the part that matters for
self-improvement, because it shows the landscape is not smooth:

| Component | Qwen3.7-Max | DeepSeek-V4-Pro |
| --- | --- | --- |
| Tool registry | +4.57 pp | +3.54 pp |
| Task-specific subagents | +5.91 pp | +4.46 pp |
| Explicit planning | small positive | small positive |
| Lazy skills | small positive | model-dependent |
| Context compression | -4.86 pp | -3.85 pp |
| General subagents | negative | negative |
| All combined | +7.37 pp | +6.21 pp |

Two lessons for any RSI loop.

1. **Gradients are not additive.** The combined gain is less than the sum of the positive
   components, and the negative components do not simply subtract. A search that scores
   changes one at a time will overestimate stacks.
2. **Some "obvious" improvements are losses.** Context compression cut prompt tokens by 54
   to 77 percent and cost 4 to 5 points of resolved rate. An optimizer that only measures
   cost will confidently adopt it.

If harness design were linear, a simple hill climb would work. It is not linear, which is
why the branching paper exists and why InfraRSI builds a global model over all trials
instead of stepping from the incumbent.

## RHI: recursion at the prompt level

RHI is the cheapest credible version of the idea, and therefore the best place to start.

### The representation: harness as prompt

RHI defines the harness as the agent loop itself, written as text. Four components:

| Component | What it specifies |
| --- | --- |
| Roles | Which agents exist and what each is responsible for |
| Instructions | How each agent behaves, what it must produce |
| Contracts | Which information passes between agents and the orchestrator |
| Hops | The workflow structure: who runs when, what triggers the next step |

Agent design is roles plus instructions. Agent workflow is contracts plus hops. The method
deliberately prioritizes the workflow, and the reason is the most interesting hypothesis in
the paper: task-specific contracts specify what a downstream agent needs, so it does not
have to condition on the entire interaction history. Restricting inter-agent communication
is a sparsity pattern over information flow. Less redundant context, less KV-cache traffic,
lower cost.

The analogy in the paper is sparse attention, and it is a good one. A fully shared history
is dense all-to-all attention. A contract is a learned sparsity mask, chosen per task.

### The algorithm

RHI does not search a population. It compares the current harness against its immediate
predecessor, one step at a time.

```
H(0)  = initial harness, written by a human for a task family
y(0)  = agent(H(0), task)

for i = 1, 2, ... :
    y(i)     = agent(H(i), task)
    pref(i)  = judge(y(i), y(i-1))          # pairwise, three outcomes
    history  = history + pref(i)
    rate     = mean(pref(i) == win) across tasks
    if rate < epsilon: break
    H(i+1)   = optimizer(H(i), history)     # optimizer never sees the rubric
```

Three details carry the method.

**Pairwise, not scalar.** The judge compares two outputs. There is no absolute score, which
means no calibration across runs and no invented number. For open-ended work where the
output is a whole repository, this is more honest than a rubric score, and much cheaper
than running a full test suite.

**Local competitor.** The comparison is against the previous harness, not against a
population. That is a deliberate change of the objective: from "beat arbitrary harnesses" to
"beat my own last version". The paper is explicit that this is a relaxation, not an unbiased
estimator.

**History as momentum.** One pairwise judgment is noisy. Conditioning the update on the
whole preference chain is what lets the method converge in two or three iterations. The
paper calls it a momentum-semantic signal, which is the right metaphor: no gradient exists,
but a direction accumulates.

### Why it is cheap

This is the part worth copying even if you ignore the rest.

| Objective | Traces per iteration | Judgments per iteration | Cost |
| --- | --- | --- | --- |
| Compare against a full reference population | M | M choose 2 | Quadratic |
| Compare within a sampled population of size m | m | m choose 2 | Quadratic in m |
| Compare against the previous harness | 1 | 1 | Constant |

One agent execution and one judgment per iteration, given that previous outputs are cached.
Scaling to n tasks multiplies all three rows by n and changes nothing about the ordering.

That matters because of a finding the paper cites: once search cost is properly accounted
for, automatic harness evolution fails to consistently beat simple test-time scaling under a
fixed inference budget. The alternative to a cheap optimizer is often not a better optimizer.
It is just spending the same tokens on more attempts.

### What the numbers say

The benchmark is 30 synthetic open-ended ML research tasks across quantitative finance,
robotics, and pharmacy. Each task asks for a complete repository with standard deliverables.
Judging is pairwise, by LLM, averaged over two judges and three seeds.

| Base model | Iterations | Result | Cost change |
| --- | --- | --- | --- |
| Sonnet 4.6 high | 2 | Beats Sonnet 4.6 max, 20 wins of 30 | 7 percent lower than max |
| Opus 4.7 high | 1 | Beats both xhigh and max | 18 percent lower than max |
| Opus 4.8 high | 2 | Beats xhigh, ultracode and max | 23 percent lower than max, 60 percent lower than ultracode |

The headline claim is that a few iterations of prompt-level harness work raises the ceiling
that test-time scaling saturates at. The most surprising result is the last row: a
user-written prompt beat a provider-built dynamic workflow that can spawn subagents. That is
an argument that one fixed system-level harness cannot cover a heterogeneous task
distribution, and that per-task specialization has real headroom.

Cache traffic tells the mechanism story:

| Base model | Cache read/write, before to after | Reduction |
| --- | --- | --- |
| Sonnet 4.6 | 4.91 to 3.31 | 33 percent |
| Opus 4.7 | 3.37 to 2.11 | 37 percent |
| Opus 4.8 | 2.51 to 1.69 | 32 percent |

Output tokens stayed roughly flat while performance rose: 1.71 to 1.86 for Sonnet, 1.42 to
1.81 for Opus 4.8. For Opus 4.7 the evidence was inconclusive because both rose together.
So for two of three models the gain is not "more thinking". It is better context
management, visible as less cache traffic.

The component analysis supports that reading. Embedding the harness components and measuring
how they cluster by task, contracts separate most clearly, then hops and instructions, with
roles least separable. Contracts also stabilize fastest: consecutive similarity rises
0.48, 0.66, 0.69, 0.72, while roles crawl from 0.28 to 0.31. The optimizer figures out what
should be communicated before it figures out who should exist.

### The information-theoretic hypothesis

The paper does not claim to know RHI's true objective. It offers a hypothesis that fits the
observations: the loop increases mutual information between task-specific components and the
task, while penalizing redundancy across components.

In words: make each harness component informative about the task, and make the components
informative about different things. The second term is what stops a degenerate solution
where every component restates the task description. Roles define expertise, instructions
define behavior, contracts define what to communicate, hops define control flow. Specialize
or waste context.

Treat this as a lens, not a law. The paper labels it a hypothesis and the analysis is
correlational, on embeddings, over a black-box agent.

### Where RHI is weak

Be clear-eyed, because you are about to copy it.

- **No elitism.** The update is `H(i+1) = optimizer(H(i), history)` unconditionally. If the
  optimizer proposes something worse, nothing in the algorithm keeps the incumbent. The
  paper says losing revisions are "discarded or revised", but the pseudocode does not
  enforce a keep-the-best rule. Add one. EVO's keep-or-revert is not ceremony.
- **One trajectory.** No branches, no archive, no diversity pressure. The branching paper
  exists because of exactly this.
- **Judge dependence.** The signal is an LLM preference. It carries the judge's priors,
  including a known positivity bias toward LLM output. Two judges and three seeds help but
  do not remove it.
- **Synthetic tasks.** Thirty generated ML research tasks are a controlled setting. Whether
  the same loop specializes well on a messy enterprise repository is untested.
- **Does not replace a better model.** RHI-improved Sonnet does not consistently close the
  gap to plain Opus. It raises the ceiling of one model family, not the ceiling of models.

## Branching search: recursion without collapse

If RHI is a single climber on a hill, the branching paper is a small expedition with a map
and a dispatcher.

### The problem it solves

Meta-Harness, the baseline, runs an agentic proposer against a fixed development set with
fixed proposal instructions. That has two consequences.

First, the development set decides the search forever. If a candidate solves cases that the
current leader misses but does worse on average, it ranks low and gets dropped. Capabilities
that are not yet good are never developed, because they never win.

Second, proposal instructions do not adapt. The proposer keeps getting the same guidance
even after the search has revealed which mechanisms work and which repeatedly fail.

Both effects push toward one basin. Search converges confidently on a local optimum, and the
final harness is the best version of one idea rather than a portfolio of two.

### The mechanism

Split the search into branches. In the experiments, two branches, twenty iterations each,
frontier size five, ownership margin two.

Each branch has its own development subset, its own candidate history, and its own proposal
guidance document. Every iteration:

1. The branch's proposer reads its candidate history and filesystem, and proposes a new
   harness.
2. The harness is evaluated on the branch's current development subset.
3. Periodically, a coverage vote runs across branch frontiers. For each development case,
   count how many harnesses in each branch's top five solve it.
4. If every frontier in every branch solves a case, delete it. It teaches nothing.
5. If one branch's coverage exceeds the best other branch by the margin, that branch owns the
   case and it is removed from the others.
6. Periodically, each branch rewrites its own proposal guidance from its own recent history:
   what worked, what repeatedly failed, what is still unresolved.

The pruning rule is the clever part. It is not clustering by task category, which requires
someone to define categories. It is ownership by demonstrated relative advantage. A branch
keeps the cases it is uniquely good at, and those cases become its objective. Different
objectives produce different harnesses, without anyone writing a taxonomy.

The guidance update is the second half. A branch that has learned "extract concrete
information from retrieved solutions" keeps pursuing that, while the other branch, having
learned "restructure the derivation", pursues something else. Same proposer, different local
memory, divergent priorities.

### The router

Now you have two or more specialized harnesses and no way to compare their scores, because
they were measured on different subsets. That is the deployment problem.

The answer is to route per input. Development cases solved by exactly one final branch head
become labeled examples, with the successful head as the label. A router prompt is fitted on
those examples, using GEPA, and at deployment it picks a head before execution. It sees the
problem and the harness source, not the outputs, and definitely not whether the outputs were
correct.

### The numbers

Held-out performance, with all selection done on development data:

| Setting | Model | Baseline harness | Meta-Harness | Branches plus router |
| --- | --- | --- | --- | --- |
| Olympiad math | Gemini 3 Flash | 46.5 | 46.0 | 62.0 |
| Olympiad math | Sonnet 4.5 | 27.0 | 29.0 | 30.5 |
| Terminal-Bench 2.0 | Sonnet 4.5 | 43.1 | 44.8 | 50.0 |
| SWE-bench Lite | Sonnet 4.5 | 62.8 | 63.6 | 66.0 |

Relative gains over Meta-Harness: 34.8 percent on math with Gemini, 5.2 percent on math with
Sonnet, 11.6 percent on Terminal-Bench, 3.8 percent on SWE-bench Lite.

Per-head results are more instructive than the router number:

| Configuration | Math Gemini | Math Sonnet | Terminal-Bench | SWE-bench Lite |
| --- | --- | --- | --- | --- |
| Head 1 only | 56.0 | 26.0 | 44.8 | 65.6 |
| Head 2 only | 58.0 | 31.0 | 48.3 | 66.4 |
| Routed | 62.0 | 30.5 | 50.0 | 66.0 |

The router beats the stronger head on two settings and loses by one case on the other two.
Combined coverage, meaning at least one head solves it, is 4 to 9 points above the stronger
head. The router captures about three quarters of that oracle gap, so there is a real but
bounded benefit to having complementary experts.

Ablations, on math with Gemini:

| Component | Accuracy |
| --- | --- |
| Neither pruning nor guidance updates | 51.0 |
| Guidance updates only | 50.0 |
| Development pruning only | 54.0 |
| Both | 62.0 |

Pruning is what helps. Guidance updates alone do nothing, and only pay off once the branches
have different objectives to reason about. That is a genuinely useful negative result: do not
build the adaptive prompt machinery before you have divergent objectives.

Update frequency also matters: every five iterations gives 53.0, every three gives 56.0,
every iteration gives 62.0. Fast feedback on which branch is winning which cases is worth
more than a stable objective.

### Where the branching paper is weak

The authors are unusually honest, and the honesty is worth repeating:

- **Unequal token budgets.** The branched system spends more total tokens than the baseline,
  so part of the gain is more search, not better search. The paper says this limits
  efficiency conclusions.
- **Shared cases between search and test.** The baseline's own numbers move when you select
  on test data. Meta-Harness goes from 46.0 to 49.0 on math if you allow test-based selection
  among its ten candidates. That is the optimism gap, and it is why the paper reports
  development-selected numbers as the headline.
- **Causality.** The ablations support the combination but do not prove each trajectory
  change caused the later gain.
- **Router shortfall.** Routing is still 4.4 to 5.5 points below combined coverage, so some
  complementarity is left on the table.

## InfraRSI: recursion under a locked contract

The first two papers optimize what agents say to each other. InfraRSI optimizes what the
machine does, and it is the hardest of the three because the domain punishes optimism.

Training throughput depends on launch knobs, kernels, and communication schedules that
interact non-linearly. A change that helps on one GPU generation hurts on another. Memory
limits create cliffs where two individually good changes cannot coexist. Timing noise spans
two orders of magnitude. And the whole thing is an obvious target for cheating, because
"faster" is trivially fake if you move work outside the measurement window.

### The five stages

| Stage | What it does |
| --- | --- |
| `init` | Parses the repository, declares editable files, pins SHA-256 digests of frozen files: data loaders, evaluation scripts, loss definitions, timers |
| `doctor` | Runs the reference baseline, trims warmup, calibrates pairwise step-time noise, profiles phase breakdown, probes interconnect bandwidth, grades prior coverage |
| `run` | Runs the budgeted compositional search, records receipts and full cost, re-verifies top candidates back to back, writes experience packs |
| `report` | Renders the campaign report, invariant verdicts and resource accounting for source auditing |
| `apply` | Reads the promoted candidate, checks for working-tree conflicts, writes the launch config and source diffs |

Notice what `init` is really doing. It is not configuration. It is the boundary of the
search: which files the agent may edit, and which files are frozen and hashed. Everything
else depends on that boundary holding. A self-improving system with an editable evaluator is
not a search, it is a story.

### The contract: 16 invariants in 5 layers

The objective is maximization of log speedup subject to boolean constraints:

```
maximize  y(a) = ln(T0 / T(a))
subject to I_k(a) = True for k = 1..16
```

| Layer | Invariants | Core check |
| --- | --- | --- |
| L1 execution | 3 | Exit 0, full update count, no NaN, OOM, NCCL or import error, VRAM within cap |
| L2 workload | 4 | Same tokens per update, same sequence length, data digest, model digest and parameter count, frozen-file hashes |
| L3 schedule | 1 | Same optimizer step count, auxiliary state updated synchronously inside the timed window |
| L4 numerical | 3 | Pre-declared loss rule, gradient norm bound, permitted precision menu |
| L5 timing and pair | 2 | Harness wall clock agrees with reported step time, promotion requires a fresh back-to-back re-run beyond calibrated noise |

The audit over 1,212 stored executions is the part to read twice. Four hundred were rejected,
33.0 percent, with 710 total trigger events. Thirty-nine of those, 3.2 percent, passed every
non-numerical check and were caught only by the numerical layer. That is the shape of a
useful verifier: the cheap layers catch most of it, and the expensive layer catches the
residue that would otherwise look perfect.

A unit suite of 40 system tests, 28 perturbed and 12 benign, reproduces 40 of 40 expected
verdicts. Perturbations include halved token counts, wrong sequence length, missing steps, an
edited learning-rate schedule, altered data order, early exit with status zero, frozen loss,
memory-cap violation, edited frozen files, clock skew, and a mismatched model digest. Each of
those is a real way an agent has faked a speedup.

### The four failure modes it defends against

**Reward hacking and timing skew.** Unauthorized low-precision casts, deferred auxiliary
updates pushed past the timing window, timer shifts that inflate reported speed relative to
wall clock, and aggressive kernel fusions that quietly degrade loss. The defense is the
contract plus source-path auditing: a human or a reviewer model reads the diff of every
promoted candidate, not just its receipts.

**Wide-spectrum noise.** Paired step-time noise ranges from 0.04 to 0.10 percent on dedicated
8xH100 and 8xH200 nodes to over 6 percent on shared hosts. A fixed 2 percent gate is too
coarse on a quiet node, where it discards valid 0.5 to 1.5 percent gains that compound when
stacked, and too fine on a noisy host, where it promotes jitter. The defense is calibration:
measure the noise on this cluster, then gate at `max(0.02, 2 * sigma_pair)`, and require a
fresh re-run to clear `exp(2 * sigma_pair) - 1` before promotion.

**Miscalibrated LLM priors.** Zero-shot speedup predictions correlate negatively with
measured hardware performance, with Spearman rank correlation between -0.49 and -0.06. The
memorable examples: graph compilation predicted at plus 2.0 percent and measured at plus 55
percent on Gemma-4-26B-A4B; extra NCCL channels predicted to slow things down and measured at
plus 10.2 percent on two-node Qwen3.5-35B-A3B. A prior that confidently vetoes the best
options is worse than no prior, so the design includes contrarian probing of high-uncertainty
high-impact settings and explicit prior revision from measurements.

**Single-incumbent myopia.** Greedy search dies at memory and compiler cliffs. On
Gemma-4-26B-A4B, turning off activation recomputation needs 18 GiB more memory than exists,
and turning on torch.compile hangs with the default fused kernels. Either change alone is
infeasible. Together with disabling Liger, which frees 14 GiB, and a FlexAttention patch, the
combination reaches 2.75x. No greedy loop finds that, because every intermediate state is
invalid.

### Budgeted compositional search

The search controller has five moving parts, and each maps to a failure above.

**Multi-start initialization.** The first three full trials are deliberately different: a
warm start from the most similar verified configuration in the experience bank, a second
start that differs in at least one high-impact knob, and a uniform random legal configuration
to anchor variance. In the Qwen3.5-9B run, the experience-seeded start hit 1.55x on trial 1.

**Global time and memory models.** A Cholesky Bayesian linear model over log speedup, fitted
across all trials with indicator features for knob settings, verified patches, and pairs. In
parallel, a right-censored Tobit model for peak memory, where OOM trials are not discarded but
treated as lower bounds. That is the trick that makes memory cliffs navigable: a crash is
information, not a dead end.

**Prior calibration.** Empirical Bayes shrinkage on knob priors, a conservative discount on
LLM patch predictions, and contrarian probes scheduled whenever a high-impact lever is rated
low but has a two-sigma upside that clears the noise gate.

**Failure attribution and bundle completion.** OOM is tagged with a required memory-saving
partner covering at least the measured shortfall. Non-memory crashes ban only the minimal
conflicting tuple, keeping individual settings eligible elsewhere. Patch failures are blamed
on the patch, not the configuration.

**Big-knob escape.** The search partitions settings into those whose single-knob log effect
clears the noise gate and those that do not, and runs all structural exploration over the
former. After two failed improvements, it forces a leap of one to three big knobs, does tabu
filtering on visited signatures, and periodically warm-restarts from a different
configuration class.

Context stays bounded by summarizing older trials into single-line records of about 28k
characters while keeping full traces for the fastest and most recent runs.

### The two-level loop

This is the actual RSI structure, and it is worth naming precisely because most write-ups
blur it.

- **Level one, within a run:** priors are revised online from every measurement, including
  failures. The search learns about this cluster while it runs.
- **Level two, across runs:** verified findings are distilled into an experience bank with
  normalized environment, observation, and effect records. Eleven seed packs covering 191
  environments, 698 observations, 543 effects and 71 canonical mechanisms. New runs warm
  start from it.

The cross-hardware result is the payoff: on Qwen3.5-9B with 8xH100, cross-SKU transfer lifts
final speedup from 1.70x to 1.82x and is the only condition that reaches 90 percent of peak
within budget, at trial 9 and 2.97 GPU-hours. Cold start and all-packs were censored past 15
and 17 trials respectively.

The reason naive transfer fails is also documented. Effects flip sign across hardware:

| Mechanism | H20 | H100 or H200 | Cause |
| --- | --- | --- | --- |
| FP8 precision | +58 percent | +30 percent on H200 | Compute-bound versus comm-bound |
| Tensor parallel 2 | +24 percent | -4 percent on H100 | AllReduce exceeds GEMM gain |
| FP8 attention | +6 percent | -8 percent on H200 | BF16 FlashAttention-3 wins |
| Graph compilation | +20 to 29 percent | +5 to 10 percent | Launch amortization versus collective fusion |

So the bank stores effects conditioned on roofline, not bare numbers. Environment, observation
and effect are separate records, and retrieval filters by compatibility before ranking by
similarity.

### Results

| Workload and hardware | Base MFU | Best baseline | InfraRSI |
| --- | --- | --- | --- |
| Qwen3.5-9B, 8xH100 | 25.3 | 1.62x, RE-Bench | 1.73x, 43.8 percent MFU |
| Gemma-4-26B-A4B MoE, 8xH200 | 6.4 | 1.33x, RE-Bench | 2.75x, 17.6 percent MFU |
| Qwen3.8-27B, 8xH200 | 29.3 | 1.39x, Auto-Research | 1.55x, 45.4 percent MFU |
| Qwen3.5-35B-A3B MoE, 16xH100 | 8.7 | 1.17x | 1.51x, 13.2 percent MFU |
| Geometric mean over four | 17.4 | 1.37x | 1.83x, 30.0 percent MFU |

The tolerance ablation is the most reassuring table in the paper, because it shows the result
is not a knife-edge artifact of one threshold. Across relative loss tolerances of 0.10, 3.00
and 50.00 percent, and a fixed 2.00 percent noise floor, all four arms converge to between
1.70x and 1.75x within 10 to 11 trials.

### Where InfraRSI is weak

- **Expensive.** This is tens of GPU-hours per campaign, not minutes. The economics only work
  because a few percent of a large training cluster is worth a lot.
- **Narrow domain.** The invariants are training-specific: tokens per update, loss tolerance,
  precision menu. Porting the pattern to product code means inventing a different invariant
  set, and that is the hard part.
- **Residual source audit.** Layer 3 caught zero offenders offline; the deferred-update cheat
  was caught by human source review. Automated verification is necessary, not sufficient.
- **Single-team results.** Four workloads from one group, on hardware they control. Treat the
  numbers as an existence proof, not a benchmark you can expect to match.

## The RSI tax: recursion that costs more than it delivers

The three papers above report accuracy. None of them reports what the loop cost to run, in
the same units as the task it was supposed to improve. This paper does, and it produces the
least comfortable number of the year.

The finding, in one line: **for three of the five adaptive methods, and for every method that
revises the harness itself, the cost of improving the agent exceeded the cost of running it.**

### The setup

Six methods, two models, two benchmarks, four settings, 2,328 scored method-task pairs.

| Method | What it updates | Update cadence |
| --- | --- | --- |
| Static | Nothing | Never |
| ReasoningBank | A memory of extracted strategies | Per task, with retrieval |
| Meta-Harness | Controller code | Every four tasks |
| EvoSkill | Reusable skill folders | Every four tasks |
| RRSI | Harness, with a regularizer against benchmark-specific edits | Every four tasks |
| SRN | A single bounded note | Every four tasks, failures only |

Two protocol details carry the whole design.

**Each task is scored before its own feedback is used.** The outcome is recorded, then the
update happens. That turns the experiment from a training run into a deployment simulation,
which is the only version of the question that matters if you are paying the bill.

**Re-execution is charged, and it does not replace the original outcome.** When a method
re-runs a completed task to validate a candidate, those tokens go on the RSI bill, and the
task keeps its first score. That single accounting rule is what makes the comparison honest,
and it is the rule most published evaluations quietly skip.

The streams are 105 repository positions from SWE-Chain-Evo (seven chains of fifteen, state
reset between chains) and 89 Terminal-Bench 2.1 tasks in a fixed order. The models are
DeepSeek V4.1 Flash and GPT-6 Luna.

### The metric

```
N_task = tokens spent executing arriving tasks
N_RSI  = tokens spent improving the agent, whether or not the update was adopted
tax    = N_RSI / N_task
```

A tax of 100 percent means the loop costs as much as the work. The tax accounts for
`tax / (1 + tax)` of total spend, so a 300 percent tax means three quarters of your budget
went into improving the thing that does the work.

The tax decomposes into three operations, and the split is where the design advice lives.

| Operation | What it covers |
| --- | --- |
| Verify | Running the incumbent or a candidate on completed support tasks to inform selection: baselines, smoke tests, frontier re-evaluation |
| Explore | Extra rollouts, proposal generation without edits, trajectory judging, embedding calls |
| Write | Creating or revising persistent state: harness code, skills, notes, memories |

The paper also labels each cost by whether the state or artifact it produced was **used in a
later task** before the next reset. That label is descriptive, not causal, and the paper says
so. It is still the most useful diagnostic in the paper, because it separates "expensive and
load-bearing" from "expensive and forgotten".

### The numbers

Accuracy in percent, total tokens in millions, where total includes both task execution and
the tax.

| Method | DeepSeek, SWE | GPT-6 Luna, SWE | DeepSeek, terminal | GPT-6 Luna, terminal |
| --- | --- | --- | --- | --- |
| Static | 43.8 / 487.92 | 38.1 / 179.69 | 69.7 / 185.55 | 66.3 / 78.86 |
| ReasoningBank | 40.0 / 520.64 | 37.1 / 191.21 | 69.7 / 198.87 | 67.4 / 85.46 |
| Meta-Harness | 45.7 / 976.61 | 40.0 / 495.81 | 77.5 / 762.57 | 65.2 / 317.99 |
| EvoSkill | 41.0 / 1,166.51 | 40.0 / 612.39 | 71.9 / 898.72 | 68.5 / 358.85 |
| RRSI | 44.8 / 1,092.94 | 39.0 / 574.07 | 74.2 / 605.75 | 61.8 / 454.30 |
| SRN | 48.6 / 492.56 | 41.0 / 157.07 | 78.7 / 214.65 | 68.5 / 87.08 |

Read the last row twice. A note capped at 2,048 tokens, revised only from failed tasks every
four tasks, with no extra sampling, no candidate validation and no retrieval search, has the
highest observed accuracy in three of four settings and ties the best in the fourth. It also
uses fewer total tokens than Meta-Harness, EvoSkill and RRSI in every setting.

Relative to Static, SRN gains 4.7 points of mean accuracy for 3.6 percent more tokens. Relative
to the three expensive methods it saves 65.6, 71.0 and 68.2 percent of mean total tokens,
weighted equally across settings.

### Where the money goes

The tax rate is the number to remember.

| Method | DeepSeek, SWE | GPT-6 Luna, SWE | DeepSeek, terminal | GPT-6 Luna, terminal |
| --- | --- | --- | --- | --- |
| ReasoningBank | 4.78 | 5.96 | 4.53 | 7.39 |
| Meta-Harness | 109.06 | 177.35 | 314.16 | 329.15 |
| EvoSkill | 144.35 | 213.21 | 393.10 | 358.57 |
| RRSI | 125.79 | 213.02 | 223.23 | 346.68 |
| SRN | 0.04 | 0.25 | 0.13 | 0.36 |

Three of the five methods exceed 100 percent in all four settings. Meta-Harness and EvoSkill
exceed 300 percent on the terminal stream. SRN never reaches one half of one percent.

The decomposition says why. Verification, meaning re-running the agent on tasks it has
already seen, is 74.8 percent of Meta-Harness's tax, 78.1 percent of EvoSkill's and 93.6
percent of RRSI's. The search is not the expensive part. **Checking the search is.**

The sharpest single example: on the DeepSeek terminal stream, EvoSkill spends 497.45 million
tokens refreshing its existing skill frontier, against 182.26 million tokens serving the 89
arriving tasks. Re-evaluating programs it already had cost more than doing the work, before
any new rollout or new-skill validation. For comparison, EvoSkill spends 4.59 million tokens
on actually materializing skills. The ratio between deciding and writing is over one hundred
to one.

Then there is the waste. The share of the tax attached to state or artifacts that were never
used in a later task:

| Method | Unused share of tax |
| --- | --- |
| Meta-Harness | 52.78 |
| EvoSkill | 37.91 |
| ReasoningBank | 63.57 |
| RRSI | 23.70 |
| SRN | 0.00 |

Between a quarter and two thirds of a typical RSI budget pays for candidates that are then
ignored. Meta-Harness's unused share is 564.85 million verification tokens, 217.60 million
exploration tokens and 69.22 million writing tokens. ReasoningBank's is split almost evenly
between judging and memory extraction, which is a different disease with the same symptom.

### The reversal that makes the point

On the DeepSeek terminal stream, Meta-Harness uses fewer task-execution tokens than SRN:
184.13 million against 214.37 million. If you report execution cost, Meta-Harness looks
cheaper.

Add the tax and the comparison inverts. Meta-Harness carries a 578.45 million RSI tax for a
total of 762.57 million. SRN totals 214.65 million. And Meta-Harness scores slightly lower:
77.5 against 78.7 percent.

That is the argument in one comparison. A method that is cheaper per task and more expensive
per outcome, reported in a way that hides it.

### What this changes in a design

Five rules, all of them cheap to adopt.

**Report tax, not just accuracy.** If a paper reports accuracy on a task stream without the
update cost, you cannot tell whether the method pays. Assume it does not until shown
otherwise.

**Budget verification first.** Verification is three quarters of the tax in every measured
method. Cache the baseline runs, subsample the support set, reuse the frontier scores you
already have, and stop re-validating candidates that lost on the same evidence.

**Bounded state is a feature.** SRN is not a strawman. It is a working hypothesis that most
of the value of experience fits in a small, durable, human-readable summary of what went
wrong. Before you build a harness search, check whether the note gets you most of the way.
The paper's own framing is that it provides a counterexample to the need for a costly update
procedure, not that it dominates on every axis.

**Compare against more attempts, not against nothing.** The correct counterfactual for a
search budget is spending the same tokens on more tries at the task. SRN versus Static is
that comparison in miniature, and it is the reason the tax matters: the tax is spend that
does not produce a task attempt.

**Charge the unused.** The unused-artifact share is the cheapest available diagnostic. If
half your updates are never read, your proposal distribution is wrong, your support set is
stale, or your gate is admitting things nobody uses.

### Where the tax paper is weak

- **Two models, one task ordering.** The authors say this themselves. Ordering effects on a
  terminal benchmark with no environmental drift are untested.
- **Attribution is descriptive.** Use in a later task does not prove the tokens bought
  accuracy, and absence of use does not prove the tokens were removable without changing
  later updates. Controlled ablations are future work.
- **No adaptive policy.** The paper compares fixed procedures and realized costs. It does not
  evaluate a controller that forecasts the tax and chooses whether to update, which is the
  obvious next experiment.
- **Tokens, not dollars.** Input and output tokens are summed. A verification run and a
  proposal run can differ in price per token by an order of magnitude.
- **SRN is a baseline, not a method.** The experiment does not isolate which of its choices
  (bounded note, failures only, four-task cadence) matters. It only shows the combination is
  competitive.

## TRUST: recursion with a statistical gate

RHI has no gate: the last iteration wins. The branching paper has an implicit gate: selection
on development data. InfraRSI has a gate made of boolean invariants, which is cheap and
exact, and useless for the question "is this candidate actually better".

None of them answers the question you face on the first day of a real loop. Given a few
hundred validation tasks, a candidate that scored 2 points higher than the incumbent, and
thirty revisions ahead of you, **how often will that gate accept a change that is actually
worse?**

TRUST answers it, with a guarantee.

### Split the system before you test it

The paper's framing is worth copying even if you ignore the statistics. Separate three things:

| Part | Job | Tested how |
| --- | --- | --- |
| Solver | Runs the task under the current harness | Held-out score |
| Proposer | Generates the candidate revision | Acceptance rate, novelty |
| Gate | Decides whether the candidate replaces the incumbent | False evolution rate |

The gate is where the safety property lives, and it is the only part that can be evaluated
independently of the other two. That is why this paper can make a claim about a whole class
of loops: the claim is about the gate, not about the harness.

### False evolution rate

Define the true population difference between candidate and incumbent as `delta`. Pick a
tolerance `epsilon`. Then a revision falls into one of three regions.

| Region | Meaning | Label |
| --- | --- | --- |
| `delta <= -epsilon` | Unacceptably worse | False evolution |
| `-epsilon < delta <= 0` | Worse, but inside tolerance | Tolerated |
| `delta > 0` | Genuinely better | True evolution |

The false evolution rate is the expected proportion of accepted updates that land in the
first region.

```
FER(T) = E[ (number of accepted updates with delta <= -epsilon) / max(1, number accepted) ]
```

Two things make this the right criterion rather than a convenience.

**It is a proportion of accepts, not of proposals.** A gate that accepts almost nothing can
have a low FER trivially. That is a real failure mode, and the paper demonstrates it (more
below).

**It has a tolerance.** Demanding proof that a candidate is at least as good is hopeless with
limited samples, and the theory shows it: at `epsilon = 0`, the admissible betting fraction
range collapses and the power result does not go through. A small declared tolerance is what
buys statistical power. That is a design decision, not a fudge, and it should be written down
before the first run.

### The five mechanisms

| Mechanism | What it does | Parameter |
| --- | --- | --- |
| Noninferiority | Tests against `-epsilon` instead of zero, so a small loss is allowed | `epsilon` |
| E-value testing | Accumulates evidence as a nonnegative martingale, valid at any stopping time | betting fraction |
| Overlap correction | Discounts evidence when validation samples have been seen before, weighted by exposure probability | `beta` |
| Level allocation | Spends a fixed error budget `q` across rounds, e-LOND style inside e-GAI | `q` |
| LLM allocator | Reads the candidate and prior feedback, adjusts the spending fraction within bounds | `rho_min`, `rho_max` |

The overlap correction is the piece most practitioners get wrong without noticing. Rounds
reuse the same validation pool, the proposer sees feedback from previous rounds, and the
estimates become optimistic. That is adaptive data analysis, and it is the same problem the
reusable holdout was invented for. TRUST models the correction as an allowance `beta`,
weighted by the probability that a given draw was actually exposed before.

The LLM allocator is the piece that sounds like a violation of the whole premise. It is not,
and the reason is important: **the safety guarantee does not depend on the LLM being right.**
The allocator can only move the spending fraction within a bounded range. A bad judgment
makes the loop less efficient, not less safe. That is the correct way to add a model to a
verification path, and it generalizes well beyond this paper.

### The algorithm

```
B = q                                  # remaining error budget
for each round t:
    rho = clamp(LLM(context) * 1/(T-t+1), rho_min, rho_max)
    alpha = allocate(B, rho, accepts_so_far)
    for m = 1..n:                      # sequential test on validation draws
        M = e_value(observations[1..m], beta)   # with overlap correction
        if M >= 1/alpha: accept; break
    else: keep the incumbent
    B = charge(B, alpha)
```

Three properties follow, under stated assumptions.

| Result | Statement |
| --- | --- |
| FER control | `FER(T) <= q` for the whole process, and at any stopping time |
| Power consistency | True evolution rate goes to 1 as validation and pool sizes grow |
| Gain lower bound | Final deployment gain is bounded below in terms of miss probability and tolerance |

The stopping-time part matters operationally: you may stop the campaign early based on what
you have seen, and the guarantee survives. That is exactly what a stop rule needs and almost
never has.

### The numbers

30 rounds, 5 seeds, 200 validation examples, 300 held-out test examples. `q = 0.30`,
`epsilon = 0.10`, `beta = 0.01`. Gain in points, FER0 counting all accepted non-improving
updates, MDD as maximum drawdown in points.

| Dataset | Model | Greedy gain | Greedy FER0 | TRUST gain | TRUST FER0 | TRUST MDD |
| --- | --- | --- | --- | --- | --- | --- |
| HotpotQA | DeepSeek | 7.87 | 64.67 | 11.58 | 10.00 | 0.02 |
| HotpotQA | Qwen | 20.66 | 44.67 | 27.72 | 0.00 | 0.00 |
| DROP | DeepSeek | 36.24 | 35.28 | 31.47 | 0.00 | 0.00 |
| DROP | Qwen | 15.15 | 37.38 | 17.22 | 0.00 | 0.00 |
| APPS | DeepSeek | 33.89 | 41.08 | 34.55 | 0.00 | 0.00 |
| APPS | Qwen | 28.03 | 50.44 | 26.53 | 6.67 | 0.27 |

Averaged over the six settings: FER0 falls from 45.59 to 2.78 percent, maximum drawdown from
4.963 to 0.047 points, and mean final gain is the highest of any method at 24.84 points.
Greedy's worst drawdown is 8.48 points. TRUST's worst is 0.27.

The trajectory shape is the part that explains the mechanism. Greedy climbs fast and then
declines, because it keeps accepting noise and building on it. TRUST climbs slower, overtakes
greedy in later rounds, and keeps what it has.

### The gate that is too strict

The paper's most useful negative result is not about greedy. It is about the conservative
baselines.

SGM-B, which controls the familywise error rate across rounds with a Bernstein test, **never
accepts an update in any setting**. SGM-H accepts three updates across all runs. Both are
technically safe and practically useless: a gate that never opens has an FER of zero and a
gain of zero.

That is the counterweight to every "just be more conservative" instinct. Safety and power are
two axes, and the whole point of an error budget is to spend it, not hoard it. PACE, which
controls false acceptance within a single round, sits between: zero FER0 in five of six
settings, but gains of 10.15, 26.42, 29.70, 13.22, 28.68 and 26.24, which is below TRUST's
final score in all six.

### Sensitivity

On HotpotQA with DeepSeek: raising `beta` from 0 to 0.03 takes FER0 from 23.33 percent to
zero, and final gain peaks at 11.58 points at `beta = 0.01` against 10.97 with no correction.
So a moderate correction both improves safety and improves gain, which is not the usual
trade-off shape. Larger `q` and `epsilon` make the gate more aggressive, raising both TER and
FER0, which is what the definitions predict.

### The EVO reading

This is the Must layer with a budget attached, and the most rigorous version of E5 and E6 in
the whole literature.

- **The gate is a measured component.** You would never ship a cache without a hit-rate
  meter. TRUST says the same about your accept rule: measure its false acceptance rate, and
  give it an error budget.
- **Declare the tolerance.** `epsilon` is a Must-with-tolerance: an explicit statement of how
  much regression the business will absorb per revision. That is a Plan-level number and it
  belongs in the revision card.
- **Declare the budget.** `q` is the fraction of accepted revisions you are willing to have
  been wrong about. Thirty percent is loose for a product harness, and it is set that way to
  give a weak proposer room to move. Write yours down, then tighten it as the proposer
  improves.
- **The stopping rule is now sound.** The earlier stop rule in this page ("two consecutive
  flat revisions") is a heuristic. A sequential test with a stopping-time guarantee is the
  principled version, and it is not much harder to implement.

### Where TRUST is weak

- **Small validation pools.** 200 examples, 30 rounds. The guarantee holds, but the power is
  limited by the data, and most teams have less validation data than this, not more.
- **The proposer assumption.** Power requires that the proposer eventually proposes a real
  improvement. In a domain where the harness is already near its ceiling, the gate correctly
  accepts almost nothing, and the guarantee tells you nothing about whether to keep looking.
- **The guarantee is about the accept set.** It bounds the proportion of accepted updates
  that were bad. It does not bound how much good you left on the table, and it does not make
  the final harness good in absolute terms.
- **No cost accounting.** The tax paper's lesson is not incorporated: verification here is
  free in the analysis and expensive in reality, and sequential testing changes how much
  verification you buy.
- **Three benchmarks, two models.** QA and code, both with clean validation sets. A flaky
  enterprise suite violates the exchangeability assumptions in ways the paper does not test.
- **`q = 0.30` is a loose budget.** A thirty percent false acceptance rate is defensible for
  a research loop and indefensible for a production harness. The paper's own results show the
  method works at much lower empirical FER0, so the budget is conservative in practice, but
  the headline number should be read as a setting, not a recommendation.

## Beneath the Surface: recursion that moves tasks around

The third audit asks a question that sounds trivial and is not: when the score goes up, what
actually changed?

The answer, across four methods and sixteen evolved agents: **everything moved. Tasks were
gained and tasks were lost, in every single lineage.** The aggregate score is a net figure
that hides a gross flow.

### The setup

Four recipes, two harnesses, two benchmarks, sixteen lineages, one model (GPT-5.4).

| Factor | Levels |
| --- | --- |
| Method | AHE, HyperAgents (implementation-centric); A-Evolve, GEPA (reflection-centric) |
| Harness | MiniSWE 2.4.5 (source-editable), Codex 0.143.0 (outer-layer only: prompts, skills, config, orchestration) |
| Benchmark | tau3-Banking, 97 general tasks with simulated users; Terminal-Bench 2, 89 coding tasks |
| Protocol | 8 passes per task, train/validation/test split, evolution sees train and validation only |

Two metrics, and the distinction is the whole paper.

- **Reliability (Avg@8).** Mean success across eight passes. Does the agent succeed on
  average?
- **Coverage (Pass@8).** Fraction of tasks solved at least once in eight passes. Can the
  agent solve it at all?

A single-pass evaluation cannot tell these apart, and most reported numbers are single-pass.
That is not a minor methodological quibble. It is the difference between "this harness is
better" and "this harness is luckier".

### Reliability and coverage

Deltas in points against the matching seed.

| Benchmark | Harness | Method | Reliability | Coverage |
| --- | --- | --- | --- | --- |
| tau3-Banking | MiniSWE | AHE | +5.4 | +11.3 |
| tau3-Banking | MiniSWE | HyperAgents | +5.2 | +3.1 |
| tau3-Banking | MiniSWE | A-Evolve | -1.2 | +1.0 |
| tau3-Banking | MiniSWE | GEPA | +0.8 | +4.1 |
| tau3-Banking | Codex | AHE | +5.9 | +6.2 |
| tau3-Banking | Codex | HyperAgents | +6.6 | +9.3 |
| tau3-Banking | Codex | A-Evolve | -2.2 | +1.0 |
| tau3-Banking | Codex | GEPA | -0.8 | -3.1 |
| Terminal-Bench 2 | MiniSWE | AHE | +4.4 | +1.1 |
| Terminal-Bench 2 | MiniSWE | HyperAgents | +1.8 | -1.1 |
| Terminal-Bench 2 | MiniSWE | A-Evolve | +2.1 | 0.0 |
| Terminal-Bench 2 | MiniSWE | GEPA | +2.7 | +2.2 |
| Terminal-Bench 2 | Codex | AHE | +2.1 | +1.1 |
| Terminal-Bench 2 | Codex | HyperAgents | +2.7 | -3.4 |
| Terminal-Bench 2 | Codex | A-Evolve | -2.0 | -2.2 |
| Terminal-Bench 2 | Codex | GEPA | -1.8 | -3.4 |

Reliability improves in eleven of sixteen lineages, coverage in ten. Some move the two metrics
in opposite directions, and one improves reliability only. A paper that reported "average
improvement" would have averaged all of that into a single number and told you nothing.

### Turnover is the finding

Every one of the sixteen champions gained coverage on some tasks and lost coverage on others.
Some examples, as gained and lost task counts.

| Benchmark | Harness | Method | Gained | Lost |
| --- | --- | --- | --- | --- |
| tau3-Banking | MiniSWE | AHE | 15 | 4 |
| tau3-Banking | MiniSWE | HyperAgents | 13 | 10 |
| tau3-Banking | Codex | HyperAgents | 11 | 2 |
| Terminal-Bench 2 | MiniSWE | AHE | 4 | 3 |
| Terminal-Bench 2 | Codex | HyperAgents | 2 | 5 |

The HyperAgents row on tau3-Banking with MiniSWE is the case the abstract quotes: reliability
rose 5.2 points **while losing ten previously covered tasks**. Thirteen gained, ten lost, net
plus three coverage, plus five reliability. Every one of those ten losses is a user who used
to be served and now is not.

The behavioral audit of twenty-two selected task transitions says the differences are
concrete rather than mysterious. Gains cluster in state and dependency management (seven
increases, one decrease): preserving inputs, respecting action order, leaving a self-contained
executable result. Losses cluster in exact grounding (one increase, four decreases): matching
product conditions, dates, output characters. Two other categories, completion and handoff,
and tool discovery and recovery, split more evenly.

That is a testable claim about what evolution does. It tends to buy robustness in process and
pay for it with precision in detail.

### Cost

Eight of the eleven reliability-improving champions cost more per trial than their seed. The
three that got cheaper were all source-editable harness runs on coding tasks, where the
harness could remove work rather than add it.

Evolution cost ran from 723.4 million to 2,372.8 million tokens per campaign, against
deployment costs of 5.1 to 8.9 USD per task. On tau3-Banking with MiniSWE, AHE cost 1,235.0
million tokens of evolution to reach a champion, HyperAgents 867.0, A-Evolve 1,057.6 and GEPA
2,262.8. Recall from the tax paper that this is the same failure mode at a different scale:
the campaign is not free, and nobody reports it in the same table as the gain.

The cost picture has one genuine nuance. Per-trial cost and deployment efficiency can diverge,
because a better harness may need fewer attempts to reach a coverage target. MiniSWE with AHE
on tau3-Banking reaches 56.7 percent coverage in four passes, beating the seed's 54.6 percent
in eight, at lower total deployment cost. So "costs more per attempt" is not the same as
"costs more per outcome". Report both, and report the coverage target you are paying for.

### Generalization

Test reliability improves in ten of sixteen lineages, including seven of eight
implementation-centric cases across both harness types and both domains. Reflection-centric
gains are harness-dependent: most source-editable cases improve, and **all outer-layer-only
cases decline**.

External transfer is more selective still. Coverage falls for seven of eight champions on the
general-task target and rises for seven of eight on the coding target, across both harness
types and both paradigms. Reliability moves the other way: all source-editable champions
improve general-task transfer reliability and lose coding-task transfer reliability.

The pattern is coherent if you think about what a harness change encodes. A change that
encodes a task family's conventions transfers to a sibling family and hurts on a different
one. There is no such thing as general harness improvement, only improvement relative to a
distribution you did or did not name.

### The four operators

The paper then intervenes on the operators directly, which is the part that turns diagnosis
into design.

**Select: current score is a bad predictor.** Give each champion pool of four parents, let
each produce three candidates through the same analysis and mutation process, then ask which
parent produced the best candidates. The native selection rules beat random (25 percent) on
coding tasks at 59.5 and 55.7 percent, and fall **below** random on general tasks at 17.5 and
8.8 percent. Selecting the best current agent is actively counterproductive on tau3-Banking.

**Analyze: specific beats generic.** Fifteen of sixteen components outperform their matched
generic reminder, which is not a high bar: the generic reminders mostly do nothing. On tau3
with MiniSWE, a specific component takes reliability from 27.4 to 32.1 while the generic
reminder moves it to 27.8. On Terminal-Bench with Codex, the generic reminder *lowers*
reliability from 69.9 to 65.7. "Check your work carefully" is not a harness improvement.

**Mutate: combinations are not additive.** Six of eight champions beat either isolated
component, including all coding cases. Two general-task cases, one per harness, favor a
subset: the full champion is worse than one component alone. In one coding case only the
combination beats the seed. So components interact, in both directions, and the sign depends
on the harness.

**Gate: stricter admission is not uniformly better.** Adding a constraint (higher mean success
plus incumbent-relative regression at most 0.05) reduced best-candidate retention from fifteen
pools to six. Its size-normalized score fell for the source-editable harness and rose for the
outer-layer-only harness. A stricter gate is safer and loses candidates you wanted. That is
the same tension TRUST formalizes, arriving from the empirical side.

### AGE, the constructive follow-up

The authors do not stop at diagnosis. EvoAudit is an agent-assisted workflow that reads
archived evolution runs and proposes operator revisions with evidence and applicability
conditions. Installing four of those revisions into A-Evolve gives AGE: regression-aware
tie-breaking in select, behavior-grounded diagnosis in analyze, dependency-closed
mechanism-linked mutation, and a score-first cost-aware gate.

AGE beats every reference method on both harnesses in both benchmarks.

| Benchmark | Harness | Seed reliability | AGE reliability | Seed coverage | AGE coverage | Gained | Lost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tau3-Banking | MiniSWE | 27.4 | 34.0 | 54.6 | 66.0 | 13 | 2 |
| tau3-Banking | Codex | 30.3 | 38.1 | 56.7 | 67.0 | 15 | 5 |
| Terminal-Bench 2 | MiniSWE | 65.9 | 71.8 | 86.5 | 89.9 | 5 | 2 |

Note the last two columns. AGE gains fifteen tasks on tau3 with Codex and loses five. The
turnover does not disappear. What improves is the ratio: more gained per lost, and a
regression-aware tie-break that prefers the parent with fewer seed-relative regressions when
scores tie.

Eight domain experts reviewed the four operator revisions blind to the proposal: direction
agreement 6 of 8, evidence support 6.25 of 8, problem addressing 6.5 of 8, endorsement for
validation 6.75 of 8. That is a modest but real signal, and it is the kind of check that
should be standard before you install a proposed operator change.

### The EVO reading

This paper is E8 with a microscope, and it produces three rules that belong in any acceptance
gate.

**Report gross, not net.** Gained and lost tasks are separate metrics. A gate that only sees
the mean cannot see that it is trading your best customers for new ones.

**Reliability and coverage are different products.** Coverage is a capability claim. Reliability
is a service claim. A harness that solves a task one time in eight is not a 12.5 percent
capability, it is a support ticket.

**Preservation is a Must, not a preference.** The regression count belongs in the acceptance
rule, at the same level as the cost ceiling. AGE's select tie-break is the cheapest version:
among equally good candidates, prefer the one that regresses least.

### Where it is weak

- **Eight passes is expensive.** Ninety-seven tasks times eight passes times sixteen lineages is
  a serious evaluation budget, and it is the reason this study exists and the reason it will
  not be replicated often.
- **One model.** All sixteen lineages use GPT-5.4. A model that manages context better might
  shrink the harness effects, which is the RHI caveat all over again.
- **Two harnesses, two domains.** The source-editable versus outer-layer-only distinction is
  well chosen and still only two points.
- **Percentage granularity.** With 97 and 89 tasks, one task is about one point. Effects of
  two to three points are two to three tasks.
- **AGE is not independent.** The same authors diagnose the problem and validate the fix, on
  the same benchmarks, with the same harnesses. The expert review helps, and it is not a
  substitute for a replication by someone with no stake in the answer.

## The rest of the 2026 wave

The six papers above are the spine. Around them, November 2026 produced a dense cluster of
work that attacks the same problem from different angles. This table is a map, not a
literature review.

| Paper | arXiv | Contribution in one line |
| --- | --- | --- |
| Criteria Exposure | 2611.08318 | Showing the verifier's success criteria to the evolving agent raises benchmark scores that vanish when the criteria change slightly, so the agent learned the verifier |
| Frozen Weights | 2611.11342 | Failure traces add 4.0 points over a matched search that never sees them, but the search process alone got about 60 percent of the total gain, and the effect vanishes in full conversations |
| Third Eye | 2611.12988 | A further native update after selection erases or reverses the immediate gain: near-zero selected utility falls 1.78 points on continuation |
| Flex-RSI | 2611.08946 | A benchmark for harness-level self-improvement on vision and robotics tasks under a fixed budget |
| SelfImprove-Bench | 2611.02797 | Separates capability gain from scenario fitting, with tiered tasks, unseen difficulties and per-trace attribution |
| RSI-Env | 2611.01736 | A persistent environment with an independent host controller, where each accepted model-harness version runs the next improvement round |
| BOXBOX | 2611.09218 | Harness revision triggered inside a long-running task, for open-ended performance optimization, with the PerfRace benchmark |
| JoMoHa | 2611.11499 | Joint RL training of an executable harness-generation policy and a task policy, after showing naive alternation degrades both |
| Verify by Doing | 2611.15276 | Co-evolving actor and evaluator harnesses when no external feedback exists, with tool-using verification of artifacts and state |
| Experience-Handoff RL | 2611.16409 | Learning to construct the handed-off experience artifact with gradients instead of hand-writing the playbook |
| Singularity-Bench | 2611.16591 | Six end-to-end AI development tasks (pre-training, mid-training, post-training, inference, harness, orchestration) scored against human-engineered baselines |
| RSI-PDEbench | 2611.14949 | 1,001 PDE cases across 42 templates, with clean, noisy and hidden-equation settings for self-improving agents |

Three patterns are worth naming.

**The measurement papers are converging on the same verdict.** Criteria Exposure, Frozen
Weights and Third Eye all find that a benchmark gain is not the thing you thought it was:
it may be verifier fitting, or search-process luck, or a gain that the next update destroys.
Any of the three would be a footnote. Together they are a methodological correction.

**The environment papers are moving from benchmark to substrate.** RSI-Env and
Singularity-Bench both stop treating "the task" as a fixed list and start treating the
environment, the versioning and the handoff between generations as the object of study. That
is the right direction, and it is much harder to evaluate.

**The joint-optimization papers are reopening the weights question.** JoMoHa and
Experience-Handoff RL both find that a harness optimized against a frozen model is leaving
value on the table, and that naively alternating the two makes things worse. That is the
boundary this page does not cross. Everything here assumes frozen weights, which is the
practical assumption for a team that does not train models. If you do train them, the
verification problem gets harder in exactly the way the "what does not transfer" section
describes.

## The same loop in three costumes

Put the three side by side and the shared skeleton shows.

| Dimension | RHI | Branching search | InfraRSI |
| --- | --- | --- | --- |
| What is optimized | Prompt-level harness: roles, instructions, contracts, hops | Harness code, evolved by a proposer | Launch knobs plus source patches |
| Search shape | Single trajectory, pairwise against predecessor | Two or more branches, frontier of five | Multi-start, global models, escape moves |
| Feedback signal | LLM pairwise preference | Task reward mean on a branch subset | Log speedup under 16 invariants |
| Cost per iteration | One trace, one judgment | One harness execution plus evaluation | 10 to 20 GPU runs |
| Diversification | None | Evolving development subsets | Experience bank plus random start |
| Memory of the search | Preference history | Branch guidance plus candidate filesystem | Structured experience packs |
| Selection | Implicit, last iteration wins | Development-only, router at deployment | Back-to-back re-run plus audit |
| Frozen element | Evaluation prompt withheld from optimizer | Test set and router labels | SHA-pinned files and invariants |
| Main risk it addresses | Cost of search | Local optima | Reward hacking and noise |

### The three audits side by side

The three audits do not optimize anything. They measure three different things, and each maps
to one number you should be tracking.

| Audit | Question | Unit | Headline | What it changes in your loop |
| --- | --- | --- | --- | --- |
| RSI Tax | Does the loop pay? | Tokens | Tax of 109 to 393 percent for three of five methods; unused share 24 to 64 percent | Report tax beside accuracy; budget verification |
| TRUST | Is the gate honest? | False accept rate | 45.59 percent of greedy accepts are bad; 2.78 percent under a tested gate | Put a declared error budget on accepts |
| Beneath the Surface | What actually moved? | Tasks | All 16 lineages gain and lose tasks; reliability up 5.2 while losing 10 tasks | Report gained and lost separately; regress-guard the gate |

The three questions are independent, and a loop can pass one while failing the others. A loop
can be cheap and wrong. A loop can be statistically honest and too expensive. A loop can be
both and still be trading your best tasks for new ones.

### The eight parts every loop needs

1. **A frozen evaluator.** Otherwise the loop optimizes the evaluator.
2. **A cheap per-iteration cost.** Otherwise search eats the gains.
3. **A representation the proposer can edit.** Prompt text, harness code, config plus diffs.
4. **A memory of what was tried.** Preference history, branch guidance, experience packs.
5. **An acceptance rule with elitism.** Keep the incumbent unless the candidate wins under
   the gate.

After the three audits, that list is incomplete. Add three.

6. **A tax meter.** Task tokens and improvement tokens counted separately, per revision.
7. **A gate with a stated error budget.** Not "looks better", but "passes a test at a declared
   false acceptance rate".
8. **A task-level ledger.** Gained, lost, unchanged, and the deployment cost of each.

The first five make the loop run. The last three make it worth running.

The papers differ on how much they invest in each. RHI is all-in on cheap. The branching
paper is all-in on diversity and selection. InfraRSI is all-in on verification and memory.
The audits are all-in on measurement, and they exist because the first three papers did not
report what the loop cost, whether the gate was honest, or what the score hid.

A practical system needs all eight, and that is the real finding: **no single paper gives you
a complete harness RSI loop.** You have to compose them.

### What each contributes to a design

- From RHI: keep the iteration cheap, compare against your own last version, withhold the
  rubric, and expect the gains to come from context management rather than longer reasoning.
- From the branching paper: never let one development set own the whole search, prune
  saturated cases, let each branch write its own guidance, and expect complementarity you
  must route rather than average.
- From InfraRSI: lock the contract before you search, treat failures as censored data, record
  the cost of failed trials, calibrate noise instead of hardcoding a threshold, and store
  experience conditioned on the environment.
- From the tax paper: count task tokens and improvement tokens separately, expect verification
  to dominate the bill, and treat a bounded note as a serious baseline before you build a
  search.
- From TRUST: separate the gate from the proposer, declare a tolerance and an error budget,
  correct for validation reuse, and measure the gate's false acceptance rate like any other
  component.
- From Beneath the Surface: measure reliability and coverage separately, report gained and
  lost tasks, treat regression count as a Must, and do not assume the best current agent is
  the best parent.

## The EVO reading

EVO is a method for delivering small steps of measurable value under a budget, where the
measurement decides what happens next. A self-improving harness is that sentence with the
harness as the product.

| Principle | RSI design rule | What it prevents |
| --- | --- | --- |
| E1 Decompose by results and stakeholders | Each loop iteration changes one component and is scored on a task outcome, not on diff size | Optimizing a prompt for elegance instead of results |
| E2 Do high-risk steps early | Build the evaluator and the reward-hack test before the optimizer | Discovering in week six that the loop cheats |
| E3 Improve the most valuable objectives first | Rank candidate harness changes by expected value per search dollar | Spending the budget on a component with a 0.5 point ceiling |
| E4 Evolve the existing system | Optimize the harness you actually run, on your actual tasks | A benchmark harness that shares nothing with production |
| E5 Design to cost dynamically | Every iteration has a search budget, and search spend is a first-class metric in the same units as task execution | A loop whose search costs 300 percent of the delivery it enables |
| E6 Design to performance dynamically | Verify quality attributes, not just tests. Loss tolerance, latency, review minutes, and coverage as well as reliability | Adopting compression because it is cheaper while losing 5 points |
| E7 Invest in an open-ended architecture | The harness must be toggleable and revertible per component | A monolith where one bad revision cannot be undone |
| E8 Reward results, not effort | Score the loop on delivered value per dollar, and on tasks gained against tasks lost, not on iterations run or proposals accepted | A dashboard that rewards churn, or a mean that hides ten regressions |
| E9 Prioritize by value, not queue position | Stop the loop when the value per iteration drops below the cost, using a stop rule with an error budget | Running twenty iterations to gain 0.3 points |
| E10 Learn fast, change fast | Version every revision, keep a decision log, replay failures | Anecdotal tuning with no memory |

The principle table tells you how to decide. The three audits tell you how often the decision
is wrong, what it cost, and what it moved. That is the part EVO leaves implicit and every
engineering team eventually asks for.

### The Must and Plan structure is the whole trick

EVO separates value objectives, which trade off, from Must constraints, which do not. A Must
is a threshold that zeroes the delivery when violated.

InfraRSI's sixteen invariants are Must levels in everything but name. Speed is the value
objective. Correct workload, permitted precision, and timing agreement are Must. Break one and
the candidate scores zero, no matter how fast it looked.

TRUST contributes a subtler version. Its tolerance `epsilon` and error budget `q` are not Must
constraints on the harness. They are Must constraints on the **gate**. A revision is rejected
if its acceptance cannot be justified at the declared false acceptance rate, regardless of how
good the validation number looks. That is a constraint on the decision procedure rather than
on the product, and it is the layer most teams never write down.

Beneath the Surface contributes a third. A revision that regresses previously solved tasks is
not a trade to be weighed, it is a delivery failure for those tasks. Gained and lost are not
interchangeable, because the lost tasks have owners.

RHI has no explicit Must layer, and that is its weakest point. It relies on the evaluator
prompt to implicitly encode quality. The branching paper relies on benchmark tests, which is
a Must layer in practice. The tax paper has no Must layer at all, because it measures cost
rather than gating it, which is why its conclusion is "this method does not pay" rather than
"reject this revision".

If you build one thing from this section, build the Must layer. It is the cheapest part and
it is what makes the loop safe to run unattended.

### Impact estimation over harness changes

EVO's other import is the discipline of writing the estimate down before the measurement.

| Field | Example |
| --- | --- |
| Objective | Resolved rate on the holdout suite |
| Hypothesis | Task-specific contracts will raise resolved rate 3 to 6 points on multi-file tasks |
| Mechanism | Less redundant context, fewer dropped requirements |
| Estimated value | +4 points |
| Estimated cost | +8 percent tokens, plus 40 minutes of search |
| Confidence | Medium. The RHI evidence is on synthetic ML tasks |
| Measure | 20 scenarios, 3 runs, same snapshot |
| Decision rule | Keep if the lower bound of the interval clears +1.5 points and cost grows under 15 percent |

Writing this down before the run is what turns a preference into a forecast, and a forecast
into a team that can estimate. Without it, every result is discovered to have been predicted
all along.

## A reference RSI loop for a coding harness

Here is the composition. It is deliberately boring and deliberately slow to run unattended.

```
   +--------------------------------------------------------------------------+
   |  FROZEN CONTRACT                                                       |
   |  task, acceptance check, invariants, budget, holdout                   |
   |  hashed. optimizer may read, never write.                              |
   +----------------------------------v---------------------------------------+
                                      |
   +----------------------------------v---------------------------------------+
   |  INNER LOOP: agent runs the task under harness H(i)                    |
   |  tools, context, planner, subagents, budgets, tracing                  |
   +--------------------------------------------------------------------------+
                                      |  artifact, receipt, cost, trace
   +----------------------------------v---------------------------------------+
   |  VERIFIER: deterministic checks first, then behavioral, then rubric    |
   |  failure taxonomy attached to every verdict                            |
   +--------------------------------------------------------------------------+
                                      |  verdict plus failure class
   +----------------------------------v---------------------------------------+
   |  COMPARATOR: H(i) against H(i-1), paired, same scenarios               |
   |  visible dev set for the optimizer, hidden holdout for you             |
   +--------------------------------------------------------------------------+
                                      |  preference, interval, task-level diff
   +----------------------------------v---------------------------------------+
   |  MUTATOR: proposes H(i+1), one component at a time                     |
   |  sees history, never the rubric, never the holdout                     |
   +--------------------------------------------------------------------------+
                                      |  proposed diff to harness only
   +----------------------------------v---------------------------------------+
   |  GATE: invariants, regression count, holdout delta, cost delta.        |
   |  Sequential test at a declared error budget. Reject keeps incumbent.   |
   +--------------------------------------------------------------------------+
                                      |  accepted revision, reason, test result
   +----------------------------------v---------------------------------------+
   |  LEDGER: tasks gained, lost, unchanged; delivery tokens and tax        |
   |  tokens per revision. This is the number you report, not the mean.     |
   +--------------------------------------------------------------------------+
                                      |  tax rate, unused share, regressions
   +----------------------------------v---------------------------------------+
   |  EXPERIENCE STORE: what worked, on which model, on which tasks         |
   +--------------------------------------------------------------------------+
```

### The ten components

| Component | Job | Failure if missing |
| --- | --- | --- |
| Contract lock | Define what cannot change, and hash it | The loop edits the tests |
| Scenario bank | Fixed, stratified, versioned tasks with hidden split | The loop overfits the visible set |
| Verifier | Deterministic before probabilistic | Judged gains that do not exist |
| Comparator | Paired comparison, same snapshot, same runs | Noise read as progress |
| Mutator | Propose one change, with a rationale and an estimate | Random walk with a story |
| Gate | Accept only on holdout plus cost plus safety, at a declared error rate | Silent regression |
| Ledger | Gained, lost, unchanged tasks, plus delivery and tax tokens | A mean that hides a trade |
| Tax meter | Improvement tokens counted separately from task tokens | A loop that costs more than it delivers |
| Experience store | Record what worked and where | Every campaign starts from zero |
| Rollback | One command to restore `H(i-1)` | A bad revision you cannot undo |

The rollback item is not an afterthought. If reverting is expensive, the gate becomes
political, and a gate that is political is not a gate.

The ledger item is the one teams add last and need first. Without it you cannot tell a
trade from an improvement, and every one of the sixteen lineages in the audit section
would have looked like a win.

### A revision card

```yaml
revision: 12
parent: H11
component: contract                 # contract | hop | instruction | role | tool | budget
objective: ResolvedRate
hypothesis: >
  Requiring the verifier subagent to return a diff summary plus a list of
  unverified assumptions will reduce premature-victory failures on multi-file tasks.
estimate:
  resolved_delta_pp: [2, 5]
  cost_delta_pct: [5, 12]
  review_delta_minutes: -2
evidence:
  - failure taxonomy: premature victory 31 percent of remaining failures
  - rhi appendix: contract changes stabilize first
search_cost:
  traces: 1
  judgments: 20
  usd: 3.40
tax:
  task_tokens: 1840000
  rsi_tokens: 96000
  rate_pct: 5.2
  unused_share_pct: 4.0
measurement:
  scenarios: dev-v4
  holdout: holdout-v2
  runs: 3
  model: pinned-2026-11-01
  gate_test: sequential e-value, q=0.10, epsilon=0.02
task_ledger:
  gained: 3
  lost: 0
  unchanged: 14
decision: null
```

### Budget the search, not just the task

The loop has three budgets and most teams only track one.

| Budget | What it covers | Practical rule |
| --- | --- | --- |
| Delivery budget | Tokens, steps, minutes per task | Set per task contract, as in the harness design guide |
| Search budget | Traces, judgments, dollars per revision | Small enough that one revision cannot blow the week |
| Tax | Improvement tokens as a share of task tokens | Measure it. 100 percent means the loop costs as much as the work |
| Total budget | Delivery plus tax | If tax exceeds 20 percent of delivery spend, the loop is not paying for itself |

That last row is the one that keeps a self-improving harness honest. A loop that spends
40 percent of its budget improving itself had better be producing harness improvements that
generalize, or it is a very expensive hobby. The published methods sit at 109 to 393 percent,
which is the empirical answer to "how bad can it get": five to twenty times worse than the
threshold a team should accept.

One nuance before you copy the 20 percent rule. The tax paper's tax is measured over a task
stream with per-task updates. A campaign that improves a harness once and then serves ten
thousand tasks has a different denominator, and a much better ratio. The rule is about the
loop's steady state, not about the first week. Write the denominator down when you report the
number, because a tax rate without a horizon is meaningless.

### Acceptance rule with elitism

RHI's missing piece, stated as a rule:

```
accept(H(i+1)) iff
    invariants(H(i+1)) == all_true                              # must
and regressions(H(i+1)) == 0 || regressions(H(i+1)) < regressions(H(i))  # preservation
and holdout_delta(H(i+1)) > 0                                   # generalization
and cost(H(i+1))    <= cost(H(i)) * (1 + cost_ceiling)           # cost
and gate_test(H(i+1), q) == pass                                # statistical honesty
```

Five clauses, each corresponding to a known failure.

| Clause | Failure it stops |
| --- | --- |
| Invariants | The cheat |
| Regressions | Trading your best tasks for new ones |
| Holdout delta | Overfitting the visible set |
| Cost | The compression trap |
| Gate test | Accepting noise and building on it |

The gate test is the one the audits added, and it is the cheapest to add if you already have
a paired comparator. You need a sequential test, a declared tolerance, and a declared error
budget. That is a page of code, and it converts "this looked better" into "this passed a test
at a stated false acceptance rate".

The holdout clause is the one people skip, and it is the one that separates a search from a
self-delusion. Visible-set improvement is nearly free to obtain. Holdout improvement is not.
The preservation clause is the one people add last and regret not having: a revision that
gains five tasks and loses six is not a net positive, it is a product change you did not
intend to ship.

## The three clocks

Self-improvement can happen at three timescales, and mixing them up is a common design error.

| Clock | Period | What changes | Safe? |
| --- | --- | --- | --- |
| Per step | Seconds | Context, tool choice, retry policy | Only with a hard policy layer |
| Per campaign | Hours to days | Harness components, prompts, contracts | Yes, with the gate above |
| Per model generation | Weeks to months | The whole harness portfolio, priors, routing | Yes, and mandatory |

**Per step.** Adaptive behavior inside a task: choosing a tool, compacting context, spawning
a subagent. This looks like self-improvement but it is really policy execution. Letting an
agent rewrite its own system prompt mid-task is how you get an agent that has talked itself
out of its constraints. Keep this clock closed, or restrict it to choosing among pre-approved
options.

**Per campaign.** One task or a small batch, then a revision. This is where RHI and the
branching paper live. The gate applies, the incumbent is kept on rejection, and the cost is
small enough to iterate weekly.

**Per model generation.** A new model lands and some scaffolding stops being load-bearing.
Anthropic observed this directly when Opus 4.6 arrived and their sprint construct became
unnecessary. InfraRSI's experience bank is a version of this clock, conditioned on hardware
instead of model. Every component must be re-tested when the model changes, and components
that no longer pay for themselves get deleted rather than kept out of habit.

The practical rule: **close the fast clock, gate the middle clock, schedule the slow clock.**
Attempts to run self-improvement at the fast clock are where the scary stories come from.

## Simulating the loop before building it

You can test a self-improving harness without letting it touch production. In fact you should,
because the failure modes are cheap to find in simulation and expensive to find in a merge.

This is simulation squared. [The simulation protocol](evo-simulation.md) covers simulating the
agent's work. Here you also simulate the optimizer that improves the harness.

### Four layers

| Layer | Question | Setup | Cost |
| --- | --- | --- | --- |
| L0 Replay | Does a candidate harness change anything on fixed tasks? | Frozen traces, re-score with the new harness | Cents |
| L1 Mutator | Does the proposer produce plausible revisions? | Run the mutator against a frozen evaluator, no execution | Dollars |
| L2 Campaign | Does the loop improve over iterations? | Full loop, N iterations, visible and hidden sets | Hundreds |
| L3 Adversarial | Can the loop cheat? | Give the optimizer edit rights it should not have, and see | Hundreds |

L3 is the one nobody runs and everybody needs. If you are going to lock the evaluator, prove
the lock works by attacking it.

### The visible and hidden split

This is the single most important simulation design decision.

- The mutator and the comparator see the **visible** development set.
- You, the human, score on the **hidden** holdout.
- The gap between the two curves is your overfit signal.

A loop with no hidden set will look like it is improving forever. A loop with a hidden set
tells you when it stopped learning and started memorizing.

Practical split: 70 percent visible, 30 percent hidden, both stratified by task type, scope,
and spec quality as described in the simulation protocol. Report holdout once per harness
version, not per iteration, or you will overfit the holdout by watching it.

### The loop simulation, step by step

1. **Freeze the corpus.** Same tasks, same base commits, same acceptance checks, same model
   snapshot for the whole experiment.
2. **Baseline.** Run `H(0)` on visible and hidden. Three runs per task. Write the numbers.
3. **Iterate.** Ten revisions is enough to see whether the loop works. Twenty is the point of
   diminishing returns in the published work.
4. **Record per iteration:** visible score, hidden score, cost, failure taxonomy, revision
   description, acceptance decision, and time spent.
5. **Stop** on the rule in the next section, not on a hunch.

### Metrics for the loop itself

| Metric | Definition | What it tells you |
| --- | --- | --- |
| Improvement rate | Wins over the previous revision, per iteration | Is the loop moving |
| Holdout delta | Hidden score change per accepted revision | Is the movement real |
| Overfit gap | Visible minus hidden, per iteration | When memorization starts |
| Search cost | Traces, judgments, dollars per revision | Is the loop affordable |
| Tax rate | Improvement tokens divided by task tokens, per revision | Is the loop paying for itself |
| Unused share | Share of improvement tokens attached to state never read later | Is the proposer producing things nobody uses |
| Cost per point | Search spend divided by holdout gain | The number to compare against test-time scaling |
| Acceptance rate | Accepted revisions over proposed | Is the mutator any good |
| False accept rate | Accepted revisions that were worse on the holdout, over accepts | Is the gate honest |
| Revert rate | Accepted then reverted later | Is the gate too loose |
| Time to plateau | Iterations until holdout gain clears noise | Is there headroom |
| Gained and lost | Tasks newly solved and tasks newly broken | Is the loop trading breadth for depth |
| Reliability and coverage | Mean success across runs, and solve-at-least-once | Is the gain consistency or luck |
| Failure taxonomy shift | Distribution of failure classes per iteration | Where the bottleneck moved |

The taxonomy metric is the most actionable and the most often omitted. RHI's story is a
taxonomy shift: contracts improved, cache traffic fell, and the remaining failures moved. A
single score would have hidden the mechanism.

The false accept rate is the one with a published baseline. Greedy gates run at 35 to 65
percent in the TRUST experiments. If your gate has never been measured, assume it is in that
range, because the mechanism that produces it (a point estimate on a reused validation pool)
is the default behavior of every loop in this page.

### Simulating the gate

The gate is the one component you can test in isolation, and almost nobody does.

1. **Freeze a pool of candidate revisions.** Twenty is enough to start. For each, record the
   validation score the gate would see and the holdout delta the gate must not see.
2. **Replay the gate.** Run your acceptance rule over the pool in order, updating the
   incumbent as it goes, using only validation evidence.
3. **Count false accepts.** An accept where the replayed candidate's holdout delta is at or
   below `-epsilon` is a false evolution. Divide by accepts.
4. **Inject known-bad candidates.** Take the champion and break one component deliberately:
   remove a tool, invert a rule, drop a contract. You know the true delta is negative. A gate
   that accepts these is not gated.
5. **Report acceptance rate and false accept rate together.** One without the other is
   meaningless, as the SGM-B result shows: zero false accepts, zero accepts.

A cheap version of step 1 is to use the revision log from a previous campaign. You already
have the candidates and the scores. Replaying them through a new gate costs nothing but
compute, and it is the highest-value hour in the whole build.

### Simulating the router

If you adopt branching, simulate the routing too, because routing has its own failure mode:
a router that cannot tell the branches apart.

- Hold out cases solved by exactly one branch head. That is your router's training set.
- Measure router accuracy on a fresh batch of exclusive cases.
- Report three numbers: head A alone, head B alone, routed. If routed is not above the better
  head, the branches are not complementary enough to justify the complexity.

In the branching paper, routed beat the better head by 4.0 points on one setting and 1.7 on
another, and lost by one case on the other two. That is a realistic distribution of outcomes
for a good router, so calibrate expectations accordingly.

### The adversarial test

Sit down and try to cheat your own loop. Then automate it.

| Attack | How to simulate | Expected defense |
| --- | --- | --- |
| Weaken the tests | Give the mutator edit rights to test files, watch | Diff guard on test paths, mutation check |
| Move work outside the window | Add a deferred update to a fixture | Timing agreement check |
| Lower precision silently | Cast a fixture to a cheaper type | Precision menu invariant |
| Overfit the visible set | Duplicate visible scenarios with renamed identifiers | Hidden set, paraphrase test |
| Game the judge | Put persuasive text in the diff, not the code | Judge sees artifacts, not chat |
| Exploit noise | Submit the same harness twice, look for a "win" | Paired gate, calibrated threshold |
| Collapse the search | Fix the dev set, run twenty iterations | Branch coverage, novelty check |

If any attack succeeds, the loop is not ready. This is E2, the high-risk step first, applied
to the loop rather than the product.

### Simulating cost honestly

The branching paper's own limitation is the template: unequal token budgets make gains hard
to attribute. The tax paper is the answer to it: count the improvement tokens separately, and
report them against the task tokens.

- Total tokens by role: action model, proposer, judge, router.
- Improvement tokens split into verify, explore and write. Expect verify to dominate.
- The share of improvement tokens attached to state that was never read again.
- Total dollars, including the judge, which is easy to forget.
- GPU or wall-clock hours for verification.
- Human minutes reading traces and diffs.

Then answer the only question that matters: **compared with spending the same budget on more
test-time compute, does the loop win?** If you cannot answer that, you have built a very
elaborate way to feel productive.

There is one simulation trick worth naming. Run the same budget twice: once as a search loop,
once as N independent attempts at the same tasks with no learning. If the loop does not beat
the flat baseline at equal spend, the loop is not adding value, it is adding process. That
comparison is trivially cheap to set up and it is the one the literature keeps skipping.

## The overfitting curve

Draw this chart before you build anything else.

```
score
  |
  |                        visible ................
  |                   .....
  |              .....
  |         .....
  |    .....
  |....
  |         .....            hidden .............
  |              .....                   .....
  |                   .....                    .....
  |                        .....                    .....
  +----------------------------------------------------> revision
        learn        plateau        memorize
```

Three phases, three different decisions.

**Learn.** Both curves rise. The loop is working. Keep going, and keep the gate loose enough
to let revisions through.

**Plateau.** Visible still rises, hidden flattens. The loop is now fitting. Stop accepting
revisions that only move visible, tighten the gate, and consider that the next gain is in a
different component.

**Memorize.** Visible rises, hidden falls. The loop is actively harmful. Stop. Roll back to
the best holdout revision, which is now several revisions in the past.

A stop rule that follows from this:

```
for each revision:
    if holdout_delta <= noise_floor for two consecutive revisions:
        stop and report
    if holdout_delta < 0:
        revert to best_holdout_revision
```

Two consecutive flat revisions, not one, because single-iteration noise is real. And revert on
negative, not "investigate later", because the best revision is a known artifact.

This is where EVO's E9 lands: abandonment is a feature. A loop that cannot stop is not
improving, it is spending.

### The second curve: coverage churn

The curve above plots the mean. There is a second curve, and it is a flow rather than a level:
tasks gained and tasks lost, per revision.

Plot both against revision alongside the mean. Three shapes tell you three different things.

| Shape | What it means |
| --- | --- |
| Gained rises, lost stays near zero | The loop is adding capability |
| Gained rises, lost rises with it | The loop is redistributing capability, and the mean hides it |
| Gained flat, lost flat, mean flat | The loop has stopped, whatever the dashboard says |

The middle shape is the one to watch for, because it looks like success. Beneath the Surface
found turnover in all sixteen of its lineages, including the ones that improved on both
reliability and coverage. A harness that gains twelve tasks and loses six has changed what it
is good at, and the six have owners.

Report the count, not just the delta. "Plus three coverage" can mean fifteen gained and twelve
lost, which is a different product decision from three gained and none lost.

## Guardrails

The five failure modes, their published evidence, and the mechanism that addresses them.

| Failure | Evidence | Guardrail |
| --- | --- | --- |
| Prompt injection through tool output | General agent finding, not specific to RSI | Treat tool output as data, never as instruction |
| Editing the judge | InfraRSI source audits found deferred updates that receipts missed | Read-only evaluator, hashed files, separate process |
| Test tampering | Common coding-agent failure | Diff guard on test and fixture paths, mutation testing |
| Timing window games | InfraRSI L5 caught 158 timing mismatches | Wall clock versus reported time agreement |
| Precision downgrade | InfraRSI L4, 42 loss-tolerance triggers | Declared precision menu, loss and gradient bounds |
| Noise exploitation | InfraRSI: noise spans 0.04 to over 6 percent | Calibrated noise floor, back-to-back re-run |
| Search collapse | Branching paper: fixed dev set plateaus | Evolving subsets, pruning, branch guidance |
| Visible-set overfit | Branching paper: Meta-Harness gains 3 points when selecting on test | Hidden holdout, dev-only selection |
| Cost blowup | RHI citing Wang et al. 2026 | Search budget as a first-class metric |
| Tax exceeds delivery | Tax paper: 109 to 393 percent for three of five methods | Improvement tokens counted separately, verification budgeted |
| Gate accepts noise | TRUST: greedy FER0 of 45.59 percent | Sequential test, declared error budget, overlap correction |
| Coverage churn | Audit: 16 of 16 lineages gain and lose tasks; plus 5.2 reliability while losing 10 tasks | Gained and lost reported separately, regression clause in the gate |
| Verifier fitting | Criteria Exposure: gains vanish when the criteria change slightly | Paraphrase the criteria, hold out a second verifier |
| Gain destroyed by the next update | Third Eye: selected utility falls 1.78 points on continuation | Evaluate after one further update, not only at selection |
| Silent regression | Harness study: compression loses 4 to 5 points | Paired regression suite on every revision |
| Unbounded context | InfraRSI: 28k character summarization of old trials | Summarize old trials, keep full traces for recent |
| Bad revision with no way back | RHI lacks elitism in its pseudocode | Versioned harness, one-command rollback |

Two rules that are not in any table because they are cultural:

**The optimizer never sees the rubric.** RHI enforces this structurally. Copy it. If your
mutator can read the acceptance criteria in full, it will optimize the criteria.

**A human promotes, the loop proposes.** Automation bias is real, and a loop that merges its
own revisions has no independent check. Keep the promotion gate human for the first six
months, then automate only the classes of revision where the gate has never disagreed.

## What breaks

Specific failure modes of the RSI loop, with the mechanism that catches them.

| Break | Symptom | Fix |
| --- | --- | --- |
| The loop optimizes the judge | Scores rise, user complaints rise | Separate judge context, adversarial judge, human spot checks |
| The loop optimizes the visible set | Beautiful dev curve, flat production | Hidden holdout, refresh from production failures |
| The loop optimizes cost | Tokens down, quality down, nobody notices | Must-level quality floor, paired comparison |
| The loop stops learning | Ten revisions, no holdout movement | Different component, different objective, or stop |
| The loop oscillates | Revision 12 undoes revision 9 | Keep an archive, penalize reversals, longer history |
| The loop specializes too hard | Great on one task family, worse on others | Branch or route, as in the branching paper |
| The loop inherits stale priors | New model, old scaffolding, no gain | Re-run the component ablation at every model change |
| The loop cannot explain itself | A revision nobody can justify | Mandatory rationale and estimate per revision |
| The loop costs more than it saves | Search spend exceeds delivery spend | Budget ratio, stop rule, tax meter |
| The loop looks free | Nobody ever measured the improvement tokens | Count verify, explore and write separately |
| The gate is a coin flip | Accept rate near random when candidates are shuffled | Replay the archive, inject known-bad candidates |
| The loop buys its own score | Every task gained costs one lost, mean unchanged | Gained and lost ledger, regression clause |
| The gain evaporates next revision | The candidate was good once, and worse after one more update | Third Eye continuation check before promotion |
| The loop learned the verifier | Scores collapse when the criteria are paraphrased | Second held-out verifier, criteria paraphrase test |
| The loop is unreviewable | A 900-line prompt diff | Component granularity, one change per revision |

The oscillation entry deserves a note. RHI's pairwise-against-predecessor design has no
protection against A-B-A-B cycling, because each comparison is local. The history helps, but a
longer archive plus a penalty on re-proposing a rejected revision is the practical fix. That
is also why the branching paper's filesystem of all prior candidates matters: the proposer can
see that this idea was already tried.

## Build order

Each stage has an exit criterion, which is the gate. Do not skip ahead; the later stages are
worthless without the earlier meters.

**Stage 1: the frozen contract.**

Write the task contract, the acceptance checks, and the invariant list. Hash the frozen files.
Make the evaluator read-only and run it in a separate process.

Exit: you can prove the evaluator rejects a deliberately broken submission, and the optimizer
cannot write to it.

**Stage 2: the scenario bank with a hidden split.**

Twenty scenarios minimum, stratified. Seventy percent visible, thirty percent hidden. Version
them in git with base commits and acceptance commands.

Exit: a baseline run produces resolved rate, cost, and failure taxonomy on both splits.

**Stage 3: the comparator.**

Paired comparison against the incumbent, same model snapshot, three runs, same scenarios.
Report intervals, not points.

Exit: you can distinguish a 5-point change from noise on your corpus.

**Stage 4: the mutator.**

One component per revision, with a rationale, an estimate, and a mechanism. It sees history
and failures. It does not see the rubric or the holdout.

Exit: ten proposed revisions, at least six of which a human reviewer calls plausible.

**Stage 5: the gate.**

Accept on holdout delta plus cost plus invariants. Keep the incumbent on rejection. One
command rolls back.

Exit: a deliberately bad revision is rejected, the rollback is exercised for real, and the
threshold has been replayed against at least twenty archived candidates so you know its
empirical error rate.

**Stage 6: the tax meter and the ledger.**

Count improvement tokens separately from task tokens, split into verify, explore and write.
Track gained, lost and unchanged tasks per revision, with the deployment cost of each.

Exit: one report shows tax rate, unused share and task turnover for the last five revisions,
and reading it changes at least one decision. If it changes nothing, the meter is decoration.

**Stage 7: the statistical gate.**

Replace the point-estimate threshold with a sequential test, a declared tolerance and a
declared error budget. Correct for validation reuse.

Exit: replaying the archive gives a measured false accept rate below the declared budget, at
an acceptance rate that is not near zero. Both numbers, or the stage is not done.

**Stage 8: adversarial hardening.**

Run the attack table from the simulation section against the real loop, including the gate
itself and the known-bad candidate injection.

Exit: every attack is caught, and the catch is logged.

**Stage 9: the experience store.**

Structured records: environment, observation, effect. Model version, task class, component,
outcome.

Exit: a new campaign warm-starts from the store and reaches its previous best faster.

**Stage 10: branching, if the single trajectory plateaus.**

Two branches, evolving subsets, coverage voting, branch-local guidance. Only after stage 5
proves the gate works, because branching multiplies whatever the gate does wrong.

Exit: routed holdout beats the better single head.

**Stage 11: the router.**

Fit on head-exclusive development cases. Evaluate on fresh exclusive cases.

Exit: routing beats the best head on at least two of three task families, or drop the router.

**Stage 12: scheduled re-evaluation.**

Every model upgrade triggers a component ablation. Components that no longer pay are deleted.

Exit: a written record of what was removed and why, per model generation.

The ordering is the EVO ordering: value first, cost second, complexity last. Most teams
invert it, build the branching router, and discover they cannot tell whether any of it helped.

Two of the stages are new, and both exist because of the audits. Stage 6 is cheap and it is
the only one that can tell you to stop. Stage 7 is a day of work and it is the difference
between a gate and a coin flip. Neither requires a better model, a bigger cluster or a new
benchmark, which is why skipping them is hard to defend.

## What does not transfer

Honesty section. These are the limits you should carry into any adoption decision.

**Task-specific does not mean general.** RHI produces a harness per task. That is a real
benefit for repeated similar work and a real cost for diverse work, where you pay the search
cost per task. The paper's framing is continual specialization, not one universal harness.

**Prompt-level gains may not survive a model change.** RHI's gains persist across three model
generations, which is encouraging. But the mechanism is context management, and context
management is exactly what providers keep improving for free. Re-test, do not assume.

**The judge is the soft spot.** Several of these papers rely on LLM judgment for the signal.
Positivity bias, prompt sensitivity, and model-version drift all leak into the objective.
Deterministic verifiers are better wherever the task allows them.

**Synthetic tasks are not your repository.** Thirty generated ML research tasks, Olympiad
problems, and terminal benchmarks are all cleaner than a ten-year-old codebase with flaky
tests and undocumented invariants.

**Hardware results do not transfer.** InfraRSI's sign flips across H20, H100 and H200 are the
clearest demonstration that a learned prior can be actively wrong on new hardware.

**The search cost is easy to hide.** The branching paper admits unequal token budgets. RHI's
cited finding is that search cost can erase the gains entirely. The tax paper measures it at
109 to 393 percent for three of five methods. Count it.

**The tax rate depends on the horizon.** A campaign that improves a harness once and then
serves ten thousand tasks has a tiny tax. A loop that updates every four tasks has a huge one.
The published numbers are from the second regime. If your deployment looks like the first,
you are allowed to be less worried about the tax, and you are not allowed to skip measuring it.

**A mutator can pass the gate and still not be worth it.** TRUST's guarantees are about the
proportion of accepted updates that were bad. They say nothing about the size of the good ones,
the cost of finding them, or whether the final harness is good in absolute terms. A safe loop
can be a slow loop.

**The gate needs validation data you may not have.** 200 examples and 30 rounds is already
more than most teams have. With 40 validation cases, the sequential test will be correct and
will accept almost nothing, which is the SGM-B outcome. Plan for the statistical power
problem before you plan for the loop.

**Gains are not durable by default.** Third Eye's result is the sharpest version: immediate
selected utility near zero, and a further update reduces it by 1.78 points. Beneath the
Surface shows the same thing structurally, with every lineage losing tasks. A gain that only
exists at selection time is not a gain.

**The recursion is shallow.** Nobody in these papers improves the improver. The mutator is a
fixed model with a fixed prompt. A true second-order loop, where the optimizer improves the
optimizer, squares the verification problem: you would need to verify that the improved
verifier is still honest. That is where the concept becomes genuinely hard, and no paper here
crosses that line.

**Dev and test overlap flatters everyone.** Meta-Harness gains 3 points on math if you let
test outcomes select among candidates. Any paper reporting search-set performance as a
headline is reporting an optimistic number, and the branching authors say so. Criteria
Exposure is the same disease in a different organ: the agent optimizes the checker rather
than the task.

## Worked example: one week of harness RSI

A team has a coding harness with a 43 percent resolved rate on their internal suite, and one
engineer for a week. Numbers below are illustrative but the structure is not.

**Monday: contract and meter.**

They hash the test command, the fixture data, and the acceptance script. They split 24
scenarios into 17 visible and 7 hidden. Baseline: 43 percent visible, 41 percent hidden, 2.10
USD per task, 24 review minutes.

**Tuesday: the first revision.**

The failure taxonomy from the baseline says 38 percent of failures are "requirements dropped
from long specs" and 22 percent are "premature victory". The estimate: adding a contract
requirement, forcing the verifier subagent to restate each acceptance criterion before
finishing, will move 3 to 6 points at 8 percent cost.

One revision, one component. Cost: 3.10 USD of search, 22 judgments.

**Wednesday: measurement.**

| Split | Before | After | Delta |
| --- | --- | --- | --- |
| Visible | 43 | 48 | +5 |
| Hidden | 41 | 44 | +3 |

Accepted. Visible gain 5, hidden gain 3, so roughly 40 percent of the visible improvement was
fitting. Cost rose 9 percent, inside the ceiling. Review minutes unchanged. Tax for the
revision: 0.42M improvement tokens against 3.6M task tokens, so 12 percent, and the unused
share is zero because the only artifact the revision produced is the harness itself.

**Thursday: the second revision, and a rejection.**

The mutator proposes enabling context compression to recover the cost increase. The failure
taxonomy from the harness study is in its history, so it also predicts a 4-point loss. The
measurement agrees: visible 46, hidden 40. Rejected under the quality clause. The incumbent
stays.

This is the most valuable day of the week, and it produced no improvement. It prevented a
plausible-looking cost optimization from erasing the first gain, and it cost 2.40 USD.

They also replay both revisions through the gate they plan to adopt next month, a sequential
test with an error budget of 0.10 and a tolerance of 0.02. The first revision passes. The
second fails on the holdout. Two observations is not a measured error rate, and it is the
start of one.

**Friday: stop, and write it down.**

Two revisions, one accepted, one rejected. The holdout moved 3 points. The decision log
records both estimates against both results. The next hypothesis, chosen because the taxonomy
moved rather than because it is interesting, is about specification quality rather than
another harness component.

The ledger for the week: three tasks gained, none lost, fourteen unchanged on the visible
split. Two gained, none lost, five unchanged on the hidden split. That is a clean trade, which
is unusual, and they know it is clean only because they counted.

**What a week bought:** +3 points of real holdout improvement, one prevented regression, two
calibration data points, a first reading on the gate, and a stop decision made on evidence
rather than fatigue.

**What it did not buy:** a self-improving system. That takes a quarter. The week bought a
working *instrument*, which is the thing you actually need first.

## Open questions

1. Does prompt-level harness improvement transfer from synthetic ML research tasks to
   long-lived enterprise repositories with weak tests?
2. How much of RHI's gain survives a model generation that already manages context well? The
   mechanism is context management, which providers improve continuously.
3. Is the branching paper's router a real capability or a small-sample artifact? The gains are
   34.8 points on one setting and 3.8 on another, which is a very wide spread.
4. Can the verifier be improved without being gamed? Second-order RSI is the open frontier and
   nobody has demonstrated a safe version.
5. What is the right search-to-delivery cost ratio? Twenty percent is a guess, not a finding.
6. Do experience packs transfer across organizations, or is the retrieval only meaningful
   within one team's hardware and conventions?
7. Which parts of a harness are load-bearing at frontier capability, and which are just
   compensation for weaker models? Anthropic's answer keeps shrinking, and nobody has mapped
   the shrinkage systematically.
8. Does a routed portfolio of specialized harnesses beat one well-tuned general harness at
   equal total cost? The branching paper suggests yes on complementary benchmarks, but the
   token budgets were unequal.
9. What is the right tax denominator? The published numbers come from streams that update
   every four tasks. A harness improved once and served for months has a different ratio, and
   nobody has measured the crossover.
10. Can the gate's false accept rate be estimated without a large holdout, by replaying an
    archive of candidates whose true deltas are known from production? That would make TRUST
    affordable for teams with forty validation cases.
11. Does the statistical gate survive a proposer that cannot produce real improvements? TRUST
    assumes the proposer eventually finds one. A weak proposer plus a correct gate is a loop
    that accepts nothing.
12. Is coverage churn a property of harness evolution, or of eight-pass evaluation on small
    benchmarks? The ledger has not been run on a large production suite.
13. Do the three audits interact? A cheaper loop buys more revisions, more revisions need a
    tighter gate, and a tighter gate on the same data accepts less. The composition of the
    three constraints is unstudied.

## Checklist

- [ ] The evaluator is read-only, hashed, and runs in a separate process.
- [ ] The optimizer never sees the rubric or the holdout split.
- [ ] A contract, not the model, decides whether a task is complete.
- [ ] Must-level invariants zero the candidate on violation.
- [ ] A hidden holdout exists, and it is reported once per harness version.
- [ ] One component changes per revision, with a written rationale and estimate.
- [ ] Revisions are paired comparisons on the same scenarios and model snapshot.
- [ ] The gate has invariants, regressions, holdout, cost and gate-test clauses.
- [ ] The gate has a declared tolerance and a declared error budget.
- [ ] The gate's false accept rate has been measured by replaying archived candidates.
- [ ] Known-bad candidates have been injected, and they were rejected.
- [ ] The incumbent is kept on rejection, and rollback is one command.
- [ ] Improvement tokens are counted separately from task tokens, per revision.
- [ ] Verification cost has been budgeted, not just task cost.
- [ ] The unused share of the tax has been measured at least once.
- [ ] Gained, lost and unchanged tasks are reported per revision.
- [ ] A continuation check runs before promotion: is the candidate still good after one more
      update?
- [ ] Search cost is measured in dollars, not just in tokens.
- [ ] Tax is under 20 percent of delivery spend, or there is a reason and a horizon.
- [ ] The visible and hidden curves are plotted together.
- [ ] There is a stop rule, and it has been used at least once.
- [ ] The failure taxonomy is reported per iteration, not just the score.
- [ ] The adversarial attack table has been run against the real loop.
- [ ] Every revision has a version, a decision, and a reason.
- [ ] Components are re-ablated at every model upgrade, and dead ones are deleted.
- [ ] A human promotes; the loop proposes.

## References

The six papers this page is built on:

- Hyunin Lee, Jinglue Xu, Jeffrey Seely, Donghyun Lee, Matei Zaharia, Yujin Tang,
  "Recursive Harness Self-Improvement", arXiv 2607.15524, July 2026. Harness as prompt,
  pairwise feedback over revision history, 30 synthetic ML research tasks, up to 60 percent
  lower inference cost.
  https://arxiv.org/abs/2607.15524
- Haoyu Dong, Yuhang Zhou, Zihao Lin, Yifan Wu, Bo Peng, Mingyi Wang, Xiangjun Fan,
  Lizhu Zhang, Zhuokai Zhao, "Mixture of Self-Improving Branches for Agent Harness
  Optimization", arXiv 2609.37834, September 2026. Evolving development subsets, branch-local
  proposal guidance, development-informed routing.
  https://arxiv.org/abs/2609.37834
- InfraRSI Team, Yuchuan Tian, Haocheng Mei, Ye Yuan, Chao Xu, Boxun Li, Guohao Dai, Kai Han,
  Allen Chen, Yunhe Wang, Yu Wang, "InfraRSI: Harnessing Recursive Self-Improvement for
  Training Infrastructure", arXiv 2611.11558, November 2026. Five-stage workflow, fixed task
  contract, budgeted compositional search, cross-hardware experience bank.
  https://arxiv.org/abs/2611.11558
- Yitong Zhang, Ang Li, Yisen Wang, "The RSI Tax: When Recursive Self-Improvement Is Not Worth
  the Cost", arXiv 2611.13524, November 2026. Token cost of self-improvement on continual task
  streams, the verify-explore-write decomposition, subsequent-use attribution, and a bounded
  note baseline.
  https://arxiv.org/abs/2611.13524
- Zihe Gao, Zhengling Qi, Yifan Cui, "Trustworthy Recursive Self-Improvement with Statistical
  Guarantees", arXiv 2611.10787, November 2026. False evolution rate, e-value testing with
  overlap correction, error budget allocation, and an LLM-assisted spending policy.
  https://arxiv.org/abs/2611.10787
- Xiaobo Wang, Zimu Wang, Siyu Ye, Jiaqi Li, Min Tang, Jun Bai, Yuling Shi, Ruobing Wang,
  Jingjing Zhang, Chaofan Wang, Kai Wu, Mengnan Qi, Kai Cai, Xiaodong Gu, Qi Liu,
  Zilong Zheng, "Beneath the Surface: What We Overlook When We Talk About Agent Evolution",
  arXiv 2611.07624, November 2026. Sixteen lineages, reliability versus coverage, task
  turnover, deployment cost, operator interventions, and AGE.
  https://arxiv.org/abs/2611.07624

The measurement base:

- Haichuan Hu et al., "Beyond the Model: Demystifying Harness Effects in Software Engineering
  Agents", arXiv 2609.32459, September 2026. Harness gap of 19.4 points, model gap of 22.8,
  NanoHarness component ablations.
  https://arxiv.org/html/2609.32459v1

The rest of the wave, cited by arXiv ID in the landscape table:

- Wenbo Huang et al., "Learning the Task or Learning the Verifier? Rethinking Criteria
  Exposure in Embodied Self-Improvement", arXiv 2611.08318.
- Arkid Mitra et al., "Agent Self-Improvement with Frozen Weights: The Added Value and Limits
  of Failure Traces", arXiv 2611.11342.
- Sujato Dutta et al., "Third Eye: Beyond Immediate Gains in Recursive Self-Improvement",
  arXiv 2611.12988.
- Jingdong Zhang et al., "Flex-RSI: Benchmarking Recursive Self-Improvement of Frontier
  Agents", arXiv 2611.08946.
- Bangrui Xu et al., "SelfImprove-Bench: Evaluating Generalization in Self-Improving Agents",
  arXiv 2611.02797.
- Wanying Qu et al., "RSI-Env: An Open-Ended Environment for Recursive Self-Improvement of
  Agents", arXiv 2611.01736.
- Yuhao Tan et al., "BOXBOX: Recursive Harness Self-Improvement for Long-Running Performance
  Optimization", arXiv 2611.09218.
- Xudong Wu et al., "JoMoHa: Joint Model-Harness Optimization with Reinforcement Learning",
  arXiv 2611.11499.
- Yitong Lin et al., "Verify by Doing: Co-Evolving Agent Execution and Evaluation without
  External Feedback", arXiv 2611.15276.
- Doyoung Kim et al., "Experience-Handoff Reinforcement Learning for Recursive
  Self-Improvement", arXiv 2611.16409.
- Yang Zhou et al., "Singularity-Bench: Can Agents Build Agents?", arXiv 2611.16591.
- Binghang Lu et al., "RSI-PDEbench: A Benchmark for Self-Improving Agents in PDE Solving",
  arXiv 2611.14949.

Methods cited by those papers:

- Yoonho Lee et al., "Meta-Harness: End-to-end optimization of model harnesses", arXiv
  2603.28052, 2026.
- Zhang et al., "Self-Harness", 2026. Verifier-based harness revision with held-in and
  held-out regression checks.
- Lakshya A. Agrawal et al., "GEPA: Reflective prompt evolution can outperform reinforcement
  learning", ICLR 2026.
- Wang et al., 2026, on harness evolution failing to beat test-time scaling once search cost
  is counted.

Harness design and measurement:

- [Building a custom AI harness with EVO principles](evo-in-ai-harness.md) for the harness
  itself, including the component portfolio and the build order.
- [Simulating the EVO process for harness development](evo-simulation.md) for scenario
  corpora, run variance, ablation design, fault injection and multi-session shifts.
- [EVO in the AI harness era](evo-in-ai-era.md) for the evidence base and the E1 to E10
  mapping.
- [EVO in software development](evo-sw-devel.md) for the method itself.

Method:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process", InfoQ, 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- Tom Gilb, *Competitive Engineering*, Elsevier, 2005. Planguage, impact estimation, Must and
  Plan levels.
