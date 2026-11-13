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
  variant.toml    max_turns, model, tools, notes
  system.md       text appended to the base system prompt
```

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
