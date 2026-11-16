#!/usr/bin/env bash
# Four tasks, four stub agents, one small Python repo. Runs the batch three ways:
#   naive     every agent in its own worktree off the same base, land in order (today's default)
#   declared  waves and enforced leases built from what each task names
#   inferred  waves and enforced leases built from the code graph (WaveLease)
# plus one run where an agent strays outside its lease.
# --break plans with declared leases where the inferred plan is expected, so the checks on the
# inferred plan must fail.
set -uo pipefail
cd "$(dirname "$0")"
planned=inferred
[[ "${1:-}" == "--break" ]] && planned=declared && echo "BREAK MODE: planning with declared leases instead of inferred ones"
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v jq >/dev/null || { echo "jq is required"; exit 1; }
rm -rf out && mkdir -p out

python3 -m unittest wavelease.test_plan -q 2>/dev/null || { echo "planner unit tests failed"; exit 1; }
python3 -m wavelease.factory naive --out out/naive.json || exit 1
python3 -m wavelease.factory declared --out out/declared.json || exit 1
python3 -m wavelease.factory "$planned" --out out/planned.json || exit 1
python3 -m wavelease.factory "$planned" --stray --out out/stray.json || exit 1
echo

pass=0; fail=0; n=0
check() {
  n=$((n + 1))
  if [[ "$(jq -r "$3" "$2")" == "true" ]]; then
    echo "PASS $n. $1"; pass=$((pass + 1))
  else
    echo "FAIL $n. $1"; fail=$((fail + 1))
  fi
}
task() { echo "(.tasks[] | select(.task == \"$1\"))"; }

check "naive: every agent's own tests pass in its own worktree" out/naive.json \
  '.tasks | length == 4 and all(.own_tests_pass)'
check "naive: landing them leaves main broken (a textual conflict plus a clean merge that fails tests)" out/naive.json \
  '.main_tests_pass == false and ([.tasks[] | select(.conflict)] | length) >= 1 and ([.tasks[] | select(.landed)] | length) >= 2'
check "declared leases miss the call sites the signature change must edit, so the producer is refused" out/declared.json \
  "$(task T1) | .landed == false and (.refused == [\"shop/cart.py\", \"shop/invoice.py\"])"
check "the planned lease for T1 adds cart.py and invoice.py, found from the call graph" out/planned.json \
  '.leases[0].writes == ["shop/cart.py", "shop/invoice.py", "shop/pricing.py", "tests/test_t1.py"]'
check "the plan runs T1 with T3, then T2 with T4, and orders T1 before both consumers of price()" out/planned.json \
  '.waves == [["T1", "T3"], ["T2", "T4"]] and ([.edges[] | [.[0], .[1]]] == [["T1", "T2"], ["T1", "T4"]])'
check "planned: all 4 tasks land with no conflict and main tests pass after every wave" out/planned.json \
  '([.tasks[] | select(.landed and (.conflict | not))] | length) == 4 and all(.after_wave[]; .main_tests_pass) and .main_tests_pass'
check "planned: still parallel, 4 tasks in 2 waves" out/planned.json '(.waves | length) == 2'
check "an out-of-lease edit is refused at landing, and none of it reaches main" out/stray.json \
  "($(task T3) | .landed == false and .refused == [\"shop/pricing.py\"]) and .main_files_from_refused == [] and .main_tests_pass"

echo
jq -r '"naive: \([.tasks[] | select(.landed)] | length)/4 landed, main tests pass: \(.main_tests_pass)"' out/naive.json
jq -r '"declared: \([.tasks[] | select(.landed)] | length)/4 landed, main tests pass: \(.main_tests_pass)"' out/declared.json
jq -r --arg m "$planned" '"\($m) (planned): \([.tasks[] | select(.landed)] | length)/4 landed in \(.waves | length) waves, main tests pass: \(.main_tests_pass)"' out/planned.json
echo "$pass/$n checks passed"
[[ $fail == 0 ]]
