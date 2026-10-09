#include "model.hpp"
#include <functional>
using namespace ridge;

int failures=0;
void check(const char* name,bool passed,double error=0) {
    std::cout<<name<<' '<<(passed?"pass":"FAIL")<<" error="<<std::setprecision(16)<<error<<'\n';
    if(!passed)++failures;
}
Parameters small_parameters() {
    Parameters p;p.length=4000;p.width=4000;p.dx=250;p.perturbation=0;
    p.migration=false;p.viscosity=false;p.C=0;p.qmin=p.qmax=2500;
    return p;
}
double sum(const std::array<double,3>& x) {return std::accumulate(x.begin(),x.end(),0.);}

void characteristic_boundaries() {
    // Construct independent interior and boundary states sharing the outgoing
    // invariant, then recover the known boundary momentum flux from specified q.
    const double hb=6,qb=5,hi=5;
    double outgoing=qb/hb-2*std::sqrt(g*hb),ui=outgoing+2*std::sqrt(g*hi);
    auto inlet=channel_inlet_flux(State{hi,hi*ui,0,0,0,0},qb);
    double momentum=qb*qb/hb+.5*g*hb*hb;
    check("inlet_discharge_and_outgoing_characteristic",inlet[0]==qb&&std::abs(inlet[1]-momentum)<1e-10,inlet[1]-momentum);
    State interior{5,6,0,1,2,3};
    auto outlet=channel_outlet_flux(interior,55,.0001);
    double depth=std::pow(outlet[0]/(55*std::sqrt(.0001)),2./3.);
    double invariant=outlet[0]/depth+2*std::sqrt(g*depth);
    double expected=interior[1]/interior[0]+2*std::sqrt(g*interior[0]);
    check("outlet_rating_and_outgoing_characteristic",std::abs(invariant-expected)<1e-12,invariant-expected);
    for(int k=0;k<3;++k)check("outlet_passive_concentration",std::abs(outlet[3+k]/outlet[0]-interior[3+k]/interior[0])<1e-14);
    check("dry_outlet_zero_flux",channel_outlet_flux(State{},55,.0001)==State{});
    check("closed_dry_inlet_zero_flux",channel_inlet_flux(State{},0)==State{});
    State fast{1,4,0,3,2,1};
    check("supercritical_outgoing_flux",channel_outlet_flux(fast,55,.0001)==physical_flux(fast,0));
    auto backflow=channel_outlet_flux(State{1,-1,0,1,2,3},55,.0001);
    check("subcritical_backflow_respects_outlet_rating",backflow[0]>0&&std::isfinite(backflow[1]));
    auto flat=channel_outlet_flux(State{2,0,0,0,0,0},55,0);
    check("zero_slope_outlet_lake",flat[0]==0&&std::abs(flat[1]-2*g)<1e-12);
    bool dry=false,super_in=false,super_tail=false;
    try{channel_inlet_flux(State{},1);}catch(const std::runtime_error&){dry=true;}
    try{channel_inlet_flux(fast,4);}catch(const std::runtime_error&){super_in=true;}
    try{channel_outlet_flux(State{1,-4,0,0,0,0},55,.0001);}catch(const std::runtime_error&){super_tail=true;}
    check("underspecified_boundary_regimes_reported",dry&&super_in&&super_tail);
}

void coupled_lake() {
    auto p=small_parameters();p.slope=0;p.qmin=p.qmax=0;
    Model m(p);geometry(m,0);m.channel.resize(m.line.size());m.ws={0,0,0};
    for(size_t i=0;i<m.channel.size();++i)m.channel[i]={2-m.zc[i],0,0,0,0,0};
    for(size_t i=0;i<m.q.size();++i)m.q[i]={2-m.z[i],0,0,0,0,0};
    for(auto& f:m.faces)if(f.boundary==2)f.boundary=1;
    synchronize(m);auto before=storage(m);
    double dt=std::min(0.1,floodplain_rates(m)),maxrate=0;
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)
        maxrate=std::max({maxrate,std::abs(m.rate[i][1]),std::abs(m.rate[i][2])});
    check("coupled_closed_lake_momentum_rate",maxrate<1e-12,maxrate);
    channel_advance(m,0,dt,{0,0,0});floodplain_advance(m,dt);
    double residual=storage(m).water-before.water-m.external.water;
    check("coupled_closed_lake_water",std::abs(residual)<1e-7,residual);
}

void exchange_budget() {
    auto p=small_parameters();Model m(p);initialize(m);m.ws={0,0,0};
    for(size_t i=0;i<m.channel.size();++i)m.channel[i]={10,10,0,10,5,2};
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)
        m.q[i]={0.7+0.01*(i%3),0.02,-0.01,0.1,0.2,0.3};
    synchronize(m);auto before=storage(m);
    double dt=std::min(0.1,floodplain_rates(m));
    channel_advance(m,0,dt,{0,0,0});floodplain_advance(m,dt);
    auto after=storage(m);
    double water=after.water-before.water-m.external.water-m.water_correction;
    check("coupled_exchange_water",std::abs(water)<1e-6,water);
    for(int k=0;k<3;++k) {
        double error=after.sediment[k]-before.sediment[k]-m.external.sediment[k];
        std::string name="coupled_exchange_class_"+std::to_string(k);
        check(name.c_str(),std::abs(error)<1e-6,error);
    }
}

void remap_budget(double aggradation=0) {
    auto p=small_parameters();p.A=aggradation;Model m(p);initialize(m);
    for(size_t i=0;i<m.channel.size();++i)m.channel[i]={4+0.1*i,1,0,1+0.05*i,0.5,0.2};
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)m.q[i]={0.5,0.01,0.01,0.1,0.2,0.3};
    synchronize(m);auto before=storage(m);auto oldz=m.z;auto oldmap=m.mapping;
    // Force one grid-cell translation, including endpoints. This exercises the
    // actual remapper without conflating its budgets with the migration law.
    for(auto& point:m.line)point.y+=p.dx;
    remap_after_flood(m,1);auto after=storage(m);
    double dw=after.water-before.water;
    check("remap_water",std::abs(dw)<1e-6,dw);
    for(int k=0;k<3;++k) {
        double error=after.sediment[k]-before.sediment[k];
        std::string name="remap_suspended_class_"+std::to_string(k);
        check(name.c_str(),std::abs(error)<1e-6,error);
    }
    double solid_change=0;
    for(size_t i=0;i<m.z.size();++i)solid_change+=(m.z[i]-oldz[i])*p.dx*p.dx*p.rho_s*(1-p.porosity);
    double ds=solid_change+sum(m.bank)-m.bed_external_mass;
    check(aggradation==0?"translated_remap_solid_and_bank":"aggrading_translated_remap_solid_and_bank",std::abs(ds)<1e-3,ds);
}

void exchange_plume_positivity() {
    auto p=small_parameters();Model m(p);initialize(m);m.ws={0,0,0};
    for(auto& a:m.channel)a={10,10,0,0,0,0};
    m.channel[m.channel.size()/2][3]=1;
    synchronize(m);
    // A wet channel node containing a plume borders a clean wet node. Its
    // interpolated ghost cell may export only sediment present in each donor.
    auto initial=storage(m);double time=0,minimum_dt=1e100;
    for(int i=0;i<150;++i) {
        double dt=floodplain_rates(m);minimum_dt=std::min(minimum_dt,dt);
        channel_advance(m,time,dt,{0,0,0});floodplain_advance(m,dt);time+=dt;
    }
    auto final=storage(m);
    check("coupled_plume_exchange_positive_timestep",minimum_dt>1e-6,minimum_dt);
    double wr=final.water-initial.water-m.external.water-m.water_correction;
    double sr=sum(final.sediment)-sum(initial.sediment)-sum(m.external.sediment)-m.mass_correction;
    check("subcycled_plume_water_budget",std::abs(wr)<1e-5,wr);
    check("subcycled_plume_sediment_budget",std::abs(sr)<1e-6,sr);
}

void uniform_channel() {
    auto run=[](double spacing) {
        auto p=small_parameters();Model m(p);initialize(m);
        double h=normal_depth(p.qmin,p.channel_width,p.channel_chezy,p.slope);
        resample(m.line,spacing);geometry(m,0);
        m.channel.assign(m.line.size(),State{h,p.qmin/p.channel_width,0,0,0,0});
        channel_advance(m,0,1000,{0,0,0});
        double error=0;for(auto q:m.channel)error=std::max(error,std::abs(q[0]/h-1));
        return error;
    };
    double coarse=run(250),fine=run(125);
    check("uniform_channel_depth_relative_error",coarse<0.005,coarse);
    check("uniform_channel_grid_refinement",coarse/fine>1.7,fine);
}

void recycle_normalization() {
    auto run=[](double cfl) {
        auto p=small_parameters();p.duration=1000;p.qmax=15000;p.cfl=cfl;
        Model m(p);initialize(m);m.bank={1e6,2e6,3e6};
        const double initial=total_sediment_inventory(m),partial_time=0.4*p.duration;
        auto integrate=[&](double until){
            double integral=0;int n=20000;
            for(int i=0;i<=n;++i)integral+=(i==0||i==n?1:i%2?4:2)*std::pow(hydrograph(p,until*i/n),2.5);
            return integral*until/n/3;
        };
        const double integral=integrate(p.duration),partial=integrate(partial_time);
        std::array<double,3> coeff{};for(int k=0;k<3;++k)coeff[k]=m.bank[k]/integral;
        channel_advance(m,0,partial_time,coeff);
        const double shape_error=std::abs(m.bank_injected/6e6-partial/integral);
        channel_advance(m,partial_time,p.duration-partial_time,coeff);
        double ledger=sum(m.bank)+m.bank_injected-6e6;
        check("recycle_reservoir_debit_matches_injection",std::abs(ledger)<1e-6,ledger);
        check("recycle_reservoir_nonnegative",m.bank[0]>=0&&m.bank[1]>=0&&m.bank[2]>=0,sum(m.bank));
        double total=total_sediment_inventory(m)-initial+m.bank_injected-sum(m.external.sediment);
        check("recycle_global_solid_bank_suspension_ledger",std::abs(total)<1e-3,total);
        std::cout<<"recycle_shape_error cfl="<<cfl<<" error="<<shape_error<<'\n';
        return shape_error;
    };
    double coarse=run(.4),fine=run(.2);
    check("recycle_shape_time_refinement",coarse/fine>1.6,fine);
}

int main() {
    for(auto test:std::vector<std::function<void()>>{characteristic_boundaries,coupled_lake,exchange_budget,[]{remap_budget();},[]{remap_budget(0.01);},exchange_plume_positivity,uniform_channel,recycle_normalization}) {
        try{test();}catch(const std::exception& e){++failures;std::cout<<"FAIL exception "<<e.what()<<'\n';}
    }
    return failures?1:0;
}
