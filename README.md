# WaveLease

Run a batch of coding-agent tasks in parallel without breaking main. WaveLease reads your code
graph, works out what each task will really have to edit and what it depends on, packs the tasks
into parallel waves with disjoint write leases, puts every contract change ahead of the code that
uses it, and refuses any landing that writes outside its lease.

This repo is a proof of concept for that capability on Python, with stub agents. It is not a
product yet.

## The problem

Software factories hand a backlog to a fleet of coding agents, one git worktree each. Worktrees
stop agents overwriting each other's files, but not each other's assumptions. Each agent passes its
own tests, then the merges collide: a textual conflict, or worse, a clean merge that fails on main
because one agent changed a signature another agent was coding against.

Planning around declared scopes helps only if the scopes are right. A task that says "change
`price()`" really has to edit every caller of `price()` too, and any task working near those callers
has to wait for it. The NP-Bench paper below flags inferring scopes as the open problem.

## What the demo shows

Four tasks on a tiny shop package (`fixture/`):

| Task | Names | What it really needs |
| --- | --- | --- |
| T1 | `shop.pricing.price` (adds a required `currency` arg) | also edits callers in `cart.py` and `invoice.py` |
| T2 | `shop.cart` (adds `bulk_total`) | calls `price()`, so it must see T1's new signature |
| T3 | `shop.shipping` (adds `free_over`) | independent |
| T4 | `shop.invoice` (adds `tax_line`) | calls `price()` |

The same batch runs three ways:

| Run | Result |
| --- | --- |
| naive: all four in parallel worktrees, land in order | 3/4 land, one textual conflict, main tests fail |
| declared leases: plan and enforce what each task names | 3/4 land; T1 is refused because its real edits exceed its declared lease |
| inferred leases (WaveLease) | 4/4 land in 2 waves (`T1,T3` then `T2,T4`), main green after each wave |

A fourth run has the T3 agent "tidy" `shop/pricing.py`, which T1 holds. The landing is refused and
nothing from it reaches main.

```
bash demo.sh           # 8 pass/fail checks, exits non-zero on any failure
bash demo.sh --break   # plans with declared leases instead; checks 4 to 7 fail
python3 -m wavelease fixture tasks.json   # print inferred leases and waves for a repo
```

Needs `python3` (3.10+), `git` and `jq`. No network, no model calls, no third-party packages.

## How it works

1. `wavelease/graph.py` parses each module with `ast`: where every function lives, what it calls,
   and what each module imports.
2. `wavelease/plan.py` turns each task into a `Lease`. Declared: the files of the named symbols plus
   the task's own test file. Inferred adds, for a signature change, the file of every caller; and
   records as reads what the edited functions call, or what an edited module imports.
3. Producer to consumer edges: task P changes the contract of a symbol task C reads. Waves are
   built in task order: a task joins the current wave once all its producers have landed and its
   writes do not overlap anything already in the wave.
4. `wavelease/factory.py` runs each wave: worktrees off current main, one stub agent per task,
   then for each task a lease check (`git diff --name-only base..branch` must sit inside the lease)
   and a merge. Main tests run after each wave.

## What is real and what is a stub

- Real: the code graph, lease inference, wave planner, git worktrees, merges, lease enforcement
  and the test runs.
- Stub: the agents. `stubs/agents.py` holds scripted edits standing in for Claude Code, Codex and
  the like. Like a real agent, each stub reads the code in its own worktree, so T2 and T4 call
  `price()` with whatever signature their base has. That is the behaviour the plan relies on.

## Limits

- Python only, and only module-level functions with direct calls. Methods, dynamic dispatch,
  re-exports and cross-language calls are not followed. A real version would use Tree-sitter or
  language servers.
- Tasks still name the symbols they target. Getting those from a ticket's text (with a model, or
  from history) is the next step and is not built.
- File-level leases. Symbol-level leases would let more tasks share a wave.
- No replanning: a refused landing is reported, not retried with a widened lease.
- One fixture, four tasks, deterministic stubs. It shows the mechanism, not how often real batches
  collide.

## Nearest alternatives

- [gitta](https://github.com/gitta-io/gitta) warns agents when code their work uses changes, tests
  combined work inside the git merge, and `gitta run --schedule` holds tasks that touch the same
  files. It reacts as conflicts appear; WaveLease plans waves before any agent starts, from
  inferred scopes, so the clash is not scheduled at all. The two fit together.
- [Nerveplane](https://github.com/sumanyumuku98/Nerveplane) and its
  [NP-Bench paper](https://arxiv.org/abs/2610.07261) plan disjoint scopes and producer to consumer
  merge order from declared scopes, and name inferring scopes as open work.
- Orchestrators such as [Shep](https://github.com/shep-ai/shep),
  [Spec Kitty](https://github.com/spec-kitty/spec-kitty) and
  [Agentic Software Factory](https://github.com/OmegaMc1331/agentic-software-factory) give each agent
  a worktree and gate merges; WaveLease is the planning step they could call.
- Merge queues such as [OpenMerge](https://github.com/CanadaApollo6/openmerge) and
  [SVRF](https://github.com/nybarius/SVRF) keep main green at landing time by batching and
  bisecting. They catch the broken combination after the agent work is done; WaveLease avoids
  producing it.
