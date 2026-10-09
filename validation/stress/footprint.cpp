#include "model.hpp"
using namespace ridge;
struct Case {std::string name;std::vector<Point> line;double shift=0;bool cutoff=false;};
int main(){
 std::filesystem::create_directories("validation/stress/footprint");
 std::ofstream report("validation/stress/footprint/nodes.csv"),cases("validation/stress/footprint/cases.csv");report<<std::setprecision(17);cases<<std::setprecision(17);
 report<<"case,dx,node,x,y,control_area,abandoned_debit_area,ratio\n";
 cases<<"case,dx,old_nodes,new_nodes,cutoffs,old_channel_area,old_raster_area,new_channel_area,abandoned_area,max_node_ratio,max_node,uniform_target_water,localized_class_target,remap_result\n";
 std::vector<Point> sine;for(int i=0;i<=32;++i)sine.push_back({250.*i,4000+500*std::sin(2*std::acos(-1.)*i/32)});
 std::vector<Case> tests={{"neck",{{0,4000},{2500,4000},{3500,4000},{3500,6000},{1500,6000},{1500,4250},{4000,4250},{8000,4000}},0,true},
 {"oblique_shift",{{0,2500},{8000,4100}},1000,false},{"sine_halfwidth",sine,250,false},{"sine_width",sine,500,false}};
 for(double dx:{125.,250.,500.})for(const auto& test:tests) {
  Parameters p;p.length=p.width=8000;p.dx=dx;p.perturbation=0;p.migration=false;p.C=0;
  Model old(p);old.line=test.line;resample(old.line,p.channel_width/2);geometry(old,0);old.channel.assign(old.line.size(),State{4.,2.,0.,0.,0.,0.});synchronize(old);
  Model next=old;int cuts=0;
  if(test.cutoff){auto cut=neck_cutoffs(next.line,p.channel_width);cuts=cut.cutoffs;resample(next.line,p.channel_width/2);}else for(auto& point:next.line)point.y+=test.shift;
  geometry(next,0);
  std::vector<double> debit(old.line.size(),0.);double area=dx*dx,abandoned=0,old_raster=0;
  for(size_t i=0;i<old.mapping.size();++i)if(old.mapping[i].a>=0){old_raster+=area;if(next.mapping[i].a<0){auto map=old.mapping[i];debit[map.a]+=(1-map.w)*area;debit[map.b]+=map.w*area;abandoned+=area;}}
  int worst=0;for(size_t i=0;i<debit.size();++i){if(debit[i]/old.volume[i]>debit[worst]/old.volume[worst])worst=i;report<<test.name<<','<<dx<<','<<i<<','<<old.line[i].x<<','<<old.line[i].y<<','<<old.volume[i]<<','<<debit[i]<<','<<debit[i]/old.volume[i]<<'\n';}
  double oldarea=std::accumulate(old.volume.begin(),old.volume.end(),0.);
  Model trial=old;trial.channel[worst][3]=1.;synchronize(trial);trial.line=next.line;
  std::string result="pass";try{remap_after_flood(trial,1);}catch(const std::exception& e){result=e.what();}
  cases<<test.name<<','<<dx<<','<<old.line.size()<<','<<next.line.size()<<','<<cuts<<','<<oldarea<<','<<old_raster<<','<<std::accumulate(next.volume.begin(),next.volume.end(),0.)<<','<<abandoned<<','<<debit[worst]/old.volume[worst]<<','<<worst<<','<<4*(oldarea-abandoned)<<','<<old.volume[worst]-debit[worst]<<','<<result<<'\n';cases.flush();
  std::cout<<test.name<<" dx="<<dx<<" max_node_ratio="<<debit[worst]/old.volume[worst]<<" localized_target="<<old.volume[worst]-debit[worst]<<" uniform_water_target="<<4*(oldarea-abandoned)<<" result="<<result<<std::endl;
 }
}
