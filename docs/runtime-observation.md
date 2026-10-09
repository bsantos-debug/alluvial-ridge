# Runtime observation, 2026-10-09

This is a read-only observation of running jobs, not a completion forecast.
No process was stopped, restarted, shortened, attached to a debugger, or replaced.
Three samples from 19:25:22.638 through 19:27:08.950 UTC are retained in
`tmp/runtime-observation/samples.jsonl`; the interval calculations are in
`tmp/runtime-observation/intervals.json`. The observations read `/proc/PID/stat`,
process records, atomic `progress.json` files, and existing logs.

## Production 002

The production executable and both active sensitivity executables were verified
through `/proc/PID/exe`: SHA-256
`b3d984881a2f82757ff9bb6ca7c15f9e3c28e3d34106ae477fe7c06af6f8099c`.
This matches `tmp/full-rebuild-002/workspace/data/_inputs/provenance.json`.
At the final sample, all 31 production processes were runnable and had advanced
since the first sample. Their last written progress spanned flood 1, days
**5.136–5.832 of 20**, with 11,000–16,000 macrosteps. Sensitivity baseline250
was at day 5.285 and coarse500 at day 7.501. No completed flood or failure was
recorded for these production/sensitivity 002 cases during this window.

Across the first-to-last recorded production progress intervals:

| Quantity | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Mean macrostep (simulation s) | 11.825 | 13.686 | 14.129 |
| Mean channel substep (simulation s) | 3.594 | 3.638 | 4.132 |
| Channel substeps per macrostep | 3.000 | 3.796 | 3.903 |
| Simulation s per wall s | 286.46 | 350.95 | 533.90 |
| Wall s per macrostep | 0.02330 | 0.03942 | 0.04782 |
| CPU s per observation wall s | 0.526 | 0.599 | 0.959 |

Simulation rates use each case's own recorded progress times and counters;
CPU fractions use the common 106.312 s `/proc` observation interval. These are
different interval endpoints and must not be combined into an exact CPU cost
per step. All 33 production/sensitivity 002 children had nice value 10.
Their varying CPU allocations make wall time an imperfect measure of kernel
cost on this shared host. Progress is written every 1,000 cumulative macrosteps,
so a temporarily unchanged file does not by itself indicate a stalled solver.

There is no aggregate evidence of timestep collapse in this window. Live
progress does not record instantaneous/minimum timesteps, active area, or the
binding CFL/positivity constraint; it cannot rule out brief small timesteps or
establish the current limiting constraint. All cases continued advancing.

## Why the early cost grows

The existing `tmp/performance_corrected/timings.csv` supplies the missing phase,
wet-area and timestep diagnostics for an **older corrected-core benchmark**.
Its source hashes are in that directory's `manifest.json`; this is not a
production 002 timing experiment. Representative rows and preceding 1,000-step
CPU intervals are:

| Macrostep | Flood day | Last dt (s) | Wet FP cells, h>1 mm | Active rectangle cells | CPU s / preceding 1,000 steps |
|---|---:|---:|---:|---:|---:|
| 4,000 | 3.524 | 63.928 | 0 | 1,152 | 1.377 |
| 6,000 | 4.256 | 18.964 | 6,406 | 16,128 | 7.313 |
| 8,000 | 4.647 | 15.406 | 12,446 | 22,464 | 15.066 |
| 10,000 | 4.982 | 13.675 | 17,086 | 27,648 | 20.212 |
| 11,000 | 5.137 | 13.077 | 19,152 | 29,952 | 23.110 |

This directly demonstrates two effects: more work per macrostep as the wet
domain expands, and more steps per simulation second as the wave CFL tightens.
At all complete 1,000-step diagnostic rows, the channel-bank wave constraint
bound the macrostep; the positivity limits were inactive or much larger. The
last partial interval reached dt=12.747 s at day 5.234. Its bound columns repeat
the preceding diagnostic and are not a new constraint measurement. Cumulative
phase times were 87.44 s floodplain rates, 26.79 s floodplain advance, and
5.73 s channel advance in 120.01 wall seconds. Thus this observed early
slowdown was dominated by growing floodplain work, with a finite wave-limited
timestep, rather than increasing channel subcycling or a positivity collapse.
The adopted later arithmetic optimizations change absolute costs; this older
trace establishes the mechanism only over its observed early-flood window.
Peak inundation, recession, remapping and later floods are not timed here, so
neither early startup throughput nor this short interval supports a 580-flood ETA.

## Older first-flood validations, kept separate

The older executable SHA-256 is
`c723c3cf8656e7b8935a35d718fe469f4a90c5d0de65de62d2b24d546010632b`.
Actual `/proc` executable hashes confirm this for baseline v4 PID 3756153,
fine125 PID 3757990 and time250_cfl02 PID 3770900. At 19:27:08.950 UTC all three
were runnable and had accumulated respectively 2,619.29, 2,418.18 and
1,697.88 CPU seconds. They gained about 105 CPU seconds each during the
106.312 s observation. They have no progress file or completed summary row;
CPU activity alone cannot locate them within the flood or predict completion.

`validation/runs/coarse500` had already completed one 20-day flood with exit
code 0 using this older executable: 59,535 macrosteps, 404,334 channel substeps,
724.464 model wall seconds. Its saved 144×96 raster records time 1,728,000 s;
all saved values are finite and saved water depths are nonnegative. The
pre-remap summary reports water residual −9.346e−5 m³, suspended/deposited
sediment residual −0.33744 kg, and solid residual −0.26030 kg; beta is
0.00417848 and ridge height 0.0335724 m. These are completion and budget
observations for the older coarse case, not a resolution-convergence result,
post-remap conservation check, or evidence that production 002 has completed.
Its manifest keeps the channel node spacing at 250 m while changing the
floodplain grid to 500 m. The newer conservative remap and checkpoint revision
are outside this older binary's validation scope.

## Available compute resources at 22:42 UTC

A later read-only check used `lscpu`, `mpstat`, `/proc`, cgroup files, and
NVIDIA tools while corrected rebuild 002 continued. The host has two Intel
Xeon Gold 5220R sockets, with 48 physical cores and 96 online logical CPUs.
All 31 production processes and both sensitivity processes may use CPUs
0--95. Each is a single thread with nice value 10. The root CPU cgroup has
quota −1 and no recorded throttling; no restrictive cpuset was identified.

Three one-second `mpstat` samples reported zero idle CPU and mean I/O wait
of 0.12%. The one- and five-minute load averages were approximately 123.
Available memory was about 695 GiB; the 33 model processes together used
about 589 MiB resident memory and no swap. These observations identify
shared CPU contention without a detected quota, affinity, memory, or I/O
constraint to correct. They do not establish future throughput or a
580-flood completion time. More local jobs would compete for the same
observed busy processors.

A Quadro P400 with 2 GiB VRAM was idle, and CUDA compiler 11.3 was installed.
The current solver has no GPU backend, so the live binaries cannot use it
through a configuration change. No GPU performance measurement was made.
The existing tested CPU optimizations are documented in
[performance-review.md](performance-review.md); this resource check does
not supply evidence for another numerical or implementation change.

The installed Slurm 20.11.9 clients also do not expose an identified usable
allocation. `/etc/slurm/slurm.conf` specifies a local controller at
127.0.0.1:6817 and one `localhost CPUs=1` node in partition `debug`.
An initial five-second status query timed out. A subsequent bounded
`scontrol ping`, with that configuration explicitly selected, reported the
primary controller down; `ss` found no listener on port 6817. Both Slurm
services were absent and inactive according to `systemctl`. No alternative
controller or allocation appeared in the inspected standard configuration
locations or selected job/allocation environment variables. This establishes
the state of the identified local configuration, not the absence of any
separate remote facility.

The resource check launched no benchmark or model and changed no source,
process, priority, affinity, or service. Continuing the existing verified
calculations remains the supported next action.
