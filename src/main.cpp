#include "model.hpp"
#include <map>
using namespace ridge;
int main(int argc,char** argv) {
    try {
        std::map<std::string,std::string> args;
        for(int i=1;i<argc;i+=2){if(i+1==argc)throw std::runtime_error("options require values");args[argv[i]]=argv[i+1];}
        Parameters p;std::string output="data/run11";bool resume=false;double stop_seconds=1e100;
        if(args.count("--config")){std::ifstream f(args["--config"]);if(!f)throw std::runtime_error("configuration file missing");std::string key,val;while(f>>key>>val)if(!args.count("--"+key))args["--"+key]=val;}
        auto set=[&](const char* key,double& v){if(args.count(key))v=std::stod(args[key]);};
        if(args.count("--run"))p.run=std::stoi(args["--run"]);
        std::string runs=args.count("--runs")?args["--runs"]:"config/runs.csv";
        std::ifstream rf(runs);std::string row;std::getline(rf,row);bool found=false;
        while(std::getline(rf,row)){std::replace(row.begin(),row.end(),',',' ');std::istringstream s(row);int n;double A,C,E;std::string load;s>>n>>A>>C>>E>>load;if(n==p.run){p.A=A;p.C=C;p.E=E;p.fine=load=="fine";found=true;break;}}
        if(!found)throw std::runtime_error("run absent from configuration table");
        set("--dx",p.dx);set("--length",p.length);set("--width",p.width);set("--channel-width",p.channel_width);
        set("--A",p.A);set("--C",p.C);set("--E",p.E);set("--cfl",p.cfl);set("--max-dt",p.max_dt);
        set("--duration",p.duration);set("--migration-scale",p.migration_scale);set("--perturbation",p.perturbation);
        set("--qmin",p.qmin);set("--qmax",p.qmax);set("--tau-critical",p.tau_critical);
        set("--channel-chezy",p.channel_chezy);set("--floodplain-chezy",p.floodplain_chezy);
        set("--sand-d",p.sand_d);set("--silt-ws",p.silt_ws);set("--clay-d",p.clay_d);set("--diffusion-scale",p.diffusion_scale);
        set("--concentration-scale",p.concentration_scale);set("--porosity",p.porosity);set("--initial-depth",p.initial_depth);
        set("--stop-seconds",stop_seconds);
        if(args.count("--floods"))p.floods=std::stoi(args["--floods"]);
        if(args.count("--seed"))p.seed=std::stoi(args["--seed"]);
        if(args.count("--migration"))p.migration=std::stoi(args["--migration"]);
        if(args.count("--viscosity"))p.viscosity=std::stoi(args["--viscosity"]);
        if(args.count("--out"))output=args["--out"];
        if(args.count("--resume"))resume=std::stoi(args["--resume"]);
        if(!(p.dx>0&&p.channel_width>0&&p.duration>0&&p.cfl>0&&p.cfl<=.5&&p.max_dt>0&&p.porosity>=0&&p.porosity<1&&p.qmin>0&&p.qmax>=p.qmin&&p.floods>0))throw std::runtime_error("invalid simulation parameters");
        std::filesystem::create_directories(output);Model m(p);initialize(m);int first=resume?restart(m,output):0;
        if(!resume&&std::filesystem::exists(output+"/summary.csv"))throw std::runtime_error("output already exists: use a new directory or resume");
        if(resume) {
            // A crash after writing diagnostics but before atomically replacing the
            // checkpoint can leave a trailing uncheckpointed row. Regenerate it.
            for(const char* name:{"/summary.csv","/remap_budget.csv"}) {
                std::ifstream old(output+name);std::string line;std::vector<std::string> kept;
                if(std::getline(old,line))kept.push_back(line);
                while(std::getline(old,line))if(!line.empty()&&std::stoi(line.substr(0,line.find(',')))<=first)kept.push_back(line);
                old.close();std::ofstream clean(output+name);for(const auto& l:kept)clean<<l<<'\n';
            }
        }
        std::ofstream config(output+"/parameters.txt",resume?std::ios::app:std::ios::out);config<<std::setprecision(17);
        config<<"command";for(int i=0;i<argc;++i)config<<' '<<argv[i];config<<"\nrun "<<p.run<<"\nA "<<p.A<<"\nC "<<p.C<<"\nE "<<p.E<<"\nfine "<<p.fine<<"\ndx "<<p.dx<<"\nlength "<<p.length<<"\nwidth "<<p.width<<"\nduration "<<p.duration<<"\nfloods "<<p.floods<<"\nmigration_scale "<<p.migration_scale<<"\nseed "<<p.seed<<"\ntau_critical "<<p.tau_critical<<"\ncfl "<<p.cfl<<"\nmax_dt "<<p.max_dt<<"\n";config<<"channel_width "<<p.channel_width<<"\nslope "<<p.slope<<"\ninitial_depth "<<p.initial_depth
              <<"\nqmin "<<p.qmin<<"\nqmax "<<p.qmax<<"\nchannel_chezy "<<p.channel_chezy<<"\nfloodplain_chezy "<<p.floodplain_chezy
              <<"\nporosity "<<p.porosity<<"\nrho_s "<<p.rho_s<<"\nsand_d "<<p.sand_d<<"\nsilt_ws "<<p.silt_ws<<"\nclay_d "<<p.clay_d
              <<"\ndiffusion_scale "<<p.diffusion_scale<<"\nconcentration_scale "<<p.concentration_scale<<"\nperturbation "<<p.perturbation
              <<"\nmigration "<<p.migration<<"\nviscosity "<<p.viscosity<<"\n";config.close();
        std::ofstream summary(output+"/summary.csv",resume?std::ios::app:std::ios::out);
        std::ofstream remaps(output+"/remap_budget.csv",resume?std::ios::app:std::ios::out);
        if(!resume)summary<<"flood,alpha,interface_fraction,mean_water,beta,ridge_height,channel_depth,sinuosity,cutoffs,water_storage,water_residual,sediment_residual,bank_mass,steps,channel_steps,wall_seconds,solid_sediment_residual,recycled_mass,bed_forcing_mass\n";
        if(!resume)remaps<<"flood,water_transfer_residual,sand_transfer_residual,silt_transfer_residual,clay_transfer_residual,solid_transfer_residual,post_water_residual,post_sediment_residual,post_solid_sediment_residual,post_water_storage\n";
        remaps<<std::setprecision(16);
        summary<<std::setprecision(12);Budget initial=storage(m);double sediment_initial=std::accumulate(initial.sediment.begin(),initial.sediment.end(),0.);
        Budget ext_start=m.external;double dep_start=m.deposited_mass;
        double solid_initial=total_sediment_inventory(m),bank_start=m.bank_injected,bed_start=m.bed_external_mass;
        double water_correction_start=m.water_correction,mass_correction_start=m.mass_correction;
        // Simpson quadrature normalizes recycled-bank concentration by integral Q^(5/2).
        double integral=0;int nq=20000;
        for(int i=0;i<=nq;++i)integral+=(i==0||i==nq?1:i%2?4:2)*std::pow(hydrograph(p,p.duration*i/nq),2.5);
        integral*=p.duration/nq/3;
        auto start=std::chrono::steady_clock::now();
        for(int flood=first+1;flood<=p.floods;++flood) {
            bool save_fields=flood==1||flood==50||flood==61||flood==225||flood==251||flood==400||flood==501||flood==562||flood==580||flood==p.floods;
            std::fill(m.deposition.begin(),m.deposition.end(),0.);Metrics peak;double t=0;
            std::array<double,3> coeff;for(int k=0;k<3;++k)coeff[k]=std::max(0.,m.bank[k])/integral;
            while(t<p.duration-1e-8) {
                double dt=std::min(floodplain_rates(m),p.duration-t);
                if(t<.6*p.duration&&t+dt>.6*p.duration)dt=.6*p.duration-t;
                channel_advance(m,t,dt,coeff);floodplain_advance(m,dt);t+=dt;
                if(std::abs(t-.6*p.duration)<1e-6){
                    m.clock=(flood-1+.6)*p.duration;synchronize(m);peak=metrics(m);
                    if(save_fields)snapshot(m,output,flood,"peak_");
                }
                double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
                if(m.steps%1000==0) {
                    std::ofstream progress(output+"/progress.tmp");progress<<std::setprecision(16)
                      <<"{\"flood\":"<<flood<<",\"time_in_flood_seconds\":"<<t<<",\"duration_seconds\":"<<p.duration
                      <<",\"steps\":"<<m.steps<<",\"channel_steps\":"<<m.channel_steps<<",\"wall_seconds\":"<<wall<<"}\n";
                    progress.close();std::filesystem::rename(output+"/progress.tmp",output+"/progress.json");
                }
                if(wall>stop_seconds) {synchronize(m);snapshot(m,output,flood);std::ofstream status(output+"/status.txt");status<<"partial flood "<<flood<<" time_seconds "<<std::setprecision(15)<<t<<" of "<<p.duration<<"; observation-limited benchmark, no restart checkpoint\n";std::cout<<"benchmark_stop flood="<<flood<<" t="<<t<<" steps="<<m.steps<<" wall="<<wall<<std::endl;return 3;}
            }
            // The local loop ends exactly at the prescribed event boundary.
            // Avoid accumulation error in this output-only global clock.
            m.clock=flood*p.duration;
            synchronize(m);auto final=metrics(m);auto store=storage(m);
            double wr=store.water-initial.water-(m.external.water-ext_start.water)-(m.water_correction-water_correction_start);
            double sr=std::accumulate(store.sediment.begin(),store.sediment.end(),0.)-sediment_initial+m.deposited_mass-dep_start;
            for(int k=0;k<3;++k)sr-=m.external.sediment[k]-ext_start.sediment[k];
            sr-=m.mass_correction-mass_correction_start;
            double solid_residual=total_sediment_inventory(m)-solid_initial+m.bank_injected-bank_start-(m.bed_external_mass-bed_start);
            for(int k=0;k<3;++k)solid_residual-=m.external.sediment[k]-ext_start.sediment[k];
            solid_residual-=m.mass_correction-mass_correction_start;
            double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            summary<<flood<<','<<peak.alpha<<','<<peak.inundated_fraction<<','<<peak.mean_water<<','<<final.beta<<','<<final.ridge<<','<<final.channel_depth<<','<<final.sinuosity<<','<<m.cutoffs<<','<<store.water<<','<<wr<<','<<sr<<','<<std::accumulate(m.bank.begin(),m.bank.end(),0.)<<','<<m.steps<<','<<m.channel_steps<<','<<wall<<','<<solid_residual<<','<<m.bank_injected<<','<<m.bed_external_mass<<'\n';summary.flush();
            if(save_fields)snapshot(m,output,flood);
            std::cout<<"run="<<p.run<<" flood="<<flood<<" alpha="<<peak.alpha<<" beta="<<final.beta<<" sinuosity="<<final.sinuosity<<" steps="<<m.steps<<" wall="<<wall<<" water_residual="<<wr<<" sediment_residual="<<sr<<std::endl;
            double solid_before=total_sediment_inventory(m),bed_before=m.bed_external_mass;
            double wc_before=m.water_correction,mc_before=m.mass_correction;
            remap_after_flood(m,flood);auto after=storage(m);
            double dw=after.water-store.water,ds=0;
            double db=total_sediment_inventory(m)-solid_before-(m.bed_external_mass-bed_before);
            remaps<<flood<<','<<dw;
            for(int k=0;k<3;++k){double delta=after.sediment[k]-store.sediment[k];ds+=delta;remaps<<','<<delta;}
            remaps<<','<<db<<','<<wr+dw-(m.water_correction-wc_before)
                  <<','<<sr+ds-(m.mass_correction-mc_before)
                  <<','<<solid_residual+db-(m.mass_correction-mc_before)<<','<<after.water<<'\n';remaps.flush();
            checkpoint(m,output,flood);
        }
        std::ofstream status(output+"/status.txt");status<<"complete "<<p.floods<<" floods\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"ERROR: "<<e.what()<<std::endl;return 1;}
}
