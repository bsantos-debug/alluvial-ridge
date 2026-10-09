#!/usr/bin/env python3
"""Print completed first-flood grid sensitivity; never launch simulations or write data."""
import csv, hashlib, io, json, math, runpy, struct, sys
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
base=root/'tmp/full-rebuild-002/workspace/validation/runs'
method=root/'scripts/validate_runs.py'
lib=runpy.run_path(str(method),run_name='read_only_audit')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def csvrows(p):return list(csv.DictReader(io.StringIO(p.read_text())))
def image(p,prefix):
 h,v=lib['fields'](p/(prefix+'fields_0001.bin'))
 nx,ny,dx=h['nx'],h['ny'],h['dx'];N=nx*ny
 fp=[i for i in range(N) if v[4*i+3]==0];faces=0
 for j in range(ny):
  for i in range(nx):
   t=j*nx+i
   for u in ([t+1] if i+1<nx else [])+([t+nx] if j+1<ny else []):
    faces+=int(v[4*t+3]!=v[4*u+3])
 return {'clock_seconds':h['elapsed_seconds'],'channel_cells':N-len(fp),'bank_length_m':faces*dx,
  'wet_floodplain_area_m2':sum(v[4*i+1]>.001 for i in fp)*dx*dx,
  'floodplain_water_m3':math.fsum(v[4*i+1] for i in fp)*dx*dx,
  'deposit_bulk_m3':math.fsum(v[4*i+2] for i in fp)*dx*dx,
  'deposit_max_m':max(v[4*i+2] for i in fp)},(h,v)
def remapped(p,par,old):
 h,v=old;nx,ny,dx=h['nx'],h['ny'],h['dx'];N=nx*ny
 data=(p/'checkpoint.bin').read_bytes();at=0
 def get(fmt):
  nonlocal at
  a=struct.unpack_from('='+fmt,data,at);at+=struct.calcsize('='+fmt)
  return a[0] if len(a)==1 else a
 nbytes=get('Q');sig=data[at:at+nbytes].decode();at+=nbytes
 f=get('i');clock=get('d');steps=get('q');cs=get('q');cuts=get('i');ext=get('4d');bank=get('3d')
 dep,forcing,release,wcorr,mcorr=get('5d');n=get('Q')
 line=[get('2d') for _ in range(n)];ch=[get('6d') for _ in range(n)]
 z=[get('d') for _ in range(N)];q=[get('6d') for _ in range(N)]
 assert at==len(data) and sig.startswith('ridge-checkpoint-v2 ') and f==1 and clock==1728000
 assert release==wcorr==mcorr==0
 mask=[False]*N;r=par['channel_width']/2
 for a,b in zip(line,line[1:]):
  vx,vy=b[0]-a[0],b[1]-a[1];ll=vx*vx+vy*vy
  for j in range(max(0,int(math.floor((min(a[1],b[1])-r)/dx))),min(ny-1,int(math.floor((max(a[1],b[1])+r)/dx)))+1):
   for i in range(max(0,int(math.floor((min(a[0],b[0])-r)/dx))),min(nx-1,int(math.floor((max(a[0],b[0])+r)/dx)))+1):
    px,py=(i+.5)*dx-a[0],(j+.5)*dx-a[1];w=max(0.,min(1.,(px*vx+py*vy)/ll))
    if math.hypot(px-w*vx,py-w*vy)<=r:mask[j*nx+i]=True
 return {'new_channel_cells':sum(v[4*i+3]==0 and mask[i] for i in range(N)),
  'abandoned_channel_cells':sum(v[4*i+3]==1 and not mask[i] for i in range(N)),
  'bank_mass_kg':math.fsum(bank),'deposited_mass_kg':dep,'bed_forcing_mass_kg':forcing,
  'post_channel_nodes':n,'post_channel_min_h_m':min(x[0] for x in ch),
  'post_channel_max_h_m':max(x[0] for x in ch),
  'water_correction_m3':wcorr,'mass_correction_kg':mcorr,'cutoffs':cuts}
cases={}
for name in ('baseline250','coarse500'):
 p=base/name;s=json.loads((p/'process_status.json').read_text())
 assert s['state']=='complete' and s['exit_code']==0
 assert all(sha(p/f)==x for f,x in s['artifact_sha256'].items())
 a=lib['inspect_case'](p);assert a['state']=='complete'
 peak,unused=image(p,'peak_');end,old=image(p,'')
 assert peak['clock_seconds']==1036800 and end['clock_seconds']==1728000
 a.update(process=s,peak=peak,end=end,checkpoint=remapped(p,a['parameters'],old),
  remap={k:float(v) for k,v in csvrows(p/'remap_budget.csv')[0].items()})
 cases[name]=a
b,c=cases['baseline250'],cases['coarse500']
diff={k:[b['parameters'][k],c['parameters'][k]] for k in b['parameters'] if b['parameters'][k]!=c['parameters'][k]}
assert diff=={'dx':[250.,500.]}
assert b['process']['binary_sha256']==c['process']['binary_sha256']
out={'scope':'Completed first-flood sensitivity only; 250 m channel-node spacing held fixed.',
 'processor_sha256':sha(method),'parameter_differences':diff,'all_completed_artifact_hashes_verified':True,
 'coarse_relative_to_baseline_percent':{k:100*(c['metrics'][k]/b['metrics'][k]-1)
  for k in ('alpha','beta','ridge_height','channel_depth','water_storage')},
 'coarse_deposit_mass_change_percent':100*(c['checkpoint']['deposited_mass_kg']/b['checkpoint']['deposited_mass_kg']-1),
 'common_floodplain_fields':lib['compare_fields'](base/'baseline250',base/'coarse500'),'cases':cases}
text=json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
sys.stdout.write(text);sys.stderr.write('JSON_SHA256 '+hashlib.sha256(text.encode()).hexdigest()+'\n')
