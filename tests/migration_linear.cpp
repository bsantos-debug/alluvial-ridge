#include "migration.hpp"
#include <complex>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

using namespace ridge;
using Complex=std::complex<double>;
constexpr double pi=3.14159265358979323846;
constexpr double L=72000, W=500, D=8, E=1, kl=400, Cf=9.81/(55.*55.);
constexpr double S=E*kl*W, alpha=2*Cf/D;

static void require(bool condition,const std::string& message) {
    if(!condition) throw std::runtime_error(message);
}
static bool finite(Complex z) { return std::isfinite(z.real())&&std::isfinite(z.imag()); }
struct Fit { Complex coefficient; double residual=0; int nodes=0; };
static Fit project(const std::vector<Point>& p,double k,double lo=24000,double hi=48000) {
    double cc=0,ss=0,cs=0,cy=0,sy=0;
    Fit r;
    for(auto q:p) if(q.x>=lo&&q.x<=hi) {
        double c=std::cos(k*q.x),s=std::sin(k*q.x);
        cc+=c*c;ss+=s*s;cs+=c*s;cy+=c*q.y;sy+=s*q.y;++r.nodes;
    }
    double det=cc*ss-cs*cs;
    require(det>0&&r.nodes>2,"singular mode projection");
    double c=(cy*ss-sy*cs)/det,s=(sy*cc-cy*cs)/det;
    r.coefficient={c,-s}; // y=Re[C exp(ikx)]; downstream propagation has negative phase.
    for(auto q:p) if(q.x>=lo&&q.x<=hi)
        r.residual+=std::pow(q.y-c*std::cos(k*q.x)-s*std::sin(k*q.x),2);
    r.residual=std::sqrt(r.residual/r.nodes);
    return r;
}
static std::vector<Point> initial(double h,double wavelength,double amplitude,bool literal=false) {
    // The extra interval avoids a ceil(arc_length/h) node-count transition.
    // The separate literal control starts with exactly h-spaced x coordinates.
    int n=int(std::ceil(L/h))+(literal?0:1);
    std::vector<Point> p;
    for(int i=0;i<=n;++i) {
        double x=L*i/n;
        p.push_back({x,i==0||i==n?0:amplitude*std::sin(2*pi*x/wavelength)});
    }
    return p;
}
static Complex continuum(double k) {
    return S*k*k*(-1.+2.5*alpha/(alpha+Complex(0,k)));
}
static Complex discrete(double k,double d) {
    // Fourier symbol of circumcircle curvature in the small-slope limit and
    // exact exponential integration of linearly interpolated nodal curvature.
    double q=std::exp(-alpha*d),a=-std::expm1(-alpha*d),b=(a-alpha*d*q)/(alpha*d);
    Complex e=std::exp(Complex(0,-k*d)),H=((a-b)+b*e)/(1.-q*e);
    return S*std::pow(2*std::sin(k*d/2)/d,2)*(-1.+2.5*H);
}
struct Result {
    std::string kind;
    double wavelength=0,h=0,A=0,T=0,dt=0,d=0,dmin=0,dmax=0,residual=0;
    std::size_t initial_nodes=0,final_nodes=0;
    int calls=0,substeps=0,resamples=0,cutoffs=0,fit_nodes=0;
    Complex gain,gain2,rate,direct,exact,spatial,euler,velocity,finite_inlet;
    double inlet_displacement=0,outlet_displacement=0;
    bool euler_applies=false;
};
static Result calculate(const std::string& kind,double wavelength,double h,double amplitude,
        double T,int calls,bool literal=false) {
    Result r;
    r.kind=kind;r.wavelength=wavelength;r.h=h;r.A=amplitude;r.T=T;r.calls=calls;r.dt=T/calls;
    auto p=initial(h,wavelength,amplitude,literal),start=p;
    double k=2*pi/wavelength;
    r.initial_nodes=p.size();r.d=L/(p.size()-1);
    auto before=project(p,k),before2=project(p,k,36000,60000);
    r.fit_nodes=before.nodes;
    for(int call=0;call<calls;++call) {
        if(kind.find("resample")==0) { resample(p,h);++r.resamples; }
        else {
            auto stats=migrate(p,W,kl,E,D,Cf,h,r.dt);
            r.substeps+=stats.substeps;r.resamples+=stats.resamples;r.cutoffs+=stats.cutoffs;
        }
    }
    auto after=project(p,k),after2=project(p,k,36000,60000);
    r.gain=after.coefficient/before.coefficient;r.gain2=after2.coefficient/before2.coefficient;
    r.exact=continuum(k);r.spatial=discrete(k,r.d);
    if(T>0) { r.rate=std::log(r.gain)/T;r.direct=(r.gain-Complex(1,0))/T; }
    r.euler_applies=T>0&&r.substeps==calls;
    if(r.euler_applies) r.euler=std::log(1.+r.dt*r.spatial)/r.dt;
    auto v=start,finite_values=start;
    auto c=curvature(start),up=exponential_upstream_mean(arc_length(start),c,alpha);
    for(std::size_t i=0;i<start.size();++i) {
        v[i].y=finite_values[i].y=0;
        if(i&&i+1<start.size()) {
            auto t=start[i+1]-start[i-1];
            v[i].y=-S*(-c[i]+2.5*up[i])*t.x/std::hypot(t.x,t.y);
            double x=start[i].x;
            double u=alpha*(alpha*std::sin(k*x)-k*std::cos(k*x)+k*std::exp(-alpha*x))/
                ((alpha*alpha+k*k)*(-std::expm1(-alpha*x)));
            finite_values[i].y=S*amplitude*k*k*(-std::sin(k*x)+2.5*u);
        }
    }
    r.velocity=project(v,k).coefficient/before.coefficient;
    r.finite_inlet=project(finite_values,k).coefficient/before.coefficient;
    auto arcs=arc_length(p);r.dmin=L;
    for(std::size_t i=1;i<arcs.size();++i) {
        r.dmin=std::min(r.dmin,arcs[i]-arcs[i-1]);r.dmax=std::max(r.dmax,arcs[i]-arcs[i-1]);
    }
    r.final_nodes=p.size();r.residual=after.residual/amplitude;
    r.inlet_displacement=distance(p.front(),start.front());
    r.outlet_displacement=distance(p.back(),start.back());
    return r;
}
static const Result& find(const std::vector<Result>& rows,const std::string& kind,
        double wavelength,double h,double amplitude=.1,double dt=0) {
    for(const auto& r:rows) if(r.kind==kind&&r.wavelength==wavelength&&r.h==h&&r.A==amplitude&&(!dt||r.dt==dt)) return r;
    throw std::runtime_error("missing mode check");
}
static void csv(std::ostream& out,const std::vector<Result>& rows) {
    out<<std::setprecision(17);
    out<<"kind,wavelength_m,nominal_spacing_m,amplitude_m,literal_grid,duration_floods,call_dt_floods,initial_nodes,final_nodes,initial_x_spacing_m,final_min_arc_spacing_m,final_max_arc_spacing_m,calls,substeps,resamples,cutoffs,fit_nodes,gain_real,gain_imag,amplitude_ratio,phase_radians,rate_real,rate_imag,direct_rate_real,direct_rate_imag,continuum_real,continuum_imag,spatial_real,spatial_imag,euler_reference_applies,euler_real,euler_imag,initial_velocity_real,initial_velocity_imag,finite_inlet_real,finite_inlet_imag,crop_gain_difference,relative_fit_residual,inlet_displacement_m,outlet_displacement_m\n";
    for(const auto& r:rows) {
        out<<r.kind<<','<<r.wavelength<<','<<r.h<<','<<r.A<<','<<(r.kind=="resample_literal")<<','<<r.T<<','<<r.dt<<','
            <<r.initial_nodes<<','<<r.final_nodes<<','<<r.d<<','<<r.dmin<<','<<r.dmax<<','<<r.calls<<','
            <<r.substeps<<','<<r.resamples<<','<<r.cutoffs<<','<<r.fit_nodes<<','
            <<r.gain.real()<<','<<r.gain.imag()<<','<<std::abs(r.gain)<<','<<std::arg(r.gain)<<',';
        if(r.T>0) out<<r.rate.real()<<','<<r.rate.imag()<<','<<r.direct.real()<<','<<r.direct.imag();
        else out<<",,,"; // No elapsed time: growth rates are undefined.
        out<<','<<r.exact.real()<<','<<r.exact.imag()<<','<<r.spatial.real()<<','<<r.spatial.imag()<<','<<r.euler_applies<<',';
        if(r.euler_applies) out<<r.euler.real()<<','<<r.euler.imag();
        else out<<','; // Native calls can contain many unrecorded Euler substeps.
        out<<','<<r.velocity.real()<<','<<r.velocity.imag()<<','<<r.finite_inlet.real()<<','<<r.finite_inlet.imag()<<','
            <<std::abs(r.gain-r.gain2)<<','<<r.residual<<','<<r.inlet_displacement<<','<<r.outlet_displacement<<'\n';
    }
}
int main(int argc,char** argv) {
    try {
        require(argc==1||(argc==3&&std::string(argv[1])=="--csv"),"usage: migration_linear_test [--csv path]");
        std::vector<Result> rows;
        for(double wavelength:{12000.,4000.}) for(double h:{500.,250.,125.}) {
            for(double amplitude:{.1,.05}) {
                rows.push_back(calculate("single_step",wavelength,h,amplitude,.001,1));
                rows.push_back(calculate("single_step",wavelength,h,amplitude,.0005,1));
                rows.push_back(calculate("evolve",wavelength,h,amplitude,.1,100));
                rows.push_back(calculate("evolve",wavelength,h,amplitude,.1,200));
                rows.push_back(calculate("resample_stable",wavelength,h,amplitude,0,200));
            }
            rows.push_back(calculate("native",wavelength,h,.1,1,1));
            rows.push_back(calculate("resample_literal",wavelength,h,.1,0,1,true));
        }
        double max_euler=0,max_amplitude=0,max_crop=0,max_resample=0;
        for(const auto& r:rows) {
            std::string label=r.kind+" "+std::to_string(r.wavelength)+"/"+std::to_string(r.h);
            for(auto z:{r.gain,r.gain2,r.exact,r.spatial,r.velocity,r.finite_inlet}) require(finite(z),"nonfinite coefficient: "+label);
            require(std::isfinite(r.dmin+r.dmax+r.residual)&&r.dmin>0&&r.dmax<=r.h*(1+1e-10),"invalid node spacing: "+label);
            require(r.cutoffs==0&&r.inlet_displacement==0&&r.outlet_displacement==0,"cutoff or endpoint change: "+label);
            require(r.resamples==r.calls,"unexpected internal mesh distortion: "+label);
            // The omitted kernel tail is tiny at x>=24 km. Compare the projected
            // exact finite-inlet solution directly: 1e-8/flood is an accuracy criterion.
            require(std::abs(r.finite_inlet-r.exact)<1e-8,"finite-inlet reference is not in the far field: "+label);
            require(std::abs(r.velocity-r.spatial)<1e-7,"initial velocity disagrees with discrete symbol: "+label);
            if(r.kind=="resample_literal") {
                require(r.final_nodes==r.initial_nodes+1,"literal-spacing resample did not add one node");
                require(std::abs(r.gain)>0&&std::abs(r.gain)<1&&std::abs(std::arg(r.gain))<1e-10,"literal resample mode response changed");
                continue;
            }
            require(r.final_nodes==r.initial_nodes,"prepared mode changed node count: "+label);
            require(r.residual<1e-7&&std::abs(r.gain-r.gain2)<1e-8,"interior mode/crop control failed: "+label);
            max_crop=std::max(max_crop,std::abs(r.gain-r.gain2));
            if(r.kind=="resample_stable") {
                max_resample=std::max(max_resample,std::abs(r.gain-Complex(1,0)));
                require(std::abs(r.gain-Complex(1,0))<1e-8,"stable-count interpolation changed amplitude materially");
                continue;
            }
            require(finite(r.rate)&&finite(r.direct)&&r.rate.imag()<0,"invalid downstream phase: "+label);
            require((r.wavelength==12000&&r.rate.real()>0)||(r.wavelength==4000&&r.rate.real()<0),"incorrect growth/damping sign: "+label);
            if(r.kind=="single_step") {
                require(r.euler_applies&&std::abs(r.gain-(1.+r.dt*r.spatial))<1e-8,"single-step gain failed");
            } else if(r.kind=="evolve") {
                require(r.euler_applies,"controlled call used multiple Euler steps");
                double error=std::abs(r.rate-r.euler);
                max_euler=std::max(max_euler,error);
                // Controlled amplitude/crop/regridding effects are below 1e-8/flood;
                // 1e-7 leaves a margin while remaining far below resolved spatial errors.
                require(error<1e-7,"complex rate disagrees with discrete Euler response: "+label);
                if(r.A==.1) {
                    double difference=std::abs(r.rate-find(rows,r.kind,r.wavelength,r.h,.05,r.dt).rate);
                    max_amplitude=std::max(max_amplitude,difference);
                    require(difference<5e-8,"small-amplitude limit not resolved");
                }
            }
        }
        std::cout<<std::setprecision(12);
        for(double wavelength:{12000.,4000.}) {
            for(const std::string kind:{"native","evolve"}) {
                double previous=0;
                std::cout<<"migration_linear_"<<(kind=="native"?"native":"spatial_symbol")<<"_complex_errors_"<<wavelength;
                for(double h:{500.,250.,125.}) {
                    const auto& r=find(rows,kind,wavelength,h,kind=="native"?.1:.05,kind=="native"?1:.0005);
                    double error=std::abs((kind=="native"?r.rate:r.spatial)-r.exact);
                    if(previous) require(previous/error>3.5&&previous/error<4.5,"spatial refinement is not approximately second order");
                    previous=error;std::cout<<' '<<error;
                    if(kind=="evolve") {
                        const auto& coarse=find(rows,kind,wavelength,h,.05,.001);
                        double ratio=std::abs(coarse.rate-r.spatial)/std::abs(r.rate-r.spatial);
                        require(ratio>1.8&&ratio<2.2,"Euler time refinement is not first order");
                    }
                }
                std::cout<<'\n';
            }
            double previous=0;
            std::cout<<"migration_linear_literal_resample_loss_percent_"<<wavelength;
            for(double h:{500.,250.,125.}) {
                double loss=1-std::abs(find(rows,"resample_literal",wavelength,h).gain);
                if(previous) require(previous/loss>3.5&&previous/loss<4.5,"literal interpolation attenuation did not diminish with resolution");
                previous=loss;std::cout<<' '<<100*loss;
            }
            std::cout<<'\n';
        }
        std::cout<<"migration_linear_controls max_Euler_rate_error "<<max_euler<<" max_amplitude_rate_difference "<<max_amplitude
            <<" max_crop_gain_difference "<<max_crop<<" max_200_resample_gain_change "<<max_resample<<'\n';
        if(argc==3) {
            std::ofstream out(argv[2]);require(bool(out),"cannot open CSV output");csv(out,rows);
            out.close();require(bool(out),"cannot write complete CSV output");
        }
        std::cout<<"PASS migration Fourier growth/phase, spatial/time refinement, amplitude/boundary controls, and separate resampling response (72 cases)\n";
    } catch(const std::exception& e) { std::cerr<<"FAIL "<<e.what()<<'\n';return 1; }
}
