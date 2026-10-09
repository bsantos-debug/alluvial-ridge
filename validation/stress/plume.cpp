#include "model.hpp"
using namespace ridge;
int main(){
 std::filesystem::create_directories("validation/stress/plume");
 std::ofstream out("validation/stress/plume/results.csv");out<<std::setprecision(17)<<"shape,dx,sigma,transport_seconds,cutoffs,node,maximum_abs_curvature,water_before,water_target,class_before,class_debit,class_target,min_class_state,result\n";
 std::vector<Point> circle{{0,2800}};double pi=std::acos(-1.),delta=.1;
 for(int i=0;i<=40;++i){double theta=-pi/2+delta+(2*pi-2*delta)*i/40;circle.push_back({4000+1500*std::cos(theta),4500+1500*std::sin(theta)});}circle.push_back({8000,3300});
 std::vector<std::pair<std::string,std::vector<Point>>> shapes={{"rounded_loop",circle},{"polygonal_loop",{{0,4000},{2500,4000},{3500,4000},{3500,6000},{1500,6000},{1500,4250},{4000,4250},{8000,4000}}}};
 for(const auto& shape:shapes)for(double dx:{125.,250.}) {
  Parameters p;p.length=p.width=8000;p.dx=dx;p.duration=1000;p.qmin=p.qmax=2500;p.C=0;p.migration=true;p.migration_scale=.001;p.perturbation=0;
  Model old(p);old.line=shape.second;resample(old.line,p.channel_width/2);geometry(old,0);old.channel.assign(old.line.size(),State{4.,2.,0.,0.,0.,0.});synchronize(old);
  Model next=old;auto stats=migrate(next.line,p.channel_width,p.migration_scale,p.E,metrics(old).channel_depth,g/(p.channel_chezy*p.channel_chezy));geometry(next,0);
  std::vector<double> debit(old.line.size());double abandoned_water=0,area=p.dx*p.dx;
  for(size_t i=0;i<old.q.size();++i)if(old.mapping[i].a>=0&&next.mapping[i].a<0){auto map=old.mapping[i];debit[map.a]+=(1-map.w)*area;debit[map.b]+=map.w*area;abandoned_water+=old.q[i][0]*area;}
  double curv=0;for(double c:curvature(old.line))curv=std::max(curv,std::abs(c));
  for(double sigma:{0.,125.,250.,500.,1000.}) {
   int center=0;double worst=1e100;
   for(size_t j=0;j<old.channel.size();++j){double target=0;for(size_t i=0;i<old.channel.size();++i){double mass=1e-8+(sigma>0?std::exp(-.5*std::pow((old.s[i]-old.s[j])/sigma,2)):double(i==j));target+=mass*(old.volume[i]-debit[i]);}if(target<worst){worst=target;center=j;}}
   for(double seconds:{0.,120.}) {
    Model m=old;for(size_t i=0;i<m.channel.size();++i)m.channel[i][3]=1e-8+(sigma>0?std::exp(-.5*std::pow((m.s[i]-m.s[center])/sigma,2)):double(int(i)==center));synchronize(m);
    double time=0;while(time<seconds-1e-9){double dt=std::min(floodplain_rates(m),seconds-time);channel_advance(m,time,dt,{});floodplain_advance(m,dt);time+=dt;}synchronize(m);
    auto initial=storage(m);Model future=m;auto cut=migrate(future.line,p.channel_width,p.migration_scale,p.E,metrics(m).channel_depth,g/(p.channel_chezy*p.channel_chezy));geometry(future,0);
    double demand=0,water=0,minmass=1e100;for(const auto& q:m.channel)minmass=std::min(minmass,q[3]);
    for(size_t i=0;i<m.q.size();++i)if(m.mapping[i].a>=0&&future.mapping[i].a<0){demand+=m.q[i][3]*area;water+=m.q[i][0]*area;}
    double water_channel=0,mass_channel=0;for(size_t i=0;i<m.channel.size();++i){water_channel+=m.channel[i][0]*m.volume[i];mass_channel+=m.channel[i][3]*m.volume[i];}
    std::string result="pass";try{remap_after_flood(m,1);}catch(const std::exception& e){result=e.what();}
    out<<shape.first<<','<<dx<<','<<sigma<<','<<seconds<<','<<cut.cutoffs<<','<<center<<','<<curv<<','<<initial.water<<','<<water_channel-water<<','<<mass_channel<<','<<demand<<','<<mass_channel-demand<<','<<minmass<<','<<result<<'\n';out.flush();
    std::cout<<shape.first<<" dx="<<dx<<" sigma="<<sigma<<" transport="<<seconds<<" class_target="<<mass_channel-demand<<" water_target="<<water_channel-water<<" result="<<result<<std::endl;
   }
  }
  (void)stats;
 }
}
