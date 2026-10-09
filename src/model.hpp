#pragma once
#include "finite_volume.hpp"
#include "migration.hpp"
#include "sediment.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace ridge {
struct Parameters {
    double length=72000,width=48000,dx=250,channel_width=500,slope=.0001,initial_depth=8;
    double duration=20*86400.,qmin=2500,qmax=15000,channel_chezy=55,floodplain_chezy=10;
    double A=0,C=.003,E=1,migration_scale=400,perturbation=5;
    double cfl=.4,max_dt=120,porosity=.4,rho_s=2650,tau_critical=.1;
    double sand_d=.0002,silt_ws=.0002,clay_d=.000002,diffusion_scale=1,concentration_scale=.001;
    int floods=580,seed=2018,run=11;
    bool fine=false,migration=true,viscosity=true;
};
struct Mapping {int a=-1,b=-1;double w=0,tx=1,ty=0;};
struct Link {int a,b,axis,boundary=0;}; // boundary: 1 reflected, 2 downstream open
struct Budget {double water=0;std::array<double,3> sediment{};};
struct Model {
    Parameters p;int nx,ny,lo_x=0,hi_x=0,lo_y=0,hi_y=0;
    std::vector<int> mapped_ids,face_start;
    std::vector<Point> line;
    std::vector<State> channel,cr,exchange,q,rate;
    std::vector<double> z,zc,s,volume,tx,ty,deposition,initial_z;
    std::vector<Mapping> mapping;
    std::vector<Link> faces;
    std::vector<std::array<double,4>> gradient;
    std::array<double,3> fractions,ws,bank{};
    double bank_water=0,water_correction=0,mass_correction=0;
    Budget external;double deposited_mass=0,bed_external_mass=0,bank_injected=0;
    double clock=0;long steps=0,channel_steps=0;int cutoffs=0;
    Model(const Parameters& par):p(par),nx(std::lround(p.length/p.dx)),ny(std::lround(p.width/p.dx)) {
        if(nx<4||ny<4||std::abs(nx*p.dx-p.length)>1e-8||std::abs(ny*p.dx-p.width)>1e-8)
            throw std::runtime_error("grid must tile the domain exactly");
        int n=nx*ny;q.resize(n);rate.resize(n);z.resize(n);initial_z.resize(n);
        mapping.resize(n);deposition.resize(n);gradient.resize(n);
        fractions=p.fine?std::array<double,3>{.05,.20,.75}:std::array<double,3>{.05,.75,.20};
        ws=settling_velocities(p.sand_d,p.silt_ws,p.clay_d);
        std::mt19937 gen(p.seed);std::uniform_real_distribution<double> noise(-std::sqrt(3.),std::sqrt(3.));
        int nc=std::lround(p.length/(p.channel_width/2));
        for(int i=0;i<=nc;++i) {
            double y=p.width/2+(i==0||i==nc?0:p.perturbation*noise(gen));
            line.push_back({p.length*i/nc,y});
        }
        for(int j=0;j<ny;++j)for(int i=0;i<nx;++i) z[j*nx+i]=initial_z[j*nx+i]=p.slope*(p.length-(i+.5)*p.dx);
    }
};
inline double hydrograph(const Parameters& p,double t) {
    // Smooth symmetric flood, a declared choice because only endpoints and peak are published.
    double a=std::sin(3.141592653589793*std::clamp(t/p.duration,0.,1.));
    return p.qmin+(p.qmax-p.qmin)*a*a;
}
inline double normal_depth(double discharge,double width,double chezy,double slope) {
    return std::pow(std::abs(discharge)/(width*chezy*std::sqrt(slope)),2./3.);
}
// Wet subcritical inlet: impose unit discharge and preserve the outgoing
// characteristic u-2*sqrt(g*h). A second hydraulic datum would be required
// for a dry or supercritical inflow; the written specification provides none.
inline State channel_inlet_flux(const State& interior,double unit_discharge) {
    if(unit_discharge<0 || interior[0]<0)
        throw std::invalid_argument("invalid channel inlet state");
    if(interior[0]==0) {
        if(unit_discharge==0)return State{};
        throw std::runtime_error("dry channel inlet requires a prescribed inflow depth");
    }
    double wave=std::sqrt(g*interior[0]),u=interior[1]/interior[0];
    if(std::abs(u)>=wave)
        throw std::runtime_error("non-subcritical channel inlet requires an additional hydraulic boundary condition");
    double outgoing=u-2*wave,h;
    if(unit_discharge==0)h=std::pow(-outgoing/(2*std::sqrt(g)),2);
    else {
        // q/h-2*sqrt(g*h) strictly decreases from +infinity to -infinity.
        double lo=0,hi=std::max(interior[0],std::pow(unit_discharge/std::sqrt(g),2./3.));
        while(unit_discharge/hi-2*std::sqrt(g*hi)>outgoing) {
            hi*=2;
            if(!std::isfinite(hi))throw std::runtime_error("channel inlet root bracket overflow");
        }
        for(int iteration=0;iteration<60;++iteration) {
            double mid=.5*(lo+hi);
            if(mid==lo||mid==hi)break;
            if(unit_discharge/mid-2*std::sqrt(g*mid)>outgoing)lo=mid;else hi=mid;
        }
        h=.5*(lo+hi);
    }
    State flux{};flux[0]=unit_discharge;
    flux[1]=(h>0?unit_discharge*unit_discharge/h:0)+.5*g*h*h;
    return flux;
}
// Subcritical outlet assumption: Chezy normal-flow rating u=C*sqrt(S*h),
// coupled to the outgoing characteristic u+2*sqrt(g*h). No incoming sediment.
inline State channel_outlet_flux(const State& interior,double chezy,double slope) {
    if(interior[0]<0||chezy<=0||slope<0)
        throw std::invalid_argument("invalid channel outlet state");
    if(interior[0]==0)return State{};
    double wave=std::sqrt(g*interior[0]),u=interior[1]/interior[0];
    if(u>=wave)return physical_flux(interior,0);
    if(u<=-wave)
        throw std::runtime_error("supercritical inflow at downstream boundary requires an external hydraulic state");
    double rating=chezy*std::sqrt(slope);
    double root_h=(u+2*wave)/(rating+2*std::sqrt(g));
    State boundary{};boundary[0]=root_h*root_h;boundary[1]=boundary[0]*rating*root_h;
    for(int k=3;k<6;++k)boundary[k]=boundary[0]*(interior[k]/interior[0]);
    return physical_flux(boundary,0);
}
inline double norm_u(const State& a) {
    if(a[0]<=1e-12)return 0.;
    double u=a[1]/a[0],v=a[2]/a[0],square=u*u+v*v;
    if(!std::isfinite(square))throw std::runtime_error("nonfinite squared velocity");
    return std::sqrt(square);
}
inline void resistance(State& a,double chezy,double dt) {
    if(a[0]<=1e-10){a[1]=a[2]=0;return;}
    double r=1+dt*g*norm_u(a)/(chezy*chezy*a[0]);a[1]/=r;a[2]/=r;
}
inline void geometry(Model& m,int flood) {
    size_t n=m.line.size();m.s.assign(n,0);m.zc.resize(n);m.volume.resize(n);m.tx.resize(n);m.ty.resize(n);
    for(size_t i=1;i<n;++i)m.s[i]=m.s[i-1]+std::hypot(m.line[i].x-m.line[i-1].x,m.line[i].y-m.line[i-1].y);
    for(size_t i=0;i<n;++i) {
        size_t a=i?i-1:0,b=std::min(i+1,n-1);double l=std::hypot(m.line[b].x-m.line[a].x,m.line[b].y-m.line[a].y);
        m.tx[i]=(m.line[b].x-m.line[a].x)/l;m.ty[i]=(m.line[b].y-m.line[a].y)/l;
        m.volume[i]=.5*(m.s[b]-m.s[a])*m.p.channel_width;
        m.zc[i]=m.p.slope*m.p.length*(1-m.s[i]/m.s.back())-m.p.initial_depth+flood*m.p.A;
    }
    m.mapping.assign(m.nx*m.ny,Mapping{});
    std::vector<double> best(m.nx*m.ny,1e100);
    double radius=.5*m.p.channel_width;
    for(size_t k=0;k+1<n;++k) {
        auto a=m.line[k],b=m.line[k+1];double vx=b.x-a.x,vy=b.y-a.y,ll=vx*vx+vy*vy;
        int i0=std::max(0,int(std::floor((std::min(a.x,b.x)-radius)/m.p.dx)));
        int i1=std::min(m.nx-1,int(std::floor((std::max(a.x,b.x)+radius)/m.p.dx)));
        int j0=std::max(0,int(std::floor((std::min(a.y,b.y)-radius)/m.p.dx)));
        int j1=std::min(m.ny-1,int(std::floor((std::max(a.y,b.y)+radius)/m.p.dx)));
        for(int j=j0;j<=j1;++j)for(int i=i0;i<=i1;++i) {
            double px=(i+.5)*m.p.dx-a.x,py=(j+.5)*m.p.dx-a.y;
            double w=std::clamp((px*vx+py*vy)/ll,0.,1.);double d=std::hypot(px-w*vx,py-w*vy);int id=j*m.nx+i;
            if(d<=radius&&d<best[id]){best[id]=d;m.mapping[id]={int(k),int(k+1),w,vx/std::sqrt(ll),vy/std::sqrt(ll)};}
        }
    }
    m.faces.clear();m.faces.reserve(m.nx*m.ny*2);
    m.mapped_ids.clear();m.face_start.resize(m.nx*m.ny+1);
    for(int j=0;j<m.ny;++j)for(int i=0;i<m.nx;++i){
        int a=j*m.nx+i;m.face_start[a]=m.faces.size();
        if(m.mapping[a].a>=0)m.mapped_ids.push_back(a);
        if(i+1<m.nx && (m.mapping[a].a<0||m.mapping[a+1].a<0))m.faces.push_back({a,a+1,0,0});
        if(j+1<m.ny && (m.mapping[a].a<0||m.mapping[a+m.nx].a<0))m.faces.push_back({a,a+m.nx,1,0});
        if(m.mapping[a].a>=0)continue;
        if(i==0)m.faces.push_back({a,-1,0,-1});
        if(i==m.nx-1)m.faces.push_back({a,-1,0,2});
        if(j==0)m.faces.push_back({a,-1,1,-1});
        if(j==m.ny-1)m.faces.push_back({a,-1,1,1});
    }
    m.face_start.back()=m.faces.size();
    m.cr.resize(n);m.exchange.resize(n);
}
inline State channel_at(const Model& m,const Mapping& a) {
    State r{};
    for(int k=0;k<6;++k)r[k]=(1-a.w)*m.channel[a.a][k]+a.w*m.channel[a.b][k];
    double stream=r[1];r[1]=stream*a.tx;r[2]=stream*a.ty;return r;
}
inline void synchronize(Model& m) {
    for(int i:m.mapped_ids) {
        auto a=m.mapping[i];m.q[i]=channel_at(m,a);m.z[i]=(1-a.w)*m.zc[a.a]+a.w*m.zc[a.b];
    }
}
inline void initialize(Model& m) {
    geometry(m,0);m.channel.resize(m.line.size());
    double h=normal_depth(m.p.qmin,m.p.channel_width,m.p.channel_chezy,m.p.slope*m.p.length/m.s.back());
    for(auto& q:m.channel) {q={h,m.p.qmin/m.p.channel_width,0,0,0,0};}
    synchronize(m);
}
inline Budget storage(const Model& m) {
    Budget a;
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0) {
        a.water+=m.q[i][0]*m.p.dx*m.p.dx;
        for(int k=0;k<3;++k)a.sediment[k]+=m.q[i][3+k]*m.p.dx*m.p.dx;
    }
    for(size_t i=0;i<m.channel.size();++i){a.water+=m.channel[i][0]*m.volume[i];for(int k=0;k<3;++k)a.sediment[k]+=m.channel[i][3+k]*m.volume[i];}
    return a;
}
inline void check_state(State& a,Model& m,double area,const char* location) {
    for(int k: {0,3,4,5}) {
        if(!std::isfinite(a[k])||a[k]<-1e-8)throw std::runtime_error(std::string("negative/nonfinite ")+location+" component "+std::to_string(k)+" value "+std::to_string(a[k]));
        if(a[k]<0){if(k==0)m.water_correction-=a[k]*area;else m.mass_correction-=a[k]*area;a[k]=0;}
    }
    if(!std::isfinite(a[1])||!std::isfinite(a[2]))throw std::runtime_error("nonfinite momentum");
    if(a[0]<1e-10)a[1]=a[2]=0;
}
inline void add_exchange(Model& m,int id,const State& flux,double sign,const State* floodplain_donor=nullptr) {
    auto a=m.mapping[id];int nodes[2]={a.a,a.b};double weights[2]={1-a.w,a.w};
    // Outgoing component flux is withdrawn in proportion to each section's
    // contribution to the interpolated donor inventory, preserving positivity.
    for(int k:{0,3,4,5}) {
        double amount=sign*flux[k]*m.p.dx;
        double total=weights[0]*m.channel[nodes[0]][k]+weights[1]*m.channel[nodes[1]][k];
        for(int side=0;side<2;++side) {
            int j=nodes[side];double fraction=amount<0?(total>0?weights[side]*m.channel[j][k]/total:0):weights[side];
            m.exchange[j][k]+=fraction*amount/m.volume[j];
            if(k==0) {
                double u=0;
                if(amount<0&&m.channel[j][0]>1e-12)u=m.channel[j][1]/m.channel[j][0];
                else if(floodplain_donor&&(*floodplain_donor)[0]>1e-12)
                    u=((*floodplain_donor)[1]*m.tx[j]+(*floodplain_donor)[2]*m.ty[j])/(*floodplain_donor)[0];
                m.exchange[j][1]+=fraction*amount*u/m.volume[j];
            }
        }
    }
}
inline void velocity_gradients(Model& m) {
    for(int j=m.lo_y;j<m.hi_y;++j)for(int i=m.lo_x;i<m.hi_x;++i){int a=j*m.nx+i;
        if(m.q[a][0]<=1e-10){m.gradient[a]={};continue;}
        int l=j*m.nx+std::max(0,i-1),r=j*m.nx+std::min(m.nx-1,i+1),b=std::max(0,j-1)*m.nx+i,t=std::min(m.ny-1,j+1)*m.nx+i;
        auto vel=[&](int id,int k){return m.q[id][0]>1e-10?m.q[id][k]/m.q[id][0]:0.;};
        m.gradient[a]={(vel(r,1)-vel(l,1))/((r-l)*m.p.dx),(vel(t,1)-vel(b,1))/((t-b)/m.nx*m.p.dx),
                       (vel(r,2)-vel(l,2))/((r-l)*m.p.dx),(vel(t,2)-vel(b,2))/((t-b)/m.nx*m.p.dx)};
    }
}
// Compute rates once per floodplain step. The channel is subcycled at its own
// wave CFL while these conservative lateral exchange rates remain fixed.
inline double floodplain_rates(Model& m) {
    synchronize(m);
    // Every nonzero-depth cell and one neighboring cell are included. A face
    // outside this rectangle has two exactly dry states, hence zero flux.
    // Keep the original row/face order so floating-point sums are unchanged.
    m.lo_x=m.nx;m.hi_x=0;m.lo_y=m.ny;m.hi_y=0;
    for(int j=0;j<m.ny;++j)for(int i=0;i<m.nx;++i)if(m.q[j*m.nx+i][0]>0) {
        m.lo_x=std::min(m.lo_x,i);m.hi_x=std::max(m.hi_x,i+1);
        m.lo_y=std::min(m.lo_y,j);m.hi_y=std::max(m.hi_y,j+1);
    }
    m.lo_x=std::max(0,m.lo_x-1);m.hi_x=std::min(m.nx,m.hi_x+1);
    m.lo_y=std::max(0,m.lo_y-1);m.hi_y=std::min(m.ny,m.hi_y+1);
    for(int j=m.lo_y;j<m.hi_y;++j)for(int i=j*m.nx+m.lo_x;i<j*m.nx+m.hi_x;++i)m.rate[i]={};
    for(auto& a:m.exchange)a={};
    if(m.p.viscosity)velocity_gradients(m);
    double dt=m.p.max_dt,dx=m.p.dx;
    for(int j=m.lo_y;j<m.hi_y;++j)for(int i=j*m.nx+m.lo_x;i<j*m.nx+m.hi_x;++i)if(m.mapping[i].a<0&&m.q[i][0]>1e-10) {
        double speed=(std::abs(m.q[i][1])+std::abs(m.q[i][2]))/m.q[i][0]+2*std::sqrt(g*m.q[i][0]);
        dt=std::min(dt,m.p.cfl*dx/speed);
    }
    for(int j=m.lo_y;j<m.hi_y;++j)for(int face=m.face_start[j*m.nx+m.lo_x];face<m.face_start[j*m.nx+m.hi_x];++face) {
        auto e=m.faces[face];
        State a=m.q[e.a],b=e.b>=0?m.q[e.b]:a;
        if(a[0]==0&&b[0]==0)continue;
        double za=m.z[e.a],zb=e.b>=0?m.z[e.b]:za;
        if(e.boundary==1)b[1+e.axis]*=-1;
        if(e.boundary==-1)a[1+e.axis]*=-1;
        if(e.boundary==2){zb-=m.p.slope*dx;b[1]=std::max(0.,b[1]);}
        // Tracer fluxes below use upwind concentration plus diffusion; avoid
        // calculating passive HLL tracer fluxes that would be overwritten.
        auto f=face_flux<3>(a,b,za,zb,e.axis);
        double ca=m.mapping[e.a].a>=0?m.p.channel_chezy:m.p.floodplain_chezy;
        double cb=e.b>=0&&m.mapping[e.b].a>=0?m.p.channel_chezy:m.p.floodplain_chezy;
        double hf=std::min(std::max(0.,a[0]+za-std::max(za,zb)),std::max(0.,b[0]+zb-std::max(za,zb)));
        double da=sediment_diffusivity(a[0],std::sqrt(g)*norm_u(a)/ca);
        double db=sediment_diffusivity(b[0],std::sqrt(g)*norm_u(b)/cb);
        auto dif=diffusion_flux(a,b,da*m.p.diffusion_scale,db*m.p.diffusion_scale,hf,dx);
        for(int k=3;k<6;++k) {
            double conc=f.left[0]>=0?(a[0]>1e-12?a[k]/a[0]:0):(b[0]>1e-12?b[k]/b[0]:0);
            f.left[k]=f.right[k]=f.left[0]*conc+(std::abs(e.boundary)==1?0:dif[k-3]);
        }
        if(m.p.viscosity&&e.b>=0&&hf>0) {
            auto ga=m.gradient[e.a],gb=m.gradient[e.b];double nud=.5*(da+db)*hf;
            if(e.axis==0){double normal=nud*(ga[0]+gb[0]),shear=.5*nud*(ga[1]+gb[1]+ga[2]+gb[2]);f.left[1]-=normal;f.right[1]-=normal;f.left[2]-=shear;f.right[2]-=shear;}
            else {double normal=nud*(ga[3]+gb[3]),shear=.5*nud*(ga[1]+gb[1]+ga[2]+gb[2]);f.left[2]-=normal;f.right[2]-=normal;f.left[1]-=shear;f.right[1]-=shear;}
        }
        if(e.boundary==-1)for(int k=0;k<6;++k)f.left[k]=-f.right[k];
        for(int side=0;side<2;++side) {
            int id=side?e.b:e.a;if(id<0)continue;State fl=side?f.right:f.left;double sign=side?1:-1;
            if(m.mapping[id].a<0){for(int k=0;k<6;++k)m.rate[id][k]+=sign*fl[k]/dx;}
            else {
                // Signal speed uses reconstructed overbank depth, not deep channel ghost storage.
                double h=std::max(0.,m.q[id][0]+m.z[id]-std::max(za,zb));
                double speed=norm_u(m.q[id])+2*std::sqrt(g*h);
                dt=std::min(dt,m.p.cfl*dx/std::max(speed,1e-6));
                int donor=side?e.a:e.b;
                add_exchange(m,id,fl,sign,donor>=0?&m.q[donor]:nullptr);
            }
        }
    }
    // Conservative positivity restriction for explicit transport and diffusion.
    // Only negative net rates constrain the local forward-Euler update.
    for(int j=m.lo_y;j<m.hi_y;++j)for(int i=j*m.nx+m.lo_x;i<j*m.nx+m.hi_x;++i)if(m.mapping[i].a<0)for(int k:{0,3,4,5})
        if(m.rate[i][k]<0)dt=std::min(dt,.9*m.q[i][k]/(-m.rate[i][k]));
    for(size_t i=0;i<m.channel.size();++i)for(int k:{0,3,4,5})
        if(m.exchange[i][k]<0)dt=std::min(dt,.5*m.channel[i][k]/(-m.exchange[i][k]));
    if(!(dt>1e-6)||!std::isfinite(dt))throw std::runtime_error("floodplain timestep collapsed: "+std::to_string(dt));
    return dt;
}
inline void channel_advance(Model& m,double floodtime,double dt,const std::array<double,3>& recycle_coeff) {
    double elapsed=0;size_t n=m.channel.size();double B=m.p.channel_width;
    while(elapsed<dt-1e-10) {
        double sub=dt-elapsed;
        for(size_t i=0;i<n;++i) {
            double speed=norm_u(m.channel[i])+std::sqrt(g*m.channel[i][0]);
            sub=std::min(sub,m.p.cfl*(m.volume[i]/B)/std::max(speed,1e-6));
            m.cr[i]=m.exchange[i];
        }
        for(size_t i=0;i+1<n;++i) {
            auto f=face_flux<3>(m.channel[i],m.channel[i+1],m.zc[i],m.zc[i+1],0);
            double hf=std::min(m.channel[i][0],m.channel[i+1][0]);
            double da=sediment_diffusivity(m.channel[i][0],std::sqrt(g)*norm_u(m.channel[i])/m.p.channel_chezy);
            double db=sediment_diffusivity(m.channel[i+1][0],std::sqrt(g)*norm_u(m.channel[i+1])/m.p.channel_chezy);
            auto dif=diffusion_flux(m.channel[i],m.channel[i+1],da*m.p.diffusion_scale,db*m.p.diffusion_scale,hf,m.s[i+1]-m.s[i]);
            for(int k=3;k<6;++k){const State& donor=f.left[0]>=0?m.channel[i]:m.channel[i+1];double c=donor[0]>1e-12?donor[k]/donor[0]:0;f.left[k]=f.right[k]=f.left[0]*c+dif[k-3];}
            if(m.p.viscosity&&hf>0) {
                double u=m.channel[i][1]/m.channel[i][0],v=m.channel[i+1][1]/m.channel[i+1][0];
                double stress=(da+db)*hf*(v-u)/(m.s[i+1]-m.s[i]);f.left[1]-=stress;f.right[1]-=stress;
            }
            for(int k=0;k<6;++k){m.cr[i][k]-=f.left[k]*B/m.volume[i];m.cr[i+1][k]+=f.right[k]*B/m.volume[i+1];}
        }
        double Q=hydrograph(m.p,floodtime+elapsed);
        State inlet=channel_inlet_flux(m.channel.front(),Q/B);
        std::array<double,3> recycled_rate{};
        for(int k=0;k<3;++k){
            recycled_rate[k]=std::min(recycle_coeff[k]*std::pow(Q,2.5),std::max(0.,m.bank[k])/sub);
            inlet[3+k]=(m.p.concentration_scale*m.p.C*m.fractions[k]*std::pow(Q,2.5)+recycled_rate[k])/B;
        }
        // Boundary flux is at the endpoint section, whose volume is a half cell.
        auto outlet=channel_outlet_flux(m.channel.back(),m.p.channel_chezy,
                                        m.p.slope*m.p.length/m.s.back());
        for(int k=0;k<6;++k){m.cr.front()[k]+=inlet[k]*B/m.volume.front();m.cr.back()[k]-=outlet[k]*B/m.volume.back();}
        for(size_t i=0;i<n;++i)for(int k:{0,3,4,5})if(m.cr[i][k]<0)sub=std::min(sub,.9*m.channel[i][k]/(-m.cr[i][k]));
        if(!(sub>1e-8)||!std::isfinite(sub))throw std::runtime_error("channel timestep collapsed");
        m.external.water+=sub*B*(inlet[0]-outlet[0]);
        for(int k=0;k<3;++k){m.external.sediment[k]+=sub*B*(inlet[3+k]-outlet[3+k]);m.bank[k]=std::max(0.,m.bank[k]-sub*recycled_rate[k]);m.bank_injected+=sub*recycled_rate[k];}
        for(size_t i=0;i<n;++i){for(int k=0;k<6;++k)m.channel[i][k]+=sub*m.cr[i][k];check_state(m.channel[i],m,m.volume[i],"channel");resistance(m.channel[i],m.p.channel_chezy,sub);}
        elapsed+=sub;++m.channel_steps;
    }
}
inline void floodplain_advance(Model& m,double dt) {
    double area=m.p.dx*m.p.dx;
    // Summing all storage rates cancels internal fluxes. Add the difference
    // from lateral channel exchange to identify only external FP boundary flux.
    State total{};for(int j=m.lo_y;j<m.hi_y;++j)for(int i=j*m.nx+m.lo_x;i<j*m.nx+m.hi_x;++i)if(m.mapping[i].a<0)for(int k:{0,3,4,5})total[k]+=m.rate[i][k]*area;
    for(size_t i=0;i<m.channel.size();++i)for(int k:{0,3,4,5})total[k]+=m.exchange[i][k]*m.volume[i];
    m.external.water+=dt*total[0];for(int k=0;k<3;++k)m.external.sediment[k]+=dt*total[3+k];
    for(int j=m.lo_y;j<m.hi_y;++j)for(int i=j*m.nx+m.lo_x;i<j*m.nx+m.hi_x;++i)if(m.mapping[i].a<0) {
        if(m.q[i][0]==0&&m.rate[i][0]==0)continue;
        for(int k=0;k<6;++k)m.q[i][k]+=dt*m.rate[i][k];
        check_state(m.q[i],m,area,"floodplain");
        resistance(m.q[i],m.p.floodplain_chezy,dt);
        double tau=1000*g*std::pow(norm_u(m.q[i])/m.p.floodplain_chezy,2);
        auto d=deposit(m.q[i],m.ws,tau,m.p.tau_critical,dt);
        double dz=deposit_thickness(d,m.p.rho_s,m.p.porosity);m.z[i]+=dz;m.deposition[i]+=dz;
        m.deposited_mass+=std::accumulate(d.begin(),d.end(),0.)*area;
    }
    m.clock+=dt;++m.steps;
}
}
namespace ridge {
struct Metrics {double alpha=0,inundated_fraction=0,mean_water=0,beta=0,ridge=0,channel_depth=0,sinuosity=0;};
inline Metrics metrics(const Model& m) {
    Metrics r;double totalh=0,count=0,wetinterface=0,interface=0,bankz=0,banklength=0,bedz=0;
    double wetcut=1e-3; // diagnostic threshold only, never used to clip simulation water.
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a<0){totalh+=m.q[i][0];++count;}
    for(auto f:m.faces)if(f.b>=0&&((m.mapping[f.a].a>=0)!=(m.mapping[f.b].a>=0))) {
        int channel=m.mapping[f.a].a>=0?f.a:f.b,fp=channel==f.a?f.b:f.a;
        ++interface;if(m.q[fp][0]>wetcut&&m.q[channel][0]+m.z[channel]-m.z[fp]>wetcut)++wetinterface;
        bankz+=m.z[fp]-m.initial_z[fp];banklength+=1;
        bedz+=m.z[channel]-m.initial_z[fp];
    }
    r.mean_water=count?totalh/count:0;r.inundated_fraction=interface?wetinterface/interface:0;
    r.alpha=r.inundated_fraction>0?r.mean_water/r.inundated_fraction:std::numeric_limits<double>::quiet_NaN();
    // The paper does not specify the ridge estimator. Use the central 80% reach,
    // maximum cross-valley longitudinal-mean relief, and outermost 10% distal bands.
    std::vector<double> transverse(m.ny,0);std::vector<int> samples(m.ny,0);
    for(int j=0;j<m.ny;++j)for(int i=m.nx/10;i<m.nx-m.nx/10;++i){int id=j*m.nx+i;if(m.mapping[id].a<0){transverse[j]+=m.z[id]-m.initial_z[id];++samples[j];}}
    double distal=0,nd=0,crest=-1e99;
    for(int j=0;j<m.ny;++j)if(samples[j]){transverse[j]/=samples[j];crest=std::max(crest,transverse[j]);if(j<m.ny/10||j>=m.ny-m.ny/10){distal+=transverse[j];++nd;}}
    r.ridge=crest-(nd?distal/nd:0);r.channel_depth=banklength?(bankz-bedz)/banklength:m.p.initial_depth;
    r.beta=r.channel_depth>0?r.ridge/r.channel_depth:std::numeric_limits<double>::quiet_NaN();
    r.sinuosity=m.s.back()/m.p.length;return r;
}
inline void remap_after_flood(Model& m,int flood) {
    synchronize(m);auto oldmapping=m.mapping;auto oldchannel=m.channel;auto oldvolume=m.volume;auto olds=m.s;
    double h=metrics(m).channel_depth;
    if(!(h>0))throw std::runtime_error("prescribed channel bed has reached or exceeded mean bank height; migration depth is undefined");
    if(m.p.migration){auto result=migrate(m.line,m.p.channel_width,m.p.migration_scale,m.p.E,h,g/(m.p.channel_chezy*m.p.channel_chezy));m.cutoffs+=result.cutoffs;}
    for(auto p:m.line)if(p.x<0||p.x>m.p.length||p.y<.5*m.p.channel_width||p.y>m.p.width-.5*m.p.channel_width)
        throw std::runtime_error("channel migrated outside domain; expand domain, do not clip centerline");
    // Migration/cutting precedes the prescribed bed increment (DR1).
    geometry(m,flood-1);double area=m.p.dx*m.p.dx;
    // The sampled raster footprint need not equal the exact rectangular 1-D
    // control area. Partition each old donor inventory over its entire raster
    // support before transferring abandoned cells. The same nonnegative
    // geometrical weights apply to water, momentum, and every sediment class.
    std::vector<double> support(oldchannel.size(),0),retained(oldchannel.size(),0);
    for(size_t i=0;i<oldmapping.size();++i)if(oldmapping[i].a>=0) {
        auto mp=oldmapping[i];int nodes[2]={mp.a,mp.b};double weights[2]={1-mp.w,mp.w};
        for(int side=0;side<2;++side) {
            support[nodes[side]]+=area*weights[side];
            if(m.mapping[i].a>=0)retained[nodes[side]]+=area*weights[side];
        }
    }
    size_t n=m.line.size();std::vector<State> incoming(n);
    for(size_t i=0;i<m.q.size();++i){
        if(oldmapping[i].a>=0&&m.mapping[i].a>=0){
            auto mp=m.mapping[i];double newz=(1-mp.w)*m.zc[mp.a]+mp.w*m.zc[mp.b];
            m.bed_external_mass+=(newz-m.z[i])*area*m.p.rho_s*(1-m.p.porosity);
        } else if(oldmapping[i].a>=0&&m.mapping[i].a<0){
            auto mp=oldmapping[i];int nodes[2]={mp.a,mp.b};double weights[2]={1-mp.w,mp.w};State r{};
            for(int side=0;side<2;++side) {
                int j=nodes[side];
                if(support[j]>0)for(int k=0;k<6;++k)r[k]+=weights[side]*oldvolume[j]/support[j]*oldchannel[j][k];
            }
            double stream=r[1];r[1]=stream*mp.tx;r[2]=stream*mp.ty;m.q[i]=r;
            check_state(m.q[i],m,area,"abandoned channel cell");
        } else if(oldmapping[i].a<0&&m.mapping[i].a>=0) {
            auto mp=m.mapping[i];double newz=(1-mp.w)*m.zc[mp.a]+mp.w*m.zc[mp.b];
            double erosion=std::max(0.,m.z[i]-newz)*area*m.p.rho_s*(1-m.p.porosity);
            for(int k=0;k<3;++k)m.bank[k]+=erosion*m.fractions[k];
            m.bed_external_mass+=std::max(0.,newz-m.z[i])*area*m.p.rho_s*(1-m.p.porosity);
            State r=m.q[i];r[1]=r[1]*mp.tx+r[2]*mp.ty;r[2]=0;
            for(int k=0;k<6;++k){incoming[mp.a][k]+=(1-mp.w)*area*r[k];incoming[mp.b][k]+=mp.w*area*r[k];}
        }
    }
    // Unsupported donors remain in 1-D storage. Resample each remaining donor
    // conservatively in normalized arc length, then add newly captured floodplain
    // inventories locally. No component-dependent global rescaling is used.
    for(size_t j=0;j<oldchannel.size();++j) {
        double fraction=support[j]>0?retained[j]/support[j]:1;
        for(double& x:oldchannel[j])x*=fraction;
    }
    m.channel.assign(n,State{});
    std::vector<double> oldedges(oldchannel.size()+1,0),newedges(n+1,0);
    for(size_t i=0;i<oldchannel.size();++i)oldedges[i+1]=oldedges[i]+oldvolume[i]/(m.p.channel_width*olds.back());
    for(size_t i=0;i<n;++i)newedges[i+1]=newedges[i]+m.volume[i]/(m.p.channel_width*m.s.back());
    oldedges.back()=newedges.back()=1;
    size_t a=0;
    for(size_t i=0;i<n;++i){while(a+1<oldchannel.size()&&oldedges[a+1]<=newedges[i])++a;
        for(size_t j=a;j<oldchannel.size()&&oldedges[j]<newedges[i+1];++j){double overlap=std::max(0.,std::min(newedges[i+1],oldedges[j+1])-std::max(newedges[i],oldedges[j]));
            double fraction=overlap/(oldedges[j+1]-oldedges[j]);
            for(int k=0;k<6;++k)m.channel[i][k]+=fraction*oldvolume[j]/m.volume[i]*oldchannel[j][k];}
    }
    for(size_t i=0;i<n;++i)for(int k=0;k<6;++k)m.channel[i][k]+=incoming[i][k]/m.volume[i];
    for(size_t i=0;i<n;++i)check_state(m.channel[i],m,m.volume[i],"remapped channel");
    for(auto& z:m.zc)z+=m.p.A;
    for(const auto& mp:m.mapping)if(mp.a>=0)
        m.bed_external_mass+=m.p.A*area*m.p.rho_s*(1-m.p.porosity);
    synchronize(m);
}
inline double total_sediment_inventory(const Model& m) {
    auto a=storage(m);double total=std::accumulate(a.sediment.begin(),a.sediment.end(),0.)+std::accumulate(m.bank.begin(),m.bank.end(),0.);
    double density=m.p.rho_s*(1-m.p.porosity)*m.p.dx*m.p.dx;
    for(size_t i=0;i<m.z.size();++i)total+=(m.z[i]-m.initial_z[i])*density;
    return total;
}
inline void snapshot(const Model& m,const std::string& out,int flood,const std::string& prefix="") {
    char name[64];std::snprintf(name,sizeof(name),"fields_%04d.bin",flood);
    std::ofstream file(out+"/"+prefix+name,std::ios::binary);int header[4]={m.nx,m.ny,int(m.line.size()),flood};
    file.write(reinterpret_cast<char*>(header),sizeof(header));double scalars[3]={m.p.dx,m.clock,m.p.slope};file.write(reinterpret_cast<char*>(scalars),sizeof(scalars));
    for(size_t i=0;i<m.q.size();++i){float x[4]={float(m.z[i]),float(m.q[i][0]),float(m.deposition[i]),float(m.mapping[i].a>=0)};file.write(reinterpret_cast<char*>(x),sizeof(x));}
    std::snprintf(name,sizeof(name),"channel_%04d.csv",flood);std::ofstream c(out+"/"+prefix+name);c<<std::setprecision(12)<<"x,y,bed,water_depth,velocity,control_area\n";
    for(size_t i=0;i<m.line.size();++i)c<<m.line[i].x<<','<<m.line[i].y<<','<<m.zc[i]<<','<<m.channel[i][0]<<','<<m.channel[i][1]/std::max(m.channel[i][0],1e-30)<<','<<m.volume[i]<<'\n';
    if(!file||!c)throw std::runtime_error("snapshot write failed");
}
inline std::string parameter_signature(const Parameters& p) {
    std::ostringstream s;s<<std::setprecision(17)<<"ridge-checkpoint-v2 ";
    for(double x:{p.length,p.width,p.dx,p.channel_width,p.slope,p.initial_depth,p.duration,p.qmin,p.qmax,
                  p.channel_chezy,p.floodplain_chezy,p.A,p.C,p.E,p.migration_scale,p.perturbation,p.cfl,
                  p.max_dt,p.porosity,p.rho_s,p.tau_critical,p.sand_d,p.silt_ws,p.clay_d,
                  p.diffusion_scale,p.concentration_scale})s<<x<<' ';
    s<<p.seed<<' '<<p.run<<' '<<p.fine<<' '<<p.migration<<' '<<p.viscosity;
    return s.str();
}
inline void checkpoint(const Model& m,const std::string& out,int flood) {
    std::ofstream f(out+"/checkpoint.tmp",std::ios::binary);
    auto put=[&](const auto& x){f.write(reinterpret_cast<const char*>(&x),sizeof(x));};
    auto signature=parameter_signature(m.p);size_t length=signature.size();put(length);f.write(signature.data(),length);
    put(flood);put(m.clock);put(m.steps);put(m.channel_steps);put(m.cutoffs);put(m.external);put(m.bank);put(m.deposited_mass);put(m.bed_external_mass);put(m.bank_injected);put(m.water_correction);put(m.mass_correction);
    size_t n=m.line.size();put(n);for(auto x:m.line)put(x);for(auto x:m.channel)put(x);for(auto x:m.z)put(x);for(auto x:m.q)put(x);
    f.close();if(!f)throw std::runtime_error("checkpoint write failed");std::filesystem::rename(out+"/checkpoint.tmp",out+"/checkpoint.bin");
}
inline int restart(Model& m,const std::string& out) {
    std::ifstream f(out+"/checkpoint.bin",std::ios::binary);if(!f)throw std::runtime_error("checkpoint missing");
    auto get=[&](auto& x){f.read(reinterpret_cast<char*>(&x),sizeof(x));};int flood;
    size_t length;get(length);if(length>4096)throw std::runtime_error("unrecognized checkpoint format");
    std::string signature(length,0);f.read(&signature[0],length);
    if(signature!=parameter_signature(m.p))throw std::runtime_error("checkpoint parameters do not match requested run");
    get(flood);get(m.clock);get(m.steps);get(m.channel_steps);get(m.cutoffs);get(m.external);get(m.bank);get(m.deposited_mass);get(m.bed_external_mass);get(m.bank_injected);get(m.water_correction);get(m.mass_correction);
    size_t n;get(n);if(n>100000||n<2)throw std::runtime_error("invalid checkpoint node count");m.line.resize(n);m.channel.resize(n);
    for(auto& x:m.line)get(x);
    geometry(m,flood);
    for(auto& x:m.channel)get(x);
    for(auto& x:m.z)get(x);
    for(auto& x:m.q)get(x);
    if(!f)throw std::runtime_error("truncated checkpoint");
    synchronize(m);return flood;
}
}
