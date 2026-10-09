# Independent migration geometry

The centerline migrates according to the linear-curvature Howard–Knutson/Ikeda
parameterization. Curvature affects migration locally and through an upstream
integral. This is an independently implemented written model, but its exact
equivalence to the 2018 implementation remains unverified.

## Written specification and limits of attribution

- Howard and Knutson (1984), *Water Resources Research* 20, 1659–1667,
  [doi:10.1029/WR020i011p01659](https://doi.org/10.1029/WR020i011p01659).
  The accessible abstract describes a nonlinear nominal migration function,
  strongest at bend radius/channel width approximately 3, upstream weighting,
  and neck cutoffs. The publisher denied full-text PDF access (HTTP 403);
  no precise nonlinear function was established from this source. We do not
  invent one or present the linear approximation as that nonlinear function.
- Schwendel et al. (2015), *Earth Surface Processes and Landforms* 40, 2026–2040,
  [doi:10.1002/esp.3777](https://doi.org/10.1002/esp.3777),
  [accepted manuscript, lines 226–256](https://ray.yorksj.ac.uk/id/eprint/2620/1/ESPL%20draft%204.pdf).
  This Nicholas-group antecedent selects the Howard–Knutson parameterization
  equivalent to Ikeda et al. (1981), with local/upstream curvature, nodes at
  half-width spacing, neck cutoffs, and an initially straight channel with
  small random coordinate perturbations. This supports the present choice
  as a model-family precedent; it does not establish the exact 2018 settings.
- Limaye and Lamb (2014), *Journal of Geophysical Research: Earth Surface*,
  [doi:10.1002/2013JF002997](https://doi.org/10.1002/2013JF002997),
  [author's thesis, chapter 3, pp. 62–64, equations 4–6](https://thesis.caltech.edu/8713/7/Limaye_Ajay_2014_thesis_optimized.pdf).
  Provides the explicit linear nominal rate, upstream kernel, weights, and
  optional sinuosity factor used below. Their lateral erosion coefficient
  has dimensions length/time. Their neck criterion is bank impingement.
  Their periodic boundary conditions differ from the fixed endpoints assumed
  here. Their value of friction is 0.01; it is not our default.
- Sylvester et al. (2019), *Geology* 47, 263–266,
  [doi:10.1130/G45608.1](https://doi.org/10.1130/G45608.1),
  [written article, equations 1–4](https://eartharxiv.org/repository/object/1536/download/3406/).
  Independently states the linear nominal-rate simplification, weights
  −1 and 2.5, and exponential decay length used below.

No external simulation code, scripts, numerical output, or figure files were
used for this module. Published curves were not digitized. These sources were
read as scientific descriptions. The implementation and tests were written
from the equations and geometry.

## Equations and units

Let downstream arc length be `s` [m], channel width be `W` [m], bankfull depth
be `D` [m], and signed centerline curvature be `κ` [1/m]. Positive curvature
denotes a counterclockwise turn. The dimensional coefficient `k_l` [m/flood]
multiplies normalized curvature. It is not the spatially averaged migration
distance. The dimensionless erodibility multiplier is `E`.

```
R0(s) = k_l W κ(s)
alpha = 2 Cf / D
G(ξ) = exp(-alpha ξ)
R1(s) = -R0(s) + 2.5 integral_0^s[R0(s-ξ) G(ξ) dξ]
                           / integral_0^s[G(ξ) dξ]
dX/dt = E μ^p R1(s) n_out
```

Here `n_out=(t_y,-t_x)` is the right normal to the downstream unit tangent.
With signed curvature this moves a broad, positively curved bend outward.
`μ` is arc length divided by inlet–outlet distance. Limaye and Lamb use
`p=-2/3`; the default here is `p=0` because the 2018 migration-sinuosity
correction is unspecified. The caller can set `sinuosity_exponent=-2.0/3.0`
to assess that documented alternative. Migration changes only planform
geometry; floodplain erosion, abandoned-channel filling, sediment return,
water remapping, and prescribed channel-bed changes belong to the coupled
model's separate volume and mass budgets.

The convolution integrates the available upstream domain and normalizes by
that domain's kernel integral. At the inlet, its limiting value is `R0(0)`.
No unseen upstream meanders are prescribed. Both end curvatures are zero,
and inlet/outlet coordinates remain fixed. These are explicit boundary
assumptions, not established 2018 conditions. Downstream propagation can
eventually carry the original perturbations out of a finite domain; there
is no ongoing random forcing that replenishes them.

`Cf=9.81/55^2=0.003243` is the default friction coefficient, obtained by
converting the Chezy value 55 documented in Nicholas (2013), as recorded
in the project's hydrodynamic specification. For `D=8 m`, the upstream
e-folding distance is `D/(2 Cf)=1233.4 m`. Depth can vary between calls.
The exact friction value used by the 2018 migration routine is unspecified.
The dimensional migration coefficient must be supplied; there is no hidden
default. For example, `k_l=400 m/flood` produces nominal migration
`40 m/flood` at `Wκ=0.1`, before upstream weighting and `E`.

For an infinitely long, almost straight channel with `p=0`, a transverse
Fourier perturbation with wavenumber `k` has real growth rate

```
sigma(k) = E k_l W k^2 [ -1 + 2.5 alpha^2/(alpha^2+k^2) ].
sigma_max = E k_l W alpha^2 (sqrt(2.5)-1)^2.
Omega(k) = 2.5 E k_l W alpha k^3/(alpha^2+k^2).
```

This follows by Fourier transforming the stated exponential convolution;
it is not an additional migration law. For `W=500 m`, `D=8 m`, `E=1`,
and the default friction, `k_l=40 m/flood` gives an e-folding time of about
225 floods, whereas `k_l=400 m/flood` gives about 22.5 floods. This scale
distinguishes the coefficient from observed migration and motivates
testing its uncertainty. Finite-domain evolution also depends on the
upstream boundary and cutoff history.

The full perturbation is proportional to `exp(sigma t) cos(k x - Omega t)`.
The positive frequency `Omega` therefore moves crests downstream at speed
`Omega/k`; it is distinct from amplitude growth. With the default parameters,
the neutral wavelength is 6327.77 m and the fastest-growing wavelength is
10166.14 m. Shorter waves decay in this linear limit, so the rapid loss of
short-wavelength initial coordinate noise can coexist with slower growth of
long bends. This calculation does not establish the later nonlinear planform
or its agreement with the manuscript.

## Numerical implementation

`src/migration.hpp` contains plain `ridge::Point{x,y}` data and functions.
Three-point circumcircles give curvature; a centered chord gives the
tangent. The upstream integral uses exact exponential integration of
piecewise-linear curvature, with an O(number of nodes) recurrence.
The `alpha=0` limit becomes the normalized trapezoidal integral. A series
expansion avoids cancellation for small `alpha*spacing`.

Migration uses explicit Euler substeps. Each substep obeys both a geometric
displacement limit of 0.2 times the shortest segment and a conservative
curvature-diffusion timestep `0.2 ds_min^2/[3.5 E k_l W μ^p]`. These are
numerical accuracy/stability criteria: the complete requested flood interval
is integrated, and velocities are not capped. Lagrangian nodes are also
resampled within the migration stage when any segment lies outside
0.5–1.5 times the requested spacing. This prevents node crowding from
collapsing the timestep while the physical curve remains regular.
A collapsed timestep raises an error rather than silently stopping.
Coordinates are interpolated to
equal arc-length intervals no greater than the requested spacing after
the migration/cutoff update; the default is `W/2`. Linear interpolation
can smooth poorly resolved bends, so node-spacing sensitivity is necessary.

Cutoff detection uses minimum distance between nonadjacent line segments,
including interior crossings. When two limbs are less than one width apart,
the intervening loop is replaced by the shortest straight connector.
Candidates separated along the centerline by no more than two widths are
excluded to avoid treating a local bend as a separate neck. That exclusion,
connector choice, and upstream-first processing of simultaneous contacts
are declared numerical geometry assumptions. They were not specified in
the 2018 supplement. Chute cutoffs are absent. The routine records removed
arc length, and the test checks the exact before/after length difference.
There is no water or sediment volume inside this geometry module.

The primary interface is:

```cpp
auto stats = ridge::migrate(centerline, width_m, k_l_m_per_flood,
                            erodibility, depth_m);
```

Optional subsequent arguments are friction, maximum node spacing,
duration in floods, and sinuosity exponent. `MigrationStats` returns
cutoff count, removed length [m], substep/resampling counts, and
`max_displacement` [m]. The latter is the sum of substep maximum speeds
times timestep, a conservative bound on integrated kinematic movement;
it excludes coordinate changes due solely to resampling.
With zero duration, erodibility, or dimensional migration coefficient,
the centerline remains bitwise unchanged.

## Verification commands and outcome

Run from the repository root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -pedantic -Isrc tests/migration.cpp -o tmp/test_migration
./tmp/test_migration
```

The test verifies zero migration of a straight river, the zero-erodibility
and zero-coefficient limits, exact curvature of a circular arc, constant
and affine analytical upstream integrals, the zero-decay limit, second-order
convergence for a sinusoidal integral, segment crossings, neck removal,
the removed-length budget, endpoint retention, reflection symmetry,
resampling with duplicate input nodes, and 580 finite migration updates
of a 72 km channel initialized with Gaussian coordinate noise of
5 m standard deviation (seed 742, `k_l=400 m/flood`). The latter develops
tight bends and cutoffs and checks that mesh crowding remains controlled.
The measured maximum circle-curvature error is `4.46e-16 m^-1`.
Doubling quadrature resolution reduces the sinusoidal error from
`5.21e-4` to `1.30e-4` (ratio `3.999`). The cutoff length-budget error
is zero at printed precision. The noisy 72 km test finishes with sinuosity
`3.86170` and 29 cutoffs. Geometry-only probes using the same initial
noise and `k_l=200` or `800 m/flood` also completed all 580 floods, with
final sinuosities `2.95733` and `2.37546`, respectively. These are independent
model calculations, not published reference results or calibration targets.
These tests establish geometric consistency;
they do not establish agreement with the 2018 planforms or validate
coupled water/sediment remapping.

## Linear growth, phase, and node-spacing check

`tests/migration_linear.cpp` checks the small-slope Fourier response of the
same migration header used by rebuild 002. This later component check was
not part of that rebuild's frozen launch checks. It uses a 72 km domain,
`W=500 m`, `D=8 m`, `E=1`, `k_l=400 m/flood`, `p=0`, and the default friction.
The 12 km mode grows and the 4 km mode decays; both propagate downstream.
Their continuum complex rates `lambda=sigma-i Omega` are respectively
`0.04190077-0.06247190i` and `-0.23396204-0.50281014i` per flood.

The independently derived spatial reference includes central curvature and
the piecewise-linear exponential integral. With actual initial node spacing
`d`, `S=E k_l W`, `q=exp(-alpha d)`, and `w=1-q`, it is

```
b = (w-alpha d q)/(alpha d)
H = [(w-b)+b exp(-i k d)]/[1-q exp(-i k d)]
lambda_d = S [2 sin(k d/2)/d]^2 [-1+2.5 H].
```

For one explicit Euler substep per call, the predicted measured logarithmic
rate is `log(1+dt lambda_d)/dt`. The test compares this prediction with
0.1-flood evolutions at `dt=0.001` and `0.0005` floods, sinusoid amplitudes
0.1 and 0.05 m, and maximum node spacings 500, 250, and 125 m. A least-squares
cosine/sine fit at actual node coordinates measures amplitude and phase over
24--48 km. A second window, 36--60 km, checks boundary sensitivity. The exact
initial finite-inlet convolution is also projected and compared with the
infinite-domain reference. These controls bound fixture effects empirically;
the small omitted kernel tail alone is not a bound on the evolving solution.

The controlled measured rate differs from the independent discrete Euler
reference by at most `6.08e-9` per flood. Halving the amplitude changes the
rate by at most `4.61e-9` per flood. Halving the call interval halves the
remaining temporal error relative to the spatial reference. The assertion
tolerances are fixture accuracy criteria: `1e-7` per flood for the controlled
rate, `5e-8` for the amplitude contrast, and `1e-8` for stable-count gain
controls. They are not manuscript-agreement tolerances.

A separate native one-flood call uses the migration routine's own time-step
selection. The measured logarithmic complex-rate errors are:

| Maximum node spacing (m) | 12 km mode error (per flood) | 4 km mode error (per flood) |
|---|---:|---:|
| 500 | 1.12575e-3 | 4.25733e-2 |
| 250 | 2.84940e-4 | 1.08143e-2 |
| 125 | 7.15915e-5 | 2.71815e-3 |

Errors fall by factors 3.94--3.98 on refinement. This is combined spatial
and temporal convergence because the native time-step limit scales as
`d^2`; the calls contain 15, 57, and 225 internal substeps. Their CSV rows
therefore omit the single-Euler-step reference. The independent spatial
symbol also approaches the continuum rate at approximately second order.

Resampling requires a distinct control. The prepared migration modes use
`ceil(72000/h)+1` intervals, with actual initial spacings 496.552, 249.135,
and 124.783 m. Their node counts remain unchanged; 200 resampling-only
calls change complex gain by at most `6.81e-10`. In contrast, a sinusoid
initialized at literal spacing `h` has arc length slightly greater than
72 km, so `ceil(arc_length/h)` adds one interval during resampling. A single
such interpolation, with no elapsed migration time, has the following
measured amplitude loss in the primary fitting window:

| Literal node spacing (m) | 12 km mode loss (%) | 4 km mode loss (%) |
|---|---:|---:|
| 500 | 0.823124 | 7.304149 |
| 250 | 0.206250 | 1.847948 |
| 125 | 0.051605 | 0.463479 |

These losses depend on the interpolation and fitting window; they are not
physical damping rates. Zero-duration CSV rows leave rate fields empty.
Tiny single-step comparisons use gains because dividing the initial
resampling change by a short duration exaggerates its apparent rate.
All fixtures retain fixed endpoints, remain finite, and have no cutoffs.
They establish the implemented linear growth and phase response and expose
resampling attenuation. They do not establish coupled grid convergence,
explain the entire production sinuosity change, or assess late manuscript
planforms.

The test is included in `make check`. To repeat only this check without
overwriting the retained observation:

```sh
source scripts/environment.sh
make build/migration_linear_test
build/migration_linear_test --csv tmp/migration-linear-results.csv
```

The [retained record](../validation/migration-linear/README.md) contains all
72 CSV rows, build/test logs, command and compiler details, and source/output
hashes. No coupled calculation was launched by this check.
