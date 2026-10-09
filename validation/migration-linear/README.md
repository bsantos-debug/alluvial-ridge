# Migration Fourier response verification

This is a later analytical component check of the unchanged migration
header used by clean rebuild 002. It is separate from that rebuild's frozen
checks, coupled sensitivity cases, and manuscript-panel assessments.

- [Method, equations, controls, and interpretation](../../docs/migration.md#linear-growth-phase-and-node-spacing-check)
- [Test source](../../tests/migration_linear.cpp)
- [All 72 cases](results.csv)
- [Build log](build.log) and [passing test log](check.log)
- [Command, compiler, and byte identities](provenance.json)

The test covers growing 12 km and decaying 4 km sinusoidal modes at three
node spacings, two small amplitudes, two controlled call intervals, a native
one-flood call, and separate resampling controls. Complex coefficients use
`y=Re[C exp(i k x)]`: a negative imaginary rate means downstream phase motion.
The CSV marks whether the single-Euler-step reference applies; it is absent
for native calls with multiple internal steps. Resampling-only cases have
zero duration and blank growth-rate fields. Literal-spacing resampling adds
one node and has separate interpolation attenuation; those rows do not obey
the stable-count crop or gain tolerances.

To repeat the check from the project root while preserving these files:

```sh
source scripts/environment.sh
make build/migration_linear_test
build/migration_linear_test --csv tmp/migration-linear-results.csv
```

The retained native one-flood errors include both spatial and temporal
discretization. This check establishes neither coupled grid convergence nor
agreement with the Nicholas et al. manuscript. No authors' code, outputs,
figure files, or digitized curves were used.
