#pragma once
#include "finite_volume.hpp"

namespace ridge {

// Ferguson & Church (2004), eq. 4, doi:10.1306/051204740933.
// d [m], submerged relative density R=(rho_s-rho_w)/rho_w, nu [m^2/s].
// C1=18,C2=1 describe one natural-grain choice, not an inferred 2018 value.
inline double settling_velocity(double d,double R=1.65,double nu=1e-6,
                                double C1=18,double C2=1) {
    if(d<0 || R<0 || nu<=0 || C1<=0 || C2<0)
        throw std::invalid_argument("invalid settling parameters");
    return R*g*d*d/(C1*nu+std::sqrt(0.75*C2*R*g*d*d*d));
}

// Spherical, unflocculated particles at low particle Reynolds number.
inline double stokes_settling_velocity(double d,double R=1.65,double nu=1e-6) {
    return settling_velocity(d,R,nu,18,0);
}

// Sand diameter and clay diameter are explicit reconstruction assumptions.
// Silt fall speed is inherited from Nicholas et al. (2013), section 3.1.
inline std::array<double,3> settling_velocities(double sand_d=2e-4,
                                               double silt_ws=2e-4,
                                               double clay_d=2e-6,
                                               double R=1.65,double nu=1e-6) {
    if(silt_ws<0) throw std::invalid_argument("negative silt fall speed");
    return {settling_velocity(sand_d,R,nu),silt_ws,
            stokes_settling_velocity(clay_d,R,nu)};
}

// Quadratic Chezy bed stress [Pa], for velocity magnitude [m/s].
inline double bed_shear_stress(double speed,double chezy,double rho_w=1000) {
    if(speed<0 || chezy<=0 || rho_w<=0)
        throw std::invalid_argument("invalid bed stress parameters");
    return rho_w*g*speed*speed/(chezy*chezy);
}

// Nicholas et al. (2013), eq. 23. A numerical tau_c is not reported there.
inline double krone_factor(double tau_b,double tau_c=0.1) {
    if(tau_b<0 || tau_c<=0)
        throw std::invalid_argument("invalid deposition shear stress");
    return std::max(0.,1-tau_b/tau_c);
}

// At fixed depth, remove and return deposited class mass [kg/m^2].
// Default sand settling is shear-independent: an explicit assumption.
// Dry-cell suspension becomes bed inventory; this is drainage bookkeeping.
// The caller must apply returned masses to its bed inventory exactly once.
inline std::array<double,3> deposit(State& q,const std::array<double,3>& ws,
                                   double tau_b,double tau_c,double dt,
                                   bool sand_krone=false) {
    const double attenuation=krone_factor(tau_b,tau_c);
    std::array<double,3> deposited{};
    for(int k=0;k<3;++k)
        deposited[k]=settle(q,k,ws[k]*(k==0&&!sand_krone?1:attenuation),dt);
    return deposited;
}

// Convert dry mineral mass [kg/m^2] to porous deposit thickness [m].
inline double deposit_thickness(const std::array<double,3>& deposited,
                                double rho_s=2650,double porosity=0.4) {
    if(rho_s<=0 || porosity<0 || porosity>=1)
        throw std::invalid_argument("invalid deposit density or porosity");
    return (deposited[0]+deposited[1]+deposited[2])/(rho_s*(1-porosity));
}

// D_H=nu_t assumes turbulent Schmidt number 1; u_star is shear velocity.
inline double sediment_diffusivity(double h,double u_star) {
    if(h<0 || u_star<0) throw std::invalid_argument("negative diffusivity input");
    return 0.07*u_star*h;
}

// Shared, left-to-right diffusive class flux [kg/(m s)] across a wetted face.
// face_depth is the common hydraulic aperture after bed reconstruction.
// The caller applies equal/opposite integrated fluxes to its two stores and
// enforces the explicit diffusion stability restriction; this is not capped.
inline std::array<double,3> diffusion_flux(const State& left,const State& right,
                                         double D_left,double D_right,
                                         double face_depth,double distance) {
    if(D_left<0 || D_right<0 || face_depth<0 || distance<=0)
        throw std::invalid_argument("invalid sediment diffusion face");
    std::array<double,3> flux{};
    if(left[0]<=0 || right[0]<=0 || face_depth==0) return flux;
    const double conductance=0.5*(D_left+D_right)*face_depth/distance;
    for(int k=0;k<3;++k)
        flux[k]=conductance*(left[3+k]/left[0]-right[3+k]/right[0]);
    return flux;
}

} // namespace ridge
