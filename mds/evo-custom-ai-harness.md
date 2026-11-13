# Choosing a custom AI harness: Tau, JAZ and the minimal Python field

You can build an agent harness out of skills and hooks. Plenty of people do, and the
results look fine in a demo. Then the demo becomes a nightly job, the nightly job runs
unattended for six hours, and you discover that skills and hooks were never the harness.
They were two layers of it.

The harness is the thing that decides what the model sees, what it is allowed to touch,
what it costs, what happens when it fails, and how anyone proves afterwards that the run
was worth its money. Skills are one input to that. Hooks are one control surface on it.
The rest - the loop contract, context projection, compaction, delegation, budgets,
permissions, the session store, tracing, evaluation, interfaces, distribution and model
access - is where the engineering actually lives.

That is the argument of this page. It is also why the tool choice matters more than it
looks. Two harnesses can both advertise "skills and hooks" and differ by an order of
magnitude in what they can safely do on a Tuesday night with nobody watching.

This page compares six of them, in depth:

- **Tau** (Hugging Face, `huggingface/tau`, MIT) - a small Python coding agent you can
  read in an afternoon, with a real TUI, print mode, RPC and a Python SDK.
- **JAZ** (MIT CSAIL, arXiv 2609.26891) - a research framework built on a single
  language primitive, `invoke`, with published results on long-horizon recall and
  continual self-improvement.
- **smolagents** (Hugging Face, Apache-2.0) - the code-agent library that made
  "agents write Python" normal.
- **OpenAI Agents SDK** (MIT) - a small set of primitives with tracing and handoffs.
- **Pydantic AI** (MIT) - a typed agent runtime with an opinionated harness package and
  durable execution.
- **mini-swe-agent** (Princeton and Stanford, MIT) - the hundred-line agent that scores
  above 74 percent on SWE-bench verified.

And one ancestor, because it explains Tau: **Pi** (Earendil Inc, MIT) is the TypeScript
harness Tau re-derives. Pi is not the subject of this page, but you cannot evaluate Tau
without knowing what it inherited and what it left behind.

If you already like Tau for the reason most people like it - a good terminal loop for a
human, plus a scriptable path for automated runs - this page will not talk you out of it.
It will tell you where that combination wins, where it silently does not, and what to
build around it so the second half is true.

Read [Building a custom AI harness with EVO principles](evo-in-ai-harness.md) for the
design vocabulary, and [Simulating and building a self-improving EVO
harness](evo-rsi-harness.md) for the loop that improves the thing you build here.

## Contents

- [The claim in one page](#the-claim-in-one-page)
- [Skills and hooks are layers two and nine](#skills-and-hooks-are-layers-two-and-nine)
- [The thirteen layers of a harness](#the-thirteen-layers-of-a-harness)
- [What breaks when a layer is missing](#what-breaks-when-a-layer-is-missing)
- [Four clusters, in detail](#four-clusters-in-detail)
- [Tau in depth](#tau-in-depth)
- [JAZ in depth](#jaz-in-depth)
- [The rest of the field](#the-rest-of-the-field)
- [Head to head](#head-to-head)
- [Language is a layer: the Python-only rule](#language-is-a-layer-the-python-only-rule)
- [Where Tau wins](#where-tau-wins)
- [Where Tau loses, and what beats it](#where-tau-loses-and-what-beats-it)
- [The architecture I would actually run](#the-architecture-i-would-actually-run)
- [Mapping to EVO E1 to E10](#mapping-to-evo-e1-to-e10)
- [Build order](#build-order)
- [Limits and open questions](#limits-and-open-questions)
- [Checklist](#checklist)
- [References](#references)

## The claim in one page

A harness is a contract between three parties who do not trust each other: the model, the
machine, and the person paying. Every layer exists to make one of those relationships
explicit.

The model needs a loop it can predict, tools it can call, and a context it can afford.
The machine needs a boundary it cannot be talked out of. The payer needs a number and a
receipt. If a harness leaves any of those implicit, the model fills the gap with
improvisation, and improvisation is exactly what you cannot audit at 3am.

Skills address the first need, weakly: they are deferred instructions. Hooks address the
second and third, weakly: they are callbacks that can observe and sometimes veto. Neither
addresses context projection, session durability, evaluation, or distribution. That is
the gap this page is about.

The practical consequence is a split in how you should use the tools:

- **Tau is an operator shell.** It is very good at being the thing a human drives and a
  script invokes. It is not trying to be the thing that scores itself.
- **JAZ is an experiment bench.** It is very good at expressing a loop compactly,
  replaying it, and measuring it. It is not trying to be a product.
- **Pydantic AI is a service runtime.** It is very good at typed outputs, durable
  execution, and OpenTelemetry. It is not trying to be a terminal.
- **mini-swe-agent is a control.** It is very good at being small enough to trust and
  fast enough to run in batches. It is not trying to be extensible.

Picking one and forcing it to do all four jobs is how harness projects fail. Picking the
seam between them is the actual design decision.

## Skills and hooks are layers two and nine

It is worth being precise about what these two mechanisms can and cannot do, because the
marketing makes them sound like the whole architecture.

A **skill** is a directory with a `SKILL.md`, a name, a description and some supporting
files. The harness advertises the name and description in the system prompt and loads the
body only when the model asks. Tau implements the Agent Skills specification and follows
Pi here. A skill can:

- change what the model knows for one part of the task,
- ship scripts and reference files next to the instructions,
- be forced by a human with `/skill:name`,
- be hidden from automatic selection with `disable-model-invocation: true`.

A skill cannot:

- change the loop,
- change what tools exist,
- change what the run costs,
- survive compaction on its own,
- stop a bad tool call,
- score the result.

That is not a criticism. Deferred instructions are a genuinely good idea, and the
progressive disclosure model is why a 400-line skill can sit in a harness all day without
costing context. But a skill is a document. Documents do not enforce anything.

A **hook** is a callback on a lifecycle event. Both Tau and Pi expose a rich set. In Tau
the intercepting ones are `input`, `tool_call` and `tool_result`; the observing ones are
`agent_start`, `agent_end`, `agent_settled`, `turn_start`, `turn_end`, `message_start`,
`message_update`, `message_end`, `tool_execution_start`, `tool_execution_update`,
`tool_execution_end`, `queue_update`, `compaction_start`, `compaction_end`,
`entry_appended`, `session_info_changed`, `thinking_level_changed`, `auto_retry_start`
and `auto_retry_end`. Hooks can:

- block a tool call and tell the model why,
- rewrite tool arguments before execution,
- rewrite a tool result after execution,
- transform or consume raw user input,
- inject messages and prompt sections,
- persist extension-owned entries into the session,
- render custom transcript rows,
- mount widgets and intercept keys,
- observe every token if you want to pay for it.

Hooks cannot:

- guarantee the process is sandboxed,
- guarantee a dollar budget,
- replay a run from a saved trace,
- compare two runs statistically,
- ship themselves to another machine.

Tau's own docs are refreshingly blunt about the boundary: "Project trust is not a process,
filesystem, network, credential, tool, model, or prompt-injection sandbox." That sentence
is the whole reason this page exists. A hook-level permission gate is a suggestion to a
cooperative model. A boundary is a boundary.

So: skills are layer two, hooks are layer nine. There are eleven more.

## The thirteen layers of a harness

Here is the full stack, with the honest answer to "do skills or hooks cover this".

| # | Layer | The question it answers | Covered by skills or hooks? |
| --- | --- | --- | --- |
| 1 | Loop control | When does a turn end, when does the run end, what happens on retry or overflow? | hooks can observe and sometimes interrupt, not define |
| 2 | Context projection | What exactly is in the request, in what order, with what cache behaviour? | skills are one input, hooks can rewrite |
| 3 | Compaction and memory | What leaves the window, what is summarised, what is retrievable later? | hooks can replace the summariser |
| 4 | Tool registry | What can be called, with what schema, and what stays hidden until asked for? | no |
| 5 | Delegation | What is handed to another agent, with what context and budget? | no |
| 6 | Budgets and accounting | Who stops the run when the money or the clock runs out? | hooks can enforce piecemeal, skills cannot |
| 7 | Permissions and trust | What is allowed to touch the machine, and who approved it? | hooks gate weakly, skills cannot |
| 8 | Session store | Can you resume, fork, replay and audit a run after the fact? | no |
| 9 | Observability | Can you reconstruct what happened without reading the transcript by hand? | hooks are the seam, not the store |
| 10 | Evaluation | How is a run scored, and what stops a regression? | no |
| 11 | Interfaces and protocols | TUI, pipe, JSON stream, RPC, in-process SDK: who drives it? | no |
| 12 | Distribution | How does a customisation travel to another machine or another person? | skills and extensions get packaged here |
| 13 | Model access | Which providers, credentials, retries, and cost tables? | no |

Seven of thirteen are untouched by both mechanisms. Three more are only partly reachable.
That is the arithmetic behind the claim.

The layers are not equally valuable. From the 2026 evidence in
[EVO in the AI harness era](evo-in-ai-era.md), the layers that move benchmark scores most
are 2, 3, 4 and 5 - context, compaction, tools and delegation. The layers that decide
whether you can run the thing unattended are 6, 7 and 8. The layers that decide whether
you learn anything are 9 and 10. A harness that is strong on the first group and empty on
the second is a demo. A harness that is strong on the second and empty on the first is a
sandbox with no agent in it. You want both, and almost nobody ships both.

## What breaks when a layer is missing

This is the table to keep. Every row is a failure I have seen in harness write-ups or
reproduced while thinking through this page.

| Missing layer | Symptom | Cheapest fix |
| --- | --- | --- |
| Loop control | A run never settles, `agent_end` fires three times, and the wrapper starts a fourth | Port a `finish_turn` style host callback and a `max_turns` cap |
| Context projection | The model forgets the task it was given while still holding the file it read | Build the prompt from explicit sections, diff the sections, patch instead of replace |
| Compaction | Summaries quietly drop the acceptance criteria, so the agent declares success early | Keep the task contract out of the compacted span; re-inject it every turn |
| Tool registry | Twenty tools are declared, the model calls the wrong one, and the schema is the only documentation | Declare four tools by default, expose the rest through search |
| Delegation | Subagents return prose, the parent cannot verify it, and the budget doubles | Require a typed result and pass a budget reference, not a copy |
| Budgets | A $4 experiment costs $180 because a retry loop was not counted | One ledger per run tree, checked before each request, not after |
| Permissions | An unattended run edits `.env` because the model was asked nicely not to | Container plus a read-only mount; the hook is a second line, not the first |
| Session store | You cannot reproduce yesterday's failure because the transcript was pretty-printed to stdout | Append-only JSONL with a tree, replayed into the next run |
| Observability | Debugging means scrolling a terminal and guessing which tool call burned 40k tokens | One event per span with tokens, cost and duration attached |
| Evaluation | Every change "feels better" and the score drifts down for three weeks | A frozen task set and a gate that blocks promotion |
| Interfaces | The interactive path and the CI path drift until they are different agents | One core, several frontends, one event contract |
| Distribution | The improvement lives on one laptop | Versioned packages with pinned refs |
| Model access | A provider outage looks like an agent failure | Explicit retry classification and a documented fallback |

## Four clusters, in detail

The thirteen layers group into four questions. This is where the depth is, and where the
difference between Tau and JAZ becomes concrete.

### Cluster A: the loop and what it sees (layers 1, 2, 3)

The loop is easy to write and hard to get right. The hard part is not "call the model,
run the tool". The hard part is knowing when the run is actually finished.

Tau and Pi both solve this with a two-level notion of completion. `agent_end` means one
low-level run finished. It does not mean the agent is done, because an automatic retry, a
threshold compaction, or a queued follow-up can start another run immediately.
`agent_settled` means nothing further will happen without new input. Tau's docs spell this
out, and the events table shows `agent_settled` as "the started run has finished teardown
and has no automatic retry, compaction, or continuation remaining".

That distinction is not pedantry. If your orchestrator treats `agent_end` as "done", you
will ship a harness that double-counts cost, races the next task against a queued
compaction, and occasionally starts two runs on one session. It is one of the cheapest
correctness wins available, and it comes free if you pick a harness that already made the
distinction.

Tau goes further than most by exposing `finish_turn` on the portable harness config. It
runs after the assistant message and tool results are appended, before `TurnEndEvent`,
and returns either `action="end"` or `action="continue"`. That is a host policy seam: the
coding app decides that a successful `submit_results` call ends the run, without the agent
core knowing what `submit_results` is. Tau's docs call it "Pi's `finishTurn` scheduling
contract with Python names and typed dataclasses". This is a good pattern and worth
copying even if you do not use Tau.

The companion feature is terminating tools. A tool can return
`AgentToolResult(..., terminate=True)` to submit a final answer without a follow-up model
call. The batch rule matters: a mixed batch continues, and a batch terminates only when
every final result opts in, after tool-result hooks. That prevents a parallel tool fan-out
from ending the run halfway through.

JAZ solves the same problem differently, and the difference is the point. There is no
"turn" object to finalise, because the model is writing Python. The loop is a REPL: the
model emits code, the code runs, the output comes back, repeat. Termination is the code
returning. That is simpler and more expressive, and it gives up the structured event
stream that a TUI needs.

Context projection is where Tau and Pi are strongest relative to the Python field. Pi
builds the request from base instructions, discovered context files, tool definitions and
skill descriptions, and it patches changed sections rather than replacing the whole prompt,
which preserves the provider's cached prefix. Tau ports the shape: a Pi-style prompt
builder, tool snippets and guidelines, a skill index, project context, and a date and
working-directory suffix. The practical result is that adding one extension guideline does
not invalidate the entire prompt cache on every turn.

Compaction is where most harnesses quietly lose the plot. Tau stores an append-only JSONL
tree and writes a compaction entry with a `first_kept_entry_id`, which replays as "insert
the summary, then keep that entry and everything after it". It is Pi-compatible and it does
not rewrite history, so the original entries remain inspectable. Pi's version is documented
in more detail: a 16,384-token reserve by default, 20,000 recent tokens kept, a cut point
that never lands inside a tool result, tool results truncated to 2,000 characters during
summarisation, and a structured summary with Goal, Constraints and Preferences, Progress,
Key Decisions, Next Steps and Critical Context.

That structure is not decoration. The "Constraints and Preferences" section is what keeps
the acceptance criteria alive after the fifth compaction. If your harness summarises to
prose, the constraints evaporate first, because they are the least token-dense part of the
conversation.

JAZ's answer to the same problem is more radical: do not compact, delegate. When the
window fills, the agent calls `invoke` again and passes `prev_history` by reference along
with a progress summary. The full history stays in the REPL as a Python object. That is
tail-recursive delegation, and the paper reports it beating a dedicated memory system on
far recall at less than half the cost. Numbers below.

### Cluster B: what the model can do (layers 4, 5)

The tool registry is the layer people most often mistake for the harness. It is one layer.
What matters is not the count of tools but the declaration policy.

Pi and Tau both default to four tools: read, bash, edit, write. Everything else is opt-in.
Pi adds grep, find, ls and a Windows powershell tool. Then it adds two mechanisms that
change the economics: `codemode`, which runs JavaScript in a QuickJS sandbox with
`tools.<name>(args)` so the model can call several tools and filter output before it
reaches the context, and `tool_search`, which declares only the tools the model asked for.

Tau has the same four tools and the same extensibility, but not codemode or tool search.
That is a real gap for large tool surfaces and worth knowing before you port a Pi
workflow. Tau's built-in tools live in `tau_coding/tools.py` at 1,218 lines, which tells
you the interesting complexity is in the coding tools, not the loop.

Delegation is the layer with the widest gap between harnesses.

- **Tau**: not built in. Subagents are an extension. The reference implementation is
  `rian-dolphin/tau-subagents`, a port of `pi-subagents`, which spawns in-process
  `CodingSession`s with their own tools and system prompts, foreground and background
  modes, agent types in `.tau/agents/*.md`, plus `get_subagent_result` and
  `steer_subagent` tools. It is good work, and it is an extension, which means you own it.
  Two seams make it possible: `trust_override` so a child inherits the parent's project
  trust decision instead of silently losing skills and `AGENTS.md`, and
  `allowed_tool_names` so a child can be restricted to `read` and `bash` in a way an
  extension cannot bypass.
- **JAZ**: recursion is the default. `invoke` calls `invoke`, and the budget pool is
  shared across the whole tree unless you scope it otherwise. This is the single cleanest
  delegation model in the field, because delegation is a function call, not a protocol.
- **OpenAI Agents SDK**: handoffs and agents-as-tools, with the runtime owning the loop.
- **Pydantic AI**: `SubAgents` as a capability, composable with the rest.
- **Claude Agent SDK**: subagents are a first-class capability with permissions.
- **mini-swe-agent**: none, on purpose.

The lesson is not "Tau is bad at delegation". It is that delegation is a design decision
with a trust and budget consequence, and a harness that leaves it to an extension is
telling you to make that decision explicitly. That is arguably healthier than a harness
that spawns subagents by default and silently multiplies your bill.

### Cluster C: what it costs and who allows it (layers 6, 7)

Budgets split into two very different things: accounting and enforcement. Almost every
harness has the first. Few have the second.

Tau has real accounting. Its HTML session export includes a Cache tab that summarises the
active branch's model requests, prompt caching, output and reasoning tokens, estimated
API-rate cost, tool calls and compactions, with summary-generation requests labelled
separately. That is a genuinely good artifact and better than most commercial tools. What
it does not have is a dollar budget that stops a run. It has `max_turns` and cancellation.

JAZ has enforcement. `BudgetPool(cost_budget=..., calls_budget=...)` is enforced across the
whole invoke tree, including recursive sub-invokes, and `IterationLimit`, `RecursionLimit`,
`BudgetForcing` and `ContextWindowWarning` cover the other dimensions. The scoping rule is
the clever part: a hook passed positionally to `invoke` applies only to that call, while a
hook activated as a context manager applies to every call under the `with` block. That is
exactly the semantics you want for "this experiment gets $5, the whole sweep gets $50".

Pi sits between them with something unusual: a `cache_warming_decision` event that carries
`warmCost`, `missCost` and `continuationProbability`, and lets an extension override
whether to warm the prompt cache. I have not seen another harness expose prompt-cache
economics as a first-class hook. If you run long sessions with a stable prefix, that is
real money.

Permissions are the weakest layer across the entire Python field, and Tau is honest about
it:

- Extensions "execute arbitrary Python with your user permissions".
- Project extensions are off by default and require both trust approval and
  `--project-extensions`.
- The docs state plainly that trust "is not a process, filesystem, network, credential,
  tool, model, or prompt-injection sandbox".
- The `permission_gate.py` example blocks dangerous bash commands with the `tool_call`
  hook. That is a speed bump, not a boundary, and the docs do not pretend otherwise.

Compare:

- **mini-swe-agent** ships local, docker/podman, singularity/apptainer, bubblewrap and
  contree environments. The sandbox is the product.
- **smolagents** supports sandboxed execution through Modal, Blaxel, E2B or Docker.
- **Pydantic AI** has a workspace-rooted `FileSystem` and an allowlisted `Shell`.
- **Claude Agent SDK** has a real permission system with approval modes.
- **Pi** has no permission popups by design, but documents containerisation as the answer.

So the honest position for Tau is: the permission boundary is the container you run it in,
and the `tool_call` hook is a second line of defence for the cases where the container is
too permissive. Any EVO harness that runs unattended must own that container. No amount of
hook engineering replaces it.

### Cluster D: what survives the run (layers 8, 9, 10, 11, 12, 13)

Sessions. Tau stores append-only JSONL under `~/.tau/sessions/<cleaned-path>-<hash>/`, as a
tree. `/tree` lets you navigate, `S` summarises the branch you are leaving, `L` bookmarks an
entry, `Ctrl+F` shows only labelled entries. Resume validates the active branch and repairs
malformed tool-call history by appending a provider-safe branch rather than rewriting the
JSONL. That repair path is the kind of detail that only appears after real users hit it,
and it is a good sign.

JAZ's equivalent is `TrajectoryRecorder` and `TrajectoryReplay`, which write and read ATIF
trajectories. Replay substitutes saved responses until it runs out, then goes live. That is
the right primitive for a research loop: you can re-run the deterministic part without
paying for it. Tau's session files are better for auditing a human's work; JAZ's
trajectories are better for re-running an experiment. They are not the same artifact and
you should not pretend one replaces the other.

Observability. Tau emits a typed event stream and every frontend consumes it. The TUI,
print mode, JSON mode, RPC and the SDK are all listeners. That is a genuinely good
architecture and it is why Tau's SDK is real rather than bolted on. JAZ emits hooks events
around three spans - Invoke, LLMQuery, REPLExec - each with Enter, Send, Complete and Exit
stages, and ships Langfuse and Jaeger presets. Also good, different shape.

Evaluation. This is where both lose to Pydantic AI and mini-swe-agent. Tau has no scorer.
JAZ has an eval harness in a separate repo (`jaz-lang/jaz-evals`), not in the core. If your
harness is supposed to improve itself, evaluation is not a nice-to-have; it is the fitness
function. You will build it, and the only question is whether you build it inside the
harness or beside it. Build it beside it, with a frozen task set, as
[the RSI page](evo-rsi-harness.md) argues at length.

Interfaces. Tau: TUI, `-p` print, `--mode json`, `--mode transcript`, RPC, Python SDK. That
is the best interface matrix in the Python field, and it is the reason the "human plus
automation" claim holds up. JAZ: a `jaz` console REPL with sugar, plus `-c` for one prompt.
No TUI, no RPC, no SDK. If you want a human to watch, JAZ is not the tool.

Distribution. Tau has `tau install git:...`, a `~/.tau/extensions/` directory, a
`[tool.tau]` manifest, and an extensions marketplace on the roadmap. Pi has a full package
manager with `pi install`, `pi update`, `pi config` and npm or git sources. Tau's docs list
what is missing versus Pi: a complete package manager, custom entry renderers, declarative
keyboard shortcuts, CLI flag registration, system-prompt replacement and context rewriting.
Know that list before you plan a large extension surface.

Model access. Tau covers OpenAI, Anthropic, OpenAI Codex subscription auth, OpenRouter,
Hugging Face and any OpenAI-compatible endpoint including local models, with a
`catalog.toml` you can extend without code. It also routes Hugging Face inference
providers, with `set_inference_provider` and an automatic or fixed mode. That last part is
unusually specific and useful if you are running open models through HF. JAZ defaults to
LiteLLM, with GitHub Copilot and SGLang backends, and a small `BaseLLM` contract
(`complete(messages) -> LLMResponse`) that is easy to implement.

## Tau in depth

Tau is worth understanding on its own terms, not just as "Pi in Python".

### What it actually is

- Repository: `huggingface/tau`, MIT, created 11 June 2026, 3,048 stars on 13 November 2026.
- Distribution: `tau-ai` on PyPI, version 0.4.11, 37 releases, Python 3.12 or newer.
- Install: `uv tool install tau-ai`, `pipx install tau-ai`, `pip install tau-ai`, conda-forge,
  or `pixi global install tau-ai`.
- Command: `tau`. Update with `tau update`.
- Three packages: `tau_ai` (providers), `tau_agent` (portable brain), `tau_coding`
  (the coding app, TUI, tools, sessions).
- Dependency direction is one way: `tau_coding -> tau_agent -> tau_ai`. The core must not
  import CLI, Rich, Textual or resource-loading code.

That last constraint is the whole design. Because the brain is UI-free, the same agent
drives the Textual TUI, print mode, and your own frontend. The docs put it in one line:

```
AgentHarness = reusable brain
CodingSession = coding-agent environment
TUI = one possible frontend
```

The stated reading route is seven files and about 2,300 lines: `events.py` (87),
`_provider_events.py` (93), `tools.py` (118), `loop.py` (376), `harness.py` (259),
`session/jsonl.py` (171), `tau_coding/tools.py` (1,218). You can read the loop in an
evening and the tools over a weekend. That is a genuine strategic advantage over every
other harness in this comparison, because it means you can audit the thing you are about
to trust with your repository.

### The event contract

Everything is an event, and the events are typed. The portable stream in
`tau_agent.events` is: `AgentStart`, `AgentEnd`, `TurnStart`, `TurnEnd`, `MessageStart`,
`MessageUpdate`, `MessageEnd`, `ToolExecutionStart`, `ToolExecutionUpdate`,
`ToolExecutionEnd`. Streaming detail nests under `MessageUpdateEvent.assistant_message_event`
with `text_start`, `text_delta`, `text_end`, `thinking_start`, `thinking_delta`,
`thinking_end`, `toolcall_start`, `toolcall_delta`, `toolcall_end`.

`tau_coding.events` extends that for frontends and SDK users with `agent_settled`, queue
updates, compaction, session-entry and session-info changes, thinking-level changes and
automatic-retry events.

The important detail: the final `AssistantMessage` is authoritative. It persists text,
thinking and tool calls as ordered content blocks. The nested update events are for
responsive rendering only. Saved sessions and provider history replay use the finalised
structured message. If you build a frontend from deltas and never reconcile against
`MessageEnd`, your session replay will diverge from what the model actually saw.

A frontend is a `match` on event types. The docs show one in about a dozen lines. That is
the correct amount of ceremony for a harness extension, and it is why the SDK is credible.

### The SDK is the harness, not a wrapper

This is the detail that decides whether Tau is a tool or a dependency. The Python SDK
(`AgentHarness` in `tau_agent`) is the same object the Textual TUI drives. It is not a
client that shells out to the CLI, and it is not a thin adapter over an HTTP API. If the
TUI can do it, your script can call it.

There are two entry points, and confusing them is the most common mistake:

| You want | Import | You get |
| --- | --- | --- |
| A brain inside your own program | `tau_agent.AgentHarness` | The loop, tools, events, queues and cancellation. No config files, no extensions runtime, no TUI. |
| A full coding environment | `tau_coding.CodingSession` | Everything the CLI has: sessions on disk, project instructions, skills, extensions, trust, tool allow-list. |

The portable config is small enough to quote:

```python
AgentHarnessConfig(
    provider, model, system,
    tools=[],                  # list[AgentTool]
    max_turns=None,
    queue_mode="one_at_a_time",  # or "all"
    session_id=None,
    before_tool_call=None,     # intercept and rewrite arguments
    after_tool_call=None,      # rewrite results
    finish_turn=None,          # host policy: "end" or "continue"
)
```

And the surface on `AgentHarness` is: `prompt(text)`, `prompt_message(msg)` and
`continue_()` returning an async iterator of events; `steer()` and `follow_up()` for
queued input; `subscribe(listener)` returning an unsubscribe callable; `cancel()`;
`append_message()` and `replace_messages()`; plus read-only `messages`, `is_running` and
`queued_messages`.

Three implementation choices make that surface trustworthy for unattended work:

1. **The queue is enforced, not suggested.** `prompt()` raises `RuntimeError` if a run is
   already active, and the error tells you to use `steer()` or `follow_up()`. You cannot
   accidentally start two runs on one session.
2. **Interrupted tool calls are repaired on every run.** `_append_interrupted_tool_results()`
   runs at the start of each run and again in the `finally` block after a cancel,
   synthesising error results for dangling tool calls and pushing them to subscribers as
   well as to the consumer. That is the "session died mid-tool-call" bug, fixed in about
   twenty lines, and it is why a resumed run does not 400 on provider history validation.
3. **`finish_turn` is a host callback, not an extension hook.** The coding app decides that
   a successful `submit_results` call ends the run, and the portable core never learns what
   `submit_results` is. That is the correct direction of dependency for a harness you plan
   to score: policy lives above the loop.

For an EVO harness, the split writes itself. `AgentHarness` is what the bench and the
scorer call, because it has no opinions about your filesystem. `CodingSession` is what CI
calls, because it has durable sessions and a non-zero exit code on failure. Same core,
two levels of opinion, one event contract.

What the SDK does not give you, as of 0.4.11: a per-request context rewriting hook, a
system prompt you can swap mid-run, an enforced dollar budget, or a permission system. It
gives you `replace_messages()` between runs, `max_turns`, `before_tool_call` and
`after_tool_call`. That is enough to build all four around it, and not enough to pretend
they are in it.

### Sessions, branching, compaction, export

- Append-only JSONL, per working directory, under `~/.tau/sessions/`.
- A session is a tree. `/tree` navigates, plain Enter moves in memory, `S` writes a
  structured branch summary immediately, `C` adds focus instructions for that summary,
  `L` bookmarks, `Ctrl+F` filters to labelled entries.
- Resume validates the active branch and repairs missing, misplaced, duplicate or orphaned
  tool results by appending a provider-safe branch. Idempotent, diagnosed, and it does not
  rewrite the original entries.
- Compaction writes a `first_kept_entry_id` boundary, Pi-compatible, replacing older
  `replaces_entry_ids` arrays. Older arrays still read.
- `/export` writes self-contained HTML with a Transcript tab and a Cache tab. The Cache tab
  summarises model requests, prompt caching, output and reasoning tokens, estimated
  API-rate cost, tool calls and compactions, and can export charts as PNG. It also embeds
  the current system prompt in a collapsed section when exporting live, which is a useful
  honesty feature and a reminder to review before sharing.

That export is the best "show me the receipt" feature in this comparison. For an EVO
project, where the claim is that value must be measurable, an artifact that lists cost per
request and labels the summary calls is exactly the right shape.

### Extensions in practice

An extension is a Python module with a plain `def setup(tau)`. It can register tools,
process-local providers, local backends, slash commands, prompt guidelines, prompt
sections, message renderers, event handlers, sidebar sections and Textual widgets. It can
send user or custom messages, append durable entries, set labels, notify, and open
`select`, `confirm` and `input` dialogs.

Two details are better than the competition:

1. **`setup` must be synchronous.** Async work belongs on events. That removes a whole
   class of startup races.
2. **Dialogs are safe without a UI.** In print mode or tests, every dialog returns its
   cancel default immediately, so an extension can call `confirm` unconditionally. Check
   `tau.context.has_ui` only if the behaviour should differ.

The intercepting hooks are `input` (transform or consume), `tool_call` (block, give a
reason, rewrite arguments, fail-safe on a crashing handler) and `tool_result` (rewrite
content or details). All other handler failures are contained as diagnostics and never
crash the session. That containment policy is the right default for an extension
ecosystem, and it is another sign that this code has met real users.

What is missing versus Pi is mostly surface area: no package registry with dependency
installation, no remove or update command, no custom entry renderers for non-context cards,
no declarative keybindings, no CLI flag registration, no system-prompt replacement, no
context rewriting. The marketplace is the next phase on the roadmap. Do not build a
product on those seams yet.

### The subagent question

Tau has no built-in subagents. The reference extension, `tau-subagents`, builds them out of
`CodingSession.load`, which is possible because the session is a reusable object rather
than a CLI invocation. Two config fields make it safe:

- `trust_override="approve"` (or `"decline"`) so a headless child inherits the parent's
  project trust decision. Without it, the child silently loses the project's skills,
  `AGENTS.md` and project extensions, even though the human already approved the repo.
- `allowed_tool_names=frozenset({"read", "bash"})`, which filters the final composed tool
  list and is re-applied on `/reload`, so an extension cannot bypass it. Pair with
  `skills_enabled=False` for a child that should get nothing but the basics.

That is a well-designed seam. It is also a decision you have to make yourself, and the
default is "no delegation", which is a defensible default for a teaching harness and a
questionable one for a production one.

### Pi, and what Tau inherited

Pi is the TypeScript original: MIT, 121,791 stars on 13 November 2026, Node 22.19 or newer,
published as `@earendil-works/pi-coding-agent` with `pi-agent-core`, `pi-ai`, `pi-tui`,
`pi-schema` and `pi-durable` alongside. It runs interactively, in print mode, in JSON mode,
in RPC mode and through a TypeScript SDK. It has a tree session store, compaction with
branch summarisation, a deep extension event surface including provider-level hooks and
cache warming decisions, `codemode` in a QuickJS sandbox, tool search, MCP support, and a
real package manager.

It deliberately does not ship subagents, plan mode, permission popups, built-in todos or
background bash. Tau inherited that philosophy almost intact, and added one thing Pi does
not have: it is Python, it is small enough to read, and it is installable in the same
environment as the rest of your data work.

Tau's own framing is careful: "Not a port; the same honest core, rebuilt as a teaching
example." The name is a joke about circles - pi is half a turn, tau is the whole turn -
and the docs lean into it. The framing matters because it sets expectations: Tau is
optimised for legibility first. When you are choosing a harness for a long-running EVO
loop, legibility is a feature, and it is also a constraint.

## JAZ in depth

JAZ is the opposite bet. Instead of a complete product, it is a single primitive and a
hook system, with published measurements.

### The paper

- "Harness as a Language: A Minimalist Agent Framework With Maximal Expressivity",
  arXiv 2609.26891v2, submitted 22 September 2026, revised 30 September 2026.
- MIT CSAIL plus an independent researcher. Authors include Zhening Li, Joshua Liu, Mateja
  Vukelic, Nicole Shen, Supriya Lall, Amitayush Thakur, Alex Zhang, Omar Khattab, Jonathan
  Light and Armando Solar-Lezama.
- NeurIPS 2026 TTCL Workshop.
- Code: `github.com/jaz-lang/jaz`, Apache-2.0, 80 stars on 13 November 2026. Evaluation
  code at `github.com/jaz-lang/jaz-evals`.
- Distribution: `jaz-lang` on PyPI, 0.2.0b1, 5 releases, Python 3.12 or newer, 3.14
  recommended for t-string prompts and the `jaz` console.

Eighty stars is the number to hold onto. This is research code with a published result,
not an ecosystem. That is not a criticism of the work; it is the correct expectation for
what you are adopting.

### One primitive

`invoke` is a function whose implementation is written by the model at call time. The
paper's two defining properties:

1. The model can write arbitrary executable code, including recursive `invoke` calls.
2. Everything visible to the model - every input to `invoke`, and the REPL history itself
   - is a variable in the code environment.

Property 2 is the part that distinguishes it from CodeAct and from recursive language
models. In smolagents and in RLMs, the prompt and the history are messages shown to the
model. In JAZ they are Python objects the model can manipulate. `__history__` is a variable.
That single change is what makes lossless handoff possible.

There is no distinction between prompts, tools and ordinary data. Every input is a keyword
argument, and a tool is just a function you pass in:

```python
from jaz import invoke
from jaz.hooks import ReturnType

def web_search(query: str) -> list[str]:
    """Search the web and return result snippets."""
    ...

result = invoke(
    ReturnType(dict),
    task="Look up each name and summarize what you find",
    names=["ada", "grace"],
    web_search=web_search,
)
```

The signature and docstring become the tool description. `invoke("...")` is an error,
because positional arguments are hooks. That is a small piece of API discipline that
prevents a whole class of confusion.

### Tail-recursive delegation

When the context fills, the agent delegates the remainder and passes history by reference:

```python
return invoke(
    ...,
    prev_history=globals().get("prev_history", []) + __history__,
    prev_progress_summary=...,
    next_steps=...,
    ...,
)
```

The paper notes that the subagent must combine its own `__history__` with the
`prev_history` it received before delegating again, and that a built-in
`ContextWindowWarning` hook is what elicits the behaviour: it appends a user message when
the window passes a threshold, telling the agent to delegate and showing the template.

The paper also points out that this pattern subsumes the alternatives. Compaction is
"pass only `prev_progress_summary`". Automated context management is "pass a filtered
version of `__history__`". That is a strong claim and the ablation supports it: the same
mechanism, run with a thin summary, behaves like compaction, and run with full history, it
behaves like memory.

### Dynamic scoping and the config seam

`scope(...)` is a context manager that makes variables available to every `invoke` under
it, including recursive sub-invokes. Hooks work the same way: positional to one call, or
scoped to the block. Configuration is one more instance of the same idea:
`Config(llm, repl, protocol)`, with `ConfigOverride` either local or scoped.

The paper justifies dynamic scoping unusually well. Static scoping exists so a function can
be reused without surprising context changes, but `invoke` has no static implementation and
no reuse, because every call generates a new one. So dynamic scoping is not a shortcut
here; it is the only coherent choice.

That is the kind of argument that makes a research framework worth reading even if you
never adopt it. It gives you a reason, not just an API.

### The hook system as an event bus

Three spans - Invoke, LLMQuery, REPLExec - each with four stages: Enter (the proposal),
Send (the committed input), Complete (the raw result), Exit (the outcome, observation
only). Effects are typed and only valid at specific stages: `AddInputs`, `DropInputs`,
`DisableRecursion`, `SupplyInvokeResult`, `ModifyInvokeResult`, `AddMessages`,
`DropMessages`, `SupplyLLMResponse`, `ModifyLLMResponse`, `AddToNamespace`,
`DropFromNamespace`, `InsertCode`, `DeleteCode`, `SupplyExecResult`, `ModifyExecResult`,
`Abort`, `BlackboardWrite`. Returning an effect at the wrong stage raises
`InvalidEffectError`.

Built-in hooks fall into four groups:

- Observability: `PrintLogger`, `FileLogger`, `TrajectoryDirectoryRecorder`,
  `TrajectoryRecorder`, `LangfuseTracing`, `JaegerTracing`.
- Resumability: `TrajectoryRecorder`, `TrajectoryReplay`.
- Resource control: `BudgetPool`, `IterationLimit`, `RecursionLimit`, `BudgetForcing`,
  `ContextWindowWarning`.
- Validation: `ReturnType`, `ValidateReturn`, `ValidateREPLCode`.

`ValidateREPLCode` is the interesting one. It can veto code before it runs. That is a
genuine pre-execution boundary, and it is more than Tau's `tool_call` hook can do because
it sees the code, not a tool call. It is still not a sandbox, and should not be sold as
one.

### The two experiments, with numbers

Both use GPT-5.4 nano at high thinking for the solver unless stated. Means with standard
errors over independent runs.

**StuLife** - 1,284 ordered tasks simulating a student's semester, 939 graded, 207
requiring recall of information delivered more than 50 tasks earlier. A typical episode is
7,000 to 8,000 environment interactions and 3,000 to 5,000 model calls. Three runs.

| Method | Prompt-only | Pass (all) | Score (all) | Pass (far recall) | Cost |
| --- | --- | --- | --- | --- | --- |
| CodeAct, per task | yes | 52.5 ± 0.3 | 59.2 ± 0.1 | 24.8 ± 0.6 | 4.4 ± 0.1 |
| CodeAct + subagents, smolagents | yes | 30.2 ± 4.8 | 33.6 ± 5.2 | 20.6 ± 0.6 | 9.4 ± 1.4 |
| CodeAct + subagents, JAZ | yes | 60.0 ± 1.1 | 68.1 ± 1.0 | 32.0 ± 2.3 | 13.1 ± 0.9 |
| Letta (MemGPT) | no | 70.9 ± 0.5 | 81.0 ± 0.5 | 61.8 ± 2.3 | 42.1 ± 1.6 |
| JAZ invoke | yes | 72.6 ± 0.1 | 81.6 ± 0.1 | 69.9 ± 1.8 | 18.3 ± 0.3 |

**AppWorld** - 417 tasks across 9 simulated apps, test-challenge split, order shuffled with
seed 42, full test feedback after each task. The self-improving methods get 6 runs, the
others 3. The solver is GPT-5.4 nano, the meta-agent is GPT-5.4.

| Method | Prompt-only | TGC | SGC | Cost | Meta | Solver |
| --- | --- | --- | --- | --- | --- | --- |
| CodeAct, official | no | 48.2 ± 1.6 | 20.4 ± 3.2 | 16.6 ± 0.2 | - | 16.6 |
| CodeAct, JAZ, per task | yes | 67.5 ± 1.2 | 43.4 ± 2.5 | 10.2 ± 0.2 | - | 10.2 |
| CodeAct + subagents, JAZ | yes | 71.1 ± 1.3 | 47.6 ± 2.1 | 21.6 ± 1.8 | 7.3 | 14.3 |
| ACE on CodeAct | no | 69.9 ± 1.4 | 47.1 ± 1.3 | 30.6 ± 0.5 | 17.1 | 13.5 |
| JAZ invoke | yes | 74.2 ± 2.1 | 51.1 ± 3.7 | 20.9 ± 3.7 | 9.9 | 10.9 |

TGC is task goal completion, SGC is scenario goal completion. Read the cost columns before
the score columns.

### How to read those numbers

Four honest caveats, three of which are in the paper.

1. **Tau is not in these tables, and neither is Pi.** These are comparisons of loop
   paradigms under a controlled setup, not a product shootout. You cannot conclude that
   `invoke` beats a coding agent at coding. You can conclude that the expressivity gap is
   real on long-horizon recall and continual learning.
2. **The smolagents row is not a fair indictment of smolagents.** The authors say
   explicitly that established implementations "were found to perform worse than our
   reimplementation due to defects in prompting and REPL implementation as opposed to the
   actual distinction between CodeAct(+subagents) and invoke". They reimplemented CodeAct
   inside JAZ as an ablation for exactly this reason. Do not quote 30.2 versus 72.6 as
   "JAZ is 2.4x better than smolagents". It is not what the paper claims.
3. **The ACE comparison is generous to ACE on cost, not on scope.** ACE's reflector and
   curator cost about ten times more per task than JAZ invoke, so the authors restricted
   ACE's learning to the first 42 tasks (10 percent) to balance cost and performance. ACE
   still cost more overall. That is a strong result, and it is also a reminder that
   "specialised harness" does not automatically mean "efficient".
4. **The self-improvement mechanism is prompting, not training.** The meta-agent batches
   tasks, reads failure traces, rewrites the subagent's prompt and tools, and adjusts batch
   size. It gets subagent trajectories by asking the subagent to return `__history__`. The
   paper's own diagnosis of why this beats ACE: ACE optimises only the prompt after every
   task, while JAZ's meta-agent optimises any input to `invoke`, including tools it writes,
   and reads trajectories selectively instead of ingesting all of them.

That fourth point is the one that matters for an EVO project. It is a cleaner statement of
E7, invest in an open-ended architecture: the winning loop was not a better-designed
workflow, it was a workflow that could redesign itself because the interface was general.

### What JAZ does not have

- No TUI, no RPC, no Python SDK. A `jaz` console REPL and `-c` for one prompt.
- No sandbox. `PythonREPL` with an `exec_timeout`, plus `ValidateREPLCode` if you add it.
- No package or extension distribution. Custom hooks are Python you import.
- No built-in evaluation. The eval harness is a separate repo.
- No permission model beyond code validation.
- No packaging story for sharing a setup with a colleague.
- 80 stars, 5 PyPI releases, a beta version number, and a README that says the repository
  is generated from a private source tree.

If you need a human in the loop, JAZ is the wrong tool. If you need a loop you can express
in forty lines and replay for free, it is the best tool in this comparison.

## The rest of the field

### smolagents

Hugging Face, Apache-2.0, 30,350 stars. The pitch is that the agent logic fits in about a
thousand lines and stays close to raw code. Two agent types: `CodeAgent`, which writes
actions as Python, and `ToolCallingAgent`, which uses conventional JSON tool calls. Sandboxed
execution through Modal, Blaxel, E2B or Docker. Hub integration so agents and tools can be
shared as Gradio Spaces. Model-agnostic through LiteLLM and transformers.

For this comparison, smolagents is the reference implementation of the CodeAct paradigm
that JAZ generalises. It is a library, not a harness: no session store, no TUI, no
permission model beyond the sandbox you choose, no prompt assembly policy. You assemble
those. That is the trade: maximum flexibility, zero opinions, and you own every layer from
the table above that matters.

### OpenAI Agents SDK

MIT, 30,648 stars. Primitives: agents, handoffs (or agents-as-tools), guardrails. The
runtime owns the loop, tool execution, sessions and tracing. It has grown well past the
original Swarm replacement: sandbox agents with manifest-defined files and resumable
sessions, realtime and voice agents, MCP, human-in-the-loop, SQLAlchemy/Redis/Mongo/Encrypted
sessions, and built-in tracing with evaluation and fine-tuning hooks.

It is the strongest "managed runtime" option here, and the weakest fit for an EVO harness
that wants to own its own loop, because the loop is the product. Also: the default path is
the OpenAI Responses API, and the design assumes you are comfortable with that.

### Pydantic AI

MIT, 21,188 stars. The most complete *service* runtime in the list, and the one that has
thought hardest about the layers Tau and JAZ leave out.

- Typed end to end: structured outputs, typed dependency injection, typed tools, output
  validation with reflection and retry.
- A `Capability` primitive that bundles tools, instructions, hooks and model settings, so
  the harness is composable rather than configured.
- A separate `pydantic-ai-harness` package with `Coder`, `SubAgents`, `FileSystem`,
  `Shell`, `RepoContext`, planning, compaction, `Advisor`, `StepPersistence`, and ACP.
- Durable execution on nine engines, including Temporal, DBOS, Prefect and Restate, with
  human-in-the-loop approval.
- OpenTelemetry native, `Pydantic Evals` for outputs and trajectories, `genai-prices` for
  current pricing, `Monty` as a sandboxed Python interpreter.
- Interfaces: CLI, web chat, AG-UI, Vercel AI, ACP, GitHub Agentic Workflows.

If the answer is "a Python service that must survive restarts and be graded", this is the
answer, and Tau is not. The cost is weight: you are adopting a framework with opinions
about types, dependency injection and persistence, and you will write more code before your
first run than you would with Tau.

### mini-swe-agent

MIT, 9,586 stars. The control condition. About a hundred lines for the agent class, a bit
more for the environment, model and run script. Over 74 percent on SWE-bench verified
(vendor claim, on the project README). Supports local, docker/podman, singularity/apptainer,
bubblewrap and contree environments. Models via LiteLLM, OpenRouter, Portkey, and
`/completion` and `/response` endpoints. Used by Meta, NVIDIA, IBM, Nebius, Anyscale,
Princeton and Stanford, among others, per the README.

There is no extensibility story because there is nothing to extend. The value is that you
can read the whole thing, run it in whatever sandbox you trust, and use it as a baseline
that no amount of harness engineering can cheat. Every EVO harness should keep a
mini-swe-agent row in its results table. If your clever harness cannot beat a hundred
lines of Python on your own task set, you have learned something expensive and useful.

### Claude Agent SDK

MIT SDK, 8,537 stars for the Python package, commercial terms of service for the underlying
service. It wraps the Claude Code binary, so you inherit built-in tools, hooks, subagents,
MCP, permissions, sessions, skills, commands, memory and plugins. It is the only harness
here with a real permission system out of the box.

It is also the least portable: Anthropic's terms, Anthropic's binary, and a note in the
docs that third-party developers may not offer claude.ai login or rate limits through
products built on the SDK. If your harness is meant to be vendor-neutral, this is a
reference architecture rather than a dependency.

### The comparison that matters

None of these are interchangeable, and the honest summary is a sentence each:

- Tau: the best readable Python shell for a human plus a script.
- JAZ: the best compact expression of an experimental loop.
- smolagents: the best library when you want to own everything.
- OpenAI Agents SDK: the best managed runtime if you accept its opinions.
- Pydantic AI: the best typed, durable service runtime.
- mini-swe-agent: the best control condition.
- Claude Agent SDK: the best permissions story, with the least portability.

## Head to head

Stars and versions as of 13 November 2026. Treat star counts as a proxy for "how many
people have hit the bugs you are about to hit", not as a quality score.

### Positioning

| | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude Agent SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Shape | coding harness | research framework | library | managed runtime | service runtime | control | vendor SDK |
| Language | Python | Python | Python | Python | Python | Python | Python and TS |
| License | MIT | Apache-2.0 | Apache-2.0 | MIT | MIT | MIT | MIT SDK |
| Stars | 3,048 | 80 | 30,350 | 30,648 | 21,188 | 9,586 | 8,537 |
| Version | 0.4.11 | 0.2.0b1 | stable | stable | stable | 2.x | stable |
| Primary job | drive a repo | test an idea | build an agent | ship a workflow | ship a service | measure a baseline | ship on Claude |

### Runtime layers

Cells say full, partial or none. "Partial" means it exists but you will extend it, or it
covers only part of the layer.

| Layer | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Loop control | full | partial | partial | full | full | partial | full |
| Context projection | full | partial | none | partial | full | none | full |
| Compaction | full | full | none | partial | full | none | full |
| Tool registry | full | partial | full | full | full | partial | full |
| Delegation | partial | full | partial | full | full | none | full |
| Budgets, enforced | none | full | none | partial | partial | none | partial |

### Operational layers

| Layer | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Permissions | none | partial | partial | partial | partial | full | full |
| Session store | full | partial | none | full | full | partial | full |
| Observability | full | full | partial | full | full | partial | full |
| Evaluation | none | partial | none | partial | full | full | partial |
| Interfaces | full | partial | none | partial | full | partial | full |
| Distribution | partial | none | partial | partial | full | none | full |
| Model access | full | full | full | partial | full | full | none |

### Interfaces and automation

| | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TUI | Textual | console REPL | none | none | CLI plus web | Textual CLI | CLI |
| One-shot | `-p` | `-c` | script | script | CLI | `mini -t` | `-p` |
| JSON events | `--mode json` | hooks and traces | none | tracing | OTel | inspector | stream JSON |
| RPC | yes | none | none | none | ACP | none | subprocess |
| In-process API | `AgentHarness` | `invoke` | `CodeAgent` | `Runner` | `Agent` | `DefaultAgent` | `ClaudeSDKClient` |
| Exit codes | yes | no | no | no | no | yes | yes |

### Safety and governance

| | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tool gate | hook | code validator | custom | guardrail | capability | none | permission mode |
| Sandbox | none | none | Modal, E2B, Docker | docker sandbox | workspace, shell allowlist | docker, podman, singularity | vendor sandbox |
| Secret handling | none | none | none | none | none | none | partial |
| Cost cap | none | pool budget | none | usage limits | gateway limits | none | usage limits |
| Audit trail | JSONL plus HTML | ATIF traces | none | traces | OTel | logs | sessions |

### Maturity and cost of ownership

| | Tau | JAZ | smolagents | OpenAI Agents | Pydantic AI | mini-swe-agent | Claude SDK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Readable end to end | yes, 2,300 lines | yes, one primitive | partially | no | no | yes, 100 lines | no |
| Breaking changes | likely, 0.4.x | likely, beta | low | low | low | low | low |
| Docs quality | excellent | paper plus README | good | good | excellent | good | good |
| Support | community | paper authors | HF | OpenAI | Pydantic | Princeton team | Anthropic |
| Lock-in | low | none | low | medium | low | none | high |

## Language is a layer: the Python-only rule

You want a fully Python stack. So does this project. That deserves to be treated as a design
constraint rather than a preference to be traded against features, because it eliminates
most of the field before the feature comparison starts. It is also the strongest argument
for Tau over Pi, and it is separate from the layer-by-layer case that follows.

The language boundary is not one of the thirteen layers, because it is not a capability.
It is a tax on every layer you touch, and the tax is paid per iteration. That is why it
belongs in a selection guide at all.

### The boundary Pi has and Tau does not

| | Pi | Tau |
| --- | --- | --- |
| Agent loop | TypeScript | Python |
| Extension language | TypeScript modules, loaded in process | Python modules with `def setup(tau)` |
| Tool definition | TypeScript `AgentTool` | Python `AgentTool` |
| Embed in your own program | TypeScript SDK, Node or Bun | `tau_agent.AgentHarness`, any Python process |
| Cross-language escape hatch | RPC mode: JSONL on stdin and stdout | RPC mode too, but unnecessary from Python |
| Runtime to install | Node 22.19 or newer | Python 3.12 or newer |
| Distance from your scorer | A process hop | An import |

Pi's RPC mode is a genuine design decision, not a workaround. The docs describe it as the
path for "other languages, isolated processes, IDEs, or custom clients", it uses strict
JSONL framing with correlated responses, and the documentation ships a Python subprocess
example. It works, and people use it.

But it is still a process boundary sitting in the middle of the thing you are trying to
improve. Pi's extension surface is richer than Tau's - per-request context rewriting,
`codemode` in a QuickJS sandbox, tool search, a real package manager - and every one of
those advantages is reachable only from TypeScript. From Python you can call the agent,
send prompts, receive events and read sessions. You cannot reach into the loop and change
what it does on turn four.

That distinction is the whole argument. Capability you cannot reach from your language is
not capability you have.

### What the boundary costs, per iteration

An EVO harness is edited constantly. That is the point of
[the RSI page](evo-rsi-harness.md). So the right way to price a language boundary is per
change, not per install.

| Step of one experiment | One language (Tau) | Two runtimes (Pi plus a Python bridge) |
| --- | --- | --- |
| Add a tool | Write a Python function, pass it in | Write a TS module, or bridge every call that needs your data |
| Change a hook | Edit Python, rerun | Edit TS, rebuild, restart the RPC process |
| Score a run | Import the scorer, read the event stream | Convert RPC JSONL to `runs.jsonl` first |
| Debug a bad turn | One process, one debugger, one stack trace | Decide which side is at fault before you can look |
| Ship to CI | One image, one lockfile, one Python version | Two runtimes, two lockfiles, two upgrade paths |

None of those rows is fatal. All of them are recurring, and they compound in exactly the
place where an EVO project cannot afford friction: the loop that measures whether a change
was worth keeping. A measurement loop that takes an extra twenty minutes of plumbing per
iteration gets run less often, and a loop that runs less often produces fewer promotions.

There is a second-order cost that is easy to miss. With two languages, your failures split
into harness bugs and bridge bugs, and the symptom is often identical: the agent stops,
the event never arrives, the run ends with no result. You spend the first hour of every
investigation deciding where the bug lives. In one language, the stack trace tells you.

### The honest counter-case

This is not a universal rule, and there are three situations where I would break it.

- **Your team writes TypeScript.** If the people who will edit the harness are TS
  developers, the boundary costs them nothing and Pi's deeper extension surface is free
  upside. Do not adopt Python to satisfy a diagram.
- **You need per-request context rewriting now.** Tau has no `context` hook and no mid-run
  system prompt replacement. You can `replace_messages()` between runs, which covers the
  search loop, and it does not cover rewriting the projection inside a turn. If that
  experiment is the product, Pi in TypeScript is the honest choice, and the bridge is the
  price of keeping your scorer in Python.
- **You need the vendor's tools more than you need portability.** Then the Claude Agent SDK
  is the answer and the language question is secondary, because you are already accepting a
  bundled CLI, a vendor's terms and a permission system you do not control.

For everything else - a terminal agent that a human drives, a bench that scores it, a
ledger that prices it - one language wins on the arithmetic above.

### The rule

Put the loop, the tools, the scorer and the bench in one language. If they are in one
language, an experiment runs in one process, under one debugger, against one lockfile, and
a change is a diff rather than an integration.

The one-sentence version, if you need to defend the choice in a meeting:

> If the harness and the evaluation are not in the same language, you have two projects.

### What this decides, and what it does not

The Python rule picks Tau over Pi. It does not pick Tau over JAZ, smolagents, OpenAI Agents
SDK, Pydantic AI or mini-swe-agent, because all of those are already Python. That is why
the rest of this page exists: the language argument closes the door on one strong
alternative, and then the layer analysis has to do the remaining work.

It also explains the shape of the recommendation. If the constraint is "one language", the
bench does not have to be a second framework. The section on expanding Tau instead of
adopting JAZ is the direct consequence: a ledger, a response cache and a typed return tool,
written in the same Python as everything else, are cheaper than a second toolchain that
happens to ship them.

## Where Tau wins

Five claims that survive scrutiny.

**1. It is the only one that is good at both halves of your requirement.** Human
interaction and automated runs are different interface problems, and most harnesses solve
one. Tau has a Textual TUI with streaming, steering, pickers and tree branching, and it has
`-p`, `--mode json`, `--mode transcript`, RPC and an SDK, all from the same core, all
sharing the same event contract. The SDK is not a wrapper around the CLI; it is the same
`AgentHarness` the TUI uses. That is rare and it is worth paying for.

**2. It is auditable.** 2,300 lines across seven files, with a stated reading order. If
your harness is going to run unattended against a real repository, the ability to read the
loop, the tool implementations and the session format in one sitting is not a luxury. It
is how you find out that the thing you are trusting does what the docs say.

**3. The event contract is the right abstraction.** Everything is an event, frontends are
listeners, and the portable core knows nothing about Textual or Rich. This is why the SDK,
RPC and JSON mode are cheap to maintain, and why your own evaluation harness can subscribe
to the same stream the TUI uses. When you build the meter layer from
[the harness guide](evo-in-ai-harness.md), you plug it in here.

**4. The accounting artifacts are honestly good.** A session tree with branch summaries,
labels, idempotent repair on resume, and an HTML export with a Cache tab that separates
summary-generation requests from assistant turns and estimates cost per request. That last
artifact is closer to what an EVO project needs than anything else in this comparison,
because it makes the cost claim inspectable rather than asserted.

**5. It is Python end to end.** Not a Python client over a Node process: the loop, the
tools, the extensions, the session store and the SDK are one language, installable with one
`pip install tau-ai` in the same environment as your scorer. For a single-language stack
that is the deciding property rather than a footnote, and it has its own section above.

## Where Tau loses, and what beats it

This is the part you asked for. Four scenarios where Tau is not the best choice, with the
tool that wins and why.

### Scenario 1: you need a scored, replayable experiment loop

**Winner: JAZ.** If the question is "does this harness change improve the score", Tau gives
you events and you build the scorer, the replay and the statistics yourself. JAZ gives you
`TrajectoryRecorder` and `TrajectoryReplay` (saved responses replay, then live calls take
over), a scoped `BudgetPool` that covers the whole recursion tree, `ReturnType` for typed
results, and a publishable evaluation harness next to the framework. The paper's own
experiments are the proof that this is enough to produce credible numbers.

Tau's counter-argument is real: its session JSONL plus `--mode json` is enough to build
replay. It is just work you have to do, and it is work that is easy to do wrong, because
replay correctness depends on capturing every non-deterministic input, not just the
messages.

### Scenario 2: you need typed outputs and durable execution in a service

**Winner: Pydantic AI.** Structured outputs validated at the boundary, dependency injection
that a type checker understands, `TemporalDurability` or `DBOS` so a run survives a
restart, `StepPersistence` to snapshot every settled step, `Pydantic Evals` for trajectory
grading, OTel for everything. Tau has none of that and is not trying to. If your harness is
a nightly job that must not lose six hours of work when a pod dies, the answer is a durable
execution engine, not a better TUI.

### Scenario 3: you need a sandbox you can actually trust

**Winner: mini-swe-agent, with smolagents second.** mini-swe-agent treats the environment as
the product: local, docker, podman, singularity/apptainer, bubblewrap, contree. smolagents
gives you Modal, Blaxel, E2B or Docker for code execution. Tau runs tools with the
permissions of the Tau process and says so. If your threat model includes "the model reads
a malicious README and decides to exfiltrate `.env`", then Tau plus a `tool_call` hook is
not a mitigation. Tau plus a container is, but then the container is doing the work and you
should choose the harness that makes the container easy.

### Scenario 4: you need subagents, permissions and plan mode out of the box

**Winner: Claude Agent SDK, with OpenAI Agents SDK second.** Subagents, hooks, MCP,
permission modes, sessions, skills, commands and plugins are all built in and documented.
Tau gets there through extensions: `tau-subagents` for delegation, `permission_gate.py` for
a bash blocklist, and your own plan-mode prompt. That is a fine answer if you want to own
the code. It is a bad answer if you wanted to buy the capability.

### And the honest scorecard

Tau is the best shell and the second-best bench. It is not the best sandbox, the best
service runtime, or the best research framework. Anyone claiming otherwise is comparing
interfaces, not layers.

The asymmetry that matters: Tau's weaknesses are all in the layers you can put *around* it
(a container, a scorer, a budget proxy), while its strengths are in the layer that is
hardest to add afterwards, which is the interface contract. That is a good trade for an EVO
harness. It is a bad trade if you were hoping the harness would also be the safety boundary.

## The architecture I would actually run

Given the above, the answer is not "pick one". It is two tools and one contract.

```
        HUMAN                        AUTOMATION
          |                              |
          v                              v
   +--------------+              +--------------+
   |  Tau TUI     |              |  Tau -p      |
   |  steer, fork |              |  --mode json |
   +------+-------+              +------+-------+
          |                             |
          +-------------+---------------+
                        |
                        v
              +--------------------+
              |  Tau AgentHarness  |  <- operator shell
              |  sessions, tools,  |
              |  compaction        |
              +---------+----------+
                        |
          events.jsonl  |  (one contract)
                        v
              +--------------------+
              |  LEDGER + SCORER   |  <- the meter layer
              |  cost, pass, time  |
              +---------+----------+
                        ^
                        |  atif traces
              +---------+----------+
              |  JAZ invoke loop   |  <- experiment bench
              |  budget pool,      |
              |  replay, typed     |
              +--------------------+
```

Three pieces:

1. **Tau is the operator shell.** A human drives it in the TUI, and CI invokes
   `tau -p --mode json --session-id <uuid>` with a pre-reserved session id so the run is
   addressable without scanning the session directory. Same tools, same project context,
   same storage. Print mode exits non-zero on failure, so it composes with a shell.
2. **JAZ is the experiment bench.** Every candidate change to the harness is expressed as a
   JAZ loop first, with a scoped `BudgetPool`, a `ReturnType`, and `TrajectoryReplay` for
   the deterministic part. It is cheap, it is fast, and it is disposable. You do not need a
   TUI to find out that a prompt change is worth 4 points. See the next subsection if you
   would rather keep one language.
3. **One contract between them.** This is the part people skip and then regret.

The contract has three files:

- **`tasks.jsonl`** - one task per line: id, prompt, working directory, acceptance check,
  budget, and the class it belongs to. Frozen before the search starts. The RSI page calls
  this the frozen evaluator rule, and it is the single most important artifact in the
  system.
- **`runs.jsonl`** - one row per run: run id, harness, harness version, task id, model,
  tokens in and out, cache reads and writes, cost, wall clock, turns, tool calls, exit
  reason, and the score. Tau's JSON events and JAZ's ATIF traces both reduce to this row.
  Write the reducer once, and keep it outside both harnesses.
- **`budget.toml`** - per run, per task, per day and per experiment caps, plus the routing
  table. JAZ enforces its part with `BudgetPool`; Tau's part is enforced by the wrapper
  that refuses to start the next task when the ledger is over, and by the container's own
  limits.

The rule that makes it work: **the bench never talks to the shell through anything but
`runs.jsonl`, and the shell never gets a change the bench has not scored.** Promotion is a
diff plus a score, not a vibe.

This is also how you get the RSI loop from the other page without a research project. The
bench proposes, the scorer decides, the shell runs what survived. Nothing in Tau needs to
know it is being improved.

### If you would rather expand Tau and skip JAZ

Fair question, and the honest answer is that you can. The bench is a place for experiments,
and `AgentHarness` is a perfectly good place to run them. The only thing JAZ gives you that
Tau does not is two primitives, and both are small enough to write:

| JAZ primitive | What it does | Tau equivalent you would write |
| --- | --- | --- |
| `BudgetPool` | Enforced cost and call budget across the whole recursion tree | A ledger checked before each `prompt()`, plus `max_turns` |
| `TrajectoryReplay` | Replay saved responses, then go live | A response cache keyed by request hash, in front of the provider |
| `ReturnType` | Enforce a typed return | A `submit_results` tool with a schema and `terminate=True` |
| `ConfigOverride` | Swap model, REPL or protocol per call | Construct a second `AgentHarness` with a different config |

The ledger is forty lines. The response cache is harder than it looks, because the key has
to cover the model, the system prompt, the tool set and the full message list, or your
replay silently diverges. That is the one piece where JAZ has genuinely done the work for
you.

So the decision is not "Tau or JAZ". It is:

- **One language, one codebase, one deploy:** expand Tau. This is the option the
  [language rule](#language-is-a-layer-the-python-only-rule) points at. Write the ledger,
  write the cache, keep `tasks.jsonl` and `runs.jsonl` exactly as specified. You lose
  nothing important, and you gain the ability to debug a failing experiment in the same
  debugger as the harness.
- **Two languages but a proven bench:** Tau for the shell, JAZ for the bench. You get replay
  and pooled budgets on day one, and you pay for it with a second toolchain and a trace
  format conversion.
- **One language and a research-grade bench:** skip both and use JAZ everywhere. You will
  miss the TUI within a week.

The thing not to do is expand Tau in the direction it explicitly does not go yet: per-request
context rewriting and mid-run prompt replacement. You can `replace_messages()` between runs,
and that is enough for a search loop. If you find yourself patching `run_agent_loop` to
rewrite the projection on every turn, stop and either upstream the hook or move that
experiment to JAZ, because you are now maintaining a fork of a 0.4.x package.

### What to port, and what not to

Do not try to make Tau into JAZ, or the reverse. Port the four things that are cheap:

- JAZ's budget scoping idea, into your wrapper: one pool for the sweep, one for the task,
  one for the retry.
- JAZ's typed-return idea, into a `submit_results` tool with `terminate=True` and a JSON
  schema, so the parent gets structured data instead of prose.
- Tau's `agent_settled` discipline, into anything that consumes events: never treat
  `agent_end` as "done".
- Tau's export discipline, into your ledger: every run produces an artifact a human can
  read, not just a row in a database.

Do not port the TUI into the bench, or the search loop into the shell. Interactive
steering during a scored experiment invalidates the experiment, and a headless sweep has no
use for a picker.

## Mapping to EVO E1 to E10

The ten principles from [EVO in software development](evo-sw-devel.md), read as harness
requirements against this stack.

| Principle | Harness requirement | Where it lands |
| --- | --- | --- |
| E1 decompose by results and stakeholders | One task, one acceptance check, one owner | `tasks.jsonl`, one row per task |
| E2 do high-risk steps early | First run is the one that can fail on permissions or cost | Stage 1 of the build order, container before agent |
| E3 improve the most valuable objective first | Score before you tune | Scorer and ledger before any prompt work |
| E4 evolve the existing system | Adopt a harness, do not write one | Tau for the shell, JAZ for the bench |
| E5 design to cost dynamically | Budget per class, routing by task difficulty | `budget.toml` plus JAZ `BudgetPool` |
| E6 design to performance dynamically | Re-baseline when the model or the tool set changes | Quarterly re-run, new `harness_version` |
| E7 invest in an open-ended architecture | The loop must be able to rewrite its inputs, not just its prompt | JAZ `invoke`, or a Tau extension that rewrites tools |
| E8 reward results, not effort | Merge on score, not on hours | Promotion gate in `runs.jsonl` |
| E9 prioritize by value, not queue position | Run the expensive task when the budget is healthiest | Wrapper reads the ledger, not the backlog |
| E10 learn fast, change fast | One change, one score, one commit | Bench run is the unit of review |

Two rows deserve a warning.

E7 is the one people fake. Adding a "reflection" step that rewrites a system prompt is not
open-ended architecture; it is a fixed workflow with a template. The JAZ result is
interesting precisely because the meta-agent could rewrite tools and inputs, not just
prose. If your harness can only rewrite text, expect text-sized gains.

E8 is the one people corrupt. The moment "the agent ran for six hours" becomes a proxy for
value, the loop learns to run for six hours. The scorer must be the only thing that
promotes.

## Build order

Twelve stages. Each one has a piece of evidence that says it is done. Do not skip to the
fun part.

| Stage | What to build | Evidence it worked |
| --- | --- | --- |
| 1 | A container with a read-only mount for secrets and an egress allowlist | A test task that tries to read `.env` fails and the failure is logged |
| 2 | `tasks.jsonl` with 20 to 50 tasks, frozen | Two people can run the same file and get the same task set |
| 3 | One reducer from Tau JSON events and JAZ ATIF traces to `runs.jsonl` | The same run, reduced twice, produces identical rows |
| 4 | Cost and token fields, including cache reads and writes | A run's ledger row reconciles with the provider invoice within 5 percent |
| 5 | A hard budget check before each task starts | A runaway task is killed at the cap, not after it |
| 6 | A deterministic acceptance check per task | The score is reproducible across three runs on the same harness |
| 7 | A scorer with a declared noise floor | You can say "this change is inside noise" without hand-waving |
| 8 | A JAZ bench loop for one candidate change | One prompt or tool change is measured end to end for under a dollar |
| 9 | A `submit_results` tool with `terminate=True` and a schema | The parent gets typed data, and the run ends without an extra model call |
| 10 | A Tau extension that reports the ledger in the sidebar and on `agent_settled` | A human can see cost and score without leaving the TUI |
| 11 | A promotion gate: diff plus score, applied as one commit | Every promotion is revertible by hash |
| 12 | A quarterly re-baseline, including a mini-swe-agent row | The harness is still better than a hundred lines of Python |

Stage 12 is the one that keeps you honest. Keep the control condition in the table forever.
The day your harness loses to mini-swe-agent on your own tasks is the day you learn
something worth the whole project.

## Limits and open questions

- **Tau is 0.4.x.** The roadmap lists 34 shipped phases and one in progress. Expect the
  extension API to move. Pin the version in anything that runs unattended, and read the
  changelog before upgrading.
- **Tau has no permission system.** The docs say it, the `permission_gate.py` example
  implies it, and this page has said it three times. If you take one thing away: the
  container is the boundary.
- **JAZ is research code with 80 stars.** The results are credible and the interface is
  elegant, but a beta package maintained by a paper's authors is not a platform. Budget for
  the possibility that you fork it.
- **The JAZ numbers are not a product comparison.** They compare loop paradigms under a
  controlled setup with GPT-5.4 nano. They do not tell you whether Tau's compaction beats
  JAZ's delegation on your repository. Only your task set does that.
- **The smolagents row in the paper is an implementation artefact, and the authors say so.**
  Anyone quoting 30.2 versus 72.6 as a product comparison is misreading the paper.
- **No harness in this comparison has a real budget enforcement plus a real permission
  system.** JAZ has the budget. Claude Agent SDK has the permissions. Pydantic AI has
  durable execution. Nobody has all three. That is an open gap in the field, not a gap in
  your evaluation.
- **Open question: does a readable harness stay readable?** Tau's 2,300 lines are a
  deliberate constraint. Extensions, subagents and a marketplace all push against it. The
  interesting test is whether Tau is still auditable at 1.0.
- **Open question: is `invoke` expressivity a win outside benchmark worlds?** StuLife and
  AppWorld both reward long, stateful, feedback-rich sequences. A brownfield repository
  with a flaky test suite might reward the opposite: a rigid, boring, well-instrumented
  loop.
- **Open question: what is the right unit of promotion?** A prompt change, a tool change
  and a model change are not comparable. The RSI page's coverage-churn audit suggests you
  should track which tasks each change wins and loses, not just the mean.
- **Open question: how much of the harness advantage is the harness?** The evidence in
  [EVO in the AI harness era](evo-in-ai-era.md) says harness choice can rival model choice,
  and that the gains are not additive. This page assumes that holds for Tau and JAZ. It has
  not been measured.

## Checklist

Before you commit to a harness, answer these. Any "no" is a stage in the build order, not
a reason to switch tools.

- [ ] Can I read the loop, the tools and the session format in one sitting?
- [ ] Are the loop, the tools, the scorer and the bench in one language?
- [ ] Does the harness distinguish "one run ended" from "nothing further will happen"?
- [ ] Can I resume, fork and replay a run without rewriting history?
- [ ] Does compaction preserve constraints, or only progress?
- [ ] Are tools declared by default in small numbers, with a path to the rest?
- [ ] Is delegation explicit, with inherited trust and an inherited budget?
- [ ] Is there a hard stop on money, not just a report?
- [ ] Is the permission boundary outside the model's reach?
- [ ] Does every run produce a row I can join to a task and a version?
- [ ] Can I score a change without a human reading the transcript?
- [ ] Do the interactive and automated paths share one core?
- [ ] Can a customisation travel to another machine with a pinned version?
- [ ] Do I have a control condition that is embarrassing to lose to?
- [ ] Have I written down what would make me switch?

The last one is the EVO question. A harness choice is a step with a claim attached. Write
the claim, set the score, and let the measurement decide.

## References

Primary sources for Tau:

- Hugging Face, "tau: A Python port of Pi's minimalist coding agent", GitHub.
  https://github.com/huggingface/tau
- Tau documentation, "Architecture overview", "The agent loop and events", "Extensions",
  "Sessions", "Print mode and scripting", "Roadmap".
  https://twotimespi.dev/
- Tau on PyPI, `tau-ai`, version 0.4.11, Python 3.12 or newer.
  https://pypi.org/project/tau-ai/
- Tau roadmap issue, GitHub issue #1.
  https://github.com/huggingface/tau/issues/1
- `rian-dolphin/tau-subagents`, the subagent extension.
  https://github.com/rian-dolphin/tau-subagents

The JAZ paper and code:

- Zhening Li, Joshua Liu, Mateja Vukelic, Nicole Shen, Supriya Lall, Amitayush Thakur,
  Alex Zhang, Omar Khattab, Jonathan Light, Armando Solar-Lezama, "Harness as a Language:
  A Minimalist Agent Framework With Maximal Expressivity", arXiv 2609.26891v2, September
  2026. NeurIPS 2026 TTCL Workshop.
  https://arxiv.org/abs/2609.26891
- JAZ source, Apache-2.0. https://github.com/jaz-lang/jaz
- JAZ evaluation harness. https://github.com/jaz-lang/jaz-evals
- JAZ on PyPI, `jaz-lang`, version 0.2.0b1. https://pypi.org/project/jaz-lang/

Tau's ancestor:

- Pi, Earendil Inc, MIT. https://pi.dev and https://github.com/earendil-works/pi
- Pi documentation, "How Pi works", "Sessions and context", "Compaction reference",
  "Extensions", "Skills", "Command line".
  https://pi.dev/docs/latest

The rest of the field:

- Hugging Face, `smolagents`, Apache-2.0. https://github.com/huggingface/smolagents and
  https://huggingface.co/docs/smolagents
- OpenAI, `openai-agents-python`, MIT. https://github.com/openai/openai-agents-python and
  https://openai.github.io/openai-agents-python/
- Pydantic, `pydantic-ai`, MIT. https://github.com/pydantic/pydantic-ai and
  https://ai.pydantic.dev/
- SWE-agent, `mini-swe-agent`, MIT. https://github.com/SWE-agent/mini-swe-agent and
  https://mini-swe-agent.com
- Anthropic, Claude Agent SDK, MIT SDK. https://code.claude.com/docs/en/agent-sdk/overview
  and https://github.com/anthropics/claude-agent-sdk-python

Standards and background:

- Agent Skills specification. https://agentskills.io/specification
- Hugging Face, "Harness, scaffold, and the AI agent terms worth getting straight", May
  2026. https://huggingface.co/blog/agent-glossary
- Hugging Face, "Designing the hf CLI as an agent-optimized way to work".
  https://huggingface.co/blog/hf-cli-for-agents

Harness design and measurement:

- [Building a custom AI harness with EVO principles](evo-in-ai-harness.md) for the
  thirteen-layer view, component defaults and the reference architecture.
- [Simulating the EVO process for harness development](evo-simulation.md) for scenario
  corpora, run variance, ablation design and fault injection.
- [Simulating and building a self-improving EVO harness](evo-rsi-harness.md) for the loop
  that improves the harness, the three audits and the frozen evaluator rule.
- [EVO in the AI harness era](evo-in-ai-era.md) for the evidence base and the E1 to E10
  mapping.
- [EVO in software development](evo-sw-devel.md) for the method itself.

Method:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process", InfoQ, 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- Tom Gilb, *Competitive Engineering*, Elsevier, 2005. Planguage, impact estimation, Must
  and Plan levels.
