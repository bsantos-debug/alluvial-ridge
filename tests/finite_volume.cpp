#include "finite_volume.hpp"
#include <iostream>
#include <vector>
#include <numeric>
using namespace ridge;
void require(bool ok,const char* what) {if(!ok) throw std::runtime_error(what);}
int main() {
    // A stepped bed intersects a constant free surface, including a dry island.
    const int n=80;double dx=10,dt=.05;
    std::vector<double> z(n);
    std::vector<State> q(n),dq(n);
    for(int i=0;i<n;++i) {z[i]=i>28&&i<51?3:0.3*std::sin(i*.3);q[i][0]=std::max(0.,2-z[i]);}
    auto initial=q;
    for(int t=0;t<1000;++t) {
        for(auto& a:dq)a={};
        for(int i=0;i<n-1;++i) {
            auto f=face_flux(q[i],q[i+1],z[i],z[i+1],0);
            for(int k=0;k<6;++k){dq[i][k]-=f.left[k]*dt/dx;dq[i+1][k]+=f.right[k]*dt/dx;}
        }
        // Reflecting end faces.
        State l=q.front(),r=q.back();l[1]*=-1;r[1]*=-1;
        auto fl=face_flux(l,q.front(),z.front(),z.front(),0);
        auto fr=face_flux(q.back(),r,z.back(),z.back(),0);
        for(int k=0;k<6;++k){dq.front()[k]+=fl.right[k]*dt/dx;dq.back()[k]-=fr.left[k]*dt/dx;}
        for(int i=0;i<n;++i)for(int k=0;k<6;++k)q[i][k]+=dq[i][k];
    }
    double err=0;for(int i=0;i<n;++i)for(int k=0;k<6;++k)err=std::max(err,std::abs(q[i][k]-initial[i][k]));
    require(err<1e-11,"lake at rest failed");
    std::cout<<"lake_at_rest_max_error "<<err<<'\n';
    // Shared face applied between unequal-volume channel/floodplain stores.
    State a{4,3,0,2,1,.5},b{1,0,0,.1,.2,.3};
    auto f=face_flux(a,b,0,0,0);double va=500*250,vb=250*250;
    for(int k: {0,3,4,5}) {
        double before=va*a[k]+vb*b[k];
        a[k]-=f.left[k]*.1*250/va;b[k]+=f.right[k]*.1*250/vb;
        require(std::abs(va*a[k]+vb*b[k]-before)<1e-9,"exchange conservation failed");
    }
    std::cout<<"shared_face_water_sediment_conservation pass\n";
    State s{2,0,0,3,0,0};double d=settle(s,0,.001,1000);
    require(std::abs(s[3]-3*std::exp(-.5))<1e-13,"settling exponential failed");
    require(std::abs(s[3]+d-3)<1e-13,"settling mass failed");
    std::cout<<"analytical_settling_and_mass_conservation pass\n";
    auto fzero=face_flux(State{},State{},0,0,0);
    for(auto x:fzero.left)require(x==0,"dry flux failed");
    std::cout<<"dry_interface pass\n";
}
