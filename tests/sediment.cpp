#include "sediment.hpp"
#include <iostream>
#include <numeric>
#include <vector>
using namespace ridge;

void require(bool ok,const char* what) {if(!ok) throw std::runtime_error(what);}
bool near(double a,double b,double tolerance=1e-12) {
    return std::abs(a-b)<=tolerance*std::max({1.,std::abs(a),std::abs(b)});
}

// Periodic diffusion of c=1+0.2 sin(2 pi x/L), exact amplitude exp(-D k^2 t).
// Its convergence checks the integrated face operator, not just one formula.
double diffusion_error(int n) {
    const double pi=std::acos(-1.),L=100,dx=L/n,D=2,h=3,T=20;
    const int steps=static_cast<int>(std::ceil(T/(0.2*dx*dx/D)));
    const double dt=T/steps;
    std::vector<State> q(n),next(n);
    for(int i=0;i<n;++i) q[i]={h,0,0,h*(1+0.2*std::sin(2*pi*(i+0.5)*dx/L)),0,0};
    for(int j=0;j<steps;++j) {
        next=q;
        for(int i=0;i<n;++i) {
            int k=(i+1)%n;
            auto f=diffusion_flux(q[i],q[k],D,D,h,dx);
            next[i][3]-=dt*f[0]/dx;
            next[k][3]+=dt*f[0]/dx;
        }
        q.swap(next);
    }
    double error=0,mass=0;
    for(int i=0;i<n;++i) {
        double exact=1+0.2*std::exp(-D*4*pi*pi*T/(L*L))*std::sin(2*pi*(i+0.5)*dx/L);
        error+=std::pow(q[i][3]/h-exact,2);
        mass+=q[i][3]*dx;
        require(q[i][3]>=0,"diffusion positivity");
    }
    require(near(mass,h*L),"periodic diffusion mass conservation");
    return std::sqrt(error/n);
}

int main() {
    auto ws=settling_velocities();
    // Check low-Re Stokes and inviscid constant-drag asymptotes separately.
    double small=1e-9;
    require(std::abs(settling_velocity(small)/stokes_settling_velocity(small)-1)<1e-8,
            "Stokes limit");
    double large_limit=std::sqrt(4*1.65*g*0.01/3);
    require(near(settling_velocity(0.01,1.65,1e-15),large_limit,1e-10),
            "constant drag limit");
    require(ws[0]>ws[1] && ws[1]>ws[2],"grain sorting speeds");
    require(near(ws[2],3.597e-6),"clay Stokes scale");
    std::cout<<"fall_speeds_m_s "<<ws[0]<<' '<<ws[1]<<' '<<ws[2]<<'\n';

    State q{2,0,0,3,4,5};
    const State initial=q;
    auto deposited=deposit(q,ws,0,0.1,1000);
    for(int k=0;k<3;++k) {
        require(near(q[3+k],initial[3+k]*std::exp(-ws[k]*500)),"quiescent analytic settling");
        require(near(q[3+k]+deposited[k],initial[3+k]),"deposition class mass conservation");
    }
    const double dz=deposit_thickness(deposited,2650,0.4);
    require(near(dz*2650*0.6,std::accumulate(deposited.begin(),deposited.end(),0.)),
            "mass to porous deposit thickness");
    require(q[0]==initial[0] && q[1]==initial[1] && q[2]==initial[2],"source modifies only sediment");

    State high=initial;
    auto no_fines=deposit(high,ws,0.2,0.1,1000);
    require(no_fines[0]>0 && no_fines[1]==0 && no_fines[2]==0,"Krone suppression and sand exception");
    State all=initial;
    auto no_grains=deposit(all,ws,0.1,0.1,1000,true);
    require(no_grains==std::array<double,3>{},"Krone equality threshold");
    State half=initial;
    deposit(half,ws,0.05,0.1,1000,true);
    for(int k=0;k<3;++k)
        require(near(half[3+k],initial[3+k]*std::exp(-ws[k]*250)),"Krone attenuated analytic decay");
    State zero=initial;
    require(deposit(zero,ws,0,0.1,0)==std::array<double,3>{},"zero time settling");
    State dry{0,0,0,3,4,5};
    auto dried=deposit(dry,ws,100,0.1,10);
    require(dried==std::array<double,3>{3,4,5} && dry[3]==0 && dry[4]==0 && dry[5]==0,
            "dry suspension enters bed inventory");
    std::cout<<"analytic_settling_shear_suppression_mass_budget pass\n";

    State a{4,0,0,2,1,0.5},b{1,0,0,0.1,0.2,0.3};
    const double va=500*250,vb=250*250,face_length=250,dt=10;
    auto f=diffusion_flux(a,b,0.1,0.2,1,250);
    auto reverse=diffusion_flux(b,a,0.2,0.1,1,250);
    for(int k=0;k<3;++k) {
        double before=va*a[3+k]+vb*b[3+k];
        a[3+k]-=f[k]*dt*face_length/va;
        b[3+k]+=f[k]*dt*face_length/vb;
        require(near(before,va*a[3+k]+vb*b[3+k]),"unequal volume diffusion exchange");
        require(f[k]==-reverse[k],"diffusion antisymmetry");
    }
    State same_a{4,0,0,2,4,8},same_b{1,0,0,0.5,1,2};
    require(diffusion_flux(same_a,same_b,0.1,0.2,1,250)==std::array<double,3>{},
            "uniform concentration across depth gradients");
    require(diffusion_flux(same_a,State{},0.1,0.2,1,250)==std::array<double,3>{},"dry diffusion boundary");
    require(diffusion_flux(same_a,same_b,0.1,0.2,0,250)==std::array<double,3>{},"closed diffusion face");
    require(near(sediment_diffusivity(2,0.1),0.014),"diffusivity scale");
    require(near(bed_shear_stress(0.1,10),0.981),"Chezy shear stress scale");
    std::cout<<"diffusion_mass_uniform_concentration_dry_boundary pass\n";

    const double e32=diffusion_error(32),e64=diffusion_error(64),e128=diffusion_error(128);
    require(e32/e64>3 && e64/e128>3,"diffusion second order convergence");
    std::cout<<"periodic_diffusion_rms_error "<<e32<<' '<<e64<<' '<<e128<<'\n';
}
