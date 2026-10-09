#!/usr/bin/env python3
"""Read-only first-flood evidence; writes only beside this script; no model calls."""
import csv, datetime, hashlib, io, json, math, os, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT/'tmp/full-rebuild-002/workspace'
OUT = Path(__file__).resolve().parent
hashes = {}
def read(path):
    data=path.read_bytes()
    hashes[str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)]=hashlib.sha256(data).hexdigest()
    return data
def csvrows(path):
    return list(csv.DictReader(io.StringIO(read(path).decode())))
def js(path):
    return json.loads(read(path).decode())
def fields(folder,prefix):
    path=folder/(prefix+'fields_0001.bin')
    if not path.exists(): return None
    data=read(path); nx,ny,n,flood,dx,clock,slope=struct.unpack_from('=4i3d',data)
    assert len(data)==40+16*nx*ny
    rows=list(struct.iter_unpack('=4f',data[40:]))
    assert all(math.isfinite(x) for r in rows for x in r)
    assert all(r[3] in (0.,1.) for r in rows)
    channel=csvrows(folder/(prefix+'channel_0001.csv'))
    assert len(channel)==n
    values=[{k:float(v) for k,v in r.items()} for r in channel]
    assert all(math.isfinite(x) for r in values for x in r.values())
    fp=[r for r in rows if r[3]==0]
    mean=math.fsum(r[1] for r in fp)/len(fp)
    interface=wet=0
    for j in range(ny):
        for i in range(nx):
            a=j*nx+i
            for b in ([a+1] if i+1<nx else [])+([a+nx] if j+1<ny else []):
                if rows[a][3]==rows[b][3]: continue
                c,f=(a,b) if rows[a][3] else (b,a)
                interface+=1
                wet+=int(rows[f][1]>.001 and rows[c][0]+rows[c][1]-rows[f][0]>.001)
    frac=wet/interface if interface else 0
    water=math.fsum(r[1]*dx*dx for r in fp)+math.fsum(r['water_depth']*r['control_area'] for r in values)
    # A half-ulp bound for every serialized float32 depth plus a conservative
    # 12-significant-digit bound on each channel h and control area.
    bound=0
    for r in fp:
        bits=struct.unpack('=I',struct.pack('=f',r[1]))[0]
        upper=struct.unpack('=f',struct.pack('=I',bits+1))[0]
        bound+=(upper-r[1])*.5*dx*dx
    def bound12(x): return 0 if x==0 else .5*10**(math.floor(math.log10(abs(x)))-11)
    bound+=math.fsum(abs(r['control_area'])*bound12(r['water_depth'])+abs(r['water_depth'])*bound12(r['control_area']) for r in values)
    report=dict(nx=nx,ny=ny,nchan=n,flood=flood,dx_m=dx,clock_seconds=clock,
        expected_clock_seconds=.6*1728000 if prefix else 1728000,
        exact_expected_clock=clock==(.6*1728000 if prefix else 1728000),
        all_finite=True,min_h_m=min(r[1] for r in rows),max_h_m=max(r[1] for r in rows),
        min_deposit_m=min(r[2] for r in rows),max_deposit_m=max(r[2] for r in rows),
        channel_min_h_m=min(r['water_depth'] for r in values),channel_min_area_m2=min(r['control_area'] for r in values),
        channel_cells=sum(int(r[3]) for r in rows),floodplain_cells=len(fp),
        floodplain_water_m3=math.fsum(r[1]*dx*dx for r in fp),water_storage_from_saved_fields_m3=water,
        water_storage_rounding_bound_m3=bound,floodplain_bulk_deposit_m3=math.fsum(r[2]*dx*dx for r in fp),
        mean_water_from_saved_fields_m=mean,interface_faces=interface,wet_interface_faces=wet,
        interface_fraction_from_saved_fields=frac,alpha_from_saved_fields_m=mean/frac if frac else None)
    return report,rows,values

def checkpoint(folder,nx,ny):
    data=read(folder/'checkpoint.bin'); cursor=0
    def get(fmt):
        nonlocal cursor
        x=struct.unpack_from('='+fmt,data,cursor);cursor+=struct.calcsize('='+fmt)
        return x[0] if len(x)==1 else x
    length=get('Q'); signature=data[cursor:cursor+length].decode();cursor+=length
    flood=get('i');clock=get('d');steps=get('q');channel_steps=get('q');cutoffs=get('i')
    external=get('4d');bank=get('3d');deposited,bed_forcing,bank_injected,wcorr,mcorr=get('5d');n=get('Q')
    line=[get('2d') for _ in range(n)];channel=[get('6d') for _ in range(n)]
    z=[get('d') for _ in range(nx*ny)];q=[get('6d') for _ in range(nx*ny)]
    assert cursor==len(data)
    assert signature.startswith('ridge-checkpoint-v2 ')
    assert all(math.isfinite(x) for rows in (line,channel,q) for row in rows for x in row)
    assert all(math.isfinite(x) for x in z+list(bank)+list(external))
    # Reconstruct geometry masks and exact 1-D control areas from stored points.
    dx=500.;W=500.;radius=W/2
    s=[0.]
    for a,b in zip(line,line[1:]):s.append(s[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    areas=[.5*(s[min(i+1,n-1)]-s[max(i-1,0)])*W for i in range(n)]
    mask=[False]*(nx*ny)
    for a,b in zip(line,line[1:]):
        vx,vy=b[0]-a[0],b[1]-a[1];ll=vx*vx+vy*vy
        for j in range(max(0,int(math.floor((min(a[1],b[1])-radius)/dx))),min(ny-1,int(math.floor((max(a[1],b[1])+radius)/dx)))+1):
            for i in range(max(0,int(math.floor((min(a[0],b[0])-radius)/dx))),min(nx-1,int(math.floor((max(a[0],b[0])+radius)/dx)))+1):
                px,py=(i+.5)*dx-a[0],(j+.5)*dx-a[1]
                w=max(0.,min(1.,(px*vx+py*vy)/ll))
                if math.hypot(px-w*vx,py-w*vy)<=radius:mask[j*nx+i]=True
    store=[math.fsum(row[k]*dx*dx for i,row in enumerate(q) if not mask[i])+math.fsum(row[k]*a for row,a in zip(channel,areas)) for k in (0,3,4,5)]
    scalar_min={str(k):min([row[k] for row in q]+[row[k] for row in channel]) for k in (0,3,4,5)}
    return dict(signature=signature,flood=flood,clock_seconds=clock,steps=steps,channel_steps=channel_steps,cutoffs=cutoffs,
        all_finite=True,minimum_water_and_sediment_components=scalar_min,bank_mass_by_class_kg=bank,
        channel_min_h_m=min(row[0] for row in channel),channel_max_h_m=max(row[0] for row in channel),
        dry_channel_nodes=sum(row[0]==0 for row in channel),inlet_h_m=channel[0][0],
        external_water_and_classes=external,deposited_mass_kg=deposited,bed_forcing_mass_kg=bed_forcing,
        bank_injected_kg=bank_injected,water_correction_m3=wcorr,mass_correction_kg=mcorr,
        water_and_suspended_storage=store,channel_nodes=n,mapped_cells=sum(mask)),mask,line

report=dict(utc_observed=datetime.datetime.utcnow().isoformat()+'Z',scope='Read-only audit of independent full-first-flood diagnostics; coarse500 is sensitivity only, not a manuscript panel.')
production=js(STAGE/'data/_inputs/provenance.json')
validation=js(STAGE/'validation/runs/_inputs/provenance.json')
report['corrected_binary_sha256']=hashlib.sha256(read(STAGE/'data/_inputs/ridge')).hexdigest()
report['frozen_sources_verified']=all(hashlib.sha256(read(STAGE/'data/_inputs'/name)).hexdigest()==expected for name,expected in production['frozen_sha256'].items())
report['production_validation_binary_match']=production['binary_sha256']==validation['binary_sha256']==report['corrected_binary_sha256']
processes=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        if not (('ridge ' in argv or '/ridge-' in argv) and ('--run ' in argv)):continue
        st=(p/'stat').read_text().rsplit(')',1)[1].split()
        binary=hashlib.sha256((p/'exe').read_bytes()).hexdigest()
        processes.append(dict(pid=int(p.name),state=st[0],cpu_seconds=(int(st[11])+int(st[12]))/os.sysconf('SC_CLK_TCK'),
            start_ticks=int(st[19]),nice=int(st[16]),binary_sha256=binary,command=argv.strip()))
    except (OSError,ValueError):pass
report['live_model_processes']=processes
report['corrected_live_process_count']=sum(p['binary_sha256']==report['corrected_binary_sha256'] for p in processes)
report['legacy_live_process_count']=sum(p['binary_sha256']=='c723c3cf8656e7b8935a35d718fe469f4a90c5d0de65de62d2b24d546010632b' for p in processes)
case=STAGE/'validation/runs/coarse500'
report['corrected_coarse500_process_status']=js(case/'process_status.json')
report['corrected_coarse500_progress']=js(case/'progress.json')
peak=fields(case,'peak_')
report['corrected_coarse500_peak']=peak[0] if peak else None
end=fields(case,'')
report['corrected_coarse500_end']=end[0] if end else None
if (case/'status.txt').exists():report['corrected_coarse500_status']=read(case/'status.txt').decode().strip()
summary=csvrows(case/'summary.csv');remaps=csvrows(case/'remap_budget.csv')
report['corrected_coarse500_summary']=summary;report['corrected_coarse500_remaps']=remaps
if summary and remaps and end and (case/'checkpoint.bin').exists():
    saved,post_mask,new_line=checkpoint(case,end[0]['nx'],end[0]['ny']);report['corrected_coarse500_checkpoint']=saved
    s={k:float(v) for k,v in summary[-1].items()};r={k:float(v) for k,v in remaps[-1].items()}
    metrics={k:peak[0][key]-s[k] for k,key in [('alpha','alpha_from_saved_fields_m'),('mean_water','mean_water_from_saved_fields_m'),('interface_fraction','interface_fraction_from_saved_fields')]}
    metrics['saved_water_minus_summary_m3']=end[0]['water_storage_from_saved_fields_m3']-s['water_storage']
    metrics['saved_water_rounding_bound_m3']=end[0]['water_storage_rounding_bound_m3']
    metrics['checkpoint_water_minus_postremap_storage_m3']=saved['water_and_suspended_storage'][0]-r['post_water_storage']
    metrics['post_water_ledger_identity_m3']=r['post_water_residual']-(s['water_residual']+r['water_transfer_residual'])
    metrics['post_suspended_ledger_identity_kg']=r['post_sediment_residual']-(s['sediment_residual']+sum(r[k+'_transfer_residual'] for k in ('sand','silt','clay')))
    metrics['post_solid_ledger_identity_kg']=r['post_solid_sediment_residual']-(s['solid_sediment_residual']+r['solid_transfer_residual'])
    metrics['abandoned_raster_cells']=sum(old[3]==1 and not new for old,new in zip(end[1],post_mask))
    metrics['new_channel_raster_cells']=sum(old[3]==0 and new for old,new in zip(end[1],post_mask))
    old_line=[(row['x'],row['y']) for row in end[2]]
    assert all(b[0]>a[0] for line in (old_line,new_line) for a,b in zip(line,line[1:]))
    assert old_line[0][0]==new_line[0][0] and old_line[-1][0]==new_line[-1][0]
    knots=sorted(set([p[0] for p in old_line]+[p[0] for p in new_line]))
    def interpolate(line):
        values=[];j=0
        for x in knots:
            while j+1<len(line)-1 and line[j+1][0]<x:j+=1
            a,b=line[j],line[j+1];f=(x-a[0])/(b[0]-a[0]);values.append(a[1]+f*(b[1]-a[1]))
        return values
    old_y,new_y=interpolate(old_line),interpolate(new_line)
    delta=[b-a for a,b in zip(old_y,new_y)]
    absolute=squared=0.
    for x0,x1,a,b in zip(knots,knots[1:],delta,delta[1:]):
        span=x1-x0;squared+=span*(a*a+a*b+b*b)/3
        absolute+=span*(abs(a)+abs(b))/2 if a*b>=0 else span*(a*a+b*b)/(2*(abs(a)+abs(b)))
    length=knots[-1]-knots[0]
    metrics['lateral_change_at_fixed_x']={'method':'Piecewise-linear old and new y(x), common union of all x knots; exact valley-length integrals. Shape change, not material-node trajectories.',
        'both_x_monotone':True,'mean_absolute_m':absolute/length,'rms_m':math.sqrt(squared/length),
        'max_absolute_m':max(map(abs,delta)),
        'old_lateral_extent_m':max(p[1] for p in old_line)-min(p[1] for p in old_line),
        'new_lateral_extent_m':max(p[1] for p in new_line)-min(p[1] for p in new_line),
        'area_between_centerlines_m2':absolute,
        'new_raster_channel_area_m2':metrics['new_channel_raster_cells']*500**2}
    waterin=1728000*(2500+15000)/2
    n=20000;T=1728000.
    sedin=math.fsum((1 if i in (0,n) else 4 if i%2 else 2)*(.001*.003*(2500+12500*math.sin(math.pi*i/n)**2)**2.5) for i in range(n+1))*T/n/3
    metrics['prescribed_upstream_water_m3']=waterin;metrics['prescribed_upstream_sediment_kg']=sedin
    for key in ('water_residual','sediment_residual','solid_sediment_residual'):
        metrics[key+'_relative_to_prescribed_input']=s[key]/(waterin if key=='water_residual' else sedin)
    report['corrected_coarse500_crosschecks']=metrics
report['legacy_pre_remap_byte_comparison']={name: read(case/name)==read(ROOT/'validation/runs/coarse500'/name) for name in ('fields_0001.bin','channel_0001.csv')}
report['other_case_states']={}
for label,folder in [('corrected_baseline250',STAGE/'validation/runs/baseline250'),('corrected_fine125',STAGE/'validation/runs/fine125'),('legacy_baseline',ROOT/'tmp/full_flood_v4'),('legacy_coarse500',ROOT/'validation/runs/coarse500'),('legacy_fine125',ROOT/'validation/runs/fine125'),('legacy_time250_cfl02',ROOT/'validation/runs/time250_cfl02')]:
    x={}
    for name in ('process_status.json','progress.json'):
        if (folder/name).exists():x[name]=js(folder/name)
    if (folder/'summary.csv').exists():x['summary_rows']=len(csvrows(folder/'summary.csv'))
    if (folder/'status.txt').exists():x['status']=read(folder/'status.txt').decode().strip()
    report['other_case_states'][label]=x
read(Path(__file__).resolve())
report['input_sha256']=hashes
(OUT/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:report[k] for k in ('utc_observed','corrected_live_process_count','legacy_live_process_count','frozen_sources_verified','production_validation_binary_match')}))
print(json.dumps(report.get('corrected_coarse500_crosschecks',{'coarse500_terminal':False})))
