"""Runs a batch of tasks through stub agents in git worktrees and lands them on main.

mode "naive": every task starts from the same base and lands in order (worktrees, no plan).
mode "declared" / "inferred": tasks run wave by wave from the plan built with that kind of lease;
each wave starts from main as it stands after the previous wave landed, and every landing is
checked against the task's lease first.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from stubs import agents
from wavelease import graph, plan

GIT_ENV = ["-c", "user.name=wavelease", "-c", "user.email=wavelease@localhost"]


def git(repo, *args, check=True):
    r = subprocess.run(["git", *GIT_ENV, *args], cwd=repo, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def tests_pass(repo):
    r = subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-q"],
                       cwd=repo, capture_output=True, text=True)
    last = [l for l in r.stderr.strip().splitlines() if l.strip()]
    return r.returncode == 0, (last[-1] if last else "")


def lease_violations(repo, base, branch, lease):
    changed = git(repo, "diff", "--name-only", base, branch).stdout.split()
    return sorted(set(changed) - lease.writes)


def run(fixture, tasks, mode, stray=False, workdir=None):
    work = Path(workdir or tempfile.mkdtemp(prefix=f"wavelease-{mode}-"))
    repo = work / "main"
    shutil.copytree(fixture, repo, ignore=shutil.ignore_patterns("__pycache__"))
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fixture")

    g = graph.build(repo)
    make = {"declared": plan.declared_lease, "inferred": plan.inferred_lease}.get(mode)
    leases = [make(t, g) if make else None for t in tasks]
    by_id = {t["id"]: l for t, l in zip(tasks, leases)}
    waves = plan.waves(leases) if make else [[t["id"] for t in tasks]]

    report = {"mode": mode, "stray": stray, "waves": waves,
              "edges": plan.edges(leases) if make else [],
              "leases": [l.to_json() for l in leases] if make else [], "tasks": [], "after_wave": []}
    for wave in waves:
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        for tid in wave:  # all agents in a wave start from the same base, in parallel worktrees
            wt = work / f"wt-{tid}"
            git(repo, "worktree", "add", "-q", "-b", f"task/{tid}", str(wt), base)
            agents.run(tid, wt, stray=stray)
            git(wt, "add", "-A")
            git(wt, "commit", "-q", "-m", f"{tid}: agent work")
        for tid in wave:
            own_ok, own_tail = tests_pass(work / f"wt-{tid}")
            rec = {"task": tid, "own_tests_pass": own_ok, "own_tests": own_tail,
                   "landed": False, "refused": [], "conflict": False}
            lease = by_id[tid]
            if lease is not None:
                rec["refused"] = lease_violations(repo, base, f"task/{tid}", lease)
            if not rec["refused"]:
                m = git(repo, "merge", "--no-ff", "-q", "-m", f"land {tid}", f"task/{tid}", check=False)
                if m.returncode:
                    git(repo, "merge", "--abort", check=False)
                    rec["conflict"] = True
                else:
                    rec["landed"] = True
            report["tasks"].append(rec)
        ok, tail = tests_pass(repo)
        report["after_wave"].append({"main_tests_pass": ok, "main_tests": tail})
    ok, tail = tests_pass(repo)
    report["main_tests_pass"], report["main_tests"] = ok, tail
    report["main_files_from_refused"] = [
        f for r in report["tasks"] for f in r["refused"]
        if "TODO(T3)" in (repo / f).read_text()] if stray else []
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["naive", "declared", "inferred"])
    ap.add_argument("--stray", action="store_true", help="the T3 stub also edits a file outside its task")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent.parent
    rep = run(here / "fixture", json.loads((here / "tasks.json").read_text()), a.mode, a.stray)
    Path(a.out).write_text(json.dumps(rep, indent=2))
    print(f"{a.mode:9} stray={a.stray!s:5} waves={rep['waves']} main_tests_pass={rep['main_tests_pass']}"
          f" ({rep['main_tests']})")
    for t in rep["tasks"]:
        state = "landed" if t["landed"] else ("REFUSED " + ",".join(t["refused"]) if t["refused"]
                                              else "CONFLICT")
        print(f"  {t['task']}: own tests {'pass' if t['own_tests_pass'] else 'FAIL'}, {state}")
