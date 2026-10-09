# Hydraulic and sediment methods: evidence and unresolved choices

The methods paper is Nicholas, Ashworth, Sambrook Smith, and Sandbach (2013),
*Numerical simulation of bar and island morphodynamics in anabranching
megarivers*, JGR Earth Surface 118, 2019–2044,
[doi:10.1002/jgrf.20132](https://doi.org/10.1002/jgrf.20132).
The permitted written paper was retrieved on 2026-10-09 from the
[University of Brighton](https://cris.brighton.ac.uk/ws/files/305870/Nicholas%20et%20al%202013%20offprint.pdf).
Local reading copies are `sources/nicholas-2013-methods.pdf` and `.txt`.
No author code, output archive, source dataset, or separate figure file was
retrieved. Equations below use notation chosen for this implementation.

## Direct 2013 evidence

The following specification is from equations 3–6, 22–24, and sections 2.1
and 3.1 of the [methods paper](https://doi.org/10.1002/jgrf.20132).
Let $\mathbf q=h\mathbf u$.

$$
\boldsymbol\tau_b/\rho_w=(g/C_h^2)\mathbf u|\mathbf u|,
\qquad u_*=(|\boldsymbol\tau_b|/\rho_w)^{1/2},
\qquad \nu_t=0.07u_*h.
$$

$$
\tau_{xx}/\rho_w=2\nu_t\partial_xu,\quad
\tau_{yy}/\rho_w=2\nu_t\partial_yv,\quad
\tau_{xy}/\rho_w=\nu_t(\partial_yu+\partial_xv).
$$

$$
\partial_t(h\phi)+\nabla\cdot(\mathbf q\phi)
=\nabla\cdot(D_Hh\nabla\phi)-D_R+E_R+B_R,
\qquad
D_R=\phi w_s\max(0,1-\tau_b/\tau_c).
$$

Here $C_h$ is Chezy resistance, distinct from the sediment rating coefficient;
$D_H$ is horizontal sediment diffusivity. The nonnegative clipping follows
the stated absence of deposition above $\tau_c$.

| Parameter | Reported value | Location |
|---|---:|---|
| Channel $C_h$ | 55 m$^{1/2}$ s$^{-1}$ | §3.1 |
| Floodplain $C_h$ | 10 m$^{1/2}$ s$^{-1}$ | §2.1 |
| Silt $w_s$ | 0.0002 m s$^{-1}$ | §3.1 |
| Sand bed diameter | 0.4 mm | §3.1 |
| Silt inlet concentration | 150 mg L$^{-1}$ | §3.1 |

Silt entrainment is $E_R=|q_{Ex}|/\Delta x+|q_{Ey}|/\Delta y$,
where $\mathbf q_E$ is unfilled sand transport capacity. Floodplain vertical
scour requires velocity above $V_{cr}$. Porosity is constant. The text gives
no numeric $\tau_c$, $D_H$, $V_{cr}$, or porosity. There is no clay class.

## Applicability to the 2018 reconstruction

The [2018 supplement](https://doi.org/10.1130/2018219), DR1, adopts the earlier
process equations and changes the channel representation to one dimension.
It prescribes channel bed elevation and excludes calculation of bedload
transport. Therefore the 2013 entrainment closure, which requires an evolving
sand bed and its capacity deficit, does not close the 2018 problem. Carrying
that closure over would require physical state variables absent from DR1.

Inherited Chezy values and the silt settling speed are evidence-based
choices, but their use in 2018 is an inference: DR1 does not repeat them.
The 2013 sand bed diameter does not specify the diameter or fall velocity of
the 2018 suspended sand fraction. No written value was found for either the
2018 suspended sand or clay settling speed. In particular, all three fractions
cannot be treated as the 2013 silt class without changing grain-size sorting.

The following items therefore remain choices requiring an explicit assumption
and sensitivity calculation: $D_H$ (including whether it equals $\nu_t$),
$\tau_c$ for each fraction, sand and clay $w_s$, dry sediment bulk density,
initial deposit composition, vertical floodplain entrainment, and exchange of
suspension with the prescribed channel bed. These omissions do not justify
removing advection, diffusion, deposition, or two-way channel–floodplain mass
exchange from the reconstruction.

## Concentration units and dimensional audit

The 2018 main text, Methods, defines $S=CQ^{1.5}$ as a **concentration**
relation and reports $Q$ in m$^3$ s$^{-1}$. Neither the main text nor DR1/DR2
states the units of $S$ or $C$. The cited rating-curve paper likewise defines
a power law for concentration, not sediment mass flux
([Syvitski et al., 2000](https://doi.org/10.1029/2000WR900133)).
Consequently, interpreting $CQ^{1.5}$ as a mass discharge is inconsistent
with the stated definition.

A working convention consistent with the concentration units in the earlier
methods paper is $S$ in mg L$^{-1}$. This is **an assumption**, not a recovered
2018 parameter. It gives

$$
c_{\rm in}=10^{-3}CQ^{3/2}\quad\mathrm{kg\,m^{-3}},\qquad
\dot M_{\rm in}=Qc_{\rm in}=10^{-3}CQ^{5/2}\quad\mathrm{kg\,s^{-1}}.
$$

The numerical value of $C$ then has units
mg L$^{-1}$ (m$^3$ s$^{-1}$)$^{-3/2}$; equivalently the SI coefficient
$10^{-3}C$ has units kg s$^{3/2}$ m$^{-15/2}$.
Multiplication by the specified mass fractions gives the concentration of
each sediment class.

The following values are independently calculated from the rating relation,
not copied results:

| $C$ | $S$ at 2500 m$^3$ s$^{-1}$, mg L$^{-1}$ | $S$ at 15000 m$^3$ s$^{-1}$, mg L$^{-1}$ | Peak SI concentration, kg m$^{-3}$ |
|---:|---:|---:|---:|
| 0.0003 | 37.5 | 551.135 | 0.551135 |
| 0.001 | 125 | 1837.117 | 1.837117 |
| 0.003 | 375 | 5511.352 | 5.511352 |
| 0.01 | 1250 | 18371.173 | 18.371173 |

Using $CQ^{1.5}$ directly as kg m$^{-3}$ makes every load 1000 times larger.
The highest case would imply more than 18,000 kg of suspended solids per
cubic metre, incompatible with an aqueous suspension of ordinary mineral
sediment. This dimensional and physical check rejects that interpretation;
it does not by itself prove that mg L$^{-1}$ was the authors' convention.

## Conservative implementation implications

The statements in this section are independent mathematical consequences and
proposed bookkeeping, not assertions about the unpublished implementation.
The printed 2013 entrainment formula combines volumetric sand transport
capacity (m$^2$ s$^{-1}$) with cell widths, giving $E_R$ units m s$^{-1}$.
Dimensional consistency therefore requires $\phi$ in that equation to be a
volume fraction, even though inlet concentration is reported in mg L$^{-1}$.
A mass-concentration implementation uses $c=\rho_s\phi$ and multiplies
volumetric erosion/deposition rates by $\rho_s$. This is a dimensional
inference; the conversion is not explained explicitly in the paper.

Store class mass per wet horizontal area as $m_k=hc_k$ in kg m$^{-2}$.
Then use the mass balance

$$
\partial_tm_k+\nabla\cdot(\mathbf u m_k-hD_H\nabla c_k)
=e_k-d_k.
$$

With $d_k=w_{s,k}r_kc_k$ and
$r_k=\max(0,1-\tau_b/\tau_{c,k})$, deposition into an immobile bed changes
$z$ at the rate

$$
\partial_tz=\frac{\sum_k(d_k-e_k)}{\rho_s(1-p)},
$$

where grain density $\rho_s$ is kg m$^{-3}$ and porosity $p$ is dimensionless.
A deposited mass must be subtracted from suspension and added to the stored
bed inventory once. Deposits left when a cell dries must also enter that
inventory. Choosing zero vertical entrainment is an explicit assumption;
it must not be described as the 2013 entrainment law.

The local deposition ODE has an exact nonnegative update when $h$, $w_s$,
and shear stress are frozen during a source substep:

$$
m_k(t+\Delta t)=m_k(t)\exp[-w_{s,k}r_k\Delta t/h].
$$

The removed mass sets the bed increment. The limit $\tau_b\geq\tau_c$
requires zero deposition; the zero-shear limit gives settling time
$h/w_s$. Water depth must be treated consistently with a moving bed, and any
operator splitting error evaluated by time-step refinement.

The conservative form puts $hD_H$ inside the diffusive flux. Replacing it
with $D_H\nabla^2(hc)$ creates transport across gradients of depth even when
concentration is uniform. Zero gradient in concentration must therefore be a
null solution of the sediment diffusion operator, including at a coupled
channel–floodplain interface.

A bed volume $V_{\rm bank}$ eroded during migration contains mineral mass
$\rho_s(1-p)V_{\rm bank}$. Moving this mass into an inlet reservoir requires
removing it from the local bed inventory. The choice to inject it during the
next flood with the same $Q^{3/2}$ concentration shape can be made conservative
by defining, for each class,

$$
\Delta c_k(t)=
\frac{M_{{\rm bank},k}Q(t)^{3/2}}
{\int_0^TQ(t)^{5/2}\,dt}.
$$

Then $\int_0^TQ\Delta c_k\,dt=M_{{\rm bank},k}$. This temporal redistribution
is a stated implementation choice: DR1 identifies the inlet as the return
location but does not specify the time profile or the grain-class allocation.
The external rating-curve coefficient can remain fixed while the recycled
mass contribution changes between floods. External supply and recycled bank
mass should be reported separately.

As a separate hydraulic scale check, wide rectangular normal flow obeys
$Q=BC_hh^{3/2}\sqrt{S_0}$. Using $B=500$ m, $S_0=10^{-4}$, and
$C_h=55$ m$^{1/2}$ s$^{-1}$ gives normal depths 4.356 and 14.383 m at the
minimum and maximum specified discharges, respectively. An 8 m deep channel
has corresponding bankfull discharge 6223 m$^3$ s$^{-1}$. These values are
independently calculated checks of the chosen resistance, not numerical
results from a coupled floodplain run. They imply overbank flow during the
initial flood for this resistance choice.

## Remaining evidence limits

Only the written articles and supplement were searched. The 2013 publisher
page returned HTTP 403; the complete institutional paper was available.
Neither a missing numerical closure nor a missing concentration unit can be
recovered by tuning against the prohibited original outputs. Any adopted
values must be listed in the model configuration and the report and tested
with independently generated numerical runs.


## Implemented sediment closure module

`src/sediment.hpp` now supplies the source and diffusive face operators.
The coupled solver remains responsible for the channel geometry, wetting/drying,
advective transport, source splitting, and updates to the bed inventory.
Functions use kg m$^{-3}$ concentration, kg m$^{-2}$ suspended/deposited mass,
and kg m$^{-1}$ s$^{-1}$ horizontal face flux. `deposit` returns the removed
mass of each class; `deposit_thickness` converts the sum to porous thickness.
It does not apply bed elevation or water-depth changes by itself.

For assumed 0.2 mm sand the module uses

$$
w_s=\frac{Rg d^2}{C_1\nu+\sqrt{0.75C_2Rg d^3}},
$$

with $R=1.65$, $\nu=10^{-6}$ m$^2$ s$^{-1}$, $C_1=18$, and $C_2=1$.
This is equation 4 of
[Ferguson and Church (2004)](https://doi.org/10.1306/051204740933), verified
in the [University of Wyoming paper copy](https://geoweb.uwyo.edu/geol5330/FergusonChurch_GrainSettling_JSR04.pdf).
It tends to Stokes settling at small diameter and constant-drag settling at
large diameter. The selected coefficients represent one natural-grain
approximation. This formula and the sand diameter are implementation
assumptions, not reported choices from Nicholas et al. (2018).
Local permitted reading copies are `sources/ferguson-church-2004-settling.pdf`
and `.txt`.

The silt speed is 0.0002 m s$^{-1}$. Clay uses Stokes settling with the
assumed 2 micrometre diameter, ignoring flocculation. The resulting fall
speeds are 0.0232440, 0.0002, and 0.000003597 m s$^{-1}$ for sand, silt,
and clay. All inputs can be changed through function parameters. The default
critical deposition shear stress is 0.1 Pa, explicitly assumed. Silt and clay
use the Krone attenuation. Sand has attenuation one by default, which assumes
settling without vertical sand resuspension; an optional switch applies Krone
attenuation to sand as well. A dry cell transfers all remaining suspended
mass into the returned deposited inventory. The caller must count this dry
residue separately if reporting physical settling alone.

Sediment diffusivity is $D_H=0.07u_*h$. This adopts a turbulent Schmidt number
of one, an explicit assumption beyond the inherited viscosity equation. At
a face, the module uses the arithmetic mean of the two cell diffusivities,
the common wet face aperture, and the difference in concentration divided
by centre spacing. A face with zero aperture or a dry neighbor has zero
flux. One returned flux must update the two stores with opposite signs.
For explicit diffusion with fixed water depths, positivity requires

$$
\frac{\Delta t}{h_i A_i}\sum_{f\in i}
\frac{h_f D_f L_f}{\ell_f}\leq1,
$$

where $A_i$ is the horizontal storage area, $L_f$ the face length, and
$\ell_f$ the distance between adjacent concentration values. The module
neither silently clips the flux nor chooses the solver's timestep.

`tests/sediment.cpp` checks both settling asymptotes, analytical quiescent
and shear-attenuated exponential settling, threshold suppression, deposit
mass and porous thickness, dry residue accounting, unequal-area conservative
exchange, the uniform-concentration null solution across depth gradients,
and convergence to a periodic analytical diffusion solution. Running

```sh
mkdir -p build .tmp
TMPDIR="$PWD/.tmp" g++ -O3 -std=c++17 -Wall -Wextra -Wpedantic -Isrc \
  tests/sediment.cpp -o build/sediment_test
./build/sediment_test
```

passes all checks. Periodic diffusion RMS concentration errors for 32, 64,
and 128 cells are $1.0410\times10^{-5}$, $3.0444\times10^{-6}$, and
$7.6130\times10^{-7}$, respectively. The coupled calculation still needs
separate stability, moving-bed, and mass-budget verification.
