#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace ridge {
constexpr double g=9.81;
// SI: h [m], momenta hu,hv [m^2/s], suspended masses h*c [kg/m^2].
using State=std::array<double,6>;
template<int components=6>
inline State physical_flux(const State& q, int axis) {
    State f{};
    if(q[0]<=0) return f;
    double u=q[1+axis]/q[0];
    for(int k=0;k<components;++k) f[k]=u*q[k];
    f[1+axis]+=0.5*g*q[0]*q[0];
    return f;
}
template<int components=6>
inline State reconstruct(const State& q,double z,double face_z) {
    State r{};
    r[0]=std::max(0.,q[0]+z-face_z);
    if(q[0]>0) for(int k=1;k<components;++k) r[k]=q[k]*r[0]/q[0];
    return r;
}
struct Face {State left,right;};
// Hydrostatic reconstruction with HLL flux; pressure corrections are side-specific.
// left/right are fluxes directed from left to right, used to update each side.
template<int components=6>
inline Face face_flux(const State& l,const State& r,double zl,double zr,int axis) {
    static_assert(components==3||components==6,"use hydraulic or complete state flux");
    double z=std::max(zl,zr);
    State a=reconstruct<components>(l,zl,z), b=reconstruct<components>(r,zr,z);
    State fa=physical_flux<components>(a,axis),fb=physical_flux<components>(b,axis),f{};
    double ua=a[0]>0?a[1+axis]/a[0]:0,ub=b[0]>0?b[1+axis]/b[0]:0;
    double ca=std::sqrt(g*a[0]),cb=std::sqrt(g*b[0]);
    double sl=std::min({0.,ua-ca,ub-cb}),sr=std::max({0.,ua+ca,ub+cb});
    if(sr>sl) for(int k=0;k<components;++k)
        f[k]=(sr*fa[k]-sl*fb[k]+sl*sr*(b[k]-a[k]))/(sr-sl);
    Face out{f,f};
    out.left[1+axis]+=0.5*g*(l[0]*l[0]-a[0]*a[0]);
    out.right[1+axis]+=0.5*g*(r[0]*r[0]-b[0]*b[0]);
    return out;
}
// Exact settling substep at fixed water depth, well-mixed concentration.
// Return deposited mass [kg/m^2]; bed conversion is handled by morphology.
inline double settle(State& q,int grain,double ws,double dt) {
    if(ws<0 || dt<0) throw std::invalid_argument("negative settling input");
    if(q[0]<=0) {double m=q[3+grain];q[3+grain]=0;return m;}
    double loss=-q[3+grain]*std::expm1(-ws*dt/q[0]);
    q[3+grain]-=loss;
    return loss;
}
}
