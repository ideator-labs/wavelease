# AGENTS.md

Handoff for a coding agent with no prior context.

## What this is

WaveLease is a proof of concept for one capability: run a batch of coding-agent tasks in parallel
and land all of them on a green main, by inferring each task's write lease and dependencies from
the code graph, planning parallel waves, and refusing out-of-lease landings. See README.md for the
problem, results and alternatives.

## Status

- Real: Python `ast` code graph, lease inference, wave planner, git worktrees, merges, lease
  enforcement, unittest runs. Python 3.13 and git on the build box; stdlib only.
- Stub: `stubs/agents.py`, scripted edits standing in for coding agents. They read the code in
  their own worktree (T2 and T4 check `price()`'s signature) but do not reason.
- Verified: `bash demo.sh` 8/8 pass; `bash demo.sh --break` fails checks 4 to 7 and exits 1; both
  from a fresh clone.

## Data shape

- Task (`tasks.json`): `id`, `title`, `edits` (qualnames: a module like `shop.cart` or a function
  like `shop.pricing.price`), `contract_change` (true when the task changes the named functions'
  signatures).
- `CodeGraph` (`wavelease/graph.py`): `files` qualname -> file, `calls` function -> callees,
  `imports` module -> imported qualnames. `callers(symbol)`.
- `Lease` (`wavelease/plan.py`): `task`, `writes` (files), `reads` (symbols), `contract` (symbols
  whose signature changes), `why` (reasons for each inferred path).
- Plan: `waves` is a list of lists of task ids; `edges` is `(producer, consumer, symbols)`.
- Report (`out/*.json` from `wavelease/factory.py`): `mode`, `waves`, `edges`, `leases`, `tasks[]`
  (`own_tests_pass`, `landed`, `refused` files, `conflict`), `after_wave[]`, `main_tests_pass`,
  `main_files_from_refused`.

## Repo map

- `wavelease/graph.py`: builds the CodeGraph from a directory of Python files (skips `tests/`).
- `wavelease/plan.py`: `declared_lease`, `inferred_lease`, `edges`, `waves`.
- `wavelease/factory.py`: runs a batch in mode `naive`, `declared` or `inferred` in a temp dir,
  `--stray` makes the T3 stub edit `shop/pricing.py` too.
- `wavelease/__main__.py`: prints inferred leases and waves for any repo and tasks file.
- `wavelease/test_plan.py`: planner unit tests (edge ordering with disjoint files, overlap).
- `stubs/agents.py`: the four stub agents.
- `fixture/`: the shop package and its base tests. `tasks.json`: the four tasks.
- `demo.sh`: runs everything and the 8 checks. `--break` swaps the planned run to declared leases.

## Next steps

1. Symbol targets from ticket text: a model or retrieval step proposes `edits`, the graph widens
   them. Keep the graph as the source of truth for writes.
2. Tree-sitter graphs for TypeScript, Go and C#, plus methods and re-exports.
3. Replan on refusal: widen the lease, move the task to a later wave, rerun the agent.
4. Run waves as a durable workflow (Workflow Core or graphrun) so a crash mid-wave resumes.
5. Hook into gitta or a merge queue for the landing gate instead of the local merge loop.

## Rules

- No em-dashes in prose. No invented links or numbers. Label stubs as stubs.
- Keep `demo.sh` checks honest: each one must be able to fail, and `--break` must fail some.
