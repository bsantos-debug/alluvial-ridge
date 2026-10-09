# Current authoritative state

2026-10-09: Read the user's attachment, required guidance, manuscript and
supplement. Created specification and complete 13-panel ledger. No model,
simulation output, generated numerical figure or final report exists yet.

Available: g++, python3 (3.6), pdflatex, curl, git, gh. Python executable named
`python` is absent. GitHub CLI reports no logged-in host. Authorized SSH test
succeeded as account bsantos-debug. SSH permits git transport but does not
itself supply a GitHub API token for repository creation. Check available
connector capabilities before requesting user action.

Methods acquisition: University of Brighton's Nicholas 2013 paper download
returned 403. Howard's former erode.evsc.virginia.edu host did not resolve.
Exeter thesis download produced an empty file; do not treat as read.

Next: obtain written governing equations/closures and migration equations,
implement independent C++ conservative finite-volume coupled model, validate,
then execute complete suite and finish deliverables. Goal remains active.

Additional progress: independently implemented the shallow-water HLL/hydrostatic
face flux and exact well-mixed settling kernel. `make check` passed: lake-at-rest
maximum state error 6.75848e-15 after 1000 steps, shared-face water and three
sediment mass conservation, analytical settling and deposition mass balance,
and dry-interface zero flux. These are kernel checks, not validation of the
not-yet-implemented coupled model. `config/runs.csv` has all 31 documented
configuration combinations and excludes published result columns.

No GitHub connector is available among current tools. Asked the user to log
in to gh or provide an empty repository URL; this does not block local science
work. Publication remains outstanding.
