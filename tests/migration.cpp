#include "migration.hpp"
#include <iostream>
#include <random>
#include <string>

using namespace ridge;
static void require(bool condition,const std::string& message) {
    if(!condition) throw std::runtime_error(message);
}
static bool equal(const std::vector<Point>& a,const std::vector<Point>& b,double tol=0) {
    if(a.size()!=b.size()) return false;
    for(std::size_t i=0;i<a.size();++i) if(distance(a[i],b[i])>tol) return false;
    return true;
}
static double sine_error(int n) {
    double alpha=.002,k=.0017,length=5000;
    std::vector<double> s(n+1),f(n+1);
    for(int i=0;i<=n;++i) { s[i]=length*i/n;f[i]=std::sin(k*s[i]); }
    auto u=exponential_upstream_mean(s,f,alpha);
    double error=0;
    for(int i=1;i<=n;++i) {
        double exact=alpha*(alpha*std::sin(k*s[i])-k*std::cos(k*s[i])+k*std::exp(-alpha*s[i]))/
            ((alpha*alpha+k*k)*(-std::expm1(-alpha*s[i])));
        error=std::max(error,std::abs(u[i]-exact));
    }
    return error;
}
int main() {
    try {
        std::vector<Point> line;
        for(int i=0;i<=40;++i) line.push_back({double(i)*250,0});
        auto original=line;
        auto stats=migrate(line,500,400,1,8);
        require(equal(line,original),"straight river moved");
        require(stats.cutoffs==0&&stats.max_displacement==0,"straight migration nonzero");
        std::vector<Point> circle;
        const double radius=1500;
        for(int i=0;i<=40;++i) circle.push_back({radius*std::cos(.02*i),radius*std::sin(.02*i)});
        auto c=curvature(circle);double curvature_error=0;
        for(std::size_t i=1;i+1<c.size();++i) curvature_error=std::max(curvature_error,std::abs(c[i]-1/radius));
        require(curvature_error<1e-14,"circle curvature incorrect");
        auto before=circle;migrate(circle,500,400,0,8);
        require(equal(circle,before),"zero erodibility changed centerline");
        migrate(circle,500,0,1,8);
        require(equal(circle,before),"zero migration coefficient changed centerline");

        std::vector<double> s={0,1,10,250,800},constant(s.size(),2.4),affine;
        for(double v:s) affine.push_back(3+.25*v);
        for(double a:{0.,1e-12,.003,1.}) {
            auto mean=exponential_upstream_mean(s,constant,a);
            for(double v:mean) require(std::abs(v-2.4)<1e-12,"constant upstream mean changed");
        }
        auto mean=exponential_upstream_mean(s,affine,.003);
        for(std::size_t i=1;i<s.size();++i) {
            double exact=3+.25*(s[i]-1/.003+s[i]/std::expm1(.003*s[i]));
            require(std::abs(mean[i]-exact)<1e-10,"affine upstream integral incorrect");
        }
        double coarse=sine_error(100),fine=sine_error(200);
        require(coarse/fine>3.9&&coarse/fine<4.1,"upstream integral did not converge quadratically");

        std::vector<Point> loop={{-30,0},{0,0},{30,0},{30,30},{0,30},{0,5},{-30,5}};
        auto ends=loop;double old_length=arc_length(loop).back();
        auto cut=neck_cutoffs(loop,10);
        require(cut.cutoffs>0,"contacting limbs did not cut off");
        require(distance(loop.front(),ends.front())==0&&distance(loop.back(),ends.back())==0,"cutoff moved an endpoint");
        double length_error=std::abs(old_length-arc_length(loop).back()-cut.removed_length);
        require(length_error<1e-12,"cutoff removed length budget incorrect");
        require(neck_cutoffs(loop,10).cutoffs==0,"cutoff was not idempotent");
        std::vector<Point> crossing={{-20,0},{20,20},{-20,20},{20,0}};
        auto intersection=neck_cutoffs(crossing,2);
        require(intersection.cutoffs==1,"segment intersection was missed");
        require(closest_segments({0,0},{1,0},{2,2},{2,4}).distance==std::sqrt(5.),"segment distance incorrect");
        std::vector<Point> duplicates={{0,0},{0,0},{1000,0},{1000,0}};
        resample(duplicates,200);
        require(duplicates.size()==6,"duplicate-node resampling failed");
        for(std::size_t i=1;i<duplicates.size();++i)
            require(distance(duplicates[i],duplicates[i-1])==200,"straight resampling spacing wrong");

        std::vector<Point> channel;
        for(int i=0;i<=144;++i) channel.push_back({250.*i,5*std::sin(250.*i*.0009)});
        auto reflected=channel;
        for(auto& p:reflected) p.y=-p.y;
        migrate(channel,500,400,1,8);migrate(reflected,500,400,1,8);
        for(auto& p:reflected) p.y=-p.y;
        require(equal(channel,reflected,1e-10),"reflection symmetry violated");
        // A long noisy initial channel develops tight bends and cutoffs. A lone
        // sinusoid can leave the finite domain without exercising mesh crowding.
        channel.clear();
        std::mt19937 generator(742);std::normal_distribution<double> noise(0,5);
        for(int i=0;i<=288;++i) channel.push_back({250.*i,i==0||i==288?0:noise(generator)});
        Point inlet=channel.front(),outlet=channel.back();int total_cutoffs=0;
        for(int flood=0;flood<580;++flood) {
            auto step=migrate(channel,500,400,1,8);
            total_cutoffs+=step.cutoffs;
            for(auto p:channel) require(std::isfinite(p.x+p.y),"migration became nonfinite");
            require(distance(channel.front(),inlet)==0&&distance(channel.back(),outlet)==0,"fixed endpoint moved");
            require(step.max_displacement>=0,"negative migration distance");
        }
        require(total_cutoffs>0,"long migration test never exercised cutoffs");
        std::cout.precision(12);
        std::cout<<"circle_curvature_max_error "<<curvature_error<<"\n";
        std::cout<<"upstream_integral_errors "<<coarse<<" "<<fine<<" ratio "<<coarse/fine<<"\n";
        std::cout<<"cutoff_length_budget_error "<<length_error<<"\n";
        std::cout<<"migration_580_floods_sinuosity "<<arc_length(channel).back()/distance(inlet,outlet)<<"\n";
        std::cout<<"migration_580_floods_cutoffs "<<total_cutoffs<<"\n";
        std::cout<<"PASS migration limits, exact quadrature, convergence, cutoff geometry, symmetry, finite evolution\n";
    } catch(const std::exception& e) { std::cerr<<"FAIL "<<e.what()<<"\n";return 1; }
}
