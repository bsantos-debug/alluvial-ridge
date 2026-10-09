#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <vector>

namespace ridge {

struct Point { double x=0, y=0; };
inline Point operator+(Point a,Point b) { return {a.x+b.x,a.y+b.y}; }
inline Point operator-(Point a,Point b) { return {a.x-b.x,a.y-b.y}; }
inline Point operator*(Point a,double b) { return {a.x*b,a.y*b}; }
inline double dot(Point a,Point b) { return a.x*b.x+a.y*b.y; }
inline double cross(Point a,Point b) { return a.x*b.y-a.y*b.x; }
inline double distance(Point a,Point b) { return std::hypot(a.x-b.x,a.y-b.y); }

inline std::vector<double> arc_length(const std::vector<Point>& p) {
    std::vector<double> s(p.size(),0);
    for(std::size_t i=0;i<p.size();++i) {
        if(!std::isfinite(p[i].x)||!std::isfinite(p[i].y))
            throw std::invalid_argument("nonfinite centerline coordinate");
        if(i) s[i]=s[i-1]+distance(p[i],p[i-1]);
    }
    return s;
}

// Signed inverse circumradius [1/m], positive for a counterclockwise turn.
// End curvatures are zero: no curved reach is prescribed beyond the endpoints.
inline std::vector<double> curvature(const std::vector<Point>& p) {
    std::vector<double> c(p.size(),0);
    for(std::size_t i=1;i+1<p.size();++i) {
        Point a=p[i]-p[i-1],b=p[i+1]-p[i];
        double d=std::hypot(a.x,a.y)*std::hypot(b.x,b.y)*distance(p[i+1],p[i-1]);
        if(d>0) c[i]=2*cross(a,b)/d;
    }
    return c;
}

// Integral from the inlet to s, normalized by the integral of exp[-alpha*(s-u)].
// Piecewise-linear nominal values are integrated exactly in O(number of nodes).
inline std::vector<double> exponential_upstream_mean(
        const std::vector<double>& s,const std::vector<double>& nominal,double alpha) {
    if(s.size()!=nominal.size()||!std::isfinite(alpha)||alpha<0)
        throw std::invalid_argument("invalid upstream convolution");
    std::vector<double> mean(s.size(),0);
    if(s.empty()) return mean;
    mean[0]=nominal[0];
    double integral=0;
    for(std::size_t i=1;i<s.size();++i) {
        double d=s[i]-s[i-1];
        if(!(d>0)) throw std::invalid_argument("centerline arc length must increase");
        if(alpha==0) {
            integral+=0.5*d*(nominal[i-1]+nominal[i]);
            mean[i]=integral/(s[i]-s[0]);
        } else {
            double t=alpha*d,e=std::exp(-t),a=-std::expm1(-t);
            // b=integral_0^t (v/t)*exp(-v) dv; expansion avoids cancellation.
            double b=t<1e-3?t*(0.5+t*(-1.0/3+t*(0.125-t/30))):(a-t*e)/t;
            integral=e*integral+a*nominal[i]-b*(nominal[i]-nominal[i-1]);
            mean[i]=integral/(-std::expm1(-alpha*(s[i]-s[0])));
        }
    }
    return mean;
}

// Piecewise-linear interpolation at equal arc-length intervals, retaining endpoints.
inline void resample(std::vector<Point>& p,double maximum_spacing) {
    if(!(maximum_spacing>0)||!std::isfinite(maximum_spacing))
        throw std::invalid_argument("invalid centerline spacing");
    if(p.size()<2) return;
    auto s=arc_length(p);
    if(s.back()==0) { p.resize(1); return; }
    std::size_t n=std::max<std::size_t>(1,std::ceil(s.back()/maximum_spacing));
    std::vector<Point> result;result.reserve(n+1);result.push_back(p.front());
    std::size_t j=1;
    for(std::size_t i=1;i<n;++i) {
        double target=s.back()*i/n;
        while(j+1<s.size()&&s[j]<target) ++j;
        while(j+1<s.size()&&s[j]==s[j-1]) ++j;
        double t=(target-s[j-1])/(s[j]-s[j-1]);
        result.push_back(p[j-1]+(p[j]-p[j-1])*t);
    }
    result.push_back(p.back());p.swap(result);
}

struct SegmentPair { Point first,second; double t=0,u=0,distance=0; };
inline SegmentPair closest_segments(Point a,Point b,Point c,Point d) {
    Point ab=b-a,cd=d-c;
    double den=cross(ab,cd);
    if(den!=0) {
        double t=cross(c-a,cd)/den,u=cross(c-a,ab)/den;
        if(t>=0&&t<=1&&u>=0&&u<=1) {
            Point hit=a+ab*t;return {hit,hit,t,u,0};
        }
    }
    SegmentPair best;best.distance=std::numeric_limits<double>::infinity();
    auto candidate=[&](double t,double u) {
        Point x=a+ab*t,y=c+cd*u;double r=distance(x,y);
        if(r<best.distance) best={x,y,t,u,r};
    };
    auto fraction=[](Point x,Point v) {
        return dot(v,v)>0?std::max(0.,std::min(1.,dot(x,v)/dot(v,v))):0.;
    };
    candidate(0,fraction(a-c,cd));candidate(1,fraction(b-c,cd));
    candidate(fraction(c-a,ab),0);candidate(fraction(d-a,ab),1);
    return best;
}

struct MigrationStats {
    int cutoffs=0,substeps=0,resamples=0;
    double removed_length=0,max_displacement=0;
};

// Finite-width neck contact: join disjoint limbs separated by less than width.
// Exclude along-channel separations <=2 widths to avoid treating a local bend as a neck.
// This exclusion and the shortest straight connector are explicit geometric assumptions.
inline MigrationStats neck_cutoffs(std::vector<Point>& p,double width) {
    if(!(width>0)||!std::isfinite(width)) throw std::invalid_argument("invalid cutoff width");
    MigrationStats stats;
    bool changed=true;
    while(changed&&p.size()>3) {
        changed=false;
        auto s=arc_length(p);
        for(std::size_t i=0;i+1<p.size()&&!changed;++i) {
            for(std::size_t j=i+2;j+1<p.size();++j) {
                if(s[j+1]-s[i]<=2*width) continue;
                if(std::max(p[i].x,p[i+1].x)+width<std::min(p[j].x,p[j+1].x)||
                   std::max(p[j].x,p[j+1].x)+width<std::min(p[i].x,p[i+1].x)||
                   std::max(p[i].y,p[i+1].y)+width<std::min(p[j].y,p[j+1].y)||
                   std::max(p[j].y,p[j+1].y)+width<std::min(p[i].y,p[i+1].y)) continue;
                auto q=closest_segments(p[i],p[i+1],p[j],p[j+1]);
                double sa=s[i]+q.t*(s[i+1]-s[i]),sb=s[j]+q.u*(s[j+1]-s[j]);
                if(q.distance>=width||sb-sa<=2*width) continue;
                std::vector<Point> kept(p.begin(),p.begin()+i+1);
                auto append=[&](Point a) { if(distance(kept.back(),a)>1e-10) kept.push_back(a); };
                append(q.first);append(q.second);
                for(std::size_t k=j+1;k<p.size();++k) append(p[k]);
                p.swap(kept);++stats.cutoffs;stats.removed_length+=sb-sa-q.distance;
                changed=true;break;
            }
        }
    }
    return stats;
}

// Linear-curvature HK/Ikeda form, as written by Limaye & Lamb (2014), Eqs.4-6.
// migration_scale is k_l [m/flood] per unit W*curvature, not the mean migration.
// It is mandatory because Nicholas et al. (2018) do not specify its dimensional value.
inline MigrationStats migrate(std::vector<Point>& p,double width,double migration_scale,
        double erodibility,double depth,double friction=9.81/(55.*55.),double spacing=0,
        double duration_floods=1,double sinuosity_exponent=0) {
    if(!(width>0)||!(depth>0)||migration_scale<0||erodibility<0||friction<0||
       duration_floods<0||!std::isfinite(width+depth+migration_scale+erodibility+
       friction+duration_floods+sinuosity_exponent+spacing))
        throw std::invalid_argument("invalid migration parameters");
    MigrationStats stats;
    if(p.size()<3||migration_scale==0||erodibility==0||duration_floods==0) return stats;
    if(spacing==0) spacing=width/2;
    if(spacing<0) throw std::invalid_argument("invalid migration spacing");
    auto initial_s=arc_length(p);
    double valley_length=distance(p.front(),p.back());
    if(!(valley_length>0)) throw std::invalid_argument("river endpoints must differ");
    for(std::size_t i=1;i<p.size();++i)
        if(initial_s[i]==initial_s[i-1]) throw std::invalid_argument("duplicate centerline nodes");
    double remaining=duration_floods,total_bound=0;
    while(remaining>0) {
        if(p.size()<3) break;
        auto s=arc_length(p);
        double dmin=s.back(),dmax=0;
        for(std::size_t i=1;i<p.size();++i) {
            dmin=std::min(dmin,s[i]-s[i-1]);
            dmax=std::max(dmax,s[i]-s[i-1]);
        }
        // Lagrangian nodes can converge even while the curve remains regular.
        // Reparameterize distorted meshes instead of allowing a vanishing timestep.
        if(dmin<0.5*spacing||dmax>1.5*spacing) {
            resample(p,spacing);
            if(++stats.resamples>100000) throw std::runtime_error("migration resampling failed");
            continue;
        }
        auto c=curvature(p);
        auto upstream=exponential_upstream_mean(s,c,2*friction/depth);
        double scale=erodibility*migration_scale*width*
            std::pow(s.back()/valley_length,sinuosity_exponent);
        std::vector<Point> velocity(p.size());
        double vmax=0;
        for(std::size_t i=1;i+1<p.size();++i) {
            Point tangent=p[i+1]-p[i-1];double norm=std::hypot(tangent.x,tangent.y);
            double v=scale*(-c[i]+2.5*upstream[i]);
            if(norm>0) velocity[i]={v*tangent.y/norm,-v*tangent.x/norm};
            vmax=std::max(vmax,std::abs(v));
        }
        if(vmax==0) break;
        // Accuracy/stability substeps integrate the entire requested interval; no velocity cap.
        double dt=std::min({remaining,0.2*dmin/vmax,0.2*dmin*dmin/(3.5*scale)});
        if(!(dt>1e-12)) throw std::runtime_error("migration timestep collapsed");
        for(std::size_t i=1;i+1<p.size();++i) p[i]=p[i]+velocity[i]*dt;
        remaining=std::max(0.,remaining-dt);total_bound+=vmax*dt;++stats.substeps;
        if(stats.substeps>100000) throw std::runtime_error("migration substep limit exceeded");
    }
    auto cuts=neck_cutoffs(p,width);
    stats.cutoffs=cuts.cutoffs;stats.removed_length=cuts.removed_length;
    // Sum of substep maxima bounds integrated kinematic movement, excluding regridding.
    stats.max_displacement=total_bound;
    resample(p,spacing);++stats.resamples;
    return stats;
}

} // namespace ridge
