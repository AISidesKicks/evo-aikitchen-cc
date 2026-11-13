# Benchmarks

The task corpus lives here. One JSON object per line in `tasks.jsonl`, one task
per line, no trailing commas.

`tasks.example.jsonl` is a schema example, not a runnable corpus. Copy it to
`tasks.jsonl` and replace the placeholders with real tasks from this repository.

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

## Sizing

| Purpose | Tasks | Rough resolution |
| --- | --- | --- |
| Smoke test | 20 | 20 points |
| Weekly comparison | 120 | 9 points |
| Promotion gate | 300 | 6 points |
| Small effects | 1,000 plus a paired design | 2 to 3 points |

Start with 20. A bench you trust at 20 tasks beats a bench you abandoned at 300.
