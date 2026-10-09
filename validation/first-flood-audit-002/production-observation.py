#!/usr/bin/env python3
"""Observe live first-flood checkpoints; prints JSON and never alters model data.

Pass the frozen workspace path. This is a time-specific observation: it refuses
later checkpoints or exited processes rather than relabeling their state.
"""
import csv,datetime,hashlib,io,json,math,struct,sys
from pathlib import Path
import numpy as np
W=Path(sys.argv[1]).resolve(); D=W/"data"; hashes={}; records=[]
def read(p):
 a=p.stat(); b=p.read_bytes(); c=p.stat()
 assert (a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(c.st_ino,c.st_size,c.st_mtime_ns,c.st_ctime_ns),str(p)
 hashes[str(p.relative_to(W))]=hashlib.sha256(b).hexdigest()
 return b
def rows(b): return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(io.StringIO(b.decode()))]
def identity(pid):
 s=Path("/proc/%d/stat"%pid).read_text().rsplit(") ",1)[1].split()
 return s[0],s[19]
def geometry(line,nx,ny,dx,width):
 s=[0.]
 for a,b in zip(line,line[1:]):s.append(s[-1]+math.hypot(*(b-a)))
 areas=np.array([.5*(s[min(i+1,len(line)-1)]-s[max(i-1,0)])*width for i in range(len(line))])
 mask=np.zeros(nx*ny,dtype=bool); R=width/2
 for a,b in zip(line,line[1:]):
  vx,vy=b-a; ll=vx*vx+vy*vy; assert ll>0
  i0=max(0,int(math.floor((min(a[0],b[0])-R)/dx)));i1=min(nx-1,int(math.floor((max(a[0],b[0])+R)/dx)))
  j0=max(0,int(math.floor((min(a[1],b[1])-R)/dx)));j1=min(ny-1,int(math.floor((max(a[1],b[1])+R)/dx)))
  for j in range(j0,j1+1):
   for i in range(i0,i1+1):
    px,py=(i+.5)*dx-a[0],(j+.5)*dx-a[1];t=max(0.,min(1.,(px*vx+py*vy)/ll))
    if math.hypot(px-t*vx,py-t*vy)<=R:mask[j*nx+i]=True
 return mask,areas,s[-1]
suite=json.loads(read(D/"suite_manifest.json"));provenance=suite["provenance"]
for name,h in provenance["frozen_sha256"].items():assert hashlib.sha256(read(D/"_inputs"/name)).hexdigest()==h
sigkeys=("length width dx channel_width slope initial_depth duration qmin qmax channel_chezy floodplain_chezy A C E migration_scale perturbation cfl max_dt porosity rho_s tau_critical sand_d silt_ws clay_d diffusion_scale concentration_scale seed run fine migration viscosity").split()
for run in range(1,32):
 F=D/("run%02d"%run);status=json.loads(read(F/"process_status.json"));pid=status["pid"]
 state,ticks=identity(pid);assert state not in ("Z","X") and ticks==status["process_start_ticks"]
 assert hashlib.sha256(Path("/proc/%d/exe"%pid).read_bytes()).hexdigest()==provenance["binary_sha256"]
 argv=Path("/proc/%d/cmdline"%pid).read_bytes().decode().strip("\0").split("\0")
 assert argv[argv.index("--out")+1]==str(F)
 p={k:float(v) for k,v in (x.split(" ",1) for x in read(F/"parameters.txt").decode().splitlines()) if k!="command"}
 hist=rows(read(F/"summary.csv"));remaps=rows(read(F/"remap_budget.csv"))
 assert [r["flood"] for r in hist]==[1.] and [r["flood"] for r in remaps]==[1.]
 assert all(math.isfinite(v) for r in hist+remaps for v in r.values())
 a,b=hist[0],remaps[0]
 for prefix,time in [("",1728000.),("peak_",1036800.)]:
  raw=read(F/(prefix+"fields_0001.bin"));nx,ny,n0,nf,dx,clock,slope=struct.unpack_from("=4i3d",raw)
  v=np.frombuffer(raw,dtype=np.float32,offset=40).reshape((-1,4))
  assert nf==1 and clock==time and len(raw)==40+16*nx*ny and dx==p["dx"]
  assert nx*dx==p["length"] and ny*dx==p["width"] and slope==p["slope"]
  assert np.isfinite(v).all() and (v[:,1:3]>=0).all() and np.isin(v[:,3],[0.,1.]).all()
  ch=rows(read(F/(prefix+"channel_0001.csv")))
  assert len(ch)==n0 and all(math.isfinite(x) for r in ch for x in r.values())
  assert all(r["water_depth"]>0 and r["control_area"]>0 for r in ch)
  if not prefix:oldmask=v[:,3].astype(bool);endfields=v
 cp=read(F/"checkpoint.bin");sz=struct.unpack_from("=Q",cp)[0];signature=cp[8:8+sz].decode().split()
 assert signature[0]=="ridge-checkpoint-v2" and list(map(float,signature[1:]))==[p[k] for k in sigkeys]
 at=8+sz;fmt="=idqqi4d3d5dQ";h=struct.unpack_from(fmt,cp,at);at+=struct.calcsize(fmt)
 assert h[0]==1 and h[1]==1728000 and h[2]==a["steps"] and h[3]==a["channel_steps"]
 n=h[-1];external=np.array(h[5:9]);bank=np.array(h[9:12]);dep,forcing,recycled,wcorr,mcorr=h[12:17]
 line=np.frombuffer(cp,dtype=np.float64,count=2*n,offset=at).reshape((n,2));at+=16*n
 channel=np.frombuffer(cp,dtype=np.float64,count=6*n,offset=at).reshape((n,6));at+=48*n
 z=np.frombuffer(cp,dtype=np.float64,count=nx*ny,offset=at);at+=8*nx*ny
 q=np.frombuffer(cp,dtype=np.float64,count=6*nx*ny,offset=at).reshape((-1,6));at+=48*nx*ny
 assert at==len(cp) and all(np.isfinite(x).all() for x in [line,channel,z,q,external,bank])
 assert (channel[:,[0,3,4,5]]>=0).all() and (q[:,[0,3,4,5]]>=0).all() and (bank>=0).all()
 mask,areas,length=geometry(line,nx,ny,dx,p["channel_width"])
 storage=np.array([math.fsum(q[~mask,k]*dx*dx)+math.fsum(channel[:,k]*areas) for k in [0,3,4,5]])
 Qin=p["duration"]*(p["qmin"]+p["qmax"])/2;N=20000
 Sin=math.fsum((1 if i in (0,N) else 4 if i%2 else 2)*(p["qmin"]+(p["qmax"]-p["qmin"])*math.sin(math.pi*i/N)**2)**2.5 for i in range(N+1))*p["duration"]/N/3*p["C"]*p["concentration_scale"]
 r=dict(run=run,pid=pid,start_ticks=ticks,completed_floods=1,checkpoint_nodes=n,cutoffs=h[4],
  captured_cells=int(np.count_nonzero(mask&~oldmask)),abandoned_cells=int(np.count_nonzero(oldmask&~mask)),
  bank_mass=math.fsum(bank),water_correction=wcorr,mass_correction=mcorr,recycled_mass=recycled,bed_forcing_mass=forcing,
  min_channel_h=float(channel[:,0].min()),max_channel_h=float(channel[:,0].max()),post_sinuosity=length/p["length"],
  checkpoint_water_minus_post_ledger=storage[0]-b["post_water_storage"],
  reconstructed_sediment_minus_post_ledger=math.fsum(storage[1:])+dep-math.fsum(external[1:])-mcorr-b["post_sediment_residual"],
  water_ledger_identity_error=b["post_water_residual"]-(a["water_residual"]+b["water_transfer_residual"]),
  sediment_ledger_identity_error=b["post_sediment_residual"]-(a["sediment_residual"]+sum(b[k+"_transfer_residual"] for k in ["sand","silt","clay"])),
  solid_ledger_identity_error=b["post_solid_sediment_residual"]-(a["solid_sediment_residual"]+b["solid_transfer_residual"]),
  alpha=a["alpha"],beta=a["beta"],ridge_height=a["ridge_height"],bankfull_depth=a["channel_depth"],
  maximum_event_deposit=float(endfields[~oldmask,2].max()),bulk_event_deposit=math.fsum(float(x)*dx*dx for x in endfields[~oldmask,2]))
 for k in ["water_residual","sediment_residual","solid_sediment_residual"]:r[k]=a[k]
 for k in ["water_transfer_residual","sand_transfer_residual","silt_transfer_residual","clay_transfer_residual","solid_transfer_residual","post_water_residual","post_sediment_residual","post_solid_sediment_residual"]:r[k]=b[k]
 for k in ["post_water_residual","post_sediment_residual","post_solid_sediment_residual"]:r[k+"_relative_input"]=abs(b[k])/(Qin if k=="post_water_residual" else Sin)
 progress=json.loads((F/"progress.json").read_text());r["progress_flood"]=progress["flood"];r["progress_days"]=progress["time_in_flood_seconds"]/86400
 assert identity(pid)[1]==ticks
 records.append(r)
numeric=[k for k in records[0] if k not in ["run","pid","start_ticks"]]
ranges={k:dict(min=min((r[k],r["run"]) for r in records),max=max((r[k],r["run"]) for r in records)) for k in numeric}
print(json.dumps(dict(utc=datetime.datetime.utcnow().isoformat()+"Z",scope="31 corrected production first floods; snapshots before remap, checkpoints after remap; later flood evolution incomplete.",
 binary_sha256=provenance["binary_sha256"],all_live_identity_checks_passed=True,all_finite_positivity_signature_checks_passed=True,
 ranges=ranges,records=records,input_sha256=hashes),indent=2,allow_nan=False))
