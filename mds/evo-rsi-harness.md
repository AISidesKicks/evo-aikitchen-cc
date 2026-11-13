# Simulating and building a self-improving EVO harness

A harness that improves itself sounds like science fiction until you write down what it
actually means. In practice it means this: the harness runs a task, something observes the
result, and a program rewrites part of the harness so the next attempt is better. That is
it. No new model weights, no gradient, no magic. Just a loop with a feedback signal.

The uncomfortable part is that "better" has to be defined by something the loop cannot
edit. Every credible result in this space freezes the evaluator before the search starts.
Every failure in this space comes from a loop that found a way around the evaluator. That
single asymmetry explains most of the design decisions in this page.

Three 2026 papers make the topic concrete, and they attack three different parts of it:

- **Recursive Harness Self-Improvement** (RHI, arXiv 2607.15524) shows that a harness
  written as a prompt can be revised in two or three iterations to beat the strongest
  test-time scaling setting of the same model, at up to 60 percent lower cost.
- **Mixture of Self-Improving Branches** (arXiv 2609.37834) shows that a single search
  trajectory stalls, and that branching the search with evolving development subsets and
  a router recovers complementary harnesses.
- **InfraRSI** (arXiv 2611.11558) shows what it takes to run this loop against real
  hardware: a locked task contract, sixteen invariants, a noise model, and a cross-cluster
  experience bank that survives the transfer.

Alongside them sits the measurement base from
[Beyond the Model](https://arxiv.org/html/2609.32459v1), which established that harness
choice is worth roughly a model generation in points.

This page is the synthesis. It covers what the three papers actually did, how to read them
through EVO, how to simulate the loop before you build it, and where the whole idea breaks.

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

### Three ways it goes wrong

| Failure | What it looks like | First paper to name it |
| --- | --- | --- |
| Reward hacking | Tests weakened, work moved outside the timing window, precision lowered beyond the declared menu | InfraRSI |
| Search collapse | Every proposal resembles the last one, the loop plateaus in one basin | Branching paper |
| Cost blowup | Search costs more than the delivery it enables, so the "gain" is negative | RHI motivates it, citing Wang et al. 2026 |

Every design decision in the rest of this page exists to address one of those three.

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

### The five parts every loop needs

1. **A frozen evaluator.** Otherwise the loop optimizes the evaluator.
2. **A cheap per-iteration cost.** Otherwise search eats the gains.
3. **A representation the proposer can edit.** Prompt text, harness code, config plus diffs.
4. **A memory of what was tried.** Preference history, branch guidance, experience packs.
5. **An acceptance rule with elitism.** Keep the incumbent unless the candidate wins under
   the gate.

The papers differ on how much they invest in each. RHI is all-in on cheap. The branching
paper is all-in on diversity and selection. InfraRSI is all-in on verification and memory.

A practical system needs all five, and that is the real finding: **no single paper gives you
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
| E5 Design to cost dynamically | Every iteration has a search budget, and search spend is a first-class metric | A loop whose search costs more than the delivery it enables |
| E6 Design to performance dynamically | Verify quality attributes, not just tests. Loss tolerance, latency, review minutes | Adopting compression because it is cheaper while losing 5 points |
| E7 Invest in an open-ended architecture | The harness must be toggleable and revertible per component | A monolith where one bad revision cannot be undone |
| E8 Reward results, not effort | Score the loop on delivered value per dollar, not on iterations run or proposals accepted | A dashboard that rewards churn |
| E9 Prioritize by value, not queue position | Stop the loop when the value per iteration drops below the cost | Running twenty iterations to gain 0.3 points |
| E10 Learn fast, change fast | Version every revision, keep a decision log, replay failures | Anecdotal tuning with no memory |

### The Must and Plan structure is the whole trick

EVO separates value objectives, which trade off, from Must constraints, which do not. A Must
is a threshold that zeroes the delivery when violated.

InfraRSI's sixteen invariants are Must levels in everything but name. Speed is the value
objective. Correct workload, permitted precision, and timing agreement are Must. Break one and
the candidate scores zero, no matter how fast it looked.

RHI has no explicit Must layer, and that is its weakest point. It relies on the evaluator
prompt to implicitly encode quality. The branching paper relies on benchmark tests, which is
a Must layer in practice.

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
        +-----------------------------------------------------------+
        |  FROZEN CONTRACT                                          |
        |  task, acceptance check, invariants, budget, holdout      |
        |  hashed. optimizer may read, never write.                 |
        +-----------------------------+-----------------------------+
                                      |
   +----------------------------------v----------------------------------+
   |  INNER LOOP: agent runs the task under harness H(i)                |
   |  tools, context, planner, subagents, budgets, tracing              |
   +----------------------------------+---------------------------------+
                                      |  artifact, receipt, cost, trace
   +----------------------------------v---------------------------------+
   |  VERIFIER: deterministic checks first, then behavioral, then rubric|
   |  failure taxonomy attached to every verdict                        |
   +----------------------------------+---------------------------------+
                                      |  verdict plus failure class
   +----------------------------------v---------------------------------+
   |  COMPARATOR: H(i) against H(i-1), paired, same scenarios           |
   |  visible dev set for the optimizer, hidden holdout for you         |
   +----------------------------------+---------------------------------+
                                      |  preference plus history
   +----------------------------------v---------------------------------+
   |  MUTATOR: proposes H(i+1), one component at a time                 |
   |  sees history, never the rubric, never the holdout                 |
   +----------------------------------+---------------------------------+
                                      |  proposed diff to harness only
   +----------------------------------v---------------------------------+
   |  GATE: regression, holdout delta, cost delta, safety, human        |
   |  accept, reject, or promote. reject keeps the incumbent.           |
   +----------------------------------+---------------------------------+
                                      |  accepted revision plus reason
   +----------------------------------v---------------------------------+
   |  EXPERIENCE STORE: what worked, on which model, on which tasks     |
   +--------------------------------------------------------------------+
```

### The eight components

| Component | Job | Failure if missing |
| --- | --- | --- |
| Contract lock | Define what cannot change, and hash it | The loop edits the tests |
| Scenario bank | Fixed, stratified, versioned tasks with hidden split | The loop overfits the visible set |
| Verifier | Deterministic before probabilistic | Judged gains that do not exist |
| Comparator | Paired comparison, same snapshot, same runs | Noise read as progress |
| Mutator | Propose one change, with a rationale and an estimate | Random walk with a story |
| Gate | Accept only on holdout plus cost plus safety | Silent regression |
| Experience store | Record what worked and where | Every campaign starts from zero |
| Rollback | One command to restore `H(i-1)` | A bad revision you cannot undo |

The rollback item is not an afterthought. If reverting is expensive, the gate becomes
political, and a gate that is political is not a gate.

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
measurement:
  scenarios: dev-v4
  holdout: holdout-v2
  runs: 3
  model: pinned-2026-11-01
decision: null
```

### Budget the search, not just the task

The loop has two budgets and most teams only track one.

| Budget | What it covers | Practical rule |
| --- | --- | --- |
| Delivery budget | Tokens, steps, minutes per task | Set per task contract, as in the harness design guide |
| Search budget | Traces, judgments, dollars per revision | Small enough that one revision cannot blow the week |
| Total budget | Delivery plus search | If search exceeds 20 percent of delivery spend, the loop is not paying for itself |

That third row is the one that keeps a self-improving harness honest. A loop that spends
40 percent of its budget improving itself had better be producing harness improvements that
generalize, or it is a very expensive hobby.

### Acceptance rule with elitism

RHI's missing piece, stated as a rule:

```
accept(H(i+1)) iff
    resolved(H(i+1)) >= resolved(H(i)) - epsilon_regression     # quality
and cost(H(i+1))    <= cost(H(i)) * (1 + cost_ceiling)          # cost
and invariants(H(i+1)) == all_true                              # must
and holdout_delta(H(i+1)) > 0                                   # generalization
```

Four clauses, each corresponding to a known failure. Quality stops a lucky visible-set win.
Cost stops the compression trap. Invariants stop the cheat. Holdout stops the overfit.

The last clause is the one people skip, and it is the one that separates a search from a
self-delusion. Visible-set improvement is nearly free to obtain. Holdout improvement is not.

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
| Cost per point | Search spend divided by holdout gain | The number to compare against test-time scaling |
| Acceptance rate | Accepted revisions over proposed | Is the mutator any good |
| Revert rate | Accepted then reverted later | Is the gate too loose |
| Time to plateau | Iterations until holdout gain clears noise | Is there headroom |
| Regression rate | Previously passing scenarios now failing | Is the loop trading breadth for depth |
| Failure taxonomy shift | Distribution of failure classes per iteration | Where the bottleneck moved |

That last metric is the most actionable and the most often omitted. RHI's story is a taxonomy
shift: contracts improved, cache traffic fell, and the remaining failures moved. A single
score would have hidden the mechanism.

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
to attribute. So in simulation, log:

- Total tokens by role: action model, proposer, judge, router.
- Total dollars, including the judge, which is easy to forget.
- GPU or wall-clock hours for verification.
- Human minutes reading traces and diffs.

Then answer the only question that matters: **compared with spending the same budget on more
test-time compute, does the loop win?** If you cannot answer that, you have built a very
elaborate way to feel productive.

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

## Guardrails

The three failure modes, their published evidence, and the mechanism that addresses them.

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
| The loop costs more than it saves | Search spend exceeds delivery spend | Budget ratio, stop rule |
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

Exit: a deliberately bad revision is rejected, and the rollback is exercised for real.

**Stage 6: the experience store.**

Structured records: environment, observation, effect. Model version, task class, component,
outcome.

Exit: a new campaign warm-starts from the store and reaches its previous best faster.

**Stage 7: branching, if the single trajectory plateaus.**

Two branches, evolving subsets, coverage voting, branch-local guidance. Only after stage 5
proves the gate works, because branching multiplies whatever the gate does wrong.

Exit: routed holdout beats the better single head.

**Stage 8: the router.**

Fit on head-exclusive development cases. Evaluate on fresh exclusive cases.

Exit: routing beats the best head on at least two of three task families, or drop the router.

**Stage 9: adversarial hardening.**

Run the attack table from the simulation section against the real loop.

Exit: every attack is caught, and the catch is logged.

**Stage 10: scheduled re-evaluation.**

Every model upgrade triggers a component ablation. Components that no longer pay are deleted.

Exit: a written record of what was removed and why, per model generation.

The ordering is the EVO ordering: value first, cost second, complexity last. Most teams
invert it, build the branching router, and discover they cannot tell whether any of it helped.

## What does not transfer

Honesty section. These are the limits you should carry into any adoption decision.

**Task-specific does not mean general.** RHI produces a harness per task. That is a real
benefit for repeated similar work and a real cost for diverse work, where you pay the search
cost per task. The paper's framing is continual specialization, not one universal harness.

**Prompt-level gains may not survive a model change.** RHI's gains persist across three model
generations, which is encouraging. But the mechanism is context management, and context
management is exactly what providers keep improving for free. Re-test, do not assume.

**The judge is the soft spot.** Two of the three papers rely on LLM judgment for the signal.
Positivity bias, prompt sensitivity, and model-version drift all leak into the objective.
Deterministic verifiers are better wherever the task allows them.

**Synthetic tasks are not your repository.** Thirty generated ML research tasks, Olympiad
problems, and terminal benchmarks are all cleaner than a ten-year-old codebase with flaky
tests and undocumented invariants.

**Hardware results do not transfer.** InfraRSI's sign flips across H20, H100 and H200 are the
clearest demonstration that a learned prior can be actively wrong on new hardware.

**The search cost is easy to hide.** The branching paper admits unequal token budgets. RHI's
cited finding is that search cost can erase the gains entirely. Count it.

**The recursion is shallow.** Nobody in these papers improves the improver. The mutator is a
fixed model with a fixed prompt. A true second-order loop, where the optimizer improves the
optimizer, squares the verification problem: you would need to verify that the improved
verifier is still honest. That is where the concept becomes genuinely hard, and no paper here
crosses that line.

**Dev and test overlap flatters everyone.** Meta-Harness gains 3 points on math if you let
test outcomes select among candidates. Any paper reporting search-set performance as a
headline is reporting an optimistic number, and the branching authors say so.

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
fitting. Cost rose 9 percent, inside the ceiling. Review minutes unchanged.

**Thursday: the second revision, and a rejection.**

The mutator proposes enabling context compression to recover the cost increase. The failure
taxonomy from the harness study is in its history, so it also predicts a 4-point loss. The
measurement agrees: visible 46, hidden 40. Rejected under the quality clause. The incumbent
stays.

This is the most valuable day of the week, and it produced no improvement. It prevented a
plausible-looking cost optimization from erasing the first gain, and it cost 2.40 USD.

**Friday: stop, and write it down.**

Two revisions, one accepted, one rejected. The holdout moved 3 points. The decision log
records both estimates against both results. The next hypothesis, chosen because the taxonomy
moved rather than because it is interesting, is about specification quality rather than
another harness component.

**What a week bought:** +3 points of real holdout improvement, one prevented regression, two
calibration data points, and a stop decision made on evidence rather than fatigue.

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

## Checklist

- [ ] The evaluator is read-only, hashed, and runs in a separate process.
- [ ] The optimizer never sees the rubric or the holdout split.
- [ ] A contract, not the model, decides whether a task is complete.
- [ ] Must-level invariants zero the candidate on violation.
- [ ] A hidden holdout exists, and it is reported once per harness version.
- [ ] One component changes per revision, with a written rationale and estimate.
- [ ] Revisions are paired comparisons on the same scenarios and model snapshot.
- [ ] The gate has quality, cost, invariant and holdout clauses.
- [ ] The incumbent is kept on rejection, and rollback is one command.
- [ ] Search cost is measured in dollars, not just in tokens.
- [ ] Search spend is under 20 percent of delivery spend, or there is a reason.
- [ ] The visible and hidden curves are plotted together.
- [ ] There is a stop rule, and it has been used at least once.
- [ ] The failure taxonomy is reported per iteration, not just the score.
- [ ] The adversarial attack table has been run against the real loop.
- [ ] Every revision has a version, a decision, and a reason.
- [ ] Components are re-ablated at every model upgrade, and dead ones are deleted.
- [ ] A human promotes; the loop proposes.

## References

The three papers this page is built on:

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

The measurement base:

- Haichuan Hu et al., "Beyond the Model: Demystifying Harness Effects in Software Engineering
  Agents", arXiv 2609.32459, September 2026. Harness gap of 19.4 points, model gap of 22.8,
  NanoHarness component ablations.
  https://arxiv.org/html/2609.32459v1

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
