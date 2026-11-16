"""python3 -m wavelease <python-repo> <tasks.json>: print inferred leases and waves as JSON."""
import json
import sys

from wavelease import graph, plan

if len(sys.argv) != 3:
    sys.exit(__doc__)
g = graph.build(sys.argv[1])
leases = [plan.inferred_lease(t, g) for t in json.load(open(sys.argv[2]))]
print(json.dumps({"waves": plan.waves(leases), "edges": plan.edges(leases),
                  "leases": [l.to_json() for l in leases]}, indent=2))
