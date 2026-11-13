# Benchmarks

The task corpus lives here. One JSON object per line in `tasks.jsonl`, one task
per line, no trailing commas.

`tasks.example.jsonl` is a schema example, not a runnable corpus. `tasks.jsonl`
is the real one, and it currently holds seven tasks against the `calc` fixture.

## Why a task corpus and not a public benchmark

A public benchmark tells you how a model compares to other models. It does not
tell you whether your harness improved on your repository. See
[the evaluation guide](../mds/evo-benchmark-evals.md) for the five distances
between a benchmark score and delivered value, and for the arithmetic that says
how many tasks a decision needs.

## The task card

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable identifier, never reused |
| `prompt` | yes | Exactly what the agent sees |
| `acceptance` | yes | The command that decides pass or fail |
| `class` | no | Bug fix, feature, refactor, migration, test, docs |
| `source` | no | Incident, commit, release note, synthetic |
| `repo` | no | Repository path or remote |
| `commit` | no | Starting commit |
| `regression` | no | What must keep passing |
| `budget` | no | `{"turns": 20, "usd": 2.0}` |
| `difficulty` | no | Easy, medium, hard |
| `contamination` | no | Private, post-cutoff, public, unknown |
| `partial` | no | What a half-done attempt should score |
| `notes` | no | Anything the grader or the reader needs |

The `partial` field is the one people skip. If you cannot say what half-done
looks like, your partial-credit scoring is a guess.

## Rules

1. **Freeze before a campaign.** No edits to tasks or acceptance checks while a
   comparison is running. If a grader is wrong, stop, bump its version and
   re-run the baseline.
2. **Gold control first.** The reference patch must score 100 percent. If it
   does not, the task is broken and every comparison on it is measuring the
   error.
3. **Null control second.** An agent that does nothing must score 0.
4. **Rotate.** Retire tasks every variant passes, add fresh ones monthly, and
   keep a small permanent core that is never used for tuning.
5. **Stratify.** Keep the class mix in proportion to the real backlog, not in
   proportion to how easy the task was to write.

## Layout

```
benchmarks/
  tasks.jsonl          the corpus, one task per line
  tasks.example.jsonl  schema example
  fixtures/calc/       the starting code for the calc tasks
  gold/<task-id>/      the reference solution, copied over the workspace
  variants/<name>/     candidate configurations: variant.toml and system.md
```

A task names its starting code with `fixture` and its reference solution with
`gold`. Both are paths relative to the repository root. A gold entry may be a
directory of replacement files, which is easy to author, or a `.patch` file
applied with `git apply`, which is what to use once tasks come from real
commits.

The `calc` fixture is a toy on purpose: it makes the controls cheap to run and
the failure modes obvious. Real tasks should come from commits and incidents in
this repository or the repositories you actually ship.

## Variants and cycles

A variant is a candidate configuration: prompt text, model, turn budget, tool
allow list. It lives in `benchmarks/variants/<name>/`:

```
variants/strict/
  variant.toml    model, tools, max_turns, notes
  system.md       text appended to the base system prompt
```

The shipped variants change the prompt one at a time, with no turn-budget change,
because a variant that changes two things measures neither. The first campaign in
this repository proved the point: two variants that also cut the turn budget lost
badly, and every failure landed exactly on its cap. That was the budget, not the
prompt.

The directory name is the variant's identity, so there is only one source of
truth. A variant with no files is an exact copy of the baseline, which is a
useful control.

A cycle runs the baseline and every candidate over the corpus and gates each
candidate against the baseline:

```sh
python -m evo_bench cycle --candidates strict,smallest-diff --max-usd 5
```

It writes `runs/cycle.jsonl` and a readable `runs/cycle-summary.md` with one gate
report per candidate. `--max-usd` stops the cycle between runs, so the cap is a
budget rather than a report.

The cycle does not invent variants. Someone, or something, writes a variant
directory; the cycle measures it fairly. That is the honest division of labour
until a generator exists, and it keeps every candidate reviewable as a diff.

## Truncated runs

A run that stops at the turn cap is recorded with `exit_reason = max_turns`, not
`graded`. The distinction matters: a truncated run did not fail, it ran out of
budget, and a comparison made mostly of truncated runs measures turn efficiency
rather than quality. The gate refuses to decide when more than half the runs were
capped, and the report counts them per variant.

This came from a real campaign on three mined tasks. At twelve turns the
baseline scored 0/3 and the `strict` variant 2/3, and every run ended
mid-tool-call. The tempting reading was "the stricter prompt helps". The correct
reading was "twelve turns is fewer than these tasks need". Re-running the same
two variants at thirty turns gave 3/3 and 3/3, delta zero, exact McNemar p = 1.0,
with every run finishing rather than being capped. The gain was the budget, not
the prompt.

## Saturation

Mining click produced 67 tasks that a 30-turn budget solves almost completely:
the baseline passed every one of the first ten runs. A corpus the model already
solves measures nothing about capability, because a variant cannot beat 100
percent. Two honest responses, and this bench uses both:

- run at a **tighter budget** (20 turns) so the tasks that need 26 turns have to
  be done more efficiently, which is a real engineering question;
- report **cost and turns per success** when pass rates saturate, because a
  variant that reaches the same score in half the turns is a genuine improvement.

The failure to avoid is quoting "no difference in pass rate" from a corpus where
the pass rate was pinned at 100 percent.

## Concurrency

`--concurrency N` runs N tasks at once. Runs are independent by construction:
each gets its own workspace copy, its own sandbox and its own trace file, and the
only shared state is the ledger append, which is serialised by a lock. This is
the only setting that shortens a campaign without weakening it, since lowering
the turn budget changes what is being measured.

## Deadlines and estimates

`--deadline SECONDS` bounds a single run by wall clock. The budget cap stops a
campaign between tasks, which is too late for one run that will not stop; a run
that hits the deadline is recorded with `exit_reason = deadline`.

`evo_bench estimate` costs a campaign before it starts, using the token averages
observed in a previous ledger rather than a guess:

```sh
python -m evo_bench estimate --tasks benchmarks/mined/tasks.jsonl \
    --candidates 1 --ledger runs/click24.jsonl
```

## Trials and reliability

`--trials k` runs each task k times, and both `compare` and the report aggregate
as `pass^k`: a task counts only when every trial passed. A variant that succeeds
two times in three is not a 67 percent variant for unattended work.

`--trials` disables the response cache on purpose. Replaying a stored answer for
every trial reports perfect reliability, which is the opposite of what a trial is
for.

## Mining a real corpus

The `calc` fixture proves the plumbing. Real tasks come from a repository's own
history:

```sh
python -m evo_bench mine --repo /path/to/repo --limit 12
python -m evo_bench control --tasks benchmarks/mined/tasks.jsonl
```

A commit becomes a task when it changes both tests and source. The fixture is the
tree at the parent commit with the *new tests* overlaid, so the tests fail before
the change and pass after it. The gold solution is the source half of the commit,
written as a patch. Only the tests that actually flip are graded, because every
repository has pre-existing failures in any given environment.

Mined cards live in `benchmarks/mined/tasks.jsonl`, with gold patches beside them.
Fixtures are materialised under `scratch/mined/` and are gitignored: they are
regenerable and they are large.

Four details decide whether a mined task is real or noise, and all four were bugs
before they were rules:

1. **The workspace must shadow installed packages.** `PYTHONPATH=src` is part of
   the acceptance command. Without it, `import click` resolves to site-packages
   and the agent's edit has no effect on the score.
2. **Node ids, not files.** Tests are named individually, and parametrised ids can
   contain quotes, so they are shell-quoted with `shlex.quote`.
3. **`git apply` must not escape the workspace.** A fixture inside another
   repository makes git discover the outer one and apply the patch against the
   wrong root, so the ceiling is pinned to the workspace parent.
4. **The sandbox workspace is writable.** A read-only mount means the agent cannot
   edit files through `bash` and pytest cannot write its cache.

The miner keeps a task only if its gold patch makes the named tests pass. The next
step is `evo_bench control`, which checks the same thing under the sandbox, and
that is the gate every task must clear before it can affect a decision.

## Commands

```sh
pixi run control                                  # gold must pass, null must fail
python -m evo_bench run --provider fake --limit 3 # dry run, no credentials
python -m evo_bench compare runs/a.jsonl runs/b.jsonl --labels before,after
python -m evo_bench gate runs/a.jsonl runs/b.jsonl --labels before,after
```

`gate` applies the promotion policy and exits 0 only on a promote. The default
policy needs 20 paired tasks, a significant paired difference, no more than a 20
percent rise in cost per success, and no regression on the holdout split
(`"split": "holdout"` on a task). Lower `--min-tasks` when the corpus is smaller,
and write down that you did.

Nothing is worth measuring until `pixi run control` is green.

## Sizing

| Purpose | Tasks | Rough resolution |
| --- | --- | --- |
| Smoke test | 20 | 20 points |
| Weekly comparison | 120 | 9 points |
| Promotion gate | 300 | 6 points |
| Small effects | 1,000 plus a paired design | 2 to 3 points |

Start with 20. A bench you trust at 20 tasks beats a bench you abandoned at 300.
