#include "model.hpp"
#include <functional>
using namespace ridge;

int failures=0;
void require(bool condition,const std::string& message) {
    if(!condition)throw std::runtime_error(message);
}
bool close(double difference,double scale,double absolute=1e-7) {
    return std::abs(difference)<=absolute+2e-12*std::max(1.,std::abs(scale));
}
double sum(const std::array<double,3>& a) {return std::accumulate(a.begin(),a.end(),0.);}
Parameters small(double dx=250) {
    Parameters p;p.length=p.width=8000;p.dx=dx;p.perturbation=0;p.C=0;
    p.qmin=p.qmax=2500;p.duration=300;p.migration=false;return p;
}
std::vector<Point> polygonal_loop() {
    return {{0,4000},{2500,4000},{3500,4000},{3500,6000},
            {1500,6000},{1500,4250},{4000,4250},{8000,4000}};
}
std::vector<Point> rounded_loop() {
    std::vector<Point> line{{0,2800}};double pi=std::acos(-1.),delta=.1;
    for(int i=0;i<=40;++i) {
        double theta=-pi/2+delta+(2*pi-2*delta)*i/40;
        line.push_back({4000+1500*std::cos(theta),4500+1500*std::sin(theta)});
    }
    line.push_back({8000,3300});return line;
}
Model with_line(Parameters p,std::vector<Point> line) {
    Model m(p);m.line=line;resample(m.line,p.channel_width/2);geometry(m,0);
    m.channel.assign(m.line.size(),State{4,2,0,0,0,0});synchronize(m);return m;
}
void valid(const Model& m) {
    for(const auto* states:{&m.channel,&m.q})for(const auto& q:*states) {
        for(double x:q)require(std::isfinite(x),"nonfinite remapped state");
        for(int k:{0,3,4,5})require(q[k]>=0,"negative remapped inventory");
    }
    require(m.water_correction==0&&m.mass_correction==0,"remap needed inventory clipping");
}
void concentration(const Model& m,const std::array<double,3>& c) {
    for(const auto* states:{&m.channel,&m.q})for(const auto& q:*states)if(q[0]>1e-12)
        for(int k=0;k<3;++k)require(std::abs(q[3+k]/q[0]-c[k])<2e-12,"constant concentration changed");
}
void remap_budget(Model& m,int flood,const std::string& label) {
    auto before=storage(m);double solid=total_sediment_inventory(m),forcing=m.bed_external_mass;
    auto bank=m.bank;auto bed=m.z;remap_after_flood(m,flood);auto after=storage(m);valid(m);
    require(close(after.water-before.water,before.water),label+" water budget");
    for(int k=0;k<3;++k)require(close(after.sediment[k]-before.sediment[k],before.sediment[k]),label+" class budget");
    double error=total_sediment_inventory(m)-solid-(m.bed_external_mass-forcing);
    require(close(error,solid,1e-3),label+" solid/bank/forcing budget");
    long double bedchange=0;double density=m.p.dx*m.p.dx*m.p.rho_s*(1-m.p.porosity);
    for(size_t i=0;i<bed.size();++i)bedchange+=(m.z[i]-bed[i])*density;
    double eroded=m.bed_external_mass-forcing-double(bedchange);
    for(int k=0;k<3;++k)require(close((m.bank[k]-bank[k])-eroded*m.fractions[k],eroded,1e-3),label+" bank class allocation");
}
void identity_and_signed_momentum() {
    auto p=small();p.length=p.width=4000;Model m(p);initialize(m);
    for(size_t i=0;i<m.channel.size();++i)m.channel[i]={4+.1*std::sin(i),0,0,.1+.01*i,.2,.3};
    m.channel[2][1]=1;m.channel[3][1]=-m.volume[2]/m.volume[3];
    synchronize(m);auto old=m.channel;auto oldq=m.q;auto oldz=m.z;
    remap_budget(m,1,"identity");double maximum=0;
    for(size_t i=0;i<old.size();++i)for(int k=0;k<6;++k)maximum=std::max(maximum,std::abs(old[i][k]-m.channel[i][k]));
    for(size_t i=0;i<oldq.size();++i)for(int k=0;k<6;++k)maximum=std::max(maximum,std::abs(oldq[i][k]-m.q[i][k]));
    require(maximum<1e-12,"identity erased cancelling local momentum or another field");
    require(oldz==m.z,"identity changed bed");std::cout<<"identity_max_component_change "<<maximum<<'\n';
}
void pulse_counterexample() {
    auto p=small();p.migration=true;p.migration_scale=.001;
    Model m=with_line(p,polygonal_loop());
    // Original dx250 remap debited 145371.759 m2 against this 107303.006 m2 donor.
    // The resulting -38068.754 kg class target failed despite 19 million m3 of water.
    m.channel.at(22)[3]=1;synchronize(m);remap_budget(m,1,"localized cutoff pulse");
    require(m.cutoffs>0,"pulse fixture did not cut off");
    std::cout<<"localized_cutoff_pulse_survives_with_positive_class_storage\n";
}
void advance_event(Model& m,const std::array<double,3>& recycle);
void gaussian_and_constant_concentration() {
    for(double dx:{125.,250.,500.})for(double sigma:{250.,500.,1000.}) {
        auto p=small(dx);p.migration=true;p.migration_scale=.001;
        Model m=with_line(p,rounded_loop());size_t middle=m.channel.size()/2;
        for(size_t i=0;i<m.channel.size();++i) {
            double a=1e-8+std::exp(-.5*std::pow((m.s[i]-m.s[middle])/sigma,2));
            m.channel[i][3]=a;m.channel[i][4]=.3*a;m.channel[i][5]=.1*a;
        }
        synchronize(m);remap_budget(m,1,"smooth cutoff plume");require(m.cutoffs>0,"smooth fixture did not cut off");
        if(sigma==500) {
            auto before=storage(m),external=m.external;double solid=total_sediment_inventory(m);
            m.p.duration=120;advance_event(m,{});auto after=storage(m);
            require(close(after.water-before.water-(m.external.water-external.water),before.water),"smooth post-cutoff water budget");
            double error=total_sediment_inventory(m)-solid;
            for(int k=0;k<3;++k)error-=m.external.sediment[k]-external.sediment[k];
            require(close(error,solid,1e-3),"smooth post-cutoff solid budget");
            std::cout<<"smooth_cutoff_transport_120_seconds_dx "<<dx<<" pass\n";
        }
    }
    auto p=small();p.migration=true;p.migration_scale=.001;
    Model m=with_line(p,rounded_loop());std::array<double,3> c{.1,.03,.007};
    for(auto& q:m.channel)for(int k=0;k<3;++k)q[3+k]=q[0]*c[k];
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0){m.q[i]={.5,.05,.01,0,0,0};for(int k=0;k<3;++k)m.q[i][3+k]=.5*c[k];}
    synchronize(m);remap_budget(m,1,"constant concentration cutoff");concentration(m,c);
    std::cout<<"gaussian_cutoff_grids_125_250_500_and_constant_concentration pass\n";
}
void unsupported_donors_and_wet_capture() {
    auto p=small(500);p.length=p.width=4000;p.channel_width=100;
    Model m=with_line(p,{{0,2250},{4000,2250}});std::array<double,3> c{.2,.03,.005};
    for(auto& q:m.channel)for(int k=0;k<3;++k)q[3+k]=q[0]*c[k];
    synchronize(m);
    std::vector<bool> supported(m.channel.size(),false);
    for(auto map:m.mapping)if(map.a>=0){if(map.w<1)supported[map.a]=true;if(map.w>0)supported[map.b]=true;}
    int unsupported=std::count(supported.begin(),supported.end(),false);
    require(unsupported>0,"unsupported-node fixture has full raster coverage");
    for(auto& point:m.line)point.y=2000;
    remap_budget(m,1,"unsupported donors");concentration(m,c);
    require(storage(m).water>0,"unsupported donors disappeared");
    std::cout<<"zero_raster_support_nodes_retained "<<unsupported<<'\n';

    p=small();p.length=p.width=4000;m=Model(p);initialize(m);
    for(auto& q:m.channel)q={4,2,0,.4,.8,1.2};
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)m.q[i]={.5,-.1,.025,.15,.2,.25};
    synchronize(m);double momentum=0;
    for(size_t i=0;i<m.channel.size();++i)momentum+=m.channel[i][1]*m.volume[i];
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)momentum+=m.q[i][1]*p.dx*p.dx;
    for(auto& point:m.line)point.y+=p.dx;
    remap_budget(m,1,"wet captured floodplain");double after=0;
    for(size_t i=0;i<m.channel.size();++i){auto q=m.channel[i];after+=q[1]*m.volume[i];
        require(q[0]>0&&q[1]/q[0]>=-.2-1e-12&&q[1]/q[0]<=.5+1e-12,"mixed velocity escaped donor bounds");
        for(int k=0;k<3;++k)require(q[3+k]/q[0]>=.1*(k+1)-1e-12&&q[3+k]/q[0]<=.3+.1*k+1e-12,"mixed concentration escaped donor bounds");}
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)after+=m.q[i][1]*p.dx*p.dx;
    require(close(after-momentum,momentum),"straight remap lost streamwise momentum");
}
void advance_event(Model& m,const std::array<double,3>& recycle) {
    double t=0;while(t<m.p.duration-1e-8) {
        double dt=std::min(floodplain_rates(m),m.p.duration-t);
        channel_advance(m,t,dt,recycle);floodplain_advance(m,dt);t+=dt;
    }
    synchronize(m);valid(m);
}
void repeated_remap_recycling() {
    auto p=small();p.length=p.width=4000;p.A=0;p.duration=300;
    Model m(p);initialize(m);m.bank={1e4,2e4,3e4};
    // Zero-settling limit isolates three independent suspension/recycling budgets.
    m.ws={0,0,0};for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0)m.q[i]={.5,0,0,.05,.02,.01};
    synchronize(m);auto initial=storage(m);double solid=total_sediment_inventory(m),injected=0;
    double maximum_water=0,maximum_class=0,maximum_solid=0;int changed=0;
    for(int event=1;event<=24;++event) {
        auto bank=m.bank;std::array<double,3> coeff{};
        for(int k=0;k<3;++k)coeff[k]=bank[k]/(p.duration*std::pow(p.qmin,2.5));
        advance_event(m,coeff);for(int k=0;k<3;++k)injected+=bank[k]-m.bank[k];
        auto mask=m.mapping;double y=p.width/2+.5*p.dx*(1-std::cos(2*std::acos(-1.)*event/8));
        for(auto& point:m.line)point.y=y;
        remap_budget(m,event,"repeated remap");for(size_t i=0;i<mask.size();++i)changed+=(mask[i].a>=0)!=(m.mapping[i].a>=0);
        auto current=storage(m);double dw=current.water-initial.water-m.external.water;
        maximum_water=std::max(maximum_water,std::abs(dw));require(close(dw,initial.water),"repeated water drift");
        for(int k=0;k<3;++k){double ds=current.sediment[k]-initial.sediment[k]-m.external.sediment[k];maximum_class=std::max(maximum_class,std::abs(ds));require(close(ds,current.sediment[k],1e-3),"repeated class drift");}
        double ds=total_sediment_inventory(m)-solid+m.bank_injected-m.bed_external_mass-sum(m.external.sediment);
        maximum_solid=std::max(maximum_solid,std::abs(ds));require(close(ds,solid,1e-2),"repeated solid/bank drift");
        require(close(m.bank_injected-injected,injected,1e-3),"bank debit differs from recorded inlet injection");
        require(m.bank[0]>=0&&m.bank[1]>=0&&m.bank[2]>=0,"negative recycling reservoir");
    }
    require(changed>0,"repeated test never changed a raster mask");
    std::cout<<"repeated_24_events_mask_transitions "<<changed<<" max_water_residual "<<maximum_water<<" max_class_residual "<<maximum_class<<" max_solid_residual "<<maximum_solid<<" recycled_mass "<<m.bank_injected<<'\n';
}
void aggradation_and_reoccupation_limit() {
    auto p=small();p.length=p.width=4000;p.A=.01;
    Model m(p);initialize(m);
    for(int event=1;event<=4;++event) {
        double y=p.width/2+.5*p.dx*(1-std::cos(2*std::acos(-1.)*event/8));
        for(auto& point:m.line)point.y=y;
        remap_budget(m,event,"repeated aggradation");
    }
    Model limit(p);initialize(limit);bool guarded=false;int last_valid=0;
    for(int event=1;event<=16;++event) {
        double depth=metrics(limit).channel_depth;
        double y=p.width/2+.75*p.dx*std::sin(2*std::acos(-1.)*event/8);
        for(auto& point:limit.line)point.y=y;
        try{remap_budget(limit,event,"reoccupation limit");last_valid=event;}
        catch(const std::exception& e) {
            if(std::string(e.what()).find("mean bank height")==std::string::npos)throw;
            require(depth<=0,"bank-height guard did not correspond to nonpositive mean depth");
            guarded=true;std::cout<<"expected_reoccupation_limit_event "<<event<<" last_valid_event "<<last_valid<<" mean_bank_depth "<<depth<<'\n';break;
        }
    }
    require(guarded&&last_valid>=4,"reoccupation fixture did not reach its documented model limit");
}
void cutoff_dry_gap_and_transport() {
    auto p=small();p.migration=true;p.migration_scale=.001;p.duration=120;p.A=.01;
    Model m=with_line(p,rounded_loop());
    for(auto& q:m.channel)q[3]=.01*q[0];
    synchronize(m);
    remap_budget(m,1,"cutoff dry-gap probe");int dry=0;for(auto q:m.channel)dry+=q[0]==0;
    std::cout<<"cutoff_internal_dry_sections "<<dry<<" inlet_depth "<<m.channel.front()[0]<<'\n';
    require(m.channel.front()[0]>0,"cutoff made the specified subcritical inlet dry");
    channel_inlet_flux(m.channel.front(),p.qmin/p.channel_width);
    auto initial=storage(m);auto ext=m.external;advance_event(m,{});auto final=storage(m);
    require(close(final.water-initial.water-(m.external.water-ext.water),initial.water),"post-cutoff transport water budget");
    std::cout<<"post_cutoff_transport_120_seconds pass\n";
}
int main() {
    std::cout<<std::setprecision(17);
    for(const auto& test:std::vector<std::pair<std::string,std::function<void()>>>{{"identity",identity_and_signed_momentum},{"pulse",pulse_counterexample},{"smooth",gaussian_and_constant_concentration},{"unsupported_and_capture",unsupported_donors_and_wet_capture},{"repeated",repeated_remap_recycling},{"aggradation_limit",aggradation_and_reoccupation_limit},{"dry_gap",cutoff_dry_gap_and_transport}}) {
        try{test.second();std::cout<<test.first<<" pass\n";}catch(const std::exception& e){++failures;std::cout<<test.first<<" FAIL "<<e.what()<<'\n';}
    }
    return failures?1:0;
}
