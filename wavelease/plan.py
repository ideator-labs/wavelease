"""Leases and waves.

A Lease is what one agent may write and what it depends on. A Plan is a list of waves: tasks in
one wave run in parallel with disjoint write sets; a task that consumes a contract another task
changes runs in a later wave, on a base that already contains the change.
"""
from dataclasses import dataclass, field


@dataclass
class Lease:
    task: str
    writes: set
    reads: set
    contract: set = field(default_factory=set)   # symbols whose signature this task changes
    why: list = field(default_factory=list)      # human-readable reasons for each inferred path

    def to_json(self):
        return {"task": self.task, "writes": sorted(self.writes), "reads": sorted(self.reads),
                "contract": sorted(self.contract), "why": self.why}


def _test_file(task_id):
    return f"tests/test_{task_id.lower()}.py"


def declared_lease(task, g):
    """What a task names, and nothing more. This is the input Nerveplane-style planners assume."""
    writes = {g.files[e] for e in task["edits"]} | {_test_file(task["id"])}
    contract = set(task["edits"]) if task.get("contract_change") else set()
    return Lease(task["id"], writes, set(), contract, ["declared: files of the named symbols"])


def inferred_lease(task, g):
    """Declared scope plus what the code graph says the task will have to touch or depend on."""
    lease = declared_lease(task, g)
    lease.why = []
    for e in task["edits"]:
        lease.why.append(f"{g.files[e]}: defines {e}")
        if e in g.imports:  # a whole module: new code there will use what it already imports
            lease.reads |= g.imports[e]
            for q in sorted(g.imports[e]):
                lease.why.append(f"reads {q}: imported by {e}")
        else:
            lease.reads |= g.calls.get(e, set())
        if task.get("contract_change"):
            for caller in sorted(g.callers(e)):
                lease.writes.add(g.files[caller])
                lease.why.append(f"{g.files[caller]}: {caller} calls {e}, whose signature changes")
    return lease


def edges(leases):
    """producer -> consumer pairs: the consumer reads a symbol whose contract the producer changes."""
    out = []
    for p in leases:
        for c in leases:
            if p is not c and p.contract & c.reads:
                out.append((p.task, c.task, sorted(p.contract & c.reads)))
    return out


def waves(leases):
    order = [l.task for l in leases]
    by_id = {l.task: l for l in leases}
    preds = {t: set() for t in order}
    for p, c, _ in edges(leases):
        preds[c].add(p)
    done, plan = set(), []
    while len(done) < len(order):
        wave, held = [], set()
        for t in order:
            if t in done or not preds[t] <= done or by_id[t].writes & held:
                continue
            wave.append(t)
            held |= by_id[t].writes
        if not wave:
            raise ValueError("cycle in producer -> consumer edges")
        plan.append(wave)
        done |= set(wave)
    return plan
